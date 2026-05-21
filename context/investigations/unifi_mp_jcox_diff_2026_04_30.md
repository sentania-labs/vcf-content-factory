# UniFi MP — factory v1 vs jcox-au reference diff

Comparison of `tmp/unifi_v1.json` (factory render, 2026-04-30) against
`references/jcox-au_vmware/unifi_MP_Builder_Design.json` (community
reference, untouched during design/authoring per Phase 1.5 calibration
discipline).

## Top-line shape

|                | Factory v1 | jcox-au | Δ |
|---|---|---|---|
| Object kinds   | 4          | 6       | -2 |
| Requests       | 3          | 9       | -6 |
| Chains         | 0          | 7       | -7 |
| Relationships  | 0          | 3       | -3 |
| Events         | 0          | 0       | 0 |
| Metrics total  | 139        | 57      | +82 |

**Two designs, two different bets.** We went deep on per-device
observability; they went broad on per-entity coverage and
cross-adapter relationships.

## Object-kind comparison

**Factory (4):**
- UniFi Site (singleton) — 39 metrics — health subsystems + site agg
- Access Point (list) — 32 metrics — incl per-radio 2.4/5 GHz
- Switch (list) — 21 metrics
- Gateway (list) — 47 metrics — UDM lives here, WAN ports + system

**jcox-au (6):**
- 2 unlabeled scalar kinds (likely empty world stub + singleton)
- UniFi - Devices (list) — 17 metrics, all device types collapsed
- UniFi - Clients (list) — 13 metrics, per-MAC tracking
- UniFi - Networks (list) — 6 metrics, network configs
- UniFi - WiFi Broadcasts (list) — 21 metrics, SSIDs

## Substantive divergences (with classification)

Per Phase 1.5 calibration discipline, each meaningful divergence is
classified as (a) factory output is correct / jcox chose differently,
(b) factory output is wrong / substrate fix needed, or (c) defer to
install-time evidence.

### 1. Device split (3 kinds vs 1) — (a)

We split AP / Switch / Gateway into three first-class kinds; jcox
collapses all device types into one `UniFi - Devices` kind. Both
legitimate. Per-kind split renders better in Ops (type-specific
dashboards, distinct metric schemas — switch has port_table+PoE,
AP has radio_table_stats, gateway has WAN ports). Their consolidated
approach is simpler but every device gets the same metric schema, so
WAN data lives on a row that's also a Switch when it shouldn't be.

**Verdict:** factory choice is the better Ops fit.

### 2. Per-device metric depth (139 vs 57) — (a) factory deeper

We expose `system-stats.cpu/mem`, `temperatures`, `system-load`,
per-radio breakdown, per-port aggregates, per-subsystem health.
jcox's per-device set (17 metrics) is curated to inventory + a few
counters. We're 2.4× their coverage on per-device.

**Verdict:** factory is more comprehensive. No factory bug.

### 3. Clients exposed as objects — (a) explicit scope choice

jcox has `UniFi - Clients` (13 metrics, per-MAC), enabling VM↔Client
correlation. We deferred per-client objects in v2 design due to
unbounded cardinality (guest WiFi MACs every day). Documented in
v1 §"Scope reductions" inherited into v2.

**Verdict:** legitimate scope difference. v2+ work to add Client
kind once cardinality strategy lands (sliding window, retention
cap, etc.).

### 4. Networks / WiFi Broadcasts as objects — (a) explicit scope choice

jcox has `UniFi - Networks` and `UniFi - WiFi Broadcasts` for config
visibility. We deferred config-drift to v3 in v1 scope reductions.

**Verdict:** legitimate scope difference, v3 work.

### 5. Cross-adapter relationships absent — (a) explicit scope, but worth noting

jcox has 3 cross-adapter relationships:
- `vSphere Distributed Port Group → UniFi - Networks`
- `Virtual Machine → UniFi - Clients`
- `UniFi - Devices → UniFi - Clients` (in-pack)

These prove cross-adapter `field_match` works in MPB and shows real
operator value (VM↔WiFi-client correlation). We have zero in v2 by
explicit scope.

**Verdict:** the cross-adapter relationship grammar is on roadmap
(see designs §Future Work — v2 ESXi Host pNIC → Switch port). jcox
shows the pattern works in production.

### 6. 7 chains in jcox vs 0 in ours — (a)

jcox chains heavily: `get-device-detail`, `get-device-statistics`,
`get-broadcasts-detail` are all per-device/per-broadcast follow-up
calls. We chose `stat/device` as a bulk endpoint that returns
everything in one shot. Our zero-chain design is a calibration
finding (the chain grammar from Synology's substrate work isn't
exercised here).

**Verdict:** different API surfaces, both work. Our choice avoids
the per-row API call multiplication; theirs gives them more
flexibility per kind. UniFi's API supports both.

### 7. Question E (one request → multiple list kinds) — (c) install-time evidence

Our `dev_inventory` request feeds AP, Switch, and Gateway with
different `list_path` JMESPath filters. jcox does NOT do this — they
have separate `get-devices-all` / `get-device-detail` chain instead.
This is the first time the factory renders a single request feeding
three distinct list object types. The loader accepts it; whether the
MPB renderer's `dataModelLists` per-type emission is correct is
**unverified until import test on devel**.

**Verdict:** monitor closely at devel install. If MPB rejects,
factory has to either fan out to three requests (mp-author edit) or
tooling adds the multi-list-from-one-request pattern explicitly.

## What's NOT a divergence

- **objectBinding shape**: ours all-null (no chains, none needed);
  theirs has 3 `other`-typed bindings for chain wiring. Both correct
  for their respective designs.
- **Singleton/world distinction**: their 2 unlabeled scalar kinds
  look like empty world stub + singleton. We have one Site singleton,
  no world stub (`world_count: 0` per 2026-04-29 substrate work).
  Cleaner.
- **MP display name format**: theirs untagged ("UniFi - Devices" etc.);
  ours uses `VCF Content Factory UniFi` per updated naming convention.

## Net assessment

**Factory output is structurally sound and meaningfully different from
jcox in legitimate ways.** No (b)-class divergences (no factory bugs
surfaced). Two install-time risks:

- **Question E** — single request → three list kinds, wire-format
  unverified at MPB import (this diff couldn't tell; only devel
  install will).
- **Question C** — Site's `site_meta` metrics deferred (5 of original
  44 Site metrics dropped due to singleton-from-list-row unverified
  behavior).

Phase 1.5 calibration verdict: factory + jcox are siblings, not
clones. Substrate generalized cleanly to Unifi (no Synology-specific
bumps surfaced). The cross-adapter relationships gap is the most
interesting "they have it, we should too" item — material for the
v2 roadmap conversation.

## Diff metadata

- Render: `tmp/unifi_v1.json` (185,536 bytes, 2026-04-30)
- Reference: `references/jcox-au_vmware/unifi_MP_Builder_Design.json`
- Compared by: orchestrator (post-render diff stage)
- Calibration discipline: jcox reference NOT consulted during
  design or authoring; opened only at this diff stage
