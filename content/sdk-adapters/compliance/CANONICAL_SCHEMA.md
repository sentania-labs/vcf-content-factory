# Canonical Benchmark CSV Schema

The compliance adapter consumes benchmarks in a single, header-aware
CSV format. Source benchmarks (VMware SCG 8.x, VMware SCG 9.x, CIS
vSphere) are normalized into this schema before being loaded by the
adapter. The adapter does not parse vendor-specific formats — it
parses only the canonical schema.

Why: the previous loader used positional indexing tuned for SCG 8.0
(`fields[6]`, `fields[9]`, `fields[11]`). SCG 9.0 reordered the
columns (added Secure Controls Framework / DISA STIG / PCI DSS
columns at positions 1–3, shifting everything else). The 9.0 CSV
parsed without error but every rule read garbage values, producing
zero matching controls per host and a sentinel score of 100. A
header-aware loader against a single canonical schema makes that
class of bug impossible.

## File layout

```
profiles/                                  # source CSVs (vendor formats)
  vmware_scg_8.0.csv
  vmware_scg_9.0.csv
  cis_vsphere_8.csv
profiles/canonical/                        # canonical CSVs (loaded by adapter)
  scg_8.0.csv
  scg_9.0.csv
  cis_vsphere_8.csv
```

Source CSVs stay in `profiles/` so future updates can be diffed and
re-normalized. The adapter loads only from `profiles/canonical/`.

## Columns

The canonical CSV has these 13 columns, in this order. Columns 1–12
are required; column 13 (`read_recipe`) is optional (see below). The
loader looks columns up by header name, so column order in the file
is informational — but normalizers produce them in this order for
reviewability.

| # | Column | Type | Description |
|---|---|---|---|
| 1 | `control_id` | string | Object-type-prefixed stable slug. Stable across framework versions. |
| 2 | `priority` | enum | `P0` / `P1` / `P2` |
| 3 | `resource_kind` | string | VCF Ops resource kind for stitching (e.g. `HostSystem`) |
| 4 | `adapter_kind` | string | VCF Ops adapter kind for stitching (e.g. `VMWARE`) |
| 5 | `parameter` | string | The thing being read (advanced setting key, vim property logical key, etc.). For `vim_property` this is the canonical logical key the evaluator looks up (e.g. `securityPolicy.forgedTransmits`); the vim25 path lives in `read_recipe`. |
| 6 | `parameter_kind` | enum | How to read it. See enum below. |
| 7 | `value_type` | enum | `integer` / `string` / `boolean` |
| 8 | `expected_value` | string | Baseline value (always a string in the CSV; parsed per `value_type`) |
| 9 | `title` | string | Short human-readable |
| 10 | `description` | string | Long description for the control |
| 11 | `source_ref` | string | Traceability: `<source>:<original_id>` |
| 12 | `remediation_text` | string | PowerCLI/esxcli command to fix it; symptom-message-ready |
| 13 | `read_recipe` | string | **Optional.** `<style>:<vim_path>` read spec for a `vim_property` or `esxcli` control. Empty for every other kind. See below. |

### `read_recipe` format (column 13)

Makes `vim_property` **and `esxcli`** controls **data-driven**: a new
control whose extraction *style* already exists is added by editing the
CSV and re-normalizing, with **no Java change**.

Grammar: `<style>:<vim_path>` (for `esxcli`, the style is `esxcli` and
the remainder is `<namespace.command>:<ResultField>` — see the table).

- `<vim_path>` — a vim25 property path resolvable from the control's
  resource MO. The adapter's generic reader (`VSphereClient.readByRecipe`)
  has PropertyCollector resolve the longest leading prefix it can, then
  walks the remaining segments with reflective zero-arg getters. Never
  casts to a concrete vim25 subclass.
- `<style>` — closed extraction-style set (adding a style is the only
  thing that ever needs Java):

  | style | meaning | example path |
  |---|---|---|
  | `scalar` | direct scalar / String / Number / Boolean at the path | `config.product.version` |
  | `bool` | boolean via `is<Field>()` / `get<Field>()` on the parent | `configurationEx.vsanConfigInfo.enabled` |
  | `bool_policy` | unwrap a `BoolPolicy` wrapper's `.value` | `config.defaultPortConfig.securityPolicy.forgedTransmits` |
  | `string_list_join` | join a `List<String>` on `,` | `config.dateTimeInfo.ntpConfig.server` |
  | `esxcli` | read a PascalCase result field from an esxcli `get` command over the **vCenter session** (no host creds); grammar is `esxcli:<namespace.command>:<ResultField>`. `EsxcliSoapClient` issues `RetrieveManagedMethodExecuter` + `ExecuteSoap` (`version=urn:vim25/5.0`). Returned `true`/`false` types as Boolean, else String. Build 36. | `esxcli:system.syslog.config.get:LocalLogOutputIsPersistent` |
  | `service_state` | filter the host service list (`config.service` → `HostServiceInfo.getService()` → `List<HostService>`) by service key and read one field. Grammar is `service_state:<service_key>:<field>`, `<field>` ∈ {`running`, `policy`}. `running` typed as Boolean (`HostService.isRunning()`/`getRunning()`), `policy` as String (`getPolicy()`: on/off/automatic). A **missing service entry** or an unreadable list folds to UNREADABLE (never a sentinel "stopped/compliant"). Build 38. | `service_state:TSM-SSH:running` |
  | `vm_hardware_device_absent` | walk to the device list, then return Boolean `true` iff **no** element's runtime class simple-name equals the named device type ("device absent" → compliant), `false` iff ≥1 matching device present. Grammar `vm_hardware_device_absent:<list_path>.<DeviceTypeSimpleName>` — the **final** segment names the vim25 device type, the preceding segments are the list path. Type match is by `getClass().getSimpleName()`, never `instanceof` a concrete subclass. **Cardinal-trap separation:** the list is read via `readListConfirmed`, which folds a **failed fetch** (container node null, or accessor not a `List`) to UNREADABLE; an **empty but confirmed** list is the compliant "absent" reading. Build 40. | `vm_hardware_device_absent:config.hardware.device.VirtualPCIPassthrough` |
  | `list_empty` | walk to the list and return Boolean `true` iff the list was read AND has **zero** elements, `false` iff ≥1 element. Grammar `list_empty:<list_path>`. **Cardinal-trap separation:** same `readListConfirmed` helper — a **failed fetch** of the list folds to UNREADABLE (never "empty → compliant"); only a **confirmed** (read off a non-null container) empty list scores compliant. Build 40. | `list_empty:config.vspanSession` |
  | `vlan_id_not` | type-aware VGT (Virtual Guest Tagging) detection on a VLAN spec node — VGT is **non-compliant**. Returns Boolean `true` (compliant) iff the spec is a plain id spec (`...VlanIdSpec`, recognized by `"VlanId"` in the runtime type name) AND `vlanId != 4095`; `false` iff the spec is a trunk spec (`...TrunkVlanSpec`, recognized by `"Trunk"`) OR a plain id spec with `vlanId == 4095`. Grammar `vlan_id_not:<vlan_spec_path>`. An **unreadable** spec node, OR a runtime type that is neither a recognized id spec nor trunk spec, folds to UNREADABLE — never a guess-pass. Type discrimination is by `getClass().getSimpleName()` substring, never `instanceof`. Build 40. | `vlan_id_not:config.defaultPortConfig.vlan` |
  | `vami` | read a JSON field from a vCenter Appliance Management (VAMI) REST endpoint. **A different transport from vim25 SOAP** — `VCenterAdapterInstance`-only, `parameter_kind=vami_api`. Grammar `vami:<appliance-path>:<json-field>` where `<appliance-path>` is everything after `/api/appliance/` (the path may contain `/` and is parsed as everything up to the **last** `:`), and `<json-field>` is the response field (dotted for nesting; the literal `(list)` token means "the response body itself is the list"). `VamiApiClient` opens its OWN REST session (`POST /api/session`, HTTP Basic with the raw username/password, token passed as `vmware-api-session-id`) — NOT the SOAP cookie. A JSON boolean is returned as Boolean (so `expected_value` `true`/`false` compares correctly), a JSON list as the comma-joined element string (pair with `(non-empty)`), a scalar as its String form. **Cardinal trap:** any auth failure, non-200, 404, timeout, parse error, **absent field**, or **empty list** folds to UNREADABLE — only a successful 200 with the field present yields a value; a failed GET of a "should be disabled" endpoint NEVER becomes "disabled → compliant". Failed session + per-endpoint results cached per cycle. **BLIND build (build 41): JSON field names are documentation-derived, not wire-captured — coverage is claimed, not proven, until a live run.** | `vami:access/ssh:enabled` |

Rules:

- `service_state` and `esxcli` use a **three-part** grammar (the `<path>`
  after the style itself carries a `:`); both are dispatched in
  `readByRecipe` **before** the generic dotted-path split.

- `vm_hardware_device_absent`, `list_empty`, and `vlan_id_not` use the
  generic two-part `<style>:<dotted-path>` grammar. For
  `vm_hardware_device_absent` the **final** dotted segment is overloaded
  as the device type filter (not a property accessor) — the reader splits
  it off before walking the list path.

- `vami` is a **three-part** grammar (`vami:<appliance-path>:<json-field>`)
  and is **NOT** dispatched in `VSphereClient.readByRecipe` (that reader is
  vim25-SOAP-only and resolves a `ManagedObjectReference`). VAMI controls
  target the `VCenterAdapterInstance`, which has no MoRef; they are read by
  a separate transport (`VamiApiClient`) wired into
  `ComplianceAdapter.collectVCenter` via `evaluateVamiForVCenter`, and
  scored by the same `ControlEvaluator.evaluateVimProperties` dispatcher
  (which now also accepts `vami_api`). The appliance-path is parsed as
  everything up to the **last** colon so the path may itself contain
  segments; the field is the remainder.

- **Cardinal rule for the "empty == compliant" styles
  (`vm_hardware_device_absent`, `list_empty`).** A read that fails to
  obtain the collection is **UNREADABLE**, NOT an empty list. The
  `readListConfirmed` helper makes the distinction positive: it walks to
  the list's **container node** and confirms it is non-null (proof the
  read reached the owning object) before reading the list off it. Only a
  `List` obtained off a non-null container counts as a confirmed read
  (empty or not); a null container, an absent accessor, or a non-`List`
  return folds to UNREADABLE. This is the exact `garbage in → score 100`
  failure the canonical schema redesign exists to prevent — a failed
  fetch can never be scored as "list empty → compliant".

- `read_recipe` is **optional** and kept OUT of the loader's required-
  column set, so older bundled or custom CSVs still load.
- A `vim_property` or `esxcli` control with an **empty** `read_recipe`
  is **non-evaluable** (informational only): it loads and appears for
  traceability, and the evaluator skips it — it is *not* counted as
  unreadable (we never declared we could read it).
- An **unknown** `<style>`, a malformed recipe, or a read that resolves
  to null makes the control **unreadable** (see "Unreadable outcome"
  below) — never a silent skip and never a guess.

The bundled normalizers own the vim-path knowledge for the shipped
profiles via the `_READ_RECIPE_BY_PARAMETER` map in
`scripts/_compliance_normalize.py`. Custom-profile authors supply
`read_recipe` directly in their CSV.

### Unreadable outcome

`vim_property` controls have three outcomes, not two:

- **pass** / **fail** — value read and compared (as today).
- **unreadable** — `read_recipe` present and evaluable, but the read
  resolved to null / the style couldn't extract / the style is unknown.

Unreadable controls are **excluded from pass, fail, and the score
denominator** — they are not failures (we don't know), and per the
cardinal rule they are **never compliant / never a sentinel pass**. A
per-resource `VCF-CF Compliance|unreadable_count` stat and a world
`Summary|total_unreadable_controls` aggregate surface them as a
*profile/coverage* signal, distinct from non-compliance. The
zero-divisor contract is unchanged: no evaluable controls →
score=100.0 with `total_count=0`, and callers refuse to fold a
`total_count==0` result into rollups.

### `control_id` format

`<object_type>.<slug>` — for example `esx.account-auto-unlock-time`.

The object-type prefix is redundant with the `resource_kind` column,
but it keeps the ID self-describing in log lines, symptom messages,
and dashboards. Strip framework version from the slug so the ID is
stable across versions; the `profile_name` property on the host tells
operators which version is loaded.

Object-type prefix map (use these exact tokens; propose new ones,
don't invent silently):

| `resource_kind` | prefix |
|---|---|
| `HostSystem` | `esx` |
| `VCenterAdapterInstance` | `vc` |
| `DistributedVirtualSwitch` | `vds` |
| `DistributedVirtualPortgroup` | `dvpg` |
| `Datastore` | `datastore` |
| `VirtualMachine` | `vm` |
| `ClusterComputeResource` | `cluster` |

Source-product sub-prefixes (added during the SCG 9.0 import for
controls that ship inside the VMware Cloud Foundation umbrella but
target a sub-product the compliance adapter does not stitch to today;
all currently come in as `manual_audit` / `powercli_only`):

| Prefix | Source-ID family | Notes |
|---|---|---|
| `nsx` | `nsx-9.*` | NSX-T security controls |
| `vcf` | `vcf-9.*` | VCF lifecycle/install controls |
| `sddc` | `sddc-9.*` | SDDC Manager |
| `installer` | `installer-9.*` | VCF installer |
| `ops` | `operations-9.*` | VCF Operations |
| `fleet` | `fleet-9.*` | Operations Fleet Management |
| `logs` | `logs-9.*` | Operations for Logs |
| `networks` | `networks-9.*` | Operations for Networks |

These rows exist in the profile for traceability; they don't push
data because the adapter cannot reach those sub-products today.

Slug rules: lowercase, hyphen-separated, ASCII only. When the source
ID already encodes the version (`esxi-8.account-auto-unlock-time`,
`esx-9.account-lockout-duration`), normalizers strip the leading
`<prefix>-<version>.` segment and re-prepend the canonical prefix.

### `parameter_kind` enum

How the adapter should read this control's actual value at collection
time. Determines whether the control is *evaluable* in-adapter or
informational-only.

| Value | Meaning | Evaluable in adapter? |
|---|---|---|
| `advanced_setting` | ESXi Advanced System Setting (e.g. `Security.AccountUnlockTime`). Read via vSphere SOAP `OptionManager.QueryOptions`. | yes |
| `vim_property` | Vim object property (e.g. `config.defaultPortConfig.securityPolicy.forgedTransmits`). Read data-driven via the `read_recipe` column (vSphere SOAP `PropertyCollector` + reflective getter walk). | yes, **iff** `read_recipe` is non-empty (else informational) |
| `esxcli` | esxcli command result field (e.g. `system syslog config get` -> `LocalLogOutputIsPersistent`). Read data-driven via the `read_recipe` column with the `esxcli:<namespace.command>:<ResultField>` style — `EsxcliSoapClient` issues `RetrieveManagedMethodExecuter` + `ExecuteSoap` over the **existing vCenter session** (no host credentials, no per-host fan-out; build 36). | yes, **iff** `read_recipe` is non-empty (else informational) — was "no" before build 36 |
| `vami_api` | vCenter Appliance Management (VAMI) REST field (e.g. `/api/appliance/access/ssh` -> `enabled`). `VCenterAdapterInstance`-only. Read data-driven via the `read_recipe` column with the `vami:<appliance-path>:<json-field>` style — `VamiApiClient` opens its OWN REST session (`POST /api/session`, HTTP Basic auth, `vmware-api-session-id` header) distinct from the vim25 SOAP cookie (build 41). | yes, **iff** `read_recipe` is non-empty (else informational) |
| `powercli_only` | Requires PowerCLI-specific cmdlet that has no direct vSphere SOAP equivalent. | no |
| `manual_audit` | Has no machine-readable assessment command. Human review only. | no |

The "evaluable" flag is *derived*; there is no separate column.
`advanced_setting` is always evaluable; `vim_property`, `esxcli`, and
`vami_api` are evaluable only when `read_recipe` is non-empty (the recipe
IS the read path).
The loader records all rows in the profile; the evaluator skips rows
that are not evaluable. The remaining kinds (`esxcli`, `powercli_only`,
`manual_audit`) ship in the profile for traceability and future
expansion.

### `value_type` enum

| Value | Match rule |
|---|---|
| `integer` | Numeric comparison (parsed as double; tolerance 0.001). |
| `boolean` | Case-insensitive match against `true`/`false`/`1`/`0`/`yes`/`no`. |
| `string` | Case-insensitive string equality after stripping surrounding quotes. |

Normalizers infer `value_type` from `expected_value`:
- Parses cleanly as integer or float → `integer`
- Lowercases to `true`/`false` → `boolean`
- Anything else → `string`

If `expected_value` is empty, `value_type` defaults to `string` and
the row will not match anything at evaluation time — it's effectively
informational.

### `expected_value` comparison modes (build 39)

By default `expected_value` selects **case-insensitive equality** (with a
numeric tolerance path per `value_type`). Two **sentinel tokens** in the
`expected_value` column select an alternative comparison semantic. They
work for both the `advanced_setting` path and the recipe-driven
`vim_property` / `esxcli` path (the same tokens are honored by both
evaluator entry points).

| `expected_value` | Mode | Compliant iff |
|---|---|---|
| `(non-empty)` | **presence / non-empty** | the read value is **present** (non-null, and — for a stringified list — non-empty). |
| `not:<value>` | **not-equal** | the read value is **present** AND is **not** case-insensitively equal to `<value>`. |

**When to use `(non-empty)`.** Where the SCG baseline column is a
site-specific sentinel that no real read value can string-equal — e.g.
the NTP server list, whose SCG baseline is literally `Site-Specific`.
Plain equality against that sentinel would manufacture a permanent false
**fail** on every correctly-configured host. `(non-empty)` instead passes
the control as soon as ≥1 value is configured. Example row:
`esx.timekeeping-sources` →
`read_recipe=string_list_join:config.dateTimeInfo.ntpConfig.server`,
`expected_value=(non-empty)`.

**Operator/auditor semantic (read this).** For the NTP-server and
syslog-forwarding `(non-empty)` controls — `esx.timekeeping-sources`,
`vc.vami-time`, `vc.time` (NTP) and `vc.vami-syslog`, `vc.log-forwarding`
(syslog forwarding) — **"compliant" means a remote target is
configured, not that the *correct* target is configured.** These controls
verify presence (≥1 NTP source / a remote log destination is set); they do
not validate the address against an organizational allowlist. (An empty or
failed read still folds to UNREADABLE upstream and is never a false pass.)

**When to use `not:<value>`.** Where the SCG test is "the value must NOT
be the known-bad sentinel" rather than "must equal a specific good
value" — e.g. `ScratchConfig.CurrentScratchLocation` must **not** equal
`/tmp/scratch` (the non-persistent ramdisk location). Example row:
`esx.logs-audit-persistent` / `esx.log-audit-persistent` (an
`advanced_setting`) → `expected_value=not:/tmp/scratch`.

**Cardinal-rule invariant (both modes).** A missing / unreadable / empty
read is **never** folded into a pass:

- For `vim_property` / `esxcli`, an unreadable read is the UNREADABLE
  sentinel — excluded from pass/fail/total and counted in
  `unreadable_count` — and is short-circuited *before* the mode helpers
  run. (A `string_list_join` of an empty list already resolves to null →
  UNREADABLE upstream, so an empty NTP list is a coverage gap, never a
  `(non-empty)` pass.)
- For `advanced_setting`, an absent key is **skipped** (excluded from the
  score denominator) by the existing absent-key branch *before* the
  `not:` / `(non-empty)` comparison is consulted. In particular the
  not-equal mode **never** treats a missing value as "not equal to X,
  therefore compliant" — absence is an exclusion, not a pass.

These tokens are reserved values in the `expected_value` column. A
literal expected value of `(non-empty)` or one beginning `not:` is not
expressible as a plain equality target (use a custom recipe/style if a
profile genuinely needs that literal — no shipped SCG control does).

### `source_ref` format

`<source>:<original_id>` — e.g. `SCG-9.0:esx-9.account-lockout-duration`.

Sources currently in use:

| Source token | Description |
|---|---|
| `SCG-8.0` | VMware Security Configuration Guide v8.x |
| `SCG-9.0` | VMware Security Configuration Guide v9.x |
| `CIS-vSphere-8` | CIS Benchmark for vSphere 8 |

### `remediation_text` format

Single-line PowerCLI/esxcli command suitable for embedding in symptom
messages. Normalizers strip newlines, collapse whitespace, and CSV-escape
quotes and commas. Where the source has no remediation command, the
column is empty.

## Normalizers

Per-source Python scripts under `scripts/`:

- `scripts/normalize_scg_v8.py` — VMware SCG 8.x source format
- `scripts/normalize_scg_v9.py` — VMware SCG 9.x source format
  (different column order than 8.x)
- `scripts/normalize_cis_vsphere.py` — CIS vSphere benchmark source

Each script takes `<input.csv> <output.csv>` as positional args. They
log counts (in / out / skipped, by `parameter_kind`) to stderr and
exit non-zero on hard errors (missing required source columns,
unmapped Component values).

## Loader contract

`BenchmarkLoader.parseCanonical` reads the canonical CSV and:

1. Reads the first non-blank line as the header row.
2. Builds a `Map<String, Integer>` of column name → index.
3. Hard-fails (throws `RuntimeException`) if any of the 12 required
   columns (1–12) is missing. The caller (`ComplianceAdapter`) wraps
   this into a `CollectionException` and the adapter goes Down with a
   descriptive message. Column 13 (`read_recipe`) is **optional** — its
   absence does not fail the loader; every `vim_property` control then
   loads as non-evaluable / informational.
4. For each data row, builds a `BenchmarkProfile.Control` by header
   lookup. No positional indexing. The optional `read_recipe` column is
   read by name when present, defaulted to empty when absent.

The cache key in `BenchmarkLoader.load` includes the resolved profile
name; when the configured profile changes, the cache is rebuilt.
