# UniFi Integration API — Device Filter Probe (2026-05-08)

## Question

Which fields and operators does the UniFi Integration API's `filter`
query parameter support on the device list endpoint, and can they
distinguish a UDM Pro (gateway) from regular switches?

## Target

- Controller: `unifi.int.sentania.net`
- Endpoint: `GET /proxy/network/integration/v1/sites/{siteId}/devices`
- Site ID: `88f7af54-98f8-306a-a1c7-c9349722b1f6`
- Auth: `X-API-Key` header (stateless, `.env` `UNIFI_API_KEY`)
- Date: 2026-05-08

## Lab device inventory (baseline, no filter)

15 devices total. The UDM Pro is the only gateway-class device.

| name | model | features | interfaces |
|---|---|---|---|
| udm | UDM Pro | `["switching"]` | `["ports"]` |
| usw-lite-16-nuc | USW Lite 16 PoE | `["switching"]` | `["ports"]` |
| usw-lite-16-r740 | USW Lite 16 PoE | `["switching"]` | `["ports"]` |
| usw-lite-16-central | USW Lite 16 PoE | `["switching"]` | `["ports"]` |
| usw-lite-8-attic | USW Lite 8 PoE | `["switching"]` | `["ports"]` |
| ap-basement | AC IW | `["switching","accessPoint"]` | `["ports","radios"]` |
| ap-lower | AC IW | `["switching","accessPoint"]` | `["ports","radios"]` |
| AtticFlex | USW Flex | `["switching"]` | `["ports"]` |
| GarageFlex | USW Flex | `["switching"]` | `["ports"]` |
| ap-livingroom | AC Pro | `["accessPoint"]` | `["ports","radios"]` |
| ap-bedroom | AC Pro | `["accessPoint"]` | `["ports","radios"]` |
| ap-office | Nano HD | `["accessPoint"]` | `["radios"]` |
| Backyard WiFI | AC Mesh | `["accessPoint"]` | `["radios"]` |
| Backyard Flex | USW Flex | `["switching"]` | `["ports"]` |
| usw-xg-8-ms | USW Pro XG 8 PoE | `["switching"]` | `["ports"]` |

Key observation: the UDM Pro does NOT include `"gateway"` in its
`features` array. It reports only `["switching"]`, making it
indistinguishable from a regular switch by features alone.

The detail endpoint (`GET /devices/{id}`) reveals one structural
difference: the UDM Pro has **no `uplink` field** (it is the root
device), while every other device has `"uplink":{"deviceId":"b3134082-..."}`.
However, `uplink` is not a filterable property on the list endpoint.

---

## Probe results (18 probes)

### Working filters

| # | Filter expression | HTTP | totalCount | Notes |
|---|---|---|---|---|
| 1 | `model.eq('UDM Pro')` | 200 | 1 | **WORKS.** Returns only the UDM Pro. |
| 3 | `model.ne('UDM Pro')` | 200 | 14 | **WORKS.** Returns everything except UDM Pro. |
| 4 | `and(features.contains('switching'),not(features.contains('accessPoint')))` | 200 | 9 | **WORKS.** Compound `and()` + `not()` syntax confirmed. Returns 8 pure switches + UDM Pro. |
| 5 | `model.in('USW Lite 16 PoE','USW Lite 8 PoE','USW Flex','USW Pro XG 8 PoE')` | 200 | 8 | **WORKS.** Multi-value `in()` confirmed. Returns exactly 8 pure switches. |
| 6 | `and(features.contains('switching'),model.ne('UDM Pro'))` | 200 | 10 | **WORKS.** Switching devices minus UDM Pro = 8 pure switches + 2 AC IW (dual-feature APs). |
| 7 | `name.like('usw*')` | 200 | 5 | **WORKS.** `like` with wildcard on `name`. Case-sensitive: matches `usw-*` names only, not `AtticFlex`/etc. |
| 8 | `interfaces.contains('radios')` | 200 | 6 | **WORKS.** Same 6 as `features.contains('accessPoint')`. |
| 10 | `state.eq('ONLINE')` | 200 | 15 | **WORKS.** All devices online. |
| 11 | `or(features.contains('accessPoint'),features.contains('gateway'))` | 200 | 6 | **WORKS.** `or()` syntax confirmed. Returns 6 APs (`gateway` contributes 0). |
| 12 | `features.containsAny('accessPoint','gateway')` | 200 | 6 | **WORKS.** Same result as probe 11 but cleaner syntax. |
| 13 | `model.notIn('UDM Pro')` | 200 | 14 | **WORKS.** `notIn()` with single value, same as `ne()`. |
| 14 | `firmwareVersion.like('7*')` | 200 | 8 | **WORKS.** `like` confirmed on `firmwareVersion` (the only field besides `name` that allows it). |
| 17 | `and(features.contains('switching'),not(features.contains('accessPoint')),model.ne('UDM Pro'))` | 200 | 8 | **WORKS.** Triple-compound. **This is the pure-switch filter.** Returns exactly 8 switches, no UDM, no AC IW. |
| 18 | `model.in('UDM Pro','UDM SE','UDM','UXG Pro','UXG Lite','USG','USG Pro','UDR','UCG Ultra')` | 200 | 1 | **WORKS.** Gateway-by-model-enumeration. Returns UDM Pro only. |

### Rejected filters (400)

| # | Filter expression | HTTP | Error message |
|---|---|---|---|
| 2 | `model.like('UDM*')` | 400 | `'like' is not allowed for 'model' at 1:7` |
| 9 | `model.like('USW*')` | 400 | `'like' is not allowed for 'model' at 1:7` |
| 15 | `ipAddress.like('172*')` | 400 | `'like' is not allowed for 'ipAddress' at 1:11` |
| 16 | `nonexistent.eq('foo')` | 400 | `unknown filter property 'nonexistent' at 1:1` |

---

## Live-verified operator matrix

Cross-referencing docs with live probes. "D" = documented only,
"L" = live-verified, "X" = live-verified 400 rejection.

| Property | Type | eq | ne | in | notIn | like | contains | containsAny | containsAll | isEmpty | isNull | gt/ge/lt/le |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `id` | UUID | D | D | D | D | — | — | — | — | — | — | — |
| `macAddress` | STRING | D | D | D | D | — | — | — | — | — | — | — |
| `ipAddress` | STRING | D | D | D | D | X (400) | — | — | — | — | — | — |
| `name` | STRING | D | D | D | D | L | — | — | — | — | — | — |
| `model` | STRING | L | L | L | L | X (400) | — | — | — | — | — | — |
| `state` | STRING | L | D | D | D | — | — | — | — | — | — | — |
| `supported` | BOOLEAN | D | D | — | — | — | — | — | — | — | — | — |
| `firmwareVersion` | STRING | D | D | D | D | L | — | — | — | — | D | D |
| `firmwareUpdatable` | BOOLEAN | D | D | — | — | — | — | — | — | — | — | — |
| `features` | SET(STRING) | — | — | — | — | — | L | L | D | D | — | — |
| `interfaces` | SET(STRING) | — | — | — | — | — | L | D | D | D | — | — |

**Key limitation: `model` does NOT support `like`.** This means
pattern-matching (e.g., `model.like('UDM*')` to catch all gateway
models) is not available. The API only allows exact match (`eq`),
negation (`ne`), and set membership (`in`, `notIn`) on `model`.

**Only `name` and `firmwareVersion` support `like`** among all
filterable properties.

---

## Compound expression syntax (live-verified)

All three compound expression types work:

| Syntax | Example | Live status |
|---|---|---|
| `and(expr1, expr2, ...)` | `and(features.contains('switching'),model.ne('UDM Pro'))` | 200 |
| `or(expr1, expr2, ...)` | `or(features.contains('accessPoint'),features.contains('gateway'))` | 200 |
| `not(expr)` | `not(features.contains('accessPoint'))` | 200 |
| Nested | `and(features.contains('switching'),not(features.contains('accessPoint')))` | 200 |
| Triple+ | `and(a,not(b),c)` with 3 terms | 200 |

---

## Error message format

400 errors return a structured JSON body with helpful diagnostics:

```json
{
  "statusCode": 400,
  "statusName": "BAD_REQUEST",
  "code": "api.request.invalid-filter",
  "message": "failed to parse filter expression: <detail> at <line>:<col>",
  "timestamp": "<ISO 8601>",
  "requestPath": "<path>",
  "requestId": "<uuid>"
}
```

The `<detail>` string takes two forms:
- **Disallowed operator:** `'like' is not allowed for 'model'`
- **Unknown field:** `unknown filter property 'nonexistent'`

The `at <line>:<col>` suffix pinpoints the position in the filter
expression string where parsing failed.

---

## Gateway discrimination strategies

The core problem: the UDM Pro reports `features: ["switching"]`
and does NOT include `"gateway"`. Three viable server-side
strategies exist, each with different tradeoffs.

### Strategy A: `model.eq('UDM Pro')` (exact match)

```
?filter=model.eq('UDM Pro')
```

- **Result:** 1 device (correct)
- **Pro:** Simple, exact, fast.
- **Con:** Breaks if the customer has a different gateway model
  (UDM SE, UXG Pro, USG, etc.). The filter is hardcoded to a
  single model string.

### Strategy B: `model.in(...)` with gateway model enumeration

```
?filter=model.in('UDM Pro','UDM SE','UDM','UXG Pro','UXG Lite','USG','USG Pro','UDR','UCG Ultra')
```

- **Result:** 1 device on this lab (correct)
- **Pro:** Catches all known gateway models.
- **Con:** Requires maintaining a model-name allowlist. If Ubiquiti
  releases a new gateway model with a new name, it won't be
  matched until the list is updated. The model name strings are
  human-readable (e.g., `"UDM Pro"` not `"UDMPRO"`), which means
  they could theoretically change between firmware versions
  (though this is unlikely).

### Strategy C: Exclude by subtraction

```
?filter=and(features.contains('switching'),not(features.contains('accessPoint')))
```

Then client-side: the one device that has `switching` but is NOT a
known USW model pattern is the gateway.

- **Result:** 9 devices (8 pure switches + UDM Pro)
- **Pro:** No hardcoded model names. Works with any gateway that
  has `switching` feature.
- **Con:** Requires client-side post-filtering to separate UDM from
  switches. Not purely server-side.

### Recommended for MP design: Strategy B with fallback

Use `model.in(...)` with the known gateway model list for the
gateway object type request. Maintain the list in MP configuration.
Fall back to Strategy C (subtraction + client-side model check) if
the model list proves too brittle.

For **pure switches** (excluding both UDM and dual-feature APs):

```
?filter=and(features.contains('switching'),not(features.contains('accessPoint')),model.ne('UDM Pro'))
```

This returns exactly 8 pure switches on this lab. For a generalized
MP, replace `model.ne('UDM Pro')` with `model.notIn('UDM Pro','UDM SE',...)`.

---

## Clean-up

No objects were created. All probes were read-only GET requests.
No clean-up required.

---

## Cross-references

- `context/api-maps/unifi-integration-api.md` -- full API map
  (Finding 2 documents the filterable properties from the v10.1.84
  OpenAPI spec; this probe live-verifies and extends those findings)
- `designs/unifi-mp-v2.md` -- MP design that will consume these
  findings for the gateway identification gap (action item #4)
