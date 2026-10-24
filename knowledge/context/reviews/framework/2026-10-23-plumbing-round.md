# Framework review: plumbing round (#233, #235, #216, #232, #154, #158, #166, #165, #167, #239), 2026-10-23

Branch `fix/plumbing-233-235-216-232-154-158-166-165-167`, ten commits on
`origin/main` (`10b1ad0`), head `639be3f`. Reviewed in a detached worktree
with the gitignored pak clones symlinked in; baseline built from a second
detached worktree at `origin/main`. Both worktrees removed afterwards.

**Verdict: CHANGES REQUESTED.** 1 BLOCKING, 4 WARNING, 4 NIT.

The one blocker is #167. The repo's own export corpus has a dashboard that
stayed half-built for 19 days with every adapter it waits on installed. The
new check would print "NOTE: still finishing its import (normal for some
minutes...)" for it, and bundle sync would report it `ok` with no message at
all. The issue asked for exactly that case to be reported after a poll.

## Re-run evidence

| Check | Result |
|---|---|
| Default suite (`pytest`, clones linked) | 2215 passed, 9 skipped, 131 deselected. Matches the author's claim |
| Full suite (`pytest -m "" -n 8 --dist=loadgroup`) | 2346 passed, 9 skipped |
| Seven-package validate chain | all rc=0 |
| Render regression: `vcfcf_packaging build --all` + all 12 release manifests + `vcfcf_dashboards package`, main vs branch, every zip and nested zip extracted and diffed | Content byte-identical. Only differences: `vcfops_manifest.json` `built_at`, `install.py` docstring, the offline package's time-based `*L.v1` name (pre-existing), and zip metadata of the inner dashboard zip (its 5 members are byte-identical) |
| `install.py` main vs branch, AST compare with docstrings blanked | identical: the #166 edit is comment-only |
| `CURRENT_TEMPLATE_VERSION` | not bumped. Correct here: shipped `install.py` behaves the same, so old bundles are not stale |
| #233 against real clones (`synology`, `unifi`, `compliance`) | each resolves its own repo root and gets real per-build history (65 to 100 lines). The old code produced the stub |
| #167 classifier over the 5 migrator-corpus exports | 0 disagreements between `entryKeys` and `importComplete` across 148 dashboards. `entryKeys` keys are `resource`, `resourceKind`, `uuid`, so the fixtures match the real shape |
| Em-dashes in added lines and commit messages | 0 |

Stale-zip list: #158 touches `src/vcfcf_core/packaging/assembly.py` (adds
`error_cls=` only) and #166 touches `src/vcfcf_packaging/templates/install.py`
(docstring only). Both claims are confirmed. Built bundle content does not
change, so a rebuild is cosmetic.

## BLOCKING

### B1. #167: "settling" says "normal" for a dashboard that is stuck, and the poll the issue asked for is missing

`src/vcfcf_core/dashboards/materialization.py:132-137` (SETTLING message),
`:104-112` (classification), `src/vcfcf_dashboards/handler.py:104` (settling
maps to a bare `ok`),
`knowledge/context/api-surface/dashboard_import_two_phase_materialization.md:308`
("the settling case completes on its own").

The issue's third bullet says: "`importComplete: false` and old, or still
false after a sensible poll: report it". The branch never polls. Any
incomplete dashboard whose pending adapter kinds are all installed is SETTLING,
which means a NOTE that calls it normal in the CLI and silence in bundle sync.

Counterexample from the corpus the commit cites,
`content/migrator/corpus/scott-8.18.7-2026-09-14.zip`:
`[VCF Content Factory] VCF License Consumption Overview` was last written
2026-08-26 at 4:10 PM and was still `importComplete: false` at the
2026-09-14 export, 19 days later. Its pending kinds are `CASAdapter`,
`NSXTAdapter`, `VMWARE` and `VMWARE_INFRA_HEALTH`, and
`2026-08-26-vcf-license-consumption-recon-818.md` records all four as
installed on that 8.18.7 instance. Its `entryKeys.resource` names specific
resources: `License Usage`, `NSX World`, `Automation World`. Two things
follow:

- Phase 2 can stall with every adapter installed. Plausibly a named resource
  is missing (not proven, since that would need a live read). The classifier
  never reads `entryKeys.resource` names, so it cannot see that cause.
- The doc claim that settling "completes on its own" is contradicted by the
  factory's own evidence.

So on this platform the new check prints reassurance for a broken dashboard.
That is the reports-green-while-broken class (dimension 8). It also means
"Closes #167" overstates what shipped.

Smallest correct fix:
1. Add a bounded re-check: after a short wait, one more export. A dashboard
   still incomplete after it is reported as a WARNING that names the pending
   adapter kinds and the `entryKeys.resource` names. It need not fail the
   sync.
2. Drop "normal" from the settling message, or keep it only for the first
   read before the re-check.
3. Carry the same message into the bundle-sync item (`warn`, not a bare `ok`).
4. Correct the doc line, citing the 8.18 counterexample.

If the poll is deferred, change the commit to "Refs #167" and keep the issue
open for that part.

## WARNING

### W1. #167 is closed, but the shipped installer does not run the check

`src/vcfcf_packaging/templates/install.py` is unchanged in behaviour, and the
doc says so (`dashboard_import_two_phase_materialization.md`, "The shipped
`install.py` and the pak installer do not run this check"). The issue asks
for "the installer". The distributed `install.py` is the only installer a
downstream operator runs, so that path still reports silent success. The
limitation is stated loudly, so this is a WARNING, not a BLOCKING. Fix: either
extend `install.py`, which needs a `CURRENT_TEMPLATE_VERSION` bump, or file a
follow-up for it and use "Refs #167".

The check has also never been run live (the commit says "Not yet run against
a live instance"), and it can now fail a previously green sync (rc 1, or a
failed item). Before merge, run one `vcfcf_dashboards sync` against devel
through `content-installer`. That proves the DASHBOARDS export plus
`/api/adapterkinds` read and gives no false STALLED on factory content
(adapter kinds `VMWARE`, `NSXTAdapter`, `CASAdapter`, `VMWARE_INFRA_HEALTH`,
`VirtualAndPhysicalSANAdapter`).

### W2. #216: a pak with a zero-byte `signature.cert` counts as signed, so the preflight is skipped

`src/vcfcf_managementpacks/installer.py:120-133` (`_pak_is_signed`).
`knowledge/context/mpb/mpb_pak_signing_chain.md` §"Community paks: unsigned"
says that community paks (vCommunity) ship `signature.mf` plus a **zero-byte**
`signature.cert`, and are unsigned. The check tests file presence only, so
such a pak skips the switch read. The upload then fails with the raw key,
which the translation now catches, so the operator still gets the steps, but
only after a wasted upload. Factory-built paks carry neither file (checked 8
recent `dist/*.pak`), so factory paks always get the preflight. Fix: treat a
`signature.cert` of size 0 as unsigned, and add a test.

Verified correct: a present `false` is the only thing that stops the upload;
a missing key, a 404 or any other read failure proceeds. 8.18 has no key, per
`2026-10-15-devel-8-18-recon.md` §3. `ignoreSignatureChecking=true` is
unchanged.

### W3. #158 fixed one of the name maps that resolve `@supermetric:`; the SDK pak path is still last-wins

`src/vcfcf_managementpacks/sdk_builder.py:1928` builds
`{sm.name: sm.id for sm in supermetrics}` from `adapter.yaml`
`bundled_content.supermetrics`. That list is hand-authored, bypasses the
walker, and is the same class as the manifest path #158 describes. Two
bundled SMs with one display name still resolve silently to the last one.
This branch touches `sdk_builder.py` (#233), so per CLAUDE.md rule 9 it is
fixed here rather than in a follow-up. Fix: build the map with
`sm_name_to_uuid_map(supermetrics, error_cls=SdkBuildError)`. Same class, and
lower stakes because the import is equally last-wins:
`src/vcfcf_supermetrics/cli.py:160` (the new #154 preflight map).

### W4. #232: bundle sync now reaches the reports handler, which reloads with CWD-relative factory defaults

`src/vcfcf_reports/handler.py:45,58` calls `load_file(Path(p))` with the
defaults `views_dir="content/views"` and `enforce_framework_prefix=True`.
`load_bundle` already loaded the same reports with the bundle's own
`report_views_dir` and `factory_native`. Before this branch the handler was
unreachable from bundle sync. Now a third-party PROJECT.yaml carrying reports
fails at sync on view resolution or the prefix check, even though its build
validates. So does any sync run from outside the repo root. The corpus has
none today: the only bundle with reports is `vks-core-consumption-bundle`,
and its report loads from the repo root. The failure is loud, not silent.
Fix: pass the bundle context through, or have `sync_bundle` hand the handler
the already-loaded `ReportDef`s.

## NIT

- **N1** `src/vcfcf_core/extractor/extractor.py:216`: the comment says "a
  monkeypatch ... on either name sees the other". That is false: rebinding
  one module attribute does not rebind the other. Identity holds; the
  monkeypatch claim does not.
- **N2** `src/vcfcf_extractor/extractor.py:45,51`: the factory itself still
  imports the underscore aliases. Switch it to the public names now, so
  dropping the aliases next release breaks nothing in the factory.
- **N3** `src/vcfcf_dashboards/cli.py:541`: the CLI runs the materialization
  check even when the import skipped every dashboard. The handler skips it in
  that case. The CLI can then fail a sync (rc 1) over a pre-existing stuck
  dashboard that this run did not import. Pick one behaviour for both paths.
- **N4** PR body: say that the stale-zip-list edits (`assembly.py`,
  `templates/install.py`) leave built content byte-identical, so the
  `content-packager` rebuild is cosmetic (only the `install.py` docstring
  changes) and no template-version bump is needed.

## Proven safe (no finding)

- #235: every `solution_action` carries `(10, 120)`. Settle re-reads get only
  the time left in the window, and a timeout becomes RuntimeError. The test
  uses a real listening socket that never answers. `mainAction=install` and
  `remove` are async with polling (`pak_ui_upload_investigation.md`
  §wizard), so 120s cannot cut a legitimate call short.
- #232: `SYNC_CONTENT_TYPES` keys match the `Bundle` attribute names exactly,
  so nothing collides. `KNOWN_MANIFEST_KEYS` covers every key in `bundles/*.yaml`
  and `third_party/*/PROJECT.yaml`. Over the corpus: one correct WARN
  (`storage-path-monitoring`, 1 recommendation; the alerts handler upserts via
  REST and installs no recommendations) and one for `idps-planner`
  `builtin_metric_enables`. Empty `managementpacks: []` stays silent.
  `reports` sync_order 7 runs after views (3).
- #154: the preflight and the import resolver both use `SM_CROSSREF_RE`
  (single and double quotes, any token case, absorbed prefixes), and both
  resolve against the batch first, then the target. A near-miss token is not
  caught by the preflight, but the import still hard-errors on it, as before.
  The issue's second ask (give dashboards sync the SM batch) is not done; the
  commit says so and uses "Refs".
- #158: same SM listed twice (same id) is accepted; different ids raise
  `BundleValidationError` naming both files. Corpus bundles all build.
- #165: the public names are importable from `vcfcf_core.extractor`, and the
  aliases are the same objects.
- #166, #239: comment and help text only. No remaining `qa` profile string in
  `src/` help.
- Materialization runs only in `vcfcf_dashboards sync` (with a non-empty
  dashboard list) and in the bundle-sync dashboards handler after a FINISHED,
  not-all-skipped import. It does not run for views-only syncs, reports,
  `install.py` or paks.
