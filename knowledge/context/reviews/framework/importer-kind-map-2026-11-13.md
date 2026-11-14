# Framework review: import-local `--map-kind` / `--describe` (feat/importer-kind-map)

- Branch `feat/importer-kind-map`, commit `9372360b` on `532dee29`.
- Area: `src/vcfcf_core/importer/` (`kinds.py` new, `accounting.py`,
  `convert.py`), `src/vcfcf_extractor/importer.py`, how-to
  `knowledge/context/authoring/importer_offline_conversion.md`.
- Verdict: **CHANGES REQUESTED**: 3 BLOCKING, 4 WARNING, 3 NIT.

## Checks re-run

| Check | Result |
|---|---|
| Validate chain (7 packages, worktree) | all exit 0 |
| `scripts/path_reference_audit.sh` | clear (2 standing RULE-015 exceptions) |
| pytest, full suite, `-m "" --override-ini addopts=` (serial; xdist not installed) | branch 4814 passed / 8 failed / 12 skipped |
| pytest delta vs base | +34 `test_import_local_kind_map.py` tests and +2 `test_core_contract` params for `kinds.py`, all passing. All 167 base `test_import_local*` tests pass on the branch. Nothing regressed. The 8 branch failures (`test_common_doctor` x5, `test_gap_b_f_d` JMESPath x2, `test_deeply_nested_json_does_not_escape_as_recursionerror`) fail the same way on base. They come from the environment (venv detection, Python 3.14), not this diff. Base ran from a `git archive` and has 12 more failures because it has no `.git` and no gitignored clones; those 12 pass in the worktree. |
| Render/stale-zip paths | not touched (importer only), so no rebuild and no template-version bump needed |

### No-new-options byte-identity claim (base vs branch code, same inputs)

Inputs: the vCommunity `...-releasedimage.pak` (read-only, converted to
scratch only), the factory corpus rendered as in
`test_factory_corpus_renders_convert_back_identically`, and the synthetic
`test_import_local` source. Option sets: pak/keep/unprefixed (plus
`--target-min 9.1.1`), third-party/keep, content/mint/factory-prefixed,
third-party/mint/unprefixed.

- Written trees: identical in every run.
- stdout: one added `verbatim source text:` line in every run, nothing else.
  The exception is corpus + `--ids mint`, where the verify block changes.
- `report.json` minus `objects[].verbatim_text`: identical, except
  **corpus + `--ids mint`**. There, `verify` goes from 9 alerts DIFFERS
  (`SymptomSet[]@ref` derived id vs minted id) to all identical. This is the
  verification half of the derived-id fix. The how-to documents it, but the
  claim "report byte-identical" does not hold for that input (NIT 1).

### Independent oracle for the self-cancel question

Verification compares the render with the **re-pointed** source. A place
the rewriter misses is unchanged on both sides and cancels out. Only
`account_kinds` guards against that. To check it with independent logic I
diffed the YAML of a mapped run against the YAML of an unmapped run of the
same input (`VMWARE * -> NEWAK *`, `VMWARE VirtualMachine -> NEWAK NewVM`,
`VMWARE VirtualMachine -> VMWARE NewVM`, on the pak and the corpus). Every
differing leaf had to be an old-to-new kind swap, and every leaf still
holding the old kind had to be text. Every differing leaf was a clean swap.
The survivors were descriptions and `VMWARE_INFRA_HEALTH` (correct), plus
three real misses: B1, W2 and W2b. A 27-case formula battery on
`remap_formula` / `formula_kind_problem` passed: nesting, where clauses,
`adaptertype=` inside quotes, escaped quotes, whitespace and case, `*`,
depth, `this`, sm refs, `resourcename`, `identifiers`, precedence,
unclosed entries. Chains, swaps and duplicate rows are refused. A derived-id
collision with an existing object is caught.

## BLOCKING

**B1. A derived recommendation key is re-pointed, but its YAML keeps
`adapter_kind: <old>`, and the run prints a false note.**
`convert.py:609-635`. `rec_kind` is keyed by the alerts' recommendation
refs. After `apply_kind_map` those refs carry the **re-pointed** key, but
the lookup at :630 uses the recommendation's **source** id, so it misses.
The code then falls back to `VMWARE` and notes "adapter_kind is not in the
source and no alert in the set references this recommendation", which is
false.
- Input: factory corpus + `VMWARE\t*\tNEWAK\t*`. Four files
  `recommendations/recommendation-df-newak-*.yaml` have
  `id: Recommendation-df-NEWAK-...` with `adapter_kind: VMWARE`, and each
  is reported "identical apart from re-pointed kinds".
- Synthetic repro: an `ProbeOld` recommendation without an id, referenced
  by `a_d`, under the star map. The output has
  `adapter_kind: VMWARE` (not even the old kind).
- Authority: RULE-002 (no fabrication: the note is untrue). The YAML also
  contradicts its own key (`alerts/loader.py:191` derives
  `Recommendation-df-<adapter_kind>-<slug>`), so removing the explicit id
  later re-derives a key on the wrong kind.
- Fix: key `rec_kind` by source id (map the ref back through
  `kind_unmap`, or build it before `apply_kind_map`). For a re-pointed key,
  take the kind from the re-pointed alert. Add a test with a derived-key
  recommendation (the suite's only recommendation is `probeKindRec`, a
  non-derived key, which is why this passed).

**B2. A dashboard AlertList is re-pointed to a derived alert id that
nothing ships, and the dashboard reports "identical apart from re-pointed
kinds".**
`kinds.py:444-493` builds `ids.table` from every kept-id object before any
object is remapped. `convert.py:574-599` then fails objects whose remap has
problems, but their table entries stay. `kinds.py:697` rewrites the
AlertList through that table.
- Input: the synthetic kind-map source with the
  `SymptomDefinition-ProbeOld-Probe_Derived_Symptom` definition removed
  from `alerts.xml`, star map, `--allow-partial`. `Probe Derived Alert`
  fails ("references symptom ... not in the input"). The dashboard still
  converts with
  `alert_definitions: [AlertDefinition-probe_new-Probe_Derived_Alert]`.
  That id exists neither in the source nor in the output, and the
  dashboard's status is "identical apart from re-pointed kinds". Without
  the map, the AlertList keeps the source id, which at least exists in the
  source pack.
- Authority: RULE-002 (a fabricated reference reported as verified). This
  is the self-cancel case: the expectation carries the same fabricated id.
- Fix: two passes. Remap, collect the failures, then drop the failed
  objects' entries from `ids.table` and re-run the dependants. Or have
  `_ref` / `target()` treat a table hit whose owner failed as a failed
  target, which cascades. Add the test above.

**B3. The `--drop` / `--id-map` wire-id fix crosses types: a symptom's
wire id also drops or maps the same-slug alert.**
`convert.py:121-130` (`norm_key`) strips **either** prefix and compares the
result with `norm_id(o.type, o.id)` for every type (:546, :732). The type
the operator wrote is thrown away. Derived ids differ only by prefix when a
symptom and an alert share a name, which is a common authoring pattern.
- Input: the synthetic kind-map source with `a_d` renamed to
  `Probe Derived Symptom`.
  - `--drop` row `SymptomDefinition-ProbeOld-Probe_Derived_Symptom`
    drops both the symptom **and**
    `AlertDefinition-ProbeOld-Probe_Derived_Symptom` (exit 0).
  - `--id-map` row
    `SymptomDefinition-ProbeOld-Probe_Derived_Symptom\tSymptomDefinition-1111...`
    also maps the alert, to `AlertDefinition-symptomdefinition-1111...`,
    which then fails. Under `--allow-partial` the alert is silently not
    shipped.
- On base, the same rows matched nothing and printed a WARNING. A loud
  no-op has become a wrong action, so the fix newly mis-resolves (review
  dimension 4).
- Fix: a key carrying `SymptomDefinition-` matches only symptoms, and one
  carrying `AlertDefinition-` only alerts. Only a bare key stays
  type-agnostic (as before). Add the same-slug test. The how-to sentence on
  wire-id matching should say a prefixed key names its type.

## WARNING

**W1. A resource-kind-only map stops every derived-key recommendation on
that adapter kind, and the alerts that use them, even when none of those
alerts moves.**
`kinds.py:476-492`. Corpus + `VMWARE\tVirtualMachine\tNEWAK\tNewVM`: all 4
`Recommendation-df-VMWARE-*` recommendations fail ("mapped only for some
resource kinds"). Two HostSystem and Cluster alerts that the map never
touches cascade with them. When no alert referencing the key moves,
keeping the key is certain. Fix: re-point or stop only when some
referencing alert's pair is mapped; otherwise leave the key alone. The
doc's "otherwise it stops" needs the same narrowing. This is a loud false
stop, not a silent pass.

**W2. Kind-valued "text" fields keep the old kind after re-pointing.**
`accounting.py:929` classifies `groupBy.parentText` as text. The renderer
defaults it to the adapter kind key (`render.py:2555`), and
`dashboard_fidelity_wire_format.md` §Heatmap says "historically the adapter
kind key". Corpus + star map gives `parent_text: VMWARE` beside
`parentId`/`adapter_kind: NEWAK` (6 tabs in
`capacity-assessment-right-sizing`, `fleet-capacity-rightsizing`).

**W2b.** The same applies to `{_METRICS}.resourceKindName`
(`accounting.py:922`, which `render.py:1912` defaults to the resource kind
key). The synthetic source with `ProbeOld\tProbe Item\tProbeOld\tProbe
Thing` writes `resource_kind_name: Probe Item` on the re-pointed Scoreboard
metric.

Both are cosmetic on the wire, but they ship the old kind's name as the
label. Fix: when the value equals the old key exactly (the renderer's
default form), re-point it or drop the explicit YAML field so the renderer
re-derives it. Otherwise leave it as text.

**W3. The `verbatim_text` listing undercounts the prose it says ships.**
`convert.py:439-461`. Under `--naming factory-prefixed` a name is
`[VCF CF] ` plus the source's name verbatim, but it is excluded as
"replaced". The stated purpose (doc §Verbatim source text: "so a porter
sees what prose is shipping") needs it listed. Lengths are also taken from
the mapped YAML: a whitespace-stripped description (a recorded loss) or
HTML whose UUIDs were rewritten under mint is reported as "exactly as the
source wrote them". Fix: exclude only `--rename` / `--describe`
replacements, and either measure the source value or say "as written".

**W4. No independent-logic test of re-pointing completeness.**
Dimension 10. Every kind-map test asserts against the importer's own
expectation, or against values chosen by hand on one fixture. Add a
corpus-scale oracle test: convert the rendered factory corpus with and
without `VMWARE\t*\tX\t*`, diff the YAML, and require two things. Every
differing leaf must be an exact old-to-new swap. No leaf at a kind field
(`adapter_kind`, `adapter_kind_key`, `resource_kind*`, `parent_text` equal
to the key) may still hold a mapped kind. This oracle found B1 and W2 in
about 60 lines.

## NIT

1. The claim "report byte-identical minus `verbatim_text`" is false for
   `--ids mint` with derived symptom refs (corpus: the verify block
   changes, 9 alerts DIFFERS become identical). The change is the intended,
   documented fix. Say so in the PR body.
2. The how-to's stress-run numbers ("131 identical apart from intended
   changes", "14 with a View traversal spec") do not reproduce on the named
   releasedimage pak with `--prefer-source` (132; 16 traversal, 6 Summary,
   1 cascade). State the exact command, or drop the counts.
3. `parse_kind_map` / `parse_describe_map` recognize a header only on file
   line 1. A header after a leading `#` comment is a usage error.
   `--describe` with an upper-case UUID matches nothing, which is
   consistent with `--rename` but worth one doc line.

## If shipped as-is

A porter mapping a pack's kind gets B2 and B1. A dashboard whose alert
failed to re-point ships an AlertList pointing at an id that exists
nowhere, and verification calls it intended. Derived-key recommendations
ship `adapter_kind: VMWARE` under the run's false claim that no alert uses
them. Separately (B3), anyone who drops or id-maps a derived-id symptom by
its wire id also silently drops or breaks the same-named alert.
