# .pak Wire Format (MPB Management Pack Package)

Documented from reverse-engineering two reference paks:
- `GitHub-1.0.0.2.pak` (mpb_github_adapter3)
- `Broadcom Security Advisories-1.0.1.6.pak` (mpb_broadcom_security_advisories_adapter3)

Both are in `references/dalehassinger_unlocking_the_potential/VMware-Aria-Operations/Management-Packs/`.

## Top-level .pak ZIP layout

```
/
├── manifest.txt              # JSON (not XML despite .txt extension)
├── eula.txt                  # License text (Broadcom standard ~111 lines)
├── default.png               # Solution icon (19377 bytes, same file both paks)
├── adapters.zip              # Nested ZIP — bulk of the file
├── validate.py               # Pre-install validator (checks VCOPS_BASE)
├── preAdapters.py            # Pre-adapter hook (stub: prints "In Pre")
├── postAdapters.py           # Post-adapter hook (stub: prints "In post")
├── post-install.py           # Post-install content importer (real work)
├── post-install-fast.sh      # Bash redescribe stub
├── post-install.sh           # Secondary bash stub (present but minimal)
├── content/
│   ├── supermetrics/customSuperMetrics.json   # "{}" or "[]"
│   ├── dashboards/            # bundled dashboard JSON files (may be empty)
│   ├── reports/               # empty
│   ├── views/                 # empty
│   └── files/reskndmetric/    # empty
└── resources/
    └── resources.properties   # DISPLAY_NAME, DESCRIPTION, VENDOR keys
```

## manifest.txt shape

```json
{
  "display_name": "DISPLAY_NAME",
  "name": "<adapter_name>",
  "description": "<description>",
  "version": "<major>.<minor>.<patch>.<build>",
  "run_scripts_on_all_nodes": "true",
  "vcops_minimum_version": "7.5.0",
  "disk_space_required": 500,
  "eula_file": "eula.txt",
  "platform": ["Windows", "Linux Non-VA", "Linux VA"],
  "vendor": "<author>",
  "pak_icon": "default.png",
  "license_type": "adapter:<adapter_kind>",
  "pak_validation_script": {"script": "python validate.py"},
  "adapter_pre_script": {"script": "python preAdapters.py"},
  "adapter_post_script": {"script": "python post-install.py"},
  "adapters": ["adapters.zip"],
  "adapter_kinds": ["<adapter_kind>"]
}
```

## adapters.zip internal layout

```
/
├── manifest.txt              # SAME as pak root (duplicated)
├── eula.txt                  # SAME as pak root (duplicated)
├── default.png               # SAME as pak root (duplicated)
├── resources/
│   └── resources.properties  # SAME as pak root (duplicated)
├── <adapter_dir>.jar         # The adapter runtime JAR (see ADAPTER_JAR_GAP)
│                             # e.g. mpb_github_adapter3.jar
└── <adapter_dir>/
    ├── conf/
    │   ├── design.json       # The MPB design JSON (our rendered output)
    │   ├── describe.xml      # Adapter kind XML (generated from design)
    │   ├── export.json       # MPB export metadata (appears to be full design copy)
    │   ├── <adapter_kind>.properties  # Runtime config (relationship_sync_interval etc.)
    │   ├── version.txt       # Major/Minor/Implementation-Version
    │   ├── supermetrics/
    │   │   └── customSuperMetrics.json   # "{}" (empty)
    │   ├── dashboards/       # bundled dashboard JSON (empty for new MPs)
    │   ├── reports/          # empty
    │   ├── views/            # empty
    │   ├── images/
    │   │   ├── TraversalSpec/default.png
    │   │   ├── AdapterKind/<adapter_kind>.png
    │   │   └── ResourceKind/<adapter_kind>.png  (+ per-object-type variants)
    │   └── resources/
    │       └── resources.properties  # integer-keyed localization strings
    ├── lib/
    │   └── *.jar             # 59 shared library JARs (identical across all MPB paks)
    ├── work/                 # empty runtime work directory
    └── doc/                  # empty documentation directory
```

The `<adapter_dir>` name pattern is `<adapter_kind>_adapter3`
(e.g. `mpb_synology_dsm_adapter3`).

## ADAPTER_JAR_GAP

The `<adapter_dir>.jar` file is compiled by the MPB server build endpoint
from the design JSON. It contains Kotlin/Java classes with the adapter kind
key baked into the package path (e.g. `com.vmware.mpb.mpbgithub`). The
factory cannot generate this JAR.

Workaround: the factory copies the GitHub reference JAR (renamed) as a
stand-in. The lib/*.jar files are the actual adapter implementation JARs
and are identical across all MPB paks — these provide the real collection
logic. The main JAR appears to be a thin shim with adapter-specific class
names used by the VCF Ops plugin loader. Test whether a renamed stub JAR
allows the pak to install and function; if the adapter uses the main JAR
as its entry point (not just lib/), install will fail.

**To get a real JAR**: upload the design JSON to the MPB UI → Build pak →
download. Extract the JAR from adapters.zip and drop it into
`vcfops_managementpacks/adapter_runtime/<adapter_dir>.jar`.
The builder will prefer an adapter-specific JAR over the generic stand-in.

## describe.xml structure

```xml
<AdapterKind key="<adapter_kind>" nameKey="1" version="1">
  <CredentialKinds>
    <CredentialKind key="<adapter_kind>_credentials" nameKey="2">
      <CredentialField key="username" password="false" type="string" .../>
      <CredentialField key="password" password="true" type="string" .../>
    </CredentialKind>
  </CredentialKinds>
  <ResourceKinds>
    <!-- World/adapter-instance object: type="8" subType="6" -->
    <ResourceKind key="..." nameKey="..." worldObjectName="..." type="8" subType="6">
      <ResourceGroup key="summary" ...>
        <ResourceAttribute key="..." dataType="float" isProperty="false" .../>
      </ResourceGroup>
      <ComputedMetrics>
        <ComputedMetric key="summary|<metric>" expression="sum(...)" />
      </ComputedMetrics>
    </ResourceKind>
    <!-- Regular resource kind: type="7" credentialKind="..." monitoringInterval="5" -->
    <ResourceKind key="..." nameKey="..." type="7" credentialKind="..." monitoringInterval="5">
      <ResourceIdentifier key="mpb_hostname" identType="1" .../>  <!-- identType 1 = display -->
      <ResourceIdentifier key="mpb_port" identType="2" .../>      <!-- identType 2 = advanced -->
      ... (mpb_connection_timeout, mpb_concurrent_requests, mpb_max_retries, mpb_ssl_config) ...
      <ResourceIdentifier key="support_autodiscovery" identType="2" enum="true" .../>
      <ResourceGroup key="summary" ...>
        <ResourceAttribute key="<metric_key>" dataType="float" isProperty="false" .../>
      </ResourceGroup>
      <ResourceAttribute key="<prop_key>" dataType="string" isProperty="true" .../>
    </ResourceKind>
  </ResourceKinds>
  <Discoveries>
    <Discovery key="<adapter_kind>_manual_discovery" nameKey="100"/>
  </Discoveries>
  <TraversalSpecKinds/>
  <LicenseConfig enabled="false"/>
  <SymptomDefinitions/>
  <AlertDefinitions/>
  <Recommendations/>
  <UnitDefinitions>
    <!-- Full unit type set: bytes_base10/2, bits_base10/2, rates, cycle_rate,
         time, count, percent, per_second — see builder.py for exact XML -->
  </UnitDefinitions>
</AdapterKind>
```

## post-install.py behavior

The post-install.py script:
1. Determines VCOPS_BASE from environment.
2. Ensures the adapter work/ directory exists.
3. Calls `ops-cli.py control redescribe --force` to make VCF Ops pick up the
   new describe.xml from `conf/`.
4. Sleeps 30 seconds.
5. Imports bundled views, reports, supermetrics, and dashboards from `conf/`
   subdirectories using ops-cli.
6. Logs all operations to `work/install.log`.

The describe.xml is NOT generated at install time — it is pre-baked in conf/
and loaded by the adapter framework when the redescribe runs. This is
consistent with the MPB adapter architecture: design JSON → describe.xml is
a build-time step done by the MPB server, not a runtime step.

## resources/resources.properties (adapters.zip/conf/resources/)

Integer-keyed localization strings. Minimum required keys:
- `version=1`
- `1=<adapter kind display name>`
- `2=Credentials`
- `3=Username` / `4=Password`
- Subsequent integers: resource kind labels, metric labels.

## lib/ JARs

Identical across all MPB paks (verified by directory listing comparison):
59 JAR files including kotlin-stdlib, jackson, ktor, log4j, guava, and the
MPB-specific `mpb_common-2.0.0-ga-32.jar` and `mpb_clients-2.0.0-ga-32.jar`.
These provide the collection runtime; the main adapter JAR is a thin adapter-
kind-specific shim on top.
