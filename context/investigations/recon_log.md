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

