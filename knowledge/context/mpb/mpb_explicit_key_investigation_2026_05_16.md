# MPB explicit metric key investigation — 2026-05-16

## TL;DR

**No knob.** The MPB API path (`POST /designs/import` → ... →
`POST /install`) **cannot** be told to honor an explicit metric
`key`. MPB stores no `key` on metric definitions at all — neither
on import nor in the live design read-back. The `key` is derived
**at pak build time** from the metric `label` and is observable
only inside the built pak's `template.json`. Any `key` field
attached to a metric in the import body or in a PUT to
`/designs/{id}/objects` is silently dropped server-side.

The factory's `key` field is therefore honored **only** on the
standalone-pak install path, where `vcfops_managementpacks`
controls `template.json` directly. On the MPB API path it is
informational only.

Two viable workarounds:

1. **Label engineering** — pick labels whose MPB-derived key
   equals the desired wire key. The derivation rule is
   deterministic (see "Derivation algorithm" below). This is
   ugly because the label is what users see in the UI, but it is
   the only way to get the same wire key from both install paths.
2. **Declare the pak path canonical**, drop the MPB API path for
   factory-managed MPs, document the divergence, and treat MPB
   API import as a one-way export-to-MPB-Designer convenience
   (not a deployment mechanism).

Recommendation: option 2. Option 1 forces YAML authors to know
MPB's slug rules and to write labels like
`"CPU Utilization Pct"` instead of `"CPU %"` to get
`cpu_utilization_pct` instead of `cpu_`. The factory's existing
pak builder already produces correct wire keys; the MPB API path
should be reserved for design-editor round-tripping, not
installation.

## Method

- Devel profile `vcf-lab-operations-devel.int.sentania.net`.
- Imported one EXPLORE- design (`6624dfc3-da1f-408a-b2ea-9047520bb6ca`),
  read back via `GET /designs/{id}/objects/{objId}`, attempted
  `PUT /designs/{id}/objects` with injected `key`, then deleted.
  No install executed (probe was INVALID).
- Reference paks: `tmp/VCFContentFactoryUniFiIntegration-1001.pak`
  and `tmp/VCFContentFactoryvSphereStoragePaths-1001.pak` —
  MPB-UI-built outputs of the same factory YAML. Compared
  `conf/export.json` (the import-format envelope) against
  `conf/template.json` (the runtime format with derived keys).
- Probed `/install` POST body for hypothetical knobs:
  `{preserveKey, useExplicitKey, keyDerivation}` and query-string
  `?preserveKey=true`. All silently ignored.

All test artifacts cleaned up. Verified `GET /designs` shows
only the two pre-existing factory designs.

## Endpoints surveyed

Relevant endpoints for the design/metric lifecycle (full catalog
in `context/mpb_api_surface.md`):

| Method | Path | Carries metric key? |
|---|---|---|
| `POST` | `/internal/mpbuilder/designs/import` | Body MAY contain `objects[].object.metricSets[].metrics[].key`. **Silently dropped** by the importer. |
| `GET`  | `/internal/mpbuilder/designs/{id}` | Returns `DesignInfo` (name/version/status only). No metrics. |
| `GET`  | `/internal/mpbuilder/designs/{id}/objects` | Returns `objectSummaries` (id + label). No metrics. |
| `GET`  | `/internal/mpbuilder/designs/{id}/objects/{objId}` | Returns full `ObjectForm`. Metric records contain `id, label, dataType, expression, kpi, usage, unit, groups`. **No `key`, no `metricKey`, no `derivedKey`.** |
| `PUT`  | `/internal/mpbuilder/designs/{id}/objects` | Bulk update. Documented as broken per-object (returns 500 on `/{objId}` form). Tested with `key` injected on metric records — server returned 400 "ID must not be null" for the wrapped envelope shape; even when shape was valid, no `key` persisted on read-back. |
| `GET`  | `/internal/mpbuilder/designs/export?id={uuid}` | Round-trips the import envelope. Metrics carry no `key`. |
| `POST` | `/internal/mpbuilder/designs/{id}/install` | Triggers pak build + install. Body params silently ignored; query-string params silently ignored. No knob exposed. |
| `POST` | `/internal/mpbuilder/designs/{id}/jobs` (`COLLECTION_PREVIEW`) | Returns inferred attributes from a live source response. Not key-related. |

OpenAPI coverage check: `reference/docs/internal-api.json` and
`reference/docs/operations-api.json` contain **zero** matches for
`mpbuilder`. The `/internal/mpbuilder/*` namespace is undocumented
in shipped specs. No `preserveKey`, `useExplicitKey`,
`keyDerivation`, `metricKey`, `derivedKey`, or `deriveKey` strings
appear in either spec.

On-appliance dev spec
`/usr/lib/vmware-vcops/tomcat-enterprise/webapps/suite-api/docs/openapi/v3/dev-api.json`
is filesystem-only (403 over HTTP) and not cached in this repo —
the schema cited in `context/mpb_api_surface.md` was the
clean-room reference.

## What MPB stores post-import

**Nothing about keys.** Post-import metric record on
`GET /designs/{id}/objects/{objId}` (verbatim from the
EXPLORE- probe):

```json
{
  "id": "41aa1d7c-8a57-48e6-81c1-9c38e4c7aea9",
  "label": "Device ID",
  "dataType": "STRING",
  "expression": { "id": "...", "expressionText": "...",
                  "expressionParts": [ ... ] },
  "kpi": false,
  "usage": "PROPERTY",
  "unit": "",
  "groups": []
}
```

Fields present: `id, label, dataType, expression, kpi, usage,
unit, groups`. (Plus `example` and `regexOutput` on
expressionParts, which the factory strips on import per
`render_export.py`.)

Fields **absent**: `key`, `metricKey`, `derivedKey`.

Same shape on the pre-existing UniFi production design.
`jq 'paths(scalars) as $p | select($p[-1]=="key")'` finds `key`
**only** inside `requests[].chainingSettings.params[]` (HTTP
chaining param names) — not on metrics.

Conclusion: MPB does not store the metric key. It is computed
on demand from the label during the pak-build pipeline.

## When the derivation happens

The MPB-built pak (`VCFContentFactoryUniFiIntegration-1001.pak`)
contains two parallel JSON files in
`adapters/<adapter_kind>/conf/`:

| File | `key` field on metrics? |
|---|---|
| `export.json` (import-envelope format) | NO — pure label/expression |
| `template.json` (runtime format) | YES — 123 derived keys |

So MPB's build pipeline:

1. Takes the stored design (label-only).
2. Renders it to `template.json` while computing `key` per metric
   from `label`.
3. Renders it to `export.json` as-is (label-only).
4. Both files go into the pak; the runtime reads `template.json`
   for metric registration.

This is why two install paths land different keys:

- **Factory pak path**: factory's renderer writes both files
  itself, putting `cpu_pct` (from YAML) into `template.json`.
- **MPB API path**: factory POSTs an exchange-format payload that
  has no `key` (since MPB rejects it anyway), MPB ingests +
  stores label-only, then on `/install` MPB's own build pipeline
  computes `cpu_` from label `"CPU %"`. The factory's `key:`
  field never reaches the runtime.

## Derivation algorithm (reverse-engineered)

From the MPB-built pak's `template.json`, 40+ label→key pairs
across the UniFi MP. The rule:

1. Drop `.` (period) — no replacement character.
2. Drop `(` and `)` — no replacement character; content kept.
3. Lowercase.
4. Replace whitespace and `%` with `_`. (Other punctuation
   classes not exhaustively tested — see open questions.)
5. Collapse consecutive `_` to a single `_`.
6. Leave leading and trailing `_` intact (`"CPU %"` → `cpu_`,
   not `cpu`).

Worked examples:

| Label | Lowercased / period-stripped / parens-stripped | After whitespace+`%`→`_` | Collapsed | Final key |
|---|---|---|---|---|
| `Device ID` | `device id` | `device_id` | `device_id` | `device_id` |
| `MAC Address` | `mac address` | `mac_address` | `mac_address` | `mac_address` |
| `2.4 GHz Channel` | `24 ghz channel` | `24_ghz_channel` | `24_ghz_channel` | `24_ghz_channel` |
| `2.4 GHz Channel Width (MHz)` | `24 ghz channel width mhz` | `24_ghz_channel_width_mhz` | `24_ghz_channel_width_mhz` | `24_ghz_channel_width_mhz` |
| `CPU %` | `cpu %` | `cpu__` | `cpu_` | `cpu_` |
| `Memory %` | `memory %` | `memory__` | `memory_` | `memory_` |
| `Uptime (s)` | `uptime s` | `uptime_s` | `uptime_s` | `uptime_s` |
| `WAN Uplink TX (bps)` | `wan uplink tx bps` | `wan_uplink_tx_bps` | `wan_uplink_tx_bps` | `wan_uplink_tx_bps` |
| `Load Average (1m)` | `load average 1m` | `load_average_1m` | `load_average_1m` | `load_average_1m` |
| `5 GHz TX Retries %` | `5 ghz tx retries %` | `5_ghz_tx_retries__` | `5_ghz_tx_retries_` | `5_ghz_tx_retries_` |
| `Firmware Updatable` | `firmware updatable` | `firmware_updatable` | `firmware_updatable` | `firmware_updatable` |

The full 40-row mapping is in
`/tmp/mpb_unifi_inspect/adapters/mpb_vcf_content_factory_unifi_integration_adapter3/conf/template.json`
(extract via `jq -r '.source.resources[].requestedMetrics[].metrics[] | "\(.label) :: \(.key)"'`).

The trailing-`_` pattern from `%`-suffixed labels is the proximate
cause of the user's `cpu_` vs `cpu_pct` divergence. The label
the factory authored (`"CPU %"`) cannot derive to `cpu_pct`
under MPB's rule. To get `cpu_pct` from MPB's derivation, the
label would have to be `"CPU Pct"` or `"CPU Pct."` or
`"CPU Pct (%)"` — none of those match the YAML's current label.

## ARIA_OPS stitching is different

Storage Paths (ARIA_OPS-stitching mode) uses a separate code path.
In `template.json`, external metric records use the full
user-supplied string verbatim:

```json
{
  "id": "dc3372b9-...",
  "expression": "${@@@MPB_QUOTE_BODY datastore_name @@@MPB_QUOTE}",
  "key": "Datastore Name",         <-- verbatim, spaces and all
  "dataType": "STRING",
  ...
}
```

ARIA_OPS objects don't suffer the derivation issue because the
"label" IS the key (label is null in template.json for external
metrics). This investigation's recommendations therefore apply
to INTERNAL object types only. ARIA_OPS-stitching MPs are
key-stable across install paths.

## Knobs tried (all silently ignored)

- Import body: `objects[].object.metricSets[].metrics[].key` field.
  Server-side: dropped on import; absent from read-back.
- PUT objects: same field on bulk-replace body. Dropped.
- `/install` body params: `{"preserveKey": true, "useExplicitKey": true, "keyDerivation": "EXPLICIT"}`.
  Server returned the normal `IN_PROGRESS` envelope; design was
  already INVALID so no actual install ran; no hint that any
  flag was recognized.
- `/install` query string: `?preserveKey=true`. Same as above.

No endpoint encountered during this investigation accepts a flag
that would override the label-based derivation.

## Recommendations

### 1. Accept the limitation — pak path is canonical (preferred)

Document this clearly: the factory's pak path
(`vcfops_managementpacks build` → `POST /api/solutions/pakManagement/...`)
is the **only** install path that honors explicit `key:` fields in
YAML. The MPB API path
(`render-export` → `POST /designs/import` → `/install`) is for
round-tripping designs into the MPB UI editor, not for production
installation.

Tradeoff: loses the convenience of "edit factory YAML, push to
MPB Designer, install from there." Author/install workflow stays
factory → pak → API install.

Required follow-ups:

- Add a `factory install` mode warning if the user picks MPB API
  path while explicit keys are declared.
- Update `context/mpb_api_surface.md` and
  `ADMIN.md` to declare the canonical install path.
- Optionally remove `render-export` from the install pipeline
  entirely, leaving it only as a `factory export-design`
  command for MPB UI handoff.

### 2. Label engineering (only if option 1 is unacceptable)

Choose labels whose MPB-derived key equals the desired wire key.
This is mechanically possible:

- Want key `cpu_pct`? Use label `CPU Pct`.
- Want key `memory_pct`? Use label `Memory Pct`.
- Want key `uptime_seconds`? Use label `Uptime Seconds`.

Cost: labels are user-facing, so prose-style labels (`"CPU %"`,
`"Memory %"`, `"Uptime (s)"`) become impossible. Also asymmetric:
the factory's pak path still honors `key:` regardless, so the
YAML still has redundant `key:` declarations that are obeyed in
one install path and ignored in the other.

This is workable but ugly. Codify the rule in
`context/authoring/guide_content_authoring.md` if pursued.

### 3. Mutate the design via PUT before install (not viable)

Tested: PUT objects with `key` injected is silently no-op. The
server's schema doesn't accept it. No combination of body shape
made the field stick. Crossed off.

## Open questions for vendor engagement

These would benefit from VMware confirmation if a support case
opens:

1. **Is there an `internal/mpbuilder` endpoint or flag (perhaps
   behind a non-default feature toggle) that preserves explicit
   metric keys end-to-end?** Asking specifically because the
   exchange-format envelope clearly allowed `key` in some prior
   schema (factory's pre-strip version had it).
2. **Is the derivation algorithm above documented?** It's
   reverse-engineered from 40 samples; edge cases (Unicode,
   non-Latin scripts, leading digits, very long labels) untested.
3. **Will the algorithm change between VCF Ops releases?** If
   so, that's a stability risk for option 2 (label engineering).
4. **Why does the importer accept the `key` field but silently
   drop it?** A 400 with field-level diagnostics would be far
   easier to catch than the current "key just disappears."

## Correlation hooks for clean-room data

When clean-room research from the user arrives, the following
fields would help correlate against this investigation:

- **Source of the derivation rule** — is the user citing MPB
  source code, a VMware doc, or independent observation? If
  source code, the algorithm in this writeup can be tightened
  for edge cases.
- **VCF Ops version observed** — this investigation ran against
  9.0.x devel. If clean-room observed a different version with
  different behaviour, the recommendation set changes.
- **Any internal endpoint or `X-`-header that toggles
  derivation** — would invalidate the "no knob" verdict.
- **Whether `template.json`'s `key` field is read at adapter-kind
  registration or at first collection** — would tell us whether
  in-place runtime patching of an installed pak is even a
  theoretical option.

## Files referenced

- `/home/scott/projects/vcf-content-factory/tmp/unifi_api_lifecycle.json` —
  factory's POST body to `/designs/import` (label-only metrics).
- `/home/scott/projects/vcf-content-factory/tmp/VCFContentFactoryUniFiIntegration-1001.pak` —
  MPB-UI-built reference pak. Internal `conf/export.json` is
  label-only; internal `conf/template.json` carries derived keys.
- `/home/scott/projects/vcf-content-factory/tmp/VCFContentFactoryvSphereStoragePaths-1001.pak` —
  ARIA_OPS-stitching reference; key is verbatim user input.
- `/home/scott/projects/vcf-content-factory/content/managementpacks/unifi_network_integration.yaml` —
  declares `key: cpu_pct, label: CPU %`. Diverges at install.
- `/home/scott/projects/vcf-content-factory/context/mpb_api_surface.md` —
  full `/internal/mpbuilder/*` endpoint catalog.
- `/home/scott/projects/vcf-content-factory/vcfops_managementpacks/render_export.py` —
  factory's exchange-format renderer; intentionally strips `key`
  on metrics because the importer rejects unknown fields.

## Cleanup verification

- Probe design `6624dfc3-da1f-408a-b2ea-9047520bb6ca` deleted
  via `DELETE /designs?id=...`. Returned HTTP 200.
- `GET /designs` post-cleanup shows only the two pre-existing
  factory designs (UniFi `af3cf0d2-...` and Storage Paths
  `c8876ec1-...`). No EXPLORE- artifacts remain.
- No install was triggered; no adapter kind landed on devel.
