# unifi build 8 — SDK adapter review

- **Adapter:** `content/sdk-adapters/unifi`
- **Build reviewed:** 8 (commit `a71b280`, working tree clean)
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-07-02
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT

## Scope

Cross-MP relationship fix build. Two adapter-source changes plus
version/doc/CHANGELOG housekeeping:

- `UniFiStitcher.java#SuiteApiHostBridge.listResources()` — read the real
  per-identifier `isPartOfUniqueness` flag from the Suite API response
  instead of hardcoding `"true"`.
- `UniFiAdapter.java#emitLldpHostCrossLink` — try every `lldp_table` entry
  on a switch port (first REAL match wins) instead of `lldp_table.get(0)`.

Diff touched only: `UniFiStitcher.java`, `UniFiAdapter.java`, `adapter.yaml`
(`build_number 5→8`, `version 1.0.0→0.0.0`), `CHANGELOG.md`, `docs/README.md`,
`docs/inventory-tree.md`. Minimal, no drive-by refactor.

## Independent claims verification

All author claims re-run, not repeated:

| Claim | Result |
|---|---|
| `validate-sdk` pass | **Confirmed** — "OK: valid Tier 2 SDK adapter project" (4 files compiled, 1 benign `-source 11` warning) |
| build reproduces, stamped `0.0.0.8` | **Confirmed** — `vcfcf_sdk_unifi_controller.0.0.0.8.pak` built clean |
| pak-compare vs `0.0.0.7` = 0/0/0 | **Confirmed** — "No structural divergences found. Score: 0 BLOCKING, 0 WARNING, 0 INFO" |
| pak-compare vs compliance reference = 0 BLOCKING | **Confirmed** — 0 BLOCKING / 2 WARNING / 37 INFO. Both WARNINGs (`instance identifier count 3 vs 4`, `TraversalSpecKind count 1 vs 0`) and all INFOs are inherent cross-adapter shape differences vs the loader-shaped compliance reference — not regressions. Gate is zero BLOCKING; met. |
| bytecode carries the fix | **Confirmed** — `javap` of `UniFiStitcher$SuiteApiHostBridge.class` in the built `unifi_controller.jar` shows the `identifierType` / `isPartOfUniqueness` / `SimpleJson.asBoolean:()Z` read. Not a stale compile. |
| framework containment (AmbientCredential, additive RelationshipBuilder, applyBcMirrorTransport) | **Confirmed** — bundled `lib/vcfcf-adapter-base.jar` carries `AmbientCredential`, `ForeignResourceResolver`, `RelationshipBuilder`, and `VcfCfAdapter.applyBcMirrorTransport(HttpsURLConnection)` + `openPlatformConnection`. |

## Correctness walk

**1. Uniqueness-flag propagation (the fix) — SOUND.**
`lessons/cross-mp-foreign-key-uniqueness-flags.md`. The read path
`id.get("identifierType").get("isPartOfUniqueness").asBoolean()` matches the
rule's mandated Suite API shape
(`resourceIdentifiers[].identifierType.isPartOfUniqueness`). Verified against
`SimpleJson` source: `get()` on a missing key returns a `SimpleJson(null)`
(never NPEs), and no-arg `asBoolean()` returns `false` on a null/absent value
— so the author's "defaults to `false` on absent/null, never over-mark" claim
is exact. The flag flows correctly through: `String[]{name,value,"true"/"false"}`
→ `ForeignResourceResolver.fetchAndCache` `Boolean.parseBoolean(id[2])` →
`ResourceIdentifierConfig(name, value, isUnique)`. Byte-identical to
`SynologyStitcher.SuiteApiDatastoreBridge` (synology `1.0.0.19`, the
certified-working reference whose edges are live-proven persisting per DEF-003
/ DEF-006 closing evidence). Default-`false` is the correct conservative choice:
under-marking at worst drops an edge (degrade); only over-marking silently
corrupts binding, which this avoids.

**2. Multi-candidate LLDP loop — SOUND.** Bounded iteration over
`lldpTable.asList()`, `break` on first non-null match → **at most one edge per
port** even when two neighbours both resolve (no duplicate edges).
`matchHostByName` guards empty/null `sysName` (returns null) so a bad entry
just advances the loop. One-neighbour common case is behaviour-identical to the
old `get(0)` path. Empty/absent `lldp_table` still guarded upstream
(`isNull() || size()==0` → continue).

**3. Crash-the-cycle — SAFE.** Whole `emitLldpHostCrossLink` body wrapped in
try/catch → `logWarn`, internal topology returned regardless. Suite API down is
swallowed *inside* `ForeignResourceResolver.fetchAndCache` (returns empty index)
→ null host → skip, never a throw up the collect path. `stitcher == null` →
early return. No path where a stitch fault costs the cycle its own inventory.

**4. DEF-002 clobber concern — structurally addressed.** Verified in framework
source: `rb.parentForeign(host, portKey)` sets `foreignParent=true`;
`RelationshipBuilder.doBuild` routes foreign parents to additive
`rels.addRelationships` (line 316), full-set `rels.setRelationships` is used
**only** for own-adapter parents (line 319). The DEF-002 full-set-onto-foreign
clobber idiom is not present in this build.

**5. Logging / gaps — CLEAN.** One summary line per cycle
(`"...N port→host edges"`), per-no-match at debug (no loop spam), no secrets. No
fabricated edges — no match yields no edge, never a phantom HostSystem
(`rules/no-fabricated-metrics.md` respected).

## Registry check (`context/defects.md`)

- **DEF-002** (`unifi`, open, blocking) — **still open; re-asserted.** This
  build addresses the *static-review basis* (the full-set-`setRelationships`-
  onto-foreign-HostSystem clobber concern from WARNING-1): the write verb is now
  additive `parentForeign`→`addRelationships`, verified in framework bytecode.
  **But the defect's stated closing criterion is a LIVE proof** — "a unifi devel
  collect against an LLDP-reachable ESXi host shows the matched HostSystem
  retains its pre-existing VMWARE children AND gains the UniFiSwitchPort child."
  That live collect has **not** been run (golden baseline: no configured devel
  instance). **No closure proposed.** The CHANGELOG (`0.0.0.8` entry) states this
  honestly ("Closes the unifi half of DEF-002's static-review basis … DEF-002
  itself remains open pending its stated closing criterion") — **no overclaim.**
  Consequence for the orchestrator: DEF-002 is open-blocking against `unifi`, so
  `defect-gate` will (correctly) refuse any `v*` release of this pak until the
  live proof lands (RULE-012). This is a dev-preview `0.0.0.8` build with no tag,
  so the gate is not tripped here.
- No other open defect names `unifi`. (DEF-005/DEF-006 `Affects: synology`,
  both closed; their BC-mirror transport rides into this pak via the shared
  framework jar — inherited, not a unifi defect.)

## Findings

### NIT

- **[`src/com/vcfcf/adapters/unifi/UniFiAdapter.java:1028`]** — doc drift. The
  `emitLldpHostCrossLink` method javadoc still reads "for each switch port whose
  **first** LLDP neighbour … names a real VMWARE HostSystem" after this build
  changed the logic to try *every* neighbour and take the first REAL match.
  Fix: reword to "whose LLDP neighbour set contains a real VMWARE HostSystem"
  (or similar). Cosmetic only — behaviour and the inline comment at 1051–1059
  are correct.

## If shipped as-is

An operator gets a correctly-behaving dev-preview: the LLDP→HostSystem cross-MP
edge is now built with a properly-marked foreign key (so it can actually bind,
unlike the pre-fix silent-drop) and matched across all LLDP neighbours on a
port. The one remaining risk — that full-set semantics could clobber the foreign
host's VMWARE children — is structurally closed (additive verb), but its live
confirmation (DEF-002) is still owed; this pak must not be `v*`-released until
that devel collect proves the matched HostSystem keeps its VMWARE children and
gains the UniFiSwitchPort child.

## Report

`context/reviews/unifi-build-8.md`
