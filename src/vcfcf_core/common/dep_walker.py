"""Offline dependency walker for VCF Operations content (M2 row 3: the pure
half of ``vcfcf_common.dep_walker``).

Everything here traverses in-memory content models: reference extraction,
``@supermetric:"<name>"`` expansion, project-scope resolution and
``collect_deps``. Nothing here takes a client or touches an instance; the
live-sync advisory (``walk_and_check``, the describe fetch, SM enablement)
stays in ``vcfcf_common.dep_walker``, which re-exports every name below.

Given a set of loaded content models (SuperMetricDef, ViewDef, Dashboard,
CustomGroupDef), the factory's walker (this module plus the live half):

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

The online half (``walk_and_check`` and its ``WalkResult``) lives in
``vcfcf_common.dep_walker``.

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
    from ..supermetrics.loader import SuperMetricDef
    from ..dashboards.loader import ViewDef, Dashboard


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
    from ..supermetrics.crossref import crossref_names

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

def _pick_sm_by_name(
    candidates: "List",
    preferred_provenance: str,
):
    """Choose one SM among same-named candidates.

    Display names are unique within a project but not across the corpus: a
    third-party project may ship an SM whose name matches a factory one.  The
    documented scope semantics say same-project content wins and factory
    content is only the cross-linked fallback, so a flat ``{name: sm}`` dict
    (last loaded wins) is wrong in both directions.  Order of preference:

      1. provenance == ``preferred_provenance`` (the scope, or the referrer's
         own project when there is no scope)
      2. provenance == "factory" (the scope check then decides whether the
         cross-link allows it)
      3. the first candidate as loaded

    Emit-time resolution (``crossref.sm_name_to_uuid_map``) runs over the
    bundle's own SM set, which is what this walk produced, so the two agree
    once the walk has chosen.
    """
    if not candidates:
        return None
    if preferred_provenance:
        for sm in candidates:
            if getattr(sm, "provenance", "") == preferred_provenance:
                return sm
    for sm in candidates:
        if getattr(sm, "provenance", "") == "factory":
            return sm
    return candidates[0]


def _sm_candidates_by_name(all_sms: "List") -> "dict":
    """``{name: [sm, ...]}`` in load order, one list per display name."""
    out: "dict" = {}
    for sm in all_sms:
        out.setdefault(sm.name, []).append(sm)
    return out


def _walk_sm_crossrefs(
    seeds: "List",
    resolve: "Callable[[str, object], object]",
    accept: "Callable[[object, str], bool]",
    errors: List[str],
) -> None:
    """Breadth-first walk over ``@supermetric:"<name>"`` formula references.

    ``resolve(name, referrer)`` returns the SM the name means from the point
    of view of the referring SM, or None.  ``accept(sm, source)`` is called
    once per referent found; it returns True when the referent is newly taken
    into the result set (so its own formula gets walked too) and False when
    it was already present or was rejected.  A referent ``resolve`` cannot
    find is recorded in ``errors`` and the walk continues, so the caller sees
    every missing name in one pass.

    Tokens are found with ``vcfcf_supermetrics.crossref.crossref_names`` (the
    ``SM_CROSSREF_RE`` match): the ``@supermetric`` token is case-insensitive,
    the quoted name is matched exactly against the SM display name.  Cycles terminate via a visited set
    keyed on the SM id (falling back to the name for id-less fixtures).
    """
    from ..supermetrics.crossref import crossref_names

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
            ref = resolve(ref_name, sm)
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
    by_name = _sm_candidates_by_name(all_sms)
    result: "List" = []
    seen: Set[str] = set()
    errors: List[str] = []

    def _resolve(name: str, referrer) -> object:
        return _pick_sm_by_name(
            by_name.get(name, []), getattr(referrer, "provenance", "")
        )

    def _accept(sm, _source: str) -> bool:
        key = (getattr(sm, "id", "") or "").lower() or sm.name
        if key in seen:
            return False
        seen.add(key)
        result.append(sm)
        return True

    for sm in sms:
        _accept(sm, "")
    _walk_sm_crossrefs(list(sms), _resolve, _accept, errors)
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
    # Name -> candidate SMs.  Names can collide across projects; the picker
    # prefers the scope's own project, then factory (cross-link fallback).
    sm_candidates = _sm_candidates_by_name(all_sms)

    def _sm_for_name(name: str, referrer=None):
        preferred = _scope or getattr(referrer, "provenance", "") or ""
        return _pick_sm_by_name(sm_candidates.get(name, []), preferred)

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
                sm = _sm_for_name(mn.group(1), view)
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
        list(needed_sms.values()), _sm_for_name, _accept_crossref, graph.errors
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
