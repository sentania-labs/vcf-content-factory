# vCommunity notification-event parity — foreign-VM event push

**Date:** 2026-06-22
**Agent:** api-explorer
**Question:** Can the `vcfcf_vcommunity` Tier-2 Java adapter emit Windows
event-log entries as **real VCF Ops notification events** stapled onto foreign
VMWARE VirtualMachine resources — matching the original Python pak — or is the
property-degradation (TOOLSET GAP #1) the architectural ceiling?

**Verdict (one line):** **Reachable.** The public Suite API exposes
`POST /api/events/bulk` which targets *any* resource by UUID — the same UUID the
stitcher already resolves for foreign VMWARE VMs. Parity is a small framework
addition (a `pushEvents` helper alongside `pushProperties`/`pushStats`), not new
transport. It is a **v1-scope fix**, with one empirical check flagged below.

---

## 1. How the original sends one event

`reference/references/.../app/events/vm/collect_windows_event_logs.py:183` — per CSV row:

```python
vm_obj.with_event(
    message=formattedMessage,          # f"[WindowsEvent-{eventLevel} {eventMessage}"
    criticality=criticality,           # aria.ops.event.Criticality.{INFO|WARNING|IMMEDIATE|CRITICAL}
    auto_cancel=True,
    watch_wait_cycle=1,
    cancel_wait_cycle=3,
    update_date=now,                   # int(time.time()*1000)
)
```

Level→Criticality map (lines 168–179): Information/Verbose→INFO, Warning→WARNING,
Error→IMMEDIATE, Critical→CRITICAL, else→INFO.

**The foreign-resource wrinkle — how it works.** `vm_obj` is NOT a resource the
adapter owns. In `collectVMData.py:44-61`, `vm_obj` is fetched from
`suite_api_client.query_for_resources({"adapterKind":["VMWARE"],
"resourceKind":["VirtualMachine"], "adapterInstanceId":[...]})` — i.e. an
`aria.ops.object.Object` **handle to a VMware-adapter-owned VM**, keyed by
`VMEntityObjectID` (the vim `_moId`). The Python Integration SDK lets you staple
events/metrics/properties onto a foreign object handle and `result.add_object(vm_obj)`
(line 80); `result.send_results()` serializes the whole `CollectResult` and the
platform routes each object's payload to the resource named by its key. So in the
Python SDK model, **a foreign-resource event is just an event riding in the
collection result on a foreign object handle** — no distinct REST call. `auto_cancel`
+ `watch_wait_cycle`/`cancel_wait_cycle` are the SDK's expression of
"externally-managed event, auto-clear after N cycles if not re-pushed."

## 2. Can our adapter reach an equivalent path?

Our Java adapter does **not** use a native collection-result for foreign resources.
Two distinct sinks (`VCommunityAdapter.collectWorld`):

- **`out` (List<MetricData>)** — native result, but only for resources the adapter
  *owns* (the synthetic `vCommunityWorld` INTERNAL anchor). MetricData carries
  metrics + properties only; there is no event channel and it cannot target a
  foreign VMWARE VM. **Dead end for foreign events.**
- **`SuiteApiStitcher`** (`VCommunityStitcher` → framework
  `SuiteApiStitchClient`) — REST facade that resolves a foreign VM's UUID from
  `/api/resources` and POSTs onto it. Today only:
  - `POST /api/resources/{id}/properties`  (`buildPropertiesJson`)
  - `POST /api/resources/{id}/stats`        (`buildStatsJson`)
  - `GET  /api/resources?...`               (UUID resolution)

  `rawPost` is private; there is no public `pushEvents`/generic `post`.

### (a) Is there a Suite API endpoint that posts events onto a foreign resource? YES.

Public **operations-api.json** (tag `Events`, no `X-Ops-API-use-unsupported`
required — it is NOT internal-only):

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/events` | Push a single event |
| POST | `/api/events/bulk` | Push N events (one request) |
| POST | `/api/events/adapterkinds/{adapterKind}` | Single, source = adapterKind |
| POST | `/api/events/bulk/adapterkinds/{adapterKind}` | N events, source = adapterKind |

**`event` schema** (required: `eventType`, `message`, `resourceId`):

| field | maps to original | notes |
|---|---|---|
| `resourceId` (uuid, **required**) | the foreign VM | **The crux.** Targets *any* resource by UUID — exactly the UUID `VCommunityStitcher.Entry.resourceId` already holds. No ownership constraint in the schema. |
| `message` (**required**) | `message=` | identifies the event in-system |
| `eventType` (**required**) | — | enum; use `NOTIFICATION` for an event-log entry (`CHANGE/RESOURCE_DOWN/HARD_THRESHOLD/DIAGNOSTIC/...` are the others) |
| `severity` (xml `criticality`) | `criticality=` | enum `UNKNOWN/NONE/INFORMATION/WARNING/IMMEDIATE/CRITICAL/AUTO` — **direct 1:1 with the Python `Criticality` map** |
| `notificationSubType` | — | enum `LOG/UNKNOWN` — set **`LOG`** for a Windows event-log entry |
| `startTimeUTC` (int64 ms) | `update_date=now` | must be >= 946684800000 (2000-01-01) |
| `cancelTimeUTC` (int64 ms) | the clear | "for an externally managed event a new event with the **same `message`** must be sent with a cancelTime to cancel it" |
| `managedExternally` (bool) | `auto_cancel`/cycle counts | **true** = persists across cycles until changed; **false** = auto-cancelled next cycle if not re-pushed. This is the Java equivalent of `auto_cancel=True` + `cancel_wait_cycle`. |

`events` (bulk) schema = `{ "event": [ <event>, ... ] }`.

### (b) Native collection-result event path? NO (and not worth adding).

Our framework reports foreign resources only via the REST stitcher, never via a
native multi-object CollectResult the way the Python SDK does. The `MetricData`
list is single-resource (the owned anchor) and has no event slot. Replicating the
Python "event rides in the result on a foreign object handle" model would mean
re-architecting reporting onto a CollectResult-with-foreign-objects abstraction —
unnecessary, because path (a) achieves the identical outcome over the transport we
already have.

## 3. Verdict + recipe

**Notification-event parity is reachable and v1-scope.** Not a property-flood
fallback — a real `NOTIFICATION`/`LOG` event per matched event-log row on the
foreign VM, with proper criticality and auto-clear.

### Recipe — emit one Windows-event-log event onto a foreign VM

1. Resolve the foreign VM UUID — already done:
   `VCommunityStitcher.matchVm(name, moid).resourceId`.
2. Framework addition (`tooling`, in `SuiteApiStitchClient` + `SuiteApiStitcher`):
   a `pushEvents(List<Event>, ...)` helper that builds the `events` body and
   `rawPost("/api/events/bulk", body, tok)`. Reuses the existing token-acquire/
   release + platform-SSL machinery verbatim — no new transport. (Alternatively a
   generic `post(path, body)`; a typed `pushEvents` is cleaner and mirrors
   `pushProperties`.)
3. Per CSV row build:
   ```json
   {
     "eventType": "NOTIFICATION",
     "notificationSubType": "LOG",
     "resourceId": "<foreign-vm-uuid>",
     "message": "[WindowsEvent-<level>] <event text>",
     "severity": "WARNING",            // mapped from Level, same table as Python
     "startTimeUTC": <epoch-ms>,
     "managedExternally": true
   }
   ```
   Batch all rows for the cycle into one `POST /api/events/bulk`
   (one request, not one per row — avoids the property-flood concern entirely).
4. **Clearing:** with `managedExternally:true`, re-POST the same `message` with a
   `cancelTimeUTC` set once the condition clears (event no longer present). If you
   instead want the Python `auto_cancel` behaviour (auto-clear when not re-pushed
   next cycle), set `managedExternally:false` and simply stop re-pushing — the
   platform cancels it on the following collection cycle. The latter is the closer
   match to `auto_cancel=True` and is simpler (no explicit cancel bookkeeping).
   Recommend `managedExternally:false` for event-log parity.

### Uncertainty / EMPIRICAL VERIFY before relying on it

- **Foreign-resource targeting is asserted from the schema, not yet tested.** The
  `event.resourceId` field has no documented ownership constraint, and properties/
  stats already push onto foreign VMWARE UUIDs successfully via the same token —
  so events almost certainly accept the same UUIDs. **But confirm against the live
  appliance:** POST one event to a known VMWARE VirtualMachine UUID and verify it
  appears on that VM's events/troubleshoot timeline (not rejected for cross-adapter
  ownership). `GET /api/events` returns 500 in our lab (surface doc item 9/§756),
  but that is the *read* path with missing query params — it does not bear on the
  POST push path.
- **adapterKind variant:** `POST /api/events/bulk/adapterkinds/vcfcf_vcommunity`
  tags the event's *source* as our adapter (cleaner provenance) while still
  targeting the foreign VM by `resourceId`. Prefer this variant; verify the
  adapterKind path accepts our kind during the same live test.
- **Auth:** identical to the existing stitcher (ambient maintenance token via
  `/api/auth/token/acquire`). No extra credential surface.

**Not** a deferral. The TOOLSET GAP #1 framing ("framework Suite API facade
exposes only properties/stats") is accurate *about today's facade* but the gap is
a missing thin helper, not a missing capability — the endpoint and the resolved
UUID both already exist. Recommend reclassifying from "v1.1 future work" to "v1
framework addition + one live POST verification."

---

## Empirical test 2026-06-22 (api-explorer, live devel)

**Verdict: SPLIT — foreign-resource push WORKS, but `NOTIFICATION` events
are silently dropped. The v1 plan as written (NOTIFICATION/LOG on a foreign
VM) is RED. The transport (foreign-resource event push) is GREEN.**

### Setup

- Instance: `vcf-lab-operations-devel.int.sentania.net` (devel profile).
- Auth: standard `POST /suite-api/api/auth/token/acquire`,
  `Authorization: vRealizeOpsToken <tok>` (note: base is `/suite-api`, header
  is `vRealizeOpsToken` not `OpsToken` — used `vcfops_common.client.VCFOpsClient`).
- Target foreign resource: VMWARE VirtualMachine **`dcint1`** =
  `6a20cdd2-559e-46c0-814f-0c9d4beebb2e` (`adapterKindKey: VMWARE`, NOT owned
  by `vcfcf_vcommunity`). Resolved via `POST /api/resources/query`.
- Read-back path: `GET /internal/events?type=<T>&active=<bool>`
  (**unsupported — requires `X-Ops-API-use-unsupported: true`**). There is NO
  public `GET /api/events` (POST-only in the spec); the read used in earlier
  recon (`GET /api/events` → 500) is not a real endpoint. `/internal/events`
  works and was validated against 9 pre-existing real `DIAGNOSTIC` events.

### Result 1 — adapterKind-scoped variant: REJECTED (400)

`POST /api/events/bulk/adapterkinds/vcfcf_vcommunity` →
**400** `{"message":"The Adapter Kind \"vcfcf_vcommunity\" specified is not of
OPENAPI type.","apiErrorCode":1514}`.

Root cause: `GET /api/adapterkinds` shows `vcfcf_vcommunity` has
`"adapterKindType": "GENERAL"`, not `OPENAPI`. SDK/MPB-built adapter kinds are
GENERAL, so **the adapterKind-scoped event endpoints are categorically
unavailable to our adapter.** (Same is true of `vcfcf_compliance`.) Drop the
"prefer the adapterKind variant for provenance" recommendation entirely — it
cannot accept our kind.

### Result 2 — plain `/api/events/bulk`, eventType=NOTIFICATION: 200 but DROPPED

`POST /api/events/bulk` with a `NOTIFICATION` / `notificationSubType:LOG` event
onto the foreign VM returned **HTTP 200, empty body** — but the event **never
surfaced**. Polled `GET /internal/events?type=NOTIFICATION` for both
`active=true` and `active=false`, for **>3.5 minutes** total across multiple
attempts, with both `managedExternally:false` (auto-cancel) and
`managedExternally:true` (persistent). Result every time: **zero NOTIFICATION
events in the system** (`totalCount:0`). The 200 is not a success signal — the
event is silently discarded. (System-wide there are 0 NOTIFICATION events at
all, suggesting NOTIFICATION ingestion via this REST path may be disabled or
require a channel we don't have.)

### Result 3 — plain `/api/events/bulk`, eventType=DIAGNOSTIC: 200 and LANDED

Control test to isolate the variable. Same request shape, same foreign VM, same
auth, but `eventType:DIAGNOSTIC` / `diagnosticSubType:LOG`. POST → 200, and at
**t+45s** the event appeared on the foreign VM's timeline:

```json
{"eventId":"b752a3e0-eba7-4774-8459-ebf283f953c5","eventType":"DIAGNOSTIC",
 "resourceId":"6a20cdd2-559e-46c0-814f-0c9d4beebb2e",
 "message":"TEST vcommunity probe DIAG — safe to ignore",
 "severity":"WARNING","diagnosticSubType":"LOG","cancelTimeUTC":0}
```

This is the load-bearing finding: **cross-adapter foreign-resource event push
over `/api/events/bulk` genuinely works** — a `GENERAL`-type adapter's token
can staple an event onto a VMWARE-owned VM by `resourceId` with no ownership
rejection, and it surfaces on that VM (~45s ingestion lag). The transport the
v1 plan needs is real. The pre-existing 9 `DIAGNOSTIC` events (from
`vCenter_VMsnapshotover7days_KB_318825`) corroborate that DIAGNOSTIC is the
type that actually populates this surface.

### Interpretation: the variable is `eventType`, not foreign-resource targeting

Identical everything-else, only `eventType` differs: DIAGNOSTIC lands,
NOTIFICATION is dropped. So the original research's central worry
(cross-adapter ownership rejection) is **disproved — that part is GREEN**. The
new, unanticipated blocker is that **`NOTIFICATION` specifically does not
ingest via `/api/events/bulk`** on this build (9.x devel), while DIAGNOSTIC
does.

### Consequence for the v1 plan

- The recipe's `eventType:"NOTIFICATION"` + `notificationSubType:"LOG"` shape
  is **RED** — it will return 200 and vanish. A naive implementation would
  appear to work (200 OK) while producing nothing on the VM. This is exactly
  the silent-drop failure mode the framework is supposed to refuse.
- **Most promising pivot (needs its own verification before code):** emit the
  Windows event-log rows as `eventType:"DIAGNOSTIC"` /
  `diagnosticSubType:"LOG"` instead of NOTIFICATION/LOG. DIAGNOSTIC/LOG is
  semantically a log-derived diagnostic event and **is proven to land on the
  foreign VM**. It would surface on the VM's events/troubleshooting timeline
  rather than the notification stream — a presentation difference from the
  original Python pak, but a real, visible, foreign-resource event with correct
  criticality and message, which is the actual parity goal. Map the Python
  `Criticality` table to `severity` unchanged.
- Before committing the DIAGNOSTIC pivot to code, confirm with the user whether
  surfacing on the diagnostic/troubleshoot timeline (vs. the notification
  stream) is acceptable parity, and verify the auto-cancel behaviour:
  `managedExternally:false` + stop-re-pushing as the `auto_cancel=True`
  analogue (this probe used `managedExternally:true` and cleared via explicit
  `cancelTimeUTC`, which also works).
- Keep using **plain `/api/events/bulk`** (the adapterKind-scoped variant is
  permanently closed to GENERAL adapters — Result 1).

### Auth / endpoint corrections to the recipe above

- Token header is `vRealizeOpsToken`, base path `/suite-api` (the §"recipe"
  pseudocode is endpoint-correct; just noting the wire details).
- There is no GET on `/api/events`; use `/internal/events` (unsupported header
  required) for verification only — not a runtime dependency of the adapter.

### Clean-up — VERIFIED

The DIAGNOSTIC test event was `managedExternally:true` (persistent), so it was
explicitly cancelled by re-POSTing the same `message` with `cancelTimeUTC`. The
two persistent NOTIFICATION probe messages were defensively cancelled the same
way (harmless since they never ingested). Confirmed via `/internal/events`:
active DIAGNOSTIC count returned to the original **9** (test event gone at
t+30s after cancel), and a sweep across DIAGNOSTIC/NOTIFICATION/CHANGE/
HARD_THRESHOLD shows **zero remaining active `TEST vcommunity` events**. Devel
is clean. No resources, properties, or stats were created or modified — events
only.
