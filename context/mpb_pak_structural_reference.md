# MPB Pak Structural Reference

Canonical structural reference for Management Pack Builder (MPB) .pak
files. Derived from dissecting 8+ reference paks (2026-05-14).

## Reference inventory

### MPB-built paks (Gen-2, VCF Ops 9.x)

| Pak | Auth | Objects | ARIA_OPS | Events | Source |
|---|---|---|---|---|---|
| devel MPB-built (vSphere Storage Paths) | none | 0 INTERNAL, 2 ARIA_OPS | HostSystem, Datastore | 0 | Our devel instance |

### MPB-built paks (Gen-1, Aria Ops 8.x)

| Pak | Auth | Objects | ARIA_OPS | Events | Source |
|---|---|---|---|---|---|
| Dale GitHub 1.0.0.2 | username+password | 1 INTERNAL | 0 | 0 | dalehassinger GitHub |
| Dale SecAdvisories 1.0.1.6 | username+password | 2 INTERNAL | 0 | 0 | dalehassinger GitHub |
| Rubrik 1.1.0.25 | username+password | 5 INTERNAL, 1 ARIA_OPS (VM) | 1 | **1** | brockpeterson GitHub |
| phpIPAM 1.0.0.11 | username+password | 3 INTERNAL, 4 ARIA_OPS | 4 | 0 | jcox-au GitHub |
| Ubiquiti UniFi 1.0.0.7 | unknown | 4 INTERNAL, 2 ARIA_OPS | 2 | 0 | jcox-au GitHub |

### SDK-based paks (different adapter runtime)

| Pak | Type | Objects | Source |
|---|---|---|---|
| HPE SimpliVity 1.5.0.2 | SDK-Java | 5 | HewlettPackard GitHub |
| Pure Storage 3.2.0 | SDK-Java | 22 | PureStorage-Connect GitHub |
| vCommunity 0.2.8 | Integration SDK | N/A (container) | vmbro GitHub |
| Hardware vCommunity 2.1.1 | Integration SDK | N/A (container) | vmbro GitHub |

### MPB design JSONs (no pak, design export only)

| Design | ARIA_OPS | Events | Source |
|---|---|---|---|
| Dale FastAPI | 2 (VM, HostSystem) | 0 | dalehassinger GitHub |
| vrealize.it vSAN policy | 1 (Datastore) | 0 | vrealize.it blog |

## Gen-1 vs Gen-2 MPB differences

Gen-1 (Aria Ops 8.x, MPB standalone OVA):
- Has `design.json` inside adapters.zip
- Does NOT have `template.json`
- Bundles ~30 dependency JARs in `lib/`
- Has post-install scripts (post-install.py, preAdapters.py, validate.py)
- Adapter jar uses Kotlin/Ktor HTTP client

Gen-2 (VCF Ops 9.x, MPB built into VCF Ops):
- Does NOT have `design.json` inside adapters.zip
- Has `template.json`
- Bundles only `mpb_adapter-9.0.1-patch-1.jar` in `lib/`
- NO post-install scripts
- Signed (signature.cert, signature.mf)

## Canonical pak structure

### Outer pak (zip)

```
manifest.txt                    # JSON — pak metadata
eula.txt                        # License text
adapters.zip                    # Inner zip with adapter
default.svg                     # Pak icon (Gen-2: svg; Gen-1: png)
resources/resources.properties  # i18n strings
signature.cert                  # Gen-2 only — signing cert
signature.mf                    # Gen-2 only — manifest hash
content/dashboards/overview/overview.json  # Gen-2: bundled dashboard
post-install.py                 # Gen-1 only
preAdapters.py                  # Gen-1 only
postAdapters.py                 # Gen-1 only
validate.py                     # Gen-1 only
post-install.sh                 # Gen-1 only
post-install-fast.sh            # Gen-1 only
```

### manifest.txt key fields

```json
{
    "display_name": "DISPLAY_NAME",     // Literal placeholder in MPB
    "name": "<MP name>",
    "version": "1.0.0.1",
    "vcops_minimum_version": "8.10.0",  // Gen-1; Gen-2 unknown
    "vendor": "VENDOR",                 // Literal placeholder in MPB
    "pak_icon": "default.svg",          // Gen-2: svg; Gen-1: png
    "license_type": "adapter:<adapter_kind>",
    "adapter_kinds": ["<adapter_kind>"],
    "pak_validation_script": {"script": ""},   // Gen-2: empty
    "adapter_pre_script": {"script": ""},      // Gen-2: empty
    "adapter_post_script": {"script": ""}      // Gen-2: empty
}
```

### describe.xml structure

```xml
<AdapterKind key="<adapter_kind>" nameKey="1" version="1">
  <!-- CredentialKinds: present for authenticated MPs, ABSENT for preset:none -->
  <CredentialKinds>
    <CredentialKind key="<ak>_credentials" nameKey="N">
      <ResourceAttribute key="username" .../>
      <ResourceAttribute key="password" .../>
    </CredentialKind>
  </CredentialKinds>

  <ResourceKinds>
    <!-- Adapter instance (type=7) -->
    <ResourceKind key="<ak>" type="7"
                  credentialKind="<ak>_credentials"  <!-- OMIT for preset:none -->
                  monitoringInterval="5">
      <ResourceGroup key="summary" nameKey="3" instanced="false"/>
      <ResourceIdentifier key="mpb_hostname" .../>
      <!-- 8 standard ResourceIdentifiers -->
    </ResourceKind>

    <!-- Data object kinds (INTERNAL objects only) -->
    <ResourceKind key="<ak>_<object_key>" type="?" ...>
      <ResourceGroup key="<group>" instanced="false">
        <ResourceAttribute key="<metric_key>" .../>
      </ResourceGroup>
      <ResourceIdentifier key="<ident1>" identType="1" .../>
      <ResourceIdentifier key="<ident2>" identType="2" .../>
    </ResourceKind>

    <!-- Relatives (type=4) — always present -->
    <ResourceKind key="<ak>_relatives" type="4" showTag="true" dynamic="true">
      <ResourceGroup key="relationships" instanced="false">
        <!-- One ResourceAttribute per INTERNAL object + ARIA_OPS target -->
        <ResourceAttribute key="<suffix>_child" isProperty="true" .../>
      </ResourceGroup>
    </ResourceKind>

    <!-- World (type=8) — always present -->
    <ResourceKind key="<ak>_world" type="8" subType="6"
                  worldObjectName="<name> World" showTag="true">
      <ResourceGroup key="summary" instanced="false"/>
      <ComputedMetrics>
        <!-- One ComputedMetric per INTERNAL data object kind -->
      </ComputedMetrics>
    </ResourceKind>
  </ResourceKinds>

  <!-- ARIA_OPS objects do NOT appear as ResourceKinds in describe.xml -->

  <Discoveries>
    <Discovery key="<ak>_manual_discovery"/>
  </Discoveries>
  <TraversalSpecKinds/>  <!-- Gen-2: empty; Gen-1: may have entries -->
  <LicenseConfig enabled="false"/>
  <SymptomDefinitions/>
  <AlertDefinitions/>
  <Recommendations/>
  <UnitDefinitions><!-- standard unit types --></UnitDefinitions>
</AdapterKind>
```

### Key rules

1. **ARIA_OPS objects do NOT appear in describe.xml** — they only
   exist in export.json/template.json. The adapter runtime handles
   stitching at collection time.

2. **`_relatives` gets one `_child` attribute per object type** —
   both INTERNAL objects (using their key suffix) and ARIA_OPS
   targets (using the target resource_kind name like `HostSystem`).

3. **`_world` gets one ComputedMetric per INTERNAL data object** —
   this is the object count metric. ARIA_OPS objects don't get
   computed metrics.

4. **`preset: none` → no CredentialKinds** — omit the entire block
   and the `credentialKind=` attribute. Gen-2 MPB also omits all
   scripts for no-auth paks.

5. **ResourceGroup "summary"** must appear on adapter instance and
   world ResourceKinds, even when empty.

## ARIA_OPS stitching patterns

From all references, ARIA_OPS objects in the design JSON have:
- `ariaOpsConf` with multiple `REFERENCE_ID` metrics (VMEntityName,
  VMEntityObjectID, VMEntityVCID, isPingEnabled, etc.)
- Optionally many `REFERENCE_PROPERTY` metrics (existing properties
  exposed for binding)
- `objectBinding` with `objectBindingType: "ATTRIBUTE_TO_PROPERTY"`

The factory currently emits only one `REFERENCE_ID` bind metric.
This works for basic stitching but limits binding flexibility.

## Event wire format (TOOLSET GAP — pak runtime format unknown)

Events defined in YAML (`mpb_events:`) are rendered for the design
import path but **stripped from pak builds** because the pak runtime
expects a different schema than the design JSON format. All factory
paks emit `events: []` in export.json, template.json, and
design.json. This is tracked in `lessons_pak_install_reliability.md`.

Only one reference has events: Rubrik (1 event in design format).
No reference exists for the pak runtime event format. Key structure
of the **design format** (NOT the pak runtime format):
- Wrapped in `{"event": {...}}`
- Has `alert` block (type, badge, subType, waitCycle, cancelCycle)
- Has `severityMap` array mapping raw values to ARIA_OPS severities
- Has `eventMatchers` array for cross-object matching (ARIA_OPS)
- Message uses `@@@MPB_QUOTE <id> @@@MPB_QUOTE` template syntax
- Event metrics referenced by `originId` format:
  `<requestId>-<listId>-<fieldName>`

Full reference: `context/mpb_wire_reference/rubrik_event_wire_format.json`

## Files

| Path | What |
|---|---|
| `tmp/devel_mpb_built.pak` | Gen-2 MPB-built, no-auth, ARIA_OPS stitch |
| `tmp/reference_paks/phpIPAM-1.0.0.11.pak` | Gen-1 MPB, auth, mixed objects |
| `tmp/reference_paks/Ubiquiti_UniFi-1.0.0.7.pak` | Gen-1 MPB, auth, mixed objects |
| `tmp/reference_paks/HPESimplivityVropsMP-1.5.0.2.pak` | SDK-Java |
| `tmp/reference_paks/PureStorageAdapter-3.2.0_signed.pak` | SDK-Java |
| `tmp/reference_paks/phpIPAM-1.0.0.11_MP_Builder_Design.json` | Design export |
| `tmp/reference_paks/Ubiquiti_UniFi-1.0.0.7_MP_Builder_Design.json` | Design export |
| `tmp/reference_paks/vSAN default storage policy.json` | Design export |
| `context/mpb_wire_reference/rubrik_event_wire_format.json` | Event ground truth |
| `context/mpb_wire_reference/rubrik_relationship_wire_format.json` | Relationship ground truth |
| `tmp/pak_compare_report.txt` | Full pak-compare report |
