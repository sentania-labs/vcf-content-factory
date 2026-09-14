# Content migrator: plan v1

Status: approved plan, 2026-09-14. Milestones M1 and M2 happen in this
repo. M3 and M4 happen in a new repo the factory authors.

## Use case

A customer migrates custom content from one VCF Operations instance to
another. Before importing, they review the tree of custom content and its
dependencies (dashboards, views, super metrics, custom groups, symptoms,
alerts, policies, notifications, outbound settings), preview each object
with mock data, select what to keep, and produce an import bundle.

## Decisions

- **Separate tool, separate repo, own release cadence.** Runs on a
  customer workstation (Linux, Windows, macOS) with no LLM, no repo clone,
  no factory. Shipped as one binary per OS from its own CI.
- **The factory's parsers and walkers become a library**, not a copy.
  Distribution name `vcf-cf-tooling-core`. Import name: `vcfcf` (decided 2026-09-14), packages `vcfcf_<name>`.
  Never `vcfops-*`: that implies ownership we do not have.
- **Publish the wheel alongside buildkit** (GitHub Release attachment) for
  now. The migrator pins by URL. Move to PyPI when a second consumer or a
  `uvx` install path needs version-range resolution. The switch is one
  workflow change plus one pin edit.
- **The library gets its own tag line** (`vcf-cf-tooling-core` 0.1.x),
  independent of factory release tags, so factory releases do not churn
  the migrator's pin.
- **Offline first.** MVP input is an export zip. Live connect, dry-run
  import, cross-version translation, and outbound-settings scrubbing are
  follow-on releases unless the M3 spec pulls one in.

## Reality checks carried into the spec

- No dashboard renderer exists. Factory previews are hand-authored HTML
  mocks (RULE-011). The migrator needs a real layout-plus-widget mock
  renderer. Largest new piece; phase it (layout skeleton, then widgets).
- Extractor coverage is dashboards, views, super metrics only. The
  migrator needs the full graph including alerts, symptoms, policies,
  notifications, custom groups, reports.
- "Custom" is a diff against stock content for the version, and a
  customized built-in is its own category (modified stock).
- Outbound settings carry secrets and hostnames (rule 19).

## Milestones

| # | What | Where | Gate |
|---|---|---|---|
| M0 | Fix the walker and renderer issues below. **Done 2026-09-14**: PRs #155, #156, #157 merged; zips rebuilt, dashboard.json byte-identical across builds | this repo | reviewer, PR |
| M1 | Rename import namespace `vcfcf_*` to the chosen name. Mechanical, no behavior change, one PR | this repo | Scott picks the name; reviewer, PR, factory tag |
| M2 | Carve pure parse/walk/build code into `vcf-cf-tooling-core` with its own `pyproject.toml`; factory imports it in-tree; CI builds and attaches the wheel on a library tag | this repo | one PR per package, reviewer each |
| M3 | Migrator spec (`knowledge/designs/content-migrator-v1.md`) and repo skeleton: `sentania-labs/vcf-cf-migrator`, gitignored clone plus registry line like SDK adapters, CI with three-OS PyInstaller matrix, empty app that starts and shows the library version | new repo | Scott approves spec and repo creation |
| M4 | Migrator MVP: load export zip, tree with dependencies, mock preview, select, emit import bundle | new repo | qa pass against a real export |

Open questions for M3, answered by Scott before the spec is written:
offline only or live from day one; same version only or 8.x to 9.x;
outbound settings in v1; customer-run with no LLM or consultant-run.

## M0: issues fixed before the namespace sweep

Status: complete. Fallout: DEF-021 (four unquoted SM columns in the
vCommunity vSphere pak) fixed at source in that repo (PR #21 merged),
pak re-release tracked as that repo's issue #22. New follow-ups: #154
(sync CLI runs import before the walker), #158 (duplicate SM name in a
hand-authored manifest).

All live in code the migrator lifts. Fix under the old names, then rename.

| Issue | Why it blocks | Files |
|---|---|---|
| #144 | Dependency walker skips SM to SM references; the migrator tree is built on this walker | `vcfcf_common/dep_walker.py`, `vcfcf_packaging/discrete_builder.py` |
| #146 | View-column SM refs with a mis-cased token render blank; same walker family | `vcfcf_dashboards/render.py`, `vcfcf_packaging/deps.py` |
| #147 | Widget ids use salted `hash()`, so bundle output differs every run; migrator output must be reproducible | `vcfcf_dashboards/render.py` |
| #143 | Describe cache refresh replaces instead of merges; sits inside the carve-out boundary | `vcfcf_packaging/describe.py` |

Parallel plan: three isolated worktrees, split by file ownership.
#144 alone; #146 plus #147 (and #148's test) together since both edit
`render.py`; #143 alone. Each gets a framework review and its own PR.

## Alongside, order does not matter

| Issue | Note |
|---|---|
| #153 | Defect gate ignores multi-token Affects. Factory plumbing, not library code. |
| #152 | Doctor does not voice the bootstrap `unknown=` key. Factory plumbing. |
| #148 | Pin SM-name case sensitivity with a test. Rides with #146 (same regex). |

Not blocking: #145 (CI investigation, worth understanding before M2 adds
a publish job), #149 (docs).

## Housekeeping

Thirty-odd local branches are squash-merged PRs and five worktrees are
prunable. Deleting them needs Scott's words (rule 12). Not blocking.
