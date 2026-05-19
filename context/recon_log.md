# Recon Log

Append-only. Each entry is a dated investigation section.

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

