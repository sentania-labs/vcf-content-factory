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

The canonical CSV has exactly these 12 columns, in this order. The
loader looks columns up by header name, so column order in the file
is informational — but normalizers produce them in this order for
reviewability.

| # | Column | Type | Description |
|---|---|---|---|
| 1 | `control_id` | string | Object-type-prefixed stable slug. Stable across framework versions. |
| 2 | `priority` | enum | `P0` / `P1` / `P2` |
| 3 | `resource_kind` | string | VCF Ops resource kind for stitching (e.g. `HostSystem`) |
| 4 | `adapter_kind` | string | VCF Ops adapter kind for stitching (e.g. `VMWARE`) |
| 5 | `parameter` | string | The thing being read (advanced setting key, vim property path, etc.) |
| 6 | `parameter_kind` | enum | How to read it. See enum below. |
| 7 | `value_type` | enum | `integer` / `string` / `boolean` |
| 8 | `expected_value` | string | Baseline value (always a string in the CSV; parsed per `value_type`) |
| 9 | `title` | string | Short human-readable |
| 10 | `description` | string | Long description for the control |
| 11 | `source_ref` | string | Traceability: `<source>:<original_id>` |
| 12 | `remediation_text` | string | PowerCLI/esxcli command to fix it; symptom-message-ready |

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
| `vim_property` | Vim object property (e.g. `config.dateTimeInfo.ntpServers`). Read via vSphere SOAP `PropertyCollector`. | yes (future) |
| `esxcli` | esxcli-only setting. Read via `Get-EsxCli` style commands. | no (today) — adapter cannot replicate without a PowerCLI runtime |
| `powercli_only` | Requires PowerCLI-specific cmdlet that has no direct vSphere SOAP equivalent. | no |
| `manual_audit` | Has no machine-readable assessment command. Human review only. | no |

The "evaluable" flag is *derived* from `parameter_kind`; there is no
separate column. The loader records all rows in the profile; the
evaluator skips rows whose `parameter_kind` is not in the evaluable
set. Today only `advanced_setting` is evaluated — the rest ship in
the profile for traceability and future expansion.

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
   columns is missing. The caller (`ComplianceAdapter`) wraps this
   into a `CollectionException` and the adapter goes Down with a
   descriptive message.
4. For each data row, builds a `BenchmarkProfile.Control` by header
   lookup. No positional indexing.

The cache key in `BenchmarkLoader.load` includes the resolved profile
name; when the configured profile changes, the cache is rebuilt.
