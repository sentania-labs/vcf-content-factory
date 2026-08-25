# Empty-collection wire shapes for the uninstaller's list endpoints

Read-only recon against the **devel** lab (2026-08-24), scoped to
three deferred `install.ps1` uninstaller fixes:

- `Get-AllViews` (`install.ps1` — calls
  `viewServiceController.getGroupedViewDefinitionThumbnails`)
- `Get-AllReports` (`install.ps1` — calls
  `reportServiceController.getReportDefinitionThumbnails`)
- `Get-AllDashboards` (`install.ps1` — calls Struts
  `mainAction=getDashboardList`)

Question: when a collection is legitimately empty, what shape does
the server return, so the parsing code can be judged safe (or not)
to refuse on an unrecognised shape instead of silently dropping data?

See `dashboard_delete_api.md` for the auth flow, transport, and the
confirmed *populated*-collection shapes this file assumes as context.
Auth/session mechanics are identical; not repeated here.

## Method 1: cannot filter server-side, so no forced-empty case exists

Both Ext.Direct list methods
(`getGroupedViewDefinitionThumbnails`, `getReportDefinitionThumbnails`)
were probed with alternate `data` payloads to see whether any
client-supplied filter narrows the result set. Findings:

- `getGroupedViewDefinitionThumbnails` **ignores its `data` argument
  entirely**. Calling it with `[]` (the shape in the existing doc),
  with `[{"start":0,"limit":500}]`, and with a bogus
  `[{"subject":{"adapterKind":"NoSuchAdapter","resourceKind":"NoSuchKind"}}]`
  all returned the identical full, unfiltered result (same 6 top-level
  type keys, same view counts). There is no server-side filter to
  coax an empty view type out of a populated instance.
- `getReportDefinitionThumbnails` **does honor `contentFilter`**.
  Setting `contentFilter.isTenant: true` on the devel lab (which is
  not multi-tenant) produced a genuinely empty, unmanufactured result
  — see below. This is an honest empty case: it was not created or
  deleted, it reflects a real, always-zero subset of the same
  underlying data.

## Question 1: `getGroupedViewDefinitionThumbnails` — empty view type

**Could not observe.** The devel lab has views in all 6 view types
the server currently returns (`TREND`, `IMAGE`, `LIST`, `SUMMARY`,
`POPULATION_DISTRIBUTION`, `TEXT`), and every subject group within
every type has at least one view — no zero-length array or empty
object was found anywhere in the structure. Since the method ignores
filters (see above), there is no way to manufacture an empty type
without deleting content, which is out of scope for this
investigation (RULE-009, read-only, devel-only, create/delete
nothing).

Request used (verbatim, matches the documented working shape):

```json
POST /ui/vcops/services/router
secureToken: <csrf>

[{
  "action": "viewServiceController",
  "method": "getGroupedViewDefinitionThumbnails",
  "data": [],
  "type": "rpc",
  "tid": 1
}]
```

Observed top-level keys of `result` (all populated, none empty):

```json
["TREND", "IMAGE", "LIST", "SUMMARY", "POPULATION_DISTRIBUTION", "TEXT"]
```

Per-type subject-group counts (all subject groups within every type
had >=1 view; none were `[]`):

```
TREND: 24 subject groups, all non-empty
IMAGE: 1 subject group, non-empty
LIST: 74 subject groups, all non-empty
SUMMARY: 9 subject groups, all non-empty
POPULATION_DISTRIBUTION: 13 subject groups, all non-empty
TEXT: 3 subject groups, all non-empty
```

**Unresolved: whether a view type absent from the server's actual
type enum (i.e. a type genuinely at zero) is omitted from the keyed
object, present as `{}`, or something else. Not observed on this
instance and not reachable without deleting content.**

**Verdict on Q1: it is not safe for `Get-AllViews` to refuse on an
unrecognised shape at either the `$subjectMap -is [PSCustomObject]`
check or the `$viewList -is [System.Array]` check.** No empty case
was reachable to test the current silent-skip behavior against, and
because the endpoint ignores all filters, an empty result for this
method can only ever happen on an instance that truly has zero views
of every type it returns keys for — a case that cannot be
distinguished, from the recon done here, from a malformed response.
Refusing is a guess in the more dangerous direction: it would block
every uninstall on any lab or customer instance whose true shape
turns out to be `{}`/`null`/absent-key for an empty type, not just
mis-report some content. The silent-skip (drop unrecognised shapes,
keep going) remains the safer default until an empty case is
actually observed somewhere.

## Question 2: `getReportDefinitionThumbnails` — empty report list

**Observed.** Filtering with `contentFilter.isTenant: true` on the
non-multi-tenant devel lab produced a genuine, unmanufactured empty
result (0 of the lab's 74 reports are tenant reports).

Request (verbatim):

```json
POST /ui/vcops/services/router
secureToken: <csrf>

[{
  "action": "reportServiceController",
  "method": "getReportDefinitionThumbnails",
  "data": [{
    "contentFilter": {"isTenant": true},
    "resourceContext": null,
    "page": 1, "start": 0, "limit": 500,
    "sort": [{"property": "creationTime", "direction": "DESC"}]
  }],
  "type": "rpc",
  "tid": 1
}]
```

Response (verbatim, full body):

```json
[
  {
    "type": "rpc",
    "tid": 1,
    "action": "reportServiceController",
    "method": "getReportDefinitionThumbnails",
    "result": {
      "metaData": {
        "root": "records",
        "totalProperty": "total",
        "successProperty": "success",
        "start": 0,
        "limit": 500,
        "sortInfo": {
          "field": "creationTime",
          "direction": "DESC"
        }
      },
      "success": true,
      "total": 0,
      "records": []
    }
  }
]
```

The shape is the same envelope as the populated case
(`{"records":[...], "total": N, "metaData":{...}, "success":true}`),
just with `records` as a **bare empty array `[]`** and `total: 0`.
The `records` key is **present**, not omitted, and is an array, not
`null` or `{}`.

**Verdict on Q2: `Get-AllReports`'s `records` branch (the first key
in the recognised-key list at `install.ps1:2028`) is confirmed
correct for the observed true-empty case.** One important caveat
before generalising: the observed empty response came from
`contentFilter.isTenant: true`, while `Get-AllReports` in production
sends `isTenant: false`. The empty case for the *exact production
filter* has not been observed, so "an honest empty result always
carries `records: []`" is an inference from the tenant-scoped probe
(same endpoint, same envelope, different filter value), not an
observation of the production request. In the observed case the
honest empty result carried `records: []` (present, typed as array)
inside the same envelope, not an envelope lacking all five keys.
Treating a no-recognised-keys `result` as malformed is therefore
well supported but not proven for the production filter; see #124
for why the shipped fix is warn-and-continue rather than a hard
refusal. The existing
flatten fallback at `install.ps1:2036-2044` would also correctly
return an empty list here (no array-typed properties to flatten),
so both the primary path and the fallback already do the right thing
on this observed shape.

This does not confirm the shape for report lists scoped by *user*
(only by the `isTenant` tenant/non-tenant split was reachable
without creating or deleting content) — a per-owner-scoped empty
case was not tested.

## Question 3: `getDashboardList` — empty dashboard envelope

**Could not observe.** No filterable parameter was found for this
Struts `mainAction`; every call returns the full unfiltered
dashboard list for the authenticated session (176 dashboards on
devel, spanning both built-in and `[VCF Content Factory]`-prefixed
content). No scope, owner, or tenant split was found that narrows
the list to zero, and manufacturing one would require deleting
dashboards, which is out of scope here.

Request used:

```
POST /ui/dashboard.action
mainAction=getDashboardList
secureToken=<csrf>
currentComponentInfo=TODO
globalDate={"dateRange":"last6Hour"}
```

Observed response shape (envelope only, all 176 entries structurally
identical to the documented shape in `dashboard_delete_api.md`):

```json
{"dashboards": [ /* 176 entries */ ]}
```

Top-level key is `dashboards`, no other keys present at that level.

**Verdict on Q3: genuinely unresolved.** Whether an empty instance
returns `{"dashboards": []}` (an empty array under the same key,
following the pattern the reports endpoint showed for its own empty
case) or `{"dashboards": null}` or omits the key was not observable
here. Given the reports precedent (same-envelope, array-typed,
present-not-omitted for the empty case) it is *plausible* dashboards
follow the same pattern, but that is an inference from a sibling
endpoint's behavior, not an observation of this endpoint, and should
not be treated as confirmed. **Do not add a refuse-on-unrecognised-shape
guard at `Get-AllDashboards` on the strength of that inference alone.**

## Summary for the three deferred fixes

| Site | Empty case observed? | Safe to refuse on unrecognised shape? |
|---|---|---|
| `Get-AllViews` (view-type/subject-map checks) | No — not reachable, no server-side filter exists | **No.** Keep silent-skip; refusing risks blocking every uninstall on a shape actually meaning "empty," which this recon could not rule out. |
| `Get-AllReports` (`records`-key fallback) | Yes — but under `contentFilter.isTenant: true`, not the `isTenant: false` the production call sends | **Qualified yes.** The observed empty case matches the documented populated envelope with `records: []`, so a no-recognised-keys `result` is very likely malformed rather than honestly empty. But the production filter's empty case was not itself observed (nor per-owner/per-user scopes), so this is a strong same-endpoint inference, not proof. Prefer warn-and-continue over a hard refusal until the production-filter empty case is observed. |
| `Get-AllDashboards` (envelope) | No — not reachable, no server-side filter exists | **No.** Only an inference from the reports endpoint's pattern exists, not an observation of this endpoint; do not act on it as confirmed. |

## Method notes

- Auth/session/CSRF mechanics: see `dashboard_delete_api.md`.
- All calls used `VCFOpsUIClient.from_env(default_profile="devel")`
  (`src/vcfops_dashboards/ui_client.py`), plus one-off inline scripts
  for raw (non-post-processed) response capture — the shipped client's
  `list_dashboards()` / `list_views()` methods pre-filter/flatten the
  response, which would have hidden exactly the distinction this
  investigation needed, so raw `requests` calls through the client's
  authenticated session were used instead.
- No content was created or deleted. No writes were made to `prod`
  or `qa` (RULE-009); `devel` profile only, GET/list Ext.Direct and
  Struts calls only.
