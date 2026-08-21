# How the factory uploads content to VCF Operations

A short methodology digest: which API path each content type takes and
the order of operations around it. The authoritative copies are the
`vcfops-api` skill (`.claude/skills/vcfops-api/SKILL.md` and its
`references/`) and the per-topic files in this directory; if this
digest ever disagrees with those, they win.

Written 2026-08-20 for Scott, on request.

## 1. Authenticate

```
POST /api/auth/token/acquire
  {"username": "...", "password": "...", "authSource": "Local"}
```

Returns a token used as `Authorization: OpsToken <token>` on every
subsequent Suite API call. Credentials come from env vars
(`VCFOPS_HOST/USER/PASSWORD`, profile form via `src/vcfops_common/_env.py`),
never from disk or argv. Internal (`/internal/*`) endpoints additionally
require the header `X-Ops-API-use-unsupported: true`.

## 2. Pick the transport: three upload paths, by content type

| Content type | Upload path | Why |
|---|---|---|
| Super metrics | content-zip import | The only path that preserves caller-supplied UUIDs (`POST /api/supermetrics` rejects them; UUID stability is the contract, RULE-007) |
| Views | content-zip import | No REST create/update exists at all |
| Dashboards | content-zip import | Same, no REST CRUD |
| Report definitions | content-zip import | REST surface is read-only |
| Symptoms | `POST/PUT /api/symptomdefinitions` | Full public CRUD; sync identity by name |
| Alerts | `POST/PUT /api/alertdefinitions` | Full public CRUD |
| Recommendations | `POST/PUT /api/recommendations` | Full public CRUD |
| Custom groups | `POST/PUT /api/resources/groups` | Groups do NOT ride the content-zip; server assigns the id, identity is `resourceKey.name` |
| Policies | `/api/policies/{import,export}` | Separate mechanism from content ops |
| Management packs (.pak) | `/ui/` SPA Struts layer | No Suite API pak install; see `pak_ui_upload_investigation.md` §Live-source findings |

## 3. The content-zip flow (SMs, views, dashboards, reports)

```
POST /api/content/operations/import
  Content-Type: multipart/form-data
  field name: contentFile        <- exactly this; "file" gets a 500
```

Returns 202 with an operation id. Poll
`GET /api/content/operations/import` until `state == FINISHED`, then
check `errorCode` / `errorMessages` AND `operationSummaries`.

Non-negotiables the factory bakes into every import:

1. **Marker file.** Every zip must contain the instance-specific
   `<19-digit>L.v1` marker (contents: the owner user UUID). The
   importer rejects anything else. The factory discovers it via a
   throwaway export against the target instance first.
2. **One import at a time.** A concurrent import returns 403
   "Task is already running": retry at 30s intervals, max 3.
3. **Imported-nothing check.** `imported=0, skipped>0` in the
   summaries means the import finished without changing anything on
   the instance: never report that as a successful install.
   For **SUPER_METRICS** specifically, this is the bisected ghost-state
   signature (content readable by id but invisible to list/assign) and
   the verified recovery is re-importing the same zip; the SM paths do
   that automatically. That cause and that remedy are **evidence only
   for SUPER_METRICS**, so do not assume they generalize. For dashboards
   and views the factory reports a loud warning, per content type, naming
   the affected content, and does not retry, because nothing has bisected what
   `imported=0/skipped>0` means there (issue #97). (Details:
   `vcfops-api` skill `references/wire-formats.md`.)

Exact zip layouts per type (`SUPER_METRICS`, `VIEW_DEFINITIONS`,
`DASHBOARDS`, `REPORT_DEFINITIONS`) are in that same wire-formats
reference.

## 4. Enable / assign (upload alone is not "working")

- **Super metric into the Default Policy:**
  `PUT /internal/supermetrics/assign/default` with body
  `{"superMetricId": "<uuid>", "resourceKindKeys": [{"adapterKind": "VMWARE", "resourceKind": "VirtualMachine"}]}`.
  Use the `/default` variant only; the `?policyIds=` variant can
  return 200 without actually enabling.
- **Alerts:** `PUT /api/alertdefinitions/{id}/enable` (public).
- **Symptom realtime toggle:** `/internal/symptomdefinitions/{id}/realtimemonitoring/{enable,disable}`.

## 5. Verify (done means seen working)

- `GET /api/supermetrics` / type-appropriate list call: the object is
  visible, not just 200-on-import.
- `GET /api/resources/{id}/stats/latest`: the metric is actually
  collecting on a real resource.
- For dashboards/views/reports: a browser pass over the rendered
  surface (qa-tester / content-installer Playwright step).

## 6. The factory's end-to-end order

validate (loaders, offline) -> render the wire format -> assemble the
zip with the target's marker -> import -> poll to FINISHED -> check
summaries for ghost state -> enable/assign where the type needs it ->
verify visible + collecting. All of this is what `content-installer`
runs via the per-type CLIs (`python3 -m vcfops_<type> sync|enable`);
pak install is `python3 -m vcfops_managementpacks install`.
