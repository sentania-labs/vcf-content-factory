# Framework review: pak content layout, content gate, post-install content check

- **Branch / commit:** `fix/pak-content-import-defects`, `fa55f1b9` on `549c560a`
- **Area:** `src/vcfcf_managementpacks/sdk_builder.py`, `post_install_content.py`,
  `installer.py`, `cli.py`, `buildkit.py`; `src/vcfcf_core/packaging/pak_content.py`
- **Date:** 2026-11-14
- **Verdict:** CHANGES REQUESTED (2 BLOCKING, 4 WARNING, 5 NIT)

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (worktree) | all rc 0 |
| `scripts/path_reference_audit.sh` | clear (2 standing RULE-015 warnings, pre-existing) |
| Full suite, CI flags without xdist, head vs base on identical copies (same `content/sdk-adapters/` and `reference/references/`) | head 4924 passed / 8 failed / 11 skipped; base 4901 / 8 / 8. The 8 failures are the same test ids on both sides (missing `jmespath`, doctor venv tests, a recursion-depth test): environment, not this change. +23 passed are the new tests. The 3 extra skips are SDK-jar skips (environment). |
| Content render, base vs head, six registered projects (`_write_outer_pak` on copies) | Claims confirmed exactly: vcommunity-java differs only by 10 `symptomdefs/` files removed and 39 `content.properties`; the 4 alert files byte-identical; definition counts unchanged on every project; base gate problems 63 / 20 / 20 / 1 / 0 / 0 (vcj, synology, unifi, vsanperf, compliance, template), head 0 everywhere. synology: 2 alert files merged away (Storage Degraded, Volume Not Healthy), unifi: 2 merged away (Gateway Offline, Switch Offline). |
| Determinism | synology and unifi rendered twice under different `PYTHONHASHSEED`: byte-identical trees. Group order is `adapter.yaml` list order. |
| Properties round trip | 21 hostile values (`=`, `:`, `#`, `!`, leading space/tab/FF, backslashes, `A` literal, CR/LF/CRLF, U+2028, NEL, BOM, 5000 chars, non-ASCII) through `_properties_line` and back through `vcfcf_core/java_properties.py` **and real `java.util.Properties`** (UTF-8 reader): all values exact. Keys: see N1. |
| Post-install replay against p6 evidence | 0.0.0.15 inventory + saved `live.json`/`defs.json`: devel (9.0.2) 18 lines = the 14 views, 1 report, Windows symptom, License alert lost 7/7, Windows alert lost 1/1; devel_9_1 (9.1.1) 15 lines = the 14 views and 1 report, no false alarm on the 7 `condition_self` symptoms. |
| Assembled buildkit 1.0.29 | assembles; `validate-sdk` from the kit (no `PYTHONPATH`) passes vcommunity-java, synology, unifi; kit `sdk_builder._pak_content` is the kit `pak_content`. |
| `validate-sdk` writes into the project? | No file under the project copies changed. |
| Stale-zip / template version | No file in the stale-zip list is touched; `CURRENT_TEMPLATE_VERSION` not in scope. Buildkit 1.0.29 is untagged (latest tag `sdk-buildkit-v1.0.27`), so keeping the version is right. |

## Evidence the change did not cite

Two artifacts decide most of the "try to break it" questions.

**1. The 9.0.2 installer bytecode** (`/mnt/holding/vcf-content-factory/evidence/owner-mapping-dashboard-skip/9.0.2-25429562/original/vcops-view-server-1.0-SNAPSHOT.jar`, `javap -c -p SolutionManagerDistributedTask`):

- `installContent` passes **one** symptom-id set (local 10) to both
  `installAlertDefsContent` (as its 4th argument, filled from
  `ImportExportResultDto.importedSymptomDefinitionIds`) and
  `installSymptomDefsContent`. Alert and recommendation ids likewise come
  from the DTO, never from a file name.
- `removeObsoleteContent` computes obsolete per type as recorded-before minus
  this run's set, guarded by `symptomDefinitionIdsInstalled`.
- So on 9.0.2 pak content is tracked **by id per type, not by file or
  directory**. Moving a symptom from `symptomdefs/` into an alert file, or
  merging alert files, does not change identity or bookkeeping, provided the
  alert-type import reports the embedded symptom ids in the DTO (the bridge
  server is not in hand; probe 2 below shows it does).

**2. The factory's own 9.0.2 probe run** (`/mnt/holding/vcf-content-factory/backups/symptom-dupkey-2026-11-14/`, run 08:49 to 09:48Z with this branch's code as `fx16`): three probe paks with fresh UUIDs, each 2 `condition_self` symptoms, 1 standalone symptom, 2 alerts.

| Step | Layout | Result (list endpoint, alert JSON) |
|---|---|---|
| T1 install A | new (alert files only) | all present, conditions intact |
| T2 install B | **old: every symptom in `symptomdefs/` and again in its alert file** | **all present, no duplicate-key error**; analytics logs `Updating adapter-defined Symptom Definition` for the second copies (an upsert) |
| T3a/T3b uninstall + reinstall A, B | both | uninstall removes the alert-file-only symptoms from the list (so they are recorded); reinstall restores |
| T4a upgrade A 1 to 2 | new to new | intact |
| T4b install C old, upgrade to C new | **old to new** | standalone symptom still in the list, alerts intact, also 10 min later |
| cleanup | | every probe symptom gone from the list |
| T5 REST create/delete | | `DELETE` 204, then `GET /api/symptomdefinitions/{id}` **200 with the full body**, absent from the list, second `DELETE` 404 |

## BLOCKING

### B1. Defect B's stated cause is contradicted by the factory's own probe, and the PR codifies it as fact

Authority: the probe above (T2), `knowledge/rules/source-of-truth.md` (RULE-001: repo and lab evidence is the source of truth), reviewer doctrine (unproven claims are findings).

Probe B shipped the exact 0.0.0.15 defect, every symptom defined twice, and
installed on the same 9.0.2 instance with **no** `kv_symptomproblemdefinition`
error and nothing lost. Duplicates inside a pak are upserted on 9.0.2. Order
also argues against the stated mechanism. `installContent` imports
`alertdefs/` before `symptomdefs/`, so on the fresh 0.0.0.15 install the
License and Windows alert files failed on their first insert, before any
`symptomdefs/` copy had been read. The failing ids (`7675759b` Windows,
`9803e6a3`, `7a5c6ce4` License conditions) have devel history going back to
June and appear around a 2026-07-31 purge (`history/devel_id_history.txt`).
`dc3a1b70` (Collection Warnings) has no history before November and imported
fine. One counterexample: `c8d1e671` (NIC) has June history and also imported
fine, so instance history is a lead, not a proven cause. **What causes the
9.0.2 duplicate key is unknown. The duplicate in the pak is ruled out as
sufficient.**

The claim appears as fact in:

- `src/vcfcf_core/packaging/pak_content.py:18-22` (module doc) and
  **`:155-160`, the gate's error text** ("on VCF Operations 9.0.2 the second
  definition fails the import (duplicate key) and what referenced it loses
  it"). That text is printed for any type, super metrics included, with no
  evidence for any of them.
- `src/vcfcf_managementpacks/sdk_builder.py:3766-3772` (comment) and the
  `plan_alert_content_files` / `_write_outer_pak` docstrings.
- `knowledge/context/tier2_architecture.md:520-522` and its changelog row.
- `knowledge/context/wire-formats/alert_fidelity_wire_format.md:81-89`.
- `knowledge/context/investigations/2026-11-14-pak-content-silent-drops.md` §B.
  It also still says "Inferred, not yet measured: that 9.0.2 imports every
  symptom ... with no duplicate". The probe measured exactly that (A, C).

If shipped as-is, a rebuilt vCommunity Java pak on devel 9.0.2 will probably
lose the Windows symptom and License conditions again. The docs will have
taught every later agent a false cause, and the investigation is closed on
it.

**Fix:** keep the layout. It is the vendor shape (Physical SAN, Kubernetes
paks), it is unambiguous, and it is proven on 9.0.2 at probe scale for
install, upgrade and uninstall. Rewrite every site above to say what is
proven:

- Each id is defined once per pak as a factory policy (vendor shape; which
  copy wins when two copies differ is not specified).
- On 9.0.2 a pak with every symptom defined twice imported cleanly
  (probe B).
- The 0.0.0.15 duplicate-key loss is unexplained. It correlates with ids
  that have history on devel, and the next step is a fresh-id rebuild of the
  License alert's shape: 7 conditions on one instanced metric key.

Give the gate message a neutral form. Cite the probe set in the investigation
beside the p6 set.

### B2. The post-install symptom check reads a cache that answers 200 for deleted symptoms

Authority: probe T5 and T3a (above), `post_install_content.py:146-151` and
module doc lines 16-17 ("200 present, 404 absent"). Reviewer dimension 8
(reports green while broken).

On 9.0.2, `GET /api/symptomdefinitions/{id}` returned 200 with the full
definition for a symptom deleted with REST (T5), and for symptoms a pak
uninstall had removed (T3a; final cleanup). The list endpoint had already
dropped them. The by-id read is truthful only for a symptom that was never
created, which is the 0.0.0.15 fresh-install case, so the replay passes. It
lies on exactly the path this layout change puts at risk: an upgrade or
reinstall where `removeObsoleteContent` or an uninstall deletes symptoms.
The check would print `CONTENT OK` over missing symptoms.

**Failing scenario:** upgrade a pak whose new version loses a symptom (for
example, an alert file whose symptom batch fails on the upgrade, so the id is
missing from this run's set and is removed as obsolete). The by-id GET says
200, and the install exits 0.

**Fix:** read presence from the list endpoint (`GET /api/symptomdefinitions`
paged, or `?id=` repeated, as the probe's `all_symptomdefs` did). Add a test
whose fake answers 200 by id but leaves the symptom out of the list.

## WARNING

### W1. A non-JSON 200 or any non-transport error escapes the content check as a traceback

`post_install_content.py:139-157`. `_get` wraps only `_request`. `r.json()`
(a proxy or maintenance page, an empty body) raises `ValueError`, which
`check_installed_content` does not catch (it catches only
`ContentUnreadable`). Reproduced with a fake suite: `ESCAPED: ValueError`.
After a successful install the CLI dies with a traceback and exit 1, and the
three-way 0/3/4 contract is lost.

**Fix:** convert any exception in `read_live_content` into
`ContentUnreadable` (`UNCHECKED` warning, as the module promises), and test
it.

### W2. Views are matched only on `viewDefinitionKey`; the repo records thumbnails that carry only `id`

`post_install_content.py:75-87`. `src/vcfcf_packaging/templates/install.ps1:4085-4091`
and `install.py:2865` exist because some `getGroupedViewDefinitionThumbnails`
entries carry `id` and no `viewDefinitionKey` (#116). On a build that
answers like that, every such view of the pak reads as `CONTENT MISSING`:
exit 3, a false alarm. 9.0.2 and 9.1.1 carried the key on every entry
(p6 `live.json` was built with `v['viewDefinitionKey']`), and 8.18.7 was not
measured.

**Fix:** fall back to `id` the way the installers do.

### W3. Merged alert files remove an independent import path and widen the blast radius; not documented

`sdk_builder.py:3283-3343` (`plan_alert_content_files`). Authority:
`knowledge/context/wire-formats/symptomdef_dt_condition_import.md`
("The symptom batch in one file is all-or-nothing").

Before this change, a symptom whose alert-file batch failed still came in
through its own `symptomdefs/` file. On Synology 0.0.0.35, every symptom but
the DT one landed that way. Now:

- synology `Expansion Unit Lost.xml` carries 2 alerts, 8 symptoms and
  2 recommendations;
- unifi `Access Point Offline.xml` carries 3 alerts, merged only because they
  share a recommendation.

One bad definition in either file now drops every symptom and alert in it,
on every version. The post-install check would at least make that loud (once
B2 is fixed). Merging on a shared recommendation is policy only: B1 removes
the evidence that a duplicate recommendation is harmful.

**Fix:** document the trade-off in `tier2_architecture.md` and the
investigation. Consider merging on shared symptoms only. Either way, cover a
merged group in the live proofs below.

### W4. Upgrade of already-shipped paks: proven on 9.0.2 at probe scale only

Known, from 9.0.2 bytecode and probe T4b:

- ids are tracked per type, from both directories;
- file names play no part;
- an old-to-new upgrade keeps a symptom that moved into the alert file, and
  the alerts keep their conditions;
- uninstall removes alert-file-only symptoms, so they are recorded.

Unknown:

- 9.1.1 and 8.18.7: no bytecode in hand, no probe. RULE-019 requires all
  three versions.
- Real shapes: synology's merged groups, the DT group, unifi's recommendation
  shared three times.
- Active-alert continuity: the compliance-86 review question still applies.

Synology, unifi and vsanperf have shipped the old layout. Do not release a
rebuilt pak for them until the live list below is green.

## NIT

- **N1.** `sdk_builder.py:3000-3008`, `_java_properties_escape_key` does not
  escape a leading `#`/`!` or tab, CR/LF or FF. A dashboard named
  `#Dash: a=b c` loses its entry (it is read as a comment; confirmed with real
  Java). The dashboard gate checks only empty values, so it misses this.
  Escape them, and make the gate re-read every expected key.
- **N2.** Values are written raw UTF-8. The encoding the importer uses for
  `content/reports/*/resources/` is not recorded anywhere, and an ISO-8859-1
  `Properties.load(InputStream)` mojibakes them (confirmed). Writing
  `\uXXXX` escapes for non-ASCII characters makes the file correct under
  either reader.
- **N3.** The gate ignores duplicate property keys. The 0.0.0.15 pak had them
  in 10 directories (`config_storageDevice_multipathInfo_numberofActivePath`,
  `net_usage_average`, ...), from columns whose attribute keys sanitize to the
  same key (the `6c59f6b` pattern, harmless here because the XML references no
  keys). Those views imported on both versions (`8f50f651`, `a54e74b2`, ...
  present). Record "duplicate keys tolerated, proven" in
  `view_column_wire_format.md` so the next change does not gate on it, or
  start gating on it.
- **N4.** `sdk_builder.py` `_dry_render_content_problems` redirects all of
  the render's stderr, so validate-sdk never shows the new
  "`condition_*` symptom with no alert" warning (or any other render
  warning). Surface the warning lines.
- **N5.** `buildkit.py:379/443` and `:386/436` define `alerts_loader.py` and
  `symptoms_loader.py` twice in `_IMPORT_REWRITES`. The first entries (the
  `rendered_id_collisions` rewrites) are dropped, so the kit's
  `alerts_loader.load_dir` still has `from .render import ...` and its
  `symptoms_loader.load_dir` still has `from vcfcf_core.alerts.render import ...`
  (verified in the assembled kit). This change does not make it live: the kit
  calls `load_file` only. The file is touched by this branch, so merge the
  lists here.

## Answers to the brief's specific questions

- **Upgrade deletes symptoms / changes ids?** Ids are unchanged (same
  `id:` / `_symptom_id` derivation, and the render diff shows byte-identical
  alert files on vcj). Deletion: on 9.0.2, no (bytecode plus probe T4b).
  9.1.1 and 8.18.7 are unknown (W4).
- **File naming:** the first alert's id-basis name. Deterministic. Not part
  of identity on 9.0.2 (bytecode). Merged-away files leave nothing behind,
  because the installer records ids, not files.
- **Several AlertDefinitions in one file:** the vendor corpus does this
  (cited in the investigation). The schema is
  `alertDefinitionSchema.xsd` in the SDK reference. Not independently
  re-verified here beyond the investigation's corpus note.
- **Symptom also used outside the pak:** it is still defined by id, now from
  the alert file. A failed alert-file batch loses it with no fallback (W3).
- **Empty display name:** the XML carries no `displayName` and no
  `localizationKey` (the gate's dangling-key check passes on all projects).
  That is the source pak's shape, which imported on 8.18.7. What label the
  product shows was not visually verified (live item 8).
- **Gate false negatives:** ids inside zips under `content/` are scanned
  (`scan_bytes` recurses). `adapters.zip` is outside `content/` and is
  ignored by design. A different-type same-id pair is not a duplicate, which
  is correct.
- **Release builds** delete the failing pak (test present). Dev builds leave
  it.

## Must be proven live before any already-shipped pak is rebuilt and released

1. **9.0.2, rebuilt vCommunity Java, fresh install on devel:** do the Windows
   symptom and License conditions land? Read symptoms from the list
   endpoint. B1 predicts that they may not.
2. **9.0.2, an instance or ids with no history:** a fresh-UUID probe of the
   License alert's shape (7 `condition_self` on one instanced metric key).
   This separates shape from instance history.
3. **9.1.1 and 8.18.7, upgrade synology and unifi from the shipped
   (duplicated) build to the new layout:** before and after, list-endpoint
   symptom ids, alert symptom sets and conditions, recommendations attached
   to each alert, no id changes, nothing deleted in the minutes after the
   import (the 9.x obsolete-removal timing).
4. **The same upgrade on 9.0.2 at synology scale**, including the DT group.
5. **Uninstall after each upgrade:** the alert-file-only symptoms are
   removed, and nothing else is.
6. **Active alerts survive the upgrade** with the same alert ids and start
   times.
7. **The post-install content check (after B2/W1/W2)** agrees with
   list-endpoint truth on every run above, and gives no false alarm on 9.1.1.
8. **A view column with no localization entry** shows the metric's default
   label in the browser.
