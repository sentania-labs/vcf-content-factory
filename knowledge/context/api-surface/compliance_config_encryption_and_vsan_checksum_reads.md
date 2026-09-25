# Compliance adapter: config-encryption and vSAN checksum reads (why unreadable, what to read instead)

**Date:** 2026-09-23 (investigation ~4:20 to 4:45 PM CDT)
**Investigator:** api-explorer
**Instance:** devel `vcf-lab-operations-devel.int.sentania.net` (VCF Ops 9.1), compliance pak 0.0.0.69, profile SCG 9.1.
Hosts ESX 9.1.1 (`config|product|apiVersion = 9.1.1.0` on all 9), vCenter 9.1.1.
**Posture:** read-only. Root SSH to the appliance for `ls`/`grep`/`cat` of adapter logs and a
read-only copy of three binding jars off-box for `javap`. Suite API `GET`s only (devel profile).
No vCenter or ESX access (the factory environment holds no vCenter credential; the adapter's
vCenter credential is stored encrypted inside VCF Ops and was deliberately not extracted).
Nothing created or modified anywhere.

Controls in scope: `esx.tpm-configuration`, `esx.secureboot-enforcement`,
`esx.tpm-trusted-binaries` (HostSystem), `cluster.object-checksum` (ClusterComputeResource).

---

## TL;DR

| Control | Root cause | Evidence level | Recommended read |
|---|---|---|---|
| `esx.tpm-configuration` | `config.encryptionState` **does not exist** in vim25. `HostConfigInfo` has no such field; the data lives at `HostRuntimeInfo.stateEncryption` (since vSphere 7.0 U3). | Evidence (type model + live unreadable on 8/8 healthy hosts) | `esxcli:system.settings.encryption.get:Mode` (preferred) or `scalar:runtime.stateEncryption.protectionMode` |
| `esx.secureboot-enforcement` | same | Evidence | `esxcli:system.settings.encryption.get:RequireSecureBoot` or `bool:runtime.stateEncryption.requireSecureBoot` |
| `esx.tpm-trusted-binaries` | same, plus the leaf name is also wrong (`requireExecuteInstalledOnly` vs vim25 `requireExecInstalledOnly`) | Evidence | `esxcli:system.settings.encryption.get:RequireExecutablesOnlyFromInstalledVIBs` or `bool:runtime.stateEncryption.requireExecInstalledOnly` |
| `cluster.object-checksum` | The vim25 field exists (`VsanClusterConfigInfoHostDefaultInfo.checksumEnabled`) but vCenter 9.1.1 does **not populate it**: the sibling `autoClaimStorage` in the same `defaultConfig` element reads `false` on all 3 clusters, `checksumEnabled` is null on all 3. SCG 9.1's audit point is a per-storage-policy SPBM attribute, not a cluster field. | Evidence for "sibling reads, this leaf is null"; inference for "vCenter never sets it on 9.x" (no raw SOAP captured) | **Cannot be read by this adapter** (needs an SPBM/pbm reader, or ESA detection plus a policy walk). Demote to manual audit. Also: its `expected_value=false` is polarity-inverted. |

Separate defect found on the way (**evidence**): the vSAN presence gate
(`VSphereClient.hasVsanConfig`) tests only that `configurationEx.vsanConfigInfo` *exists*.
vCenter returns that element on non-vSAN clusters too, so the gate never says "non-vSAN":
`wld01-cl01` and `wld02-cl01` (iSCSI + NFS datastores only, no vSAN datastore) are scored on
vSAN controls, and `cluster.managed-disk-claim` records a **false pass** (`Actual=false`,
expected `false`) on both.

---

## 1. Adapter log evidence (devel)

Logs: `/usr/lib/vmware-vcops/user/log/adapters/ComplianceAdapter/ComplianceAdapter_{5379,5381,5382}.log`
(5379 = vcf-lab-mgmt vCenter, 5382 = vcf-lab-wld02, 5381 = wld01/stitcher traffic).

**The adapter never logs the per-control reason.** No line in any current log mentions
`encryptionState`, `checksum`, `vsanConfigInfo`, or the four control ids. The reader swallows
the cause by design: `readVimProperties` catches every exception and maps null to
`UNREADABLE`, and `post()` returns null on a SOAP fault (HTTP 500) without logging the fault
string. The only surfaced signal is an aggregate count. Latest cycle, verbatim
(21:13Z = **4:13 PM CDT today**):

```
2026-09-23T21:13:26.212Z WARN  ComplianceAdapter 6190 [... instanceId="5379"] [(5379) com.vcfcf.adapters.compliance.ComplianceAdapter.logWarn] - 24 control instance(s) could not be read this cycle (declared-but-unreadable). They count as failing in each object's score, each affected object is non-compliant, and its "Compliance data not collected" alert fires.
2026-09-23T21:13:22.279Z WARN  ComplianceAdapter 6190 [... instanceId="5382"] [(5382) com.vcfcf.adapters.compliance.ComplianceAdapter.logWarn] - 12 control instance(s) could not be read this cycle (declared-but-unreadable). They count as failing in each object's score, each affected object is non-compliant, and its "Compliance data not collected" alert fires.
```

and the profile-level variant (16:21Z = 11:21 AM CDT today):

```
2026-09-23T16:21:28.602Z WARN ... [(5379) ...ComplianceAdapter.logWarn] - Profile 'VMware_SCG_9.1' declares 24 vim_property control instance(s) this adapter could not read this cycle (declared-but-unreadable). These are excluded from every compliance score. This is a coverage signal, not non-compliance.
```

(The two messages disagree on whether unreadables count against the score; the first matches
build-63 behaviour. Cosmetic, noted for the author.)

**Negative evidence for the vSAN gate:** the string `has no vsanConfigInfo` (logged by
`ComplianceAdapter.probeVsan` whenever the gate says "non-vSAN") appears **0 times** across
all three current logs, although two of the three clusters are not vSAN (section 4).

The per-control outcome is visible in the pushed properties instead (Suite API, devel):

- All 9 HostSystems: `VCF-CF Compliance|VMware_SCG_9.1|esx.{tpm-configuration,secureboot-enforcement,tpm-trusted-binaries}|Actual = (unreadable)`.
  8 of the 9 hosts are otherwise healthy (lockdown, esxcli rows etc. all read).
  `vcf-lab-wld01-esx02` reads `(unreadable)` on **every** control this cycle, so it is not
  evidence for this specific defect.
- All 3 clusters: `cluster.managed-disk-claim|Actual = false`, `cluster.object-checksum|Actual = (unreadable)`.

## 2. Code path (adapter HEAD, build 73)

Note: `CANONICAL_SCHEMA.md` line 236 still says "PropertyCollector + reflective getter walk".
That is stale. Since the raw-SOAP rewrite the walk is over the **response DOM by element
local-name** (`VSphereClient` class javadoc, lines 50 to 55). The logic is the same.

For `scalar:<p>` / `bool:<p>` (`readScalarRecipe` / `readBoolRecipe` -> `walkToNode`):

1. Split the path on `.`.
2. `getLongestPrefixElement`: issue one `RetrieveProperties` per prefix, **longest first**,
   single object, single `pathSet`, until one returns a `<propSet><val>`. For
   `config.encryptionState.mode` that is three round trips:
   `config.encryptionState.mode` (fault: InvalidProperty, since the field is not on the type)
   -> `config.encryptionState` (fault) -> `config` (returns the **entire HostConfigInfo**).
3. Walk the remaining segments with `firstDirectChild(node, localName)`. `<config>` has no
   `<encryptionState>` child, so null.
4. null -> `UNREADABLE` in `readVimProperties`.

Cost side-effect: each of the three host controls pulls the whole `HostConfigInfo` (hundreds
of KB on a real host) every cycle, so nine full-config fetches per host per cycle are spent
producing nothing.

For `bool:configurationEx.vsanConfigInfo.defaultConfig.checksumEnabled`: prefixes down to
`configurationEx` fault or are absent (the declared type of `configurationEx` is
`ComputeResourceConfigInfo`, so deeper paths are not valid PropertyCollector paths);
`configurationEx` returns a `ClusterConfigInfoEx`; DOM walk
`vsanConfigInfo -> defaultConfig -> checksumEnabled`. The identical walk for
`autoClaimStorage` succeeds, so `defaultConfig` is present and only the `checksumEnabled`
element is missing.

**Unreadable vs absent**, as implemented:

- *absent / skipped*: control has no `read_recipe` (or is not `vim_property`/`esxcli`). Not counted.
- *unreadable*: recipe present, but any of: SOAP fault, every prefix fails, a DOM segment is
  missing, leaf text empty, a bool leaf that is not `true`/`false`, unknown style, esxcli
  `COMMAND_FAILED`, esxcli field missing from the result struct. There is no distinction
  between "the path is wrong", "the field is optional and unset", and "the call failed".
- A whole-object fold to unreadable also happens when the host is not `connected` or the
  cluster vSAN probe throws.

**vSAN gate** (`ComplianceAdapter.collectVimObject` -> `probeVsan` -> `VSphereClient.hasVsanConfig`):
`true` iff `configurationEx` has a direct child `vsanConfigInfo`. It does not read
`vsanConfigInfo/enabled`.

**Evaluator:** `ControlEvaluator.valuesMatch` is case-insensitive, so a vim25 enum `tpm` or
an esxcli `TPM` both match `expected_value=TPM`.

**API version negotiation (ruled out as the cause):** `VSphereClient.post` sends
`SOAPAction: urn:vim25/<Method>` with no version, so which schema version vCenter serves
is not pinned. Evidence it is at least 7.0.2: `vm.ft-encrypted` reads
`config.ftEncryptionMode` (a field annotated `@versionClass v7_0_2_0` in the 8.0.2 bindings)
successfully on 69 of 69 VMs (`ftEncryptionOpportunistic`). `stateEncryption` is
`v7_0_3_0`, one step newer, so there is a small residual risk it is filtered; the first cycle
after a vim25-path fix settles it. The esxcli channel is unaffected (it pins
`version=urn:vim25/5.0` for `ExecuteSoap`, and the esxcli result is not vim25-versioned).

## 3. vim25 type facts (from `vim-vmodl-bindings-8.0.2.jar`, the newest binding on the appliance)

Source: `javap` of classes in
`/usr/lib/vmware-vcops/user/plugins/inbound/vmwarevi_adapter3/lib/vim-vmodl-bindings-8.0.2.jar`.

- `vim.host.ConfigInfo` (HostConfigInfo): **no** `encryptionState`, no `encryption*` field of
  any kind. Crypto-adjacent fields: `certificate` (bytes) only.
- `vim.host.RuntimeInfo` (HostRuntimeInfo): `cryptoState` (String), `cryptoKeyId`,
  `tpmPcrValues`, and **`stateEncryption`** of type `HostRuntimeInfoStateEncryptionInfo`.
- `HostRuntimeInfoStateEncryptionInfo` (`@versionClass v7_0_3_0`, i.e. vSphere 7.0 U3):
  - `protectionMode` : String, enum `HostRuntimeInfoStateEncryptionInfoProtectionMode` = `none` | `tpm`
  - `requireSecureBoot` : Boolean (optional)
  - `requireExecInstalledOnly` : Boolean (optional)
- `vim.host.Capability`: `tpmSupported`, `tpmVersion`, `cryptoSupported`,
  `hostConfigEncryptionSupported` (useful to explain a `none` result, not to replace the reads).

Not substitutes: `runtime.cryptoState` (`incapable`/`prepared`/`safe`/`pendingIncapable`) is
the **VM-encryption host key** state, not configuration encryption. On devel it reads
`incapable` on mgmt and wld02 hosts and `safe` on wld01 hosts (VCF Ops vCenter-adapter
property `runtime|cryptoState`). `runtime.tpmPcrValues` / `config.certificate` say nothing
about the three SCG settings.

vSAN:

- `vim.vsan.cluster.ConfigInfo` (VsanClusterConfigInfo): `enabled`, `defaultConfig`,
  and (in the vmodl binding) `vsanEsaEnabled`.
- `vim.vsan.cluster.ConfigInfo.HostDefaultInfo`: `uuid`, `autoClaimStorage`, `checksumEnabled`
  (all optional).
- Everything else vSAN (encryption, operations reserve, File Services, iSCSI, ESA detail)
  is on the vSAN Management SDK endpoint (`/vsanHealth`, `VsanVcClusterConfigSystem`
  `VsanClusterGetConfig`), see `knowledge/context/investigations/2026-05-29-vsan-management-sdk-gap.md`.
  Object checksum on OSA is a **storage-policy** attribute (SPBM, `/pbm/sdk`, VSAN capability
  "Disable object checksum"), which neither vim25 nor the vSAN cluster config exposes as a
  cluster flag. SCG 9.1 text (`vcf-security-configuration-guide-91-controls.csv`, row
  `vsan-9.object-checksum`): "On vSAN ESA, object checksums are always computed and cannot be
  disabled regardless of policy. On vSAN OSA, the policy attribute is the audit point."

esxcli (vendor evidence: SCG 9.1 `tools/audit-esx-9.ps1` lines 332 and 343, and the 9.1
controls CSV remediation for `esx-9.tpm-trusted-binaries`):
`esxcli system settings encryption get` returns a get-struct with fields
`Mode` (`TPM` | `NONE`), `RequireSecureBoot` (bool), `RequireExecutablesOnlyFromInstalledVIBs`
(bool). PowerCLI `Get-EsxCli -V2` exposes esxcli struct fields under their wire names, which
is the same convention the adapter's working rows already rely on
(`LocalLogOutputIsPersistent`, `Enabled`, `LogFilteringEnabled`, `Profile`).

## 4. Cluster facts (devel)

| Cluster | Datastores (Suite API `summary|type`) | vCenter-adapter `configuration|vsanEnabled` | Compliance gate | `managed-disk-claim` Actual | `object-checksum` Actual |
|---|---|---|---|---|---|
| vcf-lab-mgmt-cl01 | `vcf-lab-mgmt-cl01-vsan` (vsan), NFS, local VMFS | Enabled | vSAN | false | (unreadable) |
| vcf-lab-wld01-cl01 | `vcf-lab-wld01-cl01-iscsi` (VMFS), NFS | (not published) | **vSAN (wrong)** | false (**false pass**) | (unreadable) |
| vcf-lab-wld02-cl01 | `vcf-lab-wld02-cl01-iscsi` (VMFS), NFS | (not published) | **vSAN (wrong)** | false (**false pass**) | (unreadable) |

Inference: vCenter 9.1.1 serialises `configurationEx.vsanConfigInfo` for every cluster with
`enabled=false` and a `defaultConfig{autoClaimStorage=false}` when vSAN is off, and never
sets `checksumEnabled` (not even on the vSAN-enabled mgmt cluster). A raw
`RetrieveProperties configurationEx` capture on one vSAN and one non-vSAN cluster would make
this evidence.

## 5. Recommendations (for the sdk-adapter-author and the normalizer owner)

### Host controls: switch to the esxcli channel (preferred)

Why esxcli over the corrected vim25 path: it is the SCG's own audit command (exact parity),
it always returns a value (`Mode: NONE` on a TPM-less host becomes an honest FAIL rather than
an UNREADABLE plus a collection alert), the channel already works on 8/8 healthy devel hosts,
and it one-shots all three fields in one command per host (the esxcli client caches per
command). vim25 `stateEncryption` and its two Booleans are all optional, so on hardware
without TPM they may be unset and would still fold to UNREADABLE.

Canonical rows (`scg_9.1.csv`, and the same control ids in `scg_9.0.csv`, `scg_8.0.csv`,
`scg_7.0.csv` where present; all four files carry `config.encryptionState`):

| control_id | parameter | parameter_kind | value_type | expected_value | read_recipe |
|---|---|---|---|---|---|
| esx.tpm-configuration | `encryption.Mode` | `esxcli` | string | `TPM` | `esxcli:system.settings.encryption.get:Mode` |
| esx.secureboot-enforcement | `encryption.RequireSecureBoot` | `esxcli` | boolean | `true` | `esxcli:system.settings.encryption.get:RequireSecureBoot` |
| esx.tpm-trusted-binaries | `encryption.RequireExecutablesOnlyFromInstalledVIBs` | `esxcli` | boolean | `true` | `esxcli:system.settings.encryption.get:RequireExecutablesOnlyFromInstalledVIBs` |

(The `parameter` values follow the `keypersistence.Enabled` precedent; any unique logical key works.)

Fallback if esxcli is unavailable for some reason, vim25 recipes (same `vim_property` kind):
`scalar:runtime.stateEncryption.protectionMode`, `bool:runtime.stateEncryption.requireSecureBoot`,
`bool:runtime.stateEncryption.requireExecInstalledOnly`. These are valid PropertyCollector
paths, so each resolves in one round trip instead of three.

What must change:
- `scripts/_compliance_normalize.py` (factory; owns the shipped rows): the three entries at
  ~lines 653 to 667 move from the vim_property table to the esxcli table (the
  `esx.key-persistence` entry at ~line 928 is the template). Then regenerate the canonical CSVs.
- `content/sdk-adapters/compliance/profiles/canonical/scg_{7.0,8.0,9.0,9.1}.csv`: the regenerated rows.
- `tests/.../ProfileSetTest.java` `ALLOWED_PATHS["HostSystem"]` (lines 236 to 238): drop the
  three `config.encryptionState.*` paths (they are not vim25 fields; review W1 in
  `knowledge/context/reviews/compliance-build-73.md` already flagged this).
- `profiles/UNAUDITED_CONTROLS.md` lines 192 and 627 reference `config.encryptionState`; update.
- No Java change is required for the esxcli route.

### `cluster.object-checksum`: cannot be read by this adapter

Because: the only vim25 candidate (`defaultConfig.checksumEnabled`) is unpopulated on 9.1.1,
and the real SCG audit point is per storage policy (SPBM) on OSA and "always on" on ESA.
Neither the pbm endpoint nor the vSAN Management SDK is on this adapter's classpath or
transport. Recommendation: demote to `manual_audit` (empty `read_recipe`) in 8.0/9.0/9.1,
the same treatment as the other SDK-gap vSAN rows. If it is ever re-implemented, note the
existing `expected_value=false` against a field named `checksumEnabled` is inverted: SCG
wants checksumming **on** (the SCG "Disabled" refers to the *Disable object checksum*
policy attribute being unset). The normalizer comment at `_compliance_normalize.py` ~line 521
reasons its way to the wrong polarity.

### vSAN presence gate (defect, affects `cluster.managed-disk-claim` today)

`VSphereClient.hasVsanConfig` must return `vsanConfigInfo/enabled == true`, not "element
present". Suggested: read `bool:configurationEx.vsanConfigInfo.enabled` semantics, i.e.
`childText(vsanCfg, "enabled")` parsed as boolean; `false` or absent -> non-vSAN (N/A);
a failed read -> null (UNREADABLE), as today. Update the javadoc. After the fix, wld01/wld02
clusters should log `has no vsanConfigInfo (non-vSAN cluster)` (reword the message to
"vSAN not enabled") and stop scoring vSAN controls.

### Logging (optional, cheap)

Log at DEBUG, once per cycle per (control, reason): the recipe and whether the failure was a
SOAP fault (with `faultstring`), a missing DOM segment (name it), or an unparsable leaf. Today
the only way to diagnose this class of defect is to reason from the code, as this
investigation had to.

## 6. Live proof still needed

The factory environment has no vCenter credential, so no direct PropertyCollector/MOB or
esxcli call was possible. Remaining proof, cheapest first:

1. **After the esxcli change ships to devel:** read the three `|Actual` properties on any
   healthy host. Expect `TPM`/`NONE` and `true`/`false`, not `(unreadable)`. If a field name is
   wrong the row reads `(unreadable)` while the other esxcli rows keep reading; that isolates
   a naming error immediately.
2. With a vCenter read-only session: `RetrieveProperties` of `runtime.stateEncryption` on one
   host (confirms whether vCenter populates it on TPM-less hosts) and of `configurationEx` on
   `vcf-lab-mgmt-cl01` and `vcf-lab-wld01-cl01` (confirms `enabled=true/false` and the absence
   of `checksumEnabled`).
3. Or, on one ESX host shell: `esxcli --formatter=xml system settings encryption get` shows the
   exact struct field names the ExecuteSoap path returns.

## Related

- `knowledge/context/investigations/compliance_build46_golden_comparison.md` §3.2 (same three unreadable in June).
- `knowledge/context/reviews/compliance-build-73.md` W1.
- `knowledge/context/investigations/2026-05-29-vsan-management-sdk-gap.md`.
