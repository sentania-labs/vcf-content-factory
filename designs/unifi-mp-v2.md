# Design Artifact: UniFi Network Management Pack v2

**Status.** mp-author-ready (round 3 closed 2026-04-30).

**MP display name:** `VCF Content Factory UniFi`
(per CLAUDE.md hard rule #5 — MPs use prose-form `VCF Content Factory
<name>`, no brackets; distinct from content's bracketed `[VCF Content
Factory]` form.)

**Supersedes.** `designs/unifi-mp-v1.md` (2026-04-18). v1 was written
*before* `context/api-maps/unifi-network-api.md` landed and *before* the
2026-04-29 substrate gains (`is_singleton`, explicit `chains_from`/`bind`
grammar, three-phase MPB validation model, URL-path-identity recognition
rule). v1's object model, grammar, and framework-vs-target review are
re-derived here against current substrate.

**Calibration discipline.** The community-authored
`references/jcox-au_vmware/unifi_MP_Builder_Design.json` is the post-render
diff anchor and was **not** consulted during this design pass.

**Target MP filename:** `content/managementpacks/unifi_network.yaml`
**Adapter kind:** `mpb_unifi_network`
**Bundled content:** none in v2 (factory dashboards ship separately, same
pattern as Synology v2).

---

## Original Request

Phase 1.5 of the framework growth path. The Synology MP terminated
2026-04-29 because MPB's chained-collection wire format can't represent
Synology's URL-path-identity API pattern (parent ID consumed by URL path,
not echoed in response — `objectBinding` can't bind). That failure produced
durable substrate gains. UniFi's job: be the second target the substrate
sees, on a fresh API surface, and surface any *new* gaps so Phase 3 has a
prioritized list.

End state: factory-built UniFi MP installed on devel lab with data
flowing in. Diff against the jcox-au reference (post-render, not
pre-design) should be small; large divergences are substrate gaps.

---

## Design revisions

- **2026-04-30 (v2 round 3 — topology pivot, design closure)** —
  Scott's round-2 design-review gate decisions baked in. Concrete
  changes:
  - **Topology pivot.** `Controller` kind dissolved. `Site` promoted
    to top-level singleton. Controller's summary metrics (health
    subsystems, controller version/build, site identity) move to
    Site; Controller's hardware metrics (CPU, mem, system load,
    uptime) move to Gateway. On a UDM Pro the controller IS the
    gateway — same physical device, no longer represented twice.
    The UDM appears once: as a row in the Gateway list with all its
    hardware metrics. Generalizes cleanly to non-UDM (CloudKey+USG)
    where Site singleton exists with USG as the Gateway entry.
  - **MP display name finalized:** `VCF Content Factory UniFi`
    (round-2 OQ #6 closed; per repo-wide naming-convention update).
  - **Events deferred to v1.1 (round-2 OQ #2 closed).** No MPB
    events in v2. Tier 1 alerting via factory symptoms over
    `stat/anomalies` + `stat/rogueap` (both confirmed working on
    Network App 10.3.55, unlike the legacy `stat/event` which
    404s).
  - **Per-metricSet cadence — defer (round-2 OQ #4 closed).** No
    framework cadence work commissioned for v1. Collection cadence
    stays at adapter default. Revisit Phase 3 if needed.
  - **Icons accepted defaults (round-2 OQ #5 closed):** Site →
    `network-aggregator.svg`, Gateway → `firewall.svg`, Switch →
    `network-switch.svg`, AP → `wireless-access-point.svg`.
  - **Network App version verified (round-2 OQ #8 closed).**
    Controller is now on 10.3.55 (was 10.2.105 on 2026-04-18 —
    upgrade between dates). 2026-04-30 spot-check
    (`context/api-maps/unifi-network-api.md` §"Version verification")
    confirms zero drift in v2's metric paths. Two minor field-shape
    notes:
    - `port_table[].mac` is NOT on classic switch surface and never
      has been (round-2 design wrongly listed it). Removed.
      Wired-client → switch-port joining goes through
      `stat/sta.last_uplink_mac` + `stat/sta.sw_port` per the
      cross-request join table.
    - `radio_table_stats[].last_interference_at` is now conditional
      / optional (was present 2026-04-18, absent 2026-04-30 — only
      emitted on recent interference events). Not in v2
      dependencies; harmless. Recorded as a "conditional field"
      pattern.
  - **OQ #1 (WAN consolidation)** — moot under topology pivot. WAN
    metrics live on Gateway naturally now (UDM is the gateway).
    Closed.
  - **OQ #7 (object name)** — superseded by topology pivot
    ("Controller" no longer exists; "Site" is the singleton).
    Closed.
  - **§"Future Work" expanded** with relationships roadmap (v1.1
    AP→Switch and Switch→Switch via `uplink.uplink_mac`
    field_match; v2 cross-adapter ESXi Host pNIC → UniFi Switch
    port via `stat/sta.sw_mac` + `sw_port`; v2+ per-VM client
    correlation gated on client-cardinality solve; v3 Integration
    API UUID-pointer pivot for topology grammar).
  - **§"Key Risks" augmented** with a low-priority risk on
    Network-App-version field-shape drift; mitigation is
    api-cartographer spot-check every Network App major bump.
  - **No new TOOLSET GAPs** introduced by the topology pivot.
    Site-as-singleton uses the same `is_singleton: true` substrate
    Controller would have. Gaps B + F + D (renderer-side data-shaping
    cluster) remain the priority cluster. mp-author-ready after this
    pass.

- **2026-04-18 (v1, retired)** — briefing-grounded design, predated the
  api-cartographer pass. Object model assumptions (Wireless Client
  Aggregate as separate object_type, all relationships as
  `adapter_instance`) carried over from a different mental model. v1's
  twelve-axis framework-vs-UniFi review is superseded by the smaller §
  framework-vs-UniFi review here.
- **2026-04-30 (v2 auth-path pass)** — incorporated
  `context/api-maps/unifi-integration-api.md` evidence (28 endpoints
  probed authenticated against the live UDM Pro). Decision: **stay on
  classic `cookie_session`. Do NOT pivot to Integration API.** Coverage
  audit shows Integration v1 covers ~23% of v2's ~132 metric/property
  set (~30 of 132), and the covered slice is overwhelmingly inventory
  / properties — 0 throughput, 0 utilization, 0 PoE wattage, 0 system
  load, 0 health subsystems, 0 speedtest, 0 temperature, 0 uptime
  metrics. The Gateway WAN block (20 of 36 Gateway metrics) is
  entirely absent. Pivoting would gut the design. Gap B (two-value
  extract on classic auth) is reframed from "alternate-path tradeoff"
  to "small contained tooling fix". Integration v1 retained as a
  **v3 supplement** — its stable UUIDs (`uplink.deviceId`),
  `provisionedAt` and `configurationId` make it the right surface for
  identity binding, topology, and config-drift detection once the v2
  metric pipeline is shipping. Concrete updates: §"Authentication"
  de-hedged; new §"Auth path decision (2026-04-30)" added; OQ #3
  closed; Gap B severity reframed; §"Open dependencies on tooling
  agent" added; new caveat raised on Network App version-skew
  (10.2.105 vs 10.3.55) requiring re-confirmation before authoring
  metric keys.
- **2026-04-29 (v2, this doc)** — re-derived from
  `context/api-maps/unifi-network-api.md` against post-substrate grammar.
  Concrete deltas from v1:
  - **No `is_world` kind.** v2 follows Synology v2 — adapter instance is
    the implicit topology root; `is_singleton: true` carries
    per-controller metrics. `world_count = 0`.
  - **Wireless Client Aggregate folded onto Site (now Controller
    singleton).** v1 open-question #1 resolved to "fold" — the aggregate
    is `stat/health[?subsystem=='wlan']` data, naturally a few more
    metrics on the singleton, not its own object.
  - **Explicit chain grammar applied** where chains exist
    (`chains_from`/`bind`/`${chain.X}`). v1 talked about chaining but
    didn't specify it.
  - **Auth defaulted to classic cookie_session.** v1 led with
    Integration API. Verdict reversed on three grounds: (a) no API key
    has been generated against the lab; (b) Integration API response
    shapes are uncaptured (api map probed only auth wall); (c)
    classic-session GET-only path is confirmed-working and CSRF is
    confirmed-stable across GETs (no rotation), satisfying MPB's
    session-management ceiling.
  - **Tier-3-grammar `field_match` relationships used** where the API
    provides a peer key (the gateway-MAC ↔ Gateway link). v1 declared
    every relationship `adapter_instance`; v2 keeps adapter_instance for
    the trivial root edges and uses `field_match` only where data
    actually joins.

---

## Scope reductions

Inherited from v1, validated against the api map. Only the entries
that change are called out; unchanged entries remain.

| Scope | v2 | v1.1 | v2 (later) | Why |
|---|---|---|---|---|
| Site (singleton) + AP + Switch + Gateway | **in** | — | — | Core Network App story, all four kinds confirmed live in api map. **Round-3 topology pivot:** `Controller` kind dissolved — its summary metrics moved to Site, hardware metrics moved to Gateway. UDM Pro appears once as a Gateway row, not twice. |
| Wireless Client Aggregate as **separate** object_type | dropped | — | — | Folded onto Site singleton (round-1 OQ #1 resolved). |
| Per-radio metrics on AP via JMESPath filter | **in (with caveat)** | — | — | Api map confirms `radio_table_stats[]` shape; renderer JMESPath filter-predicate support is the gating tooling item — see TOOLSET GAPs. |
| Per-port metrics on Switch (aggregate counts only) | **in (degraded)** | first-class Port | — | Api map confirms `port_table[]` shape but PoE-power coercion (string→number) and null `total_max_power` need renderer compose support. v2 ships only the metrics that don't need compose. First-class Port object deferred. |
| Gateway WAN metrics (top-level `wan1`, `wan2`, `uplink`) | **in** | per-WAN object | — | Api map clarifies that WAN data lives on top-level `wan1`/`wan2` objects, not inside `port_table`. v2 emits as scalar fields on Gateway. |
| Gateway temperatures (`temperatures[]` array) | **in (degraded)** | full per-sensor | — | Api map shows `temperatures[]` is array-of-objects, not flat. v2 ships only CPU temp via JMESPath filter; per-sensor breakouts deferred. |
| Protect cameras | — | **in** | — | Different auth context (`/proxy/protect/`); api map confirms separate API surface and notes WS update stream out of MPB scope. |
| Tier 2 MPB events (notification feed) | — | — | **deferred indefinitely** | Round-3 OQ #2 closed: skip MPB events entirely. Tier 1 alerting via factory symptoms over `stat/anomalies` + `stat/rogueap` (both confirmed working on Network App 10.3.55). Legacy `stat/event` is 404 on 10.x; `rest/event` / `list/event` exist but require uncaptured time-window params. The factory-symptoms path delivers more value per effort. |
| In-pack topology relationships (AP→Switch, Switch→Switch via `uplink.uplink_mac` field_match) | — | **in** | — | Api map confirms join keys exist on `uplink.uplink_mac`. Lab has at least one AP-parented AP (`ap-lower` → `ap-basement`) — relationship must tolerate AP→AP edges, not assume parent is always Switch. Easy adds once relationship grammar lands. Defer to v1.1. |
| Cross-adapter relationship: ESXi Host pNIC → UniFi Switch port | — | — | **v2 candidate** | Wired-host-to-switch-port join via `stat/sta.last_uplink_mac` + `stat/sta.sw_port` MAC-match. Doable, useful for "which switch is this host on" troubleshooting. Defer to v2. |
| Site Manager API (multi-site/MSP) | — | — | **in (v3+)** | Api map confirms 1 site on this controller; multi-site case unverified. v3 introduces a Site list child once MSP shape is mapped. |
| Per-client objects (per-MAC) | — | — | **in (v2+, gated)** | Api map confirms 128 clients on this lab (~200 KB); per-VM client correlation is gated on solving client object cardinality (unbounded guest WiFi/IoT MACs). |
| Config drift (`rest/networkconf`, `rest/wlanconf`, `rest/firewallrule`) | — | — | **in (v3)** | Api map cached but not modeled. v3 surface, likely on Integration v1 (clean `provisionedAt` + `configurationId`). |
| Topology grammar pivot to Integration v1 (UUID pointers) | — | — | **v3** | Once we're already on Integration for config drift / identity, pivot the topology grammar to `uplink.deviceId` UUID pointers instead of MAC matches. |

Tier 1 threshold alerting (AP down, switch port error rate, WAN status,
gateway temp thresholds) is **not deferred** — ships alongside the MP via
`vcfops_symptoms` / `vcfops_alerts`. Same doctrine as Synology.

---

## Interview Answers

Scott answered most v1 open questions in his Phase-1.5 briefing. Carrying
those forward, with the four still-open noted at end:

| Question | Answer | Source |
|---|---|---|
| Monitoring scope | Site (singleton) + AP + Switch + Gateway. | api map §"Object model candidates"; round-3 topology pivot. |
| Object granularity | AP/Switch/Gateway are first-class peer-level lists; Site is the singleton anchor. Per-port and per-radio are nested-within-device metrics in v2 via JMESPath filter predicates; first-class Port/Radio objects only if v1.1 demand appears. UDM Pro is a single row in the Gateway list (not represented twice). | round-3 topology pivot; api map. |
| Relationship topology | Two-level shallow tree. Implicit adapter-instance parentage for AP/Switch/Gateway/Site. Zero explicit relationships in v2. v1.1 adds AP→Switch + Switch→Switch via `uplink.uplink_mac` field_match (in-pack topology). | api map; mp_relationships.md mechanism #1. |
| Cross-adapter relationships | None in v2. v2 candidate: ESXi Host pNIC → UniFi Switch port via wired-client MAC join. v2+: per-VM client correlation gated on cardinality solve. v3: Integration API UUID pivot. | round-3 future-work roadmap. |
| Events | **Closed round 3.** Tier 1 → factory symptoms over `stat/anomalies` + `stat/rogueap` (both confirmed working on 10.3.55). Tier 2 MPB events deferred indefinitely; the factory-symptoms path is faster, lower-risk, and more value per effort. | round-3 OQ #2; api map endpoint #7. |
| Bundled content | None in .pak. Dashboards ship separately via factory bundles, same as Synology v2. | Synology v2 precedent. |
| Collection intervals | **Closed round 3** — adapter default cadence; no per-metricSet cadence grammar commissioned for v1. Revisit Phase 3 if needed. | round-3 OQ #4. |
| Controller version assumption | **Verified round 3** — UniFi OS 5.0.16 / Network Application 10.3.55 on 2026-04-30 (was 10.2.105 on 2026-04-18; controller upgraded between dates). Zero drift in v2's metric paths. Network App ≥ 9.3.43 → Integration API is *available* but rejected as v1 path on coverage grounds. | api map §"Version verification — 2026-04-30 spot-check". |
| Lab target | `unifi.int.sentania.net` (UDM Pro). Base path `/proxy/network/api/s/default/` for site-scoped reads. | api map §url layout. |
| Auth method | **Classic cookie_session** as v2 default. Integration API rejected as v1 primary on coverage grounds; retained as v3 supplement. | See §Authentication. |
| Icons (round-3) | Site → `network-aggregator.svg`; Gateway → `firewall.svg`; Switch → `network-switch.svg`; AP → `wireless-access-point.svg`. | round-3 OQ #5. |
| MP display name (round-3) | `VCF Content Factory UniFi` (per CLAUDE.md hard rule #5). | round-3 OQ #6; CLAUDE.md naming convention. |

**All open questions closed at the round-3 design-review gate (2026-04-30).**
See §"Open questions for Scott" — every entry is closed with the
resolution noted.

---

## Object Model

### Object tree

```
Adapter Instance (implicit, MPB-managed; carries every kind below)
│
├── UniFi Site   (is_singleton: true — per-adapter-instance anchor)
│   └── 3 metricSets: site_meta (scalar from self/sites[0]),
│                     site_sysinfo (scalar from stat/sysinfo — controller
│                       version/build/retention; site-logical because the
│                       adapter targets one site),
│                     site_health (scalar w/ 5 JMESPath subsystem extracts)
│       Carries: site identity + Network App version metadata + per-
│       subsystem health aggregates (wlan/wan/www/lan/vpn) + wireless-
│       client-aggregate counts (folded from v1).
│
└── [peer device graph, parented implicitly by adapter instance]
    ├── Access Point  (list, from stat/device[?type=='uap'])
    │     metricSets: dev_inventory (primary, list)
    │     ~12 device-level metrics + per-radio metrics via JMESPath filter
    │
    ├── Switch        (list, from stat/device[?type=='usw'])
    │     metricSets: dev_inventory (primary, list)
    │     ~12 device-level metrics + per-port aggregates via JMESPath filter
    │
    └── Gateway       (list, from stat/device[?type=='udm' || type=='ugw'])
          metricSets: dev_inventory (primary, list)
          ~10 device-level + WAN top-level + temperatures[?name=='CPU']
          On a UDM Pro the controller IS the gateway — UDM appears once
          here as a Gateway row, not separately as a Controller object.
          UDM hardware metrics (CPU, mem, uptime) live on this row.
```

Four object_types total. `world_count = 0` (no `is_world: true` kind).

### Topology pivot rationale (round-3, 2026-04-30)

Round-2 modeled `Controller` as a singleton AND `Gateway` as a list. On
a UDM Pro (and any UniFi all-in-one box) the controller IS the gateway
— same physical device represented twice. Round 3 collapses that:

- **Promote Site to top-level singleton.** UniFi scopes everything by
  site (`/api/s/{site}/*`); the "controller-level" health subsystems
  (wlan/wan/lan/vpn/www) are really *site-level* metrics. UniFi's own
  UI uses Site as the management context — this matches that mental
  model.
- **Dissolve the Controller kind.** Its summary metrics move to Site;
  its hardware metrics (CPU, system load, uptime) move to Gateway.
  The UDM appears **once** as a row in the Gateway list.
- **Generalizes cleanly to non-UDM** — a CloudKey + USG split still
  has one Site singleton + a Gateway entry (USG). The CloudKey
  doesn't show up because it's not an adopted UniFi device (it's the
  controller appliance, not a managed device). The model is
  topologically the same regardless of whether controller-and-gateway
  are one box or two.

### Why no `is_world`

Same reasoning as Synology v2 (`context/mpb_synology_pickup_2026_04_29.md`
§"Architecture decision"):

- `is_world: true` is for cross-instance anchors with no identifiers and
  no metricSets. UniFi has no cross-instance roll-up requirement in v2.
- The Site singleton carries per-site identity (`name` / `_id` from
  `self/sites`) and per-site metrics (health aggregates +
  Network-App-version metadata). That's `is_singleton: true` shape.
- v3 may add `UniFi World` (`is_world: true`) if fleet-level aggregation
  supermetrics are authored, or to anchor MSP multi-site rollups. Cheap
  to add later.

### Identifiers and name expressions per kind

| Object | Identifier(s) | name_expression | Source |
|---|---|---|---|
| UniFi Site | `site_name` from `self/sites[0].name` (URL-path identifier; literal `"default"` on this lab); secondary `site_id` from `self/sites[0]._id` (Mongo object id, stable across renames) | `site_desc` (from `self/sites[0].desc`, e.g. `"Default"`; falls back to `site_name` if blank) | api map endpoint #2 |
| Access Point | `mac` from `stat_device.mac` | `name` (admin-set; api map confirms field exists, may be blank — v1.1 may need composite `${name} (${model})` once renderer supports multi-part) | api map endpoint #4, common device fields |
| Switch | `mac` | `name` | api map endpoint #4 |
| Gateway | `mac` | `name` | api map endpoint #4 |

`mac` is empirically stable across adoption cycles for UniFi devices —
the api map confirms every device returns it. Lower-tier identity
choices (`_id` Mongo IDs) would also work but are surface-area-internal;
`mac` is the natural identity humans recognize.

For Site, `name` is the URL-path identifier (literally `"default"` on
single-site deployments); `_id` is the Mongo object id (stable across
display-name renames). Using `name` as primary identifier matches how
the API addresses the site; `_id` becomes a secondary identifier for
durability across renames in MSP scenarios.

### Relationships

```
relationships:
  # Trivial root edges — implicit adapter_instance parentage already
  # provides each child a path to the inventory root. No explicit
  # relationships needed for AP/Switch/Gateway → Site (they all
  # parent the adapter instance implicitly).
  # See mp_relationships.md mechanism #1.
```

Final relationship count: **0 explicit relationships in v2.**

v1.1 adds two explicit field_match relationships for in-pack topology:

```
v1.1:
  - parent: switch
    child: access_point
    scope: field_match
    parent_expression: mac
    child_expression: uplink.uplink_mac

  - parent: switch        # AP-uplink-on-switch only resolves when
    child: switch         # the join lands on a Switch row; AP→AP
    scope: field_match    # mesh edges are accepted by the same
    parent_expression: mac # join (the lab has at least one AP-
    child_expression: uplink.uplink_mac # parented AP — `ap-lower`).
```

(Both AP→Switch and Switch→Switch use the same `uplink.uplink_mac` →
parent `mac` join. AP-parented APs collapse into the same edge shape;
no separate AP→AP relationship needed.)

### Singleton vs list shape per kind

| Object | Shape | Renders as | Why |
|---|---|---|---|
| UniFi Site | `is_singleton: true` | `isListObject: false`; 3 metricSets in scalar context (`list_path: ""` for sysinfo and health; `list_path` consuming first row of `self/sites` for site_meta — see TOOLSET QUESTION C) | One per adapter instance. Synology Diskstation precedent — singleton with multiple parallel non-chained metricSets. |
| Access Point | list | `isListObject: true`; one primary metricSet from `stat/device` filtered to `type=='uap'` | N APs per site. |
| Switch | list | `isListObject: true`; one primary metricSet from `stat/device` filtered to `type=='usw'` | N switches per site. |
| Gateway | list | `isListObject: true`; one primary metricSet from `stat/device` filtered to `type=='udm' \|\| type=='ugw'` | Typically 0-1 per site (one combined gateway/controller on UDM, or one USG on CloudKey-split deployments). |

**No chained metricSets in v2.** This is an important calibration result
— see §"Chaining grammar application" for the analysis.

---

## Authentication

**MP display name:** `VCF Content Factory UniFi`
(per CLAUDE.md hard rule #5 — MPs use prose-form `VCF Content Factory
<name>`; brackets are reserved for content authored *for* VCF Ops, not
MPs that *extend* it.)

**v2 auth surface: classic `cookie_session` preset. Final.**
Integration API v1 was evaluated as an alternative on 2026-04-30 and
**rejected as v1 primary** — see §"Auth path decision (2026-04-30)"
below for the coverage-audit evidence. Integration is retained as a
**v3 supplement** for identity, topology, and config-drift surfaces;
it is not the v1 metric-collection path under any circumstance.

### Classic cookie_session — the v1 auth surface

| Factor | Classic `cookie_session` |
|---|---|
| Confirmed working live | Yes — api map endpoint #1-7 all session-authed |
| Response shapes captured | Yes — full per-endpoint shape |
| MPB CSRF rotation handling | CSRF does NOT rotate on GETs (api map §auth-flow); single token captured at login is sufficient |
| Available on lab controller | Yes |
| Available on older controllers | Yes (universal — predates the 9.3.43 Integration v1 cutover) |
| Read-only safety | Confirmed (api map §auth-flow) |
| Coverage of v2 metric set | ~100% (every v2 metric maps to a classic endpoint field) |

**Why not Integration v1:** Integration is a clean, officially-supported,
inventory-shaped API — but inventory only. Per the 2026-04-30 audit
(`context/api-maps/unifi-integration-api.md` §"Coverage comparison vs
classic"), Integration v1 covers ~23% of v2's planned metric set,
overwhelmingly properties / inventory. **0 throughput, 0 utilization,
0 PoE wattage, 0 system load, 0 health-subsystem aggregates, 0
speedtest, 0 temperatures, 0 uptime counters, and the entire Gateway
WAN block (20 of 36 Gateway metrics) is absent.** A pivot would not
relocate Gap B; it would gut the design. Gap B is the right tooling
spend.

### Auth YAML shape

```yaml
source:
  port: 443
  ssl: NO_VERIFY              # lab uses self-signed cert
  base_path: "proxy/network/api/s/default"   # site-scoped classic surface
  timeout: 30
  max_retries: 2
  max_concurrent: 10

  auth:
    preset: cookie_session
    credentials:
      - {key: username, label: username, sensitive: false}
      - {key: password, label: password, sensitive: true}
    login:
      method: POST
      path: "../../../../api/auth/login"   # /api/auth/login is at /api root, NOT under /proxy/network/api/s/default
      # NOTE: relative-path "../" depth depends on base_path. If the loader/renderer
      # rejects the "../" form, declare the login path as an absolute /api/auth/login
      # — this is a MINOR TOOLSET CHECK before mp-author runs (see §risks).
      body: '{"username": "${credentials.username}", "password": "${credentials.password}", "rememberMe": false}'
      # TOOLSET GAP A — login.body needs to set Content-Type: application/json.
      # See open Synology gap "getSession.headers" in mpb_synology_pickup §7.
      # Likely runtime-injected by adapter, but flagged for parity.
    extract:
      # Two values must come back from the login response:
      #   1. TOKEN cookie  → the session cookie
      #   2. x-csrf-token  → CSRF header for every subsequent request
      # The api map says GETs do NOT rotate CSRF, so a single capture at login is fine.
      # The current `extract:` grammar binds ONE value per extract block — this is a
      # TWO-VALUE-EXTRACT TOOLSET GAP B, see §risks.
      location: HEADER
      name: "Set-Cookie"
      bind_to: session.token_cookie
    inject:
      # Cookie auto-handled by the HTTP stack from the session.token_cookie
      # binding (in MPB's session model, the cookie sticks to the session).
      # CSRF needs an explicit inject:
      - type: header
        name: "x-csrf-token"
        value: "${session.csrf_token}"   # depends on TOOLSET GAP B resolution
    logout:
      method: POST
      path: "../../../../api/auth/logout"

  test_request:
    method: GET
    path: "stat/sysinfo"
    # Returns 200 + {meta:{rc:"ok"}} when authed; predictable health probe.
```

### Auth-related TOOLSET GAPs (see §risks for full list)

- **Gap A:** `login.body` needs Content-Type. Same gap Synology surfaced
  at `getSession.headers`. Workaround: rely on adapter runtime injecting
  Content-Type for JSON bodies (Synology lab observed this works).
  Lower priority — likely runtime-injected.
- **Gap B (small contained tooling fix):** `extract:` block binds one
  value at a time, but UniFi classic session needs TWO captures
  (`Set-Cookie` header AND `x-csrf-token` header) from the same login
  response. The fix is a **list-of-extracts grammar on the existing
  `extract:` block** — a contained loader/renderer change with no new
  protocol surface, no new auth path, no new wire format. **Blocking
  for cookie_session, which is the v1 auth surface. There is no
  fallback** — Integration API was evaluated and rejected on coverage
  grounds (see §"Auth path decision (2026-04-30)"). Tooling agent
  brief inherits this framing: contained fix, blocking, not
  alternate-path.

---

## Auth path decision (2026-04-30)

At the v2 design-review gate, the orchestrator asked whether v2 should
pivot from classic `cookie_session` (Gap B blocking) to UniFi's
Integration API (`X-API-Key` bearer — sidesteps Gap B entirely). The
Integration v1 surface was probed authenticated against the live UDM
Pro; results live in `context/api-maps/unifi-integration-api.md`.

### Decision

**Stay on classic `cookie_session`. Pin Gap B to tooling.**

### Evidence

From `context/api-maps/unifi-integration-api.md` §"Coverage comparison
vs classic":

| Object | v2 planned | Integration covered | % | Headline gap |
|---|---|---|---|---|
| Controller | ~46 | ~5 | 11% | All health-subsystem metrics; speedtest; uptime; data retention |
| Access Point | ~32 | ~9 | 28% | All per-radio counters; CPU/mem; uptime; satisfaction; client counts |
| Switch | ~18 | ~9 | 50% | All chassis temp/fan; PoE wattage; per-port counters |
| Gateway | ~36 | ~7 | 19% | All WAN1/WAN2 metrics; speedtest; temperatures |
| **Total** | **~132** | **~30** | **~23%** | |

Of the ~30 covered, ~22 are properties / inventory (most are renamed
camelCase or transformed enum-vs-int vs classic). ~8 are derivable
metrics (counts, channel-per-radio). **0 are throughput / utilization /
per-radio-occupancy / system load / health-subsystem metrics.** The
entire Gateway WAN block (20 of 36 Gateway metrics) is absent —
Integration v1 has no `/health`, no `/statistics`, no `/devices/{id}/wan`,
no speedtest, no temperatures.

Per the api map's §"Recommendation":

> Integration v1 is genuinely an inventory API, not a metrics API. The
> intended consumer is integration partners building topology / config
> / orchestration tooling against a stable, officially-supported
> schema — not monitoring tooling that needs second-by-second
> counters.

### Cost-of-work asymmetry

- **Gap B** (two-value `extract:` on classic auth) — small, contained
  loader/renderer change. No new protocol surface, no new wire
  format, no new endpoints to map.
- **Pivot to Integration v1** — requires re-deriving ~80% of the v2
  metric set against a surface that doesn't expose those metrics.
  Result is a 23%-coverage MP, not a 100%-coverage MP with a
  contained tooling fix.

The Gap-B-vs-pivot comparison is not "two paths of similar effort,
weigh tradeoffs". It's "small fix vs catastrophic coverage cliff".

### Gap F is unaffected

Gap F (renderer needs JMESPath filter predicates inside metric source
paths to consume `stat/health[?subsystem=='X']`) was a candidate to
sidestep IF Integration v1 split each subsystem to its own endpoint.
It does not — Integration v1 has no `/health` surface at all. Per the
api map's §"Gap F revisit": "Gap F remains a renderer-side concern,
but the question of 'can Integration shape the wire to avoid it?' is
moot — there is no wire to reshape." Gap F belongs in the same
tooling round as Gap B regardless of auth path.

### Future role for Integration v1 (v3)

Integration v1 is the **right surface for a v3 supplement**. Per the
api map's §"Recommendation" item 4 and §"Future v3 use cases":

- **Identity binding** — clean stable UUIDs (`uplink.deviceId`)
  independent of MAC, which can change on hardware swap. Replaces
  classic's MAC-based join keys with UUID joins.
- **Topology** — `uplink.deviceId` is a much cleaner parent pointer
  than classic's `uplink_mac`-requiring-a-join-on-`mac` pattern.
- **Config drift** — `provisionedAt` (last config push timestamp) and
  `configurationId` (opaque config snapshot id) are first-class on
  Integration's per-device detail endpoint. Classic exposes neither
  cleanly.
- **Inventory layer** — paginated, officially-supported `/sites`,
  `/devices`, `/clients`, `/networks` endpoints with stable
  pagination envelopes. The natural source for site/network
  enumeration in v3.

These uses get scoped into v3 once the v2 metric pipeline ships.
Integration v2 (when released — `/v2/*` endpoints all 404 on Network
App 10.3.55 today, suggesting reserved future expansion slot) should
trigger a re-cartography pass at that time; the coverage delta vs
classic is the same audit performed today.

### What this closes

- **OQ #3 (v1 carry-forward)** — "Integration API pivot if Gap B is
  too big a tooling lift?" — **answered NO.** Gap B is the smaller
  spend; pivoting trades a contained fix for a 77% coverage cliff.

### Caveat raised by the evidence

**Network App version skew.** Classic `stat/sysinfo.version` reported
`10.2.105` on 2026-04-18. Integration `/info.applicationVersion`
reported `10.3.55` on 2026-04-30. Most likely interpretation: the
controller was upgraded between the two recons. **Action item before
mp-author runs metric-key authoring**: re-pull classic `stat/sysinfo`
on the lab to confirm current version. UniFi has historically renamed
or removed fields across Network App version bumps; v2's drift-fix
assumptions in the metric source paths were grounded against
10.2.105. If the controller is now on 10.3.55 (or higher), spot-check
that `system-stats.cpu`, `radio_table_stats[].cu_total`,
`temperatures[?name=='CPU']`, and `wan1.tx_bytes-r` still resolve
before authoring. See §"Open questions for Scott" #8.

---

## Metrics by Object Type

Every metric below is grounded in a specific endpoint and field path
from `context/api-maps/unifi-network-api.md`. Field-name corrections from
v1 (api map drift findings) are applied. Round-3 topology pivot has
re-bucketed metrics: hardware-specific fields that were previously on
Controller (CPU, mem, system load, hardware uptime, hardware identity)
now live on Gateway; site identity / Network App version metadata /
health subsystem aggregates live on Site. `usage` column: M = METRIC,
P = PROPERTY.

### UniFi Site (`is_singleton: true`)

Source endpoints: `self/sites` (identity), `stat/sysinfo` (controller-
software metadata — site-logical because the adapter targets one site),
`stat/health` (5 subsystems via JMESPath filter — site-level
aggregates).

#### From `self/sites` (metricSet `site_meta`)

Sites endpoint returns a list — but for a single-site deployment, the
Site singleton consumes the first (and only) row. **TOOLSET QUESTION
C**: a singleton metricSet consuming the first element of a list
response — does the renderer support `list_path: "."` or similar to
bind the single-element list to scalar context? If not, fall back to
`stat/sysinfo.hostname` for site identity (which doubles as site name
on this lab — `"udm"`) and defer the descriptor metadata. See §risks.

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `site_name` | Site Name | P | STRING | `metricset:site_meta[0].name` | endpoint #2 (URL-path identifier, `"default"` on this lab) |
| `site_id` | Site ID | P | STRING | `metricset:site_meta[0]._id` | endpoint #2 (Mongo object id; stable across display-name renames) |
| `site_desc` | Site Description | P | STRING | `metricset:site_meta[0].desc` | endpoint #2 (display name; `"Default"` on this lab) |
| `site_role` | Site Role | P | STRING | `metricset:site_meta[0].role` | endpoint #2 |
| `device_count` | Devices | M | NUMBER | `metricset:site_meta[0].device_count` | endpoint #2 |

#### From `stat/sysinfo` (metricSet `site_sysinfo`)

Controller-software metadata. On a UDM Pro the controller runs on the
gateway box, but the adapter targets one site — these fields describe
the controller serving this site, not the underlying hardware.
Hardware-specific sysinfo fields (`hostname`, `uptime`,
`console_display_version`, `udm_version`, `ubnt_device_type`) moved to
Gateway in the round-3 topology pivot.

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `controller_id` | Controller ID | P | STRING | `metricset:site_sysinfo.anonymous_controller_id` | endpoint #1 |
| `network_app_version` | Network App Version | P | STRING | `metricset:site_sysinfo.version` | endpoint #1 (10.3.55 on lab as of 2026-04-30) |
| `network_app_build` | Network App Build | P | STRING | `metricset:site_sysinfo.build` | endpoint #1 |
| `previous_network_app_version` | Previous Network App Version | P | STRING | `metricset:site_sysinfo.previous_version` | endpoint #1 (10.2.105 on lab; useful for upgrade-detection) |
| `timezone` | Timezone | P | STRING | `metricset:site_sysinfo.timezone` | endpoint #1 |
| `is_cloud_console` | Cloud Console | P | STRING | `metricset:site_sysinfo.is_cloud_console` | endpoint #1 |
| `update_available` | Update Available | P | STRING | `metricset:site_sysinfo.update_available` | endpoint #1 |
| `data_retention_days` | Data Retention (days) | P | NUMBER | `metricset:site_sysinfo.data_retention_days` | endpoint #1 |

#### From `stat/health` (metricSet `site_health`, with JMESPath subsystem extraction)

Each row is one of `wlan` / `wan` / `www` / `lan` / `vpn`. Schema is
heterogeneous per row. The renderer needs JMESPath filter-predicate
support (`[?subsystem=='X']`) — flagged in api map §renderer-gap-finding-1
and listed in §risks.

WAN subsystem (`stat/health[?subsystem=='wan']`):

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `wan_status` | WAN Status | P | STRING | filter `[?subsystem=='wan'].status` | endpoint #3 |
| `wan_clients` | WAN Connected Clients | M | NUMBER | filter `[?subsystem=='wan'].num_sta` | endpoint #3 |
| `wan_tx_bytes_rate` | WAN TX Bytes/s | M | NUMBER | filter `[?subsystem=='wan'].tx_bytes-r` (HYPHEN, not underscore — api map drift fix) | endpoint #3 |
| `wan_rx_bytes_rate` | WAN RX Bytes/s | M | NUMBER | filter `[?subsystem=='wan'].rx_bytes-r` | endpoint #3 |
| `wan_gateway_mac` | WAN Gateway MAC | P | STRING | filter `[?subsystem=='wan'].gw_mac` | endpoint #3 (could be the `field_match` parent_expression for moving WAN metrics to Gateway in v1.1) |
| `wan_isp_name` | WAN ISP | P | STRING | filter `[?subsystem=='wan'].isp_name` | endpoint #3 |

WWW subsystem (`stat/health[?subsystem=='www']`):

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `internet_latency_ms` | Internet Latency (ms) | M | NUMBER | filter `[?subsystem=='www'].latency` | endpoint #3 |
| `internet_uptime_seconds` | Internet Path Uptime (s) | M | NUMBER | filter `[?subsystem=='www'].uptime` | endpoint #3 |
| `internet_drops` | Internet Drops | M | NUMBER | filter `[?subsystem=='www'].drops` | endpoint #3 |
| `internet_xput_up` | Internet Speedtest Up | M | NUMBER | filter `[?subsystem=='www'].xput_up` | endpoint #3 |
| `internet_xput_down` | Internet Speedtest Down | M | NUMBER | filter `[?subsystem=='www'].xput_down` | endpoint #3 |
| `speedtest_status` | Speedtest Status | P | STRING | filter `[?subsystem=='www'].speedtest_status` | endpoint #3 |
| `speedtest_ping_ms` | Speedtest Ping (ms) | M | NUMBER | filter `[?subsystem=='www'].speedtest_ping` | endpoint #3 |

WLAN subsystem (`stat/health[?subsystem=='wlan']`) — folded from v1's
Wireless Client Aggregate:

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `wlan_status` | WLAN Status | P | STRING | filter `[?subsystem=='wlan'].status` | endpoint #3 |
| `wlan_user_count` | Wireless Users | M | NUMBER | filter `[?subsystem=='wlan'].num_user` | endpoint #3 |
| `wlan_guest_count` | Guest Users | M | NUMBER | filter `[?subsystem=='wlan'].num_guest` | endpoint #3 |
| `wlan_iot_count` | IoT Users | M | NUMBER | filter `[?subsystem=='wlan'].num_iot` | endpoint #3 |
| `wlan_ap_count` | APs | M | NUMBER | filter `[?subsystem=='wlan'].num_ap` | endpoint #3 |
| `wlan_ap_disconnected` | APs Disconnected | M | NUMBER | filter `[?subsystem=='wlan'].num_disconnected` | endpoint #3 |
| `wlan_tx_bytes_rate` | WLAN TX Bytes/s | M | NUMBER | filter `[?subsystem=='wlan'].tx_bytes-r` | endpoint #3 |
| `wlan_rx_bytes_rate` | WLAN RX Bytes/s | M | NUMBER | filter `[?subsystem=='wlan'].rx_bytes-r` | endpoint #3 |

LAN subsystem (`stat/health[?subsystem=='lan']`):

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `lan_status` | LAN Status | P | STRING | filter `[?subsystem=='lan'].status` | endpoint #3 |
| `lan_user_count` | LAN Wired Users | M | NUMBER | filter `[?subsystem=='lan'].num_user` | endpoint #3 |
| `lan_switch_count` | Switches | M | NUMBER | filter `[?subsystem=='lan'].num_sw` | endpoint #3 |
| `lan_switch_disconnected` | Switches Disconnected | M | NUMBER | filter `[?subsystem=='lan'].num_disconnected` | endpoint #3 |
| `lan_tx_bytes_rate` | LAN TX Bytes/s | M | NUMBER | filter `[?subsystem=='lan'].tx_bytes-r` | endpoint #3 |
| `lan_rx_bytes_rate` | LAN RX Bytes/s | M | NUMBER | filter `[?subsystem=='lan'].rx_bytes-r` | endpoint #3 |

VPN subsystem (`stat/health[?subsystem=='vpn']`):

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `vpn_remote_users_active` | VPN Active Users | M | NUMBER | filter `[?subsystem=='vpn'].remote_user_num_active` | endpoint #3 |
| `vpn_tx_bytes` | VPN TX Bytes | M | NUMBER | filter `[?subsystem=='vpn'].remote_user_tx_bytes` | endpoint #3 |
| `vpn_rx_bytes` | VPN RX Bytes | M | NUMBER | filter `[?subsystem=='vpn'].remote_user_rx_bytes` | endpoint #3 |

**Site metric count: ~43** (5 from site_meta, 8 from site_sysinfo, 30
from health subsystems — 6 wan + 7 www + 8 wlan + 6 lan + 3 vpn).
Wireless Client Aggregate is folded in (no separate object). Hardware-
specific metadata that the round-2 design parked on Controller
(hostname, hardware uptime, UniFi OS version, UDM firmware version,
device type) moved to Gateway under the round-3 topology pivot. Per-
device hardware uptime is now `Gateway.uptime_seconds`, not a separate
controller metric.

### Access Point (list, `is_singleton: false`)

Source: `stat/device` (one shared request) filtered by `type=='uap'`.

`stat/device` is heavy (~385 KB for 15 devices on this lab). The request
fires once per cycle; AP/Switch/Gateway each consume the same response
through their respective primary metricSets, just with different
`list_path` filters. **Important**: this means the renderer must support
THREE list objects sharing a single request — see §"Request Mapping" and
§risks.

#### Device-level metrics

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `mac` | MAC | P | STRING | `metricset:dev_inventory.mac` | endpoint #4 |
| `name` | Name | P | STRING | `metricset:dev_inventory.name` | endpoint #4 |
| `model` | Model | P | STRING | `metricset:dev_inventory.model` | endpoint #4 (e.g. U7PG2, U7IW) |
| `model_in_lts` | Model In LTS | P | STRING | `metricset:dev_inventory.model_in_lts` | endpoint #4 |
| `firmware_version` | Firmware Version | P | STRING | `metricset:dev_inventory.version` | endpoint #4 |
| `upgradable` | Upgrade Available | P | STRING | `metricset:dev_inventory.upgradable` | endpoint #4 |
| `adopted` | Adopted | P | STRING | `metricset:dev_inventory.adopted` | endpoint #4 |
| `ip` | IP Address | P | STRING | `metricset:dev_inventory.ip` | endpoint #4 |
| `serial` | Serial | P | STRING | `metricset:dev_inventory.serial` | endpoint #4 |
| `country_code` | Country Code | P | STRING | `metricset:dev_inventory.country_code` | endpoint #4 |
| `state` | State (1=connected) | M | NUMBER | `metricset:dev_inventory.state` | endpoint #4 |
| `uptime_seconds` | Uptime (s) | M | NUMBER | `metricset:dev_inventory._uptime` (underscore variant; api map confirms identical to `uptime`) | endpoint #4 |
| `last_seen_epoch` | Last Seen (epoch s) | M | NUMBER | `metricset:dev_inventory.last_seen` | endpoint #4 |
| `cpu_pct` | CPU % | M | NUMBER | `metricset:dev_inventory.system-stats.cpu` (string-or-number; **TOOLSET COERCION D**) | endpoint #4 |
| `mem_pct` | Memory % | M | NUMBER | `metricset:dev_inventory.system-stats.mem` (string-or-number; same coercion gap) | endpoint #4 |
| `client_count` | Connected Clients | M | NUMBER | `metricset:dev_inventory.num_sta` | endpoint #4 |
| `user_client_count` | User Clients | M | NUMBER | `metricset:dev_inventory.user-num_sta` | endpoint #4 |
| `guest_client_count` | Guest Clients | M | NUMBER | `metricset:dev_inventory.guest-num_sta` | endpoint #4 |
| `satisfaction` | Satisfaction | M | NUMBER | `metricset:dev_inventory.satisfaction` | endpoint #4 (-1 = no data) |
| `uplink_mac` | Uplink Device MAC | P | STRING | `metricset:dev_inventory.uplink.uplink_mac` | endpoint #4 (v1.1 topology join key) |

#### Per-radio metrics (JMESPath filter-predicate-required)

For 2.4 GHz (`radio=='ng'`) and 5 GHz (`radio=='na'`). 6 GHz (`radio=='ax'`
or `'6e'`) absent on lab hardware but the JMESPath shape generalizes.

These metrics use JMESPath filter predicates inside `radio_table_stats[]`
to extract per-radio scalar metrics. Renderer support is the gating
tooling item (§risks).

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `radio_24ghz_clients` | 2.4 GHz Clients | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='ng'].user-num_sta \| [0]` | api map drift fix table |
| `radio_24ghz_tx_power` | 2.4 GHz TX Power | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='ng'].tx_power \| [0]` | drift fix |
| `radio_24ghz_satisfaction` | 2.4 GHz Satisfaction | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='ng'].satisfaction \| [0]` | drift fix |
| `radio_24ghz_channel` | 2.4 GHz Channel | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='ng'].channel \| [0]` | drift fix |
| `radio_24ghz_cu_total` | 2.4 GHz Channel Util % | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='ng'].cu_total \| [0]` | drift fix |
| `radio_24ghz_tx_retries_pct` | 2.4 GHz TX Retries % | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='ng'].tx_retries_pct \| [0]` | drift fix |
| `radio_5ghz_clients` | 5 GHz Clients | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='na'].user-num_sta \| [0]` | drift fix |
| `radio_5ghz_tx_power` | 5 GHz TX Power | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='na'].tx_power \| [0]` | drift fix |
| `radio_5ghz_satisfaction` | 5 GHz Satisfaction | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='na'].satisfaction \| [0]` | drift fix |
| `radio_5ghz_channel` | 5 GHz Channel | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='na'].channel \| [0]` | drift fix |
| `radio_5ghz_cu_total` | 5 GHz Channel Util % | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='na'].cu_total \| [0]` | drift fix |
| `radio_5ghz_tx_retries_pct` | 5 GHz TX Retries % | M | NUMBER | `metricset:dev_inventory.radio_table_stats[?radio=='na'].tx_retries_pct \| [0]` | drift fix |

**AP metric count: ~32**.

**Round-3 note on conditional fields.**
`radio_table_stats[].last_interference_at` is now classified as a
conditional/optional field — it was present on 2026-04-18 but absent
on 2026-04-30 (0/12 radio rows carried it across all 6 APs). Same
pattern as `upgrade_to_firmware`: only emitted when the condition
holds (recent interference event). v2 does not depend on this field
(not listed above), so harmless. Pattern recorded for future
authoring discipline: prefer fields confirmed present across multiple
spot-checks; treat condition-only fields as optional.

### Switch (list, `is_singleton: false`)

Source: `stat/device` filtered by `type=='usw'`.

#### Device-level metrics

Same common device set as AP (`mac`, `name`, `model`, `model_in_lts`,
`version` → `firmware_version`, `adopted`, `ip`, `state`, `_uptime`,
`last_seen`, `system-stats.cpu`, `system-stats.mem`, `serial`,
`uplink.uplink_mac`) — list duplicated for clarity:

| key | label | usage | type | source path |
|---|---|---|---|---|
| `mac` | MAC | P | STRING | `metricset:dev_inventory.mac` |
| `name` | Name | P | STRING | `metricset:dev_inventory.name` |
| `model` | Model | P | STRING | `metricset:dev_inventory.model` |
| `model_in_lts` | Model In LTS | P | STRING | `metricset:dev_inventory.model_in_lts` |
| `firmware_version` | Firmware Version | P | STRING | `metricset:dev_inventory.version` |
| `serial` | Serial | P | STRING | `metricset:dev_inventory.serial` |
| `ip` | IP Address | P | STRING | `metricset:dev_inventory.ip` |
| `state` | State | M | NUMBER | `metricset:dev_inventory.state` |
| `uptime_seconds` | Uptime (s) | M | NUMBER | `metricset:dev_inventory._uptime` |
| `last_seen_epoch` | Last Seen | M | NUMBER | `metricset:dev_inventory.last_seen` |
| `cpu_pct` | CPU % | M | NUMBER | `metricset:dev_inventory.system-stats.cpu` (coercion D) |
| `mem_pct` | Memory % | M | NUMBER | `metricset:dev_inventory.system-stats.mem` (coercion D) |
| `client_count` | Clients | M | NUMBER | `metricset:dev_inventory.num_sta` |
| `uplink_mac` | Uplink MAC | P | STRING | `metricset:dev_inventory.uplink.uplink_mac` |
| `overheating` | Overheating | P | STRING | `metricset:dev_inventory.overheating` |

#### Switch-specific (chassis-level)

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `total_max_power_w` | PoE Budget Max (W) | M | NUMBER | `metricset:dev_inventory.total_max_power` (NULLABLE on non-PoE switches — renderer must skip emit when null) | endpoint #4 PoE findings |
| `has_temperature` | Has Temperature Sensor | P | STRING | `metricset:dev_inventory.has_temperature` | endpoint #4 |
| `has_fan` | Has Fan | P | STRING | `metricset:dev_inventory.has_fan` | endpoint #4 |

#### Per-port aggregates

These need either JMESPath aggregates (`length(port_table[?up==true])`)
or renderer-side compose. v2 ships only the ones JMESPath can express
without numeric coercion or compose; PoE-budget-remaining and
sum-of-poe-power are deferred (need TOOLSET work — coercion + null
propagation, see §risks).

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `port_count` | Port Count | M | NUMBER | `metricset:dev_inventory.port_table \| length(@)` | derived; renderer JMESPath-aggregate-required |
| `ports_up_count` | Ports Up | M | NUMBER | `metricset:dev_inventory.port_table[?up==true] \| length(@)` | renderer-required |
| `ports_poe_capable_count` | PoE-Capable Ports | M | NUMBER | `metricset:dev_inventory.port_table[?port_poe==true] \| length(@)` | renderer-required |

**v2 explicitly defers:**
- `poe_power_total_w` — sum-of-string-coerced-poe_power across PoE ports
- `poe_budget_remaining_w` — `total_max_power - sum(poe_power)`
- `port_tx_bytes_total`, `port_rx_bytes_total` — sum aggregates over `port_table[*].tx_bytes`/`rx_bytes`

These belong in v1.1 once tooling lands JMESPath aggregates, type
coercion, and compose with null propagation.

**Switch metric count: ~18** (15 device-level + 3 chassis + 3 port
aggregates), with ~5 deferred to v1.1.

**Round-3 note on `port_table[].mac`.** Round-2 design discussion
listed `port_table[].mac` as a candidate field for wired-client →
switch-port joining. The 2026-04-30 spot-check confirms this field
does NOT exist on the classic switch surface and never has — it was
not in the captured `port_table` union on 2026-04-18 either. Wired-
client → switch-port joining flows through `stat/sta.last_uplink_mac`
+ `stat/sta.sw_port` (per the api map's cross-request join table).
mp-author MUST NOT depend on `port_table[].mac`. The future
cross-adapter ESXi-Host-pNIC → UniFi-Switch-port relationship (v2
roadmap) uses the `stat/sta` MAC join, not `port_table[].mac`.

### Gateway (list, `is_singleton: false`)

Source: `stat/device` filtered by `type=='udm' || type=='ugw'`.

On a UDM Pro the controller IS the gateway (single physical device).
The round-3 topology pivot collapsed the previous Controller singleton
into Site (for site-logical metadata) and Gateway (for hardware
metadata). UDM hardware identity / uptime / system load now live here
on the Gateway row, NOT on the Site singleton — UDM appears once in
the inventory tree, as a Gateway.

For non-UDM deployments (CloudKey + USG split), Gateway is the USG
entry; the CloudKey doesn't appear (it's the controller appliance, not
a managed UniFi device). The Site singleton still carries Network App
metadata; the USG carries hardware metrics. Topology is identical.

#### Device-level metrics (common device set + UDM-pivot-additions)

| key | label | usage | type | source path |
|---|---|---|---|---|
| `mac` | MAC | P | STRING | `metricset:dev_inventory.mac` |
| `name` | Name | P | STRING | `metricset:dev_inventory.name` |
| `hostname` | Hostname | P | STRING | `metricset:dev_inventory.hostname` (round-3 pivot — was on Controller via sysinfo; redundant on Gateway as `name` typically; included for completeness) |
| `model` | Model | P | STRING | `metricset:dev_inventory.model` |
| `model_in_lts` | Model In LTS | P | STRING | `metricset:dev_inventory.model_in_lts` |
| `device_type` | Device Type | P | STRING | `metricset:dev_inventory.type` (`udm` or `ugw`); on UDM also captures `ubnt_device_type` from sysinfo equivalent (e.g. `UDMPRO`) — round-3 pivot |
| `firmware_version` | Firmware Version | P | STRING | `metricset:dev_inventory.version` |
| `unifi_os_version` | UniFi OS Version | P | STRING | `metricset:dev_inventory.console_display_version` (UDM only — round-3 pivot from Controller; absent on USG) |
| `udm_version` | UDM Firmware Version | P | STRING | `metricset:dev_inventory.udm_version` (UDM only — round-3 pivot; absent on USG) |
| `serial` | Serial | P | STRING | `metricset:dev_inventory.serial` |
| `ip` | IP Address | P | STRING | `metricset:dev_inventory.ip` |
| `state` | State | M | NUMBER | `metricset:dev_inventory.state` |
| `uptime_seconds` | Uptime (s) | M | NUMBER | `metricset:dev_inventory._uptime` (round-3 pivot — was Controller's `controller_uptime_seconds` from sysinfo on UDM Pro; on USG-split deployments the controller uptime is irrelevant since it runs on the CloudKey) |
| `last_seen_epoch` | Last Seen | M | NUMBER | `metricset:dev_inventory.last_seen` |
| `cpu_pct` | CPU % | M | NUMBER | `metricset:dev_inventory.system-stats.cpu` (coercion D — UDM emits string) |
| `mem_pct` | Memory % | M | NUMBER | `metricset:dev_inventory.system-stats.mem` (coercion D) |
| `system_load_1m` | System Load (1m) | M | NUMBER | `metricset:dev_inventory.system-stats.loadavg_1` (round-3 pivot — system load is a hardware metric per CLAUDE.md classification) |
| `system_load_5m` | System Load (5m) | M | NUMBER | `metricset:dev_inventory.system-stats.loadavg_5` |
| `system_load_15m` | System Load (15m) | M | NUMBER | `metricset:dev_inventory.system-stats.loadavg_15` |
| `client_count` | Clients | M | NUMBER | `metricset:dev_inventory.num_sta` |

#### WAN metrics from top-level `wan1` and `wan2`

API map clarifies WAN data is in top-level `wan1`/`wan2` objects, NOT in
`port_table`. v1's "filter port_table by network_name=='wan'" path is
discarded.

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `wan1_tx_bytes_total` | WAN1 TX Bytes (cumulative) | M | NUMBER | `metricset:dev_inventory.wan1.tx_bytes` | endpoint #4 UDM section |
| `wan1_rx_bytes_total` | WAN1 RX Bytes (cumulative) | M | NUMBER | `metricset:dev_inventory.wan1.rx_bytes` | endpoint #4 |
| `wan1_tx_bytes_rate` | WAN1 TX Bytes/s | M | NUMBER | `metricset:dev_inventory.wan1.tx_bytes-r` | endpoint #4 |
| `wan1_rx_bytes_rate` | WAN1 RX Bytes/s | M | NUMBER | `metricset:dev_inventory.wan1.rx_bytes-r` | endpoint #4 |
| `wan1_tx_errors` | WAN1 TX Errors | M | NUMBER | `metricset:dev_inventory.wan1.tx_errors` | endpoint #4 |
| `wan1_rx_errors` | WAN1 RX Errors | M | NUMBER | `metricset:dev_inventory.wan1.rx_errors` | endpoint #4 |
| `wan1_latency_ms` | WAN1 Latency (ms) | M | NUMBER | `metricset:dev_inventory.wan1.latency` | endpoint #4 |
| `wan1_availability_pct` | WAN1 Availability % | M | NUMBER | `metricset:dev_inventory.wan1.availability` | endpoint #4 |
| `wan1_speed_mbps` | WAN1 Speed (Mbps) | M | NUMBER | `metricset:dev_inventory.wan1.speed` | endpoint #4 |
| `wan1_up` | WAN1 Link Up | P | STRING | `metricset:dev_inventory.wan1.up` | endpoint #4 |
| `wan2_*` | (mirror of wan1, all fields) | — | — | `metricset:dev_inventory.wan2.*` | endpoint #4 |

(Listing only wan1; wan2 mirrors with `wan2_` prefix. ~10 metrics each.)

#### Active-WAN speedtest (`uplink` top-level object)

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `active_wan_xput_up` | Active WAN Speedtest Up | M | NUMBER | `metricset:dev_inventory.uplink.xput_up` | endpoint #4 |
| `active_wan_xput_down` | Active WAN Speedtest Down | M | NUMBER | `metricset:dev_inventory.uplink.xput_down` | endpoint #4 |
| `active_wan_speedtest_status` | Active WAN Speedtest Status | P | STRING | `metricset:dev_inventory.uplink.speedtest_status` | endpoint #4 |
| `active_wan_speedtest_ping_ms` | Active WAN Ping (ms) | M | NUMBER | `metricset:dev_inventory.uplink.speedtest_ping` | endpoint #4 |
| `active_wan_drops` | Active WAN Drops | M | NUMBER | `metricset:dev_inventory.uplink.drops` | endpoint #4 |
| `active_wan_uptime` | Active WAN Path Uptime | M | NUMBER | `metricset:dev_inventory.uplink.uptime` | endpoint #4 |

#### Temperatures (UDM only)

The api map confirms `temperatures[]` is array-of-objects (`{name, type,
value}`). Sensor names on the UDM Pro are `"CPU"`, `"Local"` (board),
`"PHY"` (board). v1's `[?name=='System']` filter does NOT match — fixed
here to `[?name=='CPU']`.

| key | label | usage | type | source path | api map ref |
|---|---|---|---|---|---|
| `cpu_temp_c` | CPU Temperature (°C) | M | NUMBER | `metricset:dev_inventory.temperatures[?name=='CPU'].value \| [0]` | endpoint #4 UDM |
| `overheating` | Overheating | P | STRING | `metricset:dev_inventory.overheating` | endpoint #4 |

v2 defers `local_temp_c` and `phy_temp_c` (board sensors) and per-mountpoint
storage usage from `storage[]` — not gated on tooling, just out-of-scope
to keep v2 lean.

**Gateway metric count: ~42** (20 device-level including the round-3
pivot additions [hostname, unifi_os_version, udm_version, device_type,
controller-uptime, system load 1m/5m/15m] + 20 WAN + 6 speedtest + 2
temp). The pivot moved 5 hardware-identity properties and 4 hardware
metrics off Controller onto Gateway (where applicable; UDM-only fields
are absent on USG-split deployments).

---

## Chaining grammar application

**v2 has no chained metricSets.**

This is a calibration finding worth flagging. UniFi was assumed
(implicitly, by analogy to Synology) to need chains for per-device
detail enrichment. The api map shows it does not — `stat/device` returns
all device fields including nested per-radio (`radio_table_stats[]`),
per-port (`port_table[]`), and per-WAN (`wan1`/`wan2`/`temperatures[]`)
data in a single response. There is no per-device-detail endpoint that
needs chained substitution.

The path of least resistance for per-radio / per-port / per-temp metrics
is therefore **JMESPath filter predicates inside the existing
metricSet's source path**, not chained metricSets. Renderer support for
JMESPath filter predicates is the gating tooling item (§risks); chain
grammar is unused in v2.

**Implication for substrate calibration:** the `chains_from`/`bind`
grammar wasn't exercised by UniFi v2 at all. That doesn't mean it's
broken — Synology v2 already exercises it (Volume's `volume_util` chain).
UniFi v2 instead exercises the *renderer-side data-shaping* grammar
(JMESPath filter predicates, JMESPath aggregates, soon: type coercion
and compose). Those are different muscles. Phase 3 prioritization should
treat them as orthogonal.

**Implication for URL-path-identity recognition:** the api map shows no
UniFi endpoint chains in a way that consumes parent ID via URL path
without echoing it back. The closest pattern would be a hypothetical
`stat/device/{mac}` per-device detail endpoint — which UniFi doesn't
have (everything's in the bulk `stat/device` response). Synology's
URL-path-identity failure mode is therefore not reproducible against
UniFi's classic API. **No SDK pivot recommended for any UniFi metric in
v2.**

---

## Name expressions

All four object kinds use single-metric `name_expression` shorthand (the
multi-part form's renderer is still deferred per Synology v1 axis 3).

| Object | name_expression | Why |
|---|---|---|
| UniFi Site | `site_desc` | From `self/sites[0].desc`. Falls back to `site_name` (URL-path identifier) if `desc` is blank. On a single-site lab `desc` is `"Default"`. |
| Access Point | `name` | From `stat_device.name`. Falls back to MAC if blank — v1.1 composite candidate. |
| Switch | `name` | Same. |
| Gateway | `name` | Same. UDM Pro defaults to `"udm"`; admins can rename. |

**Future composite ask (v1.1, gated on multi-part renderer):**
`${name} (${model})` for AP/Switch/Gateway — operators reading the
inventory tree benefit from seeing the model alongside the admin-set
name. Not a v2 blocker.

---

## Request Mapping

Three top-level requests in v2:

| # | Request | API path (relative to `base_path = proxy/network/api/s/default`) | Method | Consumers | Notes |
|---|---|---|---|---|---|
| 1 | `site_sysinfo` | `stat/sysinfo` | GET | Site singleton (controller-software metadata: version/build/retention/timezone) — round-3 pivot moved hardware-specific sysinfo fields (hostname, console_display_version, udm_version, ubnt_device_type, uptime) to Gateway via `dev_inventory` | ~1.5 KB |
| 2 | `site_meta` | `../../self/sites` | GET | Site singleton | ~300 B; site identity. **TOOLSET QUESTION C** — singleton consuming first row of a list response. |
| 3 | `site_health` | `stat/health` | GET | Site singleton (5 JMESPath subsystem extractions) | ~2.4 KB; per-subsystem aggregates |
| 4 | `dev_inventory` | `stat/device` | GET | AP, Switch, Gateway (each with their own `type==X` filter). Gateway row also carries the round-3-pivoted hardware identity/uptime/system-load metrics that previously lived on Controller via sysinfo — all are present in `dev_inventory` for the UDM row natively. | ~385 KB on lab (15 devices); single response feeds three list objects |

**Total per-cycle requests: 4.** Pull cardinality is constant in
collection (no chains). At a 100-device MSP scenario `dev_inventory`
grows linearly to ~2.5 MB but request count stays at 4 — within
expected MPB tolerance.

### Cross-object metricSet pattern

Three list objects (AP, Switch, Gateway) share request `dev_inventory`,
each with a different `list_path` filter:

```yaml
# Access Point object
metricSets:
  - from_request: dev_inventory
    primary: true
    list_path: "[?type=='uap']"

# Switch object
metricSets:
  - from_request: dev_inventory
    primary: true
    list_path: "[?type=='usw']"

# Gateway object
metricSets:
  - from_request: dev_inventory
    primary: true
    list_path: "[?type=='udm' || type=='ugw']"
```

**TOOLSET QUESTION E**: does the renderer support the same request
feeding three different list objects with different JMESPath
`list_path` filters, all in scope of the same `dataModelLists[]` derived
from a single response? Synology's pattern is "one request per list
object"; this is a different shape. The MPB wire format almost certainly
supports it (the design's `requests[]` and `objects[]` are independent;
each object's metricSet just references a `requestId`+`listId`), but
**factory render path needs verification**. See §risks.

If the renderer can't, fall back to **three separate but identical
`stat/device` requests** (one per device kind) — wasteful but
mechanically simple. Or, if MPB rejects three identical requests, use
one request and post-filter at the metric-source level (rendering
`source: "metricset:dev_inventory[?type=='uap'].name"` etc., which
collapses the same shape into the metric source rather than `list_path`).

---

## Events

**None in v2. Deferred to v1.1 (round-3 OQ #2 closed).**

Same doctrine as Synology v2 — Tier 1 threshold alerting goes through
factory `vcfops_symptoms` + `vcfops_alerts` referencing
`mpb_unifi_network` adapter metrics after the MP ships.

Round-3 closure on Tier 2 MPB events: **skipped entirely.** The api
map confirms classic `stat/event` is **404 on Network App 10.x** —
every prior briefing/supplement that cited it as the event surface is
stale on current controllers (10.3.55 verified 2026-04-30). `rest/event`
/ `list/event` exist but require uncaptured time-window params.
`stat/anomalies` (per-device satisfaction/anomaly counts) and
`stat/rogueap` (rogue AP detection) ARE confirmed working on 10.3.55
and feed factory symptoms naturally — same pipeline that already works
for threshold alerting. The factory-symptoms-over-poll path delivers
more value per effort than wrestling MPB's event grammar against an
under-documented `rest/event` time-window contract.

**v1.1 Tier 1 alerting plan** (out of v2 scope but on the immediate
roadmap):

- `stat/anomalies` rows → factory symptom: per-device anomaly count
  exceeds threshold.
- `stat/rogueap` rows → factory symptom: count of rogue APs detected
  in the last poll.
- Standard threshold symptoms over Site/AP/Switch/Gateway metrics
  (AP down, switch port error rate, WAN status, gateway temp
  thresholds, AP satisfaction floor, etc.).

These are authored via `vcfops_symptoms` / `vcfops_alerts` after the
MP ships; they reference `mpb_unifi_network`'s metric/property keys
without any MPB-side wiring.

---

## Framework-vs-UniFi review

UniFi exercises seven substrate axes — two re-used from Synology v2,
five new stress points. Round-3 topology pivot reframed Axis 1 (now
"site-level anchor" not "per-controller anchor") and added Axis 2
(peer-level relationships at top tier — same mechanism Synology
exercised, here applied to a different topology shape):

### Axis 1 — `is_singleton` for the site-level anchor (REUSED, generalized)

Synology v2 introduced `is_singleton: true` for Diskstation. UniFi
Site re-exercises the same pattern with three parallel non-chained
metricSets (`site_meta`, `site_sysinfo`, `site_health`), matching
Synology's count. No new substrate need. **Validates: pattern
generalizes across two targets.**

The round-3 topology pivot also refines the *meaning* of
`is_singleton: true` for future targets: in round-2's design the
singleton was "Controller", a hardware-flavored anchor that fit
poorly with UDM-Pro single-box deployments. Site is the cleaner
abstraction — it's the management-context the API uses
(`/api/s/{site}/*`), it generalizes to non-UDM (CloudKey + USG
split has the same Site singleton + Gateway entry shape), and it
matches UniFi's own UI mental model. Lesson for future design
passes: prefer the **logical management context** as the singleton
anchor, not a specific hardware role. Document this in
`context/mpb_relationships.md` after this design passes review.

### Axis 2 — Peer-level relationships at top tier (REUSED)

Synology v2 introduced peer-level relationships (Pool/Volume/Disk/
Share at peer tier under Diskstation). UniFi v2 keeps it simpler —
all four kinds (Site, AP, Switch, Gateway) parent the adapter
instance implicitly, with zero explicit relationships in v2 itself.
v1.1 adds AP→Switch and Switch→Switch via field_match on
`uplink.uplink_mac` (in-pack topology). This is the same
mechanism Synology peer relationships use; no new substrate.

The round-3 topology pivot also confirms a useful pattern: when a
single physical device serves multiple logical roles (UDM = controller
+ gateway + WiFi-NVR-host), model the **device once** as its
strongest role (Gateway here) and let the **logical anchor** (Site)
carry context-only fields. Avoids the round-2 design's "represented
twice" smell.

### Axis 3 — JMESPath filter predicates as metric source paths (NEW STRESS POINT)

Synology v1/v2 exercised metric source paths of the shape
`metricset:request_name.dot.path` (simple object access) and `[?...]`
filter predicates only at the relationship level (`field_match` on
attribute equality, computed by MPB at collection time, not via
JMESPath in the metric source).

UniFi's `stat/health` endpoint is a heterogeneous array of subsystem
rows. There's no clean way to extract per-subsystem metrics without
JMESPath filter predicates inside the metric source itself —
`metricset:site_health[?subsystem=='wan'].latency`. The api map §
renderer-gap-finding-1 confirmed the wire shape requires this; the
factory renderer's current support is unverified.

**Substrate gap candidate**: if the renderer doesn't support filter
predicates inside metric source paths, the alternative is to split
`stat/health` into 5 separate requests (one per subsystem URL — UniFi
doesn't expose those, so this fallback is impossible) or to move
per-subsystem metric extraction into a separate metricSet per subsystem
(but each metricSet binds to one request → still need filter to scope
the response to one subsystem row → still JMESPath). **Filter predicates
on metric source paths is the v2-gating renderer gap.** TOOLSET GAP F.

### Axis 4 — Type coercion (string `system-stats.cpu` → number) (NEW)

Synology API was numeric-typed throughout. UniFi's `system-stats.cpu`
returns strings on UDM gateways and numbers on APs (api map §endpoint #4
field verification). Same JSON path, different runtime type per device.

The renderer needs to coerce when the metric is declared NUMBER. Either:
- (a) the loader auto-detects and inserts a wire-level coercion, or
- (b) the YAML grammar grows a `coerce: number` knob on metric source.

Either is fine. Option (a) is preferable (fewer authoring decisions).
**TOOLSET GAP D.**

### Axis 5 — Single request feeding multiple list objects (NEW)

Synology has one request per object kind. UniFi's `stat/device` feeds
three list objects (AP, Switch, Gateway) differentiated by `type` field.
The MPB wire format almost certainly supports it (independent
`requests[]` and `objects[]` arrays), but the factory renderer may
implicitly assume 1-request-per-object. **TOOLSET QUESTION E** —
verification, not necessarily a gap.

### Axis 6 — Two-value extract on auth login response (NEW)

Synology's `cookie_session` extracts ONE value (`Set-Cookie`) per login.
UniFi needs TWO (`TOKEN` cookie AND `x-csrf-token` header). The current
`extract:` block grammar is one-value-per-block. **TOOLSET GAP B** —
grammar grows to a list-of-extracts. Small contained tooling fix; **no
fallback** (Integration API was evaluated 2026-04-30 and rejected on
coverage grounds — see §"Auth path decision (2026-04-30)").

### Axis 7 — Singleton consuming first row of a list response (POSSIBLY NEW)

Site singleton wants `self/sites[0]` — the api map confirms
`self/sites` returns a single-element array on a single-site
deployment. The current grammar's `list_path: ""` consumes the entire
response root; a list response wouldn't bind to a singleton metricSet.
**TOOLSET QUESTION C** — needs grammar/renderer verification.
Workaround: drop the five `site_meta` metrics from v2 (use sysinfo's
`hostname` as the de-facto site name; site identity becomes the
adapter-instance name) — degraded but shippable.

### Substrate axes NOT exercised by UniFi

- **Chain grammar (`chains_from`/`bind`)** — UniFi's API gives
  everything in bulk; no chains needed.
- **URL-path-identity sniff test** — no UniFi endpoint exhibits the
  Synology pattern. No SDK pivot needed.
- **Multi-part `name_expression`** — same deferral as Synology.
- **Stitch_to / Aria-native binding** — UniFi has no Aria-native
  stitching candidates in v2.
- **Aria stitching `me=ATTRIBUTE` / `ome=METRIC`** (the renderer's
  morning-of 2026-04-29 `stitch_to:` knob) — not exercised. UniFi has
  no candidate for this either; the `me=ATTRIBUTE`+`ome=METRIC` pattern
  per `mpb_object_binding_wire_format.md` §9 is for peer-to-peer same-
  object metricSet stitching, which UniFi v2 doesn't need.

### Net substrate verdict

UniFi does **not** require chain or URL-path-identity work. It does
require **renderer-side data-shaping work** that Synology side-stepped:
JMESPath filter predicates in metric sources (Gap F), type coercion
(Gap D), two-value auth extract (Gap B), singleton-from-list-response
(Question C), and request-fan-out-to-multiple-list-objects (Question
E). These are smaller, more orthogonal items than Synology's chained-
collection wire-format ceiling. **Phase 1.5 is well-targeted** — it
exercises an unrelated substrate corner.

---

## Key Risks

1. **TOOLSET GAP F — JMESPath filter predicates in metric source paths.**
   v1's axis-5 risk reaffirmed. UniFi v2 cannot ship a useful Site
   object without JMESPath filter predicate support
   (`[?subsystem=='X']`) inside metric `source:` paths. Without it, v2
   collapses to a sysinfo-only Site (~13 metrics of the planned ~43)
   and AP/Switch lose all per-radio / per-port aggregates. **Gating
   tooling work before mp-author runs.**

2. **TOOLSET GAP D — Type coercion for string-typed numeric fields.**
   `system-stats.cpu` and `system-stats.mem` arrive as strings on UDM,
   numbers on APs. PoE port `poe_power` is also string. Renderer must
   coerce when METRIC + NUMBER is declared. **Gating only for affected
   metrics** — v2 can ship the metric set minus these if necessary, but
   then CPU% and Memory% are missing from Gateway and broken on APs.

3. **TOOLSET GAP B — Two-value extract on auth login (small contained
   tooling fix; blocking).** Classic `cookie_session` for UniFi needs
   both TOKEN cookie AND x-csrf-token from the same login response.
   Current `extract:` grammar is one-value-per-block. The fix is a
   list-of-extracts grammar on the existing `extract:` block — no new
   protocol surface, no new auth path, no new wire format. **Blocking
   for cookie_session, which is the v1 auth surface.** Per §"Auth path
   decision (2026-04-30)", **Integration API was evaluated as a
   fallback and rejected** on coverage grounds (~23% of v2's metric
   set, 0 throughput / utilization / health metrics). Gap B is the
   right tooling spend; there is no alternate path. Tooling agent
   brief inherits this framing.

4. **TOOLSET GAP A — login.body Content-Type.** Same gap Synology has
   with `getSession.headers`. Likely runtime-injected by adapter for
   JSON bodies; non-blocking but produces a diff against any reference
   export. **Defer to tooling, not blocking.**

5. **TOOLSET QUESTION C — Singleton consuming first element of list
   response.** Site wants five metrics from `self/sites[0]` (name,
   id, desc, role, device_count). If renderer doesn't support, drop
   those five metrics and use `site_sysinfo.hostname` as the de-facto
   site name (degraded but shippable; site identity collapses to the
   adapter-instance name). **Degradable, not blocking.**

6. **TOOLSET QUESTION E — Single request feeding three list objects
   with different JMESPath filters.** AP/Switch/Gateway all consume
   `stat/device` filtered by `type`. If renderer doesn't support, fall
   back to three identical requests (wasteful but works). **Probably
   works; verify before authoring.**

7. **Integration API verified, role scoped to v3 (no longer a v2
   risk).** As of 2026-04-30 Integration v1 has been probed
   authenticated against the live UDM Pro
   (`context/api-maps/unifi-integration-api.md`). It is **not**
   suitable as the v1 metric-collection path (~23% coverage; no
   throughput/utilization/health metrics; entire Gateway WAN block
   absent). It IS the right surface for v3 supplements: identity
   binding via stable `id` UUIDs, topology via `uplink.deviceId`,
   config drift via `provisionedAt` / `configurationId`. **Document
   in MP README under "Future direction" — not as a customer-facing
   v1.1 alternative.** v1.1's auth story is unchanged: classic
   cookie_session.

8. **Cameras deferred to v1.1.** Same as v1. Protect API has separate
   auth context and a WebSocket update stream that MPB doesn't support.
   Documented prominently in README. **Design decision, not a risk.**

9. **MPB events deferred — `stat/event` is 404 on Network App 10.x.**
   Briefing and supplement both stale. v1.1 events scope can't be
   authored until api-cartographer maps the `rest/event` /
   `list/event` time-window param requirement. Alternative path:
   factory symptoms over `stat/anomalies` + `stat/rogueap`, which
   already work today. **Document as deferred capability.**

10. **UniFi field-name churn risk.** Same as v1. Network App version
    bumps have historically renamed/removed fields (api map drift table
    confirms several v1 design assumptions). Mitigation: declare
    `network_app_version` as a property so operators can correlate
    metric absence with version. Long-term: prefer Integration API
    (officially supported, stable schema).

13. **Field-shape drift between Network App versions (LOW priority,
    monitoring discipline).** Round-3 evidence: between 2026-04-18
    (Network App 10.2.105) and 2026-04-30 (10.3.55), two minor
    drift items surfaced — `port_table[].mac` was wrongly assumed on
    switches in round-2 design (and never existed on the classic
    surface), and `radio_table_stats[].last_interference_at`
    transitioned from "present" to "conditional/optional" (only
    emitted on recent interference events). Neither breaks v2's
    metric paths, but the pattern matters: minor Network App bumps
    are not no-ops on field shape. **Mitigation:** api-cartographer
    spot-check (10-minute targeted re-verification, not a full
    re-cartography) every Network App major-version bump on the lab.
    Document conditional fields as such in the api map. The
    2026-04-30 spot-check pattern is the template. Treat this as
    operational hygiene, not a v2 blocker.

11. **`dev_inventory` response size at fleet scale.** ~385 KB at 15
    devices is fine. Linear scaling — at MSP-scale 500 devices that's
    ~13 MB per cycle. May need pagination or per-type endpoints; api
    map didn't probe this. Document as scaling assumption; fix in v3.

12. **No cartography on the `paging:` retired grammar.** Synology v2
    learned that MPB regenerates paging trees from live API
    introspection at import time. UniFi authoring does NOT declare
    `paging:`; trust MPB to introspect. **Documented assumption, not
    a risk.**

---

## Framework-capability prerequisites summary

Required tooling before mp-author can produce shippable YAML:

| Capability | Owner | Blocks v2? | Notes |
|---|---|---|---|
| Renderer: JMESPath filter predicates in metric source paths (Gap F) | tooling | **Yes** | Required for Site's site_health subsystems and AP/Switch per-radio/per-port aggregates. ~80% of v2's interesting metrics depend on this. |
| Renderer: type coercion (Gap D) — string→NUMBER for `system-stats.cpu`/`mem` and `poe_power` | tooling | Partial (specific metrics only) | v2 can drop Gateway CPU%/Mem% if necessary; degraded but ships. |
| Loader/renderer: two-value `extract:` (Gap B) — list-of-extracts grammar | tooling | **Yes** | Small contained tooling fix. **No alternate path** — Integration API was evaluated 2026-04-30 and rejected (23% coverage cliff). See §"Auth path decision (2026-04-30)". |
| Loader/renderer: single request feeding multiple list objects (Question E) | tooling | Verification, not necessarily a gap | Wire format almost certainly supports; renderer path needs check. |
| Loader/renderer: singleton metricSet consuming first row of a list response (Question C) | tooling | Degradable | Drop site_meta metrics if not supported. |
| Loader/renderer: login.body Content-Type (Gap A) | tooling | No | Likely runtime-injected; flag for parity. |
| api-cartographer: Integration API response shapes | api-cartographer | **Done (2026-04-30)** — see `context/api-maps/unifi-integration-api.md`. Result: Integration v1 is v3 supplement only, not a v2 alternative. | — |
| api-cartographer: `rest/event` time-window param shape | api-cartographer | No (events deferred to v1.1) | Required before v1.1 events authoring. |
| MPB UI .pak install verification | Scott (manual) | Yes | Same as Synology — devel-lab MPB UI install path. |

Phase-3 substrate seed (orthogonal to Synology's chain/binding work):
filter predicates, type coercion, multi-extract, request-fan-out,
list-to-singleton — the "renderer-side data shaping" cluster.

---

## Open dependencies on tooling agent

Priority-ordered. The first three are **blocking**; mp-author cannot
produce shippable YAML without them. Items 4-6 are degradable or
nice-to-have.

1. **Gap B — list-of-extracts grammar on `extract:` block.**
   Loader/renderer support for multiple `extract:` bindings on a
   single response (specifically: `Set-Cookie` cookie capture AND
   `x-csrf-token` header capture from the same login response, both
   bound to `session.*` slots for downstream `inject:` use).
   - **Severity:** small contained tooling fix; **blocking**.
   - **Without it:** classic `cookie_session` does not work
     end-to-end. There is no alternate auth path (Integration API
     was evaluated 2026-04-30 and rejected — see §"Auth path
     decision").
   - **Brief framing:** contained grammar extension on existing
     `extract:` block. Not a new protocol surface, not a new wire
     format.

2. **Gap F — JMESPath filter predicates in metric source paths.**
   Renderer must accept filter predicates inside metric `source:`
   paths (e.g. `metricset:site_health[?subsystem=='wan'].latency`,
   `metricset:dev_inventory.radio_table_stats[?radio=='ng'].cu_total |
   [0]`, `metricset:dev_inventory.temperatures[?name=='CPU'].value |
   [0]`).
   - **Severity:** **blocking** for ~80% of v2's metric set.
   - **Without it:** Site collapses to sysinfo-only (~13 of ~43
     metrics); AP loses all 12 per-radio metrics; Switch loses
     port-aggregate counts; Gateway loses CPU temperature.
   - **Brief framing:** the api map evidence (UniFi has no `/health`
     subsystem split; classic `stat/health` returns a heterogeneous
     subsystem array; Integration v1 has no `/health` at all)
     confirms there is no wire-side workaround. Renderer-side fix is
     the only path.

3. **Gap D — type coercion (string → NUMBER) for stringy numeric
   fields.** Renderer must coerce string-valued JSON fields to NUMBER
   when the metric is declared `dataType: NUMBER`. Affected fields:
   `system-stats.cpu` (string on UDM, number on APs — same JSON
   path, different runtime type per device kind), `system-stats.mem`
   (same shape), per-port `poe_power` (string Watts).
   - **Severity:** **blocking** for those specific metrics.
   - **Without it:** Gateway CPU% / Memory% either fail to load or
     load as PROPERTY strings; AP CPU%/Mem% inconsistent across the
     fleet; PoE-port power deferred (already deferred to v1.1, but
     the underlying gap is the same).
   - **Brief framing:** preferred fix is loader auto-detect-and-coerce
     based on declared dataType; alternative is a `coerce: number`
     YAML knob on metric source.

4. **Gap A — `login.body` Content-Type header authoring.** Lower
   priority. Same gap Synology has at `getSession.headers`. Likely
   runtime-injected by adapter for JSON bodies (Synology lab observed
   this works in practice).
   - **Severity:** non-blocking; cosmetic for export-diff parity.
   - **Without it:** v2 ships fine, but a post-render diff against
     reference exports will show a missing Content-Type declaration.

5. **Question C — singleton metricSet consuming first row of a list
   response.** Site wants five metrics from `self/sites[0]` (name,
   id, desc, role, device_count). Design-side workaround documented
   (drop site_meta metrics; use `site_sysinfo.hostname` as de-facto
   site identity).
   - **Severity:** degradable, non-blocking.
   - **Brief framing:** verification first; may be supported. If
     not, design has a documented fallback.

6. **Question E — single request feeding multiple list objects with
   different `list_path` filters.** AP/Switch/Gateway all consume
   `stat/device` filtered by `type`. Wire format almost certainly
   supports it (independent `requests[]` and `objects[]` arrays).
   Design-side workaround documented (three identical requests, or
   per-source post-filter).
   - **Severity:** degradable, non-blocking.
   - **Brief framing:** verification first; renderer-path-only check.

**Tooling round priority:** items 1-3 ship together. They are the
"renderer-side data shaping" cluster called out in §"Framework-vs-UniFi
review" §"Net substrate verdict". They are orthogonal to Synology's
chain/binding substrate work and represent Phase 1.5's substrate
contribution.

---

## Open questions for Scott — ALL CLOSED at round-3 design-review gate (2026-04-30)

Every open question from rounds 1 and 2 is closed. mp-author is
unblocked on the design side; remaining blockers are the substrate
gaps cluster (Gap B + F + D) tracked under §"Open dependencies on
tooling agent".

1. **WAN consolidation** — **CLOSED (round-3 topology pivot).**
   Moot under topology pivot: Site carries the per-site WAN
   subsystem aggregate metrics from `stat/health[?subsystem=='wan']`;
   Gateway carries per-gateway WAN uplink metrics from `wan1`/`wan2`
   on the UDM row directly (no relationship needed — same physical
   device). On a UDM Pro the "controller" and "gateway" perspectives
   collapse onto the same row. Both metric sets co-exist naturally
   without a `field_match` join. Closed.

2. **Events scope** — **CLOSED (round-3, deferred to v1.1).**
   Skip MPB events entirely. Tier 1 alerting via factory symptoms
   over `stat/anomalies` + `stat/rogueap` (both confirmed working
   on Network App 10.3.55). Less wire-format risk, faster
   iteration, more value per effort. v1.1 plan documented in
   §Events.

3. **Integration API pivot** — **CLOSED 2026-04-30 (round-2 auth
   pass).** Answer: no pivot. Integration v1 covers ~23% of v2's
   metric set; pivoting trades a contained tooling fix for
   catastrophic coverage loss. Gap B stays pinned to tooling;
   classic `cookie_session` is the v1 auth surface. Integration v1
   retained as a v3 supplement for identity / topology /
   config-drift only. Full reasoning in §"Auth path decision
   (2026-04-30)".

4. **Per-metricSet collection cadence** — **CLOSED (round-3,
   defer).** Adapter-default cadence for v1; no per-metricSet
   cadence grammar commissioned. UniFi naturally tiers
   (`stat/device` liveness at 30s; per-port/per-radio at 5min;
   config drift at 15min) but the single-interval-per-adapter
   constraint is acceptable for v1. Revisit Phase 3 if operational
   experience flags a real cost.

5. **Icon mapping** — **CLOSED (round-3, defaults accepted).**
   - UniFi Site → `network-aggregator.svg`
   - Access Point → `wireless-access-point.svg`
   - Switch → `network-switch.svg`
   - Gateway → `firewall.svg`
   Loader doesn't validate icon names (verified in code); MPB
   import-time falls back to `server.svg` if the named SVG isn't
   packaged. Site icon was explicitly noted as adjustable to
   something more topology-y if `network-aggregator.svg` doesn't
   convey site-scope cleanly — mp-author may swap during authoring
   if a better SVG presents itself.

6. **MP display name** — **CLOSED (round-3): `VCF Content Factory
   UniFi`.** Per CLAUDE.md hard rule #5: MPs use prose-form `VCF
   Content Factory <name>` with no brackets, distinct from content's
   bracketed `[VCF Content Factory]` form. The "UniFi Network" /
   "Ubiquiti UniFi" debate is moot — the framework prefix is
   load-bearing and the trailing word is just `UniFi`.

7. **Object name (Controller vs Site vs Site Manager)** —
   **CLOSED (round-3, superseded by topology pivot).** The
   "Controller" kind no longer exists — the round-3 topology pivot
   dissolved it. The top-level singleton is **`UniFi Site`**, named
   to match UniFi's own management-context terminology. v3 may
   introduce a Site list child for MSP multi-site; the singleton
   becomes either a controller-level anchor or stays as
   "primary site" (TBD when MSP shape is mapped). No rename
   required between v2 and v3 — Site stays Site.

8. **Network App version re-confirm** — **CLOSED 2026-04-30
   (round-3, verified).** Classic `stat/sysinfo` re-pulled on
   2026-04-30; controller is on Network App 10.3.55 (was 10.2.105
   on 2026-04-18; controller upgraded between dates). Per the api
   map's §"Version verification — 2026-04-30 spot-check": every
   v2-design metric path resolves on 10.3.55 with the same shape
   and field names as 10.2.105. Two minor field-shape items
   recorded:
   - `port_table[].mac` was wrongly assumed on switches in
     round-2 design — never existed on classic surface. Removed
     from v2; addressed under §Switch metrics ("Round-3 note on
     `port_table[].mac`"). Wired-client → switch-port joining
     uses `stat/sta.last_uplink_mac` + `stat/sta.sw_port` (the
     v2 cross-adapter ESXi-Host-pNIC roadmap item also uses this
     join, not `port_table[].mac`).
   - `radio_table_stats[].last_interference_at` is conditional/
     optional (was present 2026-04-18, absent 2026-04-30 — only
     emitted on recent interference events). Not in v2
     dependencies; harmless. Recorded as a "conditional field"
     pattern under §AP metrics.
   No further re-cartography needed before mp-author runs.

---

## Future Work — relationships and capability roadmap

Captured 2026-04-30 round-3 for traceability. None of these are v2
scope; they're the candidate-pile that informs how v2's design choices
should hold up.

### v1.1 (next factory iteration after v2 ships)

- **In-pack topology relationships.** AP→Switch and Switch→Switch via
  `field_match` on `uplink.uplink_mac` → parent `mac`. Same mechanism
  Synology v2's peer relationships use; no new substrate. Lab has at
  least one AP-parented AP (`ap-lower` → `ap-basement`) — relationship
  must tolerate AP→AP edges, not assume parent is always Switch (the
  existing field_match grammar handles this naturally).
- **Tier 1 alerting via factory symptoms** over `stat/anomalies` +
  `stat/rogueap` + standard threshold metrics (AP down, switch port
  error rate, WAN status, gateway temp thresholds, AP satisfaction
  floor). See §Events for the v1.1 plan.
- **Per-port first-class Switch object** (deferred from v2 §Scope
  Reductions). Requires JMESPath aggregates landing + PoE-power
  string→number coercion + null-`total_max_power` propagation.

### v2 candidates (cross-adapter scope)

- **ESXi Host pNIC → UniFi Switch port relationship.** Cross-adapter
  edge from VMware Adapter's Host objects to `mpb_unifi_network`'s
  Switch / Switch-Port objects. Join is via the host's pNIC MAC (from
  the VMware adapter) matched against `stat/sta.last_uplink_mac` (with
  `stat/sta.sw_mac` identifying the switch and `stat/sta.sw_port`
  identifying the port). Useful for "which switch is this host on"
  troubleshooting workflows. Not gated on additional UniFi-side
  cartography — `stat/sta` is documented in the api map already.
  Gated on cross-adapter relationship grammar.

### v2+ (gated on capability solves)

- **Per-VM client correlation.** End-to-end traceability from VMware
  VM through pNIC through UniFi Switch port to UniFi Wireless Client
  (where applicable). Gated on solving client object cardinality —
  unbounded guest WiFi / IoT MACs make naive per-client modeling
  unsustainable at scale. Likely requires a "managed device clients
  only" classifier or per-client TTL discipline before this can ship.

### v3 (Integration API supplement)

- **Integration API as identity / topology / config-drift surface.**
  Per the api map's §"Future v3 use cases": Integration v1's stable
  UUIDs (`uplink.deviceId`), `provisionedAt` (last config push
  timestamp), and `configurationId` (opaque config snapshot id) are
  the right surface for these specific workloads. Classic surface
  stays the metric-collection path.
- **Topology grammar pivot to Integration v1's UUID pointers.** Once
  we're already on Integration for config drift / identity, pivot the
  v1.1 topology grammar from MAC matches (`uplink.uplink_mac` →
  `mac`) to UUID pointers (`uplink.deviceId` → `id`). Cleaner
  identity, survives MAC-swap on hardware replacement.
- **Site Manager API (multi-site / MSP).** Materialize Site as a list
  child of an MSP-level singleton; deferred until MSP shape can be
  cartographed against a real multi-site controller.
- **Config drift modeling.** `rest/networkconf` / `rest/wlanconf` /
  `rest/firewallrule` (cached but not modeled in v2). Likely on
  Integration v1 once the v3 supplement lands.

### Substrate-side carry-overs

These belong to Phase 3 substrate work, not specifically UniFi:

- **Per-metricSet cadence grammar** (round-3 OQ #4 deferred). UniFi
  naturally tiers (liveness 30s; per-port/per-radio 5min; config
  15min) but adapter-level single interval is acceptable for now.
- **Multi-part `name_expression`** (carry-over from Synology v1 axis
  3 deferral). UniFi v1.1 wants `${name} (${model})` for
  AP/Switch/Gateway readability.

---

## Mockup — bundled dashboard scaffold

v2 ships **no bundled dashboard**, same as Synology v2. Factory
dashboards under the `[VCF Content Factory]` prefix will be authored
post-install via the standard pipeline. Sketch for the eventual
dashboard:

```
+--------------------------------------------------------------+
| [VCF Content Factory] UniFi Network Overview                 |
+--------------------------------------------------------------+
| Scoreboard: Devices Adopted | Disconnected | Update Available|
| Scoreboard: Wireless Users  | Guest Users  | IoT Users       |
+--------------------------------------------------------------+
| Heatmap: AP Channel Utilization (cu_total) by AP & radio     |
| MetricChart: WAN Latency (Site.internet_latency_ms)          |
+--------------------------------------------------------------+
| ResourceList: APs ranked by satisfaction (asc)               |
| ResourceList: Switches with overheating==true                |
+--------------------------------------------------------------+
| AlertList: All open alerts on mpb_unifi_network adapter      |
+--------------------------------------------------------------+
```

---

## Agent architecture reminder (for mp-author)

Reading order before mp-author starts:

1. `context/management_pack_authoring.md` — the YAML grammar spec
2. `context/mpb_relationships.md` — relationship pattern reference
3. `context/mp_chain_authoring.md` — chain grammar (used here only for
   completeness; v2 has no chains)
4. `context/api-maps/unifi-network-api.md` — every metric source path
   maps back to a specific endpoint here; cross-check before authoring
5. `context/mpb_object_binding_wire_format.md` §10 — `objectBinding`
   rules. v2 has no chained-secondary metricSets, so the §10 emit shape
   does not apply; all metricSets in v2 are either singleton-scalar
   (`is_singleton: true`) or list-primary, both of which keep
   `objectBinding: null`.
6. **Tooling prerequisites before authoring**: confirm Gaps B (two-value
   extract), F (JMESPath filter predicates), and D (type coercion) are
   landed, per §"Open dependencies on tooling agent". If a gap is NOT
   landed at author-time, drop the dependent metrics from v2 (degraded
   shippable) and document the cut in a §"Deferred from v2 due to
   tooling" subsection of the resulting MP YAML's design-comments.
   Integration API is NOT a fallback — that path was evaluated and
   rejected on coverage grounds (round-2 auth pass, see §"Auth path
   decision (2026-04-30)").

mp-author should validate with `python3 -m vcfops_managementpacks
validate` before returning.
