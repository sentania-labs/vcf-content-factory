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
from typing import Callable, Dict, Iterable, List, Optional, Tuple

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
    "read_recipe",
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


# Setting Location -> (resource_kind, object_type_prefix). The
# 'Setting Location' column in Bob Plankers' SCG source CSVs is a
# second signal that the Component column lacks: 'Component=ESX'
# covers everything that lives on the host *or* is configured through
# a host command, including port-group / virtual-switch security
# policies that should really be stitched to DVS / DVPG objects in
# VCF Ops. Without this, every network control gets mis-classified
# as HostSystem.
#
# Match rules are case-insensitive substring matches. First match
# wins, so list the most-specific patterns first (e.g. "port group"
# before "virtual switch" -- a "Virtual Port Group" string would
# match both otherwise).
#
# Defaults:
# - Port-group controls -> DistributedVirtualPortgroup. Modern
#   production environments overwhelmingly use distributed switches;
#   a future variant could split standard-switch port groups off to
#   HostNetworkSystem based on the source-ID `network-standard-*`
#   prefix.
# - Virtual-switch controls -> DistributedVirtualSwitch. Same
#   rationale.
# - vCenter UI / configuration paths -> VCenterAdapterInstance.
# - ESX advanced / esxcli / shell paths -> HostSystem (this also
#   happens to be what the Component-based fallback would produce,
#   so the entry is defensive in case the Component column is later
#   inconsistent).
#
# Anything that doesn't match falls through to the existing
# Component + source-ID-prefix pipeline. That keeps VM, vSAN, NSX,
# VCF Operations, and other rows on the same path they were on
# before this map existed.
SETTING_LOCATION_MAP: List[tuple] = [
    # Port group (must come before "virtual switch" so "Virtual Port
    # Group" lands on dvpg, not vds)
    ("port group", ("DistributedVirtualPortgroup", "dvpg")),
    # Virtual / distributed switch
    ("distributed switch", ("DistributedVirtualSwitch", "vds")),
    ("virtual switch", ("DistributedVirtualSwitch", "vds")),
    # vCenter Server UI / configuration paths. "vcenter" appears in
    # many forms ("vCenter Server SSO Configuration", "Advanced
    # vCenter Settings", "vCenter Server >> Configure >> ...").
    ("vcenter", ("VCenterAdapterInstance", "vc")),
    # vSphere Client / Content Library / SSO admin paths are all
    # configured through vCenter.
    ("vsphere client", ("VCenterAdapterInstance", "vc")),
    ("content library", ("VCenterAdapterInstance", "vc")),
    ("single sign on", ("VCenterAdapterInstance", "vc")),
    ("vami", ("VCenterAdapterInstance", "vc")),
    # ESX(i) host-side locations. The Component-based fallback
    # already produces HostSystem for these, but pinning them
    # here makes the map self-documenting and protects against
    # source files that mis-tag the Component column.
    ("esx advanced", ("HostSystem", "esx")),
    ("esxi advanced", ("HostSystem", "esx")),
    ("esxcli", ("HostSystem", "esx")),
    ("esx shell", ("HostSystem", "esx")),
    ("esxi shell", ("HostSystem", "esx")),
    ("esx services", ("HostSystem", "esx")),
    ("esxi services", ("HostSystem", "esx")),
    ("esx security profile", ("HostSystem", "esx")),
    ("esxi security profile", ("HostSystem", "esx")),
    ("esx firewall", ("HostSystem", "esx")),
    ("esxi firewall", ("HostSystem", "esx")),
    ("esx authentication", ("HostSystem", "esx")),
    ("esxi authentication", ("HostSystem", "esx")),
    ("esx iscsi", ("HostSystem", "esx")),
    ("esxi iscsi", ("HostSystem", "esx")),
    ("esx vmkernel", ("HostSystem", "esx")),
    ("esxi vmkernel", ("HostSystem", "esx")),
    ("esx time", ("HostSystem", "esx")),
    ("esxi time", ("HostSystem", "esx")),
]


def map_setting_location(setting_location: str) -> Optional[tuple]:
    """Return (resource_kind, prefix) for a Setting Location value.

    Case-insensitive substring matching. First entry in
    SETTING_LOCATION_MAP that matches wins. Returns None if no entry
    matches; caller should fall back to the Component-based pipeline.
    """
    if not setting_location:
        return None
    needle = setting_location.strip().lower()
    if not needle or needle == "n/a":
        return None
    for token, kind_prefix in SETTING_LOCATION_MAP:
        if token in needle:
            return kind_prefix
    return None


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
      0. Multi-key parameter (parameter contains a newline) ->
         manual_audit. A row whose `parameter` column lists multiple
         keys (e.g. vc.smtp: ``mail.smtp.port\\nmail.smtp.username
         \\nmail.smtp.password``) cannot be scored as a single
         key/value lookup against an advanced-settings dictionary —
         the canonical `expected_value` is a sentinel like
         "Configured" / "Persistent Storage Location", not a real
         value to compare. The Java evaluator silently skips these
         rows (``if (param.contains("\\n")) continue``) so tagging them
         advanced_setting at the canonical level falsely inflates the
         per-resource control count. Treating them as manual_audit
         keeps the canonical truth and the evaluator output in
         agreement.
      1. Empty / 'N/A' assessment command -> manual_audit
      2. Assessment command contains Get-AdvancedSetting ->
         advanced_setting
      3. Assessment command contains EsxCli markers -> esxcli
      4. Assessment command reads a vim property -> vim_property
      5. Otherwise -> powercli_only
    """
    if parameter and "\n" in parameter:
        return "manual_audit"
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


# Phase 3 / Batch 3b — DVS + DVPG security-policy classifier.
#
# SCG sources express these controls as PowerCLI cmdlet chains. Two
# distinct shapes appear in SCG 8.0 and 9.0:
#
#   Standard switch / port group (Get-VirtualSwitch / Get-VirtualPortGroup):
#     Get-VMHost -Name $ESX | Get-VirtualSwitch -Standard
#         | Get-SecurityPolicy | select VirtualSwitch,ForgedTransmits
#     Get-VMHost -Name $ESX | Get-VirtualPortGroup -Standard
#         | Get-SecurityPolicy | select VirtualPortGroup,MacChanges
#     Get-VMHost -Name $ESX | Get-VirtualPortGroup -Standard
#         | Get-SecurityPolicy | select VirtualPortGroup,AllowPromiscuous
#
#   Distributed switch / port group (Get-VDSwitch / Get-VDPortgroup):
#     Get-VDSwitch -Name $VDS | Get-VDSecurityPolicy
#     Get-VDPortgroup -Name $VDPG | Get-VDSecurityPolicy
#
# The distributed-switch shape doesn't carry the specific field name
# in the assessment command — the field is in the remediation column
# (Set-VDSecurityPolicy -ForgedTransmits / -MacChanges / -AllowPromiscuous)
# and/or the source_id slug. We detect from the slug as a fallback
# so the classifier still produces a canonical parameter for those rows.
#
# vim25 read path (see VSphereClient.getDvsSecurityPolicy /
# getDvpgSecurityPolicy):
#     DistributedVirtualSwitch.config.defaultPortConfig
#         .securityPolicy.{forgedTransmits,macChanges,allowPromiscuous}.value
#     DistributedVirtualPortgroup.config.defaultPortConfig
#         .securityPolicy.{forgedTransmits,macChanges,allowPromiscuous}.value
#
# So when the classifier matches, we override `parameter` to the
# canonical dot-path: securityPolicy.forgedTransmits etc. The
# Java ControlEvaluator parses that path and dispatches on the
# trailing field name.
#
# The token-set per canonical field has multiple spellings so we
# match both the cmdlet-flag spelling that appears in the assessment
# command body (ForgedTransmits, MacChanges, AllowPromiscuous) AND
# the slug spelling that appears in the source_id and title text
# (forged-transmit, mac-changes, promiscuous-mode). We collapse all
# non-alphanumerics on the comparison side so hyphenated forms match
# the camelCase canonical key.
_SECPOL_FIELD_MAP: Dict[str, List[str]] = {
    "securityPolicy.forgedTransmits": [
        "forgedtransmits",
        "forgedtransmit",
    ],
    "securityPolicy.macChanges": [
        "macchanges",
        "macchange",
    ],
    "securityPolicy.allowPromiscuous": [
        "allowpromiscuous",
        "promiscuousmode",
        "promiscuous",
    ],
}


def _detect_security_policy_field(text: str) -> Optional[str]:
    """Return canonical securityPolicy.<field> string for a chunk of
    text (PowerCLI command, source_id, title), or None.

    Case-insensitive, whitespace- and punctuation-tolerant. Non-
    alphanumeric characters are stripped before matching so a slug
    like `network-reject-mac-changes-dvportgroup` collapses to
    `networkrejectmacchangesdvportgroup` and `macchanges` substring-
    matches it. First field matched wins — security-policy controls
    in SCG sources are one-field-per-row so this is unambiguous.
    """
    if not text:
        return None
    needle = re.sub(r"[^a-z0-9]", "", text.lower())
    for canonical, tokens in _SECPOL_FIELD_MAP.items():
        for token in tokens:
            if token in needle:
                return canonical
    return None


def classify_security_policy_param(powercli_command: str,
                                   source_id: str,
                                   source_title: str) -> Optional[str]:
    """If the PowerCLI command matches a Get-SecurityPolicy /
    Get-VDSecurityPolicy pattern, return the canonical securityPolicy.*
    parameter key. Otherwise return None.

    Detection is case-insensitive and whitespace-tolerant so the
    multi-line continuations the SCG source ships (with embedded
    newlines and varying spacing) all match the same pattern.

    The field name (ForgedTransmits / MacChanges / AllowPromiscuous) is
    looked up in priority order:
      1. the PowerCLI command body (standard-switch shape carries the
         field after `select ...`)
      2. the source_id slug (distributed-switch shape: the assessment
         command is bare `Get-VDSecurityPolicy` but the slug names the
         field, e.g. `vcenter-9.network-reject-forged-transmit-dvportgroup`)
      3. the title text as a last-ditch backstop
    """
    cmd = (powercli_command or "").strip()
    if not cmd:
        return None
    # Whitespace-flattened lowercase view of the command for the
    # cmdlet-shape sniff.
    flat = re.sub(r"\s+", "", cmd).lower()
    standard_shape = (
        "get-securitypolicy" in flat
        and ("get-virtualswitch" in flat
             or "get-virtualportgroup" in flat)
    )
    distributed_shape = "get-vdsecuritypolicy" in flat
    if not (standard_shape or distributed_shape):
        return None
    # Field detection — try each signal in turn.
    field = _detect_security_policy_field(cmd)
    if field is not None:
        return field
    field = _detect_security_policy_field(source_id or "")
    if field is not None:
        return field
    field = _detect_security_policy_field(source_title or "")
    if field is not None:
        return field
    return None


# Phase 3 — vSAN cluster-config classifier.
#
# SCG's vSAN controls do NOT carry PowerCLI commands in the raw source
# CSV ("PowerCLI Command Assessment" is N/A for every vsan-*.* row).
# So the powercli-pattern classifier classify_security_policy_param
# can't fire for these. The only signals we have are the source ID
# slug (vsan-9.<feature>) and the title text.
#
# Of the 14 SCG ClusterComputeResource controls, only TWO are reachable
# via the vim25.jar that ships in this adapter's lib/:
#
#   cluster.managed-disk-claim   <- VsanClusterConfigInfo
#                                   .defaultConfig.autoClaimStorage
#   cluster.object-checksum      <- VsanClusterConfigInfo
#                                   .defaultConfig.checksumEnabled
#
# The other 12 (encryption-rest, encryption-transit-{esa,osa},
# force-provisioning, iscsi-mutual-chap, file-services-*,
# network-isolation-*, operations-reserve, automatic-rebalance,
# auto-policy-management) live on the vSAN Management SDK
# (com.vmware.vim.vsan.binding) jar, which is NOT on this adapter's
# classpath. They stay parameter_kind=manual_audit until the SDK
# jar lands and the Java client grows readers for them.
#
# Note on canonical naming: the canonical PARAMETER value matches the
# key the Java VSphereClient.getClusterVsanConfig() returns
# (vsanConfig.<field>), so the evaluator's vim_property dispatcher
# can look the key up directly with no rewriting.
_VSAN_CLUSTER_PARAM_BY_SLUG: Dict[str, str] = {
    # source_id slug fragment -> canonical parameter
    "managed-disk-claim": "vsanConfig.autoClaimStorage",
    "object-checksum": "vsanConfig.objectChecksumEnabled",
}


# For the two vSAN cluster controls we can read via plain vim25, the
# SCG "Baseline Suggested Value" column uses control-specific
# vocabulary ("Configured", "Disabled") whose polarity against the
# underlying vim25 Boolean isn't obvious without the title context:
#
#   cluster.managed-disk-claim — SCG title says "vSAN must disable
#     managed disk claims" and Suggested=Configured. The underlying
#     vim25 field VsanClusterConfigInfo.defaultConfig.autoClaimStorage
#     should be FALSE for the cluster to be compliant (auto-claim off).
#
#   cluster.object-checksum — SCG title says "vSAN must calculate
#     object checksums to protect data integrity" but the Suggested
#     column reads "Disabled" — which is the SCG-default profile value,
#     NOT the desired state for the vim25 field. Reading the SCG row
#     more closely: the row is an "Audit"-style control where the
#     baseline IS Disabled (for OSA; ESA cannot disable). The
#     vim25 field VsanClusterConfigInfo.defaultConfig.checksumEnabled
#     should match what SCG calls Disabled — i.e. FALSE.
#
# Rather than teach the Java evaluator to invert polarity by source_id
# (which is brittle), we rewrite the canonical expected_value here to a
# JS-style boolean the existing evaluator already handles. The
# evaluator's expectedAsBoolean() maps "true"/"false" directly to
# Boolean.TRUE/FALSE so the comparison against the vim25 boolean is
# unambiguous. The descriptive title and SCG source_ref still carry
# the original "Configured" / "Disabled" SCG language for audit
# traceability.
_VSAN_CLUSTER_EXPECTED_BY_SLUG: Dict[str, str] = {
    "managed-disk-claim": "false",
    "object-checksum": "false",
}


def classify_vsan_cluster_expected(source_id: str) -> Optional[str]:
    """When the row is a vSAN cluster control that we can read via
    plain vim25, return the canonical expected_value (JS-boolean
    form) that pairs with the canonical parameter from
    {@link classify_vsan_cluster_param}. Otherwise return None.

    See {@link _VSAN_CLUSTER_EXPECTED_BY_SLUG} for the polarity
    rationale per control.
    """
    if not source_id:
        return None
    sid = source_id.lower()
    for slug, expected in _VSAN_CLUSTER_EXPECTED_BY_SLUG.items():
        if slug in sid:
            return expected
    return None


# Coverage expansion (build 35) — existing-style vim_property
# reclassifications for HostSystem, VirtualMachine, and DVS/DVPG.
#
# These are SCG controls the recon (scg89-audit-coverage-recon.md)
# classified as reachable with an EXISTING read_recipe style
# (scalar / bool / bool_policy). They ship in the SCG source CSV as
# powercli_only / esxcli / manual_audit because the SCG remediation
# column carries a PowerCLI/esxcli cmdlet — but the underlying state is
# a plain vim25 property, so the data-driven reader can score them with
# no Java per-control.
#
# Keyed by the CANONICAL control_id (prefix.slug) so the override is
# version-stable: the same control_id is produced by both the 8.0 and
# 9.0 normalizers from differing source IDs. When a control_id is in
# this map, the normalizer promotes the row to parameter_kind=vim_property,
# sets `parameter` to the unique vim path the evaluator looks up, sets
# `read_recipe` to "<style>:<vim_path>", and overrides expected_value to
# the form the Java evaluator's expectedAsBoolean() / scalar matcher can
# compare (SCG vocabulary like "Enabled"/"Not Configured" does not
# coerce reliably — see ControlEvaluator.expectedAsBoolean).
#
# A control_id is in this map ONLY when its expected state is exactly
# comparable by the existing evaluator. NTP-source controls
# (esx.timekeeping-sources / esx.time) are deliberately ABSENT: their
# read_recipe (string_list_join of config.dateTimeInfo.ntpConfig.server)
# reads correctly, but the SCG expected_value is the sentinel
# "Site-Specific" — which the actual server list can never string-equal,
# so reclassifying them would manufacture a permanent false "fail". They
# need a presence/non-empty comparison mode the evaluator does not have
# yet; they stay informational and are listed in UNAUDITED_CONTROLS.md.
#
# value: (parameter, read_recipe_style, vim_path, expected_override_or_None)
_VIM_RECLASS_BY_CONTROL_ID: Dict[str, tuple] = {
    # --- DistributedVirtualSwitch (pure CSV — collector already reads
    #     vim props today) ---
    "vds.network-reset-port": (
        "config.policy.portConfigResetAtDisconnect",
        "bool",
        "config.policy.portConfigResetAtDisconnect",
        "true",   # SCG "Enabled" -> reset-at-disconnect must be ON
    ),
    # Same read on the portgroup. SCG 9.1 files the control under
    # Distributed Port Group (dvpg.network-reset-port), and the read is a
    # portgroup-policy field, so this entry is the one every version that
    # maps the control to DVPG needs (#169).
    "dvpg.network-reset-port": (
        "config.policy.portConfigResetAtDisconnect",
        "bool",
        "config.policy.portConfigResetAtDisconnect",
        "true",   # SCG "Enabled" -> reset-at-disconnect must be ON
    ),
    "vds.network-restrict-discovery-protocol": (
        "config.linkDiscoveryProtocolConfig.operation",
        "scalar",
        "config.linkDiscoveryProtocolConfig.operation",
        # Pinned to the enum string the read returns. SCG 8.0 / 9.x write
        # the baseline as "none"; SCG 7.0 writes the same requirement as
        # the prose "Deactivated", which no switch ever reads back (#169).
        "none",
    ),
    "vds.network-restrict-netflow-usage": (
        "config.defaultPortConfig.ipfixEnabled",
        "bool_policy",
        "config.defaultPortConfig.ipfixEnabled",
        "false",  # SCG "Not Configured" -> ipfix (NetFlow) must be OFF
    ),
    "vds.network-nioc": (
        "config.networkResourceManagementEnabled",
        "bool",
        "config.networkResourceManagementEnabled",
        "true",   # SCG "Configured" -> NIOC must be ON (9.0 only)
    ),
    # --- DistributedVirtualPortgroup (pure CSV) ---
    "dvpg.network-mac-learning": (
        "config.defaultPortConfig.macManagementPolicy.macLearningPolicy.enabled",
        "bool",
        "config.defaultPortConfig.macManagementPolicy.macLearningPolicy.enabled",
        "false",  # SCG "Disabled" -> MAC Learning must be OFF
    ),
    # MEDIUM / PARTIAL coverage: this single flag covers only the
    # securityPolicy override of the ~7 per-port override flags the
    # control intends. A `pass` here is NOT full-control fidelity. The
    # partial-coverage caveat is appended to the description below and
    # recorded in UNAUDITED_CONTROLS.md.
    "dvpg.network-restrict-port-level-overrides": (
        "config.policy.securityPolicyOverrideAllowed",
        "bool",
        "config.policy.securityPolicyOverrideAllowed",
        "false",  # securityPolicyOverrideAllowed must be FALSE
    ),
    # --- HostSystem (needs collectHosts() vim_property extension; build 35) ---
    "esx.lockdown-mode": (
        "config.lockdownMode",
        "scalar",
        "config.lockdownMode",
        None,     # SCG expected "lockdownNormal" compares to the enum string
    ),
    "esx.firewall-incoming-default": (
        "config.firewall.defaultPolicy.incomingBlocked",
        "bool",
        "config.firewall.defaultPolicy.incomingBlocked",
        "true",   # SCG "Enabled" (default-block firewall) -> incomingBlocked ON
    ),
    "esx.secureboot-enforcement": (
        "config.encryptionState.requireSecureBoot",
        "bool",
        "config.encryptionState.requireSecureBoot",
        "true",
    ),
    "esx.tpm-configuration": (
        "config.encryptionState.mode",
        "scalar",
        "config.encryptionState.mode",
        None,     # SCG expected "TPM" compares to HostEncryptionState.mode enum
    ),
    "esx.tpm-trusted-binaries": (
        "config.encryptionState.requireExecuteInstalledOnly",
        "bool",
        "config.encryptionState.requireExecuteInstalledOnly",
        "true",   # 9.0 only (execInstalledOnly enforcement)
    ),
    # --- VirtualMachine (needs collectVms() vim_property extension; build 35) ---
    "vm.secure-boot": (
        "config.bootOptions.efiSecureBootEnabled",
        "bool",
        "config.bootOptions.efiSecureBootEnabled",
        "true",
    ),
    "vm.vmotion-encrypted": (
        "config.migrateEncryption",
        "scalar",
        "config.migrateEncryption",
        None,     # SCG expected "required" compares to MigrateEncryptionMode enum
    ),
    "vm.ft-encrypted": (
        "config.ftEncryptionMode",
        "scalar",
        "config.ftEncryptionMode",
        None,     # SCG expected "ftEncryptionRequired" compares to the enum
    ),
    "vm.log-enable": (
        "config.flags.enableLogging",
        "bool",
        "config.flags.enableLogging",
        "true",
    ),
    # scalar config.version returns "vmx-NN". The baseline is scored as a
    # floor: _EXPECTED_REWRITE_BY_CONTROL_ID turns a bare "vmx-N" into
    # "vmx-N or newer", the form the adapter compares as a minimum
    # (ControlEvaluator.VMX_MINIMUM, adapter build 57; #170).
    "vm.virtual-hardware": (
        "config.version",
        "scalar",
        "config.version",
        None,     # SCG baseline, rewritten to the minimum form below
    ),
}


# Partial-coverage caveat appended to the control description so a `pass`
# is never mistaken for full-control fidelity. Keyed by control_id.
_VIM_RECLASS_DESCRIPTION_CAVEAT: Dict[str, str] = {
    "dvpg.network-restrict-port-level-overrides": (
        " [PARTIAL COVERAGE: this adapter checks only the "
        "securityPolicyOverrideAllowed flag (1 of ~7 per-port override "
        "flags the full control intends — block/teaming/vlan/shaping/"
        "vendorConfig/ipfix/trafficFilter overrides are NOT checked). A "
        "pass means the security-policy override is correctly disabled, "
        "not that the whole control is satisfied. See UNAUDITED_CONTROLS.md.]"
    ),
    # Text identical to the compliance repo's VMX_MINIMUM_CAVEAT
    # (scripts/normalize_scg_v91.py), so every SCG version carries the
    # same caveat for this control (#170).
    "vm.virtual-hardware": (
        " [COVERAGE: this adapter reads config.version (e.g. \"vmx-21\") and "
        "scores the VM compliant when its hardware version is at or above the "
        "baseline minimum (the \"or newer\" / \"or higher\" floor), "
        "non-compliant below it. See UNAUDITED_CONTROLS.md.]"
    ),
}


# Expected-value rewrites keyed by control_id. Applied by
# normalize_scg_source AFTER every classifier override, to the final
# expected_value, so one rule covers every SCG version whatever spelling
# that version's baseline uses.
_VMX_BARE_RE = re.compile(r"^\s*vmx-(\d+)\s*$", re.IGNORECASE)


def vmx_minimum(expected: str) -> str:
    """``vmx-N`` -> ``vmx-N or newer``; anything else unchanged.

    ``vmx-N or newer`` / ``vmx-N or higher`` is the form the adapter scores
    as a minimum hardware version (CANONICAL_SCHEMA.md, build 57). SCG 7.0
    and 9.1 already phrase the baseline that way; SCG 8.0 and 9.0 write a
    bare ``vmx-N`` while their titles say "version N or newer", so a VM on
    newer hardware than the baseline failed an exact match (#170).
    """
    m = _VMX_BARE_RE.match(expected or "")
    if not m:
        return expected
    return f"vmx-{m.group(1)} or newer"


_EXPECTED_REWRITE_BY_CONTROL_ID: Dict[str, Callable[[str], str]] = {
    "vm.virtual-hardware": vmx_minimum,
}


def rewrite_expected(control_id: str, expected: str) -> str:
    """Apply the control_id-keyed expected-value rewrite, if any."""
    fn = _EXPECTED_REWRITE_BY_CONTROL_ID.get(control_id)
    return fn(expected) if fn is not None else expected


# esxcli sprint (build 36) — esxcli recipe reclassifications keyed by
# canonical control_id.
#
# Like _VIM_RECLASS_BY_CONTROL_ID, these are SCG controls that ship in
# the raw source as parameter_kind=manual_audit / esxcli because their
# only assessment hint is an esxcli command (or a multi-line `parameter`
# the Java evaluator silently skips). Build 36 added an esxcli SOAP
# reader that rides the existing vCenter session (no host credentials,
# no per-host fan-out — see EsxcliSoapClient + the spike investigation
# §0), so these controls become API-auditable via the read_recipe
# column.
#
# read_recipe grammar: esxcli:<namespace.command>:<ResultField>
#   - <namespace.command> dotted (system.syslog.config.get) maps to the
#     ha-cli-handler moid + vim.EsxCLI.* method mechanically (spike §0.4)
#   - <ResultField> is the PascalCase field of the get struct
#
# value: (parameter, esxcli_recipe, expected_override_or_None,
#         description_caveat_or_None)
#
# SLICE SCOPE (build 36): ONLY syslog persistence. The SSH / firewall /
# account / key-persistence esxcli controls are HELD for a later build
# (design section C) and are deliberately absent here.
#
# What is NOT here and WHY (proven against the live struct captured from
# vcf-lab-mgmt-esx01 — spike §2):
#   - esx.log-audit-persistent / esx.logs-audit-persistent: the
#     `system syslog config get` struct carries NO audit-record-
#     persistence field (its fields are AllowVsanBacking,
#     EnforceSSLCertificates, LocalLogOutput, LocalLogOutputIsConfigured,
#     LocalLogOutputIsPersistent, LogLevel, RemoteHost,
#     StrictX509Compliance). Audit-record location lives in a separate
#     namespace (system auditrecords / the auditRecord.storageDirectory
#     advanced setting), not in this get. We do NOT force it onto a
#     field that does not exist — it stays manual_audit. Holding it is
#     the build-35 discipline: never manufacture a read.
#   - RemoteHost (remote-syslog): the remote-syslog controls
#     (esx.logs-remote / esx.log-forwarding) are already evaluable as
#     advanced_setting on Syslog.global.logHost via OptionManager today;
#     reclassifying them to esxcli would be churn with no coverage gain.
#     Held.
#
# The `parameter` we set is the PascalCase field name itself
# (LocalLogOutputIsPersistent). It is the key the Java evaluator looks
# up in the property-value map and must be UNIQUE among the host
# control parameters; LocalLogOutputIsPersistent does not collide with
# any advanced_setting or vim_property parameter in the SCG profiles.
_ESXCLI_RECLASS_BY_CONTROL_ID: Dict[str, tuple] = {
    # ESXi local-log persistence. Absorbs the parked Tier A item: a
    # clean boolean (LocalLogOutputIsPersistent == true) is strictly
    # better than the old ScratchConfig "not-equal /tmp/scratch" hack.
    # control_id is identical across the 8.0 and 9.0 normalizers
    # (esx.logs-persistent vs esx.log-persistent) so BOTH are listed.
    "esx.logs-persistent": (
        "LocalLogOutputIsPersistent",
        "esxcli:system.syslog.config.get:LocalLogOutputIsPersistent",
        "true",
        None,
    ),
    "esx.log-persistent": (
        "LocalLogOutputIsPersistent",
        "esxcli:system.syslog.config.get:LocalLogOutputIsPersistent",
        "true",
        None,
    ),

    # ----------------------------------------------------------------
    # Build 37 — esxcli sprint section C: SSH-daemon hardening, account
    # shell access, key-persistence, syslog log-filter, TLS profile.
    #
    # Every recipe below is derived VERBATIM from the SCG SOURCE
    # "PowerCLI Command Assessment" column (vmware_scg_8.0.csv /
    # vmware_scg_9.0.csv) — the exact namespace.command and the exact
    # PascalCase field the audit command selects. We do NOT guess; a
    # control whose audit command is not a clean single-value esxcli
    # read is HELD (see the held-controls block after this map).
    #
    # Two recipe shapes are used:
    #   esxcli:<ns.command>:<Field>                       (get-struct)
    #   esxcli:<ns.command>:<Field>[<Selector>=<Value>]   (list row)
    # The list-row shape (build-37 EsxcliSoapClient.readRowField) selects
    # the first ArrayOfDataObject row whose <Selector> field equals
    # <Value> and returns that row's <Field>. UNREADABLE on miss — never
    # a false pass (build-35 contract).
    # ----------------------------------------------------------------

    # --- SSH daemon hardening (8.0). One bulk command
    #     `system.ssh.server.config.list` returns Key/Value rows; each
    #     control selects its row by Key and reads Value. Cached per host
    #     so all 11 controls cost ONE ExecuteSoap. The expected_value is
    #     SCG's own (clean single values: no/yes/3/200//etc/issue/cipher
    #     list) — NOT overridden. PowerCLI audit cmd proves both the row
    #     selector field (Key) and the returned field (Value).
    "esx.ssh-fips-ciphers": (
        "ssh.ciphers",
        "esxcli:system.ssh.server.config.list:Value[Key=ciphers]",
        None,
        None,
    ),
    "esx.ssh-gateway-ports": (
        "ssh.gatewayports",
        "esxcli:system.ssh.server.config.list:Value[Key=gatewayports]",
        None,
        None,
    ),
    "esx.ssh-host-based-auth": (
        "ssh.hostbasedauthentication",
        "esxcli:system.ssh.server.config.list:Value[Key=hostbasedauthentication]",
        None,
        None,
    ),
    "esx.ssh-idle-timeout-count": (
        "ssh.clientalivecountmax",
        "esxcli:system.ssh.server.config.list:Value[Key=clientalivecountmax]",
        None,
        None,
    ),
    "esx.ssh-idle-timeout-interval": (
        "ssh.clientaliveinterval",
        "esxcli:system.ssh.server.config.list:Value[Key=clientaliveinterval]",
        None,
        None,
    ),
    "esx.ssh-login-banner": (
        "ssh.banner",
        "esxcli:system.ssh.server.config.list:Value[Key=banner]",
        None,
        None,
    ),
    "esx.ssh-rhosts": (
        "ssh.ignorerhosts",
        "esxcli:system.ssh.server.config.list:Value[Key=ignorerhosts]",
        None,
        None,
    ),
    "esx.ssh-stream-local-forwarding": (
        "ssh.allowstreamlocalforwarding",
        "esxcli:system.ssh.server.config.list:Value[Key=allowstreamlocalforwarding]",
        None,
        None,
    ),
    "esx.ssh-tcp-forwarding": (
        "ssh.allowtcpforwarding",
        "esxcli:system.ssh.server.config.list:Value[Key=allowtcpforwarding]",
        None,
        None,
    ),
    "esx.ssh-tunnels": (
        "ssh.permittunnel",
        "esxcli:system.ssh.server.config.list:Value[Key=permittunnel]",
        None,
        None,
    ),
    "esx.ssh-user-environment": (
        "ssh.permituserenvironment",
        "esxcli:system.ssh.server.config.list:Value[Key=permituserenvironment]",
        None,
        None,
    ),

    # --- Account shell access (list-row selection on UserID, read
    #     Shellaccess). PowerCLI audit cmd:
    #       $ESXcli.system.account.list.Invoke()
    #         | Where {$_.UserID -eq '<acct>'} | Select Shellaccess
    #     control_ids differ across profiles (8.0 esx.account-dcui /
    #     esx.account-vpxuser; 9.0 esx.disable-accounts-dcui). The
    #     expected_value is SCG's own; NOTE the 8.0/9.0 vocabulary
    #     diverges (false vs Disabled) — the evaluator coerces both to
    #     a boolean-FALSE check (expectedAsBoolean handles "false" and
    #     "disabled"), so they score equivalently IF Shellaccess returns
    #     "true"/"false". The Shellaccess return FORMAT is unverified on
    #     a live host — see the build-37 verification note. A wrong
    #     format surfaces as a loud FAIL (never a false pass), correctable
    #     on devel.
    "esx.account-dcui": (
        "account.dcui.shellaccess",
        "esxcli:system.account.list:Shellaccess[UserID=dcui]",
        None,
        None,
    ),
    "esx.account-vpxuser": (
        "account.vpxuser.shellaccess",
        "esxcli:system.account.list:Shellaccess[UserID=vpxuser]",
        None,
        None,
    ),
    "esx.disable-accounts-dcui": (
        "account.dcui.shellaccess",
        "esxcli:system.account.list:Shellaccess[UserID=dcui]",
        None,
        None,
    ),

    # --- Key persistence (get-struct, field Enabled). 8.0 + 9.0 share
    #     control_id esx.key-persistence. PowerCLI:
    #       $ESXcli.system.security.keypersistence.get.invoke()
    #         | Select-Object -ExpandProperty Enabled
    #     SCG expected_value 'false' (clean boolean).
    "esx.key-persistence": (
        "keypersistence.Enabled",
        "esxcli:system.security.keypersistence.get:Enabled",
        None,
        None,
    ),

    # --- Syslog log filtering (get-struct, field LogFilteringEnabled).
    #     8.0 esx.logs-filter / 9.0 esx.log-filter. PowerCLI:
    #       $ESXcli.system.syslog.config.logfilter.get.invoke()
    #         | Select -ExpandProperty LogFilteringEnabled
    #     SCG expected_value 'false' (clean boolean).
    "esx.logs-filter": (
        "syslog.LogFilteringEnabled",
        "esxcli:system.syslog.config.logfilter.get:LogFilteringEnabled",
        None,
        None,
    ),
    "esx.log-filter": (
        "syslog.LogFilteringEnabled",
        "esxcli:system.syslog.config.logfilter.get:LogFilteringEnabled",
        None,
        None,
    ),

    # --- TLS server profile (get-struct, field Profile). 8.0
    #     esx.tls-profile / 9.0 esx.tls-ciphers. PowerCLI:
    #       $ESXcli.system.tls.server.get.invoke()
    #         | Select-Object -ExpandProperty Profile
    #     SCG expected_value 'NIST_2024' (clean string compare).
    "esx.tls-profile": (
        "tls.Profile",
        "esxcli:system.tls.server.get:Profile",
        None,
        None,
    ),
    "esx.tls-ciphers": (
        "tls.Profile",
        "esxcli:system.tls.server.get:Profile",
        None,
        None,
    ),
}


# Build 38 — service_state vim_property reclassifications.
#
# ESXi services can be read directly from HostSystem.config.service.service[]
# via a new read_recipe style: service_state:<key>:running. The recipe
# selects the HostServiceInfo element whose key== matches <key> and returns
# the running boolean. Because the state is a plain vim25 property on
# HostConfigInfo, the parameter_kind is vim_property (not a new kind).
#
# All service controls follow the same pattern:
#   - parameter: service.<key>.running  (unique per-service key)
#   - read_recipe: service_state:<key>:running
#   - expected: "false" (service should be stopped) or "true" (ntpd)
#   - value_type: boolean (inferred from "true"/"false" override)
#
# Keyed by canonical control_id, shared across 8.0 and 9.0 where the same
# control_id appears in both profiles.
_SERVICE_STATE_RECLASS_BY_CONTROL_ID: Dict[str, tuple] = {
    # --- Build 38: SCG 8.0 service deactivation controls ---
    # esx.deactivate-cim — CIM broker (sfcbd-watchdog). SCG: "Stopped".
    "esx.deactivate-cim": (
        "service.sfcbd-watchdog.running",
        "service_state:sfcbd-watchdog:running",
        "false",
    ),
    # esx.deactivate-shell — TSM (ESXi Shell). SCG: "Stopped".
    # Shared key across 8.0 (esxi-8.deactivate-shell) and 9.0
    # (esx-9.deactivate-shell); both normalizers produce esx.deactivate-shell.
    "esx.deactivate-shell": (
        "service.TSM.running",
        "service_state:TSM:running",
        "false",
    ),
    # esx.deactivate-slp — SLP daemon. SCG: "Stopped". 8.0 only.
    "esx.deactivate-slp": (
        "service.slpd.running",
        "service_state:slpd:running",
        "false",
    ),
    # esx.deactivate-snmp — SNMP daemon. SCG: "Stopped". 8.0 only;
    # 9.0 uses esx.snmp.
    "esx.deactivate-snmp": (
        "service.snmpd.running",
        "service_state:snmpd:running",
        "false",
    ),
    # esx.deactivate-ssh — TSM-SSH (SSH daemon). SCG: "Stopped". 8.0 only;
    # 9.0 uses esx.ssh.
    "esx.deactivate-ssh": (
        "service.TSM-SSH.running",
        "service_state:TSM-SSH:running",
        "false",
    ),
    # esx.timekeeping-services — ntpd. SCG: "Running". 8.0 only;
    # 9.0 uses esx.time.
    "esx.timekeeping-services": (
        "service.ntpd.running",
        "service_state:ntpd:running",
        "true",
    ),
    # --- Build 38: SCG 9.0 service controls (different slugs) ---
    # esx.snmp — SNMP daemon. 9.0 slug for esx.deactivate-snmp (8.0).
    "esx.snmp": (
        "service.snmpd.running",
        "service_state:snmpd:running",
        "false",
    ),
    # esx.ssh — SSH daemon. 9.0 slug for esx.deactivate-ssh (8.0).
    "esx.ssh": (
        "service.TSM-SSH.running",
        "service_state:TSM-SSH:running",
        "false",
    ),
    # esx.time — ntpd. 9.0 slug for esx.timekeeping-services (8.0).
    "esx.time": (
        "service.ntpd.running",
        "service_state:ntpd:running",
        "true",
    ),
}


def classify_service_state_reclass(control_id: str):
    """If ``control_id`` is a build-38 service_state vim_property
    reclassification, return
    ``(parameter, read_recipe, expected_override)``.
    Otherwise return ``None``.

    The normalizer applies this after the esxcli reclass (the two
    control_id sets do not overlap). It promotes the row to
    parameter_kind=vim_property with a service_state recipe the Java
    VSphereClient.readServiceState() dispatches on.
    """
    entry = _SERVICE_STATE_RECLASS_BY_CONTROL_ID.get(control_id)
    if entry is None:
        return None
    return entry  # (parameter, read_recipe, expected_override)


# Build 40, re-keyed in #169: vim_property reclassifications keyed by
# control_id AND source product.
#
# Used only when a control_id is shared by two source rows and only ONE of
# them should be reclassified (the other stays at its naturally-derived kind).
# Currently covers:
#
#   dvpg.network-vgt: produced by BOTH the ESX standard-switch row
#   (esxi-7 / esxi-8 / esx-9 .network-vgt, stays powercli_only) AND the
#   vCenter distributed-switch row (vcenter-7 / -8 / -9 .network-vgt,
#   promoted to vim_property). The control_id is identical for both; the
#   source product separates them.
#
# The source product is the canonical prefix the source-ID prefix maps to
# in SOURCE_ID_PREFIX_MAP (vcenter -> vc, esxi / esx -> esx), so a rule
# here names no SCG version and covers every one, including the next.
#
# value: (source_products, (parameter, read_recipe_style, vim_path,
#         expected_override_or_None))
# DVPG VGT check: the vlan_id_not recipe reads the vlan object's type/id
# and returns true when VLAN 4095 (VGT) is NOT configured. One constant,
# shared by this rule and the deprecated source-ID table below, so the two
# cannot diverge.
_VGT_DVPG_RECIPE: tuple = (
    "config.defaultPortConfig.vlan.notVgt",
    "vlan_id_not",
    "config.defaultPortConfig.vlan",
    "true",
)

_VIM_RECLASS_BY_CONTROL_ID_AND_PRODUCT: Dict[str, tuple] = {
    "dvpg.network-vgt": (frozenset({"vc"}), _VGT_DVPG_RECIPE),
}


def source_product(source_id: str) -> str:
    """Canonical product prefix of a versioned SCG source ID, or ''.

    ``vcenter-8.network-vgt`` -> ``vc``; ``esx-9.network-vgt`` -> ``esx``.
    Same parse as derive_resource_kind, so it follows SOURCE_ID_PREFIX_MAP
    (including entries a driver adds at run time). A source ID with no
    version-prefixed shape (SCG 6.7 Guideline IDs) returns ''.
    """
    if not source_id:
        return ""
    m = re.match(r"^([a-zA-Z]+)-?\d+(?:\.\d+)?\.", source_id.strip())
    if not m:
        return ""
    mapped = SOURCE_ID_PREFIX_MAP.get(m.group(1).lower())
    return mapped[0] if mapped is not None else ""


def classify_scoped_vim_reclass(control_id: str, source_id: str):
    """vim_property reclassification keyed by control_id, limited to the
    source products listed for it. Returns
    ``(parameter, read_recipe, expected_override_or_None, caveat_or_None)``
    or ``None``.

    Applied AFTER classify_vim_reclass so it can selectively override one
    of two rows that share a control_id.
    """
    entry = _VIM_RECLASS_BY_CONTROL_ID_AND_PRODUCT.get(control_id)
    if entry is None:
        return None
    products, (parameter, style, vim_path, expected_override) = entry
    if source_product(source_id) not in products:
        return None
    return (parameter, f"{style}:{vim_path}", expected_override, None)


# DEPRECATED (#169): the source-ID-keyed form of the rule above. The factory
# SCG pipeline no longer reads it. It stays, with its build-40 entries,
# only because the compliance repo's SCG 6.7 and 7.0 drivers call
# classify_source_id_vim_reclass and guard on and extend this dict; their
# output is unchanged because the control_id rule covers the same rows.
# Remove both once those drivers use classify_scoped_vim_reclass.
#
# value: (parameter, read_recipe_style, vim_path, expected_override_or_None).
# Built from _VGT_DVPG_RECIPE, the tuple the control_id rule uses, so an
# edit to the recipe reaches both.
_VIM_RECLASS_BY_SOURCE_ID: Dict[str, tuple] = {
    "vcenter-8.network-vgt": _VGT_DVPG_RECIPE,
    "vcenter-9.network-vgt": _VGT_DVPG_RECIPE,
}


def classify_source_id_vim_reclass(source_id: str):
    """DEPRECATED (#169): use classify_scoped_vim_reclass. Kept for the
    compliance repo's 6.7 / 7.0 drivers; see _VIM_RECLASS_BY_SOURCE_ID.

    If ``source_id`` is a vim_property reclassification keyed by source_id
    (build 40 dvpg.network-vgt distributed-switch rows), return
    ``(parameter, read_recipe, expected_override_or_None, caveat_or_None)``.
    Otherwise return ``None``.
    """
    entry = _VIM_RECLASS_BY_SOURCE_ID.get(source_id)
    if entry is None:
        return None
    parameter, style, vim_path, expected_override = entry
    read_recipe = f"{style}:{vim_path}"
    return (parameter, read_recipe, expected_override, None)


# Build 39/40/41 — generic control overrides for advanced_setting and
# vami_api reclassifications keyed by canonical control_id.
#
# These controls cannot use the vim_property or esxcli reclass maps because
# their target parameter_kind is neither vim_property nor esxcli:
#
#   advanced_setting reclassifications (build 39):
#     esx.logs-audit-persistent / esx.log-audit-persistent — source has a
#     multi-key parameter (ScratchConfig.CurrentScratchLocation\n
#     Syslog.global.auditRecord.storageDirectory). The normalizer promotes
#     multi-key parameters to manual_audit unconditionally (priority 0 in
#     classify_parameter_kind). The reclassification singles out the one key
#     that IS evaluable (ScratchConfig.CurrentScratchLocation) and replaces
#     the expected "Persistent Storage Location" sentinel with the NOT-
#     comparison form the Java evaluator supports: "not:/tmp/scratch".
#
#     vc.vpxuser-length — source Assessment is "N/A" (→ manual_audit) but
#     the parameter is a single clean Get-AdvancedSetting key, so it is
#     evaluable as advanced_setting with expected "32".
#
#   vami_api reclassifications (build 41):
#     12 vCenter controls whose assessment uses the VAMI CIS REST API
#     (com.vmware.appliance.*). The parameter_kind becomes "vami_api" and
#     the read_recipe grammar is "vami:<path>:<field>" where <path> uses
#     forward slashes (matching the VAMI URL path fragment) and <field> is
#     the JSON key in the response body. The Java VamiApiClient dispatches
#     on this recipe at runtime; the kind is evaluable iff read_recipe is
#     non-empty (same contract as vim_property and esxcli).
#
# value: (parameter, parameter_kind, expected_override_or_None, read_recipe_or_None)
_CONTROL_OVERRIDE_BY_CONTROL_ID: Dict[str, tuple] = {
    # -----------------------------------------------------------------------
    # Build 39 — advanced_setting reclassifications
    # -----------------------------------------------------------------------

    # ESXi local audit-record scratch location. The source row has a
    # two-key parameter (with embedded newline) so the classifier promotes
    # it to manual_audit. We single out ScratchConfig.CurrentScratchLocation
    # and use the NOT-comparison sentinel "not:/tmp/scratch" so the Java
    # evaluator's notCompare() path fires. The second key
    # (Syslog.global.auditRecord.storageDirectory) is informational-only and
    # cannot be evaluated by a simple key/value lookup — it stays absent from
    # the canonical row (the NOTE is in the description). 8.0 slug.
    "esx.logs-audit-persistent": (
        "ScratchConfig.CurrentScratchLocation",
        "advanced_setting",
        "not:/tmp/scratch",
        None,
    ),
    # 9.0 slug for the same control.
    "esx.log-audit-persistent": (
        "ScratchConfig.CurrentScratchLocation",
        "advanced_setting",
        "not:/tmp/scratch",
        None,
    ),
    # vpxuser password length. Source Assessment is "N/A" (manual_audit) but
    # the parameter is a single clean advanced-setting key. Reclassify to
    # advanced_setting so the evaluator can compare the integer value.
    # 9.0 only (8.0 does not have this control).
    "vc.vpxuser-length": (
        "config.vpxd.hostPasswordLength",
        "advanced_setting",
        None,
        None,
    ),

    # -----------------------------------------------------------------------
    # Build 40 — vim_property list/device recipes
    # -----------------------------------------------------------------------

    # vds.network-restrict-port-mirroring — list_empty recipe: the Java
    # VsphereClient.readListEmpty() checks whether the vspanSession list on
    # the DVS config is empty (no port-mirror sessions configured). The
    # canonical parameter serves as the unique key; the recipe carries the
    # actual vim path. Both 8.0 and 9.0 produce the same control_id.
    "vds.network-restrict-port-mirroring": (
        "config.vspanSession.empty",
        "vim_property",
        "true",
        "list_empty:config.vspanSession",
    ),

    # vm.pci-passthrough — vm_hardware_device_absent recipe: checks whether
    # any device in config.hardware.device[] is an instance of
    # VirtualPCIPassthrough. Canonical expected "true" means no such device
    # is present. Both 8.0 and 9.0 produce this control_id.
    "vm.pci-passthrough": (
        "config.hardware.device.absent.VirtualPCIPassthrough",
        "vim_property",
        "true",
        "vm_hardware_device_absent:config.hardware.device.VirtualPCIPassthrough",
    ),

    # -----------------------------------------------------------------------
    # Build 39 — vim_property with string_list_join recipe
    # -----------------------------------------------------------------------

    # esx.timekeeping-sources — NTP server list. The Java reader joins the
    # List<String> from config.dateTimeInfo.ntpConfig.server on "," and
    # compares the result against the expected value. The SCG baseline is
    # site-specific ("Site-Specific or:"), which cannot be string-compared.
    # The hand-edited canonical replaces it with "(non-empty)" — a sentinel
    # the Java evaluator's nonEmptyCompare() path handles. 8.0 only;
    # 9.0 uses esx.time which is covered by the service_state map.
    "esx.timekeeping-sources": (
        "config.dateTimeInfo.ntpConfig.server",
        "vim_property",
        "(non-empty)",
        "string_list_join:config.dateTimeInfo.ntpConfig.server",
    ),

    # -----------------------------------------------------------------------
    # Build 41 — vami_api reclassifications (6 controls in 8.0, 6 in 9.0)
    # -----------------------------------------------------------------------

    # vc.vami-access-ssh (8.0) / vc.ssh (9.0)
    # VAMI GET /api/appliance/access/ssh -> {"enabled": bool}
    "vc.vami-access-ssh": (
        "vami.access.ssh.enabled",
        "vami_api",
        "false",
        "vami:access/ssh:enabled",
    ),
    "vc.ssh": (
        "vami.access.ssh.enabled",
        "vami_api",
        "false",
        "vami:access/ssh:enabled",
    ),

    # vc.vami-syslog (8.0) / vc.log-forwarding (9.0)
    # VAMI GET /api/appliance/logging/forwarding -> list of forwarders.
    # "(non-empty)" expected — VamiApiClient checks list is non-empty.
    "vc.vami-syslog": (
        "vami.logging.forwarding",
        "vami_api",
        "(non-empty)",
        "vami:logging/forwarding:(list)",
    ),
    "vc.log-forwarding": (
        "vami.logging.forwarding",
        "vami_api",
        "(non-empty)",
        "vami:logging/forwarding:(list)",
    ),

    # vc.vami-time (8.0) / vc.time (9.0)
    # VAMI GET /api/appliance/ntp -> list of NTP servers.
    # "(non-empty)" expected.
    "vc.vami-time": (
        "vami.ntp.servers",
        "vami_api",
        "(non-empty)",
        "vami:ntp:(list)",
    ),
    "vc.time": (
        "vami.ntp.servers",
        "vami_api",
        "(non-empty)",
        "vami:ntp:(list)",
    ),

    # vc.fips-enable (8.0 + 9.0)
    # VAMI GET /api/appliance/system/security/global-fips -> {"enabled": bool}
    "vc.fips-enable": (
        "vami.system.security.global-fips.enabled",
        "vami_api",
        "true",
        "vami:system/security/global-fips:enabled",
    ),

    # vc.tls-profile (8.0) / vc.tls-ciphers (9.0)
    # VAMI GET /api/appliance/tls/profiles/global -> {"profile": "NIST_2024"}
    "vc.tls-profile": (
        "vami.tls.profiles.global.profile",
        "vami_api",
        "NIST_2024",
        "vami:tls/profiles/global:profile",
    ),
    "vc.tls-ciphers": (
        "vami.tls.profiles.global.profile",
        "vami_api",
        "NIST_2024",
        "vami:tls/profiles/global:profile",
    ),

    # vc.vami-administration-password-expiration (8.0) / vc.vami-password-max-age (9.0)
    # VAMI GET /api/appliance/local-accounts/policy -> {"max_days": int}
    # SCG baseline: password expiration disabled (max_days = -1).
    "vc.vami-administration-password-expiration": (
        "vami.local-accounts.policy.max-days",
        "vami_api",
        "-1",
        "vami:local-accounts/policy:max_days",
    ),
    "vc.vami-password-max-age": (
        "vami.local-accounts.policy.max-days",
        "vami_api",
        "-1",
        "vami:local-accounts/policy:max_days",
    ),
}


def classify_control_override(control_id: str):
    """If ``control_id`` has a build-39/40/41 control override (advanced_setting
    or vami_api reclassification, or vim_property list/device recipe), return
    ``(parameter, parameter_kind, expected_override_or_None, read_recipe_or_None)``.
    Otherwise return ``None``.

    Applied AFTER all other reclassifiers (vim, esxcli, service_state,
    source_id_vim). The parameter_kind field in the tuple IS the final kind
    — the caller sets parameter_kind directly (unlike vim/esxcli which
    hard-code their kind inside their respective classifier functions).

    For vami_api controls, read_recipe is the vami:<path>:<field> recipe
    string; for advanced_setting controls read_recipe is None (no recipe
    needed — the evaluator looks up the key directly in the advanced-settings
    map). For vim_property list/device controls read_recipe carries the
    non-standard recipe style (list_empty, vm_hardware_device_absent,
    vlan_id_not) and build_read_recipe() is NOT called afterward.
    """
    return _CONTROL_OVERRIDE_BY_CONTROL_ID.get(control_id)


def classify_esxcli_reclass(control_id: str):
    """If ``control_id`` is an esxcli recipe reclassification (build 36
    esxcli sprint), return
    ``(parameter, read_recipe, expected_override_or_None, description_caveat_or_None)``.
    Otherwise return ``None``.

    The normalizer applies this in the same slot as
    ``classify_vim_reclass``: it overrides ``parameter``, forces
    ``parameter_kind=esxcli``, sets ``read_recipe``, and (when an
    override is given) replaces ``expected_value`` with the form the
    Java evaluator can compare. esxcli became an evaluable kind in
    build 36 (BenchmarkProfile.isEvaluableKind), evaluable iff
    read_recipe is non-empty — exactly like vim_property.
    """
    entry = _ESXCLI_RECLASS_BY_CONTROL_ID.get(control_id)
    if entry is None:
        return None
    parameter, read_recipe, expected_override, caveat = entry
    return (parameter, read_recipe, expected_override, caveat)


def classify_vim_reclass(control_id: str):
    """If ``control_id`` is an existing-style vim_property reclassification
    (build 35 coverage expansion), return
    ``(parameter, read_recipe, expected_override_or_None, description_caveat_or_None)``.
    Otherwise return ``None``.

    The normalizer applies this AFTER the security-policy and vSAN
    classifiers and BEFORE writing the row: it overrides ``parameter``,
    forces ``parameter_kind=vim_property``, sets ``read_recipe``, and (when
    an override is given) replaces ``expected_value`` with a form the Java
    evaluator can compare. The description caveat is appended in-place when
    present so the partial-coverage controls self-document.
    """
    entry = _VIM_RECLASS_BY_CONTROL_ID.get(control_id)
    if entry is None:
        return None
    parameter, style, vim_path, expected_override = entry
    read_recipe = f"{style}:{vim_path}"
    caveat = _VIM_RECLASS_DESCRIPTION_CAVEAT.get(control_id)
    return (parameter, read_recipe, expected_override, caveat)


def classify_vsan_cluster_param(source_id: str,
                                source_title: str) -> Optional[str]:
    """If the row is one of the vSAN cluster controls that the plain
    vim25 surface CAN reach, return the canonical
    {@code vsanConfig.<field>} parameter key. Otherwise return None.

    Detection is by source_id slug fragment — the SCG raw CSV doesn't
    carry PowerCLI commands for vSAN rows, so the cmdlet-pattern
    classifier classify_security_policy_param can't fire. The slug is
    the only reliable signal (the title text varies across SCG
    revisions).

    Only the two controls reachable via vim25's bare
    {@code VsanClusterConfigInfo.defaultConfig} are mapped here. The
    other 12 ClusterComputeResource controls remain manual_audit
    until the vSAN Management SDK jar lands on the classpath.
    """
    if not source_id:
        return None
    sid = source_id.lower()
    for slug, param in _VSAN_CLUSTER_PARAM_BY_SLUG.items():
        # Match the slug as a substring of the source_id. The source_id
        # format is vsan-9.managed-disk-claim etc.; substring matching
        # tolerates an optional version digit shift.
        if slug in sid:
            return param
    return None


# Phase 3 / Batch 3c — canonical column 13: read_recipe.
#
# read_recipe = "<style>:<vim_path>" carries the full vim25 read spec
# for a vim_property control, so a NEW vim_property control whose
# extraction *style* already exists becomes pure CSV data — no Java
# change. See CANONICAL_SCHEMA.md (column 13) and
# VSphereClient.readByRecipe for the consuming end.
#
# Closed style set (adding a style is the only thing that needs Java):
#   scalar           — direct scalar/String/Number/Boolean at the path
#   bool             — boolean via isX()/getX() at the trailing segment
#   bool_policy      — unwrap a BoolPolicy wrapper's .value
#   string_list_join — join a List<String> on ","
#
# This map translates the canonical logical `parameter` key (the key
# the evaluator looks up) to its read_recipe. It owns the vim-path
# knowledge for the BUNDLED profiles; a custom-profile author supplies
# read_recipe directly in their CSV. Keys not in the map get an empty
# read_recipe (the control loads as non-evaluable/informational).
#
# The paths reproduce EXACTLY what the bespoke readers walked, so the
# generic reader is byte-identical:
#   bespoke readSecurityPolicy: config.defaultPortConfig ->
#       getSecurityPolicy -> get<Field> (BoolPolicy) -> .value
#   bespoke getClusterVsanConfig: configurationEx -> getVsanConfigInfo
#       -> isEnabled/getEnabled, and -> getDefaultConfig ->
#       isAutoClaimStorage / isChecksumEnabled
_READ_RECIPE_BY_PARAMETER: Dict[str, str] = {
    # DVS / DVPG security policy — BoolPolicy wrappers under
    # config.defaultPortConfig.securityPolicy.
    "securityPolicy.allowPromiscuous":
        "bool_policy:config.defaultPortConfig.securityPolicy.allowPromiscuous",
    "securityPolicy.macChanges":
        "bool_policy:config.defaultPortConfig.securityPolicy.macChanges",
    "securityPolicy.forgedTransmits":
        "bool_policy:config.defaultPortConfig.securityPolicy.forgedTransmits",
    # vSAN cluster config — plain booleans under
    # configurationEx.vsanConfigInfo[.defaultConfig]. The trailing
    # segment maps to is<Field>()/get<Field>(); the bespoke reader used
    # the defaultConfig.checksumEnabled field for object-checksum, so
    # the canonical key vsanConfig.objectChecksumEnabled maps to the
    # checksumEnabled vim field.
    "vsanConfig.enabled":
        "bool:configurationEx.vsanConfigInfo.enabled",
    "vsanConfig.autoClaimStorage":
        "bool:configurationEx.vsanConfigInfo.defaultConfig.autoClaimStorage",
    "vsanConfig.objectChecksumEnabled":
        "bool:configurationEx.vsanConfigInfo.defaultConfig.checksumEnabled",
}


def build_read_recipe(parameter: str, parameter_kind: str) -> str:
    """Return the read_recipe for a control, or '' when none applies.

    Only vim_property controls carry a recipe. A vim_property control
    whose canonical parameter is not in the bundled map gets an empty
    recipe — it loads as non-evaluable (informational) rather than
    being silently skipped or guessed. Non-vim_property kinds always
    get an empty recipe (read_recipe is meaningless for them).
    """
    if parameter_kind != "vim_property":
        return ""
    if not parameter:
        return ""
    return _READ_RECIPE_BY_PARAMETER.get(parameter.strip(), "")


def clean_expected_value(text: str) -> str:
    """Collapse a multi-line SCG 'Baseline Suggested Value' to its
    first non-empty line.

    SCG occasionally embeds a clarifying prose continuation in the
    expected-value cell (e.g. ``allow:hd\\nonce the guest OS is
    installed`` for vm.efi-boot-types). The actual baseline IS the
    first line; the continuation is documentation that breaks the
    Java evaluator's equality compare. Take line one, strip, return.
    """
    if not text:
        return ""
    for line in text.replace("\r", "").split("\n"):
        s = line.strip()
        if s:
            return s
    return ""


_UNDEFINED_DEFAULTS_RE = re.compile(
    r"^\s*Undefined\s*\(\s*Defaults to\s+(.+?)\s*\)\s*$", re.IGNORECASE)


def rewrite_undefined_baseline(text: str) -> str:
    """``Undefined (Defaults to X)`` -> ``X or Undefined``; else unchanged.

    SCG 7.0 writes a baseline whose platform default is the hardened state
    as ``Undefined (Defaults to X)``; SCG 8.0 and later write the same
    meaning as ``X or Undefined``, the form the adapter's evaluator
    recognizes (an absent key is compliant, a present key is compared
    against X). Untranslated, an absent key would be skipped instead of
    passed and a hardened key would fail against the literal sentence.

    Matches the whole cell (``.`` does not cross a newline), so a
    multi-line cell is left for clean_expected_value exactly as before.
    Applied by normalize_scg_source to every row, so any SCG version
    that uses the phrasing gets it (#169).
    """
    m = _UNDEFINED_DEFAULTS_RE.match(text or "")
    if not m:
        return text
    return f"{m.group(1)} or Undefined"


# Characters after which a "#" starts a PowerShell comment: the start of a
# token. Whitespace is checked separately.
_PS_TOKEN_START = ";{(|"

# Constructs the comment tokenizer below does not model: block comments,
# here-strings, and the typographic quotes PowerShell accepts as string
# delimiters. A remediation holding one is collapsed the old way and logged.
_PS_UNMODELED = ("<#", "@\"", "@'", "\u201c", "\u201d", "\u201e",
                 "\u2018", "\u2019", "\u201a", "\u201b")

# Line ends and starts across which " ; " would break the statement
# (a block or call left open, a pipeline or list continued, a closing
# brace or paren, a block or clause that belongs to the line before):
# those lines are joined with a single space instead.
_PS_JOIN_OPEN_END = ("{", "(", "|", ",", "`")
_PS_JOIN_CLOSE_START = ("{", "}", ")")
_PS_JOIN_CLAUSE_RE = re.compile(r"(else|elseif|catch|finally)\b", re.I)
# A line that is only an attribute, e.g. "[CmdletBinding()]": it belongs to
# the param block or function on the next line.
_PS_ATTRIBUTE_LINE_RE = re.compile(r"\[[A-Za-z_][\w.]*(\(.*\))?\]")


class _UnmodeledPowerShell(Exception):
    """A remediation uses syntax the comment tokenizer does not model."""


def _split_ps_comment(
        line: str, quote: Optional[str]) -> Tuple[str, Optional[str],
                                                  Optional[str]]:
    """Split one remediation line into code and a PowerShell ``#`` comment.

    Returns ``(code, comment, quote)``: ``comment`` is the text after the
    ``#`` (``None`` when the line has no comment) and ``quote`` the string
    state at the end of the line, passed back in for the next line
    because PowerShell strings may span lines.

    A ``#`` starts a comment when it is outside a string and starts a
    token: first on the line, or after whitespace or one of ``; { ( |``.
    So ``"<New VLAN#>"`` and ``...html#/doc`` are kept. A ``#`` directly
    followed by a digit with code before it on the line is prose ("item
    #3"), not a comment. ``#requires`` is treated as a comment like any
    other ``#`` line; it means nothing in a pasted one-liner. A backtick
    escapes the next character inside double quotes; a doubled quote
    inside a string reads as close-then-reopen, which leaves the state
    right.

    A ``$(`` subexpression inside a double-quoted string can hold its own
    strings (``"a $("b # c") d"``), which a flat quote state misreads, so
    it raises ``_UnmodeledPowerShell`` and the caller leaves the text alone.
    """
    i, n = 0, len(line)
    while i < n:
        ch = line[i]
        if quote is None:
            if ch in ("'", '"'):
                quote = ch
            elif ch == "#" and (i == 0 or line[i - 1].isspace()
                                or line[i - 1] in _PS_TOKEN_START):
                before = line[:i]
                if not (i + 1 < n and line[i + 1].isdigit()
                        and before.strip()):
                    return before.rstrip(), line[i + 1:], None
        elif quote == '"' and ch == "`":
            i += 1
        elif quote == '"' and ch == "$" and line[i + 1:i + 2] == "(":
            raise _UnmodeledPowerShell()
        elif ch == quote:
            quote = None
        i += 1
    return line, None, quote


def _ps_block_comment(texts: List[str]) -> str:
    """Render comment texts as one inline ``<# ... #>`` block comment.

    A ``#>`` inside the text would close the block early, so it is
    written ``# >``.
    """
    body = " ".join(t.strip().lstrip("#").strip() for t in texts)
    body = re.sub(r"\s+", " ", body).strip().replace("#>", "# >")
    return f"<# {body} #>" if body else ""


def _join_ps_lines(lines: List[Tuple[str, str, str]]) -> str:
    """Join ``(lead comment, code, trailing comment)`` lines into one.

    Lines are joined with `` ; ``, or with a space where ``;`` would break
    the statement: after code ending in ``{ ( | ,`` or a backtick (the
    backtick, a line continuation, is dropped), after a line that is only
    an attribute (``[CmdletBinding()]``), and before code starting
    with ``{ } )`` or ``else``/``elseif``/``catch``/``finally``. The
    decision reads the code only, never the block comments around it.
    """
    out, prev = "", ""
    for lead, code, tail in lines:
        glue = " ; "
        if prev.endswith(_PS_JOIN_OPEN_END) or \
                _PS_ATTRIBUTE_LINE_RE.fullmatch(prev) or \
                code.startswith(_PS_JOIN_CLOSE_START) or \
                _PS_JOIN_CLAUSE_RE.match(code):
            glue = " "
        if prev.endswith("`") and out.endswith("`"):
            out = out[:-1].rstrip()
        piece = " ".join(p for p in (lead, code, tail) if p)
        out = piece if not out else out + glue + piece
        prev = code
    return out


def _collapse_remediation_legacy(text: str) -> str:
    """The pre-#254 collapse: every newline becomes `` ; ``."""
    s = text.replace("\r", " ").replace("\n", " ; ")
    return re.sub(r"\s+", " ", s).strip()


def collapse_remediation(text: str, control_id: str = "") -> str:
    """Collapse a multi-line PowerCLI remediation into a single line.

    Joining the lines with `` ; `` would let a PowerShell ``#`` comment
    swallow every statement after it: a leading comment line turns the
    whole recommendation into one comment, and a trailing ``# ...`` on a
    statement comments out the statements that follow (#254,
    vm.virtual-hardware). So each ``#`` comment is rewritten as an inline
    ``<# ... #>`` block comment, which keeps the vendor's guidance next to
    the code and still pastes and runs as one line: a run of comment
    lines goes in front of the code line that follows it, a trailing
    comment stays after its code, and comments after the last code line
    are appended to it. In a remediation that had a comment, blank lines
    are dropped too, so no empty `` ; `` segment is left behind (one with
    no comment keeps them, as before). Lines are joined by
    ``_join_ps_lines`` so an open block, call or pipeline is not cut by a
    ``;``.

    Left as the old `` ; `` join instead:
    - a remediation that is nothing but comments (a commented-out vendor
      example), since there is no code to run;
    - a remediation holding a construct the tokenizer does not model
      (``<#``, a here-string, typographic quotes, a ``$( )`` subexpression
      inside a double-quoted string); this is logged with ``control_id``.
    """
    if not text:
        return ""
    if any(tok in text for tok in _PS_UNMODELED):
        log(f"WARNING: {control_id or '<unknown control>'}: remediation "
            "holds a block comment, here-string or typographic quote; "
            "comments left as they are")
        return _collapse_remediation_legacy(text)
    try:
        return _collapse_remediation_modeled(text)
    except _UnmodeledPowerShell:
        log(f"WARNING: {control_id or '<unknown control>'}: remediation "
            "holds a $( ) subexpression inside a double-quoted string; "
            "comments left as they are")
        return _collapse_remediation_legacy(text)


def _collapse_remediation_modeled(text: str) -> str:
    """collapse_remediation for text the tokenizer models."""
    code_lines: List[Tuple[str, str, str]] = []
    pending: List[str] = []  # comment lines waiting for the next code line
    quote: Optional[str] = None
    had_comment = False
    for line in text.replace("\r", " ").split("\n"):
        code, comment, quote = _split_ps_comment(line, quote)
        had_comment = had_comment or comment is not None
        if not code.strip():
            if comment is not None:
                pending.append(comment)
            else:
                code_lines.append(("", "", ""))  # blank line
            continue
        lead = _ps_block_comment(pending)
        pending = []
        tail = _ps_block_comment([comment]) if comment is not None else ""
        code_lines.append((lead, code.strip(), tail))
    if had_comment:
        # A dropped comment must not leave an empty " ; " segment, so the
        # blank lines go too; text with no comment keeps them as before.
        code_lines = [c for c in code_lines if c[1]]
    if not any(c[1] for c in code_lines):
        return _collapse_remediation_legacy(text)
    if pending:
        lead, code, tail = code_lines[-1]
        tail = " ".join(p for p in (tail, _ps_block_comment(pending)) if p)
        code_lines[-1] = (lead, code, tail)
    return re.sub(r"\s+", " ", _join_ps_lines(code_lines)).strip()


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


# ---------------------------------------------------------------------------
# Shared SCG row pipeline (#169).
#
# Every SCG version runs the same classifier chain; only the source column
# names and the source_ref token differ. The per-version drivers
# (normalize_scg_v8.py, normalize_scg_v9.py, and the compliance repo's
# drivers built on them) pass those in and stay thin. Every scoring fix-up
# in the chain is keyed by control_id (or control_id plus source product),
# never by a versioned vendor ID, so one rule covers every SCG version.
# ---------------------------------------------------------------------------

# Logical column keys a driver maps to its source's header names.
SCG_COLUMN_KEYS = (
    "scg_id", "component", "priority", "title", "description", "parameter",
    "expected", "assessment", "remediation", "setting_location",
)


def normalize_scg_source(input_path: str, output_path: str, *,
                         columns: Dict[str, str],
                         required_columns: List[str],
                         source_token: str,
                         label: str,
                         classify_kind=None) -> int:
    """Normalize one SCG source CSV to the canonical schema.

    columns:          logical key (SCG_COLUMN_KEYS) -> source header name.
    required_columns: header names that must be present.
    source_token:     source_ref prefix, e.g. "SCG-8.0".
    label:            log prefix, e.g. "normalize_scg_v8".
    classify_kind:    parameter_kind classifier; defaults to
                      classify_parameter_kind (a driver may wrap it).

    Returns 0 on success, 2 on a bad input header.
    """
    if classify_kind is None:
        classify_kind = classify_parameter_kind
    absent = [k for k in SCG_COLUMN_KEYS if k not in columns]
    if absent:
        raise ValueError(f"{label}: columns map lacks {absent}")
    col = columns
    with open(input_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            log(f"ERROR: {input_path} has no header row")
            return 2
        missing = [c for c in required_columns if c not in reader.fieldnames]
        if missing:
            shown = [m.replace("\n", "\\n") for m in missing]
            log(f"ERROR: {input_path} missing required columns: {shown}")
            return 2

        in_count = 0
        skipped: Dict[str, int] = {}
        by_kind: Dict[str, int] = {}
        unmapped_components: Dict[str, int] = {}
        out_rows = []

        def _bump(counter: Dict[str, int], key: str) -> None:
            counter[key] = counter.get(key, 0) + 1

        for src in reader:
            in_count += 1
            source_id = (src.get(col["scg_id"]) or "").strip()
            if not source_id:
                _bump(skipped, "empty_scg_id")
                continue

            component = (src.get(col["component"]) or "").strip()
            mapped = map_component(component)
            if mapped is None:
                _bump(unmapped_components, component)
                _bump(skipped, "unmapped_component")
                continue
            fallback_resource_kind, fallback_prefix = mapped

            control_id = build_control_id(fallback_prefix, source_id)
            if not control_id or "." not in control_id:
                _bump(skipped, "empty_slug")
                continue
            resource_kind = derive_resource_kind(
                source_id, fallback_resource_kind)

            # Setting Location refinement: when the source-ID prefix
            # didn't disambiguate to a sub-product (resource_kind ==
            # Component fallback), let the Setting Location column narrow
            # the resource_kind further. This catches network / port-group
            # / virtual-switch controls that the Component column mis-tags
            # as ESX. The control_id prefix is forced to match the new
            # resource_kind (the schema says they must agree).
            setting_location = (src.get(col["setting_location"]) or "").strip()
            sl_override = map_setting_location(setting_location)
            if sl_override and resource_kind == fallback_resource_kind:
                resource_kind, sl_prefix = sl_override
                _, slug = control_id.split(".", 1)
                control_id = f"{sl_prefix}.{slug}"

            parameter = (src.get(col["parameter"]) or "").strip()
            if parameter == "N/A":
                parameter = ""

            assessment = (src.get(col["assessment"]) or "").strip()
            parameter_kind = classify_kind(parameter, assessment)

            # DVS + DVPG security policy override (Phase 3 / Batch 3b).
            title = (src.get(col["title"]) or "").strip()
            if resource_kind in (
                "DistributedVirtualSwitch",
                "DistributedVirtualPortgroup",
            ):
                secpol = classify_security_policy_param(
                    assessment, source_id, title)
                if secpol is not None:
                    parameter = secpol
                    parameter_kind = "vim_property"

            # vSAN cluster-config override (Phase 3).
            vsan_expected_override = None
            if resource_kind == "ClusterComputeResource":
                vsan_param = classify_vsan_cluster_param(source_id, title)
                if vsan_param is not None:
                    parameter = vsan_param
                    parameter_kind = "vim_property"
                    vsan_expected_override = (
                        classify_vsan_cluster_expected(source_id))

            # control_id-keyed reclassifiers, in order; a later one wins:
            # build 35 vim_property, build 36/37 esxcli, build 38
            # service_state, build 40 control_id + source product, and
            # the build 39/40/41 generic override last.
            reclass_recipe = ""
            reclass_expected = None
            reclass_caveat = None
            reclass = classify_vim_reclass(control_id)
            if reclass is not None:
                parameter, reclass_recipe, reclass_expected, reclass_caveat = reclass
                parameter_kind = "vim_property"

            esxcli_reclass = classify_esxcli_reclass(control_id)
            if esxcli_reclass is not None:
                parameter, reclass_recipe, reclass_expected, reclass_caveat = esxcli_reclass
                parameter_kind = "esxcli"

            svc_reclass = classify_service_state_reclass(control_id)
            if svc_reclass is not None:
                parameter, reclass_recipe, reclass_expected = svc_reclass
                parameter_kind = "vim_property"
                reclass_caveat = None

            scoped_reclass = classify_scoped_vim_reclass(control_id, source_id)
            if scoped_reclass is not None:
                parameter, reclass_recipe, reclass_expected, reclass_caveat = scoped_reclass
                parameter_kind = "vim_property"

            ctrl_override = classify_control_override(control_id)
            if ctrl_override is not None:
                parameter, parameter_kind, reclass_expected, co_recipe = ctrl_override
                reclass_recipe = co_recipe or ""
                reclass_caveat = None

            _bump(by_kind, parameter_kind)

            # Baseline: version phrasing normalized first, then a
            # multi-line cell collapsed to its first non-empty line, then
            # the classifier overrides.
            expected = clean_expected_value(rewrite_undefined_baseline(
                src.get(col["expected"]) or ""))
            if vsan_expected_override is not None:
                expected = vsan_expected_override
            if reclass_expected is not None:
                expected = reclass_expected
            expected = rewrite_expected(control_id, expected)
            value_type = infer_value_type(expected)

            priority_raw = src.get(col["priority"]) or ""
            priority = clean_priority(priority_raw)
            if not priority_raw.strip():
                log(f"WARN: missing priority for {source_id}, defaulting to P2")

            description = (src.get(col["description"]) or "").strip()
            if reclass_caveat:
                description = description + reclass_caveat
            remediation = collapse_remediation(
                src.get(col["remediation"]) or "", control_id)

            out_rows.append({
                "control_id": control_id,
                "priority": priority,
                "resource_kind": resource_kind,
                "adapter_kind": ADAPTER_KIND,
                "parameter": parameter,
                "parameter_kind": parameter_kind,
                "value_type": value_type,
                "expected_value": expected,
                "title": title,
                "description": description,
                "source_ref": f"{source_token}:{source_id}",
                "remediation_text": remediation,
                "read_recipe": (
                    reclass_recipe
                    if reclass_recipe
                    else build_read_recipe(parameter, parameter_kind)
                ),
            })

    written = write_canonical(output_path, out_rows)

    log(f"[{label}] in={in_count}  out={written}  "
        f"skipped={sum(skipped.values())}")
    for k, v in sorted(skipped.items()):
        log(f"  skipped {k}: {v}")
    if unmapped_components:
        log("  unmapped Component values (skipped):")
        for k, v in sorted(unmapped_components.items()):
            log(f"    {v:5d}  {k!r}")
    log("  by parameter_kind:")
    for k, v in sorted(by_kind.items()):
        log(f"    {v:5d}  {k}")
    return 0
