# Investigation: SDK MPs blocked from VCF-managed VMWARE adapter

**Date:** 2026-05-15
**Status:** Active — root cause hypothesis (CLOUD_TYPE=VMWARE_CLOUD_FOUNDATION
authz block) testing in progress.
**Owner:** scott + orchestrator

## TL;DR

VCF Operations 9 SDK MPs that use ARIA_OPS stitching against
`VMWARE:Datastore` / `VMWARE:HostSystem` fail on prod with a 403
from the adapter's internal Suite API client. Devel is unaffected
even with active Aggregator federation pulling from prod. The
differentiator is **`CLOUD_TYPE` on the VMWARE adapter instance** —
`VMWARE_CLOUD_FOUNDATION` on prod (VCF-managed) vs `PRIVATE_CLOUD`
on devel (user-configured). Federation residue (FDR_* adapter
kinds) is NOT the cause as initially theorized — that theory is
superseded by direct test on devel. Active reproduction (delete
devel's vCenter adapters, install VcfAdapter, observe stitching
break on the auto-provisioned VCF-managed VMWARE instances) is
planned but not yet run. FDR_VMWARE-targeting variant of the MP
imports cleanly on both prod and devel — test collection result
pending.

## Symptom (verbatim)

```
WARN - Unable to retrieve VMware Aria Operations resources of
       type 'VMWARE:Datastore'. Check that the resource type is valid.
WARN - VMware Aria Operations client is forbidden access to the
       given call.
```

The second line is the real signal. The "resource type" complaint
on the first line is the SDK runtime's stock translation when the
authz call fails — misleading. External admin-creds Suite API calls
to the same endpoint succeed cleanly.

## Activity log

### Phase 1 — Session resume + wrong root cause (early)

- Resumed after a corrupted session (`d2181965-...jsonl`). Handoff
  brief reconstructed from prior transcript.
- Initial reading from handoff: "Storage Paths prod failure is RBAC
  (Suite API 403 on the MPB adapter)." Wrong call. Symptoms are
  authz-shaped but the cause is more specific.

### Phase 2 — Object-type-mismatch hypothesis

- User's first-cut hypothesis: prod's MPB picker shows only
  `FDR_VMWARE:Datastore (Aggregated)` for `datastore` (no plain
  `VMWARE:Datastore`); Storage Paths targets the missing kind, so
  stitching can't link. Screenshot: `tmp/Screenshot 2026-05-15 121345.png`.
- Recon refuted: `VMWARE:Datastore` is present on prod with 10
  resource instances, 3 healthy vCenter adapter instances. The
  underlying objects exist; the picker is misleading.

### Phase 3 — Federation residue theory (built up then falsified)

- Identified `FDR_VMWARE`, `FDR_VirtualAndPhysicalSANAdapter`,
  `FDR_vCenter Operations Adapter` adapter kinds registered on
  prod with zero instances (ghost residue from a defunct
  federation to a legacy Aria Ops 8 source).
- User uninstalled the Aggregator solution on prod. Solution
  dropped; FDR_* adapter kinds persisted.
- Redescribe ran. FDR_* kinds still present.
- Service reboot. FDR_* kinds STILL present. Pollution is
  persisted to disk.
- Confirmed via grep of both API specs: no DELETE endpoint exists
  for adapter kinds in either public or internal API. Cleanup is
  not possible via supported APIs.
- Wrote `context/federation_breaks_aria_ops_stitching.md`
  documenting the theory. **This file is now SUPERSEDED** —
  see next phase.

### Phase 4 — Federation theory falsified on devel

- User installed Aggregator on devel (no federation pull configured).
  Recon: FederatedAdapter registered, FDR_* kinds NOT registered.
  Storage Paths still works.
- User configured devel's Aggregator to pull from prod. FDR_VMWARE
  registered with active resource population (10 FDR_Datastore
  records mirroring prod's 10).
- **Storage Paths test collection on devel STILL succeeded.**
- This falsifies "federation pollution permanently breaks
  ARIA_OPS-stitching SDK MPs." The hypothesis was too broad.

### Phase 5 — VCF-managed vCenter hypothesis (current leading theory)

- User's pre-existing hypothesis (set aside during the federation
  detour): prod uses VcfAdapter to manage its vCenter adapter
  instances; devel uses direct vCenter adapter configuration.
  Maybe the difference is at the adapter-instance level, not the
  Datastore level.
- Side-by-side diff of `VMWARE:Datastore` records on prod vs devel
  (same physical datastore `vcf-lab-mgmt-cl01-vsan`,
  `VMEntityObjectID=datastore-7001`).
  - Datastore record itself: structurally identical, no
    VcfAdapter ownership edges, no extra identifiers.
  - **Adapter instance differs.** `CLOUD_TYPE` on the VMWARE adapter:
    - **prod = `VMWARE_CLOUD_FOUNDATION`**
    - **devel = `PRIVATE_CLOUD`**
  - Plus `ENABLE_ACTIONS`, `LOG_COLLECTION`, `PDRS_STATS_PROVIDER`
    differ — all consistent with prod being VCF-managed.
  - Ownership chain at platform level: `VCFDomain → VMWARE adapter instance`.
    Prod has 3 VCFDomain resources tied to its 3 vCenter adapter
    instances; devel has 0 VCFDomain resources.
- **Refined hypothesis:** SDK MP `getResourcesByType` calls are
  blocked when the underlying VMWARE adapter instance has
  `CLOUD_TYPE=VMWARE_CLOUD_FOUNDATION`. The platform has an
  authz layer specific to VCF-managed VMWARE adapter instances
  that rejects MP-internal Suite API enumeration. Direct admin
  creds bypass this check; SDK identity does not.

### Phase 6 — Authoring probes (test designs on devel + prod)

- **Test 1 (devel):** Imported clone of vSphere Storage Paths design
  with `VMWARE:*` parent targets. Result: 201, design INVALID only
  on source-test gate, parent refs preserved verbatim. Design id
  `f618a89e-092d-4977-9230-71ca731b10f1` ("VCF Content Factory Test
  Storage Paths"). Confirms import layer does not block or rewrite.
- **Test 2 (prod + devel):** Imported clone with `FDR_VMWARE:*`
  parent targets. Both 201, both INVALID only on source-test gate,
  parent refs preserved as FDR_VMWARE / FDR_Datastore /
  FDR_HostSystem. Design ids:
  - prod: `1aa0a975-3d3d-4dab-98ad-bcb7612eb6cd` ("VCF Content
    Factory FDR Storage Paths", source.id `866b8bd4-...`)
  - devel: `68bcaf33-3668-4a99-a9dd-5a69e6c72e30` (same name, source.id `37048c79-...`)
- **Test 3 (devel FDR collection — RAN 2026-05-15T20:38):**
  Collection Preview on the devel FDR draft design FAILED, but
  with a NEW error class:
  - Suite API resource enumeration of FDR_VMWARE succeeded (no 403)
  - `IdentifierNotFoundException` thrown from `Resource.getIdentifierValue`
    inside `HttpObjectMapperKt.getVROpsMatchIdentifierValue` →
    `mapResourceMetricsByBindingValue`
  - Diagnosis: stitch binding expressions reference VMWARE-style
    identifiers (probably `VMEntityObjectID`); FDR_Datastore objects
    have different identifiers, so per-row identifier match fails.
- **Implications:**
  - **Good news**: FDR_VMWARE enumeration is NOT blocked by the
    authz layer that blocks VMWARE on prod. So FDR_VMWARE is
    structurally readable by SDK MPs in a way VMWARE isn't on
    VCF-managed instances.
  - **Bad news**: FDR_VMWARE-targeting is not a drop-in workaround.
    Using it requires re-authoring bind metrics against
    FDR-specific identifiers.
- **Test 4 (prod FDR collection — pending):** Same Collection Preview
  on prod's FDR draft. Expected: same `IdentifierNotFoundException`
  (confirms prod sees the same stitch-binding failure, not a different
  authz block). One click.
- **Test 5 (FDR_Datastore identifier survey — pending):** Dump a
  FDR_Datastore record from devel via `/api/resources/{id}` —
  what identifiers does it carry? Is there anything that maps back
  to the source vCenter Datastore's MOID, or is it federation-
  internal-only? Answers whether FDR_VMWARE could ever be a
  sustainable stitch target with redesigned bind metrics.

### Phase 7 — User recall: SDDC Manager add took control of vCenter adapters

**Critical missing piece surfaced 2026-05-15 late session.** User
recalled that when they originally added SDDC Manager on prod,
VcfAdapter **claimed the existing vCenter adapter instances** —
didn't create new ones. The act of claiming flipped their
`CLOUD_TYPE` from `PRIVATE_CLOUD` to `VMWARE_CLOUD_FOUNDATION`
and registered VCFDomain → VMWARE-adapter-instance edges. This
is the exact moment Storage Paths stopped being collectable on
prod (it never worked on prod, because it was installed after
this point).

**Revised causal chain:**

1. vCenter adapters initially `CLOUD_TYPE=PRIVATE_CLOUD` —
   SDK MPs can read VMWARE:* resources fine.
2. SDDC Manager added; VcfAdapter claims existing vCenter adapter
   instances and flips their `CLOUD_TYPE=VMWARE_CLOUD_FOUNDATION`.
3. SDK MP Suite API enumeration of VMWARE:* now returns 403 from
   the SDK identity (admin still works).
4. Any ARIA_OPS-stitching MP installed at/after step 2 cannot
   collect against VMWARE:Datastore / VMWARE:HostSystem.

**Simplified reproduction test on devel:** add SDDC Manager (do not
delete vCenter adapters first). Watch for:
- VcfAdapter claiming the existing `vcf-lab-mgmt` and `vcf-lab-wld01`
  vCenter adapter instances.
- Their `CLOUD_TYPE` field flipping from `PRIVATE_CLOUD` to
  `VMWARE_CLOUD_FOUNDATION`.
- Storage Paths stitching breaking immediately after.

Devel snapshot in place; reversible.

**Framework implication if confirmed:** any VCF Operations 9
instance running SDDC Manager / VcfAdapter has its vCenter adapter
instances under VCF management, and SDK MPs that stitch onto
VMWARE:Datastore / VMWARE:HostSystem cannot collect on those
instances. Since SDDC Manager is the standard deployment pattern
for VCF, this means **ARIA_OPS-stitching MPs targeting vSphere
objects are essentially unusable on production VCF deployments**.

Known workarounds:
1. INTERNAL-object MPs with `relationship_rules:` — sidesteps the
   authz check entirely (no Suite API enumeration call).
2. Some undiscovered way to opt out of VCF management for specific
   adapter instances. Worth investigating, but unlikely to be
   user-exposed.
3. Platform-level fix from VMware. Out of scope.

### Phase 8 — SDDC Manager test on devel (FALSIFIES VcfAdapter hypothesis)

User added SDDC Manager as a connection on devel. The VcfAdapter
instance **claimed the existing vCenter cloud accounts** as predicted.
But Storage Paths kept collecting normally on devel after the claim.

**VcfAdapter / CLOUD_TYPE hypothesis falsified.** Adding SDDC Manager
and having it take ownership of vCenter adapter instances is not
sufficient to break SDK MP stitching.

### Phase 9 — Collector affinity hypothesis (CONFIRMED)

Re-examining the original prod-vs-devel diff revealed a field that
had been there all along but wasn't centered: `collectorId`. Targeted
recon:

| | PROD | DEVEL |
|---|---|---|
| Collectors on instance | 2 (id=1 INTERNAL, id=2 UNIFIED_CLOUD_PROXY) | 1 (id=1 INTERNAL) |
| VMWARE adapters collectorId | **2** (all three) | **1** (all three) |
| Storage Paths MP collectorId | **1** | **1** |
| Same collector? | **DIFFERENT** | SAME |
| MP collection message | `"All collection requests failed. Cannot collect resources."` | (none) |

Prod's MP adapter runs on the **embedded INTERNAL collector** while
the VMWARE adapter instances run on a **remote UNIFIED_CLOUD_PROXY**
collector at 172.27.8.51. SDK-issued Suite API tokens evidently
have a scope restriction that blocks cross-collector resource
enumeration; admin tokens do not have this restriction.

This explains every observation:
- Admin Suite API calls work; SDK calls fail. (Different identities,
  different cross-collector scope.)
- Devel works regardless of everything we did. (Single collector,
  no cross-call ever.)
- Federation, FDR_VMWARE, VcfAdapter, CLOUD_TYPE all moved nothing
  because none of them was the actual differentiator.
- "client is forbidden access to the given call" is the SDK's stock
  string for any Suite API authz failure, including this one.

**Asymmetric bonus finding:** prod's Storage Paths MP has
`collectorGroupId: 2fd79476-…` but **none of the prod VMWARE
adapters carry any collector group**. Devel's MP and VMWARE
adapters all share one group (`2bb3a52a-…`). Whether this is
the actual gatekeeper (same-group required) or whether
same-collector alone is enough is testable by the next step.

### Phase 10 — Fix attempt (pending)

Move the Storage Paths MP adapter instance on prod from collector 1
to collector 2 (UNIFIED_CLOUD_PROXY where the VMWARE adapters
live). Test:
- If collection succeeds → confirmed: same-collector required for
  SDK MP cross-adapter resource lookups.
- If still 403 → collector group membership matters too; need to
  put the MP into the same group as the VMWARE adapters.

### Phase 11 — Pre-existing planned tests (now superseded)

The "delete vCenter adapters, install VcfAdapter" devel reproduction
test from earlier phases is no longer relevant. The collector
hypothesis explains everything and is more directly testable.

### Phase 12 — Factory pak install regression discovered (2026-05-15 evening)

The MPB-vs-factory comparison surfaced 8 Category-A items
(`mp_format_comparison_2026_05_15.md`). Tooling implemented all 8.
First rebuild produced `.6` paks; install on prod failed at
"Applied Adapter (Failed)". Diff vs working `.5` showed three changes:
(1) `vcops_minimum_version` 7.5.0 → 8.10.0, (2) `conf/design.json`
removed (item 8), (3) `externalResources` populated (item 1, the
critical fix). Item 8 reverted (the 2026-04-18 Synology rule that
both `design.json` and `export.json` are required is restored,
2026-05-15 inferential removal was wrong). Rebuild as `.7`.

`.7` install on prod failed at "Applied Adapter Pre Script" — one
phase earlier. `.7` install on devel **silently failed** — install
task completed with no error but adapter kind never registered.
Inspection: `.7` pak (and `.5`, `.6`) were missing all install
scripts (`post-install.py`, `validate.py`, etc.) at pak root, and
`manifest.txt` had empty script slots. Builder had a `no_auth`
branch (gated on `auth: preset: none`) that stripped these for
no-auth MPs. Storage Paths is the only no-auth MP we have; UniFi
(with auth) had scripts and worked.

Tooling removed the `no_auth` branch (`builder.py`). Rebuild as `.8`.
`.8` pak structure verified correct: scripts present at root,
manifest slots populated (`"python validate.py"`,
`"python post-install.py"` etc.), `conf/design.json` present in
adapters.zip, `externalResources` populated.

**`.8` install on devel STILL silently failed.** Adapter kind
absent from solutions/adapterkinds, prior `vsphere-data` instance
wiped, no error from install task. The post-install.py script is
correct (calls `ops-cli control redescribe --force`) and identical
in shape to UniFi's. Without analytics log access
(`/storage/log/vcops/log/analytics/` on the appliance), we can't
see what's actually failing inside `redescribe`.

**Resume options when revisiting:**

1. SSH into devel appliance, pull the install-attempt analytics
   log entry. Direct evidence of the redescribe failure.
2. Try a clean uninstall + fresh install (avoid upgrade path).
3. Deeper structural diff against UniFi (adapter JAR, describe.xml
   ARIA_OPS-only paths) to find what triggers redescribe rejection
   for ARIA_OPS-stitching MPs.
4. **Sidestep the pak install entirely via the MPB API lifecycle**
   — see `mpb_api_surface.md` for the full recipe. Render factory
   YAML → `POST /designs/import` → COLLECTION_PREVIEW job →
   `PUT /verifyDesign/{jobId}` → `POST /install`. Uses the MPB
   designer's install code path, not the standalone pak loader.
   This is the leading workaround candidate.

**Current state of artifacts:**
- `dist/mpb_vcf_content_factory_vsphere_storage_paths.2.0.0.8.pak`
  — structurally correct, install fails silently
- `dist/mpb_vcf_content_factory_unifi_integration.1.0.0.8.pak`
  — built but not installed
- UniFi 1.0.0.7 is installed on prod (works). Storage Paths is
  effectively uninstalled on both prod and devel (the .8 install
  attempt removed prior versions).

**Code state:** all 8 Category-A fixes plus item-8 revert plus
no_auth fix landed. Builder is in the best state it's been in.
The remaining issue is in the install pipeline interaction, not
in code we control.

### Phase 13 — MPB API install path PROVEN end-to-end on devel

**Pivot decision.** Instead of further chasing the standalone
pak-install silent-fail, we tested whether the MPB API install
path works. Recipe per `mpb_api_surface.md`'s "End-to-end
create-from-scratch loop": import → source-test → preview →
verify → install.

**Result: both MPs registered successfully on devel via API.**

| Step | Storage Paths | UniFi |
|---|---|---|
| Render exchange JSON | OK | OK |
| `POST /designs/import` | OK (`c8876ec1-…`) | OK (`af3cf0d2-…`) |
| Source test | OK | OK (UniFi v10.3.58) |
| `COLLECTION_PREVIEW` | OK (3kk/9r/42m) | OK (6kk/162r/125m) |
| `PUT /verifyDesign/{jobId}` | `verified:true` | `verified:true` |
| `POST /install` | OK (47s) | OK (47s) |
| Adapter kind registered | YES | YES |
| Solution registered | YES | YES |

Both adapter kinds now live on devel, designs in VERIFIED status.
No adapter instances created yet (separate `POST /api/adapters`
step to start metric collection).

**The standalone pak install pipeline is the broken path.** The
renderer + MPB API combo proves the design is structurally sound.
The factory-built `.5`/`.6`/`.7`/`.8` paks contain the same wire
content; they just fail to register through the standalone
pak-loader for reasons we can't diagnose without analytics log
access.

### MPB API findings worth codifying into `mpb_api_surface.md`

Five gotchas that broke the existing recipe and were resolved
during the lifecycle drive:

1. **`GET /designs/{id}/source` returns different shape than
   export envelope's `source.source`.** PUT expects the live
   shape. Round-trip of export-shape PUT yields HTTP 400 with no
   diagnostic.
2. **Source test requires `configuration.collectorId` as the
   collector's `uuId` (UUID4), not the short `id` string.** Wrong
   format → `"No collector found with UUID null"`.
3. **Verify needs THREE inputs, not just the COLLECTION_PREVIEW
   jobId:**
   - (a) `source.testRequest.response` must be re-populated with
     the source-test action result (decoded base64) and PUT back
     into source.
   - (b) COLLECTION_PREVIEW must complete successfully.
   - (c) `PUT /verifyDesign/{previewJobId}` flips VALID → VERIFIED.
   The current `mpb_api_surface.md` "End-to-end" recipe is
   missing step (a). Without persisting the testRequest.response
   back into source, the design stays INVALID forever even after
   a successful TEST_CONNECTION.
4. **COLLECTION_PREVIEW requires `logLevel` in body.** One of
   `[TRACE, ALL, NOTICE, ERROR, INFO, FATAL, DEBUG, OFF, WARN]`.
   Without it, job gets accepted (202) but immediately FAILS
   with "Unexpected value for 'logLevel' (was null)". Schema
   entry missing this.
5. **Action poll terminal status is `COMPLETED_SUCCESSFULLY`,
   not `COMPLETED`.** Install jobs use `COMPLETED` in the
   deployment-status envelope, but actions use the longer string.

### Phase 14 — Pending next moves (resume points)

1. **Replay the API install on prod.** Same recipe, prod profile.
   If it works, Storage Paths is finally registered on prod and
   we can spin up an adapter instance and test whether the
   underlying VMWARE-authz issue (Phase 9) still bites at
   collection time. If it doesn't work, prod has additional
   constraints (likely the same authz issue blocking source
   test or COLLECTION_PREVIEW from succeeding).
2. **Codify the five MPB API findings** into
   `context/mpb_api_surface.md`. They're hard-won and easily
   re-lost in a future session.
3. **Add `api-install` subcommand to
   `vcfops_managementpacks/installer.py`** as a first-class
   install path. Pak install becomes the offline-cluster use
   case; API install becomes the primary loop. Bypasses every
   pak-loader failure mode (signature, conf/ matching, etc.)
   and uses the same wire format MPB UI uses.

### Current state of artifacts

**Devel (live):**
- Storage Paths design `c8876ec1-ed00-46f2-b1a8-71786466c720`
  VERIFIED, adapter kind registered, solution registered, no
  adapter instance.
- UniFi design `af3cf0d2-64f9-4078-8e32-48760aead6f1` VERIFIED,
  adapter kind registered, solution registered, no adapter
  instance.

**Prod (live):**
- UniFi `1.0.0.7` installed (pre-existing, unclear how it got
  there; functional).
- Storage Paths absent (`.6`/`.7` install attempts failed; no
  registered adapter kind).

**dist/ artifacts:**
- `mpb_vcf_content_factory_vsphere_storage_paths.2.0.0.8.pak`
  (structurally correct; install fails silently — known
  bad path)
- `mpb_vcf_content_factory_unifi_integration.1.0.0.8.pak`
  (built but not installed)

**Probe scripts on disk** (gitignored, scratch):
- `tmp/mpb_lifecycle.py` — Phase 0 cleanup driver
- `tmp/mpb_phase1_sp.py` — Storage Paths driver
- `tmp/mpb_phase2_unifi.py` — UniFi driver
- `tmp/sp_api_lifecycle.json` — rendered Storage Paths exchange
- `tmp/unifi_api_lifecycle.json` — rendered UniFi exchange

- User's plan: delete devel's 3 vCenter adapter instances, install
  VcfAdapter, point it at the VCF deployment, let it auto-provision
  its managed vCenter adapter instances. The auto-provisioned
  instances should come up with `CLOUD_TYPE=VMWARE_CLOUD_FOUNDATION`.
  Then re-test Storage Paths stitching on devel.
- Expected outcomes:
  - If stitching breaks → CLOUD_TYPE / VcfAdapter-managed
    instances are the authz cause. Theory confirmed.
  - If stitching keeps working → some other prod-specific factor
    is the cause (one of the 5 extra adapter kinds on prod:
    `NETWORK_INSIGHT`, `OrchestratorAdapter`, `VCFAutomation`,
    `VCFOperationsvCommunity`, etc.).
- Caveat: devel and prod would both be pointing the same VCF
  instance via VcfAdapter — possible cross-contamination, but
  acceptable for a controlled test window. Snapshot in place on
  devel.

## Current artifacts

### Files in repo

| Path | Purpose |
|---|---|
| `context/federation_breaks_aria_ops_stitching.md` | **SUPERSEDED** — federation-causes-breakage writeup, falsified by Phase 4 test |
| `context/vcf_managed_vmware_authz_investigation_2026_05_15.md` | This file — running activity log |
| `tmp/test_storage_paths_export.json` | Exchange-format render of Storage Paths YAML, used for the VMWARE clone |
| `tmp/fdr_storage_paths_export.json` | FDR_VMWARE-modified payload sent to prod |
| `tmp/fdr_storage_paths_export_devel.json` | FDR_VMWARE-modified payload sent to devel |
| `tmp/fdr_probe_results.json` | Full status + object summaries from FDR probe |
| `tmp/Screenshot 2026-05-15 121345.png` | Original prod MPB picker screenshot (datastore filter) |
| `tmp/Screenshot 2026-05-15 141645.png` | Devel MPB picker showing FDR_VMWARE Host System (Aggregated) |

### Drafts on prod (delete when done)

```bash
curl -ks -X DELETE \
  -H "Authorization: vRealizeOpsToken <token>" \
  -H "X-Ops-API-use-unsupported: true" \
  "https://${VCFOPS_PROD_HOST}/suite-api/internal/mpbuilder/designs?id=1aa0a975-3d3d-4dab-98ad-bcb7612eb6cd"
```

### Drafts on devel (delete when done)

```bash
# VCF Content Factory Test Storage Paths (VMWARE-targeting clone)
curl -ks -X DELETE -H ... "...?id=f618a89e-092d-4977-9230-71ca731b10f1"

# VCF Content Factory FDR Storage Paths (FDR_VMWARE-targeting clone)
curl -ks -X DELETE -H ... "...?id=68bcaf33-3668-4a99-a9dd-5a69e6c72e30"
```

## Open questions

1. **Does the prod FDR_VMWARE-targeting design pass source test
   + test collection** where the VMWARE-targeting design fails?
   If yes, FDR_VMWARE targeting is the workaround for VCF-managed
   environments. If no, the authz block applies to FDR_VMWARE too
   and we need a different approach.
2. **Does VcfAdapter swap on devel reproduce the 403?** Active
   test pending.
3. **Are FDR_VMWARE kinds a sustainable target for SDK MP
   authoring?** They only exist when federation is active. A
   factory MP targeting FDR_VMWARE would fail to install on any
   instance without federation. Two possible authoring patterns
   to evaluate:
   - Conditional target — design declares VMWARE primary, FDR_VMWARE
     fallback. SDK behavior unknown.
   - Variant pak — ship VMWARE pak for standalone instances,
     FDR_VMWARE pak for federated/VCF-managed. Higher cost,
     lower coupling.
4. **Is there a CLOUD_TYPE-aware version of the authz check that
   could be patched?** Likely vendor-internal, not actionable
   from outside.

## Lessons codified

- **Federation residue alone does NOT break ARIA_OPS stitching.**
  Active aggregation with FDR_VMWARE registered is fine on
  Ops9→Ops9. Prod-specific damage came from elsewhere (probably
  the Ops8→Ops9 federation schema mismatch creating different
  kind of registry pollution, OR the VCF management of the
  vCenter adapter — TBD by VcfAdapter swap test).
- **Adapter-kind registry is persisted to disk and there is no
  DELETE endpoint in any documented API surface.** Cleanup of
  orphan kinds requires vendor support or instance rebuild.
- **MPB design import doesn't enforce parent-object adapter-kind
  validity at intake.** FDR_VMWARE, VMWARE, and presumably any
  string survive verbatim. Validity is checked elsewhere (UI,
  install-time, or collection-time).
- **"forbidden access to the given call" from an SDK adapter is
  not literal RBAC denial** — it's the framework's stock string
  for any failed adapter-kind resolution. The real symptom is
  whatever broke before this message.

## Watch protocol — until VcfAdapter swap or test-collection results

If anything below changes, the conclusions above need re-evaluation:

- Does devel's existing Storage Paths MP (the installed pak, not
  the drafts) ever start 403ing as federation continues to run?
- Do any FDR_* kinds appear on devel that weren't there at the
  Phase 4 recon?
- Does prod's adapter-kind list change (e.g. an orphan kind
  spontaneously drops)?
