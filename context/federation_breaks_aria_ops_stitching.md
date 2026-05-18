# Federation Aggregator and ARIA_OPS-Stitching SDK MPs

Captured: 2026-05-15. Updated 2026-05-18 with extended devel observation
(below). Authored by ops-recon from live devel API data (T2) and
orchestrator-supplied T0/T1 summaries. All API calls were read-only
against the devel profile.

---

## TL;DR

Configuring a VCF Operations instance as a Federation Aggregator
permanently registers `FDR_*` shadow adapter kinds that survive solution
uninstall, redescribe, and full service reboot. On at least one **prod
(Ops8 source)** instance, these shadow kinds caused ARIA_OPS-stitching
SDK Management Packs to receive `403 Forbidden` on every collection
cycle. **On devel (Ops9 source) the breakage has NOT recurred across
extended observation (T2 → present, ≥72 hours).** This narrows the
working hypothesis to "Ops8 → Ops9 federation specifically corrupts the
adapter-kind metadata resolver"; Ops9 → Ops9 federation appears safe
for ARIA_OPS stitching based on the devel evidence. Default posture
for new content is updated below.

## 2026-05-18 disproof status (Ops9 → Ops9)

The original 2026-05-15 capture flagged "T2 → T3 breakage on Ops9→Ops9
is the open question under active watch." Three days of continued
collection on devel (federated against an Ops9 source) without any of
the breakage signals in the watch protocol below constitutes informal
disproof of the strong claim ("federation permanently breaks ARIA_OPS
stitching"). The narrower claim ("Ops8 → Ops9 federation broke it on
that specific prod") stands as the original observation.

**Implication for the framework**: mp-designer may propose ARIA_OPS
stitching (Pattern B) for hardware / vSphere-enrichment MPs without a
federation-related health warning, **provided** the target instance is
Ops9 and any federated source is also Ops9. Retain the warning for
Ops8 → Ops9 deployments. A defensive pre-install check that aborts when
`FDR_*` kinds are registered is still a reasonable belt-and-suspenders
move for content shipped to unknown customer environments.

---

## Symptom

**Error observed on prod (ARIA_OPS-stitching MP, every collection cycle):**

```
403 Forbidden — "client is forbidden access to the given call"
  source: GET /api/resources?adapterKind=VMWARE&resourceKind=Datastore
```

**What it actually means:**

The error string `"client is forbidden access to the given call"` is the
MPB SDK runtime's stock translation of "adapter-kind metadata resolution
failed," not literal RBAC. The adapter runtime resolves VMWARE:Datastore
against registered adapter kind metadata before issuing the Suite API call.
When FDR_* shadow kinds shadow or confuse the registry, the resolution
fails internally and surfaces as a generic 403. The actual HTTP call to
the Suite API never happens (or happens against the wrong kind registry
entry), so RBAC is not the issue — the SDK's own pre-call metadata lookup
is failing.

This interpretation is INFERRED from the prod symptom + the structure of
FDR_* kinds registered on devel at T2. The SDK source is not available for
direct inspection.

---

## Causal chain (under investigation)

### T0 — Baseline (earlier 2026-05-15, pre-Aggregator install)

- **Devel adapter kinds:** 19 solutions, standard VCF Ops adapter kinds.
- **FDR_* kinds:** none registered.
- **VMWARE:Datastore count:** 8.
- **Storage Paths collection:** operating normally (INFERRED from T1/T2
  continuity; direct T0 snapshot not captured in this session).
- **FederatedAdapter:** not installed.

### T1 — Aggregator MP installed, federation not configured (earlier 2026-05-15)

- **FederatedAdapter:** registered as an adapter kind, 0 instances.
- **FDR_* kinds:** still absent.
- **VMWARE adapter:** undisturbed.
- **Storage Paths collection:** still working.
- **Key observation:** mere installation of the Aggregator solution is not
  sufficient to register FDR_* kinds. Federation configuration is required.

### T2 — Aggregator configured and pulling from prod (2026-05-15 ~14:23 UTC-5)

Live API snapshot (ops-recon, read-only, devel profile):

**Adapter kinds registered (23 total):**

```
FDR_VMWARE                              (adapterKindType: OPENAPI, describeVersion: 1)
FDR_VirtualAndPhysicalSANAdapter        (adapterKindType: OPENAPI, describeVersion: 1)
FDR_vCenter Operations Adapter          (adapterKindType: OPENAPI, describeVersion: 1)
FederatedAdapter                        (Aggregator Adapter — the connector, not a shadow)
```

The three FDR_* kinds appeared between T1 and T2 — exactly when federation
was configured and the pull from prod began.

**FDR_* resource counts (live, actively populated from prod):**

| Adapter Kind | Resource Kind | Count |
|---|---|---|
| FDR_VMWARE | FDR_ClusterComputeResource | 3 |
| FDR_VMWARE | FDR_Datacenter | 3 |
| FDR_VMWARE | FDR_Datastore | 10 |
| FDR_VMWARE | FDR_VMWARE Adapter Instance | 0 |
| FDR_VMWARE | FDR_HostSystem | 8 |
| FDR_VMWARE | FDR_VMwareAdapter Instance | 3 |
| FDR_VMWARE | FDR_VmwareDistributedVirtualSwitch | 3 |
| FDR_VMWARE | FDR_vSphere World | 1 |
| FDR_VirtualAndPhysicalSANAdapter | FDR_VirtualAndPhysicalSANAdapter Adapter Instance | 0 |
| FDR_VirtualAndPhysicalSANAdapter | FDR_VirtualSANDCCluster | 1 |
| FDR_vCenter Operations Adapter | FDR_vCenter Operations Adapter Adapter Instance | 0 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Analytics | 1 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-CaSA | 2 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Cluster | 1 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Collector | 2 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Controller | 1 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Fsdb | 1 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Node | 1 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Persistence | 1 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Product-UI | 1 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Suite-API | 2 |
| FDR_vCenter Operations Adapter | FDR_vC-Ops-Watchdog | 2 |

Note: `FDR_Datastore count = 10` > `VMWARE:Datastore count = 8`. The
FDR_* shadow appears to include datastores from multiple vCenter instances
on prod that do not exist on devel. The shadow resource graph reflects
prod's inventory, not devel's.

**FederatedAdapter instance:**

```
id: 8b9844e4-6e15-4d07-a749-160db23781a5
host: vcf-lab-operations.int.sentania.net  (prod)
monitoringInterval: 15 min
lastCollected: 2026-05-15T14:13:58 (local)
lastHeartbeat: 2026-05-15T14:22:50 (local)
numberOfResourcesCollected: 1  (counts only the FederatedAdapterInstance object itself)
messageFromAdapterInstance: "Configuration succeed."
```

**VMWARE:Datastore — unchanged, no FDR_* contamination yet:**

```
totalCount: 8  (unchanged from T0)
Sample: vcf-lab-mgmt-esx02-local (id: 0d5ab9d8-9861-4780-bbbc-c060e8268599)
  adapterInstanceId: 5aa31ee3-39f2-4239-bf4f-840eb0bdc99d
  resourceStatus: DATA_RECEIVING / STARTED
  Relationship count: 4
  FDR_* relationship edges: 0
```

The VMWARE:Datastore resources are not yet carrying FDR_* relationship edges.

**Storage Paths MP (mpb_vcf_content_factory_vsphere_storage_paths):**

```
adapter instance id: f8cb5191-3fb7-4927-a7dc-ba438583ec08
name: vsphere-data
lastCollected: 2026-05-15T14:22:30 (local)
lastHeartbeat: 2026-05-15T14:23:24 (local)
numberOfResourcesCollected: 9 (adapter list) / 4 (resource query: world + 2 relatives + adapter instance)
numberOfMetricsCollected: 42
messageFromAdapterInstance: (empty — no error)
```

Collection is succeeding at T2. No error message. This diverges from prod
behavior — the question is whether devel will degrade over subsequent cycles.

**Outside-client smoke test:**

```
GET /api/resources?adapterKind=VMWARE&resourceKind=Datastore&pageSize=1
HTTP 200 — totalCount=8
```

The Suite API endpoint that prods SDK MP to 403 is answering normally on
devel at T2.

### T3 — Future state (not yet observed)

Unknown. Prod reached a state where Storage Paths MP began 403'ing on
VMWARE:Datastore queries after federation was established. Whether devel
will follow the same path depends on questions in the Open Questions section.

---

## What we know cleans up cleanly

- **Aggregator solution removal** drops the `FederatedAdapter` adapter kind
  and its instance. (Observed on a prior devel session; the FederatedAdapter
  kind is absent from T0 baseline and present only after T1 install.)
- **FDR_* resource objects** may eventually age out if the federation pull
  stops, but this has not been verified.

---

## What does NOT clean up

- **FDR_* shadow adapter kinds** (`FDR_VMWARE`, `FDR_VirtualAndPhysicalSANAdapter`,
  `FDR_vCenter Operations Adapter`) persist after solution uninstall on prod.
  They are not removed by:
  - Aggregator solution uninstall
  - Full service reboot
  - `redescribe` (for any adapter kind)
  - Any known Suite API or Internal API DELETE call

- **No DELETE endpoint** for adapter kinds exists in either:
  - Public API (`docs/operations-api.json`)
  - Internal API (`docs/internal-api.json`)

  The adapter kinds appear to be persisted to disk (likely in the Cassandra
  datastore or a flat-file registry) and survive all runtime resets. This
  matches the behavior of Cassandra-backed metadata in VCF Operations — once
  a kind is registered, removing it requires either a database-level
  operation or a schema migration, neither of which is exposed via the API.

---

## Implications for content authoring (updated 2026-05-18)

**Default posture for platform-resident objects (updated):**

- ARIA_OPS stitching is **fine to propose** for new MPs targeting Ops9
  instances — Ops9 → Ops9 federation has not reproduced the breakage
  after three days of continuous observation on devel.
- Retain the original caution **only** for instances with Ops8 → Ops9
  federation history. That specific path produced the prod breakage and
  the cleanup limitation (no DELETE endpoint for adapter kinds) is
  unchanged.

**Optional defensive posture for content shipped to unknown environments:**

- If the target customer's federation history is unknown and the MP
  will be installed broadly, gate delivery on a pre-install check:
  `GET /api/adapterkinds` returning `FDR_*` keys + an Ops8 source
  somewhere in the federation history is the risk signature. If both
  are present, warn or block. Either condition alone is not enough to
  block (Ops9-source FDR_* kinds on devel have not caused issues).

**Alternative when stitching is contraindicated:**

- Use `INTERNAL`-object MPs with `relationship_rules` that traverse the
  parent-child graph to reach VMWARE-native resources. INTERNAL objects
  are not affected by FDR_* kind registration because they do not
  perform adapter-kind metadata resolution against VMWARE. This remains
  the safer choice when the target instance is known to have Ops8
  federation history.

**This repo's affected MP:**

- `mpb_vcf_content_factory_vsphere_storage_paths` uses ARIA_OPS stitching
  on `VMWARE:HostSystem` and `VMWARE:Datastore`. It has been collecting
  cleanly on devel through the federated-state observation window. The
  v2 plan (`vsphere_storage_paths_v2_plan.md`) is unblocked for ARIA_OPS
  stitching against Ops9 targets. Prod (the Ops8-source instance) is
  still a known-bad target and should remain on a non-stitching path
  until that environment is upgraded or cleaned up.

---

## Open questions

1. **Ops9→Ops9 federation: same breakage as Ops8→Ops9?**
   Prod breakage was observed with an Ops8 source. Devel (T2) is pulling
   from another Ops9 instance. If devel's Storage Paths MP degrades over
   the next N collection cycles, the answer is yes — both directions pollute.
   If devel stays healthy, the trigger may be version-specific (Ops8 registered
   FDR_* kinds in a way that confuses Ops9's SDK metadata resolver; Ops9→Ops9
   may register FDR_* kinds that the SDK handles gracefully).

2. **Registration vs. active aggregation: which triggers breakage?**
   FDR_* kinds registered at T2 (first federation pull). Storage Paths still
   working at T2. If breakage occurs, when exactly? After the first full
   collection cycle? After a specific FDR_* resource crosses a threshold?
   After the FDR_VMWARE kind entry overwrites or collides with something in
   the adapter-kind registry that the SDK reads for VMWARE resolution?

3. **Is breakage reversible by stopping the federation pull?**
   Option A: Stop the FederatedAdapter instance. FDR_* resource population
   stops, but kinds remain registered. Does the SDK resume resolving VMWARE
   correctly without the kinds being removed?
   Option B: Uninstall the Aggregator solution. FederatedAdapter kind
   removed. FDR_* kinds remain (per prod evidence). Does this change SDK
   behavior?
   Option C: Database-level removal of FDR_* kind registrations. Unknown
   procedure; would require Broadcom support engagement.

4. **Relationship edges: the missing link?**
   At T2, VMWARE:Datastore resources have zero FDR_* relationship edges.
   If breakage is correlated with FDR_* edges appearing on native VMWARE
   resources (i.e., the federation creates parent-child links between
   FDR_Datastore and VMWARE:Datastore), the SDK failure mode could be
   "resolves to FDR_VMWARE kind instead of VMWARE kind due to relationship
   traversal." Watch for this in the relationship check section of the watch
   protocol.

5. **FDR_Datastore count (10) > VMWARE:Datastore count (8):**
   The extra 2 FDR_Datastore resources likely reflect prod inventory not
   present on devel. Confirms FDR_* is a full shadow graph of the source
   instance, not a filtered subset.

---

## Watch protocol

Run this check sequence after each federation collection cycle (15-minute
interval) until devel either breaks or stays clean for 24 hours.

### Check 1 — Storage Paths collection health

```
GET /api/adapters/f8cb5191-3fb7-4927-a7dc-ba438583ec08
```

Fields to watch:
- `messageFromAdapterInstance` — any non-empty value is a warning; a
  403 reference is breakage.
- `numberOfMetricsCollected` — should stay >= 42. Drop to 0 is breakage.
- `lastCollected` — should advance every ~15 min.

**Breakage signal:** `messageFromAdapterInstance` contains "403" or
"forbidden" or "metadata resolution"; OR `numberOfMetricsCollected` drops
to 0 with no infrastructure explanation (adapter not running, etc.).

### Check 2 — VMWARE:Datastore count stability

```
GET /api/resources?adapterKind=VMWARE&resourceKind=Datastore&pageSize=1
```

Field to watch:
- `pageInfo.totalCount` — must stay at 8.

**Breakage signal:** Count drops to 0 or changes unexpectedly.

### Check 3 — FDR_* kind count (stable vs. growing)

```
GET /api/adapterkinds
```

Count FDR_* keys. At T2: exactly 3. If new FDR_* kinds appear over time,
note them — it may indicate that additional source adapters register shadow
kinds on subsequent collection cycles.

### Check 4 — Relationship edge contamination on VMWARE:Datastore

Pick one stable VMWARE:Datastore resource (e.g., `0d5ab9d8-9861-4780-bbbc-c060e8268599`)
and run:

```
GET /api/resources/0d5ab9d8-9861-4780-bbbc-c060e8268599/relationships
```

Count resources where `resourceKey.adapterKindKey` starts with `FDR_`.
At T2: 0. If this count rises above 0, document the relationship type
and which FDR_* kind is involved — this would be strong evidence for
hypothesis 4 (relationship-traversal resolution confusion).

### Check 5 — Outside-client smoke test

```
GET /api/resources?adapterKind=VMWARE&resourceKind=Datastore&pageSize=1
```

Should return HTTP 200. If it returns 403 or 5xx from this client (which
authenticates with admin credentials), that would indicate a platform-level
change, not just an SDK MP collection failure.

### What constitutes "Ops9→Ops9 is NOT broken by federation alone"

All of the following must be true after >= 24 hours of active federation
(>= 96 collection cycles):
- Check 1: no error message, metrics >= 42, collection advancing.
- Check 2: VMWARE:Datastore count stable at 8.
- Check 3: FDR_* kind count stable at 3 (no new kinds added).
- Check 4: FDR_* relationship edge count on VMWARE:Datastore = 0.
- Check 5: HTTP 200 throughout.

If all five pass at 24h, the working hypothesis becomes: FDR_* shadow kinds
from an Ops9 source are registered but do not collide with the SDK's VMWARE
metadata resolution. The prod breakage may be Ops8-specific (different FDR_*
schema or different kind registration path).

### What constitutes breakage

Any one of:
- Check 1 error message containing "403"/"forbidden"/"metadata" with
  metrics collapsing.
- Check 2 count = 0.
- Check 5 HTTP 4xx/5xx.

If breakage occurs, immediately capture: the exact cycle number when it
started, the `messageFromAdapterInstance` verbatim, and the result of
Check 4 at that moment. These three data points will narrow hypothesis 4.
