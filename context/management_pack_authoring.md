# Management Pack YAML — authoring reference

Authoritative field-by-field spec for `managementpacks/*.yaml`, the factory's
**source-of-truth grammar** for Management Pack Builder (MPB) designs. This
is what `mp-author` writes, what `vcfops_managementpacks` validates, and what
`render_export.py` compiles into an MPB-importable design JSON.

**Grammar level:** Option C / Tier 3.3 (2026-04-18). Older forms
(`requests:` under `object_type:`, `source: "request:..."`, loose
`identifiers:` shorthand, implicit request-is-metricSet) are rejected with
migration hints — do not use them.

**Companion docs.**
- [`mpb_relationships.md`](mpb_relationships.md) — when to express a
  parent/child edge as a chained metricSet vs an explicit relationship,
  dual-parent patterns, sidecar pattern.
- [`mpb_chaining_wire_format.md`](mpb_chaining_wire_format.md) — wire-level
  design-export format for chained requests.
- [`mpb_api_surface.md`](mpb_api_surface.md) — live MPB REST surface
  (`/suite-api/internal/mpbuilder/*`).
- `docs/reference-mpb-research.md` — MPB JSON schema reference.

**Ground truth for behavior.** When this doc and the loader disagree, the
loader wins — open a tooling ticket to reconcile. Loader source is
`vcfops_managementpacks/loader.py`; the module docstring has a working
example.

---

## File layout at a glance

```yaml
name: "<Human-Readable MP Name>"
version: "1.0.0"
build_number: 1
author: "<org>"
adapter_kind: "mpb_<slug>"      # optional; auto-derived from name
description: "<what this MP monitors>"

source:                          # connection + auth (optional block)
  port: <int>
  ssl: NO_VERIFY | VERIFY | NO_SSL
  base_path: "<url path, no leading />"
  timeout: 30
  max_retries: 2
  max_concurrent: 15
  auth: { ... }                 # see §"auth"
  test_request: { ... }         # health-check probe
  config_fields: [ ... ]        # UI-configurable knobs

requests:                        # MP-SCOPE (not per-object). See §"requests"
  - name: <identifier>
    method: GET | POST | ...
    path: "<path>"
    params: [ {key, value}, ... ]
    body: null | "<body>"
    response_path: "<dot.path>"

object_types:                    # see §"object_types"
  - name: "<Display Name>"
    key: <identifier>
    type: INTERNAL | ARIA_OPS
    icon: "<svg>.svg"
    is_world: true | false
    identifiers: [ ... ]
    identity: { tier, source }  # required iff is_world: true
    name_expression: { parts: [ ... ] }  # or shorthand
    metricSets: [ ... ]
    metrics: [ ... ]

relationships:                   # explicit parent/child edges
  - parent: <child_obj_key>
    child: <child_obj_key>
    scope: field_match | adapter_instance
    parent_expression: <metric_key>   # required for field_match
    child_expression: <metric_key>    # required for field_match

mpb_events:                      # optional, see §"mpb_events"
  - name: ...
    severity: INFO | WARNING | IMMEDIATE | CRITICAL | AUTOMATIC
    source_request: <request name>
    response_path: <dot.path>
    ...

content:                         # optional bundled content (dashboards/views)
  dashboards: []
  views: []
```

---

## Top-level fields

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Human-readable MP display name. No `[VCF Content Factory]` prefix — MPs extend VCF Ops; prefix is for content authored *inside* Ops. |
| `version` | yes | Semver string. Bumped by author for design changes. |
| `build_number` | no (default `1`) | Integer. MPB UI shows it next to version. |
| `author` | no | Free text. |
| `description` | no | Free text; appears in MPB UI and .pak manifest. |
| `adapter_kind` | no (derived) | Must match `^mpb_[a-z0-9_]+$`. If omitted, derived from `name` by lowercasing and replacing non-alphanum with `_`. Must be stable — it's the collection keyspace. |
| `source_path` | — | Populated by the loader to carry the YAML file path; not written by authors. |

---

## `source:` — connection + auth

Optional at the schema level but effectively required for any collecting MP.

```yaml
source:
  port: 443
  ssl: NO_VERIFY                # NO_VERIFY | VERIFY | NO_SSL (plaintext)
  base_path: "api"              # no leading slash
  timeout: 30                   # seconds
  max_retries: 2
  max_concurrent: 15
  auth: { ... }                 # see §"auth"
  test_request:                 # health-check probe fired at adapter startup
    method: GET
    path: "health"
    params: []
  config_fields:                # operator-facing config knobs in MPB UI
    - {key: site, label: "Site ID", type: STRING, default: "", description: "..."}
```

`config_fields[].type` — `STRING`, `NUMBER`, or `SINGLE_SELECTION`.

### `auth:` — flow-based grammar (Tier 3.2)

Every auth block declares a **preset**. The preset picks the MPB
`credentialType` and constrains which other auth blocks are allowed:

| Preset | Blocks allowed | Use for |
|---|---|---|
| `none` | (none — no creds, no login/logout/inject) | Fully open APIs |
| `basic_auth` | `credentials` (must be exactly `username` + `password`), `inject` | HTTP Basic |
| `bearer_token` | `credentials` (exactly one field — the token), `inject` | API keys / bearer tokens |
| `cookie_session` | `credentials`, `login`, `extract`, `inject`, `logout` (ALL required) | Session-cookie APIs (Synology, most vendors) |

```yaml
auth:
  preset: cookie_session

  credentials:
    - {key: username, label: username, sensitive: false}
    - {key: passwd,   label: passwd,   sensitive: true}

  login:                          # session-establishment request
    method: GET
    path: "auth.cgi"
    params:
      - {key: account, value: "${credentials.username}"}
      - {key: passwd,  value: "${credentials.passwd}"}

  extract:                        # where to find the session token
    location: HEADER              # HEADER or BODY
    name: "Set-Cookie"            # header name (HEADER) or JSON path (BODY)
    bind_to: session.set_cookie   # session variable; referenced as ${session.set_cookie}

  inject:                         # attach the token to every data request
    - type: header                # header or query_param
      name: "id"
      value: "${session.set_cookie}"

  logout:                         # session-teardown request
    method: DELETE
    path: "auth.cgi"
    params:
      - {key: method, value: "logout"}
```

**Substitution tokens.**
- `${credentials.<key>}` — field declared in `credentials[]`.
- `${session.<key>}` — session variable bound by `extract.bind_to`.
- `${configuration.<key>}` — operator-configured `config_fields[]` value.

The loader validates that every `${credentials.X}` / `${session.X}` token in
`login`, `logout`, and `inject[].value` resolves to a declared key.

---

## `requests:` — MP-scope (not per-object)

Every HTTP request this MP fires is declared here, once. Object types
reference them by name via `metricSets:`.

```yaml
requests:
  - name: get_volumes             # identifier; unique across MP
    method: GET                   # GET POST PUT DELETE PATCH
    path: "entry.cgi"             # relative to source.base_path
    params:                       # list of {key, value} pairs
      - {key: api,     value: "SYNO.Core.Storage.Volume"}
      - {key: method,  value: "list"}
    body: null                    # JSON body for POST/PUT; string
    response_path: "data"         # strips this prefix from all metric paths
```

**`response_path`** is a factory convention: if set, all metric `path:` values
on every metricSet backed by this request are resolved **relative to this
sub-path**. Setting `response_path: "data"` on every Synology request lets
metric paths say `space.volume.read_access` instead of
`data.space.volume.read_access`.

**`${chain.<name>}` tokens** in `path`, `params[].value`, or `body` make this
a chained-off-parent request — see §"Chained metricSets" below.

---

## `object_types:` — the collection schema

Every collected thing the MP produces is an object type. The factory enforces
**exactly one `is_world: true` object type** per MP (MPB requires a single
root/world/singleton anchor).

```yaml
object_types:
  - name: "Volume"                # display name
    key: "volume"                 # identifier; unique across MP
    type: INTERNAL                # INTERNAL | ARIA_OPS
    icon: "hard-drive-disks.svg"  # MPB renders from its icon library
    is_world: false               # true only for the adapter root
    identifiers: [ ... ]
    identity: { ... }             # required iff is_world: true
    name_expression: { parts: [...] }
    metricSets: [ ... ]
    metrics: [ ... ]
```

### `is_world`, singleton vs list

| Kind | `is_world` | `primary:` on metricSets |
|---|---|---|
| **World / singleton** | `true` | All metricSets MUST be non-primary. Singletons have no list iteration. |
| **List object** | `false` | Exactly ONE metricSet MUST have `primary: true`. |

A world object is not the adapter instance itself — MPB materializes the
adapter instance automatically. The world object is the root of the
collected hierarchy (e.g., "Synology Diskstation" represents the NAS as a
whole).

### `type: INTERNAL` vs `ARIA_OPS`

- `INTERNAL` — a new object type this MP owns.
- `ARIA_OPS` — a cross-adapter reference to an existing VCF Ops object type
  (advanced; rarely needed). Used to relate MP-created objects to existing
  vSphere/etc. objects.

### `identifiers:` — object-identity fields

Every object needs at least one stable identifier. Composite identifiers
(2+ keys) are supported; MPB treats them as a tuple.

Two accepted forms:

```yaml
# Shorthand (bare key names; source inferred from primary metricSet):
identifiers: [serial]

# Structured (explicit source, preferred when not using primary):
identifiers:
  - key: serial
    source: "metricset:system.serial"
  - key: pool_path
    source: "metricset:get_storage_pools.pool_path"
```

Reserved (rejects if set): `derive:` — computed/derived identifiers are not
yet implementable.

**Guidance.** Prefer `system_issued` hardware IDs (serials, UUIDs). Avoid
display names as identifiers — they can change. Array indices are never
stable.

### `identity:` — world-object identity tier (REQUIRED for `is_world: true`)

Non-world objects must NOT declare `identity:`. World objects MUST declare
it. The tier picks the preference category for VCF Ops identity resolution:

```yaml
identity:
  tier: system_issued | connection_address | display_name
  source: "metricset:<name>.<path>"
```

- `system_issued` — stable hardware/system UUID or serial. Preferred.
- `connection_address` — operator-entered hostname/URL. Use when no serial
  is exposed by the API.
- `display_name` — last resort; admin-entered name.

### `name_expression:` — how the object's display name is assembled

Two accepted forms:

```yaml
# Shorthand: bare metric key:
name_expression: hostname

# Structured (parts list):
name_expression:
  parts:
    - metric: model              # resolves to this object's "model" metric value
    - literal: " - "
    - metric: serial
```

Multi-part expressions are accepted by the grammar, but the renderer
currently emits a "not yet implemented" error — only single-part name
expressions are verified end-to-end. If you need composite naming, flag
a TOOLSET GAP.

### `metricSets:` — per-object data source bindings

`metricSets[]` explicitly binds a request's response to this object type.
Each entry consumes one request's response (or a sub-path within it) and
turns its fields into metrics on THIS object.

```yaml
metricSets:
  - from_request: get_volumes    # must name a top-level request
    primary: true                # exactly one per list object; absent on singletons
    list_path: "volumes"         # bare array name; do NOT add trailing .*
    as: volumes_main             # optional alias; defaults to from_request
    chained_from: null           # null = direct; sibling name = chained
    bind: []                     # ${chain.*} per-row substitutions on chained
```

**Field semantics.**

| Field | Purpose |
|---|---|
| `from_request` | Top-level request this metricSet consumes. |
| `primary` | Which metricSet defines list membership (list objects only). |
| `list_path` | Where in the response rows are found. `""` = whole response as scalar context (singletons and `is_world: true` objects — must be empty for world objects). Bare array name only — `"volumes"` iterates the `volumes` array. Do NOT use trailing `.*` (e.g. `"volumes.*"` is wrong — write `"volumes"`). The renderer normalizes legacy `.*` suffixes but emits a `DeprecationWarning`. |
| `as` | Local alias. Defaults to `from_request`. Only needed when the same request is consumed twice on the same object type (disambiguates). |
| `chained_from` | Names a sibling metricSet's `local_name` (its `as:` or `from_request`). Makes THIS metricSet fire once per row of the sibling, with `${chain.*}` substitutions. |
| `bind` | Per-row substitution bindings. Required when `chained_from` is set. Each entry: `{name: <chain_name>, from_attribute: <sibling row field>}`. |

**Primary rules.**
- List object (`is_world: false`): exactly one `primary: true` metricSet.
- World/singleton (`is_world: true`): zero `primary: true` metricSets.

### Chained metricSets — the per-row fan-out pattern

Use a chained metricSet when one object type needs enrichment from a request
that takes a per-item parameter (e.g., utilization per volume).

```yaml
# Parent request returns the list; lives at top-level requests:
- name: get_volumes
  path: "entry.cgi"
  params:
    - {key: api,    value: "SYNO.Core.Storage.Volume"}
    - {key: method, value: "list"}
  response_path: "data"

# Child request takes per-row parameter; MPB substitutes ${chain.volume_id}:
- name: volume_util
  path: "entry.cgi"
  params:
    - {key: api,      value: "SYNO.Core.System.Utilization"}
    - {key: location, value: "${chain.volume_id}"}
  response_path: "data"
```

```yaml
# Object type consumes both, wiring the chain:
- name: "Volume"
  metricSets:
    - from_request: get_volumes   # PRIMARY — defines list membership
      primary: true
      list_path: "volumes"        # bare array name; no trailing .*
    - from_request: volume_util   # CHAINED — fires once per primary row
      chained_from: get_volumes
      list_path: "space.volume"   # sub-path under volume_util's response_path
      bind:
        - name: volume_id         # ${chain.volume_id} in volume_util's params
          from_attribute: id      # volume row's "id" field supplies the value
```

The loader validates that every `${chain.<name>}` token in the request has a
matching `bind[]` entry, and that `chained_from` names a real sibling
metricSet. Cross-object-type chains are not supported in v1.

For the wire-level design-export format of chaining, see
[`mpb_chaining_wire_format.md`](mpb_chaining_wire_format.md).

### `metrics:` — individual metric/property definitions

Each entry is one metric or one property on this object type.

```yaml
metrics:
  - key: cpu_user_load             # unique within this object; factory-scoped
    label: "CPU User Load"         # display name
    usage: METRIC                  # METRIC or PROPERTY
    type: NUMBER                   # NUMBER or STRING
    unit: "%"                      # "" when n/a
    kpi: false                     # optional; marks key metrics
    source:
      metricset: utilization       # names a metricSet local_name on this object
      path: "cpu.user_load"        # dot-separated; relative to request.response_path + metricSet.list_path item
```

Shorthand `source: "metricset:utilization.cpu.user_load"` is accepted and
parses to the same structure.

**usage × type rules.**
- `METRIC` requires `type: NUMBER`.
- `PROPERTY` accepts either `STRING` or `NUMBER`. Prefer `STRING` for
  status enums, version strings, names. Use `NUMBER` for static numeric
  metadata (slot ID, cores, ram size).

**path resolution.** The full JSON path used at collection is:
`request.response_path` + `metricSet.list_path` (iterated) + `source.path`.
With `response_path: "data"` and `list_path: "volumes"`, `path: "name"`
resolves to the `name` field on each element of `data.volumes[]`.

**Reserved fields** on `source:` (reject if present): `aggregate`, `extract`,
`compose`. Future-use; fail-loud on set.

---

## Pagination

### Passing `offset` and `limit` as mandatory query params

Some REST APIs require `offset` and `limit` as mandatory query parameters —
the server rejects requests without them. In those cases, pass them in
`params:` as-is. Synology's convention is `offset=0, limit=-1` to mean
"return all rows in one response" — MPB passes them through to the server
unchanged.

**Ground truth.** `/tmp/mpb_chain_export/Synology DSM MP.json` (Scott's
hand-built, working MP exported from MPB) contains `Get Volumes` with
`params: [version=1, method=list, location=internal, offset=0, limit=-1,
api=SYNO.Core.Storage.Volume]` and **no `paging` key at all**. This request
imports cleanly, the Volume object opens in the MPB editor, and data collects.
`offset` + `limit` params without an explicit `paging:` block is the
known-working pattern for Synology's API. The `synology_dsm.yaml`
`docker_container_list` request also uses `limit=0, offset=0` with no
`paging:` block and works per Scott's usage history.

The loader does **not** reject requests that carry `offset`/`limit` params
without a `paging:` block. Pass them when the API requires them.

### Option (a): omit the params (when the API defaults to all rows)

```yaml
requests:
  - name: get_volumes
    method: GET
    path: "entry.cgi"
    params:
      - {key: api,    value: "SYNO.Core.Storage.Volume"}
      - {key: method, value: "list"}
    response_path: "data"
    # No offset/limit — the API defaults to all rows.
```

### Option (b): pass mandatory offset/limit params without a paging block

```yaml
requests:
  - name: get_volumes
    method: GET
    path: "entry.cgi"
    params:
      - {key: api,    value: "SYNO.Core.Storage.Volume"}
      - {key: method, value: "list"}
      - {key: offset, value: "0"}    # mandatory for this API
      - {key: limit,  value: "-1"}   # -1 means return all rows
    response_path: "data"
    # No paging: block — MPB passes params through as literal values.
```

### Option (c): explicit `paging:` block — RETIRED (2026-04-21)

> **Status: the `paging:` grammar is no longer wired to any renderer output.**
> As of 2026-04-21, `loader.py` parses the `paging:` block but
> `RequestDef.paging` is forced to `None` by the loader; the field is ignored
> at render time. The `paging` key in the MPB UI exchange-format is
> auto-populated from live API responses when MPB imports the design — it
> is not sourced from author-declared YAML. Do NOT declare a `paging:` block in
> new YAML. Existing YAMLs that carry the block silently ignore it.
>
> **Background:** Wire captures of working Synology requests show that paging
> sub-responses are populated with rich DML variant trees (e.g.,
> `data.volumes.*`, `data.volumes.*.*`) that MPB derives from actually
> polling the target API endpoint. There is no mechanism to reproduce these
> from static YAML. The `paging` key in the exchange format is therefore an
> MPB runtime artifact, not an author concern. Options (a) and (b) remain the
> correct patterns.
>
> The `paging:` YAML grammar (type/paging_param/limit_param/limit_value/
> list_path_id/start) is retained in the loader dataclass for backward
> compatibility but should be treated as dead weight — do not add
> documentation about it to new designs, and do not add new `paging:` blocks
> to author YAMLs.

---

## `relationships:` — explicit parent/child edges

Relationships are how you say "Pool contains Volume" or "VM runs on Host".

```yaml
relationships:
  - parent: storage_pool         # names an object_type KEY
    child: volume                # names an object_type KEY
    scope: field_match           # or adapter_instance
    parent_expression: id        # metric key on parent
    child_expression: pool_path  # metric key on child
```

Two scopes:

| `scope:` | Required expressions | Meaning |
|---|---|---|
| `field_match` | `parent_expression` + `child_expression` | Value-join predicate. The child's `child_expression` metric value must equal the parent's `parent_expression` metric value. |
| `adapter_instance` | neither (must be absent) | Trivial adapter-instance containment. Renderer synthesizes the wire-level predicate. |

Non-trivial relationships are almost always `field_match`. The loader errors
if you mix them (e.g., `field_match` scope with missing expressions, or
`adapter_instance` scope with expressions set).

**You cannot self-reference** — loader rejects `parent == child`.

**You cannot point at unknown object keys** — loader rejects parents/children
that aren't defined under `object_types:`.

For design-level guidance on when to use explicit relationships vs chained
metricSets, and how peer-vs-root dual-parent patterns behave, see
[`mpb_relationships.md`](mpb_relationships.md).

---

## `mpb_events:` — MP-native event conditions

Optional. Turn an API response into a VCF Ops event. Use sparingly —
factory symptoms + alerts (authored separately) are usually a better fit
because they compose with repo-wide alert logic.

```yaml
mpb_events:
  - name: "Volume Degraded"
    severity: CRITICAL               # INFO | WARNING | IMMEDIATE | CRITICAL | AUTOMATIC
    source_request: get_volumes      # must name a top-level request
    response_path: "volumes.*"       # JSON path to event/row list

    match_rules:
      - field: "status"              # response field
        operator: NOT_EQUALS         # see §"match operators"
        value: "normal"

    object_binding:                  # optional — pins event to object instance
      object_type: volume
      match_field: "id"              # response field that finds the target object
      match_normalizer: null         # optional lightweight transform

    collection_strategy:
      interval_seconds: 300
      dedup_strategy: TUPLE_HASH     # TUPLE_HASH | FIELD_ID | NONE
      dedup_fields: [id, status]     # required when dedup is TUPLE_HASH

    message_template: "Volume ${name} status is ${status}"
    description: "Fires when a volume reports non-normal status."
```

**Match operators:** `EQUALS`, `NOT_EQUALS`, `CONTAINS`, `NOT_CONTAINS`,
`MATCHES_REGEX`, `NOT_MATCHES_REGEX`, `STARTS_WITH`, `ENDS_WITH`, `EXISTS`,
`NOT_EXISTS`.

**`events:` (bare key) is rejected at parse time.** The old top-level
`events:` block was deprecated 2026-04; conditions previously authored as
events must now be re-authored as factory symptoms + alerts after the MP
installs. Use `mpb_events:` only for true event-log-style emissions from
the API.

---

## `content:` — bundled dashboards/views

Optional. Factory MPs can ship dashboards/views inside the .pak.

```yaml
content:
  dashboards: []
  views: []
```

Typical workflow: leave this empty and ship dashboards as factory content
bundles (subject to the `[VCF Content Factory]` prefix convention). MP-
bundled content is for MP-specific views that should travel with the MP
.pak even outside the factory content flow.

---

## Reserved / retired forms (rejected by the loader)

| Old form | Rejected | Migrate to |
|---|---|---|
| `requests:` under an `object_type:` | Option A grammar | Top-level `requests:` + explicit `metricSets:` on the object |
| `source: "request:<name>.<field>"` | Old source format | `source: "metricset:<local_name>.<path>"` — where `local_name` is the metricSet's `as:` alias or `from_request` |
| Top-level `events:` | v0 MP-native events key | `mpb_events:` block with new schema |
| `identifiers:` with `derive:` on any entry | Reserved | Use a real metric key reference |
| `source.aggregate` / `.extract` / `.compose` | Reserved | Not implementable yet; fail-loud |

Skip convention: files whose filename contains `.reference.` are ignored by
`load_dir()`. Use for keeping archival pre-migration YAML alongside current
files.

---

## Validation loop

```bash
python3 -m vcfops_managementpacks validate managementpacks/<file>.yaml
python3 -m vcfops_managementpacks validate            # whole dir
```

Validation is fast and read-only. Run it after every edit.

**Render/export** to produce the MPB-importable design JSON (what Scott
drops into the MPB UI):

```bash
python3 -m vcfops_managementpacks render-export managementpacks/<file>.yaml --out /tmp/design.json
```

**Extract** to reverse an MPB UI exchange-format JSON back to a factory YAML
(useful as a starting point after building a design in the MPB UI):

```bash
python3 -m vcfops_managementpacks extract \
    --from context/mpb_wire_reference/synology_nas_working_export.json \
    --out managementpacks/extracted.yaml
```

The extract command writes a header comment block listing fields that need
manual review (metric keys, list_path values, identity tier, relationships).
The resulting YAML passes `validate` and round-trips through `render-export`
to a semantically equivalent exchange JSON. Byte-for-byte match with the
source is not a goal — UUIDs differ (factory uses UUID5, MPB uses UUID4), and
MPB enriches `dataModelLists` from live API introspection at import time.

**About `dataModelLists` in the exchange format.**
The renderer emits a minimal `dataModelLists` set per request: one wildcard
DML per metricSet with a non-empty `list_path` (e.g. `data.volumes.*`) plus a
`base` DML guaranteed on every request. MPB enriches this set with additional
nested DML variants (`data.volumes.*.*`, deep sub-paths) when it polls the
live API at import time — those extra entries are a runtime artifact and
cannot be reproduced from author YAML. The minimal set is sufficient for
MPB to accept and import the design.

See `vcfops_managementpacks/README.md` for the full CLI surface. The authoring
loop stops at the YAML; rendering and install are not mp-author's job.

---

## Authoring checklist

Before returning an AUTHOR RESULT, confirm:

- [ ] File at `managementpacks/<slug>.yaml` with unique `name` and `adapter_kind`.
- [ ] Exactly one `is_world: true` object type, with an `identity:` block.
- [ ] Every non-world object has `is_world: false` and no `identity:`.
- [ ] Every list object has exactly one `primary: true` metricSet.
- [ ] Every world/singleton has zero `primary: true` metricSets.
- [ ] Every `source: "metricset:X.Y.Z"` references a real metricSet on the
      same object.
- [ ] All `list_path` values use bare array names (`"volumes"`, not `"volumes.*"`).
- [ ] World-object (`is_world: true`) metricSets have `list_path: ""` (or omit it).
- [ ] Every chained metricSet has `bind[]` entries covering all `${chain.*}`
      tokens in its request's params/path/body.
- [ ] Every relationship's `parent`/`child` names a real object key, and
      expressions are set iff `scope: field_match`.
- [ ] Every `${credentials.X}` / `${session.X}` token in auth blocks
      resolves to a declared key.
- [ ] `python3 -m vcfops_managementpacks validate` exits zero.
