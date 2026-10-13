# Review: compliance adapter build 91

- **Adapter:** `content/sdk-adapters/compliance`, branch `feat/build-90-overrides-file`
- **Reviewed:** HEAD `18d6f0a` against the third-pass-approved `eae8658` (2026-10-13, 11:27 AM local)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.91.pak`, sha256 `cdad54e35494a27d38b40d52c2acda8045af071cfc24337e3885bebeecae36e4` (confirmed)
- **Verdict:** APPROVE, 0 BLOCKING / 0 WARNING / 1 NIT

Build 91 is the build 90 pak with one describe.xml change: the overrides
alert's only symptom set now sits bare under `<State>`. Nothing else in the
shipped adapter changed. The jar is entry-for-entry identical to build 90,
and every remaining `<SymptomSets>` container has two or three children.

## Scope check

`git diff --stat eae8658..18d6f0a`: 11 files, +91 / -12. All of it is what the brief states:

| Commit | Files | Content |
|---|---|---|
| `e720dc7` | README.md, docs/overrides.md | The build 90 N9 sentences (intentional dvfilter VMs now fail `vm.dvfilter`; Skip example). Doc only. |
| `18d6f0a` | scripts/generate_compliance_alerts.py | Overrides alert emits a bare `<SymptomSet>`; `<SymptomSets operator="or">` wrapper removed; comment states why |
| | describe.xml | The regenerated 4-line change at lines 4157 to 4160, nothing else |
| | tests/test_describe_symptom_sets.py | New: fails on any `<SymptomSets>` with fewer than 2 set children, plus a guard-the-guard case |
| | tests/test_generate_compliance_alerts.py | Asserts no `State/SymptomSets` on the overrides alert; refs read from `State/SymptomSet` |
| | ci/run_java_tests.sh | Runs the new test |
| | adapter.yaml | build_number 90 to 91 |
| | CHANGELOG.md | One build 91 line; its claims (144 alerts, 7 remaining containers with 2 or 3 children) check out below |
| | docs/README.md, docs/inventory-tree.md | Generated version string 0.0.0.90 to 0.0.0.91 |

`git diff eae8658..18d6f0a -- src` is empty. The working tree was clean before and after my build.

## Independent verification

| Check | Result |
|---|---|
| Pak describe.xml vs HEAD describe.xml | byte-identical (`cmp`) |
| Build 90 pak describe.xml vs `git show eae8658:describe.xml` | byte-identical |
| Pak describe 90 vs 91 | only the overrides alert's container removed (lines 4157 to 4160) |
| Overrides alert, 90 vs 91 (parsed) | same id, nameKey 2041, VMWARE / `VMwareAdapter Instance`, type 15 subType 21, wait 1 cancel 1, State severity Automatic, Impact badge risk, SymptomSet ref `vcfcf_compliance_overrides_vcenter_not_loaded` (operator and, aggregation any, applyOn self, negate false), Recommendation `vcfcf_compliance_overrides_check` priority 1. Symptom definition (nameKey 2040, Warning, `VCF-CF Compliance\|Summary\|overrides_not_loaded = 1`) unchanged. |
| `<SymptomSets>` count, my own parse of the built pak | 91: 7 containers, all 2 or 3 children (score_degraded 2; collection host 2, vm 2, vcenter 3, cluster 2, vds 2, portgroup 2). 90: 8, the eighth is `vcfcf_compliance_overrides_vcenter` with 1. 89: same 7 as 91. Raw text count agrees (7 open, 7 close tags). |
| Precedent for the bare form | build 89 (installed on devel) has 136 alerts with a bare SymptomSet under State, 15 of them on `VMwareAdapter Instance`; build 91 has 137 and 16 |
| `test_describe_symptom_sets.py` on the build 90 describe (scratch copy) | FAILS: `[('vcfcf_compliance_overrides_vcenter', 1)]` |
| Same test on the build 91 describe | 2 tests OK |
| `generate_compliance_alerts.py --check` | up to date (136 control alerts, 6 collection, 1 overrides) |
| Jar, 90 vs 91 | file hash differs (zip timestamps); all 77 entries byte-identical (`diff -r` of the extracted trees, CRC list identical). views.zip contents identical. Only manifest.txt and version.txt carry 0.0.0.91. |
| `validate-sdk` | OK, 21 sources compile |
| `build-sdk` from HEAD into the scratchpad | builds 0.0.0.91; adapters.zip, jar entries, describe and content identical to the author's pak; `overview.packed` differs only in archive timestamps (extracted contents identical) |
| `pak-compare` 91 vs 89 | gate PASS, 0 BLOCKING / 2 WARNING (identifier count 6 vs 5; ComplianceWorld group attributes 6 vs 1) / 1 INFO (overrides template). Same as build 90 vs 89. |
| `pak-compare` 91 vs 90 | 0 / 0 / 0. pak-compare does not inspect alert structure at all, which is why it passed build 90. |
| `ci/run_java_tests.sh` | 13 Java suites pass; generator 17 OK; new symptom-set test 2 OK; AlertList 6, widget types 2, template 5 OK |
| `pytest tests/` | 32 passed (30 at build 90 plus the 2 new), 11 subtests |

## Review dimensions

No Java changed, so dimensions 1 to 8 (read paths, vim25, exceptions,
loader, stitching, logging, memory, API discipline) are unchanged from the
build 90 third pass, and the identical jar confirms it. Dimension 9: build
bumped, CHANGELOG line present, minimal diff. Dimension 10: no gap
changes. Dimension 11: the alert's docs (name, wait and cancel cycles,
trigger) are unchanged and still match. The N9 dvfilter sentences in
README and overrides.md match the build 90 W3 behavior.

## Findings

**NIT 1** [tests/test_describe_symptom_sets.py:24 to 32] Only
`<SymptomSets>` nested inside an `<AlertDefinition>` is scanned. Ops only
accepts the container there, so a stray one elsewhere would fail some
other way, but the gate could be one line simpler and total by iterating
`root.iter(NS + "SymptomSets")` directly. No ship impact.

## Registry check (knowledge/context/defects.md)

- **DEF-022** (absent advanced setting skipped): code fix unchanged in
  build 91 (no `src` diff; jar identical to the build 90 jar the third pass
  approved). The close condition's code and test parts are met. The
  "devel evidence from the build 90 install" in its Progress note no longer
  exists, because build 90 never installed. The devel evidence must now
  come from build 91. Still open.
- **DEF-023** (single-page resource list): unchanged; the fix has been in
  since build 88. Still owed: devel proof of the paging or of the vCenter
  collection alert path. Still open.
- **DEF-024** (`vm.dvfilter` literal lookup): same as DEF-022. Matcher
  unchanged in an identical jar, close condition met in code, devel
  evidence now owed from build 91. Still open.

## Install expectation

The rejection that failed build 90 cannot recur from this pak: no
undersized container remains, and the bare form is already accepted on
devel in build 89. Verify the install by the installed solution version
reading 0.0.0.91, not by the CLI's OK line (factory issue #202).

## Did I miss this in the three build 90 passes?

Yes. All three passes approved a describe.xml with a one-child
`<SymptomSets>`, even though the rule was in the lessons index the whole
time ("SymptomSets needs ≥2 children", `knowledge/lessons/pak-content-bundling.md`
point 4). Three things caused the miss. (1) My review dimensions are all
about Java read-path correctness. Nothing in the reviewer prompt or the
vcfops-sdk-adapter skill names describe.xml install-time constraints, so I
did not check the generated alert XML against Ops' import rules. (2) I
treated the generator as the authority. I accepted "additive" plus a clean
`--check` as evidence, but `--check` only proves the describe matches its
generator, not that Ops will accept it. The generator's own test asserted
the wrong shape, so the green tests confirmed the bug. (3) The rule lives
in a lesson titled for content-directory bundling, and I did not connect a
"bundling" lesson to an alert-definition change. validate-sdk and
pak-compare were both blind to it (91 vs 90 compares 0 / 0 / 0), and their
passes gave false assurance. The lesson should say: when a build touches
describe.xml alerts or symptoms, count every `<SymptomSets>` child against
the two-child rule by parsing the built pak, and do not count generator
self-consistency as validity. The orchestrator should also consider adding
"describe.xml import constraints" as a reviewer dimension and putting the
rule in the skill, since I cannot edit `.claude/`.
