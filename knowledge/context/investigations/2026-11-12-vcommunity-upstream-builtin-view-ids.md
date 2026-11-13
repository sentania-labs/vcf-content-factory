# Upstream vCommunity packs ship views under built-in view ids: what was measured (2026-11-12)

Follow-up to
`2026-11-11-devel-stock-views-deleted-by-vcommunity-pak-uninstall.md` and
the lesson `knowledge/lessons/pak-content-must-not-reuse-stock-ids.md`.
That investigation found the factory's own retired port deleting built-in
views. This one establishes the same defect in the two upstream Python
packs, measures what install, upgrade and uninstall do on each supported
product line, and records the fixes sent upstream.

## The defect

Both lines of the pack ship view definitions whose ids are the ids of
views built into VCF Operations. The platform tracks pak content by id, so
installing the pak overwrites the built-in view and uninstalling the pak
deletes it. Built-in dashboards that use those views then show "The view
does not exist".

| Pack line | Versions | Views under built-in ids |
|---|---|---|
| `vmbro/VCF-Operations-vCommunity` | 0.1.4 (released pak) | 0 (ships no views) |
| | 0.1.5 (released pak) | 41 |
| | 0.1.6 to 0.3.1 | 117 |
| `e1-rahabok/VCF-vCommunity-Adapter` | 0.4.2 to 0.8.1 | 120 (the 117 plus three VCF Management Services views that are built in on 9.1.1) |

Counted from the repository tags and, for 0.1.4, 0.1.5, 0.2.8 and 0.3.1,
from the released paks. The released 0.1.5 pak ships views its repository
tag does not, so the tag is not evidence for early versions.

The matching ids show where these views came from: they are the product's
own views, not look-alikes (random UUIDs do not collide). Most likely each
was edited in place on an instance, which keeps the id where the Clone
action would have assigned a new one, and then exported into the pack;
editing an exported file by hand would give the same result. Of the 117: 8
are identical to the built-in view, 11 differ only in title or description
(three of those also set one explicit default, `isSum=false`), and 98
carry real changes to columns, filters or presentation. The factory's own
classification of those 98 during the fix, which is not in any upstream
text, was 62 with structural changes and 36 with presentation changes
only.

No collision was found in the other content types, within what was
checked. `python3 -m vcfcf_packaging stock-id-check` on the released 0.8.1
pak reports 0 hits among its dashboards, report templates, symptoms and
alerts, and 120 among its views. Super metrics are not covered by that
check (the stock-id baseline holds no super metric ids); the packs' super
metric ids were compared with a 9.1.1 export only.

## Measured behavior, by product line

With the released 0.3.1 pak (117 ids) and a corrected build of the same
content, no adapter instance configured. Compared by full content exports
before and after each step, plus the audit log.

| Step | 8.18.7 | 9.0.2 | 9.1.1 |
|---|---|---|---|
| Install of 0.3.1 | 90 of the 117 built-in views changed | 109 | 109 |
| Uninstall of 0.3.1 | every view the pak shipped is deleted, built-in ids included | same | same |
| Fresh install of the corrected build | 160 views added, 0 existing views changed | same | same |
| Uninstall of the corrected build | exactly the 160 it added are deleted | same | same |
| Upgrade 0.3.1 to the corrected build | nothing deleted; the old copies stay under the built-in ids; 75 new views get " 1" appended to their titles | all 117 built-in views deleted about a minute after the import | all 117 deleted |
| Uninstall after that upgrade | 249 views deleted (the 160 new ones and 89 under built-in ids) | only the pak's views | only the 160 |
| Restore by importing the views from a clean export of the same version | works (run after the uninstall, and after the upgrade, where it overwrites the lingering copies) | works (after the uninstall and after the upgrade) | works (after the uninstall and after the upgrade) |

The upgrade row is the one to plan for. On 9.x the platform removes
content that the new version of a pak no longer ships, so the release that
stops shipping the built-in ids deletes those built-in views at upgrade
time. On 8.18.7 it does not: the old copies stay under the built-in ids,
so the built-in views stay replaced, with duplicate titles beside the new
views. Uninstalling is not a way to clear them, because that uninstall
deletes the views under 89 built-in ids. Why 89 and not all 117 on 8.18.7
is not explained (the install had changed 90 there). Either way the built-in views have
to be re-imported once from a clean export of the same product version. An
export taken from the affected instance does not help: it contains the
pack's copies.

Views the fix stops shipping (the 19 that are identical or renamed only)
are referenced in place, so on 9.x the upgrade also leaves the pack's own
widgets that use them dangling until the restore.

For the `e1-rahabok` line, a build of the corrected 0.8.1 content on the
released 0.8.1 adapter image was installed and uninstalled once on 9.1.1:
170 views added, 0 existing views changed, all 52 dashboards imported, the
same 170 deleted on uninstall, instance back at baseline. The upgrade path
was not run for that line; its documentation carries the 0.3.1
measurements and says so.

Undetermined:

- On 9.0.2 one of two upgrade runs never reported completion (the
  `SOLUTION_INSTALL` task stayed RUNNING; the pak manager marked it failed
  after 3600 s; the last log entry was the 117-view delete). A repeat on
  the same instance completed in under five minutes. Hypothesis only: the
  run that hung upgraded while the previous version's dashboards were
  still importing.
- On a first fresh install of the corrected 0.3.x build on 8.18.7 and on
  9.0.2, 45 of 46 dashboards were present, a different one missing each
  time; all 46 were present on later installs. The `Section` widget, which
  aborts a dashboard import before 9.1.1
  (`knowledge/lessons/unknown-widget-type-aborts-pak-dashboard-import.md`),
  is ruled out here: the 0.3.x content has no Section widget, and that
  failure would drop the same dashboards every time. The cause is unknown.
- Whether views restored on 8.18.7 after an upgrade are deleted again by a
  later uninstall of the pack. After an 8.18.7 upgrade the pak still owns
  those ids, so a re-import after any later uninstall may be needed.
- That a 9.1.1 upgrade from an `e1-rahabok` version (0.4.2 to 0.8.1) to a
  corrected one also deletes the three VCF Management Services built-in
  views. It follows from the same platform behavior and was not measured.
- On 9.0.2 only 1 of 9 symptoms imports (`duplicate key value violates
  unique constraint "kv_symptomproblemdefinition_pkey"`) and one alert
  fails with "Invalid format of the imported file". This happens
  identically with the released 0.3.1 pak, so the fix does not cause it;
  what the duplicate key collides with was not established.
- No browser check was made and no test ran with adapter accounts
  configured.

## What went upstream

- `vmbro/VCF-Operations-vCommunity`: issue 99, pull request 100.
- `e1-rahabok/VCF-vCommunity-Adapter`: issue 91, pull request 92 (the same
  fix ported, with the same new ids so both lines agree, covering 120 ids,
  with a test and documentation).

The fix in both: the 19 views that are identical to or only renamed from a
built-in view are no longer shipped and are referenced in place; the other
views get ids of their own and every dashboard reference is repointed.
Reviews: `knowledge/context/reviews/python-packs/vcommunity-fix-builtin-view-ids.md`
and
`knowledge/context/reviews/python-packs/vcommunity-fix-builtin-view-ids-e1.md`.
Both reviews were of earlier commits; every finding in them was addressed
on the branches before the pull requests opened.

## What the factory changed because of it

- The stock-id guard (`knowledge/context/stock_id_guard.md`, issue #345)
  now fails a build, validate, import or pak install that defines content
  under a product id. `python3 -m vcfcf_packaging stock-id-check <pak>`
  finds 120 view hits in the released 0.8.1 pak, 117 in 0.3.1 and 41 in
  0.1.5.
- An instance that runs an affected version must not be uninstalled or
  upgraded without a view export from a clean instance of the same product
  version at hand. On 8.18.7, keep that export: a later uninstall of the
  pack may delete the restored views again (untested, see above).
