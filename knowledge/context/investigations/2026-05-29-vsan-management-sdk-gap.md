# vSAN Management SDK gap — ClusterComputeResource compliance

**Date:** 2026-05-29
**Component:** `content/sdk-adapters/compliance` Phase 3
**Status:** OPEN — 12 of 14 SCG ClusterComputeResource controls
unreachable until a vSAN Management SDK jar lands on the classpath.

## Summary

The compliance adapter's Phase 3 plan was to evaluate 14 SCG-9.0
ClusterComputeResource controls covering vSAN configuration. Plain
`vim25.jar` (8.0.2) — the only vSAN-aware jar on this adapter's
classpath — exposes a tiny slice of the cluster-level vSAN
configuration: `VsanClusterConfigInfo.{enabled, defaultConfig.
{autoClaimStorage, checksumEnabled}}`. The vmodl bindings jar
(`vim-vmodl-bindings-8.0.2.jar`) adds one more field
(`vsanEsaEnabled`) and nothing else.

The other 12 SCG controls (data-at-rest encryption, data-in-transit
encryption, iSCSI mutual CHAP, File Services NFS access control,
File Services SMB authentication, network isolation for vSAN iSCSI
target, network isolation for vSAN Max, operations reserve,
automatic rebalance, auto-policy-management, force-provisioning)
live on richer interfaces that the **vSAN Management SDK**
(`com.vmware.vim.vsan.binding.*`) jar ships but plain vim25 does
not. The relevant managed objects include:

  - `VsanConfigSystem` — encryption-rest, encryption-transit,
    force-provisioning, operations-reserve
  - `VsanFileServiceSystem` / `VsanFileServiceConfig` — file-services
    NFS access control, SMB authentication
  - `VsanIscsiTargetSystem` — iSCSI mutual CHAP, iSCSI target
    network isolation
  - `VsanVcStretchedClusterSystem` — network isolation vSAN Max
  - `VsanClusterHealthSystem` (or the unified vSAN management API)
    for automatic-rebalance, auto-policy-management

## What landed

Two controls flipped from `manual_audit` to `vim_property` in the
canonical SCG 9.0 CSV:

  - `cluster.managed-disk-claim` -> `vsanConfig.autoClaimStorage`
  - `cluster.object-checksum` -> `vsanConfig.objectChecksumEnabled`

And one in SCG 8.0:

  - `cluster.object-checksum` (the 8.0 source didn't carry
    managed-disk-claim).

Java path: `VSphereClient.getClusterVsanConfig` reads
`ClusterComputeResource.configurationEx.vsanConfigInfo` and exposes
the boolean fields keyed by `vsanConfig.<field>`. Empty map when
the cluster has no vSAN. The existing
`ControlEvaluator.evaluateVimProperties` dispatcher handles
Boolean actuals against the JS-boolean expected_value the
normalizer rewrites in for these rows.

Lab observation: `vcf-lab-mgmt-cl01` has vSAN enabled (per VCF Ops
property `configuration|vsanEnabled = Enabled`);
`vcf-lab-wld01-cl01` does not. The non-vSAN cluster will return an
empty `vsanConfig` map and get the profile-name-only push so it
still appears under VCF-CF Compliance in the metric browser.

## What's blocked

The remaining 12 cluster controls need the vSAN Management SDK jar:

  - `cluster.encryption-rest`
  - `cluster.encryption-transit-esa`
  - `cluster.encryption-transit-osa`
  - `cluster.force-provisioning`
  - `cluster.iscsi-mutual-chap`
  - `cluster.file-services-access-control-nfs`
  - `cluster.file-services-authentication-smb`
  - `cluster.automatic-rebalance`
  - `cluster.auto-policy-management`
  - `cluster.network-isolation-vsan-iscsi-target`
  - `cluster.network-isolation-vsan-max`
  - `cluster.operations-reserve`

These stay `manual_audit` in the canonical and are skipped by
both the evaluator and the dispatcher. Cluster resources still
appear under VCF-CF Compliance in the metric browser via the
profile-name-only push.

## Path forward

1. **Acquire the vSAN Management SDK jar.** VMware ships this in
   the vSAN Management SDK download bundle (Java distribution).
   The classes live under `com.vmware.vim.vsan.binding.vim.cluster.*`
   and `com.vmware.vim.vsan.binding.vim.host.*`. Need to verify
   redistribution license terms before bundling in `lib/`.
2. **Endpoint:** vSAN Management API uses the same SOAP endpoint
   as vim25 but a different SDK URL
   (`https://<vc>/vsanHealth`). Authentication tokens are shared
   with the vim25 session.
3. **Java work, per control:**
   - `getClusterVsanConfigSystem(MoRef cluster)` returning a
     `VsanConfigSystem` MoRef
   - Reads against `VsanConfigSystem.VsanClusterGetConfig` /
     `VsanClusterGetRuntimeStats` / etc.
   - For each control: identify the field path on the returned
     config object, extend `getClusterVsanConfig` to populate
     the canonical key.
4. **Normalizer:** extend `_VSAN_CLUSTER_PARAM_BY_SLUG` and
   `_VSAN_CLUSTER_EXPECTED_BY_SLUG` in
   `scripts/_compliance_normalize.py` with the 12 new slugs and
   their per-control polarities.

## References

- Existing build artifacts: `dist/vcfcf_sdk_compliance.1.0.0.31.pak`
  ships the two-control implementation against plain vim25.
- Java entry point: `VSphereClient.getClusterVsanConfig`
  (`content/sdk-adapters/compliance/src/com/vcfcf/adapters/
  compliance/VSphereClient.java`).
- Normalizer: `scripts/_compliance_normalize.py`
  (`classify_vsan_cluster_param`, `classify_vsan_cluster_expected`).
- vim25 surface confirmed by `javap` against
  `lib/vim25.jar:com/vmware/vim25/VsanClusterConfigInfo.class` and
  `lib/vim-vmodl-bindings-8.0.2.jar:com/vmware/vim/binding/vim/
  vsan/cluster/ConfigInfo.class` — both expose only enabled,
  defaultConfig.{autoClaimStorage, checksumEnabled}, plus
  vsanEsaEnabled on the vmodl variant.
