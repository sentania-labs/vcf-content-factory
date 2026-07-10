# Parity review — `vcommunity-vsphere` vs original vCommunity source pak (vSphere scope)

**Reviewer:** `sdk-adapter-reviewer` (read-only, static)
**Date:** 2026-07-09
**Adapter under review:** `content/sdk-adapters/vcommunity-vsphere/` (build_number 4, branch `fix/localization-raw-keys-build-2`, working tree AS-IS)
**Reference source (RULE-016, read-only):** `reference/references/vmbro_vcf_operations_vcommunity/` — Onur Yuzseven's `VCFOperationsvCommunity` Python Integration-SDK pak
**Scope:** vSphere aspects only (clusters/hosts/VMs stitched onto VMWARE kinds). Guest-OS/Windows surface is out of scope here (belongs to `vcommunity-os` by design).
**Type:** parity review, NOT a build review. No install, no live calls.

---

## Branch note (origin/main vs `fix/localization-raw-keys-build-2`)

The in-flight branch touches ONLY localization plumbing: `resources/resources.properties`, `.github/workflows/build-pak-on-tag.yml`, `CHANGELOG.md`, `adapter.yaml` (build_number → 4), `docs/README.md`, `docs/inventory-tree.md`. It touches **no** collector Java, **no** `content/`, **no** dashboards/alerts/symptoms/views, and **adds no reports**. **Every parity finding below is present identically on origin/main and on this branch** — none is introduced or resolved by the localization fix.

---

## Parity summary

**Collector / metric-key parity (the load-bearing surface): FULL.** Every vSphere-scoped `vCommunity|` key family the source emits is emitted by our Java, with matching metric-vs-property typing and matching gating semantics. This confirms the parity-plan claim that pak-level collector parity is "essentially reached."

**Content parity: PARTIAL — not yet at the split design's declared bar.** Super-metrics and user-facing dashboards are fully ported; symptoms/alerts and views/reports are not.

| Surface | Source (vSphere-allocated) | Ported to ours | Verdict |
|---|---|---|---|
| Cluster keys | 13 | 13 | FULL |
| Host key families | adv-settings + packages(7) + install-date + licensing(5) + uplink(4) | all | FULL |
| VM key families (vSphere) | snapshot + options + adv-params + SCSI(2) + Tools OS(6) | all | FULL |
| Super metrics | 37 canonical | 37 | FULL |
| Symptoms (vSphere) | 1 (NIC Disconnected) | 1 | FULL |
| Alerts (vSphere) | 2 (NIC Disconnected, License Expiring) | 1 | **GAP: License Expiring missing** |
| Dashboards (user-facing) | 12 | 12 | FULL |
| Dashboards (report template) | 1 (Input dashboards) | 0 | GAP (tied to reports) |
| Views | 16 | ~11 present + ~95-view superset | **GAP: ~4–5 source views absent** |
| Reports | 16 (`Report - VOA - *`) | 0 (no `reports/` dir) | **GAP: all 16 missing** |

---

## 1. Object/metric/property parity — mapping (source → ours)

### Cluster (`ClusterCollector.java` vs `collectClusterData.py` + `clusterConfigs.yaml`) — 13/13 FULL

| Source key | Ours | Status |
|---|---|---|
| `Cluster Configuration\|vSphere HA\|Host Monitoring` | same | present |
| `…vSphere HA\|Response \ Host Isolation / Default VM Restart Priority / Datastore APD / Datastore PDL` | same | present |
| `…vSphere HA\|VM Monitoring`, `…\|Heartbeat Datastore` | same | present |
| `…DRS\|Proactive DRS`, `…DRS\|Scale Descendants Shares` | same | present |
| `…DRS\|CPU Over-Commitment` ("N/A" when `MaxVcpusPerCore` absent) | same | present |
| `…DRS\|DRS Score` (metric) | same (stats) | present, type preserved |
| `…EVC\|Enabled`, `…EVC\|Mode` | same | present |

HA/DRS "null"-when-disabled gating and EVC enabled/mode logic are faithfully reproduced.

### Host (`HostCollector.java` vs `collectHostData.py` + property collectors) — FULL

`Configuration|Advanced System Settings|{key}` (check-list-filtered), `Configuration|Packages:{name}|*` (7 keys), `Configuration|Install Date|UTC`, `Licensing:{name}|{Name,License Key,License Expiration Date,Edition Key}` + `Remaining Days` (metric), `Network|Device:{device}|{Device Name,Driver Version,Firmware Version,Status}` — all present, connected-host-only gating preserved.

### VM (`VmCollector.java` vs `collectVMData.py` + property collectors) — vSphere surface FULL

`Snapshot|Count` (metric), `Options|{configPath}`, `Configuration|Advanced Parameters|{key}`, `Configuration|SCSI Controllers|Count` (metric) + `Configuration|SCSI Controllers:{bus}|Type`, `Guest OS|Operating System|OS {Name,Version,BuildNumber,Architecture,Last Boot Up Time,Release ID}` (Tools path). Key names match; metric-vs-property typing matches; SCSI legacy pipe-key deliberately not resurrected (documented, matches upstream deletion commit d4633a6).

### BY-DESIGN moved off vSphere (NOT gaps)

`Guest OS|Services:*`, Windows event logs, and the in-guest CSV `Guest OS|Operating System|*` path → allocated to `vcommunity-os` per `vcommunity-three-adapter-split.md` §1 (surface allocation) and the 2026-06-23 OPEN-A refinement (vsphere keeps the passive Tools-path OS keys; os owns the richer in-guest path). `GuestOpsClient` correctly stripped from this fork.

---

## 2. BY-DESIGN divergences (cited, not gaps)

- **Guest-OS/Windows surface absent from vsphere** — `vcommunity-three-adapter-split.md` §1, §5. Services/events/CSV-OS ship in `vcommunity-os`.
- **Windows Service Down symptom + alert absent from vsphere** — split §5 allocates them to `vcommunity-os`. Correct.
- **Passive Tools-path OS keys emitted for ALL guests (incl. non-Windows)** — a benign superset vs the source's Windows-only CSV path; split §1 OPEN-A refinement (2026-06-23) explicitly keeps this in vsphere.
- **Stitch identity uses `VMEntityVCID`-scoped MOID join, not the source's bare `VMEntityObjectID` (MOID-only)** — this is an intentional *improvement* per `knowledge/lessons/stitch-moid-not-unique-across-vcenters.md` (the build-2 scoping fix). Confirmed present in `VCommunityStitcher`. Not a regression; a correctness upgrade over the source.
- **Install-date read failure degraded to a `Configuration|Install Date|Read Error` property instead of the source's CRITICAL foreign-resource event** — TOOLSET GAP #1 (no foreign-event push in the factory Suite API facade), documented in `HostCollector.java` header. Accepted staged divergence.

---

## 3. Behavioral / unit / type parity

- **No unit or type drift.** Every source `with_metric` stays a stat (DRS Score, Remaining Days, SCSI Count, Snapshot Count); every `with_property` stays a property. Verified per collector.
- **Gating preserved** (HA/DRS disabled → "null"; connected-host only; EVC enabled/mode).
- **Reflection-tolerant reads** — unreadable fields skip rather than push sentinels; per-resource try/catch isolates a single object's failure from the cycle. (Not the focus of a parity review, but no cardinal-correctness regression was observed while mapping keys.)
- **One data-source divergence worth flagging** (see WARNING below): the `Critical Business Applications` dashboard's "OS Services" widget points at a **Service Discovery (`APPLICATIONDISCOVERY`) view (`Guest OS List of Services`)**, not the source's vCommunity `Guest OS|Services`-keyed view. The widget renders from a different adapter's data than the original intended.

---

## 4. Real gaps — ranked by operator value

1. **[HIGH] `ESXi Host License Expiring` alert MISSING** (`alertdefs/ESXi Host License Expiring.xml` in source; only `esxi-host-nic-disconnected.yaml` exists in `alerts/`). This is a vSphere-scoped alert on `vCommunity|Licensing:*|Remaining Days` — a key **our HostCollector already emits** — with inline tiered conditions (<30 crit / 30–60 warn / 60–90 / 90–160). Split design §5 explicitly allocates it to vsphere. Operators lose all proactive license-expiry warning despite the data landing. Smallest fix: port the one inline-condition alertdef. **Highest value, lowest cost.**
2. **[MED-HIGH] All 16 `Report - VOA - *` reports MISSING** (no `reports/` directory; no `ReportDef` anywhere in the pak). Split §5 allocates all 16 to vsphere; parity-plan Phase 2 authors reports last, so this is known-incomplete rather than a defect — but it is a real, large parity gap (Capacity, Configuration, Inventory, Executive Summary, Performance, and the CSV-export set). Depends on the **`Input dashboards` template dashboard**, also not ported.
3. **[MED] `nfnic VIB Vendor Distribution` view MISSING** (source `View - Cluster nenic nfnic VIBs.xml`). Reads the VIB/package surface our HostCollector emits; no equivalent in our 95-view set. Operator loses VIB-vendor visibility that the pak's own data supports.
4. **[MED] SM-consuming source views MISSING: `VM Network Top Talkers` (Collection01), `VM Memory Allocation Trend` (Set 1), and the `Distributed Port Groups` view (Set 4).** The consumed SMs all exist in our pak, so these are pure content ports. (`ESXi High Memory Trend` (Set 2) and `VM Memory Size Distribution` (Set 3) ARE present.)
5. **[LOW] `Windows Services vCommunity` view not ported to vsphere** — split OPEN-B1 said ship it once in vsphere so the `Critical Business Applications` embed resolves and degrades gracefully. Instead the dashboard substitutes a Service Discovery view (`Guest OS List of Services`). The dashboard is functional, but (a) it no longer reflects the vCommunity pak's own guest-services data and (b) it silently depends on the separate Service Discovery adapter. Deviates from the design's stated OPEN-B1 resolution.

**Note (not a gap):** our pak ships a ~95-view superset far beyond Onur's 16 (ESXi CPU/BIOS/HyperThread/Storage-adapter distributions, VM capacity/latency/RDM views, cluster/port-group config views, etc.). Value-add, but it raises the cross-pak name-collision surface with `vcommunity-os` if that pak also ships views — worth a uniqueness check before both are installed together.

---

## 5. Registry check (`knowledge/context/defects.md`)

- **No OPEN defect names `vcommunity-vsphere` in its `Affects:` line.** The one open vCommunity defect (line 138, guest-ops in-guest collection empty) `Affects: vcommunity-os` only — out of scope here.
- The closed framework-transport defect (DEF, line 161, `Affects: synology`, Status: closed) notes the shared Tier-2 transport ships in `vcommunity*` and should be "verified per pak as each rebuilds" — informational; that defect is already closed and is not a `vcommunity-vsphere` open item.

---

## Verdict — do the parity-plan claims hold?

**Collector / metric-key parity claim: HOLDS.** Every vSphere-scoped source key is emitted, correctly typed, with source gating semantics preserved, plus a stitch-identity correctness improvement over the source. Metric-parity is genuinely at the bar.

**Content-parity claim: DOES NOT YET HOLD.** The split design §5 allocates 16 reports + the license-expiry alert + several views to vsphere; the pak ships 0 reports, 1 of 2 alerts, and ~11 of 16 source views. This is consistent with parity-plan Phase 2 being incomplete (reports authored last), so it is *known-incomplete parity*, not a silent false claim — but any statement that `vcommunity-vsphere` is at like-for-like content parity with the source is **not yet true**.

**Recommended fix order handed back to the orchestrator (I do not fix):**
1. Port `ESXi Host License Expiring` alert (data already lands; highest value/lowest cost).
2. Port `nfnic VIB Vendor Distribution` + the three missing SM-consuming views.
3. Decide OPEN-B1 for real: either port `Windows Services vCommunity` into vsphere as the design says, or formally record the Service-Discovery substitution as the accepted divergence in the split design.
4. Port the 16 VOA reports + the `Input dashboards` template (Phase-2-last bulk work).

No cardinal-correctness (unreadable-is-compliant), stitch-corruption, or crash-the-cycle finding was observed in the vSphere collectors during this parity mapping.
