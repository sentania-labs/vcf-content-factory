# API pattern catalog

Recognition guide for well-known API shapes the framework has built
against. The goal is to short-circuit the wizard-style "ask the user
about every modeling decision" pattern: when api-cartographer
identifies a known shape, mp-designer should propose the canonical
object model and only ask about real ambiguities.

## How to use this catalog

When `mp-designer` reads an api-cartographer report:

1. Match the API against the **Signature** column of each entry
   below. Signatures are bytes-on-the-wire fingerprints: characteristic
   endpoints, response envelopes, header conventions, identifier
   shapes.
2. If matched, propose the entry's **Default object model**. Only
   interview the user on the items under **Real ambiguities** — those
   are decisions where two reasonable users would pick differently.
3. Read the **Known limitations** before finalizing the design.
   Several catalog entries have framework gaps documented from
   real failures.
4. If no entry matches, walk the generic OpenAPI / REST path and
   ask api-cartographer for a deeper map. Add the new pattern to
   this catalog after the MP ships.

Catalog grows by experience, not by hypothesis. Only entries we've
actually built against (or have ground-truth references for) belong
here.

---

## Redfish (DMTF DSP0266 — server hardware management)

### Signature

- Service root at `/redfish/v1/` returning `@odata.context`,
  `@odata.id`, `@odata.type` fields.
- Every response carries `@odata.id` (URL of the resource) and
  `@odata.type` (schema reference).
- Top-level collections at `/redfish/v1/Systems`,
  `/redfish/v1/Chassis`, `/redfish/v1/Managers`.
- `Server: RedfishMockupHTTPD_...` or vendor-specific (iDRAC, iLO,
  XClarity) on responses.
- Hierarchy encoded in URL paths:
  `/Systems/{id}/Processors/{cpu}`,
  `/Chassis/{id}/Thermal#/Fans/{n}`, etc.

### Auth

- HTTP Basic Auth on every request (stateless), or
- Session-based: `POST /redfish/v1/SessionService/Sessions` with
  credentials → returns `X-Auth-Token` in response header → send
  on subsequent requests. Required for high-volume polling on some
  iDRAC firmware versions.

Public-facing mocks usually accept Basic on every request without
session preference.

### Default object model

- **System** (one per managed BMC) — identifier from `Id` field
  (typically `System.Embedded.1` on Dell, similar on other vendors).
- **Processor** (per CPU) — from `/Systems/{id}/Processors/Members[*]`.
- **Memory DIMM** — from `/Systems/{id}/Memory/Members[*]`.
- **Network Interface** — from `/Systems/{id}/EthernetInterfaces/Members[*]`.
- **Drive** — from `/Systems/{id}/Storage/{ctrl}/Drives[*]`.
- **Fan** — from `/Chassis/{id}/Thermal#/Fans[*]`.
- **Temperature Sensor** — from `/Chassis/{id}/Thermal#/Temperatures[*]`.
- **Power Supply** — from `/Chassis/{id}/Power#/PowerSupplies[*]`.
- **Power Control** — from `/Chassis/{id}/Power#/PowerControl[*]`.
- **Firmware Component** — from `/UpdateService/FirmwareInventory/Members[*]`.
- Vendor OEM blocks (Dell `DellNumericSensors`, HPE `iLO`, etc.)
  surface as additional object types when present.

### Real ambiguities

- **Per-component object vs. instanced metric on parent.** See
  Known Limitations below — this isn't really a free choice today,
  but if the framework gains instanced-metric authoring, ask the
  user which they prefer for alerting granularity.
- **Vendor OEM scope.** Dell OEM blocks, HPE OEM blocks, etc.
  Default to "include vendor OEM data when present, skip otherwise."
- **Stitch to vSphere HostSystem?** If the user runs vCenter on the
  same instance, add an ARIA_OPS-stitched relationship matching on
  BIOS UUID (Server's `UUID` field).

### Known limitations

**MPB Tier 1 + Redfish cannot author per-component parent-child
relationships.** Documented in
`context/lessons_dell_redfish_2026_05_18.md`. Redfish encodes the
parent-child hierarchy in URL paths, not in flat scalar fields of
child response bodies. MPB's relationship model requires real
metric values that match between parent and child — Redfish doesn't
expose the parent identifier as a flat field on component responses.
All three of the factory's `adapter_instance`-scope strategies fail
against real MPB UI. The `field_match` approach requires either
regex extraction from `@odata.id` (not yet implemented) or
cross-request scalar broadcast (no abstraction for this in the
factory's metric DSL).

**For hardware MPs, recommend Tier 2 SDK authoring.** Onur's
vmbro/VCF-Operations-Hardware-vCommunity (Python Integration SDK)
sidesteps the relationship problem entirely by modeling every
component as an instanced metric on a single PhysicalServer object.
The Tier 2 native Java SDK path can do the same. Tier 1 hits the
wall by construction.

### Reference

- `references/vmbro_vcf_operations_hardware_vcommunity/` — Onur's
  Python adapter, canonical hardware-MP design for this API shape.
- `context/lessons_dell_redfish_2026_05_18.md` — full empirical
  writeup of what fails and why.
- `tmp/dell_v4_export_source.json` — original v4 design that
  inspired this catalog entry.

---

## Synology DSM (NAS management)

### Signature

- Login endpoint: `POST /webapi/auth.cgi` with `account` / `passwd`
  / `session` / `format=cookie` query params. Returns `SID` either
  as a JSON field or a cookie.
- Subsequent API calls: `GET /webapi/entry.cgi?api=SYNO.XYZ.ABC&...`
  with `_sid` query param (DSM6) or session cookie (DSM7).
- Discovery: `GET /webapi/query.cgi?api=SYNO.API.Info&method=query&version=1`
  returns the catalog of available APIs and their endpoints.
- JSON response envelope always `{ "success": true|false, "data": {...} }`
  or `{ "success": false, "error": { "code": N } }`.

### Auth

Session-cookie auth via the login flow above. The framework's
session-cookie auth strategy handles this — declare it in the MP
YAML's `source.auth` block.

### Default object model

- **Diskstation** (the NAS itself) — singleton; identifier from
  serial number returned by `SYNO.Core.System`.
- **Volume** — from `SYNO.Core.Volume` list endpoint; parent: Diskstation.
- **Storage Pool** — from `SYNO.Storage.CGI.Pool`; parent: Diskstation.
- **Disk** (physical) — from `SYNO.Storage.CGI.HddMan`; parent:
  Diskstation (disks are peers of pools/volumes, not nested under
  them, in DSM's model).
- **Share** — from `SYNO.FileStation.List`; parent: Volume.
- **iSCSI LUN / Target** — from `SYNO.Core.ISCSI.LUN` /
  `SYNO.Core.ISCSI.Target`; parent: Diskstation.

### Real ambiguities

- **DSM6 vs DSM7.** API surface differs significantly — api-cartographer
  should detect and choose path conventions. DSM7 prefers session
  cookies; DSM6 accepts both `_sid` query param and cookies.
- **Photo Station / Video Station / Note Station extras.** Skip
  unless the user explicitly asks; they're optional packages and
  not present on every NAS.

### Known limitations

Same MPB Tier 1 relationship gap that hit Dell applies in
principle, but Synology happens to expose enough shared scalar
identifiers (volume IDs in disk responses, pool IDs in volume
responses) to make `field_match` workable for many parent-child
edges. Walk each relationship case-by-case rather than assuming
the gap blocks everything.

### Reference

- `references/sentania_aria_operations_dsm_mp/` — sentania's
  Synology DSM MPB design as starting point. 4 object types, 9
  requests, 1 declared relationship in current state.

---

## UniFi Network (Ubiquiti)

### Signature

- Login endpoint: `POST /api/login` (UniFi OS) or
  `POST /api/auth/login` (controller mode) with `username` /
  `password` JSON body. Returns session cookies (`TOKEN`,
  `unifises`, `csrf_token`).
- Subsequent calls: `GET /proxy/network/api/s/{site}/stat/...`
  with session cookies. CSRF token required as header on POSTs.
- Sites are first-class: `/api/self/sites` lists them.
- JSON envelope: `{ "meta": { "rc": "ok" }, "data": [...] }`.

### Auth

Session-cookie. Same scheme handler as Synology, different endpoints
and cookie names. CSRF header required on writes (not on collect).

### Default object model

- **Site** — from `/api/self/sites`. Singleton-per-adapter-instance
  if monitoring one site; list if monitoring all sites on a controller.
- **Device** (access point, switch, gateway) — from
  `/api/s/{site}/stat/device`. Identifier: `mac` or `_id`.
- **Client** — from `/api/s/{site}/stat/sta`. Identifier: `mac`.
  Carries `uplink_device_id` referencing parent Device.
- **Network** (VLAN) — from `/api/s/{site}/rest/networkconf`.
- **WiFi Radio** (per AP) — from device's `radio_table` field.
- **Port** (per switch port) — from device's `port_table` field.

### Real ambiguities

- **Single-site vs multi-site monitoring.** Most users want
  single-site; ask only if controller has many sites.
- **Client-level granularity.** Tracking every Client object can
  produce inventory bloat (thousands per site). Ask whether to
  collect Clients or aggregate to per-AP statistics.

### Known limitations

None specific to this API shape. UniFi's data model is naturally
relationship-friendly: Client responses include `uplink_device_id`
which matches Device's `_id` directly — MPB `field_match`
relationships work out of the box without any extraction tricks.

### Reference

- `references/jcox-au_vmware/unifi_MP_Builder_Design.json` —
  working MPB-authored design with 3 functional relationships.
  Canonical reference for `field_match` relationship authoring.

---

## Cloudflare API (CDN / DNS / analytics)

### Signature

- Base URL: `https://api.cloudflare.com/client/v4/`.
- Auth header: `Authorization: Bearer <api_token>` (preferred) or
  legacy `X-Auth-Email` + `X-Auth-Key`.
- All responses wrap in: `{ "success": bool, "result": <payload>,
  "errors": [], "messages": [] }`. The `success` field is the
  reliable health signal — `result` may still contain partial data
  on failure.
- Account- and Zone-scoped endpoints: `/accounts/{id}/...`,
  `/zones/{id}/...`.
- GraphQL analytics endpoint at `/graphs/...` for time-series data
  (separate from REST endpoints).

### Auth

Bearer token. Token scope is set when minted in the Cloudflare
dashboard — operator picks per-zone vs account-wide. The MP YAML
declares Bearer auth with the token as a sensitive credential.

### Default object model

- **Account** — singleton per adapter instance.
- **Zone** — from `/zones`. Identifier: `id`.
- **DNS Record** — from `/zones/{id}/dns_records`; parent: Zone.
- **Worker Script** — from `/accounts/{id}/workers/scripts`.
- **Tunnel** — from `/accounts/{id}/cfd_tunnel`.
- **R2 Bucket** — from `/accounts/{id}/r2/buckets`.

### Real ambiguities

- **Time-series scope for GraphQL analytics.** Cloudflare charges
  for some analytics queries — ask user what window and granularity
  they want.

### Known limitations

GraphQL filter syntax has been finicky in our experience —
date params and filter shapes vary across Cloudflare API versions.
See commit `e613b15` (Cloudflare API compat fixes from earlier
work).

### Reference

- `content/managementpacks/cloudflare.yaml` — current factory MP.

---

## vSphere REST (vCenter Server)

### Signature

- Login: `POST /api/session` with HTTP Basic → returns session ID as
  the response body (string).
- Subsequent requests: `GET /api/vcenter/...` with header
  `vmware-api-session-id: <session_id>`.
- Modern endpoints under `/api/`, legacy under `/rest/`.
- Response shape varies — some endpoints return raw objects, others
  wrap in `{ "value": ... }` (the older convention).

### Auth

Acquire session via Basic, then use the session ID as a custom header.
The factory's session-token auth flow handles this.

### Default object model

**Use ARIA_OPS stitching, not new object kinds.** VCF Operations
already has a vSphere adapter that produces canonical
`HostSystem`, `VirtualMachine`, `Datastore`, `ClusterComputeResource`,
`ResourcePool` objects. A new MP should augment those with additional
metrics/properties via `type: ARIA_OPS`, matching on:
- HostSystem: `Summary|Hardware|BIOS UUID` (`uuid` field on vSphere REST side)
- VirtualMachine: `Summary|Instance UUID` (`instance_uuid`)
- Datastore: `Summary|Datastore URL` or `Capacity|Capacity` (instance UUID where available)

### Real ambiguities

- **Which built-in kind to stitch onto.** Usually clear from the
  endpoint scope (`/api/vcenter/host/*` → HostSystem). If ambiguous,
  ask the user about the data's logical owner.

### Known limitations

None specific to the API shape. The ARIA_OPS path is well-validated
in the framework. Skip declaring new INTERNAL object kinds for
vSphere data — that creates inventory duplication and confuses
users who already have the canonical objects from the built-in
vSphere adapter.

### Reference

- `content/managementpacks/vsphere_storage_paths.yaml` — pure
  ARIA_OPS stitch example.
- `tmp/reference_paks/vSAN default storage policy.json` — vrealize.it
  reference for ARIA_OPS Datastore extension.

---

## Generic REST + OpenAPI (the fallback case)

### Signature

The user hands you an OpenAPI / Swagger specification and there's no
catalog entry above that matches. The framework has no special
knowledge of the API.

### Default behavior

Drop into wizard-style interview: ask the user about authentication,
identifiers, parent-child structure, and which endpoints feed which
object types. Use the OpenAPI spec to ground every endpoint and
field name — never invent.

After the MP ships and validates against a live source, add the
new pattern as a catalog entry. The catalog grows by experience.

---

## Adding a new pattern

When you finish authoring an MP for a new API surface:

1. Add a new top-level entry to this catalog with the same shape
   (Signature, Auth, Default object model, Real ambiguities, Known
   limitations, Reference).
2. The Signature must be specific enough that future api-cartographer
   reports can match against it without ambiguity.
3. The Reference list must point at a real factory artifact or
   external repo — no "Coming Soon" entries.
4. If you hit a framework gap during authoring, document it under
   Known Limitations even if it didn't block the immediate ship.
   The next contributor against the same API needs to know.
