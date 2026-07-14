# vCommunity vSphere — PROD (original) vs DEVEL (Tier 2 port) live parity comparison

**Author:** `api-explorer` (read-only; all calls GET, zero writes either instance)
**Date:** 2026-07-13
**Method:** live Suite-API key-set diff of matched mgmt01 objects across two
instances monitoring the *same* management vCenter
(`vcf-lab-vcenter-mgmt.int.sentania.net`).
**Profiles:** `prod` (`vcf-lab-operations.int.sentania.net`, READ-ONLY GETs) /
`devel` (`vcf-lab-operations-devel.int.sentania.net`), `--skip-ssl-verify`.
**Scope:** the adapter-kind-contributed `vCommunity|` metric/property namespace
(empirically the only prefix either adapter contributes), plus the pack's
Super-Metric content layer.

## Verdict: PARITY HOLDS — no DRIFT

Every key-set delta observed between the two instances is fully attributable to
one of: (a) **stale persisted keys** from a prior pack version (confirmed by
20–160-day-old last-datapoint timestamps), (b) **prod-side runtime config
opt-ins** (config files ship byte-identical between source and port), (c) a
**documented by-design redesign** in the port, or (d) **policy / SM-enablement**
environment differences. None trace to an unintended divergence in the port's
active collection. The actively-collected `vCommunity|` namespace is identical
on every matched pair once stale/env keys are removed.

## Adapter-kind / instance identification

| Instance | vCommunity adapter kind | mgmt adapter-instance resource id |
|---|---|---|
| **prod** | `VCFOperationsvCommunity` (Onur's original "VCF Operations vCommunity") | `3555f3cd-26cc-4e8b-acdb-158fd5cae069` |
| **devel** | `vcfcf_vcommunity_vsphere` (our Tier 2 port, v1.0.0.12 CI) | `62288eb3-1034-4222-b882-5e39a89db510` |

Note: prod *also* has the `vcfcf_vcommunity_vsphere` adapter **kind** registered
but **no instance** of it — so prod is unambiguously running the original pack
against mgmt. The pack stitches `vCommunity|` metrics/properties onto native
**VMWARE** resources (Cluster/Host/VM); its own adapter-instance world object
carries **no** `vCommunity|` keys on either side (0=0).

## Matched objects

| Object | display name | resource kind | devel id | prod id |
|---|---|---|---|---|
| cluster | vcf-lab-mgmt-cl01 | VMWARE ClusterComputeResource | d8b36417 | 716866c9 |
| host esx01 | vcf-lab-mgmt-esx01 | VMWARE HostSystem | 8bd31613 | 471404d8 |
| host esx03 | vcf-lab-mgmt-esx03 | VMWARE HostSystem | 5fd4f7b2 | 6d11f05f |
| VM #1 | vcf-lab-sddcmgr | VMWARE VirtualMachine | 502d402c | 7a6f1577 |
| VM #2 | vcf-lab-nsxmgr-mgmta | VMWARE VirtualMachine | daa96ab5 | a42d63cd |
| world | vCenter adapter-instance obj | (kind instance) | 62288eb3 | 3555f3cd |

## Per-object `vCommunity|` key-set diff (active keys)

| Object | stats d/p | props d/p | Net active delta |
|---|---|---|---|
| cluster | 1 / 1 | 12 / 12 | **0 — identical** (incl. `DRS Score`, EVC, HA, DRS config) |
| esx03 | 1 / 1 | 17 / 17 | **0 — identical** (VCF-cores licensing + vmnic0-2 device props) |
| esx01 | 1 / 1* | 17 / 17* | 0 active (*prod +Eval-Mode license = 160-day stale; devel +Install-Date Read-Error = by-design) |
| vm_sddcmgr | 2 / 2* | 2 / 2* | 0 active (*Config\| short-ns, bare Last-Boot = stale; Adv-Params/Options = env opt-in; OS-Last-Boot = by-design) |
| vm_nsxmgr | 2 / 2* | 2 / 2* | same pattern as sddcmgr |
| world | 0 / 0 | 0 / 0 | **0 — both empty** |

Pack Super-Metric layer: **15/15 cluster-rollup SM definitions present on both
with byte-identical UUIDs** (`vSphere Cluster Performance` a1b7d29a,
`vSphere Cluster Worst ESXi Bad Network Packets` 48f81e75, `… CPU Ready`
9cfb6d0c, `… vMotions` bbd24970, all UUID-MATCH). SM *compute* on individual
resources differs by policy only (see ENVIRONMENT below).

## DRIFT items

**None.**

## BY-DESIGN deltas (with citation)

1. **Instanced / version-aware licensing** — both instances emit the identical
   `vCommunity|Licensing:VMware Cloud Foundation (cores)|{Remaining Days, Edition
   Key, License Expiration Date, License Key, Name}` family on esx01 & esx03. The
   port's redesign (instanced `Licensing:<edition>|`, no hardcoded 8.x SKU, no
   sentinel firing) is faithful. Cite: parity-certification §1;
   `content/sdk-adapters/vcommunity-vsphere/CHANGELOG.md:461-473`;
   `HostCollector.java:143` (`"vCommunity|Licensing:" + name + "|"`).
   *Value spot-check:* license **Remaining Days** consistent — prod esx01 = 144
   (measured 273 h / 11 d ago), devel esx01 = 132 (fresh); 144 − 11 ≈ 133 ≈ 132
   ⇒ same underlying expiry, no unit/magnitude mismatch.

2. **Passive VMware-Tools `OS Last Boot Up Time`** — devel emits
   `vCommunity|Guest OS|Operating System|OS Last Boot Up Time` as a passive
   property (`runtime.bootTime`, no guest login); prod (source) sources it via an
   active guest-OS query that returns nothing on these Photon appliances. Cite:
   `REFERENCE.md:113`; `VCommunityVSphereClient.java:626-629`.

3. **Install-Date degraded-to-property** — devel esx01 carries
   `vCommunity|Configuration|Install Date|Read Error` (alertable property when the
   install date can't be read). Cite: `README.md:106,119`.

4. **DEF-010 — "Bad Network Packets" SM** — inherited shared defect (formula
   byte-identical to source, same UUID). The leaf SM computes on **neither**
   instance (symmetric); the `vSphere Cluster Worst ESXi Bad Network Packets`
   rollup UUID is identical on both. Cite: `knowledge/context/defects.md` DEF-010.

5. **Events / Windows guest-OS services (OPEN-B1, events TOOLSET GAP)** — not
   exercisable in this matched set (no Windows VMs; all mgmt VMs are
   Photon/appliance) and not represented in the statkey/property API surface.
   Symmetric absence, no observable delta. Cite: parity-certification gap #5;
   REFERENCE.md:183-185.

## ENVIRONMENT / STALE caveats (honest, not DRIFT)

- **prod vCommunity stats are ~11 days stale** (DRS Score age 273.6 h, license
  Remaining Days age 273.5 h) vs devel fresh (~0 h). prod's original-pack adapter
  is on a slow/stalled stat-collection cadence. Property **key presence** is
  unaffected; spot-checked **values agree** (DRS Score prod 96 vs devel 95;
  license as above).
- **prod-only `vCommunity|Licensing:Evaluation Mode|*` on esx01** — last datapoint
  **3862 h (~160 d) old**: a persisted historical artifact from before esx01 was
  licensed with VCF cores. Not actively collected; not present in devel's DB
  because devel never saw esx01 in eval mode. STALE, not drift.
- **`vCommunity|Config|SCSI Controllers|*` (short "Config" ns) + bare
  `Guest OS|…|Last Boot Up Time`** appear on both/devel but are **stale** (devel
  `Config|SCSI Controllers|Count` last data 482.9 h / ~20 d old). Both the source
  and the port retired the short `Config|` namespace for `Configuration|`
  (`VmCollector.java:106,111`; source `vm_scsi_controller_type.py:24,46`); the
  current port emits only `Configuration|SCSI Controllers|Count` (live, 0.1 h).
- **prod-only VM Advanced-Parameters / Options** (`svga.present`,
  `RemoteDisplay.maxConnections`, `Options|config.latencySensitivity.level`,
  `Options|config.maxMksConnections`) = **prod runtime opt-in**. The
  `vm_options.xml` and `vm_advanced_parameters.xml` solutionconfig checklists ship
  **byte-identical** between source and port (both commented-out by default —
  verified `diff`); prod's admin uncommented them in the running instance.
- **Super-Metric compute differences** = policy/enablement. prod carries many
  admin-authored `[Custom] …` / `[IDPS] …` SMs absent from devel; devel's pack SMs
  were first policy-enabled 2026-07-13 (per DEF-010). Pack SM *definitions* are
  UUID-identical on both, so this is an enablement/environment difference, not a
  content divergence.

## Could not compare / limitations

- **Events** — neither the statkey nor property API surfaces events; events are
  stripped from the port's pak (known TOOLSET GAP). Not comparable by this method.
- **Windows guest-OS service/event surface (vcommunity-os / OPEN-B1)** — no
  Windows VMs in the matched mgmt set; deferral not exercisable here.
- **prod stat staleness** — value spot-checks on prod use datapoints ~11 days old
  (still internally consistent with devel's fresh values); prod's collection
  cadence is an environmental factor, not adjusted for.

## Addendum 2026-07-14 — prod staleness caveat RESOLVED

User restarted the vCommunity collector(s) on prod; a read-only `ops-recon`
freshness re-check confirmed all active `vCommunity|` stats on the five matched
objects are now minutes-old. With both sides fresh, values match exactly
(DRS Score 86 = 86; license Remaining Days 132 = 132 on esx01 and esx03). No
new keys appeared; the only remaining stale item is esx01's
`Licensing:Evaluation Mode` family (~161.7 d, aged consistently — the known
pre-licensing artifact). Verdict above unchanged: PARITY HOLDS — no DRIFT.

## Implications for code

None. No DRIFT ⇒ no port change indicated. DEF-010 remains the only
content-level open item and is a documented shared/inherited defect, not a
prod-vs-devel divergence.
