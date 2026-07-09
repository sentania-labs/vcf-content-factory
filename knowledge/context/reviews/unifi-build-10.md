# unifi — SDK adapter review, build 10

- **Adapter:** `content/sdk-adapters/unifi/`
- **Commit reviewed:** `20db25a` (adapter repo main, "hardware-label alias
  in the vmnic→port own-inventory index")
- **Base:** `3bb262a` (build 9, APPROVEd — `knowledge/context/reviews/unifi-build-9.md`)
- **Design of record:** `knowledge/designs/managementpacks/unifi-switchport-host-stitch-v2.md`
  (§"Build 10 amendment")
- **Reviewer:** `sdk-adapter-reviewer`
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT

## Claims check (all re-run independently)

| Claim | Author | Reviewer (this run) |
|---|---|---|
| `validate-sdk` | pass | **pass** — "OK: valid Tier 2 SDK adapter project" (4 src, 1 benign `-source 11` warning) |
| build stamp | `0.0.0.10` | **`0.0.0.10`** reproduced |
| pak-compare vs build 9 | 0/0/0 | **0 BLOCKING / 0 WARNING / 0 INFO** — "No structural divergences found" (built `0.0.0.9` from `3bb262a` in a throwaway worktree; the delta is code-internal + version stamp, so structure is byte-identical) |
| pak-compare vs compliance ref | 0 BLOCKING | **0 BLOCKING** (2W/37I — identical to build 9's baseline; all expected cross-adapter structural divergence) |
| bytecode carries the alias change | yes | **confirmed** — `UniFiAdapter.buildOwnPortIndex` disassembly shows `new java/util/LinkedHashSet`, the `makeConcatWithConstants` for `"Port "+idx` (const pool `#1322 = String "Port "`), and the `String.equals` per-key presence check |

No discrepancy between the author's result block and observed behavior.

## Registry check (`knowledge/context/defects.md`)

- **DEF-002** (Affects: unifi) — **closed** at build 9 (`0.0.0.9`, devel
  proof 2026-07-06; all 8 hosts gained UniFiSwitchPort children via additive
  `parentForeign`→`addRelationships`, no VMWARE-child clobber). **This diff
  does not regress its basis.** The write verb lives entirely in the caller
  (`computeVmnicStitch` → `s.vmnicEdges.add(new VmnicEdge(...))` →
  `parentForeign`, `UniFiAdapter.java:1378`), which is **untouched** by build
  10 — the diff is confined to `buildOwnPortIndex` (index construction) plus
  two imports. Additive verb intact, no `setRelationships` / full-set
  reintroduced anywhere in the delta. Re-asserted: remains **closed**, not
  reopened.
- No other open registry defect names `unifi`. (DEF-004 → vcommunity-os;
  DEF-005/006 → synology; DEF-001/003 closed.)

## Hunt results (per the brief)

1. **Double-count trap — collapses correctly, both mechanisms.** Two
   independent dedup layers, each covering its own case, both required
   (skill §*Unreadable is NOT compliant* — a spurious ambiguity would
   silently drop a real edge):
   - **Exact-string coincidence (common unrenamed port).**
     `portDisplayName(port,idx)` returns `"Port "+idx` when `port.name` is
     empty (`UniFiAdapter.java:1099-1102`), so both aliases are the identical
     string `"Port "+idx2`. The `LinkedHashSet<String> aliases`
     (`:1430-1432`) collapses them to **one** element → one `joinKey` → one
     registration. No double-count. ✔
   - **Normalized-equality (strings differ pre-fold, same after `normPort`).**
     e.g. a display name that folds to the same token as the hardware label
     but is a different raw string — the `Set` keeps both, both iterate, both
     compute the **same** `joinKey`. The per-key **portKey presence check**
     (`:1436-1443`, `existing.portKey.equals(portKey)`) then refuses the
     second add. Result: exactly one candidate in that list. This is the case
     the `Set` alone cannot catch, and the presence check is what catches it.
     ✔

2. **Real collision — a renamed "Port 3" on a switch that has a real Port 3.**
   The renamed port (say `idx=7`, `port.name="Port 3"`) registers under
   `normPort("Port 3")` (display alias) **and** `normPort("Port 7")`
   (hardware alias); the real port (`idx=3`, unrenamed) registers under
   `normPort("Port 3")`. Both land in joint-key list `"<switch> port 3"`
   with **different** portKeys (`MAC_3`, `MAC_7`) — the presence check does
   *not* dedup them (correct: they are genuinely distinct candidates). The
   list size is 2, so the caller (`computeVmnicStitch:1362`,
   `candidates.size()>1`) increments `vmnicAmbiguousCount`, logs debug, and
   emits **no edge** — no fabrication (skill §*Exception & failure
   granularity*; design §3 "do **not** emit to all candidates"). Verified
   this is also **not a regression**: build 9 already produced the same
   ambiguity for that pair via the display-name index (both ports displayed
   "Port 3"), so build 10 preserves the honest skip, it does not newly break
   it. ✔

3. **Cross-switch scoping — no alias leakage.** `joinKey =
   normSwitch(devName) + " " + normPort(alias)` (`:1434`), with `devName`
   captured inside the per-device loop (`:1419`). The switch identity is a
   prefix of every joint key, so `"Port 15"` on switch A
   (`"usw-a port 15"`) and switch B (`"usw-b port 15"`) are distinct keys.
   Aliases cannot bleed across switches. ✔

4. **No behavior drift elsewhere.** `git diff 3bb262a..20db25a` touches only:
   `UniFiAdapter.java` (`buildOwnPortIndex` body + `LinkedHashSet`/`Set`
   imports), `adapter.yaml` (`build_number` 9→10), `CHANGELOG.md` (one honest
   entry), and generated `docs/` (version-stamp bumps + an `overview.md`
   prose paragraph that accurately describes the two-alias join — no
   fabricated capability). The matching discipline
   (`computeVmnicStitch:1354-1385`: null/empty→unmatched, `>1`→ambiguous,
   else emit), the additive `parentForeign` edge semantics, the crash-safety
   try/catch (`:1387`), the `LLDP|*`/`vmnicLldpByPortKey` population
   (`:1383`), and the INFO summary counters (`:1072`) are **byte-for-byte
   unchanged** from build 9. pak-compare vs 0.0.0.9 = 0/0/0 corroborates:
   describe.xml, resources.properties, template.json all identical. ✔

5. **Full-diff scan for out-of-scope change.** None found. Every hunk maps to
   the stated build-10 amendment or its mechanical version-stamp fallout.
   The `overview.md` "renamed ports" paragraph is honest (replaces build 9's
   "unverified" caveat with the verified two-alias behavior); no gap hidden,
   no coverage inflated (`knowledge/rules/no-fabricated-metrics.md`). ✔

## NIT (non-blocking, no action required to ship)

- **[UniFiAdapter `buildOwnPortIndex`/`computeVmnicStitch` ~L1383]** The
  build-9 NIT stands, marginally more reachable: if two *different* hosts'
  vmnics both resolve to the same joint `(switch,port)` key, the
  `vmnicLldpByPortKey` property is last-write-wins. The two-alias index
  slightly widens key coverage, so a pathological rename could in principle
  route a second host onto a key it wouldn't have hit in build 9. Still
  physically impossible input (one port ↔ one host) and it degrades safely
  (both are real matches on advertised data; no fabricated edge — the edge
  set is a `List<VmnicEdge>` and any duplicate `parentForeign` to the same
  child is idempotent in `RelationshipBuilder` per design §3). Noted for
  completeness only.

## If shipped as-is

An operator gets build 9's working UniFi inventory and vCenter-side
vmnic→host stitch, plus the one previously-missed edge for renamed ports
whose switch advertises the hardware LLDP label (`usw-lite-16-nuc` port 15
"Router" → matches "Port 15") — 16/16 devel edges instead of 15/16. No new
silent-false-pass, no fabricated edge (a genuine alias collision degrades to
the existing ambiguous-skip), no stitch-corruption, no crash-the-cycle risk,
and DEF-002's closed additive-verb basis is untouched. This is a minimal,
correctly-scoped, dedup-safe amendment.
