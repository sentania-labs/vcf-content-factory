"""Live-sync half of the dependency walker (M2 row 3).

The offline walk (reference extraction, ``@supermetric:"<name>"``
expansion, project-scope resolution, ``collect_deps``, ``DepGraph``,
``CollectDepsCrossLinks``, ``MetricRef``, ``SmRef``) lives in
``vcfcf_core.common.dep_walker``; every one of those names resolves through
this module unchanged (module ``__getattr__``), so
``from vcfcf_common.dep_walker import collect_deps`` keeps working and reads
back the identical object. To monkeypatch a core name so the running walker
sees it, patch ``vcfcf_core.common.dep_walker``.

This module keeps what needs an instance: ``walk_and_check`` (the sync-time
advisory), the describe fetch, the target-side SM lookup and enablement,
and the ``WalkResult`` / ``MetricGap`` result types they fill in.

Public API (online, requires VCFOpsClient)
------------------------------------------
  walk_and_check(
      client,             # vcfcf_supermetrics.client.VCFOpsClient (SM-extended)
      supermetrics,       # list[SuperMetricDef]: SMs being synced
      views,              # list[ViewDef]
      dashboards,         # list[Dashboard]
      customgroups,       # list[CustomGroupDef], optional, default []
      auto_enable_metrics=False,
      skip_metric_check=False,
  ) -> WalkResult

  WalkResult.ok           # True if no blockers (WARN is not a blocker when skip_metric_check=True)
  WalkResult.sm_enabled   # list[str]: SM names that were auto-enabled
  WalkResult.sm_already   # list[str]: SM names already enabled (no-op)
  WalkResult.sm_failed    # list[str]: SM names that failed to enable
  WalkResult.metric_gaps  # list[MetricGap]: OOTB metrics not defaultMonitored
  WalkResult.metric_enabled # list[MetricGap]: metrics that were auto-enabled
  WalkResult.messages     # list[(level, str)]: "OK"|"WARN"|"ERROR" + message
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

from vcfcf_core.common import dep_walker as _core
from vcfcf_core.common.dep_walker import (  # noqa: F401  (used by walk_and_check)
    MetricRef,
    SmRef,
    extract_customgroup_names_from_views,
    extract_refs_from_dashboards,
    extract_refs_from_supermetrics,
    extract_refs_from_views,
)

if TYPE_CHECKING:
    from vcfcf_supermetrics.client import VCFOpsClient
    from vcfcf_supermetrics.loader import SuperMetricDef
    from vcfcf_dashboards.loader import ViewDef, Dashboard


# ---------------------------------------------------------------------------
# Result types of the live walk
# ---------------------------------------------------------------------------

@dataclass
class MetricGap:
    """An OOTB metric with defaultMonitored=false on the target instance."""
    adapter_kind: str
    resource_kind: str
    metric_key: str
    sources: List[str] = field(default_factory=list)


@dataclass
class WalkResult:
    ok: bool = True
    sm_enabled: List[str] = field(default_factory=list)
    sm_already: List[str] = field(default_factory=list)
    sm_failed: List[str] = field(default_factory=list)
    metric_gaps: List[MetricGap] = field(default_factory=list)
    metric_enabled: List[MetricGap] = field(default_factory=list)
    messages: List[Tuple[str, str]] = field(default_factory=list)

    def _msg(self, level: str, text: str) -> None:
        self.messages.append((level, text))
        if level == "ERROR":
            self.ok = False


# ---------------------------------------------------------------------------
# Describe endpoint helper
# ---------------------------------------------------------------------------

def _fetch_describe(client: "VCFOpsClient", adapter_kind: str, resource_kind: str) -> Optional[dict]:
    """Fetch and return {metric_key: defaultMonitored} for one (adapter, kind) pair.

    Returns None if the endpoint is unreachable or returns a non-200.
    Raises VCFOpsError only on auth failures (handled upstream).
    """
    import urllib.parse
    # URL-encode adapter/resource kind keys (some have spaces, e.g. "vCenter Operations Adapter")
    ak_enc = urllib.parse.quote(adapter_kind, safe="")
    rk_enc = urllib.parse.quote(resource_kind, safe="")
    path = f"/api/adapterkinds/{ak_enc}/resourcekinds/{rk_enc}/statkeys"
    try:
        r = client._request("GET", path)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    body = r.json()
    # Per adapter_describe_exploration.md: real wrapper key is always
    # "resourceTypeAttributes" regardless of what the OpenAPI spec says.
    items = body.get("resourceTypeAttributes") or body.get("stat-key") or []
    return {item["key"]: item.get("defaultMonitored", True) for item in items}


# ---------------------------------------------------------------------------
# SM enablement helper (thin wrapper over client method)
# ---------------------------------------------------------------------------

# Sentinel: the target lookup itself failed (ambiguous name, transport error),
# as opposed to the target answering "no such name" (None).  A failed lookup
# has already been reported; it must not also be reported as "absent".
_LOOKUP_FAILED = object()


def _lookup_sm_uuid_on_target(
    client: "VCFOpsClient",
    sm_name: str,
    result: WalkResult,
):
    """Resolve an SM display name to its UUID on the target instance.

    Uses the SM client's ``find_by_name`` (exact name; raises on a duplicate
    name rather than guessing).  Returns the lower-cased UUID on a hit, None
    when the client cannot look names up or the target has no such name, and
    ``_LOOKUP_FAILED`` when the lookup raised; the failure is recorded on
    ``result`` and is the only line the operator should see for that name.
    """
    find = getattr(client, "find_by_name", None)
    if find is None:
        return None
    try:
        hit = find(sm_name)
    except Exception as e:  # VCFOpsError on ambiguity or transport failure
        result._msg("ERROR", f"lookup of super metric '{sm_name}' on target failed: {e}")
        return _LOOKUP_FAILED
    uid = (hit or {}).get("id") or None
    return uid.lower() if uid else None


def _resolve_sm_name(client: "VCFOpsClient", sm_uuid: str) -> Optional[str]:
    """Look up SM display name from UUID via GET /api/supermetrics/{id}."""
    try:
        sm = client.get_supermetric(sm_uuid)
        return sm.get("name", "")
    except Exception:
        return None


def _enable_sm(
    client: "VCFOpsClient",
    sm_uuid: str,
    sm_name: str,
    resource_kinds: list,
    result: WalkResult,
) -> None:
    """Enable one SM on the Default Policy, recording outcome into result."""
    from vcfcf_supermetrics.client import VCFOpsError
    import time
    SM_ENABLE_VERIFY_DELAY = 2

    try:
        client.enable_supermetric_on_default_policy(sm_uuid, resource_kinds)
    except VCFOpsError as e:
        result.sm_failed.append(sm_name or sm_uuid)
        result._msg("ERROR", f"SM enable failed for '{sm_name or sm_uuid}': {e}")
        return

    time.sleep(SM_ENABLE_VERIFY_DELAY)
    try:
        policy_xml = client.export_default_policy_xml()
        status = client.verify_supermetrics_enabled(policy_xml, [sm_uuid])
        if status.get(sm_uuid):
            result.sm_enabled.append(sm_name or sm_uuid)
            result._msg("OK", f"enabled SM '{sm_name or sm_uuid}'  ({sm_uuid})")
        else:
            result.sm_failed.append(sm_name or sm_uuid)
            result._msg("ERROR", f"SM '{sm_name or sm_uuid}' not confirmed enabled after inject")
    except VCFOpsError as e:
        result.sm_failed.append(sm_name or sm_uuid)
        result._msg("ERROR", f"SM verify failed for '{sm_name or sm_uuid}': {e}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def walk_and_check(
    client: "VCFOpsClient",
    supermetrics: "List[SuperMetricDef]",
    views: "List[ViewDef]",
    dashboards: "List[Dashboard]",
    customgroups: "List" = None,
    auto_enable_metrics: bool = False,
    skip_metric_check: bool = False,
    sm_name_map: Optional[dict] = None,
) -> WalkResult:
    """Walk all content, check instance-side dependencies, auto-enable where appropriate.

    Args:
        client:               SM-extended VCFOpsClient (from vcfcf_supermetrics.client).
        supermetrics:         SuperMetricDef list being synced (may be empty for dashboard-only sync).
        views:                ViewDef list being synced (may be empty).
        dashboards:           Dashboard list being synced (may be empty).
        customgroups:         CustomGroupDef list, used to validate customgroup references
                              found in view ``customgroup:`` fields. Pass the full repo corpus.
                              Defaults to [] (no customgroup validation).
        auto_enable_metrics:  If True, enable OOTB metrics with defaultMonitored=false on Default Policy.
        skip_metric_check:    If True, skip the OOTB metric describe check entirely.
        sm_name_map:          Optional {sm_name: uuid} map from the repo's SM YAML.
                              Used to annotate SM refs discovered by UUID-only with their names.

    Returns WalkResult with all outcomes recorded.
    """
    from vcfcf_supermetrics.client import VCFOpsError

    result = WalkResult()
    _customgroups = customgroups if customgroups is not None else []
    _sm_name_map = sm_name_map or {}
    # Reverse map: uuid -> name
    _uuid_to_name: dict = {v: k for k, v in _sm_name_map.items()}
    # Also build reverse from the repo SMs being synced
    for sm in supermetrics:
        if sm.id and sm.name:
            _uuid_to_name[sm.id] = sm.name

    # --- Phase 0: customgroup reference validation -------------------------
    # Check that every group referenced by view ``customgroup:`` fields is
    # present in the provided corpus.  This is a static check, no API call.
    if _customgroups:
        cg_corpus_names = {cg.name for cg in _customgroups}
        cg_refs = extract_customgroup_names_from_views(views)
        for cg_name in cg_refs:
            if cg_name not in cg_corpus_names:
                result._msg(
                    "ERROR",
                    f"customgroup dependency: view references group "
                    f"'{cg_name}' which is not present in the synced customgroups corpus. "
                    f"Sync the custom group first or add it to the bundle."
                )

    # --- Phase 1: extract all references -----------------------------------
    sm_refs_all: List[SmRef] = []
    metric_refs_all: List[MetricRef] = []

    sm_r, m_r = extract_refs_from_supermetrics(supermetrics, sm_name_map=_sm_name_map)
    sm_refs_all.extend(sm_r)
    metric_refs_all.extend(m_r)

    sm_r, m_r = extract_refs_from_views(views)
    sm_refs_all.extend(sm_r)
    metric_refs_all.extend(m_r)

    sm_r, m_r = extract_refs_from_dashboards(dashboards)
    sm_refs_all.extend(sm_r)
    metric_refs_all.extend(m_r)

    # --- Phase 1b: name-only SM refs (@supermetric:"<name>" tokens) --------
    # A referent that is neither in this batch nor in the repo SM YAML may
    # still exist on the target (the push-time resolver falls back to
    # find_by_name the same way).  Resolve it here so the policy check below
    # covers it; when nothing knows the name, say so up front, naming the
    # referrer and the referent, instead of letting the push fail later.
    _remote_by_name: dict = {}
    _missing_reported: Set[Tuple[str, str]] = set()  # (source, name)
    for ref in sm_refs_all:
        if ref.sm_id or not ref.name:
            continue
        if ref.name not in _remote_by_name:
            _remote_by_name[ref.name] = _lookup_sm_uuid_on_target(
                client, ref.name, result
            )
        uid = _remote_by_name[ref.name]
        if uid is _LOOKUP_FAILED:
            continue  # already reported as a failed lookup; not "absent"
        if uid:
            ref.sm_id = uid
            _uuid_to_name[uid] = ref.name
        elif (ref.source, ref.name) not in _missing_reported:
            _missing_reported.add((ref.source, ref.name))
            result._msg(
                "ERROR",
                f"{ref.source} references @supermetric:\"{ref.name}\" but no "
                f"super metric with that name is in this sync batch, in the "
                f"repo SM YAML, or on the target instance. Sync that super "
                f"metric first, or fix the name in the formula."
            )

    # Deduplicate SM refs by UUID, collecting sources
    sm_by_uuid: dict = {}
    for ref in sm_refs_all:
        if not ref.sm_id:
            continue
        uid = ref.sm_id.lower()
        if uid not in sm_by_uuid:
            name = ref.name or _uuid_to_name.get(uid, "")
            sm_by_uuid[uid] = {"name": name, "sources": [ref.source]}
        else:
            if ref.source not in sm_by_uuid[uid]["sources"]:
                sm_by_uuid[uid]["sources"].append(ref.source)
            if not sm_by_uuid[uid]["name"] and ref.name:
                sm_by_uuid[uid]["name"] = ref.name

    # --- Phase 2: SM check + enable ----------------------------------------
    if sm_by_uuid:
        result._msg("OK", f"dependency walker: found {len(sm_by_uuid)} SM reference(s), checking policy")
        try:
            policy_xml = client.export_default_policy_xml()
        except VCFOpsError as e:
            result._msg("ERROR", f"cannot export Default Policy for SM dependency check: {e}")
            return result

        enabled_map = client.verify_supermetrics_enabled(policy_xml, list(sm_by_uuid.keys()))

        # Identify SMs in the current sync set (enabled automatically as part
        # of the normal sync+enable path). We still check pre-existing SMs.
        syncing_ids = {sm.id.lower() for sm in supermetrics if sm.id}

        for uid, info in sm_by_uuid.items():
            name = info["name"]
            if not name:
                # Try to resolve from instance
                resolved = _resolve_sm_name(client, uid)
                name = resolved or uid
                info["name"] = name

            if enabled_map.get(uid):
                result.sm_already.append(name)
                result._msg("OK", f"SM already enabled: '{name}'  ({uid})")
            elif uid in syncing_ids:
                # Part of this sync batch, will be enabled by the caller's enable step
                result._msg("OK", f"SM in sync batch (enable step will activate): '{name}'  ({uid})")
            else:
                # Pre-existing SM on instance, not yet enabled, auto-enable it.
                result._msg("OK", f"SM not enabled, enabling: '{name}'  ({uid})")
                # Need to find resource_kinds for this SM from the instance.
                rks = _get_sm_resource_kinds(client, uid, name, result)
                if rks is not None:
                    _enable_sm(client, uid, name, rks, result)

    # --- Phase 3: OOTB metric check ----------------------------------------
    if skip_metric_check:
        result._msg("OK", "OOTB metric check skipped (--skip-metric-check)")
        return result

    if not metric_refs_all:
        return result

    # Deduplicate metric refs by (adapter_kind, resource_kind, metric_key)
    metric_by_key: dict = {}  # (ak, rk, mk) -> [sources]
    for ref in metric_refs_all:
        k = (ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if k not in metric_by_key:
            metric_by_key[k] = [ref.source]
        else:
            if ref.source not in metric_by_key[k]:
                metric_by_key[k].append(ref.source)

    # Group by (adapter_kind, resource_kind) for one describe call per pair
    ak_rk_to_keys: dict = {}
    for (ak, rk, mk), sources in metric_by_key.items():
        if not rk:
            continue  # can't describe without resource_kind
        pair = (ak, rk)
        if pair not in ak_rk_to_keys:
            ak_rk_to_keys[pair] = {}
        ak_rk_to_keys[pair][mk] = sources

    gaps: List[MetricGap] = []
    describe_errors: List[str] = []

    for (ak, rk), key_sources in ak_rk_to_keys.items():
        describe = _fetch_describe(client, ak, rk)
        if describe is None:
            describe_errors.append(f"{ak}/{rk}")
            continue
        for mk, sources in key_sources.items():
            monitored = describe.get(mk)
            if monitored is None:
                # Key not in describe, could be a property key or a valid but
                # rare metric. We skip it rather than blocking on uncertainty.
                # This avoids false positives for OnlineCapacityAnalytics| keys etc.
                pass
            elif monitored is False:
                gaps.append(MetricGap(
                    adapter_kind=ak,
                    resource_kind=rk,
                    metric_key=mk,
                    sources=sources,
                ))

    if describe_errors:
        result._msg("ERROR",
            "OOTB metric check: describe endpoint unreachable for "
            + ", ".join(describe_errors)
            + ", sync marked incomplete (use --skip-metric-check to override)"
        )
        return result

    if not gaps:
        result._msg("OK", "OOTB metric check: all referenced metrics are defaultMonitored=true")
        return result

    # We have gaps. Either auto-enable or warn.
    if auto_enable_metrics:
        result._msg("OK", f"--auto-enable-metrics: enabling {len(gaps)} metric(s) on Default Policy")
        entries = [
            {"adapter_kind": g.adapter_kind, "resource_kind": g.resource_kind, "metric_key": g.metric_key}
            for g in gaps
        ]
        try:
            already_map = client.enable_builtin_metrics_on_default_policy(entries)
        except VCFOpsError as e:
            result._msg("ERROR", f"auto-enable-metrics failed: {e}")
            return result
        for g in gaps:
            already = already_map.get(g.metric_key, False)
            if already:
                result._msg("OK", f"  metric already enabled: {g.adapter_kind}/{g.resource_kind}/{g.metric_key}")
                result.sm_already.append(g.metric_key)
            else:
                result._msg("OK", f"  metric enabled: {g.adapter_kind}/{g.resource_kind}/{g.metric_key}")
                result.metric_enabled.append(g)
    else:
        # Default: WARN loudly but do not block sync success.
        result.metric_gaps = gaps
        result._msg("WARN",
            f"OOTB metric check: {len(gaps)} metric(s) have defaultMonitored=false, "
            "these metrics are not collected by default and will render as empty. "
            "Use --auto-enable-metrics to enable them, or --skip-metric-check to suppress this warning."
        )
        for g in gaps:
            result._msg("WARN",
                f"  NOT MONITORED: {g.adapter_kind}/{g.resource_kind}/{g.metric_key}"
                + (f"  (referenced by: {g.sources[0]})" if g.sources else "")
            )

    return result


def _get_sm_resource_kinds(
    client: "VCFOpsClient",
    sm_uuid: str,
    sm_name: str,
    result: WalkResult,
) -> Optional[list]:
    """Fetch resource kinds for an SM from the instance.

    Returns a list of {adapterKind, resourceKind} dicts, or None on failure.
    """
    from vcfcf_supermetrics.client import VCFOpsError
    try:
        sm_data = client.get_supermetric(sm_uuid)
    except VCFOpsError as e:
        result._msg("ERROR", f"cannot fetch SM '{sm_name}' ({sm_uuid}) from instance: {e}")
        return None

    raw_rks = sm_data.get("resourceKinds") or []
    rks = []
    for rk in raw_rks:
        ak = rk.get("adapterKindKey") or rk.get("adapterKind", "VMWARE")
        rkk = rk.get("resourceKindKey") or rk.get("resourceKind", "")
        if rkk:
            rks.append({"adapterKind": ak, "resourceKind": rkk})

    if not rks:
        result._msg("WARN",
            f"SM '{sm_name}' ({sm_uuid}) has no resourceKinds on the instance, cannot enable. "
            "Run 'python3 -m vcfcf_supermetrics sync' first."
        )
        return None
    return rks


def __getattr__(name: str):
    """Every name this module does not define itself resolves to core."""
    try:
        return getattr(_core, name)
    except AttributeError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
