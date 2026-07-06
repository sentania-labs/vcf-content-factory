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

---

# Delta Review — markdown table-cell escaping (Codex PR #33 P2 fix)

- **Date:** 2026-07-06 (delta on top of the APPROVEd base above)
- **Reviewer:** framework-reviewer (RULE-013 delta gate)
- **Scope:** `git diff HEAD -- vcfops_managementpacks/ tests/` only — the
  uncommitted follow-up. Base change already APPROVEd above.
- **Change:** new `_escape_md_table_cell()` helper in `docs_gen.py`
  (`|` → `\|`; collapse `[\r\n]+` runs to a single space), applied to the
  parent label + child label + `foreign_adapter_kind` annotation
  (`_format_cross_mp_endpoint`) and the description cell
  (`_render_cross_mp_edges_md`). One new test class
  (`TestCrossMpEdgesTableCellEscaping`) + `import re` in the test file.
- **Verdict: APPROVE** (0 BLOCKING / 0 WARNING / 2 NIT)

## Checks re-run (independently)

| Check | Result |
|---|---|
| `tests/managementpacks/` | **139 passed / 4 skipped** (was 138 — +1 new test class, its 1 method) |
| `test_docs_gen_cross_mp_edges.py` in isolation | **11 passed** (was 10) |
| `python3 -m vcfops_managementpacks validate` | **pass** — 5 Tier 1 + 6 Tier 2 valid |
| Byte-identical on clean input — synology (edges=2, real pipe-free stanza) | `docs/README.md` **BYTE-IDENTICAL** vs committed build 28; `docs/inventory-tree.md` **BYTE-IDENTICAL** |
| Stitch-less adapter — compliance (edges=0) | `docs/README.md` + `docs/inventory-tree.md` **BYTE-IDENTICAL** — untouched |
| Render-regression | clean |
| pak-compare | n/a (docs-only markdown; no describe.xml / template.json / wire format) |

(Note: synology root `README.md` is a *hand-curated* index, not a docs_gen
target — `generate_docset` writes `docs/README.md` + `docs/inventory-tree.md`
only, per its REGENERATE policy. The generated targets are byte-identical;
the root file is correctly out of the picture.)

## Verification of the four asks

1. **Tests + validate** — re-run above; all green. New test's pipe-counting
   logic is sound: it counts `|` chars not preceded by a `\`, asserts exactly
   4 column separators, asserts escaped pipes survive and no `\r`/`\n` remain.
   Not vacuous — it first asserts the raw model actually contains the `|`/`\n`
   hazards before checking the rendered row.

2. **Byte-identical on clean input** — confirmed for synology (2 real edges,
   pipe-free values incl. a backtick code-span `<nas_ip>/<vol_path>/<share>`
   and a folded-scalar description) and for stitch-less compliance. The escape
   is a genuine no-op on pipe/newline-free input: `re.sub` matches nothing,
   `.replace("|", …)` finds nothing. Confirmed diffs are empty.

3. **Escaping completeness — EVERY rendered cell path covered.** The table
   has exactly 3 columns (Parent / Child / Description). All rendered value
   paths pass through `_escape_md_table_cell`: parent label + child label +
   `foreign_adapter_kind` annotation (docs_gen.py:406-407) and description
   (docs_gen.py:437). Header row, heading, and prose paragraph are static
   code literals — no author data. No uncovered cell.

   **Code-span composition (the load-bearing question):** an own-adapter
   endpoint renders as a backtick code span, so a pipe value yields
   `` `relationships\|Datastore_parent` `` — a `\|` *inside* backticks. This
   renders correctly on GitHub. Per the **GFM spec, tables extension,
   example 200**: input `` b `\|` az `` renders as `b <code>|</code> az`
   — the table extension unescapes `\|` → `|` *before* the code span is
   formed, so the reader sees a literal `|` with **no visible backslash**.
   Same for italic/bold (`` **\|** `` → `<strong>|</strong>` in the same
   example), which covers the `*{label}*` foreign path. So the escape
   composes correctly with both the backtick and italic wrapping; no separate
   strategy for the code-span cell is needed. Verified the emitted string
   shape by hand (`_format_cross_mp_endpoint` output eyeballed).

4. **Anything beyond stated scope** — none. The diff is exactly: `import re`
   (both files), the helper, two call-site applications, one test class.
   No behavioral change to any other function, no new default, no wire path.

## Dimension walk (delta-specific)

- **Global-default / pak-specific leak (00d3382):** none. The escape is a
  pure, context-free string transform applied uniformly to every edge cell;
  it introduces no pak-specific default and no coordinate/flag. Inert on
  clean input (proven byte-identical on 2 adapters).
- **Key / label collision (6c59f6b):** none. No key derivation; this is
  display-cell escaping only. Distinct labels remain distinct (escape is
  injective on the pipe/newline alphabet — it never merges two inputs).
- **Wire-format conformance:** n/a — generated markdown, no wire doc governs.
- **Silent downgrade:** none. Escaping *prevents* a silent corruption (a raw
  `|`/newline previously breaking the row); strictly a correctness gain.
- **Test coverage:** the changed behavior is directly covered by the new
  test class (pipe + newline in parent/child/foreign_kind/description).

## NIT (non-blocking)

- `_escape_md_table_cell` handles `|` and `\r\n` but **not** a literal
  backtick in an own-adapter label (which would break the `` `…` `` code
  span). Out of the stated P2 scope (pipes/newlines) and low-likelihood
  (labels are resource-kind / adapter-kind names), but worth a follow-up if
  cell content ever widens. Not blocking.
- The `docs/inventory-tree.excalidraw` / `.svg` diagram outputs embed edge
  labels in JSON/SVG, not markdown; a pipe there would need JSON/XML escaping,
  not `\|`. Pre-existing and out of this delta's scope (synology values are
  pipe-free, so no regression today). Noting for awareness only.

## If shipped as-is

No operator-visible change on any shipped adapter: synology and compliance
docs regenerate byte-identical. The escape only activates when an author puts
a literal `|` or a newline in a `cross_mp_edges` value — where it converts a
previously-broken table row into a correct single-line, correctly-columned
one that renders the intended literal pipe on GitHub. Pure correctness gain,
zero regression surface.
