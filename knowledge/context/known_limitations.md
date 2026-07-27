# Known limitations

Current capability boundaries the orchestrator should communicate
to users early, rather than discovering mid-workflow.

## 1. Dashboard widget types

Dashboard authoring supports 10 widget types covering ~94% of
observed usage: `ResourceList`, `View`, `TextDisplay`, `Scoreboard`,
`MetricChart`, `HealthChart`, `ParetoAnalysis`, `Heatmap`,
`AlertList`, `ProblemAlertsList`. `PropertyList` (47 uses on the
survey instance) is the highest-value remaining gap. Other
unsupported types (~14 uncommon variants, ~91 total observed uses)
require renderer expansion via `tooling` with api-explorer to
document the wire format. If a user requests a dashboard with
unsupported widget types, set expectations before delegating.

## 2. Policy enablement — CLI targets Default Policy only

This is a code gap, not a server constraint. The `enable` CLI
command hard-codes the Default Policy: `get_default_policy_id`
refuses to return any other policy, the `enable` command takes no
`--policy` flag, and the XML-injection helper hunts the first
`<Policy>` element in the exported ZIP (implicitly the default).
Users with custom policies can sync content but cannot enable
super metrics via the CLI today.

The *server* constraint is narrower:
`PUT /internal/supermetrics/assign` with `policyIds` is a no-op for
content-zip-imported SMs (real server behavior, documented in
`src/vcfops_supermetrics/client.py:287-292`). But the policy-export →
edit-XML → re-import path used for actual enablement is
policy-agnostic — it already operates on whatever ZIP the server
returns. The Default-only behavior is a framework code shortcut,
not a platform limit. Remediation is scoped in
`context/framework_review_2026_04_18.md` §2.3: add `--policy` flag,
iterate to "find the policy whose `<id>` matches target" in the XML
editor, keep Step 1 (the `/internal/assign` call) Default-scoped
because that's about resource-kind assignment, not enablement.
Deferred until a user asks.

## 3. Recommendations — authoring works, REST sync does not

Recommendation YAML authoring under `recommendations/` is fully
supported: `alert-author` writes recommendation files, alerts
reference them by name, and the validator resolves all cross-
references. Recommendations are included in `AlertContent.xml` in
distribution packages and import correctly via content-zip.
**However, `python3 -m vcfops_alerts sync` (the live REST path)
omits recommendations** because `POST /api/alertdefinitions` has no
recommendations field — recommendations only travel via the
AlertContent.xml import path. Users who sync alerts via the
authoring loop will get alerts without recommendations until they
re-import via a distribution package or content-zip.

## 4. Reference source clones

Recon checks allowlisted external repos under `reference/references/`
(gitignored). Fresh setups won't have these clones. Run
`scripts/bootstrap_references.sh` to populate them, or expect recon
to report missing-clone gaps.

## 5. View and report delete

2026-04-11 correction — previously documented as a VCF Ops 9.0.2
server bug. Both operations work correctly via
`viewServiceController.deleteView` and
`reportServiceController.deleteReportDefinitions` on the legacy
`/ui/vcops/services/router` Ext.Direct endpoint, **with the correct
nested-JSON-string data shape**. The 500s observed in earlier
investigations were the server-side POJO deserializer crashing on
malformed client payloads (bare UUID strings), not a broken handler.
See `context/dashboard_delete_api.md` §"2026-04-11 correction" for
the authoritative wire format and working Python/PowerShell call
shapes. Install scripts have been updated; view and report uninstall
are both supported.

## 6. UI-session uninstall requires `admin` account

The content-zip importer assigns dashboard ownership to the `admin`
account regardless of who authenticates the import. Only the `admin`
user's UI session can delete imported dashboards, views, and
reports. Install scripts enforce this: uninstall of bundles
containing any of these three content types aborts with a clear
early error if the user is not `admin`. Install (import) works with
any admin-privileged account.

## 7. No per-object UI import endpoints in VCF Ops 9.0.2

Every legacy `/ui/*.action` upload mainAction and every Ext.Direct
upload RPC is either unregistered, a dead stub, or wired-but-
throwing. The new SPA UI wraps drag-dropped files client-side into a
bulk content-zip envelope and POSTs to
`/api/content/operations/import` — the same endpoint `install.py`
already uses. Consequences: (a) our distribution package drop-in
artifacts (`supermetric.json`, `Dashboard.zip`, `Views.zip`,
`Reports.zip`, `AlertContent.xml`) work for admins hand-dragging
into the UI because the SPA does the envelope wrap, but (b)
qa-tester cannot automate that drag-drop path headlessly — it's
human-in-the-loop only. See `memory/project_vcf_ops_902_ui_deadends.md`.

## 8. MPB events not supported in factory-built paks

The factory can define events in YAML (`mpb_events:`) and render
them for the MPB UI design import path. However, factory-built
`.pak` files strip all events because the pak runtime expects a
different schema than the design JSON format. No ground-truth
reference exists for the pak runtime event format — every MPB
reference pak in the repo has `events: []`. Events defined in YAML
will work when the design is imported via MPB and built there, but
not when built directly by the factory's `build` command.

See `context/lessons_pak_install_reliability.md` §5.

## 9. Metric labels cannot contain `|` or `:`

The VCF Ops stat key format uses `|` as the group separator and
`:` is also reserved. MPB rejects metric labels containing either
character at collection time. The factory loader does not currently
validate this — it's caught only when the adapter tries to run.

## 10. ARIA_OPS properties don't stitch

ARIA_OPS stitching delivers metrics only. Properties declared on
ARIA_OPS objects are silently dropped at collection time
(`collected_properties = 0`). This is a VCF Ops platform
limitation, not a factory bug. Keep properties on ARIA_OPS objects
for documentation but don't expect them to appear on the target
resource.

## 11. No multi-key ARIA_OPS binding

MPB's `objectBinding` only supports single-field matching. There
is no evidence of composite key support (multiple
`expressionParts`) in any reference pak or design JSON. Join keys
must be globally unique on their own. For hosts, use `hostname`
(FQDN) → `VMEntityName`, not `host_moid` → `VMEntityObjectID`
(MOIDs are per-vCenter, not global).

## 12. MPB <9.2 runtime: no JMESPath filter projections

`ResourceQueryHelperKt` in MPB versions prior to 9.2 does not evaluate
JMESPath filter expressions like `[?field=='value']` — these are
silently no-op'd at runtime. The expression is accepted by MPB at import
and build time and appears valid in the design editor, but the adapter
collects no data for any metric whose source path contains a filter
predicate.

Patterns requiring per-element selection by predicate must wait for MPB
9.2 or use chained metricSets (one resource kind per element, so the
predicate can be replaced with a chain bind that selects the element by
identity).

Authority: cleanroom finding (see `context/mpb_designer_wire_format.md`
§"The expression language (runtime form)") + first-party confirmation
from the engineer who built MPB.

Prior art: UniFi radio metrics were dropped in 1.0.0.13 because they
relied on `radio_table[?radio=='ng'].xxx` patterns that the runtime
could not evaluate. The metrics rendered and built cleanly into a pak
but registered zero collections on prod. This limitation affects only
the INTERNAL resource collection path; ARIA_OPS metric expressions are
evaluated by a different engine and are not affected.

## 13. MPB Tier 1 cannot author parent-child relationships for Redfish-shape APIs

MPB's relationship model requires real metric values that match
between parent and child objects, where both metrics are pulled from
each object's own primary request response body (the "UniFi
pattern" — see `knowledge/context/api_pattern_catalog.md` UniFi entry for the
canonical example).

Redfish APIs encode parent-child hierarchy in URL paths
(`/Systems/{id}/Processors/{cpu}`), **not** in flat scalar fields of
the child's response body. A Fan or PSU response carries its own
identifier and metrics, but the parent System identifier appears only
inside the `@odata.id` URL — not as a top-level value MPB can read
as a metric.

To bridge that data shape, the factory would need at least one of:
- Cross-request scalar broadcast (`from_request: X` as a non-primary
  metricSet on a list object whose primary is request Y) — not
  supported; the factory's `chained_from:` mechanism requires a
  chained-bind that fits chained-request semantics, not scalar
  broadcast.
- Regex extraction from `@odata.id` strings — explicitly "not yet
  supported" per `loader.py:2073`. The MPB wire format does carry
  `regex`/`regexOutput` fields on `expressionParts[]`, so the
  runtime supports it; only the factory's authoring DSL lacks the
  surface.
- Config-field source for metrics (`source: config_field:...`) —
  no such source type in the factory.
- Instanced metrics on a single parent object (Onur's vCommunity
  Hardware pattern, the `<ResourceGroup instanced="true">` wire
  form) — MPB UI cannot author this; would require direct
  describe.xml emission, which Tier 1 doesn't expose.

All three of the factory's `adapter_instance`-scope relationship
strategies (`synthetic_adapter_instance`, `shared_constant_property`,
`world_implicit`) were empirically falsified against live MPB UI in
the Dell PowerEdge investigation (2026-05-18). They imported but
either failed MPB's design validator (synthetic placeholder
references a non-existent property), failed the test collection
(literal constants forbidden in metric expressions), or were
rejected at import (null expressions treated as malformed envelope).

**Practical recommendation:** for hardware monitoring MPs (Redfish,
IPMI, vendor BMC APIs, similar URL-path-hierarchical data), use the
Tier 2 native Java SDK adapter authoring path. Tier 2 has full
programmatic control over relationship emission and the metric wire
format. The factory's Tier 2 pipeline (`build-sdk`, `scaffold-sdk`,
`validate-sdk` CLI commands, framework JAR at
`src/vcfops_managementpacks/adapter_framework/`) is Phase-1 operational.

For Synology DSM-shape APIs (where the data model exposes shared
scalar identifiers between parent and child responses), `field_match`
relationships work in Tier 1 — walk each relationship case-by-case
rather than assuming this limitation blocks everything.

Authority: `context/lessons_dell_redfish_2026_05_18.md` (empirical
session writeup with MPB error messages for each failure mode);
`knowledge/context/api_pattern_catalog.md` Redfish entry.

## 14. View `description` >1024 chars — content-zip import fails SILENTLY

**VCF Ops 9.1 server-side limit. Empirically bisected 2026-07-27 on
devel: 1024 chars → `FINISHED`, `imported=1`. 1025 chars → `FAILED`,
`skipped=1`, and `errorMessages` is EMPTY.**

This is a silent-failure trap, not a normal error. A
`VIEW_DEFINITIONS` content-zip import whose `<Description>` exceeds
1024 characters returns a job envelope that looks exactly like a
generic import failure:

```
state: FAILED
  VIEW_DEFINITIONS     imported=0 skipped=1 failed=0 state=FAILED
  errorMessages: []
```

No field name, no length, no hint. Non-transient — retrying does not
help. The failure mode is indistinguishable from an auth problem, a
malformed zip, or a UUID collision unless you already know to check
description length.

**Author rule: keep view `description:` at or under 1024 characters.**
The factory's view YAML encourages long prose descriptions (folded
`>` blocks are the house style in `content/views/*.yaml`) and it is
easy to sail past 1024 without noticing — count the *rendered* string,
not the YAML source lines.

**Enforced at validate time (2026-07-27):** `ViewDef.validate()` in
`src/vcfops_dashboards/loader.py` now rejects any view whose rendered
`description` exceeds 1024 characters with a local
`DashboardValidationError`, so this trap is caught by `python3 -m
vcfops_dashboards validate` instead of surfacing as a silent import
failure. Scoped to `VIEW_DEFINITIONS` / `description` only per the
"Scope notes" below.

**Debugging heuristic:** whenever a view import reports `FAILED` /
`skipped>=1` with zero `errorMessages`, check description length
FIRST before suspecting anything else.

Scope notes (unverified, do not assume either way):
- Whether the same 1024 ceiling applies to dashboard, report, symptom
  or alert descriptions was **not** tested. Only `VIEW_DEFINITIONS`
  was bisected.
- Whether view `name`/`Title` has an analogous ceiling was not tested.
- Whether the limit is bytes or characters was not probed with
  multi-byte content; the bisect used ASCII, where the two coincide.

Authority: devel install close-out 2026-07-27 (content-installer
bisect). Cross-ref:
`knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md`
§"Server-side limit: view description >1024 chars imports silently
FAILED" and `knowledge/context/wire-formats/view_column_wire_format.md`.

## 15. View row filtering — ONLY via an instanced key in `SubjectType filter`

**This entry was rewritten 2026-07-27** after its original claim ("views
cannot filter rows — impossible") was falsified by the user the same day.

A list view has exactly **one** filter surface: the `filter=` attribute on
`<SubjectType>`. It has **two different semantics** depending on the key:

| key shape | semantics |
|---|---|
| **flat** — `diskspace\|snapshot\|snapshotAge` | **object-level.** Selects which resources feed the view. A passing object renders **all** its rows. |
| **instanced** — `diskspace:<inst>\|snapshot:snapshot-<n>\|numberOfDays` | **per-row.** Evaluated against each fanned-out instance row; non-matching rows are dropped, and an object with no surviving row disappears entirely. |

The instance segment in an instanced key is a **generalized placeholder**
(like a column's `sample_instance`) — its literal value is irrelevant and
may name an instance that exists on no object. The **family prefix and
attribute suffix must be real**: a wrong family or bogus suffix fails
**closed** (zero rows everywhere), it does not degrade to "pass".

```yaml
subject:
  filter:
    - filter_type: properties       # or: metrics
      metric_key: "diskspace:90|snapshot:snapshot-1|numberOfDays"
      condition: GREATER_THAN
      value: 0
```

Works with `filter_type: metrics` on instanced metric keys too, and with
`NOT_EQUALS`/`GREATER_THAN`. `transform: CURRENT` is optional (inert).
**Do not expect an OR group to relax an instanced clause** — empirically the
outer OR array behaves object-level while the instanced clause still
constrains rows (inferred, not proven).

Full characterization (15-variant matrix) and the credit for the discovery:
`knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md`
§"Per-row filtering: IT EXISTS".

### What genuinely does NOT filter rows

The surveys below are still valid — no *other* surface offers row
filtering, which is why the mechanism above was missed:

- **View widget config**: surveyed 446 `type: "View"` widgets across 138
  reference dashboards — a closed 11-key config surface with **zero**
  filter fields. Every *other* widget type (ResourceList, MetricChart,
  Scoreboard, Heatmap, AlertList, PropertyList, ParetoAnalysis,
  HealthChart, SparklineChart, ResourceRelationship\*) carries
  `filter`/`customFilter`/`tagFilter`/`filterMode`; View alone has none.
  And those filters select *resources*, not rows.
- **View definition**: parsed 1,233 `<ViewDef>`s (live prod export +
  vendor paks). The entire `<Control>` vocabulary is
  `time-interval-selector`, `attributes-selector`, `metadata`,
  `pagination-control`, `buckets-control`. Property names containing
  "filter" or "condition": **zero**.
- **Endpoints**: `GET /internal/views/{id}/data/export` takes only
  `resourceId`/`traversalSpec`/`page`/`pageSize`; `POST /api/reports`
  has no filter field; report `<Section>` has no filter child. Probed
  live with `filter`/`instanceFilter`/`rowFilter`/`instanceName` params —
  all silently ignored, row count unchanged.
- **Widget `states[]`** grid-state blobs (389 View widgets decoded)
  carry only `id`/`hidden`/`width` per column. No filter.

### Secondary levers (pre-date the discovery; rarely needed now)

- **Member-column selection steers the row set.** The fan-out set is the
  union, across member columns, of instances holding a value for that
  member's attribute — so a metric-only member list excludes instances
  whose metrics have stopped. Costs you any property-only column.
- `listTopResultSize` (`metadata` control top-N) plus a sort — truncates
  by position, not value.
- Per-column colour bounds — cosmetic.

### Lesson

The original version of this entry declared row filtering impossible on the
strength of four exhaustive negative surveys (widget configs, 1,233 view
definitions, endpoint params, grid-state blobs). All four were *correct*.
The conclusion was still wrong, because the capability lived in a field
already surveyed and mis-modelled as object-only. **Exhaustively proving a
mechanism you imagined doesn't exist is not proof the capability doesn't
exist** — re-test the semantics of surfaces already classified before
writing "impossible".

Authority:
`knowledge/context/investigations/vm-snapshot-instanced-fanout-2026-07-27.md`
§"Per-row filtering: IT EXISTS" (15-variant matrix, devel 9.1).
Mechanism discovered by the user, 2026-07-27.

## Pak install is UI-only (not scriptable via Suite API)

The Suite API has no pak install endpoint. `.pak` files must be
installed via the VCF Ops admin UI (Administration → Solutions →
Upload). The bundle install scripts (`install.py`, `install.ps1`)
use the Suite API and cannot install paks.

**Impact on bundles that include management paks:** the README and
install instructions must explicitly state: "Install the .pak via
the VCF Ops UI first, then run `install.py` for the content bundle."
The `managementpacks:` field in the bundle manifest identifies the
dependency but does not automate the install.

**Impact on the `/publish` pipeline:** the auto-generated README in
the distribution repo must include pak install instructions before
the content install section for any bundle that references a
management pack.

Alternatives considered and deferred:
- UI session auth in the install script (complex, adds Struts login)
- SSH + pakManager in the install script (requires SSH access)
- CaSA REST API (tested, returns "Operation failed" on all pak ops)
