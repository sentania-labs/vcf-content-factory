# Framework Review — reorg-v2 Phase 2 (knowledge/ move + citation sweep)

- **Branch:** `chore/reorg-v2-phase2-knowledge`
- **Diff range:** `e0c1de8..HEAD` (2 commits: `6808d45` git-mv, `e20823f` citation sweep)
- **Reviewer:** framework-reviewer (RULE-013 blanket gate)
- **Date:** 2026-07-09
- **Verdict:** CHANGES REQUESTED — 1 BLOCKING

## Scope

`src/vcfops_*/` touched under RULE-013 blanket gate. Change claims to be:
five functional path-constant relocations plus docstring/comment citation
repoints. Independently verified every `src/` hunk against disk, the
wire-format docs, and the re-run gates.

## Gates re-run (independently)

| Gate | Result |
|---|---|
| `scripts/path_reference_audit.sh` | clean (exit 0) — but see WARNING-2: it does **not** scan `src/` Python string/comment path tokens, so it missed the dead citations below |
| validate ×7 (sm/dash/cg/sym/alert/report/mp) | all PASS |
| `pytest tests/ -q` | 468 passed, 4 skipped, 162 deselected |
| `defect-gate --pak synology` | exit 0 (reads real moved `knowledge/context/defects.md`, 7 entries) |
| `6808d45` rename integrity | pure renames (all R100; zero A/M/D content changes) |

**Every gate is green — and the BLOCKING finding below still slips
through all of them, because no test exercises the live `push-design`
endpoint.** This is the exact escape shape the gate exists to catch:
passes validate/tests, breaks only against a live instance.

## BLOCKING

### B1 — Live MPB import REST endpoint corrupted by the blind `designs/` → `knowledge/designs/` substitution

- **File:** `src/vcfops_managementpacks/client.py:100`
- **Was:** `path = f"{_MPB_BASE}/designs/import"` → `/internal/mpbuilder/designs/import`
- **Now:** `path = f"{_MPB_BASE}/knowledge/designs/import"` → `/internal/mpbuilder/knowledge/designs/import`
- **Authority:** `knowledge/context/mpb/mpb_api_surface.md:36` documents the
  CONFIRMED endpoint used by the `push-design` CLI as
  `POST /suite-api/internal/mpbuilder/designs/import`. There is no
  `/knowledge/` segment in the vendor endpoint — it is a repo directory
  name that the citation sweep leaked into a wire path because the string
  literal happened to contain the substring `designs/`.
- **Impact:** `post_design_import()` is the actual HTTP request path for
  `push-design` (the MPB UI Verify cheap-loop and the design import
  workflow). Against a live instance it will now 404/400 — the design
  import step of the entire Tier-1 MP flow is broken. A behavior change
  smuggled into a change asserted to be "docstring/comment-only + five
  path constants."
- **Blast radius (same root cause, fix together):**
  - `client.py:100` — **the load-bearing one** (actual request path).
  - `cli.py:755` `ui_url` — printed MPB UI deep-link, now `.../mpbuilder/knowledge/designs/{id}` (user-facing wrong URL).
  - Doc/print/comment echoes of the same endpoint: `cli.py:603, 718, 1244`; `client.py:64, 73`; `render.py:14, 1042`.
- **Smallest correct fix:** restore `f"{_MPB_BASE}/designs/import"` at
  `client.py:100` and revert every `mpbuilder/knowledge/designs` back to
  `mpbuilder/designs` across the 8 sites above (they are vendor REST/UI
  paths, not repo citations — the sweep must exclude them). Confirm with
  `grep -rn "mpbuilder/knowledge/designs" src/` returning empty.

## WARNING

### W1 — Dead citations: `mpb_wire_reference` files repointed to a non-existent path

- **Files:** `render.py`, `render_export.py`, `builder.py`,
  `pak_compare.py`, `extract.py` — 11 references to 3 distinct files.
- **Cited (dead):** `knowledge/context/mpb_wire_reference/{synology_nas_working_describe.xml, synology_nas_working_export.json, vsphere_storage_paths_aria_ops_stitch.json}`
- **Real location on disk:** `knowledge/context/mpb/wire_reference/…`
- **Root cause:** these were already stale at `e0c1de8`
  (`context/mpb_wire_reference/…`; the files actually live under
  `mpb/wire_reference/`). The sweep mechanically prepended `knowledge/`
  instead of correcting them — so a stale citation stayed stale. The
  brief claims the sweep "repointed ~30 stale pre-subdir citations to
  **real** subdir locations"; these 3/11 were missed.
- **Severity:** comment/docstring only — no runtime effect — hence
  WARNING, not BLOCKING. But it is direct evidence the sweep was **not
  verified against disk**, which is why B1 also escaped.
- **Fix:** repoint the 11 references to `knowledge/context/mpb/wire_reference/`.

### W2 — `path_reference_audit.sh` does not cover `src/` Python citations

- The audit passed clean while B1 (wire path) and W1 (dead file
  citations in `src/` comments) both exist. The audit's own scan scope
  excludes `src/*.py` string/comment path tokens. Not a defect in this
  diff, but the sweep leaned on this audit as its correctness proof and
  the audit cannot see the class of error the sweep introduced. Flagging
  so `tooling` does not treat "audit clean" as sufficient here.

### W3 — Stale-zip discipline: rebuild not flagged

- Diff touches `src/vcfops_dashboards/render.py`,
  `src/vcfops_packaging/builder.py`, and
  `src/vcfops_packaging/templates/{install.py,install.ps1}`. Per CLAUDE.md
  "After tooling changes," all dist zips are stale — the template install
  scripts are shipped verbatim, so their embedded-comment bytes change,
  and `builder.py:307` changed the convention design-lookup path
  (`designs/` → `knowledge/designs/`). A `content-packager` rebuild of
  every `bundles/` manifest is warranted and was not flagged.
- **Fix:** after B1 is resolved, delegate `content-packager` to rebuild.

## Verified safe (no finding)

- **Five functional constants** all resolve at runtime and read real data:
  `defects.py:63` REGISTRY_PATH (7 entries), `describe.py:70`
  `_DEFAULT_CACHE_ROOT` (exists), `managed_paks.py:73`
  `_DEFAULT_REGISTRY_PATH` (6 paks), `publish.py:790` `registry_path`,
  `builder.py:307` convention design lookup (`knowledge/designs/` exists).
  Each reads the file the same way as before — no fail-open masking: I
  confirmed the constants point at real files, so the `.exists()`-guarded
  degrade paths (`builder.py` empty-design-dict, `_gate_publish` vacuous
  pass) are inert, not silently swallowing a moved-away file.
- **`test_defect_gate.py`** — real-corpus tests (`TestRealRegistryStructural`)
  load the **real** `REAL_REGISTRY = knowledge/context/defects.md` and
  passed; behavioral tests correctly use tmp_path fixtures via
  `REGISTRY_PATH` monkeypatch. Not quietly pointed at a fixture.
- **`buildkit.py`** — packages sibling packages + `LICENSE` only; no
  reference to any moved dir (`context/`, `rules/`, `lessons/`,
  `designs/`). Rewrite rules touch `_REPO_ROOT/LICENSE`,
  `/tmp/reference_paks`, `/dist` — none moved. Both isolation tests
  (`test_buildkit_isolated_build.py`, `test_buildkit_release_flag.py`)
  passed in the full run.
- **`6808d45`** is a clean pure-rename commit (all R100, zero content
  edits inside the "move").
- **No global-default leak / key-collision** patterns introduced —
  anchors `00d3382` / `6c59f6b` are not re-opened; this is a path-string
  change set, and the standalone content-import render path is untouched.

## If shipped as-is

The `push-design` command — the MPB UI Verify cheap loop that gates every
Tier-1 management-pack build — would POST to a non-existent
`/internal/mpbuilder/knowledge/designs/import` and fail on every live
instance, silently blocking the MP authoring workflow with a 404/400 that
looks like an instance problem, not a factory regression.

---

## Addendum — re-review of fix `cd7c130` (2026-07-09)

**Verdict: APPROVE** (0 BLOCKING). B1 and W1 resolved; no new regression.

`tooling` committed `cd7c130` ("restore MPB import endpoint + correct
mpb_wire_reference citations"). Independently re-verified:

- **B1 fixed.** `grep -rn "mpbuilder/knowledge/designs" src/` returns
  empty. Runtime construction confirmed: `f"{_MPB_BASE}/designs/import"`
  → `/internal/mpbuilder/designs/import`, matching
  `knowledge/context/mpb/mpb_api_surface.md:36`. All 8 sites
  (client.py:100 load-bearing + cli/render doc echoes + ui_url) restored.
- **W1 fixed.** All 3 `mpb_wire_reference` files now cited as
  `knowledge/context/mpb/wire_reference/…` and resolve on disk; the old
  `mpb_wire_reference` token no longer appears in `src/`.
- **No regression / no smuggle.** `cd7c130` is 20 insertions / 20
  deletions across 7 files; a full `-U0` content-line audit shows **every**
  changed line is an endpoint restore or a wire_reference repoint — no
  behavior change outside the two findings.
- **Comprehensive re-check.** All 71 distinct `knowledge/` file+dir
  citations in `src/` now resolve on disk (was 3 dead).
- **Gates re-run green:** validate ×7 PASS; `pytest tests/ -q` 468 passed
  / 4 skipped; `path_reference_audit.sh` clear; `defect-gate --pak
  synology` clean.

**Remaining, tracked out of this verdict:** W3 (dist-zip rebuild) —
`content-packager` before the PR, per coordinator. W2 (audit does not
scan `src/` Python path tokens) — backlog.

**Final verdict: APPROVE.** Clear to open the PR once W3's rebuild lands.
