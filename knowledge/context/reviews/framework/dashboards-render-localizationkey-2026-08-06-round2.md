# Framework review — round 2: drop `localizationKey` from view `<Title>`/`<Description>` (DEF-018)

- **Date:** 2026-08-06 (round 2)
- **Reviewer:** `framework-reviewer` (pre-PR gate, RULE-013)
- **Round 1:** `dashboards-render-localizationkey-2026-08-06.md` — CHANGES REQUESTED, 2 BLOCKING / 3 WARNING / 2 NIT
- **Verdict:** **APPROVE** — 0 BLOCKING / 2 WARNING (1 carried, 1 new observation) / 1 NIT

## Independent verification (re-run, not taken on faith)

| Check | Result |
|---|---|
| 7-package `validate` chain | **pass** (7/7 exit 0) |
| Test suite (default selection, no `-m` override) | **633 passed, 4 skipped**, 177 deselected — exactly +2 vs round 1's 631, i.e. Test C's two tests |
| `tests/test_renderer_regression_phase16.py` (`-m ""`) | 6 passed |
| Test C **negative control** | Pre-fix `render.py` (`git show HEAD:…`) staged into a scratch `src/`, run via `PYTHONPATH=<scratch>/src`: **both Test C assertions FAIL** (`localizationKey="title"` / `"desc"` present). The guard genuinely trips on re-introduction. Read-only; repo untouched. |
| Test C marker scope | `--collect-only` with no `-m` collects all 6 → Test C is in the **default** gate, not the slow-deselected set |
| `vcfops_packaging defect-gate --all` | exit 2 — **DEF-004 only** (pre-existing, unrelated pak). DEF-018 (`tracked`/`open`) does not gate |
| DEF-018 registry parse | `load_registry()` → `DEF-018 | tracked | open`; `tracked` is a documented severity (registry schema line 36) |
| `pak-compare` | n/a — no builder/template change, no pak built |
| Renderer functional delta vs round 1 | none — only comment text changed; round 1's byte-exact corpus regression (19 views, drift == exactly the two stripped attributes) still stands |

## Round-1 findings — disposition

**B1 (no regression test) — RESOLVED.**
`tests/test_renderer_regression_phase16.py::TestViewDefTitleDescriptionNoLocalizationKey`
implements exactly the requested Test C: (a) no `localizationKey` on any
`<Title>`/`<Description>`, (b) zero `localizationKey` occurrences anywhere
in the standalone rendered document. Fixtures are `tmp_path`-local,
`sm_scope=[]` keeps it hermetic (no `content/supermetrics` scan), and the
module docstring's "must fail if the pre-fix behavior is re-introduced"
contract is now literally true — proven by the negative control above,
not asserted.

**B2 (lesson instructed the opposite) — RESOLVED.**
`knowledge/lessons/pak-content-localization-bundles.md` now opens with a
`SCOPE NARROWED 2026-08-06 (DEF-018)` banner that (i) scopes the whole
lesson to bundle-shipping pak units, (ii) states explicitly it is *not* an
instruction to emit `localizationKey` in general, (iii) names the inverse
8.18 hard-fail, and (iv) records the corpus invariant — emit only with a
co-located `content.properties`, never dangling. The Reference section's
renderer line, which round 1 flagged as naming `render.py` as the
attribute-emitting renderer of record, now reads "since DEF-018 emits plain
`<Title>`/`<Description>`". `knowledge/lessons/INDEX.md`'s row matches.
The still-present "localizationKey alignment rule" section is correct
*within* the narrowed scope and is reached only after the banner.

Cross-checked against the round-1 corpus evidence: the banner's
"14 of 934 vendor Title/Description elements carry the attribute; all 14
ship a co-located bundle, zero without" reproduces my own scan exactly.

**W1 (false corpus claim) — RESOLVED.** `render.py:725-750` and DEF-018's
*Summary* both now state the bundle-coupled invariant and name the two
`AriaOperationsContent` counterexamples plus the four
`brockpeterson_operations_dashboards` zips. Matches the corpus.
RULE-001/RULE-002 satisfied.

**W2 (DEF-018 closed while artifacts reproduce it) — RESOLVED.** DEF-018 is
`Status: open`, `Severity: tracked`, with an explicit *Close condition*
(all `bundles/` manifests rebuilt by `content-packager`; a rebuilt
`Views.zip` spot-checked for zero `localizationKey`). See W-A below for
the residual enforcement gap, which is a registry-design observation, not a
regression in this diff.

**W3 (`sdk-buildkit` tarball parity) — NOT ADDRESSED, carried forward.**
`grep DEF-018` finds no mention in `src/vcfops_managementpacks/buildkit.py`
or the registry. See W-B.

**N1 / N2 — RESOLVED.** `test_sdk_content_emit.py:1599-1607` docstring now
gives the spec A3 rationale and states the entries are populated but
unreferenced. `_validate_localization_key_contract()` gained the dormant
note, correctly cross-referencing the `render.py:216-224` column-case twin
(line reference verified accurate).

## Findings (round 2)

### BLOCKING

None.

### WARNING

**W-A — A `factory:<area>` defect gates nothing mechanically, so the stale
shipped zips are tracked by prose only.** `src/vcfops_packaging/defects.py`
(`gate_pak` / `gate_item` / `gate_all`) and `src/vcfops_packaging/cli.py:1149-1163`.
`release`/`publish` gate on `<content_type>/<slug>` or a managed-pak name,
and `gate_all` returns `blocking` only. DEF-018 is `factory:dashboards` and
`tracked`, so a `/publish` of the `vm-snapshot-inventory-dashboard` bundle
today would still succeed and still ship a `Views.zip` that VCF Ops 8.18
hard-rejects. The round-1 fix ("keep it open until the rebuild") was
applied correctly; this is the residual hole underneath it, not a
regression in this diff. **Fix:** either register a companion
`Affects: bundle/<slug>` (or `dashboard/vm_snapshot_inventory`) entry at
`blocking` until the rebuild lands, or accept prose tracking explicitly and
make the `content-packager` rebuild the next scheduled action before any
`/publish`. Do not let the rebuild drift past this PR.

**W-B — `sdk-buildkit` tarball parity (carried from round 1, unaddressed).**
`src/vcfops_managementpacks/buildkit.py:138-147` vendors `render.py` into
the kit as `dashboard_render.py` at kit-build time. Any already-published
buildkit tarball still emits the attributes, so an SDK pak released off it
diverges from the factory renderer. Benign in effect (SDK paks ship the
matching bundle, and 8.18's reject is dangling-key-specific), but it is
real factory/kit drift with nothing written down. **Fix:** one line in
DEF-018's *Close condition* or a `Related:` note — re-cut the kit on the
next release, or record why the divergence is acceptable.

### NIT

**N-A — DEF-018's `Affects:` token carries a parenthetical.**
`knowledge/context/defects.md`: parsed value is
`'factory:dashboards (\`src/vcfops_dashboards/render.py\`)'`, not the clean
`factory:dashboards` token DEF-017 uses. The registry schema (line 38) says
"exactly one artifact scope per entry". No functional impact today (nothing
matches `factory:*` tokens) and DEF-014 sets the same precedent, but if the
entry were ever upgraded to `blocking` and a `factory:` gate added, exact
matching would miss it. Prefer the bare token, with the file path in
`Summary`.

## If shipped as-is

The renderer fix is correct, provably inert outside the intended attribute,
and now genuinely guarded: the regression test fails on the pre-fix
renderer and runs in the default suite. The precedence-2 lesson no longer
instructs the next agent to re-introduce the 8.18 hard reject. The
remaining exposure is entirely in already-shipped artifacts: an operator
downloading `dist/dashboards/*.zip` today still gets the defective zip, and
nothing mechanical refuses a publish of it — so the `content-packager`
rebuild of every `bundles/` manifest must be the next action after this PR,
not a later cleanup.
