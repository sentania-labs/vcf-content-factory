# vcfops_managementpacks

Authoring, validation, rendering, and packaging for VCF Operations
management packs. Consumed by the `managementpacks/*.yaml` source of
truth and produces importable `.pak` files under `dist/`.

## Commands

```bash
# Validate all MP YAML sources
python3 -m vcfops_managementpacks validate

# List known management pack definitions
python3 -m vcfops_managementpacks list

# Render MP YAML to an MPB design JSON (for upload into MPB UI or inspection)
python3 -m vcfops_managementpacks render managementpacks/synology_dsm.yaml \
  --output /tmp/synology.mpb.json \
  [--relationship-strategy {world_implicit|synthetic_adapter_instance|shared_constant_property|test_all}]

# Build a .pak file end-to-end from MP YAML
python3 -m vcfops_managementpacks build managementpacks/synology_dsm.yaml \
  --output dist/ \
  [--relationship-strategy ...]
```

```bash
# Install a .pak onto a live VCF Ops instance
# Credentials: VCFOPS_HOST, VCFOPS_USER, VCFOPS_PASSWORD (or --host/--user/--password flags)
# Any admin-privileged account works — no separate admin account required.
python3 -m vcfops_managementpacks install dist/mpb_synology_dsm.1.0.0.1.pak

# Uninstall by display name, UI pakId, or adapter_kind
python3 -m vcfops_managementpacks uninstall "Synology DSM"
python3 -m vcfops_managementpacks uninstall mpb_synology_dsm

# Fire-and-forget (no completion polling)
python3 -m vcfops_managementpacks install dist/mpb_synology_dsm.1.0.0.1.pak --no-wait
python3 -m vcfops_managementpacks uninstall "Synology DSM" --no-wait
```

Both install and uninstall run through a single `/ui/` SPA session —
no `/admin/` session or separate admin credentials required.  See
`context/pak_ui_upload_investigation.md` §"Live-source findings" for
the wire format, and `context/pak_uninstall_api_exploration.md` for
the `isUnremovable` safety guard (mandatory; built-in paks are refused
unless `--allow-builtin` is passed).

**Subprocess timeout note**: the `install` command's internal completion
poller defaults to 300 seconds (`POLL_TIMEOUT`).  If you invoke
`python3 -m vcfops_managementpacks install` from a script or test harness
via `subprocess`, set your subprocess timeout to at least 400 seconds —
a subprocess timeout of 300s or less will race the internal poller and
kill the process while an install is still in progress on the server.

**Credential env vars** (matches the rest of the factory):

| Env var | Purpose |
|---|---|
| `VCFOPS_HOST` | Hostname or IP of the VCF Ops instance |
| `VCFOPS_USER` | Admin-privileged username |
| `VCFOPS_PASSWORD` | Password |

The legacy `VCFOPS_ADMIN` / `VCFOPS_ADMINPASSWORD` names are accepted
as fallbacks with a deprecation warning.  Rename to the primary names
at your earliest convenience.

## Bootstrap: populating `adapter_runtime/`

`.pak` file assembly requires the MPB adapter runtime JARs —
specifically the generic `lib/*.jar` files (common across all
MPB-generated paks) and a top-level `<adapter_kind>_adapter3.jar`.
These are VMware/Broadcom binaries; they are not distributed via
this repo. The `vcfops_managementpacks/adapter_runtime/` directory
is gitignored for that reason.

To bootstrap a workstation so `build` can run:

1. Acquire any working MPB-generated `.pak` file from a VCF Ops
   solution you are entitled to use (example: Dale Hassinger's
   GitHub MP at
   `references/dalehassinger_unlocking_the_potential/VMware-Aria-Operations/Management-Packs/GitHub/GitHub-1.0.0.2.pak`).

2. Extract `adapters.zip` from the `.pak`:

   ```bash
   unzip -q -o <pak-file> adapters.zip -d /tmp/
   ```

3. Extract the adapter runtime from the inner `adapters.zip`:

   ```bash
   mkdir -p vcfops_managementpacks/adapter_runtime
   unzip -q /tmp/adapters.zip -d /tmp/adapters_extracted
   # Pick the inner adapter directory (e.g. mpb_github_adapter3/)
   cp /tmp/adapters_extracted/<adapter-dir>/lib/*.jar \
     vcfops_managementpacks/adapter_runtime/lib/
   cp /tmp/adapters_extracted/<adapter-dir>_adapter3.jar \
     vcfops_managementpacks/adapter_runtime/mpb_adapter3.jar
   ```

4. Verify: `ls vcfops_managementpacks/adapter_runtime/lib/ | wc -l`
   should report around 59. The top-level `mpb_adapter3.jar` should
   exist.

## Adapter JAR gap

The `<adapter_kind>_adapter3.jar` at the root of each pak contains
Kotlin/Java classes with the adapter kind baked into the package
path (e.g. `com.vmware.mpb.mpbsynologydsm`). The factory cannot
regenerate this JAR — only MPB's server-side build endpoint can
compile it. The bootstrap step above uses a renamed generic JAR
(derived from the GitHub reference pak) as a structural stand-in.

**Whether VCF Ops accepts the stand-in JAR at install time is
unverified.** Install testing is the only way to confirm. If
rejected, the workaround is a one-time MPB-UI bootstrap per
adapter kind:

1. Render your `managementpacks/*.yaml` to MPB design JSON via
   `render --output design.json`.
2. Upload `design.json` into the MPB UI on a VCF Ops instance;
   let MPB compile the pak.
3. Download the generated `.pak`; extract the real
   `<adapter_kind>_adapter3.jar`.
4. Drop that JAR into `vcfops_managementpacks/adapter_runtime/`
   under the adapter-kind-specific name (e.g.
   `mpb_synology_dsm_adapter3.jar`). The builder will prefer
   adapter-specific JARs over the generic stand-in.

After that one-time bootstrap, the factory handles all subsequent
regenerations end-to-end for that adapter kind.

## Bootstrap: populating `adapter_runtime/` for Tier 2 SDK

Tier 2 SDK builds require four Broadcom/VMware JAR files in
`vcfops_managementpacks/adapter_runtime/` plus the compiled framework JAR.
These are VMware/Broadcom binaries; **do not commit them**. The directory
is gitignored for this reason.

### Where the JARs come from

The four staged JARs originate from the cleanroom workspace
`inputs/from-devel/sdk/` (captured from the VCF Ops devel appliance
on 2026-05-15 by Navani):

| JAR | Layer | On appliance classpath? |
|---|---|---|
| `vrops-adapters-sdk-2.2.jar` | Layer 1 — SDK contract | Yes (do NOT bundle in pak) |
| `alive_common.jar` | Layer 1 — SDK types | Yes (do NOT bundle in pak) |
| `alive_platform.jar` | Layer 1 — platform API types | Yes (do NOT bundle in pak) |
| `aria-ops-core-8.0.0.jar` | Layer 2 — UnlicensedAdapter | No (MUST bundle in pak) |

A new cloning user would source these JARs the same way: from a VCF Ops
devel/lab appliance using the same cleanroom extraction procedure. The
JARs are NOT publicly downloadable — they ship as part of the VCF Ops
appliance installation.

### Bootstrap steps

1. Obtain the four JARs (from a Navani-style devel extraction or equivalent):

   ```
   vcfops_managementpacks/adapter_runtime/vrops-adapters-sdk-2.2.jar
   vcfops_managementpacks/adapter_runtime/alive_common.jar
   vcfops_managementpacks/adapter_runtime/alive_platform.jar
   vcfops_managementpacks/adapter_runtime/aria-ops-core-8.0.0.jar
   ```

2. Build the framework JAR (requires JDK 11+):

   ```bash
   cd vcfops_managementpacks/
   ./adapter_framework/build-framework.sh
   ```

   This produces `adapter_runtime/vcfcf-adapter-base.jar` (~28KB).

3. Create the compile-time stub for `com.vmware.ops.api.model.resource.ResourceDto`
   (needed because aria-ops-core's `Resource` class references this type, which
   lives on the appliance's runtime classpath but is absent from the staged JARs):

   ```bash
   mkdir -p /tmp/rds/com/vmware/ops/api/model/resource
   cat > /tmp/rds/com/vmware/ops/api/model/resource/ResourceDto.java << 'EOF'
   package com.vmware.ops.api.model.resource;
   public class ResourceDto implements java.io.Serializable {
       private static final long serialVersionUID = 1L;
   }
   EOF
   javac /tmp/rds/com/vmware/ops/api/model/resource/ResourceDto.java -d /tmp/rds/classes
   jar cf vcfops_managementpacks/adapter_runtime/vmware-ops-api-stubs.jar \
       -C /tmp/rds/classes .
   ```

4. Verify: `python3 -m vcfops_managementpacks validate-sdk content/sdk-adapters/hello-world/`
   should print `OK`.

## Tier 2 commands

```bash
# Compile and package a Tier 2 SDK adapter project into a .pak
python3 -m vcfops_managementpacks build-sdk content/sdk-adapters/hello-world/
# Output: dist/vcfcf_hello_world.1.0.0.1.pak

# Validate an adapter project (schema + compile-check, no pak output)
python3 -m vcfops_managementpacks validate-sdk content/sdk-adapters/hello-world/

# Generate an empty Tier 2 adapter project skeleton
python3 -m vcfops_managementpacks scaffold-sdk "My Custom Monitor" \
    --output content/sdk-adapters/

# Auto-routed build (detects Tier 1 vs Tier 2 from the argument):
#   If arg is a .yaml file → Tier 1 MPB build
#   If arg is a directory with adapter.yaml → Tier 2 SDK build
python3 -m vcfops_managementpacks build content/sdk-adapters/hello-world/
python3 -m vcfops_managementpacks build content/managementpacks/cloudflare.yaml
```

### Framework rebuild

When framework Java source under `adapter_framework/src/` changes:

```bash
cd vcfops_managementpacks/
./adapter_framework/build-framework.sh
```

This rebuilds `adapter_runtime/vcfcf-adapter-base.jar` in place.

### Tier 2 pak structure (SDK format)

Tier 2 paks differ from Tier 1 (MPB) paks in these ways:

| Field | Tier 1 (MPB) | Tier 2 (SDK) |
|---|---|---|
| Outer pak prefix | `mpb_vcf_content_factory_*` | `vcfcf_*` |
| `manifest.txt` `adapters:` field | Present | Absent |
| `manifest.txt` `adapter_kinds:` | Yes | Yes (only field referencing adapter) |
| `design.json` in adapters.zip | Present | Absent |
| `template.json` in adapters.zip | Present | Absent |
| Entry JAR | `mpb_adapter-*.jar` (Broadcom) | `<adapter_kind>.jar` (we build) |
| `adapter.properties` | MPB generates | `sdk_builder.py` generates |
| `describe.xml` | MPB generates from BuilderFile | Hand-authored in project |
| `lib/vcfcf-adapter-base.jar` | Absent | Present (our framework) |
| `lib/aria-ops-core-*.jar` | Present (MPB dep) | Present (required; not on shared classpath) |

For the Tier 2 adapter kind naming convention:
- `adapter_kind` in `adapter.yaml` does NOT include the `vcfcf_` prefix
  (e.g. `hello_world`, `synology`)
- The pak filename automatically adds the prefix: `vcfcf_hello_world.1.0.0.1.pak`

## Related context

- `context/mpb/reference-mpb-research.md` — MPB design JSON schema baseline
- `context/mp_schema_vs_existing_mp.md` — sanity check against a
  known-working MP; documents wire-format deltas informed by live
  reference JSON
- `context/pak_wire_format.md` — `.pak` and `adapters.zip` internals,
  manifest shape, describe.xml structure, adapter JAR gap
- `context/pak_install_api_exploration.md` — scripted install via
  admin SPA Struts layer (11-step flow)
- `context/pak_uninstall_api_exploration.md` — scripted uninstall via
  `/ui/solution.action mainAction=remove`, mandatory
  `isUnremovable` safety guard
