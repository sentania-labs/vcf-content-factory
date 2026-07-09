# VCF Operations 9.1 — Adoption Review for the VCF Content Factory

**Date:** 2026-06-13
**Reviewer:** Claude (read-only analysis; orchestrator commits)
**Governing philosophy (user):** "take advantage of new things but be
mindful of how old versions work — we don't want to clearly abandon
anything that is still a supported product." Additive, version-aware
adoption. **NOT a hard cutover off 9.0.x** (9.0.x is still supported).

**Sources used:**
- **HTML what's-new** (curated delta index):
  `https://techdocs.broadcom.com/us/en/vmware-cis/vcf/vcf-9-0-and-later/9-1/release-notes/vmware-cloud-foundation-9-1-0-0-release-notes/what-s-new/whats-new-vcf-ops.html`
- **VCF 9.1 release-notes landing**: build `25377994`, release date 12 May 2026.
- **Committed prod OpenAPI specs** (`reference/docs/operations-api-9.1.json` public 343
  paths, `reference/docs/internal-api-9.1.json` internal 217 paths): fetched read-only
  from the prod instance, confirmed **VCF Operations 9.1.0.0, build `25435105`**
  via `/suite-api/api/versions/current`. This is a different 9.1.0.0 patch build
  than the GA what's-new's `25377994` — both are 9.1.0.0; the specs reflect the
  actual prod instance, the right ground truth for prod-accurate authoring. **All
  spec-based claims below are reconciled against these committed files** (this
  supersedes any PDF prose where they conflict — e.g. `receiverAddress`).
- **VCF 9.1 PDF** `reference/docs/vmware-cloud-foundation-9-1.pdf` (9,279 pp),
  extracted to `/tmp/vcf91.txt` (687,364 lines). Cited as `PDF:<line>`
  (pdftotext line numbers, stable for this extract; the PDF prints a
  page footer near each cited block — e.g. the API contract block prints
  "552", the Prometheus MP design prints "6194/6195").

Where a claim cannot be confirmed from what was obtained, it is marked
**UNVERIFIED** — not fabricated.

---

## Executive summary

**Highest-value adoptable items (additive, no 9.0.x abandonment):**

1. **Prometheus-source management packs in MPB** (`PDF:5087`, design
   `PDF:496806`). A first-class MPB wizard path that builds an MP from a
   Prometheus server (define source → map metrics to objects → relationships
   → verify → install) with **no SDK integration**. This is a genuinely new
   *authoring lane* the factory's MP track could expose for Prometheus-backed
   targets — adjacent to today's Tier-1 MPB YAML and Tier-2 Java SDK. **WATCH
   → DEFER to design**: investigate whether the wizard emits a design.json the
   factory's render-export/push-design loop can drive, or whether it's UI-only.

2. **Two VCF Operations Suite-API contract changes — both non-breaking**
   (`PDF:31476`, reconciled against the committed `reference/docs/operations-api-9.1.json`).
   (a) `POST /suite-api/api/alertplugins/{pluginId}/test` gains a
   `receiverAddress` parameter — but the spec declares it **`required: false`**
   (default `""`), so the PDF's "must supply" prose overstates it: it is
   **optional and email-plugin-specific**. (b) `GET
   /suite-api/api/resources/{id}/relationships` **relaxes** the
   `relationshipType` query parameter from required (9.0) to optional (9.1) —
   confirmed in both committed specs. Neither breaks a 9.0.x client: (a) is a
   new optional field, (b) is a relaxation. **WATCH**, not adopt-now — the
   factory has no caller for either today; keep sending `relationshipType`
   where it already does (required on 9.0.x, harmless on 9.1).

3. **Public Findings / Diagnostics REST API** (`PDF:5503`) and **Real-Time
   Metrics APIs (VODAP), Prometheus-compatible, PromQL** (`PDF:5790`). New
   read surfaces. The Findings API is the more directly factory-relevant
   (diagnostic findings → reporting/ticketing); VODAP/PromQL is a new metrics
   plane the factory does not currently model. **WATCH** — neither is a content
   type the factory authors today; both are candidate future data sources.

4. **Log content packs are end-of-general-support; convert to management
   packs** (`PDF:31215`). Starting 9.1 you can no longer use VCF Operations
   for Logs (formerly Aria Operations Logs) content packs — third-party content
   packs **must be converted to management packs**. Log management is now
   converged into Operations (what's-new "Unified Log Management"). This
   reframes log dashboards/alerts as MP-delivered content — squarely in the
   factory's MP lane. **WATCH** (no factory log content exists yet; note the
   direction).

**Portability landmines (things that would abandon 9.0.x if adopted blindly):**

- **FIPS compliance is enabled by default and *cannot be disabled* on 9.1**
  (`PDF:31225`). The factory's Tier-2 SDK lessons already assume this
  (`context/tier2_architecture.md:105`, `:414` — bouncycastle
  `approved_only=true`, the `AmbientCredential` FIPS-safe decrypt path). 9.0.x
  did **not** hard-force FIPS. Any adapter crypto/HTTP path that only works
  with non-approved providers is a 9.1 install failure. **This is already a
  prod-9.1 reality** — see the JAX-WS Provider failure
  (`context/investigations/prod_91_jaxws_provider_failure.md`). Do not "adopt"
  anything that assumes FIPS-off.
- **Direct vCenter authentication removed in 9.1** (`PDF:31231`). vCenter user
  credentials can no longer authenticate to the Operations API, and the vCenter
  list is gone from the login screen. The factory authenticates via
  `/suite-api/api/auth/token/acquire` (local/SSO), so this is **not** a factory
  break today — but any doc/example that suggested vCenter-cred auth is now
  invalid on 9.1. Keep token-acquire as the only documented path.
- **Network Share alert/report plugin removed in 9.1** (`PDF:31223`,
  FIPS-driven). If the factory ever emits a Network Share notification plugin
  config it would fail on 9.1; Standard Email is the replacement.
- **Standalone MPB appliance no longer supported** (`PDF:31234`) — use the
  in-product MPB (introduced 9.0). The factory already targets in-product MPB,
  so no change; just don't reintroduce a standalone-appliance assumption.

**Bottom line:** The factory's core content-definition schemas (super metrics,
views, dashboards, custom groups, symptoms, alerts, reports) show **no breaking
property changes** in 9.1 — checked property-by-property against the committed
9.1 OpenAPI spec (`reference/docs/operations-api-9.1.json`), not just the doc TOC: no
properties added or removed on `symptom-definition`, `alert-definition`,
`recommendation`, or `report-definition`, so **no forced content rewrite**. Two
caveats keep this from being "no delta at all": (1) 9.1 **deprecates**
`symptom-definition.realtimeMonitoringEnabled` (`operations-api-9.1.json`:
`deprecated: true`; absent in 9.0) — existing content still validates, but new
symptom authoring should avoid that field; (2) the public API surface is
**+93 paths (250→343, 0 removed)** — purely additive, so no call the factory
makes today breaks. The adoptable surface is **APIs and the MP authoring lane**;
there is **no mandatory content rewrite** and (per item 2) no *mandatory* API
absorption either — the API additions are naturally version-guardable behind
the existing `/suite-api/api/versions/current` anchor.

---

## Per-candidate analysis

### C1 — Suite-API contract: `alertplugins/{id}/test` adds `receiverAddress`

- **What's new in 9.1:** `POST /suite-api/api/alertplugins/{pluginId}/test`
  gains a `receiverAddress` request parameter. The PDF prose says "Test-alert
  workflows must be updated to supply this address" (`PDF:31476`) — **but the
  committed 9.1 spec declares it `required: false` with default `""`**
  (`reference/docs/operations-api-9.1.json`, the `receiverAddress` parameter). So it is
  **optional and email-plugin-specific**, not a blanket requirement; the PDF
  prose overstates it. Nothing deleted/deprecated.
- **Factory relevance:** Low. The factory authors alert *definitions*; it does
  not drive the alert-plugin *test* flow today. If tooling ever does, supply
  `receiverAddress` only when testing an email plugin.
- **Verdict: WATCH** (corrected down from ADOPT NOW after the spec reconcile).
  Optional param, no factory caller today — nothing to absorb until the factory
  actually exercises plugin tests.
- **Version-awareness:** Minimal. The parameter simply does not exist on 9.0.x,
  so omit it there; on 9.1 include it only when testing an email plugin. **No
  mandatory version-gate** — it is optional on the wire (`required: false`) and
  unused by the factory today.

### C2 — Suite-API contract: `resources/{id}/relationships` drops required `relationshipType`

- **What's new in 9.1:** For `GET /suite-api/api/resources/{id}/relationships`,
  the `relationshipType` query parameter is **no longer required** (`PDF:31481`).
- **Factory relevance:** Recon/ops-recon and SDK-adapter stitch verification
  read relationships. A 9.0.x caller that always passed `relationshipType`
  still works on 9.1 (param is optional, not removed).
- **Verdict: NO ACTION (no-op for existing callers).** Existing callers that
  pass the param continue to work unchanged; new callers may omit it on 9.1.
  Nothing to adopt — this is why item 2 of the executive summary rates the
  pair WATCH rather than adopt-now.
- **Version-awareness:** **No guard needed** if the factory keeps passing the
  param. Backward-compatible. Only relevant if someone *relies* on omitting it
  — then it's 9.1-only.

### C3 — Prometheus-source Management Packs in MPB

- **What's new in 9.1:** "Prometheus support is now added to the Management
  Pack Builder… create your own Management Pack using metrics from Prometheus
  Servers… without writing new integrations using the SDK." (`PDF:5087`). Full
  wizard: Define a Source (host/port 9090/TLS Verify|No-Verify|No-TLS/Basic|No-
  Auth, Test Connection lists Prometheus *jobs*) → Add Objects (map Prometheus
  metrics+labels to Ops object types; identifiers from shared labels; `instance`
  label present by default) → Specify Relationships → Verify → Install
  (`PDF:496806`–`PDF:496900`).
- **Factory relevance:** A new MP authoring lane orthogonal to Tier-1 MPB YAML
  and Tier-2 Java SDK. For any Prometheus-exporting target, this could replace
  a hand-authored adapter. The open question is the **interchange format**:
  does the wizard persist a design artifact (design.json) the factory's
  render-export → push-design → MPB UI Verify loop can drive headlessly, or is
  it UI-only?
- **Verdict: WATCH → DEFER to a design spike.** High potential value, but
  requires `api-explorer`/`mp-designer` investigation of the wizard's persisted
  format before any factory lane is built. **UNVERIFIED**: whether the
  Prometheus design is push-design compatible.
- **Version-awareness:** **9.1-only feature.** Prometheus MPB does not exist on
  9.0.x, so any factory lane built on it must be version-gated and must **not**
  replace the existing Tier-1/Tier-2 lanes (which remain the only options on
  9.0.x). Purely additive — safe as long as it's gated.

### C4 — Public Findings / Diagnostics REST API

- **What's new in 9.1:** "Starting with VCF Operations health and diagnostics
  9.1, you can use a set of public APIs that allow you to integrate diagnostic
  findings into your internal reporting and monitoring workflows… centralize
  monitoring of real-time findings or get data for trend analyses." See
  "Diagnostics Public REST API" (`PDF:5503`).
- **Factory relevance:** Not a content type the factory authors. Potential
  future data source (findings → report/dashboard), and a candidate input for
  recon. Exact endpoints/schemas **UNVERIFIED** (release notes name the feature;
  the API reference page was not retrieved).
- **Verdict: WATCH.** No action until a concrete user request references
  findings-as-content.
- **Version-awareness:** 9.1-only. Additive; no 9.0.x impact.

### C5 — Real-Time Metrics APIs (VODAP) + PromQL Viewer widget

- **What's new in 9.1:** New "Real-Time Metrics APIs (VODAP)" —
  Prometheus-compatible Edge APIs, up to 2-second granularity across ESX/
  vCenter/vSAN/NSX, native PromQL, Grafana-as-datasource; single API call
  selects built-in collection profiles (Essentials/Standard/Verbose); legacy
  vStats Tech-Preview APIs **deprecated** (`PDF:5790`). A **PromQL Viewer
  widget** is added to dashboards (`PDF:392192`); requires the real-time
  metrics component to be installed (`PDF:392200`). PromQL Custom Query in the
  UI has no autocomplete (`PDF:5468`, `PDF:383760`).
- **Factory relevance:** Two angles. (a) The **PromQL Viewer widget** is a new
  dashboard widget type the factory's `dashboard-author` does not know — if a
  user wants a PromQL widget on a 9.1 dashboard, that's a renderer/loader gap
  (TOOLSET GAP candidate). (b) VODAP is a separate metrics plane (real-time
  metrics component / store) the factory does not model.
- **Verdict: WATCH** (PromQL Viewer widget) — DEFER the VODAP plane.
- **Version-awareness:** **Landmine if adopted into dashboard YAML schema.** A
  PromQL Viewer widget requires the real-time metrics component and is 9.1-only;
  emitting it would make a dashboard fail to render on 9.0.x. If ever supported,
  it must be a version-gated widget, not a default. The real-time metrics
  store/component is a separate deployable (`PDF:184473`) — not present on a
  plain 9.0.x Ops, another reason to gate.

### C6 — Log management converged; log content packs → management packs

- **What's new in 9.1:** "Unified Log Management" integrated into VCF Operations
  (masking, filtering, forwarding, partitioning, archived-log import; Log
  Insight agent + Fluentbit). **End of general support for VCF Operations for
  Logs content packs** — third-party content packs must be **converted to
  management packs** ("Converting Content Packs to Management Packs",
  `PDF:31215`, `PDF:336966`). A "Log Management Health Overview Dashboard" ships
  (`PDF:1786`).
- **Factory relevance:** Reframes log dashboards/alerts as **MP-delivered**
  content — the factory's MP lane (Tier-1 MPB YAML / Tier-2 SDK). No factory
  log content exists today, so nothing to migrate; this is directional.
- **Verdict: WATCH.** If a user asks for log content, the answer on 9.1 is an
  MP, not a content pack.
- **Version-awareness:** The content-pack→MP conversion is a 9.1 *requirement*,
  not something the factory does today. No 9.0.x abandonment risk for the
  factory because the factory never authored log content packs.

### C7 — Password policy framework + third-party integration (Enterprise Vault) APIs

- **What's new in 9.1:** Fleet/instance **password policies** (length,
  complexity, lockout, change interval, history) across VCF components incl.
  standalone vCenter/ESX ≥ 8.0 U3; **new APIs to integrate with third-party
  tools such as Enterprise Vault / CyberArk** (`PDF:5200`, `PDF:295541`);
  break-glass passwords no longer stored. Certificate management gains
  **third-party-integration/automation APIs** for all VCF components
  (`PDF:5186`).
- **Factory relevance:** **Out of scope** for the factory's content lane —
  these are fleet/security operations APIs, not Operations *content* (super
  metrics/dashboards/etc.). The user's brief flagged them to verify; they are
  real (cited) but they are not authoring surfaces the factory drives.
- **Verdict: DEFER / out of scope.** Note their existence; no factory action.
- **Version-awareness:** 9.1-only. No 9.0.x impact since the factory doesn't
  touch these.

### C8 — VCP configuration drift-detection templates (Fleet Configuration Management)

- **What's new in 9.1:** "Configuration Management (Earlier Known as
  Configuration Drifts)" — configuration *templates* for vSphere Configuration
  Profile (VCP) enabled clusters; monitor + detect drift + **schedule drift
  detection** on ESX clusters across the fleet; download host/cluster drift
  reports (`PDF:5224`). Standalone Configuration Drifts functionality has been
  **incorporated into the new VCF Operations Fleet Configuration Management
  service** (`PDF:31228`). Global remediation settings for VCP clusters
  (`PDF:4176`).
- **Factory relevance:** **Out of scope** for the content lane — VCP drift
  templates are a fleet-config service, not authored Operations content.
  Flagged in the brief; verified as real, but not a factory authoring surface.
- **Verdict: DEFER / out of scope** (note for awareness).
- **Version-awareness:** 9.1 reorganization (rename + service move). No factory
  content impact.

---

## Reconciling the 9.0.2-hardcoded lessons against 9.1

The factory enshrines several 9.0.2 runtime behaviors. The 9.1 release notes
and what's-new pages do **not** address any of these runtime semantics
directly — so the honest answer for most is **still UNVERIFIED on 9.1**, and
the existing "open residual / 9.1 unverified" flags remain correct. Do **not**
rewrite these lessons based on 9.1 docs; they require a live 9.1 collect.

- **`lessons/setrelationships-foreign-adapter-scoped.md`** (per-reporting-
  adapter `setRelationships` scoping). 9.1 docs say nothing about
  `setRelationships` *runtime scoping*. The only relationships-API change in
  9.1 is C2 above (the read endpoint's optional `relationshipType`), which is
  **unrelated** to the write-side per-adapter scoping the lesson asserts.
  **Verdict: UNVERIFIED on 9.1 — lesson's open residual stands.** Keep the
  acceptance criterion: prove foreign-parent edge retention on the first 9.1
  stitch install. (The 9.0.2 proof is recorded in
  `context/investigations/v2_round2_devel_acceptance_2026_06_10.md`; the mixed-
  fleet hazard is already captured in
  `lessons/cross-runtime-pak-upgrade-split-brain.md`.)

- **`lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`** (Suite-API SSL
  trust-on-first-use vs Java HTTP). 9.1 docs do **not** describe any change to
  Suite-API SSL trust behavior. (The only "TOFU" references in the 9.1 PDF are
  NSX ARP/ND snooping — `PDF:223234` — entirely unrelated.) **Verdict:
  UNVERIFIED on 9.1.** *However*, the **FIPS-by-default-and-cannot-be-disabled**
  change (`PDF:31225`) is the relevant adjacent risk: the SSL/HTTP path on a
  9.1 collector runs under `approved_only` crypto, which is exactly the regime
  `context/tier2_architecture.md` and `prod_91_jaxws_provider_failure.md`
  already document as the prod-9.1 JAX-WS Provider failure. So the SSL-TOFU
  lesson's *mechanism* is unchanged-by-docs, but the *crypto environment it
  runs in* is now hard-FIPS on 9.1 — re-validate the stitch SSL path on a 9.1
  collector, not just 9.0.2.

- **`context/api-surface/vcf_operations_api_surface.md`** (404s on
  `/internal/adapterkinds`, `/internal/credentials`, etc., on 9.0.2). 9.1 docs
  don't enumerate internal-endpoint presence. **UNVERIFIED on 9.1** — re-probe
  with ops-recon against a 9.1 instance before relying on either presence or
  absence. The version anchor `GET /suite-api/api/versions/current`
  (`vcf_operations_api_surface.md:497`) remains the correct mechanism for any
  version-guarded behavior (C1 especially); on 9.1 it returns the 9.1 release
  name/major/minor/build.

- **Confirmed-by-docs 9.1 deltas that touch the lessons' environment:**
  FIPS-by-default (`PDF:31225`), direct-vCenter-auth removed (`PDF:31231`),
  Network Share plugin removed (`PDF:31223`), standalone MPB appliance
  unsupported (`PDF:31234`). None *contradict* an existing lesson; the
  FIPS-by-default one *reinforces* the Tier-2 architecture's existing FIPS
  assumptions and the prod-9.1 JAX-WS investigation.

---

## What to do next (recommendation, no action taken)

1. **ADOPT NOW (small, version-guarded):** C1/C2 Suite-API contract handling —
   route through `tooling` to add a `versions/current`-gated `receiverAddress`
   on the alert-plugin test call; C2 needs no change if the factory keeps
   passing `relationshipType`.
2. **DESIGN SPIKE (DEFER):** C3 Prometheus MPB — spawn `api-explorer` /
   `mp-designer` to determine whether the Prometheus wizard persists a
   push-design-compatible artifact before building a new MP lane.
3. **WATCH (no action):** C4 Findings API, C5 PromQL Viewer widget + VODAP, C6
   log-content-pack→MP direction. Revisit when a concrete user request lands.
4. **Out of scope (note only):** C7 password/cert third-party APIs, C8 VCP
   drift templates — fleet/security ops, not Operations content.
5. **Do not rewrite the 9.0.2 lessons.** Their "9.1 unverified" flags are
   correct; close them only with a live 9.1 collect, not with these docs.
   Keep version-conditioned ("9.0.2: X / 9.1: Y") handling rather than a
   blanket rewrite — 9.0.x remains supported.
