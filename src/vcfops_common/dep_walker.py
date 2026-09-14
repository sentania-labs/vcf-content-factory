"""Sync-time dependency walker for VCF Operations content.

Given a set of loaded content models (SuperMetricDef, ViewDef, Dashboard,
CustomGroupDef), this module:

  1. Extracts every dependency that requires an instance-side capability to
     be active:
       - Super metric references (must be enabled on the target policy),
         including @supermetric:"<name>" formula cross-references, which are
         resolved against the sync batch, the repo SM YAML, then the target
         instance, and reported as a missing referent when none knows the name
       - OOTB metric references (must be collected — defaultMonitored may be false)
       - Custom group references (view-scoped groups must exist on the target)

  2. Queries the adapter describe endpoint once per (adapter_kind, resource_kind)
     pair to check defaultMonitored state. Fails closed if the endpoint is
     unreachable.

  3. For SM dependencies: checks the current policy XML and enables any SM
     that is present on the instance but not yet enabled.

  4. For OOTB metric dependencies with defaultMonitored=false: warns loudly
     (default) or enables them (--auto-enable-metrics).

Public API — offline (no client required)
-----------------------------------------
  collect_deps(
      dashboards,         # list[Dashboard] — starting point(s) for the walk
      all_views,          # corpus of all ViewDef available in the repo
      all_sms,            # corpus of all SuperMetricDef available in the repo
      all_customgroups,   # corpus of all CustomGroupDef available in the repo
      project_scope=None, # Optional[str] — "factory", a third-party slug, or None
      cross_links=None,   # Optional[CollectDepsCrossLinks] — allowed factory fallbacks
  ) -> DepGraph

  DepGraph.views          # list[ViewDef] — transitively required views
  DepGraph.supermetrics   # list[SuperMetricDef] — transitively required SMs
                          #   (including SMs pulled in by @supermetric:"<name>"
                          #   formula cross-references, walked to a fixed point)
  DepGraph.customgroups   # list[CustomGroupDef] — transitively required groups
  DepGraph.errors         # list[str] — missing-dep error messages

  expand_sm_crossrefs(
      sms,                # list[SuperMetricDef]: seed SMs
      all_sms,            # corpus of all SuperMetricDef available in the repo
  ) -> (list[SuperMetricDef], list[str])
      Same SM-to-SM walk collect_deps runs, for callers that start from a
      super metric or a view instead of a dashboard.  Seeds first, then
      referents in discovery order; errors name the missing referent.

Project-scope semantics
-----------------------
  project_scope=None         No scoping.  Resolves against the full corpus the same
                             way as today.  Auto-detected from the starting dashboard's
                             provenance when exactly one starting dashboard is provided.

  project_scope="factory"    Only resolves to provenance=="factory" components.
                             Errors if a needed component lives in any third-party project.

  project_scope="<slug>"     Resolves to same-project components first; falls back to
                             provenance=="factory" only when the dependency's display name
                             is explicitly listed in the corresponding ``cross_links``
                             parameter.  Errors otherwise.

  provenance==""             Components with empty provenance (test fixtures, objects
                             constructed without a source_path) are always accepted
                             regardless of scope — the scope boundary is only enforced
                             on objects whose provenance is known.

Public API — online (requires VCFOpsClient)
-------------------------------------------
  walk_and_check(
      client,             # vcfops_supermetrics.client.VCFOpsClient (SM-extended)
      supermetrics,       # list[SuperMetricDef] — SMs being synced
      views,              # list[ViewDef]
      dashboards,         # list[Dashboard]
      customgroups,       # list[CustomGroupDef] — optional, default []
      auto_enable_metrics=False,
      skip_metric_check=False,
  ) -> WalkResult

  WalkResult.ok           # True if no blockers (WARN is not a blocker when skip_metric_check=True)
  WalkResult.sm_enabled   # list[str] — SM names that were auto-enabled
  WalkResult.sm_already   # list[str] — SM names already enabled (no-op)
  WalkResult.sm_failed    # list[str] — SM names that failed to enable
  WalkResult.metric_gaps  # list[MetricGap] — OOTB metrics not defaultMonitored
  WalkResult.metric_enabled # list[MetricGap] — metrics that were auto-enabled
  WalkResult.messages     # list[(level, str)] — "OK"|"WARN"|"ERROR" + message

Extraction helpers (importable for packaging use)
-------------------------------------------------
  extract_view_names_from_dashboards(dashboards)  -> list[str]
  extract_customgroup_names_from_views(views)     -> list[str]
  extract_customgroup_names_from_dashboards(dashboards, cg_names) -> list[str]
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from vcfops_supermetrics.client import VCFOpsClient
    from vcfops_supermetrics.loader import SuperMetricDef
    from vcfops_dashboards.loader import ViewDef, Dashboard


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class MetricRef:
    """One (adapter_kind, resource_kind, metric_key) reference extracted from content."""
    adapter_kind: str
    resource_kind: str
    metric_key: str
    source: str  # human-readable provenance: "view <name> col <display_name>", etc.


@dataclass
class SmRef:
    """One super metric reference extracted from content.

    sm_id is the bare UUID (without sm_ prefix).
    name may be empty if we only have the UUID from a pre-resolved column attribute.
    """
    sm_id: str
    name: str  # may be empty if only UUID available
    source: str


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


@dataclass
class DepGraph:
    """Result of a pure offline dependency walk starting from a set of dashboards.

    Populated by collect_deps(). No network calls; purely traverses in-memory
    content models.

    Attributes:
        views:          Transitively required ViewDef objects (de-duplicated by name).
        supermetrics:   Transitively required SuperMetricDef objects (de-duplicated by id).
        customgroups:   Transitively required CustomGroupDef objects (de-duplicated by name).
        errors:         Missing-dependency error strings. Non-empty means the
                        collected dep graph is incomplete — callers should treat
                        this as a build error.
    """
    views: "List" = field(default_factory=list)
    supermetrics: "List" = field(default_factory=list)
    customgroups: "List" = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class CollectDepsCrossLinks:
    """Allowed factory fallbacks for a project-scoped walk.

    When ``collect_deps`` is called with ``project_scope="<slug>"``, only deps
    whose display name appears in the corresponding list here are permitted to
    resolve against factory-provenance content.  All other factory-provenance
    components are out-of-scope and produce an error.

    All three lists contain *display names* (the ``name`` field in each content
    YAML).  Pass an instance of this class as the ``cross_links`` argument to
    ``collect_deps``.

    The common case (fully self-contained project) is to pass ``None`` — the
    walker then rejects *all* factory fallbacks.
    """
    views: Set[str] = field(default_factory=set)
    supermetrics: Set[str] = field(default_factory=set)
    customgroups: Set[str] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Reference extraction helpers
# ---------------------------------------------------------------------------

_SM_UUID_RE = re.compile(
    r"sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)

_FORMULA_METRIC_RE = re.compile(
    r"\$\{[^}]+\}",
    re.IGNORECASE,
)

_FORMULA_ADAPTERTYPE_RE = re.compile(r"adaptertype\s*=\s*([A-Za-z0-9_\- ]+?)(?:,|$)", re.IGNORECASE)
_FORMULA_OBJECTTYPE_RE = re.compile(r"objecttype\s*=\s*([A-Za-z0-9_ ]+?)(?:,|$)", re.IGNORECASE)
_FORMULA_METRIC_KEY_RE = re.compile(r"metric\s*=\s*([A-Za-z0-9_|.:\- ]+?)(?:,|\}|$)", re.IGNORECASE)
_FORMULA_ATTR_RE = re.compile(r"attribute\s*=\s*([^\s,}]+)", re.IGNORECASE)


def _is_sm_key(key: str) -> bool:
    """True if the key is a super metric reference (sm_<uuid> or Super Metric|sm_<uuid>)."""
    k = key.strip()
    return k.startswith("sm_") or k.startswith("Super Metric|sm_") or k.startswith("Super Metric|") and "sm_" in k


def _extract_sm_uuid(key: str) -> Optional[str]:
    """Extract bare UUID from sm_<uuid> or Super Metric|sm_<uuid>, else None."""
    m = _SM_UUID_RE.search(key)
    return m.group(1) if m else None


def extract_refs_from_supermetrics(
    defs: "List[SuperMetricDef]",
    sm_name_map: Optional[dict] = None,
) -> Tuple[List[SmRef], List[MetricRef]]:
    """Extract SM-to-SM and SM-to-OOTB-metric references from SM formulas.

    SM formulas reference other SMs either pre-resolved, as
    ``attribute=sm_<uuid>`` inside ${...} resource entries, or by name with
    the authoring-time token ``@supermetric:"<name>"``; and reference OOTB
    metrics as ``metric=<key>`` with an adaptertype/objecttype context.

    A name-keyed reference yields an SmRef whose ``name`` is the referenced
    display name and whose ``sm_id`` is resolved from ``sm_name_map`` (a
    ``{name: uuid}`` dict) or from ``defs`` themselves; when neither knows
    the name, ``sm_id`` is empty and the caller decides what that means
    (``walk_and_check`` tries the target instance, then reports it).
    """
    from vcfops_supermetrics.crossref import crossref_names

    _names: dict = dict(sm_name_map or {})
    for d in defs:
        if d.name and d.id and d.name not in _names:
            _names[d.name] = d.id

    sm_refs: List[SmRef] = []
    metric_refs: List[MetricRef] = []
    for sm in defs:
        formula = sm.formula or ""
        for ref_name in crossref_names(formula):
            uid = _names.get(ref_name) or ""
            sm_refs.append(SmRef(
                sm_id=uid.lower(),
                name=ref_name,
                source=f"SM '{sm.name}' formula",
            ))
        for entry_match in _FORMULA_METRIC_RE.finditer(formula):
            raw = entry_match.group(0)
            inner = raw[2:-1]  # strip ${...}
            # Check for SM attribute reference
            attr_m = _FORMULA_ATTR_RE.search(inner)
            if attr_m:
                attr_val = attr_m.group(1).strip()
                sm_uuid = _extract_sm_uuid(attr_val)
                if sm_uuid:
                    sm_refs.append(SmRef(
                        sm_id=sm_uuid,
                        name="",
                        source=f"SM '{sm.name}' formula",
                    ))
            # Check for OOTB metric reference
            metric_m = _FORMULA_METRIC_KEY_RE.search(inner)
            if metric_m:
                metric_key = metric_m.group(1).strip().rstrip(",}")
                if not _is_sm_key(metric_key):
                    # Extract adaptertype / objecttype for the describe call.
                    # "this" entries reference the SM's own resource kinds.
                    head = inner.split(",", 1)[0].strip().lower()
                    if head == "this":
                        # One ref per resource_kind the SM is assigned to.
                        for rk in (sm.resource_kinds or []):
                            metric_refs.append(MetricRef(
                                adapter_kind=rk.get("adapterKindKey", "VMWARE"),
                                resource_kind=rk.get("resourceKindKey", ""),
                                metric_key=metric_key,
                                source=f"SM '{sm.name}' formula (this)",
                            ))
                    else:
                        at_m = _FORMULA_ADAPTERTYPE_RE.search(inner)
                        ot_m = _FORMULA_OBJECTTYPE_RE.search(inner)
                        if at_m and ot_m:
                            metric_refs.append(MetricRef(
                                adapter_kind=at_m.group(1).strip(),
                                resource_kind=ot_m.group(1).strip(),
                                metric_key=metric_key,
                                source=f"SM '{sm.name}' formula",
                            ))
    return sm_refs, metric_refs


def extract_refs_from_views(
    views: "List[ViewDef]",
) -> Tuple[List[SmRef], List[MetricRef]]:
    """Extract SM and OOTB metric references from view column attributes."""
    sm_refs: List[SmRef] = []
    metric_refs: List[MetricRef] = []
    for v in views:
        ak = v.adapter_kind or "VMWARE"
        rk = v.resource_kind or ""
        for col in v.columns:
            attr = col.attribute.strip()
            sm_uuid = _extract_sm_uuid(attr)
            if sm_uuid:
                sm_refs.append(SmRef(
                    sm_id=sm_uuid,
                    name="",
                    source=f"view '{v.name}' col '{col.display_name}'",
                ))
            elif attr and not attr.startswith("Super Metric|"):
                # Plain OOTB metric key — strip namespace prefix if present
                # (some attrs may be e.g. "OnlineCapacityAnalytics|cpu|demand|timeRemaining")
                metric_refs.append(MetricRef(
                    adapter_kind=ak,
                    resource_kind=rk,
                    metric_key=attr,
                    source=f"view '{v.name}' col '{col.display_name}'",
                ))
    return sm_refs, metric_refs


def extract_refs_from_dashboards(
    dashboards: "List[Dashboard]",
) -> Tuple[List[SmRef], List[MetricRef]]:
    """Extract SM and OOTB metric references from all dashboard widget configs."""
    sm_refs: List[SmRef] = []
    metric_refs: List[MetricRef] = []

    def _handle_metric_key(metric_key: str, adapter_kind: str, resource_kind: str, source: str) -> None:
        k = metric_key.strip()
        if not k:
            return
        sm_uuid = _extract_sm_uuid(k)
        if sm_uuid:
            sm_refs.append(SmRef(sm_id=sm_uuid, name="", source=source))
        else:
            metric_refs.append(MetricRef(
                adapter_kind=adapter_kind,
                resource_kind=resource_kind,
                metric_key=k,
                source=source,
            ))

    for dash in dashboards:
        for w in dash.widgets:
            src_base = f"dashboard '{dash.name}' widget '{w.local_id}'"

            # Scoreboard and MetricChart use MetricSpec list
            for spec_config in [w.scoreboard_config, w.metric_chart_config]:
                if spec_config is not None:
                    for spec in (spec_config.metrics or []):
                        _handle_metric_key(
                            spec.metric_key,
                            spec.adapter_kind or "VMWARE",
                            spec.resource_kind or "",
                            f"{src_base} ({w.type}) metric '{spec.metric_name}'",
                        )

            # HealthChart — single flat metric spec
            if w.health_chart_config is not None:
                hc = w.health_chart_config
                _handle_metric_key(
                    hc.metric_key,
                    hc.adapter_kind or "VMWARE",
                    hc.resource_kind or "",
                    f"{src_base} (HealthChart)",
                )

            # ParetoAnalysis — single flat metric spec
            if w.pareto_analysis_config is not None:
                pa = w.pareto_analysis_config
                _handle_metric_key(
                    pa.metric_key,
                    pa.adapter_kind or "VMWARE",
                    pa.resource_kind or "",
                    f"{src_base} (ParetoAnalysis)",
                )

            # Heatmap — one or more tabs, each has color_by and optionally size_by
            if w.heatmap_config is not None:
                for tab in w.heatmap_config.tabs:
                    tab_src = f"{src_base} (Heatmap tab '{tab.name}')"
                    if tab.color_by_key:
                        _handle_metric_key(
                            tab.color_by_key,
                            tab.adapter_kind or "VMWARE",
                            tab.resource_kind or "",
                            f"{tab_src} color_by",
                        )
                    if tab.size_by_key:
                        _handle_metric_key(
                            tab.size_by_key,
                            tab.adapter_kind or "VMWARE",
                            tab.resource_kind or "",
                            f"{tab_src} size_by",
                        )

    return sm_refs, metric_refs


# ---------------------------------------------------------------------------
# Structural extraction helpers (pure — no client, no network)
# ---------------------------------------------------------------------------

def _walk_sm_crossrefs(
    seeds: "List",
    sm_by_name: "dict",
    accept: "Callable[[object, str], bool]",
    errors: List[str],
) -> None:
    """Breadth-first walk over ``@supermetric:"<name>"`` formula references.

    ``accept(sm, source)`` is called once per referent found; it returns True
    when the referent is newly taken into the result set (so its own formula
    gets walked too) and False when it was already present or was rejected.
    A referent whose name is not in ``sm_by_name`` is recorded in ``errors``
    and the walk continues, so the caller sees every missing name in one pass.

    Tokens are found with ``vcfops_supermetrics.crossref.crossref_names`` (the
    ``SM_CROSSREF_RE`` match): the ``@supermetric`` token is case-insensitive,
    the quoted name is matched exactly against the SM display name.  Cycles terminate via a visited set
    keyed on the SM id (falling back to the name for id-less fixtures).
    """
    from vcfops_supermetrics.crossref import crossref_names

    queue = list(seeds)
    visited: Set[str] = set()
    while queue:
        sm = queue.pop(0)
        key = (getattr(sm, "id", "") or "").lower() or sm.name
        if key in visited:
            continue
        visited.add(key)
        source = f"super metric '{sm.name}'"
        for ref_name in crossref_names(getattr(sm, "formula", "") or ""):
            ref = sm_by_name.get(ref_name)
            if ref is None:
                errors.append(
                    f"{source}: formula references @supermetric:\"{ref_name}\" "
                    f"but no super metric with that name was found in the corpus"
                )
                continue
            if accept(ref, source):
                queue.append(ref)


def expand_sm_crossrefs(
    sms: "List",
    all_sms: "List",
) -> "Tuple[List, List[str]]":
    """Transitively add super metrics referenced by ``@supermetric:"<name>"``.

    An SM formula may reference another SM by name (the authoring-time
    cross-reference form).  Every emit path resolves that token to the native
    ``Super Metric|sm_<uuid>`` wire token and hard-errors when the referent is
    not in the bundle, so anything that ships or syncs an SM must carry its
    referents the same way a view carries the SMs its columns use.

    Returns ``(supermetrics, errors)``.  Input order is preserved, newly
    pulled SMs are appended after it in discovery order, and a formula with no
    cross-reference token is a no-op.  A referent missing from ``all_sms``
    lands in ``errors`` rather than raising, matching ``collect_deps``; the
    caller decides whether that is fatal (the discrete builder treats it as a
    hard failure, the same as the resolver would at emit time).
    """
    by_name = {sm.name: sm for sm in all_sms}
    result: "List" = []
    seen: Set[str] = set()
    errors: List[str] = []

    def _accept(sm, _source: str) -> bool:
        key = (getattr(sm, "id", "") or "").lower() or sm.name
        if key in seen:
            return False
        seen.add(key)
        result.append(sm)
        return True

    for sm in sms:
        _accept(sm, "")
    _walk_sm_crossrefs(list(sms), by_name, _accept, errors)
    return result, errors


def extract_view_names_from_dashboards(
    dashboards: "List",
) -> List[str]:
    """Return the unique list of view names referenced by dashboard widgets.

    Walks every widget in every dashboard and collects the ``view_name``
    attribute from View-type widgets. Preserves insertion order; de-duplicates
    by name.  This is the dashboard→view step of the dependency graph.
    """
    seen: set = set()
    result: List[str] = []
    for dash in dashboards:
        for w in dash.widgets:
            if w.view_name and w.view_name not in seen:
                seen.add(w.view_name)
                result.append(w.view_name)
    return result


def extract_customgroup_names_from_views(
    views: "List",
) -> List[str]:
    """Return the unique list of custom group names referenced by the given views.

    Reads the ``customgroups`` field on each ViewDef (a list of group name
    strings, populated from the YAML ``customgroup:`` key by the loader).
    De-duplicates by name, preserves insertion order.
    """
    seen: set = set()
    result: List[str] = []
    for v in views:
        for cg_name in (getattr(v, "customgroups", None) or []):
            if cg_name and cg_name not in seen:
                seen.add(cg_name)
                result.append(cg_name)
    return result


def extract_customgroup_names_from_dashboards(
    dashboards: "List",
    known_cg_names: "Optional[set]" = None,
) -> List[str]:
    """Return custom group names directly referenced by dashboard widget configs.

    Currently the YAML widget model does not have a dedicated
    ``customgroup_scope`` field — no existing factory dashboard pins a widget
    directly to a custom group as its scope resource.  This function is
    provided as the extension point for when that field is added.

    If ``known_cg_names`` is supplied (set of all group names in the corpus),
    this function checks each widget's ``pin.resource_kind`` against that set
    as a heuristic (custom groups are Container-adapter resources; their name
    is their identity).  In practice no factory dashboard pin currently matches
    a group name, so this returns an empty list today.

    TOOLSET GAP NOTE: a first-class ``customgroup_scope:`` widget YAML field
    would make this extraction unambiguous.  Deferred to a future phase.
    """
    if not known_cg_names:
        return []
    seen: set = set()
    result: List[str] = []
    for dash in dashboards:
        for w in dash.widgets:
            pin = getattr(w, "pin", None)
            if pin is not None:
                rk = getattr(pin, "resource_kind", "") or ""
                if rk in known_cg_names and rk not in seen:
                    seen.add(rk)
                    result.append(rk)
    return result


def _auto_detect_scope(dashboards: "List") -> Optional[str]:
    """Infer project_scope from the provenance of a single starting dashboard.

    Returns the provenance string if all dashboards share the same non-empty
    provenance; returns None if the list is empty, has multiple dashboards
    with different provenances, or has empty provenance.

    Rationale: when a caller passes a single starting dashboard the walker can
    automatically scope to that dashboard's project, giving DTRT behaviour
    without requiring every caller to pass project_scope explicitly.
    """
    if not dashboards:
        return None
    provenances = {getattr(d, "provenance", "") for d in dashboards}
    # If all dashboards share exactly one non-empty provenance, use it.
    provenances.discard("")  # ignore unknown-provenance dashes (test fixtures)
    if len(provenances) == 1:
        return provenances.pop()
    return None


def _scope_allows(
    obj_provenance: str,
    obj_name: str,
    project_scope: str,
    cross_links_for_type: Optional[Set[str]],
) -> Optional[str]:
    """Return None if the object is in-scope; return an error string if not.

    Args:
        obj_provenance:      The loaded object's provenance field.
        obj_name:            The display name of the object (for error messages).
        project_scope:       "factory" or a third-party slug.
        cross_links_for_type: The set of cross-linked names allowed for this
                              content type (e.g. cross_links.views), or None.

    Semantics:
      * Empty provenance (test fixtures, programmatically constructed objects)
        → always allowed.  The scope boundary only applies to objects whose
        provenance is known.
      * project_scope == "factory" → obj must have provenance "factory".
      * project_scope == "<slug>" → obj must have provenance "<slug>" OR
        (provenance "factory" AND name in cross_links_for_type).
      * Cross-project (third-party slug ≠ project_scope) → always an error.
    """
    if not obj_provenance:
        return None  # unknown provenance — pass through

    if obj_provenance == project_scope:
        return None  # same project or both factory — always OK

    if project_scope == "factory":
        # Factory dashboards must only use factory components.
        if obj_provenance != "factory":
            return (
                f"scope violation: '{obj_name}' has provenance "
                f"'{obj_provenance}' but project_scope='factory' requires "
                f"factory-native components only"
            )
        return None  # obj_provenance == "factory" already handled above

    # project_scope is a third-party slug
    if obj_provenance == "factory":
        # Factory fallback — only allowed if the name is in cross_links
        if cross_links_for_type and obj_name in cross_links_for_type:
            return None  # explicitly cross-linked
        return (
            f"scope violation: '{obj_name}' has provenance 'factory' "
            f"but is not listed in cross_links for project '{project_scope}'. "
            f"Add it to the project's PROJECT.yaml cross_links section to "
            f"allow this dependency."
        )

    # obj_provenance is a different third-party slug
    return (
        f"scope violation: '{obj_name}' belongs to project "
        f"'{obj_provenance}' but dashboard project_scope is '{project_scope}'"
    )


def collect_deps(
    dashboards: "List",
    all_views: "List",
    all_sms: "List",
    all_customgroups: "List",
    project_scope: Optional[str] = None,
    cross_links: Optional["CollectDepsCrossLinks"] = None,
) -> "DepGraph":
    """Pure offline dependency walk starting from a set of dashboards.

    Traversal order:
      1. dashboard widgets → view names (extract_view_names_from_dashboards)
      2. resolved views → SM refs (extract_refs_from_views), dashboard
         widget metric_keys → SM refs, then each collected SM's formula →
         @supermetric:"<name>" refs, walked to a fixed point (SM → SM)
      3. resolved views → customgroup names (extract_customgroup_names_from_views)
      4. dashboard widgets → direct customgroup names (extract_customgroup_names_from_dashboards)
      5. each customgroup → any relationship-condition customgroup refs (recursion,
         typically a leaf; relationship.name may reference another group)

    Missing deps are recorded as errors in DepGraph.errors — the walk
    continues so callers see the full error list in one pass.

    Args:
        dashboards:       Starting dashboard objects.
        all_views:        Full corpus of ViewDef from the repo.
        all_sms:          Full corpus of SuperMetricDef from the repo.
        all_customgroups: Full corpus of CustomGroupDef from the repo.
        project_scope:    Optional project scope string.  When None, the scope
                          is auto-detected from the starting dashboards'
                          provenance (if they all share the same provenance).
                          Pass an explicit string to override.  See module
                          docstring for full semantics.
        cross_links:      Allowed factory fallbacks for a project-scoped walk
                          (a ``CollectDepsCrossLinks`` instance).  Only
                          relevant when project_scope is a third-party slug.

    Returns:
        DepGraph with .views, .supermetrics, .customgroups, .errors populated.
    """
    graph = DepGraph()

    # --- Auto-detect scope from starting dashboards -------------------------
    _scope = project_scope
    if _scope is None:
        _scope = _auto_detect_scope(dashboards)

    # Unpack cross_links sets for efficient lookup (avoid None checks inline)
    _cl_views: Optional[Set[str]] = None
    _cl_sms: Optional[Set[str]] = None
    _cl_cgs: Optional[Set[str]] = None
    if cross_links is not None:
        _cl_views = set(cross_links.views) if cross_links.views else set()
        _cl_sms = set(cross_links.supermetrics) if cross_links.supermetrics else set()
        _cl_cgs = set(cross_links.customgroups) if cross_links.customgroups else set()

    view_by_name = {v.name: v for v in all_views}
    sm_by_id = {sm.id.lower(): sm for sm in all_sms}
    # Build a name→SM map for scope-checking (SMs are resolved by UUID, but
    # the scope check uses the name from the cross_links list).
    sm_by_name = {sm.name: sm for sm in all_sms}
    cg_by_name = {cg.name: cg for cg in all_customgroups}
    known_cg_names = set(cg_by_name.keys())

    needed_views: "dict" = {}       # name -> ViewDef
    needed_sms: "dict" = {}         # id -> SuperMetricDef
    needed_cgs: "dict" = {}         # name -> CustomGroupDef
    _sm_scope_rejected: Set[Tuple[str, str]] = set()  # (uuid, source) already reported

    # --- Step 1: dashboard → view names ------------------------------------
    view_names = extract_view_names_from_dashboards(dashboards)
    for vname in view_names:
        if vname in needed_views:
            continue
        view = view_by_name.get(vname)
        if view is None:
            graph.errors.append(
                f"dashboard references unknown view '{vname}' "
                f"(not found in views corpus)"
            )
            continue
        # --- Scope check ---
        if _scope is not None:
            err = _scope_allows(
                getattr(view, "provenance", ""),
                view.name,
                _scope,
                _cl_views,
            )
            if err:
                graph.errors.append(err)
                continue  # do not recurse into out-of-scope view's SMs/CGs
        needed_views[vname] = view

    # --- Step 2a: resolved views → SM refs ---------------------------------
    import re as _re
    sm_uuid_re = _re.compile(
        r"sm_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        _re.IGNORECASE,
    )

    def _collect_sm_uuid(uuid_str: str, source: str) -> bool:
        """Take the SM into needed_sms.  True only when it is newly added."""
        sm_uuid = uuid_str.lower()
        if sm_uuid in needed_sms:
            return False
        sm = sm_by_id.get(sm_uuid)
        if sm is None:
            graph.errors.append(
                f"{source} references unknown SM uuid '{sm_uuid}'"
            )
            return False
        # --- Scope check ---
        if _scope is not None:
            err = _scope_allows(
                getattr(sm, "provenance", ""),
                sm.name,
                _scope,
                _cl_sms,
            )
            if err:
                # Name the referrer: for a formula cross-reference the
                # referring SM is the only pointer an operator has to where
                # the out-of-scope name came from.  One line per (referent,
                # referrer): a formula that names the same SM twice does
                # not repeat itself.
                if (sm_uuid, source) not in _sm_scope_rejected:
                    _sm_scope_rejected.add((sm_uuid, source))
                    graph.errors.append(f"{source}: {err}")
                return False
        needed_sms[sm_uuid] = sm
        return True

    sm_name_re = _re.compile(r'''supermetric:["'](.+?)["']''')
    sm_by_name = {sm.name: sm for sm in all_sms}

    for view in needed_views.values():
        for col in view.columns:
            m = sm_uuid_re.search(col.attribute)
            if m:
                _collect_sm_uuid(
                    m.group(1),
                    f"view '{view.name}' col '{col.display_name}'",
                )
                continue
            mn = sm_name_re.search(col.attribute)
            if mn:
                sm = sm_by_name.get(mn.group(1))
                if sm and sm.id:
                    _collect_sm_uuid(
                        sm.id,
                        f"view '{view.name}' col '{col.display_name}'",
                    )
                elif sm is None:
                    graph.errors.append(
                        f"view '{view.name}' col '{col.display_name}' "
                        f"references unknown SM name '{mn.group(1)}'"
                    )

    # --- Step 2b: dashboard widget metric_keys → SM refs -------------------
    # Scoreboard, MetricChart, ParetoAnalysis, HealthChart, and Heatmap
    # widgets may reference SMs directly by metric_key (sm_<uuid>).
    for dash in dashboards:
        for w in dash.widgets:
            src = f"dashboard '{dash.name}' widget '{w.local_id}'"
            # Scoreboard / MetricChart — list of MetricSpec
            for spec_config in [
                getattr(w, "scoreboard_config", None),
                getattr(w, "metric_chart_config", None),
            ]:
                if spec_config is None:
                    continue
                for spec in (getattr(spec_config, "metrics", None) or []):
                    m = sm_uuid_re.search(getattr(spec, "metric_key", "") or "")
                    if m:
                        _collect_sm_uuid(m.group(1), src)
            # HealthChart — single flat metric_key
            hc = getattr(w, "health_chart_config", None)
            if hc is not None:
                m = sm_uuid_re.search(getattr(hc, "metric_key", "") or "")
                if m:
                    _collect_sm_uuid(m.group(1), src)
            # ParetoAnalysis — single flat metric_key
            pa = getattr(w, "pareto_analysis_config", None)
            if pa is not None:
                m = sm_uuid_re.search(getattr(pa, "metric_key", "") or "")
                if m:
                    _collect_sm_uuid(m.group(1), src)
            # Heatmap — color_by_key and size_by_key per tab
            hm = getattr(w, "heatmap_config", None)
            if hm is not None:
                for tab in (getattr(hm, "tabs", None) or []):
                    for key_attr in ("color_by_key", "size_by_key"):
                        key = getattr(tab, key_attr, None) or ""
                        m = sm_uuid_re.search(key)
                        if m:
                            _collect_sm_uuid(m.group(1), src)

    # --- Step 2c: SM formulas → @supermetric:"<name>" refs (SM → SM) -----
    # Every emit path resolves the token to Super Metric|sm_<uuid> and
    # hard-errors when the referent is absent, so a referent is as much a
    # dependency as the SM a view column names.  Walked to a fixed point so
    # chains (A → B → C) are complete; cycles terminate on the visited set.
    def _accept_crossref(sm, source: str) -> bool:
        if not sm.id:
            graph.errors.append(
                f"{source}: formula references @supermetric:\"{sm.name}\" "
                f"and that super metric is in the corpus but carries no id, "
                f"so it has no sm_<uuid> to reference.  Give it an 'id:' in "
                f"its YAML."
            )
            return False
        return _collect_sm_uuid(sm.id, source)

    _walk_sm_crossrefs(
        list(needed_sms.values()), sm_by_name, _accept_crossref, graph.errors
    )

    # --- Step 3: resolved views → customgroup refs -------------------------
    cg_names_from_views = extract_customgroup_names_from_views(list(needed_views.values()))
    for cg_name in cg_names_from_views:
        if cg_name not in needed_cgs:
            cg = cg_by_name.get(cg_name)
            if cg is None:
                graph.errors.append(
                    f"view references unknown custom group '{cg_name}' "
                    f"(not found in customgroups corpus)"
                )
                continue
            # --- Scope check ---
            if _scope is not None:
                err = _scope_allows(
                    getattr(cg, "provenance", ""),
                    cg.name,
                    _scope,
                    _cl_cgs,
                )
                if err:
                    graph.errors.append(err)
                    continue
            needed_cgs[cg_name] = cg

    # --- Step 4: dashboards → direct customgroup refs ----------------------
    direct_cg_names = extract_customgroup_names_from_dashboards(dashboards, known_cg_names)
    for cg_name in direct_cg_names:
        if cg_name not in needed_cgs:
            cg = cg_by_name.get(cg_name)
            if cg is None:
                graph.errors.append(
                    f"dashboard widget directly references unknown custom group "
                    f"'{cg_name}'"
                )
                continue
            # --- Scope check ---
            if _scope is not None:
                err = _scope_allows(
                    getattr(cg, "provenance", ""),
                    cg.name,
                    _scope,
                    _cl_cgs,
                )
                if err:
                    graph.errors.append(err)
                    continue
            needed_cgs[cg_name] = cg

    # --- Step 5: customgroup rules → relationship-referenced group names ---
    # Recurse into relationship conditions (typically a leaf; guard with a
    # visited set to prevent infinite loops in pathological cases).
    _cg_queue = list(needed_cgs.keys())
    _cg_visited: set = set()
    while _cg_queue:
        cg_name = _cg_queue.pop(0)
        if cg_name in _cg_visited:
            continue
        _cg_visited.add(cg_name)
        cg = needed_cgs.get(cg_name) or cg_by_name.get(cg_name)
        if cg is None:
            continue
        for rule in (cg.rules or []):
            for rel_cond in (rule.get("relationship") or []):
                ref_name = rel_cond.get("name", "")
                if ref_name and ref_name not in needed_cgs:
                    ref_cg = cg_by_name.get(ref_name)
                    if ref_cg is None:
                        graph.errors.append(
                            f"custom group '{cg_name}' relationship condition "
                            f"references unknown group '{ref_name}'"
                        )
                    else:
                        # --- Scope check on relationship-referenced CG ---
                        if _scope is not None:
                            err = _scope_allows(
                                getattr(ref_cg, "provenance", ""),
                                ref_cg.name,
                                _scope,
                                _cl_cgs,
                            )
                            if err:
                                graph.errors.append(err)
                                continue
                        needed_cgs[ref_name] = ref_cg
                        _cg_queue.append(ref_name)

    graph.views = list(needed_views.values())
    graph.supermetrics = list(needed_sms.values())
    graph.customgroups = list(needed_cgs.values())
    return graph


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
    from vcfops_supermetrics.client import VCFOpsError
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
        client:               SM-extended VCFOpsClient (from vcfops_supermetrics.client).
        supermetrics:         SuperMetricDef list being synced (may be empty for dashboard-only sync).
        views:                ViewDef list being synced (may be empty).
        dashboards:           Dashboard list being synced (may be empty).
        customgroups:         CustomGroupDef list — used to validate customgroup references
                              found in view ``customgroup:`` fields. Pass the full repo corpus.
                              Defaults to [] (no customgroup validation).
        auto_enable_metrics:  If True, enable OOTB metrics with defaultMonitored=false on Default Policy.
        skip_metric_check:    If True, skip the OOTB metric describe check entirely.
        sm_name_map:          Optional {sm_name: uuid} map from the repo's SM YAML.
                              Used to annotate SM refs discovered by UUID-only with their names.

    Returns WalkResult with all outcomes recorded.
    """
    from vcfops_supermetrics.client import VCFOpsError

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
    # present in the provided corpus.  This is a static check — no API call.
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
        result._msg("OK", f"dependency walker: found {len(sm_by_uuid)} SM reference(s) — checking policy")
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
                # Part of this sync batch — will be enabled by the caller's enable step
                result._msg("OK", f"SM in sync batch (enable step will activate): '{name}'  ({uid})")
            else:
                # Pre-existing SM on instance, not yet enabled — auto-enable it.
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
                # Key not in describe — could be a property key or a valid but
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
            + " — sync marked incomplete (use --skip-metric-check to override)"
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
            f"OOTB metric check: {len(gaps)} metric(s) have defaultMonitored=false — "
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
    from vcfops_supermetrics.client import VCFOpsError
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
            f"SM '{sm_name}' ({sm_uuid}) has no resourceKinds on the instance — cannot enable. "
            "Run 'python3 -m vcfops_supermetrics sync' first."
        )
        return None
    return rks
