# unifi — SDK adapter review, build 11

- **Adapter:** `content/sdk-adapters/unifi/`
- **Commit reviewed:** `8ca645b` (adapter repo main, "conflicted-port property
  honesty in the vmnic→port stitch")
- **Base:** `20db25a` (build 10, APPROVEd — `context/reviews/unifi-build-10.md`;
  build 10 uninstalled, superseded by this build)
- **Design of record:** `designs/managementpacks/unifi-switchport-host-stitch-v2.md`
  (§"Build 11 amendment — conflicted-port property honesty")
- **Reviewer:** `sdk-adapter-reviewer`
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT

## Claims check (all re-run independently)

| Claim | Author | Reviewer (this run) |
|---|---|---|
| `validate-sdk` | pass | **pass** — "OK: valid Tier 2 SDK adapter project" (4 src, 1 benign `-source 11` warning) |
| build stamp | `0.0.0.11` | **`0.0.0.11`** reproduced (`vcfcf_sdk_unifi_controller.0.0.0.11.pak`, adapters.zip 104,369 bytes) |
| pak-compare vs build 10 | 0/0/0 | **0 BLOCKING / 0 WARNING / 0 INFO** — "No structural divergences found" (built `0.0.0.10` from `20db25a` in a throwaway worktree; delta is code-internal + version stamp, structure byte-identical) |
| pak-compare vs compliance ref | 0 BLOCKING | **0 BLOCKING** (2W/37I — all expected cross-adapter structural divergence, identical baseline to build 10) |
| bytecode carries the conflict logic | yes | **confirmed** — `UniFiAdapter$Snapshot.vmnicConflictedCount:I` field present; `computeVmnicStitch` disassembly shows `new java/util/LinkedHashSet` (tombstone set), `Map.remove` (earlier-claim suppression), `Map.get` (claimant lookup), and `String.equals` (same-host comparison); `INFO`-summary `getfield vmnicConflictedCount` in `emitVmnicHostStitch` |

No discrepancy between the author's result block and observed behavior.

## Registry check (`context/defects.md`)

- **DEF-002** (Affects: unifi) — **closed** at build 9 (`0.0.0.9`, devel proof
  2026-07-06; additive `parentForeign`→`addRelationships`, no VMWARE-child
  clobber). **This diff does not regress its additive-verb basis.** The write
  verb lives entirely in `emitVmnicHostStitch` (`UniFiAdapter.java:1061-1074`):
  `for (VmnicEdge e : s.vmnicEdges) { … rb.parentForeign(e.hostKey, portRk); }`
  — **byte-identical to build 10** except the summary line now appends
  `+ s.vmnicConflictedCount + " conflicted"`. No `setRelationships` / full-set
  reintroduced anywhere in the delta. The build-11 changes are confined to the
  **property** map (`vmnicLldpByPortKey`) and never touch `vmnicEdges`. Remains
  **closed**, not reopened.
- No other open registry defect names `unifi`. (DEF-004 → vcommunity-os;
  DEF-001/002/003/005/006 all closed; DEF-005/006 Affects: synology.)

## Hunt results (per the brief)

1. **Resurrection bug — tombstone persists, cannot repopulate. SAFE.**
   `computeVmnicStitch` (`:1410-1460`) checks
   `conflictedPortKeysThisCycle.contains(match.portKey)` **first**, before any
   claimant lookup; a hit `continue`s. So once host A claims → host B conflicts
   it (`conflictedPortKeysThisCycle.add`, `vmnicLldpByPortKey.remove`), any
   later claim — from A, B, or a third host C — short-circuits at the
   contains-check and the property stays removed. `claimantHostByPortKey` still
   holds the stale original claimant A, but it is **never consulted again** for
   that portKey because the conflicted-set check precedes the claimant lookup.
   Bytecode confirms the `LinkedHashSet` tombstone and the `Map.remove`. No
   resurrection path exists. ✔ (skill §*Unreadable is NOT compliant* — a
   contradictory-data property honestly suppressed, not last-write-fabricated.)

2. **False conflicts — impossible from the code. SAFE.**
   Host identity compared is `host.key.getResourceName()` (a `String`, via
   `String.equals`).
   - *Same host, two aliases folding to one portKey:* both vmnics belong to the
     same `ForeignHost` object → identical `host.key` → identical `hostName` →
     `existingHost.equals(hostName)` true → **idempotent** re-write, not a
     conflict (`:1445-1450`). ✔
   - *Same host, two vmnics on two DIFFERENT ports:* different `portKey`s →
     separate map entries → no interaction, no conflict. ✔
   A false *positive* (marking a non-conflict conflicted) requires two DIFFERENT
   `hostName` strings for the same portKey; two vmnics of one host share the
   exact `host.key`, so that cannot arise. ✔

3. **Cross-cycle leakage — resets every cycle. SAFE.**
   `claimantHostByPortKey` and `conflictedPortKeysThisCycle` are declared
   **local** to `computeVmnicStitch` (`:1376-1377`), created fresh on each call.
   `computeVmnicStitch` is invoked exactly once per `Snapshot.build`
   (`:1252`), and `Snapshot.build` constructs a **new** `Snapshot`
   (`:1204`) — so `vmnicLldpByPortKey` and the `int vmnicConflictedCount`
   default to empty/0 each build. `currentSnapshot()` (`:473-481`) rebuilds on
   TTL expiry (`MIN_REFRESH_INTERVAL_MS`), so a transient flap in one snapshot
   does not permanently suppress the property — the next refresh recomputes from
   scratch. No accumulation across cycles. ✔

4. **Edge emission truly untouched. SAFE.**
   `s.vmnicEdges.add(new VmnicEdge(host.key, match.portKey, match.portName))`
   (`:1413`) runs **unconditionally per match**, *before* any property/conflict
   branch, and the conflicted-port `continue` sits *after* it — so a conflicted
   portKey still contributes its edge(s), one per claimant. `emitVmnicHostStitch`
   (`:1061-1074`) walks `s.vmnicEdges` and calls `rb.parentForeign` identically
   to build 10; pak-compare vs 0.0.0.10 = 0/0/0 corroborates the write path is
   byte-identical. A conflicted PROPERTY portKey still emits its edges. ✔
   (skill §*ARIA_OPS stitching identity* — additive foreign edge preserved;
   `lessons/setrelationships-foreign-adapter-scoped.md`.)

5. **Summary-line arithmetic — no double-count. SAFE.**
   `vmnicConflictedCount++` fires only in the `else` (different-host) branch
   (`:1456`), which is guarded by the earlier `conflictedPortKeysThisCycle`
   contains-check `continue` — so a portKey can transition to conflicted **at
   most once**, and every subsequent claim on it short-circuits before reaching
   the counter. `conflicted` is an orthogonal dimension: a conflicted portKey's
   neighbours were already counted in `vmnicNeighbourCount` and their edges
   emitted; `conflicted` counts the *port* that lost its property, not the
   neighbours. No overlap with `ambiguous`/`unmatched` (those `continue` before
   the match is taken) or with edge count. ✔ (`rules/no-fabricated-metrics.md`.)

6. **Full-diff scan (`git diff 20db25a..8ca645b`) — nothing beyond scope.**
   Touched: `UniFiAdapter.java` (comment updates at `:737`/`:1188`; new
   `int vmnicConflictedCount` field; new summary token; the conflict logic in
   `computeVmnicStitch`), `adapter.yaml` (`build_number` 10→11 only — the
   description block is unchanged context), `CHANGELOG.md` (one honest 0.0.0.11
   entry), `REFERENCE.md` + `docs/{README,inventory-tree,overview}.md`
   (version-stamp bumps + honest prose describing the conflict behavior — no
   fabricated capability, correctly states the edge is still emitted). No
   drive-by refactor, no import churn beyond what build 10 already added
   (`LinkedHashSet`/`Set` imports pre-exist). `build_number` bumped + matching
   CHANGELOG line (author hard rules 8–9; `rules/validate-before-install.md`). ✔

## NIT (non-blocking, no action required to ship)

- **[UniFiAdapter.java `computeVmnicStitch` ~L1442]** Host identity for the
  conflict comparison is `host.key.getResourceName()` (the display name),
  not a UUID/MOID. This is safe for the *false-positive* direction (the brief's
  primary concern) — it cannot manufacture a conflict. The only theoretical
  gap is a *missed* conflict: two genuinely distinct HostSystems that happen to
  share an identical resource name would fold to `existingHost.equals(hostName)`
  and be treated as an idempotent same-host re-claim (last-write-wins), i.e.
  exactly build 10's behavior for that pathological pair — a degrade in the
  **safe** direction, no worse than the code this build improves on. VMWARE
  HostSystem resource names are FQDN-derived and unique in practice, so this is
  noted for completeness only. If ever tightened, compare the foreign
  `ResourceKey`'s uniqueness-bearing identifier set rather than the display
  name. No action required to ship.

## If shipped as-is

An operator gets build 10's working UniFi inventory and vCenter-side
vmnic→host stitch, with one honesty improvement: when two different ESXi hosts
contradictorily claim the same UniFi switch port as an LLDP neighbour in one
cycle (mis-cable / stale LLDP), the `LLDP|lldp_system_name` /
`LLDP|lldp_port_id` properties are suppressed for that port that cycle instead
of silently showing whichever host was processed last, with a `<N> conflicted`
count in the per-cycle INFO line and both claimants at debug. The
`HostSystem → UniFiSwitchPort` relationship edges are unchanged (still emitted
for every match, conflicted or not), the conflict state resets each collect,
a re-claim can't resurrect the suppressed property, and DEF-002's closed
additive-verb basis is untouched. No silent false-pass, no fabricated
property, no stitch corruption, no crash-the-cycle risk. Minimal,
correctly-scoped, conflict-safe amendment.
