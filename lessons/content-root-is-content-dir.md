# Content root is `content/` — not the repo root

## Symptom

A freshly authored dashboard and two custom groups validated "clean" per the
authoring agent, but `python -m vcfops_dashboards validate` (run by the
orchestrator) did **not** list them — the dashboard count was unchanged and the
custom-group validate showed only the pre-existing group. The new files existed
on disk and parsed fine; they were simply invisible to the loader and would
never have shipped in a content-import.

The files had landed at the **repo root** (`dashboards/…yaml`,
`customgroups/…yaml`) instead of under `content/`.

## Root cause

The factory's canonical content root is **`content/`**. The loaders scan there
and nowhere else:

```
vcfops_dashboards/cli.py:18   DEFAULT_VIEWS      = Path("content/views")
vcfops_dashboards/cli.py:19   DEFAULT_DASHBOARDS = Path("content/dashboards")
vcfops_dashboards/cli.py:211  _cg_dir            = Path("content/customgroups")
```

Every content type lives under `content/` — `content/{supermetrics,views,
dashboards,customgroups,symptoms,alerts,recommendations,reports,
managementpacks,bundles}`.

But the author-agent prompts (and the CLAUDE.md roster) historically named the
**bare** legacy paths (`views/`, `dashboards/`, `customgroups/`). This is the
residue of an incomplete migration: the directory move + loader update happened,
the prompts and docs did not. Three things made it bite unevenly:

1. **`view-author` self-corrected** by globbing "existing `views/*.yaml`
   (idiom)" — `content/views/` is heavily populated, so it inferred the real
   location despite the stale prompt. That masked the bug for a long time.
2. **`customgroup-author`** had only one existing group to glob and followed its
   literal prompt path, creating a brand-new repo-root `customgroups/`.
3. **`dashboard-author`** was actively *misled* by the second dashboard
   location (see below).

## The two-location trap (dashboards specifically)

There are genuinely **two** dashboard directories, with different jobs:

| Location | Purpose | Install path |
|---|---|---|
| `content/dashboards/` | Factory content | content-import zip |
| `dashboards/` (repo root) | Dashboards embedded **inside an SDK-adapter pak** (e.g. `content/sdk-adapters/compliance/adapter.yaml` bundles `dashboards/compliance-overview.yaml`) | pak build/bundling |

The repo-root `dashboards/` holds **real, git-tracked, in-use** pak content
(`compliance-overview`, `mssql-query-performance`, `oracle-query-performance`).
A `glob` for `dashboards/*.yaml` therefore returns legitimate-looking siblings
at the WRONG path for a content-import dashboard. **Do not delete the repo-root
`dashboards/` files** — they are live pak content, not cruft.

## Fix

- Authoring agents target `content/<type>/` for all content-import content
  (`.claude/agents/{view,dashboard,customgroup}-author.md` updated; the
  dashboard prompt now carries the two-location table explicitly).
- CLAUDE.md roster "Writes to" column corrected to `content/<type>/`.
- SDK-adapter-bundled dashboards remain the SDK-adapter author's job and live
  under the adapter tree / repo-root `dashboards/` — that exception is called
  out in the dashboard-author prompt.

## Tells / how to catch it fast

- After an author returns "validates clean," the **orchestrator's** corpus
  validate is the real gate. If the new object's name/UUID is absent from the
  validate listing, it's in the wrong directory — check the repo root.
- `git status` showing a new top-level `views/`, `dashboards/`, or
  `customgroups/` path (rather than under `content/`) is the signature.

## Meta-lesson

When migrating a directory layout, grep the **agent prompts and CLAUDE.md** for
the old path, not just the Python. A loader that prefers the new path while the
prompts name the old one produces silent, intermittent misfiles that only the
agents which happen to glob will dodge.
