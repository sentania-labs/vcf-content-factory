# Design Artifact: Cloudflare Management Pack v1

**Status.** mp-author-ready (revised: Status Component Group dropped per dual-hostname limitation).

**MP display name:** `VCF Content Factory Cloudflare`
(per CLAUDE.md hard rule #5 -- MPs use prose-form `VCF Content Factory
<name>`, no brackets.)

**Target MP filename:** `content/managementpacks/cloudflare.yaml`
**Adapter kind:** `mpb_vcf_content_factory_cloudflare`
**Bundled content:** none in v1 (factory dashboards ship separately).

---

## Original Request

Track and view DNS queries against Cloudflare-hosted DNS domains,
monitor Cloudflare Pages analytics (deployments, status), and monitor
Cloudflare service health via the status page API. This is also
exercising the MPB pipeline end-to-end with a new target.

---

## Interview Answers

| Question | Answer | Source |
|---|---|---|
| Monitoring scope | DNS Analytics per-zone, HTTP traffic metrics per-zone (from GraphQL), Pages project deployment status, Cloudflare platform health (status page). | User requirements |
| Object granularity | Zone is first-class with DNS + HTTP metrics. Pages Project is first-class with latest deployment flattened as properties. Status Component Group is first-class (group-level only). Status leaf components deferred to v2. | User scope decisions |
| Relationship topology | Shallow 2-level tree. Account is adapter-instance-level (no separate object). Zone and Pages Project are peer-level under adapter instance. Status Component Group is peer-level under adapter instance. | Design decision -- follows UniFi/Synology precedent |
| Cross-adapter relationships | None in v1. | User scope |
| Events | v1 includes MPB events for zone status changes and status component degradation. Events are design-time only -- pak builds strip them (known TOOLSET GAP per mpb_pak_structural_reference.md). | Design decision |
| Bundled content | None in .pak. Dashboards ship separately via factory bundles. | Synology/UniFi precedent |
| Collection intervals | 5min for metrics (DNS analytics, GraphQL HTTP, status page). 15min for inventory (zones, pages projects). | API map cadence recommendations |
| Auth | Bearer token (Cloudflare API token). Status page is unauthenticated but bundled into the same adapter (collected unconditionally). | API map connection section |
| Deployment as separate object | Flatten latest deployment into Pages Project properties. Build-time tracking as separate Deployment object deferred to v2. | User scope decision |
| Status component scope | Group-level only (~10-15 groups vs ~300 total components). Leaf components as v2 expansion. | User scope decision + API map recommendation |

---

## Design Decisions

### REVISION (2026-05-16): Status Component Group dropped

The MPB adapter does not support requests to a hostname other than
the configured base URL. Since Status Component Group requires
`www.cloudflarestatus.com` while all other objects use
`api.cloudflare.com`, it has been dropped from v1. This eliminates
Risk #1 (dual-hostname) and simplifies the MP to 2 object types:
Zone and Pages Project. The status page could be a separate MP in
the future.

Affected sections below are marked `[DROPPED]`.

### 1. Account is the adapter instance, not a separate object

The Cloudflare API scopes everything by account (via API token
permissions) or by zone. There is no dedicated "list accounts"
endpoint -- account identity is embedded in zone responses. One
adapter instance = one Cloudflare account. Account-level properties
(`account.id`, `account.name`) are captured on the adapter instance
itself (via connection config), not as a separate object kind.

### 2. No `is_world` kind

Same reasoning as UniFi v2 and Synology v2. The adapter instance is
the implicit topology root. No cross-instance roll-up requirement in
v1. A `Cloudflare World` kind can be added in v2 if fleet-level
aggregation is needed.

### 3. [DROPPED] Two API surfaces, one adapter

~~The Cloudflare v4 REST/GraphQL API (authenticated) and the
Cloudflare Status Page API (unauthenticated, Atlassian Statuspage
format) are consumed by the same adapter instance.~~ Dropped: MPB
does not support dual-hostname collection. v1 uses only
`api.cloudflare.com`.

### 4. [DROPPED] Status components: groups only in v1

~~The status page returns ~300 components.~~ Dropped: Status
Component Group removed from v1. Could be a separate MP targeting
`www.cloudflarestatus.com` with no auth.

### 5. Deployment flattened into Pages Project

The `latest_deployment` object is embedded in the Pages Project list
response. Rather than modeling Deployment as a separate object type
(which would require a per-project detail call or cross-object
chaining), v1 flattens the latest deployment's key fields as
properties on the Pages Project. This keeps request count low and
the object model simple.

### 6. GraphQL for HTTP metrics

The GraphQL Analytics API (`POST /graphql`) provides HTTP traffic
metrics (requests, bytes, cached, threats, encrypted) per zone.
This is a POST endpoint but the operation is read-only and
idempotent. The adapter sends one GraphQL query per collection cycle
that can batch multiple zones. The dataset used is
`httpRequests1hGroups` (1-hour resolution, suitable for 5-min
collection with the latest hour's aggregate).

### 7. DNS Analytics uses aggregate report

The aggregate endpoint (`GET /zones/{zone_id}/dns_analytics/report`)
is preferred over the time-series endpoint for per-cycle collection.
Query window is `since=-5minutes&until=now` to get the most recent
5-minute aggregate. One request per zone per cycle.

---

## Object Model

### Object tree

```
Adapter Instance (implicit, MPB-managed; represents one Cloudflare account)
|
+-- [peer graph, parented implicitly by adapter instance]
    |
    +-- Zone (list, from GET /zones + enrichment from DNS analytics + GraphQL)
    |     metricSets: zone_inventory (primary, list from GET /zones)
    |                 zone_dns_analytics (chained, per-zone DNS metrics)
    |                 zone_http_analytics (chained, per-zone GraphQL HTTP metrics)
    |     ~14 metrics + ~14 properties. DNS queries, response times,
    |     HTTP traffic, cache ratios, threat counts.
    |
    +-- Pages Project (list, from GET /accounts/{account_id}/pages/projects)
    |     metricSets: pages_inventory (primary, list)
    |     Latest deployment flattened as properties.
    |     ~2 metrics + ~14 properties.
    |
    +-- [DROPPED] Status Component Group
```

Three object_types total: 2 INTERNAL + 0 ARIA_OPS. `world_count = 0`.

### Why no `is_world`

No root-device metrics to model. Account identity is implicit in the
adapter instance (one API token = one account). No fleet-level
roll-up in v1.

### Identifiers and name expressions per kind

| Object | Identifier(s) | name_expression | Source |
|---|---|---|---|
| Zone | `zone_id` from `result[].id` (32-char hex, globally unique, stable) | `zone_name` (domain name, e.g. `example.com`) | API map endpoint #1 |
| Pages Project | `project_id` from `result[].id` (UUID, globally unique, stable) | `project_name` (from `result[].name`, unique within account) | API map endpoint #4 |
| Status Component Group | `component_id` from `components[].id` (Statuspage component ID, stable string) | `component_name` (from `components[].name`, e.g. "Cloudflare DNS") | API map endpoint #6 |

All identifiers are stable across collection cycles: Cloudflare zone
IDs are immutable hex strings, Pages project IDs are UUIDs, and
Statuspage component IDs are stable strings assigned at component
creation.

### Relationships

```
relationships: []
  # Zero explicit relationships in v1.
  # All three object types parent the adapter instance implicitly
  # (mechanism #1 from mpb_relationships.md).
  #
  # Zone and Pages Project both belong to the same account (the
  # adapter instance). No inter-object join keys exist between
  # Zone and Pages Project.
  #
  # Status Component Group is from a completely different API
  # surface (unauthenticated status page) and has no join keys
  # to Zone or Pages Project.
  #
  # v2 consideration: if Status Components (leaf) are added as a
  # separate object type, a field_match relationship from
  # Status Component Group -> Status Component via group_id would
  # be added:
  #   - parent: status_component_group
  #     child: status_component
  #     scope: field_match
  #     parent_expression: component_id
  #     child_expression: group_id
```

Final relationship count: **0 explicit relationships in v1.**

### Singleton vs list shape per kind

| Object | Shape | Renders as | Why |
|---|---|---|---|
| Zone | list | `isListObject: true`; primary metricSet from GET /zones, two chained metricSets for DNS and HTTP analytics enrichment | N zones per account |
| Pages Project | list | `isListObject: true`; one primary metricSet from GET /accounts/.../pages/projects | N projects per account |
| ~~Status Component Group~~ | [DROPPED] | ~~from GET /summary.json~~ | Dropped: dual-hostname not supported |

---

## Object Type Details

### Zone

- **Key:** `zone`
- **Identifier:** `zone_id` (from `result[].id`, 32-char hex)
- **Name expression:** `zone_name` (domain name)
- **Icon hint:** `world` -- zones represent DNS domains, a globe/world
  silhouette fits the "internet domain" concept.
- **Source request(s):** `get_zones` (inventory), `get_dns_analytics`
  (chained per-zone), `get_http_analytics` (chained per-zone)
- **metricSets:**
  - `zone_inventory` -- primary, list from `get_zones`, `list_path: "result"`
  - `zone_dns_analytics` -- chained from `zone_inventory`, per-zone DNS
    metrics. Bind: `zone_id` from `zone_inventory.id`. Request path uses
    `${chain.zone_id}` substitution.
  - `zone_http_analytics` -- chained from `zone_inventory`, per-zone HTTP
    metrics from GraphQL. Bind: `zone_id` from `zone_inventory.id`.

#### Metrics and Properties

| key | label | usage | type | source | api map ref |
|---|---|---|---|---|---|
| `zone_id` | Zone ID | P | STRING | `zone_inventory.id` | endpoint #1 |
| `zone_name` | Zone Name | P | STRING | `zone_inventory.name` | endpoint #1 |
| `zone_status` | Zone Status | P | STRING | `zone_inventory.status` | endpoint #1 (active, pending, initializing, moved) |
| `zone_type` | Zone Type | P | STRING | `zone_inventory.type` | endpoint #1 (full, partial, secondary, internal) |
| `zone_paused` | Zone Paused | P | STRING | `zone_inventory.paused` | endpoint #1 |
| `zone_development_mode` | Development Mode | P | STRING | `zone_inventory.development_mode` | endpoint #1 (0=off) |
| `plan_name` | Plan Name | P | STRING | `zone_inventory.plan.name` | endpoint #1 |
| `plan_tier` | Plan Tier | P | STRING | `zone_inventory.plan.legacy_id` | endpoint #1 (free, pro, business, enterprise) |
| `name_servers` | Name Servers | P | STRING | `zone_inventory.name_servers` | endpoint #1 (array, joined as comma-separated) |
| `account_name` | Account Name | P | STRING | `zone_inventory.account.name` | endpoint #1 |
| `owner_email` | Owner Email | P | STRING | `zone_inventory.owner.email` | endpoint #1 |
| `created_on` | Created On | P | STRING | `zone_inventory.created_on` | endpoint #1 |
| `activated_on` | Activated On | P | STRING | `zone_inventory.activated_on` | endpoint #1 |
| `modified_on` | Modified On | P | STRING | `zone_inventory.modified_on` | endpoint #1 |
| `dns_query_count` | DNS Queries | M | NUMBER | `zone_dns_analytics.result.totals.queryCount` | endpoint #2 |
| `dns_response_time_avg` | DNS Avg Response Time | M | NUMBER | `zone_dns_analytics.result.totals.responseTimeAvg` | endpoint #2 (unit unverified, likely ms) |
| `http_requests` | HTTP Requests | M | NUMBER | `zone_http_analytics.data.viewer.zones[0].<dataset>[0].sum.requests` | endpoint #7 |
| `http_bytes` | HTTP Bytes | M | NUMBER | `zone_http_analytics.data.viewer.zones[0].<dataset>[0].sum.bytes` | endpoint #7 |
| `http_cached_requests` | HTTP Cached Requests | M | NUMBER | `zone_http_analytics.data.viewer.zones[0].<dataset>[0].sum.cachedRequests` | endpoint #7 |
| `http_cached_bytes` | HTTP Cached Bytes | M | NUMBER | `zone_http_analytics.data.viewer.zones[0].<dataset>[0].sum.cachedBytes` | endpoint #7 |
| `http_threats` | HTTP Threats | M | NUMBER | `zone_http_analytics.data.viewer.zones[0].<dataset>[0].sum.threats` | endpoint #7 |
| `http_encrypted_requests` | HTTPS Requests | M | NUMBER | `zone_http_analytics.data.viewer.zones[0].<dataset>[0].sum.encryptedRequests` | endpoint #7 |

**Zone metric count: 8 METRIC + 14 PROPERTY = 22 total.**

**Derived metrics (supermetric candidates, not in-pack):**
- `cache_hit_ratio` = `http_cached_requests / http_requests` -- factory SM
- `encryption_ratio` = `http_encrypted_requests / http_requests` -- factory SM

### Pages Project

- **Key:** `pages_project`
- **Identifier:** `project_id` (from `result[].id`, UUID)
- **Name expression:** `project_name` (from `result[].name`)
- **Icon hint:** TOOLSET GAP: need new hint `deployment` -- a
  rectangular page/document silhouette with a small upward-pointing
  deploy arrow, representing web deployment artifacts. Closest existing
  hints (`datastore`, `host_system`) do not visually fit a web
  deployment project. Fallback to `default` if the orchestrator
  defers the icon.
- **Source request(s):** `get_pages_projects` (inventory + latest deployment)
- **metricSets:**
  - `pages_inventory` -- primary, list from `get_pages_projects`,
    `list_path: "result"`

#### Metrics and Properties

| key | label | usage | type | source | api map ref |
|---|---|---|---|---|---|
| `project_id` | Project ID | P | STRING | `pages_inventory.id` | endpoint #4 |
| `project_name` | Project Name | P | STRING | `pages_inventory.name` | endpoint #4 |
| `subdomain` | Subdomain | P | STRING | `pages_inventory.subdomain` | endpoint #4 (e.g. my-project.pages.dev) |
| `production_branch` | Production Branch | P | STRING | `pages_inventory.production_branch` | endpoint #4 |
| `created_on` | Created On | P | STRING | `pages_inventory.created_on` | endpoint #4 |
| `source_type` | Source Type | P | STRING | `pages_inventory.source.type` | endpoint #4 (github, gitlab) |
| `source_repo` | Source Repository | P | STRING | `pages_inventory.source.config.repo_name` | endpoint #4 |
| `source_owner` | Source Owner | P | STRING | `pages_inventory.source.config.owner` | endpoint #4 |
| `build_command` | Build Command | P | STRING | `pages_inventory.build_config.build_command` | endpoint #4 |
| `latest_deploy_env` | Latest Deploy Environment | P | STRING | `pages_inventory.latest_deployment.environment` | endpoint #4 (production, preview) |
| `latest_deploy_url` | Latest Deploy URL | P | STRING | `pages_inventory.latest_deployment.url` | endpoint #4 |
| `latest_deploy_trigger` | Latest Deploy Trigger | P | STRING | `pages_inventory.latest_deployment.deployment_trigger.type` | endpoint #4 (ad_hoc, etc.) |
| `latest_deploy_branch` | Latest Deploy Branch | P | STRING | `pages_inventory.latest_deployment.deployment_trigger.metadata.branch` | endpoint #4 |
| `latest_deploy_commit` | Latest Deploy Commit | P | STRING | `pages_inventory.latest_deployment.deployment_trigger.metadata.commit_hash` | endpoint #4 |
| `latest_deploy_status` | Latest Deploy Status | P | STRING | see derivation note below | endpoint #4 |
| `latest_deploy_created` | Latest Deploy Time | P | STRING | `pages_inventory.latest_deployment.created_on` | endpoint #4 |

**Derivation note for `latest_deploy_status`:** The `stages[]` array
on `latest_deployment` contains 5 stage objects (queued, initialize,
clone_repo, build, deploy) each with a `status` field (idle, active,
success, failure, canceled). The "overall" deployment status is the
status of the last non-idle stage. JMESPath extraction:
`latest_deployment.stages[?status!='idle'] | [-1].status`. If all
stages are idle, the deployment hasn't started yet -- report `idle`.
If the renderer cannot evaluate this JMESPath expression, fall back to
the deploy stage specifically:
`latest_deployment.stages[?name=='deploy'].status | [0]`.

**Pages Project metric count: 0 METRIC + 16 PROPERTY = 16 total.**

No numeric metrics in v1 -- Pages has no traffic/performance counters
on the list endpoint. v2 could add deployment stage durations (derived
from `stages[].started_on` - `stages[].ended_on` timestamps) if the
renderer supports timestamp arithmetic, and web analytics if the
account has `web_analytics_tag` configured.

### [DROPPED] Status Component Group

- **Key:** `status_component_group`
- **Identifier:** `component_id` (from `components[].id`, Statuspage
  component ID, stable string)
- **Name expression:** `component_name` (from `components[].name`)
- **Icon hint:** `gateway` -- status component groups represent service
  health categories, and the shield/gateway silhouette conveys
  "protection/health status" visually. Reuse of `gateway` is
  acceptable here -- the hint is a visual category.
- **Source request(s):** `get_status_summary` (status page)
- **metricSets:**
  - `status_groups` -- primary, list from `get_status_summary`,
    `list_path: "components"` filtered to `[?group==true]` (JMESPath
    filter predicate). Only components where `group` is `true` are
    modeled.

#### Metrics and Properties

| key | label | usage | type | source | api map ref |
|---|---|---|---|---|---|
| `component_id` | Component ID | P | STRING | `status_groups.id` | endpoint #6 |
| `component_name` | Component Name | P | STRING | `status_groups.name` | endpoint #6 |
| `component_status` | Status | P | STRING | `status_groups.status` | endpoint #6 (operational, degraded_performance, partial_outage, major_outage, under_maintenance) |
| `component_description` | Description | P | STRING | `status_groups.description` | endpoint #6 |
| `component_updated_at` | Last Updated | P | STRING | `status_groups.updated_at` | endpoint #6 |
| `child_component_count` | Child Components | M | NUMBER | derived: length of `status_groups.components[]` array | endpoint #6 |
| `component_position` | Position | M | NUMBER | `status_groups.position` | endpoint #6 (sort order) |

**Status Component Group metric count: 2 METRIC + 5 PROPERTY = 7 total.**

**Health mapping for `component_status`:**
- `operational` = GREEN (healthy)
- `degraded_performance` = YELLOW (warning)
- `partial_outage` = ORANGE (degraded)
- `major_outage` = RED (critical)
- `under_maintenance` = GREY (maintenance)

**Derived metric candidate (supermetric, not in-pack):**
- `degraded_child_count` -- count of children in this group whose
  `status != operational`. Requires access to child component data
  within the same response. This is a v2 candidate once leaf
  components are modeled, at which point the join allows a
  supermetric across the parent-child edge.

---

## Request Mapping

| # | Request Name | Method | API Surface | Path | Objects Fed | Cadence | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `get_zones` | GET | v4 REST | `/zones?per_page=50` | Zone (primary) | 15 min | Inventory. Paginate until `page >= total_pages`. Account ID implicit in token scope. |
| 2 | `get_dns_analytics` | GET | v4 REST | `/zones/${chain.zone_id}/dns_analytics/report?metrics=queryCount,responseTimeAvg&since=-5minutes&until=now` | Zone (chained enrichment) | 5 min | Per-zone. Chained from `get_zones`, binds `zone_id`. Returns aggregate totals. |
| 3 | `get_http_analytics` | POST | v4 GraphQL | `/graphql` | Zone (chained enrichment) | 5 min | Per-zone. Chained from `get_zones`, binds `zone_id`. Body contains GraphQL query for `httpRequests1hGroups`. |
| 4 | `get_pages_projects` | GET | v4 REST | `/accounts/${config.account_id}/pages/projects?per_page=25` | Pages Project (primary) | 15 min | Inventory + latest deployment. `account_id` from adapter instance config. |
| ~~5~~ | ~~`get_status_summary`~~ | ~~GET~~ | ~~Status Page~~ | [DROPPED] | ~~Status Component Group~~ | -- | Dropped: dual-hostname not supported by MPB |

**Total requests per 5-min cycle:** 1 (status) + N zones x 2 (DNS + HTTP)
**Total requests per 15-min cycle:** above + 1 (zones inventory) + 1 (pages projects)

**Rate limit concern:** Cloudflare v4 API allows ~1200 requests per
5 minutes. With 2 chained requests per zone per 5-min cycle, the
adapter supports up to ~600 zones before hitting rate limits. For
accounts with 100+ zones, consider adding a configurable zone filter
(by name pattern or status) to limit collection scope.

### Request details

**Request 1: get_zones**
```
GET /zones?per_page=50
Authorization: Bearer ${credentials.api_token}
```
Response: standard v4 envelope, `result[]` is array of zone objects.

**Request 2: get_dns_analytics (chained)**
```
GET /zones/${chain.zone_id}/dns_analytics/report?metrics=queryCount,responseTimeAvg&since=-5minutes&until=now
Authorization: Bearer ${credentials.api_token}
```
Response: v4 envelope, `result.totals` contains aggregate metrics.
Chained from `get_zones`. Bind: `{name: zone_id, from_attribute: id}`.

**Request 3: get_http_analytics (chained)**
```
POST /graphql
Authorization: Bearer ${credentials.api_token}
Content-Type: application/json

{
  "query": "{ viewer { zones(filter: {zoneTag: $zoneTag}) { httpRequests1hGroups(filter: {datetime_gt: $start, datetime_lt: $end}, limit: 1) { sum { requests bytes cachedRequests cachedBytes threats encryptedRequests } } } } }",
  "variables": {
    "zoneTag": "${chain.zone_id}",
    "start": "<5-minutes-ago-ISO>",
    "end": "<now-ISO>"
  }
}
```
Response: GraphQL envelope, data at
`data.viewer.zones[0].httpRequests1hGroups[0].sum.*`.
Chained from `get_zones`. Bind: `{name: zone_id, from_attribute: id}`.

**IMPORTANT: GraphQL time variable injection.** The `$start` and
`$end` variables need dynamic time values (ISO 8601 timestamps for
"5 minutes ago" and "now"). MPB's variable substitution grammar
may not support dynamic time expressions. This is a **potential
TOOLSET CHECK** -- if the adapter runtime cannot inject relative
time values, the query window must be hardcoded to a fixed lookback
(e.g., `-1hour`) or the entire GraphQL approach must be reconsidered.
See Key Risks.

**Request 4: get_pages_projects**
```
GET /accounts/${config.account_id}/pages/projects?per_page=25
Authorization: Bearer ${credentials.api_token}
```
Response: v4 envelope, `result[]` is array of project objects with
embedded `latest_deployment`.

**Request 5: get_status_summary**
```
GET https://www.cloudflarestatus.com/api/v2/summary.json
(no auth headers)
```
Response: raw JSON (no v4 envelope). `components[]` is the top-level
array. Filtered at list_path level to `components[?group==\`true\`]`.

### Account ID injection

The `account_id` needed for Pages API requests must come from
somewhere. Two options:

**Option A (preferred):** Adapter instance configuration field.
The user enters their Cloudflare account ID as a connection parameter
alongside the API token. This is the simplest approach and avoids
an extra API call.

**Option B (auto-discover):** Extract `account.id` from the first
zone response. This works only if the account has at least one zone.
Less reliable.

v1 uses Option A: `account_id` is a required adapter instance
configuration parameter.

---

## Authentication

### Auth YAML shape

```yaml
source:
  port: 443
  ssl: VERIFY           # Cloudflare uses valid public certs
  base_path: "client/v4"
  timeout: 30
  max_retries: 2
  max_concurrent: 10

  auth:
    preset: token        # Bearer token auth, no login/logout
    credentials:
      - {key: api_token, label: API Token, sensitive: true}
      - {key: account_id, label: Account ID, sensitive: false}

    inject:
      - type: header
        name: "Authorization"
        value: "Bearer ${credentials.api_token}"

  test_request:
    method: GET
    path: "/zones?per_page=1"
    # Returns 200 + {"success": true} when token is valid.
```

### Status Page requests

The status page requests use a different base URL
(`https://www.cloudflarestatus.com/api/v2`) and no auth. This is a
**TOOLSET CHECK**: can the adapter make requests to a different
hostname than the configured base URL? MPB typically targets a single
hostname. If the adapter cannot reach a second hostname:

**Fallback:** Drop status page monitoring from the adapter entirely
and recommend users create a separate "no auth" adapter instance
pointing at `www.cloudflarestatus.com`. This would be a simpler,
separate MP (or a second adapter_kind in the same pak -- but that
is not supported by the factory today).

**Alternative fallback:** Make the status page data a factory
dashboard widget that calls the public API directly from the browser
(not collected through the adapter at all). This loses historical
trending but provides real-time visibility.

See Key Risks for full analysis.

---

## Events

Events are defined at design time. Per `mpb_pak_structural_reference.md`,
events are stripped from pak builds (runtime format unknown -- TOOLSET
GAP). Events below are useful for the design-import path and document
the intended alerting model.

| Event | Severity | Condition | Object Type | Notes |
|---|---|---|---|---|
| Zone Status Not Active | WARNING | `zone_status != "active"` | Zone | Fires when a zone leaves active state (pending, moved, initializing). |
| Cloudflare Service Degraded | WARNING | `component_status == "degraded_performance"` | Status Component Group | Cloudflare service experiencing degraded performance. |
| Cloudflare Service Partial Outage | CRITICAL | `component_status == "partial_outage"` | Status Component Group | Cloudflare service in partial outage. |
| Cloudflare Service Major Outage | CRITICAL | `component_status == "major_outage"` | Status Component Group | Cloudflare service in major outage. |
| Pages Deploy Failed | WARNING | `latest_deploy_status == "failure"` | Pages Project | Latest deployment failed. |

**Event count: 5** (design-time only; stripped from pak builds).

**Tier 1 alerting alternative:** Factory symptoms and alerts authored
in `symptoms/` and `alerts/` against the MP's metric keys. Same
pattern as UniFi v2. This path ships regardless of the event TOOLSET
GAP.

---

## Icons

| Object Type | Icon Hint | Rationale |
|---|---|---|
| Zone | `world` | Globe silhouette fits "internet domain / DNS zone". Exists in library. |
| Pages Project | **TOOLSET GAP** | Need new hint `deployment` -- a rectangular page/document silhouette with a small upward-pointing deploy arrow, representing web deployment artifacts. Closest existing: `datastore` (wrong metaphor -- storage, not deployment), `host_system` (wrong -- server hardware). If orchestrator defers, use `default` explicitly. |
| Status Component Group | `gateway` | Shield silhouette conveys service health/protection status. Reuse is appropriate -- the hint is a visual category. |

---

## Bundled Dashboard

None in v1. Factory dashboards ship separately via content bundles.
A v1.1 dashboard would include:

- DNS Analytics widget: queries/s trend per zone, response time trend
- HTTP Traffic widget: requests, bytes, cache hit ratio per zone
- Pages Status widget: project list with latest deploy status
- Cloudflare Health widget: status component group health grid

---

## Key Risks

### 1. Dual-hostname collection (HIGH)

**Risk:** The adapter needs to reach two different hostnames:
`api.cloudflare.com` (authenticated v4 API) and
`www.cloudflarestatus.com` (unauthenticated status page). MPB
adapters typically target a single hostname configured at adapter
instance creation.

**Mitigation:** Verify whether MPB supports absolute URLs in request
paths (overriding the base hostname). If not, the status page
collection must be split into a separate adapter instance or dropped
from the MP. The simplest fallback is two adapter instances: one
for the authenticated Cloudflare API, one for the public status page
(preset: none).

**Impact if unresolved:** Status Component Group object type is
dropped from this MP. DNS + HTTP + Pages monitoring proceeds
normally. Status page monitoring becomes a separate MP or is
deferred.

### 2. GraphQL POST as a chained request (MEDIUM)

**Risk:** Chained metricSets typically use GET requests with URL
path substitution (`${chain.zone_id}` in the path). GraphQL requires
POST with a JSON body containing the zone ID as a variable. The
current factory substrate may not support POST bodies with chain
variable substitution.

**Mitigation:** Verify whether the renderer supports `method: POST`
with `body:` containing `${chain.zone_id}` template tokens. If not,
fall back to DNS-only zone metrics (drop HTTP analytics) or use the
REST v4 zone analytics summary endpoint if one exists (not documented
in the API map -- would need cartographer verification).

**Impact if unresolved:** HTTP traffic metrics (6 of 8 zone metrics)
are dropped. DNS analytics (2 metrics) still flow. Zone becomes a
DNS-only monitoring surface.

### 3. GraphQL time variable injection (MEDIUM)

**Risk:** The GraphQL query needs dynamic time range variables
(`datetime_gt` and `datetime_lt` as ISO 8601 timestamps relative to
"now"). MPB's request grammar may not support dynamic time
expressions.

**Mitigation:** Use a fixed lookback window (e.g., the query always
fetches the last 1 hour of data). The adapter collects the latest
aggregate regardless of the exact time window. Alternatively, if the
adapter runtime supports `${time.now}` and `${time.minus_5m}` tokens,
use those.

**Impact if unresolved:** GraphQL query uses a static time window
(last 1 hour). Data staleness is bounded by the 1-hour window; the
most-recent bucket's sum values still represent current traffic rates.

### 4. JMESPath filter on status page response (LOW)

**Risk:** Filtering `components[?group==true]` requires JMESPath
boolean filter support in the `list_path`. The backtick-boolean
syntax (`[?group==\`true\`]`) is JMESPath standard but may not be
supported by the factory renderer.

**Mitigation:** If JMESPath boolean filters are not supported, collect
all ~300 components and add a property `is_group` that the factory
dashboard can filter on. Alternatively, post-process in a
supermetric. The worst case is 300 objects instead of 15 -- noisy but
functional.

**Impact if unresolved:** Object count increases from ~15 to ~300.
All components are modeled as Status Component Group (name is
misleading for leaf components). v2 would need to rename the object
type to just `status_component` and add `is_group` as a filterable
property.

### 5. API map is documentation-derived, not live-verified (LOW)

**Risk:** The entire API map is inferred from vendor documentation.
Response schemas, field names, GraphQL dataset names, and pagination
behavior have not been verified against a live Cloudflare API. Field
names or response structures may differ from documentation.

**Mitigation:** Before mp-author runs, the orchestrator should
commission an api-cartographer live-verification pass with a
Cloudflare API token. Priority verifications: (a) GraphQL
introspection to confirm `httpRequests1hGroups` dataset and field
names, (b) DNS analytics response to confirm `responseTimeAvg` unit,
(c) Pages project list to confirm `latest_deployment.stages[]`
structure.

**Impact if unresolved:** Field-name mismatches at collection time.
Metrics fail to bind. Requires post-install debugging and a v1.1
patch.

### 6. Pages project account_id dependency (LOW)

**Risk:** The Pages API requires `account_id` in the path. This is
a configuration input from the user, not auto-discovered.

**Mitigation:** Document `account_id` as a required adapter instance
parameter. Users can find it in the Cloudflare dashboard URL
(`dash.cloudflare.com/<account_id>/...`).

**Impact if unresolved:** None if documented. Users who omit the
account_id get no Pages data but zones and status still flow.

---

## v2 Considerations

1. **Status leaf components** -- model ~300 individual components as
   `status_component` object type, child of `status_component_group`
   via `field_match` on `group_id`. Enables per-datacenter and
   per-service health monitoring.

2. **Pages Deployment as separate object** -- model historical
   deployments as `pages_deployment` child of `pages_project`. Requires
   the per-project deployment list endpoint
   (`GET /accounts/{account_id}/pages/projects/{name}/deployments` --
   existence unverified). Enables build-time metrics and deployment
   history trending.

3. **Derived metrics in-pack** -- `cache_hit_ratio` and
   `encryption_ratio` as computed metrics on Zone (if MPB supports
   computed/derived metrics in describe.xml, or as supermetrics).

4. **Workers analytics** -- `workersInvocationsAdaptive` GraphQL
   dataset for serverless function monitoring. New object type or
   enrichment on a Workers Project object.

5. **Firewall/WAF analytics** -- `firewallEventsAdaptiveGroups`
   GraphQL dataset for security event counts per zone.

6. **Cross-adapter relationships** -- Zone objects relating to
   VMWARE VirtualMachines (for "which VMs serve which domains") via
   IP address matching against DNS A records. Advanced use case.

7. **Incident and maintenance tracking** -- The status page
   `summary.json` response includes `incidents[]` and
   `scheduled_maintenances[]` arrays. These could feed VCF Ops events
   or a dedicated Incident object type.

---

## Metric/Property Summary

| Object Type | Metrics | Properties | Total |
|---|---|---|---|
| Zone | 8 | 14 | 22 |
| Pages Project | 0 | 16 | 16 |
| ~~Status Component Group~~ | ~~2~~ | ~~5~~ | ~~7~~ [DROPPED] |
| **Total** | **8** | **30** | **38** |
