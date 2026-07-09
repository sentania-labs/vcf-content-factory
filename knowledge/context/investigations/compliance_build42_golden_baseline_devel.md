# Compliance Adapter Build 42 — Golden Baseline (devel, pre-upgrade)

**Captured:** 2026-06-09  
**Instance:** vcf-lab-operations-devel.int.sentania.net (VCF Ops 9.0.2)  
**Purpose:** Acceptance bar for build 43 upgrade. Post-upgrade comparison agent must diff against this file.  
**Ordering convention:** all sections sorted alphabetically by resource name, then by metric/property key.  
**Encoding:** metric values are raw floats (1.0=compliant, 0.0=non-compliant). Property values are strings as returned by the API.  
**Timestamps:** UTC ISO-8601, converted from epoch-ms.  
**Secrets check:** no secrets present — compliance scores/settings only.  

---

## 1. Adapter Instance Health

Two vcfcf_compliance adapter instances are installed. Both are healthy.

| Field | vcf-lab-vcenter-mgmt | vcf-lab-vcenter-wld01 |
|---|---|---|
| adapter_instance_id | 4c697209-b967-4315-9c53-965420337f71 | 95e1b719-944b-4dda-88ed-6038bc6429be |
| adapter_kind_key | vcfcf_compliance | vcfcf_compliance |
| benchmark_profile | VMware_SCG_9.0 | VMware_SCG_9.0 |
| vcenter_host | vcf-lab-vcenter-mgmt.int.sentania.net | vcf-lab-vcenter-wld01.int.sentania.net |
| monitoringInterval_minutes | 60 | 60 |
| numberOfMetricsCollected | 10 | 10 |
| numberOfResourcesCollected | 2 | 2 |
| lastCollected | 2026-06-10T03:15:14Z | 2026-06-10T03:15:29Z |
| lastHeartbeat | 2026-06-10T03:40:46Z | 2026-06-10T03:40:46Z |
| messageFromAdapterInstance | (empty) | (empty) |
| credentialInstanceId | 72b5e143-30da-475b-afd2-3e626d215cd5 | 5ea24778-27d0-406f-8013-b125e7404bcb |
| collectorId | 1 | 1 |
| resourceStatus | DATA_RECEIVING | DATA_RECEIVING |
| resourceState | STARTED | STARTED |
| resourceHealth | GREEN | GREEN |

**Collection cadence:** 60 minutes. Post-upgrade comparison should wait at least 65 minutes after build 43 starts collecting before diffing metric values.

---

## 2. Adapter Own Resource Tree (adapterKindKey=vcfcf_compliance)

3 resources total: 1 ComplianceWorld singleton + 2 adapter instance resources.

### 2.1 Compliance World (ComplianceWorld)

```
resource_id=2a29e4c2-d551-4c8d-a02d-c262c238e09b
adapterKindKey=vcfcf_compliance
resourceKindKey=ComplianceWorld
name=Compliance World
identifier: world_id=compliance_world
resourceHealth=GREEN
resourceHealthValue=100.0
creationTime=2026-05-29T21:50:04Z
feeds_from_adapters=4c697209-b967-4315-9c53-965420337f71, 95e1b719-944b-4dda-88ed-6038bc6429be
```

**Properties (all):**
```
Summary|last_scan_timestamp=2026-06-03T09:43:53.865407817Z
Summary|profile_name=VMware_SCG_9.0
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=GENERAL
```

**Statkeys declared (24 total):** Summary|avg_host_score, Summary|avg_vcenter_score, Summary|avg_vm_score, Summary|hosts_below_threshold, Summary|total_hosts, Summary|total_unreadable_controls, Summary|total_vcenters, Summary|total_vms, Summary|vcenters_below_threshold, Summary|vms_below_threshold, System Attributes|alert_count_critical, System Attributes|alert_count_immediate, System Attributes|alert_count_info, System Attributes|alert_count_warning, System Attributes|all_metrics, System Attributes|availability, System Attributes|health, System Attributes|self_alert_count, System Attributes|total_alarms, System Attributes|total_alert_count, badge|compliance, badge|efficiency, badge|health, badge|risk

**Note:** No stat values returned by latest stats API. Build 42 (v1 code) does not appear to push data-point values onto ComplianceWorld object — statkeys are declared but no data is present. This is expected for v1. Build 43 (v2) SHOULD populate Summary|avg_host_score etc.

### 2.2 vcf-lab-vcenter-mgmt (vcfcf_compliance)

```
resource_id=4c697209-b967-4315-9c53-965420337f71
adapterKindKey=vcfcf_compliance
resourceKindKey=vcfcf_compliance
name=vcf-lab-vcenter-mgmt
creationTime=2026-05-29T21:49:19Z
identifier: allowInsecure=true, benchmark_profile=VMware_SCG_9.0, custom_profile_path=, vcenter_host=vcf-lab-vcenter-mgmt.int.sentania.net
resourceHealth=GREEN
resourceHealthValue=100.0
resourceStatus=DATA_RECEIVING
resourceState=STARTED
```

**Properties:**
```
System Properties|host_collector_id=1.0
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=ADAPTER_INSTANCE
```

**Statkeys:** Instance Attributes|collected_metrics, Instance Attributes|collected_properties, Instance Attributes|collected_resources, Instance Attributes|elapsed_collect_time, Instance Attributes|monitoring_resources, Instance Attributes|new_resources, Instance Attributes|no_data_receiving_resource_count, Instance Attributes|not_existing_resource_count, Instance Attributes|observations, Instance Attributes|property_value_changes, Instance Attributes|relationship_updates, Instance Attributes|reropted_events (note: 'reropted' is the API spelling)

**Note:** No stat values returned by latest stats API for adapter instance resources in build 42.

### 2.3 vcf-lab-vcenter-wld01 (vcfcf_compliance)

```
resource_id=95e1b719-944b-4dda-88ed-6038bc6429be
adapterKindKey=vcfcf_compliance
resourceKindKey=vcfcf_compliance
name=vcf-lab-vcenter-wld01
creationTime=2026-05-29T21:50:11Z
identifier: allowInsecure=true, benchmark_profile=VMware_SCG_9.0, custom_profile_path=, vcenter_host=vcf-lab-vcenter-wld01.int.sentania.net
resourceHealth=GREEN
resourceHealthValue=100.0
resourceStatus=DATA_RECEIVING
resourceState=STARTED
```

**Properties:**
```
System Properties|host_collector_id=1.0
System Properties|resource_kind_subtype=GENERAL
System Properties|resource_kind_type=ADAPTER_INSTANCE
```

**Statkeys:** Instance Attributes|collected_metrics, Instance Attributes|collected_properties, Instance Attributes|collected_resources, Instance Attributes|elapsed_collect_time, Instance Attributes|monitoring_resources, Instance Attributes|new_resources, Instance Attributes|no_data_receiving_resource_count, Instance Attributes|not_existing_resource_count, Instance Attributes|observations, Instance Attributes|property_value_changes, Instance Attributes|relationship_updates, Instance Attributes|reropted_events (note: 'reropted' is the API spelling)

**Note:** No stat values returned by latest stats API for adapter instance resources in build 42.

---

## 3. Stitched Properties on Foreign Resources (VMWARE/HostSystem)

The compliance adapter stitches properties and metrics onto 8 HostSystem resources via ARIA_OPS-style stitching.

| Host | resource_id | adapter | compliance_props | stat_values |
|---|---|---|---|---|
| vcf-lab-mgmt-esx01.int.sentania.net | 8bd31613-9ff6-4af7-b51f-ea421cc48955 | vcf-lab-vcenter-mgmt | 220 | 55 |
| vcf-lab-mgmt-esx02.int.sentania.net | b21b8d6e-3acd-4b5f-8480-323b361b5e96 | vcf-lab-vcenter-mgmt | 220 | 55 |
| vcf-lab-mgmt-esx03.int.sentania.net | 5fd4f7b2-52be-40f5-813b-dc971def6a55 | vcf-lab-vcenter-mgmt | 220 | 55 |
| vcf-lab-mgmt-esx04.int.sentania.net | dee43744-bf06-4561-87cc-3db1d5e53d0e | vcf-lab-vcenter-mgmt | 220 | 55 |
| vcf-lab-wld01-esx01.int.sentania.net | 1d6dae4e-e4d4-4b52-97e2-b6e13f9484b6 | vcf-lab-vcenter-wld01 | 148 | 55 |
| vcf-lab-wld01-esx02.int.sentania.net | 3f4ed775-6612-4237-86c7-867c1be8a2f1 | vcf-lab-vcenter-wld01 | 148 | 55 |
| vcf-lab-wld01-esx03.int.sentania.net | ba2c11d0-bfbd-4806-8e70-f76b029ae120 | vcf-lab-vcenter-wld01 | 136 | 51 |
| vcf-lab-wld01-esx04.int.sentania.net | db39b704-066f-453e-82a6-54741a53c684 | vcf-lab-vcenter-wld01 | 136 | 51 |

**Property namespace:** `VCF-CF Compliance|<profile>|<control_id>|<field>`
**Metric namespace:** `VCF-CF Compliance|<profile>|<control_id>|Compliant` (1.0=pass, 0.0=fail)
**Summary metrics:** `VCF-CF Compliance|score`, `|pass_count`, `|fail_count`, `|total_count`, `|unreadable_count`, `badge|compliance`

**Profiles present per host:**
- mgmt cluster hosts (esx01-04): VMware_SCG_8.0 + VMware_SCG_9.0 (220 props, 55 stat keys)
- wld01 cluster hosts (esx01-02): VMware_SCG_9.0 only (148 props, 55 stat keys)
- wld01 cluster hosts (esx03-04): VMware_SCG_9.0 only, subset (136 props, 51 stat keys — missing esx.etc-issue, esx.login-message, esx.network-dvfilter, esx.memory-tiering-encryption)

### 3.1 SCG 9.0 Control Properties — vcf-lab-mgmt-esx01 (canonical reference)

Full Actual/Expected/Description for all 49 SCG 9.0 controls on this host.
Other mgmt hosts have identical control values unless noted in Section 3.2.

- esx.account-lockout-duration|Actual=900
- esx.account-lockout-duration|Expected=900
- esx.account-lockout-max-attempts|Actual=5
- esx.account-lockout-max-attempts|Expected=5
- esx.account-password-history|Actual=5
- esx.account-password-history|Expected=5
- esx.ad-admin-group-autoadd|Actual=false
- esx.ad-admin-group-autoadd|Expected=FALSE
- esx.ad-admin-group-name|Actual=ESX Admins
- esx.ad-admin-group-name|Expected=Anything But "ESX Admins"
- esx.ad-admin-validate-interval|Actual=90
- esx.ad-admin-validate-interval|Expected=90
- esx.api-soap-timeout|Actual=30
- esx.api-soap-timeout|Expected=10
- esx.cpu-hyperthread-warning|Actual=0
- esx.cpu-hyperthread-warning|Expected=0
- esx.dcui-timeout|Actual=600
- esx.dcui-timeout|Expected=600
- esx.deactivate-mob|Actual=false
- esx.deactivate-mob|Expected=False
- esx.deactivate-shell|Actual=false
- esx.deactivate-shell|Expected=false
- esx.disable-accounts-dcui|Actual=true
- esx.disable-accounts-dcui|Expected=Disabled
- esx.etc-issue|Actual=
- esx.etc-issue|Expected=Consult your organization's legal advisors for text that is applicable to your environment. An example is: "Authorize...
- esx.firewall-incoming-default|Actual=true
- esx.firewall-incoming-default|Expected=true
- esx.hardware-virtual-nic|Actual=1
- esx.hardware-virtual-nic|Expected=0
- esx.key-persistence|Actual=false
- esx.key-persistence|Expected=false
- esx.lockdown-dcui-access|Actual=root
- esx.lockdown-dcui-access|Expected=root
- esx.lockdown-mode|Actual=LOCKDOWN_DISABLED
- esx.lockdown-mode|Expected=lockdownNormal
- esx.log-audit-forwarding|Actual=true
- esx.log-audit-forwarding|Expected=TRUE
- esx.log-audit-local|Actual=false
- esx.log-audit-local|Expected=TRUE
- esx.log-audit-local-capacity|Actual=4
- esx.log-audit-local-capacity|Expected=100
- esx.log-audit-persistent|Actual=/vmfs/volumes/698050de-ad34a87c-b76f-38052534dfcc
- esx.log-audit-persistent|Expected=not:/tmp/scratch
- esx.log-filter|Actual=false
- esx.log-filter|Expected=false
- esx.log-forwarding|Actual=tcp://vcf-lab-operations-logs.int.sentania.net:514?formatter=RFC_5424&amp;framing=octet_counting
- esx.log-forwarding|Expected=Site-Specific Log Server
- esx.log-forwarding-tls-ciphers|Actual=true
- esx.log-forwarding-tls-ciphers|Expected=TRUE
- esx.log-forwarding-tls-x509|Actual=false
- esx.log-forwarding-tls-x509|Expected=TRUE
- esx.log-level|Actual=info
- esx.log-level|Expected=info
- esx.log-level-global|Actual=info
- esx.log-level-global|Expected=error
- esx.log-persistent|Actual=true
- esx.log-persistent|Expected=true
- esx.login-message|Actual=
- esx.login-message|Expected=Consult your organization's legal advisors for text that is applicable to your environment. An example is: "Authorize...
- esx.memeagerzero|Actual=0
- esx.memeagerzero|Expected=1
- esx.memory-tiering-encryption|Actual=0
- esx.memory-tiering-encryption|Expected=1
- esx.network-bpdu|Actual=1
- esx.network-bpdu|Expected=1
- esx.network-dvfilter|Actual=
- esx.network-dvfilter|Expected=""
- esx.password-complexity|Actual=random=0 retry=3 min=disabled,disabled,disabled,7,7
- esx.password-complexity|Expected="random=0 similar=deny retry=3 min=disabled,disabled,disabled,disabled,15"
- esx.password-max-age|Actual=99999
- esx.password-max-age|Expected=99999
- esx.secureboot-enforcement|Actual=(unreadable)
- esx.secureboot-enforcement|Expected=true
- esx.session-timeout|Actual=900
- esx.session-timeout|Expected=900
- esx.shell-interactive-timeout|Actual=0
- esx.shell-interactive-timeout|Expected=900
- esx.shell-timeout|Actual=0
- esx.shell-timeout|Expected=600
- esx.shell-warning|Actual=0
- esx.shell-warning|Expected=0
- esx.snmp|Actual=false
- esx.snmp|Expected=false
- esx.ssh|Actual=false
- esx.ssh|Expected=false
- esx.time|Actual=true
- esx.time|Expected=true
- esx.tls-ciphers|Actual=COMPATIBLE
- esx.tls-ciphers|Expected=NIST_2024
- esx.tpm-configuration|Actual=(unreadable)
- esx.tpm-configuration|Expected=TPM
- esx.tpm-trusted-binaries|Actual=(unreadable)
- esx.tpm-trusted-binaries|Expected=true
- esx.transparent-page-sharing|Actual=0
- esx.transparent-page-sharing|Expected=2
- esx.vib-trusted-binaries|Actual=true
- esx.vib-trusted-binaries|Expected=TRUE

### 3.2 Per-Control Compliance Metric Values — All Hosts

Format: `key=value (1.0=compliant, 0.0=non-compliant)` @timestamp_UTC
badge|compliance=-1.0 means the OA compliance badge is not driven by this adapter (expected for v1).

#### vcf-lab-mgmt-esx01.int.sentania.net
resource_id=8bd31613-9ff6-4af7-b51f-ea421cc48955

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.etc-issue|Compliant=0.0 @2026-05-29T18:18:07Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.login-message|Compliant=0.0 @2026-05-29T18:18:07Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memory-tiering-encryption|Compliant=0.0 @2026-06-02T01:02:39Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-dvfilter|Compliant=1.0 @2026-05-29T18:18:07Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=0.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|fail_count=16.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|pass_count=26.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|score=61.904762268066406 @2026-06-10T03:15:05Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:05Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:05Z
- badge|compliance=-1.0 @2026-06-10T03:42:36Z

#### vcf-lab-mgmt-esx02.int.sentania.net
resource_id=b21b8d6e-3acd-4b5f-8480-323b361b5e96

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.etc-issue|Compliant=0.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.login-message|Compliant=0.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memory-tiering-encryption|Compliant=0.0 @2026-06-02T01:02:39Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-dvfilter|Compliant=1.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|fail_count=16.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|pass_count=26.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|score=61.904762268066406 @2026-06-10T03:15:04Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:04Z
- badge|compliance=-1.0 @2026-06-10T03:42:36Z

#### vcf-lab-mgmt-esx03.int.sentania.net
resource_id=5fd4f7b2-52be-40f5-813b-dc971def6a55

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.etc-issue|Compliant=0.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.login-message|Compliant=0.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memory-tiering-encryption|Compliant=0.0 @2026-06-01T22:57:52Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-dvfilter|Compliant=1.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=0.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|fail_count=16.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|pass_count=26.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|score=61.904762268066406 @2026-06-10T03:15:06Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:06Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:06Z
- badge|compliance=-1.0 @2026-06-10T03:42:36Z

#### vcf-lab-mgmt-esx04.int.sentania.net
resource_id=dee43744-bf06-4561-87cc-3db1d5e53d0e

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.etc-issue|Compliant=0.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.login-message|Compliant=0.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memory-tiering-encryption|Compliant=0.0 @2026-06-01T22:57:50Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-dvfilter|Compliant=1.0 @2026-05-29T18:18:08Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=0.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|fail_count=16.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|pass_count=26.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|score=61.904762268066406 @2026-06-10T03:15:04Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:04Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:04Z
- badge|compliance=-1.0 @2026-06-10T03:42:36Z

#### vcf-lab-wld01-esx01.int.sentania.net
resource_id=1d6dae4e-e4d4-4b52-97e2-b6e13f9484b6

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.etc-issue|Compliant=0.0 @2026-05-29T18:18:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.login-message|Compliant=0.0 @2026-05-29T18:18:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memory-tiering-encryption|Compliant=0.0 @2026-06-02T17:56:34Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-dvfilter|Compliant=1.0 @2026-05-29T18:18:06Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|fail_count=16.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|pass_count=26.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|score=61.904762268066406 @2026-06-10T03:15:11Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:11Z
- badge|compliance=-1.0 @2026-06-10T03:42:29Z

#### vcf-lab-wld01-esx02.int.sentania.net
resource_id=3f4ed775-6612-4237-86c7-867c1be8a2f1

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.etc-issue|Compliant=0.0 @2026-05-29T18:18:07Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.login-message|Compliant=0.0 @2026-05-29T18:18:07Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memory-tiering-encryption|Compliant=0.0 @2026-06-02T17:56:32Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-dvfilter|Compliant=1.0 @2026-05-29T18:18:07Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|fail_count=16.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|pass_count=26.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|score=61.904762268066406 @2026-06-10T03:15:09Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:09Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:09Z
- badge|compliance=-1.0 @2026-06-10T03:42:29Z

#### vcf-lab-wld01-esx03.int.sentania.net
resource_id=ba2c11d0-bfbd-4806-8e70-f76b029ae120

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|fail_count=16.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|pass_count=26.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|score=61.904762268066406 @2026-06-10T03:15:12Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:12Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:12Z
- badge|compliance=-1.0 @2026-06-10T03:42:29Z

#### vcf-lab-wld01-esx04.int.sentania.net
resource_id=db39b704-066f-453e-82a6-54741a53c684

- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-duration|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-lockout-max-attempts|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.account-password-history|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-autoadd|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-group-name|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ad-admin-validate-interval|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.api-soap-timeout|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.cpu-hyperthread-warning|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.dcui-timeout|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-mob|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.deactivate-shell|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.disable-accounts-dcui|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.firewall-incoming-default|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.hardware-virtual-nic|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.key-persistence|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-dcui-access|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.lockdown-mode|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-forwarding|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local-capacity|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-local|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-audit-persistent|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-filter|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-ciphers|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding-tls-x509|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-forwarding|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level-global|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-level|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.log-persistent|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.memeagerzero|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.network-bpdu|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-complexity|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.password-max-age|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.secureboot-enforcement|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.session-timeout|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-interactive-timeout|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-timeout|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.shell-warning|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.snmp|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.ssh|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.time|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tls-ciphers|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-configuration|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.tpm-trusted-binaries|Compliant=0.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.transparent-page-sharing|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|VMware_SCG_9.0|esx.vib-trusted-binaries|Compliant=1.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|fail_count=14.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|pass_count=28.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|score=66.66666412353516 @2026-06-10T03:15:11Z
- VCF-CF Compliance|total_count=42.0 @2026-06-10T03:15:11Z
- VCF-CF Compliance|unreadable_count=3.0 @2026-06-10T03:15:11Z
- badge|compliance=-1.0 @2026-06-10T03:42:29Z

---

## 4. Post-Upgrade Comparison Checklist

After build 43 installs and one full collection cycle completes (~65 min):

### 4.1 Adapter health (must match or improve)
- [ ] numberOfMetricsCollected >= 10 per adapter instance
- [ ] numberOfResourcesCollected >= 2 per adapter instance
- [ ] messageFromAdapterInstance empty (or non-error)
- [ ] lastCollected timestamp advances (later than baseline)
- [ ] resourceStatus=DATA_RECEIVING, resourceState=STARTED, resourceHealth=GREEN

### 4.2 Own resource tree (must preserve)
- [ ] ComplianceWorld resource still present (id=2a29e4c2-d551-4c8d-a02d-c262c238e09b)
- [ ] Both adapter instance resources still present
- [ ] ComplianceWorld Summary|last_scan_timestamp advances
- [ ] NEW v2: ComplianceWorld Summary|avg_host_score, |total_hosts, etc. should NOW have values

### 4.3 Stitched metric values (per-control Compliant — must match exactly or improve)
- [ ] Each HostSystem carries same 55 (or 51 for wld01-esx03/04) compliance stat keys
- [ ] score values match baseline OR improved if remediation occurred between build 42 and 43
- [ ] pass_count + fail_count + unreadable_count == total_count
- [ ] No new missing controls on hosts that had them before

### 4.4 Stitched property values (must match or advance)
- [ ] Each HostSystem carries VCF-CF Compliance|... properties
- [ ] mgmt hosts: both VMware_SCG_8.0 and VMware_SCG_9.0 profiles present
- [ ] wld01 hosts: VMware_SCG_9.0 profile present
- [ ] Actual values unchanged (or reflect current host state if host was reconfigured)

### 4.5 New v2 capabilities (expected additions, not regressions)
- [ ] ComplianceWorld statkeys have live data (avg_host_score, avg_vcenter_score, etc.)
- [ ] badge|compliance driven correctly (not -1.0) if v2 wires the badge

---

## 5. Raw Data Reference

All values above were captured by ops-recon via Suite API GET-only calls. No writes performed.
Capture timestamp: 2026-06-09T~18:30Z (collection cycle at ~17:15Z per lastCollected values).
Next expected collection: ~2026-06-09T18:15Z (60-minute interval).