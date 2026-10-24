# Framework review: docs_gen include, content_naming, SCG control_id pipeline

- Branch: `fix/docsgen-naming-scg-171-229-169-170`, five commits on `origin/main` (10b1ad0):
  d6683a0 (#171), 6463e39 (#229), 1d8fd21 (#169), 31261a7 (#170), 6993ede (#229 agent prompts)
- Reviewed at: 6993ede, detached worktree, pak clones symlinked in
- Reviewer: framework-reviewer (RULE-013)
- Date: 2026-10-23

## Verdict

**APPROVE** (0 BLOCKING, 4 WARNING, 3 NIT).

The code does what the issues ask and changes nothing for paks that do not
opt in. I reproduced every byte-identity claim. The warnings cover three
things: the 8.0 floor the author picked (vmx-21) contradicts the control's
own title and the vendor's current revision; the new author-prompt wording
narrows the unprefixed escape hatch to paks that declare the field, and no
pak declares it today; and RULE-006 has no carve-out for the new
`unprefixed` value.

## What I re-ran (independently)

| Check | Result |
|---|---|
| Full test suite, clones symlinked | **2213 passed, 9 skipped, 0 failed**. The release-manifest tests run and pass with the clones present. The 9 skips are environmental and pre-existing (MPB buildNumber product decision, pak-compare dist paks absent, SDK jar absent, one shim). |
| New tests (`-k release or manifest or content_naming or index_extra or scg`) | 221 passed, 0 skipped |
| Seven-package validate chain | all rc=0; `vcfcf_managementpacks validate` reports 7 SDK projects valid |
| `validate-sdk` on every Java pak clone | compliance, synology, template, unifi: OK, no naming output (all bundled names prefixed). vcommunity (149), vcommunity-os (3), vcommunity-vsphere (176): OK plus one undeclared-default warning each. None fails. |
| docs-gen, origin/main vs branch, on scratch copies of compliance, synology, unifi, vcommunity | **whole `docs/` tree byte-identical** for all four (no `_index_extra.md` present in any clone). The clones were never written. |
| docs-gen with include present / blank / BOM | merged under `## Adapter-Specific Documentation` after Quick Reference; a whitespace-only include gives a README byte-identical to main; BOM case, see N1 |
| SCG regen via the compliance repo's own drivers (6.7, 7.0, 8.0, 9.0, 9.1), origin/main scripts | all five **byte-identical to the committed `profiles/canonical/scg_*.csv`** (baseline is sound) |
| Same, branch scripts | 6.7, 7.0, 9.1 byte-identical to committed; 8.0 and 9.0 differ in **one row each, `vm.virtual-hardware`**, two fields (`expected_value` `vmx-21` to `vmx-21 or newer` / `vmx-19` to `vmx-19 or newer`, plus the caveat text). Matches the author's `r170/out` byte for byte. |
| Factory scripts run directly (no compliance deltas), main vs branch, on the clone sources and on the current vendor sources in `reference/` | the only diff is the same `vm.virtual-hardware` row |
| Em-dashes in added lines and commit messages | one, in `tests/managementpacks/test_docs_gen_index_extra.py`, inside an assertion that the README contains none. That one is necessary. No others. |

## Failure-mode hunt

- **Silent downgrade (declared mismatch only warns):** no. When the field is
  declared, every mismatch is an error in `validate-sdk` (`sdk_builder.py`
  validate path) and raises `SdkBuildError` in `build_sdk_pak` before compile.
  A test covers the build-sdk raise. Any value other than the two allowed
  ones, including `null`, is an `SdkProjectError` (`sdk_project.py`
  `load_sdk_project`). Only an absent key gives a warning, which is the
  specified behaviour.
- **Default leaking into paks that never declared the field:** no behaviour
  change. On build and validate, an undeclared pak only gets a stderr
  warning (confirmed on all seven clones). The docs_gen include is opt-in
  by file, and the output is byte-identical without the file.
- **Key collision:** none. `content_naming_declared` comes from
  `"content_naming" in raw`. The checker loops over all seven bundled
  types, and every loader object it reads has `name` (including
  `Recommendation`). The SCG rewrite is keyed to exactly
  `vm.virtual-hardware`; a test confirms another control is untouched.
- **Deprecated source-ID VGT table vs the new control_id table:** the
  values are identical today. The regen proves no divergence in any of
  the five profiles. Nothing pins the two copies together, though (W3).
- **Classifier order:** the shared `normalize_scg_source` keeps origin/main's
  v8 order exactly (secpol, vSAN, vim, esxcli, service_state, scoped (was
  source-id), control override; then baseline, vSAN expected, reclass
  expected). The new `rewrite_undefined_baseline` and `rewrite_expected`
  steps change nothing in 6.7/7.0/8.0/9.0/9.1 except the one intended row.
- **Stale-zip / template version (dimension 9):** not triggered. No file on
  the stale list changed (`templates/`, `builder.py`, `discrete_builder.py`,
  `release_builder.py`, `assembly.py`, `render.py`). `sdk_builder.py` only
  gained a pre-compile check and emits no new bytes. docs_gen writes into
  the repo, not into the pak. No `CURRENT_TEMPLATE_VERSION` bump needed.

## The 8.0 floor: which number is right

`reference/references/vcf-security-and-compliance-guidelines/` has the vendor
CSV history for SCG 8.0 (`security-configuration-hardening-guide/vsphere/8.0/vmware-vsphere-security-configuration-guide-8-controls.csv`):

| Vendor revision | Title | Baseline Suggested Value |
|---|---|---|
| cc3402c, 7c4e302 (803-20260107-01; **byte-identical to the compliance clone's `profiles/vmware_scg_8.0.csv`**) | "version **19** or newer where supported" | `vmx-21` |
| ea455b0 (803-20260612-01, current `VERSION`) | "version **17** or newer where supported" | `vmx-17 or higher` |

SCG 9.0 has the same pattern. The clone's source says title 19, baseline
`vmx-19`. The current vendor 9.0 CSV (902-20260612-01) says
`vmx-17 or higher`.

In the revision the factory ingests, the 8.0 title and Discussion state
the requirement as 19 ("Virtual hardware 19 is compatible...", with 21 as
"consider upgrading to"). The `vmx-21` cell is the suggested target, not
the floor. The vendor confirmed this by rewriting the cell to
`vmx-17 or higher` in the next revision. **So `vmx-21` is not the right
floor.** Read as written, the source supports 19. The authoritative
current answer is 17, and it arrives verbatim (already in minimum form)
once the compliance repo re-ingests the 20260612 CSVs. See W1.

## Findings

### BLOCKING

None.

### WARNING

- **W1** [`scripts/_compliance_normalize.py:751` `vmx_minimum`; `tests/test_scg_normalize_rules.py:238,256` labels `vmx-21` "SCG 8.0 baseline"]
  Authority: the SCG 8.0 vendor CSV in `reference/` (table above), RULE-001/002.
  The #170 form fix is correct and strictly more lenient than before, so
  nothing regresses. But the regenerated 8.0 profile still scores a VM on
  vmx-19 or vmx-20 as non-compliant, while the same alert's title says
  "version 19 or newer" passes. 9.0 floors at 19 where the vendor's
  current revision says 17. Fix: do not hand-pick a number in the factory.
  Open a compliance-repo issue to re-ingest the 803-20260612-01 and
  902-20260612-01 CSVs (both say `vmx-17 or higher`, which already
  matches the minimum form). In this PR, state in the body that the 8.0
  and 9.0 floors follow the stale source cell until that refresh lands,
  and drop the word "baseline" from the test comment at line 238 or
  qualify it.

- **W2** [`.claude/agents/supermetric-author.md:78-79`, `.claude/agents/symptom-author.md:55-56`; also `alert-author.md:81`, `supermetric-author.md:95`, `symptom-author.md:69`, `view-author.md:87`, `dashboard-author.md:13`] (commit 6993ede)
  Authority: the field contract in `src/vcfcf_managementpacks/sdk_builder.py` `check_content_naming` and `sdk_project.py`.
  Values and default match the code. The absent-key behaviour does not:
  1. Two prompts narrowed the per-type-validator bypass from "a pak whose
     names are unprefixed" to "a pak whose `adapter.yaml` declares
     `content_naming: unprefixed`". No pak declares the field today
     (verified: all three vCommunity clones warn as undeclared, with 149,
     3 and 176 unprefixed names). An author briefed to add to a
     vCommunity pak now reads "factory_prefixed (the default) requires
     the prefix", prefixes the new object, and leaves the pak with mixed
     names. Before this commit the prompt would have guided that author
     correctly. This is a guidance regression until the vCommunity
     repos declare.
  2. "requires the prefix on every bundled name" is only true when the
     field is declared. Undeclared, the code warns and passes. The
     prompts never mention that build-sdk enforces too.
  Fix: either add `content_naming: unprefixed` to the three vCommunity
  `adapter.yaml` files (in their own repos, landing with or before this
  PR), or reword all five prompts to: "absent field: match the pak's
  existing names, report that the pak should declare the field;
  `validate-sdk` and `build-sdk` only warn until it does". Restore
  "names are unprefixed" as the bypass condition for the two
  per-type-validator lines.

- **W3** [`scripts/_compliance_normalize.py:1137` `_VIM_RECLASS_BY_CONTROL_ID_AND_PRODUCT` vs `:1195` `_VIM_RECLASS_BY_SOURCE_ID`]
  Authority: reviewer doctrine (two copies of a live scoring rule); dimension 10.
  The deprecated table is still live: the compliance repo's 6.7 driver
  calls `classify_source_id_vim_reclass`, and the 7.0 driver reads and
  extends the dict. Its values match the new rule today, but no test
  pins them together. An edit to the `dvpg.network-vgt` recipe in one
  table silently diverges 6.7/7.0 from 8.0/9.x. Fix: build the
  deprecated dict's entries from the scoped rule's tuple (one source),
  or add a one-line parity test asserting each deprecated entry equals
  `_VIM_RECLASS_BY_CONTROL_ID_AND_PRODUCT["dvpg.network-vgt"][1]`.

- **W4** [`knowledge/context/tier2_architecture.md` "Bundled content naming"; `src/vcfcf_managementpacks/sdk_project.py` docstring]
  Authority: `knowledge/rules/content-prefix.md` (RULE-006) and CLAUDE.md knowledge precedence ("if a context file contradicts a rule, the rule wins").
  RULE-006 says all authored content uses the prefix. Its only carve-out
  is the MP prose prefix. `content_naming: unprefixed` is a
  framework-sanctioned exemption that the rule does not list. An agent
  that reads the rules first, as the precedence requires, will refuse to
  honour the field. Fix (orchestrator-owned, `knowledge/rules/`): add a
  carve-out line to RULE-006 naming `content_naming: unprefixed` for SDK
  paks that keep upstream names, in this PR.

### NIT

- **N1** [`src/vcfcf_managementpacks/docs_gen.py:1221`] Reads the include with `encoding="utf-8"`. A file saved with a BOM (common for Windows editors, and portability is a framework requirement) lands as `U+FEFF### Extra` mid-README, verified, and CommonMark then does not parse the first heading. Fix: `encoding="utf-8-sig"`.
- **N2** [`src/vcfcf_managementpacks/docs_gen.py:1122`, docstrings and `tier2_architecture.md`] The docs say "merged verbatim", but the body is `.strip()`ped, so an include that starts with an indented code block loses its first line's indentation. Fix: strip only blank lines (`strip("\n")` after a blank check), or say "trimmed" in the docs.
- **N3** [`tests/managementpacks/test_sdk_content_naming.py:174`] build-sdk is tested only on the declared-mismatch raise. Nothing asserts that an undeclared mismatch warns and still builds, and that path is the one every vCommunity release CI takes today. Fix: one test mirroring `test_absent_key_mismatch_is_a_warning_not_an_error` against `build_sdk_pak` (stub past the content-naming step).

## If shipped as-is

Nothing changes for any existing pak or profile except the intended
`vm.virtual-hardware` row. Operators on SCG 8.0 still see vmx-19/20 VMs
flagged against a title that says 19 is fine. Content authors working in
a vCommunity pak will be told to prefix new objects in a pak whose names
are all unprefixed.
