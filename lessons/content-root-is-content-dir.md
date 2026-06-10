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
| `dashboards/` (repo root) | Dashboards bundled **inside a Tier 1 MP pak** (e.g. the mssql/oracle MPs) | pak build/bundling |

The repo-root `dashboards/` holds **real, git-tracked, in-use** Tier 1 MP pak
content (`mssql-query-performance`, `oracle-query-performance`). A `glob` for
`dashboards/*.yaml` therefore returns legitimate-looking siblings at the WRONG
path for a content-import dashboard. **Do not delete the repo-root `dashboards/`
files** — they are live pak content, not cruft.

**Update (2026-06-08):** Tier **2** SDK-adapter bundled content no longer lives
at the repo root. Each SDK adapter is now its own independent repo (cloned into
the gitignored `content/sdk-adapters/<name>/`), and its bundled views/dashboards
live **inside that adapter dir** (`content/sdk-adapters/<name>/views|dashboards/`),
resolved relative to `adapter.yaml` — not the factory root. Compliance's
`compliance-host-overview` / `compliance-overview` moved into the compliance repo
accordingly; only the Tier 1 mssql/oracle files remain at the repo root.

## Fix

- Authoring agents target `content/<type>/` for all content-import content
  (`.claude/agents/{view,dashboard,customgroup}-author.md` updated; the
  dashboard prompt now carries the two-location table explicitly).
- CLAUDE.md roster "Writes to" column corrected to `content/<type>/`.
- SDK-adapter-bundled (Tier 2) dashboards live **inside the adapter's own repo**
  (`content/sdk-adapters/<name>/dashboards|views/`), resolved relative to
  `adapter.yaml`. Tier 1 MP-bundled dashboards remain at the repo root.

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
