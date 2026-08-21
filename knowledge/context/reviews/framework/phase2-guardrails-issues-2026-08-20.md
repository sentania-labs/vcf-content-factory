# Framework review: phase2 guardrails, issues #85/#90/#92/#94/#96/#97

- **Date:** 2026-08-20
- **Reviewer:** framework-reviewer
- **Change under review:** uncommitted working-tree diff against `HEAD`
  (`9d52c2f`) on branch `phase2-guardrails-and-issues`:
  `src/vcfops_common/doctor.py`, `src/vcfops_dashboards/{cli,client,handler}.py`,
  `src/vcfops_packaging/{audit,cli}.py`,
  `src/vcfops_packaging/templates/install.py`,
  `tests/test_common_doctor.py` (+19), new
  `tests/test_dashboard_import_all_skipped.py` (14), new
  `tests/test_analyze_requires_bundle_content.py` (6), plus doc edits to
  `knowledge/context/wire-formats/wire_formats.md`,
  `knowledge/context/api-surface/content_upload_methodology.md` and
  (orchestrator-owned) `.claude/skills/vcfops-api/SKILL.md`
- **Prior history:** `common-doctor-2026-08-20.md` (6 rounds),
  `common-setup-2026-08-20.md` (2 rounds)
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 6 WARNING, 7 NIT)

## Checks re-run (independent, not taken on faith)

| Check | Result |
|---|---|
| Full default suite (`-m "not slow"` per pyproject addopts) | **827 passed, 4 skipped, 178 deselected** (was 788 at setup round 2; +39 = 19+14+6 exactly as claimed) |
| Full validate chain (7 packages) | all green |
| Slow tier `test_publish_phase3.py` + `test_publish_pr_mode_v4.py` (`-m ""`) | run independently; **23 of 52 completed, 0 failures** at 34 min of real git work, run still in progress (see "Slow-tier coverage") |
| Doctor: real CLI, healthy repo, no args | exit 0, **exactly one green line** |
| Doctor: `--help` / `-h` / `--bogus` / `--password=...` through the real CLI | exit 0 in all cases; usage on help, stderr notice on stray args |
| Doctor: 10 corrupt `.bootstrap-status` shapes through the real `run_doctor` | rc 0 in every case, no crash; **1 unbounded echo found, W-3** |
| Dashboards: mixed-content-type import result through the real `DashboardsHandler.sync`, `cmd_sync`, `_install_dashboards` | **false "changed nothing" on a successful dashboard import, B-1** |
| `analyze` on a real staged bundle (`build`-produced layout) | exit 0, unchanged |
| `analyze` on a `.zip` (`dist/bundles/storage-path-monitoring.zip`) | exit 1 with the new message (issue #85 satisfied) |
| `analyze` on `dist/vcommunity-dev-build/extracted` (a pak extract, not a bundle) | **still exit 0, "no metric references found", nothing inspected, W-6** |
| Render regression / pak-compare (dimensions 5, 6) | n/a: no renderer, loader or builder file in the diff (`src/vcfops_dashboards/render.py` untouched) |
| Stale-zip trigger (dimension 9) | **fires**: `src/vcfops_packaging/templates/install.py` is in the diff; no rebuild flagged anywhere, W-5 |
| Escape anchors `00d3382` / `6c59f6b` | n/a: no pak-specific default, coordinate convention, or key/label derivation touched; the #97 change is uniform across all three output paths |
| Em-dash scan over added lines (rule 7) | **2 hits, W-2** |

## Issue-by-issue disposition

| Issue | Status |
|---|---|
| #90 item 1 (argv ignored) | fixed and verified: `--help`/`-h`/`help` prints usage and returns 0; a stray arg gets an honest stderr notice and the report still runs (hook contract preserved) |
| #90 item 2 (diverged shadowed by dirty) | fixed and verified: both lines now render, `git pull --ff-only` still absent |
| #90 item 3 (absurd `failed=`) | fixed and verified: `-5` and 400-digit counts degrade to "unparseable", clipped |
| #92 (phantom script name) | fixed and verified: `GARBAGE PARTIAL LINE cloned=1` produces no report line at all; see W-4 for the cost of the tightening |
| #94 item 1 (clock skew silent) | fixed and verified: a `+72h` stamp reports skew; a `-0.2h` jitter stays silent |
| #94 item 2 (verbatim echo) | fixed **for `stamp`, `failed`, `failures`** only; the script-name field is still unbounded, W-3 |
| #94 item 3 (checklist ignores age) | fixed and verified: 100-day-old run is `fail`, future run is `unknown`, fresh is `ok` |
| #96 item 1 (`probe=` seam) | dropped; pinned by a signature test |
| #96 item 3 (absolute path) | fixed and verified: `[checked: current + .venv/bin/python3]`, no absolute path in the line |
| #85 (analyze on a non-bundle path) | fixed for the `.zip` and no-`content/` cases; incomplete for the general "non-bundle directory" class, W-6 |
| #97 (dashboard import ghost/all-skipped) | detection implemented on all three paths, but mis-attributed across content types, B-1 |

## BLOCKING

### B-1. A successful dashboard import is reported as "changed nothing / NOT updated" when the views co-shipped in the same zip were skipped

Files: `src/vcfops_dashboards/handler.py:36-59` (`_all_skipped_message`,
which calls `all_skipped_content_types(api_result)` with **no**
content-type filter), used at `handler.py:115` and `handler.py:287`;
`src/vcfops_dashboards/cli.py:346` (same unfiltered call);
`src/vcfops_packaging/templates/install.py:1454` (filtered to
`("DASHBOARDS", "VIEW_DEFINITIONS")`, but flags if **either** type is
all-skipped and then suppresses the success line for the dashboard).

Every one of these three paths imports **two** content types in one zip:

- `DashboardsHandler.sync` (`handler.py:270-276`) deliberately re-imports
  the views that `ViewsHandler` (`sync_order = 3`) imported seconds
  earlier in the same run: its own comment says "The views are already
  installed from the views sync step; re-importing them here is
  idempotent and harmless."
- `cmd_sync` builds one zip from views + dashboards.
- `_install_dashboards` builds one zip from `views_content.xml` +
  `dashboard.json`.

So the summaries are routinely mixed. Driven through the real code with
`DASHBOARDS imported=1 skipped=0` and `VIEW_DEFINITIONS imported=0
skipped=2`:

```
HANDLER status: ['warn']
HANDLER message: import finished but changed nothing (VIEW_DEFINITIONS
  imported=0 skipped=2); the existing object on the instance was NOT
  updated. Verify on the instance, or delete and re-sync to force an update.

cmd_sync stderr:
  WARNING: content type VIEW_DEFINITIONS: imported=0 skipped=2 - the import
    finished but changed nothing on the instance.
  WARNING: affected content in this bundle: [VCF Content Factory] Capacity
  WARNING: existing objects with the same ids/names were left as they were...

install.py:
  WARN  Import finished but changed nothing (VIEW_DEFINITIONS imported=0
    skipped=2); existing content was NOT updated: [VCF Content Factory]
    Capacity. ...
  -> ctx["warnings"] non-empty -> installer sys.exit(2), and the
     "Imported N view(s) + 1 dashboard" success line is suppressed
```

The dashboard **was** imported (`imported=1` is in the same envelope) and
the message says it was not. Three separate defects follow:

1. **A false statement to the operator**, contradicted by data the code
   already has in hand.
2. **Cry wolf, on the normal path.** This is the question the brief asked
   me to judge: yes, there is a path where this fires on a perfectly
   ordinary sync. Whether it fires *today* depends on whether the
   importer skips an identical re-import of a view. The repo's own
   authority cuts both ways and neither settles it:
   `knowledge/context/wire-formats/wire_formats.md:231` says the importer
   "treats it as already exists and returns `skipped=1`", while
   `knowledge/context/api-surface/content_api_surface.md:29` calls the
   content zip the "only create/update path" for views. Under the skeptic
   default the burden is on the code, and the code is constructed to
   re-import content it just imported. A warning that fires on a
   successful sync is exactly how operators learn to ignore the signal
   the issue exists to create.
3. **Untested in the direction that matters.** All 14 new tests use a
   single-content-type envelope
   (`tests/test_dashboard_import_all_skipped.py:29-41`). The mixed
   envelope, which is the shape these three call sites actually produce,
   is not covered. Same shape as doctor round-5 W-6.

Authority: `knowledge/context/wire-formats/wire_formats.md:254-278` (the
section this change added) scopes the signal per content type
(`DASHBOARDS` / `VIEW_DEFINITIONS`) and describes the remedy as naming
"the affected content"; the code names content that was not affected.
Dimension 8 in reverse: a loud but wrong signal is a downgrade of a
signal.

Smallest correct fix: attribute per content type at each call site.
`DashboardsHandler` flags on `DASHBOARDS` only, `ViewsHandler` on
`VIEW_DEFINITIONS` only (`all_skipped_content_types` already takes the
filter argument; use it), `cmd_sync` names dashboards for a `DASHBOARDS`
flag and views for a `VIEW_DEFINITIONS` flag, and `_install_dashboards`
reports per flagged type rather than suppressing the whole success line
when only views skipped. Add a mixed-summary test to each of the three
paths asserting that the un-skipped type is reported ok.

## WARNING

### W-1. `install.py` exit code changes from 0 to 2, contrary to the stated claim

`templates/install.py:1470` appends to `ctx["warnings"]`, which flows to
`all_warnings` (`:2364-2368`) and into the `if enable_warnings or
other_warnings:` branch that ends in `sys.exit(2)` (`:2388`). Verified by
driving the real `_install_dashboards`: any flagged import now yields a
non-empty warnings list, i.e. `Done with N warning(s):` and exit 2 where
the previous behavior was `Done. All content installed successfully.` and
exit 0. The author's disclosed behavior deltas were only "analyze exits
1" and "`checked_interpreter` is repo-relative"; the claim "leave exit
codes unchanged" is true for the two sync paths and **false for the
packaged installer**, which is the artifact operators actually run. With
B-1 unfixed the trigger is also broader than intended (a skipped view is
enough). Either disclose it in the PR body as an intended third delta, or
keep the installer's exit code at 0 for this warning class and rely on
the printed `WARN` line.

### W-2. Em-dash in operator-facing source and in a knowledge doc (rule 7)

Rule 7 is absolute and names code and generated docs explicitly; prior
rounds tracked the em-dash scan as a standing check and it was 0 in both
predecessor reviews.

- `src/vcfops_dashboards/cli.py:352`: `f"skipped={skipped} — the import
  finished but changed "` (printed to the operator).
- `knowledge/context/api-surface/content_upload_methodology.md:65`:
  `**evidence only for SUPER_METRICS** — do not assume they generalize.`

### W-3. Untrusted-field truncation is not applied everywhere such a field is echoed

The brief asked this explicitly. Answer: no. `_clip` covers `stamp`
(`doctor.py:1041`, `:1047`), `failed` (`:1063`) and `failures`
(`:1069`, 200 chars), but the field-2 **script name** is echoed verbatim
at `doctor.py:1036/1041/1047/1053/1060/1066/1071` and
`_SCRIPT_NAME_RE = ^bootstrap_[a-z_]+$` places **no length bound** on it.
Probed through the real `run_doctor` with a line whose field 2 is
`bootstrap_` + 50,000 `a`:

```
rc=0, total emitted output = 100,910 characters (two lines)
```

That is the exact failure mode issue #94 item 2 describes (a corrupt file
dumping thousands of characters into session context every session),
left open at the one site the regex tightening newly legitimizes. Fix:
`_clip(script)` at the echo sites, or bound the regex
(`^bootstrap_[a-z_]{1,40}$`).

### W-4. `_SCRIPT_NAME_RE` rejects plausible future script names, and nothing ties it to `KNOWN_BOOTSTRAP_SCRIPTS`

`^bootstrap_[a-z_]+$` (`doctor.py:681`) admits only lowercase and
underscore. This repo's own script-naming house style uses digits
(`scripts/normalize_scg_v9.py`, `scripts/vks_marker_recon_v8.py`,
`scripts/normalize_scg_v8.py`), so `bootstrap_scg_v9` or
`bootstrap_paks2` is a realistic future name; a writer that emits
`bootstrap_references.sh` in field 2 is also rejected. Verified: both
`bootstrap_paks2` and `bootstrap-paks` lines are dropped silently.

The consequence depends on whether the name is also in
`KNOWN_BOOTSTRAP_SCRIPTS`: if it is, the line is dropped and the doctor
reports "no run recorded for &lt;script&gt;" forever, which nothing the
operator does can clear. That is precisely the W-5 class from doctor
round 5 (a permanent, unactionable delta line is how operators learn to
ignore the doctor), reintroduced through a second, independent naming
gate. The near-term trigger is issue #89's Windows port, whose author
must match this regex without any cross-check telling them so. Fix:
derive the guard from `KNOWN_BOOTSTRAP_SCRIPTS` (accept those names
plus the pattern), or at minimum allow digits and add a module-level
assertion that every `KNOWN_BOOTSTRAP_SCRIPTS` entry matches the regex.

### W-5. Dimension 9: all dist zips are stale and nothing in the change says so

`src/vcfops_packaging/templates/install.py` is in the diff, which per
CLAUDE.md "After tooling changes" makes every distribution zip under
`dist/` stale and requires a `content-packager` rebuild of every manifest
in `bundles/`. Nothing in the diff, the doc edits, or the working tree
flags it. The staleness is not cosmetic here: the whole point of the #97
change is that the *installer shipped to users* stops reporting a
no-op import as success, and every already-built zip still carries the
old `install.py`. The PR must carry the rebuild (or an explicit
follow-up naming it).

### W-6. The #85 guard does not cover the "non-bundle directory" half of the issue it closes

`audit.py:376` / `cli.py:377` gate on `bundle_dir/content` being a
directory. Issue #85 names two cases: "a zip path **or a non-bundle
directory**". The zip case is closed; the directory case is only closed
for directories that happen to lack a `content/` child. A real path in
this repo still slips through:

```
$ python3 -m vcfops_packaging analyze dist/vcommunity-dev-build/extracted --no-live-describe
dependency audit (mode=analyze)
  references: 0 total
  no metric references found
RC=0
```

That directory is an extracted **pak** (`adapters.zip`, `eula.txt`,
`manifest.txt`) whose `content/` holds subdirectories
(`content/supermetrics/`, `content/dashboards/`), not the flat
`content/supermetrics.json` / `views_content.xml` / `dashboard.json`
artifacts `analyze_staged_bundle` reads. Nothing was inspected, and the
operator reads "no metric references found" as "nothing needs enabling",
which is the exact sentence in the issue. A clean discriminator exists
and is present in every real staged bundle: `bundle.json` sits beside
`content/` (verified in `dist/storage-path-monitoring.zip` ->
`bundles/storage-path-monitoring/{bundle.json,content/...}`). Requiring
it keeps `test_empty_content_dir_still_analyzes` legitimate while closing
the class.

## NIT

- N-1. The sync path has no end-of-run warning summary. `syncer.py:170`
  prints the full two-sentence warn message **once per item**, inline
  among the OK lines, and `sync_bundle` returns 0. On a bundle with a
  dozen views the signal repeats a dozen times and then scrolls away with
  a success exit code. `install.py` aggregates its warnings at the end;
  the sync path should get at least a one-line trailer count.
- N-2. `doctor.main()` (`doctor.py:1102-1110`) echoes argv verbatim to
  stderr from a module whose own usage text promises "Credential VALUES
  are never printed (RULE-008)". `python3 src/vcfops_common/doctor.py
  --password=SUPERSECRET` reproduces the value on stderr. Not reachable
  from the hook (which passes no args) and not a RULE-008 violation
  (nothing is written to disk), but it is unclipped and unredacted where
  every other untrusted echo in the module now is not.
- N-3. `.claude/skills/vcfops-api/references/wire-formats.md:71-85`
  ("SM ghost state") is the file `SKILL.md` points at for "full details"
  and did not get the scope note or the dashboards subsection. Its text
  is SM-worded throughout, so it does **not** assert the generalization
  and the three docs the brief named do agree; it is now simply the least
  current of the four. Orchestrator-owned (outside `tooling`'s scope).
- N-4. `_all_skipped_summaries` (`install.py:1284`) duplicates
  `all_skipped_content_types` (`dashboards/client.py:20`). The template
  must stay standalone so the duplication is justified, but nothing pins
  that the two keep the same semantics; one shared test asserting
  identical output on the same fixtures would.
- N-5. `build_checklist`'s `elif stale_ages:` (`doctor.py:909`) precedes
  the failure-count branch, so an old record that also carries failures
  reports only staleness and never names the failures.
- N-6. `_display_path` (`doctor.py:587`) falls back to `path.name` for a
  path outside the root, rendering `/usr/bin/python3` as the bare
  `python3`, which reads as "the ambient interpreter". Unreachable today
  (`venv_python(root)` is always under `root`), but the fallback is the
  ambiguous one.
- N-7. The #85 guard is implemented twice with two slightly different
  message texts (`cli.py:378` vs `audit.py:377`). Belt and braces is
  right for a gate, but the operator sees one wording from the CLI and a
  different one from any other caller.

## Slow-tier coverage (the disclosed gap)

The author's argument holds structurally, and I checked it rather than
taking it: `tests/test_publish_phase3.py` and
`tests/test_publish_pr_mode_v4.py` reference `install.py` only as
**literal README text** (`test_publish_phase3.py:705-710`, asserting the
string `` `python3 install.py` `` appears / is not linked); neither file
imports, executes, or copies the template, and neither touches
`vcfops_dashboards`, `vcfops_common.doctor`, or `vcfops_packaging.audit`.
The diff changes no README-generating code. I also re-ran both files
myself rather than resting on the argument: 23 of the 52 completed with
0 failures over 34 minutes before I stopped waiting. That is a partial
result, honestly reported: the structural argument is what carries the
remaining 29, and it is a sound one.

## Test quality (dimension 10)

The 39 new tests are not tautologies. The doctor set drives the real
`run_doctor` with genuinely corrupt files and asserts on degraded text,
`test_corrupt_line_does_not_create_a_phantom_script` asserts the whole
report collapses to the single green line (the strongest available
assertion), `ts(hours_ago=-72)` makes the clock-skew case relative and
non-rotting, and `test_probe_seam_is_gone` pins a removal by signature.
The analyze set covers the guard, the CLI exit code, and (correctly) the
legitimate empty-`content/` case. The dashboard set covers the detector,
both handlers, the CLI and the template.

The one gap is the one that matters: every dashboard fixture
(`test_dashboard_import_all_skipped.py:29-41`) is a **single**-content-type
envelope, so the mixed envelope these three call sites actually produce
is untested, which is why B-1 shipped. `test_all_skipped_import_is_warn_not_ok`
asserting `not result.has_failures` is good discipline; it pins the
deliberate no-exit-code-flip decision for the sync path.

## Judgment call assessed: WARN but do not retry, exit codes unchanged

- **Not auto-retrying is correct**, and the reasoning is sound: the
  re-import remedy is bisected for `SUPER_METRICS` only
  (`wire_formats.md:250-252`), a blind second dashboard import has never
  been tested here, and RULE-001/002 discipline says do not act on an
  unbisected cause. The three doc edits qualify the over-general claim
  consistently and none of them now asserts the ghost-state finding
  generalizes.
- **Is `status="warn"` surfaced?** Yes, not swallowed:
  `syncer.py:170-172` renders `warn` through `_print_warn` with the
  message. But it is per item, mid-stream, with no summary and rc 0
  (N-1).
- **Does the install-summary warning reach the operator?** Yes, loudly:
  `Done with N warning(s):` plus a `WARN` line, and (undisclosed) exit 2
  (W-1).
- **Is there a cry-wolf path on a normal repeat sync?** Yes, B-1. That is
  the finding that blocks.

## If shipped as-is

An operator who edits one dashboard and re-syncs is told, per dashboard,
that the import "changed nothing" and "the existing object on the
instance was NOT updated", while the envelope in front of the tool says
`DASHBOARDS imported=1`; the same envelope shape makes the packaged
installer print `Done with 1 warning(s)` and exit 2 on a run that
succeeded. Every dist zip still ships the old installer that reports a
genuine no-op import as success. A corrupt `.bootstrap-status` whose
script-name field is long dumps ~100 KB into session context every
session, and a future bootstrap script whose name contains a digit is
dropped silently or, if registered, produces a delta line nothing can
clear.

---

# Round 2 (2026-08-21) - confirm pass on the round-1 remediation

- **Scope:** the round-1 findings only (B-1, W-1 through W-6, and the
  NITs tooling took: N-1, N-4, N-5, plus the upgraded N-2). Dimensions
  cleared in round 1 were not re-walked.
- **Round-2 verdict:** APPROVE. The BLOCKING is resolved and I could not
  reconstruct it on any envelope shape I tried. 0 BLOCKING, 2 WARNING,
  5 NIT. The standing CHANGES REQUESTED is lifted.

## Checks re-run (round 2, independent; every claim re-driven, not read)

| Check | Result |
|---|---|
| Full default suite | **846 passed, 4 skipped, 178 deselected** (matches the claim; was 827) |
| Full validate chain (7 packages) | all green |
| `scripts/path_reference_audit.sh` | exit 0, "clear", plus the two pre-existing RULE-015 standing-exception WARNINGs |
| Slow tier, packaging/install surface (`test_cli_phase4`, `test_discrete_builder_builtin_metric_enables`, `test_third_party_routing`, `test_validate_content_hook`, `-m ""`) | **67 passed, 0 failed** in 10 min |
| Slow tier, publish files (round-1 run, tree already carrying the `install.py` template change) | **34 of 52 passed, 0 failures**, killed by my own 55-minute timeout, not by a failure |
| My own mixed-envelope reproduction, 5 shapes x 3 paths | see table below; B-1 gone in every shape |
| Packaged installer exit code on a flagged run, 4 envelope shapes | `ctx["warnings"] == []` in all four, i.e. exit 0 |
| Doctor: 10 corrupt `.bootstrap-status` shapes + 6 name-boundary shapes | rc 0 in every case; longest emitted report 976 chars (was 100,910) |
| Doctor: 6 argv shapes including `--password SECRET` as two items and a bare positional | no value reproduced in any |
| Doctor: real CLI, healthy repo, no args | exit 0, **exactly one green line** |
| `analyze` across 5 path shapes | see below |
| Em-dash scan over all added lines (rule 7) | **0** |
| Stale-zip trigger (dimension 9) | still fires, still unflagged: W-5 stands |

## B-1 - RESOLVED, on every shape I could build

Driven through the real `DashboardsHandler.sync`, `ViewsHandler.sync`
and `cmd_sync` (not the tests):

| Envelope | DashboardsHandler | ViewsHandler | cmd_sync stderr |
|---|---|---|---|
| DASH 1/0, VIEWS 0/2 (the blocking case) | `['ok']`, **message empty** | `['warn']`, VIEW_DEFINITIONS only | names VIEW_DEFINITIONS content only, plus `not affected (imported normally): DASHBOARDS`; the dashboard name is absent |
| DASH 0/3, VIEWS 2/0 | `['warn']`, DASHBOARDS only | `['ok']` | names DASHBOARDS content only, plus `not affected: VIEW_DEFINITIONS` |
| both skipped | `['warn']` | `['warn']` | both named, and the "not affected" line correctly suppressed |
| both imported | `['ok']` | `['ok']` | silent |
| DASH 1/0 + SUPER_METRICS 0/5 (foreign noise) | `['ok']` | `['ok']` | silent |

The last row matters and was not in my prescription: the round-1 code
would have flagged on an unrelated `SUPER_METRICS` summary in the same
envelope. The `DASHBOARD_CONTENT_TYPES` filter in `cmd_sync` and the
mandatory `content_type` argument in `_all_skipped_message`
(`handler.py:46`, no default) make that structurally impossible rather
than merely absent, which is the stronger fix.

Installer, same treatment (`install.py:1456-1490`), driven through the
real `_install_dashboards`:

| Envelope | Output | `ctx["warnings"]` |
|---|---|---|
| DASH 1/0, VIEWS 0/2 | `OK Imported 1 dashboard` **and** `WARN Import changed no views` | `[]` -> exit 0 |
| DASH 0/1, VIEWS 2/0 | `WARN Import changed no dashboards ... [VCF Content Factory] Capacity` **and** `OK Imported 1 view(s)` | `[]` -> exit 0 |
| both skipped | two WARN lines, no OK | `[]` -> exit 0 |
| both imported | two OK lines | `[]` -> exit 0 |

## W-1 - RESOLVED, and the call is the right one

`ctx["warnings"]` is untouched (`install.py:1488-1490` records why), so
the packaged installer exits 0 for this advisory class. I agree with the
judgment: a repeat install where content is skipped is an ordinary,
non-failing operation, and an idempotent re-install that starts exiting 2
would train wrapper scripts to ignore the code. See W-7 for the one
loose end this leaves.

## W-2, W-3, W-4, W-6, N-1, N-4, N-5, N-2 - RESOLVED

- **W-2.** 0 em-dashes across every added line in the diff, source and
  docs.
- **W-3.** `_clip(script)` at `doctor.py:1067` plus the clipped stale
  stamp. Re-probed the boundary rather than the headline case: a
  50-character name renders as `bootstrap_aaa...` (43 chars), and the
  50,000-character line is rejected outright by the length bound, so the
  worst-case emitted report is 976 characters where round 1 measured
  100,910. Both mechanisms (bound, then clip) are present and the
  41-to-50 character band exercises the clip.
- **W-4.** `^bootstrap_[a-z0-9_]{1,40}(\.sh)?$` with a module-level
  cross-check against `KNOWN_BOOTSTRAP_SCRIPTS`. Verified live:
  `bootstrap_scg_v9` is accepted and reported;
  `bootstrap_references.sh` is normalized to the bare name, and a file
  carrying **both** the suffixed and bare forms collapses to one record
  per script (`keys == ['bootstrap_managed_paks', 'bootstrap_references']`,
  no twin, no unclearable "no run recorded"); `bootstrap-references`
  (hyphen) is still correctly rejected. The unclearable-delta trap is
  closed.
- **W-6 + N-7.** One predicate, one wording, both layers. Verified:
  a real staged bundle extracted from `dist/storage-path-monitoring.zip`
  analyzes at rc 0; `dist/vcommunity-dev-build/extracted` (the extracted
  pak that slipped through round 1) now exits 1 naming `bundle.json`; a
  `.zip`, a bare directory, and a `content/`-only directory all exit 1;
  a missing path still reports "bundle directory not found".
- **N-2 (upgraded).** `_redact_arg` verified across six shapes through
  the real CLI: `--password=SECRET` -> `--password=<redacted>`;
  `--password SECRET` (two argv items) -> `--password, <value>`;
  `-p SECRET` -> `-p, <value>`; a bare positional -> `<value>`; two
  flags -> both redacted; a 500-character flag name -> clipped at 40.
  The value never appears. `--help` still prints usage, and a healthy
  repo with no args still prints exactly one green line at rc 0.
- **N-1.** The syncer trailer is real and counts per content type.
- **N-4.** `TestDetectorParity` runs both detectors over nine shared
  fixtures including all three mixed shapes. That is the right shape for
  a duplication that must stay duplicated.
- **N-5.** Failures are named before staleness, and the checklist branch
  now reports both when both hold.

## Judgment call 1: requiring `bundle.json` for every caller is safe

Assessed on its merits rather than on the grep alone, and I agree.

- **Only caller.** Re-grepped `analyze_staged_bundle` /
  `check_staged_bundle_dir` / `staged_bundle_problem` across `*.py`,
  `*.sh`, `*.yml`, `*.yaml`, `*.md`: `cli.py:408` is the only production
  caller; everything else is the new test file.
- **Both producers emit the marker.** `builder.py:704` and
  `discrete_builder.py:863` write `bundle.json` beside `content/` in
  every staged bundle they produce, so the marker is not a new
  requirement, it is an existing invariant now being checked.
- **The marker matches what the function actually reads.**
  `analyze_staged_bundle` reads the flat `content/supermetrics.json`,
  `views_content.xml`, `dashboard.json`. Those exist only in the
  `bundle.json` layout; the pak layout has per-type subdirectories
  instead. The gate now tests for the shape the code requires rather
  than a weaker proxy.
- **Failure mode is loud and typed.** A future caller pointing at a
  content-only staging directory gets an `AuditError` with an
  actionable message, which the CLI already catches. That is the
  opposite of the silent rc 0 the issue was about.

## Judgment call 2: the publish slow tests

The structural argument holds and now covers `syncer.py` too. Verified
directly rather than accepted: neither file imports `vcfops_dashboards`,
`vcfops_common`, or `vcfops_packaging.syncer` (grep count 0 in both),
their import blocks are stdlib + `pytest` + `yaml` only, and their sole
`install.py` coupling is the literal README string
`` `python3 install.py` `` (`test_publish_phase3.py:705-710`). Beyond the
argument, my round-1 run of those two files completed 34 of 52 with 0
failures on a tree that already carried the `install.py` change, and I
ran the four slow packaging/install files to completion this round (67
passed). The residual gap is 18 publish tests that exercise git
mechanics this diff does not touch.

## WARNING (round 2, new)

### W-7. The installer's final line still says "All content installed successfully" after a WARN saying the content was not updated

`install.py:2388-2396`. With `ctx["warnings"]` deliberately untouched
(the correct W-1 fix), a flagged run takes the `else` branch and the last
words the operator reads are `Done. All content installed successfully.`
even though a `WARN Import changed no dashboards ... the existing
dashboard was NOT updated` scrolled past earlier. That is a milder
version of the exact sentence issue #97 objects to ("reported by this
factory as ok"), relocated from the exit code to the summary. The
remedy already exists in this same diff: tooling added an end-of-run
trailer to `syncer.py` for precisely this reason (N-1), and the
installer is now the inconsistent one. Smallest correct fix: a second
`ctx["advisories"]` list that prints a trailer in **both** summary
branches and never touches the exit code, e.g.
`Done. All content installed, with 1 advisory: ...`.

### W-5 (round 1) - STILL OPEN

`src/vcfops_packaging/templates/install.py` is still in the diff and
nothing in the tree flags the rebuild. Every dist zip still ships the
installer that reports a no-op dashboard import as a clean install. This
is orchestrator work (`content-packager` over every manifest in
`bundles/`), not tooling work, but it must land with this PR or as an
explicitly named follow-up.

## Test quality (round 2)

The 21 added tests are not tautologies and they pin the findings in the
direction that failed. `test_handler_does_not_blame_the_imported_dashboard`
asserts `message == ""`, not merely `status == "ok"`, so a future
regression that warns with empty text still fails.
`test_cmd_sync_names_only_the_flagged_type` asserts the **absence** of
the dashboard name from stderr, which is the actual B-1 symptom.
`test_flagged_import_does_not_populate_the_installer_warnings_list`
asserts both halves of W-1 (list empty **and** WARN still printed), so
"fixed by going silent" would fail it. `TestDetectorParity` drives both
detector copies over nine fixtures. `test_sh_suffixed_script_name_records_the_same_script`
pins the twin case rather than just the parse. `test_argv_echo_never_reproduces_a_value`
asserts the value absent **and** the flag name present, which is the
property, not the implementation.

The one thing tests do not pin is the 41-to-50 character clip band in
`_clip(script)`: `test_long_script_name_does_not_flood_session_context`
passes because the 50,000-character line is rejected by the regex bound,
so the clip itself is exercised only by my probe (N-13).

## NIT (round 2)

- N-8. `assert all(_SCRIPT_NAME_RE.match(_s) for _s in KNOWN_BOOTSTRAP_SCRIPTS)`
  (`doctor.py:690`) is a module-level assert: it is stripped under
  `python -O` (verified: the module imports clean under `-O`), and if it
  ever did fire it would raise at import time inside the SessionStart
  hook, i.e. it converts a future developer's mistake into a broken
  session start for the user rather than a red test. There is already a
  test (`test_known_bootstrap_scripts_all_match_the_name_guard`) that
  catches it in CI, which is the right place; consider keeping only the
  test.
- N-9. `src/vcfops_dashboards/handler.py:39-41`: a stray double blank
  line left inside the import block where the helper used to sit.
- N-10. `install.py`'s view WARN line does not name the affected views
  (the dashboard line names its dashboards). `views_content.xml` is
  available at that point, so the asymmetry is fixable if the parse is
  cheap.
- N-11. `cmd_sync`'s "not affected (imported normally)" line names the
  content **type**, not the items, while the affected line names items.
  Deliberate and harmless, just worth knowing the two lines read at
  different granularity.
- N-12. The `staged_bundle_problem` message is a good long sentence, but
  the CLI prefixes it with `ERROR: ` and the library raises it bare, so
  the same text reaches a log with two different leaders. Cosmetic.
- N-13. The `_clip(script)` band is unpinned by tests (see Test quality).

## If shipped as-is (round 2)

An operator who re-syncs a dashboard whose views were skipped is told the
truth: the dashboard imported, the views did not, and which is which.
The bundle syncer ends with a count instead of letting the warn lines
scroll away. The packaged installer names each content type separately,
keeps the success line for the type that imported, and does not turn an
ordinary re-install into an exit 2. `analyze` refuses a zip, an extracted
pak, and any directory without the builder's own `bundle.json` marker,
while a real staged bundle still analyzes clean. The doctor still prints
exactly one green line on a healthy repo, never exceeds ~1 KB on any
corrupt input I could construct, and cannot reproduce a value typed on
its command line. The two loose ends are cosmetic-but-real: the
installer's closing line still says everything succeeded when a WARN
above says otherwise (W-7), and every dist zip is still stale (W-5).

---

# Round 3 (2026-08-21) - confirm pass on W-7 and the three nits

- **Scope:** round-2 W-7 plus N-9, N-11, N-8. Commit `6a02f24` (working
  tree clean, diffed against `9d52c2f`). Dimensions cleared in rounds 1
  and 2 were not re-walked.
- **Round-3 verdict:** APPROVE. 0 BLOCKING, 1 WARNING (the standing W-5),
  6 NIT. Every property the brief asked me to confirm was driven, not
  read.

## Checks re-run (round 3)

| Check | Result |
|---|---|
| Full default suite | **852 passed, 4 skipped, 178 deselected** (matches the claim; was 846) |
| `tests/test_dashboard_import_all_skipped.py` alone | 29 passed (was 23, +6 as claimed) |
| Full validate chain (7 packages) | all green |
| `scripts/path_reference_audit.sh` | exit 0, "clear", plus the two pre-existing RULE-015 standing-exception WARNINGs |
| Em-dash scan over every added line, `9d52c2f..6a02f24` | **0** |
| Real `_run_install` + real `_install_one_bundle`, 4 envelope shapes | see table below |
| `_extract_view_names`, 24 malformed/hostile inputs | never raised; two behavioral edges, N-14/N-15 |
| `_extract_view_names` against real rendered XML (`dist/vks-core-consumption-bundle.zip`) | 1 title, exact view name, `<Title>` count in the document is 1 |
| Mutation test on the dropped assert's replacement | mutant killed (see below) |
| `doctor.py` under `python3 -O` | imports clean; no module-level asserts remain |
| Dist zip staleness (W-5) | 3 of 3 zips carry a **different** `install.py` than the repo template |

## W-7 - RESOLVED, and the trailer really is last

Driven end to end through the **real** `_run_install` calling the
**real** `_install_one_bundle` (not the test's stubbed seam), with a stub
`Client` and a staged bundle carrying one dashboard and one view:

| Envelope | rc | "Done." line | Actual last line printed |
|---|---|---|---|
| DASH 0/1, VIEWS 2/0 | **0** | `Done. No failures, but see the attention list below.` | `  ATTENTION  [mybundle] Import changed no dashboards ...` |
| DASH 1/0, VIEWS 1/0 (clean) | **0** | `Done. All content installed successfully.` | the NOTE block; **no** attention section at all |
| DASH 0/1 + VIEWS 0/2 + a genuine `ctx["warnings"]` entry | **2** | `Done with 1 warning(s):` | `  ATTENTION  [mybundle] Import changed no views ...` |
| DASH 0/1, VIEWS 0/2, no warnings | **0** | `Done. No failures, but see the attention list below.` | `  ATTENTION  [mybundle] Import changed no views ...` |

All four properties the brief named hold:

- the trailer is the **last** thing printed on a flagged run, in both
  branches (it sits after the 5-minute NOTE block, which is the right
  order: NOTE is boilerplate, the advisory is the delta);
- a clean run still prints the unqualified success line and emits no
  "need attention" text at all, so the new channel is inert when nothing
  is flagged;
- advisories alone exit 0, and a genuine warning still exits 2 with both
  advisories surviving beside it, correctly counted (`2 item(s) need
  attention` alongside `Done with 1 warning(s)`);
- the `[{bundle}]` prefix is applied at the `_install_one_bundle` return
  (`install.py:2329`) and shows up on every trailer line.

Wiring checked rather than assumed: `ctx["advisories"]` has exactly one
producer (`_install_dashboards`, `:1492`/`:1507`), one collector
(`_run_install`, `:2425`), one printer (`_print_advisories`, `:2427`),
and one call site for `_install_one_bundle`. No path discards the list.
The uninstall ctx has no `advisories` key, and `_install_dashboards` is
unreachable from it (`_CONTENT_REGISTRY` install/uninstall functions are
separate), so the `setdefault` is defensive rather than load-bearing.

## `_extract_view_names` cannot raise - confirmed, with two edges

24 inputs through the real function: `None`, `int`, `bytes`, `list`,
`dict`, empty, non-XML, unclosed `<Title>`, orphan `</Title>`, nested
`<Title>`, embedded NUL, a `</Foo>...<Bar>` span that exercises
`re.DOTALL`, lowercase `<title>`, `<Title>` carrying an attribute, an XML
entity, a lone surrogate, 10,000 titles, and a 5 MB title. **Nothing
raised.** The `views_xml or ""` guard handles `None`/falsy and the bare
`except Exception` catches the `TypeError` from a non-str, so the
"degrade to no names" contract holds. On the real rendered corpus it is
exact: `render.py:761` emits `<Title>` once per `ViewDef` and nowhere
else, so the regex is 1:1 with views, and the one dist bundle that ships
views extracts its single view name verbatim.

Two edges, both NITs (N-14, N-15) rather than warnings, because the input
is factory-rendered XML from the same zip, not operator or network input.

## The dropped assert - the property IS genuinely covered

I did not take this on the test's existence. I mutated
`KNOWN_BOOTSTRAP_SCRIPTS` to add `"bootstrap-Refs2"` (hyphen and capitals,
which `_SCRIPT_NAME_RE` rejects) and re-ran
`test_known_bootstrap_scripts_all_match_the_name_guard`: **rc 1, test
FAILED**, naming the offending entry. Restored and byte-compared. The
test is in the default (non-slow) tier, so CI runs it on every push.
`doctor.py` now imports clean under `python3 -O` with no module-level
asserts. Agreeing with the call: the assert and the test proved the same
thing, but only one of them survives `-O`, and only one of them fails in
CI instead of at SessionStart. Dropping the assert is the correct
resolution of N-8, and the comment at `doctor.py:692-699` names the test
by full node id so the next reader can find the coverage.

## N-9, N-11 - RESOLVED

- **N-9.** The stray double blank line in `handler.py`'s import block is
  gone; the block reads cleanly into `_all_skipped_message`.
- **N-11.** `cli.py:381-392` now builds `unaffected` from
  `names_by_type`, so both the affected and not-affected lines speak in
  item names. Verified in round 2's shapes: the "not affected (imported
  normally)" line names content items, not `DASHBOARDS`/`VIEW_DEFINITIONS`.
- **N-10** (from round 2) is also closed: `_extract_view_names` gives the
  view WARN the same naming fidelity as the dashboard WARN, verified live
  (`the existing views were NOT updated: [VCF Content Factory] Alpha.`).

## WARNING (round 3)

### W-5 (rounds 1 and 2) - STILL OPEN, now measured

Not a new finding, and the orchestrator has stated the
`content-packager` rebuild lands in this same PR. Recording the
measurement so the PR has the evidence: SHA-256 of the repo template
`src/vcfops_packaging/templates/install.py` is `8f59cee8cdd9...`, and the
`install.py` inside all three `dist/*.zip` differs
(`b90012b0e83b`, `2368ebe58aae`, `3dfaf8c4f934`). Every shipped zip
therefore still carries the installer that ends a no-op dashboard import
on `Done. All content installed successfully.` and exits 0 with no
attention list, which is exactly the defect this round fixes. Closes when
the rebuild lands.

## NIT (round 3)

- N-14. `_extract_view_names` is quadratic on unclosed `<Title>` opens.
  `"<Title>" * n` measured: 1,000 -> 0.05s, 5,000 -> 1.3s, 20,000 ->
  **21s**, 50,000 and 200,000 -> still running at my 30s cutoff. `.*?`
  under `re.DOTALL` rescans to end-of-string from every open tag. Not
  reachable from `render.py` output (always balanced) and a truncated
  file yields at most one unclosed tag, so this is a hang only on a
  deliberately crafted `views_content.xml`. Bounding the input
  (`views_xml[:200_000]`) or using `[^<]*?` instead of `.*?` removes it.
- N-15. The advisory string is unbounded. A 5 MB `<Title>` produces a
  5 MB line, printed twice (inline `WARN` plus the `ATTENTION` trailer);
  a bundle with 40 views produces one very long line. This is the same
  class as W-3, which this very round fixed in `doctor.py` with `_clip`.
  The input here is factory-rendered rather than untrusted, which is why
  it is a NIT and not a repeat of W-3, but `install.py` has no `_clip`
  equivalent and `_extract_dashboard_names` shares the shape.
- N-16. The regex is brittle against any attribute on `<Title>`:
  `<Title localizationKey="k">x</Title>` extracts **zero** names and the
  message degrades to the generic `view(s)`. That exact markup is what
  the renderer emitted before DEF-018 (`8ad7dd2`), and
  `sdk_builder.py:3264` still discusses emitting it on the MP path, so
  the coupling to `render.py:761`'s precise output is live history, not
  hypothetical. `audit.py:508` does the same extraction with a real
  `ElementTree` parse, which is attribute-immune and would degrade
  identically inside the existing `try`. Nothing pins the coupling with a
  test; a fixture built from real `render.py` output would.
- N-17. View names reach the operator XML-escaped, dashboard names do
  not. A view named `CPU & Memory <top>` prints as
  `CPU &amp; Memory &lt;top&gt;` (verified through `render.py`'s own
  `escape()` then `_extract_view_names`), while `_extract_dashboard_names`
  reads JSON and prints the raw name. The two lines the operator reads
  side by side are at different fidelity.
- N-18. `Done. No failures, but see the attention list below.` is
  followed by the seven-line 5-minute NOTE block before the list actually
  appears, so "below" is seven lines away. Correct order (the delta ends
  the output), just a slightly optimistic "below".
- N-19. `TestInstallerAdvisoryTrailer._drive_summary`
  (`test_dashboard_import_all_skipped.py:487-490`) monkeypatches
  `_install_one_bundle` to return canned lists, so the four new tests pin
  the summary block precisely but not the `[{bundle}]` prefixing at
  `:2329` or the `ctx["advisories"]` wiring from `_install_dashboards`.
  Both are correct, but I had to verify them with my own end-to-end
  harness rather than the suite. One test driving the real
  `_install_one_bundle` over a staged bundle would close the seam. The
  stub is otherwise a good choice: it keeps the four summary cases fast
  and independent of the import machinery.

## Test quality (round 3)

The 6 added tests pin the fix in the direction that failed.
`test_advisory_run_does_not_end_on_all_successful` asserts the **absence**
of the old string, which is the actual W-7 symptom, not merely the
presence of the new one. `test_clean_run_still_says_all_successful`
asserts `"need attention" not in out`, so a fix that unconditionally
prints the trailer would fail it. `test_advisories_do_not_change_the_exit_code`
pins rc 0 by the absence of `SystemExit`, and
`test_trailer_also_prints_in_the_warning_branch` pins both halves of the
harder case (exit 2 **and** the advisory surviving). `test_installer_view_warning_names_the_views`
asserts both view titles individually rather than a substring of the
line. `test_extract_view_names_degrades_on_garbage` covers three of the
degradation shapes; my probe covered 24 and found no raise.

## If shipped as-is (round 3)

An operator whose re-install skips everything now ends on an explicit
attention list naming the bundle, the content type, the affected objects
and the remedy, and the installer still exits 0 because nothing failed.
An operator whose install genuinely succeeds sees the unqualified success
line and no attention section. An operator who hits a real warning gets
exit 2, the warning list, and the advisories beside it rather than behind
it. A corrupt or truncated `views_content.xml` degrades the message to
`view(s)` instead of crashing the install. The one thing still true from
round 1 is that every zip in `dist/` predates all of this (W-5); the
rebuild is the last thing this PR needs.
