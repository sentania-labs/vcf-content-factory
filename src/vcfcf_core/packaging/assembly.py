"""In-memory distribution zip assembly and the ``vcfops_manifest.json``
writer (M2 row 3).

Everything a distribution zip carries is rendered here from objects in
memory and handed back as bytes: the per-type wire payloads of a ``Bundle``
(``render_bundle_payloads``), the drag-drop inner zips, the ``bundle.json``
content block, the in-zip staleness manifest (``render_vcfops_manifest``)
and the outer zip layout (``assemble_distribution_zip``). Nothing here
reads a template, a LICENSE, a design note, the clock, or a describe cache:
the factory builders (``vcfcf_packaging.builder`` for bundle manifests,
``vcfcf_packaging.discrete_builder`` for single items) read those from the
repo and pass them in, so both produce byte-identical zips for the same
inputs.

Zip layout (member order is part of the contract; both factory builders
emitted exactly this before the move):

    install.py              -- static Python installer (no stamped vars)
    install.ps1             -- static PowerShell installer
    README.md               -- static framework overview
    vcfops_manifest.json    -- in-zip metadata for staleness detection
    LICENSE                 -- when the caller supplies one
    bundles/<slug>/
        bundle.json         -- metadata + runtime content manifest
        README.md           -- bundle- or item-specific description
        supermetric.json    -- same bytes as content/supermetrics.json
        customgroup.json    -- UI import envelope (drag-drop)
        Views.zip           -- inner content.xml at zip root
        Dashboard.zip       -- inner dashboard/dashboard.json with deterministic UUID5
        Reports.zip         -- inner content.xml
        AlertContent.xml    -- synthesised from symptoms + alerts YAML
        content/
          supermetrics.json
          views_content.xml
          dashboard.json    -- retains PLACEHOLDER_USER_ID for the installer
          customgroup.json  -- REST payload for the installer
          reports_content.xml
          symptoms.json
          alerts.json
          builtin_metric_enables.json

``vcfops_manifest.json`` keeps its name and format byte-for-byte: it is a
wire artifact read by shipped installers (``check-staleness``).
"""
from __future__ import annotations

import io
import json
import uuid
import zipfile
from dataclasses import dataclass
from typing import Mapping, Optional

from ..alerts.render import render_alert_content_xml
from ..dashboards.render import render_dashboards_bundle_json, render_views_xml
from ..reports.render import render_report_xml
from ..supermetrics.crossref import resolve_sm_formula, sm_name_to_uuid_map
from .loader import Bundle, BundleValidationError, render_bme_items

# The builder stamps PLACEHOLDER_USER_ID into the rendered dashboard JSON.
# The install script replaces this at install time with the real user UUID.
PLACEHOLDER_USER_ID = "PLACEHOLDER_USER_ID"

# Deterministic UUID5 used in drag-drop Dashboard.zip (no installer stamping
# available at drag-drop time).  Derived from the framework's canonical DNS
# label so it is constant across builds, syntactically valid, and grep-able
# as framework-stamped content.  Resolves to:
#   b58a71ee-e909-5b40-a355-9e199e6f0f53
# A 130-dashboard corpus survey found zero uses of the nil UUID in real
# community packages; UUID5 looks natural compared to the corpus's real-UUID
# values while remaining deterministic and identifiable.
DASHBOARD_DROPIN_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "vcf-content-factory.local"))

# Remediation sentence for a native bundle build: the fix is a manifest edit.
_SM_CROSSREF_HINT_BUNDLE = (
    "That super metric is not in this bundle.  Add it to the bundle manifest "
    "(or to the same discrete/release component), or remove the "
    "cross-reference from the formula."
)


# ---------------------------------------------------------------------------
# Per-type payload renderers
# ---------------------------------------------------------------------------


def _render_supermetrics_dict(bundle: Bundle) -> dict:
    """Render super metrics as a dict keyed by UUID (wire format).

    ``@supermetric:"<name>"`` cross-reference tokens are resolved to the native
    ``Super Metric|sm_<uuid>`` wire token against the bundle's own SM set.  VCF
    Ops cannot parse the authoring-time token, so an unresolvable name is a hard
    build error rather than a silently corrupt super metric.
    """
    name_to_uuid = sm_name_to_uuid_map(bundle.supermetrics)
    result = {}
    for sm in bundle.supermetrics:
        formula = " ".join(sm.formula.split())
        formula = resolve_sm_formula(
            formula,
            sm.name,
            name_to_uuid,
            error_cls=BundleValidationError,
            hint=_SM_CROSSREF_HINT_BUNDLE,
        )
        result[sm.id] = {
            "name": sm.name,
            "formula": formula,
            "description": sm.description,
            "unitId": sm.unit_id or "",
            "resourceKinds": sm.resource_kinds,
        }
    return result


def _render_customgroup_rest_payload(bundle: Bundle):
    """Render custom group REST API wire payloads (for content/customgroup.json).

    Returns a single dict if there is one group, a list if there are multiple.
    The install script's _install_customgroups() reads this file and calls
    upsert_custom_group() which POSTs/PUTs to /api/resources/groups.
    """
    if not bundle.customgroups:
        return None
    wire = [cg.to_wire() for cg in bundle.customgroups]
    return wire[0] if len(wire) == 1 else wire


def _render_customgroup_ui_payload(bundle: Bundle) -> dict | None:
    """Render custom group UI import payload (for drag-drop customgroup.json).

    Produces the envelope format expected by the VCF Ops UI custom group import
    dialog: {"customGroups": [...], "customGroupTypes": [...]}.  All groups in
    the bundle are merged into a single envelope.  Duplicate customGroupTypes
    (same resourceKind) are deduplicated, keeping the first occurrence.

    See knowledge/context/wire-formats/customgroup_import_format.md for the format specification.
    """
    if not bundle.customgroups:
        return None
    all_groups = []
    seen_type_keys: dict = {}  # resourceKind -> first localization seen
    for cg in bundle.customgroups:
        ui = cg.to_ui_wire()
        all_groups.extend(ui["customGroups"])
        for gt in ui["customGroupTypes"]:
            rk = gt["resourceKind"]
            if rk not in seen_type_keys:
                seen_type_keys[rk] = gt
    return {
        "customGroups": all_groups,
        "customGroupTypes": list(seen_type_keys.values()),
    }


def _render_alerts_payload(alerts: list) -> list:
    """YAML-equivalent alert dicts for content/alerts.json; the installer
    resolves symptom ids at runtime. RecommendationRef objects are
    serialized as plain dicts so json.dumps can handle them."""
    payload = []
    for a in alerts:
        rec_refs_serialized = [
            {"name": r.name, "priority": r.priority}
            for r in a.recommendations
        ]
        payload.append({
            "name": a.name,
            "description": a.description,
            "adapter_kind": a.adapter_kind,
            "resource_kind": a.resource_kind,
            "type": a.type,
            "sub_type": a.sub_type,
            "wait_cycles": a.wait_cycles,
            "cancel_cycles": a.cancel_cycles,
            "criticality": a.criticality,
            "impact_badge": a.impact_badge,
            "symptom_sets": a.symptom_sets,
            "recommendations": rec_refs_serialized,
        })
    return payload


# ---------------------------------------------------------------------------
# Drag-drop inner zips
# ---------------------------------------------------------------------------


def _build_views_inner_zip(xml_text: str) -> bytes:
    """Build Views.zip: inner content.xml at zip root."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml_text)
    return buf.getvalue()


def _build_dashboard_dropin_zip(dashboard_json_with_placeholder: str) -> bytes:
    """Build Dashboard.zip for drag-drop UI import.

    Uses DASHBOARD_DROPIN_USER_ID (a deterministic UUID5) in place of
    PLACEHOLDER_USER_ID since no installer is available to stamp the real
    owner at drag-drop time.  Both userId and lastUpdateUserId are covered
    by the single string replace because the renderer writes PLACEHOLDER_USER_ID
    into both fields.
    Inner structure: dashboard/dashboard.json + language resource stubs.
    """
    patched = dashboard_json_with_placeholder.replace(PLACEHOLDER_USER_ID, DASHBOARD_DROPIN_USER_ID)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dashboard/dashboard.json", patched)
        for lang in ("", "_es", "_fr", "_ja"):
            z.writestr(f"dashboard/resources/resources{lang}.properties", "")
    return buf.getvalue()


def _build_reports_dropin_zip(reports_xml: str) -> bytes:
    """Build Reports.zip for drag-drop UI import (inner content.xml)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", reports_xml)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# bundle.json
# ---------------------------------------------------------------------------


def _build_content_block(bundle: Bundle) -> dict:
    """The ``content`` block of bundle.json: one entry per content type
    present, ``file`` relative to the bundle's own subdirectory and the
    ``items`` list the installer walks (``name`` is the uninstall contract,
    ``uuid`` is present for the types that carry one)."""
    content: dict = {}
    if bundle.supermetrics:
        content["supermetrics"] = {
            "file": "content/supermetrics.json",
            "items": [{"uuid": sm.id, "name": sm.name} for sm in bundle.supermetrics],
        }
    if bundle.views:
        content["views"] = {
            "file": "content/views_content.xml",
            "items": [{"uuid": v.id, "name": v.name} for v in bundle.views],
        }
    if bundle.dashboards:
        content["dashboards"] = {
            "file": "content/dashboard.json",
            "items": [{"uuid": d.id, "name": d.name} for d in bundle.dashboards],
        }
    if bundle.customgroups:
        content["customgroups"] = {
            "file": "content/customgroup.json",
            "items": [{"name": cg.name} for cg in bundle.customgroups],
        }
    if bundle.symptoms:
        content["symptoms"] = {
            "file": "content/symptoms.json",
            "items": [{"name": s.name} for s in bundle.symptoms],
        }
    if bundle.alerts:
        content["alerts"] = {
            "file": "content/alerts.json",
            "items": [{"name": a.name} for a in bundle.alerts],
        }
    if bundle.reports:
        content["reports"] = {
            "file": "content/reports_content.xml",
            "items": [{"uuid": rd.id, "name": rd.name} for rd in bundle.reports],
        }
    if bundle.builtin_metric_enables:
        content["builtin_metric_enables"] = {
            "file": "content/builtin_metric_enables.json",
            # render_bme_items() is shared with the content/ payload so the
            # two stay byte-identical.
            "items": render_bme_items(bundle.builtin_metric_enables),
        }
    return content


def _build_bundle_json(bundle: Bundle, display_name: str) -> str:
    """Build the bundle.json metadata manifest embedded in distribution zips.

    Paths in ``file:`` are relative to the bundle's own subdirectory
    (``bundles/<slug>/``).  The install script joins them with the bundle dir.

    Shape:
      {
        "name": "...",
        "display_name": "...",   (optional; same as name if absent)
        "description": "...",
        "content": {
          "supermetrics": {"file": "content/supermetrics.json", "items": [...]},
          "views":        {"file": "content/views_content.xml",  "items": [...]},
          "dashboards":   {"file": "content/dashboard.json",     "items": [...]},
          "customgroups": {"file": "content/customgroup.json",   "items": [...]},
          "symptoms":     {"file": "content/symptoms.json",      "items": [...]},
          "alerts":       {"file": "content/alerts.json",        "items": [...]},
          "reports":      {"file": "content/reports_content.xml","items": [...]}
        }
      }
    items[].name is the uninstall contract; items[].uuid is present for
    types that carry UUIDs (supermetrics, views, dashboards, reports).
    """
    manifest: dict = {
        "name": bundle.name,
        "display_name": display_name,
        "description": bundle.description or "",
        "content": _build_content_block(bundle),
    }
    # Include provenance fields when present
    if not bundle.factory_native:
        manifest["factory_native"] = False
    if bundle.author:
        manifest["author"] = bundle.author
    if bundle.license:
        manifest["license"] = bundle.license
    if bundle.source:
        manifest["source"] = bundle.source
    return json.dumps(manifest, indent=2)


# ---------------------------------------------------------------------------
# Payloads and the outer zip
# ---------------------------------------------------------------------------


@dataclass
class BundlePayloads:
    """Every rendered artifact a distribution zip carries, or None when the
    bundle has no content of that type."""
    sm_json: Optional[str] = None
    views_xml: Optional[str] = None
    dashboard_json: Optional[str] = None        # retains PLACEHOLDER_USER_ID
    cg_rest_json: Optional[str] = None
    cg_ui_json: Optional[str] = None
    reports_xml: Optional[str] = None
    symptoms_json: Optional[str] = None
    alerts_json: Optional[str] = None
    alert_content_xml: Optional[str] = None
    builtin_metric_enables_json: Optional[str] = None


def render_bundle_payloads(
    bundle: Bundle,
    *,
    sm_map: Mapping[str, str],
    bundle_context: str,
) -> BundlePayloads:
    """Render every wire payload of ``bundle`` in memory.

    ``sm_map`` is the super metric name to uuid map the view renderer
    resolves ``supermetric:"<name>"`` columns against (the factory builds it
    from the bundle's own SM files, so a bundle's views never resolve
    against another bundle's SMs); ``bundle_context`` labels resolution
    errors.
    """
    sm_dict = _render_supermetrics_dict(bundle) if bundle.supermetrics else {}
    sm_json = json.dumps(sm_dict, indent=2) if sm_dict else None

    views_xml = (
        render_views_xml(
            bundle.views,
            sm_map=sm_map,
            sm_scope_active=True,
            bundle_context=bundle_context,
        )
        if bundle.views else None
    )

    dashboard_json = None
    if bundle.dashboards:
        views_by_name = {v.name: v for v in bundle.views}
        dashboard_json = render_dashboards_bundle_json(
            bundle.dashboards, views_by_name, PLACEHOLDER_USER_ID
        )

    cg_rest_payload = _render_customgroup_rest_payload(bundle)
    cg_rest_json = json.dumps(cg_rest_payload, indent=2) if cg_rest_payload is not None else None
    cg_ui_payload = _render_customgroup_ui_payload(bundle)
    cg_ui_json = json.dumps(cg_ui_payload, indent=2) if cg_ui_payload is not None else None

    reports_xml = render_report_xml(bundle.reports) if bundle.reports else None

    symptoms_payload = [s.to_wire() for s in bundle.symptoms] if bundle.symptoms else None
    symptoms_json = json.dumps(symptoms_payload, indent=2) if symptoms_payload else None

    alerts_json = json.dumps(_render_alerts_payload(bundle.alerts), indent=2) if bundle.alerts else None

    # AlertContent.xml, synthesised when the bundle has symptoms, alerts,
    # or recommendations.  A bundle with only recommendations (unusual but
    # valid) still emits AlertContent.xml so the recommendations are importable.
    alert_content_xml = None
    if bundle.symptoms or bundle.alerts or bundle.recommendations:
        alert_content_xml = render_alert_content_xml(
            bundle.symptoms,
            bundle.alerts,
            recommendations=bundle.recommendations or [],
        )

    bme_json = (
        json.dumps(render_bme_items(bundle.builtin_metric_enables), indent=2)
        if bundle.builtin_metric_enables else None
    )

    return BundlePayloads(
        sm_json=sm_json,
        views_xml=views_xml,
        dashboard_json=dashboard_json,
        cg_rest_json=cg_rest_json,
        cg_ui_json=cg_ui_json,
        reports_xml=reports_xml,
        symptoms_json=symptoms_json,
        alerts_json=alerts_json,
        alert_content_xml=alert_content_xml,
        builtin_metric_enables_json=bme_json,
    )


def render_vcfops_manifest(fields: Mapping[str, object], built_at: str) -> str:
    """``vcfops_manifest.json``: the caller's fields in the caller's order,
    then ``built_at``, as ``json.dumps(..., indent=2)``. The bundle builder
    passes ``bundle_name`` and ``template_version``; the discrete builder
    adds ``item_type`` / ``item_name`` / ``item_version`` between them. The
    format is read by shipped installers and must not change."""
    doc = dict(fields)
    doc["built_at"] = built_at
    return json.dumps(doc, indent=2)


def assemble_distribution_zip(
    *,
    slug: str,
    payloads: BundlePayloads,
    bundle_json: str,
    bundle_readme: str,
    install_py: str,
    install_ps1: str,
    framework_readme: str,
    vcfops_manifest: str,
    license_text: Optional[str],
) -> bytes:
    """Write the distribution zip described in the module docstring and
    return its bytes. Member order is the contract."""
    bundle_prefix = f"bundles/{slug}/"
    content_prefix = f"bundles/{slug}/content/"

    views_zip_bytes = _build_views_inner_zip(payloads.views_xml) if payloads.views_xml else None
    dashboard_zip_bytes = (
        _build_dashboard_dropin_zip(payloads.dashboard_json) if payloads.dashboard_json else None
    )
    reports_zip_bytes = (
        _build_reports_dropin_zip(payloads.reports_xml) if payloads.reports_xml else None
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # Root-level static files
        z.writestr("install.py", install_py)
        z.writestr("install.ps1", install_ps1)
        z.writestr("README.md", framework_readme)
        z.writestr("vcfops_manifest.json", vcfops_manifest)
        if license_text is not None:
            z.writestr("LICENSE", license_text)

        # Bundle subdirectory: metadata
        z.writestr(bundle_prefix + "bundle.json", bundle_json)
        z.writestr(bundle_prefix + "README.md", bundle_readme)

        # Drag-drop artifacts at bundle root (community-native filenames)
        if payloads.sm_json:
            z.writestr(bundle_prefix + "supermetric.json", payloads.sm_json)
        if payloads.cg_ui_json:
            z.writestr(bundle_prefix + "customgroup.json", payloads.cg_ui_json)
        if views_zip_bytes:
            z.writestr(bundle_prefix + "Views.zip", views_zip_bytes)
        if dashboard_zip_bytes:
            z.writestr(bundle_prefix + "Dashboard.zip", dashboard_zip_bytes)
        if reports_zip_bytes:
            z.writestr(bundle_prefix + "Reports.zip", reports_zip_bytes)
        if payloads.alert_content_xml:
            z.writestr(bundle_prefix + "AlertContent.xml", payloads.alert_content_xml)

        # Installer source files under content/
        if payloads.sm_json:
            z.writestr(content_prefix + "supermetrics.json", payloads.sm_json)
        if payloads.views_xml:
            z.writestr(content_prefix + "views_content.xml", payloads.views_xml)
        if payloads.dashboard_json:
            # content/ copy retains PLACEHOLDER_USER_ID for runtime stamping
            z.writestr(content_prefix + "dashboard.json", payloads.dashboard_json)
        if payloads.cg_rest_json:
            z.writestr(content_prefix + "customgroup.json", payloads.cg_rest_json)
        if payloads.reports_xml:
            z.writestr(content_prefix + "reports_content.xml", payloads.reports_xml)
        if payloads.symptoms_json:
            z.writestr(content_prefix + "symptoms.json", payloads.symptoms_json)
        if payloads.alerts_json:
            z.writestr(content_prefix + "alerts.json", payloads.alerts_json)
        if payloads.builtin_metric_enables_json:
            z.writestr(content_prefix + "builtin_metric_enables.json", payloads.builtin_metric_enables_json)

    return buf.getvalue()
