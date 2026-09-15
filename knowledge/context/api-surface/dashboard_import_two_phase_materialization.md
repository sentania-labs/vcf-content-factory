# Dashboard import is a two-phase replace: `importComplete`, `entryKeys`, and why widget `config` comes back empty

Investigated 2026-09-15 on `devel` (VCF Operations **9.0.2**,
`vcf-lab-operations-devel`, marker `6844548499441080431L.v1`).
**Posture: read-only.** GETs plus one `POST /api/content/operations/export`
(an export creates no content and mutates nothing). No import, no delete,
no enable, no edit. The deliberately-broken dashboard and the
imported-from-another-lab content were read and left untouched.

> **UNSUPPORTED ENDPOINTS.** The per-widget config store is read through
> `POST /ui/dashboard.action` (`mainAction=getWidgetConfigs`,
> `getDashboardList`). That is the Struts UI layer, not the Suite API. It
> carries the same no-back-compat warning as every `/ui/*.action` and
> `/internal/*` call (the latter also needs
> `X-Ops-API-use-unsupported: true`). Do not build a product behaviour on
> it without a fallback.

## The one-line answer

Importing a dashboard that already exists is a **uuid-keyed replace that
lands in a deferred state**, and the "hollow" read is that deferred state,
not damage. Phase 1 (synchronous, inside the import operation) writes the
record, widgets, layout and `states`, sets `importComplete: false`, and
parks the bundle's portability table in `entryKeys`. Phase 2
(asynchronous, minutes to hours later) resolves those tokens to this
instance's internal ids, writes each widget's `config`, clears
`entryKeys`, and flips `importComplete: true`. **Both dashboards in the
report have since completed phase 2 on their own and are fully bound
right now.** Nothing was broken and nothing needs repairing.

The real failure mode is different and is also present on this instance:
phase 2 **stalls permanently** when a referenced adapter kind is not
installed on the target.

---

## Q1. What does the import do to an existing dashboard?

**A uuid-keyed replace of the whole record, not a merge and not a
field-level upsert.** Two pieces of evidence.

**The spec.** `POST /api/content/operations/import`
(`operations-api.json`, `operationId: importContent`) documents a `force`
query parameter, `"True to force solution content overwrite"`, and the
operation description says *"If the force option is set to true, content
will be overwritten. By default the flag is true."* The factory's
`import_content_zip` (`src/vcfcf_dashboards/client.py`) hard-codes
`params={"force": "true"}`, so every factory import is in overwrite mode.

**The timestamps.** On the replaced dashboards, `creationTime` was reset
to the import time and now equals `lastUpdateTime`:

```
66ec0811 (vSAN Cluster Health)  created=2026-09-15 00:41:59  updated=2026-09-15 00:41:59
f5a14e9c (Cluster Cost Details) created=2026-09-15 00:35:27  updated=2026-09-15 00:35:27
b6796122 (CPU Support Status)   created=2026-07-29 13:57:22  updated=2026-07-29 13:57:22   <- untouched sibling
```

A merge or an in-place field update would have preserved the original
`creationTime`. It did not survive, so the record is **destroyed and
recreated under the same uuid**. That is the mechanical reason the
resolved widget config disappears: there is nothing left to merge it into.

**What the operation summary does and does not tell you.** The
`import-operation-summary` schema defines `imported` as *"The number of
objects in content"*. It is a count of objects **processed**, not objects
**changed**. `state: FINISHED`, `errorCode: NONE`, `imported: 1`,
`errorMessages: []` is therefore a truthful report that phase 1 succeeded,
and it is **structurally incapable** of reporting on phase 2, which has
not run yet when the operation finishes. The product is not lying. It is
answering a narrower question than the one being asked of it.

## Q3. Where widget `config` lives, and why `states` survived

This is the load-bearing finding, and it explains the `states`-vs-`config`
asymmetry exactly.

Export **externalizes** every instance-local identifier in a widget config
into a portable token, and records the mapping in a top-level `entries`
table in `dashboard/dashboard.json`. The same field, same widget
(`66ec0811`, the vSAN cluster picker), read from the two surfaces:

```
in the export zip     "tagFilter": {"path": ["/source/kind/kind:resourceKind:id:6_::_"]}
live, getWidgetConfigs "tagFilter": {"path": ["/source/kind/kind:002028VirtualAndPhysicalSANAdapterVirtualSANDCCluster"]}
```

with the export's `entries` table carrying the translation:

```json
{"resourceKindKey": "VirtualSANDCCluster",
 "internalId": "resourceKind:id:6_::_",
 "adapterKindKey": "VirtualAndPhysicalSANAdapter"}
```

So the config in the bundle is **not directly installable**. It is a
template that must be re-resolved against the target's own internal ids
before it can be written. That resolution is phase 2. The importer
deliberately does not copy `config` through verbatim, because on a
different instance the verbatim bytes would be wrong.

`states` needs none of this. It is an opaque URL-encoded UI blob (column
widths, sort order, hidden columns) containing no instance-local
identifier, so phase 1 carries it through untouched. That is why it
survived every import while `config` did not. The asymmetry is the design,
not a symptom.

Confirmed on an un-materialized widget, where the two fields sit side by
side in the same object:

```
2679c78f (MSSQL) widget[0]  config: {}   states: [{"value": "o%3Acolumns%3Da%253A..."}]   <- full
```

## Q4. `importComplete: false` is a real state, and it has a partner field

`importComplete` and `importAttempts` are dashboard-level fields in the
export document. **Neither appears anywhere in `operations-api.json` or
`internal-api.json`** (grepped both, plus the 9.1 copies): they are
undocumented, observable only in an export or the pak/vendor JSON.

The undocumented partner field is the one that makes the state legible:
**`entryKeys`**. It is non-null on exactly the dashboards with
`importComplete: false`, and `null` on every completed one. Across all 13
dashboards in the owner's export, with no exceptions:

```
id        importComplete  entryKeys
46f75705  true            null
b6796122  true            null
be78532e  true            null
762fc025  true            null
2679c78f  false           {"resourceKind": [...7 entries...], "resource": [...], "uuid": ...}
a426553b  false           {"resourceKind": [...], ...}
4050cc4a  true            null
62652554  true            null
9c6a3e0a  true            null
66ec0811  true            null
f5a14e9c  true            null
2311a526  true            null
3c1e8aae  false           {"resourceKind": [...mpb_rubrik...], ...}
```

`entryKeys` is the **pending resolution work list**, retained from the
import bundle until phase 2 clears it. So:

| Signal | Meaning |
|---|---|
| `importComplete: false` + `entryKeys` non-null | Phase 2 has not completed. Widget `config` is `{}` for every widget whose config referenced an unresolved token. |
| `importComplete: true` + `entryKeys` null | Phase 2 done. Configs written and resolved. |
| `getDashboardList.isLoading` | The same flag on the UI surface: `true` == `importComplete: false`. |

`importAttempts` was **0 on all 13**, including the three that have been
incomplete for months. On this build it is not a retry counter that gets
exhausted, and it is not a useful triage signal.

## Q2. The precondition being violated: none, for the two reported dashboards

There is no documented or discoverable precondition requiring a delete
first, a particular owner, an unlocked dashboard, or a policy. Both
reported dashboards are `locked: false`, `owner: admin`, owned by the
importing account, and both completed on their own.

**Both are fully bound right now**, read live from `getWidgetConfigs` and
independently from a fresh export:

```
66ec0811  vSAN Cluster Health     importComplete=true  3 widgets  0 empty config
    widget_825e58dd  View  viewDefinitionId = 2e58f142-5a21-44c6-899f-a66f09fd3ad3
    widget_f85f59d7  View  viewDefinitionId = <bound>
    widget_e702ec1a  ResourceList  tagFilter resolved to 002028VirtualAndPhysicalSANAdapterVirtualSANDCCluster

f5a14e9c  Cluster Cost Details    importComplete=true  5 widgets  0 empty config
    all five View widgets carry a viewDefinitionId; "Cluster Costs" additionally
    carries a resolved self-provider pin to vSphere World (ba1fe374-...)
```

The last write to `66ec0811` was 00:41:59; it was read bound at 05:36.
Phase 2 completed somewhere inside that window without any intervention.
`f5a14e9c`, the 8.18.7-sourced dashboard that "never bound on any of three
imports", is likewise complete. **The 8.x-to-9.x path is not implicated**;
it was the same deferred window observed three times.

The observation sequence is fully consistent with this. Step 1's read
happened outside the window (or before the record had been replaced);
steps 2 through 5 were rapid-fire, and each import restarted the clock, so
every read after them landed inside it.

**API versus UI import: not tested**, because testing it requires an
import. The UI's single-dashboard import is a different code path and may
run phase 2 inline. Treat as an open question, not as a known difference.

## The genuine failure mode: phase 2 stalls on a missing adapter kind

Three dashboards on devel have been `importComplete: false` for months
(`2679c78f` MSSQL and `a426553b` Oracle since 2026-05-28, `3c1e8aae`
Rubrik Overview since 2026-06-12). This is the real defect class, and it
is distinguishable from the transient case by age alone.

Their pending `entryKeys` name the reason:

```
2679c78f (MSSQL)  pending resourceKind:
    vcfcf_compliance / ComplianceWorld
    VMWARE          / HostSystem
    SqlServerAdapter / SqlServer, SqlQuery, SqlDatabase
    OracleDBAdapter  / oracle_database_oracle_database_instance, ..._query
3c1e8aae (Rubrik) pending resourceKind:
    mpb_rubrik / rubrik_event, rubrik_cluster, rubrik_job, rubrik_vm, rubrik_sla_domain
```

`GET /api/adapterkinds` on devel returns 21 kinds. **`SqlServerAdapter`,
`OracleDBAdapter` and `mpb_rubrik` are not among them.** Phase 2 cannot
resolve a resource kind belonging to an adapter that is not installed, so
it never completes, and those widgets' configs are never written.

The per-widget pattern matches precisely. Widgets that bind a **view uuid**
or an **alert query** resolve fine; widgets that bind a **resource kind or
a metric** do not:

```
2679c78f MSSQL            3c1e8aae Rubrik Overview
  ResourceList  EMPTY       Skittles             EMPTY
  Heatmap       EMPTY       MetricPicker         EMPTY
  View          full        MetricChart          full
  Scoreboard    EMPTY       ResourceRelationship EMPTY
  Scoreboard    EMPTY       AlertList            full
  View          full
  MetricChart   EMPTY  x4
```

This closes the DEF-014 Round 2 follow-up question, "why did MSSQL and
Oracle never materialize". The answer is that the adapters they monitor
were never installed on devel.

## Q5. Repairing a hollow dashboard

| Case | Route |
|---|---|
| Deferred, references resolvable | **Do nothing.** It completes on its own. Opening it once in the UI is the fastest observed trigger (~3 min per `ui_deep_links.md`) versus up to hours for the background pass. |
| Stalled, adapter kind absent | **Install the missing adapter or management pack.** Nothing else fixes it. Delete-and-reimport re-enters the identical stall, which is why the DEF-014 "remediation" appeared to reproduce the symptom. |

There is **no callable API that forces phase 2**. DEF-014 Round 2 tried
`openTab`, `loadTab`, `selectTab`, `getTab`, `getDashboard`,
`refreshWidget`, `materializeTab`, `saveTab`, `saveDashboardConfig`,
`getDashboardConfig`, `getWidgetConfigs` and `cloneDashboard`; all leave
the flag set, and cloning a skeleton yields a skeleton clone. Re-confirmed
by this pass's reads. The materializer lives in the modern SPA path and a
timed background worker.

---

## Are we using the import API in a way it was never meant to support?

**No.** Overwrite is the documented default and the spec says so plainly.
The factory passes `force=true`, which is correct. Replacing an existing
dashboard is supported, intended, and works.

What we got wrong is **what "finished" means**. We treated the import
operation's `FINISHED` as the end of the installation, when it is only the
end of phase 1. The product does not expose a phase-2 completion signal on
the Suite API at all: the only readable one, `importComplete` / `entryKeys`,
lives in an export document and in an undocumented UI action. That is a
genuine gap in the product's supported surface, and the correct response is
to stop reading success from the import envelope alone.

## What a tool ought to do about it

1. **Never verify a dashboard immediately after import.** The verification
   must poll for `importComplete: true` (or `getDashboardList.isLoading ==
   false`) before it looks at widget config or takes a screenshot. This is
   already `knowledge/lessons/dashboard-import-deferred-materialization.md`
   rule 1; this investigation supplies the mechanism and the second,
   cheaper signal (`entryKeys`).
2. **Distinguish the two states in the output.** `importComplete: false`
   with a `lastUpdateTime` minutes old is normal and should be reported as
   "settling". The same flag on a record hours or days old is a real
   failure and should be reported with its pending `entryKeys`, which name
   the missing adapter directly. That turns an opaque hang into an
   actionable "install the X adapter".
3. **Do not warn admins that import over existing content is unsafe.** On
   this evidence it is safe; the scary observation was a read inside the
   settling window. A warning here would be wrong, and would be a
   permanent cost paid for a transient state.
4. **Do not add a delete-before-import step.** It does not help the
   resolvable case (which needs no help) and does not help the stalled case
   (which re-stalls). DEF-014 already paid for this lesson once.
5. **Prefer opening the dashboard once** after a sync if the caller wants a
   fast settle, rather than waiting on the background pass.

## Method log (reproducible, read-only)

- Auth: `VCFOpsClient.from_env(profile="devel")` and
  `VCFOpsUIClient.from_env(profile="devel")`. No credential reached the
  transcript, argv or shell history.
- `POST /ui/dashboard.action mainAction=getDashboardList` (177 dashboards;
  `isLoading` per entry).
- `POST /ui/dashboard.action mainAction=getWidgetConfigs&tabId=<uuid>` for
  `66ec0811`, `f5a14e9c`, `2679c78f`.
- `POST /api/content/operations/export {scope: CUSTOM, contentTypes:
  [DASHBOARDS]}` then `GET /api/content/operations/export/zip`. Outer zip
  has 7 members; `dashboards/<ownerId>` is itself a **nested zip**
  containing `dashboard/dashboard.json` and
  `dashboard/resources/resources.properties`. 13 dashboards for owner
  `29c1613f-...`.
- `GET /api/adapterkinds` (21 kinds).
- Spec reads: `operations-api.json`, `internal-api.json`, and both 9.1
  copies, for `importContent`, `import-operation-summary`,
  `operation-details`, and grep for `importComplete` / `importAttempts` /
  `force*` / `overwrite`.

## Clean-up verified: yes

Nothing was created on the instance. The export operation writes no
content; it leaves a "last export operation" status record, which the
factory's own `discover_marker_filename` already churns routinely. The
deliberately-broken dashboard and the other lab's imported content were
read only and are byte-identical to before. Local scratch files under
`/tmp` (export zip and probe scripts) were deleted.

## Cross-references

- `knowledge/lessons/dashboard-import-deferred-materialization.md` — the
  rule this investigation supplies the mechanism for.
- `knowledge/context/investigations/def014-view-binding-loss-2026-07-22.md`
  — Round 2 mapped the deferred state and left two follow-ups (does an
  overwrite de-materialize a completed dashboard; why do MSSQL/Oracle never
  materialize). **Both are answered here: yes, and missing adapter kinds.**
- `knowledge/context/api-surface/content_import_skip_semantics.md` — the
  other half of the import envelope's semantics (`force=false`,
  `imported=0/skipped=N`).
- `knowledge/context/api-surface/ui_deep_links.md` — materialization timing
  datapoints (~3 min after open, up to ~20 min background).
- `knowledge/designs/content-migrator-v1.md` §"The overwrite problem" — the
  observation that prompted this pass.
