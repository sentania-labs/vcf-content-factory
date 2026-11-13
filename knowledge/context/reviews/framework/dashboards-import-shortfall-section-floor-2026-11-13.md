# Framework review: import shortfall + Section version refusal (#199)

- Branch `tooling/section-import-guard`, commit `82f420ee`, against `origin/main` `fc2f0d80`.
- Reviewed 2026-11-13 by `framework-reviewer`. This is a static, pre-PR review. Nothing was installed and no live instance was touched.
- Area: `src/vcfcf_dashboards/{client,cli,handler}.py`, `src/vcfcf_core/dashboards/widget_versions.py`, `src/vcfcf_packaging/syncer.py`, `src/vcfcf_packaging/templates/install.py` and `install.ps1`, `src/vcfcf_supermetrics/{cli,handler}.py`, `src/vcfcf_reports/{cli,handler}.py`, `template_version.py`, and the docs and lesson edits.

## Verdict: APPROVE (0 BLOCKING, 4 WARNING, 7 NIT)

The change does what it says. The shortfall rule is defined in one place, and the
two installer copies match it on every envelope I tried, apart from two shapes
no real envelope takes. The version refusal runs before anything is imported on
all five entry points. The template version was bumped. Nothing regresses on the
corpus. Every finding below still has to be fixed before the PR opens (CLAUDE.md
delegation rule 9).

## Checks re-run

| check | result |
|---|---|
| seven validators | all exit 0. `vcfcf_dashboards validate` warns once, on `content/dashboards/summary_widget_smoke.yaml` (the corpus's only Section dashboard), with the new text |
| `bash scripts/path_reference_audit.sh` | clear (2 standing RULE-015 exceptions) |
| pytest, branch | 14 failed / 4530 passed / 15 skipped |
| pytest, `fc2f0d80` (git-archive tree) | 14 failed / 4482 passed / 12 skipped. The 14 failing test names are identical to the branch's (doctor venv, release naming real-repo, gap_b_f_d JMESPath, deep-nesting names, packaging validate real-repo), so these are baseline failures |
| pwsh 7 (`/usr/bin/pwsh`) | `test_import_shortfall_and_widget_floor.py`, `test_install_ps1_materialization.py`, `test_install_ps1_tls_and_advisories.py`: 148 passed, none skipped |
| own parity probe (lib, install.py, install.ps1 harness) | agree on every realistic envelope and release name. Divergences listed under N1 and N2 |
| render regression / pak-compare | n/a. No renderer or builder change; `loader.py` changes a comment only |

## What I verified safe

- **Refusal runs before any import.**
  - `cmd_sync`: after the SM referent check, before `get_current_user` and `build_import_zip`.
  - `sync_bundle`: before the handler loop, so no SM, view or report of the bundle is sent.
  - `_run_install` / `Invoke-Install`: across all selected bundles, before `global_ctx` and before any `_install_one_bundle`. The marker discovery that runs earlier is an export, not an import.
  - So there is no half-installed bundle. With `sync --all`, the earlier bundles still land; that is per-bundle by design.
- **No nested bypass.** In the wire form a Section's members are ids (`config.widgets`), not widget objects, and the importer only walks top-level `widgets[]`. My probe with a Section object nested in a config was not flagged, which is correct, because the importer never sees it.
  - Library side: widget types are the closed factory set (`loader.py:2859`), and `Section` is the same string in YAML and on the wire (`render.py:1993`).
- **Every consumer is covered.** Every content-import caller (`grep import_content_zip|import_supermetrics_bundle|import_reports_zip`) now goes through `import_shortfalls`:
  - the dashboards CLI and both of its handlers, the SM CLI and handler, the reports CLI and handler;
  - the three import sites in each installer.
- **Out of scope by construction:**
  - Alerts, symptoms and custom groups use REST, not content import.
  - The extractor exports; `import-local` is offline.
  - The pak install goes through `/api/solutions`, so there is no envelope (see the Follow-up section).
- **Parity:** the floor table, the loss sentence, the message texts, release-name parsing and the refusal text match across the library, `install.py` and `install.ps1`, pinned by tests. The PS harness extracts the real functions with the AST.
- **PowerShell 5.1:** the new code uses only `::new()`, `-cmatch`, `String.Split(char[], StringSplitOptions)`, unary-comma returns, `Get-PropValue`/`Get-PropList`, and `[Array]::Sort` with an Ordinal comparer. No 7-only syntax (`??`, ternary, `-Parallel`).
  - Not run on 5.1, because there is no Windows host here; the harness header says so.
- **Template version** went to `2026-11-13-1`, with a history entry (dimension 9).
- **Release-name forms:**

  | releaseName | parsed | result |
  |---|---|---|
  | `9.0.2.0` | (9,0,2) | refused |
  | `9.0.2.0200` | (9,0,2,200) | refused |
  | `8.18.7` and `8.18.7 (Build n)` | (8,18,7) | refused |
  | `9.1.1.0` | (9,1,1) | allowed |
  | `9.1.1.0100` | (9,1,1,100) | allowed |
  | `9.1.0.0` | (9,1) | refused (see W1) |
  | no dotted token (SaaS-like) | None | warn and import |
  | `9.2.0.0-beta` | None | warn and import |

## WARNING

**W1. 9.1.0 is hard-refused on a floor nobody has checked, and there is no override.**
- Where: `widget_versions.py:62` (`"Section": (9, 1, 1)  # 9.1.0 unchecked`) and `import_refusal`; the same rule is pinned in both installers.
- Authority: the module's own docstring ("the floor is the lowest proven build, not necessarily the exact one"), and `recon_log.md` (prod and qa answered `VCF Operations 9.1.0.0`).
- What happens: on a 9.1.0.x instance, sync and both installers now refuse every bundle with a Section dashboard and print "Section needs 9.1.1 or later" as if it were fact. Nobody has read 9.1.0's `WidgetType` enum. There is no flag to proceed.
- Repro:
  ```
  python3 -c "from vcfcf_core.dashboards import widget_versions as w; print(w.import_refusal([('D',[('s','Section')])], w.parse_release_name('VCF Operations 9.1.0.0')) is not None)"
  # True
  ```
- Fix: refuse only at or below the highest build known to lack the type (9.0.2; 8.18.7 has the same enum). In the gap between 9.0.2 and 9.1.1 that no one has measured, warn and import, and let the shortfall check report a loss. Alternatively, read the 9.1.0 enum the way 8.18.7's was read. Either way, the text should say "proven from 9.1.1".

**W2. Shortfall as an error for SUPER_METRICS and REPORTS rests on no recorded healthy envelope.**
- Where: `client.py:import_shortfalls`, as called from `supermetrics/cli.py:130`, `supermetrics/handler.py:82`, `reports/cli.py:143`, `reports/handler.py:103`, `install.py` `_install_supermetrics` and `_install_reports`, and the matching PS functions.
- Authority: reviewer doctrine (unproven is a finding).
- Evidence gap: every committed envelope that carries `total` is VIEW_DEFINITIONS or DASHBOARDS (`content_import_skip_semantics.md`, `2026-11-11-owner-mapping-dashboard-skip-reproduction.md`, the 2026-11-13 note). There is no SUPER_METRICS or REPORTS envelope with `total` in the repo or in `/mnt/holding/vcf-content-factory`.
- Risk: if either type's `total` counts anything other than the objects sent, every healthy SM sync exits 1 and every installer run exits 2 with "cause is not known".
- Fix: record one healthy SM import envelope and one report import envelope (any one line; 9.0.2 is enough) in the investigation note or `content_import_skip_semantics.md` before the PR, and cite it in the `import_shortfalls` docstring.

**W3. The shortfall text says "still reported FINISHED" and points at widget types even when the task FAILED.**
- Where: `client.py:import_shortfall_message`, which these use without a state gate: `dashboards/handler.py:196` and `:393`, `supermetrics/handler.py:82`, `supermetrics/cli.py:130`, `reports/handler.py:103`.
- Authority: the doctrine's honest-reporting rule; `content_upload_methodology.md` §3, which defines the check as a property of a FINISHED summary.
- What happens: `import_content_zip` returns any terminal state, FAILED included. A FAILED envelope with short counters becomes "IMPORT SHORTFALL ... the task still reported FINISHED. The likely cause is a widget type...". That sends diagnosis the wrong way.
- Repro:
  ```
  import_shortfall_errors({'state':'FAILED','operationSummaries':[{'contentType':'DASHBOARDS','total':2,'imported':0,'skipped':0,'failed':0}]})
  ```
  This returns the FINISHED/widget-type text.
- Fix: apply the shortfall only when `state == "FINISHED"` (`cmd_sync` and the reports CLI already gate this way), or make the message state-aware. `install.py` already dies on a FAIL state, so it is only exposed on the library paths.

**W4. The installer prints the lost-batch error as WARN, and the run ends telling the operator to wait 5 minutes.**
- Where: `install.py:_record_import_shortfalls` (`_warn`, so it lands in `warnings`) and the summary at `install.py:~3247`. The same in `install.ps1` `Add-ImportShortfalls` / `Write-Warn`.
- Authority: the brief ("an error (exit 2)"); `new-metric-alerts-need-two-samples.md` and the reports-green-while-broken class.
- What the operator reads: `WARN IMPORT SHORTFALL: DASHBOARDS ...`, then `Done with N warning(s)`, then "Dashboards may render with empty widgets ... This is expected. Refresh after ~5 minutes." The dashboards are not there and will not appear. The exit code is right but the last lines are wrong.
- Fix: print shortfalls as `ERROR` and keep them out of, or explicitly called out in, the "expected, refresh" NOTE (for example: "N content type(s) were not imported; see IMPORT SHORTFALL above"). Same change in both templates.
- Tests: no test covers `_install_reports`' shortfall, or `Install-Supermetrics` and `Install-Reports` in PS (the harness exercises `Install-Dashboard` only). Add one case each (dimension 10).

## NIT

- **N1.** PS and Python disagree on non-integer counters. `total: 1.5, imported: 1`: PS `[int]` rounds to 2 and flags it; Python `int()` truncates and does not. `total: "2.0"`: PS parses it; Python raises and skips the entry. No real envelope looks like this. Fix: in PS, accept only integral values (`$totalRaw -is [int] -or [long]`, or a `^\d+$` string), as Python does in practice.
- **N2.** `parse_release_name` splits on any whitespace, while `ConvertFrom-ReleaseName` splits on space and tab only. `"VCF Operations\n9.0.2"` gives (9,0,2) in Python and `$null` in PS. Also, `"9.0²"` passes `str.isdigit()` and then makes `parse_ops_version` raise inside `parse_release_name`, whose contract says it returns None. Fix: use the regex `^[0-9]+(\.[0-9]+)+$` on both sides and catch `ValueError`.
- **N3.** The last dotted token wins. A releaseName that ever carries a trailing dotted token (for example an API version) would be refused against that token: `"VCF Operations 9.0.2.0 API 2.2"` parses to (2,2). Every recorded form has a single dotted token, so this is latent. Fix: prefer the first dotted token after `Operations`.
- **N4.** `dashboard_fidelity_wire_format.md` §Section and the `parse_release_name` docstring say "the body's major/minor are the API version". `recon_log.md` (9.1.0.0, 2026-06-13) records `major: 9, minor: 1, minorMinor: 0`. They are the API version on 8.18.7 and 9.0.2 but the product version on 9.1. Fix: say "on 8.18.7 and 9.0.2 ...; only releaseName is consistent across lines".
- **N5.** `IMPORT_LOSS_SENTENCE`, the lesson, the INDEX row and `summary_dashboard_pak_binding.md` all state "every dashboard in the same import". The investigation's Undetermined section says only one owner was measured. Factory imports always carry one owner, so it holds in practice. Fix: "every dashboard of the same owner in the import (factory imports carry one owner)", or note the scope once in the lesson.
- **N6.** The lesson title still reads "...aborts the whole pak dashboard import". The body now covers content import, so the title understates it.
- **N7.** Dimension 9: the commit message does not say that all dist zips are stale and need a `content-packager` rebuild of every manifest in `bundles/` (templates changed). The version bump makes old zips report stale, but the rebuild still has to be scheduled.

## Follow-up (code this branch does not touch)

The investigation's path B shows `python3 -m vcfcf_managementpacks install`
reporting "FINISHED, verified, exit 0" with 50 of 52 dashboards present. That
is the factory's own installer reporting green while broken, and nothing in
this change covers the pak path. The Tier 2 build gate covers factory-built
paks only. Third-party or forked paks installed through
`vcfcf_managementpacks install` get no Section check and no post-install
dashboard count. Recommend a separate issue: a version-floor preflight and a
by-id dashboard count after pak install.

## If shipped as-is

Operators on 8.18.7 and 9.0.x get a clear refusal naming the Section dashboards
instead of a silent total dashboard loss. Operators on 9.1.0 are refused on an
unchecked floor (W1). If SM or report totals ever differ from the count sent
(W2), every healthy install turns red.
