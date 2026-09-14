"""Adapter describe-surface cache: resolve, disk load, merge (M2 row 3).

The offline half of the describe cache. Given a cache directory, resolve a
metric or property key for an (adapter_kind, resource_kind) pair from the
JSON file ``<cache_dir>/<adapter_kind>/<resource_kind>.json``, and merge a
live section into a cached one (``_merge_section``). Nothing here knows
where the factory keeps its cache, reads credentials, or calls an instance:
``vcfcf_packaging.describe`` is the factory side that defaults the cache
directory to ``knowledge/context/adapter_describe_cache/``, attaches a
client, and does the network refresh.

At build time the cache is the authoritative source for:
  - whether a metric key exists on a given adapter/resource-kind pair
  - whether that metric is ``defaultMonitored`` (collected out-of-the-box)

Cache file layout::

    {
      "adapter_kind": "VMWARE",
      "resource_kind": "VirtualMachine",
      "fetched_at": "2026-04-16T12:00:00Z",
      "source": "https://host/suite-api/api/adapterkinds/VMWARE/...",
      "metrics": {
        "net|packetsPerSec": {
          "name": "Network|Packets per second",
          "default_monitored": false
        }
      },
      "properties": {
        "summary|guest|toolsVersion": {
          "name": "Guest OS|Tools Version",
          "default_monitored": true,
          "instance_type": "INSTANCED"
        }
      }
    }

The ``properties`` section is optional, existing cache files without it are
valid.  ``default_monitored`` / ``instance_type`` are the real values
returned by the ``/properties`` endpoint for that key (see
``knowledge/context/investigations/adapter_describe_exploration.md``, the
endpoint returns the *same* schema as ``/statkeys``, only the ``property``
discriminator differs, so properties are **not** always
``defaultMonitored: true``).  Cache files written by ``refresh()`` before
this fields were added carry only ``{"name": ...}`` per property; those
legacy entries fall back to ``default_monitored=True`` when resolved (see
``resolve_metric()``) until the cache is refreshed against a live instance,
which emits a one-time WARN per (adapter_kind, resource_kind) pair the first
time that legacy fallback is taken. Run
``python3 -m vcfcf_packaging refresh-describe`` with a live instance to
populate/upgrade the properties section.

Merge semantics (issue #143)
----------------------------

``refresh()`` (on the factory subclass) MERGES the live response into the
existing cache file, it does not replace it.  One cache file may be grounded
on more than one platform release (for example VMWARE/HostSystem.json is the
union of a 9.x lab and an 8.18 instance), and a single instance never reports
the whole union.

  - key present in the live response: entry is updated (name /
    default_monitored / instance_type taken from the live instance)
  - key absent from the live response: entry is RETAINED unchanged.  The
    first refresh from a given host that leaves keys retained emits a WARN
    naming every one; later refreshes from the same host that leave the
    same set print a single count line instead (by exception).  The set
    itself is persisted in the host's ``merged_from`` entry, see below.

A platform key is only ever removed when the caller explicitly asks for
it: ``refresh(..., prune=True)`` (CLI: ``refresh-describe --prune``).  Prune
drops every key absent from the live response, which re-grounds the file on
that one instance.  Silent removal is never performed; the build-time
auto-refresh paths (``audit.py``, ``cli.py analyze``) always merge.

The one exception is instance-local ``Super Metric|sm_<uuid>`` keys.  Those
are one instance's own super metric set, not the adapter's describe
surface, and caching them would let a bundle that references another lab's
SM pass the existence gate.  They are never imported from the live
response, and any already present in a cached section are dropped on every
refresh (reported in a WARN with the key list).

Provenance: every refresh appends or updates in place (matched by source
host) a ``merged_from`` entry with ``role: refresh``, ``source``,
``fetched_at``, per-section ``counts`` and the ``retained_absent`` key
lists, so the file records which keys each instance did not report.
Hand-written ``merged_from`` entries (``role`` primary / additive) and any
other top-level key the refresh does not own (``merge_note``, ...) are
carried through unchanged.  ``fetched_at`` and ``source`` always describe
the most recent refresh.

Corrupt cache file: refresh raises ``DescribeCacheError`` naming the
recovery (delete the file and re-run ``refresh-describe``, or pass
``--prune`` to overwrite it).  With ``prune=True`` the corrupt file is
overwritten with the live response after a WARN.

Each refresh prints one by-exception summary line: per section (metrics and
properties) the total plus only the non-zero deltas, keys added, updated
(value changed), retained-but-absent, pruned, and dropped-instance-local.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class MetricInfo:
    """Resolved metadata for a single stat key."""
    key: str
    name: str
    default_monitored: bool
    adapter_kind: str
    resource_kind: str


# ---------------------------------------------------------------------------
# Cache helper
# ---------------------------------------------------------------------------

class DescribeCacheError(RuntimeError):
    pass


class DescribeCache:
    """Describe-surface cache backed by JSON files under ``cache_dir``.

    Args:
        cache_dir: Root directory for cache files, required. The factory
            subclass (``vcfcf_packaging.describe.DescribeCache``) defaults it
            to ``knowledge/context/adapter_describe_cache/`` and adds the live
            ``refresh()`` / ``refresh_all()`` on top; this class only reads.
    """

    def __init__(self, cache_dir: "str | Path") -> None:
        if cache_dir is None or str(cache_dir) == "":
            raise TypeError("DescribeCache: cache_dir is required (a directory path)")
        self._cache_dir = Path(cache_dir)
        # In-memory layer: (adapter_kind, resource_kind) -> dict[key, MetricInfo]
        self._cache: dict[tuple[str, str], dict[str, MetricInfo]] = {}
        # Properties layer: (adapter_kind, resource_kind) -> dict[key, meta dict].
        # Populated from the "properties" section of each cache JSON file.
        # meta dict carries "default_monitored" (bool) and "instance_type" (str)
        # when present.  Older cache files written before this field existed
        # only carry {"name": ...} per property; for those, default_monitored
        # is treated as True (legacy shortcut, preserved for byte-for-byte
        # backward compatibility until the cache is refreshed).
        # When empty/absent, property lookups are skipped (no false positives).
        self._props: dict[tuple[str, str], dict[str, dict]] = {}
        # Kind pairs for which the legacy name-only property shortcut
        # (default_monitored missing -> assumed True) has already emitted its
        # one-shot WARN. Prevents a WARN-per-property flood on a cache file
        # with hundreds of legacy entries.
        self._legacy_prop_warned: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------ load

    def _cache_path(self, adapter_kind: str, resource_kind: str) -> Path:
        return self._cache_dir / adapter_kind / f"{resource_kind}.json"

    def _load_from_disk(self, adapter_kind: str, resource_kind: str) -> bool:
        """Load a cache file into memory.  Returns True if the file exists."""
        p = self._cache_path(adapter_kind, resource_kind)
        if not p.exists():
            return False
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise DescribeCacheError(
                f"describe cache file {p} is corrupt: {exc}"
            ) from exc
        metrics: dict[str, MetricInfo] = {}
        for key, meta in (raw.get("metrics") or {}).items():
            metrics[key] = MetricInfo(
                key=key,
                name=meta.get("name", key),
                default_monitored=bool(meta.get("default_monitored", False)),
                adapter_kind=adapter_kind,
                resource_kind=resource_kind,
            )
        self._cache[(adapter_kind, resource_kind)] = metrics

        # Load properties section (optional, older cache files omit it)
        props_raw = raw.get("properties") or {}
        self._props[(adapter_kind, resource_kind)] = dict(props_raw)

        return True

    # ----------------------------------------------------------------- query

    def resolve_metric(
        self,
        adapter_kind: str,
        resource_kind: str,
        metric_key: str,
    ) -> Optional[MetricInfo]:
        """Return MetricInfo for a key, or None if it is not in the cache.

        Loads the cache file lazily on first access for each kind pair.
        Does NOT perform a live refresh; the factory subclass's ``refresh()``
        rewrites the file and calls ``invalidate()`` here.

        Raises DescribeCacheError if the cache file exists but is corrupt, or
        if the kind pair has no cache file at all (caller must check for None
        vs. absence-vs-corrupt).  Actually: if no cache file exists, returns
        None to allow the caller to fail with a friendlier message.
        """
        pair = (adapter_kind, resource_kind)
        if pair not in self._cache:
            found = self._load_from_disk(adapter_kind, resource_kind)
            if not found:
                # No cache file, return sentinel None; caller decides severity.
                self._cache[pair] = {}  # mark as "attempted but missing"
        result = self._cache.get(pair, {}).get(metric_key)
        if result is not None:
            return result
        # Not found in metrics cache.  Check the properties cache, if this key
        # is a known property (e.g. summary|guest|toolsVersion) return a
        # MetricInfo using the property's own defaultMonitored value from the
        # describe API.  Properties are NOT always defaultMonitored=true,
        # e.g. VMWARE property counts across VM/HostSystem/Cluster/Datastore
        # show a real mix (see knowledge/context/investigations/
        # adapter_describe_exploration.md). Cache files written before this
        # field was persisted fall back to True (legacy shortcut) until the
        # cache is refreshed against a live instance.
        props = self._props.get(pair, {})
        if metric_key in props:
            meta = props[metric_key] or {}
            if "default_monitored" not in meta and pair not in self._legacy_prop_warned:
                self._legacy_prop_warned.add(pair)
                print(
                    f"  WARN: {adapter_kind}/{resource_kind} describe cache has "
                    f"legacy name-only property entries (no persisted "
                    f"default_monitored), properties are guessed as "
                    f"defaultMonitored=true, which is wrong for a real fraction "
                    f"of them on some resource kinds. Run "
                    f"'python3 -m vcfcf_packaging refresh-describe "
                    f"--kind {adapter_kind}:{resource_kind}' against a live "
                    f"instance to get the real per-property flag.",
                    file=sys.stderr,
                )
            return MetricInfo(
                key=metric_key,
                name=meta.get("name", metric_key),
                default_monitored=bool(meta.get("default_monitored", True)),
                adapter_kind=adapter_kind,
                resource_kind=resource_kind,
            )
        return None

    def has_cache_file(self, adapter_kind: str, resource_kind: str) -> bool:
        """Return True if a cache file exists for this kind pair."""
        return self._cache_path(adapter_kind, resource_kind).exists()

    def invalidate(self, adapter_kind: str, resource_kind: str) -> None:
        """Drop the in-memory layers for a kind pair so the next
        ``resolve_metric`` reloads the file (called after a refresh)."""
        self._cache.pop((adapter_kind, resource_kind), None)
        self._props.pop((adapter_kind, resource_kind), None)

    # --------------------------------------------------------------- refresh

# Merge helpers (issue #143)
# ---------------------------------------------------------------------------


_INSTANCE_LOCAL_PREFIX = "Super Metric|"


def _is_instance_local(key: str) -> bool:
    """True for ``Super Metric|sm_<uuid>`` keys: one instance's own SM set,
    not part of the adapter describe surface (review W4 on issue #143)."""
    return key.startswith(_INSTANCE_LOCAL_PREFIX)


def _host_of(url: str) -> str:
    """Host portion of a source URL, for matching merged_from entries."""
    rest = url.split("://", 1)[-1]
    return rest.split("/", 1)[0]


@dataclass
class MergeStats:
    """Outcome of merging one live section (metrics or properties)."""
    added: list[str]
    updated: list[str]
    unchanged: list[str]
    retained: list[str]        # cached, absent from live, kept (prune=False)
    pruned: list[str]          # cached, absent from live, removed (prune=True)
    dropped_local: list[str]   # cached instance-local keys, always removed


def _counts(stats: MergeStats) -> dict[str, int]:
    return {
        "added": len(stats.added),
        "updated": len(stats.updated),
        "unchanged": len(stats.unchanged),
        "retained": len(stats.retained),
        "pruned": len(stats.pruned),
        "dropped_instance_local": len(stats.dropped_local),
    }


def _merge_section(
    existing: dict[str, dict],
    live: dict[str, dict],
    prune: bool = False,
) -> tuple[dict[str, dict], MergeStats]:
    """Merge ``live`` into ``existing``.

    Live entries win on collision.  Keys only in ``existing`` are retained
    unless ``prune`` is True.  Instance-local ``Super Metric|`` keys are
    dropped from ``existing`` unconditionally (``live`` never carries them,
    ``refresh()`` filters them at parse time).  Returns the merged dict and
    the stats.
    """
    stats = MergeStats([], [], [], [], [], [])
    merged: dict[str, dict] = {}
    for key, meta in existing.items():
        if key in live:
            continue
        if _is_instance_local(key):
            stats.dropped_local.append(key)
        elif prune:
            stats.pruned.append(key)
        else:
            stats.retained.append(key)
            merged[key] = meta
    for key, meta in live.items():
        if key not in existing:
            stats.added.append(key)
        elif existing[key] != meta:
            stats.updated.append(key)
        else:
            stats.unchanged.append(key)
        merged[key] = meta
    for lst in (
        stats.added, stats.updated, stats.unchanged,
        stats.retained, stats.pruned, stats.dropped_local,
    ):
        lst.sort()
    return merged, stats


def _summarize(stats: MergeStats) -> str:
    """By-exception summary fragment: only the non-zero deltas, or ""."""
    parts = []
    for label, lst in (
        ("added", stats.added),
        ("updated", stats.updated),
        ("retained-but-absent", stats.retained),
        ("pruned", stats.pruned),
        ("dropped-instance-local", stats.dropped_local),
    ):
        if lst:
            parts.append(f"{len(lst)} {label}")
    return f" [{', '.join(parts)}]" if parts else ""
