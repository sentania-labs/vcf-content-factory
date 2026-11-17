# Built-in views the vCommunity packs overwrite: pristine sources and a restore zip per product line (2026-11-16)

Follows `2026-11-12-vcommunity-upstream-builtin-view-ids.md` and
`2026-11-11-devel-stock-views-deleted-by-vcommunity-pak-uninstall.md`.
Read-only against `devel_8_18` (8.18.7), `devel` (9.0.2) and `devel_9_1`
(9.1.1): root SSH reads, copies of shipped files, audit log copies, Suite API
GETs. Nothing was imported, changed or restarted on any instance. Times are UTC
in log quotes and America/Chicago (CST) in prose.

The 120 ids: `old_id` of `content/sdk-adapters/vcommunity-java/docs/design/inputs/id_map.tsv`
(98), `id` of `dropped.tsv` (19) and `old_id` of `id_map_e1_extra.tsv` (3).
The 41 shipped by vCommunity 0.1.5 come from `stock-id-check` on the released
0.1.5 pak. 41 ⊂ 117 ⊂ 120.

## Answer

1. **The authoritative pristine source is on the appliance.** Built-in views
   are not loaded from some hidden store. Each one is a `ViewDef` in a
   `content/reports/<folder>/content.xml` inside a solution pak the product
   ships, with `resources/content*.properties` beside it for the localized
   strings. Those paks are on every node under
   `/storage/db/casa/pak/dist_pak_files/` (`VA_LINUX` or `NON_VA_LINUX`). The
   120 ids come from four of them: VMware vSphere (108), the AppOS/UCP adapter
   (8), the Storage Area Network pack (1), and on 9.1.1 VMSP (the 3 VCF
   Management Services views). This was found and copied on all three lines,
   so **9.0.2 has a complete pristine source after all**, even though no
   pristine 9.0.2 export of the 64 views exists.
2. **One payload cannot serve every line.** Counting the definition plus its
   English, Spanish, French and Japanese strings, only 21 of the 117 shared
   ids are identical on all three lines. 89 have the same XML on every line
   but different strings. 7 have different XML. The 3 VCF Management Services
   views do not exist before 9.1.1. 9.0.2 and 9.1.1 are close: the XML
   differs for 2 ids, the English strings match for all 117, and the es/fr/ja
   strings differ for about 90.
3. **What restoring means was measured on all three lines.** Import the
   views through content import with overwrite on. The import envelope comes
   back clean, and a later export matches the pre-test export. Dashboards and
   reports are never touched, by the uninstall or by the restore. The
   dashboards were checked at the API only, never in a browser. Whether a
   restored view keeps "built-in" status was not measured. A product update
   re-imports its own built-in views with force; that was measured on a 9.0.2
   patch.
4. **Views need their localization lines, and nothing else.** Uninstalling a
   pack deletes only the views. Dashboards and report templates that use them
   stay, unchanged, and resolve again once the views are back.
5. **Earlier finding corrected.** The 2026-11-11 note said 9.0.2's titles
   differ from 9.1.1's for 10 ids, and that `9e427b59` is a different view in
   9.1.1. That is an artifact. The audit log names a view by the raw `<Title>`
   text in its XML, but an export shows the localized English title. On the
   product's own files, 9.0.2.0200 and 9.1.1 have the same titles for all 117
   ids. The XML differs for `4d9b6ad6` and `524d0468` only. So devel's restore
   on 2026-11-11 from 9.1.1 copies was exact apart from those 2 definitions
   and the es/fr/ja strings.

Restore zips (built and checked offline, not imported anywhere):
`/mnt/holding/vcf-content-factory/builds/builtin-view-restore-2026-11-16/<line>/`.
See §Artifacts.

## 1. Pristine source per product line

### The appliance (authoritative)

Where they are: an earlier search (2026-11-11) looked under
`/usr/lib/vmware-vcops` and `/storage/db/pakRepoLocal`, which keep only
manifests, EULAs and result files. The paks themselves are under
`/storage/db/casa/pak/dist_pak_files/`.

They are what the product imports at install. The 9.1.1 analytics log for
the first boot, 2026-10-14 14:11 to 14:12Z, shows the solution install task:
VMWARE adapter describe with `isForceInstall = true, isForceUpdateContent =
true`, then `ContentImport.importFile`. The audit log's
`VIEW_DEFINITION.IMPORT` bursts at the same minute include these ids. The
burst sizes match the pak split: 108 + 1 + 3 + 8 on 9.1.1, and 108 + 1 + 8
on 8.18.7 and on 9.0.2.

Reach: key-based root SSH worked to `devel`. On `devel_8_18` and `devel_9_1`
key auth was refused, and password SSH as root with the profile's credential
worked. The collectors were not needed. Copies, read-only, with sha256 sums:
`/mnt/holding/vcf-content-factory/evidence/builtin-view-sources/<line-build>/`.
They are Broadcom files and stay off the repo.

| Line (build) | Paks used | Ids found |
|---|---|---|
| 8.18.7 (25423534) | `VMwarevSphere-818725423577`, `AppOSUCPAdapter-818725423576`, `ManagementPackforStorageAreaNetwork-818725423575` | 117 |
| 9.0.2 (25431135, vSphere 9.0.2.0200) | `VMwarevSphere-902020025430344`, `AppOSUCPAdapter-902020025430785`, `ManagementPackforStorageAreaNetwork-902020025430349` | 117 |
| 9.1.1 (25795063, vSphere 9.1.1.0100) | `VMwarevSphere-911010025795107`, `AppOSUCPAdapter-911010025795106`, `ManagementPackforStorageAreaNetwork-911010025795118`, `VMSP-911010025795113` | 120 |

Inside a pak, each id appears in exactly one canonical form. Duplicate
copies, such as top-level `content/` against the nested adapter zip, are
identical. There are no conflicts.

**The pak form is the source of what an export shows.** Take the pak's
`ViewDef` and put its English strings into every element that carries a
`localizationKey`: the result equals the pristine export of the same line
exactly (canonical XML) for 116 of 117 ids on 8.18.7, all 53 that a pristine
9.0.2 export has, and 120 of 120 on 9.1.1. The two exceptions are titles the
first-boot import gave a " 1" suffix: `19729c38` "Guest Operating System
Distribution 1" on 8.18.7 and `9d5498ba` "Guest OS Distribution 1" on 9.0.2.
The suffix is in every locale's string on the instance and in none of the
shipped files. Inferred: the importer's handling of a duplicate title. An
export is therefore a derived form. Its text is localized English, `{Deprecated}`
prefixes are hidden, and whitespace is normalized.

Confidence: high on all three lines for the build each lab runs. The one
9.0.2 limit: devel was installed as 9.0.2.0 and updated to 9.0.2.0200 on
2026-10-14. Only the 0200 vSphere pak is on disk, so 9.0.2.0's own
definitions are not available. The audit names from the 04-17 first boot
match the 10-14 re-import for 60 of the 64 renamed views, which suggests
little changed (inferred).

### Exports on the holding share (cross-checks)

Pristine means taken after first boot, before anything touched these ids,
judged from each instance's full audit history (the 8.18.7 and 9.1.1 audit
logs start at first boot, 2026-10-15 and 2026-10-14; devel's runs from
2026-04-17).

| Export | Pristine for the 120? | Evidence |
|---|---|---|
| `devel_8_18-2026-11-12-views` (10:13 CST) and `devel_8_18-2026-11-12-vcommunity-fix-test/B0` (18:42Z) | yes, 117 | No view event on these ids between first boot (10-15) and the 0.3.2 install at 18:45Z on 11-12. Identical to each other and to the stock-id baseline's 8.18.7 recon set. |
| `devel_9_1-2026-11-11-upstream-repro/baseline` (22:26Z) | yes, 120 | Taken before the 0.2.8 install at 22:32Z. No earlier event since first boot. |
| `devel_9_1-2026-11-12-vcommunity-fix-test/B0`, `...-e1-fix-test/B0` | no by provenance, yes by content | The 117 were re-imported from the repro baseline at 22:56Z on 11-11. They are identical to it for all 120. |
| `devel-2026-11-11/devel-views-ALL-before-import.zip` (16:21 CST) | yes for the 53 it holds | The last write to those ids was the 10-14 9.0.2.0200 re-import. Equal to the 0200 pak for 52, and the 53rd differs only by the " 1" suffix. |
| `devel-2026-11-12-vcommunity-fix-test/B0`, `...-repeat/R0`, `restore_views_117_from_B0.zip` | **no** for 64 | Those 64 are the 9.1.1 copies devel was restored with on 11-11. |
| `prod-2026-11-11` | n/a | Scope CUSTOM. No built-in views. |

**What devel was restored from.** On 2026-11-11 at 22:26Z, 64 ViewDefs were
copied byte for byte from an export of `prod` (9.1.1). Devel's 64 equal the
`devel_9_1` 9.1.1 definitions. On 11-12 the fix tests re-imported devel's own
B0, so those copies carried through. Devel's history also has an event the
11-11 note did not record. Upstream vCommunity 0.2.8 was installed on
2026-06-11 at 03:28Z, and its removal at 03:39Z deleted all 117 built-in
views. The factory's ports then wrote 62 to 64 of them repeatedly between June
and July. The 9.0.2.0200 update on 10-14 re-imported all 117: 105 + 4 + 8.
That is why the 53 in the 11-11 export are pristine.

**What would produce a pristine 9.0.2 export:** not needed now, because the
appliance's pak is the source. Otherwise a fresh 9.0.2.0200 deployment,
exported before any pack is installed.

## 2. Cross-line comparison (product pak definitions)

Definition = the `ViewDef` XML, normalized for attribute order and
whitespace. Localization = the `view.<id>.*` strings in en, es, fr and ja,
compared with whitespace normalized.

| Class | Ids |
|---|---|
| Identical on 8.18.7, 9.0.2 and 9.1.1 (definition and strings) | 21 |
| Same definition on all three, strings differ | 89 |
| Definition differs | 7 |
| Absent before 9.1.1 | 3 |
| Total | 120 |

Pairwise:

- **9.0.2 against 9.1.1:** definition identical for 115 of 117; English
  identical for all 117; es 89, fr 85, ja 93 ids differ.
- **8.18.7 against 9.x:** English differs for 81 ids. That is the
  description for 80 of them, plus the title of `c0b7e702`, which 8.18.7
  ships as "Capacity | VM Snapshot 1" and 9.x as "Capacity | VM Snapshot
  (Trend View)". 8.18.7 also ships de, ko, zh_CN and zh_TW, which 9.x does
  not.

Definition differs (titles as shipped on 9.1.1):

| Id | Title | What differs |
|---|---|---|
| `4d9b6ad6` | Configuration: ESXi Configuration | host property `summary|version` on 8.18.7 and 9.0.2, `summary|version_4d` on 9.1.1 |
| `524d0468` | Configuration \| Complex \| ESXi Version | same key change on 9.1.1; description differs on 8.18.7 |
| `7bcb4d10` | Configuration \| Incorrect \| Old Snapshot | 8.18.7 against 9.x: sort criteria, a column display name with localization key `snapshotAgeDays`, `isSum=false`, distribution color |
| `40152c12`, `614c2d3f`, `87399ea9`, `998cf7f2` | Capacity \| VM Memory Utilization; Configuration: ESXi CPU Model; vSphere ESXi Memory Utilization; Inventory \| Hardware Model | inline description text, 8.18.7 against 9.x |

Absent before 9.1.1: `4747af30` VCF Management Services Nodes View,
`cadb4cc0` VCF Management Services Volumes View, `df8479d3` VCF Management
Services Components View. All 117 others exist on every line.

Same definition, different strings (89): English and es/fr/ja for 76 ids:
`02230501 0a898851 0ef97d2c 0f5cd0c6 11dd432d 1fa18cd9 23b3812d 2486078e
24bd3eec 2788178d 27f6a2e8 2805f0a4 3a88e1a7 3b0e097b 3c32ba9d 40b1d206
40c5bbc9 40e416d0 41127d01 45281acb 493527e2 49b13b68 4d71034d 51ea3aa0
5c20ba39 5c3441f2 5fc79159 653ba701 680f4627 6c06a467 6d865efb 6db204b2
6dbbe2bc 6efeb9b2 6f0a54e7 72cefd21 74639bd8 7bb1bf81 7bcdb50d 7e913396
8161f003 81ef5dfc 850c16a9 8986cc9d 8d44e30e 94b25c6a 95416c42 97e71e70
9a77a4b5 9d5498ba a3849f91 a62de769 ad2f56bc b5f3660a b8af9e79 b963d4b9
ba5d47b2 bf0d0ad1 bf6bb2c6 c0b7e702 c655b25c c9fe7a11 ccfc42fb d1ba847b
d4ba9e73 de04afbf de1ff68b df2e3054 e041c79b e0e0972a e2d1f3c7 ea6cf8d9
f752ddef f83a4c60 fc20d8a6 fc64c67a`. Non-English strings only for 13:
`3a424415 3b6b0e60 3ede5e0a 617644c5 9911f98d 9a556ea6 a8b54a14`
(es/fr/ja), `c20dadab cd6c06c5` (es/ja), `42f8a97e` (es/fr), `dadb69af`
(fr/ja), `8d497409` (es), `19729c38` (ja). Full ids: `manifest.tsv` in each
artifact directory.

Identical on all three (21): `16d4447f 3b33a0a0 4d1155bd 56abf797 7888104e
7d0d858d 86d58689 9030cd79 90f20c54 9e427b59 acb921e6 c94b11bf d5b58361
d975edde e95aa10d ed44775e f129ab04 f1474ada f982ee15 fa10900c fcab0100`.

**Patch level.** No other build's content is at hand. The share's
`evidence/dashboardaction-associate/8.18.6-25423535` holds UI JavaScript
only, and no export or pak from 8.18.x other than .7, 9.0.0, 9.0.1 or 9.1.0
was found. The definitions carry no build or version marker: `ViewDef` has
only `id`, and nothing in the text is a build number. The paks themselves
are per build, so a zip is evidence only for the build it came from.
Inferred: a patch can change a view (the 9.0.2 to 9.1.1 `version_4d` change
is the kind to expect).

## 3. Restore: measured against unknown

Measured:

| When | Line | Zip | Flags | Envelope | After |
|---|---|---|---|---|---|
| 11-11 | 9.0.2 | 64 ViewDefs from a 9.1.1 export, en/es/fr/ja strings filtered to those ids, `CUSTOM` | `force=true` | VIEW_DEFINITIONS imported 64, skipped 0, failed 0 | views 787 to 851. Widgets on 29 built-in dashboards resolve by id. All 64 render server-side (`/internal/views/{id}/data/export` 200). No browser pass. |
| 11-11 | 9.1.1 | 117 from the pre-test export | `force=true` | audit: 117 imported (user admin) | export equals the pre-test export for all 120 |
| 11-12 | 9.0.2 (two runs) | 117 from devel's B0 or R0, full string bundles, `ALL` | `force=true` | imported 117, skipped 0, failed 0, errorCode NONE (both runs) | views, dashboards, reports, SMs, symptoms, alerts and groups all equal B0/R0 |
| 11-12 | 8.18.7 | the 90 the install had changed, from B0 | `force=true` | imported 90, skipped 0, failed 0 | equals B0, except 14 descriptions where the product turned tabs into spaces |
| 11-12 | 9.1.1 | 117 from B0 | `force=true` | not saved; audit shows 117 imported by admin | equals B0 for every type; dashboard diff 0 |

- Uninstall deletes the views only. Dashboard and report counts and content
  are unchanged through uninstall and restore (`compare_vs_*`,
  `dashdiff_vs_B0`), and widgets bind by id. So restoring the views repairs
  the dashboards at the API level. Browser-confirmed "The view does not
  exist" going away: **not done** on any line.
- Product updates re-apply built-in content. On devel the 9.0.2.0200 update
  (2026-10-14) re-imported all 117 ids. It brought back the ones a pack had
  deleted and overwrote the ones a pack had changed: 60 titles reverted, per
  the 11-11 note. The 9.1.1 log shows that path runs with
  `isForceUpdateContent = true`.

Unknown:

- **Built-in status after a restore.** Neither OpenAPI spec has a view
  definition endpoint (the only view path is `/internal/views/{id}/data/export`).
  The UI listing could not be read because the shared admin account had a
  live session, and the probe did not force it. Exports carry no owner for
  views, and content import maps owners for dashboards only
  (`2026-11-11-owner-mapping-dashboard-skip-reproduction.md`).
  Edit and delete protection, the owner shown, and whether the product counts
  the view as its own: unmeasured.
- **A later product upgrade.** Inferred from the 10-14 re-import: an update
  that ships the solution paks re-imports these ids with force, so a restored
  view is replaced by the new version's definition and does not get in the
  way. Measured for a 9.0.2 patch only. A 9.0.2 to 9.1.1 upgrade was not
  observed.
- **Importing the pak form.** The zips below carry the shipped XML and
  strings, not an export's localized re-serialization. That form has not
  gone through `POST /api/content/operations/import`. It is the same XML
  schema, and first boot imports it, but through the solution-install path.
  The live test should confirm it: envelope counts, then an export compared
  with the pristine export of the line (offline, these match apart from the
  " 1" suffixes; §1).
- **The " 1" suffix on restore.** Whether the import adds it again depends on
  whether a view with the same title exists at that moment (inferred).
- **Marker content.** The zips keep the source export's marker. On 9.0.2 the
  views imported with any marker content, including invented user ids (runs
  A to F2 of the owner-mapping note). Not tested on 8.18.7 or 9.1.1 with a
  foreign marker.
- **8.18.7 after a pack upgrade.** Whether a later uninstall deletes the
  restored views again: unknown, as in the 11-12 note.

## 4. Localization and companions

- Each built-in view uses `localizationKey` attributes resolved from
  `resources/content*.properties` (`view.<id>.title`, `.desc`, column keys).
  Every key the 120 use has an English entry in the shipped files. An export
  only carries strings for views that exist: after the uninstall, the
  exports held no strings for the deleted ids. So whether the instance keeps
  them is not observable, and a restore must carry them. The 11-12 restores
  carried them, and the strings came back identical.
- No report template references any of the 120 ids (9.1.1 baseline
  `REPORT_DEFINITIONS`). Dashboards reference 118 of them. Neither is deleted
  by the pack uninstall, so neither needs to be in the restore.

## Artifacts

`/mnt/holding/vcf-content-factory/builds/builtin-view-restore-2026-11-16/`:

| Path | Views | zip sha256 |
|---|---|---|
| `8.18.7/builtin-views-restore-8.18.7.zip` | 117 | `1bd51b6c...` |
| `9.0.2/builtin-views-restore-9.0.2.zip` | 117 | `d0121c34...` |
| `9.1.1/builtin-views-restore-9.1.1.zip` | 120 | `b7b8e094...` |

Each line directory also has `manifest.tsv` (id, title, sha256 of the
`ViewDef`, the three upstream sets, the product source file), `README.txt`
(admin import steps), `SOURCES.txt` (source paks with sha256) and
`ids-vcommunity-{0.1.5,0.1.6-to-0.3.1,e1-0.4.2-to-0.8.1}.txt` (41 / 117 /
117 on 8.18.7 and 9.0.2, 41 / 117 / 120 on 9.1.1). `tools/` holds the
extractor, builder and validator; `validation-2026-11-16.txt` is the offline
check output.

Format, copied from a real scope-ALL view export of the same line:

- Outer zip: `6844548499441080431L.v1` (that export's marker, content
  verbatim), `views.zip`, and `configuration.json` set to
  `{"type": "ALL", "views": N}`. Same member order and deflate as the
  export.
- Inner `views.zip`: the line's `resources/content*.properties` (8 locales
  on 8.18.7, 4 on 9.x) in the export's order, then `content.xml`.
- `ViewDef` elements are byte-for-byte as shipped.
- The strings are the shipped `view.<id>.*` logical lines. Non-ASCII
  characters are re-encoded as `\uXXXX`: the shipped files are UTF-8, the
  exports are ASCII.

Offline checks, all pass on every line:

- both zips' CRCs; member names, order and compression equal the export;
  the marker equals the export's;
- `content.xml` parses; the id set is exact, with no duplicates; every
  `ViewDef` is byte-equal to the pak's and matches the manifest sha256;
- the strings are ASCII, hold only these views' keys, and decode to the
  pak's values;
- with English applied, each view equals the pristine export, apart from the
  two " 1" titles.

`stock-id-check` counts 117, 117 and 120 view definitions under product ids,
as expected.

Menu paths in the READMEs:

- 9.0.2: Administration > Control Panel > Content Management (VCF 9.0 docs).
- 9.1.1: Operate, then Administration > Control Panel > Content Management
  (VCF 9.1 docs).
- 8.18.7: Administration > Management > Content Management, from the 8.x-era
  community PDF in `reference/docs/`. Marked unverified.

The docs' import choice "Overwrite existing content" is the UI form of
`force=true`.
