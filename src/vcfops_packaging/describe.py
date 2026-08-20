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
``python3 -m vcfops_packaging refresh-describe`` with a live instance to
populate/upgrade the properties section.
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
                    f"'python3 -m vcfops_packaging refresh-describe "
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

    def refresh(self, adapter_kind: str, resource_kind: str) -> None:
        """Fetch statkeys from the live instance and write the cache file.

        Requires a client to have been supplied at construction time.

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
        for entry in stat_list:
            key = entry.get("key") or entry.get("statKeyId") or ""
            if not key:
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
            existing_cache_path = self._cache_path(adapter_kind, resource_kind)
            if existing_cache_path.exists():
                try:
                    existing_doc = json.loads(existing_cache_path.read_text(encoding="utf-8"))
                    properties = existing_doc.get("properties", {}) or {}
                except Exception:
                    properties = {}
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

        cache_doc = {
            "adapter_kind": adapter_kind,
            "resource_kind": resource_kind,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": (
                f"{source_host}/suite-api{url_path}"
            ),
            "metrics": metrics,
            "properties": properties,
        }

        cache_path = self._cache_path(adapter_kind, resource_kind)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache_doc, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        # Invalidate in-memory layers so the next resolve_metric reloads.
        self._cache.pop((adapter_kind, resource_kind), None)
        self._props.pop((adapter_kind, resource_kind), None)

        print(
            f"  refreshed describe cache: {adapter_kind}/{resource_kind} "
            f"({len(metrics)} metric keys, {len(properties)} property keys)"
        )

    def refresh_all(
        self,
        kinds: Optional[list[tuple[str, str]]] = None,
    ) -> None:
        """Refresh cache for a list of (adapter_kind, resource_kind) pairs.

        If ``kinds`` is None, refreshes all pairs that already have a cache
        file under ``cache_dir``.  This is the ``refresh-describe`` CLI default.
        """
        if kinds is not None:
            for ak, rk in kinds:
                self.refresh(ak, rk)
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
            self.refresh(ak, rk)


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
            from vcfops_common._env import load_dotenv, resolve_profile_credentials
            load_dotenv()
            creds = resolve_profile_credentials(default="prod")
            from vcfops_common.client import VCFOpsClient
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
