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
    "vds.network-restrict-discovery-protocol": (
        "config.linkDiscoveryProtocolConfig.operation",
        "scalar",
        "config.linkDiscoveryProtocolConfig.operation",
        None,     # SCG expected "none" compares directly to the enum string
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
    # PARTIAL: scalar config.version returns "vmx-NN". The evaluator does
    # exact string equality, so this scores compliant ONLY when the VM is
    # at exactly the SCG baseline version string ("vmx-19"), not "19 or
    # newer". Recorded as exact-match coverage in UNAUDITED_CONTROLS.md.
    "vm.virtual-hardware": (
        "config.version",
        "scalar",
        "config.version",
        None,     # compares to SCG baseline ("vmx-19" / "vmx-21") verbatim
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
    "vm.virtual-hardware": (
        " [PARTIAL COVERAGE: this adapter reads config.version (e.g. "
        "\"vmx-21\") and compares it for exact equality to the SCG "
        "baseline string. It does NOT evaluate \"version N or newer\"; a "
        "VM at a higher-than-baseline hardware version will read as "
        "non-compliant. See UNAUDITED_CONTROLS.md.]"
    ),
}


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
}


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
