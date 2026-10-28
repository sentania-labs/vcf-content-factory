# vcfcf_managementpacks

Authoring, validation, rendering, and packaging for VCF Operations
management packs. Consumed by the `managementpacks/*.yaml` source of
truth and produces importable `.pak` files under `dist/`.

## Commands

```bash
# Validate all MP YAML sources
python3 -m vcfcf_managementpacks validate

# List known management pack definitions
python3 -m vcfcf_managementpacks list

# Render MP YAML to an MPB design JSON (for upload into MPB UI or inspection)
python3 -m vcfcf_managementpacks render managementpacks/synology_dsm.yaml \
  --output /tmp/synology.mpb.json \
  [--relationship-strategy {world_implicit|synthetic_adapter_instance|shared_constant_property|test_all}]

# Build a .pak file end-to-end from MP YAML
python3 -m vcfcf_managementpacks build managementpacks/synology_dsm.yaml \
  --output dist/ \
  [--relationship-strategy ...]
```

```bash
# Install a .pak onto a live VCF Ops instance
# Credentials: VCFOPS_HOST, VCFOPS_USER, VCFOPS_PASSWORD (or --host/--user/--password flags)
# Any admin-privileged account works — no separate admin account required.
python3 -m vcfcf_managementpacks install dist/mpb_synology_dsm.1.0.0.1.pak

# Uninstall by display name, UI pakId, or adapter_kind
python3 -m vcfcf_managementpacks uninstall "Synology DSM"
python3 -m vcfcf_managementpacks uninstall mpb_synology_dsm

# Fire-and-forget (no completion polling)
python3 -m vcfcf_managementpacks install dist/mpb_synology_dsm.1.0.0.1.pak --no-wait
python3 -m vcfcf_managementpacks uninstall "Synology DSM" --no-wait
```

Both install and uninstall run through a single `/ui/` SPA session —
no `/admin/` session or separate admin credentials required.  See
`knowledge/context/api-surface/pak_ui_upload_investigation.md` §"Live-source findings" for
the wire format, and `knowledge/context/api-surface/pak_uninstall_api_exploration.md` for
the `isUnremovable` safety guard (mandatory; built-in paks are refused
unless `--allow-builtin` is passed).

**Subprocess timeout note**: the `install` command's internal completion
poller waits up to 1800 seconds (`INSTALL_POLL_TIMEOUT`; `--install-timeout`
or `VCFCF_INSTALL_TIMEOUT_S` overrides it; it was 300 s until 2026-10-26,
when two devel installs outlived it).  If you invoke
`python3 -m vcfcf_managementpacks install` from a script or test harness
via `subprocess`, set your subprocess timeout above that wait plus the
post-install checks below, or the harness kills the process while an
install is still in progress on the server.  When the poller runs out with
the server's last answer still reporting the install running, `install`
prints `INSTALL STILL RUNNING` and exits 4 (when the last status poll
failed instead, the status is unknown and it exits 1): not a failure, do not reinstall, and
the post-install checks below did not run (no command re-runs them on their
own against an installed pak).  Uninstall keeps its 300 s poll (`POLL_TIMEOUT`).
After the install verifies, `install` restarts the accounts the install
left FAILED (lesson `remote-collector-upgrade-start-race`): on a remote
collector or Cloud Proxy the server sends Start monitoring before the
collector has loaded the new jar, and every account of the adapter kind
stays FAILED until someone starts it. Before the upload it reads each
adapter instance of the pak's `adapter_kinds` and its `resourceState`;
after the install it watches them for 120 s, then sends
`PUT /api/adapters/{id}/monitoringstate/start` to each that reads FAILED,
STOPPED or NONE and read STARTED, STARTING, UPDATING or FAILED before the
install. One that was STOPPED or in maintenance before is never started
(the user's choice); one with no usable state from before (UNKNOWN, NONE,
NOT_EXISTING, no status entry, or the read failed) is started only when
FAILED. An account that reads FAILED again 60 s after its start gets a
second one, never a third. It polls until they read STARTED or a 300 s
deadline passes, with a 30 s timeout on every Suite API call, each cut to
what is left of that deadline (no request or start is sent past it, and
accounts it had no room to start are named). Starts may not use the last
30 s, which is kept for a state read after them; an account with no reading
after its last start is reported `ACCOUNT UNCHECKED`, never `ACCOUNT NOT
STARTED`. The one way past it is the
server rejecting the session token in the last seconds: the client then
gets a new token and retries the call, 30 s each, so the check takes up to
about 360 s in the worst case. It only ever starts
from that poll's reading. Each account's final state is printed (`ACCOUNT
OK`, `ACCOUNT LEFT ALONE`, `ACCOUNT NOT COLLECTING` when it has no usable
state from before and was not started, `ACCOUNT UNCHECKED` when its state
is unreadable, or `ACCOUNT NOT STARTED`, which sets exit code 3). Exit 3
also covers an account that was already FAILED before the install and still
is (bad credentials, say). When the last read failed, or a 401/403 stopped
the watch, it prints `ACCOUNTS UNCHECKED` with the state as of the last good
read and leaves the exit code alone. This adds about 2 minutes when the
pak's adapter kind has accounts; `--no-restart-failed` skips it, and
`--no-wait` never runs it.
A start runs whatever adapter jar the collector has loaded, and no Suite API
endpoint reports which version that is. When a Cloud Proxy's jar sync fails
(collector log: "Adapter jar synchronization failed", after "Did not receive
response from Controller for 'Sync Adapters' task"), the proxy keeps the old
version: re-run the same install instead of starting the account.
`ACCOUNT NOT STARTED` says so, and a `NOTE` line says so whenever the
installer sent a start.
After that, `install` checks that each dashboard the pak ships
finished building (issue #244); when one is still building it waits once
(180 s by default, `--materialization-wait`, capped at 900 s) before the
re-check, so allow that much more, or pass `--skip-materialization-check`.
When the pak binds a Summary dashboard (`dashboards.properties`), `install`
repairs the server's ordering (issue #200): the server copies the dashboard
onto the Summary tab seconds after importing it, before the dashboard has
finished building, and on 9.0.2 and 8.18 that copy stays unfinished. So
`install` polls for up to 660 s until the bound dashboards are built, then
binds again any Summary copy that is unfinished, in the request form the
build reads (issue #260), and reads the new copy back. `--skip-summary-rebind`
or `VCFCF_SUMMARY_REBIND=0` turns the repair off; the install then only
reads each copy and prints `SUMMARY OK` or `SUMMARY INCOMPLETE <kind>
<copy id> (<n> of <m> widgets loading)` as information. `--summary-rebind`
is accepted and is the default. Exit code 3 means the pak installed but a post-install check failed
(`ACCOUNT NOT STARTED`, including an account already FAILED before the install, `MATERIALIZATION STALLED`, or with the repair on `SUMMARY NOT REBOUND`,
which quotes the server's HTTP status and answer); do not reinstall on it,
except for `ACCOUNT NOT STARTED` when the collector log shows "Adapter jar
synchronization failed".

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
this repo. The `vcfcf_managementpacks/adapter_runtime/` directory
is gitignored for that reason.

To bootstrap a workstation so `build` can run:

1. Acquire any working MPB-generated `.pak` file from a VCF Ops
   solution you are entitled to use (example: Dale Hassinger's
   GitHub MP at
   `reference/references/dalehassinger_unlocking_the_potential/VMware-Aria-Operations/Management-Packs/GitHub/GitHub-1.0.0.2.pak`).

2. Extract `adapters.zip` from the `.pak`:

   ```bash
   unzip -q -o <pak-file> adapters.zip -d /tmp/
   ```

3. Extract the adapter runtime from the inner `adapters.zip`:

   ```bash
   mkdir -p vcfcf_managementpacks/adapter_runtime
   unzip -q /tmp/adapters.zip -d /tmp/adapters_extracted
   # Pick the inner adapter directory (e.g. mpb_github_adapter3/)
   cp /tmp/adapters_extracted/<adapter-dir>/lib/*.jar \
     vcfcf_managementpacks/adapter_runtime/lib/
   cp /tmp/adapters_extracted/<adapter-dir>_adapter3.jar \
     vcfcf_managementpacks/adapter_runtime/mpb_adapter3.jar
   ```

4. Verify: `ls vcfcf_managementpacks/adapter_runtime/lib/ | wc -l`
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
4. Drop that JAR into `vcfcf_managementpacks/adapter_runtime/`
   under the adapter-kind-specific name (e.g.
   `mpb_synology_dsm_adapter3.jar`). The builder will prefer
   adapter-specific JARs over the generic stand-in.

After that one-time bootstrap, the factory handles all subsequent
regenerations end-to-end for that adapter kind.

## Bootstrap: populating `adapter_runtime/` for Tier 2 SDK

Tier 2 SDK builds require four Broadcom/VMware JAR files in
`vcfcf_managementpacks/adapter_runtime/` plus the compiled framework JAR.
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

Two more jars are compile checks only, never on the shipped classpath,
one leg per supported line (issues #211, #252): `vrops-adapters-sdk-8.18.7.jar`
(Aria Operations 8.18.7; Java 11, any JDK 11+) and
`vrops-adapters-sdk-9.1.1.0100.jar` (VCF Ops 9.1.1.0100; Java 25, JDK 25+).
The 2.2 jar is the third leg (9.0, compiled again at `--release 17`). Neither
compat jar is in this public repo. Both are in the private
`sentania-labs/vcf-content-factory-sdk-runtime` repo (factory CI fetches
them there) and on the lab holding share under
`/mnt/holding/vendor/vcf-ops-8.18.7/extracted-jars/` and
`/mnt/holding/vendor/vcf-ops-9.1.1.0100/extracted-jars/` (local-only), or
take one from an appliance of that line (`common/lib/vrops-adapters-sdk.jar`).
Put each in `adapter_runtime/` **under the name above** (under any other
name it is a second primary SDK jar and the build stops), check its sha256,
and put JDK 25+ where the build can find it for the 9.1.1 leg; build-sdk,
validate-sdk and `build-framework.sh` then compile once per line and fail
on anything a line lacks. Every SDK jar's hashes and builds:
`adapter_runtime/PROVENANCE.md`.

A new cloning user would source these JARs the same way: from a VCF Ops
devel/lab appliance using the same cleanroom extraction procedure. The
JARs are NOT publicly downloadable — they ship as part of the VCF Ops
appliance installation.

### Bootstrap steps

1. Obtain the four JARs (from a Navani-style devel extraction or equivalent):

   ```
   vcfcf_managementpacks/adapter_runtime/vrops-adapters-sdk-2.2.jar
   vcfcf_managementpacks/adapter_runtime/alive_common.jar
   vcfcf_managementpacks/adapter_runtime/alive_platform.jar
   vcfcf_managementpacks/adapter_runtime/aria-ops-core-8.0.0.jar
   ```

2. Build the framework JAR (requires JDK 11+):

   ```bash
   cd vcfcf_managementpacks/
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
   jar cf vcfcf_managementpacks/adapter_runtime/vmware-ops-api-stubs.jar \
       -C /tmp/rds/classes .
   ```

4. Verify: `python3 -m vcfcf_managementpacks validate-sdk content/sdk-adapters/hello-world/`
   should print `OK`.

## Tier 2 commands

```bash
# Compile and package a Tier 2 SDK adapter project into a .pak
python3 -m vcfcf_managementpacks build-sdk content/sdk-adapters/hello-world/
# Output: dist/vcfcf_hello_world.1.0.0.1.pak

# Validate an adapter project (schema + compile-check, no pak output)
python3 -m vcfcf_managementpacks validate-sdk content/sdk-adapters/hello-world/

# Generate an empty Tier 2 adapter project skeleton
python3 -m vcfcf_managementpacks scaffold-sdk "My Custom Monitor" \
    --output content/sdk-adapters/

# Auto-routed build (detects Tier 1 vs Tier 2 from the argument):
#   If arg is a .yaml file → Tier 1 MPB build
#   If arg is a directory with adapter.yaml → Tier 2 SDK build
python3 -m vcfcf_managementpacks build content/sdk-adapters/hello-world/
python3 -m vcfcf_managementpacks build content/managementpacks/cloudflare.yaml
```

### Framework rebuild

When framework Java source under `adapter_framework/src/` changes:

```bash
cd vcfcf_managementpacks/
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

- `knowledge/context/mpb/reference-mpb-research.md` — MPB design JSON schema baseline
- `knowledge/context/mpb/mp_schema_vs_existing_mp.md` — sanity check against a
  known-working MP; documents wire-format deltas informed by live
  reference JSON
- `knowledge/context/wire-formats/pak_wire_format.md` — `.pak` and `adapters.zip` internals,
  manifest shape, describe.xml structure, adapter JAR gap
- `knowledge/context/api-surface/pak_install_api_exploration.md` — scripted install via
  admin SPA Struts layer (11-step flow)
- `knowledge/context/api-surface/pak_uninstall_api_exploration.md` — scripted uninstall via
  `/ui/solution.action mainAction=remove`, mandatory
  `isUnremovable` safety guard
