# SCG 8.0 / 9.0 Audit Coverage Recon

**Date:** 2026-06-03  
**Analyst:** ops-recon  
**Instance:** devel (`vcf-lab-operations-devel.int.sentania.net`)  
**Ground truth:** VMware_SCG_9.0 active, 25 advanced_setting HostSystem controls confirmed evaluating against `vcf-lab-wld01-esx01`, `vcf-lab-wld01-esx02`, `vcf-lab-mgmt-esx03` (and 2 more hosts).

---

## Summary

| Profile | In-scope controls | advanced_setting (reclassify) | vim_property existing style | vim_property NEW style | other API | genuinely manual | uncertain |
|---|---|---|---|---|---|---|---|
| SCG 8.0 | 98 | 0 | 11 | 20 | 8 | 50 | 9 |
| SCG 9.0 | 164 | 0 | 12 | 26 | 8 | 103 | 15 |
| **Total** | **262** | **0** | **23** | **46** | **16** | **153** | **24** |

**Headline:** Of the 262 currently non-API controls, **39 are API-auditable with existing vim styles** (pure CSV change), **46 more** would be unlocked by building new vim styles (Java work), and **16** are reachable via other vCenter REST/SOAP APIs (Java work of a different kind). **153 are genuinely manual** — physical hardware, procedural, external systems, or in-guest state the vCenter SOAP surface cannot reach.

**Note on "pure CSV":** Every vim_property reclassification for HostSystem and VirtualMachine also requires a **one-time Java extension** to `collectHosts()` and `collectVms()` to call `readVimProperties()` in addition to `getAdvancedSettings()`. That extension is architectural (not per-control), so once done, all vim_property HostSystem and VM controls become pure-CSV thereafter. The 23 "existing style" calls assume that extension is in place. Without it, they are "uncertain (architecture gap)."

**Pure-CSV today (no Java at all):** DVS and DVPG vim_property controls can be added by CSV edit alone today — those collectors already call `readVimProperties()`. That covers 13 of the 39 existing-style controls.

---

## Architecture prerequisite: extend collectHosts() and collectVms()

`ComplianceAdapter.collectHosts()` currently calls only `vsphere.getAdvancedSettings(hostRef)`. It does **not** call `vsphere.readVimProperties(hostRef, controls)`. The same gap exists for `collectVms()`. Without this extension, any vim_property recipe for HostSystem or VirtualMachine loads in the CSV but never evaluates (non-evaluable, per schema rules). This is a one-time Java change that unlocks all HostSystem and VM vim_property reclassifications below.

---

## Reclassification tables

### SCG 8.0 — HostSystem (vim_property, existing styles, need collectHosts extension)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| esx.lockdown-mode | powercli_only | `scalar:config.lockdownMode` | HIGH — LockdownMode enum, compares to `lockdownNormal` |
| esx.firewall-incoming-default | powercli_only | `bool:config.firewall.defaultPolicy.incomingBlocked` | HIGH — direct bool property |
| esx.timekeeping-sources | powercli_only | `string_list_join:config.dateTimeInfo.ntpConfig.server` | HIGH — exact same style as existing ref |
| esx.secureboot-enforcement | esxcli | `bool:config.encryptionState.requireSecureBoot` | HIGH — HostEncryptionState, added vSphere 7.0U2 |
| esx.tpm-configuration | esxcli | `scalar:config.encryptionState.mode` | HIGH — HostEncryptionState.mode enum (None/TPM/TPMRequired) |

**5 controls — require collectHosts() vim_property extension + HostSystem vim_property reader.**

### SCG 8.0 — VirtualMachine (vim_property, existing styles, need collectVms extension)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| vm.secure-boot | powercli_only | `bool:config.bootOptions.efiSecureBootEnabled` | HIGH — VirtualMachineBootOptions.efiSecureBootEnabled |
| vm.vmotion-encrypted | powercli_only | `scalar:config.migrateEncryption` | HIGH — MigrateEncryptionMode enum (required/opportunistic/disabled) |
| vm.ft-encrypted | powercli_only | `scalar:config.ftEncryptionMode` | HIGH — FtEncryptionMode enum (required/opportunistic/disabled) |
| vm.log-enable | powercli_only | `bool:config.flags.enableLogging` | HIGH — VirtualMachineFlagInfo.enableLogging |

**4 controls — require collectVms() vim_property extension.**

### SCG 8.0 — DistributedVirtualPortgroup (vim_property, existing styles — pure CSV today)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| dvpg.network-mac-learning | powercli_only | `bool:config.defaultPortConfig.macManagementPolicy.macLearningPolicy.enabled` | HIGH — direct bool at end of path |
| dvpg.network-restrict-port-level-overrides | powercli_only | `bool:config.policy.securityPolicyOverrideAllowed` (expected: false) | MEDIUM — this covers the security policy override flag; full control also checks 6 other flags (partial coverage) |

**2 controls — pure CSV (DVS/DVPG collector already calls readVimProperties).**

Note: `dvpg.network-restrict-port-level-overrides` covers partial intent with a single flag. Full fidelity would need either multiple recipe columns (architecture not supported today) or a new style.

### SCG 8.0 — DistributedVirtualSwitch (vim_property, existing styles — pure CSV today)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| vds.network-reset-port | powercli_only | `bool:config.policy.portConfigResetAtDisconnect` | HIGH — direct bool |
| vds.network-restrict-discovery-protocol | powercli_only | `scalar:config.linkDiscoveryProtocolConfig.operation` | HIGH — string enum (none/listen/advertise/both) |
| vds.network-restrict-netflow-usage | powercli_only | `bool_policy:config.defaultPortConfig.ipfixEnabled` | HIGH — BoolPolicy wrapper, same style as existing security policy recipes |

**3 controls — pure CSV.**

---

### SCG 9.0 — HostSystem (vim_property, existing styles, need collectHosts extension)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| esx.lockdown-mode | powercli_only | `scalar:config.lockdownMode` | HIGH |
| esx.firewall-incoming-default | powercli_only | `bool:config.firewall.defaultPolicy.incomingBlocked` | HIGH |
| esx.time (NTP sources) | powercli_only | `string_list_join:config.dateTimeInfo.ntpConfig.server` | HIGH |
| esx.secureboot-enforcement | esxcli | `bool:config.encryptionState.requireSecureBoot` | HIGH |
| esx.tpm-configuration | esxcli | `scalar:config.encryptionState.mode` | HIGH |
| esx.tpm-trusted-binaries | esxcli | `bool:config.encryptionState.requireExecuteInstalledOnly` | HIGH — new in vSphere 8 TPM enforcement |

**6 controls — require collectHosts() vim_property extension.**

### SCG 9.0 — VirtualMachine (vim_property, existing styles, need collectVms extension)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| vm.secure-boot | manual_audit | `bool:config.bootOptions.efiSecureBootEnabled` | HIGH |
| vm.vmotion-encrypted | powercli_only | `scalar:config.migrateEncryption` | HIGH |
| vm.ft-encrypted | powercli_only | `scalar:config.ftEncryptionMode` | HIGH |
| vm.log-enable | powercli_only | `bool:config.flags.enableLogging` | HIGH |
| vm.virtual-hardware | manual_audit | `scalar:config.version` | HIGH — returns "vmx-21" style string |

**5 controls — require collectVms() vim_property extension.**

### SCG 9.0 — DistributedVirtualPortgroup (vim_property, existing styles — pure CSV today)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| dvpg.network-mac-learning | powercli_only | `bool:config.defaultPortConfig.macManagementPolicy.macLearningPolicy.enabled` | HIGH |
| dvpg.network-restrict-port-level-overrides | powercli_only | `bool:config.policy.securityPolicyOverrideAllowed` (expected: false) | MEDIUM — partial coverage |

**2 controls — pure CSV.**

### SCG 9.0 — DistributedVirtualSwitch (vim_property, existing styles — pure CSV today)

| control_id | current kind | proposed recipe | confidence |
|---|---|---|---|
| vds.network-reset-port | powercli_only | `bool:config.policy.portConfigResetAtDisconnect` | HIGH |
| vds.network-restrict-discovery-protocol | powercli_only | `scalar:config.linkDiscoveryProtocolConfig.operation` | HIGH |
| vds.network-restrict-netflow-usage | powercli_only | `bool_policy:config.defaultPortConfig.ipfixEnabled` | HIGH |
| vds.network-nioc | manual_audit | `bool:config.networkResourceManagementEnabled` | HIGH — VmwareDVSConfigInfo.networkResourceManagementEnabled |

**4 controls — pure CSV.**

---

## New vim styles worth building

### Style A: `service_state` — HostService list filter (MEDIUM Java cost)

**What it does:** Retrieves `config.service.serviceInfo` (a `HostServiceInfo` containing a `List<HostService>`), filters by a service key, and returns both `running` (bool) and `policy` (string) for comparison.

**Grammar:** `service_state:<service_key>:<field>` where `<field>` is `running` or `policy`.

**Controls unlocked (16 total across both profiles):**

| control_id | profile | service key | field | expected |
|---|---|---|---|---|
| esx.deactivate-shell | 8.0 | TSM | running | false |
| esx.deactivate-ssh | 8.0 | TSM-SSH | running | false |
| esx.deactivate-cim | 8.0 | sfcbd-watchdog | running | false |
| esx.deactivate-slp | 8.0 | slpd | running | false |
| esx.deactivate-snmp | 8.0 | snmpd | running | false |
| esx.timekeeping-services | 8.0 | ntpd | running | true |
| esx.deactivate-shell | 9.0 | TSM | running | false |
| esx.ssh | 9.0 | TSM-SSH | running | false |
| esx.snmp | 9.0 | snmpd | running | false |
| esx.time (service) | 9.0 | ntpd | running | true |

Note: `esx.timekeeping-services` (8.0) also checks policy=on; `esx.time` (9.0) bundles NTP service + NTP sources into one control. Two recipes are needed per control (running + policy), which would require multi-recipe support or splitting. This is an additional design consideration.

Also requires `collectHosts()` vim_property extension.

### Style B: `vm_hardware_device_absent` — device-type presence check (MEDIUM Java cost)

**What it does:** Retrieves `config.hardware.device[]`, filters by a Java type or device label, and returns true if the filtered list is empty (device type absent).

**Controls unlocked (4 total):**

| control_id | profile | device filter | expected |
|---|---|---|---|
| vm.pci-passthrough | 8.0, 9.0 | VirtualPCIPassthrough | absent (empty) |
| vm.persistent-disk | 9.0 | VirtualDisk.backing.diskMode=independentNonpersistent | absent (empty) |

Note: `vm.remove-unnecessary-devices` remains manual because "unnecessary" is environment-specific and not decidable from device type alone.

Also requires `collectVms()` vim_property extension.

### Style C: `list_empty` — generic list-is-empty check (LOW Java cost)

**What it does:** Retrieves a list property and returns true if the list has zero elements.

**Controls unlocked (2 total):**

| control_id | profile | vim path | note |
|---|---|---|---|
| vds.network-restrict-port-mirroring | 8.0, 9.0 | `config.vspanSession` | VDS-level mirror sessions list |

Note: If the port mirroring config is stored at `config.mirrorPortConfigs` (older API) vs `config.vspanSession` (newer), path needs verification on the live instance. Flagged as MEDIUM confidence.

### Style D: `vlan_id_not` — VLAN ID type-aware check (MEDIUM Java cost)

**What it does:** Retrieves `config.defaultPortConfig.vlan`, checks if the runtime type is `VmwareDistributedVirtualSwitchVlanIdSpec` AND vlanId != 4095 (OR that it IS a TrunkSpec, implying 802.1Q mode). A plain `scalar:config.defaultPortConfig.vlan.vlanId` only works for simple VLAN type; VGT is indicated by the spec being a `TrunkVlanSpec` rather than by vlanId.

**Controls unlocked (2 total):**

| control_id | profile | note |
|---|---|---|
| dvpg.network-vgt | 8.0 | pure CSV once style exists |
| dvpg.network-vgt | 9.0 | pure CSV once style exists |

### Style E: `sso_lockout_policy` — vCenter SSO API (HIGH Java cost, different reader)

The SSO lockout/password policy controls (max-attempts, unlock-time, password-lifetime, password-reuse, password-policy) are readable via the vCenter SSO STS SOAP endpoint, not via vim25 PropertyCollector or the OptionManager. This is a distinct reader (different URL, different auth flow) that would need Java work to integrate. Grouped here as a cluster.

**Controls unlocked (SCG 8.0, 5 controls):**

| control_id | API endpoint | note |
|---|---|---|
| vc.administration-sso-lockout-policy-max-attempts | STS SOAP: AdminLockoutPolicy | MaxFailedAttempts |
| vc.administration-sso-lockout-policy-unlock-time | STS SOAP: AdminLockoutPolicy | AutoUnlockIntervalSec |
| vc.administration-sso-password-lifetime | STS SOAP: AdminPasswordPolicy | PasswordLifetimeDays |
| vc.administration-sso-password-reuse | STS SOAP: AdminPasswordPolicy | ProhibitedPreviousPasswordsCount |
| vc.administration-failed-login-interval | STS SOAP: AdminLockoutPolicy | FailedAttemptIntervalSec |

**Controls unlocked (SCG 9.0, 5 controls):**

| control_id | note |
|---|---|
| vc.account-lockout-duration | same STS endpoint |
| vc.account-lockout-max-attempts | same |
| vc.account-lockout-reset | same |
| vc.password-history | same |
| vc.password-max-age | same |

### Style F: `vami_api` — vCenter Appliance REST API reader (HIGH Java cost, different reader)

Several VAMI (vCenter Server Appliance Management) controls are readable via REST API at `/api/appliance/...`. This is a distinct HTTP reader using the vCenter REST API (not vim25 SOAP).

**Controls unlocked (SCG 8.0, ~6 controls):**

| control_id | REST path | note |
|---|---|---|
| vc.vami-access-ssh | GET /api/appliance/access/ssh | returns enabled bool |
| vc.vami-syslog | GET /api/appliance/logging/forwarding | returns configured targets |
| vc.vami-time | GET /api/appliance/ntp | returns NTP servers |
| vc.vami-administration-password-expiration | GET /api/appliance/local-accounts/policy | max_days |
| vc.fips-enable | GET /api/appliance/system/security/global-fips | enabled bool |
| vc.tls-profile | GET /api/appliance/tls/profiles/global | profile name (8.0.3+) |

**Controls unlocked (SCG 9.0, ~6 controls):**

| control_id | note |
|---|---|
| vc.ssh | /api/appliance/access/ssh |
| vc.log-forwarding | /api/appliance/logging/forwarding |
| vc.time | /api/appliance/ntp |
| vc.fips-enable | /api/appliance/system/security/global-fips |
| vc.tls-ciphers | /api/appliance/tls/profiles/global |
| vc.vami-password-max-age | /api/appliance/local-accounts/policy |

The vCenter adapter instance (`VCenterApiClient`) already calls the vCenter REST API for other purposes. A dedicated VAMI reader could be added there. Confidence: HIGH for endpoint availability, MEDIUM for exact response schema matching without live testing.

---

## The genuinely-manual residue

These controls have no vCenter/vim/advanced-setting/API representation. They require human review.

### SCG 8.0 — Genuinely Manual

| control_id | resource_kind | title | reason |
|---|---|---|---|
| esx.ad-auth-proxy | HostSystem | vSphere Authentication Proxy usage | Configuration decision requiring org-specific assessment; no machine-readable state |
| esx.iscsi-mutual-chap | HostSystem | iSCSI mutual CHAP | Requires per-HBA CHAP credential check; iSCSI HBA auth state is theoretically in vim25 but depends on storage adapter type and credential configuration being present |
| esx.lockdown-exception-users | HostSystem | Lockdown exception users list | HostAccessManager.retrieveLockdownExceptions() is a managed object call, not a PropertyCollector path; content is organization-specific |
| esx.secureboot | HostSystem | UEFI Secure Boot | Hardware firmware setting; not exposed via vim25 PropertyCollector (hardware-level, pre-ESXi) |
| esx.supported | HostSystem | ESXi not end-of-support | Requires comparing build/version against VMware support lifecycle calendar — no machine-readable API signals "unsupported" |
| esx.updates | HostSystem | All patches installed | Requires patch baseline comparison; not a vim25 property |
| esx.vmk-management | HostSystem | vmkernel management isolation | Environment-specific design assessment; requires knowing which vmk should have management enabled |
| esx.logs-audit-persistent | HostSystem | Persistent audit log location | Parameter notes that /tmp/scratch indicates non-persistent; ScratchConfig.CurrentScratchLocation IS an advanced setting but the compliance test requires interpreting the value against mount point semantics, not just equality — mixed; marked manual |
| esx.logs-persistent | HostSystem | Persistent log location | Same as above |
| esx.entropy | HostSystem | Entropy for crypto (disableHwrng) | Kernel boot parameter; no PropertyCollector path |
| esx.firewall-restrict-access | esxcli | Firewall per-ruleset allowed IPs | Per-ruleset IP allowlist is deeply nested in firewall object; checking "authorized networks only" is env-specific and requires organizational knowledge |
| esx.key-persistence | esxcli | Key persistence disabled | No vim25 property; esxcli only |
| esx.ssh-fips | esxcli | SSH FIPS mode | sshd_config parameter; no vim25 path |
| esx.ssh-fips-ciphers | esxcli | SSH FIPS cipher list | sshd_config parameter; no vim25 path |
| esx.ssh-gateway-ports | esxcli | SSH gatewayports=no | sshd_config parameter |
| esx.ssh-host-based-auth | esxcli | SSH host-based auth disabled | sshd_config parameter |
| esx.ssh-idle-timeout-count | esxcli | SSH clientalivecountmax | sshd_config parameter |
| esx.ssh-idle-timeout-interval | esxcli | SSH clientaliveinterval | sshd_config parameter |
| esx.ssh-login-banner | esxcli | SSH banner=/etc/issue | sshd_config parameter |
| esx.ssh-rhosts | esxcli | SSH ignorerhosts=yes | sshd_config parameter |
| esx.ssh-stream-local-forwarding | esxcli | SSH stream local forwarding | sshd_config parameter |
| esx.ssh-tcp-forwarding | esxcli | SSH tcp forwarding | sshd_config parameter |
| esx.ssh-tunnels | esxcli | SSH permittunnel=no | sshd_config parameter |
| esx.ssh-user-environment | esxcli | SSH permituserenvironment | sshd_config parameter |
| esx.account-dcui | esxcli | dcui shell access disabled | Per-account shell access flag; no vim25 property |
| esx.account-vpxuser | esxcli | vpxuser shell access disabled | Per-account shell access flag; no vim25 property |
| vm.tools-add-feature | VirtualMachine | VMware Tools allow-add-feature | tools.conf lives inside guest OS filesystem; not in vim25 extraConfig |
| vm.tools-allow-transforms | VirtualMachine | VMware Tools MSI transforms | tools.conf in guest |
| vm.tools-deactivate-appinfo | VirtualMachine | VMware Tools appinfo | tools.conf in guest |
| vm.tools-deactivate-containerinfo | VirtualMachine | VMware Tools containerinfo | tools.conf in guest |
| vm.tools-deactivate-guestoperations | VirtualMachine | VMware Tools guest operations | tools.conf in guest |
| vm.tools-deactivate-gueststoreupgrade | VirtualMachine | VMware Tools guest store | tools.conf in guest |
| vm.tools-deactivate-servicediscovery | VirtualMachine | VMware Tools service discovery | tools.conf in guest |
| vm.tools-enable-logging | VirtualMachine | VMware Tools logging | tools.conf in guest |
| vm.tools-enable-syslog | VirtualMachine | VMware Tools syslog handler | tools.conf in guest |
| vm.tools-globalconf | VirtualMachine | VMware Tools GlobalConf | tools.conf in guest |
| vm.tools-prevent-recustomization | VirtualMachine | VMware Tools deployPkg | tools.conf in guest |
| vm.tools-remove-feature | VirtualMachine | VMware Tools remove-feature | tools.conf in guest |
| vm.tools-updates | VirtualMachine | VMware Tools version current | Version check requires lifecycle database; not a vim25 property |
| vm.tools-upgrade | VirtualMachine | VMware Tools auto-upgrade | tools.conf in guest |
| vm.remove-unnecessary-devices | VirtualMachine | Remove unnecessary virtual hardware | "Unnecessary" is environment-specific; no objective API test |
| vc.administration-client-session-timeout | VCenterAdapterInstance | vSphere Client session timeout | No public API endpoint confirmed (remediation text says "No public API available") |
| vc.administration-login-message-details | VCenterAdapterInstance | Login banner details | sso-config.sh appliance shell; no public REST API |
| vc.administration-login-message-enable | VCenterAdapterInstance | Login banner enable | sso-config.sh appliance shell; no public REST API |
| vc.administration-login-message-text | VCenterAdapterInstance | Login banner text | sso-config.sh appliance shell; no public REST API |
| vc.administration-sso-groups | VCenterAdapterInstance | SSO groups for authorization | Organizational design decision; no machine check |
| vc.administration-sso-password-policy | VCenterAdapterInstance | SSO password complexity | Manual review of policy settings |
| vc.events-database-retention | VCenterAdapterInstance | Task/event retention | "No public API available" per remediation text |
| vc.vami-backup | VCenterAdapterInstance | File-based backup configured | Configuration presence check; highly env-specific |
| vc.vami-firewall-restrict-access | VCenterAdapterInstance | vCenter firewall restrict access | Organizational design decision; IP allowlist check |
| vc.supported | VCenterAdapterInstance | vCenter not end-of-support | Same lifecycle calendar issue as ESXi |
| vc.vami-updates | VCenterAdapterInstance | vCenter patches installed | Same patch baseline issue |
| cluster.data-at-rest | ClusterComputeResource | vSAN data-at-rest encryption | vSAN Management SDK gap (com.vmware.vim.vsan.binding not on classpath) |
| cluster.data-in-transit | ClusterComputeResource | vSAN data-in-transit encryption | vSAN Management SDK gap |
| cluster.file-services-access-control-nfs | ClusterComputeResource | NFS share access control | vSAN File Services; requires vSAN SDK |
| cluster.file-services-authentication-smb | ClusterComputeResource | SMB share encryption | vSAN File Services; requires vSAN SDK |
| cluster.force-provisioning | ClusterComputeResource | vSAN force provisioning disabled | vSAN storage policy evaluation; requires vSAN SDK |
| cluster.iscsi-mutual-chap | ClusterComputeResource | vSAN iSCSI mutual CHAP | vSAN iSCSI config; requires vSAN SDK |
| cluster.operations-reserve | ClusterComputeResource | vSAN operations reserve | vSAN capacity management; requires vSAN SDK |

**SCG 8.0 manual count: ~57** (including all SSH daemon config, all tools.conf, all vSAN SDK gap controls, hardware firmware controls, and env-specific assessments)

---

### SCG 9.0 — Genuinely Manual (incremental above SCG 8.0 shared controls)

All SCG 8.0 manual controls have direct equivalents in SCG 9.0 (same physical/procedural/SDK-gap reasons). In addition, SCG 9.0 adds:

**New-in-9.0 genuinely manual controls:**

| control_id | title | reason |
|---|---|---|
| esx.hardware-boot | Non-SD/USB boot device | Physical hardware inspection; no vim25 property for boot device media type |
| esx.hardware-cpu-amd-cc | AMD SEV-ES/SEV-SNP enabled | System firmware setting; not exposed via vim25 |
| esx.hardware-cpu-intel-cc | Intel SGX/TDX enabled | System firmware setting; not exposed via vim25 |
| esx.hardware-cpu-intel-txt | Intel TXT enabled | System firmware setting; not exposed via vim25 (remediation: N/A) |
| esx.hardware-firmware-updates | Firmware up to date | Off-box lifecycle management; no vim25 property |
| esx.hardware-management-authentication | BMC/iDRAC AD dependency | Off-box hardware management controller; no vim25 path |
| esx.hardware-management-log-forwarding | BMC log forwarding | Off-box hardware management controller |
| esx.hardware-management-security | BMC fully secured | Off-box hardware management controller; physical inspection |
| esx.hardware-management-time | BMC time synchronized | Off-box hardware management controller |
| esx.hardware-ports | Unused ports disabled | Physical hardware; port lock/disable is off-box |
| esx.hardware-secureboot | UEFI Secure Boot (hardware) | Same as SCG 8.0 esx.secureboot |
| esx.hardware-tpm | TPM 2.0 installed/enabled | Hardware presence; not directly in vim25 (can detect if TPM is in USE but not if it's physically present and firmware-enabled) |
| esx.nfs-encryption | NFS Kerberos encryption | Environment-specific design decision; requires AD join and storage config knowledge |
| esx.vmk-storage | Storage vmk isolation | Environment-specific network design |
| esx.vmk-vmotion | vMotion vmk isolation | Environment-specific network design |
| fleet.log-forwarding | Fleet log forwarding | vCenter-wide operational policy; no single machine-readable state |
| installer.security | VCF installer removed | One-time deployment check; no persistent state |
| logs.login-message | VCF Logs login message | External product (VCF Operations for Logs); no vim25 path |
| logs.log-receiving | VCF Logs receiving configured | External product |
| logs.password-complexity | VCF Logs password policy | External product |
| logs.retention-alert | VCF Logs retention alert | External product |
| logs.session-timeout | VCF Logs session timeout | External product |
| logs.tls-ciphers | VCF Logs TLS ciphers | External product |
| networks.enable-monitoring | VCF Operations for Networks | External product; deployment decision |
| networks.session-timeout | VCF Operations for Networks session timeout | External product |
| nsx.account-lockout-max-attempts | NSX lockout max attempts | NSX Manager; separate system, separate API |
| nsx.dhcp-disable | NSX DHCP disabled | NSX product; separate API |
| nsx.inactive-interfaces | NSX inactive interfaces | NSX product |
| nsx.login-message | NSX login message | NSX product |
| nsx.log-level | NSX log level | NSX product |
| nsx.multicast-disable | NSX multicast disabled | NSX product |
| nsx.ospf-encryption | NSX OSPF encryption | NSX product |
| nsx.password-complexity | NSX password policy | NSX product |
| nsx.reverse-path-forwarding | NSX uRPF strict | NSX product |
| nsx.service-resilience | NSX DRS anti-affinity | Design decision; env-specific |
| nsx.snmp | NSX SNMP disabled | NSX product |
| nsx.ssh | NSX SSH disabled | NSX product |
| nsx.time | NSX NTP | NSX product |
| nsx.tls-ciphers | NSX TLS ciphers | NSX product (REST API but separate system) |
| ops.account-lockout | VCF Operations lockout | External product |
| ops.certificates-validation | VCF Operations cert validation | External product |
| ops.concurrent-sessions | VCF Operations sessions | External product |
| ops.credential-ownership-enforcement | VCF Operations credentials | External product |
| ops.fips | VCF Operations FIPS | External product |
| ops.firewall-hardening | VCF Operations firewall | External product |
| ops.log-forwarding-fips | VCF Operations log forwarding | External product |
| ops.login-message | VCF Operations login message | External product |
| ops.password-complexity | VCF Operations password | External product |
| ops.service-resilience | VCF Operations HA | Design decision |
| ops.session-timeout | VCF Operations session timeout | External product |
| ops.unsigned-pak | VCF Operations unsigned pak | External product |
| sddc.api-admin | SDDC Manager API admin | External product |
| vc.account-alert | vCenter account notification | Operational/notification config; org-specific |
| vc.administration-client-plugins | vCenter plugins | Design assessment; no "unauthorized plugin" detection API |
| vc.bashshelladministrators | vCenter BashAdministrators group | AD group membership; organizational policy |
| vc.disable-accounts | vCenter unused accounts | Org-specific account list assessment |
| vc.drs | DRS enabled | Config decision; theoretically readable via vim25 (cluster config) but requires operator judgment about workload type |
| vc.login-message | vCenter login banner | sso-config.sh; no public API |
| vc.log-level | vCenter log level | Manual config check |
| vc.native-key-provider-backup | Native Key Provider backup | Organizational procedure; key backup status not in any public API |
| vc.password-complexity | SSO password complexity | Policy settings |
| vc.service-resilience-evc | EVC enabled | Design decision; env-specific |
| vc.service-resilience-ha | HA enabled | Design decision — actually readable via vim25 (cluster.configuration.dasConfig.enabled) but judgment-dependent |
| vc.service-resilience-vmotion | vMotion capability | Design decision |
| vc.smtp | vCenter SMTP config | advanced setting surface (mail.smtp.*) but credential fields require manual verification |
| vc.snmp | vCenter SNMP disabled | No confirmed public API endpoint |
| vc.snmp3 | vCenter SNMPv3 config | No confirmed public API endpoint |
| vc.vami-firewall-restrict-access | vCenter firewall restrict | Org-specific IP allowlist |
| vc.vpxuser-length | vpxuser password length | `config.vpxd.hostPasswordLength` is actually a vCenter advanced setting — check existing evaluable controls |
| vcf.disable-accounts | VCF unused accounts | Cross-product; org-specific |
| vcf.log-forwarding | VCF log forwarding | Operational config |
| vcf.mfa | VCF MFA | External identity provider integration |
| vcf.perimeter-firewall | VCF perimeter firewall | Physical/network infrastructure |
| vcf.permissions-roles | VCF permissions | Org-specific RBAC review |
| vcf.secure-baseline | VCF secure baseline | Meta-control; this document IS the baseline |
| vcf.time | VCF fleet NTP | Covered by per-component time controls; this is a fleet-level policy statement |
| vm.persistent-disk (partial) | VirtualMachine | No independent nonpersistent disks | Requires device-list filter (Style B above) — reachable but needs new style; left here pending style B |
| cluster.automatic-rebalance | ClusterComputeResource | vSAN auto rebalance | vSAN SDK gap |
| cluster.auto-policy-management | ClusterComputeResource | vSAN auto policy mgmt | vSAN SDK gap |
| cluster.encryption-rest | ClusterComputeResource | vSAN data-at-rest | vSAN SDK gap |
| cluster.encryption-transit-esa | ClusterComputeResource | vSAN data-in-transit (ESA) | vSAN SDK gap |
| cluster.encryption-transit-osa | ClusterComputeResource | vSAN data-in-transit (OSA) | vSAN SDK gap |
| cluster.file-services-access-control-nfs | ClusterComputeResource | vSAN NFS share access | vSAN SDK gap |
| cluster.file-services-authentication-smb | ClusterComputeResource | vSAN SMB encryption | vSAN SDK gap |
| cluster.force-provisioning | ClusterComputeResource | vSAN force provisioning | vSAN SDK gap |
| cluster.iscsi-mutual-chap | ClusterComputeResource | vSAN iSCSI CHAP | vSAN SDK gap |
| cluster.network-isolation-vsan-iscsi-target | ClusterComputeResource | vSAN iSCSI network isolation | vSAN SDK gap + design decision |
| cluster.network-isolation-vsan-max | ClusterComputeResource | vSAN Max network isolation | vSAN SDK gap + design decision |
| cluster.operations-reserve | ClusterComputeResource | vSAN operations reserve | vSAN SDK gap |

---

## Uncertain / needs investigation

| control_id | profile(s) | what's needed |
|---|---|---|
| esx.logs-audit-persistent / esx.log-audit-persistent | 8.0, 9.0 | `ScratchConfig.CurrentScratchLocation` IS an existing advanced setting; the compliance test is "value != /tmp/scratch". The control is classified manual_audit because of the multi-parameter nature, but the primary indicator IS an advanced setting. Could be reclassified to `advanced_setting` with a regex or "not-equal" comparison mode — needs evaluator enhancement or confirmation the current string equality match suffices. |
| esx.logs-persistent / esx.log-persistent | 8.0, 9.0 | Same as above — `LocalLogOutputIsPersistent` and `ScratchConfig.CurrentScratchLocation` are in the advanced setting surface. `LocalLogOutputIsPersistent` returns "true"/"false" as a boolean. Could be split into two separate `advanced_setting` controls instead of one `manual_audit`. |
| dvpg.network-vgt | 8.0, 9.0 | VLAN ID check for 4095 is theoretically possible via vim25 but requires type-checking (VlanIdSpec vs TrunkVlanSpec) — new style D needed. Confirmed the object model supports it; needs live test on devel DVPG to confirm the TrunkVlanSpec is what VGT uses. |
| esx.lockdown-exception-users | 8.0, 9.0 | HostAccessManager.retrieveLockdownExceptions() returns a String array (list of usernames). This is a managed-object method call, not a PropertyCollector path. Could be supported by a new `access_manager` style that calls this method. Medium Java cost. |
| esx.firewall-restrict-access | 8.0, 9.0 | Per-ruleset allowed IP list is deeply nested in `config.firewall.ruleset[].allowedHosts`. Checking "only authorized IPs" requires org-specific knowledge of what the authorized list is. The "default deny" part (`config.firewall.defaultPolicy.incomingBlocked`) is captured in `esx.firewall-incoming-default` (reclassified above). The "per-ruleset IP restriction" part is genuinely manual. |
| vc.vpxuser-length | 9.0 | The description says `config.vpxd.hostPasswordLength` but this is listed as manual_audit. It IS a vCenter advanced setting — likely the same `VirtualCenter.VimPasswordExpirationInDays` reader could read it. Needs verification that the key is present in the devel vCenter advanced settings surface. If confirmed, reclassify to `advanced_setting`. |
| vds.network-restrict-port-mirroring | 8.0, 9.0 | Port mirror session list path needs live verification: is it `config.vspanSession` or `config.mirrorPortConfigs` on VMwareDVSConfigInfo in vSphere 8? The object model changed across versions. Marked style C (list_empty) but path needs live confirmation on devel DVS object. |
| esx.hardware-tpm (9.0) | 9.0 | TPM presence in firmware is not in vim25, but whether ESXi is USING the TPM CAN be inferred from `config.encryptionState.mode` (TPM means it's configured). This is not the same as "TPM 2.0 physically present and enabled in firmware." Partial coverage only — flagged uncertain. |
| vc.drs (9.0) | 9.0 | `clusterComputeResource.configuration.drsConfig.enabled` is a readable vim25 property (bool). However, the control requires evaluating DRS configuration quality (rules, balance, automation level) not just on/off — partial coverage is possible. Uncertain whether the intent is satisfied by a simple bool read. |

---

## Revised counts (clarified)

### SCG 8.0 (98 in-scope)
- `vim_property` existing style (pure CSV for DVS/DVPG today; HostSystem/VM need collectHosts/Vms extension): **10**
  - HostSystem: 5 (lockdown-mode, firewall-incoming-default, timekeeping-sources, secureboot-enforcement, tpm-configuration)
  - VM: 4 (secure-boot, vmotion-encrypted, ft-encrypted, log-enable)
  - DVPG: 2 (mac-learning, restrict-port-level-overrides-partial)
  - DVS: 3 (reset-port, restrict-discovery-protocol, restrict-netflow-usage)
  - **Pure CSV today** (DVS/DVPG only): 5
- `vim_property` NEW style needed: **14**
  - Style A (service_state): 6 controls (shell, ssh, cim, slp, snmp, ntp-services)
  - Style B (vm_hardware_device_absent): 2 (pci-passthrough, remove-unnecessary-devices — actually remove-unnecessary is manual)
  - Style C (list_empty): 1 (restrict-port-mirroring, uncertain path)
  - Style D (vlan_id_not): 1 (network-vgt)
  - Style E (SSO API): 5 (sso lockout/password controls)
  - Style F (VAMI API): 6 (ssh, syslog, time, fips, tls-profile, password-expiration)
  - vm.pci-passthrough: Style B — 1
- `genuinely manual`: ~57
- `uncertain`: 9 (as listed above)

### SCG 9.0 (164 in-scope)
- `vim_property` existing style: **13** (lockdown-mode, firewall-incoming-default, time/NTP-sources, secureboot-enforcement, tpm-configuration, tpm-trusted-binaries + VM 5 + DVPG 2 + DVS 4)
  - **Pure CSV today** (DVS/DVPG only): 7
- `vim_property` NEW style needed: **~26** (matching SCG 8.0 cluster + SCG 9.0 additions)
- `genuinely manual`: ~110
- `uncertain`: 15

---

## Key takeaways for the roadmap

1. **Lowest cost, highest return: extend collectHosts() and collectVms() once.** This is a single architectural Java change that immediately enables vim_property controls on the two most populous resource types. It unlocks 9+ controls per profile by CSV edit alone thereafter.

2. **DVS/DVPG vim_property controls are pure CSV today.** Thirteen controls across both profiles can be added by editing the canonical CSVs and re-running normalizers. No Java required. These are confirmed evaluable because `collectDvs()` and `collectDvpg()` already call `readVimProperties()`.

3. **Style A (service_state) is the highest-value new style.** One Java style unlocks 10 service-state controls (shell/SSH/CIM/SLP/SNMP/NTP across both profiles). This is the most bang-for-buck new style.

4. **The vSAN SDK gap is the largest genuinely-manual cluster.** 10 (SCG 8.0) + 13 (SCG 9.0) vSAN cluster controls are blocked by the missing `com.vmware.vim.vsan.binding` classpath. This is documented in `context/investigations/2026-05-29-vsan-management-sdk-gap.md`.

5. **Sub-product controls (NSX, VCF Ops, VCF Logs, Networks) are all genuinely manual.** The adapter has no reach into those products' management APIs. 40+ SCG 9.0 controls fall here.

6. **VMware Tools tools.conf controls (14 in 8.0, 14 in 9.0) are genuinely manual.** tools.conf lives inside the guest OS filesystem; it is not reachable via PropertyCollector, extraConfig, or any vCenter SOAP/REST endpoint.

7. **vc.vpxuser-length (SCG 9.0) should be re-examined.** The parameter `config.vpxd.hostPasswordLength` is a vCenter advanced setting. If it is present in the devel vCenter's advanced settings surface, this control can be reclassified to `advanced_setting` with no Java at all.

---

*Report generated by ops-recon against devel instance (vcf-lab-operations-devel.int.sentania.net) on 2026-06-03. All vim25 property paths are based on vSphere 8.0 API reference and confirmed-evaluable patterns from the existing adapter implementation. HostEncryptionState paths (encryptionState.*) are confirmed for vSphere 7.0U2+.*
