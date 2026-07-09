# Design Artifact: UniFi Network Management Pack v1

## Original Request

Build the second management pack in the VCF Content Factory — a UniFi
Network MP targeting Scott's lab UDM Pro at `unifi.int.sentania.net`.
Synology is MP #1 (the tooling-and-grammar learning project). UniFi
is MP #2, and its job is to validate that the Tier 3 grammar actually
generalizes: does a second target system, with different auth, different
topology, different response shapes, fit cleanly into the framework we
built for Synology, or does it surface shortcut-or-gap evidence that
the grammar still has Synology-specific bumps in it?

Ecosystem context: no UniFi MP exists anywhere for VCF Ops / Aria
Operations (exhaustive search by Khriss, April 2026) — this is a
genuine gap. It is also concrete "framework is the product" evidence
for the Explore 2026 abstract Scott and Tim Hanchon are co-submitting.

Source material driving this design:

- `/home/scott/pka/kb/reference/2026-04-17-unifi-api-mp-authoring-briefing.md` — the
  authoritative intent doc (Jasnah synthesis + Khriss external
  research + Pattern fact-check).
- `/home/scott/pka/agents/khriss/outbox/2026-04-17-unifi-api-external-supplement.md` — 446-line
  supplement with per-surface detail.
- `designs/synology-mp-v1.md` — structural template and the 12-axis
  framework-vs-target review whose shape this artifact mirrors.
- `vcfops_managementpacks/loader.py`, `render.py` — the post-Tier-3
  grammar reality against which every grammar claim below is checked.

## Design revisions

- **2026-04-18** — initial draft. Produced as **starting-point
  artifact** before three dependencies land: (a) Scott's controller's
  actual Network Application version (briefing §5 flags Navani's
  "5.0.16" as probably a conflation of UniFi OS and Network App
  versions — the real version affects which auth surface is viable);
  (b) an `api-cartographer` pass landing under
  `context/api-maps/unifi-*.md` (right now the only grounding is the
  briefing's candidate metric tables); (c) MPB install parity
  established (the Synology adapter-JAR extraction is still blocking
  on Scott's devel-lab MPB UI — same blocker will apply to UniFi once
  MP #1 clears it). Design will revise as each of those three
  dependencies resolves.

## Scope reductions (explicit — read this before anything else)

v1 targets a deliberately narrow slice of UniFi so that mp-author and
tooling can land a clean second MP without compound blockers. Items
below are pushed out to v1.1 or v2 with reasons.

| Scope | v1 | v1.1 | v2 | Why |
|---|---|---|---|---|
| Site + Controller (collapsed) + AP + Switch + Gateway + Wireless-Client-aggregate | **in** | — | — | Core Network Application monitoring story. |
| Protect cameras | — | **in** | — | Different auth context (`/proxy/protect/` API with bootstrap + WebSocket update stream); deserves its own design pass. Scott's lab has 12 cameras — material but scope-adjacent. |
| Tier 2 MPB events (DSM-style notification feed) | — | **in** | — | `stat/event` + `stat/alarm` have a 3000-result cap plus time-windowing requirements that need api-cartographer to verify shape. Defer rather than hero-shortcut. |
| Topology relationships (AP `uplink_mac` → Switch `port_table[].mac`) | — | **in** | — | Exercises `scope: field_match` in an interesting way (nested-array join) but Synology v1 also deferred topology; keep v1 lean. |
| Site Manager API (cloud proxy) | — | — | **in** | Multi-site / MSP scenario only. Scott's lab is single-console direct-access. |
| Per-client objects (per-MAC client tracking) | — | — | **in** | Unbounded cardinality for guest/IoT traffic. v1 surfaces aggregate counts instead. |
| Config drift via `rest/networkconf` / `rest/wlanconf` / `rest/firewallrule` | — | — | **in** | Useful but is a distinct design story (delta-over-time rather than metric-over-time); defer. |

Tier 1 threshold alerting (AP down, switch port error rate, WAN
status, temp thresholds) is **not deferred** — it ships alongside the
MP via the factory's existing `vcfops_symptoms` / `vcfops_alerts`
pipelines. Per framework doctrine codified in Synology axis 4,
threshold alerting is never MPB territory.

## Interview Answers

| Question | Answer | Source |
|---|---|---|
| Monitoring scope | Site + AP + Switch + Gateway + Wireless-Client aggregate. Cameras deferred. | Briefing §3 object hierarchy; scope table above. |
| Object granularity | Each UniFi device kind (AP, Switch, Gateway) is its own object_type; Wireless Client is aggregate-only (no per-MAC objects) because client cardinality is unbounded on guest SSIDs. | Briefing §3 + framework doctrine (bounded cardinality). |
| Relationship topology | Shallow two-level tree: Site (world) → {AP, Switch, Gateway, Wireless-Client-aggregate}. Topology edges (AP uplink → Switch port) deferred to v1.1. | Briefing §3 hierarchy diagram. |
| Cross-adapter relationships | None in v1. v2 might correlate Wireless Client aggregates with NSX segment objects via VLAN ID, but that requires Scott's green light and a second API map. | — |
| Events | Tier 1 threshold conditions → factory symptoms/alerts (same as Synology precedent). Tier 2 MPB events deferred. | Framework doctrine axis 4; scope table. |
| Bundled content | Basic dashboard in the .pak (device liveness heatmap + site health scoreboard); rich dashboard via factory pipeline post-install. | Synology precedent; framework doctrine axis 9. |
| Collection intervals | 30s device liveness/util, 5min per-port / per-radio stats, 15min config-drift (deferred). Matches briefing §3 cadence recommendations. | Briefing §3 cadence column. |
| Controller version assumption | v9.3.43+ (Network Integration API eligible) — needs verification via `stat/sysinfo`. If below, fall back to cookie-session + CSRF. | Briefing §5, §2 auth decision table. |
| Lab target | `unifi.int.sentania.net` (UDM Pro). Base URL `/proxy/network/api/` (classic) or `/proxy/network/integration/v1/` (official). | Briefing §2; Navani's recon. |

## Object Model

The briefing recommends Site → Controller → {AP, Switch, Gateway, Client}.
The first design decision worth justifying: **collapse Site and
Controller into one world object**.

### Decision: collapse Site + Controller into "UniFi Site"

For a UDM Pro deployment — the dominant shape of Ubiquiti's current
hardware line, and the shape of Scott's lab — the controller
(`Dream Machine`) is the same hardware that is the gateway, has no
independent identity from the site, and has no meaningful parent/child
semantics that separate "the UDM Pro" from "the site". Modeling
Controller as a first-class parent of {AP, Switch, Gateway} would:

1. Introduce a degenerate 1:1 Site↔Controller relationship whose
   join predicate is trivially "match everything in this
   adapter-instance". Synology already carries four such
   adapter-instance-trivial relationships (see Synology axis 2) and
   we agreed to exercise `scope: adapter_instance` cleanly rather
   than proliferate them.
2. Fight the API: `stat/device` returns all devices flat, scoped to
   a site, with no per-controller grouping. A Controller tier would
   be synthetic.
3. Make Gateway confusing: the UDM Pro is **also** the gateway. Is
   it Controller, Gateway, or both? Two object_types pointing at
   the same hardware is a footgun.

So v1 collapses: the world object is **UniFi Site**, identified by
the site's `name` field (not `desc`) from `/api/self/sites`. The
Gateway object_type remains (because the MP should surface WAN-level
metrics distinctly from LAN/WLAN), but it is modeled as a peer of
AP and Switch — one of the devices living inside the site — not as
a separate controller tier above them. The UDM Pro shows up as a
Gateway instance, same as a USG would.

For multi-site deployments (MSP / Site Manager API, v2) the Site
world-object model still fits — multiple Site instances per adapter
instance instead of one. The data model carries forward.

### Object tree

```
UniFi Site (world, keyed by site_name)
|
+-- Access Point         1:N   (keyed by mac)
+-- Switch               1:N   (keyed by mac)
+-- Gateway              1:N   (keyed by mac) -- typically 0 or 1 (the UDM Pro)
+-- Wireless Client Aggregate  0:1  (keyed by site_name -- one per site)
```

Five object_types total. Wireless Client Aggregate is modeled as a
0:1 singleton per Site because it's a summary object (total clients,
guest count, 2.4/5/6 GHz band breakdown) not a per-device collection
— per-MAC client objects are explicitly deferred to v2.

### Relationships (4, all `scope: adapter_instance`)

Every relationship in v1 is adapter-instance-scoped. The API does not
expose a per-device field carrying the site name back — devices are
site-scoped by URL path (`/api/s/{site}/stat/device`), not by a
response field. So there is no `field_match` value-join available
without a synthesized property, and the framework-general answer is
to declare `scope: adapter_instance` on all four relationships and
let the renderer handle the wire emission once.

| # | Parent | Child | Scope | Source evidence / notes |
|---|---|---|---|---|
| 1 | UniFi Site | Access Point | `adapter_instance` | All APs belong to the one site addressed by the adapter-instance URL. Devices filter to `type=uap` in `stat/device` response. |
| 2 | UniFi Site | Switch | `adapter_instance` | `type=usw`. |
| 3 | UniFi Site | Gateway | `adapter_instance` | `type=ugw` (USG) or `type=udm` (Dream Machines). The UDM Pro reports `type=udm`. |
| 4 | UniFi Site | Wireless Client Aggregate | `adapter_instance` | 0:1 per Site — one aggregate singleton materialized from `stat/health` (wlan subsystem). |

No `field_match` relationships in v1. Framework validation signal:
UniFi exercises `scope: adapter_instance` four times — cleanly and
without hand-wiring — which is the exact property the Synology axis 2
refactor was designed to produce. The framework change is paying off.

v1.1 will add `field_match` relationships for the topology edge
(AP → Switch uplink): child_expression `uplink.uplink_mac`, parent
_expression `mac`. That exercises the nested-object join that Synology
v1's `pool_path` relationship already demonstrated works — a second
concrete example will be useful for the framework's relationship
wiring documentation.

## Authentication

Two viable paths; v1 leads with the X-API-Key path because it's
simpler, officially supported, and avoids the MPB CSRF-rotation
ceiling. The cookie-session fallback is documented so that older
controllers remain in scope.

### Primary v1 auth: X-API-Key via `bearer_token` preset + custom inject

The framework's `bearer_token` preset (validated in
`_validate_auth_bearer`, `loader.py` line 1172) requires exactly one
credential field and permits arbitrary `inject[]` entries — it does
not constrain the inject header name or value template. That means
the following YAML validates cleanly with the current loader, no
framework extension required:

```yaml
source:
  auth:
    preset: bearer_token
    credentials:
      - {key: api_key, label: api_key, sensitive: true}
    inject:
      - type: header
        name: X-API-Key
        value: "${credentials.api_key}"
```

This is the canonical example of framework-general auth modeling:
the preset tells the renderer which wire-level `credentialType` to
emit, the `inject[]` rules tell it what to put on every data request.
The author doesn't need to know the difference between MPB's
`BASIC`, `TOKEN`, `CUSTOM` credential types — the renderer picks.

Base URL: `https://unifi.int.sentania.net/proxy/network/integration/v1/`
(note `integration/v1`, not `api`). Every request path under the v1
MP is relative to that base.

Key rotation / ownership: a single long-lived API key generated via
UniFi Network > Settings > Control Plane > Integrations in the
controller UI. MFA on the cloud account does not affect this — the
key is local to the console. The field label `api_key` means the
value is referenced as `${authentication.credentials.api_key}` by
the renderer.

### Alternate v1 auth: cookie_session + CSRF (for pre-v9.3.43 controllers)

If `stat/sysinfo` returns a Network Application version below 9.3.43,
the integration API isn't available and we fall back to the classic
`/proxy/network/api/` surface with session-cookie auth. The framework
has a preset for this too (`cookie_session`, validated in
`_validate_auth_cookie_session`, loader.py line 1188) and Synology
already exercises it end-to-end for the DSM cookie pattern.

```yaml
source:
  auth:
    preset: cookie_session
    credentials:
      - {key: username, label: username, sensitive: false}
      - {key: password, label: password, sensitive: true}
    login:
      method: POST
      path: "auth/login"
      body: '{"username":"${credentials.username}","password":"${credentials.password}"}'
      headers:
        - {name: "Content-Type", value: "application/json"}
    extract:
      location: HEADER
      name: X-CSRF-Token
      bind_to: "session.csrf_token"
    inject:
      - type: header
        name: X-CSRF-Token
        value: "${session.csrf_token}"
      # Note: the TOKEN cookie is injected by the HTTP stack automatically
      # once login's Set-Cookie lands; MPB's wire emission captures it on the
      # session object and re-sends. We don't declare a second inject for TOKEN.
    logout:
      method: POST
      path: "auth/logout"
```

**Read-only-only constraint (MPB CSRF ceiling):** the briefing §5
and external supplement §10 establish that MPB cannot capture a
*rotated* CSRF token from a mid-session response. On the classic
UniFi API, CSRF rotates on write calls but does NOT rotate on reads.
Since this MP is read-only (no `rest/` POST/PUT/DELETE calls in
scope), the initial CSRF token from login remains valid through the
collection cycle and MPB's one-token-per-session model works. **The
moment any write call enters scope, this auth path breaks.** v1
bundle content is read-only by charter.

Decision rubric for mp-author: pick X-API-Key if Scott's controller
is v9.3.43+ (verifiable via `GET /proxy/network/integration/v1/info`,
which returns 200 only when the integration API is enabled); fall
back to cookie_session only if the integration API is unavailable.
The design assumes X-API-Key unless Scott says otherwise.

## Metrics by Object Type

Structured `MetricSourceDef` form is used for every metric — the
design establishes the canonical example for future MPs. Shorthand
`source: "metricset:<name>.<path>"` is supported by the loader too,
but the structured form surfaces field paths explicitly, which
matters when UniFi's responses carry nested arrays (see UniFi axis 5
framework-review below for `radio_table_stats[].*` stress).

### UniFi Site (world)

- `is_world: true`
- `identifiers: [site_name]`
- `name_expression`: single-part `{parts: [{metric: site_desc}]}` —
  the human-readable site description (e.g. "Sentania Lab"), not
  the internal `name` (which is usually literally "default").
- `identity: {tier: connection_address, source: "metricset:sites_self.name"}`
  — this is the axis 7 stress point. See "Framework-vs-UniFi
  review" below. The site's `name` field is derived at adapter-instance-
  configuration time (the operator enters the console URL; the MP
  discovers sites against that URL), so `connection_address` is the
  right tier. It's not `system_issued` because there's no hardware
  serial on "the site" — a site is a logical construct — and it's
  not `display_name` because the `name` field is API-stable, not
  user-displayed.

**Primary metricSet:** `sites_self` at `list_path: "data"` (the
classic API site listing is an array at the response root).

**Metrics sourced from `sites_self`:**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| site_name | Site Internal Name | PROPERTY | STRING | `sites_self.name` |
| site_desc | Site Display Name | PROPERTY | STRING | `sites_self.desc` |
| site_id | Site ID | PROPERTY | STRING | `sites_self._id` |

**Additional metricSets on Site (singleton — no `primary` flag required):**

- `site_health` at `list_path: "data"` (from `stat/health`) — returns
  one row per subsystem (`wan`, `lan`, `wlan`, `www`, `vpn`). This is
  the "wide row" we fan out into per-subsystem metrics below.

**Metrics sourced from `site_health` (per-subsystem):**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| wlan_status | WLAN Status | PROPERTY | STRING | `site_health[?subsystem=='wlan'].status` |
| wlan_connected_clients | WLAN Connected Clients | METRIC | NUMBER | `site_health[?subsystem=='wlan'].num_sta` |
| wlan_tx_bytes_r | WLAN TX Byte Rate | METRIC | NUMBER | `site_health[?subsystem=='wlan'].tx_bytes_r` |
| wlan_rx_bytes_r | WLAN RX Byte Rate | METRIC | NUMBER | `site_health[?subsystem=='wlan'].rx_bytes_r` |
| wan_status | WAN Status | PROPERTY | STRING | `site_health[?subsystem=='wan'].status` |
| wan_gw_mac | WAN Gateway MAC | PROPERTY | STRING | `site_health[?subsystem=='wan'].gw_mac` |
| wan_ip | WAN IP | PROPERTY | STRING | `site_health[?subsystem=='wan'].wan_ip` |
| www_status | Internet Status | PROPERTY | STRING | `site_health[?subsystem=='www'].status` |
| www_latency_ms | Internet Latency (ms) | METRIC | NUMBER | `site_health[?subsystem=='www'].latency` |
| www_uptime_pct | Internet Uptime % | METRIC | NUMBER | `site_health[?subsystem=='www'].uptime` |

**Known framework stress:** the `[?subsystem=='wlan']` predicate form
is a JMESPath filter expression against an array of rows. The
Synology design's `source.path` grammar is documented as
"single-scalar-path assumed; array-of-objects, regex extraction,
multi-attribute composition not expressible" (axis 5 assessment).
If the current renderer doesn't support JMESPath filter predicates,
**mp-author must flag this** — see UniFi axis 5 review for the two
fallback options.

### Access Point

- `identifiers: [mac]`
- `name_expression: {parts: [{metric: device_name}]}` — falls back
  to the device's `name` field (set by the admin at adoption time).
  If `name` is blank, the admin-set alias-less case, we'd want
  `model + mac` composite, but composites are gated on
  live-render verification — v1 uses single-metric and accepts the
  trade-off that a few un-named APs show their MAC as the display.

**Primary metricSet:** `stat_device` at `list_path: "data[?type=='uap']"`.

**Metrics from `stat_device` primary:**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| mac | MAC Address | PROPERTY | STRING | `stat_device.mac` |
| device_name | Device Name | PROPERTY | STRING | `stat_device.name` |
| model | Model | PROPERTY | STRING | `stat_device.model` |
| model_in_lts | Is LTS Model | PROPERTY | STRING | `stat_device.model_in_lts` |
| version | Firmware Version | PROPERTY | STRING | `stat_device.version` |
| upgradable | Upgrade Available | PROPERTY | STRING | `stat_device.upgradable` |
| upgrade_to_firmware | Upgrade Target | PROPERTY | STRING | `stat_device.upgrade_to_firmware` |
| state | State (1=connected) | METRIC | NUMBER | `stat_device.state` |
| uptime | Uptime (seconds) | METRIC | NUMBER | `stat_device._uptime` |
| last_seen | Last Seen (epoch) | METRIC | NUMBER | `stat_device.last_seen` |
| adopted | Adopted | PROPERTY | STRING | `stat_device.adopted` |
| cpu_pct | CPU Utilization % | METRIC | NUMBER | `stat_device.system-stats.cpu` |
| mem_pct | Memory Utilization % | METRIC | NUMBER | `stat_device.system-stats.mem` |
| ip | Management IP | PROPERTY | STRING | `stat_device.ip` |
| uplink_mac | Uplink Device MAC | PROPERTY | STRING | `stat_device.uplink.uplink_mac` |
| uplink_port_idx | Uplink Port Index | PROPERTY | STRING | `stat_device.uplink.uplink_remote_port` |

**AP-specific radio metrics** come from `stat_device.radio_table_stats[]`
— a nested array with one row per radio (2.4 GHz, 5 GHz, 6 GHz on
WiFi 6E models). This is the framework stress (axis 5).

**Option A — declare per-radio-index scalars (v1 shortcut):**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| radio_2ghz_num_sta | 2.4 GHz Clients | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='ng'].user-num_sta` |
| radio_2ghz_tx_bytes | 2.4 GHz TX Bytes | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='ng'].tx-bytes` |
| radio_2ghz_rx_bytes | 2.4 GHz RX Bytes | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='ng'].rx-bytes` |
| radio_2ghz_satisfaction | 2.4 GHz Satisfaction | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='ng'].satisfaction` |
| radio_5ghz_num_sta | 5 GHz Clients | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='na'].user-num_sta` |
| radio_5ghz_tx_bytes | 5 GHz TX Bytes | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='na'].tx-bytes` |
| radio_5ghz_rx_bytes | 5 GHz RX Bytes | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='na'].rx-bytes` |
| radio_5ghz_satisfaction | 5 GHz Satisfaction | METRIC | NUMBER | `stat_device.radio_table_stats[?radio=='na'].satisfaction` |
| total_num_sta | Total Clients (all radios) | METRIC | NUMBER | `stat_device.radio_table_stats[*].user-num_sta` with `aggregate: sum` |

**Option B — first-class Radio object_type as a chained metricSet:**
one-to-many Radio-child of AP, keyed by `mac + radio_name`, with
per-radio metrics as a flat metricSet on the Radio object. Cleaner
data model but adds two object_types (Radio across AP and Radio
across other radio-capable hardware) and more relationships. v1
holds at Option A.

**Framework stress flagged at Axis 5 below.** If the current
renderer doesn't support `[?radio=='ng']` or `[*]` + `aggregate: sum`,
mp-author must either (i) flip to Option B (Radio as first-class
object), or (ii) limit v1 AP metrics to the non-array scalars above
and flag radio breakout as a v1.1 tooling item.

### Switch

- `identifiers: [mac]`
- `name_expression: {parts: [{metric: device_name}]}`
- Primary metricSet: `stat_device` at `list_path: "data[?type=='usw']"`.

**Common device metrics:** same set as AP (mac, device_name, model,
version, upgradable, state, uptime, last_seen, adopted, cpu_pct,
mem_pct, ip, uplink_mac, uplink_port_idx). No need to redeclare
in this table.

**Switch-specific metrics from `stat_device`:**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| total_ports | Total Port Count | PROPERTY | STRING | `stat_device.num_port` |
| general_temperature | Switch Temperature | METRIC | NUMBER | `stat_device.general_temperature` |
| overheating | Overheating | PROPERTY | STRING | `stat_device.overheating` |
| total_max_power | Total PoE Budget (W) | PROPERTY | STRING | `stat_device.total_max_power` |
| fan_level | Fan Level | METRIC | NUMBER | `stat_device.fan_level` |

**Per-port metrics** come from `stat_device.port_table[]`. Framework
stress identical to AP radio stats: nested-array with scalar fan-out.

**Option A — aggregate scalars in v1, per-port detail in v1.1:**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| ports_up | Ports With Link | METRIC | NUMBER | `stat_device.port_table[?up==true].idx` with `aggregate: count` |
| ports_down | Ports Without Link | METRIC | NUMBER | `stat_device.port_table[?up==false].idx` with `aggregate: count` |
| total_tx_bytes | Total TX Bytes (all ports) | METRIC | NUMBER | `stat_device.port_table[*].tx_bytes` with `aggregate: sum` |
| total_rx_bytes | Total RX Bytes (all ports) | METRIC | NUMBER | `stat_device.port_table[*].rx_bytes` with `aggregate: sum` |
| total_tx_errors | Total TX Errors | METRIC | NUMBER | `stat_device.port_table[*].tx_errors` with `aggregate: sum` |
| total_rx_errors | Total RX Errors | METRIC | NUMBER | `stat_device.port_table[*].rx_errors` with `aggregate: sum` |
| total_poe_power | Total PoE Draw (W) | METRIC | NUMBER | `stat_device.port_table[*].poe_power` with `aggregate: sum` |
| poe_budget_remaining | PoE Budget Remaining (W) | METRIC | NUMBER | `total_max_power - total_poe_power` (computed; see Axis 5) |

**Option B — first-class Switch Port object_type**, keyed by
`switch_mac + port_idx`, 1:N child of Switch. Cleaner but adds
an object_type and a relationship; v1 avoids the cost. Deferred to
v1.1 — topology uses port info anyway so v1.1 likely wants Port
first-class.

**PoE budget remaining (last row in the table)** is a true
framework stress: it's a computed metric combining two other
metrics (one cross-metricSet, `total_max_power` from the device,
the other an aggregate, `total_poe_power` from `port_table[]`).
This is the `source.compose` axis 5 case from the Synology review.
**v1 defers this metric** unless the renderer already supports
`compose` — mp-author flags as a gap if not.

### Gateway

- `identifiers: [mac]`
- `name_expression: {parts: [{metric: device_name}]}`
- Primary metricSet: `stat_device` at
  `list_path: "data[?type=='ugw' || type=='udm']"` — accepts USG
  (standalone gateway) and UDM Pro / UCG Max (Dream Machine gateways).
  The classic API returns both under unified device listing.

**Common device metrics:** same as AP/Switch.

**Gateway-specific metrics from `stat_device`:**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| temperatures_cpu | CPU Temperature (C) | METRIC | NUMBER | `stat_device.temperatures[?name=='CPU'].value` |
| temperatures_system | System Temperature (C) | METRIC | NUMBER | `stat_device.temperatures[?name=='System'].value` |
| storage_used_pct | Local Storage Used % | METRIC | NUMBER | `stat_device.storage.used / stat_device.storage.size * 100` (computed) |

**Gateway-specific metrics from `site_health[?subsystem=='wan']`:**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| wan_rx_bytes | WAN RX Bytes (total) | METRIC | NUMBER | `site_health.wan.rx_bytes` |
| wan_tx_bytes | WAN TX Bytes (total) | METRIC | NUMBER | `site_health.wan.tx_bytes` |
| wan_rx_packets | WAN RX Packets | METRIC | NUMBER | `site_health.wan.rx_packets` |
| wan_tx_packets | WAN TX Packets | METRIC | NUMBER | `site_health.wan.tx_packets` |
| wan_speedtest_latency_ms | Speedtest Latency (ms) | METRIC | NUMBER | `site_health.wan.latency` |
| wan_speedtest_xput_up | Speedtest Upload (Mbps) | METRIC | NUMBER | `site_health.wan.xput_up` |
| wan_speedtest_xput_down | Speedtest Download (Mbps) | METRIC | NUMBER | `site_health.wan.xput_down` |

**Cross-metricSet metric emission:** Gateway's WAN metrics live on
`site_health`'s `wan` row, but Gateway's primary metricSet is
`stat_device`. This is a framework question: can an object_type
declare metrics sourced from a metricSet that is not its primary and
not chained off its primary? For a singleton-like Gateway (typically
one UDM Pro per site), the answer is "the renderer can emit those
metrics on the Site object instead, and leave Gateway with
device-level metrics only." That's the v1 approach — WAN metrics
live on **Site**, not Gateway. Listed in the Gateway table above to
document the intent; actual emission is on Site's `site_health`
metricSet. **mp-author note:** if product says WAN metrics visually
belong on Gateway (operator-intuition-wise), the cross-metricSet
pattern needs framework support and that's a tooling task —
currently not supported.

### Wireless Client Aggregate (singleton 0:1 per Site)

- `identifiers: [site_name]` (one per site — piggybacks the
  site_name identifier value)
- `name_expression: {parts: [{literal: "Wireless Clients ("},
  {metric: site_desc}, {literal: ")"}]}` — **blocked**: multi-part
  composite name expressions are renderer-gated per Synology axis 3.
  v1 falls back to `{parts: [{metric: site_name}]}` (degenerate
  single-metric) and accepts the display limitation. mp-author
  flag if the renderer has since gained composite support.
- Primary metricSet: `site_health` at
  `list_path: "data[?subsystem=='wlan']"`. **But wait** — Site
  already consumes `site_health` at the same list_path. Per
  Synology Option C rule 6, "two metricSets on different
  object_types binding the same request with identical empty
  list_path" is an error. Here list_paths are not empty but are
  identical — does the rule apply? The rule's intent is to prevent
  two object_types claiming the same rows. Here Site and Wireless
  Client Aggregate would both claim the wlan subsystem row.
  **mp-author to resolve**: rename the Wireless Client metricSet
  with a different list_path filter that still resolves to the
  wlan row (e.g., use a `_distinct` key), OR move the wireless
  client aggregate metrics onto the Site object_type (deleting
  the Wireless Client Aggregate object_type entirely) and accept
  that "wireless clients" isn't a first-class object. The latter
  is simpler and matches how Grafana/UnPoller dashboards typically
  present this data — flag for Scott.

**Assuming Wireless Client Aggregate object survives the
resolution:**

| Key | Label | Usage | Type | Source |
|---|---|---|---|---|
| num_user | Active Clients | METRIC | NUMBER | `site_health.num_user` |
| num_guest | Guest Clients | METRIC | NUMBER | `site_health.num_guest` |
| num_iot | IoT Clients | METRIC | NUMBER | `site_health.num_iot` |
| num_ap | Reporting AP Count | METRIC | NUMBER | `site_health.num_ap` |
| num_disconnected | Recently Disconnected | METRIC | NUMBER | `site_health.num_disconnected` |
| status | WLAN Health Status | PROPERTY | STRING | `site_health.status` |

## Chaining grammar application

UniFi exercises the Option C cross-object_type request-reuse pattern
even more heavily than Synology did, and it does so with fewer
chained metricSets. This is the framework validation signal.

### Top-level `requests:` block (MP scope)

| Request name | Method / path | Purpose | Consumed by |
|---|---|---|---|
| `sites_self` | `GET self/sites` | Site inventory | UniFi Site |
| `stat_device` | `GET s/${site}/stat/device` | All devices (APs, Switches, Gateway, Dream Machines) in one call | Access Point, Switch, Gateway |
| `site_health` | `GET s/${site}/stat/health` | Per-subsystem health (wan, lan, wlan, www, vpn) | UniFi Site, Wireless Client Aggregate (conditional on above) |
| `info` | `GET info` | Controller version check (optional, run once at session start) | UniFi Site (as PROPERTY only) |

**Four requests total.** Note `stat_device` is declared once and
consumed by **three object_types** (AP, Switch, Gateway) — each
selecting its own `list_path` filter (`[?type=='uap']`,
`[?type=='usw']`, `[?type=='ugw' || type=='udm']`). This is
Synology's `storage_load_info` pattern at higher fan-out. Single
HTTP call per cycle feeds three object_types. **No chained
metricSets in v1** — every object_type consumes the request as
primary.

### Zero chained metricSets in v1

Unlike Synology (5 chained metricSets for per-row utilization),
UniFi v1 has **zero**. The reason: UniFi's core endpoints each
return complete inventories in one call — `stat/device` includes
nested per-port, per-radio, and per-system-stat arrays inline on
every device row. There are no "per-row detail" endpoints to chain
off of in v1 scope.

That is itself a framework signal: **Option C's one-request-many-consumer
pattern, without chaining, is the common case.** Synology turned out
to be an unusually chain-heavy first MP because DSM's Utilization
endpoint separates device inventory from per-entity IO. UniFi is
probably closer to the typical second or third MP shape.

When chaining does emerge in UniFi (v1.1 per-port detail, v1.1 per-
client objects, v2 config-drift endpoints), the chained metricSet
pattern established in Synology applies unchanged.

### `${site}` path substitution (distinct from `${chain.*}`)

The classic API scopes every data call to a site via the URL path
segment `/api/s/{site}/...`. In the MP grammar this is a
adapter-instance-level substitution, not a chain-level one. The
operator enters the site name in adapter-instance config; every
request templates it in. This substitution is `${configuration.site}`,
not `${chain.site}`.

**Framework observation:** the loader already supports
`${configuration.X}` references (validated in
`_validate_auth_substitution_refs`). UniFi exercises this for the
first time in the factory — Synology had no per-adapter-instance
path substitution (everything is `entry.cgi` + query params). This
is clean framework generalization; flag the pattern in the framework
doctrine.

### Request timing / cadence

The briefing recommends 30s device liveness, 5min per-port / per-
radio, 15min config-drift. The framework doesn't yet have
per-metricSet cadence grammar — every metricSet polls at the MP's
single collection interval. MPB itself can configure single
collection intervals per adapter instance, but not per-metricSet.

**Framework gap flagged:** mp-author sets a single collection
interval (recommendation: 60 seconds as a compromise between 30s
and 5min), and the factory accepts that per-metric cadence
differentiation is a v2 grammar extension. Document in risks.

## Name expressions

Per Synology precedent and framework doctrine (axis 3), v1 uses
single-part structured `name_expression: {parts: [{metric: <key>}]}`
for every object_type. The structured grammar is in place so that
composites can be added once renderer-verified.

| Object type | Name metric | Rationale |
|---|---|---|
| UniFi Site | `site_desc` | e.g. "Sentania Lab". Human-readable. |
| Access Point | `device_name` | Admin-set name (e.g. "Office AP"). Fallback `mac` if blank — but v1 can't express fallback in single-part; admin should name devices. |
| Switch | `device_name` | Same as AP. |
| Gateway | `device_name` | Typically "Gateway" or similar; UDM Pro defaults to "UDM Pro". |
| Wireless Client Aggregate | `site_name` | Degenerate; intent was composite `"Wireless Clients (${site_desc})"` but that requires renderer support. |

**Composite name expression for Wireless Client Aggregate is the
first "would benefit from composite" case we've encountered** — it's
not a blocker (single-part works, display is uglier), but if the
devel-lab MPB UI ever lets us live-test a composite (gap flagged on
Synology axis 3), Wireless Client Aggregate is the obvious first
test case because the alternative reads badly.

## Events

Per framework doctrine (axis 4 codified from Synology), **threshold
alerting is never MPB territory**. UniFi v1 ships with symptom + alert
definitions in the factory's existing `vcfops_symptoms` /
`vcfops_alerts` pipelines, authored in parallel with the MP PAK and
referencing the MP's adapter kind (`mpb_unifi_network`) and resource
kinds.

### Tier 1 — threshold conditions (migrated to factory symptoms/alerts)

| Condition | Severity | Object | Metric/property | Threshold |
|---|---|---|---|---|
| AP Offline | CRITICAL | Access Point | `state` | `!= 1` |
| Switch Offline | CRITICAL | Switch | `state` | `!= 1` |
| Gateway Offline | CRITICAL | Gateway | `state` | `!= 1` |
| WAN Down | CRITICAL | UniFi Site | `wan_status` | `!= "ok"` |
| Internet Down | CRITICAL | UniFi Site | `www_status` | `!= "ok"` |
| AP High CPU | WARNING | Access Point | `cpu_pct` | `> 85` |
| Switch High CPU | WARNING | Switch | `cpu_pct` | `> 85` |
| AP High Memory | WARNING | Access Point | `mem_pct` | `> 90` |
| Switch Overheating | CRITICAL | Switch | `overheating` | `== true` |
| Switch Temp High | WARNING | Switch | `general_temperature` | `> 70` |
| Switch Port Error Spike | WARNING | Switch | `total_tx_errors` | increasing rate > threshold |
| AP Low Client Satisfaction | WARNING | Access Point | `radio_5ghz_satisfaction` | `< 60` |
| Firmware Upgrade Available | INFO | (per-device) | `upgradable` | `== "true"` |
| Internet Latency High | WARNING | UniFi Site | `www_latency_ms` | `> 100` |

Authored via the existing symptom-author / alert-author workflow
post-MP-install. No MPB-side work required.

### Tier 2 — MPB events (deferred to v1.1)

UniFi's `stat/event` and `stat/alarm` endpoints emit discrete event
records (client connect/disconnect, device adoption, firmware update,
admin login, security advisory) that map cleanly to MPB's
API-pulled-event-record model. **Deferred to v1.1** because:

1. The 3000-result cap on event/alarm endpoints means a naive
   `GET stat/event` will truncate on any site with activity. The
   correct pattern is time-windowed queries (e.g., `_limit=3000
   &_sort=-time&time_gt=<last-poll-time>`), which requires the
   MP to carry last-poll state. MPB may not support this shape.
2. The briefing §5 flags this as a v1.1 item explicitly.
3. api-cartographer has not yet landed a UniFi API map, so the
   event payload shape isn't captured. Shipping MPB events
   without the payload shape would be guessing.

v1 ships with MPB `events: []`. v1.1 adds Tier 2 events once
api-cartographer produces `context/api-maps/unifi-events.md`.

## Framework-vs-UniFi review (2026-04-18)

This is the most valuable section for framework-is-product validation.
For each of the 12 axes from Synology's framework review, does UniFi
exercise this cleanly under the current (post-Tier-3) grammar, or
does it stress the grammar differently from Synology — pointing to
either (a) confirmation the grammar generalizes or (b) a new
shortcut-or-gap?

Summary: **12 axes reviewed, 7 exercise the grammar cleanly and
confirm generalization, 3 stress the grammar in new ways that
suggest concrete framework extensions, 2 are unchanged from Synology
(auth flow, request param ordering).**

### Axis 1 — Auth flow (`bearer_token` preset + custom `X-API-Key` inject)

**Current grammar:** flow-based with four named presets
(`cookie_session`, `bearer_token`, `basic_auth`, `none`), credentials
schema, optional login/extract/inject/logout blocks.

**UniFi exercise:** primary v1 auth uses `bearer_token` preset with a
**custom `X-API-Key` header inject**, not a stock `Authorization:
Bearer <token>`. The validator at `_validate_auth_bearer`
(`loader.py:1172`) permits this: it requires exactly one credential
and calls `_validate_inject_rules`, which only checks that
`type ∈ {header, query_param}` and name/value are non-empty. The
header name is author-free.

**Assessment: framework-general; preset naming is accurate; no
extension needed.** `bearer_token` in this framework means
"a single long-lived credential injected by the inject[] rules,"
not "must use `Authorization: Bearer` shape." The preset is about
the credential model, not the wire shape. UniFi validates the
flexibility.

**However, one minor naming question surfaces:** if `bearer_token`
carries an `X-API-Key` inject, is the preset name misleading to an
author reading the YAML? A future `api_key_header` preset alias
could canonicalize the common case without breaking the bearer
preset. **Not a blocker; flag as a naming clarification opportunity
when a third MP uses the same pattern (which is likely — most
vendor APIs are X-API-Key).**

**Secondary exercise: fallback cookie_session + CSRF-as-header-inject.**
UniFi's fallback auth uses `extract.location: HEADER` +
`inject.type: header`, distinct from Synology's
`extract.location: HEADER` (Set-Cookie) + `inject.type: header`
(Cookie re-injection). Both are header-based; both fit the current
grammar. Clean.

**Verdict: axis 1 generalizes cleanly. No framework change.**

### Axis 2 — Relationship scopes (four `adapter_instance` scopes, zero `field_match`)

**Current grammar:** `scope: field_match` (requires child_expression
+ parent_expression) or `scope: adapter_instance` (no expressions
allowed; loader `_validate_relationship` at loader.py:932 enforces).

**UniFi exercise:** all four v1 relationships are `adapter_instance`
(Site → {AP, Switch, Gateway, Wireless Client Aggregate}). Zero
field_match in v1 — UniFi's API doesn't give devices a per-row field
identifying their site (site scoping is URL-based). v1.1 will add a
`field_match` for AP → Switch topology (uplink_mac → mac) which
exercises a nested-object join.

**Assessment: framework-general; v1 is the first MP to exercise
`scope: adapter_instance` in volume.** Synology has four
adapter_instance relationships; UniFi v1 has four. Having two MPs
exercise the same relationship kind, cleanly and without hand-
wiring, is the "framework generalizes" signal that was the whole
point of the Synology axis 2 refactor.

**One open question that UniFi surfaces:** what about relationships
that cross adapter-instance boundaries (e.g., a future Switch Port →
ESXi Host Physical NIC relationship where the ESXi side is a
different adapter instance)? Neither of the current two scopes
covers this. **Not a v1 issue — flag for the first MP that needs
cross-adapter relationships.** This is the "cross-adapter
relationships" question from the wizard interview; Scott said no to
it in v1, so no grammar extension needed for v1.

**Verdict: axis 2 generalizes cleanly. No framework change.**

### Axis 3 — Name expression parts (single-part only, but composite desired)

**Current grammar:** `name_expression: {parts: [{metric: <key>} |
{literal: "..."}]}`. Loader parses multi-part; renderer errors on
multi-part per Synology axis 3 risk.

**UniFi exercise:** all five object_types use single-part. **However,
Wireless Client Aggregate intends to use a three-part composite
(`"Wireless Clients (${site_desc})"`)** and falls back to a
degenerate single-part only because the renderer isn't verified.

**Assessment: grammar generalizes, renderer is the blocker.** The
loader happily accepts the composite; the renderer would reject or
emit wrong output. This is the exact capture-gap Synology axis 3
flagged.

**UniFi adds concrete motivation:** Wireless Client Aggregate
*really wants* a composite name for operator clarity. It's the
first case we've hit where the single-part form reads badly.

**Recommendation (unchanged from Synology):** flag composite name
expression rendering as a tooling task once MPB UI is available for
live verification. This is a renderer task, not a loader task. **No
grammar change needed.**

**Verdict: grammar generalizes; renderer extension is the deferred
item. UniFi provides motivation for picking it up.**

### Axis 4 — Events split (threshold → factory symptoms/alerts; API-pulled → MPB)

**Current principle (codified in Synology doctrine):** threshold
conditions always go to factory symptoms/alerts; MPB events are
only for API-pulled event records.

**UniFi exercise:** clean application. 14 threshold conditions go
to factory symptoms/alerts. Tier 2 API-pulled events (from
`stat/event` / `stat/alarm`) are deferred to v1.1 but when they
land they'll exercise the MPB event path.

**Assessment: framework-general principle confirmed at second MP.
No change.**

**Verdict: axis 4 generalizes cleanly. No framework change.**

### Axis 5 — Metric source (the big UniFi stressor)

**Current grammar:** `MetricSourceDef` with `metricset`, `path`, and
reserved fields `aggregate`, `extract`, `compose`. Shorthand string
expansion supported. **Only scalar-path supported at render.**

**UniFi exercise:** UniFi stresses this grammar in two new ways
Synology did not:

1. **Array-filter predicates** (`radio_table_stats[?radio=='ng']`,
   `port_table[?up==true]`, `temperatures[?name=='CPU']`,
   `site_health[?subsystem=='wan']`). These are JMESPath filter
   expressions against arrays of objects.
2. **Array-aggregates** (`port_table[*].poe_power` with
   `aggregate: sum`, `port_table[?up==true]` with `aggregate: count`,
   `radio_table_stats[*].user-num_sta` with `aggregate: sum`).

The **`aggregate` reserved field finally gets exercised** for real.
Synology axis 5 flagged `aggregate: count` as a theoretical need
that never materialized in v1; UniFi needs at least `sum` and
`count` to produce even the basic aggregate scalars on Switch
(`ports_up`, `total_tx_bytes`) without proliferating
object_types.

Additionally:

3. **`compose` reserved field exercised** — Switch
   `poe_budget_remaining = total_max_power - total_poe_power`.
   This is the first real case for the `compose.operator: subtract`
   pattern from Synology axis 5's proposal. Gateway
   `storage_used_pct` is another (division).
4. **Cross-metricSet references** — Gateway's WAN metrics are
   conceptually on Gateway but live on Site's `site_health`
   metricSet. UniFi's v1 ducks this by emitting WAN metrics on Site
   directly, but the shape (one object_type wants metrics sourced
   from another object_type's metricSet) is a known pattern.

**Assessment: framework grammar has placeholders for all three
cases (`aggregate`, `compose`, nested paths), but the renderer only
implements scalar paths.** UniFi v1 is bottlenecked on rendering,
not grammar.

**TOOLSET GAP (concrete, v1-blocking if v1 needs aggregates):**
renderer must support:
- JMESPath filter predicates in `source.path` — `[?key=='value']`
- Array wildcards with `aggregate: sum` and `aggregate: count`
- `compose` with at least `subtract` and `divide` operators

Without these the v1 metric catalog has to shrink to:
- AP: drop per-radio breakouts, keep only device-level scalars
  (CPU, memory, uptime, state).
- Switch: drop aggregate port counters, keep only device-level
  scalars (same set). No PoE budget.
- Gateway: drop `temperatures[?name=='CPU']` filter, keep only
  whatever top-level temperature field the API exposes (may need
  to just pick `temperatures[0].value` and live with it). Drop
  storage_used_pct (compose).
- Site `site_health` subsystem breakout requires `[?subsystem=='wlan']`
  filters — if those don't render, the whole `site_health`
  metricSet becomes unusable except for "pull the entire response
  as a blob and display raw." That's a dead-end.

**This is the MOST IMPORTANT UniFi design finding.** If the
renderer doesn't grow these capabilities, v1 is unshippable beyond
a toy 10-metric MP. Synology gets away without them because DSM's
responses are already scalar-flat — UniFi's responses are
inherently array-filtered.

**Recommendation: escalate to tooling as a pre-authoring dependency.**
Before mp-author picks up UniFi v1, tooling needs to:
1. Extend `MetricSourceDef` renderer to support JMESPath filter
   predicates in `path`.
2. Extend renderer to honor `aggregate: sum | count | avg | max |
   min` on array-wildcard paths.
3. Extend renderer to honor `compose` with `add | subtract |
   multiply | divide` operators referencing other metric sources
   on the same object_type.

If any of the three can't land in one tooling pass, v1 scope
shrinks accordingly and the shrinkage is documented in the design.
**mp-author cannot heroically work around this — the grammar fails
at the wire level, not at the YAML level.**

**Verdict: axis 5 is the v1 gating item. Framework extension
required before mp-author begins.**

### Axis 6 — Identifier schema (single-field MAC on all device types)

**Current grammar:** structured `IdentifierDef` list with shorthand
expansion.

**UniFi exercise:** every device object_type uses single-field MAC.
UniFi Site uses single-field `site_name`. Wireless Client Aggregate
uses single-field `site_name` (degenerate — one per site).

**Assessment: trivial exercise; no stress.** MAC is stable, unique,
canonical. UniFi's simplicity here contrasts Synology's dual-field
(`pool_id + pool_path`) and actually **validates that multi-field
identifiers aren't the common case** — the framework's support for
them is future-proofing, not baseline.

**Verdict: axis 6 generalizes trivially. No framework change.**

### Axis 7 — World-object identity (exercises `connection_address` tier for the first time)

**Current grammar:** `world_identity: {tier: system_issued |
connection_address | display_name, source: "metricset:X.Y"}`.

**UniFi exercise:** Site uses `tier: connection_address` with
`source: "metricset:sites_self.name"`. This is **the first time the
framework exercises a tier other than `system_issued`** — Synology
uses `system_issued` (Diskstation serial).

**Why `connection_address` and not `system_issued`?** A UniFi Site
is a logical construct inside a controller. It has no hardware
serial number. The closest "stable identifier" is the site's `name`
field (not `desc`), which is API-stable but is derived from the
controller URL the operator entered at adapter-instance setup time.
That's the exact semantic of `connection_address`: the identity
traces to the adapter-instance configuration.

**Why not `display_name`?** `display_name` is the last-resort tier
reserved for operator-renamable display strings. The site's `name`
field (the API-stable internal key) is not renamable without
recreating the site.

**Assessment: the three-tier hierarchy works.** Synology needed
tier 1 (system_issued); UniFi needs tier 2 (connection_address);
the third tier (display_name) will come when some MP targets
software-defined objects with no serial and no natural URL (e.g., a
Linux host MP keyed by hostname). **Three MPs = three tiers
exercised = grammar validated.**

**Verdict: axis 7 generalizes. UniFi provides the first non-
system_issued example.** The framework review can now concretely
answer "when do you use each tier?" with two examples instead of
one.

### Axis 8 — Request param ordering (ordered `{key, value}` list)

**UniFi exercise:** unchanged — UniFi uses `{key, value}` lists
uniformly. The `${configuration.site}` path substitution is the
new pattern, but it's a path-level template, not a param-level one.

**Verdict: axis 8 generalizes. No change.**

### Axis 9 — Bundled content split (basic `.pak` dashboard + rich factory dashboard)

**UniFi exercise:** v1 ships a basic device-liveness dashboard in
the `.pak` (heatmap of device states, site health scoreboard).
Rich dashboards — per-AP radio utilization, per-switch port
traffic, client count over time — ship via the factory content
pipeline post-install.

**Verdict: axis 9 generalizes cleanly. Confirms the doctrine.**

### Axis 10 — Phase-naming convention

**UniFi state:** this design artifact does **not** use Synology's
"Phase 4.1.5 / 4.1.7 / 4.1.8" references. Where Synology referenced
phases, this design references **framework capabilities by name**
(e.g., "Option C chaining grammar", "axis 5 renderer extension",
"bearer_token preset with custom inject"). Scott's Synology axis 10
recommendation — "for future design artifacts (starting with the
NEXT MP), adopt the capability-first convention from day one" — is
honored here.

**Verdict: convention adopted. This design is the first to practice
it.**

### Axis 11 — Primary selection semantics (all list objects have exactly one primary)

**Current grammar:** exactly one `primary: true` per list
object_type; singletons may have zero or one.

**UniFi exercise:**
- UniFi Site (singleton, `is_world: true`): 2 metricSets, neither
  flagged primary (validator permits zero primaries on singletons).
- AP / Switch / Gateway (list objects): 1 metricSet each, flagged
  primary: true. No chained metricSets in v1 to complicate.
- Wireless Client Aggregate (singleton 0:1): 1 metricSet, primary
  optional. Listed as primary for renderer clarity.

**Assessment: trivial exercise.** No chained metricSets means no
primary-vs-chained ambiguity. Framework rule "exactly one primary
per list object" applies unambiguously.

**Verdict: axis 11 generalizes. UniFi doesn't stress it.**

### Axis 12 — Request reuse across object_types (stressed further than Synology)

**Synology baseline:** `storage_load_info` consumed by 3
object_types (Storage Pool, Volume, Disk) at different list_paths.

**UniFi exercise:** `stat_device` consumed by 3 object_types (AP,
Switch, Gateway) at three different list_paths. `site_health`
consumed by 2 object_types (Site, Wireless Client Aggregate) at
filtering list_paths that target different subsystem rows.

**Net fan-out:** UniFi's 5 object_types are fed by only 4 HTTP
requests per collection cycle. That is a **1.25:1
object_type:request ratio**, versus Synology's 7 object_types /
11 requests = 0.63:1. UniFi is a stronger example of the
one-request-many-consumer scaling property.

**Assessment: framework-general, strongly validated at MP #2.**
The Option C refactor's core scaling win plays out more cleanly on
UniFi than on Synology. Synology's chain-heavy pattern was an
outlier.

**Verdict: axis 12 generalizes. UniFi provides the cleaner
example to reference in framework documentation.**

### Summary of framework-vs-UniFi findings

| Axis | UniFi exercise | Grammar adequate? | Signal |
|---|---|---|---|
| 1. Auth flow | `bearer_token` + custom `X-API-Key` inject (primary); `cookie_session` + CSRF (fallback) | **Yes** | Generalizes. Minor future `api_key_header` preset alias might improve clarity. |
| 2. Relationship scopes | 4 × `adapter_instance`; 0 × `field_match` (topology deferred) | **Yes** | Generalizes. Cross-adapter case remains unexercised (blocked by scope). |
| 3. Name expression parts | Single-part only (composite desired for one case) | Loader yes; renderer **no** | Renderer extension still deferred; UniFi provides motivation. |
| 4. Events split | Threshold → symptoms/alerts; API-pulled deferred | **Yes** | Confirms doctrine at second MP. |
| 5. Metric source (paths, aggregate, compose) | JMESPath filters, `aggregate: sum/count`, `compose: subtract/divide` all needed | Grammar yes; **renderer NO** | **Gating v1.** Renderer extension required before mp-author can proceed. |
| 6. Identifier schema | Single-field MAC / site_name throughout | **Yes** | Confirms multi-field is the rare case. |
| 7. World-object identity | `tier: connection_address` (first non-system_issued) | **Yes** | Validates three-tier hierarchy with second concrete example. |
| 8. Request param ordering | Ordered `{key,value}` lists | **Yes** | Unchanged. |
| 9. Bundled content split | Basic dashboard in `.pak`, rich via factory pipeline | **Yes** | Confirms doctrine. |
| 10. Phase-naming | This design uses capability-first language | **Yes** | First artifact practicing the convention. |
| 11. Primary selection | Exactly one per list object; zero on singletons | **Yes** | Trivial (no chains in v1). |
| 12. Request reuse across object_types | 5 object_types fed by 4 requests; two requests fan out to 3 consumers each | **Yes** | Cleaner scaling example than Synology. |

**Headline:** 11 of 12 axes generalize cleanly. Axis 5 (metric
source renderer) is the gating v1 framework extension. Axis 3
(composite name expression) is a deferred renderer item UniFi
motivates but doesn't block on. No grammar-level extensions needed
— everything stresses the renderer, not the loader.

## Key Risks

1. **Axis 5 renderer gap (the v1-gating risk).** UniFi cannot ship
   a useful v1 without renderer support for JMESPath filter paths,
   `aggregate: sum/count`, and `compose: subtract/divide` on
   `MetricSourceDef`. Without these, v1 collapses to a ~10-scalar-
   metric toy MP. **Escalate to tooling as a pre-mp-author
   dependency.** See axis 5 section above for the specific renderer
   tasks.

2. **MPB CSRF-rotation ceiling for fallback auth.** If Scott's
   controller is below Network Application v9.3.43, the
   cookie_session fallback is read-only-only. The moment any write
   call enters scope (future MP expansion), this breaks. **Prefer
   X-API-Key** — the briefing's recommendation. Document the
   constraint in the MP's README so operators know they can't add
   write-based content on pre-9.3.43 controllers.

3. **Network Application version ambiguity on Navani's recon.**
   The briefing §5 flags "Network app 5.0.16" as probably a
   UniFi-OS / Network-App version conflation. v1 authoring should
   not start until `GET /proxy/network/api/s/default/stat/sysinfo`
   has been run and the `version` field read. This changes which
   auth path is viable. **Pre-authoring task — Scott or
   api-cartographer to run before mp-author picks up the design.**

4. **Classic API undocumented + field-level churn.** The classic
   `/api/s/{site}/` surface is community-reverse-engineered; field
   names have changed across Network Application releases. v1
   metric paths are grounded in the briefing which itself cites
   UnPoller and aiounifi. **Each new Network Application version
   could break one or more metric paths.** aiounifi v90 in March
   2026 is a proxy signal — community tooling rebases often.
   Mitigation: prefer the integration API (`/proxy/network/integration/v1/`)
   where possible; document which fields came from which source so
   post-mortem debugging is possible.

5. **Cameras deferred to v1.1 (Protect API is different).** Protect
   has a separate auth context (`/proxy/protect/` with its own
   bootstrap + WebSocket update stream). Shipping a v1 that
   "monitors UniFi" without cameras is a readable scope cut;
   document prominently in README.

6. **Events deferred to v1.1 (time-windowing complexity).** The
   3000-result cap on `stat/event` + time-window requirement needs
   api-cartographer to verify the right polling shape before MPB
   events become authorable.

7. **Wireless Client Aggregate metricSet conflict.** Site and
   Wireless Client Aggregate both want to consume `site_health`.
   Two resolutions (rename or delete the object_type). **mp-author
   to decide with Scott** — leaning toward deleting the
   object_type and folding metrics onto Site. Simpler data model,
   matches Grafana/UnPoller convention.

8. **Per-metricSet cadence grammar doesn't exist.** The briefing
   recommends 30s / 5min / 15min cadence tiering. The framework
   only supports one collection interval per adapter instance.
   v1 picks 60s as compromise. **Per-metricSet cadence is a v2
   grammar extension** — flag for future framework work.

9. **UniFi adapter JAR (same class of problem as Synology).** The
   Synology MP is blocked on extracting an adapter JAR via the
   devel-lab MPB UI. UniFi will face the identical extraction
   step once Synology clears it, because the adapter-JAR-per-
   adapter-kind pattern is inherent to MPB. **Document as a known
   build-step, not a design risk** — it's pipeline plumbing, not
   framework design.

10. **No api-cartographer pass yet for UniFi.** The design is
    grounded in Khriss's briefing plus published community sources
    (UnPoller, aiounifi, ubntwiki). Every metric path in this
    design should survive `api-cartographer` running against
    `unifi.int.sentania.net` — but path-level detail (exact
    casing, nested-object shapes, array-vs-scalar) is not
    live-confirmed. **mp-author should request an api-cartographer
    pass before authoring the metric tables verbatim.**

11. **Composite name expression not yet rendered.** Same as
    Synology axis 3; UniFi motivates fixing it but doesn't block
    on it. Wireless Client Aggregate accepts a degenerate single-
    metric name for v1.

12. **Cross-metricSet metric emission is not supported.** Gateway's
    WAN metrics logically belong on Gateway but live on Site's
    `site_health` response. v1 works around by emitting the WAN
    metrics on Site directly. If product/UX wants WAN-on-Gateway,
    that's a framework extension. **Not a blocker; document as
    design trade-off.**

## Framework-capability prerequisites summary

For mp-author to take this design and produce shippable YAML,
the following tooling work must precede authoring:

| Capability | Tooling owner | Blocks v1? | Notes |
|---|---|---|---|
| `MetricSourceDef` renderer: JMESPath filter predicates (`[?key=='value']`) | tooling | **Yes** | Required for AP radio, Switch port, Gateway temp, Site subsystem breakouts. |
| `MetricSourceDef` renderer: array-wildcard + `aggregate: sum/count` | tooling | **Yes** | Required for Switch aggregate port counters, total client counts. |
| `MetricSourceDef` renderer: `compose` with basic operators | tooling | Partial (scope-shrink acceptable) | PoE budget remaining, storage usage %. v1 can ship without these two metrics. |
| Composite multi-part name_expression renderer | tooling | No | UniFi single-metric fallback works; revisit when live-testable. |
| UniFi adapter JAR extracted from devel-lab MPB UI | Scott (manual) | **Yes** | Same class as Synology JAR blocker. |
| UniFi API map under `context/api-maps/unifi-*.md` | api-cartographer | Strongly recommended | Grounds the design's metric paths in live API response shapes. |
| Live-verified controller Network Application version | Scott / api-cartographer | **Yes** | Decides X-API-Key vs cookie_session primary auth path. |

Framework capabilities whose grammar is in place but whose renderer
is v1-gating are marked **Yes**. Those are the tooling-agent tasks
that must land before mp-author begins.

## Open questions for Scott before mp-author proceeds

1. **Wireless Client Aggregate — keep as object_type or fold onto
   Site?** The `site_health` metricSet-reuse conflict has two clean
   resolutions; folding onto Site is simpler, matches UnPoller
   convention, loses "Wireless Clients" as a first-class thing but
   gains simplicity. Recommend fold — confirm.

2. **Cameras in v1.1 or later?** v1 defers cameras (Protect API
   different). Is v1.1 the right landing (next MP iteration after
   v1 ships), or does Scott want cameras pushed to v2 / a separate
   MP entirely? Protect is a big enough surface that a separate
   "UniFi Protect MP" is arguable.

3. **Axis 5 renderer extension scope envelope.** If tooling can
   only deliver two of the three axis-5 renderer items in one pass
   (filter-predicates, aggregate, compose), which two matter most?
   Recommendation: filter-predicates (unblocks most metrics) and
   aggregate (unblocks Switch aggregates); defer compose to v1.1
   and drop `poe_budget_remaining` + `storage_used_pct` from v1.

4. **`api_key_header` preset alias.** Axis 1 flags that
   `bearer_token` + custom `X-API-Key` inject reads awkwardly in
   YAML even though it validates. Should the framework add an
   `api_key_header` preset as a readability alias when a third MP
   hits the same pattern, or is that naming churn?

5. **Per-metricSet cadence grammar.** The briefing recommends
   30s / 5min / 15min tiering. The framework only supports a single
   interval. Does Scott want per-metricSet cadence as a v2
   framework extension, or is the single-interval-per-adapter
   limitation acceptable long-term (forcing authors to pick the
   finest-grained cadence they need)?

6. **api-cartographer pass.** The design is briefing-grounded, not
   live-grounded. Should we green-light an api-cartographer pass
   against `unifi.int.sentania.net` now (parallel work while
   Synology JAR remains blocked), or hold until MPB install parity
   is established on MP #1?

7. **Integration API vs classic API default.** v1 leads with
   X-API-Key (integration API) as primary auth. Does Scott want to
   reverse that — classic cookie_session as primary for broader
   controller-version compatibility, with X-API-Key as opt-in?
   (Briefing recommends integration-API-preferred; design follows
   that; confirming.)

All seven questions are resolvable by Scott in a single
conversation; none require additional research to answer. Once
resolved, this design feeds mp-author once axis-5 renderer work
lands.
