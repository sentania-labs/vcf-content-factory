# Suite API batch push: stats and properties for many resources in one call

**Question:** can a stitching adapter push stats and properties for many
foreign resources in one Suite API call on 8.18, 9.0 and 9.1, and what
would `SuiteApiStitcher` need to do it?

**Asked by:** compliance build 103 TOOLSET GAP
(sentania-labs/vcf-content-factory-sdk-compliance#17, "Two Suite API pushes
per object per cycle"). Design context:
`knowledge/designs/sdk-adapters/compliance-bulk-collection.md` §3.

**Date / evidence base (2026-10-28):**

- `reference/docs/operations-api.json` (9.0) and `operations-api-9.1.json`;
  `internal-api.json` and `internal-api-9.1.json` (no push endpoints there).
- Specs served live by each devel instance, read with GETs only:
  9.0.2.0 (`devel`, `/suite-api/doc/openapi/v3/public-api.json`), 9.1.1.0
  (`devel_9_1`, same path) and Aria Operations 8.18.7 (`devel_8_18`,
  springfox Swagger 2.0 at `/suite-api/doc/v2/api-docs?group=Public%20APIs`,
  listed by `/suite-api/doc/swagger-resources`). The 8.18.7 pair is now
  checked in verbatim as `reference/docs/operations-api-8.18.json` and
  `reference/docs/internal-api-8.18.json`.
- The framework source: `src/vcfcf_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/SuiteApiStitcher.java`
  and `SuiteApiStitchClient.java`.
- Three live writes on `devel_8_18`, all same-value (below).

All endpoints here are in the **supported public** spec on every version.
No `X-Ops-API-use-unsupported` header is involved.

## Verdict

| Question | Answer | Confidence |
|---|---|---|
| Bulk endpoints exist? | Yes: `POST /api/resources/stats` and `POST /api/resources/properties` | Spec on all three lines |
| Same on 8.18, 9.0, 9.1? | Same paths, same query params, same 200-only response, same JSON shape in the vendor examples on all three. 9.0 and 9.1 schemas are identical (key order only). 8.18's generated schema shows different field names (below); its own JSON example agrees with 9.x | High. 8.18 stats batch in the 9.x shape proven landed (live test 2); 8.18 properties batch accepted with 200 (live test 1, landing not observable for a same-value property) |
| Stats and properties in one request? | **No.** No schema in any of the six specs references both `stat-content` and `property-content`; the two bulk bodies are separate types | Spec, all versions |
| Partial failure reported per resource? | **No.** Response is `200` with no body (`Content-Length: 0`). An id that matches no resource is **silently dropped**: the batch still returns 200 and the other resources land, even when the bad id comes first (live test 3) | Spec + live on 8.18.7 |
| Documented batch size limit? | **None** in any spec, on either endpoint | Spec |

Cost change: today 2 requests per object per cycle. With batching, 2
requests per batch (one stats, one properties), so `2 x ceil(N / B)`.

## Endpoints

| Method + path | operationId 9.0 / 9.1 | operationId 8.18 (springfox) | Body schema | Query |
|---|---|---|---|---|
| `POST /api/resources/stats` | `addStatsForResources` | `addStatsForResourcesUsingPOST` | `resources-stat-contents` | `disableAnalyticsProcessing` (bool, default false) |
| `POST /api/resources/properties` | `addResourcesProperties` | `addResourcesPropertiesUsingPOST` | `resources-property-contents` | none |
| `POST /api/resources/{id}/stats` (today) | `addStats` | `addStatsUsingPOST` | `stat-contents` | `disableAnalyticsProcessing` |
| `POST /api/resources/{id}/properties` (today) | `addProperties` | `addPropertiesUsingPOST` | `property-contents` | none |

Do **not** use the `.../adapterkinds/{adapterKind}` variants
(`addStatsForResourcesUsingPushAdapterKind`,
`addResourcesPropertiesUsingAdapterKind`). The spec: "If the adapter kind
specified is not present in the system, it will be created dynamically.
However if the adapter kind specified already exists, then it must be of
*OPENAPI* adapter kind type." An SDK pak's own kind is not OPENAPI, and
passing a different kind would create one. The plain bulk paths have the
same attribution note as the per-id paths the facade uses today (adapter
instance defaults to `vRealizeOpsMgrAPI`), so switching does not change
where the data is attributed (INFERENCE from the doc text; the per-id
properties doc says `SuiteAPI`, the per-id stats doc `vRealizeOpsMgrAPI`).

Keep `disableAnalyticsProcessing` unset (false). With true, "no evaluation
of Alerts but the data gets stored": the compliance symptoms and alerts
would stop.

## Request shapes (JSON, all versions)

Stats, many resources:

```json
{
  "resource-stat-content": [
    {
      "id": "<resource uuid>",
      "stat-contents": [
        { "statKey": "Group|key", "timestamps": [1793178366127], "data": [1.0] }
      ]
    }
  ]
}
```

Properties, many resources:

```json
{
  "values": [
    {
      "resourceId": "<resource uuid>",
      "property-contents": {
        "property-content": [
          { "statKey": "Group|key", "timestamps": [1793178366127], "values": ["text"] }
        ]
      }
    }
  ]
}
```

Watch the asymmetries, they are the likely bugs:

- Stats entry key is **`id`**; properties entry key is **`resourceId`**.
- Inside a stats entry, `stat-contents` is a **bare array** of
  `stat-content`. Inside a properties entry, `property-contents` is an
  **object** wrapping a `property-content` array (the same object the
  per-id properties body is, so the facade's existing
  `buildPropertiesJson` output nests unchanged; its `buildStatsJson`
  output does **not**: drop the `{"stat-content": ...}` wrapper and use
  the array).
- Outer keys: `resource-stat-content` (stats) vs `values` (properties).

Required fields (9.x schema): `resource-stat-content[].id`;
`stat-content.statKey`, `.timestamps`; `values[].resourceId`,
`values[].property-contents`, `property-contents.property-content`;
`property-content.statKey`, `.timestamps`. `data` (double array) or
`values` (string array) per entry, "both types of the data cannot be sent
together". Timestamps in epoch milliseconds. `resource-stat-content[]`
also accepts an optional `resourceKey`; not needed when `id` is set.

### 8.18 schema caveat

The 8.18.7 springfox schema names two fields differently from its own
JSON example and from 9.x:

| Schema | 8.18 generated schema field | 8.18 JSON example and 9.x |
|---|---|---|
| `resources-stat-contents` | `list` | `resource-stat-content` |
| `resource-property-contents` | `properties` (required) | `property-contents` |

Springfox reads Java field names; the wire is serialized from the JAXB
names, which the XML and JSON examples on the same 8.18 operation both
use. The 8.18 per-id schemas (`stat-content`, `property-content`) match
9.x exactly. Treat the 9.x names as the wire format on 8.18 (INFERENCE,
now proven for stats: the 8.18 stats batch keyed `resource-stat-content` landed, live test 2).

## Live test 1: properties batch, same value (devel_8_18, 8.18.7)

Target: host `vcf-lab-mgmt-esx02` (`1e9de40c-b045-4f9e-9b4f-be7d471773e6`),
property `VCF-CF Compliance|esx.ssh|Expected`, which the compliance pak
writes every cycle, value `false`.

```
POST /suite-api/api/resources/properties
{"values": [{"resourceId": "1e9de40c-b045-4f9e-9b4f-be7d471773e6",
  "property-contents": {"property-content": [{"statKey":
  "VCF-CF Compliance|esx.ssh|Expected", "timestamps": [1793178366127],
  "values": ["false"]}]}}]}

HTTP 200, Content-Length: 0, empty body
```

Read back with `POST /api/resources/properties/latest/query`
(`{"resourceIds":[...],"propertyKeys":[...],"instanced":false}`): value
`false`, timestamp `1793177850854` before the write, the same after it,
and the same at six polls over two minutes. The compliance cycle at
04:02 CDT, which pushed the same value through the per-id path, did not
move it either. Properties are stored only on change
(`knowledge/context/reviews/compliance-build-58.md` says the same), so a
same-value write is accepted but leaves no trace. **What this proves:**
8.18 accepts the 9.x property batch shape with 200. **What it does not:**
that the data landed. Nothing to clean up: the value was unchanged and no
object was created.

## Live test 2: stats batch, same value (devel_8_18, 8.18.7)

Same host, stat `VCF-CF Compliance|total_count`, which the compliance pak
pushes every cycle, current value `48.0` (latest sample `1793178450846`).

```
POST /suite-api/api/resources/stats
{"resource-stat-content": [{"id": "1e9de40c-b045-4f9e-9b4f-be7d471773e6",
  "stat-contents": [{"statKey": "VCF-CF Compliance|total_count",
  "timestamps": [1793178725960], "data": [48.0]}]}]}

HTTP 200, Content-Length: 0, empty body
```

`GET /api/resources/stats/latest` did not show it: the pak's own cycle
pushed a later sample (`1793178751610`) before the next poll, and latest
returns only the newest point. The raw series did:
`POST /api/resources/stats/query` with
`{"resourceId":[<host>],"statKey":["VCF-CF Compliance|total_count"],"begin":1793178000000,"end":1793178900000}`
(no `rollUpType`; `"NONE"` is rejected with apiErrorCode 1501 "unit is
null") returned `(1793178151217, 48.0), (1793178450846, 48.0),
(1793178725960, 48.0), (1793178751610, 48.0)`. The third point is this
write. **The 9.x stats batch shape lands on 8.18.**

## Live test 3: partial failure (devel_8_18, 8.18.7)

One batch of two entries: first a random UUID
`35603c17-6c40-4137-a41d-2fb406281543` (checked first:
`GET /api/resources/<uuid>` 404 "No such Resource"), then the real host,
same stat and value as test 2.

```
POST /suite-api/api/resources/stats
{"resource-stat-content": [
  {"id": "35603c17-6c40-4137-a41d-2fb406281543", "stat-contents": [{"statKey":
   "VCF-CF Compliance|total_count", "timestamps": [1793178887347], "data": [48.0]}]},
  {"id": "1e9de40c-b045-4f9e-9b4f-be7d471773e6", "stat-contents": [{"statKey":
   "VCF-CF Compliance|total_count", "timestamps": [1793178887347], "data": [48.0]}]}]}

HTTP 200, Content-Length: 0, empty body
```

- **The real resource landed:** `(1793178887347, 48.0)` appeared in the
  raw series 15 to 30 s after the 200.
- **The unknown id was dropped without a trace:** still 404 on
  `GET /api/resources/<uuid>`, and `stats/query` for it answers 404 "The
  Resources ... were not found". No resource was created.
- **No extra adapter instance:** `GET /api/adapters` shows a single
  `vRealizeOpsMgrAPI` instance (the collector's default), so the batch
  path did not mint one. No before-snapshot was taken, so this shows the
  end state only.
- **Logs: not read.** SSH key auth to the 8.18 node is refused, `.env`
  has no SSH password for it, and the Suite API has no log-read endpoint
  (8.18 `/api/logs*` is configuration and forwarding only). Whether the
  server logs the dropped id is UNKNOWN.

Untested: a malformed entry (missing `statKey`, both `data` and
`values`), which may 4xx the whole batch rather than drop one entry; and
the same probe on the properties batch (assumed to behave alike,
INFERENCE). What the per-id path does with an unknown id was not tested
here.

Clean-up: all three writes carried the value already stored; the extra
samples are identical to the pak's own at adjacent timestamps. Nothing
was created.

## What the facade does today

`SuiteApiStitcher` delegates to `SuiteApiStitchClient`:

- **Auth:** `POST /api/auth/token/acquire` with `authSource` `LOCAL` and a
  credential resolved ambient-first (injected per-instance credential,
  then `automationuser.properties`, then `maintenanceuser.properties`; no
  file on a Cloud Proxy) or explicit. Header `Authorization: OpsToken
  <token>`. Token cached per client, re-acquired and the request retried
  **once** on 401, released on `discard()`/`close()`.
- **Transport:** `HttpURLConnection` from
  `VcfCfAdapter.openPlatformConnection`, connect and read timeout 30 s,
  `Content-Type: application/json`, `Accept: application/json`.
- **Payloads:** `pushProperties(id, Map<String,String>, ts)` posts
  `{"property-content":[{statKey,timestamps:[ts],values:[v]}...]}` to
  `/api/resources/{id}/properties`; `pushStats(id, Map<String,Double>, ts)`
  posts `{"stat-content":[{statKey,timestamps:[ts],data:[v]}...]}` to
  `/api/resources/{id}/stats`. One timestamp per call.
- **Failure contract:** never throws; one WARN line per failure (trace at
  DEBUG), interrupt flag restored. Non-2xx surfaces as
  `SuiteApiHttpException` (status, `apiErrorCode`, 512-char body excerpt).

## Payload size (measured, read-only)

Compliance data currently on one object, serialized as a batch entry:

| Instance | Kind | Properties | Property bytes | Stats | Stat bytes |
|---|---|---|---|---|---|
| 8.18.7 | HostSystem | 148 | ~53 KB | 57 | ~6 KB |
| 8.18.7 | VirtualMachine | 70 | ~34 KB | 31 | ~3 KB |
| 9.0.2 | HostSystem | 439 | ~145 KB | 57 | ~6 KB |
| 9.0.2 | VirtualMachine | 181 | ~56 KB | 50 | ~6 KB |

Properties dominate, mostly the per-control `Description` text. A
100-host property batch would be about 14 MB on 9.0.2. A count-only
chunk size is not safe; chunk by bytes too. Sending properties only when
they change (design §3) cuts more than batching does.

## What a batch API on the facade needs

**Built in buildkit 1.0.24** as `SuiteApiStitchClient` / `SuiteApiStitcher`
`pushPropertiesBatch`, `pushStatsBatch` and `pushBatch` (properties, then
stats), returning `SuiteApiBatchResult`. Choices the list below left open:
`disableAnalyticsProcessing` is never sent (the live tests ran without it);
a failure with no HTTP status (timeout, refused connection) is not re-sent
per id, only logged, since it may have been applied and re-sending to an
unreachable server costs a timeout per resource; a 401 that survives the
one re-acquire is not re-sent per id either; batch read timeout is 120 s.
Null keys, null values and non-finite stats are dropped before serializing,
so they cannot turn a whole batch into a 400.

1. **Two methods**, same no-throw contract as today:
   `pushPropertiesBatch(Map<String, Map<String,String>> byResource, long ts)`
   and `pushStatsBatch(Map<String, Map<String,Double>> byResource, long ts)`.
   Return a small result (resources sent, batches ok, batches failed,
   resources that fell back) so the adapter can count, not just log.
2. **Chunking by both count and bytes.** No documented limit. Proposed
   defaults until measured: at most 100 resources and about 1 MB of JSON
   per request, whichever comes first, both settable. One resource larger
   than the byte cap goes alone. Serialize per resource first, then pack.
3. **Correct builders** per the asymmetries above (`id` vs `resourceId`,
   bare array vs wrapped object). Skip resources with an empty map; skip
   the request when nothing is left. Validate ids with the existing
   `isUuid`, since an id is now in a body, not a path.
4. **Partial failure:** the response names nothing, and a stale or
   unknown id does **not** fail the batch: it is dropped and the call
   still returns 200 (live test 3). So a 200 means "accepted", not
   "every id landed", and the per-id fallback will not catch a stale id.
   Stale ids must be caught where ids are resolved (the adapter's
   `ForeignResourceResolver` refresh), not from the push result. Keep a
   fallback for a non-2xx batch (a malformed entry or a server error can
   still fail the whole call): one WARN naming the count and the first
   few resource ids (through `loggable`), then retry that chunk's
   resources once on the per-id path.
5. **Retry semantics:** keep the single 401 re-acquire and retry. No
   blind retry on 5xx or timeout beyond the per-id fallback. A timeout is
   ambiguous (the batch may have been applied); re-pushing the same
   timestamp and value is expected to be harmless (properties are stored
   on change; a stat re-sent at the same timestamp should overwrite the
   same point, INFERENCE). Consider a longer read timeout for batch calls
   than the 30 s per-id one.
6. **Ordering:** if any adapter depends on properties being visible before
   stats in the same cycle, keep properties first, as compliance's
   per-object calls do today.

## Open

1. **Size ceiling: not probed by decision.** Tooling uses conservative
   byte and count caps instead.
2. Partial failure on 9.0 and 9.1 and on the properties batch: not
   tested; assumed the same as 8.18 stats (INFERENCE, same spec family).
3. Server-side logging of a dropped id: unknown without node log access.
