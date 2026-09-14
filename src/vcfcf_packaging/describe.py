"""Adapter describe-surface cache + query helper.

Queries ``/api/adapterkinds/<kind>/resourcekinds/<rk>/statkeys`` on a live
VCF Ops instance and persists the results in a JSON file under
``knowledge/context/adapter_describe_cache/<adapter_kind>/<resource_kind>.json``.

At build time the cache is the authoritative source for:
  - whether a metric key exists on a given adapter/resource-kind pair
  - whether that metric is ``defaultMonitored`` (collected out-of-the-box)

If env vars are present (VCFOPS_HOST/USER/PASSWORD) the cache is refreshed
automatically for every (adapter_kind, resource_kind) pair referenced in the
bundle being built.  Pass ``live=False`` to force offline/cache-only mode.

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

``refresh()`` MERGES the live response into the existing cache file, it does
not replace it.  One cache file may be grounded on more than one platform
release (for example VMWARE/HostSystem.json is the union of a 9.x lab and an
8.18 instance), and a single instance never reports the whole union.

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
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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

# Cache root is repo-relative so it's always findable regardless of cwd.
_REPO_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_CACHE_ROOT = _REPO_ROOT / "knowledge" / "context" / "adapter_describe_cache"


class DescribeCacheError(RuntimeError):
    pass


class DescribeCache:
    """Describes-surface cache.  Backed by JSON files; optionally live-refreshed.

    Args:
        cache_dir: Root directory for cache files.  Defaults to
            ``knowledge/context/adapter_describe_cache/`` relative to the repo root.
        client: Optional ``VCFOpsClient`` instance.  Required for
            ``refresh()`` / ``refresh_all()``.  Pass ``None`` for offline use.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        client=None,
    ) -> None:
        self._cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_ROOT
        self._client = client
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
        Does NOT perform a live refresh, call ``refresh()`` explicitly.

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

    # --------------------------------------------------------------- refresh

    def refresh(
        self,
        adapter_kind: str,
        resource_kind: str,
        prune: bool = False,
    ) -> None:
        """Fetch statkeys from the live instance and merge into the cache file.

        Requires a client to have been supplied at construction time.

        Keys present in the live response are updated; keys absent from it
        are retained unless ``prune=True``, in which case they are removed.
        Instance-local ``Super Metric|`` keys are never imported and are
        dropped from the cached sections on every refresh.  See the module
        docstring, "Merge semantics".

        Endpoint: ``GET /api/adapterkinds/<ak>/resourcekinds/<rk>/statkeys``
        Response shape (observed on VCF Ops 9.0.2)::

            {
              "statKey": [
                {
                  "key": "cpu|usage_average",
                  "name": "CPU|Usage (%)",
                  "defaultMonitored": true,
                  ...
                },
                ...
              ]
            }
        """
        if self._client is None:
            raise DescribeCacheError(
                "DescribeCache.refresh() requires a client, "
                "construct with client=VCFOpsClient.from_env()"
            )

        pair_label = f"{adapter_kind}/{resource_kind}"
        cache_path = self._cache_path(adapter_kind, resource_kind)

        # Load the existing file once, up front: the merge, the #75
        # failed-properties path and the provenance update all read it.
        existing_doc: dict = {}
        if cache_path.exists():
            try:
                existing_doc = json.loads(cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                if prune:
                    # Explicit re-ground: nothing to retain from an unreadable
                    # file, so overwrite it with the live response.
                    print(
                        f"  WARN: describe cache file {cache_path} is corrupt "
                        f"({exc}); --prune given, overwriting with the live "
                        f"response.",
                        file=sys.stderr,
                    )
                    existing_doc = {}
                else:
                    raise DescribeCacheError(
                        f"describe cache file {cache_path} is corrupt: {exc}. "
                        f"Nothing can be merged into it. Recovery: delete the "
                        f"file and re-run 'python3 -m vcfcf_packaging "
                        f"refresh-describe --kind {adapter_kind}:{resource_kind}', "
                        f"or re-run with --prune to overwrite it (any keys "
                        f"another instance contributed are lost either way)."
                    ) from exc
            if not isinstance(existing_doc, dict):
                existing_doc = {}

        url_path = (
            f"/api/adapterkinds/{adapter_kind}/resourcekinds/{resource_kind}/statkeys"
        )
        # Use the client's _request helper which handles auth.
        resp = self._client._request("GET", url_path)
        if resp.status_code != 200:
            raise DescribeCacheError(
                f"statkeys fetch failed for {adapter_kind}/{resource_kind} "
                f"({resp.status_code}): {resp.text[:300]}"
            )

        body = resp.json()

        # Observed response key on VCF Ops 9.0.2 lab instance:
        #   "resourceTypeAttributes", 929 entries for VMWARE/VirtualMachine
        # Earlier drafts expected "statKey" / "statKeys" (from API schema);
        # the live instance uses "resourceTypeAttributes".  Try all known
        # variants so we stay compatible across releases.
        stat_list = (
            body.get("resourceTypeAttributes")
            or body.get("statKey")
            or body.get("statKeys")
            or []
        )

        metrics: dict[str, dict] = {}
        skipped_local = 0
        for entry in stat_list:
            key = entry.get("key") or entry.get("statKeyId") or ""
            if not key:
                continue
            if _is_instance_local(key):
                # Super Metric|sm_<uuid> keys belong to one instance's own
                # SM set, not the adapter's describe surface. Importing them
                # would let a bundle referencing another lab's SM pass the
                # existence gate (review W4 on issue #143).
                skipped_local += 1
                continue
            # Observed field names on VCF Ops 9.0.2:
            #   "key", "name", "defaultMonitored", "type", "description", ...
            # "defaultMonitored" is boolean. Some entries omit it entirely
            # (treat as False, if it were true they would declare it).
            name = entry.get("name") or entry.get("displayName") or key
            default_monitored = bool(entry.get("defaultMonitored", False))
            metrics[key] = {
                "name": name,
                "default_monitored": default_monitored,
            }

        source_host = (
            self._client.base.replace("/suite-api", "")
            if hasattr(self._client, "base")
            else "unknown"
        )

        # Also fetch properties via /api/adapterkinds/{ak}/resourcekinds/{rk}/properties
        props_url_path = (
            f"/api/adapterkinds/{adapter_kind}/resourcekinds/{resource_kind}/properties"
        )
        properties: dict[str, dict] = {}
        properties_fetch_failed = False
        properties_failure_desc = ""
        try:
            props_resp = self._client._request("GET", props_url_path)
            if props_resp.status_code == 200:
                props_body = props_resp.json()
                # Observed response key: "resourceTypeAttributes" (same as statkeys)
                # or "resourceTypeProperty" / "property" depending on the endpoint.
                prop_list = (
                    props_body.get("resourceTypeAttributes")
                    or props_body.get("resourceTypeProperty")
                    or props_body.get("property")
                    or []
                )
                for entry in prop_list:
                    key = entry.get("key") or entry.get("statKeyId") or ""
                    if not key:
                        continue
                    if _is_instance_local(key):
                        skipped_local += 1
                        continue
                    name = entry.get("name") or entry.get("displayName") or key
                    # Properties carry their own defaultMonitored flag, it is
                    # NOT always True (see adapter_describe_exploration.md).
                    # instanceType is persisted too, observed as always
                    # "INSTANCED" in practice but not assumed here.
                    properties[key] = {
                        "name": name,
                        "default_monitored": bool(entry.get("defaultMonitored", False)),
                        "instance_type": entry.get("instanceType", "") or "",
                    }
            else:
                # Non-200: fetch failed, don't let an empty properties dict
                # clobber whatever was cached before (see issue #75).
                properties_fetch_failed = True
                properties_failure_desc = f"HTTP {props_resp.status_code}"
        except Exception as exc:
            # Properties fetch is best-effort; don't abort the statkeys refresh.
            properties_fetch_failed = True
            properties_failure_desc = f"{type(exc).__name__}: {exc}"

        if properties_fetch_failed:
            # Preserve the previously-cached properties rather than writing
            # an empty dict over a good cache. A single failed /properties
            # call must not corrupt knowledge/context/adapter_describe_cache/
            # for subsequent offline builds.
            properties = existing_doc.get("properties") or {}
            # Warn so the operator can tell this refresh half-failed: the
            # "refreshed describe cache ... (N property keys)" success line
            # below would otherwise present preserved stale properties as
            # freshly fetched (framework review W1 on issue #75).
            print(
                f"  WARN: /properties fetch failed for {adapter_kind}/"
                f"{resource_kind} ({properties_failure_desc}); preserving "
                f"{len(properties)} previously-cached property key(s), NOT "
                f"freshly fetched.",
                file=sys.stderr,
            )

        # Merge into the existing file (issue #143). Never replace: one
        # instance never reports the whole union the file may be grounded on.
        merged_metrics, metric_stats = _merge_section(
            existing_doc.get("metrics") or {}, metrics, prune=prune
        )
        if properties_fetch_failed:
            # ``properties`` already holds the previously-cached section
            # verbatim; nothing was fetched so nothing is merged or pruned.
            merged_props = properties
            prop_stats = None
        else:
            merged_props, prop_stats = _merge_section(
                existing_doc.get("properties") or {}, properties, prune=prune
            )

        fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        source_url = f"{source_host}/suite-api{url_path}"

        # Provenance (review W2): one "refresh" entry per source host in
        # merged_from, updated in place on every refresh from that host.
        # Hand-written entries (role primary / additive) are never touched.
        # The entry also carries the retained set for this host, which is
        # what makes the WARN below by-exception (review W1): the full key
        # list prints only when it differs from the previous refresh from
        # the same host.
        merged_from = list(existing_doc.get("merged_from") or [])
        previous_entry = None
        for i, entry in enumerate(merged_from):
            if (
                isinstance(entry, dict)
                and entry.get("role") == "refresh"
                and _host_of(entry.get("source", "")) == _host_of(source_url)
            ):
                previous_entry = entry
                del merged_from[i]
                break
        retained_now = {
            "metrics": metric_stats.retained,
            "properties": prop_stats.retained if prop_stats is not None
            else list((previous_entry or {}).get("retained_absent", {}).get("properties", [])),
        }
        refresh_entry = {
            "role": "refresh",
            "source": source_url,
            "fetched_at": fetched_at,
            "counts": {
                "metrics": _counts(metric_stats),
                "properties": _counts(prop_stats) if prop_stats is not None
                else {"preserved_not_fetched": len(merged_props)},
            },
            "retained_absent": retained_now,
        }
        merged_from.append(refresh_entry)

        # Carry through top-level keys we do not own (merge_note, ...);
        # overwrite only the ones this refresh produces.
        cache_doc = dict(existing_doc)
        cache_doc.update({
            "adapter_kind": adapter_kind,
            "resource_kind": resource_kind,
            "fetched_at": fetched_at,
            "source": source_url,
            "merged_from": merged_from,
            "metrics": merged_metrics,
            "properties": merged_props,
        })

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache_doc, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        # Invalidate in-memory layers so the next resolve_metric reloads.
        self._cache.pop((adapter_kind, resource_kind), None)
        self._props.pop((adapter_kind, resource_kind), None)

        previous_retained = (previous_entry or {}).get("retained_absent") or {}
        for section, stats in (("metrics", metric_stats), ("properties", prop_stats)):
            if stats is None:
                continue
            if stats.retained:
                if sorted(previous_retained.get(section) or []) == stats.retained:
                    # Same set as last time from this host: one count line.
                    print(
                        f"  {pair_label} {section}: {len(stats.retained)} "
                        f"cached key(s) not reported by {_host_of(source_url)}, "
                        f"retained (unchanged since {previous_entry.get('fetched_at', '?')}; "
                        f"use --prune to drop)",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"  WARN: {pair_label} {section}: live instance does not "
                        f"report {len(stats.retained)} cached key(s), retained "
                        f"(use --prune to drop): {', '.join(stats.retained)}",
                        file=sys.stderr,
                    )
            if stats.pruned:
                print(
                    f"  WARN: {pair_label} {section}: pruned "
                    f"{len(stats.pruned)} key(s) absent from live instance: "
                    f"{', '.join(stats.pruned)}",
                    file=sys.stderr,
                )
            if stats.dropped_local:
                print(
                    f"  WARN: {pair_label} {section}: dropped "
                    f"{len(stats.dropped_local)} instance-local 'Super Metric|' "
                    f"key(s) from the cache (never part of the describe surface): "
                    f"{', '.join(stats.dropped_local)}",
                    file=sys.stderr,
                )
        if prop_stats is not None:
            prop_summary = f"{len(merged_props)} property keys{_summarize(prop_stats)}"
        else:
            prop_summary = f"{len(merged_props)} property keys [preserved, not fetched]"
        local_summary = (
            f"; {skipped_local} instance-local key(s) skipped" if skipped_local else ""
        )
        print(
            f"  refreshed describe cache: {pair_label}: "
            f"{len(merged_metrics)} metric keys{_summarize(metric_stats)}; "
            f"{prop_summary}{local_summary}"
        )

    def refresh_all(
        self,
        kinds: Optional[list[tuple[str, str]]] = None,
        prune: bool = False,
    ) -> None:
        """Refresh cache for a list of (adapter_kind, resource_kind) pairs.

        If ``kinds`` is None, refreshes all pairs that already have a cache
        file under ``cache_dir``.  This is the ``refresh-describe`` CLI default.
        ``prune`` is passed through to ``refresh()``.
        """
        if kinds is not None:
            for ak, rk in kinds:
                self.refresh(ak, rk, prune=prune)
            return

        # Discover existing cache files.
        if not self._cache_dir.exists():
            print("No existing describe cache files found.")
            return
        pairs_found: list[tuple[str, str]] = []
        for ak_dir in sorted(self._cache_dir.iterdir()):
            if not ak_dir.is_dir():
                continue
            for rk_file in sorted(ak_dir.glob("*.json")):
                pairs_found.append((ak_dir.name, rk_file.stem))
        if not pairs_found:
            print("No existing describe cache files found.")
            return
        for ak, rk in pairs_found:
            self.refresh(ak, rk, prune=prune)


# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Module-level factory (used by builder.py and CLI)
# ---------------------------------------------------------------------------


def make_cache(live: bool = True, cache_dir: Optional[Path] = None) -> DescribeCache:
    """Build a DescribeCache.

    If ``live`` is True and the required env vars are present, attaches a live
    client so the cache can be refreshed.  Otherwise returns an offline cache.

    Credentials are resolved from the active profile (VCFOPS_PROFILE env var
    or ``"prod"`` default, build-time describe refreshes default to prod since
    they are read-only observations). If no profile credentials are available,
    falls back to offline mode (no error).

    This is a *late* import of VCFOpsClient to avoid pulling ``requests`` at
    module import time (mirrors the pattern used elsewhere in this package).
    """
    client = None
    if live:
        try:
            from vcfcf_common._env import load_dotenv, resolve_profile_credentials
            load_dotenv()
            creds = resolve_profile_credentials(default="prod")
            from vcfcf_common.client import VCFOpsClient
            client = VCFOpsClient(
                host=creds.host,
                username=creds.user,
                password=creds.password,
                auth_source=creds.auth_source,
                verify_ssl=creds.verify_ssl,
            )
        except Exception:
            # Any import or credential failure → offline mode.
            client = None
    return DescribeCache(cache_dir=cache_dir, client=client)
