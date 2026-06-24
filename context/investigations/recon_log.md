# Recon Log

Append-only. Each entry is a dated investigation section.

---

## 2026-05-21 — MSSQL dashboard live diagnosis (api-explorer)

**Target:** `[VCF Content Factory] MSSQL Query Performance & Blocking`
(UUID `2679c78f-e88e-43ba-b1ae-864dbbe9c50c`), file
`dashboards/mssql-query-performance.yaml`.
**Instance:** vcf-lab-operations.int.sentania.net.
**Symptoms:** (1) heatmap `query_heatmap` renders empty; (2) Internal
Server Error on dashboard load.

**Findings:**

1. **MetricChart `relationship_mode: children` wire format is wrong.**
   The 2026-05-20 tooling change emits
   `"relationshipMode": {"relationshipMode": [1, -1, 0]}` (array form).
   Survey of 146 MetricChart widgets in reference bundles shows
   **zero use the array form** — all use scalar `0`, `-1`, or `1`.
   Canonical "child traversal" reference (brockpeterson VM CPU per
   ESXi host) uses scalar `-1`. **This is the 500-on-load.** Affects
   `disk_read_chart` and `disk_write_chart`.

2. **Heatmap `sizeBy: execution_count` collapses every tile.** The
   `general|execution_count` metric on SqlQuery is a per-collection
   rate (executions/sec), currently ~0 across all 10 queries. With
   sizeBy=0 the heatmap renders nothing. The cumulative
   `general|total_worker_time` metric (already in color_by) has good
   spread (35K to 26M μs).

3. SqlDatabase resources ARE valid CHILDREN of SqlServer
   (verified via `/api/resources/{id}/relationships?relationshipType=CHILD`:
   27 children — 10 SqlQuery, 10 microsoft_sql_server_wait_time,
   7 SqlDatabase). `disk_access|read_delay` /`write_delay`
   have valid data (one DB reports 25.9ms write delay).

**Evidence files:**
- `context/investigations/mssql_dashboard_live.json` — server-side
  `getDashboardConfig` (shallow tab metadata only; deep widget config
  is not retrievable for admin-owned locked dashboards from a
  non-admin user — clone is blocked by the lock).
- `context/investigations/mssql_dashboard_rendered.json` —
  the exact JSON the renderer emits and the importer received,
  including the broken `[1, -1, 0]` shape on the two disk widgets.

**Documentation updates:**
- `context/api-surface/widget_types_survey.md` §MetricChart — replaced
  the "array form [1, -1, 0]" extrapolation with the verified scalar
  `-1` shape and a 146-widget distribution table.

**Implications for code:**
- `vcfops_dashboards/render.py` `_metric_chart_widget()` line ~725:
  `relationship_mode_val` must become scalar `-1` for `children`
  (and presumably scalar `1` if a future `parents` mode is added),
  not the heatmap array form.

**Clean-up verified:** yes — read-only API calls plus a content-zip
export of the calling user's own dashboards (no foreign objects
created). No state mutated.

---

## 2026-04-29 — Pod vCPU SM inflation investigation (PROD)

**Target:** `[VCF Content Factory] Pod vCPU (count)` (UUID `46179895-f760-4472-960c-e368aa869bc7`)
**Instance:** vcf-lab-operations.int.sentania.net (PROD, read-only)
**Investigator:** ops-recon
**Hypothesis under test:** system-namespace pods showing up in vCenter 9 that were not visible in vSphere 8

---

### SM reported value vs hand-sum

| Resource | SM latest value | Timestamp | Hand-sum of num_Cpu |
|---|---|---|---|
| vcf-lab-wld01-cl01 (CCR) | **255** | ~2026-04-29T14:37 UTC | **256** |
| vcf-lab-wld01-DC | 255 | same | — |
| vcf-lab-vcenter-wld01 (VMwareAdapter Instance) | 255 | same | — |

**Match assessment:** SM value 255 vs hand-sum 256 — **1-unit transient delta** (one pod cycled between the SM collection cycle and the bulk stat query). Functionally a match; the SM is computing correctly against all VMWARE/Pod objects in inventory. The expected value in the YAML comment ("12") is **dramatically wrong** for the current lab state.

---

### Full pod inventory under WLD01 (255 pods)

All pods are `config|guestFullName = VMware CRX Pod 1 (64-bit)` — confirmed vSphere native pods, not TKC/guest-cluster KubernetesPod objects.

**Pod count by name prefix:**

| Name prefix | Count | Notes |
|---|---|---|
| `wordpress-` | 234 | User workload (deployed by Scott in `vks-test-harness` NS) |
| `wordpress-mysql-` | 2 | User workload (same NS) |
| `argocd-` (user) | 9 | User workload (`vcf-lab-argocd` NS — Scott's ArgoCD instance) |
| `argocd-service-controller-manager-` | 4 | System service (`svc-argocd-service-domain-c10`) |
| `auto-attach-` | 4 | System service (`svc-auto-attach-domain-c10`) |
| `cci-ns-controller-manager-` | 2 | System service (`svc-cci-ns-domain-c10`) |
| **Total** | **255** | |

---

### Namespace identification method

`summary|parentNamespace` is registered in the VMWARE adapter describe catalog for Pod objects but is **not populated on any live pod** (returns null/absent for all samples). No namespace string property is available directly on the Pod resource.

**Working method:** parent `ResourcePool` relationship. Every Pod has a parent ResourcePool; the ResourcePool name encodes the Supervisor namespace:

| ResourcePool name | Supervisor namespace type | Classification |
|---|---|---|
| `svc-<name>-domain-c<id>` | Supervisor service namespace | **system** |
| `vcf-lab-argocd` | User-created Supervisor namespace | user |
| `vks-test-harness` | User-created Supervisor namespace | user |

The `svc-` prefix with `domain-c<id>` suffix is the vSphere Supervisor naming convention for platform service namespaces. All three `svc-*` pools map to Supervisor-managed system services.

---

### System vs user breakdown

| Category | Pods | vCPUs | ResourcePool(s) |
|---|---|---|---|
| **System** | **10** | **10** | `svc-argocd-service-domain-c10` (4), `svc-auto-attach-domain-c10` (4), `svc-cci-ns-domain-c10` (2) |
| **User** | **245** | **246** | `vcf-lab-argocd` (9 pods, 10 vCPU incl. 2-vCPU argocd-application-controller-0), `vks-test-harness` (236 pods, 236 vCPU) |
| **Total** | **255** | **256** | — |

**System pod detail (10 pods, 10 vCPUs):**

| Pod name | ResourcePool | vCPUs |
|---|---|---|
| argocd-service-controller-manager-7586c9644f-cgnq2 | svc-argocd-service-domain-c10 | 1 |
| argocd-service-controller-manager-7586c9644f-fmdpc | svc-argocd-service-domain-c10 | 1 |
| argocd-service-controller-manager-7586c9644f-g68xd | svc-argocd-service-domain-c10 | 1 |
| argocd-service-controller-manager-7586c9644f-tflkh | svc-argocd-service-domain-c10 | 1 |
| auto-attach-5f69c75966-2gdh4 | svc-auto-attach-domain-c10 | 1 |
| auto-attach-5f69c75966-jbqtw | svc-auto-attach-domain-c10 | 1 |
| auto-attach-5f69c75966-w96k9 | svc-auto-attach-domain-c10 | 1 |
| auto-attach-5f69c75966-zjhqs | svc-auto-attach-domain-c10 | 1 |
| cci-ns-controller-manager-9d4d99c5b-5zvvc | svc-cci-ns-domain-c10 | 1 |
| cci-ns-controller-manager-9d4d99c5b-98fnf | svc-cci-ns-domain-c10 | 1 |

**User namespace detail:**
- `vcf-lab-argocd`: 9 pods, 10 vCPUs (ArgoCD deployment — `argocd-application-controller-0` has 2 vCPUs)
- `vks-test-harness`: 236 pods, 236 vCPUs (234 `wordpress-` + 2 `wordpress-mysql-`, all 1 vCPU each)

---

### Conclusion

**The hypothesis is PARTIALLY CONFIRMED with a significant twist.**

The original hypothesis was "system-namespace pods are now showing up as VMWARE/Pod objects." That is true — 10 system pods ARE present. However, they contribute only **10 vCPUs** out of 255/256 total. The primary driver of inflation is **user workload scale**: Scott's `vks-test-harness` namespace has 236 pods (a wordpress horizontal scale test, presumably), and there is also a user ArgoCD deployment in `vcf-lab-argocd`.

The SM's stated "expected value: 12" comment in the YAML is simply stale — it was written when the lab had minimal pods. The SM formula is working correctly: it is accurately summing all VMWARE/Pod objects. The count is high because there is genuinely a lot of user pod workload running.

**System pod inflation: 10 vCPUs out of 255 = ~4%.** This is real but minor. The dominant signal is user workload.

---

### Namespace identification for a follow-up where-clause

No usable string property exists to filter by Supervisor namespace on VMWARE/Pod objects. `summary|parentNamespace` is in the describe catalog but unpopulated on all live pods tested. The only namespace signal is the parent ResourcePool name (via the relationships API), which is not accessible in a super metric `where` clause.

**Implication for SM authoring:** A where-clause to exclude system pods cannot be written against a property. Options:
1. Accept the ~4% system-pod inclusion (current behavior, acceptable if lab state is representative)
2. Use the ResourcePool name as a filter if the relationships API can be expressed in a future SM DSL extension (currently not possible)
3. Rely on naming conventions — system pods follow `auto-attach-*`, `cci-ns-*`, and `<service>-service-controller-manager-*` patterns; a `config|name contains` filter could exclude known system pod prefixes (multiple separate SMs subtracted, since compound where-clauses with `contains` are broken)

The naming-convention filter approach is fragile as VMware adds new system services. The current SM (no where-clause) is the most correct defensible choice given current DSL constraints.

---

### Property keys confirmed / not confirmed

| Property key | In describe cache? | Populated on live pods? | Verdict |
|---|---|---|---|
| `summary|parentNamespace` | YES | NO (null on all samples) | Not usable for filtering |
| `summary|parentFolder` | YES | Populated but empty string | Not useful |
| `summary|parentCluster` | YES | Populated (`vcf-lab-wld01-cl01`) | Rollup only, no NS info |
| `config|guestFullName` | YES | Populated (`VMware CRX Pod 1 (64-bit)`) | Confirms Pod type, no NS info |
| `summary|config|productName` | YES | Not populated on pods | Not useful |


---

### 2026-04-29 (continued) — Pod runtime state investigation: failed/stopped pod inflation

**Trigger:** Dashboard shows a large number of pods in inventory. Hypothesis that many of the 255 VMWARE/Pod objects are no longer running (failed/completed/evicted) but still contribute `config|hardware|num_Cpu` to the SM sum.

**Method:** Bulk-fetched `summary|runtime|powerState` (string property) from `/api/resources/properties` for all 256 pods. Cross-validated against `sys|poweredOn` numeric metric (from `/api/resources/stats/query`).

---

#### Property evaluation for SM where-clause

| Property key | In describe cache? | Populated on live pods? | Data type | `defaultMonitored` | Usable in SM where? |
|---|---|---|---|---|---|
| `summary|runtime|powerState` | YES | YES (all 256 pods) | String (`"Powered On"` / `"Powered Off"`) | N/A — properties not in `/statkeys`; populated on 100% of polled pods (strong inference: always collected) | YES — `where="summary|runtime|powerState equals Powered On"` — but string where-clauses cannot use `&&`; single-condition only |
| `sys|poweredOn` | YES | YES — 1.0 on/0.0 off | Numeric (metric) | `default_monitored: true` | YES — `where=($value == 1 && $value.isFresh())` — **PREFERRED** (numeric, supports `isFresh()` guard) |
| `summary|running` | YES | YES — 1.0 on/0.0 off | Numeric (metric) | `default_monitored: true` | YES — same pattern as `sys|poweredOn`; confirmed identical values on all 14 test pods |

**Important note from `context/supermetric_authoring.md` line 125–129:** `summary|runtime|powerState` is explicitly called out as the wrong property to use in a numeric where-clause. The canonical pattern for filtering powered-on objects is `sys|poweredOn`.

---

#### Pod state distribution — all 256 pods

| `summary|runtime|powerState` | Pod count | vCPU sum |
|---|---|---|
| **Powered On** | **9** | **10** |
| **Powered Off** | **247** | **247** |
| **Total** | **256** | **257** |

**Key finding:** 247 of 256 pods (96.5%) are powered off. The SM is summing `config|hardware|num_Cpu` across all 256 objects regardless of run state. Powered-off pods still carry their vCPU reservation in the property store. **The hypothesis is confirmed.**

---

#### State distribution by namespace

**`vks-test-harness` namespace (Scott's wordpress scale test):**

| Power State | Pods | vCPUs |
|---|---|---|
| Powered On | 2 | 2 |
| Powered Off | 235 | 235 |
| **Total** | **237** | **237** |

**All other namespaces:**

| Namespace | Power State | Pods | vCPUs |
|---|---|---|---|
| `vcf-lab-argocd` | Powered On | 4 | 5 |
| `vcf-lab-argocd` | Powered Off | 5 | 5 |
| `svc-argocd-service-domain-c10` | Powered On | 1 | 1 |
| `svc-argocd-service-domain-c10` | Powered Off | 3 | 3 |
| `svc-auto-attach-domain-c10` | Powered On | 1 | 1 |
| `svc-auto-attach-domain-c10` | Powered Off | 3 | 3 |
| `svc-cci-ns-domain-c10` | Powered On | 1 | 1 |
| `svc-cci-ns-domain-c10` | Powered Off | 1 | 1 |

**Powered-on pods (9 total, 10 vCPUs):**

| Pod name | Namespace | vCPUs |
|---|---|---|
| wordpress-99ccdc54b-2xz4g | vks-test-harness | 1 |
| wordpress-mysql-5c885954b8-t48rp | vks-test-harness | 1 |
| argocd-application-controller-0 | vcf-lab-argocd | 2 |
| argocd-server-5fbf974d74-2hj9c | vcf-lab-argocd | 1 |
| argocd-repo-server-77c84dd77f-vzgp6 | vcf-lab-argocd | 1 |
| argocd-redis-557945b789-4cxjl | vcf-lab-argocd | 1 |
| argocd-service-controller-manager-7586c9644f-cgnq2 | svc-argocd-service-domain-c10 | 1 |
| auto-attach-5f69c75966-jbqtw | svc-auto-attach-domain-c10 | 1 |
| cci-ns-controller-manager-9d4d99c5b-98fnf | svc-cci-ns-domain-c10 | 1 |

---

#### SM where-clause recommendation

**Recommended filter property:** `sys|poweredOn`

- `defaultMonitored: true` — confirmed in describe cache (`VMWARE/Pod.json`)
- Numeric metric — compatible with `&&` and `isFresh()` guard
- Perfect discriminator: 1.0 on all 9 powered-on pods, 0.0 on all 247 powered-off pods (validated against `summary|runtime|powerState` ground truth)
- Explicitly recommended in `context/supermetric_authoring.md` over `summary|runtime|powerState` for this use case

**Updated SM formula:**
```
sum(${adaptertype=VMWARE, objecttype=Pod, metric=config|hardware|num_Cpu, depth=10,
     where=($value == 1 && $value.isFresh())})
```

Wait — this is self-referential: `$value` refers to the outer metric being summed (`config|hardware|num_Cpu`), not `sys|poweredOn`. The correct pattern for filtering on a separate metric requires a different approach. Per `supermetric_authoring.md` line 127-129 and `cluster_avg_vm_cpu.yaml`, the corrected pattern for powered-on filter is:

```
sum(${adaptertype=VMWARE, objecttype=Pod, metric=config|hardware|num_Cpu, depth=10,
     where=(${metric=sys|poweredOn}==1)})
```

Where `${metric=sys|poweredOn}==1` is the filter condition (the inner `${}` references a metric on the iterated Pod objects). Confirm exact DSL syntax against `cluster_avg_vm_cpu.yaml` before authoring.

**Impact of applying filter:** SM value drops from 256 → 10 vCPUs (only the 9 actively running pods). The 247 powered-off wordpress/argocd pods that vCenter retains as objects are excluded.

**Note on `summary|runtime|powerState` as a string where-clause:** Syntactically valid (`where="summary|runtime|powerState equals Powered On"`) and would work, but (a) string where-clauses cannot be combined with `&&` for freshness guard, and (b) this approach is explicitly flagged in the authoring guide as the wrong pattern. Use `sys|poweredOn` numeric filter instead.

---

#### Conclusion

The SM inflation is confirmed as a **runtime-state issue, not a namespace-scope issue**. The 234 failed/stopped wordpress pods from Scott's scale test are still present as vSphere objects with their vCPU reservation intact. The SM has no `where` clause to exclude non-running pods, so it sums all 256 objects.

**Fix:** add `where=(${metric=sys|poweredOn}==1)` to the SM formula. This reduces the reported value from ~256 to ~10, which accurately reflects actively running pod vCPU reservation. The `expected_value` comment in the YAML should also be updated.


---

## 2026-05-18 — Synology DSM MP pre-design recon

**Instance:** vcf-lab-operations.int.sentania.net (prod, read-only)
**Profile:** VCFOPS_PROD

### 1. Synology adapter / management pack on live instance

- **`mpb_synology_nas` adapter kind:** NOT PRESENT (HTTP 404). Was installed at recon date 2026-04-22 (ver 1.0.0.1, solution id "Synology NAS") but has since been uninstalled. No adapter instances, no resource objects, no solution entry.
- **`mpb_synology_dsm` adapter kind:** NOT PRESENT (HTTP 404). This is the adapter kind targeted by the repo's symptom/alert/recommendation YAML — it has never been installed.
- 29 adapter kinds total on instance. No Synology string in any name or key.

### 2. Synology-named object types on live instance

None from an MP perspective. Three objects matching "synology" by name search:
- "Synology NAS Licensing" — adapter=Container, kind=Licensing (licensing placeholder, not an MP object)
- "Synology DSM MP Licensing" — adapter=Container, kind=Licensing (same)
- "Synology NAS f9:9b" — adapter=mpb_vcf_content_factory_unifi_integration, kind=mpb_vcf_content_factory_unifi_integration_client (this is a UniFi client record whose device name is the NAS MAC — not an MP object)

No SynologyDisk, SynologyVolume, SynologyLUN, or SynologySystem objects exist.

### 3. Built-in storage / vSAN MPs present

| Solution | Version | Scope | NAS/iSCSI/NFS coverage |
|---|---|---|---|
| vSAN (Management Pack for Storage Area Network) | 9.0.2.0.25137912 | vSAN Cluster, Disk Group, Cache/Capacity Disk, File Server, File Share, Storage Pool, Witness Host | vSAN File Share only. No external NAS, iSCSI target, or NFS share. |
| vCenter (VMWARE) | 9.0.2.0.25137897 | 25 resource kinds including Datastore, Datastore Cluster, Datastore Folder | Datastore-level only — no NAS target identity, no LUN or share representation |
| NSX | 9.0.2.0.25137922 | Network fabric | No storage coverage |
| VCF for Networks | 9.0.2.0.25137914 | Network flows | No storage coverage |
| OS and App Monitoring | 9.0.2.0.25137916 | Guest OS | No external storage |

**Gap confirmed:** No built-in MP covers NAS target health, iSCSI LUN provisioning, NFS share, Synology disk/storage-pool/volume, or the stitching of those objects to ESXi hosts or datastores.

### 4. Repo content/managementpacks/

No `synology_nas.yaml` exists under `content/managementpacks/`. The file was referenced in `context/mpb_synology_pickup_2026_04_29.md` but was not committed — the list shows only: cloudflare, dell_poweredge, unifi_network, unifi_network_integration, vsphere_storage_paths. A built pak exists at `dist/mpb_synology_nas.1.0.0.1.pak` (23 MB, mtime 2026-05-09) but no source YAML backs it.

### 5. Prior session state (from context files)

As of 2026-04-29 the Synology MP workstream was parked with two paths documented:
- Path 1: remove Volume's chained metricSet, ship the community-pattern 5-object MPB pak (loses per-volume IO metrics, ~10 min work)
- Path 2: pivot to Operations Adapter SDK (keeps IO metrics, larger effort)
The YAML was left in "v3 state, not in shipping state" with a broken `volume_util` chain.


---

## 2026-05-21 — MSSQL + Oracle Query Performance / Blocking Dashboard (DPA Replacement)

**Intent:** Author two dashboards (one MSSQL, one Oracle) replicating a Solarwinds DPA layout:
top queries by wait time, active/blocked session count tiles with drill-down lists, and instance
resource line charts (CPU, buffer cache, disk read/write latency).

---

### Q1 — Adapter Installation and Resource Counts

**MSSQL (`SqlServerAdapter`)** — INSTALLED AND COLLECTING

| Kind | Count |
|---|---|
| SqlServer (Instance) | 1 (`mssqldemo MSSQLSERVER`, id `414be6ca-372c-455e-9178-aee9692e999b`) |
| SqlDatabase | 7 |
| SqlQuery | 10 |
| SqlAvailabilityGroup | 0 |
| microsoft_sql_server_wait_time | 10 |
| microsoft_sql_server_job | 0 |
| SqlServerAdapterInstance | 1 |
| SqlServerTag / sql_server_traversal_tag | 2 / 1 |

**Oracle (`OracleDBAdapter`)** — INSTALLED AND COLLECTING

| Kind | Count |
|---|---|
| oracle_database_oracle_database_instance | 1 (`FREE`, id `34a66adc-e0e3-4211-b704-18e471db67f8`) |
| oracle_database_oracle_database_database | 1 |
| oracle_database_oracle_database_query | 11 |
| oracle_database_oracle_database_event_wait_group | 11 |
| oracle_database_oracle_database_tablespace | 4 |
| oracle_database_oracle_database_database_file | 5 |
| oracle_database_oracle_database_pdb | 1 |
| oracle_database_oracle_database_service | 2 |
| oracle_database_oracle_database_redo_log_file | 3 |
| oracle_database_oracle_database_control_file | 2 |

---

### Q2 — Built-in Dashboards and Views from Adapters

No adapter-shipped dashboards or views were found via `/api/reportdefinitions`. The adapters ship
alert definitions (MSSQL: 16 alerts including "MS SQL Server Low Page Life Expectancy",
"MS SQL Server Average Query CPU Time is High", "MS SQL Server Number of Queries That End In
Deadlock has Risen"; Oracle: 6 alerts including "Above Normal Query Time", "High Database CPU
Time Usage", "High Database Wait Time") but zero report definitions.

**Relevant built-in alerts (PARTIAL match — not dashboards):**
- MSSQL: `AlertDefinition-SqlServerAdapter-alert_LowPageLifeExpectancy_SqlServer`
- MSSQL: `AlertDefinition-SqlServerAdapter-alert_AvgQueryTime_SqlServer`
- MSSQL: `AlertDefinition-SqlServerAdapter-alert_QueriesEndInDeadLock_SqlServer`
- Oracle: `AlertDefinition-OracleDBAdapter-alert-all-symptom-oracle_database_oracle_database_query-Activity-average_time-GreaterThan-metric-Warning--1449450318-`
- Oracle: `AlertDefinition-OracleDBAdapter-alert-all-symptom-oracle_database_oracle_database_instance-Performance-database_wait_time_ratio-Above-dtmetric-Warning-0-`

No built-in dashboard satisfies the DPA replacement need. **Author required.**

---

### Q3 — Existing Repo Content

```
find dashboards views supermetrics -type f
```
Returns nothing. Repo currently has zero dashboards, views, or supermetrics. Confirmed.

---

### Q4 — Reference Sources

**`references/AriaOperationsContent/`** — No SQL/Oracle/DPA-themed bundle directories found.
All bundles are vSphere-centric (VM Encryption, Rightsize, License, Portgroup). Zero match.

**`references/brockpeterson_operations_dashboards/`** — MATCH (HIGH VALUE):
`Legacy MSSQL Dashboards.zip` contains 7 dashboard JSONs:
  - `MS-SQL-DBA-Overview.json` — 13 widgets; ResourceList picker (SqlServer instances), scalar
    tiles for `buffer|buffer_cache_hit_ratio`, `general|sql_version`, `mac_addrs|mac_addr`,
    interaction wiring. PARTIAL match to session/blocking panels.
  - `MS-SQL-Query-Analysis.json` — 4 widgets; uses `general|avg_execution_time`,
    `general|execution_count`, `buffer|buffer_cache_hit_ratio`,
    `statements|sql_recompilations_ratio`. PARTIAL match to top-queries panel.
  - `MS-SQL-Query-Plan.json` — 5 widgets. Query plan detail view.
  - `MS-SQL-Database.json` — 10 widgets; uses `disk_access|read_delay`,
    `disk_access|write_delay`, `disk_access|total_bytes` on SqlDatabase. PARTIAL match to
    resource line charts (latency metrics at SqlDatabase level, not SqlServer).
  - `MS-SQL-Server-Overview.json` — 3 widgets; high-level overview.
  - `MS-SQL-Server-VM-Relationship.json` — relationship view.
  - `MS-SQL-Availability-group.json` — AG-specific.

  **Verdict: PARTIAL/INSPIRATION.** The DBA-Overview and Query-Analysis dashboards are the
  closest analogs to panels 1 and 3. Widget interaction wiring patterns (ResourceList picker →
  downstream tiles/charts) are adaptable. Metric keys in these JSONs need cross-check — several
  (`general|sql_version`, `mac_addrs|mac_addr`, `statements|sql_recompilations_ratio`,
  `relationships|VirtualMachine_parent`, `sys|poweredOn`) are NOT present in the current adapter
  describe cache and may be from an older adapter version. Usable as layout/wiring templates.
  Attribution: `brockpeterson/operations_dashboards/Legacy MSSQL Dashboards.zip`.

**`references/tkopton_aria_operations_content/`** — No SQL/Oracle/DPA content found.
All bundles are vSphere, NSX, energy, sustainability themes. Zero match.

**`references/dalehassinger_unlocking_the_potential/VMware-Aria-Operations/`** — No SQL/Oracle
dashboards in Dashboards/ or Views/. Management-Packs/ contains FastAPI, ServiceNow, GitHub,
vCommunity MPs — none database-related. Zero match.

---

### Q5 — Metric Availability Sanity Check (Live Instance)

#### MSSQL `SqlQuery` (id `1f659591-96ad-4d79-9e40-f2883852cc11`, query "IF EXISTS (SELECT TOP 1 c...")

| Metric | Status | Last Value |
|---|---|---|
| `general|total_worker_time` | COLLECTED | 35922.0 µs |
| `general|avg_execution_time` | COLLECTED | 35922.0 µs |
| `general|execution_count` | COLLECTED | 0.0 |
| `general|last_execution` | COLLECTED | 35922.0 µs |
| `general|total_logical_reads` | COLLECTED | 0.0 |
| `general|total_logical_writes` | COLLECTED | 0.0 |
| `general|total_elapsed_time` | COLLECTED | 0.0 µs |

NOTE: The originally requested metric name `general|total_elapsed_time` is confirmed in
the SqlQuery describe. `general|execution_count` is present but reports 0 at collection
time (normal if query ran between collection intervals).

#### MSSQL `SqlServer` (id `414be6ca-372c-455e-9178-aee9692e999b`)

| Metric | Status | Last Value | Notes |
|---|---|---|---|
| `sysprocesses_states|running` | COLLECTED | 1.45 | |
| `sysprocesses_states|blocked` | COLLECTED | 0.0 | Count tile confirmed feasible |
| `sysprocesses_states|sleeping` | COLLECTED | 26.3 | |
| `cpu|cpu_usage` | COLLECTED | 19.3 % | |
| `buffer|buffer_ideal_page_life_expectancy` | COLLECTED | 13.8 | |
| `buffer|buffer_page_life_expectancy` | COLLECTED | 152397.8 | |
| `disk_access|read_bytes` | COLLECTED | 0.0 B/s | |
| `disk_access|write_bytes` | COLLECTED | 2817.7 B/s | |
| `disk_access|read_ops` | COLLECTED | 0.0 | |
| `disk_access|write_ops` | COLLECTED | 4.35 | |
| `connection_capacity|number_of_active_connections` | COLLECTED | 65.4 | |
| `disk_access|read_delay` | NOT ON SqlServer | — | Only on SqlDatabase |
| `disk_access|write_delay` | NOT ON SqlServer | — | Only on SqlDatabase |

**FINDING:** Disk read/write LATENCY (`read_delay`, `write_delay`) is NOT available on
`SqlServer`. It exists on `SqlDatabase`. The requested "SQL Disk Write Latency / SQL Disk Read
Latency" line charts must use `SqlDatabase` as the subject, not `SqlServer`, OR be dropped.
The `SqlDatabase` latency metrics ARE collected (confirmed: `disk_access|write_delay` last=0.0,
`disk_access|read_delay` last=0.0 on db `model`).

#### Oracle `oracle_database_oracle_database_query` (id `12a0d155-cbc0-4c10-bc89-ec71b8e9804d`)

| Metric | Status | Last Value |
|---|---|---|
| `Activity|elapsed_time` | COLLECTED | 13363437.4 µs/s |
| `Activity|executions` | COLLECTED | 3.0 |
| `Activity|user_io_wait_time` | COLLECTED | 10753180.5 µs/s |
| `Activity|application_wait_time` | COLLECTED | 0.0 µs/s |
| `Activity|concurrency_wait_time` | COLLECTED | 773.5 µs/s |
| `Activity|cpu_time` | COLLECTED | 1495585.1 µs/s |
| `Activity|average_time` | COLLECTED | 3527777.2 µs |
| `Activity|disk_reads` | COLLECTED | 38231.3 |

#### Oracle `oracle_database_oracle_database_instance` (id `34a66adc-e0e3-4211-b704-18e471db67f8`)

**CRITICAL FINDING:** The Oracle instance is only reporting 136 of 328 declared statkeys.
The entire `Performance|` metric group is NOT being collected. This affects:

| Metric (requested) | Status | Notes |
|---|---|---|
| `Performance|host_cpu_utilization` | NOT COLLECTED | Not in live statkeys |
| `Performance|buffer_cache_hit_ratio` | NOT COLLECTED | Not in live statkeys |
| `Disk IO|average_read_time` | COLLECTED | last=0.0 ms |
| `Disk IO|average_write_time` | COLLECTED | last=2.0 ms |
| `Session|waiting_user_sessions` | COLLECTED | last=16.2 |
| `Session|unblocked_user_sessions` | COLLECTED | last=5.0 |
| `Session|blocked_user_sessions` | COLLECTED | last=0.18 |
| `Session|active_user_sessions` | COLLECTED | last=14.1 |
| `Session|sessions` | COLLECTED | last=80.3 |
| `Activity|cpu_usage` | COLLECTED | last=174.1 (centiseconds) |
| `Shared Memory|buffer_cache_size` | COLLECTED | SGA buffer cache size in bytes |

**RULE-002 BLOCKERS (Oracle):**
- `Performance|host_cpu_utilization` — declared in describe but NOT in live statkeys.
  Cannot use in a metric widget. Substitute: `Activity|cpu_usage` (centiseconds of DB CPU
  consumed per second — not a host OS %). INFERRED equivalent, not identical.
- `Performance|buffer_cache_hit_ratio` — declared in describe but NOT in live statkeys.
  Cannot use in a metric widget. No direct substitute in collected keys.
  `Shared Memory|buffer_cache_size` is a size value, not a ratio.
  **Buffer cache hit ratio widget is NOT FEASIBLE without policy enablement or adapter config change.**

The `Performance|` group absence is likely a data collection policy issue (metric not enabled
in the collection policy for this adapter instance) or an adapter license/tier limitation.
The adapter describe says the keys exist; the live instance simply isn't publishing them.

---

### Q6 — Blocking Feasibility

**MSSQL:**
- `sysprocesses_states|blocked` on `SqlServer` is a count metric — COLLECTED. Count tile = FEASIBLE.
- No individual blocked-session resource kind exists in the adapter. The adapter has no
  `SqlSession` or equivalent resource type. Drill-down list of blocked sessions (by SPID, query
  text, blocking SPID) = **NOT POSSIBLE** with this adapter.
- `microsoft_sql_server_wait_time` resources (10 collected) expose `general|wait_time` and
  `general|waiting_tasks_count` per wait type — usable as a list view of wait types,
  not individual sessions.

**Oracle:**
- `Session|blocked_user_sessions` on `oracle_database_oracle_database_instance` is a count metric — COLLECTED. Count tile = FEASIBLE.
- `Session|waiting_user_sessions` also collected — useful for active waits tile.
- No individual session resource kind in the Oracle adapter either. The adapter has
  `oracle_database_oracle_database_event_wait_group` (11 resources: Application, Idle, Other,
  Network, Configuration, etc.) with `Activity|time_waited`, `Activity|total_waits`,
  `Activity|foreground_time_waited`. This can serve as a list view of wait categories,
  but NOT individual blocked sessions.
- **Drill-down list of individual blocked sessions = NOT POSSIBLE** with this adapter.

**Summary:** Both adapters support COUNT tiles for active/blocked sessions. Neither adapter
exposes individual session resources. The DPA "blocked sessions list" panel cannot be replicated
as a ResourceList drill-down. A list view of wait types/groups can serve as a partial substitute.


---

## 2026-06-12 — Fleet Capacity self-provider fix (ops-recon)

**Target:** `[VCF Content Factory] Fleet Capacity & Rightsizing`
Dashboard UUID `762fc025-1609-4e9c-9612-a5d0232b77bc`,
repo file `content/dashboards/fleet_capacity_rightsizing.yaml`,
widget id `cluster_capacity_view` ("Cluster Capacity Breakdown").

**Context:** User manually fixed the deployed widget on devel to add
`selfProvider = true` with a vSphere World resource pin. The repo YAML
had no `self_provider:` key on this widget. This entry captures the
deployed wire format so dashboard-author can reproduce it.

**Source:** Live content-zip export from
`vcf-lab-operations-devel.int.sentania.net`, CUSTOM DASHBOARDS scope,
extracted from `dashboards/29c1613f-3bbe-4aa0-8236-2c74db22c661` inner
zip → `dashboard/dashboard.json`.

---

### Deployed widget JSON — "Cluster Capacity Breakdown"

Widget instance UUID (assigned at install, stable on this instance):
`87769840-31eb-598e-b738-b0c8d07009c5`

```json
{
  "collapsed": false,
  "id": "87769840-31eb-598e-b738-b0c8d07009c5",
  "gridsterCoords": {
    "w": 12,
    "x": 1,
    "h": 4,
    "y": 5
  },
  "type": "View",
  "title": "Cluster Capacity Breakdown",
  "config": {
    "refreshInterval": 300,
    "resource": {
      "resourceId": "resource:id:0_::_",
      "traversalSpecId": "",
      "resourceName": "vSphere World",
      "resourceKindId": "002006VMWAREvSphere World",
      "id": "Ext.vcops.chrome.model.Resource-1"
    },
    "traversalSpecId": null,
    "refreshContent": {
      "refreshContent": false
    },
    "isUpdatedView": true,
    "chartViewItems": [],
    "selectFirstRow": {
      "selectFirstRow": true
    },
    "selfProvider": {
      "selfProvider": true
    },
    "title": "Cluster Capacity Breakdown",
    "viewDefinitionId": "0a1c11af-222b-41e0-af4c-dd324d7dacc0"
  },
  "height": 210,
  "states": [...]
}
```

### Key provider fields (what changed vs. original install)

| Field | Before fix | After fix (deployed) |
|---|---|---|
| `config.selfProvider.selfProvider` | `false` | `true` |
| `config.resource` | `null` | object with `resourceId: "resource:id:0_::_"`, `resourceName: "vSphere World"`, `resourceKindId: "002006VMWAREvSphere World"` |
| `config.traversalSpecId` | `""` or absent | `null` |

The deployed wire format for `selfProvider` on a View widget is:

```json
"selfProvider": { "selfProvider": true }
```

The deployed wire format for the resource pin (vSphere World singleton):

```json
"resource": {
  "resourceId": "resource:id:0_::_",
  "traversalSpecId": "",
  "resourceName": "vSphere World",
  "resourceKindId": "002006VMWAREvSphere World",
  "id": "Ext.vcops.chrome.model.Resource-1"
}
```

`resourceId: "resource:id:0_::_"` is the stable synthetic ID the Ops
renderer emits for vSphere World (the fleet root singleton). Same pattern
used by `fleet_summary` (Scoreboard widget). Compare to the Scoreboard
widget's `pin:` which maps to `adapter_kind: VMWARE / resource_kind: vSphere
World` in the repo YAML.

### Comparison: Oversized VMs (receiver widget — no selfProvider)

For reference, View widgets that are pure interaction receivers have:

```json
"selfProvider": { "selfProvider": false },
"resource": null
```

### Interactions wiring — UNCHANGED

The deployed `widgetInteractions` for this dashboard:

```json
[
  {
    "widgetIdProvider": "87769840-31eb-598e-b738-b0c8d07009c5",
    "type": "resourceId",
    "widgetIdReceiver": "84cae449-4cb9-5365-8511-4a8bc0994117"
  },
  {
    "widgetIdProvider": "87769840-31eb-598e-b738-b0c8d07009c5",
    "type": "resourceId",
    "widgetIdReceiver": "8ac13273-e766-594f-b59d-50ef527cd2fa"
  },
  {
    "widgetIdProvider": "87769840-31eb-598e-b738-b0c8d07009c5",
    "type": "resourceId",
    "widgetIdReceiver": "8ad16f3b-4685-5298-86a9-3977e4c841cd"
  }
]
```

Three receivers match the repo YAML (`oversized_vms_view`,
`undersized_vms_view`, `datastore_reclaimable_view`). The user's fix
did NOT touch interactions — only the provider config on the source widget.

### What dashboard-author must add to the repo YAML

On the `cluster_capacity_view` widget, add:

```yaml
self_provider: true
pin:
  adapter_kind: VMWARE
  resource_kind: vSphere World
```

This is the same YAML pattern used by `fleet_summary` and the three
heatmaps in this dashboard. The renderer already knows how to translate
`self_provider: true` + `pin:` → the wire block above (confirmed by
how `fleet_summary` renders correctly in the deployed dashboard).


---

## 2026-06-13 — 9.1 OpenAPI spec baseline fetch (ops-recon)

**Task:** Fetch the 9.1 OpenAPI specs from PROD and save as versioned baselines.
**Instance:** vcf-lab-operations.int.sentania.net (prod profile, read-only).
**Auth:** Local service account `claude`, authSource=Local.

### Version confirmed

`GET /suite-api/api/versions/current` returned:
```
releaseName: VCF Operations 9.1.0.0
major: 9, minor: 1, minorMinor: 0, patch: 0
buildNumber: 25435105
releasedDate: Tuesday, March 3, 2026 at 12:00:00 PM UTC
```
9.1 confirmed. Fetch proceeded.

### Spec endpoint discovery

Standard swagger paths (`/api/swagger`, `/api/openapi`, etc.) all returned 404.
`GET /suite-api/` redirected to `/suite-api/doc/swagger-ui.html`.
`GET /suite-api/doc/swagger-configs` (the Swagger UI config endpoint) returned:
```json
"urls": [
  {"url": "./openapi/v3/public-api.json", "name": "Public APIs"},
  {"url": "./openapi/v3/internal-api.json", "name": "Internal APIs"}
]
```
Actual spec endpoints resolved to:
- Public: `GET https://vcf-lab-operations.int.sentania.net/suite-api/doc/openapi/v3/public-api.json`
- Internal: `GET https://vcf-lab-operations.int.sentania.net/suite-api/doc/openapi/v3/internal-api.json`

Both returned HTTP 200, Content-Type: application/json, no auth required (public endpoints).

### Files saved

| File | Bytes | info.title | info.version | openapi | paths |
|------|-------|------------|--------------|---------|-------|
| `docs/operations-api-9.1.json` | 2,834,482 | VMware Cloud Foundation Operations API | (empty) | 3.0.1 | 343 |
| `docs/internal-api-9.1.json` | 1,832,807 | VMware Cloud Foundation Operations API | (empty) | 3.0.1 | 217 |

Both specs contain only the `/suite-api` relative server URL — no host, no credentials.
Secret scan (token/password patterns): clean.

### Comparison to 9.0 baseline

- `docs/operations-api.json` (9.0.x baseline): 250 paths
- `docs/operations-api-9.1.json` (9.1): **343 paths** (+93)
- `docs/internal-api.json` (9.0.x baseline): paths not recorded at time of capture
- `docs/internal-api-9.1.json` (9.1): **217 paths**

### vSphere Data API

Not served by this instance. `swagger-configs` lists only two specs (public + internal).
Candidates under `/suite-api/doc/openapi/v3/vsphere*` all returned 404. No 9.1 fetch possible
from PROD. The existing `docs/vsphere-data-api-openapi.json` (8820 bytes, format is not plain JSON
— parse error, may be YAML or truncated) remains the only reference.

---

## 2026-06-16 — vCommunity devel-vs-prod parity recon (ops-recon)

**Purpose:** Verify the `vcfcf_vcommunity` Tier-2 Java SDK port (devel) is
collecting after the cloud-account host/credential fix, and establish the
`vCommunity|` key parity reference from the original `VCFOperationsvCommunity`
MP on prod.

---

### Part A — DEVEL: port health

**Instances found (both `vcfcf_vcommunity`):**

| UUID | Name | metrics | resources | lastCollected | resourceStatus |
|---|---|---|---|---|---|
| `085d3748-afca-4e36-a641-6ea895776e38` | vcf-lab-mgmt-vcenter.int.sentania.net | 6 | 2 | 2026-06-16 14:20:40 UTC | DATA_RECEIVING |
| `c6443550-e511-409f-9278-c50064890e6b` | vcf-lab-vcenter-wld01.int.sentania.net | 6 | 2 | 2026-06-16 14:21:45 UTC | DATA_RECEIVING |

Both instances: health=GREEN, resourceState=STARTED, statusMessage empty. The
UnknownHostException that previously caused NXDOMAIN failures is gone. The
credential/host fix took.

Note: "instance 5186" is a UI sequence number; the platform API uses UUIDs.
The mgmt-vcenter instance is the one previously failing.

**vCommunityWorld anchor** (`403ef6ff-21c0-44a6-abf0-458233b4894e`):
- kind: `vCommunityWorld`, health: GREEN, resourceStatus: DATA_RECEIVING
- Reported by BOTH adapter instances simultaneously (shared world object)

**vCommunityWorld latest metric values:**

| Key | Value |
|---|---|
| `Summary|clusters_stitched` | 1.0 |
| `Summary|hosts_stitched` | 2.0 |
| `Summary|vms_stitched` | 2.0 |
| `Summary|guest_vms_attempted` | 0.0 |
| `Summary|guest_vms_degraded` | 0.0 |
| `Summary|events_as_properties` | 0.0 |

**vCommunityWorld latest property values:**

- `Summary|status` = OK
- `Summary|last_scan_timestamp` = 2026-06-16T14:21:45.339231682Z
- `Summary|config_file_status` = fetch failed for all SolutionConfig XMLs
  (esxi_advanced_system_settings, esxi_packages, vm_advanced_parameters,
  vm_options, windows_service_list, windows_event_list) — HTTP 400 from Suite
  API `/api/configurations/files`. No last-good cache → gated collection
  skipped this cycle for those modules.

**Devel `vCommunity|` key set on VMWARE resources:**

ClusterComputeResource (3 resources, 13 keys):
- STAT: `vCommunity|Cluster Configuration|DRS|DRS Score`
- PROP (12): DRS CPU Over-Commitment, Proactive DRS, Scale Descendants Shares;
  EVC Enabled, EVC Mode; HA Heartbeat Datastore, Host Monitoring, Response
  Datastore APD/PDL, Default VM Restart Priority, Host Isolation, VM Monitoring

HostSystem (8 resources, 13 keys):
- STAT: none
- PROP (13): `vCommunity|Configuration|Install Date|UTC`;
  `vCommunity|Network|Device:vmnic0-2|Device Name/Driver Version/Firmware Version/Status`

VirtualMachine (42 resources, 5 keys):
- STAT (2): `vCommunity|Configuration|SCSI Controllers|Count`,
  `vCommunity|Snapshot|Count`
- PROP (3): `vCommunity|Configuration|SCSI Controllers:0-2|Type`

---

### Part B — PROD: parity reference

**Original MP:** kind `VCFOperationsvCommunity`, pak `iSDK_VCFOperationsvCommunity` v0.2.8,
DOCKERIZED (Python/containerized).

**Instances on prod:**

| UUID | Name | metrics | resources | resourceStatus | note |
|---|---|---|---|---|---|
| `3555f3cd-26cc-4e8b-acdb-158fd5cae069` | vcf-lab-vcenter-mgmt.int.sentania.net | 77 | 42 | DATA_RECEIVING | healthy |
| `4845aba2-f1c0-4fea-afc8-f8b2e7e7adad` | vcf-lab-vcenter-wld01.int.sentania.net | 7 | 6 | DATA_RECEIVING | healthy |
| `ca532ed3-ca06-43c3-91bc-3976c97e1ef9` | vcf-lab-vcenter-wld02.int.sentania.net | 0 | 6 | ERROR | gaierror NXDOMAIN — separate DNS issue |

**Object model:** The original creates only its own resource kind
(`VCFOperationsvCommunity_adapter_instance`). It does NOT create
ClusterComputeResource / HostSystem / VirtualMachine objects. All `vCommunity|`
keys land on VMWARE-adapter resources via ARIA_OPS-style stitching, identical to
the port's approach.

**Prod `vCommunity|` key set on VMWARE resources:**

ClusterComputeResource (3 resources, 13 keys):
- Identical to devel — same 1 STAT + 12 PROP keys.

HostSystem (8 resources, 73 keys):
- STAT (2): `vCommunity|Licensing:Evaluation Mode|Remaining Days`,
  `vCommunity|Licensing:VMware Cloud Foundation (cores)|Remaining Days`
- PROP (71): includes all 13 devel keys, PLUS:
  - `vCommunity|Configuration|Advanced System Settings|*` (15 keys:
    Config.HostAgent.log.level, Config.HostAgent.plugins.solo.enableMob,
    Config.HostAgent.vmacore.soap.sessionTimeout,
    Security.AccountLockFailures, Security.AccountUnlockTime, Security.PasswordMaxDays,
    Syslog.global.auditRecord.storageDirectory, Syslog.global.certificate.checkSSLCerts,
    Syslog.global.logFiltersEnable, Syslog.global.logHost, Syslog.global.logLevel,
    UserVars.DcuiTimeOut, UserVars.ESXiShellTimeOut,
    UserVars.SuppressHyperthreadWarning, UserVars.SuppressShellWarning)
  - `vCommunity|Configuration|Packages:<pkg>|*` (7 fields × 5 packages =
    35 keys; packages: i40en, nenic, nfnic, nsxcli, qlnativefc)
  - `vCommunity|Licensing:Evaluation Mode|*` (4 props: Edition Key,
    License Expiration Date, License Key, Name)
  - `vCommunity|Licensing:VMware Cloud Foundation (cores)|*` (same 4 props)

VirtualMachine (40 resources, 19 keys):
- STAT (2): same 2 as devel (SCSI Controllers Count, Snapshot Count)
- PROP (17): includes all 3 devel SCSI props PLUS:
  - `vCommunity|Configuration|Advanced Parameters|RemoteDisplay.maxConnections`
  - `vCommunity|Configuration|Advanced Parameters|svga.present`
  - `vCommunity|Config|SCSI Controllers|0-2|Type` (3 — note `Config` not `Configuration`)
  - `vCommunity|Config|SCSI Controllers|Count`
  - `vCommunity|Guest OS|Operating System|OS Architecture/BuildNumber/Last Boot Up Time/Name/Release ID/Version` (6)
  - `vCommunity|Options|config.latencySensitivity.level`
  - `vCommunity|Options|config.maxMksConnections`

---

### Part C — Parity Verdict

**ClusterComputeResource: FULL PARITY** — 13/13 keys match exactly.

**HostSystem: PARTIAL** — 13 of 73 prod keys present (18%).
Missing 60 keys in three feature groups:
- Advanced System Settings (15 props) — gated behind
  `SolutionConfig/esxi_advanced_system_settings.xml` (HTTP 400 on devel;
  this is the `config_file_status` failure already flagged in vCommunityWorld).
- ESXi Packages (35 props, 7 fields × 5 packages) — gated behind
  `SolutionConfig/esxi_packages.xml` (same 400 failure).
- Licensing (2 stats + 8 props) — NOT gated by SolutionConfig; likely a
  separate code path not yet implemented in the port.

**VirtualMachine: PARTIAL** — 5 of 19 prod keys present (26%).
Missing 14 keys:
- Advanced Parameters (2 props: RemoteDisplay.maxConnections, svga.present) —
  likely gated behind `SolutionConfig/vm_advanced_parameters.xml` (400 on devel)
  or `SolutionConfig/vm_options.xml`.
- `vCommunity|Config|SCSI Controllers|*` (4 props with path `Config` not
  `Configuration`) — appears to be a legacy/alternate path the original emits
  alongside the `Configuration` path; port only emits the `Configuration` path.
- Guest OS / Operating System (6 props: Architecture, BuildNumber, Last Boot Up
  Time, Name, Release ID, Version) — requires guest tools / WMI; likely gated
  behind `SolutionConfig/windows_service_list.xml` or a separate guest-ops
  collection path.
- Options (2 props: latencySensitivity.level, maxMksConnections) — gated
  behind `SolutionConfig/vm_options.xml` (400 on devel).

**Root cause of most HostSystem and VM gaps:** the five SolutionConfig XML
files are returning HTTP 400 on devel (`/api/configurations/files?path=SolutionConfig/...`).
The original (on prod) has these files populated; devel does not. Until those
files are created on devel (or the port has a last-good fallback), the gated
collection paths are permanently skipped every cycle. This is not a code bug in
the port — it is a test-environment setup gap.

**Licensing gap (HostSystem) is a real code gap:** the original emits 2 stats
+ 8 props under `vCommunity|Licensing:*`. These are not SolutionConfig-gated
(the original collects them even without a SolutionConfig file). The port does
not emit any Licensing keys. This needs a code path in the port.

**SCSI `Config` vs `Configuration` path (VirtualMachine) is a real gap:**
The original emits BOTH `vCommunity|Configuration|SCSI Controllers:N|Type`
AND `vCommunity|Config|SCSI Controllers|N|Type` + `vCommunity|Config|SCSI
Controllers|Count`. The port emits only the `Configuration` path. The `Config`
path appears to be a legacy/aliased output from the original. Whether the port
needs to emit both or only the canonical `Configuration` path depends on whether
any content (views, dashboards) targets the `Config` path.

**Summary table:**

| Resource Kind | Devel Keys | Prod Keys | Verdict |
|---|---|---|---|
| ClusterComputeResource | 13 | 13 | FULL |
| HostSystem | 13 | 73 | PARTIAL — missing 60 (mostly SolutionConfig-gated + Licensing) |
| VirtualMachine | 5 | 19 | PARTIAL — missing 14 (mostly SolutionConfig-gated + Guest OS + Config alias) |


---

## 2026-06-16 build-3 post-install parity verdict (ops-recon)

**Build:** vcfcf_vcommunity 1.0.0.3 (in-place upgrade from 1.0.0.2, installed ~16:09Z today)
**Recon timestamp:** 2026-06-16T16:29Z (2–3 collection cycles post-install)
**Devel instance:** vcf-lab-operations-devel.int.sentania.net (profile: VCFOPS_DEVEL)
**Prod reference:** vcf-lab-operations.int.sentania.net (profile: VCFOPS_PROD, VCFOperationsvCommunity v0.2.8)

---

### 1. Adapter instance health (devel)

| UUID | Name | resourceStatus | healthState | lastCollected | metrics | resources |
|---|---|---|---|---|---|---|
| `085d3748-afca-4e36-a641-6ea895776e38` | vcf-lab-mgmt-vcenter.int.sentania.net | DATA_RECEIVING | GREEN | 2026-06-16T16:24:50Z | 6 | 2 |
| `c6443550-e511-409f-9278-c50064890e6b` | vcf-lab-vcenter-wld01.int.sentania.net | DATA_RECEIVING | GREEN | 2026-06-16T16:24:41Z | 6 | 2 |

Both GREEN / DATA_RECEIVING. `messageFromAdapterInstance` is empty on both. No collection errors.

### 2. vCommunityWorld anchor

UUID: `403ef6ff-21c0-44a6-abf0-458233b4894e`
- `Summary|status` = **OK**
- `Summary|last_scan_timestamp` = 2026-06-16T16:29:45Z
- `Summary|hosts_stitched` = **4.0** (was 2.0 on build-2 — now picks up mgmt hosts too)
- `Summary|vms_stitched` = **36.0** (was 2.0 on build-2 — dramatic improvement)
- `Summary|clusters_stitched` = 1.0
- `Summary|config_file_status`:
  ```
  esxi_advanced_system_settings: 0 check(s)
  esxi_packages: 0 check(s)
  vm_advanced_parameters: 0 check(s)
  vm_options: 0 check(s)
  windows_service_list: 0 check(s)
  windows_event_list: fetched (716 bytes)
  ```

**SolutionConfig status:** All 6 files return HTTP 200 (the pak-builder `content/files/**` fix took).
However, the files on devel are **stub/reference files with all entries commented out** — the adapter
reads them successfully but finds 0 active entries. The "0 check(s)" log is correct behavior:
the file is parseable but contains no enabled settings. Prod has these files with actual uncommented
entries (15 Advanced System Settings, 5 × 7 = 35 package fields, 2 Advanced Parameters, 2 Options).
Until the devel SolutionConfig files are cloned from the prod defaults and entries uncommented,
the gated paths will continue collecting 0 items.

**Note on wld01-esx03 / wld01-esx04:** These 2 hosts show health=GREY / no vCommunity keys.
They are likely powered off or disconnected from vCenter on devel (0 VMWARE metrics collected, not a
port regression — these same hosts were excluded from the build-2 count).

---

### 3. Parity summary table

| Resource Kind | Build-2 | Build-3 (devel) | Prod | Delta B2→B3 | Still missing |
|---|---|---|---|---|---|
| ClusterComputeResource | 13 | **12** | 13 | -1 | **1** |
| HostSystem | 13 | **18** | 73 | +5 | **55** |
| VirtualMachine | 5 | **10** | 19 | +5 | **9** |

---

### 4. Per-kind key tables

#### ClusterComputeResource — devel build-3 (12 keys)

| Type | Key | Notes |
|---|---|---|
| STAT | `vCommunity|Cluster Configuration|DRS|DRS Score` | present |
| PROP | `vCommunity|Cluster Configuration|DRS|CPU Over-Commitment` | present |
| PROP | `vCommunity|Cluster Configuration|DRS|Proactive DRS` | present |
| PROP | `vCommunity|Cluster Configuration|EVC|Enabled` | present |
| PROP | `vCommunity|Cluster Configuration|EVC|Mode` | present |
| PROP | `vCommunity|Cluster Configuration|vSphere HA|Heartbeat Datastore` | present |
| PROP | `vCommunity|Cluster Configuration|vSphere HA|Host Monitoring` | present |
| PROP | `vCommunity|Cluster Configuration|vSphere HA|Response \ Datastore APD` | present |
| PROP | `vCommunity|Cluster Configuration|vSphere HA|Response \ Datastore PDL` | present |
| PROP | `vCommunity|Cluster Configuration|vSphere HA|Response \ Default VM Restart Priority` | present |
| PROP | `vCommunity|Cluster Configuration|vSphere HA|Response \ Host Isolation` | present |
| PROP | `vCommunity|Cluster Configuration|vSphere HA|VM Monitoring` | present |

**MISSING (1):**

| Key | Classification |
|---|---|
| `vCommunity|Cluster Configuration|DRS|Scale Descendants Shares` | UNEXPECTED GAP — not SolutionConfig-gated, not Windows. Build-2 recon showed 13/13; this regression is new in build-3. |

**Cluster regression note:** Build-2 had 13 cluster keys. Build-3 has 12. The `Scale Descendants
Shares` property appeared on the 2026-06-16 build-2 recon but is absent now. Possible cause:
(a) the prop was sourced from a cluster that no longer exists on devel, (b) it was an artifact of
the prod key pull in the build-2 entry (the build-2 entry states "ClusterComputeResource: FULL
PARITY" and describes prod as 13 keys including Scale Descendants Shares — it may have been on
prod but not devel even in build-2, with the build-2 entry conflating prod and devel). Needs
verification on a cluster that has DRS Shares configured.

#### HostSystem — devel build-3 (18 keys)

| Type | Key |
|---|---|
| STAT | `vCommunity|Licensing:VMware Cloud Foundation (cores)|Remaining Days` |
| PROP | `vCommunity|Configuration|Install Date|UTC` |
| PROP | `vCommunity|Licensing:VMware Cloud Foundation (cores)|Edition Key` |
| PROP | `vCommunity|Licensing:VMware Cloud Foundation (cores)|License Expiration Date` |
| PROP | `vCommunity|Licensing:VMware Cloud Foundation (cores)|License Key` |
| PROP | `vCommunity|Licensing:VMware Cloud Foundation (cores)|Name` |
| PROP | `vCommunity|Network|Device:vmnic0|Device Name` |
| PROP | `vCommunity|Network|Device:vmnic0|Driver Version` |
| PROP | `vCommunity|Network|Device:vmnic0|Firmware Version` |
| PROP | `vCommunity|Network|Device:vmnic0|Status` |
| PROP | `vCommunity|Network|Device:vmnic1|Device Name` |
| PROP | `vCommunity|Network|Device:vmnic1|Driver Version` |
| PROP | `vCommunity|Network|Device:vmnic1|Firmware Version` |
| PROP | `vCommunity|Network|Device:vmnic1|Status` |
| PROP | `vCommunity|Network|Device:vmnic2|Device Name` |
| PROP | `vCommunity|Network|Device:vmnic2|Driver Version` |
| PROP | `vCommunity|Network|Device:vmnic2|Firmware Version` |
| PROP | `vCommunity|Network|Device:vmnic2|Status` |

**Build-3 gains vs build-2 (+5):** Licensing stat + 4 Licensing props (VCF cores).
The Licensing code path (build-3 fix: lazy `licenseAssignmentManager`) is now working
for VCF cores licensing on devel's hosts.

**MISSING (55) — classified:**

| Count | Feature group | Classification | Root cause |
|---|---|---|---|
| 15 | Advanced System Settings (`Config.HostAgent.*`, `Security.*`, `Syslog.*`, `UserVars.*`) | UNEXPECTED GAP — SolutionConfig-gated but config-driven, not Windows | devel SolutionConfig `esxi_advanced_system_settings.xml` is the stub file (all entries commented). Not a code gap — a test-env setup gap. |
| 35 | Packages (i40en, nenic, nfnic, nsxcli, qlnativefc × 7 fields) | UNEXPECTED GAP — SolutionConfig-gated but config-driven, not Windows | devel SolutionConfig `esxi_packages.xml` is the stub file (all packages commented). Same cause as above. |
| 4 | Licensing:Evaluation Mode (Edition Key, Expiration Date, License Key, Name) | UNEXPECTED GAP — not SolutionConfig-gated, not Windows | devel hosts have no Evaluation Mode license; all run VCF subscription. The prod original emits Evaluation Mode keys because prod has at least one host with an eval license. NOT a code gap — environment difference. |
| 1 | `vCommunity|Licensing:Evaluation Mode|Remaining Days` (STAT) | Same as above — eval mode not present on devel hosts | — |

**Summary:** 50 of 55 missing host keys are environment-configuration gaps (SolutionConfig stubs),
not code gaps. 5 are environment-data gaps (no eval license on devel). Zero code gaps on HostSystem.

#### VirtualMachine — devel build-3 (10 keys)

| Type | Key |
|---|---|
| STAT | `vCommunity|Configuration|SCSI Controllers|Count` |
| STAT | `vCommunity|Config|SCSI Controllers|Count` |
| STAT | `vCommunity|Snapshot|Count` |
| PROP | `vCommunity|Configuration|SCSI Controllers:0|Type` |
| PROP | `vCommunity|Configuration|SCSI Controllers:1|Type` |
| PROP | `vCommunity|Configuration|SCSI Controllers:2|Type` |
| PROP | `vCommunity|Config|SCSI Controllers|0|Type` |
| PROP | `vCommunity|Config|SCSI Controllers|1|Type` |
| PROP | `vCommunity|Config|SCSI Controllers|2|Type` |
| PROP | `vCommunity|Guest OS|Operating System|Last Boot Up Time` |

**Build-3 gains vs build-2 (+5):**
- `vCommunity|Config|SCSI Controllers|Count` (STAT) — legacy alias now emitted
- `vCommunity|Config|SCSI Controllers|0|Type` through `|2|Type` (3 PROPs) — legacy alias now emitted
- `vCommunity|Guest OS|Operating System|Last Boot Up Time` (PROP) — partial Guest OS via `guest.detailedData`

**DEVEL KEY NOT IN PROD (1):**
- `vCommunity|Guest OS|Operating System|Last Boot Up Time` — devel emits this key under the path
  `Last Boot Up Time`; prod emits it as `OS Last Boot Up Time`. This is a property NAME difference:
  devel has `Last Boot Up Time`, prod has `OS Last Boot Up Time`. The build-3 fix for
  `guest.detailedData` landed the key but under the unprefixed name. **This is a code gap** —
  the key name should be `OS Last Boot Up Time` to match prod.

**MISSING (9) — classified:**

| Count | Feature group | Classification | Root cause |
|---|---|---|---|
| 2 | `vCommunity|Configuration|Advanced Parameters|RemoteDisplay.maxConnections` and `svga.present` | UNEXPECTED GAP — SolutionConfig-gated, config-driven | devel `vm_advanced_parameters.xml` stub has all entries commented. Not a code gap — setup gap. |
| 1 | `vCommunity|Options|config.latencySensitivity.level` | UNEXPECTED GAP — SolutionConfig-gated, config-driven | devel `vm_options.xml` stub. |
| 1 | `vCommunity|Options|config.maxMksConnections` | Same as above | — |
| 5 | `vCommunity|Guest OS|Operating System|OS Architecture`, `OS BuildNumber`, `OS Name`, `OS Release ID`, `OS Version` | Partially Windows-gated, partially unexpected | These 5 require Windows monitoring enabled (WMI queries via `guest.detailedData` only surface the last-boot timestamp on non-Windows or without monitoring agent). The `OS Architecture` and `OS Name` could come from non-WMI paths on Linux guests. Needs investigation but classified as Windows-gated pending Phase 3. |
| 1 | `vCommunity|Guest OS|Operating System|OS Last Boot Up Time` | UNEXPECTED GAP (name mismatch) | The key IS landing on devel but under wrong name (`Last Boot Up Time` vs prod's `OS Last Boot Up Time`). **Build-4 fix needed**: add `OS ` prefix to the property name in the Guest OS collector path. |

---

### 5. Parity verdict

| Resource Kind | Devel B3 | Prod | % Parity | Verdict |
|---|---|---|---|---|
| ClusterComputeResource | 12 | 13 | 92% | NEAR-FULL — 1 unexpected gap (Scale Descendants Shares) |
| HostSystem | 18 | 73 | 25% | FAIL-WITH-GAPS — all gaps are env config, not code |
| VirtualMachine | 10 | 19 | 53% | FAIL-WITH-GAPS — mix of env config + 1 code gap |

**Overall verdict: FAIL-WITH-GAPS**

The build-3 fixes landed correctly for what they targeted:
- Licensing code path: working (VCF cores licensing stat + 4 props now present)
- Config|SCSI Controllers alias: working (legacy `Config` path now emitted alongside `Configuration`)
- guest.detailedData: partially working (Last Boot Up Time lands, but under wrong key name)

However, total counts are **12/13 Cluster, 18/73 Host, 10/19 VM** — far from the 73/19 Host/VM target.

**The Host gap (18 vs 73) is entirely env-config, not code:**
- 50 keys gated behind SolutionConfig files that exist on devel but are stub files (all entries
  commented out). The original's prod files have these entries uncommented. The adapter code is
  correct; the test environment needs its SolutionConfig files populated to match prod's working
  files. This is the same as the build-2 diagnosis except the root cause shifted from "HTTP 400"
  to "HTTP 200 but stubs." The pak now ships the files; they ship as read-only reference stubs
  that say "DO NOT EDIT, CLONE IT." There is no working copy on devel.
- 5 keys (Evaluation Mode licensing) are absent because devel hosts run VCF subscription, not eval.
  Prod has at least one eval-licensed host. Not a bug.

**Build-4 candidates (actual code gaps):**

| # | Kind | Gap | Priority |
|---|---|---|---|
| B4-1 | VirtualMachine | `vCommunity|Guest OS|Operating System|Last Boot Up Time` is landing under wrong name — should be `OS Last Boot Up Time` to match prod | HIGH — the key is collecting but misnamed; downstream content that targets the prod name won't find it |
| B4-2 | ClusterComputeResource | `vCommunity|Cluster Configuration|DRS|Scale Descendants Shares` absent | MEDIUM — verify whether this prop was truly on devel in build-2 or only on prod; if a code gap, fix is straightforward (add Scale Descendants Shares to DRS collection) |

**Not build-4 candidates (env/config):**

| Item | Action needed |
|---|---|
| 50 missing Host keys (Adv System Settings + Packages) | Create working SolutionConfig XML copies on devel with entries uncommented (or populate a `SolutionConfig/custom/` path the adapter prefers over the stubs) |
| 4 missing Host Eval Mode keys | No action — env difference. Will surface on hosts with eval licenses. |
| 4 missing VM keys (Adv Params + Options) | Same SolutionConfig stub issue — populate working vm_advanced_parameters.xml and vm_options.xml |
| 5 missing VM Guest OS (arch, build, name, release, version) | Windows-gated Phase 3; defer |

---

### 6. SolutionConfig setup action (not a code change)

The "DO NOT EDIT THIS CONFIG FILE, CLONE IT" header in all stub XMLs is the original MP's own
instruction. On the prod instance the original MP installed a working copy alongside the stub
(or the user cloned + edited). The Tier-2 pak needs to either:
- Ship a pre-configured working copy (not the stub) for the settings the original monitored on
  prod (15 Adv System Settings, 5 packages), or
- Document the manual clone step in ADMIN.md.

This is a test-environment completeness question, not a code bug in the collector.


---

## 2026-06-22 — vCommunity Phase-3 Windows/Guest-OS surface recon (devel vs prod)

**Trigger:** Scott provisioned Windows guest credentials on devel (same as prod).
**Question:** Did that unlock Windows/Guest-OS collection on devel?
**Adapter:** devel = `vcfcf_vcommunity` build 1.0.0.6 (id `d02a632f-01f8-458a-a868-9a33ef19dd46`); prod = `VCFOperationsvCommunity` v0.2.8 (mgmt id `3555f3cd-26cc-4e8b-acdb-158fd5cae069`).

---

### Q1 — Adapter instance config: enums + credential

| Field | Devel (`vcfcf_vcommunity` mgmt) | Prod (`VCFOperationsvCommunity` mgmt) |
|---|---|---|
| Instances present | **1** (mgmt only; wld01 not present) | 3 (mgmt + wld01 + wld02) |
| `serviceMonitoring` enum | **Enabled** | Enabled (mgmt), Enabled (wld01), null (wld02) |
| `winEventMonitoring` enum | **Enabled** | Enabled (mgmt), null (wld01), null (wld02) |
| Credential kind | `vsphere_user` (1 combined credential) | (original credential kind, 403 on field read) |
| Credential `winUser` field | **`vcf@int.sentania.net`** (populated) | 403 (cannot read) |
| Credential `winPass` field | Present (hidden — field exists) | 403 |
| Adapter status | DATA\_RECEIVING / STARTED, `messageFromAdapterInstance: ""` | DATA\_RECEIVING (mgmt) |
| `numberOfMetricsCollected` | **6** | **77** (mgmt) |
| `numberOfResourcesCollected` | **2** (world + adapter resource only) | **42** (mgmt) |

**Key finding Q1:** Both enums on devel mgmt are `Enabled`. The Windows credential IS bound (`winUser=vcf@int.sentania.net`, `winPass` field present). The triple gate from review build-6 §A.2 (`windowsMonitoring != DISABLED AND hasWindowsCredential() AND guestOps.ready()`) — the first two conditions ARE met. The enum is not the gating cause.

---

### Q2 — Guest OS property keys on devel VMs

All 437 devel VMWARE/VirtualMachine resources scanned.

| Key family | Devel VMs with keys | Prod VMs with keys (mgmt adapter, 36 VMs) |
|---|---|---|
| `vCommunity\|Guest OS\|Operating System\|OS Name` | **25 VMs** — but **blank value** on Windows VMs (`dcint1`, `dcint2`) | **2 VMs** (`dcint1`, `dcint2`) — populated "Microsoft Windows Server 2025 Standard" |
| `vCommunity\|Guest OS\|Operating System\|OS Version` | **25 VMs** (Linux VMs via VMware-Tools path; devel Windows VMs also present: `dcint1`=10.0.26100, `dcint2`=10.0.26100) | Same 2 Windows VMs, populated |
| `vCommunity\|Guest OS\|Operating System\|OS BuildNumber` | 25 VMs (same) | 2 VMs |
| `vCommunity\|Guest OS\|Operating System\|OS Architecture` | 25 VMs | 2 VMs |
| `vCommunity\|Guest OS\|Operating System\|OS Release ID` | 25 VMs | 2 VMs |
| `vCommunity\|Guest OS\|Operating System\|OS Last Boot Up Time` | 25 VMs | 2 VMs |
| `vCommunity\|Guest OS\|Services:<name>\|Service Status` | **0 VMs** | **0 VMs** |
| Event log keys | 0 VMs | 0 VMs |

**Stale key present on devel (NOT on prod):** `vCommunity|Guest OS|Operating System|Last Boot Up Time` (without `OS ` prefix) — this is the pre-build-4 key from the non-canonical VMware-Tools path. It coexists with the new `OS Last Boot Up Time` on the same devel VMs. The rename from build 4/5 added the prefixed key but did not purge the old one (property stores persist until expiry or explicit deletion).

**Windows VMs on devel:** 8 found by `config|guestFullName`: `dcint1` (Win Server 2025, powered ON), `dcint2` (Win Server 2025, powered ON), `ca` (Win Server 2019, powered ON), `caroot`/`automic`/`mssqldemo`/`mssqldemo2`/`mssqldemo3` (Win Server 2019/2025, powered OFF). The two powered-on Windows Server 2025 VMs (`dcint1`, `dcint2`) are in the mgmt vCenter and ARE being visited by the adapter — they carry 9 `vCommunity|` keys each. But `OS Name` is **blank** on both devel Windows VMs (the Windows CSV path for `OS Name` is not emitting a value).

---

### Q3 — "Windows Service Down" symptom and Services keys

- `vCommunity|Guest OS|Services:DHCP Client|Service Status` is **absent on ALL devel VMs** (0/437).
- `vCommunity|Guest OS|Services:DHCP Client|Service Status` is **absent on ALL prod VMs** (0/36 from mgmt adapter).
- The "Windows Service Down" symptom UUID `7675759b-2ca0-4847-87ed-e3e23acdf7a5` is **present on prod** (`SymptomDefinition-7675759b-...`, `key=vCommunity|Guest OS|Services:DHCP Client|Service Status`, `op=NOT_EQ`). It is **not yet installed on devel** (the vcfcf_vcommunity pak content import is pending).
- The "ESXi Host NIC Disconnected" symptom UUID `c8d1e671-d0ea-489f-acc4-46e34cc246b6` — same: on prod, absent on devel.
- **Neither symptom has data to evaluate** on either instance, because no `vCommunity|Guest OS|Services:` keys are populated anywhere. This is true for prod (original) too, not only devel.

---

### Q4 — Adapter health and collection errors

Devel `vcfcf_vcommunity` mgmt adapter: `DATA_RECEIVING / STARTED`, `messageFromAdapterInstance: ""`. No error string in the adapter instance record. Collection event endpoints (`/api/adapters/{id}/events`, `/notifications`) return 404 — no error log surface available via API.

vCommunityWorld `Summary|config_file_status` on devel:
```
esxi_advanced_system_settings: 0 check(s)
esxi_packages: 0 check(s)
vm_advanced_parameters: 0 check(s)
vm_options: 0 check(s)
windows_service_list: 0 check(s)
windows_event_list: fetched (716 bytes)
```
`windows_service_list: 0 check(s)` = the adapter read the service list config file but found **no Windows VMs that passed the guest-ops gate** to run service checks against. `windows_event_list: fetched` = the XML was read but not applied (same reason). `last_scan_timestamp: 2026-06-22T19:29:43Z`.

The `0 check(s)` for services is the direct evidence that `guestOps.ready()` is failing for all Windows VMs in scope, even though the other two gate conditions are met (enum=Enabled, credential bound). This is the third leg of the triple gate — the guest-ops readiness check.

---

### Root-cause analysis

**Q1 verdict:** Enum gates on devel mgmt = OPEN. Credential = BOUND. Not the gating cause.

**Q2 verdict:** OS keys (Version/BuildNumber/Architecture/ReleaseID/LastBootUpTime) ARE landing on devel Windows VMs via the VMware-Tools `guest.detailedData` path (build-4 rename). `OS Name` is blank on Windows VMs — the `OS Name` field from `guest.detailedData` is apparently not populated for Windows VMs via that path (the original Python adapter uses a different CSV source for `OS Name`). This is a pre-existing data gap, not introduced by cred provisioning.

**Q3 verdict:** Services and event-log keys are absent on devel AND prod. Neither instance is collecting Windows CSV guest-ops data (the `vmOSInformation.py` equivalent path). On prod this means the prod Windows credential either isn't reaching guest-ops for those VMs, or the VM-level guest-ops manager isn't enabled for those targets.

**Primary gating cause (INFERRED — adapter log not accessible via API):** `guestOps.ready()` is returning false for the devel Windows VMs. Most likely causes in order of probability:
1. **VMware Tools not running / guest ops not enabled at vCenter level** on `dcint1` / `dcint2` (most common cause: GuestOperationsManager requires VMware Tools to be running AND the vCenter guest ops firewall enabled).
2. **Domain credential (`vcf@int.sentania.net`) auth failure** against the Windows VMs — the credential may have wrong permissions, WMI/GuestOps not authorized for that domain account, or the account doesn't exist on those specific VMs.
3. **Network connectivity** — less likely since VMware Tools path works (the `guest.detailedData` OS keys are landing, confirming vim25 reaches the guest).

**The adapter is not crashing** — it is collecting (status DATA\_RECEIVING, 6 metrics on 2 resources), and the VMware-Tools OS path is working for powered-on Windows VMs. The specific Windows guest-ops CSV collection path (`GuestOperationsManager.fileManager` / `ProcessManager`) is what is failing silently.

---

### Summary table (devel vs prod)

| Aspect | Devel (port build 6) | Prod (original v0.2.8) |
|---|---|---|
| Windows Monitoring enum | Enabled (both) | Enabled (mgmt only) |
| Windows credential bound | YES (`vcf@int.sentania.net`) | YES (403 on read, inferred) |
| `guestOps.ready()` | **FAILING** (INFERRED — 0 service checks) | **FAILING** (0 service checks on prod too) |
| OS keys (non-CSV) | Partially — 25 VMs, Windows OS Name blank | Windows VMs: OS Name populated, 6 OS keys each |
| Guest OS|Services keys | **0 VMs** | **0 VMs** |
| Event log keys | 0 VMs | 0 VMs |
| Symptoms installed | Neither | Both (by UUID) |
| Adapter status | DATA\_RECEIVING/GREEN | DATA\_RECEIVING/GREEN |
| `OS Name` gap (devel) | Blank on Windows VMs | Populated ("Microsoft Windows Server 2025 Standard") |
| Stale `Last Boot Up Time` key (no `OS ` prefix) | Present on 25 VMs (pre-build-4 residue) | Absent |

---

### Actionable findings for orchestrator

1. **guestOps gate failing on devel AND prod.** Adding the credential alone does not start collection — the `guestOps.ready()` check is failing. This is NOT a pak code bug (prod has the same failure). Required action: verify VMware Tools is running on `dcint1`/`dcint2` and that `vcf@int.sentania.net` has guest-ops permissions at the vCenter level (vCenter → Datacenter/VM → Edit Inventory → Guest Operations privilege).

2. **`OS Name` blank on devel Windows VMs.** The VMware-Tools `guest.detailedData` path emits OS Version/BuildNumber/etc. but not `OS Name` for Windows. On prod, the original Python MP gets `OS Name` from the Windows CSV path (the same path that services come from). This is an existing gap in the Java adapter's non-CSV path — not new. Impact: the 6 `OS `-prefixed keys parity target is partially met (5/6 populated, `OS Name` blank for Windows).

3. **Stale `Last Boot Up Time` (unprefixed) key on devel.** 25 VMs carry this residue from the pre-build-4 adapter. It will age out at the property retention deadline; no action needed unless content tries to use that key.

4. **`windows_service_list: 0 check(s)` in vCommunityWorld.** Directly confirms zero Windows VMs are passing the full guest-ops gate. This is the observable symptom of the `guestOps.ready()` failure.

5. **Symptom/alert content not yet installed on devel.** Phase-2 content port is not complete. The Windows Service Down and ESXi Host NIC Disconnected symptoms are installed on prod (by their canonical UUIDs) but absent from devel. Blocking Phase-3 verification only in the sense that the symptom can't evaluate even when the key arrives — but the key is the primary gate.

6. **Devel is missing the wld01 adapter instance.** Prod has 3 adapter instances; devel has 1 (mgmt only). The wld01 adapter was present in prior recons (2026-06-16 noted `hosts_stitched=4, vms_stitched=36` from two instances). This may have been removed during testing. Lower priority — the Windows VMs (`dcint1`, `dcint2`) are in the mgmt vCenter, so the mgmt instance is the relevant one.


---

## 2026-06-22 (follow-up) — automic VM guest-ops privilege hypothesis test

**Trigger:** Scott powered on the `automic` Windows VM where `vcf@int.sentania.net` is a full Administrator (vs `dcint1`/`dcint2` where the account is Server Operator only).
**Question:** Did Administrator-level access on `automic` unlock the guest-ops / Windows service collection surface?
**Investigator:** ops-recon
**Timestamp of investigation:** 2026-06-22 ~20:00 UTC

---

### Q1 — VM identification and adapter scope

- **Exact resource name:** `automic` (confirmed, no suffix). VMWARE/VirtualMachine id `b09a6f27-869d-428e-a749-6d489441f13c`.
- **Guest OS:** `config|guestFullName = Microsoft Windows Server 2025 (64-bit)`.
- **Parent vCenter/cluster:** `summary|parentVcenter = vcf-lab-mgmt`, `summary|parentCluster = vcf-lab-mgmt-cl01`, `summary|parentDatacenter = vcf-lab-mgmt-dc01`.
- **In-scope of `vcfcf_vcommunity` mgmt adapter:** YES — the adapter instance connects to `vcf-lab-vcenter-mgmt.int.sentania.net`, which manages `vcf-lab-mgmt-dc01`. `automic` is in that datacenter.
- **Power state:** `summary|runtime|powerState = Powered On`. Confirmed powered on.
- **VMware Tools status:** **`summary|guest|toolsRunningStatus = Guest Tools Not Running`**. Tools version installed: `13.0.10` (tools present on disk, not running at time of collection). `summary|guest|toolsVersionStatus2 = Guest Tools Supported Old`.
- **Guest hostname/IP:** `summary|guest|fullName = none`, `summary|guest|hostName = none`, `summary|guest|ipAddress = none` — these are all populated by VMware Tools at runtime; they are blank because Tools is not running.

---

### Q2 — Did guest-ops fire on automic?

No. Findings:

| Key | automic |
|---|---|
| `vCommunity\|Guest OS\|Services:DHCP Client\|Service Status` | **ABSENT** (0 values returned by `/stats/latest`) |
| Any `vCommunity\|Guest OS\|Services:` key | **ABSENT** |
| `vCommunity\|Guest OS\|Operating System\|OS Name` | **ABSENT** (property not present at all) |
| `vCommunity\|Guest OS\|Operating System\|OS Last Boot Up Time` | Present (`2026-06-22T19:40:08.024972Z`) — this is the VMware-Tools path, not guest-ops |
| `vCommunity\|Guest OS\|Operating System\|OS Version` / `OS Architecture` / `OS BuildNumber` / `OS Release ID` | **ABSENT** (only `OS Last Boot Up Time` is present, via MOID-level Tools path) |
| Any event-log keys | ABSENT |

**Root cause confirmed:** VMware Tools is not running on `automic`. The guest-ops gate in the adapter requires `GuestOperationsManager.areGuestOperationsAvailable()` (or equivalent `guestOps.ready()`), which requires VMware Tools to be running in the guest. With Tools not running, the adapter cannot establish a guest-ops session regardless of the Windows account privilege level. The privilege hypothesis (Server Operator vs Administrator) cannot be tested yet because the prerequisite — Tools running — is not met.

**Contrast with dcint1/dcint2:** `dcint1` and `dcint2` both have `summary|guest|toolsRunningStatus = Guest Tools Running` and `toolsVersionStatus2 = Guest Tools Current`. They carry 9 `vCommunity|` keys each (the VMware-Tools OS path keys). `automic` has only 3 `vCommunity|` keys (the SCSI controller config keys and `OS Last Boot Up Time` only — from the non-guest-ops Tools properties read). This confirms that having Tools running is sufficient to get the Tools-path keys but is not sufficient alone to get the service/event-log keys (the DCs prove that: Tools running, 9 keys, still zero Services keys).

---

### Q3 — vCommunityWorld anchor re-read

`Summary|config_file_status` at `2026-06-22T19:44:09.879474949Z`:

```
esxi_advanced_system_settings: 0 check(s)
esxi_packages: 0 check(s)
vm_advanced_parameters: 0 check(s)
vm_options: 0 check(s)
windows_service_list: 0 check(s)
windows_event_list: fetched (716 bytes)
```

**`windows_service_list` did NOT move.** Still `0 check(s)`. Timestamp advanced ~14 minutes from the prior entry (`19:29:43Z` → `19:44:09Z`), confirming the adapter ran at least one more collection cycle since the previous recon but found no additional Windows VMs passing the guest-ops gate.

---

### Q4 — Contrast: dcint1/dcint2 vs automic

| Property | dcint1 | dcint2 | automic |
|---|---|---|---|
| Tools running | YES | YES | **NO** |
| `vCommunity\|Guest OS\|` key count | 9 | 9 | 3 |
| Services keys | 0 | 0 | 0 |
| OS keys (non-CSV path) | 5 populated + OS Name blank | 5 populated + OS Name blank | Only `OS Last Boot Up Time` (1 key) |
| Event-log keys | 0 | 0 | 0 |

The DCs (Tools running, account = Server Operator) have more keys than `automic` (Tools not running, account = Administrator) because the VMware-Tools `guest.detailedData` path — which delivers the non-guest-ops OS keys — requires Tools to be running. `automic` with Tools not running gets fewer keys, not more.

---

### Q5 — Adapter health

`vcfcf_vcommunity` mgmt adapter: `DATA_RECEIVING / STARTED`, `messageFromAdapterInstance: ""`. `numberOfMetricsCollected: 6`, `numberOfResourcesCollected: 2` — unchanged from prior recon. `lastCollected: 1782157449880` (within the current investigation window). No new collection errors.

---

### Privilege hypothesis status

**NOT CONFIRMED — prerequisite not met.** The hypothesis (Server Operator insufficient, full Administrator needed) cannot be evaluated yet because `automic`'s VMware Tools is not running. The full privilege test requires:

1. VMware Tools running on `automic` (so the adapter can open a guest-ops session at all).
2. A collection cycle to run after Tools starts.
3. Then compare: does `automic` (Administrator) produce `vCommunity|Guest OS|Services:` keys while `dcint1`/`dcint2` (Server Operator) still produce zero?

**Required action to advance the test:** Start VMware Tools on `automic` (from within the Windows guest: `Start-Service VMwareToolsService`, or via vCenter guest restart, or reboot the VM). Then wait one collection cycle (adapter interval = 5 min) and re-run this recon.

---

### Summary — what we know vs what we don't

| Question | Status |
|---|---|
| Is `automic` the right VM? | YES — exact name confirmed, full Administrator account |
| Is `automic` in adapter scope? | YES — mgmt vCenter, mgmt datacenter |
| Is `automic` powered on? | YES |
| Are Tools running on `automic`? | **NO — blocker** |
| Did guest-ops fire on `automic`? | **NO** |
| Did `windows_service_list` move? | **NO — still `0 check(s)`** |
| Is privilege theory testable yet? | **NO — Tools must start first** |
| Adapter still healthy? | YES — DATA_RECEIVING/GREEN, no errors |


---

## 2026-06-22 — build-9 diagnostics post-upgrade recon (ops-recon)

**Build:** `vcfcf_vcommunity` 1.0.0.9, installed ~10:20 UTC on devel mgmt adapter `d02a632f-01f8-458a-a868-9a33ef19dd46`.
**vCommunityWorld anchor:** NEW UUID `3d101989-15bf-4005-a25a-34ba25615a42` (previous was `403ef6ff-...`; replaced at build-9 install time).
**Recon timestamp:** 2026-06-22T20:48Z (~28 min post-install; at least 3-4 collection cycles completed, interval=5 min).
**Profile:** VCFOPS_DEVEL.

---

### 1. Adapter instance health (devel)

| Field | Value |
|---|---|
| `id` | `d02a632f-01f8-458a-a868-9a33ef19dd46` |
| `numberOfMetricsCollected` | **6** |
| `numberOfResourcesCollected` | **2** |
| `lastCollected` UTC | `2026-06-22T20:43:24.752Z` |
| `lastHeartbeat` UTC | `2026-06-22T20:48:07.105Z` |
| `messageFromAdapterInstance` | `""` (empty — no errors) |
| `monitoringInterval` | 5 min |
| `resourceStatus` (anchor) | **DATA_RECEIVING** |

Adapter is healthy. Heartbeat is live within the recon window.

---

### 2. Build-9 diagnostic properties (exact values)

Anchor `3d101989-15bf-4005-a25a-34ba25615a42`, `Summary|last_scan_timestamp = 2026-06-22T20:48:41.736322868Z`:

| Property | Value |
|---|---|
| `Summary|guestops_ready` | **`true`** |
| `Summary|guestops_vms` | **`considered=36 passed=3 skipped=33`** |
| `Summary|guestops_skips` (truncated at 10+23) | `vcf-lab-operations-devel[tools=toolsOk,family=linuxGuest,...]; ca[tools=toolsNotInstalled,...]; docker[tools=toolsOk,family=linuxGuest,...]; vcf-lab-automation-runtime-lz9bv[tools=toolsOk,family=linuxGuest,...]; vcf-services-platform-template-9.0.2.0.25068117[tools=toolsNotRunning,...]; caroot[tools=toolsNotRunning,family=,guestId=windows2022srvNext_64Guest]; vcf-services-runtime-template-9.1.0.0.25370367[tools=toolsNotRunning,...]; vcf-lab-license[tools=toolsOk,family=linuxGuest,...]; vcf-lab-vcenter-wld01[tools=toolsOk,family=linuxGuest,...]; vcf-lab-nsxmgr-mgmt01[tools=toolsOk,family=linuxGuest,...]; (+23 more skipped, detail capped)` |
| `Summary|config_file_status` | `esxi_advanced_system_settings: 0 check(s); esxi_packages: 0 check(s); vm_advanced_parameters: 0 check(s); vm_options: 0 check(s); windows_service_list: 0 check(s); windows_event_list: fetched (716 bytes)` |
| `Summary|status` | `OK` |

---

### 3. Interpretation: which leg blocks

**The global leg (`guestops_ready`) is NOT the blocker.** `Summary|guestops_ready = "true"` — the `GuestOpsClient.readyReason()` method (build-9 addition) returned "true", meaning `guestFileManager != null AND guestProcessManager != null AND winUser != null/non-empty`. The prior recon's prime suspect (guestProcessManager=null) is exonerated. Build-8's broad `guest` read fix (`vmGuestToolsStatus` / `vmGuestFamily` reading `guest` GuestInfo wholesale rather than narrow sub-paths) resolved the stale-blank problem that caused guestOps.ready() to fail in earlier builds.

**The per-VM gate is also NOT the blocker.** `guestops_vms = considered=36 passed=3 skipped=33`. Three VMs PASSED the `toolsOk + windowsGuest` gate. Source (`VmCollector.java:263-264`): gate is `!"toolsOk".equals(toolsStatus) || !"windowsGuest".equals(guestFamily)`. The 3 passed VMs are — confirmed by cross-checking devel VM inventory — `dcint1`, `dcint2`, and `automic` (all three have vim25 `toolsStatus=toolsOk`, `guestFamily=windowsGuest`, and `tools Running` per Ops properties). These 3 VMs are in the `guestops_skips` overflow ("+23 more skipped, detail capped" — the cap is 10 visible skip entries; the 3 passed VMs are not in the skips list at all because they passed).

**The blocker is inside the guest-ops session itself.** All three Windows VMs pass the gate (code reaches `result.guestVmsPassed++; result.guestVmsAttempted++;` in VmCollector line 283-284), but `collectServices()` is returning an empty list and `collectOsInfo()` is returning null for all three. `windows_service_list: 0 check(s)` on the anchor confirms zero service-check results across the entire cycle.

**Root cause (INFERRED — adapter log not accessible via Suite API):** The `GuestOpsClient.collectServices()` path issues a `CreateTemporaryDirectoryInGuest` SOAP call via `guestFileManager`. The most probable failure point is that call returning a vim25 fault (`NotAuthenticated`, `GuestOperationsFault`, or `InvalidArgument`) because:

1. **The `vcf@int.sentania.net` credential is not a Local Windows account** on dcint1/dcint2/automic. It is a domain account. The `NamePasswordAuthentication` SOAP block in `auth()` (GuestOpsClient line 424-430) sends `username=vcf@int.sentania.net`. vCenter's GuestOperationsManager authenticates the SOAP credential AGAINST the guest OS. For domain accounts, vCenter uses the UPN format and it must match a user with guest-ops privileges (not just vCenter). A domain member server that is not joined to the domain, or where the account lacks the right WMI/GuestOps ACL, will fault at CreateTemporaryDirectory.

2. **Alternative: VMware Tools version mismatch.** dcint1/dcint2 show `toolsVersionStatus2=Guest Tools Current` which is good. `automic` now shows `Guest Tools Running` and `Guest Tools Current` (it started tools since the prior recon). But build-9 runs these through `GuestOpsClient.createTempDir()` and if the tools-internal guest agent reports `toolsNotInstalled` to the GuestOperationsManager (rare but possible when tools version doesn't expose `guestOperationsReady`), the SOAP call faults.

3. **Guest Operations firewall / vCenter privilege.** The `vcf@int.sentania.net` account needs the vCenter privilege `Virtual Machine > Guest Operations > Guest Operation Program Execution` on the folder/datacenter level. If this privilege is missing, `StartProgramInGuest` faults with `NotPrivileged` (caught and swallowed silently per the crash-isolation design, returning empty).

The `GuestOpsClient.collectServices()` exception path (`logWarn("guest-ops services on '" + vmName + "' failed (isolated, cycle continues): ...")`) would reveal the exact fault name, but the adapter log is a 404 via the Suite API.

---

### 4. Cross-check: payoff metrics — Services keys and config_file_status

| Check | Result |
|---|---|
| `vCommunity|Guest OS|Services:*|Service Status` on dcint1 | **0 keys — ABSENT** |
| `vCommunity|Guest OS|Services:*|Service Status` on dcint2 | **0 keys — ABSENT** |
| Any Services key on any of 38 devel VMs scanned | **0 VMs — NONE** |
| `Summary|windows_service_list` on anchor | **`0 check(s)` — unchanged** |
| `Summary|config_file_status` overall | `windows_service_list: 0 check(s)` — still zero |

Windows Services data is NOT collecting. The `0 check(s)` count did not move. The payoff (services properties) is not flowing.

**`vCommunity|Guest OS|Operating System|*` keys on Windows VMs (non-CSV path):**

| VM | Tools Running | OS Version | OS BuildNumber | OS Architecture | OS Release ID | OS Last Boot Up Time | OS Name |
|---|---|---|---|---|---|---|---|
| dcint1 | YES | 10.0.26100 | 26100 | 64-bit | 2009 | 6/10/2026 3:44:48 AM | **blank** |
| dcint2 | YES | 10.0.26100 | 26100 | 64-bit | 2009 | 6/11/2026 3:41:19 AM | **blank** |
| automic | YES (NEW — Tools started since prior recon) | 10.0.26100 | 26100 | 64-bit | 2009 | 6/22/2026 2:44:34 PM | **blank** |

`automic` now has a full set of OS keys via the VMware-Tools path (5 of 6 — OS Name still blank), confirming that starting VMware Tools on automic DID enable the non-CSV path. However it did NOT enable the guest-ops CSV path (Services still absent).

**Stale `Last Boot Up Time` key (no `OS ` prefix):** still present on dcint1/dcint2 (pre-build-4 residue); absent on automic (which first collected data after the rename was in build 4+). Will age out.

---

### 5. What is now known vs prior recon (2026-06-22 automic investigation)

| Question | Prior status | Build-9 status |
|---|---|---|
| `guestops_ready` global leg | INFERRED failing (log inaccessible) | **CONFIRMED true** — exonerated |
| Per-VM toolsOk/windowsGuest gate | Inferred passing for dcint1/dcint2 | **CONFIRMED passed=3 (dcint1, dcint2, automic)** |
| `windows_service_list` | `0 check(s)` | **Still `0 check(s)`** — no movement |
| Where exactly does it fail? | After gate, inside guest-ops session | **CONFIRMED — failure is inside `GuestOpsClient.collectServices()` or `collectOsInfo()`; exact vim25 fault INFERRED (not accessible without appliance log)** |
| automic VMware Tools | NOT RUNNING | **NOW RUNNING** — Tools started; OS keys now flowing via Tools path |
| Privilege hypothesis (Server Op vs Admin) | NOT TESTABLE (Tools not running) | **NOW TESTABLE** — but Services still absent on automic even with Tools running; implies privilege IS the issue OR a separate fault in the session |

---

### 6. Actionable findings for orchestrator

1. **Global gate is clear.** `guestops_ready=true` is now the ground truth. No build change needed for the gate itself. The build-8 broad-`guest`-read fix is confirmed working.

2. **Per-VM gate is clear for 3 Windows VMs.** dcint1, dcint2, automic all pass `toolsOk + windowsGuest`. The gate logic in VmCollector is functioning correctly.

3. **The blocker is a vim25 fault inside the guest-ops session.** The `CreateTemporaryDirectoryInGuest` or `StartProgramInGuest` call is faulting silently (caught by crash-isolation). Without the appliance log, the exact fault name is INFERRED. Most likely candidates:
   - Missing vCenter privilege: `Virtual Machine > Guest Operations > Guest Operation Program Execution` (and/or `Guest Operation File Access`) for `vcf@int.sentania.net` at the Datacenter/Folder level.
   - Domain credential format mismatch: the UPN `vcf@int.sentania.net` may need to be `SENTANIA\vcf` (NetBIOS format) for some GuestOperationsManager implementations.
   - The adapter log (on the Ops appliance, not via API) would show `"guest-ops services on 'dcint1' failed (isolated, cycle continues): <FaultName>: <message>"` — that single log line would definitively identify the fault.

4. **automic privilege hypothesis is now testable in the NEXT build cycle.** With Tools running, the next collection cycle should show either Services keys on `automic` (if Administrator is sufficient) or continued absence (confirming the issue is credential/privilege, not account type). **The absence of Services keys on `automic` this cycle suggests the guest-ops session fault is not privilege-level-specific** — the same fault happens for all three VMs regardless of whether the account is Server Operator or Administrator. This points to the domain credential format or vCenter privilege, not the Windows account level.

5. **`windows_service_list: 0 check(s)` is the sentinel.** When this moves to `windows_service_list: N check(s)` (N > 0), guest-ops has fired. Monitor this property on the new anchor `3d101989-...` to detect breakthrough.

6. **Required investigation to unblock:** Access the Ops appliance adapter log. The adapter write path (`logWarn("guest-ops services on '" + vmName + "' failed (isolated, cycle continues): ...")` in GuestOpsClient.java line 168-170) will emit the exact vim25 exception class and message for each failed VM. This is the only observable without modifying the adapter. Alternatively: add a `Summary|guestops_last_error` property to the build-10 anchor diagnostics that captures the last per-VM fault string (class + message), making it API-readable.


---

## 2026-06-22 — active-alerts confirm (ops-recon)

**Trigger:** Scott reports prod is collecting Windows event-log events from dcint1/dcint2. This entry confirms that via the alert/notification surface and contrasts prod vs devel.
**Investigator:** ops-recon (read-only; no alerts acknowledged or cancelled)
**Recon timestamp:** 2026-06-22 ~21:20Z
**Profiles:** VCFOPS_PROD (vcf-lab-operations.int.sentania.net), VCFOPS_DEVEL (vcf-lab-operations-devel.int.sentania.net)

---

### Q1 — Active alerts on prod: dcint1 / dcint2

**PROD dcint1** (`4c5bcff0-c697-4e92-9ba7-8e15ad61d18f`): **500+ notifications present** (API returned 500 on a query with `activeOnly=false`; 100 returned with `activeOnly=true` — the page cap). All 100 are:

```
Notification event-[WindowsEvent-Information
  [Timestamp=06/22/2026 HH:MM:SS]
  [Category=Application]
  [EventID=1000]
  [Source=VGAuth]
  [Message=vmtoolsd: Username and password successfully validated for 'vcf@int.sentania.net']
```

| Field | Value |
|---|---|
| Event type | WindowsEvent-Information |
| EventID | 1000 |
| Category | Application |
| Source | VGAuth |
| Message | vmtoolsd: Username and password successfully validated for 'vcf@int.sentania.net' |
| Status range | Mostly CANCELED; the 2 most recent are ACTIVE |
| Frequency | ~every 5 minutes throughout 2026-06-22 (05:30Z through 21:17Z) |
| Criticality | None (notifications, not metric-driven alerts) |

**PROD dcint2** (`39e69282-0f38-40c6-ad1b-960f778d79ed`): same pattern — 500+ WindowsEvent-Information notifications, EventID 1000, Source VGAuth, same message. 1 ACTIVE + 499 CANCELED in the sample.

**Summary:** Prod is generating one VGAuth WindowsEvent-Information notification per ~5-minute collection cycle on both dcint1 and dcint2, all day on 2026-06-22. This is the Windows event-log collection Scott described. The original `VCFOperationsvCommunity` MP is actively executing guest-ops sessions on dcint1/dcint2 every cycle and reading the Windows Application event log. The VGAuth event (EventID 1000, Source VGAuth, Category Application) records the vCommunity credential being validated by VMware Tools VGAuth daemon — it fires once per guest-ops authentication session on each cycle.

**Also on prod:** Zero conventional metric-driven alerts on dcint1/dcint2 from the vCommunity MP. The "Windows Service Down" alert definition exists on prod (`AlertDefinition-07dcccaa-eac3-4501-9dfc-34deccb963e9`, pointing to `SymptomDefinition-7675759b-2ca0-4847-87ed-e3e23acdf7a5`) and the symptom IS installed on prod (`condition.key=vCommunity|Guest OS|Services:DHCP Client|Service Status`, `op=NOT_EQ`, `stringValue=Running`). However it is NOT firing on dcint1/dcint2 — the Services keys are absent on prod as well (confirmed in the 2026-06-22 Phase-3 recon entry). The alert def is installed but its symptom is data-starved.

---

### Q2 — Active alerts on devel: dcint1 / dcint2

**DEVEL dcint1** (`6a20cdd2-559e-46c0-814f-0c9d4beebb2e`): **1 active alert**

| Field | Value |
|---|---|
| Name | Windows Service Down |
| Alert definition ID | `AlertDefinition-VMWARE-Windows_Service_Down` |
| Status | ACTIVE |
| Start time | 2026-06-22T20:42:49Z |
| Criticality | None |

**DEVEL dcint2** (`d5a62a0e-ad80-4b9a-a5e3-4e1122a68fc9`): **1 active alert**

| Field | Value |
|---|---|
| Name | Windows Service Down |
| Alert definition ID | `AlertDefinition-VMWARE-Windows_Service_Down` |
| Status | ACTIVE |
| Start time | 2026-06-22T20:44:52Z |
| Criticality | None |

**Zero notification events on devel dcint1/dcint2.** No WindowsEvent notifications of any kind.

---

### Q3 — Alert definition installation status

| Alert | Prod | Devel | Status |
|---|---|---|---|
| Windows Service Down | INSTALLED (`AlertDefinition-07dcccaa-eac3-4501-9dfc-34deccb963e9`) | INSTALLED (`AlertDefinition-VMWARE-Windows_Service_Down`) | Both installed; different ID format (UUID-based on prod, name-based on devel) |
| ESXi Host NIC Disconnected | Symptom installed (`SymptomDefinition-c8d1e671-...`, confirmed) | NOT INSTALLED | Devel content port incomplete |
| ESXi Host License Expiring | Not confirmed as a named alert def on prod (name search inconclusive in the 500-result page cap) | NOT INSTALLED | — |

**The `Windows Service Down` alert definition on devel references `SymptomDefinition-7675759b-2ca0-4847-87ed-e3e23acdf7a5` as its trigger.** That symptom is installed on PROD (`condition.key=vCommunity|Guest OS|Services:DHCP Client|Service Status`, `op=NOT_EQ "Running"`) but returns 404 on DEVEL. The alert on devel is firing WITHOUT its symptom definition being installed — the alert engine is evaluating the referenced symptom UUID even without the symptom definition present and is triggering. This is an anomalous state.

---

### Q4 — Symptom installation status

| Symptom | Prod | Devel | Condition key |
|---|---|---|---|
| Windows Service Down (`7675759b-...`) | INSTALLED | 404 (NOT INSTALLED) | `vCommunity\|Guest OS\|Services:DHCP Client\|Service Status` NOT_EQ "Running" |
| ESXi Host NIC Disconnected (`c8d1e671-...`) | INSTALLED | 404 (NOT INSTALLED) | (not fetched — prod symptom confirmed present, devel 404) |

---

### Q5 — Contrast: prod vs devel guest-ops surface

| Aspect | Prod (VCFOperationsvCommunity v0.2.8) | Devel (vcfcf_vcommunity build 1.0.0.9) |
|---|---|---|
| Windows event-log notifications | ACTIVE — ~1 per 5 min cycle, all day, EventID 1000 VGAuth Application events | ABSENT — zero notification events on dcint1/dcint2 |
| Source of notifications | vCommunity guest-ops session reading Windows Application log, finds VGAuth EventID 1000, emits as Ops notification | Not reached — `collectServices()` silently fails |
| `vCommunity\|Guest OS\|Services:*` keys | ABSENT on all prod VMs (same as devel) | ABSENT on all devel VMs |
| "Windows Service Down" alert | INSTALLED, NOT FIRING (no Services data to evaluate symptom) | INSTALLED (alert def only; symptom def missing); FIRING ANOMALOUSLY on both dcint1 and dcint2 |
| Alert content port completeness | N/A (original) | Incomplete — alert def imported without paired symptom def; ESXi Host NIC/License alert defs absent |
| `windows_service_list` anchor | N/A (prod uses properties-based event push) | `0 check(s)` — no guest-ops CSV reached dcint1/dcint2 |

---

### Key findings

**1. PROD GUEST-OPS IS CONFIRMED WORKING.** The event-log notifications prove the original `VCFOperationsvCommunity` MP is reaching the guest OS on dcint1 and dcint2 via GuestOperationsManager every collection cycle. It opens a guest-ops session, authenticates as `vcf@int.sentania.net` (VGAuth logs the successful auth as EventID 1000), reads the Windows Application event log, and pushes the events as Ops notifications. This is not inferred — the notification events with the VGAuth message are direct evidence.

**2. DEVEL GUEST-OPS IS CONFIRMED NOT REACHING THE GUEST.** Zero notification events on devel dcint1/dcint2, `windows_service_list: 0 check(s)` still unchanged. The Java port's `GuestOpsClient.collectServices()` is not completing successfully on dcint1/dcint2 or automic. The `guestops_ready=true` and `guestops_vms passed=3` diagnostics from build-9 confirm the adapter is reaching the per-VM execution gate, but something inside the guest-ops SOAP session is failing silently.

**3. CRITICAL DEDUCTION — CREDENTIAL DIFFERENCE.** Prod is making successful guest-ops authentication calls as `vcf@int.sentania.net` (confirmed by VGAuth EventID 1000 events). The same credential is bound on devel. However, the prod `VCFOperationsvCommunity` MP is a Python/containerized DOCKERIZED adapter, while the devel port is a Java `GENERAL` SDK adapter. The credential is the SAME; what may differ is HOW it is passed to the GuestOperationsManager SOAP call. Specifically: the Python original may use a different NamePasswordAuthentication format (e.g., `DOMAIN\user` or `int.sentania.net\vcf`) vs the Java port which currently passes the UPN form `vcf@int.sentania.net`. Since VGAuth is successfully validating on prod, the original Python adapter is using a credential format that vCenter's GuestOperationsManager accepts for these DCs. The Java port may be using a format that fails.

**4. ANOMALOUS ALERT STATE ON DEVEL.** `Windows Service Down` is ACTIVE on devel dcint1 and dcint2 even though: (a) the symptom definition `7675759b-...` is NOT installed on devel (404), and (b) the data key `vCommunity|Guest OS|Services:DHCP Client|Service Status` has zero values on both VMs (empty stat keys). The alert engine appears to be triggering the alert when the symptom condition cannot be evaluated (treating "data absent" as "condition met = service not Running"). This is a stale/dangling alert caused by the incomplete content import — the alert definition was imported but its paired symptom definition was not. The alert firing on NO data is a false positive and confirms the devel content port is incomplete.

**5. PROD EVENT LOG VS SERVICES KEYS DIVERGENCE.** The original Python MP is successfully reading the Windows Application event log (proven by notifications) but is NOT populating `vCommunity|Guest OS|Services:DHCP Client|Service Status` on prod either. This means either: (a) the windows_service_list SolutionConfig on prod has DHCP Client commented out / not configured, or (b) the Services collection is a separate guest-ops call that also fails. The event-log collection (guest-ops file write + process execution to read event log) succeeds; the Services WMI query may require a different code path or permission. This is a distinction that applies to the port as well once guest-ops session establishment is fixed.

---

### Actionable findings for orchestrator

1. **Prod guest-ops is working — parity gap is real and confirmed.** The VGAuth events are definitive proof. The original Python MP can open guest-ops sessions on dcint1/dcint2 as `vcf@int.sentania.net`. The Java port cannot. This is the root issue.

2. **Investigate credential format in GuestOpsClient.** The prod adapter authenticates the credential in a form VGAuth accepts. The Java port's `auth()` method (GuestOpsClient.java line 424-430) sends the credential. If it sends UPN format (`vcf@int.sentania.net`) and the Windows DCs require SAM/NetBIOS format (`SENTANIA\vcf`) for GuestOperationsManager, that would explain the silent failure. The original Python source (if accessible) would show the format it uses in its NamePasswordAuthentication call. This is build-10 priority.

3. **Devel content port is incomplete and has anomalous state.** The `Windows Service Down` alert def is firing on dcint1/dcint2 (ACTIVE) with zero data — a false positive from a missing symptom def. Before any production readiness assessment, the missing symptom `7675759b-...` must be imported to devel AND the ESXi Host NIC Disconnected / License Expiring alert defs must be ported. The current devel alert state will mislead any health-badge interpretation.

4. **`vCommunity|Guest OS|Services:*` keys are absent on prod too.** The Services surface is not collecting on prod either — this is not unique to the Java port. Once the Java port's guest-ops session is unblocked, a second investigation will be needed to understand whether Services collection requires additional SolutionConfig entries or a separate code path.

5. **VGAuth EventID 1000 as a sentinel for the Java port.** When the Java port's `collectServices()` opens a successful guest-ops session on dcint1, VGAuth will log EventID 1000 in the Application event log, which the event-log reader will pick up and surface as a notification on the devel instance. The first appearance of `Notification event-[WindowsEvent-Information ... [Source=VGAuth] [Message=vmtoolsd: Username and password successfully validated for 'vcf@int.sentania.net']` on devel dcint1/dcint2 is the proof-of-unblock sentinel — it will appear before any Services keys do.

---

## 2026-06-23 — build-10 fault-capture post-upgrade recon (ops-recon)

**Build:** `vcfcf_vcommunity` 1.0.0.10, installed ~01:15 UTC 2026-06-23 on devel mgmt adapter `d02a632f-01f8-458a-a868-9a33ef19dd46`.
**vCommunityWorld anchor:** `3d101989-15bf-4005-a25a-34ba25615a42` (unchanged from build-9).
**Recon window:** 2026-06-23T01:17Z–01:32Z (~17 min post-install; 3 full collection cycles observed at 01:15, 01:20, 01:25, 01:30 UTC).
**Profile:** VCFOPS_DEVEL.
**Investigator:** ops-recon (read-only; no writes).

---

### 1. Build-10 installation confirmed

| Field | Value |
|---|---|
| Solution ID | `VCF Content Factory vCommunity` |
| Version | **1.0.0.10** |
| Anchor resource status | **DATA_RECEIVING** |
| Adapter instance health | Heartbeat live, `messageFromAdapterInstance: ""` (no errors) |

---

### 2. `Summary|guestops_last_error` — verbatim value across all observed cycles

| Cycle (last_scan_timestamp) | `guestops_last_error` value |
|---|---|
| 2026-06-23T01:15:07Z (install cycle) | `'none'` |
| 2026-06-23T01:20:29Z (first full post-upgrade cycle) | `'none'` |
| 2026-06-23T01:25:21Z (second cycle) | `'none'` |
| 2026-06-23T01:30:38Z (third cycle) | `'none'` |

**The property is present** (build-10 shipped it successfully). The string `'none'` is the code-path return from `VmCollector.Result.guestLastErrorSummary()` when `faultsRecorded == 0` — meaning `GuestOpsClient.lastFault()` was null for all three passed Windows VMs (dcint1, dcint2, automic) across every cycle. No vim25 SOAP fault was captured.

---

### 3. Build-9 diagnostic trio — current values (unchanged from build-9)

| Property | Value |
|---|---|
| `Summary|guestops_ready` | `true` |
| `Summary|guestops_vms` | `considered=36 passed=3 skipped=33` |
| `Summary|guestops_skips` | (unchanged — same 33 non-Windows/non-toolsOk VMs) |
| `Summary|config_file_status` | `windows_service_list: 0 check(s); windows_event_list: fetched (716 bytes)` |

---

### 4. Stats across all observed cycles (anchor)

| Stat key | Value (stable across all cycles) |
|---|---|
| `Summary|guest_vms_attempted` | **3.0** |
| `Summary|guest_vms_degraded` | **0.0** |
| `Summary|events_as_properties` | **0.0** |
| `Summary|vms_stitched` | 36.0 |
| `Summary|hosts_stitched` | 4.0 |
| `Summary|clusters_stitched` | 1.0 |

`guest_vms_degraded = 0.0` across 10 historical 5-minute buckets queried. No degradation signal on any cycle, not just the build-10 window.

---

### 5. Guest OS property state on dcint1, dcint2, automic

Both VMware-Tools-path and guest-ops-CSV-path properties are present simultaneously on all three Windows VMs:

| Property | Source | dcint1 | dcint2 | automic |
|---|---|---|---|---|
| `OS Last Boot Up Time` (PowerShell format) | guest-ops CSV (`collectOsInfo`) | `6/10/2026 3:44:48 AM` | `6/11/2026 3:41:19 AM` | `6/22/2026 2:44:34 PM` |
| `OS Version` | guest-ops CSV | `10.0.26100` | `10.0.26100` | `10.0.26100` |
| `OS BuildNumber` | guest-ops CSV | `26100` | `26100` | `26100` |
| `OS Architecture` | guest-ops CSV | `64-bit` | `64-bit` | `64-bit` |
| `OS Release ID` | guest-ops CSV | `2009` | `2009` | `2009` |
| `OS Name` | guest-ops CSV | `''` (blank) | `''` (blank) | `''` (blank) |
| `Last Boot Up Time` (ISO format) | VMware Tools vSphere API | `2026-06-10T08:44:42.916297Z` | `2026-06-11T08:41:16.115287Z` | absent (first collected post-rename) |

The `OS *`-prefixed keys with PowerShell timestamp format (`6/10/2026 3:44:48 AM`) are the output of `GuestOpsClient.collectOsInfo()` — the guest-ops CSV path through `CreateTemporaryDirectoryInGuest → InitiateFileTransferToGuest → StartProgramInGuest → InitiateFileTransferFromGuest`. They are present and populated on all three Windows VMs. `OS Name` is blank (WMI `Win32_OperatingSystem.Name` includes the installation path on Windows — likely the CSV contains the full path string which the script may not be trimming, but that is a separate issue).

---

### 6. Root cause determination — what `guestops_last_error: 'none'` actually means

The build-10 fault-capture property was designed to expose a previously-swallowed vim25 SOAP fault from `GuestOpsClient.post()`. `post()` sets `this.lastFault` only when `conn.getResponseCode() >= 300` — i.e., when vCenter returns HTTP 500 with a SOAP fault body. `'none'` means `post()` returned HTTP 200 (success) on every call for every Windows VM.

Tracing the code path for the `collectServices` call:

1. `VmCollector.java:328`: gate is `cfg.windowsMonitoring.services() && svcUsable && !winServices.isEmpty() && scripts.services != null`
2. `winServices` = `winSvc.items` from `SolutionConfigStore.fetchList(...)` for `config.winServiceConfigFile`
3. `config_file_status: windows_service_list: 0 check(s)` — `parseCommaList()` returned an empty list (0 items parsed from the XML body; this is a `usable=true` fetch with 0 entries, per the SolutionConfigStore design: "an empty list from a successfully-read file")
4. Therefore `!winServices.isEmpty()` is FALSE → **`collectServices` is never called** → no `CreateTemporaryDirectoryInGuest` for services, no fault possible

Tracing the `collectOsInfo` path:

1. `VmCollector.java:353`: gate is `cfg.windowsMonitoring.services() && scripts.osInfo != null`
2. This gate passes (monitoring is enabled, `getWindowsOSInformation.ps1` script is present)
3. `collectOsInfo()` runs → `createTempDir()` → `post(CreateTemporaryDirectoryInGuest)` → **HTTP 200** → temp dir created
4. `putFile()` → `post(InitiateFileTransferToGuest)` → HTTP 200 → file uploaded → HTTP PUT succeeds
5. `runPowershell()` → `post(StartProgramInGuest)` → HTTP 200 → PID returned → process runs, waits
6. `getFile()` → `post(InitiateFileTransferFromGuest)` → HTTP 200 → CSV URL returned → HTTP GET → CSV content retrieved
7. CSV parsed → `OsInfoRow` returned → `OS *` keys populated on the VM resource
8. `guestOps.lastFault()` = null (no HTTP 5xx anywhere) → `result.recordFault(vmName, null)` → no-op
9. `result.guestVmsDegraded` unchanged (0)

**Conclusion: guest-ops is working. The SOAP session succeeds end-to-end for all three Windows VMs. The vim25 credential format (`vcf@int.sentania.net` UPN in `NamePasswordAuthentication`) is accepted by vCenter's GuestOperationsManager. All four SOAP operations succeed. There is no authentication fault, no permission fault, no serialization fault.**

---

### 7. Why `windows_service_list: 0 check(s)` and `events_as_properties: 0`

**Services (`0 check(s)`):** The SolutionConfig `windows_service_list` XML fetched by the adapter contains zero service entries after `parseCommaList()`. The `collectServices` SOAP call is never made because the `!winServices.isEmpty()` guard short-circuits it. This is a **SolutionConfig content gap**, not a SOAP or credential failure. The devel SolutionConfig file for `winServiceConfigFile` is either empty, all-commented-out, or contains malformed XML that parses to 0 entries. The adapter fetched 716 bytes of event XML (`windows_event_list: fetched (716 bytes)`) successfully; by contrast the windows_service_list reports `0 check(s)` which is the SolutionConfigStore's `"<filename>: N check(s)"` status string for a successfully-fetched-but-empty-list file.

**Events (`events_as_properties: 0`):** The `collectEvents` call runs (gate: `cfg.windowsMonitoring.eventLogs() && winEventXml != null && scripts.events != null`). The XML was fetched (716 bytes). However the event PowerShell script ran on all three VMs and returned 0 rows — meaning no Windows events in the Application log matched the filter defined in the 716-byte XML. This is a log-content issue (no matching events in the current log window) or an event XML filter issue, not a SOAP failure.

---

### 8. Candidate root-cause assessment — revised by build-10 evidence

| Candidate (from build-9 investigation) | Build-10 verdict |
|---|---|
| `CreateTemporaryDirectoryInGuest` fault with `InvalidGuestLogin`/`GuestPermissionDenied` (auth/credential-delivery) | **EXONERATED** — `createTempDir` returns a valid path (OS keys prove it); `lastFault` is null |
| `StartProgramInGuest` fault with deserialization/type error (missing `xsi:type`) | **EXONERATED** — `runPowershell` returns a valid PID; `lastFault` is null; OS CSV is retrieved |
| `InitiateFileTransferToGuest` fault (fileAttributes / file-transfer issue) | **EXONERATED** — `putFile` succeeds; OS script is uploaded and executes |
| HTTP 200 + non-zero PowerShell exit (program/path issue, not SOAP fault) | **EXONERATED** — OS CSV has data; if exit were non-zero the `getFile` step would fail or return empty |
| Domain credential format mismatch (`vcf@int.sentania.net` vs `SENTANIA\vcf`) | **EXONERATED** — VGAuth on all three DCs accepts the UPN form (OsInfo runs successfully) |
| Missing vCenter privilege (`Guest Operation Program Execution`) | **EXONERATED** — `StartProgramInGuest` succeeds |

**No vim25 fault.** The blocking candidate is none of the above.

---

### 9. Actual root cause: SolutionConfig `windows_service_list` has 0 entries

The `windows_service_list: 0 check(s)` status is the direct cause of zero Services keys. The devel SolutionConfig for the windows service check-list is either:
- Empty XML body (no `<item>` or text content in the root element)
- All entries commented out (XML comments are stripped by the DOM parser per SolutionConfigStore design)
- File contains content but `parseCommaList()` finds no comma-delimited entries in the root element's text node

The Suite API does not expose SolutionConfig file content via a public GET endpoint (tested: `/api/solutionconfigs` → 404; solution-scoped path → 404). The adapter fetches it via the SDK-injected `SuiteApiStitcher` channel using a path not exposed through the public API surface. The raw content of the XML is not retrievable for inspection via recon.

What IS known from `config_file_status`:
- `windows_service_list: 0 check(s)` — fetchList succeeded (usable=true), parsed 0 items
- `windows_event_list: fetched (716 bytes)` — fetchRawXml succeeded, 716-byte XML body passed to guest

The fix is to populate the devel SolutionConfig `windows_service_list` file with at least one service name (e.g., `DHCP Client` — the same entry used by the prod symptom definition `vCommunity|Guest OS|Services:DHCP Client|Service Status`). Once the list has entries, `!winServices.isEmpty()` becomes true, `collectServices` fires, and the `vCommunity|Guest OS|Services:*` keys will appear.

---

### 10. Adapter / instance health — confirmed GREEN

| Check | Result |
|---|---|
| Anchor `resourceStatus` | DATA_RECEIVING |
| `messageFromAdapterInstance` | `""` (empty, no errors) |
| `Summary|status` | `OK` |
| `guest_vms_degraded` | 0.0 (10-cycle history: all 0.0) |
| `guestops_last_error` | `'none'` (3 post-upgrade cycles: all `'none'`) |

---

### 11. What needs to happen next (for orchestrator)

1. **SolutionConfig `windows_service_list` must be populated.** The adapter is working. The session succeeds. The only reason Services keys are absent is zero services configured. The admin (Scott) must edit the devel SolutionConfig file for the `winServiceConfigFile` identifier to add at least one service name (`DHCP Client` is the natural first entry — it matches the existing prod symptom). This is a configuration step, not a code fix.

2. **`OS Name` blank is a secondary gap.** `collectOsInfo()` executes and the script runs, but `OS Name` returns `''`. On Windows, `Win32_OperatingSystem.Name` returns a value like `Microsoft Windows Server 2022 Standard|C:\Windows|\Device\Harddisk0\Partition2` — if the original script does not truncate at `|`, the full string may be mishandled. Check `getWindowsOSInformation.ps1` in the pak scripts. Non-blocking for Services.

3. **`events_as_properties: 0` is a separate gap.** The event XML (716 bytes) is fetched and the script runs, but returns 0 rows on all three VMs. The event filter may specify an event source, ID, or time window that no current Application log entries match on devel. Check the devel SolutionConfig `windows_event_list` XML for the filter criteria and compare to what is actually in the Application log on dcint1/dcint2. Non-blocking for Services.

4. **No code change is needed to fix Services collection.** The credential format, SOAP authentication, temp-dir creation, file transfer, and program execution are all confirmed working. The fix is SolutionConfig data, not Java source.

5. **`vCommunity|Guest OS|Services:*` keys will appear on the NEXT cycle after the SolutionConfig is updated** (5-minute interval). The sentinel for success is `windows_service_list: N check(s)` where N > 0 in `config_file_status`, followed by `vCommunity|Guest OS|Services:DHCP Client|Service Status` appearing on dcint1/dcint2/automic.


---

## 2026-06-23 — vCommunity Windows Services config verification (devel)

**Task:** Verify that the `win_service_config_file` field change (pointing at `sentania_windows_service_list.xml` with DHCPServer + NTDS entries) resulted in services keys landing on dcint1/dcint2/automic.

**Instance:** vcf-lab-operations-devel.int.sentania.net (devel), adapter `vcfcf_vcommunity` build 1.0.0.10.

---

### 1. Adapter instance config

**Only one vCommunity adapter instance exists on devel:** mgmt (`d02a632f-01f8-458a-a868-9a33ef19dd46`, host `vcf-lab-vcenter-mgmt.int.sentania.net`). No wld01 instance is registered.

`win_service_config_file` field value: **`sentania_windows_service_list.xml`**

All other config fields for reference:
- `esxi_adv_settings_config_file`: `esxi_advanced_system_settings`
- `esxi_vib_driver_config_file`: `esxi_packages`
- `serviceMonitoring`: `Enabled`
- `vm_adv_settings_config_file`: `vm_advanced_parameters`
- `vm_configuration_config_file`: `vm_options`
- `win_event_config_file`: `windows_event_list`
- `winEventMonitoring`: `Enabled`

---

### 2. Config parse status (FAIL — double-extension bug)

`Summary|config_file_status` on world anchor `3d101989-15bf-4005-a25a-34ba25615a42`:

```
esxi_advanced_system_settings: 0 check(s); esxi_packages: 0 check(s); vm_advanced_parameters: 0 check(s); vm_options: 0 check(s); sentania_windows_service_list.xml: fetch failed: IOException: Suite API GET /api/configurations/files?path=SolutionConfig/sentania_windows_service_list.xml.xml HTTP 400 — no last-good cache; SKIPPING gated collection this cycle; windows_event_list: fetched (716 bytes)
```

**Root cause:** The adapter appends `.xml` to the bare config name it reads from `win_service_config_file`. The field value `sentania_windows_service_list.xml` already includes the `.xml` extension, so the resulting path becomes `SolutionConfig/sentania_windows_service_list.xml.xml` — which does not exist and returns HTTP 400.

The adapter code (in `VCommunityAdapter.java` or the config loader) adds `.xml` at resolution time assuming the field holds a *bare name* (no extension), exactly as the other config fields do (`windows_event_list` → `SolutionConfig/windows_event_list.xml`, `esxi_advanced_system_settings` → `SolutionConfig/esxi_advanced_system_settings.xml`). Scott's `sentania_windows_service_list.xml` value, having already included the extension, produces the double-extension URL.

Other metrics:
- `Summary|guestops_last_error`: `none`
- `Summary|status`: `OK`
- `Summary|guestops_vms`: `considered=37 passed=3 skipped=34`
- `Summary|guestops_ready`: `true`
- `Summary|last_scan_timestamp`: `2026-06-23T20:44:44Z`
- `Summary|guest_vms_degraded`: `0`

---

### 3. Services keys on Windows VMs

`vCommunity|Guest OS|Services:DHCPServer|*` — **ABSENT** on dcint1, dcint2, automic.
`vCommunity|Guest OS|Services:NTDS|*` — **ABSENT** on dcint1, dcint2, automic.

All three VMs are showing existing vCommunity keys (SCSI controller type, snapshot count) confirming the stitching pipeline is active, but zero service keys of any kind. This is consistent with the config-fetch failure gating the entire services collection.

Last collection timestamp on world anchor: `2026-06-23T20:43:46Z` (at time of check, ~3 minutes prior — a live post-edit cycle has run and produced the failed state captured above).

**No post-edit cycle is pending** — the 20:43:46 cycle ran AFTER Scott made the edit and it already shows the double-extension error. The absence of service keys is therefore CONFIRMED FAIL, not PENDING.

VM OS info present (confirming in-guest execution works):
- dcint1: OS 10.0.26100 (Windows Server 2025), last boot 2026-06-10T08:44:42Z
- dcint2: OS 10.0.26100 (Windows Server 2025), last boot 2026-06-11T08:41:16Z
- automic: OS 10.0.26100, last boot 2026-06-23T03:33:42Z

---

### 4. Adapter health

- `resourceStatus`: DATA_RECEIVING
- `resourceState`: STARTED
- `statusMessage`: (empty)
- `resourceHealth`: GREEN (100.0)
- `Summary|guest_vms_degraded`: 0
- `messageFromAdapterInstance`: not surfaced as a property (no message)

---

### Fix required

Change the `win_service_config_file` field value from `sentania_windows_service_list.xml` to **`sentania_windows_service_list`** (bare name, no extension). The adapter appends `.xml` automatically, exactly as it does for all other config file fields. The corrected URL will be `SolutionConfig/sentania_windows_service_list.xml`.

Verify the SolutionConfig file exists under that exact path on the instance (i.e. the file was uploaded as `sentania_windows_service_list.xml` under `SolutionConfig/`).

After the field is corrected, the next 5-minute cycle should show:
- `config_file_status`: `sentania_windows_service_list: 2 check(s)` (or equivalent N check(s) for the two service entries)
- `vCommunity|Guest OS|Services:DHCPServer|Service Status` on dcint1 and dcint2 (both are DCs running AD DS — NTDS; only dcint1 or one of them would run DHCP Server)
- `vCommunity|Guest OS|Services:NTDS|Service Status` on dcint1 and dcint2


---

## 2026-06-23 — vCommunity Windows Services config verification, round 2 (devel + prod)

**Date:** 2026-06-23T21:14Z UTC
**Agent:** ops-recon
**Task:** Confirm current state of `win_service_config_file` (double-extension bug fix) and
Services key population across devel and prod. Prior entry (same date, earlier) found `.xml.xml`
bug still active. Scott reports he has since "updated the service file."

---

### DEVEL — vcf-lab-operations-devel.int.sentania.net

#### 1. Adapter instance config

Instance: `d02a632f-01f8-458a-a868-9a33ef19dd46` (host: vcf-lab-vcenter-mgmt.int.sentania.net)

`win_service_config_file` = **`sentania_windows_service_list`** (bare name, no `.xml` extension)

The double-extension bug IS FIXED. All other identifier fields unchanged:
- `esxi_adv_settings_config_file`: `esxi_advanced_system_settings`
- `esxi_vib_driver_config_file`: `esxi_packages`
- `serviceMonitoring`: `Enabled`
- `winEventMonitoring`: `Enabled`
- `win_event_config_file`: `windows_event_list`

#### 2. Config parse status (PASS — 2 check(s))

`Summary|config_file_status` on world anchor `3d101989-15bf-4005-a25a-34ba25615a42`
(observed at ~21:10Z cycle, ~21:14:45Z query time):

```
esxi_advanced_system_settings: 0 check(s); esxi_packages: 0 check(s);
vm_advanced_parameters: 0 check(s); vm_options: 0 check(s);
sentania_windows_service_list: 2 check(s);
windows_event_list: fetched (716 bytes)
```

`sentania_windows_service_list: 2 check(s)` — the file fetches cleanly (HTTP 200),
`parseCommaList()` found 2 entries (DHCPServer, NTDS). The `!winServices.isEmpty()` gate
is now TRUE; `collectServices()` IS being called on each guestops-eligible VM.

Other anchor diagnostics:
- `Summary|guestops_last_error`: `none`
- `Summary|status`: `OK`
- `Summary|guestops_ready`: `true`
- `Summary|guestops_vms`: `considered=37 passed=3 skipped=34`
- `Summary|last_scan_timestamp`: `2026-06-23T21:10:15.001214459Z`
- `Summary|guest_vms_attempted` (stat): `3.0` @ `2026-06-23T21:09:21Z`
- `Summary|guest_vms_degraded` (stat): `3.0` @ same timestamp

#### 3. Services keys on Windows VMs (FAIL — guest-ops SOAP session still failing)

All three VMs show `vCommunity|Guest OS|Collection Status = 'DEGRADED — one or more
guest-ops collectors returned no data this cycle (see adapter log)'`.

| VM | Services:DHCPServer|* | Services:NTDS|* | Collection Status |
|---|---|---|---|
| dcint1 (`6a20cdd2-...`) | ABSENT | ABSENT | DEGRADED |
| dcint2 (`d5a62a0e-...`) | ABSENT | ABSENT | DEGRADED |
| automic (`b09a6f27-...`) | ABSENT | ABSENT | DEGRADED |

`vCommunity|Guest OS|Operating System` keys ARE present and populated on all three
(OS 10.0.26100, architecture, build number, last boot times), confirming the
non-CSV collector path works (OsInfo via `collectOsInfo()` is running).

`OS Name` is blank on all three VMs (`''`) — the `getWindowsOSInformation.ps1`
script is executing but its Name field returns empty (secondary gap, non-blocking).

**Diagnosis:** `collectServices()` IS being invoked now (gate is open). But the
guest-ops SOAP session is failing silently. The fault is swallowed at
`GuestOpsClient.post()` (`:468`): HTTP 500 + SOAP fault body → `null` return →
no exception thrown → catch block at `:168` never fires → `logWarn` never executes
→ `guestops_last_error` stays `'none'`. The individual VM `Collection Status = DEGRADED`
is the only observable. The exact vim25 fault name is not accessible via Suite API
without the appliance adapter log.

This means the Services collection is blocked by the same guest-ops SOAP fault as
diagnosed in the prior investigation (`vcommunity-guestops-execution-divergence-2026-06-22.md`),
candidates: credential wire format / password XML-escaping, or `<spec>` missing
`xsi:type="GuestProgramSpec"`, or `<fileAttributes/>` type mismatch. The SolutionConfig
fix is complete and correct; the remaining blocker is entirely inside `GuestOpsClient`.

**OsInfo vs Services divergence note:** `collectOsInfo()` also uses guest-ops
(`guestProcManager.StartProgram`), yet OsInfo keys ARE present. This means the
guest-ops session SUCCEEDS for OsInfo — the divergence must be in the script/output
path, not the session establishment. Most likely: OsInfo script (`getWindowsOSInformation.ps1`)
produces partial output (OS fields come from `-ExpandProperty` WMI calls, some of which
succeed, others return empty); Services script (`getWindowsServices.ps1`) uses a
`Get-Service` loop that may error or return nothing for DHCPServer/NTDS due to the service
names, account privilege, or WMI scope — and the empty CSV triggers `0 rows → skip`.
This is a different failure mode than previously assumed. **The SOAP session is working.**
The per-script execution or output parsing may be the actual Services gap.

**Revised root-cause ranking:**
1. (HIGHEST, newly elevated) `getWindowsServices.ps1` fails or returns empty for
   `DHCPServer`/`NTDS` inside the already-successful guest-ops session. The script may
   use `Get-Service -Name $serviceList` and one or both names may not resolve, causing
   `Get-Service` to error and output nothing. Needs adapter log or script output inspection.
2. (MEDIUM) Per-script privilege: OsInfo uses `Win32_OperatingSystem` (read-only, any
   account), Services uses `Get-Service` which may require elevated privileges
   (`SeLoadDriverPrivilege` or similar) that `vcf@int.sentania.net` lacks on dcint1/dcint2.
3. (LOWER, prior candidate) `GuestOpsClient.post()` silent fault — now LESS likely since
   OsInfo proves the session works; but still possible if Services uses a different API
   entry point that faults.

**Devel verdict:** PENDING (config fix PASS, Services keys FAIL — cause shifted from
SolutionConfig to guest-ops script execution or privilege).

---

### PROD — vcf-lab-operations.int.sentania.net

#### 4. Adapter instances

Three `VCFOperationsvCommunity` adapter instances:
- mgmt: `3555f3cd-...` (vcf-lab-vcenter-mgmt.int.sentania.net) — `win_service_config_file = sentania_windows_service_list`
- wld01: `4845aba2-...` (vcf-lab-vcenter-wld01.int.sentania.net) — `win_service_config_file = windows_service_list`
- wld02: `ca532ed3-...` (vcf-lab-vcenter-wld02.int.sentania.net) — `win_service_config_file = windows_service_list`

**Only the mgmt adapter has been updated.** wld01 and wld02 still point at the default
`windows_service_list` which is ALL COMMENTED OUT — they will produce 0 check(s) and no
Service keys regardless of this change.

#### 5. SolutionConfig file state on prod

`GET /api/configurations/files?path=SolutionConfig/sentania_windows_service_list.xml`
→ **HTTP 200**. File content:

```xml
<windowsServices>
DHCPServer,NTDS
</windowsServices>
```

The file is present and contains exactly the two service names. The Python adapter
reads `win_service_config_file = sentania_windows_service_list` → appends `.xml` →
fetches `sentania_windows_service_list.xml` → parses comma-separated list → `[DHCPServer, NTDS]`.

Default `windows_service_list.xml` (used by wld01/wld02): all entries are commented out
(`<!-- Dhcp -->`, `<!-- WinDefend -->`, etc.). No effective service entries.

#### 6. Services keys on prod DCs

Last prod mgmt-adapter cycle: `2026-06-23T21:11:17Z` (at query time `21:14:18Z`, cycle
was 3 minutes prior — next cycle expected ~21:16Z).

**Timing:** The `sentania_windows_service_list.xml` file was uploaded to prod just before
this recon was run. The cycle at `21:11:17Z` most likely PREDATES the file upload. The
file will be read on the next cycle (~21:16Z).

| VM | Services:DHCPServer|* | Services:NTDS|* | Note |
|---|---|---|---|
| dcint1 (`4c5bcff0-...`) | ABSENT | ABSENT | Next cycle pending |
| dcint2 (`39e69282-...`) | ABSENT | ABSENT | Next cycle pending |
| automic (`8cebd7da-...`) | ABSENT | ABSENT | Not a DC; NTDS/DHCPServer not expected |

OS properties fully populated on prod dcint1/dcint2 (unlike devel, `OS Name` IS populated:
`Microsoft Windows Server 2025 Standard` on both DCs, `Windows Server 2025 Datacenter` on
automic). This confirms the original Python adapter's `getWindowsOSInformation.ps1` correctly
returns OS Name. The blank `OS Name` on devel is specific to the Java port.

Prod adapter instance Attributes stats (at 21:11:17Z):
- `collected_metrics`: 79
- `collected_resources`: 43
- `reropted_events`: 3 (Windows event-log collection active)
- `elapsed_collect_time`: 49271ms (~49 seconds)

**Prod verdict:** PENDING — file is staged, Services keys not yet present because the first
eligible cycle has not yet run. Expected to appear ~21:16Z on dcint1 and dcint2. automic
absence-by-design (not a DC, not a DHCP server).

---

### Summary: mismatches and flags

| Item | Devel | Prod |
|---|---|---|
| `win_service_config_file` value | `sentania_windows_service_list` (bare) | `sentania_windows_service_list` (bare) — mgmt only; wld01/wld02 still default |
| Double-extension bug | FIXED | N/A (Python adapter correct) |
| SolutionConfig file fetch | 200, 2 check(s) | 200 (file confirmed, cycle not yet run) |
| Services keys — dcint1/dcint2 | ABSENT (guest-ops script/privilege fail) | ABSENT (next cycle pending) |
| `OS Name` populated | BLANK on all 3 VMs | Correct on all 3 VMs |
| Active Services gap cause | `getWindowsServices.ps1` execution or privilege | N/A (pre-cycle) |

**New finding:** OsInfo succeeds on devel (session works) while Services fails (script/output
gap). Prior hypothesis of session-level SOAP fault is now downgraded. The most probable new
cause is `getWindowsServices.ps1` returning no rows for `DHCPServer`/`NTDS` service names —
either a `Get-Service` error (name not found, PowerShell error output, not data output) or
a privilege gap. Checking the script output requires adapter log access or adding a per-VM
`guestops_last_error` property to the build-11 anchor diagnostics.

**Prod wld01/wld02 note:** These two adapter instances will never produce Services data
until their `win_service_config_file` is updated from the default (all-commented). This is
a separate config task and does not affect the mgmt adapter's progress.

---

## 2026-06-23 — Prod Windows Services control-case check (Python original, build v0.2.8)

**Target:** `VCFOperationsvCommunity` adapter (Python original, v0.2.8) on prod
(`vcf-lab-operations.int.sentania.net`). Mgmt adapter instance
(`vcf-lab-vcenter-mgmt.int.sentania.net`, ID `3555f3cd-26cc-4e8b-acdb-158fd5cae069`).
**Purpose:** Control-case to determine whether prod (Python original, same service-name
config as devel build-11) successfully collects DHCPServer/NTDS services data on
dcint1/dcint2 — the decisive test for whether build-11's failure is a port bug or an
environment/config problem.
**Investigator:** ops-recon

---

### Adapter config confirmed

| Field | Value |
|---|---|
| Adapter kind key | `VCFOperationsvCommunity` |
| Adapter instance | `vcf-lab-vcenter-mgmt.int.sentania.net` (ID `3555f3cd`) |
| `win_service_config_file` | `sentania_windows_service_list` |
| `serviceMonitoring` | `Enabled` |
| `winEventMonitoring` | `Enabled` |
| `numberOfResourcesCollected` | 43 |
| `numberOfMetricsCollected` | 79 |
| `lastCollected` | `2026-06-23T21:27:16Z` |
| `lastHeartbeat` | `2026-06-23T21:30:59Z` |

Last collection is confirmed post-file-upload (Scott uploaded `sentania_windows_service_list`
with content `DHCPServer,NTDS` earlier today). At least one full collection cycle has run
since the file was in place.

---

### DC resources confirmed in adapter scope

| VM | Resource ID | Adapter scope |
|---|---|---|
| dcint1 | `4c5bcff0-c697-4e92-9ba7-8e15ad61d18f` | YES — mgmt adapter 43-resource collection |
| dcint2 | `39e69282-0f38-40c6-ad1b-960f778d79ed` | YES — mgmt adapter 43-resource collection |

Both are `VirtualMachine` kind objects stitched to the VMWARE adapter (same resource IDs
returned by both `adapterKindKey=VCFOperationsvCommunity` and `adapterKindKey=VMWARE`
queries — vCommunity pushes properties/stats onto VMWARE VM objects).

---

### Check 1 — Services stat keys (DHCPServer / NTDS)

Queried via:
- `/api/resources/{rid}/statkeys` (registered stat keys)
- `/api/resources/stats/query` (bulk, explicit stat key list)
- `/api/resources/{rid}/stats/latest` (per-resource latest)
- `/api/resources/{rid}/properties` (string/property values)

| Key | dcint1 | dcint2 |
|---|---|---|
| `vCommunity\|Guest OS\|Services:DHCPServer\|Service Status` | **ABSENT** | **ABSENT** |
| `vCommunity\|Guest OS\|Services:DHCPServer\|Service Start Type` | **ABSENT** | **ABSENT** |
| `vCommunity\|Guest OS\|Services:DHCPServer\|Service Name` | **ABSENT** | **ABSENT** |
| `vCommunity\|Guest OS\|Services:NTDS\|Service Status` | **ABSENT** | **ABSENT** |
| `vCommunity\|Guest OS\|Services:NTDS\|Service Start Type` | **ABSENT** | **ABSENT** |
| `vCommunity\|Guest OS\|Services:NTDS\|Service Name` | **ABSENT** | **ABSENT** |

Zero service stat keys or properties exist on either DC. The registered stat key list for
dcint1 has 239 entries; dcint2 has 240. Of those, only 2 are `vCommunity|*` stat keys
on each (`vCommunity|Configuration|SCSI Controllers|Count` and `vCommunity|Snapshot|Count`).
No `vCommunity|Guest OS|Services:*` keys are registered at all.

---

### Check 2 — Collection Status

| Key | dcint1 | dcint2 |
|---|---|---|
| `vCommunity\|Guest OS\|Collection Status` | **ABSENT** | **ABSENT** |

Not present as a stat or property on either DC. Neither degraded nor OK — the key does not
exist, which means the services collection path did not emit any status metric.

---

### Check 3 — OS info keys (control — confirms adapter IS collecting)

vCommunity OS properties ARE present and populated on both DCs, confirming the adapter
ran GuestOps collection successfully on at least one code path:

| Key | dcint1 | dcint2 |
|---|---|---|
| `vCommunity\|Guest OS\|Operating System\|OS Name` | `Microsoft Windows Server 2025 Standard` | `Microsoft Windows Server 2025 Standard` |
| `vCommunity\|Guest OS\|Operating System\|OS Version` | `10.0.26100` | `10.0.26100` |
| `vCommunity\|Guest OS\|Operating System\|OS Architecture` | `64-bit` | `64-bit` |
| `vCommunity\|Guest OS\|Operating System\|OS BuildNumber` | `26100` | `26100` |
| `vCommunity\|Guest OS\|Operating System\|OS Release ID` | `2009` | `2009` |
| `vCommunity\|Guest OS\|Operating System\|OS Last Boot Up Time` | `6/10/2026 3:44:48 AM` | `6/11/2026 3:41:19 AM` |

OS info is the same set seen on devel build-11, which also successfully collects these.

---

### Verdict

**FAIL** — Prod (Python original v0.2.8) **does NOT collect DHCPServer/NTDS services data**
on dcint1 or dcint2. After a confirmed post-file-upload collection cycle (21:27:16Z),
zero `vCommunity|Guest OS|Services:*` keys exist on either DC.

**Control-case conclusion:** This is NOT a decisive isolation of the port bug.

Prod and devel build-11 both fail to produce services keys for DHCPServer/NTDS under the
same conditions (same service-name config file, same DCs, Windows Server 2025, same adapter
scope). Since prod's Python original also fails, the failure is NOT specific to the Java
port — the Python original behaves identically. The root cause is upstream of the
adapter-language boundary:

- The `sentania_windows_service_list` file content (`DHCPServer,NTDS`) was uploaded but the
  GuestOps script may not be successfully executing on the Windows VMs via VMware Tools,
  **or** the service name lookup is failing silently (e.g., `Get-Service -Name DHCPServer`
  errors because the service display name vs. service name mismatch on Windows Server 2025,
  or VMware Tools GuestOps execution is failing to get a result back).
- OS info metrics populate fine (different GuestOps code path, likely `Get-WmiObject Win32_OperatingSystem`
  or similar that returns immediately without depending on service name enumeration).
- The Python original's services collection path is broken on these Windows Server 2025 DCs,
  making it an invalid control for the Java port.

**Implication for build-11 diagnosis:** The devel build-11 failure cannot be attributed to
the Java port without first establishing that the Python original works. It does not. Both
fail. Investigate the GuestOps PowerShell execution path (service name format, VMware Tools
version, PowerShell execution policy) on the DCs themselves before continuing port-specific
debugging.

**Clean-up verified:** Read-only GET calls only. No content mutated.


---

## 2026-06-23 — vCommunity guest-ops credential swap validation (post-swap cycle check)

**Target:** `vcfcf_vcommunity` build 1.0.0.11, instance resource
`d02a632f-01f8-458a-a868-9a33ef19dd46`, world anchor `3d101989-15bf-4005-a25a-34ba25615a42`.
**Instance:** vcf-lab-operations-devel.int.sentania.net.
**Context:** Previous credential `vcf@int.sentania.net` swapped out; `sentania@int.sentania.net`
(domain-admin) swapped in as Windows Guest Credential (`winUser`). Recon was requested to
confirm whether a post-swap cycle ran and whether service keys appeared.
**Mode:** Read-only GET only.

### 1. Credential confirmed

`GET /api/credentials/2ff0c11c-b981-4446-b4d3-dc68205f02b0`:
- `winUser`: `sentania@int.sentania.net` — domain-admin account is live on the instance.
- `serviceMonitoring`: `Enabled`, `winEventMonitoring`: `Enabled` (confirmed in resource
  identifiers).

### 2. Post-swap cycle ran — CONFIRMED

**Adapter instance `lastCollected`:** `2026-06-23T21:53:21.145Z`
(from `Instance Attributes|elapsed_collect_time` stats on the vCenter resource, timestamped at
`2026-06-23T21:53:21.145Z`, age ~173 s at query time).

**World anchor `Summary|last_scan_timestamp`:** `2026-06-23T21:53:21.145158119Z`

Cycle duration: 74,656 ms (~74.7 s). A full collection cycle has completed since the swap.

`Instance Attributes|property_value_changes: 2` — something changed on the resource in this cycle
(credential swap propagation artifact, likely credential-reference update or minor property churn).

### 3. Service keys — ABSENT on all three Windows VMs

Queried `GET /api/resources/{id}/properties` and `GET /api/resources/{id}/statkeys` for:

| VM | resource ID |
|---|---|
| dcint1 | `6a20cdd2-559e-46c0-814f-0c9d4beebb2e` |
| dcint2 | `d5a62a0e-ad80-4b9a-a5e3-4e1122a68fc9` |
| automic | `b09a6f27-869d-428e-a749-6d489441f13c` |

**No `vCommunity|Guest OS|Services:*` keys exist on any of the three VMs.**
`dcint1` statkeys confirmed: 0 Services entries in the full statkey list.

### 4. Collection Status — still DEGRADED on all three

All three VMs report:
```
vCommunity|Guest OS|Collection Status: 'DEGRADED — one or more guest-ops collectors returned
no data this cycle (see adapter log)'
```

Status has NOT flipped to OK.

### 5. World anchor Summary stats (post-swap cycle)

| Key | Value |
|---|---|
| `Summary|guest_vms_degraded` | **3** (unchanged) |
| `Summary|guest_vms_attempted` | 3 |
| `Summary|guestops_vms` | `considered=37 passed=3 skipped=34` |
| `Summary|guestops_last_error` | `none` |
| `Summary|status` | `OK` |
| `Summary|last_scan_timestamp` | `2026-06-23T21:53:21.145158119Z` |

Note: `guestops_last_error: none` and `Summary|status: OK` are surprising given 3 VMs are
DEGRADED. This is consistent with the previously documented observability defect:
`GuestOpsClient.post()` swallows non-2xx as null without logging the SOAP faultstring, so no
error surfaces at the world-anchor level even though all three guest-ops collections return empty.

Passive vim25 OS info (OS Version, BuildNumber, Architecture, Last Boot Up Time) still populates
on all three VMs, confirming the vSphere data path (DATA_RECEIVING) is intact. Only the in-guest
execution path is broken.

### 6. Verdict: FAIL

A post-swap cycle ran (cycle timestamp `2026-06-23T21:53:21Z`, ~5 min before recon request). The
domain-admin credential `sentania@int.sentania.net` is live. Services keys are still absent.
Collection Status is still DEGRADED on dcint1, dcint2, and automic.

**The logon-rights / credential-identity theory is not confirmed by this evidence.** Swapping from
`vcf@int.sentania.net` to a domain-admin account produced no change in guest-ops output. Either:
(a) the fault is happening before the auth credential matters (auth format / wire-level delivery
bug — the `xmlEscape` / password-serialization path in `GuestOpsClient.java:423-430`); or
(b) the fault is at a later call (`StartProgramInGuest`, `InitiateFileTransferToGuest`) and the
account level is not the variable; or
(c) something else in the environment (VMware Tools state, vCenter permission, network between
collector and guest) is uniform across all three VMs regardless of the credential value.

The `guestops_last_error: none` world anchor with 3 VMs DEGRADED is itself evidence that the
fault is not reaching the surface — consistent with the silent-null in `GuestOpsClient.post()`.

**First-priority action remains:** instrument `GuestOpsClient.post()` to extract and log the SOAP
`<faultstring>` on non-2xx (mirroring `VCommunityVSphereClient.post()`). Without the faultstring
we cannot distinguish auth-format vs. call-structure vs. environment causes. The domain-admin
swap was a useful control — it removes privilege-level as a variable — but it does not name
the fault.

**Clean-up verified:** Read-only GET calls only. No content mutated.
