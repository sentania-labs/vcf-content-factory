# VCF Compliance Adapter — Design Document

**Date**: 2026-05-27
**Status**: Design phase
**Type**: Tier 2 Java SDK Management Pack
**Adapter Kind**: VCFCFCompliance

---

## Initial prompt

User request (verbatim):

> I would like a MP to support the monitoring of VCF Infrastructure
> (MVP of hosts and VMs) for CIS compliance (or other standards given
> a benchmark definition). This will likely require querying vcenter
> for information from hosts not normally collected by Operations,
> some things like advanced settings, configurations, etc. Things of
> this nature are already captured by things like the Compliance "MPs".
> The addition/value I'd like this management pack to provide over the
> compliance packs is the robust alerting based on a dynamic hardening
> profile input, and an action set to correct hosts or VMs when they
> are found to drift from a provided standard.

Reference: https://github.com/vmware/vcf-security-and-compliance-guidelines/tree/main/security-configuration-hardening-guide

Follow-up decisions across multiple interview rounds.

---

## Vision

A self-contained Tier 2 management pack that monitors VCF
infrastructure (ESXi hosts and VMs) for compliance against
user-selectable security benchmarks (CIS, NIST, PCI, or custom).
The adapter owns all collection — no dependency on VMware's
compliance paks (which may be deprecated in a future release).
Phase 1 delivers monitoring; Phase 2 adds remediation actions.

**Key differentiators over existing compliance paks:**
- Dynamic hardening profiles (any CSV/XML benchmark definition)
- Self-contained collection (no compliance pak dependency)
- Aggregate alerting with auto-cancel on recovery
- Phase 2: remediation actions to correct drift

---

## Architecture

### Adapter model

- **Tier**: 2 (Java SDK, `ActionableAdapterInterface` in Phase 2)
- **Stitching**: ARIA_OPS onto existing VMWARE HostSystem and
  VirtualMachine resources
- **Dynamic metrics**: `isDynamicMetricsAllowed() = true` — property
  keys vary per active benchmark profile
- **Single instance, multi-vCenter**: one adapter instance connects
  to all vCenters in the VCF domain using shared SSO credentials
- **vCenter discovery**: auto-discover from VCF Ops VMWARE adapter
  instances, or manual hostname list

### Connection model

```
Adapter Instance Config:
  username:           administrator@vsphere.local
  password:           ********
  vcenter_discovery:  auto | manual
  vcenter_list:       (if manual) vcsa-01.lab.local, vcsa-02.lab.local
  benchmark_profile:  CIS_8.0 | CIS_9.0 | Custom
  custom_profile_path: /path/to/controls.csv (if Custom)
  collection_interval: 60 (minutes, default)
```

Single credential set works across all vCenters in VCF environments
(shared SSO domain). In auto mode, adapter queries VCF Ops at
discovery time for VMWARE adapter instances and extracts vCenter
hostnames.

### Resource model

No standalone resource kinds. All data stitched onto existing
VMWARE resources via ARIA_OPS:

- `VMWARE / HostSystem` — host compliance properties
- `VMWARE / VirtualMachine` — VM compliance properties

### Property naming convention

```
VCF-CF Compliance|<profile>|<scg-id>|Actual
VCF-CF Compliance|<profile>|<scg-id>|Expected
VCF-CF Compliance|<profile>|<scg-id>|Compliant     (0/1 metric)
VCF-CF Compliance|<profile>|<scg-id>|Description    (friendly name)
```

Examples:
```
VCF-CF Compliance|CIS|esxi-8.account-lockout|Actual      = "3"
VCF-CF Compliance|CIS|esxi-8.account-lockout|Expected    = "5"
VCF-CF Compliance|CIS|esxi-8.account-lockout|Compliant   = 0
VCF-CF Compliance|CIS|esxi-8.account-lockout|Description = "Lock account after failed login attempts"
```

SCG IDs (e.g., `esxi-8.account-lockout`, `vm-8.secure-boot`) are
used as property keys — human-readable AND machine-parseable,
mapping directly back to the benchmark CSV.

### Aggregate metrics (pre-declared, known at build time)

```
VCF-CF Compliance|score          (percentage, 0–100)
VCF-CF Compliance|pass_count     (integer)
VCF-CF Compliance|fail_count     (integer)
VCF-CF Compliance|total_count    (integer)
VCF-CF Compliance|profile_name   (string property)
```

These are static across all profiles and support dashboards/alerts
without knowing the specific control set.

---

## Benchmark ingestion

### Bundled profiles

The pak ships with embedded CIS 8.0 and CIS 9.0 profiles derived
from the VMware Security Configuration & Hardening Guide:

Source: https://github.com/vmware/vcf-security-and-compliance-guidelines/

CSV schema (27 columns):
- `SCG ID` — control identifier (e.g., `esxi-8.account-lockout`)
- `Component` — ESXi, vCenter, VM
- `Implementation Priority` — P0 (critical), P1 (important), P2 (recommended)
- `Configuration Parameter` — vSphere setting path
- `Installation Default Value` / `Baseline Suggested Value`
- `PowerCLI Command Assessment` / `PowerCLI Command Remediation Example`
- `DISA STIG Mapping`, `PCI DSS 4.0 Mapping`

### Custom profiles

User uploads a CSV/XML file to the VCF Ops cluster and provides
the path in the adapter instance configuration. Same column schema
as the bundled profiles. Follows the vCommunity MP pattern
(`windows_service_list.xml`).

---

## N/A control handling

Controls that don't apply to a resource (e.g., vSAN control on a
non-vSAN host) are **skipped silently**. No properties pushed, no
impact on compliance score. The score denominator only includes
applicable controls.

```
Host with vSAN:     53 controls, score = 48/53 = 90.6%
Host without vSAN:  47 controls, score = 45/47 = 95.7%
```

---

## Collection details

### ESXi host controls (via vSphere API)

| Category | API | Example controls |
|---|---|---|
| Advanced settings | `HostAdvancedOptionManager` | Account lockout, password policy, syslog, shell timeout, TPS salting, DCUI, MOB |
| Service states | `HostServiceSystem` | SSH, ESXi Shell, NTP, SNMP, SLP — running status + startup policy |
| Firewall rules | `HostFirewallSystem` | Default policy (allow/block), per-rule allowed hosts |
| Network security | `HostNetworkSystem` | Promiscuous mode, MAC changes, forged transmits per vSwitch |
| TLS/encryption | `HostSystem.config` | TLS disabled protocols, FIPS mode, TPM |
| Lockdown mode | `HostAccessManager` | Lockdown mode enabled, exception users |
| Image acceptance | `HostImageConfigManager` | VIB acceptance level |
| NTP config | `HostDateTimeSystem` | NTP server list |

### VM controls (via vSphere API)

| Category | API | Example controls |
|---|---|---|
| Advanced settings | `VirtualMachineConfigInfo.extraConfig` | Copy/paste isolation, drag-and-drop, disk shrink, HGFS, 3D graphics |
| Hardware config | `VirtualMachineConfigInfo.hardware` | Hardware version, unnecessary devices (USB, serial, parallel, floppy, CD-ROM) |
| Security features | `VirtualMachineConfigInfo` | Secure boot, vMotion encryption, FT encryption |
| Logging | `VirtualMachineConfigInfo` | Diagnostic logging enabled, log rotation |

### Collection interval

Default: **60 minutes**. Configurable per adapter instance. Compliance
settings rarely change more frequently than hourly. Keeps vCenter API
load low for large environments (100+ hosts).

---

## Alerting

### Model: aggregate alerts only

Per-control alerts are not feasible for dynamic profiles because VCF
Ops symptoms are static definitions referencing specific property keys.
Since the control set varies per benchmark profile, we cannot pre-author
symptoms for controls we don't know at build time.

### Shipped alert definitions

```
Symptom: VCF-CF Compliance Score Below 95%
  metric: VCF-CF Compliance|score
  condition: < 95
  severity: WARNING

Symptom: VCF-CF Compliance Score Below 80%
  metric: VCF-CF Compliance|score
  condition: < 80
  severity: CRITICAL

Alert: VCF-CF Host Compliance Drift Detected
  symptoms: [Score Below 95%]
  impact: Risk
  criticality: Warning
  auto-cancel: when score recovers above 95%
  recommendation: "Review failing controls in All Metrics tab.
    Navigate to the host → All Metrics → VCF-CF Compliance
    to identify non-compliant controls."

Alert: VCF-CF Host Compliance Critical
  symptoms: [Score Below 80%]
  impact: Risk
  criticality: Critical
  auto-cancel: when score recovers above 80%
  recommendation: "Multiple compliance controls are failing.
    Immediate review and remediation recommended."
```

Thresholds: **95% warning, 80% critical**. Users can adjust via
VCF Ops policy overrides.

The native `badge|compliance` metric automatically scores from
symptom violations, providing a second compliance signal through
the built-in VCF Ops compliance framework.

---

## Dashboards

### Compliance Overview

Aggregate dashboard for all profiles. Works with any benchmark.

```
[Compliance Heatmap — all hosts by score         w:12 h:5]
[Host Picker (ResourceList)  w:3] [Scoreboard: Score/Pass/Fail  w:9 h:2]
[Compliance Trend (MetricChart) w:6 h:4] [Failing Host Count (HealthChart) w:6 h:4]
```

Widgets use pre-declared aggregate metrics only (`score`,
`fail_count`, `pass_count`). No per-control column dependencies.

### Drift Timeline

Trend view showing compliance score over time per host.

```
[Host Picker w:3] [Score Trend Line (MetricChart) w:9 h:5]
[Alert Timeline (AlertList) w:12 h:4]
```

### Per-control detail

NOT a shipped dashboard. Users browse per-control properties via:
- Environment → select host → All Metrics → `VCF-CF Compliance|*`
- Or create custom views referencing specific controls they care about

This keeps dashboards maintenance-free across profile versions.

---

## Phasing

### Phase 1: Compliance Monitoring

- Tier 2 Java SDK adapter
- Single instance, multi-vCenter (shared SSO credentials)
- Auto-discover vCenters from VMWARE adapter instances
- Benchmark profile ingestion (bundled CIS 8.0/9.0 + custom CSV)
- ARIA_OPS stitching onto HostSystem / VirtualMachine
- Dynamic property push per active profile
- Aggregate metrics: score, pass/fail/total counts
- Aggregate alerts: 95% warning, 80% critical
- Dashboards: Compliance Overview, Drift Timeline
- Collection interval: 60 minutes default

### Phase 2: Remediation Actions

- Add `ActionableAdapterInterface` to Phase 1 adapter
- Action set per control category:
  - Set Advanced Setting (textfield key + textfield value)
  - Set Service Policy (combobox service + combobox policy)
  - Set Password Policy (textfield quality control string)
  - Set Syslog Target (textfield host:port)
  - Set NTP Config (textfield server list)
  - Enable/Disable SSH (checkcolumn toggle)
  - Remediate Control (pre-populated control ID, dispatches to correct API)
  - Remediate All Failures (checkcolumn confirm, bulk)
- Hidden action variants for recommendation-driven automation
- Recommendation linkage from alerts to remediation actions

---

## Dependencies and prerequisites

- VCF Operations 9.0+ (Tier 2 SDK support)
- vCenter 8.0+ (REST API + SOAP API access)
- Shared SSO credentials with read access to host/VM configuration
  (Phase 2: write access for remediation actions)
- No dependency on VMware compliance paks (self-contained collection)

## Resolved questions (2026-05-27 investigations)

1. **Actions on ARIA_OPS stitched resources** — RESOLVED.
   Cross-adapter actions ARE supported. Three installed adapters prove
   it: OrchestratorAdapter (33 actions on VMWARE HostSystem/VM/Cluster/
   Datastore), APPOSUCP (37 actions on VMWARE VirtualMachine),
   APPLICATIONDISCOVERY (1 action on VMWARE VirtualMachine). The
   `<ResourceContext adapterKind="VMWARE" resourceKind="HostSystem">`
   pattern works — no platform guard restricts it. Bonus: Phase 2 can
   also use Recommendation→Action linkage to trigger existing vRO
   workflows (17 examples in vSphere describe.xml) without declaring
   any actions in our adapter.

2. **Property key separators** — RESOLVED.
   `|` is safe for Tier 2 SDK property keys. The `|` / `:` restriction
   applies only to MPB Tier 1 metric labels. vCommunity MP pushes keys
   like `vCommunity|Guest OS|Services:{ServiceName}|Service Status` in
   production. Our `VCF-CF Compliance|CIS|esxi-8.account-lockout|Actual`
   convention is standard and correct.

3. **isDynamicMetricsAllowed()** — RESOLVED.
   Framework is ready. `addProperty()` constructs `MetricKey` with
   `isProperty=true`. `getAutoDiscoveryEnabled()` returns `true`. Just
   need a one-line `isDynamicMetricsAllowed()` override returning `true`
   in the adapter class.

4. **vCenter REST vs SOAP coverage** — APPROACH DECIDED.
   No vSphere SDK JARs on the shared appliance classpath; per-pak
   classloader isolation prevents borrowing from the VMWARE adapter.
   Strategy: start REST-only using `ManagedHttpClient` (Synology
   pattern), bundle `vapi-runtime` + `vim-stubs` in `lib/` when REST
   coverage falls short. Host advanced settings likely require the
   vSphere SDK (SOAP layer), so expect to bundle eventually.

## Open questions

1. **Stitching identity key** — the MOID trap. `host_moid`
   (VMEntityObjectID) is not unique across vCenters. Must use FQDN
   hostname or vCenter UUID + MOID as the stitching join key. Needs
   concrete design before coding — silent data corruption if wrong.

2. **Event publishing** — can the Tier 2 adapter push VCF Ops events
   per failing control? Events are inherently dynamic and could
   supplement the aggregate alerting model. Currently a TOOLSET GAP
   for pak runtime event format.

3. **Profile hot-reload** — if the user updates the benchmark CSV,
   does the adapter pick up changes on the next collection cycle, or
   does it require an adapter instance restart?

4. **Scale testing** — with 100+ controls × 100+ hosts, the adapter
   pushes 10,000+ properties per collection cycle. Need to verify
   platform performance at this cardinality.

5. **Phase 2 action architecture** — three options identified:
   (A) Own Tier 2 actions via `ActionableAdapterInterface` — full
   custom remediation, highest effort.
   (B) vRO workflow linkage via Recommendation→Action — zero action
   code, leverages existing OrchestratorAdapter, lowest effort.
   (C) Hybrid — vRO for common operations, own actions for
   compliance-specific remediation. Decision deferred to Phase 2
   design.

---

## Reference material

- Benchmark source: https://github.com/vmware/vcf-security-and-compliance-guidelines/
- SCG CSV schema: 27 columns per control (see design doc body)
- PowerCLI audit/remediation scripts: reference implementation for
  collection and remediation logic
- Action wire format: `context/investigations/action_wire_format_deep_dive.md`
- Dynamic metrics SDK: `context/cleanroom-spec/spec/01-adapter-lifecycle.md` line 176
- vCommunity service monitoring pattern: `references/vmbro_vcf_operations_vcommunity/`
- Existing compliance pak analysis: ops-recon 2026-05-27 (53 properties
  on prod, 15 on devel; gap caused by CIS/PCI paks on prod only)
