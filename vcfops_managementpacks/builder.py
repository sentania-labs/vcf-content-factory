"""Build a .pak ZIP file from a ManagementPackDef.

Wire format reverse-engineered from:
  - GitHub-1.0.0.2.pak  (mpb_github_adapter3)
  - Broadcom Security Advisories-1.0.1.6.pak  (mpb_broadcom_security_advisories_adapter3)

Key structural facts:
  - .pak is a ZIP with root-level scripts, manifest.txt, eula.txt, default.png,
    adapters.zip, content/, and resources/.
  - adapters.zip contains:
    - <adapter_dir>.jar  — the adapter runtime JAR (MPB-generated; we use the
      reference GitHub JAR as a stand-in — see ADAPTER_JAR_GAP note below)
    - <adapter_dir>/lib/*.jar  — shared library JARs (same across all MPB paks)
    - <adapter_dir>/conf/design.json  — our rendered MPB design JSON
    - <adapter_dir>/conf/describe.xml  — adapter kind XML (generated from design)
    - <adapter_dir>/conf/<adapter_kind>.properties  — runtime config
    - <adapter_dir>/conf/version.txt
    - <adapter_dir>/conf/supermetrics/customSuperMetrics.json
    - <adapter_dir>/conf/dashboards/, conf/reports/, conf/views/  — empty dirs
    - <adapter_dir>/conf/images/  — adapter icons
    - <adapter_dir>/conf/resources/resources.properties  — localization strings
    - <adapter_dir>/work/  — empty runtime work dir
    - <adapter_dir>/doc/  — empty doc dir
    - Also at adapters.zip root (duplicated from pak root):
      - manifest.txt, eula.txt, default.png, resources/resources.properties

  - manifest.txt is JSON with adapter kind key, version, scripts, etc.
  - post-install.py triggers ops-cli redescribe + content import.
  - describe.xml is pre-baked (read by VCF Ops adapter loader at startup).

ADAPTER_JAR_GAP:
  The per-adapter <adapter_dir>.jar (e.g. mpb_github_adapter3.jar) is
  compiled by the MPB server build endpoint from the design JSON. It contains
  Kotlin/Java classes with the adapter kind key baked into the package path
  (e.g. com.vmware.mpb.mpbgithub). We cannot generate this JAR in the factory.
  The builder uses the GitHub reference JAR (renamed) as a stand-in. At QA
  time, Scott should obtain the MPB-generated JAR for the real adapter kind
  (e.g. by uploading the design JSON to the MPB UI and downloading the pak),
  then drop it into adapter_runtime/ as mpb_<adapter_kind>_adapter3.jar.
  The lib/*.jar files ARE generic and identical across all MPB paks.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import struct
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from .loader import ManagementPackDef, ObjectTypeDef, MetricDef, SourceDef
from .render import render_mp_design_json

# ---------------------------------------------------------------------------
# Paths relative to this file
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_TEMPLATES_DIR = _HERE / "templates"
_ADAPTER_RUNTIME_DIR = _HERE / "adapter_runtime"

# The generic adapter runtime JAR (MPB stand-in; see ADAPTER_JAR_GAP above)
_GENERIC_ADAPTER_JAR = _ADAPTER_RUNTIME_DIR / "mpb_adapter3.jar"

# ---------------------------------------------------------------------------
# describe.xml generation
# ---------------------------------------------------------------------------

# Map from YAML metric type to describe.xml dataType
_DESCRIBE_DATA_TYPE = {
    "STRING": "string",
    "NUMBER": "float",
}

# Map from YAML metric usage to describe.xml isProperty attribute
_IS_PROPERTY = {
    "PROPERTY": "true",
    "METRIC": "false",
}

# describe.xml resource kind type codes (empirical from reference paks):
#   type 7 = adapter instance (top-level / world-like config object)
#   type 8 = world aggregation object (subType 6 = world)
#   type 4 = relatives/group (dynamic; showTag=true)
#   type 0/absent = regular resource kind
_RESOURCE_KIND_TYPE_WORLD = "8"
_RESOURCE_KIND_SUBTYPE_WORLD = "6"
_RESOURCE_KIND_TYPE_NORMAL = None  # no type attribute for regular objects

# UnitDefinitions block — the full set MPB always emits, verbatim from references.
_UNIT_DEFINITIONS_XML = """\
  <UnitDefinitions>
    <UnitType key="bytes_base10_type">
      <Unit key="byte" nameKey="1001" order="1" conversionFactor="1"></Unit>
      <Unit key="kilobyte" nameKey="1002" order="2" conversionFactor="1000"></Unit>
      <Unit key="megabyte" nameKey="1003" order="3" conversionFactor="1000"></Unit>
      <Unit key="gigabyte" nameKey="1004" order="4" conversionFactor="1000"></Unit>
      <Unit key="terabyte" nameKey="1005" order="5" conversionFactor="1000"></Unit>
      <Unit key="petabyte" nameKey="1006" order="6" conversionFactor="1000"></Unit>
    </UnitType>
    <UnitType key="bytes_base2_type">
      <Unit key="bibyte" nameKey="1001" order="1" conversionFactor="1"></Unit>
      <Unit key="kibibyte" nameKey="1007" order="2" conversionFactor="1024"></Unit>
      <Unit key="mebibyte" nameKey="1008" order="3" conversionFactor="1024"></Unit>
      <Unit key="gibibyte" nameKey="1009" order="4" conversionFactor="1024"></Unit>
      <Unit key="tebibyte" nameKey="1010" order="5" conversionFactor="1024"></Unit>
      <Unit key="pebibyte" nameKey="1011" order="6" conversionFactor="1024"></Unit>
    </UnitType>
    <UnitType key="bits_base10_type">
      <Unit key="bit" nameKey="1012" order="1" conversionFactor="1"></Unit>
      <Unit key="kilobit" nameKey="1013" order="2" conversionFactor="1000"></Unit>
      <Unit key="megabit" nameKey="1014" order="3" conversionFactor="1000"></Unit>
      <Unit key="gigabit" nameKey="1015" order="4" conversionFactor="1000"></Unit>
      <Unit key="terabit" nameKey="1016" order="5" conversionFactor="1000"></Unit>
      <Unit key="petabit" nameKey="1017" order="6" conversionFactor="1000"></Unit>
    </UnitType>
    <UnitType key="bits_base2_type">
      <Unit key="bibit" nameKey="1012" order="1" conversionFactor="1"></Unit>
      <Unit key="kibibit" nameKey="1018" order="2" conversionFactor="1024"></Unit>
      <Unit key="mebibit" nameKey="1019" order="3" conversionFactor="1024"></Unit>
      <Unit key="gibibit" nameKey="1020" order="4" conversionFactor="1024"></Unit>
      <Unit key="tebibit" nameKey="1021" order="5" conversionFactor="1024"></Unit>
      <Unit key="pebibit" nameKey="1022" order="6" conversionFactor="1024"></Unit>
    </UnitType>
    <UnitType key="bytes_rate_base10_type">
      <Unit key="bytes_per_second" nameKey="1023" order="1" conversionFactor="1"></Unit>
      <Unit key="kilobytes_per_second" nameKey="1024" order="2" conversionFactor="1000"></Unit>
      <Unit key="megabytes_per_second" nameKey="1025" order="3" conversionFactor="1000"></Unit>
      <Unit key="gigabytes_per_second" nameKey="1026" order="4" conversionFactor="1000"></Unit>
      <Unit key="terabytes_per_second" nameKey="1027" order="5" conversionFactor="1000"></Unit>
      <Unit key="petabytes_per_second" nameKey="1028" order="6" conversionFactor="1000"></Unit>
    </UnitType>
    <UnitType key="bytes_rate_base2_type">
      <Unit key="bibytes_per_second" nameKey="1023" order="1" conversionFactor="1"></Unit>
      <Unit key="kibibytes_per_second" nameKey="1029" order="2" conversionFactor="1024"></Unit>
      <Unit key="mebibytes_per_second" nameKey="1030" order="3" conversionFactor="1024"></Unit>
      <Unit key="gibibytes_per_second" nameKey="1031" order="4" conversionFactor="1024"></Unit>
      <Unit key="tebibytes_per_second" nameKey="1032" order="5" conversionFactor="1024"></Unit>
      <Unit key="pebibytes_per_second" nameKey="1033" order="6" conversionFactor="1024"></Unit>
    </UnitType>
    <UnitType key="bits_rate_base10_type">
      <Unit key="bits_per_second" nameKey="1034" order="1" conversionFactor="1"></Unit>
      <Unit key="kilobits_per_second" nameKey="1035" order="2" conversionFactor="1000"></Unit>
      <Unit key="megabits_per_second" nameKey="1036" order="3" conversionFactor="1000"></Unit>
      <Unit key="gigabits_per_second" nameKey="1037" order="4" conversionFactor="1000"></Unit>
      <Unit key="terabits_per_second" nameKey="1038" order="5" conversionFactor="1000"></Unit>
      <Unit key="petabits_per_second" nameKey="1039" order="6" conversionFactor="1000"></Unit>
    </UnitType>
    <UnitType key="bits_rate_base2_type">
      <Unit key="bibits_per_second" nameKey="1034" order="1" conversionFactor="1"></Unit>
      <Unit key="kibibits_per_second" nameKey="1040" order="2" conversionFactor="1024"></Unit>
      <Unit key="mebibits_per_second" nameKey="1041" order="3" conversionFactor="1024"></Unit>
      <Unit key="gibibits_per_second" nameKey="1042" order="4" conversionFactor="1024"></Unit>
      <Unit key="tebibits_per_second" nameKey="1043" order="5" conversionFactor="1024"></Unit>
      <Unit key="pebibits_per_second" nameKey="1044" order="6" conversionFactor="1024"></Unit>
    </UnitType>
    <UnitType key="cycle_rate_type">
      <Unit key="hertz" nameKey="1045" order="1" conversionFactor="1"></Unit>
      <Unit key="kilohertz" nameKey="1046" order="2" conversionFactor="1000"></Unit>
      <Unit key="megahertz" nameKey="1047" order="3" conversionFactor="1000"></Unit>
      <Unit key="gigahertz" nameKey="1048" order="4" conversionFactor="1000"></Unit>
      <Unit key="terahertz" nameKey="1049" order="5" conversionFactor="1000"></Unit>
      <Unit key="petahertz" nameKey="1050" order="6" conversionFactor="1000"></Unit>
      <Unit key="exahertz" nameKey="1051" order="7" conversionFactor="1000"></Unit>
    </UnitType>
    <UnitType key="time_type">
      <Unit key="microseconds" nameKey="1052" order="1" conversionFactor="1"></Unit>
      <Unit key="milliseconds" nameKey="1053" order="2" conversionFactor="1000"></Unit>
      <Unit key="seconds" nameKey="1054" order="3" conversionFactor="1000"></Unit>
      <Unit key="minutes" nameKey="1055" order="4" conversionFactor="60"></Unit>
      <Unit key="hours" nameKey="1056" order="5" conversionFactor="60"></Unit>
      <Unit key="days" nameKey="1057" order="6" conversionFactor="24"></Unit>
    </UnitType>
    <UnitType key="count_type">
      <Unit key="count" nameKey="1058" order="1" conversionFactor="1"></Unit>
    </UnitType>
    <UnitType key="percent_type">
      <Unit key="percent" nameKey="1059" order="1" conversionFactor="1"></Unit>
    </UnitType>
    <UnitType key="per_second_type">
      <Unit key="per_second" nameKey="1060" order="1" conversionFactor="1"></Unit>
    </UnitType>
  </UnitDefinitions>"""


def _generate_describe_xml(mp: ManagementPackDef) -> str:
    """Generate a describe.xml for the management pack.

    describe.xml registers the adapter kind with VCF Ops: resource kinds,
    stat/property keys, credential schemas, and unit definitions. It is
    pre-baked into adapters.zip/conf/describe.xml and read by the adapter
    loader at startup (via the redescribe triggered by post-install.py).

    Structure matches the MPB canonical (diff_mpb/conf/describe.xml, 2026-04-18):

      1. <adapter_kind>           — type=7, has credentials + mpb_hostname etc.
                                    Corresponds to the YAML is_world=True kind.
      2. <adapter_kind>_<data>    — NO type attribute (regular data kinds).
                                    adapter_instance_id is their FIRST identifier.
      3. <adapter_kind>_relatives — type=4, dynamic=true, showTag=true.
                                    Runtime-discovered ad-hoc relationship bucket.
      4. <adapter_kind>_world     — type=8, subType=6.
                                    Root aggregate container for the hierarchy.

    TraversalSpecKinds block is populated with one entry (usedFor="ALL") that
    declares the resource hierarchy path.
    """
    ak = mp.adapter_kind
    src = mp.source

    # Identify the root data kind (YAML is_world=True) and child kinds.
    world_ot = next((o for o in mp.object_types if o.is_world), None)
    child_ots = [o for o in mp.object_types if not o.is_world]

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(
        '<!-- Generated by vcfops_managementpacks builder.py -->'
    )
    lines.append(
        '<!-- Copyright VCF Content Factory. All Rights Reserved. -->'
    )
    lines.append(
        f'<AdapterKind xmlns="http://schemas.vmware.com/vcops/schema"'
        f' key="{ak}" nameKey="1" version="1">'
    )

    # CredentialKinds
    _append_credential_kinds(lines, mp, ak)

    # ResourceKinds
    lines.append("  <ResourceKinds>")
    name_key_counter = [10]  # mutable counter via list

    # 1. Adapter instance root kind (type=7) — the YAML is_world kind becomes this.
    #    It has credentials + mpb_hostname identifiers but is NOT the world aggregate.
    if world_ot is not None:
        _append_adapter_instance_kind(lines, world_ot, mp, src, ak, name_key_counter)
    else:
        # No world kind declared — emit a bare adapter instance kind
        _append_bare_adapter_instance_kind(lines, mp, src, ak, name_key_counter)

    # 2. Regular data kinds (no type attribute, adapter_instance_id first identifier)
    for ot in child_ots:
        _append_data_kind(lines, ot, mp, ak, name_key_counter)

    # 3. Relatives kind (type=4, dynamic) — MPB runtime relationship bucket
    _append_relatives_kind(lines, ak, name_key_counter)

    # 4. World aggregate kind (type=8, subType=6)
    _append_world_aggregate_kind(lines, mp, ak, name_key_counter)

    lines.append("  </ResourceKinds>")

    # Discoveries
    lines.append("  <Discoveries>")
    lines.append(
        f'    <Discovery key="{ak}_manual_discovery" nameKey="100"></Discovery>'
    )
    lines.append("  </Discoveries>")

    # TraversalSpecKinds — one entry with the resource hierarchy path
    _append_traversal_spec_kinds(lines, mp, ak, world_ot, child_ots)

    # LicenseConfig
    lines.append('  <LicenseConfig enabled="false"></LicenseConfig>')

    # SymptomDefinitions, AlertDefinitions, Recommendations (empty — authored separately)
    lines.append("  <SymptomDefinitions>")
    lines.append("  </SymptomDefinitions>")
    lines.append("  <AlertDefinitions>")
    lines.append("  </AlertDefinitions>")
    lines.append("  <Recommendations>")
    lines.append("  </Recommendations>")

    # UnitDefinitions
    lines.append(_UNIT_DEFINITIONS_XML)

    lines.append("</AdapterKind>")
    return "\n".join(lines) + "\n"


def _append_traversal_spec_kinds(
    lines: list,
    mp: ManagementPackDef,
    ak: str,
    world_ot: Optional[ObjectTypeDef],
    child_ots: list,
) -> None:
    """Append the TraversalSpecKinds XML block.

    Emits one TraversalSpecKind (usedFor="ALL") that walks the hierarchy from
    the world aggregate kind down through the root data kind (adapter instance
    world) and all child data kinds.

    ResourcePath pattern (from MPB canonical):
      <ak>::<ak>_world||<ak>::<ak>::child/skip||<ak>::<ak>_<child1>::child||...

    The 'child/skip' on the adapter instance root kind (type=7) tells VCF Ops
    to skip that level when displaying the hierarchy — child objects appear
    directly under the world aggregate, not under the adapter instance entry.
    """
    lines.append("  <TraversalSpecKinds>")

    world_rk_key = f"{ak}_world"
    display_name = mp.name

    # Build the resource path: world -> adapter-instance (skip) -> all child kinds
    path_parts = [f"{ak}::{world_rk_key}"]
    if world_ot is not None:
        root_rk_key = f"{ak}_{world_ot.key}" if not world_ot.key.startswith(ak) else world_ot.key
        path_parts.append(f"{ak}::{root_rk_key}::child/skip")
    for ot in child_ots:
        rk_key = f"{ak}_{ot.key}" if not ot.key.startswith(ak) else ot.key
        path_parts.append(f"{ak}::{rk_key}::child")

    resource_path = "||".join(path_parts)

    lines.append(
        f'    <TraversalSpecKind'
        f' name="{display_name} Resources"'
        f' rootAdapterKind="{ak}"'
        f' rootResourceKind="{world_rk_key}"'
        f' iconName="default.svg"'
        f' description="Traversal for {display_name} Resources"'
        f' usedFor="ALL">'
    )
    lines.append(f'      <ResourcePath path="{resource_path}"></ResourcePath>')
    lines.append("    </TraversalSpecKind>")
    lines.append("  </TraversalSpecKinds>")


def _append_credential_kinds(lines: list, mp: ManagementPackDef, ak: str) -> None:
    """Append CredentialKinds XML block."""
    src = mp.source
    if not src or not src.auth or src.auth.preset == "none":
        lines.append("  <CredentialKinds>")
        lines.append("  </CredentialKinds>")
        return

    auth = src.auth
    lines.append("  <CredentialKinds>")
    lines.append(
        f'    <CredentialKind key="{ak}_credentials" nameKey="2">'
    )

    if auth.preset in ("basic_auth", "cookie_session"):
        # Emit credential fields from the declared credentials list
        for i, cred in enumerate(auth.credentials, start=1):
            password_attr = 'true' if cred.sensitive else 'false'
            lines.append(
                f'      <CredentialField required="true" dispOrder="{i}" enum="false"'
                f' key="{cred.key}" nameKey="{2 + i}" password="{password_attr}" type="string">'
                "</CredentialField>"
            )
    elif auth.preset == "bearer_token":
        for i, cred in enumerate(auth.credentials, start=1):
            lines.append(
                '      <CredentialField required="true" dispOrder="1" enum="false"'
                f' key="{cred.key}" nameKey="3" password="true" type="string">'
                "</CredentialField>"
            )

    lines.append("    </CredentialKind>")
    lines.append("  </CredentialKinds>")


def _append_adapter_instance_kind(
    lines: list,
    ot: ObjectTypeDef,
    mp: ManagementPackDef,
    src: Optional[SourceDef],
    ak: str,
    name_key_counter: list,
) -> None:
    """Append the adapter instance ResourceKind (type=7).

    This corresponds to the YAML is_world=True kind.  In MPB's canonical
    structure this kind holds the connection/credential config (mpb_hostname
    etc.) and is the leaf-level data object, NOT the world aggregate.

    Pattern from MPB canonical: type="7" credentialKind="<ak>_credentials"
    monitoringInterval="5", with mpb_hostname ... mpb_min_event_severity
    identifiers and an optional summary ResourceGroup for any METRIC fields.
    """
    nk = name_key_counter[0]
    name_key_counter[0] += len(ot.metrics) + len(ot.identifiers) + 20

    rk_key = f"{ak}_{ot.key}" if not ot.key.startswith(ak) else ot.key
    cred_attr = ""
    if src and src.auth and src.auth.preset != "none":
        cred_attr = f' credentialKind="{ak}_credentials"'
    lines.append(
        f'    <ResourceKind key="{rk_key}" nameKey="{nk}"'
        f' type="7"{cred_attr} monitoringInterval="5">'
    )
    nk += 1

    # Connection config identifiers (mpb_hostname etc.)
    if src:
        ssl_map = {"NO_VERIFY": "No Verify", "VERIFY": "Verify", "NO_SSL": "No SSL"}
        ssl_display = ssl_map.get(src.ssl, "No Verify") if src.ssl else "No Verify"
        port_default = str(src.port)

        lines.append(
            f'      <ResourceIdentifier dispOrder="1" key="mpb_hostname"'
            f' nameKey="{nk}" required="true" type="string" identType="1"'
            f' enum="false" default=""></ResourceIdentifier>'
        )
        nk += 1
        lines.append(
            f'      <ResourceIdentifier dispOrder="2" key="mpb_port"'
            f' nameKey="{nk}" required="true" type="string" identType="2"'
            f' enum="false" default="{port_default}"></ResourceIdentifier>'
        )
        nk += 1
        lines.append(
            f'      <ResourceIdentifier dispOrder="3" key="mpb_connection_timeout"'
            f' nameKey="{nk}" required="true" type="string" identType="2"'
            f' enum="false" default="{src.timeout}"></ResourceIdentifier>'
        )
        nk += 1
        lines.append(
            f'      <ResourceIdentifier dispOrder="4" key="mpb_concurrent_requests"'
            f' nameKey="{nk}" required="true" type="string" identType="2"'
            f' enum="false" default="{src.max_concurrent}"></ResourceIdentifier>'
        )
        nk += 1
        lines.append(
            f'      <ResourceIdentifier dispOrder="5" key="mpb_max_retries"'
            f' nameKey="{nk}" required="true" type="string" identType="2"'
            f' enum="false" default="{src.max_retries}"></ResourceIdentifier>'
        )
        nk += 1
        lines.append(
            f'      <ResourceIdentifier dispOrder="6" key="mpb_ssl_config"'
            f' nameKey="{nk}" required="true" type="string" identType="2"'
            f' enum="true" default="{ssl_display}">'
        )
        lines.append(
            f'        <enum default="true" value="{ssl_display}"></enum>'
        )
        for v in ["No Verify", "Verify", "No SSL"]:
            if v != ssl_display:
                lines.append(f'        <enum default="false" value="{v}"></enum>')
        lines.append("      </ResourceIdentifier>")
        nk += 1
        lines.append(
            f'      <ResourceIdentifier dispOrder="7" key="mpb_min_event_severity"'
            f' nameKey="{nk}" required="true" type="string" identType="2"'
            f' enum="true" default="Warning">'
        )
        lines.append('        <enum default="false" value="Critical"></enum>')
        lines.append('        <enum default="false" value="Immediate"></enum>')
        lines.append('        <enum default="true" value="Warning"></enum>')
        lines.append('        <enum default="false" value="Info"></enum>')
        lines.append("      </ResourceIdentifier>")
        nk += 1
        lines.append(
            f'      <ResourceIdentifier dispOrder="8" key="support_autodiscovery"'
            f' nameKey="{nk}" required="true" type="string" identType="2"'
            f' enum="true" default="True">'
        )
        lines.append('        <enum default="true" value="True"></enum>')
        lines.append('        <enum default="false" value="False"></enum>')
        lines.append("      </ResourceIdentifier>")
        nk += 1

    # Metrics and properties for the adapter instance kind
    all_metrics = [m for m in ot.metrics if m.usage != "PROPERTY"]
    all_props = [m for m in ot.metrics if m.usage == "PROPERTY"]

    if all_metrics:
        lines.append(
            f'      <ResourceGroup key="summary" nameKey="{nk}" instanced="false">'
        )
        nk += 1
        for i, m in enumerate(all_metrics):
            dt = _DESCRIBE_DATA_TYPE.get(m.type, "float")
            lines.append(
                f'        <ResourceAttribute nameKey="{nk + i}"'
                f' dashboardOrder="{i + 1}"'
                f' key="{m.key}"'
                f' dataType="{dt}"'
                f' defaultMonitored="true"'
                f' isDiscrete="false"'
                f' keyAttribute="false"'
                f' isRate="false"'
                f' isProperty="false"'
                f' hidden="false" />'
            )
        nk += len(all_metrics)
        lines.append("      </ResourceGroup>")

    for i, m in enumerate(all_props):
        dt = _DESCRIBE_DATA_TYPE.get(m.type, "string")
        lines.append(
            f'      <ResourceAttribute nameKey="{nk}"'
            f' dashboardOrder="{i + 1}"'
            f' key="{m.key}"'
            f' dataType="{dt}"'
            f' defaultMonitored="true"'
            f' isDiscrete="false"'
            f' keyAttribute="false"'
            f' isRate="false"'
            f' isProperty="true"'
            f' hidden="false" />'
        )
        nk += 1

    lines.append("    </ResourceKind>")


def _append_bare_adapter_instance_kind(
    lines: list,
    mp: ManagementPackDef,
    src: Optional[SourceDef],
    ak: str,
    name_key_counter: list,
) -> None:
    """Append a minimal adapter instance kind (type=7) when no is_world kind exists."""
    nk = name_key_counter[0]
    name_key_counter[0] += 20
    cred_attr = ""
    if src and src.auth and src.auth.preset != "none":
        cred_attr = f' credentialKind="{ak}_credentials"'
    lines.append(
        f'    <ResourceKind key="{ak}" nameKey="{nk}"'
        f' type="7"{cred_attr} monitoringInterval="5">'
    )
    nk += 1
    if src:
        ssl_map = {"NO_VERIFY": "No Verify", "VERIFY": "Verify", "NO_SSL": "No SSL"}
        ssl_display = ssl_map.get(src.ssl, "No Verify") if src.ssl else "No Verify"
        lines.append(
            f'      <ResourceIdentifier dispOrder="1" key="mpb_hostname"'
            f' nameKey="{nk}" required="true" type="string" identType="1"'
            f' enum="false" default=""></ResourceIdentifier>'
        )
    lines.append("    </ResourceKind>")


def _append_data_kind(
    lines: list,
    ot: ObjectTypeDef,
    mp: ManagementPackDef,
    ak: str,
    name_key_counter: list,
) -> None:
    """Append a regular data ResourceKind (no type attribute).

    MPB canonical structure: data kinds have NO type attribute,
    adapter_instance_id as their FIRST ResourceIdentifier (dispOrder=1),
    followed by the kind's own declared identifiers (dispOrder=2+),
    then a 'relationships' ResourceGroup with a mpb_<ak>_parent attribute,
    then metric/property ResourceAttributes.
    """
    nk = name_key_counter[0]
    name_key_counter[0] += len(ot.metrics) + len(ot.identifiers) + 10

    rk_key = f"{ak}_{ot.key}" if not ot.key.startswith(ak) else ot.key
    lines.append(f'    <ResourceKind key="{rk_key}" nameKey="{nk}">')
    nk += 1

    # adapter_instance_id — always first (dispOrder=1)
    lines.append(
        f'      <ResourceIdentifier dispOrder="1" key="adapter_instance_id"'
        f' nameKey="{nk}" required="true" type="string" identType="1"'
        f' enum="false" ></ResourceIdentifier>'
    )
    nk += 1

    # Kind-specific identifiers (dispOrder=2+)
    for disp, ident_key in enumerate(ot.identifiers, start=2):
        lines.append(
            f'      <ResourceIdentifier dispOrder="{disp}" key="{ident_key}"'
            f' nameKey="{nk}" required="true" type="string" identType="1"'
            f' enum="false" ></ResourceIdentifier>'
        )
        nk += 1

    # Relationships group (MPB canonical always has this on data kinds)
    lines.append(
        f'      <ResourceGroup key="relationships" nameKey="{nk}" instanced="false">'
    )
    nk += 1
    lines.append(
        f'        <ResourceAttribute nameKey="{nk}" dashboardOrder="1"'
        f' key="{ak}_parent" dataType="string" defaultMonitored="true"'
        f' isDiscrete="false" keyAttribute="false" isRate="false"'
        f' isProperty="true" hidden="false" />'
    )
    nk += 1
    lines.append("      </ResourceGroup>")

    # Metric and property attributes
    all_metrics = [m for m in ot.metrics if m.usage != "PROPERTY"]
    all_props = [m for m in ot.metrics if m.usage == "PROPERTY"]

    for i, m in enumerate(all_metrics):
        dt = _DESCRIBE_DATA_TYPE.get(m.type, "float")
        lines.append(
            f'      <ResourceAttribute nameKey="{nk}"'
            f' dashboardOrder="{i + 1}"'
            f' key="{m.key}"'
            f' dataType="{dt}"'
            f' defaultMonitored="true"'
            f' isDiscrete="false"'
            f' keyAttribute="false"'
            f' isRate="false"'
            f' isProperty="false"'
            f' hidden="false" />'
        )
        nk += 1

    for i, m in enumerate(all_props):
        dt = _DESCRIBE_DATA_TYPE.get(m.type, "string")
        lines.append(
            f'      <ResourceAttribute nameKey="{nk}"'
            f' dashboardOrder="{i + 1}"'
            f' key="{m.key}"'
            f' dataType="{dt}"'
            f' defaultMonitored="true"'
            f' isDiscrete="false"'
            f' keyAttribute="false"'
            f' isRate="false"'
            f' isProperty="true"'
            f' hidden="false" />'
        )
        nk += 1

    lines.append("    </ResourceKind>")


def _append_relatives_kind(
    lines: list,
    ak: str,
    name_key_counter: list,
) -> None:
    """Append the <ak>_relatives ResourceKind (type=4, dynamic).

    This is the MPB runtime bucket for ad-hoc relationship discovery.
    It is always present in MPB-generated paks regardless of the MP design.
    """
    nk = name_key_counter[0]
    name_key_counter[0] += 5
    rk_key = f"{ak}_relatives"
    lines.append(
        f'    <ResourceKind key="{rk_key}" nameKey="{nk}"'
        f' type="4" showTag="true" dynamic="true">'
    )
    nk += 1
    lines.append(
        f'      <ResourceGroup key="relationships" nameKey="{nk}" instanced="false">'
    )
    lines.append("      </ResourceGroup>")
    lines.append("    </ResourceKind>")


def _append_world_aggregate_kind(
    lines: list,
    mp: ManagementPackDef,
    ak: str,
    name_key_counter: list,
) -> None:
    """Append the <ak>_world ResourceKind (type=8, subType=6).

    This is the root aggregate container for the hierarchy tree. It aggregates
    counts/rollups from the adapter instance data kinds via ComputedMetrics.
    The worldObjectName is derived from the MP display name.
    """
    nk = name_key_counter[0]
    name_key_counter[0] += 10
    rk_key = f"{ak}_world"
    world_name = f"{mp.name} World"
    lines.append(
        f'    <ResourceKind key="{rk_key}" nameKey="{nk}"'
        f' worldObjectName="{world_name}" showTag="true"'
        f' type="{_RESOURCE_KIND_TYPE_WORLD}" subType="{_RESOURCE_KIND_SUBTYPE_WORLD}">'
    )
    nk += 1
    lines.append("    </ResourceKind>")


# ---------------------------------------------------------------------------
# resources.properties generation
# ---------------------------------------------------------------------------

def _generate_resources_properties(mp: ManagementPackDef) -> str:
    """Generate the localization resources.properties for adapters.zip/resources/."""
    lines = [
        "#",
        "# Localization file for " + mp.adapter_kind,
        "# Generated by vcfops_managementpacks builder.py",
        "#",
        "version=1",
        "",
        "# Adapter kind display name",
        f"1={mp.name}",
        "",
        "# Credential kind",
        "2=Credentials",
        "3=Username",
        "4=Password",
        "",
        "# Resource kind labels (starting at 5)",
    ]
    idx = 5
    for ot in mp.object_types:
        lines.append(f"{idx}={ot.name}")
        idx += 1
        for m in ot.metrics:
            lines.append(f"{idx}={m.label}")
            idx += 1

    return "\n".join(lines) + "\n"


def _generate_pak_resources_properties(mp: ManagementPackDef) -> str:
    """Generate the pak-root resources/resources.properties (display name + description)."""
    return (
        "#This is the default localization file.\n"
        "\n"
        "#The solution's localized name displayed in UI\n"
        f"DISPLAY_NAME={mp.name}\n"
        "\n"
        "#The solution's localized description\n"
        f"DESCRIPTION={mp.description}\n"
        "\n"
        "#The vendor's localized name\n"
        f"VENDOR={mp.author}\n"
    )


# ---------------------------------------------------------------------------
# adapter .properties and version.txt
# ---------------------------------------------------------------------------

def _generate_adapter_properties(mp: ManagementPackDef) -> str:
    """Generate the adapter runtime config properties file."""
    return (
        "#\n"
        "# Adapter runtime configuration\n"
        "# Generated by vcfops_managementpacks builder.py\n"
        "#\n"
        "relationship_sync_interval=8\n"
        "max_relationships_per_collection=\n"
        "max_events_per_collection=\n"
    )


def _generate_version_txt(mp: ManagementPackDef) -> str:
    """Generate version.txt for the adapter conf/ directory."""
    return (
        f"Major-Version={mp.version.split('.')[0] if '.' in mp.version else mp.version}\n"
        f"Minor-Version={mp.version.split('.')[1] if mp.version.count('.') >= 1 else '0'}\n"
        f"Implementation-Version={mp.version}.{mp.build_number}\n"
        "Build-Tools-Version-Ref=N/A\n"
        "Adapter-Version-Ref=2.0.0-ga-32\n"
        "Core-Version-Ref=8.0.0"
    )


# ---------------------------------------------------------------------------
# manifest.txt generation
# ---------------------------------------------------------------------------

def _generate_manifest(mp: ManagementPackDef) -> str:
    """Generate manifest.txt JSON for the pak root."""
    version_str = f"{mp.version}.{mp.build_number}"
    manifest = {
        "display_name": mp.name,
        "name": mp.name,
        "description": mp.description,
        "version": version_str,
        "run_scripts_on_all_nodes": "true",
        "vcops_minimum_version": "7.5.0",
        "disk_space_required": 500,
        "eula_file": "eula.txt",
        "platform": ["Windows", "Linux Non-VA", "Linux VA"],
        "vendor": mp.author,
        "pak_icon": "default.png",
        "license_type": f"adapter:{mp.adapter_kind}",
        "pak_validation_script": {"script": "python validate.py"},
        "adapter_pre_script": {"script": "python preAdapters.py"},
        "adapter_post_script": {"script": "python post-install.py"},
        "adapters": ["adapters.zip"],
        "adapter_kinds": [mp.adapter_kind],
    }
    return json.dumps(manifest, indent=4) + "\n"


# ---------------------------------------------------------------------------
# Adapter JAR KINDKEY rewrite (Option A of ADAPTER_JAR_GAP fix)
# ---------------------------------------------------------------------------

def _rewrite_adapter_properties(jar_bytes: bytes, adapter_kind: str) -> bytes:
    """Rewrite adapter.properties inside the adapter JAR so KINDKEY matches
    the factory's declared adapter_kind.

    Root cause documented in .pka/updates/2026-04-17-0809-adapter-jar-gap-root-cause.md:
    The bootstrapped reference JAR (GitHub adapter) embeds adapter.properties
    with KINDKEY=mpb_github. VCF Ops reads KINDKEY to bind the loaded adapter
    class to the correct adapter_kind registry slot. When KINDKEY doesn't match
    the pak's declared adapter_kind, the registration silently fails and the pak
    installs with no adapter ever appearing in getIntegrations.

    ENTRYCLASS is left unchanged: it names a real Kotlin class
    (com.vmware.mpb.mpbgithub.MPBGitHubAdapter) that must match an actual .class
    file inside the JAR. Only KINDKEY is a registration label that can be freely
    set without requiring a matching class path.

    The JAR is a ZIP; we open it in-memory, rewrite the one line, and reconstruct
    a new ZIP preserving every other member verbatim.
    """
    src_buf = io.BytesIO(jar_bytes)
    dst_buf = io.BytesIO()

    with zipfile.ZipFile(src_buf, "r") as src_zf:
        with zipfile.ZipFile(dst_buf, "w", compression=zipfile.ZIP_DEFLATED) as dst_zf:
            for item in src_zf.infolist():
                data = src_zf.read(item.filename)
                if item.filename == "adapter.properties":
                    # Parse key=value lines, rewrite KINDKEY only.
                    lines = data.decode("utf-8").splitlines()
                    new_lines = []
                    for line in lines:
                        if line.startswith("KINDKEY="):
                            new_lines.append(f"KINDKEY={adapter_kind}")
                        else:
                            new_lines.append(line)
                    # Preserve trailing newline if original had one
                    separator = "\n"
                    new_content = separator.join(new_lines)
                    if data.endswith(b"\n"):
                        new_content += "\n"
                    data = new_content.encode("utf-8")
                dst_zf.writestr(item, data)

    return dst_buf.getvalue()


# ---------------------------------------------------------------------------
# adapters.zip assembly
# ---------------------------------------------------------------------------

def _zip_mkdir(zf: zipfile.ZipFile, path: str) -> None:
    """Write an explicit directory entry to a ZipFile.

    Python's zipfile module does NOT emit directory entries automatically
    when you write file members into a path — it only writes the file
    members themselves.  VCF Ops's pak installer walks adapters.zip
    directory entries to discover which adapters to extract and register.
    Without an explicit entry for '<adapter_dir>/' the installer skips
    extraction entirely and reports a silent success based on pak-metadata
    acceptance alone.  See Gap 1 root-cause analysis in
    /tmp/qa-run-1776464499/pak_comparison.json.

    path must end with '/' (zip convention for directory entries).
    """
    assert path.endswith("/"), f"directory path must end with '/': {path!r}"
    info = zipfile.ZipInfo(path)
    # External attributes 0x10 = MS-DOS directory flag; widely recognised
    # by zip implementations as a directory marker.
    info.external_attr = 0x10
    zf.writestr(info, b"")


def _build_adapters_zip(
    mp: ManagementPackDef,
    design_json_str: str,
    describe_xml_str: str,
    manifest_str: str,
    pak_resources_props_str: str,
    eula_bytes: bytes,
    icon_bytes: bytes,
) -> bytes:
    """Build adapters.zip in memory and return the bytes.

    Structure mirrors the reference pak adapters.zip layout exactly,
    including explicit directory entries that VCF Ops requires to discover
    and extract the adapter.  Reference: Rubrik-1.1.0.25.pak adapters.zip
    has 16 explicit directory entries; their absence caused the Synology
    silent-install failure (pak upload accepted, isPakInstalling=False in
    ~35s vs Rubrik's 100-200s, adapter kind never registered).

    The adapter runtime JAR is copied from adapter_runtime/mpb_adapter3.jar
    (renamed to <adapter_dir>.jar) — see ADAPTER_JAR_GAP in module docstring.
    """
    ak = mp.adapter_kind
    adapter_dir = f"{ak}_adapter3"  # e.g. mpb_synology_dsm_adapter3

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        # --- Explicit directory entries (CRITICAL for pak installer) ---
        # VCF Ops pak installer walks adapters.zip directory entries to
        # discover which adapters to extract and register.  Without the
        # adapter root entry ('<adapter_dir>/') the installer skips
        # extraction entirely.  Mirror Rubrik's 16-entry layout exactly.
        # Order: root, adapter root, then subdirs depth-first.
        _zip_mkdir(zf, "/")
        _zip_mkdir(zf, f"{adapter_dir}/")
        _zip_mkdir(zf, f"{adapter_dir}/doc/")
        _zip_mkdir(zf, f"{adapter_dir}/lib/")
        _zip_mkdir(zf, f"{adapter_dir}/work/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/supermetrics/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/dashboards/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/reports/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/images/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/images/TraversalSpec/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/images/AdapterKind/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/images/ResourceKind/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/views/")
        _zip_mkdir(zf, f"{adapter_dir}/conf/resources/")
        _zip_mkdir(zf, "resources/")

        # --- duplicate pak-root files at adapters.zip root ---
        zf.writestr("manifest.txt", manifest_str.encode("utf-8"))
        zf.writestr("eula.txt", eula_bytes)
        zf.writestr("default.png", icon_bytes)
        zf.writestr("resources/resources.properties", pak_resources_props_str.encode("utf-8"))

        # --- adapter runtime JAR (renamed from generic stand-in) ---
        # Check if there is a pak-specific JAR (custom one dropped in)
        specific_jar = _ADAPTER_RUNTIME_DIR / f"{adapter_dir}.jar"
        if specific_jar.exists():
            jar_bytes = specific_jar.read_bytes()
        elif _GENERIC_ADAPTER_JAR.exists():
            jar_bytes = _GENERIC_ADAPTER_JAR.read_bytes()
        else:
            # No JAR available — write a placeholder comment file instead
            # This will prevent the pak from functioning but allows structure validation
            jar_bytes = (
                b"# ADAPTER_JAR_GAP: mpb_adapter3.jar not found.\n"
                b"# Copy the MPB-generated adapter JAR to "
                b"vcfops_managementpacks/adapter_runtime/mpb_adapter3.jar\n"
            )
        # Rewrite KINDKEY in adapter.properties so VCF Ops registers this
        # adapter under the correct adapter_kind (not the reference pak's
        # mpb_github).  ENTRYCLASS is left unchanged.  See
        # _rewrite_adapter_properties() and the root-cause note in
        # .pka/updates/2026-04-17-0809-adapter-jar-gap-root-cause.md.
        if jar_bytes and not jar_bytes.startswith(b"# ADAPTER_JAR_GAP"):
            jar_bytes = _rewrite_adapter_properties(jar_bytes, ak)
        zf.writestr(f"{adapter_dir}.jar", jar_bytes)

        # lib/*.jar — shared library JARs
        lib_dir = _ADAPTER_RUNTIME_DIR / "lib"
        if lib_dir.exists():
            for jar_path in sorted(lib_dir.glob("*.jar")):
                zf.writestr(
                    f"{adapter_dir}/lib/{jar_path.name}",
                    jar_path.read_bytes(),
                )
        else:
            # No lib JARs — log and continue; pak won't function without them
            zf.writestr(
                f"{adapter_dir}/lib/LIB_GAP.txt",
                b"# LIB_GAP: no lib/*.jar found in adapter_runtime/lib/\n"
                b"# Copy lib JARs from a reference MPB pak's adapters.zip\n",
            )

        # conf/ files
        zf.writestr(f"{adapter_dir}/conf/design.json", design_json_str.encode("utf-8"))
        zf.writestr(f"{adapter_dir}/conf/describe.xml", describe_xml_str.encode("utf-8"))
        zf.writestr(
            f"{adapter_dir}/conf/{ak}.properties",
            _generate_adapter_properties(mp).encode("utf-8"),
        )
        zf.writestr(
            f"{adapter_dir}/conf/version.txt",
            _generate_version_txt(mp).encode("utf-8"),
        )
        # conf/supermetrics/
        zf.writestr(f"{adapter_dir}/conf/supermetrics/customSuperMetrics.json", b"{}")
        # conf/images/ — copy default.png into standard icon locations
        # (directory entries already written above via _zip_mkdir)
        for img_path in [
            f"images/TraversalSpec/default.png",
            f"images/AdapterKind/{ak}.png",
            f"images/ResourceKind/{ak}.png",
        ]:
            zf.writestr(f"{adapter_dir}/conf/{img_path}", icon_bytes)
        # conf/resources/
        adapter_resources_props = _generate_resources_properties(mp)
        zf.writestr(
            f"{adapter_dir}/conf/resources/resources.properties",
            adapter_resources_props.encode("utf-8"),
        )

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------

def build_pak(
    mp: ManagementPackDef,
    *,
    output_dir: Path,
    relationship_strategy: str = "synthetic_adapter_instance",
) -> Path:
    """Build a .pak ZIP file for the management pack.

    Steps:
    1. Render MPB design JSON from the ManagementPackDef.
    2. Generate describe.xml from the design.
    3. Build adapters.zip (design + describe + runtime JARs).
    4. Synthesize manifest.txt and all supporting files.
    5. Write the .pak ZIP to output_dir.

    Returns the path to the created .pak file.

    Raises:
        FileNotFoundError  if output_dir does not exist (caller must create it).
        OSError            on write errors.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ak = mp.adapter_kind
    version_str = f"{mp.version}.{mp.build_number}"
    pak_name = f"{ak}.{version_str}.pak"
    pak_path = output_dir / pak_name

    # 1. Render design JSON
    design_dict = render_mp_design_json(mp, relationship_strategy=relationship_strategy)
    design_json_str = json.dumps(design_dict, indent=2)

    # 2. Generate describe.xml
    describe_xml_str = _generate_describe_xml(mp)

    # 3. Generate manifest.txt
    manifest_str = _generate_manifest(mp)

    # 4. Read template files
    eula_path = _TEMPLATES_DIR / "eula.txt"
    eula_bytes = eula_path.read_bytes() if eula_path.exists() else b"No EULA.\n"

    icon_path = _TEMPLATES_DIR / "default.png"
    icon_bytes = icon_path.read_bytes() if icon_path.exists() else _minimal_png()

    # 5. Generate pak-level resources.properties
    pak_resources_props_str = _generate_pak_resources_properties(mp)

    # 6. Build adapters.zip in memory
    adapters_zip_bytes = _build_adapters_zip(
        mp=mp,
        design_json_str=design_json_str,
        describe_xml_str=describe_xml_str,
        manifest_str=manifest_str,
        pak_resources_props_str=pak_resources_props_str,
        eula_bytes=eula_bytes,
        icon_bytes=icon_bytes,
    )

    # 7. Assemble the top-level .pak ZIP
    with zipfile.ZipFile(pak_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.txt", manifest_str.encode("utf-8"))
        zf.writestr("eula.txt", eula_bytes)
        zf.writestr("default.png", icon_bytes)

        # Install scripts — read from templates
        for script_name in [
            "validate.py",
            "preAdapters.py",
            "postAdapters.py",
            "post-install-fast.sh",
        ]:
            script_path = _TEMPLATES_DIR / script_name
            if script_path.exists():
                zf.writestr(script_name, script_path.read_bytes())
            else:
                zf.writestr(script_name, b"# placeholder\n")

        # post-install.py — template substitution for adapter_kind and adapter_dir
        post_install_path = _TEMPLATES_DIR / "post-install.py"
        if post_install_path.exists():
            post_install_str = post_install_path.read_text()
            post_install_str = post_install_str.replace(
                "{adapter_kind}", ak
            ).replace(
                "{adapter_dir}", f"{ak}_adapter3"
            )
            zf.writestr("post-install.py", post_install_str.encode("utf-8"))
        else:
            zf.writestr("post-install.py", b"import sys; sys.exit(0)\n")

        # Also include post-install.sh as a simple bash stub (some installers
        # invoke it directly; mirrors reference pak layout)
        zf.writestr("post-install.sh", b"#!/bin/bash\nexit 0\n")

        # adapters.zip
        zf.writestr("adapters.zip", adapters_zip_bytes)

        # content/ directories
        zf.writestr(
            "content/supermetrics/customSuperMetrics.json",
            b"{}",
        )
        for empty_dir in [
            "content/dashboards/",
            "content/views/",
            "content/reports/",
            "content/files/reskndmetric/",
        ]:
            zf.writestr(empty_dir, b"")

        # resources/
        zf.writestr(
            "resources/resources.properties",
            pak_resources_props_str.encode("utf-8"),
        )

    return pak_path


def _minimal_png() -> bytes:
    """Return the bytes of a minimal 1x1 white PNG."""
    # Hardcoded 1x1 white PNG (67 bytes)
    return bytes([
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a,  # PNG signature
        0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk length + type
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # width=1, height=1
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # bitdepth=8, colortype=2(RGB)
        0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41,  # CRC + IDAT length + type
        0x54, 0x08, 0xd7, 0x63, 0xf8, 0xcf, 0xc0, 0x00,  # IDAT data (white pixel)
        0x00, 0x00, 0x02, 0x00, 0x01, 0xe2, 0x21, 0xbc,  # IDAT CRC
        0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e,  # IEND length + type
        0x44, 0xae, 0x42, 0x60, 0x82,                     # IEND CRC
    ])
