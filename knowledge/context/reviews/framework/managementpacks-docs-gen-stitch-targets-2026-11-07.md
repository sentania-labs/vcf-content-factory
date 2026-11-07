# Framework review: docs-gen `stitch_targets` (factory #310)

- **Date:** 2026-11-07
- **Branch:** `worktree-agent-a715c262d0a887445` (uncommitted working tree on top of `ce34da8`; reviewed with `git diff main`)
- **Area:** `src/vcfcf_managementpacks/sdk_project.py` (new `stitch_targets` adapter.yaml stanza, `StitchTargetInfo`, `_parse_stitch_targets`, wired into `load_sdk_project`) and `src/vcfcf_managementpacks/docs_gen.py` (`## Metrics Pushed Onto` in README.md / inventory-tree.md / overview scaffold; dashed external nodes in SVG and Excalidraw)
- **Also touched:** `tests/managementpacks/test_docs_gen_stitch_targets.py` (new), `tests/fixtures/sdk_adapters/docs_gen_baseline/` (new), `knowledge/context/tier2_architecture.md` (changelog row)
- **Origin:** vsanperf build 4 review W2 (`knowledge/context/reviews/vsanperf-build-4-review.md`)
- **Verdict:** APPROVE (0 BLOCKING / 1 WARNING / 4 NIT)

## Checks re-run (independent; main checkout and adapter clones untouched)

| Check | Result |
|---|---|
| Validate chain (7 packages), worktree source | pass (`&&` chain ran to the end; managementpacks `OK: 5 Tier 1 ...`) |
| `pytest tests/managementpacks/` | worktree, gap file deselected: 408 passed, 0 failed. main, full dir: 421 passed, 2 failed (`test_gap_b_f_d.py::TestGapFJMESPathPredicates` x2); the same 2 fail on the worktree. A first worktree run also failed 3 x `test_sdk_compat_target.py`; they pass on re-run and in isolation (flaky, javac-backed, no path into the changed files) |
| New tests | `test_docs_gen_stitch_targets.py` all pass |
| Other `SdkProjectDef` constructors (`test_dashboard_navigations`, `test_dashboard_summary_for`, `test_emit_fidelity_bugs`) | 159 passed |
| Regenerate docsets for the five factory paks with an adapter.yaml (compliance, vsanperf, synology, unifi, template), HEAD source vs worktree source, inputs copied to scratch (adapter.yaml, describe.xml, resources/, `_index_extra.md`), fresh scaffolds | `diff -r`: **byte-identical**, all six files per pak. Import paths confirmed per side (HEAD lacks `_render_stitch_targets_md`) |
| Baseline fixtures really captured from HEAD | regenerated `tree_pak` and `stitch_only_pak` with main's source: `diff -r` against `expected/` identical for both |
| Module-state leak | one process: tree_pak+stanza, vsanperf+stanza, compliance, tree_pak+stanza, synology. compliance and synology output byte-identical to the HEAD run |
| Determinism | tree_pak+stanza under `PYTHONHASHSEED` 1, 2, 999: one sha256 per file. Ids are md5 of seeds, ordering follows YAML order, no set iteration |
| Sample vsanperf stanza (HostSystem + ClusterComputeResource, `<vmnic>` placeholder) on the real vsanperf adapter.yaml/describe.xml | loads via `load_sdk_project`; renders README / inventory-tree.md / SVG / Excalidraw; SVG rasterized with headless Chrome and read: instance node, two dashed orange target nodes, dashed orthogonal "pushes keys" edges, `<vmnic>` shown literally |
| Adversarial stanza (`&`, `"`, `<x>` in identity and key groups; same `HostSystem` under `VMWARE` and `OTHER`) | SVG parses as XML; entities escaped; Excalidraw 15 elements, 0 duplicate ids; distinct headings `HostSystem (VMWARE)` / `HostSystem (OTHER)`; pipes `\|`-escaped inside the code span (GFM unescapes `\|` in table cells before inline parsing, so it renders as `|`) |
| Older kit behaviour | HEAD `load_sdk_project` and `generate_docset` accept the stanza, **including a malformed one** (`- bogus` entry), with no error and no section |
| pak-compare | n/a: docs only, the .pak bytes do not carry `docs/` |
| Stale-zip / `CURRENT_TEMPLATE_VERSION` | n/a: no file in the "after tooling changes" list touched; factory zips do not use docs_gen |

## Dimensions

1. **Global-default leak (00d3382 anchor).** All new branches gate on `model.stitch_targets` being non-empty; the overview f-string inserts `""` when absent. Proven inert by the five-pak byte diff, the two HEAD-captured baselines, and the in-process interleave. New module-level names are constants only. Clean.
2. **Key/label collisions (6c59f6b anchor).** Excalidraw seeds are `stitch:<ADAPTER>::<Kind>`, so the same resource kind under two adapter kinds gets distinct ids (verified); the parser rejects a duplicate (adapter, kind) pair; seeds cannot collide with main-tree `rect:<kind.key>` seeds. Main tree does not draw foreign kinds (tier2_architecture "Generated docset"), so a target that is also a cross-MP parent is not drawn twice. Clean.
3. **Wire format.** Not a wire surface; the pak is unchanged. Markdown/SVG/Excalidraw are the docset contract in `tier2_architecture.md` "Generated docset". SVG text goes through `_svg_escape`; Excalidraw text through `json.dumps`.
4. **Loader/validator.** Validation is in `load_sdk_project`, so validate-sdk reports `adapter.yaml validation error: ...` and docs-gen raises `DocsGenError` with the same message (test parametrizes 11 bad shapes through all three). No previously-valid adapter.yaml is affected (key absent returns `[]`; the five factory paks load). New dataclass field is defaulted and appended; all other constructors use keywords.
5. **Render regression.** Byte-identical on all five paks and both fixtures.
6. **Builder.** `build-sdk` calls `generate_docset` inside a try that downgrades `DocsGenError` to a warning, but `load_sdk_project` runs first in the build, so a malformed stanza still fails the build rather than just losing docs.
7. **Corpus regression.** Validate chain green; managementpacks failures pre-existing/environmental.
8. **Silent downgrade.** None in the new kit. An older kit silently ignores the stanza: see W1.
9. **Stale zip / version signal.** Not applicable (no template/builder/assembly/render file touched).
10. **Tests.** Baseline byte guard, rendering, validation and determinism covered. Two small gaps: N3.

## Findings

### WARNING

- **W1 [src/vcfcf_managementpacks/buildkit.py:92, knowledge/context/tier2_architecture.md:1288] buildkit versioning: a pinned old kit silently accepts any `stitch_targets`, malformed included.** Verified against HEAD source: `load_sdk_project` reads top-level keys with `raw.get`, so `stitch_targets: [bogus]` passes validate-sdk and build-sdk on kit 1.0.24 with no error. Impact today is small and the brief's question is answered "acceptable without a bump": pak CI (`build-pak-on-tag.yml`) ships only the .pak and SHA256SUMS, and the committed `docs/` come from local factory builds that do run the new parser. So nothing shipped changes and a malformed stanza is still caught locally. What is wrong is the changelog row's framing: "an older kit ignores the key" reads as harmless, but it also means pak CI does not gate the stanza until the pak bumps `BUILDKIT_TAG` past a kit that has this code, and a contributor who edits adapter.yaml without a local factory build gets no signal. Same posture as the 2026-10-28 docs-gen row (no bump), so this is consistent precedent, not a regression. → Reword the Versioning sentence to say exactly that: docs are generated by local factory builds so adoption does not wait on a kit; pak CI validates the stanza only once the pak pins a kit cut after this change (name it, "the next sdk-buildkit tag"). No `BUILDKIT_VERSION` bump required in this PR.

### NIT

- **N1 [src/vcfcf_managementpacks/docs_gen.py:693, :1757] heading and quick-reference use raw `resource_kind` / `adapter_kind`.** `identity` and `instanced_by` go through `_md_prose`, but the `### <Kind> (<ADAPTER>)` heading and the `Metrics pushed onto:` line do not. A kind key with `<`, `*` or `_` would be mangled. Real kind keys are identifier-like, so harmless today. → Either pass the label through `_md_prose`, or (better, and it also catches typos) reject `adapter_kind` / `resource_kind` values containing whitespace or `<>|` in `_parse_stitch_targets` (sdk_project.py:296).
- **N2 [src/vcfcf_managementpacks/docs_gen.py:655] `_md_prose` escapes only `<` and `>`.** `*`, `_`, backticks and `[` in `identity` / `instanced_by` are live markdown (e.g. `instanced_by: "*any* vmnic"` renders italic). Free text by design, low risk. → Also escape `\`, `*`, `_`, `` ` ``, `[`, `]`, or document that the fields are markdown.
- **N3 [tests/managementpacks/test_docs_gen_stitch_targets.py] two cases verified by hand are not pinned.** (a) same `resource_kind` under two `adapter_kind`s: distinct headings and distinct Excalidraw ids; (b) SVG escaping of `&` and `"` in key groups / identity (only `<vmnic>` is asserted). → Add one parametrized test each.
- **N4 [knowledge/context/tier2_architecture.md] discoverability.** The stanza's schema lives in the changelog row and the `sdk_project.py` docstring; the "Generated docset (`docs/`)" narrative section, which is where an author reads what feeds the docs, does not mention it. → Add a two-line paragraph there pointing a stitch-only pak at `stitch_targets` (and the orchestrator may want the `sdk-adapter-author` / `mp-designer` prompts to mention it for ARIA_OPS-stitching designs; prompts are not tooling's scope).

## Claims vs observed

| tooling claim | observed |
|---|---|
| byte-identical without the stanza | confirmed (5 paks, 2 fixtures, interleaved process) |
| fixtures captured from HEAD | confirmed by regenerating with main's source |
| 22 new tests pass | new file passes |
| full suite 3261 passed / 15 env failures identical to HEAD | not re-run in full; managementpacks dir re-run on both sides: only the 2 JMESPath failures, identical on main |
| older kit ignores the key | confirmed, and also ignores a malformed stanza (W1) |

## If shipped as-is

A pak without the stanza sees no change. A stitch-only pak that adds the stanza gets a landing page and diagram that say where its keys land. Until the pak pins a newer kit, its CI does not check the stanza.
