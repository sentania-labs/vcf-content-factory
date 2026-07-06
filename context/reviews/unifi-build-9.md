# unifi — SDK adapter review, build 9

- **Adapter:** `content/sdk-adapters/unifi/`
- **Commit reviewed:** `3bb262a` (adapter repo main, "replace dead
  controller-side LLDP cross-link with vCenter-side vmnic→port join")
- **Base:** `a71b280` (build 8)
- **Design of record:** `designs/managementpacks/unifi-switchport-host-stitch-v2.md`
- **Reviewer:** `sdk-adapter-reviewer`
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 3 NIT

## Claims check (all re-run independently)

| Claim | Author | Reviewer (this run) |
|---|---|---|
| `validate-sdk` | pass | **pass** — "OK: valid Tier 2 SDK adapter project" (4 src, 1 benign `-source 11` warning) |
| build stamp | `0.0.0.9` | **`0.0.0.9`** reproduced |
| pak-compare vs build 8 | 0B / 1W / 1I | **0B / 1W / 1I** exact — W1 = `UniFiSwitchPort` group attr 22→21 (the `lldp_chassis_id` removal), I1 = description reword |
| pak-compare vs compliance ref | 0 BLOCKING | **0 BLOCKING** (2W/37I, all expected cross-adapter structural divergence) |
| bytecode carries new stitch | yes | **confirmed** — `listHostsWithVmnicLldp`, `fetchVmnicNeighbours`, `emitVmnicHostStitch`, `computeVmnicStitch`, `buildOwnPortIndex`, `normPort`, `normSwitch` present; `matchHostByName`/`ForeignResourceResolver` absent; `|discoveryProtocol|lldp|` anchor in const pool |

No discrepancy between author's result block and observed behavior.

## Registry check (`context/defects.md`)

- **DEF-002** (open, blocking, Affects: unifi) — **still present, unchanged.**
  The edge is still `rb.parentForeign(host, portKey)` onto a foreign VMWARE
  `HostSystem` (`UniFiAdapter.emitVmnicHostStitch`, ~L1057;
  `computeVmnicStitch` builds `VmnicEdge(host.key, …)`). `foreignParent=true`
  routes to additive `addRelationships` (framework, unchanged this build) —
  the additive contract the closing criterion depends on is intact and
  **not regressed**. The defect's closing criterion is explicitly a **live
  devel collect** showing the matched HostSystem retains its VMWARE children
  AND gains the UniFiSwitchPort child — that cannot be produced by a static
  review and is not owed here. Note for the orchestrator: build ≤8 matched
  **zero** hosts on 10.2.105 (dead controller `lldp_table`), so DEF-002 was
  never once *exercised*; build 9 is the first path that should actually
  emit these foreign edges on devel, i.e. it is the path to DEF-002's live
  closing evidence. Re-asserted, remains **open**.
- No other open registry defect names `unifi`. (DEF-005/006 affect
  synology; the framework transport they fixed is the same BC-mirror
  plumbing this adapter rides, but they are not scoped to this pak.)

## Hunt results (per the brief)

1. **Fabrication — ambiguous/zero matches skip.** Correct.
   `computeVmnicStitch` (UniFiAdapter ~L1330): `candidates==null||isEmpty`
   → `vmnicUnmatchedCount++`, debug, no edge; `candidates.size()>1` →
   `vmnicAmbiguousCount++`, debug, no edge; exactly one → emit. No
   emit-to-all-candidates path. Both `systemName` and `portName` required:
   `fetchVmnicNeighbours` only adds a `VmnicNeighbour` when the port name
   for that vmnic is present and non-empty (systemName is the map key, so
   also required). No edge without both. ✔

2. **Normalization traps.** `normPort` = lowercase → `_`→space → collapse
   whitespace → trim. `"Port 1"`→`"port 1"`, `"Port 11"`→`"port 11"` stay
   **distinct** (no digit merge). `"SFP_ 1"`→`"sfp 1"` == `"SFP 1"`→`"sfp 1"`
   folds correctly. `normSwitch` = same minus the underscore rule. Joint
   `(switch,port)` key means a duplicate switch `dev.name` only skips when
   the *same port name* also exists on both — the honest tie. ✔

3. **DEF-002 additive semantics.** Verb unchanged (`parentForeign` →
   additive `addRelationships`); no `setRelationships` / full-set onto the
   foreign HostSystem anywhere in the delta. ✔ (live proof still owed —
   see registry.)

4. **Honest uniqueness flags.** `UniFiStitcher.listHostsWithVmnicLldp`
   reads `id.get("identifierType").get("isPartOfUniqueness").asBoolean()`
   per identifier and passes it into `new ResourceIdentifierConfig(idName,
   idVal, isUnique)` — never hardcoded true. `SimpleJson.asBoolean()`
   returns **false** on absent/null (verified in source: `SimpleJson.java`
   L86–91, and `get()` is null-safe L26–33), so absent → false. Matches
   `lessons/cross-mp-foreign-key-uniqueness-flags.md`. ✔

5. **Crash-the-cycle.** `computeVmnicStitch` wraps the entire fetch+match
   body in try/catch → `adapter.logWarn`, never rethrows; it is invoked
   inside `Snapshot.build()` *after* the internal UniFi topology is already
   assembled (sites/devices populated at L1198–1233, stitch at L1245), and
   its failure cannot fail the build. Call A (`listHostsWithVmnicLldp`,
   `throws Exception`) is caught there. Per-host Call B
   (`fetchVmnicNeighbours`) has its own try/catch → WARN, returns empty for
   that host, does **not** abort enumeration of the rest — degrade, not
   abort. `emitVmnicHostStitch` is independently try/caught and runs before
   `rb.build()`, so a late fault still returns internal relationships.
   `stitcher==null` (remote collector / no ambient creds) → early return in
   both `emitVmnicHostStitch` and `computeVmnicStitch`. ✔

6. **LLDP|* repurpose honesty.** `collectSwitchPort` (~L738) emits
   `LLDP|lldp_system_name` / `lldp_port_id` **only** when
   `s.vmnicLldpByPortKey.get(portKey) != null` (matched ports only) — no
   sentinel, no stale value on unmatched ports. `lldp_chassis_id` removed
   consistently from **code**, **describe.xml** (L213–217 group, now 2
   attrs), and **resources.properties** (key 137 gone) — no
   declared-but-never-populated attribute remains; the two survivors are
   populated from the vCenter join. On a deployment where the stitch is
   unavailable the group is simply empty (honest "no data"), an improvement
   over build ≤8 where it was empty everywhere. ✔

7. **Dead code gone.** `matchHostByName`, `ForeignResourceResolver`,
   `invalidateCache`, `SuiteApiHostBridge`, the controller `lldp_table`
   walk, and `lldp_chassis_id` reads exist **only in javadoc/comment
   prose** now (grep + `javap` confirm none in bytecode). ✔

8. **Cost / regression.** Call B is a per-host `GET
   /api/resources/{id}/properties`; the loop is bounded by
   `resourceList.size()` (single `pageSize=10000` page). H+1 GETs/cycle, all
   inside the `MIN_REFRESH_INTERVAL_MS`-throttled `Snapshot.build`.
   `buildOwnPortIndex` is a pure in-memory walk of the already-fetched
   snapshot — no new UniFi API calls. The internal topology log line
   (`World>Site>{…} tree`) is byte-identical to build 8. ✔

## NITs (non-blocking, no action required to ship)

- **[UniFiAdapter `computeVmnicStitch` ~L1370]** Two *different* hosts whose
  vmnics both normalize to the same joint `(switch,port)` key would each
  emit a `parentForeign` edge to the same port and the `vmnicLldpByPortKey`
  property would be last-write-wins. This is physically impossible input
  (one port ↔ one host) and degrades safely (no fabrication — both are
  "real" matches on identical advertised data), so it is noted only for
  completeness, not a finding.
- **[UniFiStitcher `listHostsWithVmnicLldp` ~L120]** `pageSize=10000` with no
  pagination; a vCenter with >10k HostSystems would silently truncate.
  Unchanged from build 8, unrealistic at target scale; raise as a TOOLSET
  GAP only if a large-fleet target appears (design §1 already anticipates
  this).
- **[summary counter]** `vmnicHostCount` counts identifier-less/no-vmnic
  hosts too (added with `emptyList`); purely cosmetic in the INFO summary.

## If shipped as-is

An operator gets the same working UniFi inventory as build 8, plus — where
a vCenter is reachable over the ambient Suite API — accurate per-vmnic
`HostSystem → UniFiSwitchPort` foreign edges and repurposed `LLDP|*`
properties sourced from vCenter (the controller-side read that produced zero
matches is gone). No new silent-false-pass, stitch-corruption, or
crash-the-cycle risk. The one thing static review cannot certify —
that the additive foreign edge lands on the VMWARE HostSystem **without
clobbering its VMWARE children** — is DEF-002's live-collect closing
criterion, which build 9 finally makes exercisable on devel.
