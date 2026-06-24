# vCommunity Tier 2 SDK adapter — build 4 review

- **Adapter:** `content/sdk-adapters/vcommunity`
- **Build reviewed:** 4 (`1.0.0.4`)
- **Baseline:** build 3 (`1.0.0.3`), commit `a5ef1c2`
- **Verdict:** APPROVE
- **Findings:** 0 BLOCKING / 0 WARNING / 0 NIT
- **Reviewer:** sdk-adapter-reviewer (static, pre-install gate; never installed)

## Scope

Single functional change: align the VMware-Tools Guest OS property key
names in `VCommunityVSphereClient.vmGuestOsInfo(MoRef)` to the prod
original's six canonical `OS `-prefixed names. Plus `build_number` 3→4,
a `1.0.0.4` CHANGELOG entry, and build-generated docs stamp bumps.

## Claims check (independently re-run)

- **validate-sdk:** CONFIRMED. `javac` compiles 9 source files clean (one
  benign `-source 11` system-modules warning). "OK: ... is a valid Tier 2
  SDK adapter project."
- **build-sdk:** CONFIRMED. Built `vcfcf_sdk_vcommunity.1.0.0.4.pak` into a
  temp dir (did not touch `dist/`). Build log emits all six
  `content/files/solutionconfig/*.xml`.
- **pak-compare vs `dist/vcfcf_sdk_vcommunity.1.0.0.3.pak`:** CONFIRMED.
  "No structural divergences found. Score: 0 BLOCKING, 0 WARNING, 0 INFO."
- **6 solutionconfig XMLs present (builder fix not regressed):** CONFIRMED
  via `unzip -l` — exactly 6 `solutionconfig/*.xml` in the build-4 pak,
  matching the build-3 baseline count of 6.

## Registry check (context/defects.md)

- None affect this pak. DEF-001 (synology), DEF-002 (unifi), DEF-003
  (synology, closed) — no open or tracked defect names `vcommunity` in
  `Affects:`. Nothing to re-assert; no closure proposals owed.

## Dimension findings

### 1. Key-name parity — ground-truth verified (the point of the build)

The six new map keys in `vmGuestOsInfo` (src `VCommunityVSphereClient.java`
:587-600) are byte-identical to the prod original's canonical names,
cross-checked against BOTH:

- the property *definitions*: `references/vmbro_vcf_operations_vcommunity/
  Management Pack/app/adapter.py:211-216`
- the property *push* on the Windows-CSV path: `.../app/properties/vm/
  vmOSInformation.py:171-176`

| vim25 source | build-4 key | original | match |
|---|---|---|---|
| `prettyName` | `OS Name` | `OS Name` | ✓ |
| `version` | `OS Version` | `OS Version` | ✓ |
| `buildNumber` | `OS BuildNumber` | `OS BuildNumber` | ✓ |
| `architecture` | `OS Architecture` | `OS Architecture` | ✓ (already correct in b3) |
| `releaseId` | `OS Release ID` | `OS Release ID` | ✓ |
| `runtime.bootTime` | `OS Last Boot Up Time` | `OS Last Boot Up Time` | ✓ |

No typo, no missing/extra space, no casing drift (`OS BuildNumber` —
capital N, no space — matches; `OS Release ID` two words — matches). The
author's claimed mapping is accurate.

### 2. Unreadable-is-not-a-value / skip-if-absent — PRESERVED

(skill § *Unreadable is NOT compliant*.) `putShort` (:606-608) still guards
`null`/empty; the detailedData loop skips empty `val` at :585; the
`runtime.bootTime` push is guarded at :599. The map only contains keys the
guest actually reported, and the caller (`VmCollector.java:166-169`) only
iterates present entries. No sentinels, no placeholder, no folded score. The
key-rename did not touch any guard.

### 3. Windows guest-ops OS path — UNTOUCHED, no divergence, no double-push

`VmCollector.collectGuest` (:222-245) is unchanged and already emits the
same six `OS `-prefixed names under the same `vCommunity|Guest OS|Operating
System|` prefix. Both paths now converge on identical key names. They are
not a double-emit to the platform: both write into the *same* per-VM
`props` LinkedHashMap that is pushed once at `VmCollector.java:90`. For a
toolsOk Windows guest with guest-ops enabled, the tools path runs first
(:82) and the authoritative in-guest path second (:85-88), so `props.put`
is deterministic last-writer-wins (in-guest wins). Non-Windows / guest-ops
disabled VMs get only the tools path. No key divergence between the two
paths post-build.

### 4. No collateral changes

`git diff a5ef1c2` shows only: the 5 key strings + javadoc in
`VCommunityVSphereClient.java`, `build_number` 3→4 in `adapter.yaml`, the
`1.0.0.4` CHANGELOG entry, and two 1-line bumps in `docs/README.md` /
`docs/inventory-tree.md`. The latter two are build-generated artifacts
(each header reads "regenerated on every build / Do not edit") whose only
change is the `v1.0.0.3`→`v1.0.0.4` stamp — a mechanical byproduct of the
build, not a hand edit. No drive-by refactor.

### 9. Build hygiene

`build_number` bumped (3→4) with a matching dated CHANGELOG line. Minimal
diff. Behavior-preservation on the existing Windows path proven by reading
it (unchanged) rather than asserted.

### Other dimensions

No change to read-path exception granularity, stitching identity (MOID
trap — VM stitch is `matchVm(name, moid)` at :76, unchanged), logging,
memory/resource hygiene, API discipline, or gap honesty. Confirmed no
stale references to the old bare keys (`"Name"`/`"Version"`/etc.) survive
as pushed property keys — the residual matches in `HostCollector` and
`GuestOpsClient` are an unrelated host property and CSV-header-name lookups
(header-by-name parsing, correct per skill § canonical loader contract).
`vmGuestOsInfo` has exactly one consumer.

## If shipped as-is

Operators see VM Guest OS properties under `vCommunity|Guest OS|Operating
System|OS *` populated from VMware Tools on every tools-reporting VM
(including non-Windows), with key names byte-identical to ported vCommunity
content — so existing views/SMs referencing `OS Last Boot Up Time` etc.
find data. No regression to any other surface.

## Verdict

APPROVE — zero BLOCKING. validate-sdk clean, build reproduces, pak-compare
0/0/0 vs 1.0.0.3, all six solutionconfig XMLs intact, key-name parity exact
against ground truth, skip-if-absent and the untouched Windows path both
verified. Cleared for the install gate.
