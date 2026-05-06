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
`vcfops_supermetrics/client.py:287-292`). But the policy-export →
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

Recon checks allowlisted external repos under `references/`
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
