# Framework Review — `cross_mp_edges` docs stanza (managementpacks)

- **Date:** 2026-07-06
- **Reviewer:** framework-reviewer (pre-PR, RULE-013 blanket gate)
- **Branch:** feat/cross-mp-stitch-cp-identity
- **Area:** `vcfops_managementpacks/sdk_project.py`, `vcfops_managementpacks/docs_gen.py`
- **Change:** New optional `cross_mp_edges` adapter.yaml stanza (CrossMpEdgeInfo
  dataclass + `_parse_cross_mp_edges()` validator); docs_gen renders a
  "Cross-MP Relationships" section into README.md / inventory-tree.md only
  when the stanza is non-empty. New test file (10 tests).
- **Verdict: APPROVE** (0 BLOCKING / 0 WARNING / 2 NIT)

## Checks re-run (independently, not taken from tooling's block)

| Check | Result |
|---|---|
| Full validate chain (7 packages) | **pass** (exit 0; 5 Tier 1 + 6 Tier 2 valid) |
| `tests/managementpacks/` | **138 passed / 4 skipped** — matches claim |
| New `test_docs_gen_cross_mp_edges.py` | 10 passed |
| `tests/test_defect_gate.py` | 9 failed / 40 passed — **verified pre-existing**: identical failures with the diff `git stash`ed (unifi DEF-002/DEF-004 registry blockers, unrelated to this change) |
| Byte-identical-when-absent | **confirmed** — SHA-256 of README+inventory-tree for all 6 real adapters is bit-for-bit identical old-code vs new-code (all have edges=0) |
| Render-regression | clean |
| pak-compare | n/a (docs-only; no describe.xml / template.json / wire-format touched) |

## Dimension walk

1. **Global-default / pak-specific leak (anchor 00d3382):** none.
   `cross_mp_edges` field uses `field(default_factory=list)` on both
   `SdkProjectDef` and `AdapterDocModel` — no shared mutable default.
   Verified at runtime: two fresh `build_doc_model()` calls and two fresh
   `AdapterDocModel()` instances each hold **distinct** list objects. The
   stanza is inert on every existing adapter (all edges=0). No global path
   affected — this is docs-only, not the content-import path.

2. **Key / label collision (anchor 6c59f6b):** none. No key derivation.
   docs_gen imports the *same* `_parse_cross_mp_edges` from sdk_project
   rather than re-deriving — single source of truth, so the two consumers
   (validate-sdk and docs-gen) cannot diverge. Section anchor
   `#cross-mp-relationships` correctly matches the GitHub slug of heading
   `## Cross-MP Relationships`.

3. **Wire-format conformance:** n/a. Output is generated markdown docs
   (README.md, inventory-tree.md). No wire-format doc governs these;
   describe.xml / template.json / content wire formats untouched.

4. **Loader / validator correctness:** validate-sdk reaches the stanza —
   `validate_sdk_project → load_sdk_project → _parse_cross_mp_edges` for
   all 6 adapters. No UUID/prefix logic touched (RULE-006/007 n/a).

5. **Render regression vs known-good:** clean. Byte-identical hashes above.

6. **Builder / pak structure:** untouched. Diagram outputs
   (excalidraw/svg) intentionally left alone — flagged in code comment,
   not hidden.

7. **Corpus regression:** none. Full validate chain green; no
   previously-good content newly mis-validates.

8. **Silent capability change / downgrade:** explicitly guarded. On the
   docs-gen path, `build_doc_model` calls `_parse_cross_mp_edges` and a
   malformed stanza raises `SdkProjectError` (ValueError subclass) →
   caught by `generate_docset` as `DocsGenError`. **A bad stanza is NOT
   swallowed** — verified by scratch-copy test: 7 malformed variants
   (unknown key, missing required, empty string, bad enum, non-list,
   non-mapping entry, bad field type) each produce a clear
   `adapter.yaml validation error: ... cross_mp_edges[i]: ...` message on
   the validate-sdk path.

9. **Stale-zip discipline:** n/a. Change does not touch
   `vcfops_packaging/templates/`, `vcfops_packaging/builder.py`, or
   `vcfops_dashboards/render.py`. Docs are regenerated at build time and
   are not wire-format pak content; no dist zips are stale by the
   CLAUDE.md rule.

10. **Test coverage:** strong. 10 new tests cover absent (byte-identical /
    idempotent), present (section + foreign annotation), child_foreign
    direction, and all error paths incl. generate_docset surfacing
    DocsGenError. Not vacuous.

## NIT (non-blocking, no action required)

- docs_gen imports a *private* `_parse_cross_mp_edges` across modules.
  Mild coupling smell, but it is the correct single-source-of-truth choice
  (prevents the divergent-validator drift class). Could be promoted to a
  public name later; not worth churn now.
- adapter.yaml is parsed independently in `build_doc_model` (its own
  `yaml.safe_load`) rather than reusing `load_sdk_project`. Consistent
  today because both call the same parser, but a future SdkProjectDef-only
  validation rule would not reach the docs path. Low risk; noting for
  awareness.

## If shipped as-is

No operator-visible change on any existing pak: all 6 adapters produce
byte-identical docs, describe.xml/template.json untouched, no wire impact.
The feature is purely additive and gated on a stanza that no shipped
adapter.yaml yet uses.
