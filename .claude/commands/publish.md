---
description: Publish every bundle, MP, and discrete content item marked `released: true` to the vcf-content-factory-bundles distribution repo. Validates, builds, syncs artifacts, regenerates the README between AUTO markers, commits, and pushes.
---

You are the VCF Content Factory orchestrator. The user invoked `/publish` with the following args:

```
$ARGUMENTS
```

## Your job

Ship every piece of content marked `released: true` in the factory repo to
`/home/scott/pka/workspaces/vcf-content-factory-bundles/`, regenerate the
README, commit, and push. The full design is in
`designs/publish-command-v1.md` — consult it if anything here is ambiguous.

## Prerequisites

- Working directory: `/home/scott/pka/workspaces/vcf-content-factory/`
- Distribution repo already cloned at
  `/home/scott/pka/workspaces/vcf-content-factory-bundles/` on branch `main`
  with a clean working tree and up-to-date with `origin/main`. If dirty
  or behind, stop and tell the user — do not auto-stash or force push.
- `$ARGUMENTS` optionally contains `--force` to override the
  version-guard (re-ship a version already present in the bundles repo).
  Parse it out up front.

## Flow

### 1. Validate everything

Run the full validation sweep. Abort if anything fails:

```
python3 -m vcfops_supermetrics validate && \
python3 -m vcfops_dashboards validate && \
python3 -m vcfops_customgroups validate && \
python3 -m vcfops_symptoms validate && \
python3 -m vcfops_alerts validate && \
python3 -m vcfops_reports validate && \
python3 -m vcfops_managementpacks validate
```

### 2. Enumerate released units

Scan for everything marked `released: true`:

- **Bundles:** grep `released: true` across `bundles/*.yaml` and
  `bundles/third_party/**/*.yaml`. Classify as first-party vs
  third-party by path.
- **Management packs:** grep `released: true` across
  `managementpacks/*.yaml`.
- **Discrete content items:** grep `released: true` across
  `supermetrics/`, `dashboards/`, `views/`, `reports/`, `alerts/`,
  `customgroups/`. (Symptoms and recommendations are never discretely
  released — they ride with their parent alert.)

Show the user the full published set before proceeding. If the list
is empty, stop.

### 3. Version guard

For each released unit, compute the expected artifact filename
(bundle zip, `.pak`, or discrete zip) and check whether a file with
that exact name already exists in the bundles repo. If yes, compute
the content hash of the existing file and the about-to-be-built
artifact; refuse to publish if they differ unless `--force` was
passed. Report the conflict with the version in the YAML vs the
existing version on the bundles repo side.

Duplicate-version republish = silent regressions. Always refuse
without explicit force.

### 4. Build

Delegate the heavy lifting — do NOT run builds inline.

- **Bundles:** delegate to `content-packager` with the list of
  released bundle manifests. It runs `python3 -m vcfops_packaging
  build <manifest>` for each.
- **Management packs:** delegate to `tooling` (or use the MP builder
  directly — `python3 -m vcfops_managementpacks build <mp-yaml>`)
  for each released MP.
- **Discrete items:** delegate to `content-packager` to run
  `python3 -m vcfops_packaging build-discrete <type> <item-name>`
  for each released item.

Collect the produced artifact paths.

### 5. Stage to the bundles repo

Rsync-style update of `/home/scott/pka/workspaces/vcf-content-factory-bundles/`:

```
/
  README.md, LICENSE           (preserved, README regenerated below)
  Bundles/                     first-party bundle zips
  ThirdPartyBundles/           third-party bundle zips
  ManagementPacks/             .pak files
  ContentComponents/
    Dashboards/
    SuperMetrics/
    Views/
    Reports/
    Alerts/
    CustomGroups/
```

For each target directory:

- Copy newly-built artifacts in.
- If an artifact exists in the destination whose name matches a
  previously-released unit that is no longer `released: true`,
  delete it (release revocation). Use `git rm` so the delete is
  tracked.
- Do not touch files outside these directories.

### 6. Regenerate the README

Run the auto-gen helper:

```
python3 -m vcfops_packaging update-readme \
    /home/scott/pka/workspaces/vcf-content-factory-bundles/README.md
```

The helper rewrites the tables between `<!-- AUTO:START <section> -->`
and `<!-- AUTO:END -->` markers. Sections:
`bundles`, `third-party-bundles`, `management-packs`, `dashboards`,
`supermetrics`, `views`, `reports`, `alerts`, `customgroups`.
Hand-written prose outside the markers is preserved.

If the README file doesn't yet have the markers, stop and report
— a human needs to lay out the sections first.

### 7. Commit and push

From the bundles repo working tree:

1. `git add -A` the affected paths (be explicit — don't blindly
   `git add .`).
2. `git status --short` to confirm exactly what's staged. If
   nothing changed, report "No changes to publish" and stop —
   don't create an empty commit.
3. Compose a commit message summarizing the delta:
   ```
   Publish: +<added units>, ~<updated units>, -<removed units>

   Added:   <list with versions>
   Updated: <list with old → new versions>
   Removed: <list>
   ```
4. `git commit -m "<message>"`.
5. `git push origin main`.

### 8. Report

Tell the user:

- Commit SHA in the bundles repo
- Full add/update/remove delta
- Any units that were skipped (version-guard conflicts, force-needed)
- Any warnings from builds

## Hard rules

- **Never push without user confirmation on the first run.** After
  step 5 (stage), show the user the diff summary (`git status
  --short` output) and get a yes before committing. Subsequent
  `/publish` invocations inside the same session may skip the
  confirmation if the user explicitly says "auto-confirm future
  publishes".
- **Never edit README text outside the AUTO markers.** The helper
  enforces this; don't route around it.
- **Never touch the bundles repo's git history.** No force push,
  no rebase, no amend.
- **Never publish anything not marked `released: true`.**
- **Never silently downgrade a version guard.** `--force` must be
  an explicit flag, never a fallback.

## Failure modes to surface clearly

- Validation failed → stop; report which package failed and the
  error line.
- Bundles repo dirty or not on `main` → stop; tell the user to
  clean up first.
- Version conflict without `--force` → list the conflicts; tell
  the user to bump versions in YAML or re-invoke with `--force`.
- Missing AUTO markers in README → stop; ask for manual setup.
- `git push` rejected → report the rejection; do not attempt
  pull-rebase-push automatically.

## Notes

- The authored-content "ALL content creation requires plan approval"
  rule does not apply to `/publish` — this is a mechanical ship,
  not content authoring.
- MPs keep their existing MPB 4-part external version in the `.pak`
  filename; the new internal `version:` field on MP YAML is used
  only for the version guard.
- Third-party bundle filenames are whatever the upstream author
  chose (e.g. `IDPS Planner.zip`); the factory prefix is not
  applied to them.
