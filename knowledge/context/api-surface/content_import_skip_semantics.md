# What `imported=0 / skipped=N` means for DASHBOARDS and VIEW_DEFINITIONS

Bisected 2026-08-21 on the `devel` lab (VCF Ops
`vcf-lab-operations-devel`, marker `6844548499441080431L.v1`) to close
the investigative half of issue #97. Twelve controlled imports, every
envelope captured. All probe content deleted afterwards and the
deletion verified against a pre-experiment snapshot (see §Cleanup).

**Home note:** this lives here rather than in the `vcfops-api` skill's
`references/wire-formats.md` because it is a bisection log with the raw
envelopes. The skill reference and
`knowledge/context/wire-formats/wire_formats.md` carry the short
normative rule and should point here for the evidence.

## The one-line answer

`imported=0 / skipped=N` on `DASHBOARDS` / `VIEW_DEFINITIONS` is
**not** ghost state. It is the importer's create-only mode: the query
parameter `force=false` on `POST /api/content/operations/import` means
"do not overwrite anything that already exists". The skip is a clean,
idempotent no-op. The pre-existing content stays fully usable; the
*new* version simply did not land.

The super metric ghost-state remedy (re-import the same zip) does
**not** transfer. Re-importing an identical zip under `force=false`
skips again, indefinitely.

## The `force` query parameter is the whole story

`operations-api.json`, `POST /api/content/operations/import`:

```
param: force   query   required=false
       "True to force solution content overwrite"
```

The spec text says *solution* content. Measured behaviour is broader:
it governs user-authored dashboards and views too.

| `force` value sent | content already exists? | result |
|---|---|---|
| `true` | yes | `imported=N, skipped=0` — overwritten in place |
| `true` | no | `imported=N, skipped=0` — created |
| omitted | yes | `imported=N, skipped=0` — **default is overwrite** |
| `false` | yes | `imported=0, skipped=N` — left untouched |
| `false` | no | `imported=N, skipped=0` — created |

The omitted-parameter row is the counter-intuitive one and was
measured, not assumed: leaving `force` off behaves like `force=true`,
not like `force=false`. Only an explicit `force=false` produces the
skip signature.

**Every factory import path already sends `force=true`:**

- `src/vcfops_dashboards/client.py:import_content_zip`
  (`params={"force": "true"}`) — used by the dashboards/views sync
  path, by `vcfops_reports`, and by
  `vcfops_supermetrics.client.import_supermetrics_bundle`, which
  imports that same helper.
- `src/vcfops_packaging/templates/install.py:421`
  (`params={"force": "true"}`).
- `src/vcfops_packaging/templates/install.ps1:691`
  (`...?force=true`).

So the signature the factory warns about is, as of today, **not
reachable through any of the factory's own requests**. It is reachable
by a client that sets `force=false` — which is the most likely
explanation for the other team's `total:3 skipped:3 imported:0`.

Corollary that matters for the SM story: the SM ghost state was
observed with `force=true` on the wire. It is therefore a genuinely
different phenomenon from the `force=false` skip documented here, not
the same bug seen from another angle.

## Question 1: can the signature be reproduced for DASHBOARDS?

Yes, deterministically, and only via `force=false`.

Method: a throwaway view + dashboard pair
(`[VCF Content Factory] EXP97 Probe View A` /
`... Probe Dashboard A`, fixed UUIDs) built with the ordinary
`vcfops_dashboards` loader + packager, imported through a harness that
varies exactly one thing at a time.

Verbatim, the reproduction (`C1`), immediately after an identical
import that had reported `imported=1`:

```json
{
  "_force_param": {
    "force": "false"
  },
  "_post_status": 202,
  "endTime": 1787340866464,
  "errorCode": "NONE",
  "errorMessages": [],
  "id": "29c1613f-3bbe-4aa0-8236-2c74db22c661",
  "operationSummaries": [
    {
      "contentType": "VIEW_DEFINITIONS",
      "errorMessages": [],
      "failed": 0,
      "imported": 0,
      "infoMessages": [],
      "skipped": 1,
      "state": "FINISHED",
      "total": 1,
      "type": "import"
    },
    {
      "contentType": "DASHBOARDS",
      "errorMessages": [],
      "failed": 0,
      "imported": 0,
      "infoMessages": [],
      "skipped": 1,
      "state": "FINISHED",
      "total": 1,
      "type": "import"
    }
  ],
  "startTime": 1787340864484,
  "state": "FINISHED",
  "type": "IMPORT"
}
```

And the control (`B1`), same zip, same instance, `force=true`, content
already present and byte-identical:

```json
{
  "_force_param": {
    "force": "true"
  },
  "_post_status": 202,
  "endTime": 1787340856456,
  "errorCode": "NONE",
  "errorMessages": [],
  "id": "29c1613f-3bbe-4aa0-8236-2c74db22c661",
  "operationSummaries": [
    {
      "contentType": "VIEW_DEFINITIONS",
      "errorMessages": [],
      "failed": 0,
      "imported": 1,
      "infoMessages": [],
      "skipped": 0,
      "state": "FINISHED",
      "total": 1,
      "type": "import"
    },
    {
      "contentType": "DASHBOARDS",
      "errorMessages": [],
      "failed": 0,
      "imported": 1,
      "infoMessages": [],
      "skipped": 0,
      "state": "FINISHED",
      "total": 1,
      "type": "import"
    }
  ],
  "startTime": 1787340854388,
  "state": "FINISHED",
  "type": "IMPORT"
}
```

**An unchanged re-import is not a skip.** `imported=N` means "written",
not "changed". There is no content-hash comparison; the importer does
not detect that nothing differs.

### What could NOT produce a skip

Every one of these returned `imported=1, skipped=0, failed=0,
errorCode: NONE` under `force=true`:

- re-importing the byte-identical zip (`B1`);
- re-importing with edited widget titles and an edited view column,
  same UUIDs (`E1`) — the edit landed, in place;
- importing a dashboard with the **same name but a different UUID**
  (`F1`);
- importing with a bogus `owner_user_id` / `usermappings.json` naming
  a user that does not exist on the instance (`G1`);
- a zip carrying one already-present dashboard plus one brand-new one
  (`J2`: `DASHBOARDS total=2 imported=2 skipped=0`).

Not tested, so not ruled out as alternative causes: dashboards locked
in the UI (`locked: true`), dashboards owned by a different *real*
user importing as a non-admin, and pak-supplied solution content
(which is what the spec's `force` wording is actually about).

### Side finding: dashboard import identity is NAME, not UUID

Worth knowing independently of #97. In `F1`, importing a dashboard
named `[VCF Content Factory] EXP97 Probe Dashboard A` with a new UUID
`...00d2` while `...00d1` already existed under that name produced:

- `DASHBOARDS imported=1`, dashboard list total unchanged at 177,
- one entry with that name, carrying id `...00d2`,
- `getDashboardConfig?tabId=...00d1` returning `tabConfigs: []` — the
  old UUID is gone.

Same-named dashboards are **replaced**, and the old UUID dies
silently. `G1` then reversed it (imported `...00d1` again, `...00d2`
vanished). Views behave differently: the same-name-new-UUID view was
kept alongside the original and renamed with a numeric suffix
(`[VCF Content Factory] EXP97 Probe View A 1`, view count 988 -> 989).

Practical consequence: changing a dashboard's `id:` in YAML while
keeping its name does not create a second dashboard, it orphans the
previous UUID. Any deep link or summary-page association pinned to the
old UUID breaks with no error anywhere in the import envelope.

## Question 2: when it happens, is the content usable?

Yes. Four probes, each run against the dashboard immediately after a
`force=false` skip. Naming each explicitly, per the brief:

1. **Dashboard list** (`POST /ui/dashboard.action
   mainAction=getDashboardList`): present, one hit, correct id and
   name, `shared: true`, `locked: false`. This is the probe whose SM
   analogue *fails* in ghost state. It passes here.
2. **Read by id** (`mainAction=getDashboardConfig&tabId=<uuid>`):
   returns the full `dashboardConfig.tabConfigs[0]` with both widgets,
   their `gridster*` geometry and the `tabInteractions` entry intact.
3. **Renders the right content**: widget titles read
   `Select Cluster (rev1)` / `Probe View (rev1)` — i.e. the
   *previously imported* revision, not the rev2 that was skipped.
   This is the operator-visible fact worth warning about: nothing is
   broken, but the edit did not land. (Structural render check via the
   config payload; no browser pass was run in this investigation.)
4. **Assignable** (the direct analogue of the SM assign that returns
   404 in ghost state): after a skipped import,
   `mainAction=associateResourceKindDashboards` with
   `{"resourceKind_002008APPOSUCPactivedirectory":
   "<name>_::_<uuid>"}` returned `200 "ok"`, and
   `mainAction=getSummaryTabId` then returned a real materialized
   template id (`{"tabId":"8d4f4121-3223-4aa9-b2ae-be101f61516c"}`)
   where it had returned `{}` before. Association and template
   both reverted afterwards.

The associated view definition was likewise present in
`viewServiceController.getGroupedViewDefinitionThumbnails` with its
original columns.

So: **no ghost state on the dashboard path.** There is no observed
dashboard analogue of "readable by id but invisible to list and
assign".

## Question 3: does re-importing the same zip fix it?

**No.** Plainly, and this is the point at which the SM remedy must not
be generalised on resemblance.

Three consecutive `force=false` imports of the same rev2 zip
(`D1`, `D2`, `D3`) each returned, byte-for-byte in the counts:

```
VIEW_DEFINITIONS   total=1  imported=0  skipped=1  failed=0
DASHBOARDS         total=1  imported=0  skipped=1  failed=0
```

and the dashboard still showed rev1 widget titles after all three. The
skip is idempotent. An automatic retry on this signal would be pure
wasted work: a second import that cannot succeed, on a path where a
concurrent import returns 403 and costs a 30s backoff.

The fix is `force=true` (`E1`), which imported the rev2 content in
place and flipped the widget titles to rev2 on the next read. Deleting
the object first also works but is not required.

## Question 4: VIEW_DEFINITIONS

Same answer, same evidence, measured in the same envelopes: every zip
above carried one view alongside the dashboard, and `VIEW_DEFINITIONS`
tracked `DASHBOARDS` in all twelve runs. Skipped under `force=false`
when the view id already existed, imported under `force=true` and when
`force` was omitted, imported under `force=false` when the id was new,
never recovered by a repeat import. Post-skip the view remained listed
by `getGroupedViewDefinitionThumbnails` with its previous columns.

The only place views and dashboards diverge is the same-name /
new-UUID case described above: views duplicate-with-suffix, dashboards
replace.

## What this means for the factory's behaviour

- The **loud warning is accurate and should stay**. Its text ("existing
  objects with the same ids/names were left as they were... verify on
  the instance") is exactly right for the `force=false` case, which is
  the only reproduced cause.
- **Do not add the SM-style auto-retry to the dashboard or view
  paths.** The skip is idempotent; retrying cannot help and costs a
  round trip plus the import-busy backoff. This is now evidence, not
  caution.
- The warning is currently **unreachable** through the factory's own
  code, because all four import call sites hard-code `force=true`. If
  an operator ever sees it, something outside those call sites changed
  the request or the server semantics, and that is worth a loud line.
- **`imported=N` does not mean "content changed"**, only "content
  written". Any future "did my edit land?" check must compare content,
  not counts.
- The cross-team claim that VCF Ops has no programmatic dashboard
  update path is **false**: `E1` updated a dashboard in place, same
  UUID, via the content-zip import with `force=true`.

## Cleanup

Everything created was removed and the removal verified rather than
assumed:

| Artifact | Verification | Before | After |
|---|---|---|---|
| Probe dashboards (`...00d1`, `d2`, `d4`, `d5`, `d6`) | `getDashboardList` count and name filter | 176 | 176, zero `EXP97` hits |
| Same, read by UUID | `getDashboardConfig?tabId=` per UUID | n/a | `tabConfigs: []` for all five |
| Probe views (`...0001`, `0002`, `0004`) | `getGroupedViewDefinitionThumbnails` flattened count | 987 | 987, zero `EXP97` hits |
| Materialized summary templates (2, from the assignability probe) | `mainAction=getTemplateList` (admin-privileged; templates never appear in `getDashboardList`) | 23 | 23, id set identical |
| Resource-kind detail-page map (363 kinds) | `getResourceKindList&appendDetailPageMappings=true` full snapshot, diffed | 25 non-default | diff `{}` |

A dashboard count alone would not have been proof for the templates:
they live in a namespace `getDashboardList` never returns.

## Reproducing

The harness was throwaway (scratchpad, not committed). To redo it:
build any view+dashboard pair with `vcfops_dashboards`' loader and
packager, then POST the zip to `/api/content/operations/import` with
`files={"contentFile": (...)}` and the session's
`Content-Type: application/json` suppressed, varying only the `force`
query parameter. Poll `GET /api/content/operations/import` until
`endTime` advances past the pre-POST snapshot. `devel` only: this
overwrites content by name.
