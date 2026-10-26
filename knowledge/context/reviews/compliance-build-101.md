# Review: compliance build 101

- **Date:** 2026-10-26 (America/Chicago)
- **Reviewer:** sdk-adapter-reviewer (static, pre-install; nothing installed, no live instance touched)
- **Adapter repo:** `content/sdk-adapters/compliance`, main at `1962909` (4 ahead of origin/main, not pushed)
- **Delta reviewed:** `d5ede20..1962909` = `b382c8b` (dashboards) + `1962909` (version, CHANGELOG, test, docs stamps).
  The brief names `12f9dcd`; that commit is not on any branch. It is the pre-amend form of `1962909`
  and differs only in the two docs version stamps (`git diff 12f9dcd 1962909`: docs/README.md, docs/inventory-tree.md).
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.101.pak`, sha256 `c356ac0e2ccae6f89429b4e9563ada3b22644c0d931dbb6659c8aec4b3a2b8ff` (confirmed)
- **Reference:** `dist/vcfcf_sdk_compliance.0.0.0.100.pak`
- **Prior report:** no `compliance-build-99.md` or `compliance-build-100.md` exists under `knowledge/context/reviews/` or in git history.
  The build-100 APPROVE is recorded only in `knowledge/designs/HANDOFF-2026-10-26b.md`.

## Verdict: APPROVE (0 BLOCKING, 0 WARNING, 4 NIT)

## Independent verification

| Check | Result |
|---|---|
| `validate-sdk content/sdk-adapters/compliance` | OK (SDK compat check skipped: 9.1.1.0100 jar not in adapter_runtime/; that was already the case at build 100, and no Java changed) |
| Adapter tests (`python3 -m unittest discover -s tests`) | 55 tests OK |
| `build-sdk` reproduced into scratch | Same 225 entries. Only `overview.packed` differs from the author's pak, and only in zip timestamps; both overview.html hashes are identical |
| `pak-compare` 101 vs 100 | 0 BLOCKING / 0 WARNING / 0 INFO, "No structural divergences found" |
| Adapter classes | `vcfcf_compliance.jar` (110 classes) and `lib/vcfcf-adapter-base.jar` (53 classes): every class hash identical to 100 |
| describe.xml, conf, profiles, src | Byte-identical to 100 (`git diff d5ede20 HEAD -- src describe.xml conf profiles` is empty; describe.xml does not show up in the recursive pak diff) |
| Pak-level diff 100 to 101 | Exactly 6 entries: both `manifest.txt` copies, `conf/version.txt` (0.101), `overview.packed` (timestamp), and the two dashboards |

Field-level JSON diff of every bundled dashboard, 100 to 101 (complete output):

```
ESX_Hosts              widgets[3].config.relationshipMode.relationshipMode  [-1, 0] -> [0]
vCenter__Networking    widgets[5].config.depth                              4 -> 1
vCenter__Networking    widgets[5].config.relationshipMode.relationshipMode  [-1, 0] -> [0]
```

The other three AlertLists keep the values they had at build 100: Environment Overview depth 4 `[-1,0]`,
VMs depth 1 `[-1,0]`, World Summary depth 4 `[-1,0]`. ESX Hosts was already depth 1.

## Semantics check against `knowledge/context/investigations/2026-10-26-alertlist-depth-semantics.md`

- `relationshipMode [0]` is self only, and it works at depth 1. Measured on devel: host 37 (exactly its own
  alerts), vCenter 13. The rendered wire value is `{"relationshipMode": [0]}`, which is the array form the
  investigation replayed. Depth 1 is in the server's 1 to 10 range, so the depth-0 server error does not apply.
- The editor turns the depth field off for exactly `[0]`, so depth 1 is inert and does no harm. A user who opens
  the widget editor sees the Self box checked, which is a normal UI state.
- This matches the decision recorded in `knowledge/designs/HANDOFF-2026-10-26b.md` §Findings and decisions:
  "Scott's decision: the host and vCenter Failing Controls widgets show the object's own controls only; the VMs
  dashboard covers VM controls."
- The dashboard descriptions already read "that object's failing controls" (vCenter & Networking) and "which
  controls fail" for the selected host (ESX Hosts), so they agree with the new scope.

## Review dimensions

- **1-8 (read path, vim25, exceptions, loader, stitching, logging, memory, API):** not in scope. No Java,
  describe.xml, profile or loader change, and the classes are proven byte-identical.
- **9 Build hygiene:** `build_number` 101; one matching CHANGELOG line; the diff is minimal (two YAML keys and
  two comments, one test, two generated stamps). The test now checks `relationship_mode` both ways: `self`
  where expected, and absent everywhere else (`found != ([mode] if mode else [])`). Removing it from either
  widget, or adding it to another dashboard, fails the test.
- **10 Gap honesty:** n/a.
- **11 Docs parity:** pak docs carry no claim about the scope of the alert lists. The README and inventory tree
  stamps are regenerated to 0.0.0.101. The CHANGELOG states the behavior change and where VM controls now live.
- **12 Registry:** see below.
- **13 describe.xml import rules:** the build touches no alerts, symptoms or the generator, and describe.xml is
  byte-identical to the build-100 pak, which installed on all three devel lines.

## Findings

### NIT 1: release prerequisite not stated in buildkit terms
`CHANGELOG.md` line 5 says "Needs the factory's AlertList relationship_mode support (#274) to build". CI
(`.github/workflows/build-pak-on-tag.yml:53`, `BUILDKIT_TAG: sdk-buildkit-v1`) currently resolves to
sdk-buildkit 1.0.12, published 2026-10-19. In that buildkit, `loader.py` (at tag `sdk-buildkit-v1.0.12`,
lines 3114-3127) rejects `relationship_mode: self` with a hard error: "must be 'children', 'parents'", and it
is "only supported on MetricChart". So a `v*` tag now fails loudly at build time; it does not ship a silent
`[-1,0]`. The framework jar 1.0.19 had already made a post-1.0.12 buildkit a release prerequisite. Earlier
entries (builds 83, 93, 98) name the minimum buildkit version.
→ Say "a `v*` tag needs an sdk-buildkit cut from factory 427ea58 or later" (authority: lesson
`knowledge/lessons/sdk-paks-independent-repos.md`, the official pak is the CI build).

### NIT 2: design-intent files still carry the superseded "cover all children" correction
`knowledge/designs/dashboards/compliance-vcenter-networking.md:93-117` and
`knowledge/designs/dashboards/compliance-esxi-hosts.md:124-148` end with the 2026-10-12 correction: "the input
transformation depth needs to be updated to an appropriate depth based on the input object - to cover all the
children of that object". Build 101 reverses that on these two widgets, and the 2026-10-26 decision lives only
in the handoff. The vCenter & Networking YAML description points readers at that design file. The test pins
the new values, so the risk is reader confusion, not a silent regression.
→ The orchestrator (owner of `knowledge/designs/`) appends a 2026-10-26 amendment to both files citing the
handoff decision and the investigation. This is not an adapter-author fix.

### NIT 3: live proof of self-only covers two of the five input kinds
The investigation measured `[0]` on HostSystem and VMwareAdapter Instance only. On vCenter & Networking the
widget is also driven by Cluster, vDS and Distributed Port Group. The server semantic is generic, so the
static risk is low.
→ The planned devel visual check should select one cluster, one vDS and one port group, and confirm that each
list shows only that object's own controls and is not empty where the object has its own alerts.

### NIT 4: brief and commit identity
The brief cites `12f9dcd`, a dangling pre-amend commit. Main carries `1962909`, and the pak reproduces from
`1962909`. Cite `1962909` in the install record and the eventual tag.

## Registry check (`knowledge/context/defects.md`)

Open defects with `Affects:` naming compliance: DEF-025 and DEF-026. Other open defects (DEF-004 vcommunity-os,
DEF-019 factory:extractor) do not affect this pak.

- **DEF-025** (retired-key -1 push leaves the alert active): **open, unchanged.** The fix code from build 96
  (`RetiredKeyRepeats`) ships unchanged: classes are byte-identical to 100. Still owed: the devel evidence that
  an open alert on a retired control cancels within three cycles. Build 101 does not touch this. No closure
  proposed.
- **DEF-026** (no cycle deadline / stop flag): **open, unchanged.** The `CycleBudget` code from build 96 ships
  unchanged (classes byte-identical). Still owed: the throttled or unreachable vCenter case, where the budget
  actually cuts a cycle. No closure proposed.

No registration candidates. All findings are NIT.

## If shipped as-is
On a selected host, cluster, vDS, port group or vCenter, the Failing Controls list shows only that object's own
controls and the collection alerts. VM controls appear only on the VMs dashboard. Everything else behaves exactly
as in build 100.
