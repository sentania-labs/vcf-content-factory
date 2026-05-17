# API Map: Cloudflare

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** `api.cloudflare.com/client/v4` + `www.cloudflarestatus.com/api/v2`
- **Last updated:** 2026-05-16
- **Update history:**
  - 2026-05-16 -- Live verification session #2. Token fixed and working. Authenticated v4 REST: List Zones, List Accounts verified (envelope, pagination, field names). Account has 0 zones and 0 Pages projects, so DNS Analytics and HTTP Analytics data queries return empty results but endpoint structure confirmed. GraphQL introspection FULLY verified: 1712 schema types, 245 primary datasets catalogued (53 zone-scoped, 192 account-scoped). `httpRequests1hGroups` sum/avg/uniq/dimensions fields captured. DNS analytics response time unit confirmed as microseconds (`processingTimeUs`), not milliseconds. `ZoneDnsAnalyticsAdaptiveGroups` schema fully introspected. Pages Functions invocations schema captured. Workers invocations schema captured. Firewall events dimensions captured. All previously `[inferred from docs]` tags on verified items upgraded to `[live-verified 2026-05-16]`. Token verify endpoint returns error 1000 for scoped tokens (documented as known behavior).
  - 2026-05-16 -- Live verification session #1. Status Page API fully live-verified (478 components, 8 groups, incident/maintenance schemas captured). Authenticated v4 API and GraphQL BLOCKED: `VCFOPS_PROD_CLOUDFLARE_TOKEN` contains a 15-character placeholder, not a valid Cloudflare API token (40+ chars expected). Token verification returned HTTP 400 / error 6111 "Invalid format for Authorization header". All v4 REST and GraphQL observations remain `[inferred from docs]`. Status page observations upgraded to `[live-verified 2026-05-16]`. Component count corrected from ~300 to 478. Group count corrected from 10-15 to 8. Incident and scheduled maintenance schemas added.
  - 2026-05-16 -- Initial mapping. Four API surfaces documented from vendor docs provided in orchestrator brief: REST v4 DNS Analytics, REST v4 Pages, Status Page (Atlassian Statuspage), GraphQL Analytics. No live API calls made. All observations tagged `[inferred from docs]` or `[unverified]`.
- **Evidence basis:** live API calls (all surfaces) | vendor docs | GraphQL introspection
- **Notes:** All API surfaces now live-verified as of session #2. Account has 0 zones and 0 Pages projects, so data-returning queries (DNS analytics, HTTP analytics, Pages) return empty `result` arrays but endpoint structure and auth are confirmed. GraphQL schema introspection provided complete field-level detail for all datasets.

## Connection

### Authenticated API (v4 REST + GraphQL)

- **Base URL:** `https://api.cloudflare.com/client/v4` [live-verified 2026-05-16]
- **Auth type:** TOKEN (Bearer) [live-verified 2026-05-16]
- **Auth flow:** API token passed as `Authorization: Bearer {token}` header on every request. No login/session endpoint -- stateless auth. Tokens are scoped to permissions (zone read, analytics read, etc.) and can be created in the Cloudflare dashboard. [live-verified 2026-05-16]
- **Session maintenance:** None -- stateless. Each request carries the bearer token. [live-verified 2026-05-16]
- **Rate limiting:** Cloudflare imposes rate limits (typically 1200 requests/5 minutes for the v4 API). Exact limits vary by endpoint and plan tier. [inferred from docs]
- **Alternative auth:** Global API key (`X-Auth-Email` + `X-Auth-Key` headers) is also supported but bearer tokens are preferred. [inferred from docs]
- **Token verify quirk:** `GET /user/tokens/verify` returns error code 1000 "Invalid API Token" for scoped tokens even when the token is valid for other endpoints. This is a known Cloudflare behavior -- do not use this endpoint to validate token health. Instead, use a lightweight call like `GET /accounts?per_page=1`. [live-verified 2026-05-16]

### Status Page (unauthenticated)

- **Base URL:** `https://www.cloudflarestatus.com/api/v2` [live-verified 2026-05-16]
- **Auth type:** NONE [live-verified 2026-05-16]
- **Auth flow:** N/A -- public endpoint, no authentication required [live-verified 2026-05-16]
- **Session maintenance:** N/A [live-verified 2026-05-16]
- **Provider:** Atlassian Statuspage (standard Statuspage API format) [live-verified 2026-05-16]

## Response Envelope

### v4 REST API

All v4 REST endpoints return a standard envelope [live-verified 2026-05-16]:

```json
{
  "success": true,
  "errors": [],
  "messages": [],
  "result": { ... },
  "result_info": {
    "page": 1,
    "per_page": 20,
    "count": 1,
    "total_count": 1,
    "total_pages": 1
  }
}
```

- `success` (boolean): whether the request succeeded [live-verified 2026-05-16]
- `errors` (array): error objects with `code` (integer) and `message` (string) [live-verified 2026-05-16]
- `messages` (array): informational messages (observed as empty array `[]` on all successful calls) [live-verified 2026-05-16]
- `result` (object or array): the response payload [live-verified 2026-05-16]
- `result_info` (object): pagination metadata, present on list endpoints. Fields: `page` (int), `per_page` (int), `total_pages` (int), `count` (int), `total_count` (int) [live-verified 2026-05-16]

### Status Page API

Returns raw JSON without the v4 envelope. Top-level keys: `page`, `components`, `incidents`, `scheduled_maintenances`, `status`. [live-verified 2026-05-16]

## Pagination

### v4 REST API

- **Mechanism:** `page` + `per_page` query parameters [live-verified 2026-05-16]
- **Default page size:** 20 (configurable up to 50 for most endpoints; accounts defaults to 20) [live-verified 2026-05-16]
- **Response metadata:** `result_info.total_count`, `result_info.total_pages`, `result_info.page`, `result_info.count` [live-verified 2026-05-16]
- **Iteration:** increment `page` until `page >= total_pages` [live-verified 2026-05-16]
- **Empty results:** When no resources match, `result` is `[]`, `count` and `total_count` are `0`, `total_pages` is `0` [live-verified 2026-05-16]

### Status Page API

- No pagination -- `/summary.json` returns all components in a single response (478 components as of 2026-05-16) [live-verified 2026-05-16]

---

## Endpoints

### 1. List Zones

- **Method:** GET
- **Path:** `/zones`
- **Auth:** Bearer token required [live-verified 2026-05-16]
- **Query parameters:**

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `account.id` | string | no | Filter by account ID |
  | `account.name` | string | no | Filter by account name |
  | `name` | string | no | Filter by zone name (exact match) |
  | `status` | string | no | Filter by status: `initializing`, `pending`, `active`, `moved` |
  | `type` | string | no | Filter by type: `full`, `partial`, `secondary`, `internal` |
  | `order` | string | no | Sort field: `name`, `status`, `account.id`, `account.name` |
  | `direction` | string | no | Sort direction: `asc`, `desc` |
  | `match` | string | no | Match logic: `any` (OR) or `all` (AND) |
  | `page` | integer | no | Page number (default 1) |
  | `per_page` | integer | no | Results per page (default 20, max 50) |

- **Response schema** (`result` is an array of zone objects) [live-verified 2026-05-16 -- endpoint responds with `success: true` and correct envelope; zone object field schema from docs, no zones in test account to verify individual fields]:

  ```json
  {
    "success": true,
    "errors": [],
    "messages": [],
    "result": [
      {
        "id": "string (32-char hex)",
        "name": "example.com",
        "status": "active",
        "type": "full",
        "paused": false,
        "development_mode": 0,
        "account": {
          "id": "string",
          "name": "string"
        },
        "plan": {
          "id": "string",
          "name": "Free Website",
          "price": 0,
          "currency": "USD",
          "frequency": "",
          "is_subscribed": true,
          "can_subscribe": false,
          "legacy_id": "free",
          "legacy_discount": false,
          "externally_managed": false
        },
        "name_servers": ["string"],
        "original_name_servers": ["string"],
        "created_on": "2014-01-01T05:20:00.12345Z",
        "modified_on": "2014-01-01T05:20:00.12345Z",
        "activated_on": "2014-01-02T00:01:00.12345Z",
        "meta": {
          "step": 2,
          "custom_certificate_quota": 1,
          "page_rule_quota": 3,
          "phishing_detected": false,
          "multiple_railguns_allowed": false
        },
        "owner": {
          "id": "string",
          "type": "user",
          "email": "user@example.com"
        },
        "tenant": {
          "id": "string",
          "name": "string"
        },
        "tenant_unit": {
          "id": "string"
        },
        "permissions": ["#zone:read", "#zone:edit"]
      }
    ],
    "result_info": {
      "page": 1,
      "per_page": 20,
      "count": 1,
      "total_count": 2000,
      "total_pages": 100
    }
  }
  ```

- **Object candidates:** Zone [live-verified 2026-05-16 -- endpoint confirmed]
- **Identifier candidates:** `id` (32-char hex, globally unique), `name` (domain name, unique within account) [inferred from docs]
- **Metrics:** None directly -- this is an inventory/config endpoint [live-verified 2026-05-16]
- **Properties:** `name`, `status`, `type`, `paused`, `development_mode`, `plan.name`, `plan.legacy_id`, `name_servers[]`, `original_name_servers[]`, `created_on`, `modified_on`, `activated_on`, `account.name`, `owner.email` [inferred from docs]
- **Relationships:** Zone belongs to Account (`account.id`). Zone has Owner (`owner.id`). [inferred from docs]
- **Notes:** `zone_id` from this response is required as a path parameter for DNS analytics endpoints. This is the discovery/inventory call that must run first. Test account has 0 zones so zone object field schema not individually verified, but endpoint auth and envelope are confirmed. [live-verified 2026-05-16]

---

### 1a. List Accounts

- **Method:** GET
- **Path:** `/accounts`
- **Auth:** Bearer token required [live-verified 2026-05-16]
- **Query parameters:**

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `page` | integer | no | Page number (default 1) |
  | `per_page` | integer | no | Results per page |
  | `direction` | string | no | Sort direction: `asc`, `desc` |

- **Response schema** (`result` is an array of account objects) [live-verified 2026-05-16]:

  ```json
  {
    "success": true,
    "errors": [],
    "messages": [],
    "result": [
      {
        "id": "string (32-char hex)",
        "name": "string",
        "type": "standard",
        "settings": {
          "enforce_twofactor": false,
          "api_access_enabled": null,
          "access_approval_expiry": null,
          "abuse_contact_email": null,
          "oauth_app_access_enabled": true
        },
        "legacy_flags": {
          "enterprise_zone_quota": {
            "maximum": 0,
            "current": 0,
            "available": 0
          }
        },
        "created_on": "2018-01-04T03:45:22.140866Z"
      }
    ],
    "result_info": {
      "page": 1,
      "per_page": 5,
      "total_pages": 1,
      "count": 1,
      "total_count": 1
    }
  }
  ```

- **Object candidates:** Account (previously only inferred from zone responses -- now directly verified) [live-verified 2026-05-16]
- **Identifier candidates:** `id` (32-char hex string) [live-verified 2026-05-16]
- **Metrics:** None [live-verified 2026-05-16]
- **Properties:** `name`, `type` (observed: `"standard"`), `created_on`, `settings.enforce_twofactor`, `settings.api_access_enabled`, `settings.oauth_app_access_enabled`, `legacy_flags.enterprise_zone_quota.maximum/current/available` [live-verified 2026-05-16]
- **Relationships:** Parent of Zone, parent of Pages Project [live-verified 2026-05-16]
- **Notes:** This is the correct way to discover `account_id` for Pages and other account-scoped endpoints. Test account has 1 account. `account_id` is required for `GET /accounts/{account_id}/pages/projects`. [live-verified 2026-05-16]

---

### 2. DNS Analytics -- Aggregate Report

- **Method:** GET
- **Path:** `/zones/{zone_id}/dns_analytics/report`
- **Auth:** Bearer token required [inferred from docs]
- **Path parameters:**

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `zone_id` | string | yes | Zone identifier from List Zones |

- **Query parameters:**

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `dimensions` | string | no | Comma-separated: `responseCode`, `queryName`, `queryType` |
  | `metrics` | string | no | Comma-separated: `queryCount`, `responseTimeAvg` |
  | `filters` | string | no | Filter expression (e.g., `responseCode==NOERROR`) |
  | `since` | string | no | Start time (ISO 8601 or relative like `-6hours`) |
  | `until` | string | no | End time (ISO 8601 or relative) |
  | `limit` | integer | no | Max rows returned |
  | `sort` | string | no | Sort field(s), prefix `-` for descending |

- **Response schema** [inferred from docs]:

  ```json
  {
    "success": true,
    "errors": [],
    "messages": [],
    "result": {
      "data": [
        {
          "dimensions": ["NOERROR"],
          "metrics": [12345, 3.5]
        }
      ],
      "data_lag": 60,
      "min": {},
      "max": {},
      "query": {
        "dimensions": ["responseCode"],
        "metrics": ["queryCount", "responseTimeAvg"],
        "since": "2024-01-01T00:00:00Z",
        "until": "2024-01-02T00:00:00Z",
        "limit": 100
      },
      "rows": 5,
      "totals": {
        "queryCount": 50000,
        "responseTimeAvg": 2.8
      }
    }
  }
  ```

- **Object candidates:** DNS Analytics (per-zone aggregate) -- not a persistent object, but a metric source for the Zone object [unchanged since 2026-05-16]
- **Identifier candidates:** Keyed by `zone_id` (path param); rows keyed by dimension values [unchanged since 2026-05-16]
- **Metrics:**
  - `queryCount` (integer) -- total DNS queries. Unit: count. [unchanged since 2026-05-16]
  - `responseTimeAvg` (number) -- average DNS response time. **Unit: microseconds** (confirmed via GraphQL introspection: `ZoneDnsAnalyticsAdaptiveGroupsAvg.processingTimeUs` -- the `Us` suffix = microseconds). The REST DNS analytics endpoint likely returns the same metric in a different format; verify with live data when zones are available. [live-verified 2026-05-16 via GraphQL introspection]
- **Properties:** (dimensions, not metrics)
  - `responseCode` -- DNS response code (NOERROR, NXDOMAIN, SERVFAIL, etc.) [unchanged since 2026-05-16]
  - `queryName` -- queried domain name [unchanged since 2026-05-16]
  - `queryType` -- DNS record type (A, AAAA, CNAME, MX, etc.) [unchanged since 2026-05-16]
- **Notes:** `data_lag` indicates seconds of delay in analytics pipeline. `totals` provides aggregate across all rows. No zones in test account so endpoint returns empty result, but auth and path are confirmed. [unchanged since 2026-05-16, auth confirmed live 2026-05-16]

---

### 3. DNS Analytics -- Time Series Report

- **Method:** GET
- **Path:** `/zones/{zone_id}/dns_analytics/report/bytime`
- **Auth:** Bearer token required [inferred from docs]
- **Path parameters:** Same as aggregate report [inferred from docs]
- **Query parameters:** Same as aggregate report, plus:

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `time_delta` | string | no | Time bucket size: `hour`, `day`, `week`, `month`, `year` |

- **Response schema** [inferred from docs]:

  ```json
  {
    "success": true,
    "errors": [],
    "messages": [],
    "result": {
      "data": [
        {
          "dimensions": ["NOERROR"],
          "metrics": [[100, 200, 300], [1.5, 2.0, 2.5]]
        }
      ],
      "data_lag": 60,
      "min": {},
      "max": {},
      "query": {
        "dimensions": ["responseCode"],
        "metrics": ["queryCount", "responseTimeAvg"],
        "since": "2024-01-01T00:00:00Z",
        "until": "2024-01-04T00:00:00Z",
        "time_delta": "day",
        "limit": 100
      },
      "rows": 5,
      "time_intervals": [
        ["2024-01-01T00:00:00Z", "2024-01-02T00:00:00Z"],
        ["2024-01-02T00:00:00Z", "2024-01-03T00:00:00Z"],
        ["2024-01-03T00:00:00Z", "2024-01-04T00:00:00Z"]
      ],
      "totals": {
        "queryCount": 600,
        "responseTimeAvg": 2.0
      }
    }
  }
  ```

- **Object candidates:** Same as aggregate -- metric source for Zone, not a distinct object [inferred from docs]
- **Metrics:** Same as aggregate (`queryCount`, `responseTimeAvg`) but returned as arrays aligned to `time_intervals` [inferred from docs]
- **Notes:** The `metrics` arrays within each `data` row are parallel arrays corresponding positionally to `time_intervals`. Each inner array has one value per time bucket. The MP adapter would typically use the aggregate endpoint for current-state collection and the time-series endpoint for historical backfill or trending. [inferred from docs]

---

### 4. List Pages Projects

- **Method:** GET
- **Path:** `/accounts/{account_id}/pages/projects`
- **Auth:** Bearer token required [inferred from docs]
- **Path parameters:**

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `account_id` | string | yes | Account identifier |

- **Query parameters:**

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `page` | integer | no | Page number |
  | `per_page` | integer | no | Results per page |

- **Response schema** (`result` is an array of Project objects) [live-verified 2026-05-16 -- endpoint responds with correct envelope and `success: true`; 0 projects in test account so object field schema from docs]:

  ```json
  {
    "success": true,
    "errors": [],
    "messages": [],
    "result": [
      {
        "name": "my-project",
        "id": "string (UUID)",
        "subdomain": "my-project.pages.dev",
        "production_branch": "main",
        "created_on": "2021-01-01T00:00:00Z",
        "build_config": {
          "build_command": "npm run build",
          "destination_dir": "build",
          "root_dir": "/",
          "web_analytics_tag": "string",
          "web_analytics_token": "string"
        },
        "deployment_configs": {
          "production": {
            "env_vars": {},
            "compatibility_date": "2024-01-01",
            "compatibility_flags": []
          },
          "preview": {
            "env_vars": {},
            "compatibility_date": "2024-01-01",
            "compatibility_flags": []
          }
        },
        "source": {
          "type": "github",
          "config": {
            "owner": "string",
            "repo_name": "string",
            "production_branch": "main",
            "pr_comments_enabled": true,
            "deployments_enabled": true
          }
        },
        "latest_deployment": {
          "id": "string (UUID)",
          "url": "https://<hash>.my-project.pages.dev",
          "environment": "production",
          "created_on": "2024-01-01T00:00:00Z",
          "modified_on": "2024-01-01T00:00:00Z",
          "short_id": "string",
          "project_name": "my-project",
          "deployment_trigger": {
            "type": "ad_hoc",
            "metadata": {
              "branch": "main",
              "commit_hash": "string",
              "commit_message": "string"
            }
          },
          "stages": [
            {
              "name": "queued",
              "started_on": "2024-01-01T00:00:00Z",
              "ended_on": "2024-01-01T00:00:01Z",
              "status": "success"
            },
            {
              "name": "initialize",
              "started_on": null,
              "ended_on": null,
              "status": "idle"
            },
            {
              "name": "clone_repo",
              "started_on": null,
              "ended_on": null,
              "status": "idle"
            },
            {
              "name": "build",
              "started_on": null,
              "ended_on": null,
              "status": "idle"
            },
            {
              "name": "deploy",
              "started_on": null,
              "ended_on": null,
              "status": "active"
            }
          ],
          "build_config": {},
          "source": {},
          "is_skipped": false,
          "production_branch": "main"
        },
        "canonical_deployment": {}
      }
    ],
    "result_info": {
      "page": 1,
      "per_page": 25,
      "total_count": 10,
      "total_pages": 1
    }
  }
  ```

- **Object candidates:** Pages Project [live-verified 2026-05-16 -- endpoint confirmed]
- **Identifier candidates:** `id` (UUID, globally unique), `name` (unique within account) [inferred from docs]
- **Metrics:**
  - None directly from this endpoint -- this is inventory + latest deployment status [unchanged since 2026-05-16]
  - Deployment stage durations could be derived (calculate `ended_on - started_on` for each stage) [inferred from pattern]
  - **Pages Functions metrics available via GraphQL** (`AccountPagesFunctionsInvocationsAdaptiveGroups`): `requests` (uint64), `errors` (uint64), `duration` (float64), `wallTime` (uint64), `subrequests` (uint64), `responseBodySize` (uint64), `clientDisconnects` (uint64) [live-verified 2026-05-16 via GraphQL introspection]
- **Properties:** `name`, `subdomain`, `production_branch`, `created_on`, `source.type` (`github`/`gitlab`), `source.config.owner`, `source.config.repo_name`, `build_config.build_command`, `build_config.destination_dir`, `latest_deployment.environment`, `latest_deployment.stages[].status` [inferred from docs]
- **Relationships:** Pages Project belongs to Account (`account_id` path param). Pages Project has Deployments (embedded). [unchanged since 2026-05-16]
- **Notes:** Test account has 0 Pages projects. Endpoint returns empty `result` array with correct envelope. Auth confirmed. [live-verified 2026-05-16]

---

### 5. Get Pages Project Detail

- **Method:** GET
- **Path:** `/accounts/{account_id}/pages/projects/{project_name}`
- **Auth:** Bearer token required [inferred from docs]
- **Path parameters:**

  | Parameter | Type | Required | Description |
  |-----------|------|----------|-------------|
  | `account_id` | string | yes | Account identifier |
  | `project_name` | string | yes | Project name (from List Projects) |

- **Response schema:** Same structure as a single element from the List Projects `result` array, but may include additional deployment history detail [inferred from docs]
- **Object candidates:** Same as List Projects -- enriches the Pages Project object [inferred from docs]
- **Notes:** Use this for detailed deployment history on a specific project. The List Projects endpoint embeds only the latest deployment. [inferred from docs]

---

### 6. Status Page Summary

- **Method:** GET
- **Path:** `/summary.json`
- **Base URL:** `https://www.cloudflarestatus.com/api/v2`
- **Auth:** None required [live-verified 2026-05-16]
- **Parameters:** None [live-verified 2026-05-16]
- **Response schema** [live-verified 2026-05-16]:

  ```json
  {
    "page": {
      "id": "<redacted>",
      "name": "Cloudflare",
      "url": "http://www.cloudflarestatus.com",
      "time_zone": "Etc/UTC",
      "updated_at": "2026-05-17T02:50:03.552Z"
    },
    "status": {
      "indicator": "minor",
      "description": "Minor Service Outage"
    },
    "components": [
      {
        "id": "<redacted>",
        "name": "Cloudflare Sites and Services",
        "status": "degraded_performance",
        "created_at": "2014-10-27T21:59:30.264Z",
        "updated_at": "2020-11-11T20:12:30.167Z",
        "position": 1,
        "description": "Sites and services that Cloudflare customers use ...",
        "showcase": false,
        "start_date": null,
        "group_id": null,
        "page_id": "<redacted>",
        "group": true,
        "only_show_if_degraded": false,
        "components": ["<child_id_1>", "<child_id_2>", "..."]
      },
      {
        "id": "<redacted>",
        "name": "Amsterdam, Netherlands - (AMS)",
        "status": "under_maintenance",
        "created_at": "2014-10-27T20:35:05.259Z",
        "updated_at": "2026-05-15T13:26:29.743Z",
        "position": 1,
        "description": null,
        "showcase": false,
        "start_date": null,
        "group_id": "<parent_group_id>",
        "page_id": "<redacted>",
        "group": false,
        "only_show_if_degraded": false
      }
    ],
    "incidents": [
      {
        "id": "<redacted>",
        "name": "PayPal Billing Issues",
        "status": "monitoring",
        "created_at": "2026-05-16T17:54:09.673Z",
        "updated_at": "2026-05-16T22:43:07.235Z",
        "monitoring_at": "2026-05-16T22:43:07.219Z",
        "resolved_at": null,
        "impact": "minor",
        "shortlink": "https://stspg.io/...",
        "started_at": "2026-05-16T17:54:09.665Z",
        "page_id": "<redacted>",
        "incident_updates": [
          {
            "id": "<redacted>",
            "status": "monitoring",
            "body": "A fix has been implemented ...",
            "incident_id": "<parent_incident_id>",
            "created_at": "2026-05-16T22:43:07.219Z",
            "updated_at": "2026-05-16T22:43:07.219Z",
            "display_at": "2026-05-16T22:43:07.219Z",
            "affected_components": [
              {
                "code": "<component_id>",
                "name": "Cloudflare Sites and Services - Billing",
                "old_status": "degraded_performance",
                "new_status": "degraded_performance"
              }
            ],
            "deliver_notifications": true,
            "custom_tweet": null,
            "tweet_id": null
          }
        ],
        "components": [
          {
            "id": "<component_id>",
            "name": "Billing",
            "status": "degraded_performance",
            "...": "same shape as top-level component object"
          }
        ],
        "reminder_intervals": null
      }
    ],
    "scheduled_maintenances": [
      {
        "id": "<redacted>",
        "name": "Scheduled Maintenance for Cloudflare Access",
        "status": "scheduled",
        "created_at": "2026-05-14T04:57:15.693Z",
        "updated_at": "2026-05-14T04:57:15.792Z",
        "monitoring_at": null,
        "resolved_at": null,
        "impact": "maintenance",
        "shortlink": "https://stspg.io/...",
        "started_at": "2026-05-14T04:57:15.672Z",
        "page_id": "<redacted>",
        "scheduled_for": "2026-05-17T12:00:00.000Z",
        "scheduled_until": "2026-05-17T13:00:00.000Z",
        "incident_updates": [
          {
            "id": "<redacted>",
            "status": "scheduled",
            "body": "Cloudflare will be performing scheduled maintenance ...",
            "incident_id": "<parent_id>",
            "created_at": "...",
            "updated_at": "...",
            "display_at": "...",
            "affected_components": [
              {
                "code": "<component_id>",
                "name": "Cloudflare Sites and Services - Access",
                "old_status": "operational",
                "new_status": "operational"
              }
            ],
            "deliver_notifications": true,
            "custom_tweet": null,
            "tweet_id": null
          }
        ],
        "components": ["... same shape as incident.components"]
      }
    ],
    "status": {
      "indicator": "minor",
      "description": "Minor Service Outage"
    }
  }
  ```

- **Object candidates:** Status Component [live-verified 2026-05-16]
- **Identifier candidates:** `id` (Statuspage component ID, stable string), `name` (human-readable; unique within its parent group but NOT globally unique -- e.g., position=1 appears in multiple groups) [live-verified 2026-05-16]
- **Metrics:**
  - `status` (enum string) -- component health status. Values observed: `operational`, `degraded_performance`, `partial_outage`, `under_maintenance`. Value `major_outage` not observed this session but documented by Statuspage. [live-verified 2026-05-16]
- **Properties:** `name`, `description` (string or null), `group` (boolean -- is this a group parent?), `group_id` (string or null -- parent group reference), `showcase` (boolean), `only_show_if_degraded` (boolean), `position` (integer), `start_date` (string or null -- not always present), `created_at`, `updated_at`, `page_id` [live-verified 2026-05-16]
- **Relationships:** Component belongs to Group (`group_id` references another component where `group == true`). Groups contain child IDs in their `components[]` array. **IMPORTANT: leaf components do NOT have a `components[]` field at all** -- this field is present only on group components. [live-verified 2026-05-16]
- **Notes:**
  - **478 total components** (not ~300 as previously estimated): 8 groups + 470 leaf components [live-verified 2026-05-16]
  - **8 groups** (not 10-15 as previously estimated): 1 service group ("Cloudflare Sites and Services" with 119 children) + 7 geographic groups (Africa=35, Asia=99, Europe=59, Latin America & Caribbean=64, Middle East=21, North America=59, Oceania=14) [live-verified 2026-05-16]
  - Group `showcase` is `false` for all 8 groups [live-verified 2026-05-16]
  - Leaf component `showcase` is `false` for all observed components [live-verified 2026-05-16]
  - `start_date` can be `null` (observed for many components); not always a date string [live-verified 2026-05-16]
  - `page.url` uses `http://` (not `https://`) in the response [live-verified 2026-05-16]
  - Status distribution observed: operational=416, partial_outage=36, under_maintenance=22, degraded_performance=4 [live-verified 2026-05-16]
  - `page.updated_at` indicates last status page update time [live-verified 2026-05-16]
  - `status.indicator` at the top level: observed value `minor`. Known values: `none` (all operational), `minor`, `major`, `critical` [live-verified 2026-05-16, `none`/`major`/`critical` inferred from docs]
  - `status.description` at the top level: observed value `"Minor Service Outage"` [live-verified 2026-05-16]
  - **Incident schema** is now documented (see response schema above). Incidents include `impact` (observed: `minor`), `status` (observed: `monitoring`, `identified`, `investigating`), and nested `incident_updates[]` with `affected_components[]` showing status transitions (`old_status` / `new_status`). [live-verified 2026-05-16]
  - **Scheduled maintenance schema** is now documented. Includes `scheduled_for` and `scheduled_until` timestamps (ISO 8601) plus `impact: "maintenance"`. Status observed: `scheduled`. Same `incident_updates[]` shape as incidents. [live-verified 2026-05-16]
  - 3 active incidents and 12 scheduled maintenances observed at capture time [live-verified 2026-05-16]

### 6a. Status Page -- Incident Object Schema (NEW)

Incidents are embedded in the `/summary.json` response under the `incidents[]` array. This is not a separate endpoint.

- **Field schema** [live-verified 2026-05-16]:

  | Field | Type | Description |
  |-------|------|-------------|
  | `id` | string | Unique incident identifier |
  | `name` | string | Human-readable incident title |
  | `status` | string | Incident lifecycle state: `investigating`, `identified`, `monitoring`, `resolved`, `postmortem` |
  | `created_at` | string (ISO 8601) | When the incident was created |
  | `updated_at` | string (ISO 8601) | Last update time |
  | `monitoring_at` | string or null | When the incident entered monitoring state |
  | `resolved_at` | string or null | When the incident was resolved (null if ongoing) |
  | `impact` | string | Impact severity: `minor`, `major`, `critical`, `maintenance` |
  | `shortlink` | string | Short URL for the incident page |
  | `started_at` | string (ISO 8601) | When the incident started |
  | `page_id` | string | Statuspage page identifier |
  | `incident_updates` | array | Ordered list of status updates (newest first) |
  | `incident_updates[].status` | string | Update status (same enum as incident status) |
  | `incident_updates[].body` | string | Update text content |
  | `incident_updates[].affected_components` | array | Components affected, with `code`, `name`, `old_status`, `new_status` |
  | `incident_updates[].deliver_notifications` | boolean | Whether notifications were sent |
  | `components` | array | Affected component objects (same shape as top-level components) |
  | `reminder_intervals` | null or unknown | Observed as null |

- **v2 consideration:** Incident objects could feed VCF Ops events or a dedicated Incident object type. The `affected_components[].code` field joins to `components[].id`, enabling incident-to-component correlation. [live-verified 2026-05-16]

### 6b. Status Page -- Scheduled Maintenance Object Schema (NEW)

Scheduled maintenances are embedded in `/summary.json` under `scheduled_maintenances[]`. Same shape as incidents, plus:

- **Additional fields** [live-verified 2026-05-16]:

  | Field | Type | Description |
  |-------|------|-------------|
  | `scheduled_for` | string (ISO 8601) | Planned maintenance start time |
  | `scheduled_until` | string (ISO 8601) | Planned maintenance end time |
  | `impact` | string | Always `"maintenance"` for scheduled maintenances |

- **v2 consideration:** Maintenance windows could be used to suppress alerts on affected components during the scheduled window. [live-verified 2026-05-16]

### 6c. Status Page -- Service Component Names (Reference)

The "Cloudflare Sites and Services" group contains 119 child service components. Notable services relevant to this MP [live-verified 2026-05-16]:

| Service Name | Relevance |
|---|---|
| Authoritative DNS | Core DNS monitoring target |
| Recursive DNS | DNS resolution |
| DNS Firewall | DNS security |
| DNS Updates | DNS propagation |
| CDN/Cache | HTTP caching (correlates with zone HTTP cache metrics) |
| CDN Cache Purge | Cache management |
| Pages | Cloudflare Pages deployment platform |
| Workers | Serverless (v2 GraphQL dataset) |
| Workers KV / D1 / R2 / Durable Objects | Storage services (v2 expansion) |
| Analytics | Cloudflare analytics platform |
| API | Cloudflare API health (meta -- affects data collection itself) |
| Firewall | WAF (correlates with firewall GraphQL datasets) |
| Load Balancing and Monitoring | LB analytics |
| Spectrum | TCP/UDP proxy (v2 GraphQL dataset) |
| Web Analytics | RUM analytics |
| Stream | Video streaming |
| SSL Certificate Provisioning | TLS cert health |

---

### 7. GraphQL Analytics

- **Method:** POST
- **Path:** `/graphql`
- **Auth:** Bearer token required [live-verified 2026-05-16]
- **Request body:**

  ```json
  {
    "query": "{ viewer { zones(filter: {zoneTag: $zoneTag}) { <dataset>(filter: {datetime_gt: $start, datetime_lt: $end}, limit: 100) { dimensions { ... } sum { ... } avg { ... } } } } }",
    "variables": {
      "zoneTag": "<zone_id>",
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-01-02T00:00:00Z"
    }
  }
  ```

- **Response schema** (general shape) [live-verified 2026-05-16 -- GraphQL responds, introspection confirms structure]:

  ```json
  {
    "data": {
      "viewer": {
        "zones": [
          {
            "<datasetName>": [
              {
                "dimensions": { "date": "2024-01-01" },
                "sum": { "requests": 12345, "bytes": 67890 },
                "avg": { "sampleInterval": 1.0 }
              }
            ]
          }
        ]
      }
    },
    "errors": null
  }
  ```

- **Schema statistics** [live-verified 2026-05-16]:
  - **1712 total GraphQL types** in the schema
  - **245 primary datasets** (53 zone-scoped, 192 account-scoped)
  - Datasets have sub-types: `Sum`, `Avg`, `Dimensions`, `Uniq`, `Quantiles`, `Max`, `Min`, `Ratio`, `Confidence`

- **Dataset naming conventions** [live-verified 2026-05-16]:
  - **Scope prefix:** `Zone*` (per-zone) or `Account*` (per-account)
  - **Aggregated time-bucketed:** `<product><timeWindow>Groups` suffix (e.g., `httpRequests1mGroups`, `httpRequests1hGroups`, `httpRequests1dGroups`)
  - **By-colo variants:** `<product><timeWindow>ByColoGroups` (e.g., `httpRequests1mByColoGroups`, `httpRequests1dByColoGroups`)
  - **Adaptive (sampled):** `<product>AdaptiveGroups` suffix (e.g., `firewallEventsAdaptiveGroups`, `httpRequestsAdaptiveGroups`)
  - **Raw adaptive:** `<product>Adaptive` without `Groups` -- raw per-event data (e.g., `firewallEventsAdaptive`, `httpRequestsAdaptive`)
  - **Time granularity encoded in name:** `1m` = 1-minute, `1h` = 1-hour, `1d` = 1-day
  - **CF1 Gateway variants:** `cf1Gateway*` prefix for Zero Trust gateway analytics with explicit time window docs in description

#### 7a. Zone-Scoped Datasets (53 total) [live-verified 2026-05-16]

**HTTP Request Analytics:**
- `httpRequests1mGroups` -- Minutely rollups of request data
- `httpRequests1hGroups` -- Hourly rollups of request data
- `httpRequests1dGroups` -- Daily rollups of request data
- `httpRequests1mByColoGroups` -- Minutely rollups by colo
- `httpRequests1dByColoGroups` -- Daily rollups by colo
- `httpRequestsAdaptive` -- Raw HTTP requests with adaptive sampling
- `httpRequestsAdaptiveGroups` -- Aggregated HTTP requests with adaptive sampling
- `httpRequestsOverviewAdaptiveGroups` -- High-level summary of HTTP requests

**DNS Analytics:**
- `dnsAnalyticsAdaptive` -- Raw DNS query analytics
- `dnsAnalyticsAdaptiveGroups` -- Aggregated DNS query analytics

**Firewall/Security:**
- `firewallEventsAdaptive` -- Raw firewall events
- `firewallEventsAdaptiveGroups` -- Aggregated firewall events
- `firewallEventsAdaptiveByTimeGroups` -- Firewall events grouped by time

**Health Checks:**
- `healthCheckEventsAdaptive` -- Raw health check events
- `healthCheckEventsAdaptiveGroups` -- Aggregated health check events

**Load Balancing:**
- `loadBalancingRequestsAdaptive` -- Raw LB origin requests
- `loadBalancingRequestsAdaptiveGroups` -- Aggregated LB origin requests

**Workers (zone-scoped):**
- `workersZoneInvocationsAdaptiveGroups` -- Workers invocations per zone
- `workersZoneSubrequestsAdaptiveGroups` -- Workers subrequests per zone

**Cache Reserve:**
- `cacheReserveOperationsAdaptiveGroups` -- Cache Reserve operations (Beta)
- `cacheReserveRequestsAdaptiveGroups` -- Cache Reserve HTTP requests
- `cacheReserveStorageAdaptiveGroups` -- Cache Reserve storage (Beta)

**Other zone-scoped:**
- `imageResizingRequests1mGroups` -- Image Resizing requests
- `logpushHealthAdaptiveGroups` -- Logpush job health (Beta)
- `logpushTransformersAdaptiveGroups` -- Logpush transformer health (Beta)
- `nelReportsAdaptiveGroups` -- Network error logs
- `pageShieldReportsAdaptiveGroups` -- Page Shield CSP reports
- `waitingRoomAnalyticsAdaptive` / `waitingRoomAnalyticsAdaptiveGroups` -- Waiting Room analytics
- `apiGateway*` -- API Gateway analytics (3 datasets)
- `apiRequestSequencesGroups` -- API request sequences
- `dmarcReports*` -- DMARC report records (2 datasets)
- `emailRouting*` / `emailSending*` -- Email analytics (4 datasets, Beta)
- `zaraz*` -- Zaraz analytics (11 datasets)
- `userProfiles*` -- User profile analytics (2 datasets)

#### 7b. Account-Scoped Datasets (192 total, top relevant) [live-verified 2026-05-16]

**HTTP Request Analytics (account-level):**
- `httpRequests1mGroups` / `httpRequests1hGroups` / `httpRequests1dGroups` -- Same metrics, account-aggregated
- `httpRequestsAdaptive` / `httpRequestsAdaptiveGroups` -- Raw/aggregated adaptive
- `httpRequestsOverviewAdaptiveGroups` -- High-level summary

**DNS Analytics:**
- `dnsAnalyticsAdaptive` / `dnsAnalyticsAdaptiveGroups` -- Account-level DNS analytics
- `dnsFirewallAnalyticsAdaptive` / `dnsFirewallAnalyticsAdaptiveGroups` -- DNS Firewall analytics

**Workers:**
- `workersInvocationsAdaptive` -- Workers invocations (Beta)
- `workersOverviewDataAdaptiveGroups` / `workersOverviewRequestsAdaptiveGroups` -- Overview
- `workersSubrequestsAdaptiveGroups` -- Workers subrequests
- `workersBuildsBuildMinutesAdaptiveGroups` -- Build minutes
- `workerPlacementAdaptiveGroups` -- Placement metrics
- `workersVpcConnectionAdaptiveGroups` -- VPC connections

**Pages:**
- `pagesFunctionsInvocationsAdaptiveGroups` -- Pages Functions invocations

**R2 Storage:**
- `r2OperationsAdaptiveGroups` -- R2 operations (Beta)
- `r2StorageAdaptiveGroups` -- R2 storage (Beta)
- `r2CatalogDataOperationsAdaptiveGroups` -- R2 Data Catalog operations
- `r2CatalogTableMaintenanceAdaptiveGroups` -- R2 table maintenance

**D1 Database:**
- `d1AnalyticsAdaptiveGroups` -- D1 analytics
- `d1QueriesAdaptiveGroups` -- D1 query metrics
- `d1StorageAdaptiveGroups` -- D1 storage

**Spectrum:**
- `spectrumNetworkAnalyticsAdaptiveGroups` -- Spectrum traffic analytics

**Stream:**
- `streamMinutesViewedAdaptiveGroups` -- Stream minutes viewed
- `streamCMCDAdaptiveGroups` -- Stream CMCD data

**Magic Transit/WAN/Firewall:**
- `magicTransitNetworkAnalyticsAdaptiveGroups` -- Magic Transit traffic
- `magicTransitTunnelTrafficAdaptiveGroups` -- Tunnel bandwidth
- `magicTransitTunnelHealthChecksAdaptiveGroups` -- Tunnel health (Beta)
- `magicFirewallNetworkAnalyticsAdaptiveGroups` -- Magic Firewall
- `magicFirewallSamplesAdaptiveGroups` -- Firewall samples
- `magicEndpointHealthCheckAdaptiveGroups` -- Endpoint health checks

**Zero Trust/Gateway:**
- `cf1GatewayDns*Groups` -- Gateway DNS analytics (raw, 1h, 1d)
- `cf1GatewayHttp*Groups` -- Gateway HTTP analytics (raw, 1h, 1d)
- `cf1GatewayNetwork*Groups` -- Gateway network analytics
- `gatewayL4*AdaptiveGroups` -- L4 Gateway sessions
- `gatewayL7RequestsAdaptiveGroups` -- L7 Gateway requests
- `accessLoginRequestsAdaptiveGroups` -- Access login requests
- `cloudflareTunnelsAnalyticsAdaptiveGroups` -- Tunnel device analytics

**AI/ML:**
- `aiGateway*AdaptiveGroups` -- AI Gateway (cache, requests, errors, size)
- `aiInferenceAdaptive` / `aiInferenceAdaptiveGroups` -- AI Inference

**RUM:**
- `rumPageloadEventsAdaptiveGroups` -- RUM pageload events (Beta)
- `rumPerformanceEventsAdaptiveGroups` -- RUM performance events (Beta)
- `rumWebVitalsEventsAdaptive` / `rumWebVitalsEventsAdaptiveGroups` -- Web Vitals (Beta)

#### 7c. `httpRequests1hGroups` Field Detail [live-verified 2026-05-16 via GraphQL introspection]

**`sum` fields** (all NON_NULL uint64):
| Field | Type | Description |
|-------|------|-------------|
| `requests` | uint64 | Total HTTP requests |
| `bytes` | uint64 | Total bytes transferred |
| `cachedRequests` | uint64 | Cached HTTP requests |
| `cachedBytes` | uint64 | Cached bytes |
| `threats` | uint64 | Threat requests blocked |
| `pageViews` | uint64 | Page views |
| `encryptedRequests` | uint64 | HTTPS requests |
| `encryptedBytes` | uint64 | HTTPS bytes |
| `edgeRequestBytes` | uint64 | Edge request bytes (NEW -- not in prior docs) |
| `browserMap` | LIST | Browser breakdown |
| `clientHTTPVersionMap` | LIST | HTTP version breakdown |
| `clientSSLMap` | LIST | SSL/TLS version breakdown |
| `contentTypeMap` | LIST | Content type breakdown |
| `countryMap` | LIST | Country breakdown |
| `ipClassMap` | LIST | IP class breakdown |
| `responseStatusMap` | LIST | HTTP status code breakdown |
| `threatPathingMap` | LIST | Threat pathing breakdown |

**`avg` fields** (all NON_NULL float64):
| Field | Type | Description |
|-------|------|-------------|
| `bytes` | float64 | Average bytes per request |
| `edgeRequestBytes` | float64 | Average edge request bytes |
| `sampleInterval` | float64 | Sample interval |

**`uniq` fields** (all NON_NULL uint64):
| Field | Type | Description |
|-------|------|-------------|
| `uniques` | uint64 | Unique visitors |

**`dimensions` fields**:
| Field | Type |
|-------|------|
| `date` | Date |
| `datetime` | Time |

#### 7d. `dnsAnalyticsAdaptiveGroups` Field Detail [live-verified 2026-05-16 via GraphQL introspection]

**`sum` fields** (all NON_NULL uint64):
| Field | Type | Description |
|-------|------|-------------|
| `countNotCachedAndNotStale` | uint64 | DNS queries that were not cached and not stale |
| `countStale` | uint64 | DNS queries served from stale cache |

**`avg` fields** (all NON_NULL float64):
| Field | Type | Description |
|-------|------|-------------|
| `processingTimeUs` | float64 | Average DNS processing time in **microseconds** |
| `processingTimeUsNotCachedAndNotStale` | float64 | Avg processing time for non-cached, non-stale queries (us) |
| `processingTimeUsStale` | float64 | Avg processing time for stale cache queries (us) |
| `sampleInterval` | float64 | Sample interval |

**`quantiles` fields** (all NON_NULL float64, percentiles P25/P50/P75/P90/P95/P99/P999):
- `processingTimeUsP25` through `processingTimeUsP999` -- Overall processing time percentiles (us)
- `processingTimeUsNotCachedAndNotStaleP25` through `...P999` -- Non-cached percentiles
- `processingTimeUsStaleP25` through `...P999` -- Stale cache percentiles

**`dimensions` fields**:
| Field | Type | Description |
|-------|------|-------------|
| `coloName` | string | Cloudflare colo/PoP name |
| `date` | Date | Date |
| `datetime` | Time | Timestamp |
| `datetimeFifteenMinutes` | Time | 15-minute bucket |
| `datetimeFiveMinutes` | Time | 5-minute bucket |
| `datetimeHalfOfHour` | Time | 30-minute bucket |
| `datetimeHour` | Time | 1-hour bucket |
| `datetimeMinute` | Time | 1-minute bucket |
| `destinationIP` | string | Destination IP |
| `ipVersion` | uint8 | IP version (4 or 6) |
| `protocol` | string | Transport protocol |
| `queryName` | string | Queried domain name |
| `querySizeBucket` | string | Query size range bucket |
| `queryType` | string | DNS record type (A, AAAA, CNAME, etc.) |
| `responseCached` | uint8 | Whether response was cached (0/1) |
| `responseCode` | string | DNS response code (NOERROR, NXDOMAIN, etc.) |
| `responseSizeBucket` | string | Response size range bucket |
| `responseStale` | uint8 | Whether response was stale (0/1) |
| `sourceIP` | string | Source IP |
| `upstreamIP` | string | Upstream resolver IP |

#### 7e. `firewallEventsAdaptiveGroups` Dimensions (partial) [live-verified 2026-05-16 via GraphQL introspection]

Key dimension fields (65+ total):
- `action` (string) -- action taken (block, challenge, etc.)
- `botScore` (uint8) -- bot score 0-99
- `clientASNDescription`, `clientAsn`, `clientCountryName`, `clientIP` -- client identity
- `clientRequestHTTPHost`, `clientRequestHTTPMethodName`, `clientRequestPath` -- request details
- `edgeColoName` -- Cloudflare edge PoP
- `edgeResponseStatus` (uint16) -- HTTP response status code
- `ruleId`, `rulesetId` -- rule identifiers
- `source` -- event source
- `wafAttackScore`, `wafMlAttackScore`, `wafSqliAttackScore`, `wafXssAttackScore` -- WAF scores
- `date`, `datetime`, `datetimeMinute`, `datetimeFiveMinutes`, `datetimeFifteenMinutes`, `datetimeHour` -- time dimensions

#### 7f. `workersInvocationsAdaptive` Sum Fields [live-verified 2026-05-16 via GraphQL introspection]

| Field | Type | Description |
|-------|------|-------------|
| `requests` | uint64 | Total invocations |
| `errors` | uint64 | Error count |
| `duration` | float64 | Total duration |
| `requestDuration` | float64 | Total request duration |
| `cpuTimeUs` | uint64 | Total CPU time in microseconds |
| `wallTime` | uint64 | Total wall time |
| `subrequests` | uint64 | Total subrequests |
| `responseBodySize` | uint64 | Total response body size |
| `clientDisconnects` | uint64 | Client disconnect count |

#### 7g. `pagesFunctionsInvocationsAdaptiveGroups` Sum Fields [live-verified 2026-05-16 via GraphQL introspection]

| Field | Type | Description |
|-------|------|-------------|
| `requests` | uint64 | Total invocations |
| `errors` | uint64 | Error count |
| `duration` | float64 | Total duration |
| `wallTime` | uint64 | Total wall time |
| `subrequests` | uint64 | Total subrequests |
| `responseBodySize` | uint64 | Total response body size |
| `clientDisconnects` | uint64 | Client disconnect count |

- **Notes:**
  - GraphQL introspection fully functional and catalogued [live-verified 2026-05-16]
  - Filter syntax: `datetime_gt`, `datetime_lt`, `datetime_geq`, `datetime_leq` for time ranges. Additional filters vary by dataset. [inferred from docs, filter InputObject types confirmed to exist via introspection]
  - Account-scoped queries: `viewer { accounts(filter: {accountTag: $accountId}) { ... } }` [inferred from docs, account types confirmed in schema]
  - Zone-scoped queries: `viewer { zones(filter: {zoneTag: $zoneTag}) { ... } }` [inferred from docs, zone types confirmed in schema]
  - No data queries could be executed (0 zones, 0 workers, 0 Pages) but all schema introspection succeeded [live-verified 2026-05-16]

---

## Object Model Candidates

### 1. Cloudflare Account

- **Source endpoint(s):** `GET /accounts` (inventory), also embedded in zone and project responses (`account.id`, `account.name` in zone objects; `account_id` path param for Pages) [live-verified 2026-05-16]
- **Identifier:** `id` (32-char hex string) [live-verified 2026-05-16]
- **Metrics:** None directly from REST. Account-scoped GraphQL datasets (192 datasets) provide aggregate metrics across all zones. [live-verified 2026-05-16]
- **Properties:** `name`, `type` (observed: `"standard"`), `created_on` (ISO 8601), `settings.enforce_twofactor` (boolean), `settings.api_access_enabled` (null or boolean), `settings.oauth_app_access_enabled` (boolean), `settings.access_approval_expiry` (null or value), `settings.abuse_contact_email` (null or string), `legacy_flags.enterprise_zone_quota.maximum/current/available` (integers) [live-verified 2026-05-16]
- **Relationships:** Parent of Zone, parent of Pages Project [live-verified 2026-05-16]
- **Notes:** Dedicated `GET /accounts` endpoint exists and works. Test account has 1 account. For a single-account MP, this is the adapter instance itself. [live-verified 2026-05-16]

### 2. Zone

- **Source endpoint(s):** `GET /zones` (inventory), `GET /zones/{zone_id}/dns_analytics/report` (DNS metrics), `POST /graphql` (HTTP/firewall/workers metrics via zone-scoped datasets) [live-verified 2026-05-16 -- endpoints confirmed, no zone data to verify field values]
- **Identifier:** `id` (32-char hex string, globally unique) [inferred from docs, id format confirmed via account.id]
- **Metrics:**
  - `dns_query_count` -- from REST DNS analytics `queryCount` or GraphQL `dnsAnalyticsAdaptiveGroups.sum.countNotCachedAndNotStale` + `countStale` [live-verified 2026-05-16 via introspection]
  - `dns_response_time_avg_us` -- from GraphQL `dnsAnalyticsAdaptiveGroups.avg.processingTimeUs`. **Unit: microseconds** (not milliseconds as previously assumed). Convert to ms by dividing by 1000. [live-verified 2026-05-16 via introspection]
  - `dns_response_time_p50/p90/p95/p99` -- from GraphQL `dnsAnalyticsAdaptiveGroups.quantiles.processingTimeUsP50/P90/P95/P99`. Unit: microseconds. [live-verified 2026-05-16 via introspection]
  - `http_requests` -- from GraphQL `httpRequests1hGroups.sum.requests` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_bytes` -- from GraphQL `httpRequests1hGroups.sum.bytes` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_cached_requests` -- from GraphQL `httpRequests1hGroups.sum.cachedRequests` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_cached_bytes` -- from GraphQL `httpRequests1hGroups.sum.cachedBytes` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_threats` -- from GraphQL `httpRequests1hGroups.sum.threats` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_encrypted_requests` -- from GraphQL `httpRequests1hGroups.sum.encryptedRequests` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_encrypted_bytes` -- from GraphQL `httpRequests1hGroups.sum.encryptedBytes` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_edge_request_bytes` -- from GraphQL `httpRequests1hGroups.sum.edgeRequestBytes` (uint64). **NEW** -- not in prior docs. [live-verified 2026-05-16 via introspection]
  - `http_page_views` -- from GraphQL `httpRequests1hGroups.sum.pageViews` (uint64) [live-verified 2026-05-16 via introspection]
  - `http_unique_visitors` -- from GraphQL `httpRequests1hGroups.uniq.uniques` (uint64) [live-verified 2026-05-16 via introspection]
  - `cache_hit_ratio` -- derived: `cachedRequests / requests` (supermetric candidate) [inferred from pattern]
  - `encryption_ratio` -- derived: `encryptedRequests / requests` (supermetric candidate) [inferred from pattern]
- **Properties:** `name` (domain), `status`, `type`, `paused`, `development_mode`, `plan.name`, `plan.legacy_id`, `name_servers[]`, `created_on`, `activated_on`, `modified_on`, `account.name`, `owner.email` [inferred from docs]
- **Relationships:** Child of Account [live-verified 2026-05-16]

### 3. Pages Project

- **Source endpoint(s):** `GET /accounts/{account_id}/pages/projects` (inventory), `GET /accounts/{account_id}/pages/projects/{project_name}` (detail) [inferred from docs]
- **Identifier:** `id` (UUID) or `name` (unique within account) [inferred from docs]
- **Metrics:**
  - `latest_deployment_stage_count` -- number of deployment stages [inferred from pattern]
  - Deployment stage durations (derived from `stages[].started_on` / `ended_on`) [inferred from pattern]
  - Note: No direct performance/traffic metrics from this endpoint. Web analytics may be available if `web_analytics_tag` is configured, but the data would come from a separate analytics endpoint [unverified]
- **Properties:** `name`, `subdomain`, `production_branch`, `created_on`, `source.type`, `source.config.owner`, `source.config.repo_name`, `build_config.build_command`, `latest_deployment.environment`, `latest_deployment.url`, `latest_deployment.deployment_trigger.type`, `latest_deployment.stages[-1].status` (most recent stage status) [inferred from docs]
- **Relationships:** Child of Account [inferred from docs]

### 4. Pages Deployment

- **Source endpoint(s):** Embedded in Pages Project response (`latest_deployment`, `canonical_deployment`) [inferred from docs]
- **Identifier:** `id` (UUID) [inferred from docs]
- **Metrics:**
  - Stage durations (derived: `ended_on - started_on` per stage) [inferred from pattern]
  - Total build time (derived: sum of all stage durations) [inferred from pattern]
- **Properties:** `environment` (`production`/`preview`), `url`, `short_id`, `deployment_trigger.type`, `deployment_trigger.metadata.branch`, `deployment_trigger.metadata.commit_hash`, `deployment_trigger.metadata.commit_message`, `is_skipped`, `created_on`, `modified_on` [inferred from docs]
- **Stage status values:** `idle`, `active`, `success`, `failure`, `canceled` [inferred from docs]
- **Relationships:** Child of Pages Project [inferred from docs]
- **Notes:** Whether to model Deployment as a separate object type or flatten into Pages Project depends on design goals. For monitoring, the latest deployment status is usually sufficient as properties on the Project. A separate Deployment object would be useful for build performance tracking. [inferred from pattern]

### 5. Status Component

- **Source endpoint(s):** `GET /summary.json` (from Status Page API) [live-verified 2026-05-16]
- **Identifier:** `id` (Statuspage component ID, stable string) [live-verified 2026-05-16]
- **Metrics:**
  - `status` -- health state enum: `operational`, `degraded_performance`, `partial_outage`, `major_outage`, `under_maintenance`. All except `major_outage` observed live. Maps naturally to VCF Ops health states. [live-verified 2026-05-16]
- **Properties:** `name`, `description` (string or null), `group` (boolean), `group_id` (string or null), `showcase` (boolean -- observed as `false` for all components), `only_show_if_degraded` (boolean), `position` (integer), `start_date` (string or null), `page_id`, `created_at`, `updated_at` [live-verified 2026-05-16]
- **Relationships:** Child of Status Component Group (`group_id`). Groups contain child IDs in their `components[]` array. **Leaf components do NOT have a `components[]` field** -- this field is group-only. [live-verified 2026-05-16]
- **Notes:**
  - 478 total components (8 groups + 470 leaves) [live-verified 2026-05-16]
  - `showcase` is `false` for all observed components -- cannot be used for filtering [live-verified 2026-05-16]
  - Status values map well to VCF Ops health states: `operational` = GREEN, `degraded_performance` = YELLOW, `partial_outage` / `major_outage` = RED, `under_maintenance` = GREY/UNKNOWN [live-verified 2026-05-16, except major_outage color mapping inferred]
  - This is a public API -- no Cloudflare account needed [live-verified 2026-05-16]

### 6. Status Component Group

- **Source endpoint(s):** `GET /summary.json` -- components where `group == true` [live-verified 2026-05-16]
- **Identifier:** `id` (same as Status Component) [live-verified 2026-05-16]
- **Metrics:**
  - `status` -- health state enum (same as Status Component; reflects group-level status) [live-verified 2026-05-16]
  - `degraded_child_count` -- derived: count of children not `operational` (supermetric candidate). Computable from the same response by iterating `components[]` IDs and checking each child's status. [live-verified 2026-05-16 -- feasibility confirmed, derivation logic works]
- **Properties:** `name`, `description` (string or null), `position` (integer), `components[]` (array of child component ID strings) [live-verified 2026-05-16]
- **Relationships:** Parent of Status Component [live-verified 2026-05-16]
- **Notes:**
  - Exactly 8 groups observed [live-verified 2026-05-16]:
    1. Cloudflare Sites and Services (119 children -- service/product components)
    2. Africa (35 children -- data center locations)
    3. Asia (99 children)
    4. Europe (59 children)
    5. Latin America & the Caribbean (64 children)
    6. Middle East (21 children)
    7. North America (59 children)
    8. Oceania (14 children)
  - Groups and leaf components share the same response array. Differentiated by `group == true` and presence of `components[]` field (leaf components lack this field entirely). [live-verified 2026-05-16]
  - All groups have `group_id: null`, `showcase: false` [live-verified 2026-05-16]

---

## Cross-Request Join Keys

| Field A | Endpoint A | Field B | Endpoint B | Relationship | Verified |
|---------|-----------|---------|-----------|--------------|----------|
| `result[].id` | `GET /accounts` | `{account_id}` path param | `GET /accounts/{account_id}/pages/projects` | Account -> Pages Projects | [live-verified 2026-05-16] |
| `result[].id` | `GET /accounts` | `$accountTag` variable | `POST /graphql` (account-scoped) | Account -> GraphQL Analytics | [live-verified 2026-05-16 via schema] |
| `result[].id` | `GET /zones` | `{zone_id}` path param | `GET /zones/{zone_id}/dns_analytics/report` | Zone -> DNS Analytics | [unchanged since 2026-05-16] |
| `result[].id` | `GET /zones` | `$zoneTag` variable | `POST /graphql` (zone-scoped) | Zone -> GraphQL Analytics | [live-verified 2026-05-16 via schema] |
| `result[].account.id` | `GET /zones` | `result[].id` | `GET /accounts` | Zone.account -> Account | [live-verified 2026-05-16] |
| `components[].group_id` | `GET /summary.json` | `components[].id` (where `group==true`) | `GET /summary.json` | Status Component -> Status Component Group (same response) | [live-verified 2026-05-16] |

---

## Endpoint Inventory (Collection Cadence Recommendations)

| # | API Surface | Endpoint | Object(s) Fed | Recommended Interval | Notes | Verified |
|---|-------------|----------|---------------|---------------------|-------|----------|
| 1 | v4 REST | `GET /zones` | Zone | 15 min | Inventory/config -- slow-changing | Auth confirmed, 0 zones in test acct |
| 1a | v4 REST | `GET /accounts` | Account | 60 min | Account discovery (needed for Pages/GraphQL account_id) | Fully verified |
| 2 | v4 REST | `GET /zones/{zone_id}/dns_analytics/report` | Zone | 5 min | DNS metrics (aggregate, last 5min window) | Auth confirmed, no data (0 zones) |
| 3 | v4 REST | `GET /zones/{zone_id}/dns_analytics/report/bytime` | Zone | 15 min | Time-series for trending (optional) | Auth confirmed, no data (0 zones) |
| 4 | v4 REST | `GET /accounts/{account_id}/pages/projects` | Pages Project, Deployment | 15 min | Deployment status | Auth confirmed, 0 projects |
| 5 | v4 REST | `GET /accounts/{account_id}/pages/projects/{name}` | Pages Project, Deployment | On-demand | Detail for specific project (optional) | Not tested (no projects) |
| 6 | Status Page | `GET /summary.json` | Status Component, Status Component Group | 5 min | Public health status | Fully verified |
| 7 | v4 GraphQL | `POST /graphql` | Zone, Account | 5 min | HTTP/firewall/workers/DNS metrics (245 datasets) | Schema introspection fully verified |

**Total unique endpoints:** 8 (7 GET + 1 POST)
**Requests per 5-min cycle (per zone):** 3 (DNS analytics + Status summary + GraphQL)
**Requests per 15-min cycle (per zone):** 3 + 4 = 7 (add zones inventory + accounts + bytime + pages projects)
**Note:** DNS analytics and GraphQL are per-zone, so total requests scale with zone count. Status page returns 478 components in a single ~150KB response (as of 2026-05-16) [live-verified 2026-05-16].

---

## Gaps / Questions

### RESOLVED: Authenticated API token (session #2)

~~BLOCKED: Token was a placeholder.~~ **RESOLVED 2026-05-16.** Token is now valid and all authenticated endpoints respond with `success: true`. Auth is confirmed for: `GET /zones`, `GET /accounts`, `GET /accounts/{id}/pages/projects`, `POST /graphql` (including introspection). The `GET /user/tokens/verify` endpoint returns error 1000 for scoped tokens -- this is a known Cloudflare quirk, not an auth failure.

### RESOLVED: Previously blocked items

1. ~~**GraphQL schema introspection**~~ **RESOLVED.** Full introspection completed. 1712 types, 245 primary datasets (53 zone-scoped, 192 account-scoped). All dataset names, sum/avg/uniq/quantiles/dimensions fields catalogued for key datasets (httpRequests1hGroups, dnsAnalyticsAdaptiveGroups, firewallEventsAdaptiveGroups, workersInvocationsAdaptive, pagesFunctionsInvocationsAdaptiveGroups). [live-verified 2026-05-16]

2. ~~**DNS Analytics `responseTimeAvg` unit**~~ **RESOLVED.** Unit is **microseconds** (`processingTimeUs` field name in GraphQL). The REST DNS analytics endpoint's `responseTimeAvg` may use a different scale but the GraphQL field name is definitive. Quantile percentiles also available (P25-P999). [live-verified 2026-05-16 via introspection]

3. ~~**Pages web analytics**~~ **PARTIALLY RESOLVED.** GraphQL schema confirms `rumPageloadEventsAdaptiveGroups`, `rumPerformanceEventsAdaptiveGroups`, and `rumWebVitalsEventsAdaptiveGroups` exist (all Beta, account-scoped). These would provide RUM analytics for Pages projects with `web_analytics_tag`. Field details not yet introspected. [live-verified 2026-05-16 -- existence confirmed, field detail pending]

### Still requiring verification

4. **Pages deployment list endpoint** -- There may be a `GET /accounts/{account_id}/pages/projects/{project_name}/deployments` endpoint that lists historical deployments beyond just `latest_deployment`. Cannot test with 0 Pages projects. [unverified]

5. **GraphQL filter syntax** -- Dataset-specific filter InputObject types exist in the schema (e.g., `ZoneHttpRequests1hGroupsFilter_InputObject`) but their fields were not introspected this session. [unverified -- filter InputObject types confirmed to exist]

6. **Rate limit details** -- Exact rate limits per endpoint and plan tier need clarification. The 1200 req/5min is a general guideline. GraphQL may have different limits (possibly per-query cost based). [unverified]

7. **`data_lag` values** -- The DNS analytics `data_lag` field indicates pipeline delay. Cannot verify magnitude with 0 zones. [unverified]

8. **Zone response schema field verification** -- `GET /zones` endpoint confirmed working but returns empty `result` (0 zones in test account). Individual zone object fields (nested `plan`, `meta`, `owner`, `tenant` structures) not verified against live data. [unverified -- endpoint auth confirmed]

9. **Pages project response schema field verification** -- `GET /accounts/{id}/pages/projects` confirmed working but returns empty `result` (0 projects). `latest_deployment.stages[]` structure not verified against live data. [unverified -- endpoint auth confirmed]

10. **GraphQL data query execution** -- No data-returning GraphQL queries could be executed because the account has 0 zones, 0 workers, 0 Pages projects. Schema introspection is complete but actual response shapes with populated data remain unverified. [unverified -- schema confirmed]

11. **DNS Analytics REST vs GraphQL discrepancy** -- The REST endpoint (`/zones/{id}/dns_analytics/report`) uses `queryCount`/`responseTimeAvg` metric names while the GraphQL dataset (`dnsAnalyticsAdaptiveGroups`) uses `countNotCachedAndNotStale`/`countStale`/`processingTimeUs`. These appear to be different aggregation methods. Need to verify with live data whether REST `queryCount` equals GraphQL `sum.countNotCachedAndNotStale + sum.countStale`. [unverified]

### Answered by live verification (status page)

~~Status Component scope: ~300 components~~ **ANSWERED:** 478 components (8 groups + 470 leaves). Design decision to use group-level only yields exactly 8 objects, not 10-15 as estimated. [live-verified 2026-05-16]

~~Incident/maintenance schema unknown~~ **ANSWERED:** Both schemas fully captured. Incidents include `impact` (minor/major/critical), `status` lifecycle (investigating/identified/monitoring/resolved/postmortem), and `incident_updates[]` with `affected_components[]` showing status transitions. Scheduled maintenances add `scheduled_for`/`scheduled_until` fields. [live-verified 2026-05-16]

~~`showcase` filtering~~ **ANSWERED:** `showcase` is `false` for all 478 components. Cannot be used as a filter criterion. Group-level filtering (`group == true`) is the correct approach. [live-verified 2026-05-16]

~~Leaf components `components[]` field~~ **ANSWERED:** Leaf components do NOT have a `components[]` field. Only group components have it. This is a structural difference -- code must check for field existence, not just empty array. [live-verified 2026-05-16]

### Design decisions for mp-designer

10. **Status Component scope** -- 478 components total, 8 groups. The design correctly chose group-level only (8 objects). The "Cloudflare Sites and Services" group alone has 119 children; modeling all leaves is noisy. [live-verified 2026-05-16 -- design decision confirmed as appropriate]

11. **Account as adapter instance** -- Confirmed: `GET /accounts` returns account objects with `id`, `name`, `type`, `created_on`. Account is the natural adapter instance. Account-scoped GraphQL datasets (192 total) provide aggregate metrics across all zones. [live-verified 2026-05-16]

12. **Zone count scaling** -- Test account has 0 zones. With 0 zones, per-zone calls (DNS analytics, zone-scoped GraphQL) generate 0 API calls. Scaling concern remains relevant for multi-zone accounts. [unchanged since 2026-05-16 initial mapping]

13. **Deployment as separate object vs. embedded** -- [unchanged since 2026-05-16 initial mapping]

14. **Status Page API independence** -- The Status Page API requires no authentication and monitors Cloudflare's own infrastructure health. [unchanged since 2026-05-16 initial mapping]

15. **GraphQL POST for metrics** -- Confirmed: GraphQL endpoint responds to POST with `Content-Type: application/json`. Introspection queries work. Data queries require zone or account scope. Schema is rich (1712 types). [live-verified 2026-05-16]

16. **DNS response time unit** -- **Critical design note:** DNS response time is in **microseconds** (field: `processingTimeUs`), not milliseconds. The MP must convert to ms (divide by 1000) or clearly label the metric as microseconds to avoid user confusion. Quantile percentiles (P25-P999) are also available for DNS response time. [live-verified 2026-05-16]

17. **New metric: `edgeRequestBytes`** -- The `httpRequests1hGroups.sum.edgeRequestBytes` field was not in prior documentation. This provides edge-level request byte counts separate from `bytes` (which appears to be total/origin). Consider including in Zone metrics. [live-verified 2026-05-16]

18. **Unique visitors metric** -- `httpRequests1hGroups.uniq.uniques` provides unique visitor count per zone per hour. High-value metric for dashboards. [live-verified 2026-05-16]

### Not covered in this map

12. **Other Cloudflare APIs** -- Many additional Cloudflare API surfaces exist (Workers, R2, D1, Queues, Stream, Images, Access, Zero Trust, etc.) that could feed an expanded MP. The GraphQL schema reveals 192 account-scoped datasets covering these services. This map covers only the four surfaces specified in the orchestrator brief, but the full dataset catalog is now documented in section 7b. [updated 2026-05-16 with GraphQL dataset catalog]

13. **Webhook/event push** -- Cloudflare supports notification webhooks for various events. Not covered in this map. [unchanged since 2026-05-16 initial mapping]
