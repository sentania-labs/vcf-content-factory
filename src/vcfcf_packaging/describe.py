"""Factory side of the adapter describe-surface cache (M2 row 3).

The offline half (resolve a key, load a cache file, merge a live section
into a cached one) lives in ``vcfcf_core.packaging.describe`` and takes the
cache directory as a required argument. This module keeps the three things
a library must not own:

- the cache directory's location in this repo
  (``knowledge/context/adapter_describe_cache/``, the default when
  ``cache_dir`` is not given);
- the network refresh (``DescribeCache.refresh`` / ``refresh_all``), which
  needs a client and rewrites the cache file, merging as the core module's
  docstring describes;
- ``make_cache``, which reads the active credential profile and attaches a
  live client, or falls back to offline mode.

``DescribeCache`` here is a subclass of the core class, so an instance built
through the old path is a core ``DescribeCache`` too and everything the
core audit accepts still accepts it. Every other name (``MetricInfo``,
``DescribeCacheError``, ``MergeStats``, ``_merge_section``, ...) resolves
through module ``__getattr__`` to the identical core object; patch the core
module, not this one, to affect those.

Cache file layout, merge semantics, provenance entries and the corrupt-file
recovery are documented on ``vcfcf_core.packaging.describe``.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from vcfcf_core.packaging import describe as _core
from vcfcf_core.packaging.describe import (
    DescribeCacheError,
    MetricInfo,
    _counts,
    _host_of,
    _is_instance_local,
    _merge_section,
    _summarize,
)

# Cache root is repo-relative so it's always findable regardless of cwd.
_REPO_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_CACHE_ROOT = _REPO_ROOT / "knowledge" / "context" / "adapter_describe_cache"


def _same_but_fetched_at(existing_doc: dict, cache_doc: dict) -> bool:
    """True when ``cache_doc`` differs from ``existing_doc`` only in the
    top-level ``fetched_at`` and the ``fetched_at`` of ``merged_from``
    entries. Everything else (keys, values, counts, retained sets, entry
    order, hand-written entries) must be equal."""
    def strip(doc: dict) -> dict:
        out = dict(doc)
        out.pop("fetched_at", None)
        entries = []
        for entry in out.get("merged_from") or []:
            if isinstance(entry, dict):
                entry = {k: v for k, v in entry.items() if k != "fetched_at"}
            entries.append(entry)
        if "merged_from" in out or entries:
            out["merged_from"] = entries
        return out
    return strip(existing_doc) == strip(cache_doc)


class DescribeCache(_core.DescribeCache):
    """Describe-surface cache: the core reader plus the factory's default
    location and the live refresh.

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
        super().__init__(Path(cache_dir) if cache_dir else _DEFAULT_CACHE_ROOT)
        self._client = client

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

        # M2 row 3 side item: when the only difference between the file on
        # disk and the merged document is the two ``fetched_at`` stamps (top
        # level and this host's ``merged_from`` refresh entry), leave the file
        # alone. Every credentialed build refreshes the pairs it references,
        # and a timestamp-only rewrite dirtied ten cache files per build.
        unchanged = cache_path.exists() and _same_but_fetched_at(existing_doc, cache_doc)
        if not unchanged:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(cache_doc, indent=2, sort_keys=True),
                encoding="utf-8",
            )

        # Invalidate in-memory layers so the next resolve_metric reloads.
        self.invalidate(adapter_kind, resource_kind)

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
        unchanged_summary = "; cache file unchanged, not rewritten" if unchanged else ""
        print(
            f"  refreshed describe cache: {pair_label}: "
            f"{len(merged_metrics)} metric keys{_summarize(metric_stats)}; "
            f"{prop_summary}{local_summary}{unchanged_summary}"
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


def __getattr__(name: str):
    """Every name this module does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
