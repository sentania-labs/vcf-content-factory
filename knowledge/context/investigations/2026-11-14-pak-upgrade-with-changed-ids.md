# Pak upgrade with changed content ids on 9.0.2: what was observed (2026-11-14)

**Scope note.** Cut short by the owner. Upgrading a pak in place across a
content id change is a one-off that happened in development. It is not
supported and will not be worked around. The supported path is a clean
slate: uninstall the old pack, then install fresh. The probe matrix the brief
planned was never run, and **no probe pak or probe object was installed on
any instance**. This note records only what the existing evidence and one
bytecode read established, plus the read-only state of `devel` that a
recovery needs.

**Subject:** a pak that carries the upstream vCommunity pack's content names
under its own ids (`vcfcf_vcommunity`), upgraded on `devel` (9.0.2.0 build
25429562) from build 16 to build 17. Build 17 changed every content id and
kept the names.
**Evidence (holding share, not in the repo, RULE-015):**
`/mnt/holding/vcf-content-factory/backups/vcommunity-java-p7-2026-11-14/`
(install log, `devel/logs_a.txt`, `devel/logs_removeContent.txt`, the
`chk_*.json` checkpoints, `pak-inventory16.json` and `pak-inventory17.json`,
and the build 17 pak unpacked under `pak17/`) and
`/mnt/holding/vcf-content-factory/backups/pak-upgrade-changed-ids-2026-11-14/`
(`chk_q6_now.json` for the state at 16:06Z, and `bytecode/`, the `javap -p -c -constants`
of `SolutionManagerDistributedTask` from the 9.0.2
`vcops-view-server-1.0-SNAPSHOT.jar`, with sha256 sums).

## Answer first

- **Views and report templates (A).** On 9.0.2, a pak directory under
  `content/reports/<dir>/` fails as a whole when one of its titles already
  exists under another id, **if the directory embeds a ViewDef and carries a
  `resources/content.properties` bundle**. Every factory view directory
  matches that description. The product logs `renameTitleDuplicated -
  duplicated title found`, and then `ViewManagerImpl.renameTitleDuplicated`
  (line 1248) throws a `NullPointerException` because `titleKey` is null.
  A directory with neither a ViewDef nor a bundle goes through the same
  rename path without error: the incoming report is renamed with `" 1"`.
  That much is proven. Which of the two (the ViewDef or the bundle) triggers
  the NPE is not separated, and the cause stays inferred (below).
- **Why the old views and reports stayed (B). Proven from the bytecode.**
  One failed report directory turns off obsolete-view and obsolete-report
  cleanup for the whole upgrade. Old dashboards, alerts, symptoms,
  recommendations and super metrics are still removed by id.
- **What happens on a fresh install with no same-name content:** none of A
  or B applies. Both need an existing object with the same title (A) or an
  earlier version of the same pak (B).
- **Fresh install alongside same-name leftovers** (operator clones, or views
  an earlier uninstall left behind): A applies. Every factory view or report
  directory whose title collides fails, without any error from the
  installer.

## What was observed (from the evidence set)

| Type | Build 16 ids still present | Build 17 ids present | Notes |
|---|---|---|---|
| Views | 170 / 170 | 0 / 170 | Every view directory failed with the `titleKey` NPE |
| Report templates | 16 / 16 | 5 / 16 | The 5 that imported are named `"<name> 1"` |
| Dashboards | 0 | 52 / 52 | Old ones deleted by `removeContent` at 15:28:18Z. New ones unshared (C, not pursued) |
| Super metrics | 0 | 2 / 2 | Named `"<name>-1"`. Kept that name after the old ones were deleted (D, not pursued) |
| Symptoms | 0 | 2 / 10 | Separate causes: burned ids (`2026-11-14-symptom-duplicate-key-on-902.md`) and the recommendation id format defect, both handled elsewhere |
| Alerts | 0 | 3 / 4 | Same |
| Recommendations | 0 | 0 / 1 | Recommendation id format defect (handled elsewhere) |

The state at 16:06Z (`chk_q6_now.json`) is the same as the t+30 checkpoint.

**Correction to the brief:** not all 181 directories failed. The 5 report
directories that imported are `VOA - Capacity`, `VOA - Configuration`,
`VOA - Executive Summary`, `VOA - Inventory` and `VOA - Performance`. They
are exactly the 5 of the 16 report directories in build 17 that carry **no
embedded ViewDef and no `resources/content.properties`**. The 11 report
directories that embed one ViewDef and a bundle failed, and so did all 170
view directories, each of which carries a bundle.

## Mechanisms

### A. The duplicate-title NPE

- **Proven:** the log sequence `WARN ViewManagerImpl.renameTitleDuplicated -
  View import: duplicated title found = <title>` and then
  `NullPointerException: Cannot invoke "String.equals(Object)" because
  "titleKey" is null at ViewManagerImpl.renameTitleDuplicated(ViewManagerImpl.java:1248)`,
  called from `ContentImportService.importSolutionContent(ContentImportService.java:172)`,
  then `installReportContent - importSolutionContent failed to import reports`.
  The exception fails the whole directory.
- **Proven:** a report directory without a ViewDef or a bundle survives the
  duplicate-title path on 9.0.2, and the product renames the incoming report
  to `"<title> 1"`. The 2026-11-12 note shows the same `" 1"` rename for views
  from the upstream pack on 8.18.7, and that pack ships no bundle.
- **Inferred, not tested:** when a localization bundle is present, the rename
  looks up the title's localization key (the `localizationKey` attribute on
  `<Title>`, the form product exports use). Factory view XML never emits that
  attribute (DEF-018: 8.18 rejects a key that has no bundle entry), so the key is null.
  `ViewManagerImpl` lives in `vcops-view-client-1.0-SNAPSHOT.jar`
  (`/usr/lib/vmware-vcops/common/lib/`, sha256 `1c160ce2…cafb` on 9.0.2). That jar was
  located but **not disassembled**, so the trigger was not separated: bundle
  present versus ViewDef present, or `<Title localizationKey=...>`
  with a matching `view.<id>.title` entry. Behaviour on 9.1.1 was not
  measured.

### B. Which old content an upgrade removes (bytecode, 9.0.2, proven)

From `SolutionManagerDistributedTask`:

1. `installContent` sets every `*IdsInstalled` flag to `true`, then runs
   `installLocalizationContent` and `installReportContent`, followed by the
   dashboard step and the rest.
2. In `installReportContent`, each `content/reports/<dir>` is zipped and
   passed to `ContentImport.importSolutionContent`. On success, the
   directory's `viewDefinitionIds` and `reportDefinitionIds` are added to
   this run's sets. On any exception, it logs `importSolutionContent failed
   to import reports. Error: %s` and sets
   **`viewReportDefinitionIdsInstalled = false`**. The flag is never reset
   during the run.
3. If `forceUpdateContent` is set (the upgrade case),
   `removeObsoleteContent(sc, …)` runs. For each type whose flag is still
   true, it computes obsolete = ids recorded in `SolutionContent` minus this
   run's successful ids, drops those from the record, and passes them to
   `removeContent`. For views and reports, that block sits under
   `if (viewReportDefinitionIdsInstalled)`, so **one failed report directory
   leaves every old view and report id recorded and not deleted.**
4. After that, `addViewDefinitionIds` and `addReportDefinitionIds` add this
   run's successes. They only add, and never replace.
5. `removeContent` knows how to delete reports, views, dashboards, policy,
   alertdefs, symptomdefs, recommendations, customgroups, geo regions,
   supermetrics, traversalspecs, the three widget kinds, solution configs,
   scorecards and liQueryConfigs, all **by id**. On `devel` it logged only
   dashboards, alertdefs, symptomdefs, recommendations and supermetrics,
   because the view and report sets had been skipped.

How this fits the 2026-11-12 note, where the old-id views *were* deleted on
a 9.x upgrade: those upgrades imported every view directory (the upstream
pack has no bundles, and title collisions went through the rename path), so
the flag stayed true and the obsolete ids were removed. The observed
outcomes differ only because of the flag. The rule is the same.

### C and D: not pursued

Why the 52 new dashboards are unshared, and the `-1` super metric rename
(and whether anything references a super metric by name), were dropped with
the scope cut. Neither is expected on a fresh install with no same-name
content.

## Current state on `devel` and what an uninstall would remove

Ownership in `SolutionContent` is **inferred from the bytecode** above
(`SolutionContentNamespace` was not read directly):

| Type | Recorded as the pak's content (inferred) | An uninstall with `removeContent` deletes, by id |
|---|---|---|
| Views | the 170 build 16 ids. No build 17 view exists | the 170 old views |
| Report templates | the 16 build 16 ids plus the 5 build 17 ids | all 21 (16 old, 5 `"… 1"`) |
| Dashboards | the 52 build 17 ids (old ones were removed from the record and deleted) | the 52 new dashboards |
| Super metrics | the 2 build 17 ids | both `"…-1"` |
| Symptoms, alerts | the build 17 ids that imported (2 and 3) | those |

`uninstallContent` gathers every id set from `SolutionContent` and calls
the same `removeContent`. Nothing is checked for ownership or edits. None of
the build 16 or build 17 view, report, dashboard or super metric ids is in
the stock-id baseline (`src/vcfcf_core/stock_ids/stock_ids_baseline.json`,
0 hits), so the uninstall deletes nothing built in.

### Least destructive recovery (not performed)

1. Take a full content export of `devel` (all 11 types). The `post/`
   exports in the evidence set predate nothing that changed since, but take
   a fresh one.
2. Uninstall the pak with the factory uninstaller (`removeContent` on). This
   deletes exactly the rows in the table above.
3. Verify by **name**, not id, that no view, report, dashboard, super metric,
   symptom or alert with any build 17 name remains. If one does (the record
   held something other than what the bytecode implies), delete it through
   the content API by id. Any leftover makes step 4 hit A again.
4. Fresh install of a build that carries the recommendation id fix. On a
   clean instance it should import every view and report under its own
   title. Check the symptom ids against the burned-id list in
   `2026-11-14-symptom-duplicate-key-on-902.md` first.

## Requirements for the factory (from what is proven)

- **Installer pre-flight (proven need):** before installing a pak, list the
  existing views and report templates whose titles match the pak's, under a
  different id. On 9.0.2, every colliding factory view directory fails
  silently. Refuse the install, or name the collisions and require the
  operator to clear them. That covers operator clones of the pak's views
  and leftovers from an earlier pack.
- **Post-install check:** the content count added in #367 already catches
  the missing views. Make it name the `titleKey` NPE as the likely cause
  when the failed directories' titles exist under other ids.
- **Upgrades that change ids:** unsupported (owner decision). An upgrade in
  place across an id change leaves the old views and reports owned and
  present, and the new ones missing. Only uninstall plus a fresh install
  works.
- **Builder (open, depends on the untested mechanism):** whether a bundle
  is what makes factory views fragile on title collisions was not proven.
  Do not drop bundles or add `<Title localizationKey>` on this note alone.
  The A3 contract and DEF-018 constrain both.
