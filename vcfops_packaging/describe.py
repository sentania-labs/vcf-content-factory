"""Adapter describe-surface cache + query helper.

Queries ``/api/adapterkinds/<kind>/resourcekinds/<rk>/statkeys`` on a live
VCF Ops instance and persists the results in a JSON file under
``context/adapter_describe_cache/<adapter_kind>/<resource_kind>.json``.

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
      }
    }
"""
from __future__ import annotations

import json
import os
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
_REPO_ROOT = Path(__file__).parent.parent
_DEFAULT_CACHE_ROOT = _REPO_ROOT / "context" / "adapter_describe_cache"


class DescribeCacheError(RuntimeError):
    pass


class DescribeCache:
    """Describes-surface cache.  Backed by JSON files; optionally live-refreshed.

    Args:
        cache_dir: Root directory for cache files.  Defaults to
            ``context/adapter_describe_cache/`` relative to the repo root.
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
        Does NOT perform a live refresh — call ``refresh()`` explicitly.

        Raises DescribeCacheError if the cache file exists but is corrupt, or
        if the kind pair has no cache file at all (caller must check for None
        vs. absence-vs-corrupt).  Actually: if no cache file exists, returns
        None to allow the caller to fail with a friendlier message.
        """
        pair = (adapter_kind, resource_kind)
        if pair not in self._cache:
            found = self._load_from_disk(adapter_kind, resource_kind)
            if not found:
                # No cache file — return sentinel None; caller decides severity.
                self._cache[pair] = {}  # mark as "attempted but missing"
        return self._cache.get(pair, {}).get(metric_key)

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
                "DescribeCache.refresh() requires a client — "
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
        #   "resourceTypeAttributes" — 929 entries for VMWARE/VirtualMachine
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
            # (treat as False — if it were true they would declare it).
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
        cache_doc = {
            "adapter_kind": adapter_kind,
            "resource_kind": resource_kind,
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": (
                f"{source_host}/suite-api{url_path}"
            ),
            "metrics": metrics,
        }

        cache_path = self._cache_path(adapter_kind, resource_kind)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(cache_doc, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        # Invalidate in-memory layer so the next resolve_metric reloads.
        self._cache.pop((adapter_kind, resource_kind), None)

        print(
            f"  refreshed describe cache: {adapter_kind}/{resource_kind} "
            f"({len(metrics)} keys)"
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

    This is a *late* import of VCFOpsClient to avoid pulling ``requests`` at
    module import time (mirrors the pattern used elsewhere in this package).
    """
    client = None
    if live:
        try:
            from vcfops_supermetrics._env import load_dotenv
            load_dotenv()
            host = os.environ.get("VCFOPS_HOST")
            user = os.environ.get("VCFOPS_USER")
            pw = os.environ.get("VCFOPS_PASSWORD")
            if host and user and pw:
                from vcfops_supermetrics.client import VCFOpsClient
                client = VCFOpsClient(
                    host=host,
                    username=user,
                    password=pw,
                    auth_source=os.environ.get("VCFOPS_AUTH_SOURCE", "Local"),
                    verify_ssl=os.environ.get("VCFOPS_VERIFY_SSL", "true").lower() != "false",
                )
        except Exception:
            # Any import or credential failure → offline mode.
            client = None
    return DescribeCache(cache_dir=cache_dir, client=client)
