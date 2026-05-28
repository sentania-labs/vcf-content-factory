"""Shared helpers for compliance benchmark normalizers.

The canonical compliance CSV schema is documented in
content/sdk-adapters/compliance/CANONICAL_SCHEMA.md. Per-source
normalizers (normalize_scg_v8.py, normalize_scg_v9.py,
normalize_cis_vsphere.py) import this module for the schema header,
classifiers, and writer helpers.

Keep logic in this module restricted to operations that are
identical across all sources. Per-source quirks (column name maps,
priority sanitization) live in the source-specific scripts.
"""

from __future__ import annotations

import csv
import re
import sys
from typing import Dict, Iterable, List, Optional

CANONICAL_HEADER: List[str] = [
    "control_id",
    "priority",
    "resource_kind",
    "adapter_kind",
    "parameter",
    "parameter_kind",
    "value_type",
    "expected_value",
    "title",
    "description",
    "source_ref",
    "remediation_text",
]

# Component name -> (resource_kind, object_type_prefix). Match the
# resource_kind to the VCF Ops resource model and the prefix to the
# object-type-prefix map in CANONICAL_SCHEMA.md.
COMPONENT_MAP: Dict[str, tuple] = {
    # SCG 8.x ("Component" column)
    "VMware ESXi": ("HostSystem", "esx"),
    "VMware vCenter": ("VCenterAdapterInstance", "vc"),
    "VMware vSAN": ("ClusterComputeResource", "cluster"),
    # SCG 9.x ("Component\nName" column)
    "ESX": ("HostSystem", "esx"),
    "ESXi": ("HostSystem", "esx"),
    "vCenter": ("VCenterAdapterInstance", "vc"),
    "vCenter Server": ("VCenterAdapterInstance", "vc"),
    "vSAN": ("ClusterComputeResource", "cluster"),
    # SCG 9.x sub-components: distinct prefixes so control_ids don't
    # collide across components. The compliance adapter only stitches
    # to HostSystem / VCenterAdapterInstance today, so these rows
    # ship with parameter_kind=manual_audit / powercli_only and are
    # informational-only. Prefixes added for traceability; resource_kind
    # falls back to VCenterAdapterInstance so the row is still loadable.
    "NSX": ("VCenterAdapterInstance", "nsx"),
    "Operations": ("VCenterAdapterInstance", "ops"),
    "SDDC Manager": ("VCenterAdapterInstance", "sddc"),
    "Installer": ("VCenterAdapterInstance", "installer"),
    "VCF": ("VCenterAdapterInstance", "vcf"),
    # CIS vSphere 8
    "Virtual Machine": ("VirtualMachine", "vm"),
}

ADAPTER_KIND = "VMWARE"


def map_component(component: str) -> Optional[tuple]:
    """Return (resource_kind, prefix) for a source Component value.

    Returns None for unmapped values; caller should warn and skip.
    """
    if not component:
        return None
    return COMPONENT_MAP.get(component.strip())


def clean_priority(raw: str) -> str:
    """Sanitize Implementation Priority to one of P0/P1/P2.

    Source priorities sometimes carry trailing qualifiers like "P2\n
    Upon Feature Enablement" or stray whitespace. We keep only the
    P0/P1/P2 prefix. Anything else (Advanced, N/A, blank) defaults
    to P2.
    """
    if not raw:
        return "P2"
    s = raw.strip().upper()
    m = re.match(r"P([012])", s)
    if m:
        return f"P{m.group(1)}"
    return "P2"


# Map source-ID prefix -> (canonical object-type prefix,
# canonical resource_kind). When a source ID like
# 'guest-9.audit-permissions' or 'logs-9.session-timeout' appears,
# the source-ID prefix is *more granular* than the Component column
# (Component='ESX' lumps VM-guest controls with host controls,
# Component='Operations' lumps logs/networks/operations together).
# We prefer the source-ID prefix when it gives us a finer-grained
# canonical mapping; this avoids control_id collisions across
# sub-products that share a Component value.
SOURCE_ID_PREFIX_MAP: Dict[str, tuple] = {
    "esx": ("esx", "HostSystem"),
    "esxi": ("esx", "HostSystem"),
    "vc": ("vc", "VCenterAdapterInstance"),
    "vcenter": ("vc", "VCenterAdapterInstance"),
    "vsan": ("cluster", "ClusterComputeResource"),
    "nsx": ("nsx", "VCenterAdapterInstance"),
    "vm": ("vm", "VirtualMachine"),
    "guest": ("vm", "VirtualMachine"),
    "vcf": ("vcf", "VCenterAdapterInstance"),
    "sddc": ("sddc", "VCenterAdapterInstance"),
    "installer": ("installer", "VCenterAdapterInstance"),
    "operations": ("ops", "VCenterAdapterInstance"),
    "fleet": ("fleet", "VCenterAdapterInstance"),
    "logs": ("logs", "VCenterAdapterInstance"),
    "networks": ("networks", "VCenterAdapterInstance"),
}


def derive_prefix_and_slug(source_id: str, fallback_prefix: str) -> tuple:
    """Parse a source SCG ID into (canonical_prefix, canonical_slug).

    Source IDs look like:
      esxi-8.account-auto-unlock-time   -> ('esx', 'account-auto-unlock-time')
      esx-9.account-lockout-duration    -> ('esx', 'account-lockout-duration')
      guest-9.audit-permissions          -> ('vm', 'audit-permissions')
      logs-9.session-timeout             -> ('logs', 'session-timeout')
      vcenter-9.foo                       -> ('vc', 'foo')

    When the leading prefix is recognized in SOURCE_ID_PREFIX_MAP,
    use the mapped canonical prefix. Otherwise fall back to the
    Component-derived prefix and keep the source prefix as part of
    the slug for disambiguation.

    Returns (prefix, slug). Either may be '' on bad input.
    """
    if not source_id:
        return ("", "")
    s = source_id.strip()
    m = re.match(r"^([a-zA-Z]+)-?\d+(?:\.\d+)?\.(.+)$", s)
    if m:
        raw_prefix = m.group(1).lower()
        rest = m.group(2)
        mapped = SOURCE_ID_PREFIX_MAP.get(raw_prefix)
        if mapped is not None:
            canonical_prefix = mapped[0]
            slug = _slugify(rest)
            return (canonical_prefix, slug)
        # Unrecognized prefix — fall back to component-based prefix
        # but keep the raw prefix in the slug so it disambiguates.
        slug = _slugify(f"{raw_prefix}-{rest}")
        return (fallback_prefix, slug)
    # No version-prefixed format — treat the whole thing as slug.
    slug = _slugify(s)
    return (fallback_prefix, slug)


def _slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def build_control_id(fallback_prefix: str, source_id: str) -> str:
    """Build <prefix>.<slug> control_id from a source SCG ID.

    Prefers the source-ID prefix when recognized in SOURCE_ID_PREFIX_MAP;
    falls back to the Component-derived prefix otherwise.
    """
    prefix, slug = derive_prefix_and_slug(source_id, fallback_prefix)
    if not slug:
        return ""
    return f"{prefix}.{slug}"


def derive_resource_kind(source_id: str, fallback_resource_kind: str) -> str:
    """When source-ID prefix overrides the Component mapping, also
    return the matching resource_kind. Otherwise return the fallback."""
    if not source_id:
        return fallback_resource_kind
    m = re.match(r"^([a-zA-Z]+)-?\d+(?:\.\d+)?\.", source_id.strip())
    if not m:
        return fallback_resource_kind
    raw_prefix = m.group(1).lower()
    mapped = SOURCE_ID_PREFIX_MAP.get(raw_prefix)
    if mapped is not None:
        return mapped[1]
    return fallback_resource_kind


def infer_value_type(expected: str) -> str:
    """Infer value_type from an expected_value string."""
    if expected is None:
        return "string"
    s = expected.strip()
    if not s:
        return "string"
    # Try integer/float
    try:
        float(s)
        return "integer"
    except ValueError:
        pass
    if s.lower() in ("true", "false"):
        return "boolean"
    return "string"


def classify_parameter_kind(parameter: str, assessment_cmd: str) -> str:
    """Infer parameter_kind from the source columns.

    Priority order:
      1. Empty / 'N/A' assessment command -> manual_audit
      2. Assessment command contains Get-AdvancedSetting -> advanced_setting
      3. Assessment command contains EsxCli markers -> esxcli
      4. Assessment command reads a vim property -> vim_property
      5. Otherwise -> powercli_only
    """
    cmd = (assessment_cmd or "").strip()
    if not cmd or cmd.upper() == "N/A":
        return "manual_audit"
    if "Get-AdvancedSetting" in cmd:
        return "advanced_setting"
    if "Get-EsxCli" in cmd or "$ESXcli" in cmd or "Get-ESXCli" in cmd:
        return "esxcli"
    # Heuristic for vim property reads: chained .config.* / .Config.* access
    # on the result of Get-VMHost / Get-View.
    if re.search(r"(Get-VMHost|Get-View)[^|]*\|.*\.(config|Config|Hardware)\.", cmd):
        return "vim_property"
    if re.search(r"Get-VMHost[^|]*\.(config|Config)\.", cmd):
        return "vim_property"
    return "powercli_only"


def collapse_remediation(text: str) -> str:
    """Collapse a multi-line PowerCLI remediation into a single line."""
    if not text:
        return ""
    s = text.replace("\r", " ").replace("\n", " ; ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def write_canonical(out_path: str, rows: Iterable[Dict[str, str]]) -> int:
    """Write canonical rows to out_path. Returns rows-written count."""
    count = 0
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CANONICAL_HEADER, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for row in rows:
            # Ensure all canonical columns are present; missing -> empty.
            out_row = {k: (row.get(k) or "") for k in CANONICAL_HEADER}
            w.writerow(out_row)
            count += 1
    return count


def log(msg: str) -> None:
    print(msg, file=sys.stderr)
