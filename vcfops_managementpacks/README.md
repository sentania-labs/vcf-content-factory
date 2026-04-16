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

Install and uninstall subcommands (for pushing `.pak` files to a live
VCF Ops instance) are planned under task 18 (`context/pak_install_api_exploration.md`
+ `context/pak_uninstall_api_exploration.md`).

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

## Related context

- `docs/reference-mpb-research.md` — MPB design JSON schema baseline
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
