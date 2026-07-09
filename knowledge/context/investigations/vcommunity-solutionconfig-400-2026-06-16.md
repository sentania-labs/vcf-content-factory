# vCommunity SolutionConfig HTTP 400 — root cause

**Date:** 2026-06-16
**Investigator:** api-explorer (read-only, devel + primary-lab GET probes)
**Question:** Why does `vcfcf_vcommunity` (build 2, devel) report
"fetch failed for all SolutionConfig XMLs (HTTP 400)", and what is the exact fix?

## Verdict

**INSTALL-GAP, with a packaging root cause (and one latent FETCH nit).**

- The port's **fetch request shape is correct** — proven by HTTP 200
  against the primary lab for the exact same URL/params/file-names.
- The six SolutionConfig XMLs are **absent from devel's central
  configuration-file store**. The store signals "no such file" with
  **HTTP 400 / apiErrorCode 1501**, not 404 — which is why the signal
  looked like a malformed request.
- Root cause of the absence: **the SDK pak builder never packages
  `content/files/solutionconfig/*.xml`**, so the build-2 pak installed
  on devel had nothing for SolutionManager to import into the store.
- The primary lab returns 200 only because the **original**
  `VCFOperationsvCommunity` Python MP (whose toolchain *does* pack
  `content/files/`) populated the store there previously.

There is **no fetch bug that causes the 400** — but see the "latent
fetch nit" below (`Accept` header) which should be corrected
opportunistically.

## Evidence

### 1. The exact request the port sends

`SolutionConfigStore.fetchList/fetchRawXml`
(`content/sdk-adapters/vcommunity/.../SolutionConfigStore.java:108,150`):

```
stitcher.get("/api/configurations/files?path=SolutionConfig/" + enc(fileName) + ".xml")
```

Resolved through `SuiteApiStitcher.get` →
`SuiteApiStitchClient.rawGet` (`adapter_framework/.../SuiteApiStitchClient.java:524`):

```
GET https://localhost/suite-api/api/configurations/files?path=SolutionConfig/<name>.xml
Accept: application/json
Authorization: OpsToken <token>
```

Default file names (`VCommunityConfig.java:84-95`), all
lowercase/underscore so `enc()` (URLEncoder) is a no-op:
`esxi_advanced_system_settings`, `esxi_packages`,
`vm_advanced_parameters`, `vm_options`, `windows_service_list`,
`windows_event_list`.

### 2. Spec confirms shape + the 400 idiom

`reference/docs/operations-api.json` → `GET /api/configurations/files`:
- `path` query param, **required**, format `{configFileType}/{fileName}`,
  allowed `configFileType` includes `SolutionConfig`. → port's shape is correct.
- `200` produces `*/*` (raw file body). `400` = "Request parameter is invalid".
- No POST/PUT/DELETE on this path in **either** spec — there is no
  documented write endpoint. Population is a pak-install side effect.

### 3. Live devel — reproduces 400/1501 for every name and every variant

All six default names → `HTTP 400`,
`{"message":"Value \"<name>.xml of type SOLUTION_CONFIG\" is invalid for request param.","apiErrorCode":1501}`.

Varying one dimension at a time made **no difference** (all still 400/1501):
`Accept: application/json` vs `*/*`; plain slash vs fully URL-encoded
`path`; with/without `.xml` suffix. Encoding is **not** the cause.
The message "<file> of type SOLUTION_CONFIG is invalid" means the server
parsed the path fine (type + filename) and the named file simply does
not exist in the store. `1501` is the store's "no such file" code; it
returns **400, not 404** — this is why the failure looked like a bad request.

### 4. Primary lab (prod/qa host) — same request returns 200

Via qa admin against `vcf-lab-operations.int.sentania.net`, where the
**original** community MP is installed:

| path=SolutionConfig/… | result |
|---|---|
| `esxi_advanced_system_settings.xml` | **200**, 49919 B `<advancedSettings>…` |
| `esxi_packages.xml` | **200**, 3202 B `<packages>…` |
| `vm_advanced_parameters.xml` | **200**, 2606 B `<vmAdvParameters>…` |
| `vm_options.xml` | **200**, 3345 B `<vmConfigs>…` |
| `windows_service_list.xml` | **200**, 637 B `<windowsServices>…` |
| `windows_event_list.xml` | **200**, 716 B `<Events>…` |
| CamelCase legacy names (`ESXiAdvancedSystemSettings.xml`, …) | 400/1501 |

This proves: (a) the request shape, endpoint, params and `Accept:
application/json` header are all correct (200 with XML body despite
JSON Accept); (b) the port picked the **right** lowercase file names
(CamelCase variants 400); (c) the files exist where the original MP was
installed and are simply **missing on devel**.

### 5. Why devel's store is empty — packaging root cause

- `GET /api/solutions` on devel lists `VCF Content Factory vCommunity`
  (the port) but **not** the original `VCFOperationsvCommunity`. Only the
  port has ever been installed on devel.
- The port pak is supposed to seed the store: design
  (`knowledge/designs/managementpacks/vcommunity-sdk.md:135,439-441`) says the six
  XMLs "ship in `content/files/solutionconfig/` → imported into the
  central store at pak install."
- **But the SDK builder never packs them.** In
  `vcfops_managementpacks/sdk_builder.py`, `content/files/` appears only
  as a string in the `_ALL_CONTENT_DIRS` reference list (line 1291); the
  emit logic in `_write_outer_pak` writes `content/`, `content/resources/`,
  `content/reports/` (views), `content/dashboards/` — and **nothing for
  `content/files/`**. There is no iteration over the project's
  `content/files/solutionconfig/` tree.
- Confirmed against the actual artifact: `dist/vcfcf_sdk_vcommunity.1.0.0.2.pak`
  (the build installed on devel) contains **zero** `content/`,
  `content/files`, or `solutionconfig` entries. The XMLs were never
  shipped, so SolutionManager imported nothing, so the store is empty,
  so every fetch is 400/1501.

The source XMLs do exist in-tree, unused by the build:
`content/sdk-adapters/vcommunity/content/files/solutionconfig/{6 files}.xml`
(byte-compatible with `reference/references/vmbro_vcf_operations_vcommunity/.../solutionconfig/`).

## The fix

### Primary fix — TOOLING (pak builder): pack `content/files/`

The durable fix is in the **build**, not the adapter. The `tooling`
agent should extend `_write_outer_pak` in
`vcfops_managementpacks/sdk_builder.py` to copy the project's
`content/files/**` tree into the pak verbatim (emit the
`content/files/` and `content/files/solutionconfig/` dir entries, then
`zf.write` each file at its relative path), mirroring the existing
`conf/profiles/` recursive-copy pattern (lines 915-929) and the
"only emit populated subdirs" discipline (line 1379). After the tooling
change, rebuild the pak (build 3) and reinstall on devel; SolutionManager
will import the six XMLs into the store and the fetch returns 200.

Acceptance check: `unzip -l` the new pak shows
`content/files/solutionconfig/esxi_advanced_system_settings.xml` (×6),
and post-install `GET /api/configurations/files?path=SolutionConfig/esxi_advanced_system_settings.xml`
returns 200 on devel.

### Immediate unblock — manual store population on devel (optional, no rebuild)

The API exposes no write endpoint, but the VCF Ops UI does:
**Administration → Configuration Files → Solution Configuration**,
upload the six in-tree XMLs from
`content/sdk-adapters/vcommunity/content/files/solutionconfig/`. The
port's next collection cycle then fetches 200 and lights up the ~54
gated parity keys — useful to validate the rest of the collector before
build 3 lands. (This is a lab convenience, not the shippable fix.)

### Latent fetch nit — `Accept` header (correct opportunistically, NOT the 400 cause)

`rawGet` sends `Accept: application/json` but the endpoint produces
`*/*` (raw XML). The primary lab returns 200 anyway, so this does **not**
cause the 400 and is **not** required for the fix. But it is a wire-format
mismatch worth correcting when `sdk-adapter-author` next touches the
framework: a dedicated raw-body GET (or `Accept: */*`) for config-file
fetches is more honest. Low priority; does not gate the parity keys.

## Implications for code

- **Build 3 must come from a fixed `sdk_builder.py`.** Any SDK adapter
  that ships `content/files/**` (config files, custom XML) is silently
  dropped by the current builder — this is a general SDK-pak gap, not
  vCommunity-specific. Worth a lesson.
- **Prod migration is safe:** the port's fetch is correct, so on a host
  where the original MP already seeded the store (e.g. the primary lab),
  the port reads the existing XMLs with no change. The gap is purely
  fresh-install store population.
- `content_file_status` world-anchor diagnostic is working as designed —
  it correctly surfaced the empty store rather than silently collecting
  empty check-lists.

## Cleanup

Read-only investigation. No objects created on any instance; tokens
acquired were released by `urlopen` close. Nothing to delete.
