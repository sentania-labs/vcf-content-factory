# Synology DSM "Legacy" Reference Pak — Ingest Catalog

## Ingest metadata

- **Extraction timestamp:** 2026-04-20
- **Source instance:** devel VCF Ops 9.0.2.0 build 25137838
  (`vcf-lab-operations-devel.int.sentania.net`)
- **Pak file:** `SynologyDSM-1001.pak`
- **Size:** 22,170,283 bytes
- **Sha256:** `813045863545d6b93f9195c31d9bdb1579a33c9f4ad0f2d46e0f2ac5af6fab5f`
- **Factory repo commit at ingest:** `4dcd29442563495cb3218a2285a90ab9a5cb6b5b`
  (branch `docs/2026-04-19-freshness-pass`)

This pak was retrieved from devel's pak cache during Phase A
(Navani / sentania-lab-toolkit). Scott has labelled it the
"legacy" reference artifact for roundtrip validation. The
naming ambiguity is documented below — neither the cached pak
nor the currently-registered devel MP is a strict pre-factory
hand-MPB build.

## Manifest metadata

Extracted from `manifest.txt`:

| Field | Value |
|---|---|
| `display_name` | `Synology DSM` |
| `name` | `Synology DSM` |
| `version` | `1.0.0.1` |
| `vendor` | `VCF Content Factory` |
| `adapter_kinds` | `["mpb_synology_dsm"]` |
| `license_type` | `adapter:mpb_synology_dsm` |
| `vcops_minimum_version` | `7.5.0` |
| `disk_space_required` | `500` |
| `platform` | `Windows`, `Linux Non-VA`, `Linux VA` |
| `eula_file` | `eula.txt` |
| `pak_icon` | `default.png` |
| `run_scripts_on_all_nodes` | `true` |

**Description:** "Monitors Synology DiskStation Manager (DSM)
NAS devices. Covers storage health (pools, volumes, disks),
iSCSI LUN performance, Docker container resource usage, and
UPS status. Designed for VMware/VCF environments where the NAS
provides iSCSI datastores to ESXi hosts."

**Scripts declared:**

- `pak_validation_script` → `python validate.py`
- `adapter_pre_script` → `python preAdapters.py`
- `adapter_post_script` → `python post-install.py`

## Top-level pak inventory

16 entries total. Listed largest first (bytes uncompressed):

| Bytes | Name |
|---|---|
| 22,173,941 | `adapters.zip` |
| 33,177 | `eula.txt` |
| 19,377 | `default.png` |
| 6,723 | `post-install.py` |
| 1,063 | `manifest.txt` |
| 618 | `validate.py` |
| 490 | `resources/resources.properties` |
| 170 | `postAdapters.py` |
| 167 | `preAdapters.py` |
| 127 | `post-install-fast.sh` |
| 19 | `post-install.sh` |
| 2 | `content/supermetrics/customSuperMetrics.json` |
| 0 | `content/dashboards/` (directory marker) |
| 0 | `content/views/` (directory marker) |
| 0 | `content/reports/` (directory marker) |
| 0 | `content/files/reskndmetric/` (directory marker) |

`unzip -l` produced no warnings — the pak is a standard zip.

Note that `content/supermetrics/customSuperMetrics.json` is 2
bytes (an empty `{}` or `[]`) and the `content/dashboards/`,
`content/views/`, `content/reports/` trees are empty directory
markers. This pak ships **no factory-side content** — it is
adapter-only.

## adapters.zip internal structure

`adapters.zip` expands to 90 entries (~25.1 MB uncompressed).
The adapter directory is named **`mpb_synology_dsm_adapter3`**
(note the `_adapter3` suffix, consistent with MPB-builder
output conventions).

### Adapter directory layout

```
/                                            (root marker)
mpb_synology_dsm_adapter3/
    doc/                                     (empty)
    lib/                                     (60 JAR files)
    work/                                    (empty)
    conf/
        supermetrics/customSuperMetrics.json (2 bytes — empty)
        dashboards/                          (empty)
        reports/                             (empty)
        views/                               (empty)
        resources/resources.properties       (2,449 bytes)
        images/
            AdapterKind/mpb_synology_dsm.png (19,377)
            ResourceKind/mpb_synology_dsm.png (19,377)
            TraversalSpec/default.png         (19,377)
        design.json                          (276,334 bytes)
        export.json                          (231,211 bytes)
        describe.xml                          (42,675 bytes)
        mpb_synology_dsm.properties             (175 bytes)
        version.txt                             (145 bytes)
resources/resources.properties                  (490 bytes)
manifest.txt                                  (1,063 bytes)
eula.txt                                     (33,177 bytes)
default.png                                  (19,377 bytes)
mpb_synology_dsm_adapter3.jar               (234,794 bytes)
```

### Key adapter artifacts (the interesting files)

| Path inside adapters.zip | Bytes | What it is |
|---|---|---|
| `mpb_synology_dsm_adapter3/conf/design.json` | 276,334 | MPB design document (authoring source of truth) |
| `mpb_synology_dsm_adapter3/conf/export.json` | 231,211 | MPB export/runtime snapshot |
| `mpb_synology_dsm_adapter3/conf/describe.xml` | 42,675 | Adapter-kind describe (metric/property/resource-kind schema) |
| `mpb_synology_dsm_adapter3/conf/version.txt` | 145 | Adapter version marker |
| `mpb_synology_dsm_adapter3/conf/mpb_synology_dsm.properties` | 175 | Adapter properties |
| `mpb_synology_dsm_adapter3.jar` | 234,794 | Adapter entrypoint JAR (not copied out) |
| `mpb_synology_dsm_adapter3/lib/*.jar` | ~24 MB total | 60 runtime JARs (not copied out — Kotlin stdlib, ktor client, jackson, guava, aria-ops-core, mpb_common, mpb_clients, hibernate-validator, log4j, etc.) |

JARs and PNGs are catalogued by name/size only. Binaries are
not copied into the repo; the pak itself at
`SynologyDSM-1001.pak` is the canonical bytes.

## Naming ambiguity (important for bisect scoping)

Three Synology-DSM MPB artifacts exist in this ecosystem and
they do NOT line up one-to-one:

1. **Cached pak on devel (this file):**
   `SynologyDSM-1001.pak` → `adapter_kind: mpb_synology_dsm`,
   `display_name: Synology DSM`, `vendor: VCF Content Factory`,
   `version: 1.0.0.1`. Was present in devel's pak cache but
   **not a currently active registered solution** when Phase A
   recon ran — either previously uninstalled or never fully
   registered.

2. **Currently registered MP on devel (Phase A finding):**
   `adapter_kind: mpb_synology_dsm_roundtrip`, display name
   "Synology DSM Roundtrip", `vendor: VCF Content Factory`,
   `version: 1.0.0.1`. This is the factory's diagnostic mirror
   built from `managementpacks/synology_dsm_roundtrip.yaml`.

3. **Build-8 reference JSON (hand-MPB authored):**
   `references/sentania_aria_operations_dsm_mp/Management Pack JSON/Synology DSM MP.json`
   (140,079 bytes). This is Scott's original
   hand-authored MPB design JSON from the sentania GitHub repo.
   It predates the factory and is the closest thing to a
   "legacy, pre-factory" reference.

**Consequence:** Both paks in devel's cache claim vendor
`VCF Content Factory`, so neither is a strict pre-factory
hand-MPB build. Scott's "legacy" framing for this pak is
accepted but the artifact is more accurately described as
"a prior factory build that was not the currently-registered
one". The only strictly pre-factory artifact available for
comparison is the build-8 reference JSON.

## Roundtrip reference materials already in repo

Factory MP YAMLs relevant to this bisect:

| Path | Role |
|---|---|
| `managementpacks/synology_dsm.yaml` | Current factory source of truth for the Synology DSM MP |
| `managementpacks/synology_dsm.reference.yaml` | Parallel reference-shaped YAML (see file for role) |
| `managementpacks/synology_dsm_chain1.yaml` | Chain1 diagnostic variant (chaining wire-format experiments — see `context/mpb_chaining_wire_format.md`) |
| `managementpacks/synology_dsm_roundtrip.yaml` | Roundtrip diagnostic mirror (matches the currently-registered `mpb_synology_dsm_roundtrip` on devel) |

External / hand-authored reference (do not modify):

- `references/sentania_aria_operations_dsm_mp/Management Pack JSON/Synology DSM MP.json`
  — build-8 hand-MPB design JSON, the one genuinely
  pre-factory artifact in the repo.
- `references/sentania_aria_operations_dsm_mp/API Exploration/`
  — Synology DSM API exploration notes + Postman collection
  used to scope the original MP.
- `references/sentania_aria_operations_dsm_mp/README.md`
  — upstream context; "tech demonstrator customers can relate
  to for building their own management packs".

## Next step (awaiting Scott confirmation)

Scott to confirm the bisect scope before Phase C. Two plausible
comparisons:

- **Option A (factory-output vs this legacy pak):** Build a
  factory pak from `managementpacks/synology_dsm.yaml`, then
  byte-diff its `design.json` / `export.json` / `describe.xml`
  against this pak's corresponding artifacts. Tests whether the
  factory reproduces the prior cached build.
- **Option B (factory-output vs roundtrip-YAML output):** Build
  from `managementpacks/synology_dsm_roundtrip.yaml` and diff
  against what's currently registered on devel (adapter_kind
  `mpb_synology_dsm_roundtrip`). Tests the chaining-fix
  landing from 2026-04-19.
- **Option C (factory-output vs build-8 reference JSON):** Diff
  factory `design.json` against the sentania build-8 JSON.
  Tests the "can the factory regenerate a hand-authored
  design" contract end-to-end.

No bisect performed in Phase B — inventory-only per task
scope.

## Cleanup

Extraction was performed in `/tmp/synology-pak-inspect/` with
`unzip -l` (metadata-only for the pak) and `unzip -q -o` to
pull out `manifest.txt` and `adapters.zip` for cataloging.
`adapters.zip` was listed with `unzip -l` without further
extraction. The temp directory was removed after cataloging;
no extracted bytes remain in the workspace. The only bytes
written to the repo are this `REFERENCE.md` and the pak itself
at `SynologyDSM-1001.pak`.
