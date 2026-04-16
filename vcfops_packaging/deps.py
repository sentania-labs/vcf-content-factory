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

# Pattern for instanced metric keys in SM formulas:
#   "net:Aggregate of all instances|packetsPerSec"  ->  "net|packetsPerSec"
#   "cpu:core 0|usage"                              ->  "cpu|usage"
# The describe cache stores only the base group|stat form.
_INSTANCED_KEY_RE = re.compile(r"^([^|:]+):[^|]+\|(.+)$")


def _is_sm_ref(metric_key: str) -> bool:
    """Return True if the key is a super-metric reference (not a built-in)."""
    k = metric_key.strip()
    return k.lower().startswith(_SUPER_METRIC_PREFIX) or bool(_SM_KEY_RE.match(k))


def _normalize_metric_key(metric_key: str) -> str:
    """Normalize an instanced metric key to its base form.

    The VCF Ops super metric DSL allows referencing instanced stat keys with
    the syntax ``group:instance_spec|stat`` (e.g.
    ``net:Aggregate of all instances|packetsPerSec``).  The adapter describe
    surface only exposes the base form ``group|stat``.  Strip the instance
    specifier so cache lookups succeed.

    Non-instanced keys (e.g. ``cpu|usage_average``) are returned unchanged.
    """
    m = _INSTANCED_KEY_RE.match(metric_key.strip())
    if m:
        return f"{m.group(1)}|{m.group(2)}"
    return metric_key


# ---------------------------------------------------------------------------
# Super metric formula walker
# ---------------------------------------------------------------------------


def _refs_from_formula(formula: str, sm_name: str) -> list[MetricReference]:
    """Extract built-in metric references from a super metric formula.

    Parses ``${adaptertype=X, objecttype=Y, metric=KEY, ...}`` entries.
    Skips ``${this, ...}`` entries (bound to the assigned object — no
    explicit adaptertype/objecttype, handled by resource_kinds assignment).
    Also skips entries whose ``metric=`` value is a super-metric reference.
    """
    refs: list[MetricReference] = []
    source_desc = f"SM {sm_name!r}"
    for m in _RESOURCE_ENTRY_RE.finditer(formula):
        inner = m.group(1).strip()
        # ${this, ...} — no adaptertype, skip
        head = inner.split(",", 1)[0].strip().lower()
        if head == "this":
            continue
        pairs = _split_kv(inner)
        kv: dict[str, str] = {k: v for k, v in pairs}
        adapter_kind = kv.get("adaptertype", "").strip()
        resource_kind = kv.get("objecttype", "").strip()
        metric_key = kv.get("metric", "").strip()
        # Attribute= is also used (property references) — treat the same way.
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
    renderer auto-prefixes Super Metric|sm_<uuid> — we skip those.
    The adapter_kind / resource_kind come from the view's subject.
    """
    refs: list[MetricReference] = []
    ak = view.adapter_kind
    rk = view.resource_kind
    source_desc = f"view {view.name!r}"
    for col in view.columns:
        attr = col.attribute.strip()
        if _is_sm_ref(attr):
            continue
        # "Super Metric|sm_..." already filtered above, but also skip
        # any other non-stat-key attributes (e.g. property: strings)
        # by checking for the pipe separator which stat keys always have.
        # Properties like "summary|runtime|powerState" also have pipes —
        # include them; the describe cache will classify them as unknown
        # (which is correct, since property keys don't appear in statkeys).
        # However, we must NOT skip them silently — unknown keys cause an
        # audit error, which is the correct signal (the author should either
        # declare them as properties-not-metrics or the cache needs updating).
        # For now, extract all non-SM attribute references and let the audit
        # decide.
        refs.append(MetricReference(
            adapter_kind=ak,
            resource_kind=rk,
            metric_key=attr,
            source_desc=source_desc,
        ))
    return refs


# ---------------------------------------------------------------------------
# Dashboard widget walker
# ---------------------------------------------------------------------------


def _refs_from_widgets(dashboard) -> list[MetricReference]:
    """Extract built-in metric references from all supported widget types.

    Widget types handled:
      ResourceList, View, TextDisplay, AlertList, ProblemAlertsList
        — no metric keys to extract.
      Scoreboard, MetricChart
        — metrics[] each have adapter_kind, resource_kind, metric_key.
      HealthChart, ParetoAnalysis
        — flat adapter_kind + resource_kind + metric_key fields.
      Heatmap
        — configs[].color_by_key and configs[].size_by_key per tab.
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
                        metric_key=ms.metric_key,
                        source_desc=wsrc,
                    ))

        elif wt == "MetricChart" and w.metric_chart_config is not None:
            for ms in w.metric_chart_config.metrics:
                if ms.metric_key and not _is_sm_ref(ms.metric_key):
                    refs.append(MetricReference(
                        adapter_kind=ms.adapter_kind,
                        resource_kind=ms.resource_kind,
                        metric_key=ms.metric_key,
                        source_desc=wsrc,
                    ))

        elif wt == "HealthChart" and w.health_chart_config is not None:
            hc = w.health_chart_config
            if hc.metric_key and not _is_sm_ref(hc.metric_key):
                refs.append(MetricReference(
                    adapter_kind=hc.adapter_kind,
                    resource_kind=hc.resource_kind,
                    metric_key=hc.metric_key,
                    source_desc=wsrc,
                ))

        elif wt == "ParetoAnalysis" and w.pareto_analysis_config is not None:
            pa = w.pareto_analysis_config
            if pa.metric_key and not _is_sm_ref(pa.metric_key):
                refs.append(MetricReference(
                    adapter_kind=pa.adapter_kind,
                    resource_kind=pa.resource_kind,
                    metric_key=pa.metric_key,
                    source_desc=wsrc,
                ))

        elif wt == "Heatmap" and w.heatmap_config is not None:
            for tab in w.heatmap_config.tabs:
                if tab.color_by_key and not _is_sm_ref(tab.color_by_key):
                    refs.append(MetricReference(
                        adapter_kind=tab.adapter_kind,
                        resource_kind=tab.resource_kind,
                        metric_key=tab.color_by_key,
                        source_desc=f"{wsrc} tab {tab.name!r} colorBy",
                    ))
                if tab.size_by_key and not _is_sm_ref(tab.size_by_key):
                    refs.append(MetricReference(
                        adapter_kind=tab.adapter_kind,
                        resource_kind=tab.resource_kind,
                        metric_key=tab.size_by_key,
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
        for ref in _refs_from_formula(sm.formula, sm.name):
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
