# Controls We Do Not Audit

This document ships **inside the pak** (bundled at
`vcfcf_compliance/conf/profiles/UNAUDITED_CONTROLS.md`). It is the honest
coverage statement for the VCF Content Factory Compliance adapter against
the VMware Security Configuration Guide (SCG) 8.0 / 9.0 profiles.

The adapter machine-audits every control it *can* assess from the vCenter
vim25 SOAP surface (advanced settings + `vim_property` read recipes). The
controls below it does **not** audit. They fall into two buckets, matching
how an operator should think about them:

1. **Cannot** — there is no machine-readable signal the adapter can reach.
   These require human review, off-box inspection, or a separate product's
   API. They will never be auto-scored by this adapter.
2. **Haven't fully explored yet** — the state *is* reachable via an API,
   but needs a reader (a new `read_recipe` style, or a non-vim25 reader)
   the adapter has not built. These are backlog, not dead ends.

A control being absent here means it is (or is intended to be) audited.
A control under "Cannot" or "Haven't yet" is **never** reported as a
`pass` — it ships as `manual_audit` / informational, excluded from every
compliance score. (Where a recipe is declared but the live read returns
nothing, the adapter raises an explicit `unreadable_count` signal — that
is a distinct coverage warning, not a pass.)

Source of record: `context/investigations/scg89-audit-coverage-recon.md`.

---

## Partial-coverage controls (audited, but read the caveat)

Two reclassified controls are audited with **less than full fidelity**. A
`pass` does NOT mean the whole SCG control is satisfied. These caveats are
also embedded in each control's description in the profile CSV.

| control_id | What is checked | What is NOT checked |
|---|---|---|
| `dvpg.network-restrict-port-level-overrides` | `config.policy.securityPolicyOverrideAllowed` is disabled (1 of ~7 override flags) | block / teaming / vlan / shaping / vendorConfig / ipfix / trafficFilter per-port overrides |
| `vm.virtual-hardware` | `config.version` equals the SCG baseline string exactly (`vmx-19` / `vmx-21`) | "version N **or newer**" — a higher-than-baseline VM reads as non-compliant |

> **NTP time-source controls** (`esx.timekeeping-sources` in 8.0,
> `esx.time` in 9.0) are intentionally **not** reclassified. The NTP server
> list is readable (`config.dateTimeInfo.ntpConfig.server`), but the SCG
> baseline value is the sentinel "Site-Specific", which no real server
> list can string-equal — reclassifying would manufacture a permanent
> false "fail". They need a presence / non-empty comparison mode the
> evaluator does not have yet (see "Haven't fully explored yet").

---

## Cannot (genuinely manual — no machine-readable signal)

### In-guest state (not on the vCenter SOAP surface)

VMware Tools `tools.conf` settings live inside the guest OS filesystem;
they are not reachable via PropertyCollector, `extraConfig`, or any
vCenter SOAP/REST endpoint. (14 controls in 8.0, 14 in 9.0.)

`vm.tools-add-feature`, `vm.tools-allow-transforms`,
`vm.tools-deactivate-appinfo`, `vm.tools-deactivate-containerinfo`,
`vm.tools-deactivate-guestoperations`, `vm.tools-deactivate-gueststoreupgrade`,
`vm.tools-deactivate-servicediscovery`, `vm.tools-enable-logging`,
`vm.tools-enable-syslog`, `vm.tools-globalconf`,
`vm.tools-prevent-recustomization`, `vm.tools-remove-feature`,
`vm.tools-upgrade`. (`vm.tools-updates` needs a lifecycle DB, also manual.)

### ESXi SSH daemon (`sshd_config`) — host-side config files

`sshd_config` parameters are not vim25 properties (esxcli/shell only):
`esx.ssh-fips`, `esx.ssh-fips-ciphers`, `esx.ssh-gateway-ports`,
`esx.ssh-host-based-auth`, `esx.ssh-idle-timeout-count`,
`esx.ssh-idle-timeout-interval`, `esx.ssh-login-banner`, `esx.ssh-rhosts`,
`esx.ssh-stream-local-forwarding`, `esx.ssh-tcp-forwarding`,
`esx.ssh-tunnels`, `esx.ssh-user-environment`.

### ESXi host — no PropertyCollector path / per-account / kernel boot

`esx.key-persistence` (esxcli only), `esx.entropy` (kernel boot param),
`esx.account-dcui`, `esx.account-vpxuser` (per-account shell flags),
`esx.firewall-restrict-access` (per-ruleset IP allowlist — env-specific),
`esx.iscsi-mutual-chap` (per-HBA credential check),
`esx.lockdown-exception-users` (managed-object method, not a property),
`esx.vmk-management` / `esx.vmk-storage` / `esx.vmk-vmotion`
(environment-specific network design), `esx.nfs-encryption` (AD/Kerberos
design decision).

### Physical / firmware / off-box hardware (9.0 hardware-* family)

Not exposed via vim25 — system firmware, BMC/iDRAC, physical media:
`esx.secureboot` / `esx.hardware-secureboot` (UEFI firmware),
`esx.hardware-boot` (boot media type), `esx.hardware-cpu-amd-cc`,
`esx.hardware-cpu-intel-cc`, `esx.hardware-cpu-intel-txt`,
`esx.hardware-firmware-updates`, `esx.hardware-management-authentication`,
`esx.hardware-management-log-forwarding`, `esx.hardware-management-security`,
`esx.hardware-management-time`, `esx.hardware-ports`, `esx.hardware-tpm`.

### Lifecycle / patch baseline (no "unsupported/unpatched" API signal)

`esx.supported`, `esx.updates`, `vc.supported`, `vc.vami-updates`.

### vCenter — no confirmed public API / org-policy / banner shell

`vc.administration-client-session-timeout`, `vc.events-database-retention`
("no public API"), `vc.administration-login-message-enable` / `-text` /
`-details` / `vc.login-message` (sso-config.sh shell, no REST),
`vc.administration-sso-groups`, `vc.administration-sso-password-policy` /
`vc.password-complexity`, `vc.administration-client-plugins`,
`vc.bashshelladministrators`, `vc.disable-accounts`, `vc.account-alert`,
`vc.log-level`, `vc.native-key-provider-backup`, `vc.smtp` (credential
fields), `vc.snmp` / `vc.snmp3` (no confirmed endpoint),
`vc.vami-backup`, `vc.vami-firewall-restrict-access`,
`vc.drs` / `vc.service-resilience-ha` / `-evc` / `-vmotion` (config
decisions requiring operator judgment).

### vSAN — vSAN Management SDK classpath gap

The bulk of `ClusterComputeResource` controls live on the vSAN Management
SDK (`com.vmware.vim.vsan.binding`), which is NOT on this adapter's
classpath (per-pak classloader isolation; see
`context/investigations/2026-05-29-vsan-management-sdk-gap.md`). Two vSAN
controls ARE audited today via plain vim25 (`cluster.managed-disk-claim`,
`cluster.object-checksum`). The rest cannot be read:

`cluster.encryption-rest` / `cluster.data-at-rest`,
`cluster.encryption-transit-esa` / `-osa` / `cluster.data-in-transit`,
`cluster.force-provisioning`, `cluster.iscsi-mutual-chap`,
`cluster.file-services-access-control-nfs`,
`cluster.file-services-authentication-smb`, `cluster.operations-reserve`,
`cluster.automatic-rebalance`, `cluster.auto-policy-management`,
`cluster.network-isolation-vsan-iscsi-target`,
`cluster.network-isolation-vsan-max`.

### Separate products (no API reach from this adapter)

NSX, VCF Operations, VCF Operations for Logs, VCF Operations for Networks,
SDDC Manager, and VCF-umbrella controls are separate systems with separate
management APIs the compliance adapter does not connect to. All `nsx.*`,
`ops.*`, `logs.*`, `networks.*`, `sddc.*`, `installer.*`, `vcf.*`, and
`fleet.*` controls fall here (40+ controls in 9.0). Examples:
`nsx.ssh`, `nsx.tls-ciphers`, `ops.fips`, `ops.session-timeout`,
`logs.tls-ciphers`, `networks.session-timeout`, `sddc.api-admin`,
`vcf.mfa`, `vcf.perimeter-firewall`, `fleet.log-forwarding`.

### Organizational / design / meta controls

`vm.remove-unnecessary-devices` ("unnecessary" is env-specific),
`vcf.permissions-roles`, `vcf.secure-baseline` (this guide IS the
baseline), `vcf.time` (fleet policy statement).

> **Total "Cannot": ~153 controls** across both profiles.

---

## Haven't fully explored yet (API-reachable, reader not built)

These are backlog. The state is reachable; the adapter needs a new reader.
Ranked roughly by value (most controls unlocked per unit of Java).

### New `read_recipe` styles (vim25 — same SOAP session)

| style | unlocks | controls |
|---|---|---|
| `service_state` (HostServiceInfo list filter — running/policy) | ~16 | `esx.deactivate-shell` / `esx.shell`, `esx.deactivate-ssh` / `esx.ssh`, `esx.deactivate-cim`, `esx.deactivate-slp`, `esx.deactivate-snmp` / `esx.snmp`, `esx.timekeeping-services` / `esx.time` (NTP daemon) |
| `vm_hardware_device_absent` (config.hardware.device[] filter) | ~4 | `vm.pci-passthrough`, `vm.persistent-disk` (independentNonpersistent disks absent) |
| `list_empty` (list-has-zero-elements) | 2 | `vds.network-restrict-port-mirroring` (path `config.vspanSession` vs `config.mirrorPortConfigs` needs live confirmation) |
| `vlan_id_not` (VLAN type-aware: VGT vs vlanId 4095) | 2 | `dvpg.network-vgt` |
| presence / non-empty compare (for the NTP-sources controls above) | 2 | `esx.timekeeping-sources` (8.0), `esx.time` NTP-source half (9.0) |

The ~46 new-style controls overall are unlocked by building these styles.

### Other vCenter APIs (not vim25 — separate readers)

| reader | unlocks | controls |
|---|---|---|
| vCenter SSO STS SOAP (lockout / password policy) | ~10 | `vc.administration-sso-lockout-policy-max-attempts` / `-unlock-time`, `vc.administration-failed-login-interval`, `vc.administration-sso-password-lifetime` / `-reuse` (8.0); `vc.account-lockout-duration` / `-max-attempts` / `-reset`, `vc.password-history` / `-max-age` (9.0) |
| vCenter Appliance REST (VAMI, `/api/appliance/...`) | ~12 | `vc.vami-access-ssh` / `vc.ssh`, `vc.vami-syslog` / `vc.log-forwarding`, `vc.vami-time` / `vc.time`, `vc.fips-enable`, `vc.tls-profile` / `vc.tls-ciphers`, `vc.vami-administration-password-expiration` / `vc.vami-password-max-age` |

The 16 "other-API" controls are split across these two readers.

### Uncertain — needs a live-instance check before committing a recipe

| control_id | what's needed |
|---|---|
| `esx.logs-audit-persistent`, `esx.logs-persistent` | `ScratchConfig.CurrentScratchLocation` / `LocalLogOutputIsPersistent` are advanced settings, but the test is "not /tmp/scratch" (a not-equal / mount-point compare the evaluator lacks). Could become `advanced_setting` with a not-equal mode. |
| `vc.vpxuser-length` | `config.vpxd.hostPasswordLength` may be in the vCenter advanced-settings surface — if confirmed on a live instance, reclassify to `advanced_setting`, no Java. |
| `dvpg.network-vgt` | needs live confirmation that VGT presents as a `TrunkVlanSpec` (style `vlan_id_not`). |
| `vds.network-restrict-port-mirroring` | port-mirror list path (`config.vspanSession` vs `config.mirrorPortConfigs`) varies by API version — confirm live. |
| `esx.lockdown-exception-users` | `HostAccessManager.retrieveLockdownExceptions()` is a managed-object method call, not a property — needs an `access_manager` style. |
| `esx.hardware-tpm` (9.0) | TPM physical presence is not in vim25; only TPM *in use* is inferable from `config.encryptionState.mode` (partial). |
| `vc.drs` (9.0) | `drsConfig.enabled` is readable, but the control wants DRS config *quality*, not just on/off (partial). |

> **Total "Haven't yet": ~46 new-style + ~16 other-API + ~24 uncertain.**

---

*Generated for the build 35 coverage expansion. When a "Haven't yet"
reader is built, move its controls out of this doc and into the audited
set via the canonical CSV + normalizer. The framework gets more honest,
and more complete, one reader at a time.*
