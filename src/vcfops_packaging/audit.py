"""Build-time dependency audit for bundle packages.

Walks every content artifact in a bundle, resolves each built-in metric
reference against the adapter describe-surface cache, and either auto-adds
needed entries to ``builtin_metric_enables`` or fails the build when
dependencies cannot be resolved.

Public API::

    class AuditError(RuntimeError): ...

    @dataclass
    class AuditResult:
        refs: list[MetricReference]       # all unique refs found
        unknown: list[MetricReference]    # not in describe cache at all
        enabled: list[MetricReference]    # defaultMonitored=true (no action needed)
        needs_enable: list[MetricReference]  # defaultMonitored=false
        auto_added: list[BuiltinMetricEnable]  # auto-created (mode=auto only)

    def audit_bundle_dependencies(
        bundle: Bundle,
        describe_cache: DescribeCache,
        *,
        mode: Literal["auto", "strict", "lax"] = "auto",
    ) -> AuditResult

    def print_audit_summary(result: AuditResult, mode: str) -> None

Also contains the ``analyze`` path for pre-built staged bundle directories:

    def analyze_staged_bundle(
        bundle_dir: Path,
        describe_cache: DescribeCache,
    ) -> AuditResult
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Optional

from .deps import MetricReference, _is_sm_ref, _normalize_metric_key, _refs_from_formula
from .describe import DescribeCache

if TYPE_CHECKING:
    from .loader import Bundle, BuiltinMetricEnable


# ---------------------------------------------------------------------------
# Exceptions + result types
# ---------------------------------------------------------------------------


class AuditError(RuntimeError):
    """Raised when the audit cannot proceed or finds a hard violation."""


@dataclass
class AuditResult:
    """Output of an audit run."""
    refs: list                      # list[MetricReference] — all unique refs
    unknown: list                   # list[MetricReference] — not in describe
    enabled: list                   # list[MetricReference] — defaultMonitored=true
    needs_enable: list              # list[MetricReference] — defaultMonitored=false
    auto_added: list                # list[BuiltinMetricEnable] — auto-created


# ---------------------------------------------------------------------------
# Bundle declares() helper
# ---------------------------------------------------------------------------


def _bundle_declares(bundle: "Bundle", ref: MetricReference) -> bool:
    """Return True if the bundle's builtin_metric_enables already covers ref."""
    for bme in bundle.builtin_metric_enables:
        if (
            bme.adapter_kind == ref.adapter_kind
            and bme.resource_kind == ref.resource_kind
            and bme.metric_key == ref.metric_key
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Main audit entry point
# ---------------------------------------------------------------------------


def audit_bundle_dependencies(
    bundle: "Bundle",
    describe_cache: DescribeCache,
    *,
    mode: Literal["auto", "strict", "lax"] = "auto",
) -> AuditResult:
    """Audit all metric references in a bundle against the describe cache.

    Args:
        bundle: Loaded Bundle object.
        describe_cache: Populated DescribeCache (may be live or offline).
        mode: One of:
            "auto"   — auto-add any defaultMonitored=false refs that are not
                       already declared in builtin_metric_enables (default).
            "strict" — fail the build if any defaultMonitored=false ref is
                       not explicitly declared in the bundle manifest.
            "lax"    — log but never fail; no auto-adds.

    Returns:
        AuditResult dataclass.

    Raises:
        AuditError: if unknown keys exist (all modes), or if undeclared
            defaultMonitored=false refs are found in strict mode.
        DescribeCacheError: if a needed cache file is absent and the cache
            cannot be refreshed (propagated from DescribeCache.resolve_metric).
    """
    from .deps import extract_metric_references

    # Detect missing cache files before we start resolving, so we can emit
    # a single actionable error rather than a per-key "None" cascade.
    refs = extract_metric_references(bundle)
    _check_cache_coverage(refs, describe_cache)

    unknown: list[MetricReference] = []
    enabled: list[MetricReference] = []
    needs_enable: list[MetricReference] = []

    for ref in refs:
        info = describe_cache.resolve_metric(ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if info is None:
            unknown.append(ref)
        elif info.default_monitored:
            enabled.append(ref)
        else:
            needs_enable.append(ref)

    # Unknown keys are always a hard error.
    if unknown:
        lines = ["The following metric keys were not found in the adapter describe cache:"]
        for r in unknown:
            lines.append(
                f"  {r.adapter_kind}/{r.resource_kind}  {r.metric_key}"
                f"  (referenced by {r.source_desc})"
            )
        lines.append("")
        lines.append(
            "This usually means the metric key is misspelled, or the describe cache needs "
            "refreshing. Run: python3 -m vcfops_packaging refresh-describe "
            f"--kind {unknown[0].adapter_kind}:{unknown[0].resource_kind}"
        )
        raise AuditError("\n".join(lines))

    auto_added: list = []

    if mode == "strict":
        undeclared = [r for r in needs_enable if not _bundle_declares(bundle, r)]
        if undeclared:
            lines = [
                "strict-deps mode: the following defaultMonitored=false metrics are "
                "referenced but not declared in builtin_metric_enables:"
            ]
            for r in undeclared:
                lines.append(
                    f"  {r.adapter_kind}/{r.resource_kind}  {r.metric_key}"
                    f"  (from {r.source_desc})"
                )
            lines.append("")
            lines.append(
                "Add these entries to the 'builtin_metric_enables' section of the "
                "bundle manifest, or use the default (auto) mode to add them automatically."
            )
            raise AuditError("\n".join(lines))

    elif mode == "auto":
        from .loader import BuiltinMetricEnable
        for r in needs_enable:
            if not _bundle_declares(bundle, r):
                auto_added.append(BuiltinMetricEnable(
                    adapter_kind=r.adapter_kind,
                    resource_kind=r.resource_kind,
                    metric_key=r.metric_key,
                    reason=f"Auto-detected: referenced by {r.source_desc}, defaultMonitored=false",
                ))

    # lax: nothing additional

    return AuditResult(
        refs=refs,
        unknown=unknown,
        enabled=enabled,
        needs_enable=needs_enable,
        auto_added=auto_added,
    )


def _check_cache_coverage(refs: list[MetricReference], cache: DescribeCache) -> None:
    """Raise AuditError for any (adapter_kind, resource_kind) pair that has no
    cache file and for which we cannot do a live refresh."""
    missing_pairs: set[tuple[str, str]] = set()
    for ref in refs:
        pair = (ref.adapter_kind, ref.resource_kind)
        if pair in missing_pairs:
            continue
        if not cache.has_cache_file(ref.adapter_kind, ref.resource_kind):
            missing_pairs.add(pair)
    if missing_pairs:
        pairs_str = ", ".join(f"{ak}:{rk}" for ak, rk in sorted(missing_pairs))
        raise AuditError(
            f"No describe cache files for: {pairs_str}\n"
            "Run: python3 -m vcfops_packaging refresh-describe "
            f"--kind {pairs_str.replace(', ', ' --kind ')}"
        )


# ---------------------------------------------------------------------------
# Audit summary printer
# ---------------------------------------------------------------------------


def print_audit_summary(result: AuditResult, mode: str) -> None:
    """Print a human-readable audit summary to stdout."""
    total = len(result.refs)
    print(f"\ndependency audit (mode={mode})")
    print(f"  references: {total} total")
    if result.enabled:
        print(f"  resolved:   {len(result.enabled)} defaultMonitored=true (no enable needed)")
    if result.needs_enable:
        print(f"  enablement: {len(result.needs_enable)} defaultMonitored=false")
    if result.auto_added:
        print(f"    auto-added to builtin_metric_enables ({len(result.auto_added)}):")
        for bme in result.auto_added:
            print(f"      {bme.adapter_kind}/{bme.resource_kind}  {bme.metric_key}"
                  f"  ({bme.reason})")
    if result.needs_enable and not result.auto_added and mode == "lax":
        for r in result.needs_enable:
            print(f"    WARN: {r.adapter_kind}/{r.resource_kind}  {r.metric_key}"
                  f"  (from {r.source_desc})")
    if not result.refs:
        print("  no metric references found")


# ---------------------------------------------------------------------------
# Staged-bundle analyzer (Step 2.4 — analyze CLI)
# ---------------------------------------------------------------------------


def analyze_staged_bundle(
    bundle_dir: Path,
    describe_cache: DescribeCache,
) -> AuditResult:
    """Run a dependency audit against a pre-built staged bundle directory.

    Reads ``content/supermetrics.json``, ``content/views_content.xml``, and
    ``content/dashboard.json`` from ``bundle_dir`` and extracts metric
    references without going through the YAML loaders.

    Args:
        bundle_dir: Path containing a ``content/`` subdirectory with pre-built
            artifacts.
        describe_cache: Populated DescribeCache.

    Returns:
        AuditResult (no auto_added list — analyze is read-only).

    Raises:
        AuditError on unknown keys or missing cache files.
        FileNotFoundError if required artifact files are absent.
    """
    refs: list[MetricReference] = []
    seen: dict[tuple[str, str, str], MetricReference] = {}

    def _add(ref: MetricReference) -> None:
        k = (ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if k not in seen:
            seen[k] = ref

    content_dir = bundle_dir / "content"

    # --- Super metrics ---
    sm_path = content_dir / "supermetrics.json"
    if sm_path.exists():
        sm_data: dict = json.loads(sm_path.read_text(encoding="utf-8"))
        for sm_id, sm_obj in sm_data.items():
            formula = sm_obj.get("formula") or ""
            sm_name = sm_obj.get("name") or sm_id
            for ref in _refs_from_formula(formula, sm_name):
                _add(ref)

    # --- Views (XML) ---
    views_path = content_dir / "views_content.xml"
    if views_path.exists():
        for ref in _refs_from_views_xml(views_path):
            _add(ref)

    # --- Dashboard ---
    dash_path = content_dir / "dashboard.json"
    if dash_path.exists():
        for ref in _refs_from_dashboard_json(dash_path):
            _add(ref)

    all_refs = list(seen.values())
    _check_cache_coverage(all_refs, describe_cache)

    unknown: list[MetricReference] = []
    enabled: list[MetricReference] = []
    needs_enable: list[MetricReference] = []

    for ref in all_refs:
        info = describe_cache.resolve_metric(ref.adapter_kind, ref.resource_kind, ref.metric_key)
        if info is None:
            unknown.append(ref)
        elif info.default_monitored:
            enabled.append(ref)
        else:
            needs_enable.append(ref)

    if unknown:
        lines = ["The following metric keys were not found in the adapter describe cache:"]
        for r in unknown:
            lines.append(
                f"  {r.adapter_kind}/{r.resource_kind}  {r.metric_key}"
                f"  (referenced by {r.source_desc})"
            )
        raise AuditError("\n".join(lines))

    return AuditResult(
        refs=all_refs,
        unknown=unknown,
        enabled=enabled,
        needs_enable=needs_enable,
        auto_added=[],
    )


# ---------------------------------------------------------------------------
# XML/JSON parsers for staged-bundle analysis
# ---------------------------------------------------------------------------

# Pattern for SM formula resource entries — reused from deps.py
_RESOURCE_ENTRY_RE = re.compile(r"\$\{([^}]*)\}", re.DOTALL)


def _refs_from_views_xml(views_path: Path) -> list[MetricReference]:
    """Extract metric references from a views_content.xml artifact.

    Parses ViewDef elements, reads their adapterKind/resourceKind from the
    ResourceKind element, then walks Column elements for attributeKey values.
    """
    refs: list[MetricReference] = []
    try:
        tree = ET.parse(views_path)
        root = tree.getroot()
    except ET.ParseError as e:
        # Best-effort: warn but don't abort the whole analyze run.
        print(f"  WARN: could not parse {views_path}: {e}", file=sys.stderr)
        return refs

    # The views XML root is usually <ViewList> or similar; walk all ViewDef
    # elements at any depth.
    for viewdef in root.iter("ViewDef"):
        ak = ""
        rk = ""
        view_name = viewdef.get("name", "unknown view")
        source_desc = f"view {view_name!r}"

        # ResourceKind element specifies the target object type.
        rk_el = viewdef.find(".//ResourceKind")
        if rk_el is not None:
            rk = rk_el.get("resourceKind", "") or ""
            ak = rk_el.get("adapterKind", "") or ""

        if not ak or not rk:
            continue

        # Column elements carry the metric key in their attributeKey attribute.
        for col in viewdef.iter("Column"):
            attr = col.get("attributeKey") or col.get("attribute") or ""
            attr = attr.strip()
            if not attr or _is_sm_ref(attr):
                continue
            attr = _normalize_metric_key(attr)
            refs.append(MetricReference(
                adapter_kind=ak,
                resource_kind=rk,
                metric_key=attr,
                source_desc=source_desc,
            ))

    return refs


def _refs_from_dashboard_json(dash_path: Path) -> list[MetricReference]:
    """Extract metric references from a dashboard.json artifact.

    The dashboard JSON has a top-level ``dashboardList`` array; each dashboard
    has a ``widgetList``.  Widget configs vary by type; we extract keys from
    the same fields as the YAML-based walker in deps.py.

    This is a best-effort parser — widget config shapes differ.  Unknown
    structures are silently skipped (the cache will flag unknown keys).
    """
    refs: list[MetricReference] = []
    try:
        raw = json.loads(dash_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARN: could not parse {dash_path}: {e}", file=sys.stderr)
        return refs

    # Dashboard JSON layout from render.py:
    # {"dashboardList": [{"name": ..., "widgetList": [...], ...}]}
    dash_list = raw.get("dashboardList") or []
    if isinstance(raw, list):
        dash_list = raw

    for dash in dash_list:
        dash_name = dash.get("name", "unknown dashboard")
        widget_list = dash.get("widgetList") or []
        for widget in widget_list:
            widget_type = widget.get("widgetType") or widget.get("type") or ""
            wid = widget.get("id") or widget.get("localId") or "?"
            wsrc = f"dashboard {dash_name!r} widget {wid!r} ({widget_type})"
            cfg = widget.get("configuration") or {}
            for ref in _refs_from_widget_config(cfg, widget_type, wsrc):
                refs.append(ref)

    return refs


def _refs_from_widget_config(
    cfg: dict,
    widget_type: str,
    source_desc: str,
) -> list[MetricReference]:
    """Extract metric references from a single widget's configuration dict.

    Mirrors the logic in deps.py._refs_from_widgets() but works on the
    rendered JSON wire format rather than the YAML loader objects.
    """
    refs: list[MetricReference] = []

    # Scoreboard and MetricChart: metrics[] array
    if widget_type in ("Scoreboard", "MetricChart"):
        for ms in cfg.get("metrics") or []:
            ak = ms.get("adapterType") or ms.get("adapter_kind") or ""
            rk = ms.get("resourceType") or ms.get("resource_kind") or ""
            key = ms.get("attribute") or ms.get("metric_key") or ms.get("metricKey") or ""
            if key and ak and rk and not _is_sm_ref(key):
                refs.append(MetricReference(
                    adapter_kind=ak, resource_kind=rk,
                    metric_key=_normalize_metric_key(key),
                    source_desc=source_desc,
                ))

    # HealthChart and ParetoAnalysis: flat fields
    elif widget_type in ("HealthChart", "ParetoAnalysis"):
        ak = cfg.get("adapterType") or cfg.get("adapter_kind") or ""
        rk = cfg.get("resourceType") or cfg.get("resource_kind") or ""
        key = cfg.get("attribute") or cfg.get("metricKey") or cfg.get("metric_key") or ""
        if key and ak and rk and not _is_sm_ref(key):
            refs.append(MetricReference(
                adapter_kind=ak, resource_kind=rk,
                metric_key=_normalize_metric_key(key),
                source_desc=source_desc,
            ))

    # Heatmap: tabs[] with colorByKey / sizeByKey
    elif widget_type == "Heatmap":
        for tab in cfg.get("tabs") or cfg.get("tabList") or []:
            ak = tab.get("adapterType") or tab.get("adapter_kind") or ""
            rk = tab.get("resourceType") or tab.get("resource_kind") or ""
            tab_name = tab.get("name") or ""
            for key_field in ("colorByKey", "color_by_key", "sizeByKey", "size_by_key"):
                key = tab.get(key_field) or ""
                if key and not _is_sm_ref(key) and ak and rk:
                    refs.append(MetricReference(
                        adapter_kind=ak, resource_kind=rk,
                        metric_key=_normalize_metric_key(key),
                        source_desc=f"{source_desc} tab {tab_name!r}",
                    ))

    # ResourceList, View, TextDisplay, AlertList, ProblemAlertsList: no keys
    return refs
