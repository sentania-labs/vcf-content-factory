# Feedback queue

User-originated feedback and enhancement requests captured during devel
testing, before triage. This is the **intake** queue — items here are raw
and not yet a commitment. Triage routes each item to its real home:

- A correctness problem that must converge → graduate to
  `knowledge/context/defects.md` (a `tracked` or `blocking` `DEF-NNN`).
- A design/UX change with real scope → a design note under `designs/`.
- A quick mechanical fix → straight to the owning agent.

Only the orchestrator (or the user) writes here. Ids are `FB-NNN`,
sequential, never reused. Keep the shape simple — this is a triage board,
not a gate.

| Field | Meaning |
|---|---|
| `Scope` | Which pak(s) / area. `all-sdk-paks` for cross-cutting adapter-config items. |
| `Kind` | `bug` / `ux` / `enhancement` / `question`. |
| `Status` | `open` / `triaged` / `done`. |
| `Raised` | Date + context. |

---

### FB-001 — Synology Accounts-page icon should match the Repository-page icon

- **Scope:** synology
- **Kind:** ux
- **Status:** open
- **Raised:** 2026-06-25, devel testing of `synology` 0.0.0.19.
- **Detail:** The adapter icon shown on the Accounts (adapter-instance
  config) page does not match the icon shown on the Repository / content
  page. They should be the same image. Likely a mismatch between the
  adapter-kind icon resource and the content/MP symbol icon bundled in the
  pak. Make them consistent (single source icon).

### FB-002 — Compliance "Allow Insecure" should be a pull-down

- **Scope:** compliance
- **Kind:** ux
- **Status:** open
- **Raised:** 2026-06-25, devel testing of `compliance` 0.0.0.54.
- **Detail:** The `Allow Insecure` connection parameter currently renders
  as a free-form/boolean field; it should be a **pull-down (enum)** with
  explicit choices. In describe.xml terms: give the identifier an `<enum>`
  set so the Accounts UI renders a dropdown rather than a text/checkbox
  input.

### FB-003 — "Allow Insecure" should live under Advanced Settings (all paks)

- **Scope:** all-sdk-paks
- **Kind:** ux
- **Status:** open
- **Raised:** 2026-06-25, devel testing.
- **Detail:** Across every factory SDK pak, the `Allow Insecure` parameter
  should be moved out of the primary connection fields and into the
  **Advanced Settings** section of the adapter-config form, so the default
  (secure) path is what an operator sees first. Verify the describe.xml
  mechanism for marking an identifier as advanced/collapsed.

### FB-004 — Untrusted SSL cert handling: prompt-to-accept or clear error (all paks)

- **Scope:** all-sdk-paks
- **Kind:** enhancement + question
- **Status:** open
- **Raised:** 2026-06-25, devel testing.
- **Detail:** When the target presents an untrusted/self-signed SSL cert,
  collection currently breaks (and `Allow Insecure` is the blunt
  workaround). Desired behavior, in preference order:
  1. **Prompt the user to review and accept the cert** (thumbprint
     acceptance) at connection/validate time — the native vSphere
     adapter appears to do this. **OPEN QUESTION:** can a Tier 2 SDK
     adapter surface a cert-thumbprint accept flow the way the VMWARE/
     vSphere adapter does, or is that a platform-privileged capability
     not exposed to SDK adapters? Needs research (api-cartographer /
     SDK capability investigation) before committing a design.
  2. **Failing that, emit a very clear, actionable error message** that
     names the cert problem explicitly (untrusted CA / hostname
     mismatch / self-signed + thumbprint), instead of a generic
     connection failure — so the operator knows to either fix trust or
     enable Allow Insecure.
- **Related (distinct connection):** the framework's **own loopback Suite API hop** had a separate
  TLS hostname-verification regression (fixed 2026-06-30 via the `VcfCfAdapter` shim helper — see
  `knowledge/designs/suite-api-stitcher-tls-auth-cleanup-v1.md` and FB-005). That is the adapter→`localhost`
  Suite API call, **not** the adapter→target-device call this item is about. FB-004 (the target-facing
  cert-accept flow) remains open; the loopback fix does not address it.

### FB-005 — Synology iSCSI/NFS → VMware Datastore cross-link never persists

- **Scope:** synology (and the framework cross-MP relationship path generally)
- **Kind:** bug
- **Status:** open — **root cause revised 2026-06-30** (see update at end of entry). Active prod
  blocker is the framework loopback Suite API transport, not describe.xml ResourcePath. Fix in flight:
  `knowledge/designs/suite-api-stitcher-tls-auth-cleanup-v1.md`.
- **Raised:** 2026-06-25/26, deep investigation across devel SSH logs + Suite API.
- **Detail:** The Datastore↔LUN/NFS cross-link (`emitDatastoreCrossLink` →
  `parentForeign(ds, child)`) is emitted correctly every cycle (devel log:
  `datastoreCrossLink=true`, `11 datastores loaded, 2-3 LUN + 3 NFS matches`)
  with a **byte-exact** key match (`DataStrorePath` = computed `VMFS:|naa…|`),
  but **zero edges persist** in inventory (confirmed both directions). This is
  **not** transport/credentials (maintenanceuser.properties present), **not** a
  key mismatch, and **not** the old `RelationshipBuilder` constructor swap (that
  was fixed; internal Synology edges persist fine). Root cause per
  `knowledge/context/cleanroom-spec/spec/07-relationships-cross-mp.md`: a cross-MP
  **relationship** needs **both** a declarative `<TraversalSpec>`/`<ResourcePath>`
  naming the foreign adapter kind **and** the runtime push — synology declares
  only internal paths (no `||VMWARE::Datastore` segment), so the runtime edge has
  no registered shape to bind to and is dropped. (Cross-MP **property** pushes
  need no declaration, which is why vcommunity's host props land — the spec
  separates the two; we conflated them.)
- **Secondary bug:** `matchByPath` returns one `ResourceKey`, but a shared
  datastore resolves to **N** VMWARE/Datastore UUIDs (one per vCenter view) —
  the emit must fan out to all. Out of scope for the first validation pass.
- **Codify (step 6):** cross-MP relationships require a declarative foreign
  `<ResourcePath>`; add to a lesson + the `sdk-adapter-reviewer` checklist.
- **UPDATE 2026-06-30 (prod recon — supersedes the ResourcePath theory as the active blocker):**
  Edges **do** persist on **devel** now (verified in inventory topology) with the current byte-identical
  06-26 jar — so persistence is not the live problem there. The remaining failure is **prod-only and
  transport-layer**: the stitch's `loadDatastores` Suite API call fails every cycle, so the adapter
  loads **0 datastores → 0 matches → no edge to emit at all**. Two causes by node (ground-truth from
  SSH'd adapter logs + cert inspection, see `knowledge/context/investigations/recon_log.md`):
  (1) on a **remote collector** the ambient maintenance user gets **HTTP 403** (appliance-only auth);
  (2) on the **primary node** the loopback HTTPS call fails **`certificate_unknown(46)`** because the
  operator-replaced cert's SAN lacks `localhost` and `java.net.http.HttpClient` strict-checks the
  hostname (the platform `HostnameVerifier` was dropped in the v2 `AdapterBase` rehome). The jars on
  prod and devel are **byte-identical**, so this is environmental, not a build/version issue. Fix:
  `VcfCfAdapter` shim helper wrapping `getConnection(url, getVerifier())` (Option 2) — see the design
  doc. The describe.xml ResourcePath analysis above is retained as historical record; it is not the
  prod blocker.

### FB-006 — UniFi LLDP collected from the wrong API field

- **Scope:** unifi
- **Kind:** bug
- **Status:** open
- **Raised:** 2026-06-26, direct UniFi controller API probe.
- **Detail:** The adapter reads `port_table[].lldp_table` — a key the UniFi API
  **never populates** (0 of 81 ports). UniFi serves LLDP at the **device level**
  (`device.lldp_table[]`, joined to ports via `local_port_idx`), and those
  entries carry **no `lldp_system_name`** (only `chassis_id` / `port_id`). So the
  adapter's `LLDP|lldp_system_name` emit is always null and `matchHostByName`
  can never fire. Fixing the path surfaces the **UniFi uplink/inter-switch**
  neighbors (real switch-topology value) but does **not** surface ESXi hosts
  (see FB-007). Match should key on `chassis_id`/`port_id`, not system name.

### FB-007 — UniFi switch↔host stitch: flip to host-side LLDP

- **Scope:** unifi (+ vcommunity-vsphere as the host-side data source)
- **Kind:** enhancement / redesign
- **Status:** open (circle back after synology)
- **Raised:** 2026-06-26.
- **Detail:** The UniFi-side switch→host stitch is a dead end as built: the ESXi
  hosts are **source-empty** in UniFi's LLDP (MAC table shows them cabled, but no
  LLDP neighbor record — ESXi isn't transmitting LLDP), and UniFi carries no
  `system_name` to match on. The **host side is live and complete today**: VMWARE
  `HostSystem` exposes `net:vmnicN|discoveryProtocol|lldp|systemName`
  (= UniFi switch name) + `portName` (= UniFi port name), confirmed on all 4
  ASRock WLD hosts, name-matching the live `UniFiSwitch`/`UniFiSwitchPort`
  resources. Redesign: drive the stitch from HostSystem LLDP props → match
  UniFi switch/port by name (handle the `Port 15`→`"Router"` alias via
  `portDescription`). Enabling ESXi LLDP **TX** would also light the UniFi side,
  but that path additionally needs match-by-`chassis_id` + a host vmnic MAC the
  VMWARE MP doesn't currently expose.

### FB-008 — `version_line_guard`: refuse a `v*` tag whose adapter.yaml carries a dev version line

- **Scope:** all-sdk-paks
- **Kind:** enhancement (release-safety guard)
- **Status:** open
- **Raised:** 2026-07-13 (session-handoff backlog); migrated here 2026-07-16
  during curation (the handoff file was transient and has been retired).
- **Detail:** A pre-push hook — or equivalently a CI assertion in the
  tag-triggered release workflow — that a `v*` tag's `major.minor.patch`
  equals the pak's `adapter.yaml` `version:` line, so a dev-line pak
  (`0.0.0`) refuses the tag instead of shipping. Concrete incident behind
  it: DEF-011 (closed) — the v1.0.0.12 vcommunity-vsphere release built and
  attached a `0.0.0.12` pak because adapter.yaml still carried the dev
  version line at tag time (RULE-014, `knowledge/rules/pak-version-lines.md`).
  The release-runbook post-tag verification caught it after the fact; this
  guard would refuse it up front. DEF-011's Summary names this as the
  "smallest correct fix beyond the remediation."

### FB-009 — Residual session-handoff backlog: stale citations + unifi docs stanza

- **Scope:** framework (`src/vcfops_*/`) + unifi
- **Kind:** bug (doc rot) / mechanical
- **Status:** open
- **Raised:** 2026-07-13 (session-handoff backlog); migrated here 2026-07-16
  during curation — these items were NOT resolved when the handoff file was
  retired, contrary to its "consumed" status:
- **Detail:**
  1. ~~`src/vcfops_dashboards/packager.py:7` docstring cites
     `memory/vcfops_content_import_wire_format.md`~~ **RESOLVED 2026-07-16:**
     citation fixed to `knowledge/context/wire-formats/wire_formats.md`
     (tooling, framework-reviewer APPROVE —
     `knowledge/context/reviews/framework/dashboards-packager-2026-07-16.md`).
  2. ~~"annotated dead citation in extractor.py"~~ **RESOLVED 2026-07-16:**
     the module is `src/vcfops_extractor/extractor.py` (not vcfops_packaging);
     its one dead citation (~lines 2044-2051) was already correctly
     self-annotated by the reorg-v2 phase 2 sweep — deliberate
     preserved-principle annotation, no change needed. Verified by both
     tooling and framework-reviewer.
  3. "unifi build 12 (cross_mp_edges docs stanza)" — no `cross_mp_edges`
     mention found in unifi README/docs as of 2026-07-16; verify whether the
     stanza shipped in a generated doc or is still pending.
  Items 1–2 are `src/vcfops_*/` diffs → route through `tooling` +
  `framework-reviewer` per RULE-013 when picked up.

### FB-010 — `GET /api/policies/{id}` returns HTTP 500 — blocks per-attribute policy inspection

- **Scope:** platform fault (re-scoped 2026-07-23: reproduced on BOTH devel and prod — not instance-specific; likely a platform/API-version behavior, raising the odds this is a product bug worth a Broadcom SR)
- **Kind:** bug (instance) / investigation
- **Status:** open
- **Raised:** 2026-07-16, during the DEF-010 enablement recon
  (`knowledge/context/investigations/recon_log.md`, dated entry).
- **Detail:** `GET /api/policies` (list) works and identifies the active
  default policy ("vSphere Solution's Default Policy (Apr 17, 2026)",
  id `9c1d42be-09b7-4149-92fc-2224e3d778bd`, defaultPolicy: true), but
  `GET /api/policies/{id}` — and the `/base`, `/policy/{id}`,
  `/metricconfig`, `/collectionconfig` variants — consistently return
  HTTP 500 "Internal Server error, cause unknown". Server-side fault,
  reproducible. Consequence: the per-attribute activation table for
  VMWARE HostSystem cannot be read via REST, which is what keeps
  DEF-010's enablement classification INFERRED rather than PROVEN.
  Next steps: try a different API version/path (internal surface?),
  check collector/api logs on devel, or accept the alternative proof
  (a policy edit showing `net|packets*` keys begin accumulating).

### FB-011 — vcommunity-vsphere: "HA Admission Control enabled" widget times out — renderer drops `startPeriod`/`endPeriod` from advanced-time-mode views

- **Scope:** framework (`src/vcfops_dashboards/render.py`, `loader.py`,
  `src/vcfops_extractor/`) + vcommunity-vsphere
- **Kind:** bug / framework fix + pak rebuild
- **Status:** framework half fixed 2026-07-21 (`tooling` agent,
  `framework-reviewer` APPROVED 0 BLOCKING); pak-side view YAML / rebuild /
  Playwright re-verify still open.
- **Raised:** referenced as "tracked separately as FB-011" in the DEF-012
  closure pass (`knowledge/context/reviews/def-012-closure-visual-pass-2026-07-16.md`)
  but never registered; entry written 2026-07-21 with root-cause diagnosis.
- **Detail:** On vSphere Cluster Configuration 2.0, the "HA Admission
  Control enabled" widget renders "View request timed out" while every
  sibling distribution widget renders live data (observed 2026-07-16
  build-13 visual pass; explicitly NOT a DEF-012 widget — its DISCRETE
  shape is correct). The backing view
  (`views/vSphere Cluster HA Admission Control status.yaml` in the pak
  repo) is the **only** view in the pak with `advanced_time_mode: true`.
  The vendor original ViewDef (`View - Set 3.xml`, id
  `fc64c67a-d5b0-4a03-a10b-767b9b247120`) pairs
  `advancedTimeMode=true` with `startPeriod=PREVIOUS` and
  `endPeriod=NOW`; our renderer
  (`src/vcfops_dashboards/render.py:311-317`) emits only
  `advancedTimeMode`/`unit`/`count` and silently drops
  startPeriod/endPeriod — leaving the server an advanced-mode query with
  no defined range, the leading suspect for the timeout. The loader and
  extractor likewise have no start/end-period fields, so round-trips
  lose them too.
- **Proposed fix:** extend the view time-window model with
  `start_period`/`end_period` (loader + renderer emit them when
  `advanced_time_mode: true`; extractor captures them), route through
  `tooling` + `framework-reviewer` (RULE-013), update the pak view YAML,
  rebuild, and Playwright-verify the widget renders. Fallback content-only
  fix if the framework change is deferred: drop `advanced_time_mode: true`
  from that one view to match its working siblings (accepts drift from
  vendor time semantics).
- **Related:** DEF-012 (same dashboard, distinct root cause),
  `knowledge/context/reviews/def-012-closure-visual-pass-2026-07-16.md`
- **Framework fix landed 2026-07-21:** `ViewTimeWindow` gained optional
  `start_period`/`end_period` fields (`src/vcfops_dashboards/loader.py`);
  the renderer (`src/vcfops_dashboards/render.py:_xml_time_interval_selector`)
  emits `startPeriod`/`endPeriod` Properties whenever `advanced_time_mode`
  is true, **defaulting to `PREVIOUS`/`NOW` when unset**. Defaulting
  evidence: a full survey of the reference corpus (`reference/references/**`,
  250+ time-interval-selector controls) found exactly one control with
  `advancedTimeMode=true` in the entire corpus, and it carries
  `startPeriod=PREVIOUS`/`endPeriod=NOW` — no other pairing, and no
  advanced-mode-without-range example, is attested anywhere. Properties
  are omitted entirely when `advanced_time_mode` is false, so the other
  250+ existing views render byte-identically (verified: full test suite
  583 passed / 4 skipped / 0 failed, full validate chain OK). The
  extractor (`src/vcfops_extractor/extractor.py`) and reverse-local path
  (`src/vcfops_extractor/reverse_local.py`) now capture/re-emit the same
  fields for a lossless round-trip. Test coverage:
  `tests/test_fb011_advanced_time_mode_range.py`. **Not yet done:** the
  pak's own `views/vSphere Cluster HA Admission Control status.yaml` is
  unedited (tooling agent does not touch pak content) — either add
  explicit `start_period: PREVIOUS`/`end_period: NOW` to that view's
  `time_window:` block (belt-and-suspenders, since the renderer now
  defaults it) or rely on the default, then rebuild the pak and
  Playwright-verify the widget stops timing out on a live instance.

### FB-012 — Cluster Performance 2.0: dashboard renders essentially blank

- **Scope:** vcommunity-vsphere
- **Kind:** bug / question (triage vs SM enablement)
- **Status:** open
- **Raised:** 2026-07-16 QA visual pass (FINDING-2), devel.
- **Detail:** Both top scoreboards ("Average Performance of All Clusters",
  "Count of Clusters not in Green zone") show "No data to display" while
  claiming "1 - 15 of 507 items"; the "vSphere Clusters" self-provider list
  shows only the unconfigured placeholder, leaving all downstream widgets
  empty. Two candidate causes to separate: (a) SM-enablement scope — the
  13-SM Cluster Performance chain was manually policy-enabled 2026-07-13
  for the local clusters only, and these aggregates may sweep a much larger
  resource catalog; (b) a genuine self-provider/interaction wiring defect
  (the cluster list should populate regardless of SM data). The identical
  "507 items" count also appears in FB-013 — correlate. Note: same-day
  build-13 install and the DEF-010 metric test may change what this
  dashboard shows; re-check before deep triage.

### FB-013 — Critical Business Applications: dashboard essentially blank

- **Scope:** vcommunity-vsphere (likely environment, not content)
- **Kind:** question
- **Status:** open
- **Raised:** 2026-07-16 QA visual pass (FINDING-4), devel.
- **Detail:** All Business Application cards and the average-performance
  scoreboard show "No data to display" against the same suspicious
  "507 items" count as FB-012. The Business Application object type is a
  built-in that requires app-discovery configuration/tagging the lab has
  never done — most likely environment, not a pak defect. Confirm the lab
  has zero BusinessApplication resources; if so mark this dashboard
  "requires app discovery configured" in pak docs and close.

### FB-014 — vSphere Resource Management: "Cascading Resource Pools?" widget render error

- **Scope:** vcommunity-vsphere
- **Kind:** bug
- **Status:** open
- **Raised:** 2026-07-16 QA visual pass (FINDING-3), devel.
- **Detail:** Widget body renders "The view cannot be rendered for the
  specified Object." — a genuine render failure, not "No data". Suspected
  content defect: self-provider pin / subject-type mismatch (same failure
  family as `knowledge/context/api-surface/dashboard_selfprovider_pin_wire_format.md`,
  different widget). Compare the widget's pinned object type against the
  view's subject kinds; check the vendor original's binding.

### FB-015 — Legacy MSSQL/Oracle Query Performance dashboards live on devel with mis-scoped anchor

- **Scope:** devel instance content (repo: attic'd legacy content)
- **Kind:** bug / stale-content cleanup
- **Status:** open — needs a user decision (uninstall vs fix)
- **Raised:** 2026-07-16 QA visual pass (FINDING-5), devel.
- **Detail:** `[VCF Content Factory] MSSQL Query Performance & Blocking`
  and `...Oracle Query Performance & Blocking` are installed and live on
  devel but exist in the repo only under
  `knowledge/context/attic/legacy-root-content/` (retired in reorg v2).
  Their "Select SQL Server / Oracle Instance" self-provider lists match a
  UniFi switch (`usw-lite-16-nuc`) — the anchor's resource-kind filter is
  mis-scoped — and every dependent widget is empty ("Heatmap is not
  configured"). Recommendation: uninstall both from devel (stale,
  unmaintained, no DB adapters in the lab); fixing the binding only makes
  sense if the dashboards return to active content.

### FB-016 — ~~devel: stats API returns empty for SM statkeys the UI charts~~ RESOLVED: factory-side key-format error, not a platform bug

- **Scope:** factory verification tooling (was misfiled as devel platform)
- **Kind:** bug (ours) / lesson
- **Status:** done — root-caused and codified same day
- **Raised:** 2026-07-16, DEF-010 closure investigation; resolved
  2026-07-16 by direct statkeys inspection.
- **Detail (corrected):** The stats API serves SM series under the key
  `Super Metric|sm_<uuid>` — every query that day used the bare
  `sm_<uuid>` and got `{"values": []}`, which reads exactly like "SM
  never computed." There is NO UI-vs-API data-path discrepancy: with the
  correct key, the full fleet sweep returns the complete series on all
  9 hosts + 3 clusters, values matching the UI charts exactly. The
  original entry's platform-bug theory was wrong; the plain-metric
  control (which worked) used a real key, masking the pattern. Codified:
  `knowledge/lessons/sm-statkey-api-prefix.md`. NOT related to FB-010
  (the policy-API 500 is real and remains open).

### FB-017 — loader-level validation for out-of-grid dashboard coords (DEF-013 follow-up)

- **Scope:** framework (`src/vcfops_dashboards/loader.py`)
- **Kind:** enhancement (reviewer WARNING follow-up)
- **Status:** open
- **Raised:** 2026-07-22, framework-reviewer DEF-013 review
  (`knowledge/context/reviews/framework/def013-gridster-floor-2026-07-22.md`, APPROVE
  with 2 WARNING / 1 NIT).
- **Detail:** The DEF-013 fix floor-clamps `gridsterCoords` to the
  1-indexed grid at render time, but the clamp is defensive, not a
  whole-layout translation: a fully 0-based authored dashboard shifts
  only its zero-row and can render a silent one-row widget overlap.
  Reviewer recommendation: add a loader-level validation WARNING when
  any widget authors `x < 1` or `y < 1`, so authors fix the source and
  the render clamp stays a backstop. NIT from the same review: the
  ceiling-overflow class (`x + w > 13`) is also unvalidated — the
  sibling half of the 00d3382 symptom family; cover both in one pass.
  Route through `tooling` + `framework-reviewer` (RULE-013).

### FB-018 — `vcfops_packaging build` crashes on SDK-pointer release manifests (`zip_path=None`)

- **Scope:** framework (`src/vcfops_packaging/cli.py`)
- **Kind:** bug (TOOLSET GAP, pre-existing)
- **Status:** open
- **Raised:** 2026-07-22, content-packager DEF-013 stale-zip rebuild.
- **Detail:** `python3 -m vcfops_packaging build bundles/releases/*.yaml`
  fails with `'NoneType' object has no attribute 'name'` for the three
  SDK-adapter release manifests (synology / unifi / vcommunity-vsphere
  managementpacks). Root cause (packager read-only diagnosis):
  pointer-only SDK builds intentionally return `zip_path=None`
  (`release_builder.py` ~422-439), but `cli.py::_build_release_to_dist`
  (~line 136) unconditionally dereferences `art.zip_path.name`. The
  `/publish` path handles the None case; the `build` command does not.
  Reproduced with pre-DEF-013 `render.py` — NOT a DEF-013 regression.
  Route through `tooling` + `framework-reviewer` (RULE-013).

### FB-019 — `_resource_list_widget(dashboard_id="")` default is a latent footgun

- **Scope:** framework (`src/vcfops_dashboards/render.py`)
- **Kind:** nit (reviewer follow-up)
- **Status:** open
- **Raised:** 2026-07-22, framework-reviewer column_preset review
  (`knowledge/context/reviews/framework/resourcelist-column-preset-2026-07-22.md`, NIT).
- **Detail:** Not reachable today (sole caller passes `dashboard.id`),
  but a future caller omitting the param while a widget has
  `column_preset` would silently emit a malformed states key
  `permResGrid_widget__<widget>`. Make the param required or assert
  non-empty when states is emitted. Route through `tooling` +
  `framework-reviewer` next time render.py is touched.

### FB-020 — in-place dashboard update import drops NEW widget `states[]`

- **Scope:** platform import behavior (documentation) + install procedure
- **Kind:** investigation / lesson candidate
- **Status:** open
- **Raised:** 2026-07-22, name-only column-preset verification.
- **Detail:** Adding a `states[]` grid-state entry to an EXISTING
  (previously-imported) dashboard's widget does not survive the
  content-import update path — the live widget ends with no `states`
  key while sibling widgets' pre-existing `states[]` round-trip fine.
  Fresh-UUID imports DO carry `states[]` (proven,
  `knowledge/context/api-surface/resourcelist_column_state_wire_format.md` §3 —
  that test used a fresh clone, not an in-place update; §3 needs a
  scope caveat). Local render is correct (5315-byte blob present in
  the package output). Consequence: shipping a column-preset change to
  an already-installed dashboard requires DELETE + re-import, not
  update-in-place. Verify whether other widget-level additions share
  this partial-merge behavior; then codify as a lesson + installer
  procedure note.

### FB-021 — ExtJS grid ignores byte-correct `states[]` column visibility for the ResourceList picker

- **Scope:** platform UI behavior (investigation) — dashboard/cpu_support_status picker widget
- **Kind:** bug (cosmetic) / investigation
- **Status:** open
- **Raised:** 2026-07-22/23, FB-020 remediation re-pass.
- **Detail:** After the fresh-import fix, BOTH server-side stores agree
  and are byte-correct (definition `states[]` and per-user
  `stateManager.action` entry, 5315 bytes, h15-only visible) — yet the
  rendered grid still shows all 6 default columns, across full page
  reloads. Not the materialization race (isLoading:false, full
  configs), not FB-020 (fresh import carries the blob). Hypothesis to
  test: the modern Angular shell's iframe wrapping of the legacy ExtJS
  grid may not apply `states[]` column visibility the way the direct
  `/ui/index.action` path (used in the original wire-format
  investigation) does. Needs api-explorer + browser pass. Functional
  impact: none (cosmetic — extra columns in the picker); the published
  zip carries the correct blob for platforms that honor it.
