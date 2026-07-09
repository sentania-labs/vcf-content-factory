# Design Artifact: VCF Content Factory vCommunity (Tier 2 Java SDK)

> Native Java SDK rewrite of `vmbro/VCF-Operations-vCommunity` (Onur
> Yuzseven, CC-licensed). Kills the Python Integration SDK / Docker
> runtime; the adapter runs natively in the collector like the
> compliance adapter. Full collector parity in v1 (incl. Windows
> guest-ops); all ~100 bundled artifacts ported to factory YAML as
> canonical source.
>
> **Status: APPROVED — zero open questions.** All eight design
> questions (OPEN-1 … OPEN-8) are resolved (see decisions log). Ready
> for `sdk-adapter-author`.

## Original Request

See `designs/managementpacks/vcommunity.md` (prompt-of-record, do not
rewrite). Distilled: full-parity Tier 2 rewrite, no Docker; keep the
`vCommunity|` key namespace; port all bundled content converted to
factory YAML; strengthen the MP content pipeline as a co-equal goal;
ship from `sentania-labs/vcf-content-factory-sdk-vcommunity`.

## Tier decision

**Tier 2 (Java SDK). Not negotiable.** RULE-004 triggers fire hard:

- **Non-HTTP transport** — the entire data source is vCenter vim25
  SOAP (pyVmomi `SmartConnect` → `RetrieveContent` →
  `CreateContainerView`). No HTTP/JSON collection path exists. (Trigger
  1.)
- **Programmatic in-guest actions** — Windows guest-ops uploads a
  PowerShell script via `guestOperationsManager.fileManager`, runs it
  with `processManager.StartProgram`, polls for exit, downloads CSV
  output. That is run-in-guest action execution, not collection.
  (Trigger 5.)
- **Custom response transforms / nested iteration** — recursive
  snapshot-tree walk, SCSI controller device-type discrimination,
  CSV parsing of guest output, licensing expiry arithmetic. (Triggers
  9, 10.)
- **Foreign-resource stitching with no MPB request model** — the
  whole adapter is "read vim25, push onto existing VMWARE resources."
  MPB's ARIA_OPS stitching is HTTP-request-driven; there is no HTTP
  request here to bind a `dataModelList` to.

The reference implementation (`content/sdk-adapters/compliance/`) is
the same shape (vim25 SOAP read → Suite API push onto VMWARE
HostSystem) and is healthy with two DATA_RECEIVING instances on devel,
so the runtime path is proven. **Lesson check:** no Tier-2-vs-Tier-1
ambiguity to route through `lessons/INDEX.md` — every relevant lesson
(`foreign-resource-property-push`, `suite-api-stitch-ssl-tofu-vs-java-http`,
`controller-describe-bare-instantiation`, `sdk-constants-are-display-names`,
`setrelationships-foreign-adapter-scoped`) already assumes Tier 2 and is
binding on the author.

### Tier 2 delivery model

- New repo: **`sentania-labs/vcf-content-factory-sdk-vcommunity`**,
  instantiated from `sentania-labs/vcf-content-factory-sdk-template`
  ("Use this template") — ships skeleton + `build-pak-on-tag` CI.
- Orchestrator adds one line to `context/managed_paks.md`
  (name `vcommunity` / remote / target
  `content/sdk-adapters/vcommunity/`) so bootstrap clones it for
  authoring.
- `sdk-adapter-author` authors in the cloned dir. Official `.pak` is
  the pak repo's CI on a `v*` tag, never a factory build. Bundled
  content ships **inside** that repo (`views/`, `dashboards/`,
  `supermetrics/`, etc.), co-located — not in the factory.

### Migration from the original MP (RESOLVED — side-by-side fork)

The upgrade-path experiment
(`context/investigations/vcommunity_upgrade_path_experiment.md`)
**empirically closes the in-place-upgrade door.** A same-identity
classic pak installed over the installed containerized pak is *accepted*
(version bumps, no rejection, no signature complaint) but **silently
split-brains the platform**: the adapter kind stays registered as
`adapterKindType=DOCKERIZED` with the original describe.xml, the shipped
Java JAR is never wired in, and adapter-instance creation fails
("Collector is not compatible with adapter type"). This is strictly
worse than an honest rejection — an operator sees "upgrade succeeded"
while the old container adapter is still live. **The distinct adapter
kind `vcfcf_vcommunity` (side-by-side coexistence) is therefore the only
viable shape, now a hard requirement, not a preference.**

**Operator migration procedure (document in the MP description / README):**

1. **Uninstall the original** containerized pak
   (`iSDK_VCFOperationsvCommunity`). Note `pak-uninstall-cascades-credentials` —
   the original's adapter instances and credentials cascade away.
2. **Install ours** (`vcfcf_vcommunity`).
3. **Recreate adapter instances and credentials** against the new kind
   (no instance/credential carry-over across a kind change).

**Metric-history continuity (convenience, not a contract):** because we
push onto the *same* VMware-owned resources (`ClusterComputeResource` /
`HostSystem` / `VirtualMachine`) under the *identical* `vCommunity|` key
namespace, historical metric/property series on those foreign resources
remain mechanically continuous through the migration — the new adapter
writes to the same keys on the same resource UUIDs. This is a happy
side effect of key-namespace continuity, **not** an upgrade guarantee;
do not represent it to users as a supported upgrade path.

### Author-relevant platform notes (from the upgrade experiment)

- **Classic kinds register as `adapterKindType=GENERAL`.** Every classic
  Java SDK adapter on devel (`vcfcf_compliance`, `synology_diskstation`,
  `unifi_controller`) registers as `GENERAL` (vs `DOCKERIZED` for the
  containerized original, `OPENAPI` for the REST integration). Expect
  `GET /api/adapterkinds/vcfcf_vcommunity → adapterKindType: GENERAL`
  post-install — that is the healthy classic-adapter signature.
- **The factory enforces lowercase adapter kinds.** `sdk_project.py`
  applies `re.fullmatch(r"^[a-z][a-z0-9_]*$", adapter_kind)`;
  `vcfcf_vcommunity` complies. (The same rule *blocks* a build of the
  mixed-case `VCFOperationsvCommunity` — irrelevant here since the fork
  uses a fresh lowercase kind, but it is *why* same-identity was
  un-buildable through `build-sdk` even before the split-brain finding.)
  **No tooling change needed for this design.**

## Interview Answers

All major decisions are already pinned in the prompt-of-record; the
designer interview reduces to resolving the 7 design questions. Answers
below; full reasoning in each section + the OPEN Questions block.

| Question | Answer |
|---|---|
| Adapter kind key | **`vcfcf_vcommunity`** (factory convention, mirrors `vcfcf_compliance`). NOT `VCFOperationsvCommunity`. RESOLVED (OPEN-1): side-by-side fork is now **experimentally confirmed as the only viable path** — see `context/investigations/vcommunity_upgrade_path_experiment.md`. Complies with the `sdk_project.py` `^[a-z][a-z0-9_]*$` lowercase rule (no tooling change needed). |
| Adapter display name | `VCF Content Factory vCommunity` (prose prefix per convention). |
| New object types? | **None.** Pure ARIA_OPS-style stitching onto existing VMWARE `ClusterComputeResource` / `HostSystem` / `VirtualMachine`. |
| Key namespace | `vCommunity\|...` verbatim — every key traced to source file:line below (RULE-002). |
| Property push | **Proven.** `SuiteApiStitcher.pushProperties` (compliance reference). |
| Metric/stat push | **Proven.** `SuiteApiStitcher.pushStats` exists and is used by compliance for per-host scores. NOT a gap. |
| Event push (foreign resource) | **TOOLSET GAP #1**, staged plan **ACCEPTED** (OPEN-2 RESOLVED): v1 attempts a real foreign-resource event push; if unprovable during v1 development, degrade to property representation (visible, alertable, never silently dropped) and prove real events in v1.1. No `pushEvents` on the framework facade today. |
| Windows credentials | **Second `CredentialKind`** (Windows Guest Credential), separate from the vCenter credential. RESOLVED — see Credential design. |
| Guest-ops opt-in | **One adapter-instance enum** `Windows Monitoring` with four values (Disabled \| Services \| Event Logs \| Services + Event Logs), default Disabled. Replaces the two original boolean toggles. |
| Config-file UX | **RESOLVED (OPEN-4) — pure-rewrite, central config store:** six check-list XMLs ship in `content/files/solutionconfig/` → imported into the VCF Ops **central configuration-file store** at pak install (NOT distributed to collectors). The adapter fetches them by NAME via Suite API every cycle (`GET api/configurations/files?path=SolutionConfig/<name>.xml`) exactly as the original does. The six original file-NAME identifier keys are preserved verbatim (`esxi_adv_settings_config_file`, `esxi_vib_driver_config_file`, `vm_adv_settings_config_file`, `vm_configuration_config_file`, `win_service_config_file`, `win_event_config_file`), each defaulted to the bundled file's base name. Admins customize by editing files centrally (Administration → Configuration Files) and pointing an instance's field at an alternate name. `custom_config_dir` / on-collector override files are **deleted** (prior draft was based on a wrong assumption). NO per-instance delimiter-string fields. See Config design. |
| Content port | All ~100 artifacts → factory YAML as canonical source, rendered into the pak `content/` tree. Gap list below. |
| Attribution | Onur Yuzseven / `vmbro/VCF-Operations-vCommunity`, CC license, in MP description + every ported artifact description. |

## Object Model

No domain hierarchy of its own. The adapter declares **one synthetic
own-resource** (an adapter-instance / "world" anchor so the collection
returns a non-empty `ResourceCollection` — same as compliance's
`ComplianceWorld`) and stitches everything else onto foreign VMWARE
resources.

```
vcfcf_vcommunity (adapter instance)
└── vCommunityWorld         [INTERNAL, own kind — collection anchor, health only]

   ── stitches onto (foreign, owned by VMWARE adapter) ──
   ClusterComputeResource   ← vCommunity| HA / DRS / EVC props + DRS Score metric
   HostSystem               ← vCommunity| Adv Settings / Packages / Install Date /
                               Licensing (+ Remaining Days metric) / NIC uplinks
   VirtualMachine           ← vCommunity| Config / Options / Adv Params /
                               SCSI Controllers (+ Count metric) /
                               Snapshot Count metric / Guest OS (services, OS info) /
                               Windows event-log EVENTS
```

### Relationships

1. None authored. The adapter pushes onto resources whose
   parent/child edges are owned entirely by the VMWARE adapter.
   Per `setrelationships-foreign-adapter-scoped`, do **not** emit
   `setRelationships` onto foreign resources — leave the VMWARE
   topology untouched. The `vCommunityWorld` anchor has no children.

## Stitching model (the core mechanism)

Identical in spirit to the original (`collectClusterData.py` etc.) and
to `ComplianceStitcher`:

1. vim25 `SmartConnect` to the configured vCenter; `RetrieveContent`;
   `CreateContainerView` per type (`ClusterComputeResource`,
   `HostSystem`, `VirtualMachine`).
2. For each vim object, capture its **MoID** (`_moId`) and name.
3. Resolve the foreign VCF Ops resource UUID via the framework
   `SuiteApiStitcher` → `ComplianceStitcher`-style loader:
   `GET /api/resources?adapterKind=VMWARE&resourceKind=<kind>` →
   index by **`VMEntityObjectID`** (MoID, authoritative) then
   `VMEntityName`. **The MoID match is byte-for-byte the original's
   join key** (`hosts_by_uuid[host._moId]`). Reuse
   `ComplianceStitcher` verbatim — it already loads HostSystem /
   VirtualMachine / ClusterComputeResource and matches by MoID+name.
4. `pushProperties(uuid, {vCommunity|...: value}, ts)` and
   `pushStats(uuid, {vCommunity|...: value}, ts)`.
5. Return ONLY `vCommunityWorld` in the `ResourceCollection`
   (foreign-resource-property-push lesson: foreign resources in the
   collection are silently dropped; the push goes through Suite API,
   not the collection).

**Binding lessons (author must obey):**
- `foreign-resource-property-push` — push via Suite API, not
  `ResourceCollection.add()`.
- `suite-api-stitch-ssl-tofu-vs-java-http` — `insecureSslContext()`
  for localhost Suite API; `platformSsl` for the vCenter connection
  (admin pre-approves that cert).
- `controller-describe-bare-instantiation` — supply the adapter kind
  via `super(ADAPTER_KIND)`; never call injected-state accessors in
  `describe()`.
- `sdk-constants-are-display-names` — `CommonConstants.*` are display
  strings, not paths.
- `setrelationships-foreign-adapter-scoped` — do not touch VMWARE
  topology.
- Suite API client is **null on the first cycle** — guard and skip the
  push; the next cycle catches up.

## Object Type Details

### vCommunityWorld (INTERNAL, own kind)
- Identifier: adapter instance key (one per adapter instance).
- Name expression: adapter instance name.
- Source: synthesized in-collector (no external data).
- Icon hint: `default` (**OPEN-8 RESOLVED** — synthetic anchor, no
  distinctive icon needed; documents the choice, silences build WARN. No
  branded `vcommunity.svg` for v1.).
- Carries adapter health + a per-cycle collection summary metric
  (counts of clusters/hosts/vms stitched) for operability.

### ClusterComputeResource (foreign VMWARE — stitched)
Every key traced to source. `P`=property, `M`=metric.

| Key (`vCommunity\|...`) | Type | vim25 source | Source file:line |
|---|---|---|---|
| `Cluster Configuration\|vSphere HA\|Host Monitoring` | P | `configuration.dasConfig.hostMonitoring` | clusterConfigs.yaml:3-4 |
| `Cluster Configuration\|vSphere HA\|Response \ Host Isolation` | P | `configuration.dasConfig.defaultVmSettings.isolationResponse` | clusterConfigs.yaml:5-6 |
| `Cluster Configuration\|vSphere HA\|Response \ Default VM Restart Priority` | P | `...defaultVmSettings.restartPriority` | clusterConfigs.yaml:7-8 |
| `Cluster Configuration\|vSphere HA\|Response \ Datastore APD` | P | `...vmComponentProtectionSettings.vmStorageProtectionForAPD` | clusterConfigs.yaml:9-10 |
| `Cluster Configuration\|vSphere HA\|Response \ Datastore PDL` | P | `...vmStorageProtectionForPDL` | clusterConfigs.yaml:11-12 |
| `Cluster Configuration\|vSphere HA\|VM Monitoring` | P | `configuration.dasConfig.vmMonitoring` | clusterConfigs.yaml:13-14 |
| `Cluster Configuration\|vSphere HA\|Heartbeat Datastore` | P | `configuration.dasConfig.hBDatastoreCandidatePolicy` | clusterConfigs.yaml:15-16 |
| `Cluster Configuration\|DRS\|Proactive DRS` | P | `configurationEx.proactiveDrsConfig.enabled` | clusterConfigs.yaml:19-20 |
| `Cluster Configuration\|DRS\|Scale Descendants Shares` | P | `configuration.drsConfig.scaleDescendantsShares` | clusterConfigs.yaml:21-22 |
| `Cluster Configuration\|DRS\|CPU Over-Commitment` | P | `configurationEx.drsConfig.option[key=MaxVcpusPerCore].value` ("N/A" if absent) | drs_properties.py:37-53 |
| `Cluster Configuration\|DRS\|DRS Score` | M | `summary.drsScore` | clusterConfigs.yaml:24-25 |
| `Cluster Configuration\|EVC\|Enabled` | P | `EvcManager().evcState.currentEVCModeKey` truthiness → "True"/"False" | evc_properties.py:12-29 |
| `Cluster Configuration\|EVC\|Mode` | P | `evcState.currentEVCModeKey` (else "null") | evc_properties.py:13-31 |

Gating logic to preserve (drs_properties.py:23, ha_properties.py:23):
when HA disabled (`dasConfig.enabled==False` or
`hostMonitoring=='disabled'`) push `"null"`; when DRS disabled
(`drsConfig.enabled==False`) push `"null"` (props) / `0` (DRS Score
metric). The original wraps every push in `checkLastValue` (a
change-detection cache, `constants/checkUpdatedValues.py`) — this is a
**Python-SDK-specific write-suppression optimization and need not be
replicated**; the Suite API push is idempotent. (Author may add a
last-value cache later as an optimization; not required for parity.)

### HostSystem (foreign VMWARE — stitched)
Only processed when `runtime.connectionState == "connected"`
(collectHostData.py:58).

| Key (`vCommunity\|...`) | Type | vim25 source | Source file:line |
|---|---|---|---|
| `Configuration\|Advanced System Settings\|{key}` | P | `configManager.advancedOption.setting` filtered to config-list keys | host_advanced_settings.py:11-20 |
| `Configuration\|Packages:{name}\|Package Name` | P | `configManager.imageConfigManager.fetchSoftwarePackages()[].name` | host_software_packages.py:16 |
| `Configuration\|Packages:{name}\|Package Version` | P | `package.version` | host_software_packages.py:17 |
| `Configuration\|Packages:{name}\|Acceptance Level` | P | `package.acceptanceLevel` | host_software_packages.py:18 |
| `Configuration\|Packages:{name}\|Maintenance Mode Required` | P | `package.maintenanceModeRequired` | host_software_packages.py:19 |
| `Configuration\|Packages:{name}\|Package Summary` | P | `package.summary` | host_software_packages.py:20 |
| `Configuration\|Packages:{name}\|Package Type` | P | `package.type` | host_software_packages.py:21 |
| `Configuration\|Packages:{name}\|Package Vendor` | P | `package.vendor` | host_software_packages.py:22 |
| `Configuration\|Install Date\|UTC` | P | `imageConfigManager.installDate()` ISO UTC (else "null") | host_install_date.py:16-20 |
| `Licensing:{name}\|Name` | P | `licenseAssignmentManager.QueryAssignedLicenses(moid)[].assignedLicense.name` | host_licensing.py:28 |
| `Licensing:{name}\|License Key` | P | `assignedLicense.licenseKey` | host_licensing.py:29 |
| `Licensing:{name}\|License Expiration Date` | P | `assignedLicense.properties[key=expirationDate].value` | host_licensing.py:30 |
| `Licensing:{name}\|Remaining Days` | M | `(expirationDate - now).days` | host_licensing.py:31 |
| `Licensing:{name}\|Edition Key` | P | `assignedLicense.editionKey` | host_licensing.py:32 |
| `Network\|Device:{device}\|Device Name` | P | `config.network.pnic[].device` | host_uplink.py:20 |
| `Network\|Device:{device}\|Driver Version` | P | `pnic.driverVersion` | host_uplink.py:21 |
| `Network\|Device:{device}\|Firmware Version` | P | `pnic.firmwareVersion` | host_uplink.py:22 |
| `Network\|Device:{device}\|Status` | P | `"Connected" if pnic.linkSpeed else "Disconnected"` | host_uplink.py:23 |

Note: `host_install_date.py:24` also emits a CRITICAL **event** on
failure to read install date — see Events / TOOLSET GAP #1.

### VirtualMachine (foreign VMWARE — stitched)

| Key (`vCommunity\|...`) | Type | vim25 source | Source file:line |
|---|---|---|---|
| `Snapshot\|Count` | M | recursive walk of `snapshot.rootSnapshotList` (0 if none) | vm_snapshot_metrics.py:12-31; vmConfigs.yaml:1-3 |
| `Options\|{configPath}` | P | per-key `getattr` walk over config-list paths (e.g. `config.latencySensitivity.level`, `config.nestedHVEnabled`) | vmConfig.py:11-20; vmConfigs.yaml:4-9 |
| `Configuration\|Advanced Parameters\|{key}` | P | `config.extraConfig` filtered to config-list keys | vm_extra_config.py:11-14 |
| `Configuration\|SCSI Controllers\|Count` | M | count of `VirtualSCSIController` devices | vm_scsi_controller_type.py:24 |
| `Configuration\|SCSI Controllers:{busNumber}\|Type` | P | friendly device type (PVSCSI / LSI SAS / LSI Parallel / BusLogic) | vm_scsi_controller_type.py:40 |
| `Guest OS\|Services:{displayName}\|Service Name` | P | guest PowerShell CSV (`getWindowsServices.ps1`) | vmService.py:159 |
| `Guest OS\|Services:{displayName}\|Service Status` | P | guest CSV `Status` | vmService.py:160 |
| `Guest OS\|Services:{displayName}\|Service Start Type` | P | guest CSV `StartType` | vmService.py:161 |
| `Guest OS\|Operating System\|OS Name` | P | guest CSV (`getWindowsOSInformation.ps1`) `Name` | vmOSInformation.py:171 |
| `Guest OS\|Operating System\|OS Version` | P | guest CSV `Version` | vmOSInformation.py:172 |
| `Guest OS\|Operating System\|OS BuildNumber` | P | guest CSV `BuildNumber` | vmOSInformation.py:173 |
| `Guest OS\|Operating System\|OS Architecture` | P | guest CSV `OSArchitecture` | vmOSInformation.py:174 |
| `Guest OS\|Operating System\|OS Last Boot Up Time` | P | guest CSV `LastBootUpTime` | vmOSInformation.py:175 |
| `Guest OS\|Operating System\|OS Release ID` | P | guest CSV `ReleaseId` | vmOSInformation.py:176 |

VM events: Windows event-log entries pushed as per-VM **events** with
criticality mapped from the guest event Level — see Events.

> NOTE on the original adapter.py describe block (lines 158-216): it
> declares additional groups (`config.createDate`-based `Summary|VM Age`
> in vmConfigs.yaml:10-12) that have no live collector emitting them in
> the current source. **RULE-002: only port keys with a tracing
> collector line.** `Summary|VM Age` IS emitted indirectly (it's a
> vmConfigs.yaml `Config` path consumed by `collect_vm_config_properties`
> as an `Options|...` key, NOT a `Summary|` key) — the `Summary|VM Age`
> describe entry is dead. Do **not** emit `vCommunity|Summary|VM Age`;
> it is not produced by any collector. **OPEN-7 RESOLVED — dropped**
> (user confirmed; if VM Age is ever wanted it is a new small collector,
> not a parity item).

## Guest-ops subsystem (Windows)

The single biggest piece. Native Java port of the three guest-ops
collectors (`vmService.py`, `vmOSInformation.py`,
`collect_windows_event_logs.py`), all built on
`GuestOperationsManager` in vim25:

1. **Gate** (vmService.py:131): only run when
   `vm.guest.toolsStatus == "toolsOk"` AND
   `vm.guest.guestFamily == "windowsGuest"`. Skip all others silently.
2. **Credentials**: `NamePasswordAuthentication(winUser, winPass)`
   from the **Windows Guest Credential** kind (see Credential design).
   If that credential is unset or `winUser` is blank, skip guest-ops
   entirely (do not fail the cycle). Which guest-ops collectors run is
   gated by the `Windows Monitoring` enum: `Services` →
   service collector, `Event Logs` → event-log collector,
   `Services + Event Logs` → both, `Disabled` → neither.
3. **File transfer**: `fileManager.CreateTemporaryDirectory` →
   `InitiateFileTransferToGuest` (returns a PUT URL) → HTTP PUT the
   `.ps1` script bytes. In Java: use the framework HTTP client with
   `platformSsl` (vCenter cert pre-approved). The bundled `.ps1`
   scripts (`getWindowsServices.ps1`, `getWindowsOSInformation.ps1`,
   `getWindowsEventLogs.ps1`) ship as **adapter resources** in the pak.
4. **Run-in-guest**: `processManager.StartProgram` with
   `powershell.exe -Command "& '<script>' ... | Export-Csv ..."` →
   poll `ListProcessesInGuest` for `exitCode != null`.
5. **Read output**: `InitiateFileTransferFromGuest` → HTTP GET the URL
   → parse CSV.
6. **Cleanup**: `finally { DeleteDirectoryInGuest(..., recursive) }`.

### Failure isolation (binding — crash-the-cycle concern)

The original isolates per-VM with broad `try/except` and a `finally`
cleanup; one unreachable guest logs and continues. **The Java port MUST
do the same: every per-VM guest-ops call wrapped so any exception
(timeout, auth failure, tools absent, PUT/GET failure) is caught,
logged at WARN, and the loop continues.** A single unreachable or
mis-credentialed guest must never abort the collection cycle or the
property push for other VMs/hosts/clusters. This is the highest-risk
area for a "crash-the-cycle" regression — call it out in review.

Guest-ops opt-in is per-adapter-instance via the `Windows Monitoring`
enum (not per-VM in the original). Per-VM scoping is **deferred to v2**
(OPEN-3 RESOLVED) — v1 mirrors the original's "all Windows VMs when
enabled" behavior.

## Credential / config design

### Credentials (TWO credential kinds)

**1. vCenter Credential** (required, the primary credential kind):
- `user` — vCenter User Name (string, required)
- `password` — vCenter Password (password, required)

**2. Windows Guest Credential** (optional, a *second* `CredentialKind`):
- `winUser` — Windows User Name (string)
- `winPass` — Windows Password (password)

**Decision (changed from the prior draft):** Windows creds are a
**separate `CredentialKind`**, not optional fields bolted onto the
vCenter credential. Rationale: guest-ops is an opt-in subsystem with a
distinct trust boundary (a Windows domain/local account, often managed
by a different team than the vCenter SSO account); a dedicated
credential kind lets the operator leave it unset cleanly and lets VCF
Ops credential management treat the two independently. If the Windows
Guest Credential is unset (or `winUser` blank) while `Windows Monitoring`
is anything other than Disabled, log a clear WARN and skip guest-ops
(do not fail Test/Collect).

### Adapter-instance parameters (the UI collapses to a short form)

The adapter-instance UI is exactly:

| Field | Type | Notes |
|---|---|---|
| Name | string | adapter instance name |
| vCenter Server | string, required | FQDN/IP (`host`) |
| vCenter Credential | CredentialKind ref, required | the vCenter Credential above |
| Windows Monitoring | **enum**, default `Disabled` | `Disabled` \| `Services` \| `Event Logs` \| `Services + Event Logs` — replaces the original's two boolean toggles |
| Windows Guest Credential | CredentialKind ref, optional | the Windows Guest Credential above |
| **Advanced:** ESXi Advanced System Settings Config File (`esxi_adv_settings_config_file`) | string, optional, default `esxi_advanced_system_settings` | central config-store file NAME (no path, no `.xml`). See Config design. |
| **Advanced:** ESXi Software Packages Config File (`esxi_vib_driver_config_file`) | string, optional, default `esxi_packages` | central config-store file NAME. |
| **Advanced:** VM Advanced Parameters Config File (`vm_adv_settings_config_file`) | string, optional, default `vm_advanced_parameters` | central config-store file NAME. |
| **Advanced:** VM Options Config File (`vm_configuration_config_file`) | string, optional, default `vm_options` | central config-store file NAME. |
| **Advanced:** Windows Service Configuration File (`win_service_config_file`) | string, optional, default `windows_service_list` | central config-store file NAME. |
| **Advanced:** Windows Event Log Configuration File (`win_event_config_file`) | string, optional, default `windows_event_list` | central config-store file NAME. |
| **Advanced:** port | int, default 443 | vCenter port |

**Single-line strings / enums / int only.** describe.xml has **no
multiline string type** — this is the hard constraint that killed the
per-instance delimiter-string config approach. The six config-file fields
above are single-line file NAMES (not contents), so the constraint is
satisfied; the file bodies live in the central config-file store. See
Config design below.

The `Windows Monitoring` enum maps to the two internal guest-ops
subsystems: `Services` enables the service collector
(`vmService.py` port); `Event Logs` enables the Windows event-log
collector (`collect_windows_event_logs.py` port);
`Services + Event Logs` enables both; `Disabled` runs neither.

## Config design (OPEN-4 — RESOLVED: central config-file store, pure rewrite)

> **Fidelity correction (supersedes the prior on-collector / `custom_config_dir`
> draft).** Re-inspection of the original
> (`app/adapter.py` `get_config_file_data`, ~line 261) proved the prior
> design rested on a wrong assumption: nothing lives on any collector.
> The original stores the six check-list XMLs **CENTRALLY** in the VCF Ops
> configuration-file store and fetches each by name through the Suite API
> **every collection cycle**:
> `GET api/configurations/files?path=SolutionConfig/<fileName>.xml` via
> `adapter_instance.suite_api_client` (adapter.py:262-273). The six
> adapter-instance identifiers hold file **NAMES only**. This rewrite
> reproduces that path exactly.

The six XML check-lists gate WHICH advanced settings / VIBs / VM params /
services / event IDs are collected (collection is opt-in to keep the
property explosion bounded — the `esxi_advanced_system_settings.xml`
reference file alone lists hundreds of settings, all commented out by
default).

**Resolved design (byte-identical files, central store, fetched per cycle):**

- **The six check-list files ship in the pak at
  `content/files/solutionconfig/*.xml`** — the **verbatim, byte-identical**
  originals (verify subdirectory placement against
  `lessons/pak-content-bundling.md`; the original ships them under
  `content/files/solutionconfig/` and they import into the central store at
  the `SolutionConfig/` path). At pak install these are imported into the
  VCF Ops **central configuration-file store** (the `SolutionConfig/` path),
  NOT distributed to any collector. As in the original, the shipped files
  have everything commented out → the default active check-list is empty by
  design; the adapter collects nothing in those categories until an admin
  edits a file centrally and uncomments entries.

- **Six optional single-line file-NAME identifiers** (replacing the deleted
  `custom_config_dir`), keeping the original's identifier key names verbatim
  for pure-rewrite fidelity, each defaulted to the bundled file's base name:

  | Identifier key (verbatim) | Default | Consumer | Keys gated |
  |---|---|---|---|
  | `esxi_adv_settings_config_file` | `esxi_advanced_system_settings` | host_advanced_settings.py | `Configuration\|Advanced System Settings\|{key}` |
  | `esxi_vib_driver_config_file` | `esxi_packages` | host_software_packages.py | `Configuration\|Packages:{name}\|*` |
  | `vm_adv_settings_config_file` | `vm_advanced_parameters` | vm_extra_config.py | `Configuration\|Advanced Parameters\|{key}` |
  | `vm_configuration_config_file` | `vm_options` | vmConfig.py | `Options\|{configPath}` |
  | `win_service_config_file` | `windows_service_list` | vmService.py | `Guest OS\|Services:{name}\|*` |
  | `win_event_config_file` | `windows_event_list` | collect_windows_event_logs.py | (event filter, passed to the .ps1) |

  Admins customize by uploading/editing files centrally (Administration →
  Configuration Files UI, or the configurations API) and pointing an
  instance's field at the alternate file name. Blank/default → the bundled
  file is used. Because the files live in the central store (not in the pak
  install path on disk), a pak upgrade re-imports the shipped defaults but
  does not clobber an admin-renamed custom file.

- **Java adapter fetches the named files via Suite API each cycle.** Author
  obligations:
  - **Use the framework's existing Suite API channel** — the same one
    `SuiteApiStitcher` already uses for property/stat push. Do NOT stand up
    a new HTTP client. See `lessons/foreign-resource-property-push.md` and
    `lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`. The fetch is
    `GET api/configurations/files?path=SolutionConfig/<name>.xml`; parse the
    XML body and split the comma-delimited check list exactly as
    `get_config_file_data` does (adapter.py:266-273).
  - **EMPIRICAL VERIFY:** Suite API reachability/credentials when the
    instance is hosted on a **remote collector or cloud proxy**. The SDK
    injects the Suite API connection — **do not assume localhost.** The
    original works this way in production, which proves the platform path
    exists; the author must confirm the injected client resolves and
    authenticates from a non-localhost collector during v1 development.
  - **Cache last-good parsed config in adapter memory.** A transient Suite
    API failure (or the first-cycle null Suite API client) must degrade to
    the **previous cycle's** parsed config, not to empty check lists. **Never
    silently collect with empty lists** on a fetch failure — log it (WARN)
    and raise an adapter-instance notice. On the very first cycle with no
    cached config and an unreachable store, skip the gated collection for
    that cycle rather than blanking it; the next cycle catches up.

- **`test()` / Validate Connection reports loaded-config feedback** —
  per-file fetched + parsed check counts (e.g. "esxi advanced settings: 12
  keys; windows services: 4; vm options: 0 …") so a misnamed or missing
  central file is **never silent**. If a named file is absent/unreadable in
  the store, `test()` reports it explicitly.

This is a true pure rewrite of the original config path: same central store,
same Suite API fetch, same `SolutionConfig/<name>.xml` layout, same
identifier keys, and byte-identical default XMLs. It is **not** modeled on
the compliance adapter's on-collector `custom_profile_path` — that precedent
was the wrong analogy and is dropped.

## Events

| Event | Severity | Condition | Object | Source |
|---|---|---|---|---|
| Windows event-log entry | INFO/WARNING/IMMEDIATE/CRITICAL (mapped from guest Level) | guest event matching the configured event-ID list, when `Windows Monitoring` includes Event Logs | VirtualMachine (foreign) | collect_windows_event_logs.py:168-190 |
| Host install-date read failure | CRITICAL | exception reading `imageConfigManager.installDate()` | HostSystem (foreign) | host_install_date.py:24 |

Level mapping (collect_windows_event_logs.py:168-179): Information/
Verbose→INFO, Warning→WARNING, Error→IMMEDIATE, Critical→CRITICAL.
Events use `auto_cancel=True, watch_wait_cycle=1, cancel_wait_cycle=3`.

### TOOLSET GAP #1 — foreign-resource EVENT push (likely first gap)

**Status: unproven. Flag for empirical verification by the author —
do not hand-wave as solved.** Staged plan ACCEPTED by the user
(OPEN-2 RESOLVED): attempt the real event push first; if it cannot be
proven during v1 development, degrade to property representation for v1
and prove real events in v1.1. Keep this TOOLSET GAP framing for the
author — the gap is real and must be surfaced, not silently absorbed.

The framework `SuiteApiStitcher` facade exposes `pushProperties` and
`pushStats` (both proven by the compliance adapter) but **no event /
notification push**. The underlying `SuiteApiStitchClient` has a
private `rawPost(apiPath, body, token)` and token acquire/release, so a
`pushEvents` method is constructible against a Suite API events
endpoint — but the wire format and endpoint for posting an event onto a
foreign resource is **not yet established in the factory** and is
unverified on this instance.

This mirrors a known platform reality: `pak-install-reliability` notes
events are a recurring trouble spot, and the ARIA_OPS pak path strips
events at build because the runtime format is unknown. For a Tier 2
SDK pushing onto foreign resources, the event path is genuinely new
ground.

**Author's task (empirical):**
1. Determine the Suite API endpoint + JSON body to post an event/alert
   notification onto a resource UUID (candidate: `POST /api/events` or
   the alerts/notification API; verify against the live devel
   instance).
2. If a clean path exists, add `SuiteApiStitcher.pushEvents(...)` to
   the framework (via `tooling`) and wire the two event producers.
3. **If no clean path can be proven during v1 development** (the
   user-accepted degradation), degrade gracefully: emit the Windows
   event-log findings and install-date failures as **properties** (e.g.
   `vCommunity|Guest OS|Last Event|...` /
   `vCommunity|Configuration|Install Date|Read Error`) and/or as health
   events on the `vCommunityWorld` anchor, and file the gap. Properties
   are proven, visible, and **alertable** (a symptom/alert can fire on
   the property value); this preserves operational visibility without
   blocking the build. **Do NOT silently drop the events** — surface
   them as properties and document the degradation. Real foreign-resource
   events are then a **v1.1** deliverable once the push path is proven.

This is the **expected first TOOLSET GAP** of the build. Budget for it.
The staged real-first / property-fallback / v1.1-real plan is
user-accepted (OPEN-2 RESOLVED).

## Content port plan (~100 artifacts → factory YAML)

Strengthening this pipeline is a co-equal goal. **All ported content
keeps `vCommunity|...` attribute paths verbatim** and resource kind
`VMWARE / ClusterComputeResource|HostSystem|VirtualMachine`.

### Inventory (from `reference/references/.../content/`)
| Type | Count | Source dir | Factory loader | Status |
|---|---|---|---|---|
| Super metrics | 57 | `supermetrics/*.json` | `vcfops_supermetrics` | **Partial** — see GAP #2 |
| Dashboards | 13 | `dashboards/*.json` (incl. 1 in `To be used in reports/`) | `vcfops_dashboards` | **Partial** — see GAP #3 |
| Reports | ~22 | `reports/Report*.xml`, `*vCommunity.xml`, `ESXi*.xml` | `vcfops_reports` | **Gap-heavy** — see GAP #4 |
| Views | ~9 | `reports/View*.xml` + view-shaped report XML | `vcfops_reports` (views co-located) | **Gap-heavy** — see GAP #4 |
| Symptoms | 2 | `symptomdefs/*.xml` | `vcfops_symptoms` | **Partial** — see GAP #5 |
| Alerts | 3 | `alertdefs/*.xml` | `vcfops_alerts` | **Partial** — see GAP #5 |
| Resources / traversal | 2 | `resources/`, `traversalspecs/` | none | **GAP #6 — DROPPED (OPEN-6 resolved)** |

### Port pipeline (per artifact)
Source export format (UUID-keyed JSON / vendor XML) → **factory YAML as
canonical source** → factory renderer emits pak `content/` tree. The
factory YAML is the deliverable-of-record (the prompt's explicit
"break dashboards into YAML as references" goal); the rendered
pak-tree files are build output.

### Content gaps (map of what the loaders can/can't do today)

**GAP #2 — Super metric UUID cross-references.** The SM JSONs are
UUID-keyed and reference *other* SMs by `sm_<uuid>` inside formulas
(e.g. `Cluster Performance.json` references nine `sm_<uuid>` SMs). The
factory SM loader resolves `@supermetric:"<name>"` → `sm_<uuid>` at
validate time, but the source uses raw UUIDs. **Port task:** build a
UUID→name map across all 57 JSONs, rewrite intra-formula `sm_<uuid>`
refs to `@supermetric:"<name>"` in the factory YAML. Watch for
duplicate/overlapping SM names (the source has near-duplicate names:
`Cluster Performance` vs `vSphere Cluster Performance` vs
`vSphere Clusters Performance` — keep all three distinct). Cross-check
against `unifi-metric-key-parity` (MPB derives keys from labels) — for
SMs the factory loader is name-driven, so name uniqueness is the
constraint.

**GAP #3 — Dashboard widget format.** 13 dashboards in vendor JSON
(VCF Ops export shape), not factory dashboard YAML. The factory
dashboard loader/renderer expects factory YAML widgets. **Port task:**
transcode each dashboard's widget set (ResourceList pickers, view
embeds, interaction wiring, heatmaps) to factory YAML. Watch
`heatmap-empty-groupby-crashes-renderer` (heatmaps need the 9-key
self-grouping block; AlertList needs `pin_to_world`). Several
dashboards embed views → those views must be ported first
(bottom-up). One dashboard lives under `To be used in reports/` — it's
a report-input dashboard; port it (OPEN-5 RESOLVED — port everything).

**GAP #4 — Report & view XML (highest gap risk).** ~22 reports +
~9 views in vendor XML (`reportSchema`/`viewSchema`). Reports are noted
in `reference_sources.md` as "not yet a first-class authoring target."
The factory has `vcfops_reports`, but the source XML is the VCF Ops
report-definition schema, not factory report YAML. Per
`pak-content-bundling`, views go in `content/reports/` in the pak tree
(not `content/views/`). Per `pak-content-localization-bundles`,
dashboards/views need four localization bundles with exactly-matching
`localizationKey`s — a known multi-build trap. **This is the largest
single porting gap.** Recommend: port the views first (they back the
dashboards and reports), then reports. **Scope (OPEN-5 RESOLVED): port
ALL ~22 reports + ~9 views, including the generic "Report - VOA - *"
set** — the user wants "as close to a pure rewrite as possible," so the
generic vSphere-assessment reports are in scope for v1 even though they
do not consume `vCommunity|` augmented properties. Mark the VOA set as a
**candidate for trimming in a later release** ("(for now)") — but v1
ports everything.

**GAP #5 — Symptom & alert XML.** 2 symptoms
(`ESXi Host NIC Disconnected`, `Windows Service Down`), 3 alerts
(`ESXi Host License Expiring`, `ESXi Host NIC Disconnected`,
`Windows Service Down`). Vendor `symptomDefinition`/`alertDefinition`
XML → factory `vcfops_symptoms`/`vcfops_alerts` YAML. `SymptomSets`
needs ≥2 children (`pak-content-bundling`). These reference
`vCommunity|` keys (NIC `Status`, service `Service Status`) and the
`Remaining Days` licensing metric — keep refs verbatim. The "Windows
Service Down" alert depends on guest-ops being enabled to have data.

**GAP #6 — traversalspecs / resources XML. OPEN-6 RESOLVED — dropped.**
`traversalspecs/` is empty (schema only) and `Cluster_VIB_Content.xml`
is a resource-import artifact with no factory loader; both are
**dropped** for v1 per user decision. No dashboard hard-dependency
surfaced. If a future dashboard needs `Cluster_VIB_Content`, it is a
follow-up, not a v1 parity item.

### Content port sequencing (bottom-up, RULE-011 for dashboards)
1. Super metrics (57) — resolve UUID refs → names.
2. Views (~9) — back dashboards + reports.
3. Symptoms (2) → Alerts (3).
4. Dashboards (13) — wireframe-approval gate per RULE-011 before each.
5. Reports (all ~22, incl. the VOA set) — last (depend on views).

The author should treat the content port as a **second, separable
work-stream** from the Java collector. The collector can ship and
DATA_RECEIVE before all content is ported; content lands incrementally.

## Naming / collision check (recon-confirmed)
- Adapter kind `vcfcf_vcommunity` — no collision (original is
  `VCFOperationsvCommunity`; recon: neither installed).
- Content names: recon found zero collisions across dashboards/SMs/
  views/reports/symptoms/alerts. The originals' `... 2.0` suffixes keep
  them distinct from built-ins ("ESXi Configuration", "VM Performance",
  "VM Capacity", "VM Details (NSX)"). **Preserve the `2.0` suffixes
  verbatim** — do not "clean them up."

## Attribution
- MP description (`adapter.yaml`): credit Onur Yuzseven /
  `vmbro/VCF-Operations-vCommunity`, CC license, "native Java SDK
  rewrite of the Python Integration SDK management pack."
- Every ported content artifact's `description`: cite
  `vmbro/VCF-Operations-vCommunity/Management Pack/content/<file>` per
  `context/reference_sources.md` rule 3.
- Per-file Python copyright headers credit both Onur Yuzseven and
  Scott Bowe (some collectors, e.g. `host_install_date.py`,
  `vm_scsi_controller_type.py`) — preserve dual attribution where the
  source shows it.

## Key Risks

1. **Event push is unproven (TOOLSET GAP #1).** Expected first gap.
   Mitigation: property-degradation fallback; do not block the build.
2. **Guest-ops crash-the-cycle.** Per-VM failure isolation is
   mandatory; one unreachable Windows guest must not abort the cycle.
   Highest-risk Java regression. Review-gate it.
3. **Content port is the bulk of the effort (~100 artifacts) and the
   loaders have known gaps** (reports/views XML, SM UUID refs,
   localization bundles). Budget content as a separable workstream;
   collector can ship first.
4. **First-cycle null Suite API client** (foreign-resource-property-push
   lesson) — guard and skip the push on cycle 1.
5. **vim25 in Java** — the compliance adapter uses a hand-rolled
   `EsxcliSoapClient`/`VCenterApiClient`, not full pyVmomi-equivalent
   managed-object traversal. Guest-ops (`GuestOperationsManager` file
   transfer + run-in-guest) is a substantially larger vim25 surface
   than compliance exercises. Confirm the SOAP client can reach
   `guestOperationsManager`, `licenseManager`, `imageConfigManager`,
   `EvcManager` — these may each be a mini-gap. Verify empirically.
6. **`Summary|VM Age` dead key** — declared in describe but not
   emitted; do not port (RULE-002). Dropped (OPEN-7 resolved).

## OPEN Questions

### Remaining

**None.** All design questions are resolved; the design is approved and
ready for `sdk-adapter-author`.

### Resolved (decisions log)

- **OPEN-5 (report/view scope) — RESOLVED:** port **ALL** ~22 reports +
  ~9 views, **including the generic "Report - VOA - *" set.** User
  rationale (verbatim, prompt-of-record): "we want to make this as close
  to a pure rewrite as possible so include them, as well as the config
  file/defaults behavior (for now)." Note the **"(for now)"** — the VOA
  set (generic vSphere-assessment reports not tied to `vCommunity|`
  keys) is a **candidate for trimming in a later release**, but v1 ports
  everything. See GAP #4 + content port sequencing.

- **OPEN-1 (adapter kind) — RESOLVED:** `vcfcf_vcommunity`, side-by-side
  with the original. The same-identity classic-over-container upgrade is
  **experimentally confirmed non-viable** (silent split-brain,
  `context/investigations/vcommunity_upgrade_path_experiment.md`).
  Migration = uninstall-old → install-ours → recreate
  instances/credentials; `vCommunity|` key continuity preserves metric
  history as a convenience, not a contract. See "Migration from the
  original MP."
- **OPEN-2 (event push) — RESOLVED:** staged plan ACCEPTED — attempt
  real foreign-resource event push first (TOOLSET GAP #1); if unprovable
  during v1 development, degrade to property representation (visible,
  alertable, never silently dropped) and prove real events in v1.1.
- **OPEN-3 (guest-ops scoping) — RESOLVED:** per-VM scoping deferred to
  v2; v1 mirrors the original ("all Windows VMs when enabled").
- **OPEN-4 (config UX) — RESOLVED (fidelity-corrected to a pure rewrite):**
  no per-instance delimiter-string fields. The original stores the six
  check-list XMLs **CENTRALLY** in the VCF Ops configuration-file store and
  fetches them by name via Suite API every cycle (adapter.py
  `get_config_file_data`, ~line 261). This rewrite reproduces that exactly:
  six byte-identical default XMLs ship in `content/files/solutionconfig/`
  → imported into the central store at install; six optional single-line
  file-NAME identifiers (original keys verbatim:
  `esxi_adv_settings_config_file`, `esxi_vib_driver_config_file`,
  `vm_adv_settings_config_file`, `vm_configuration_config_file`,
  `win_service_config_file`, `win_event_config_file`), each defaulted to the
  bundled file's base name; the Java adapter fetches the named files via the
  framework's existing Suite API channel each cycle and caches last-good
  parsed config. The `custom_config_dir` / on-collector-override-file design
  is **deleted** — it was based on a wrong assumption (nothing lives on a
  collector). `test()` reports per-file fetched/parsed check counts.
  EMPIRICAL VERIFY: Suite API reachability from a remote collector / cloud
  proxy (SDK injects the connection; do not assume localhost). See "Config
  design."
- **OPEN-6 (traversal/resources) — RESOLVED:** dropped for v1
  (empty traversalspecs + no-loader `Cluster_VIB_Content.xml`).
- **OPEN-7 (`Summary|VM Age`) — RESOLVED:** dead key dropped (no
  collector emits it).
- **OPEN-8 (own icon) — RESOLVED:** `default` icon for the
  `vCommunityWorld` anchor; no branded SVG in v1.
```
