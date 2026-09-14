"""Metric reference extractor for bundle dependency auditing.

Walks all content objects in a bundle (super metrics, views, dashboards)
and yields unique ``MetricReference`` tuples that name a *built-in*
(adapter-describe-surface) metric key.  Super-metric self-references
(``sm_<uuid>`` / ``Super Metric|`` prefix) are excluded.

Public API::

    @dataclass
    class MetricReference:
        adapter_kind: str
        resource_kind: str
        metric_key: str
        source_desc: str  # e.g. "SM '[VCF Content Factory] Foo Bar'"

    def extract_metric_references(bundle: Bundle) -> list[MetricReference]

"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .loader import Bundle


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass
class MetricReference:
    """A reference to a single built-in metric from a bundle artifact."""
    adapter_kind: str
    resource_kind: str
    metric_key: str
    source_desc: str  # human-readable provenance for audit output


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Pattern matches a single ${...} resource entry in a super metric formula.
_RESOURCE_ENTRY_RE = re.compile(r"\$\{([^}]*)\}", re.DOTALL)

# Split a resource entry's key=value pairs at commas (respects nested parens).
# We use a simple heuristic: split on commas that are NOT inside parentheses.
def _split_kv(inner: str) -> list[tuple[str, str]]:
    """Return a list of (key, value) pairs from a resource-entry inner string.

    Splits on top-level commas only (ignores commas inside nested
    ``${...}`` or ``(...)`` sub-expressions).
    """
    pairs: list[tuple[str, str]] = []
    depth = 0
    current = ""
    for ch in inner:
        if ch in ("(", "{", "["):
            depth += 1
            current += ch
        elif ch in (")", "}", "]"):
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            part = current.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                pairs.append((k.strip().lower(), v.strip()))
            current = ""
        else:
            current += ch
    part = current.strip()
    if part and "=" in part:
        k, _, v = part.partition("=")
        pairs.append((k.strip().lower(), v.strip()))
    return pairs


_SM_KEY_RE = re.compile(r"^sm_[0-9a-f\-]+$", re.IGNORECASE)
_SUPER_METRIC_PREFIX = "super metric|"
# Unresolved authoring-time SM cross-reference, e.g. supermetric:"<name>"
# (CLAUDE.md "Cross-reference syntax" table, View column -> SM row). Views
# carry this literal form until render_views_xml() resolves it to sm_<uuid>
# (see vcfops_dashboards/render.py:558-585), code that walks *loader*
# objects (as the dependency auditor does) sees the unresolved form and must
# recognise it too, or it hard-fails treating the SM name as an unknown
# built-in metric key.
_UNRESOLVED_SM_REF_PREFIX = "supermetric:"
# Unresolved authoring-time SM cross-reference inside an *SM formula*, e.g.
# metric=@supermetric:"<name>" (same skill table, SM formula -> SM row). Note
# the leading "@": the formula form and the view-column form differ by that one
# character, so the view constant above does not cover it. Formulas keep this
# token until emit/push time (vcfops_supermetrics.crossref), so the auditor,
# which walks loader objects, sees the unresolved form and must skip it.
_UNRESOLVED_SM_FORMULA_REF_PREFIX = "@supermetric:"


def _normalize_instanced_group_key(attribute: str) -> str:
    """Derive the describe-cache base key from a loader-synthesized
    instanced_group member column ``attribute`` string.

    Member columns synthesize ``attribute`` as
    ``f"{prefix}:{sample_instance}|{suffix}"`` (see
    ``InstancedGroupSpec``/``ViewColumn`` in vcfops_dashboards/loader.py).
    ``sample_instance`` itself may contain further ``:`` / ``|`` tokens
    (e.g. ``"356893|snapshot:snapshot-16"``), so the synthesized string can
    have more than one "|"-delimited segment. The describe cache stores the
    flat, un-instanced form: split on "|", drop the ``:<instance>`` suffix
    from each segment, and rejoin.

    Example: prefix "diskspace", sample_instance "356893|snapshot:snapshot-16",
    suffix "creator" synthesizes to
    ``"diskspace:356893|snapshot:snapshot-16|creator"``, which normalizes to
    ``"diskspace|snapshot|creator"``, matching the describe cache's
    ``diskspace|snapshot|creator`` property key.
    """
    segments = attribute.split("|")
    return "|".join(seg.split(":", 1)[0] for seg in segments)


def _is_sm_ref(metric_key: str) -> bool:
    """Return True if the key is a super-metric reference (not a built-in)."""
    k = metric_key.strip()
    return (
        k.lower().startswith(_SUPER_METRIC_PREFIX)
        or k.lower().startswith(_UNRESOLVED_SM_REF_PREFIX)
        or k.lower().startswith(_UNRESOLVED_SM_FORMULA_REF_PREFIX)
        or bool(_SM_KEY_RE.match(k))
    )


def _normalize_metric_key(metric_key: str) -> str:
    """Normalize an instanced metric key to its base form.

    The VCF Ops super metric DSL allows referencing instanced stat keys with
    the syntax ``group:instance_spec|stat`` (e.g.
    ``net:Aggregate of all instances|packetsPerSec``), and multi-segment
    property keys carry the same ``:<instance>`` token on any ``|``-delimited
    segment, not just the first (e.g.
    ``diskspace:262|snapshot:snapshot-1|used`` or
    ``vCommunity|Licensing:Evaluation Mode|Edition Key``). The adapter
    describe surface only exposes the flat, un-instanced form. Delegate to
    ``_normalize_instanced_group_key``'s segment-local rule (split on "|",
    strip ``:<instance>`` from each segment, rejoin), verified against the
    full vendor ``isInstancedGroup`` corpus to be a strict superset of the
    single-segment form this function previously handled alone, so callers
    that expected only the leading-segment case still get identical output.

    Non-instanced keys (e.g. ``cpu|usage_average``) are returned unchanged.
    """
    return _normalize_instanced_group_key(metric_key.strip())


# ---------------------------------------------------------------------------
# Super metric formula walker
# ---------------------------------------------------------------------------


def _refs_from_formula(
    formula: str,
    sm_name: str,
    resource_kinds: "list | None" = None,
) -> list[MetricReference]:
    """Extract built-in metric references from a super metric formula.

    Parses ``${adaptertype=X, objecttype=Y, metric=KEY, ...}`` entries.
    Also skips entries whose ``metric=`` value is a super-metric reference.

    ``${this, metric=KEY}`` entries carry no adaptertype/objecttype of their
    own: they bind KEY to the object the super metric is assigned to. That
    assignment is the SM's ``resource_kinds:`` declaration, so each declared
    (adapterKindKey, resourceKindKey) pair yields one auditable reference for
    KEY. Pass ``resource_kinds`` in the loader/wire shape (a list of
    ``{"adapterKindKey": ..., "resourceKindKey": ...}`` mappings; the
    snake_case authoring keys are accepted too). A ``this``-bound metric key
    with no usable resource_kinds assignment is UNAUDITABLE and raises
    AuditError; it must never be silently skipped (pre-2026-08 behavior
    skipped every ``${this, ...}`` entry, leaving this-bound keys invisible
    to the describe-cache audit in every build).
    """
    refs: list[MetricReference] = []
    source_desc = f"SM {sm_name!r}"
    for m in _RESOURCE_ENTRY_RE.finditer(formula):
        inner = m.group(1).strip()
        head = inner.split(",", 1)[0].strip().lower()
        pairs = _split_kv(inner)
        kv: dict[str, str] = {k: v for k, v in pairs}
        if head == "this":
            metric_key = kv.get("metric", "").strip() or kv.get("attribute", "").strip()
            if not metric_key or _is_sm_ref(metric_key):
                continue
            declared_pairs: list[tuple[str, str]] = []
            for rk in (resource_kinds or []):
                if not isinstance(rk, dict):
                    continue
                ak = str(rk.get("adapterKindKey") or rk.get("adapter_kind_key") or "").strip()
                rkk = str(rk.get("resourceKindKey") or rk.get("resource_kind_key") or "").strip()
                if ak and rkk:
                    declared_pairs.append((ak, rkk))
            if not declared_pairs:
                from .audit import AuditError
                raise AuditError(
                    f"{source_desc} uses a ${{this, metric=...}} reference "
                    f"({metric_key!r}) but declares no usable resource_kinds "
                    "assignment, so the metric key cannot be audited against "
                    "the describe cache. Declare resource_kinds: on the super "
                    "metric (adapter_kind_key / resource_kind_key pairs)."
                )
            metric_key = _normalize_metric_key(metric_key)
            for ak, rkk in declared_pairs:
                refs.append(MetricReference(
                    adapter_kind=ak,
                    resource_kind=rkk,
                    metric_key=metric_key,
                    source_desc=source_desc,
                ))
            continue
        adapter_kind = kv.get("adaptertype", "").strip()
        resource_kind = kv.get("objecttype", "").strip()
        metric_key = kv.get("metric", "").strip()
        # Attribute= is also used (property references), treat the same way.
        if not metric_key:
            metric_key = kv.get("attribute", "").strip()
        if not metric_key or not adapter_kind or not resource_kind:
            continue
        if _is_sm_ref(metric_key):
            continue
        # Normalize instanced key form (e.g. "net:Aggregate of all instances|packetsPerSec"
        # -> "net|packetsPerSec") before adding to the reference list.
        metric_key = _normalize_metric_key(metric_key)
        refs.append(MetricReference(
            adapter_kind=adapter_kind,
            resource_kind=resource_kind,
            metric_key=metric_key,
            source_desc=source_desc,
        ))
    return refs


# ---------------------------------------------------------------------------
# View column walker
# ---------------------------------------------------------------------------


def _refs_from_view(view) -> list[MetricReference]:
    """Extract built-in metric references from a ViewDef's columns.

    View columns reference metrics via their ``attribute`` field.  The
    renderer auto-prefixes Super Metric|sm_<uuid>, we skip those.
    The adapter_kind / resource_kind come from the view's subject(s): a
    ``subjects:`` view is audited once per kind (``view.subject_kinds``),
    because a column can be policy-disabled on the second kind while
    enabled on the first and would render blank there.  A column bound to
    one kind via ``subject:`` only ever resolves against that kind on the
    product (the adapterKind/resourceKind Properties are a kind filter,
    see knowledge/context/api-surface/view_multi_subject_column_binding.md),
    so it is audited against that one kind only; fanning it out would
    raise a false "metric key not found" for the other kinds.
    """
    # (metric key, kinds to audit it against); None means every subject kind.
    keys: list[tuple[str, list[tuple[str, str]] | None]] = []
    source_desc = f"view {view.name!r}"
    for col in view.columns:
        if getattr(col, "time_segment", None) is not None:
            # A time-segment ("Interval Breakdown") pseudo-column carries no
            # describe-cache key: its attributeKey is a literal the renderer
            # synthesizes (see loader.TimeSegmentSpec), not a metric on the
            # subject kind. Skip it exactly like the instanced-group driver
            # column below; auditing it fails every bundle build with
            # "metric key not found in the describe cache: Interval Breakdown".
            continue
        ig = getattr(col, "instanced_group", None)
        if ig is not None:
            # The driver column ("Instance Name" sentinel, prefix and
            # suffix both unset) has no describe-cache key at all: it turns
            # on fan-out mode for the view and carries no metric/property
            # reference of its own, so it is (correctly) skipped.
            #
            # Member columns DO reference a real describe-cache key: the
            # loader synthesizes their `attribute` as
            # "{prefix}:{sample_instance}|{suffix}", which embeds the
            # instance token in the middle segment(s). Without deriving and
            # auditing the base key here, any built-in whose *only*
            # reference in the bundle is via an instanced_group member
            # column silently skips the dependency/enable gate (see
            # knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md
            # and the DEF-016/PR#70 review that caught this). Emit a
            # reference using the normalized base key so it is audited
            # exactly like a direct reference.
            if ig.is_driver:
                continue
            keys.append((_normalize_instanced_group_key(col.attribute.strip()), _column_kinds(col)))
            continue
        attr = col.attribute.strip()
        if _is_sm_ref(attr):
            continue
        # Normalize instanced metric key form (e.g.
        # "net:Aggregate of all instances|packetsPerSec" -> "net|packetsPerSec").
        # The describe cache only stores the base group|stat form.
        keys.append((_normalize_metric_key(attr), _column_kinds(col)))

    # Subject-filter metric keys (SubjectType filter= JSON) are never emitted
    # as columns of their own, but they still reference a describe-cache key
    # and must be audited the same way, see issue #72 / the Codex P1 sibling
    # blind spot in audit.py's staged-bundle XML walker.
    for group in (view.subject_filter or []):
        for cond in group:
            key = (cond.metric_key or "").strip()
            if not key or _is_sm_ref(key):
                continue
            keys.append((_normalize_metric_key(key), None))

    refs: list[MetricReference] = []
    for ak, rk in view.subject_kinds:
        for key, kinds in keys:
            if kinds is not None and (ak, rk) not in kinds:
                continue
            refs.append(MetricReference(
                adapter_kind=ak,
                resource_kind=rk,
                metric_key=key,
                source_desc=source_desc,
            ))
    return refs


def _column_kinds(col) -> list[tuple[str, str]] | None:
    """Kinds a column is audited against: its bound ``subject:`` only, or
    None for every subject kind of the view (unbound column)."""
    sub = getattr(col, "subject", None)
    if sub is None:
        return None
    return [(sub.adapter_kind, sub.resource_kind)]


# ---------------------------------------------------------------------------
# Dashboard widget walker
# ---------------------------------------------------------------------------


def _refs_from_widgets(dashboard) -> list[MetricReference]:
    """Extract built-in metric references from all supported widget types.

    Widget types handled:
      ResourceList, View, TextDisplay, AlertList, ProblemAlertsList:
        no metric keys to extract.
      Scoreboard, MetricChart:
        metrics[] each have adapter_kind, resource_kind, metric_key.
      HealthChart, ParetoAnalysis:
        flat adapter_kind + resource_kind + metric_key fields.
      Heatmap:
        configs[].color_by_key and configs[].size_by_key per tab.
    """
    refs: list[MetricReference] = []
    source_prefix = f"dashboard {dashboard.name!r}"

    for w in dashboard.widgets:
        wt = w.type
        wsrc = f"{source_prefix} widget {w.local_id!r} ({wt})"

        if wt in ("Scoreboard",) and w.scoreboard_config is not None:
            for ms in w.scoreboard_config.metrics:
                if ms.metric_key and not _is_sm_ref(ms.metric_key):
                    refs.append(MetricReference(
                        adapter_kind=ms.adapter_kind,
                        resource_kind=ms.resource_kind,
                        metric_key=_normalize_metric_key(ms.metric_key),
                        source_desc=wsrc,
                    ))

        elif wt == "MetricChart" and w.metric_chart_config is not None:
            for ms in w.metric_chart_config.metrics:
                if ms.metric_key and not _is_sm_ref(ms.metric_key):
                    refs.append(MetricReference(
                        adapter_kind=ms.adapter_kind,
                        resource_kind=ms.resource_kind,
                        metric_key=_normalize_metric_key(ms.metric_key),
                        source_desc=wsrc,
                    ))

        elif wt == "HealthChart" and w.health_chart_config is not None:
            hc = w.health_chart_config
            if hc.metric_key and not _is_sm_ref(hc.metric_key):
                refs.append(MetricReference(
                    adapter_kind=hc.adapter_kind,
                    resource_kind=hc.resource_kind,
                    metric_key=_normalize_metric_key(hc.metric_key),
                    source_desc=wsrc,
                ))

        elif wt == "ParetoAnalysis" and w.pareto_analysis_config is not None:
            pa = w.pareto_analysis_config
            if pa.metric_key and not _is_sm_ref(pa.metric_key):
                refs.append(MetricReference(
                    adapter_kind=pa.adapter_kind,
                    resource_kind=pa.resource_kind,
                    metric_key=_normalize_metric_key(pa.metric_key),
                    source_desc=wsrc,
                ))

        elif wt == "Heatmap" and w.heatmap_config is not None:
            for tab in w.heatmap_config.tabs:
                if tab.color_by_key and not _is_sm_ref(tab.color_by_key):
                    refs.append(MetricReference(
                        adapter_kind=tab.adapter_kind,
                        resource_kind=tab.resource_kind,
                        metric_key=_normalize_metric_key(tab.color_by_key),
                        source_desc=f"{wsrc} tab {tab.name!r} colorBy",
                    ))
                if tab.size_by_key and not _is_sm_ref(tab.size_by_key):
                    refs.append(MetricReference(
                        adapter_kind=tab.adapter_kind,
                        resource_kind=tab.resource_kind,
                        metric_key=_normalize_metric_key(tab.size_by_key),
                        source_desc=f"{wsrc} tab {tab.name!r} sizeBy",
                    ))
        # ResourceList, View, TextDisplay, AlertList, ProblemAlertsList:
        # no metric key references to extract.

    return refs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_metric_references(bundle: "Bundle") -> list[MetricReference]:
    """Walk all content in the bundle and return unique built-in metric refs.

    Deduplication key: (adapter_kind, resource_kind, metric_key).
    When the same key appears in multiple sources, the first source_desc wins.

    Excludes super-metric self-references (sm_<uuid> / Super Metric| prefix).

    Args:
        bundle: A loaded ``Bundle`` object (from ``vcfops_packaging.loader``).

    Returns:
        List of unique ``MetricReference`` objects.
    """
    seen: dict[tuple[str, str, str], MetricReference] = {}

    def _add(ref: MetricReference) -> None:
        k = (ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if k not in seen:
            seen[k] = ref

    # --- Super metrics ---
    for sm in bundle.supermetrics:
        for ref in _refs_from_formula(
            sm.formula, sm.name, getattr(sm, "resource_kinds", None)
        ):
            _add(ref)

    # --- Views ---
    for v in bundle.views:
        for ref in _refs_from_view(v):
            _add(ref)

    # --- Dashboards ---
    for d in bundle.dashboards:
        for ref in _refs_from_widgets(d):
            _add(ref)

    return list(seen.values())
