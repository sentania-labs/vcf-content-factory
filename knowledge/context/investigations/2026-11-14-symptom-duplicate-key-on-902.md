# Symptom import fails with `duplicate key ... kv_symptomproblemdefinition_pkey`: a purged tombstone, not the pak layout (2026-11-14)

**Instances:** devel (VCF Operations 9.0.2.0, build 25429562) for every
experiment; devel_9_1 (9.1.1) and devel_8_18 (8.18.7) read only (logs and
product classes).
**Question:** on devel, a pak's symptom import fails with
`SymptomDefinitionRetriever.importSymptomDefinitions - Cannot import Symptom
Definitions ... duplicate key value violates unique constraint
"kv_symptomproblemdefinition_pkey" Detail: Key
(key)=(SymptomRelationship-SymptomDefinition-<id>) already exists`. Is the cause
the pak defining the same symptom twice (H1), or rows left behind by an earlier
install or uninstall of the same id (H2)?
**Artifacts:** `/mnt/holding/vcf-content-factory/backups/symptom-dupkey-2026-11-14/`
(probe paks, step logs, REST state per step, the log history of the affected
ids, the purge log context, `javap` listings of the classes named below).
**Related:** `2026-11-14-pak-content-silent-drops.md` (section B, on the
`fix/pak-content-import-defects` branch), `2026-11-12-vcommunity-upstream-builtin-view-ids.md`
(Undetermined, last bullet), `wire-formats/symptomdef_dt_condition_import.md`.

## Answer

**H2, refined. H1 is false.** Points 1 and 2 were proven on 9.0.2 by
experiment. Points 3 and 4 come from the product bytecode and devel's own log
history.

1. A symptom defined twice in one pak, once in `content/symptomdefs/` and once
   in its alert's `content/alertdefs/` file, imports cleanly on a fresh id. The
   second copy takes the update path (T2). The old layout is not what broke the
   import.
2. Deleting a symptom never removes its row right away: pak uninstall, a pak
   upgrade that drops it, and Suite API `DELETE /api/symptomdefinitions/{id}`
   all **soft-delete** it. The `SymptomDefinition-<id>` row stays with
   `Status=Deleted`, and the `SymptomRelationship-SymptomDefinition-<id>` row
   stays with it. A re-import inside the retention window updates that
   tombstone and succeeds (T3).
3. The daily `DeletedSymptomAlertDefinitionsCleaner` hard-deletes tombstones
   older than the global setting `CANCELLED_ALERTS_SYMPTOMS_RETENTION_TIME_IN_DAYS`
   (45 on devel). It deletes only the `SymptomDefinition-<id>` row and leaves
   the `SymptomRelationship-SymptomDefinition-<id>` row behind for good.
4. From then on, every create of that id inserts both rows in one batch and
   fails on the relationship row. Every symptom in the same import batch (one
   alert file or one symptom file) fails with it. An alert that references the
   id is still created, because the alert importer checks for relationship
   rows, not symptom rows. It comes out with empty symptom sets.

On devel a 2026-06-11 pak upgrade soft-deleted nine of these ids. One (NIC) was
re-imported in July; the other eight were purged on 2026-07-31 (log history,
below). The same import code and the same
cleaner are in 8.18.7 and 9.1.1 (bytecode), so the failure does not depend on
the product version. It depends on the instance's history: devel_9_1 has never
held these ids for more than 45 days after a delete. **Inferred, not
reproduced:** the cleaner step was not run on probe ids, because forcing it
means lowering a global retention setting that also purges real data (see
"Not done").

The premise that "eight of ten ids import fine" is also wrong. On devel only
two of the ten import (`ESXi Host NIC Disconnected`, `vCommunity Collection
Warnings`). The seven License conditions fail as one batch: the log names only
the first conflicting key (`9803e6a3`), and `condition_self` symptoms never
appear on `/api/symptomdefinitions`, which hid the other six.

## Test matrix (devel, 9.0.2)

Probe paks were built from a copy of the SDK template project. Each pak has its
own adapter kind (`zzprobe_a`, `_b`, `_c`) and fresh random ids. Each holds an
alert with two `condition_self` conditions (one per OR set, the License alert's
shape) and a second alert on one standalone symptom, all on `VMWARE:HostSystem`
with stock `cpu|usage_average` / `mem|usage_average` keys, disabled in the base
policy. OLD layout = built by `main` (each symptom in `symptomdefs/` and in the
alert file); NEW layout = built by the fix branch (each symptom once, in its
alert file). Layouts were confirmed by unpacking each pak.

| Step | What | Result |
|---|---|---|
| T1 | NEW layout (A 0.0.0.1), first install | All three symptoms `ADDED`, both alerts complete (2 conditions; 1 symptom). No error. |
| T2 | OLD layout (B 0.0.0.1), first install | All imported. The `alertdefs/` copies were created first (`ADDED`), then each `symptomdefs/` copy logged `Updating adapter-defined Symptom Definition ...` and `type=UPDATED`. No error. **H1 refuted.** |
| T3a | Uninstall A, then reinstall the same pak | Uninstall logs `type=UPDATED` (not `DELETED`) for each symptom: a soft delete. Afterwards `GET /api/symptomdefinitions/{id}` still returns **200** for the standalone symptom, but it is gone from the list and alerts are 404. Reinstall: `Updating adapter-defined Symptom Definition` / `type=UPDATED` for all three, alerts complete. |
| T3b | Uninstall B, then reinstall | Same as T3a: soft delete (`type=UPDATED`), then all symptoms take the update path (`Clobbering the user modified definition ... with a pristine`, the same lines NIC logged on devel in July), alerts complete. Both copies of each symptom imported again. |
| T4a | Upgrade A 0.0.0.1 to 0.0.0.2, identical content | No delete event. Every symptom and alert `Updating adapter-defined ...` / `type=UPDATED`, alerts complete. |
| T4b | Install C 0.0.0.1 (OLD), upgrade to C 0.0.0.2 (NEW, same ids) | Install as T2. The upgrade drops the `symptomdefs/` files, but the ids still ship in the alert files, so nothing is deleted (no `SYMPTOM_DEFINITION_DELETE`). Every symptom and alert updated in place, alerts complete. |
| T4 +10 min | Re-read all three paks 10 min after the last upgrade (19 min for A) | Unchanged: each standalone symptom present, each inline alert with both conditions, each standalone alert with its symptom. No further log line for any probe id. |
| T5 | `POST` then `DELETE /api/symptomdefinitions/{id}` | DELETE 204; then GET by id **200** with the full definition, absent from the list, a second DELETE **404** "No such SymptomDefinition". The public delete is a soft delete too. |

## The devel history that produced the stuck ids

From `analytics` and `analytics.audit` logs back to 2026-04-23
(`history/devel_id_history.txt`, `history/purge_2026-07-31_context.txt`):

| When (UTC) | Event |
|---|---|
| 2026-06-11 03:29 | Upstream Python vCommunity installed (pak directory `iSDKVCFOperationsvCommunity-028`). All 7 License conditions import as one batch, plus NIC and Windows, **each of those two twice** (symptomdefs and alert file), all succeed. Same duplicate layout as build 15, ids new to the instance (no earlier log line since 2026-04-23), on 9.0.2. |
| 2026-06-11 03:39 | Upgrade to the next upstream build (`iSDKVCFOperationsvCommunity-100`): `Deleting symptom definition(s) succeeded` for 9 ids; the KV notifications say `type=UPDATED`, i.e. soft delete. |
| 2026-06-22 to 07-09 | Another pak's alerts (`AlertDefinition-VMWARE-Windows_Service_Down`, `...ESXi_Host_NIC_Disconnected`) are created referencing the tombstoned ids; "Cannot get symptom definition" warnings. |
| 2026-07-10 to 07-16 | NIC (`c8d1e671`) is imported eight times: `Clobbering the user modified definition ... with a pristine`, `type=UPDATED`. The tombstone is revived inside the window. |
| 2026-07-31 16:13:17 | `Symptom update: ... type=DELETED` for exactly 8 ids: the 7 License conditions and Windows `7675759b`. Also 3 alert tombstones. 50 days after the soft delete: the cleaner ran (45-day retention, daily). NIC was not among them, because it was live again. |
| 2026-11-12 to 11-14 | Every import of the License batch fails on `...9803e6a3` and every import of Windows on `...7675759b` (upstream 0.3.1 and the fix build, both layouts, factory builds 15 and 16). NIC imports every time; `Collection Warnings` (`dc3a1b70`, new on this instance 11-13) imports every time. |

So what separates the two failing ids from the ones that import is history, not
content: they are the ones whose tombstones were purged. "Windows Service Status
Down" having two names upstream, and `9803e6a3` being the first inline
condition, play no part. `9803e6a3` is only the first conflicting row of its
batch to reach the database.

On devel_9_1 the same ids were imported, uninstalled and re-imported five times
between 2026-11-11 and 11-14, both layouts, all successful
(`history/devel_9_1_id_history_summary.txt`). That instance's logs start
2026-10-14, so no tombstone of these ids there is older than 45 days.

## Mechanism (bytecode, 9.0.2; same in 8.18.7 and 9.1.1)

Read-only `javap` of `persistence-1.0-SNAPSHOT.jar`,
`vcops-collector-controller-1.0-SNAPSHOT.jar`, `vcops-analytics-1.0-SNAPSHOT.jar`
and `vcops-platform-1.0-SNAPSHOT.jar` (listings in `bytecode/`).

- **Storage.** Both rows live in KV table `SymptomProblemDefinition`
  (`kv_symptomproblemdefinition`): `SymptomDefinition-<id>` and
  `SymptomRelationship-SymptomDefinition-<id>`, a `SymptomRelationship`
  (`symptomId`, `problemIds` = the alerts that use the symptom). Alert rows sit
  in the same table.
- **Create.** `SymptomDefinitionDataService.createOrUpdateSymptomDefinitionInt`
  calls `getSymptomDefinition(id)`. If null, it builds a **new**
  `SymptomRelationship(id)` (version 0). If not null (live **or tombstoned**),
  it reads the existing relationship through `getSymptomRelationships`. Either
  way, `UserDataService.saveSymptomDefinitions` writes the symptom and its
  relationship in one `batchPutDelete`. The failing statement is an `INSERT
  ... (col__kv_strvalue, col__kv_valuetype, col__kv_version, key)`. That a
  version-0 object is written as an insert is read from that SQL, not from the
  KV layer's code. So when an orphan relationship row exists, the fresh
  relationship collides with it.
- **Delete.** `SymptomDefinitionRetriever.deleteSymptomDefinitions(Collection)`
  (the public path) calls the private overload with `(soft=true, force=false)`.
  `SymptomDefinitionDataService.deleteSymptomDefinition(id, true)` sets
  `STATUS_DELETED`, and `UserDataService.deleteSymptomDefinition(data, rel,
  true)` **puts** both rows back (a tombstone). Only `soft=false` removes both
  rows, which is what `deleteSymptomDefinitionsForAdapterKind` passes.
- **Purge.** `DeletedSymptomAlertDefinitionsCleaner` (a daily
  `DistributedScheduler`; `oldDataCleanerExecutionFrequency=1` in
  `analytics/advanced.properties`) selects symptoms with metadata
  `Status=Deleted` and `deletionTimeUtc` older than
  `GlobalSettingsHelper.getAlertRetentionDays()`, which reads
  `CANCELLED_ALERTS_SYMPTOMS_RETENTION_TIME_IN_DAYS`. It `batchPutDelete`s
  **only those `SymptomDefinitionData` objects**. Nothing touches the
  relationship rows. Its log lines are below the default level; the only trace
  is the `type=DELETED` KV notification.
- **Alert import.** `UserDataService.getSymptomRelationships` is the alert
  importer's dependency check ("Cannot create alert definition ... because
  dependent symptoms" when a relationship row is missing). An orphan row passes
  that check, so the alert is saved pointing at a symptom that does not exist.

The cleaner's symptom loop and the create path are the same in the 8.18.7 and
9.1.1 classes (`saveSymptomDefinitions` on 8.18.7 has a two-argument form; the
version-0 relationship is built the same way).

## Reading an id's state without the database

| Read | Live | Tombstone (soft-deleted, revivable) | Purged or never existed |
|---|---|---|---|
| `GET /api/symptomdefinitions/{id}` | 200 | **200** | 404 |
| in `GET /api/symptomdefinitions` (list) | yes | no | no |
| `DELETE /api/symptomdefinitions/{id}` | 204 | 404 | 404 |

A `condition_self` symptom is 404 by id in every state (as already recorded).
Whether a 404 id has an orphan relationship row (purged) or none (never
existed) cannot be read from the API. The audit log history is the only
non-database evidence: a `SYMPTOM_DEFINITION_DELETE` older than the retention
setting with no import after it.

Consequence for checks: the fix branch's post-install content check
(`report_pak_content`) counts a standalone symptom as present on a GET by id,
which a tombstone also satisfies. Only the list, or an alert whose symptom set
names the id, proves a symptom is live.

## Recovery

**No API recovery exists for a purged id.** It needs the orphan relationship
row deleted, and every API path that deletes it first needs the symptom row:
symptom delete is soft and needs the definition, and the hard delete runs only
per adapter kind over existing definitions. Alert deletes rewrite relationship
rows; they never remove one. Re-creating the symptom is the failing insert
itself. The remaining routes are deleting the row in the database (Broadcom
support; not attempted, out of scope) or **giving the symptom a new id**.

Not tested on probes: the stuck state could not be reproduced (see "Not done").
On the affected pak the API was not touched, as briefed.

For an id that is only **tombstoned** (deleted under 45 days ago), recovery is
just re-importing it before the cleaner runs: T3, and NIC on devel in July.

## What this means for the factory

**(a) Layout, all three versions.** The layout does not cause the failure and
neither layout prevents it. The fix branch's layout (each symptom once, inside
its alert file, plus the gate against duplicates) stays correct: it is the
vendor shape, and it avoids redundant update passes. But the claim in
`2026-11-14-pak-content-silent-drops.md` section B that "the second definition
breaks 9.0.2" is wrong and should be corrected there. Layout is not a 9.0.2
issue on 8.18.7, 9.0.2 or 9.1.1.

**(b) Ids are burned 45 days after a delete.** On any instance, a symptom id
that is deleted (uninstall, an upgrade that stops shipping it, or a user or
API delete) and not re-imported within `CANCELLED_ALERTS_SYMPTOMS_RETENTION_TIME_IN_DAYS`
(45 days on devel, a per-instance global setting) can never be created again
on that instance. Every symptom in the same import batch fails with it, and
the alerts that use them install empty. For the factory:

- A pak that keeps the ids of the upstream vCommunity pack will fail on every
  instance where an upstream vCommunity version was uninstalled or upgraded
  away more than 45 days earlier. On devel that is 8 of its 10 symptom ids.
  Giving those symptoms new ids is the fix; that changes RULE-007 identity for
  those objects, a decision for Scott.
- **Upgrades of factory paks are safe** while a release keeps shipping its
  symptom ids: an upgrade re-imports them in place. The risk is a release that
  drops a symptom and a later release that brings the same id back, or a
  reinstall more than 45 days after an uninstall. Both re-create a purged id.
  Do not resurrect a dropped symptom id; mint a new one.
- Alert ids are probably affected the same way (the cleaner purges alert
  tombstones too, and the 07-31 run purged 3), but alerts have no relationship
  row, so the duplicate-key failure is not expected there. Not tested.
- Keep alert files small: one batch is one alert file, so an orphan takes out
  every symptom in that file. With the fix branch's grouping (alerts sharing a
  symptom share a file) one burned id can empty several alerts.
- The installer cannot see this from the import envelope. The fix branch's
  `CONTENT INCOMPLETE` check (alert symptom sets compared with the pak) does
  catch it. Its symptom-by-id check does not, see above.

## Not done, and why

- **Reproducing the stuck state on probe ids.** It needs the cleaner to purge a
  probe tombstone. That waits 45 days, or the global
  `CANCELLED_ALERTS_SYMPTOMS_RETENTION_TIME_IN_DAYS` is lowered for a day. The
  same setting retains cancelled alerts and symptoms, and the cleaner would
  also purge every older real tombstone on devel, creating more orphan rows for
  real ids. Not run without Scott's go-ahead. If approved: lower it, wait for
  the next daily run (or watch for `type=DELETED`), reinstall a probe pak, and
  restore the setting.
- Recovery was not tried on the real pak's ids, as briefed.

## Leftovers on devel from this investigation

All three probe paks are uninstalled. The API lists no `ZZ Probe` symptom,
alert or recommendation and no `zzprobe_*` adapter kind. Before and after the
work (`devel/pre`, `devel/post`, `compare_pre_post.txt`), the instance holds
the same 1309 alerts, 2026 symptoms and 1117 recommendations by full
definition, the same solutions and the same adapter kinds. The 11 content-type
exports also match. The only differences were list order (18 alert
definitions, `policies.xml`, equal once sorted) and the dashboard export's
per-export `uuid` and properties timestamp, which change on every export. The
installed vCommunity pak, its instance and its content were not touched.

**What 9.0.2 leaves behind, and the API cannot remove:** soft-delete
tombstones for 10 probe symptoms (9 from the paks, 1 from T5) and 6 probe
alerts. Of these, the 3 standalone pak symptoms and the T5 symptom are still
readable by id (200); the conditions and alerts are not. A second `DELETE`
returns 404, so they cannot be removed. In 45 days the cleaner will purge them
and leave orphan `SymptomRelationship` rows for those 10 ids. That is harmless,
because the ids are random and never reused, but it is permanent without
database access. Every factory pak uninstall leaves the same thing.
