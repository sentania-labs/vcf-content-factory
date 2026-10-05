# Policy fragment wire format: super metric enablement in a policy

**Question:** what exact wire format does VCF Operations use to record
"super metric X is enabled on resource kind Y" inside a policy, and can a
management pak ship a `content/policies/<name>.xml` fragment that carries
it?

**Date:** 2026-10-01 (America/Chicago). **Instance:** devel
(`vcf-lab-operations-devel.int.sentania.net`, VCF Operations 9.0.2 build
25137xxx paks). **Posture:** read-only. API calls were all GETs; host-side
access (SSH) was used only to read files, logs, and class constant pools.
Nothing on the instance was created, changed, or installed.

## Verdict

**Supported by the platform's own parser, with this shape; not yet proven
end to end through a pak install.**

```xml
<PackageSettings>
    <SuperMetrics adapterKind="VMWARE" resourceKind="vSphere World">
        <SuperMetric enabled="true" id="c72131ad-ee25-4e89-8190-1c93d78eeb5a"/>
    </SuperMetrics>
</PackageSettings>
```

- `id` is the **bare super metric UUID**. There is no `SuperMetric-`
  prefix (unlike `AlertDefinition-<id>` and `SymptomDefinition-<id>`), and
  it is not the `sm_<uuid>` stat key form. `sm_<uuid>` is only how a
  super metric is named inside a symptom's metric trigger.
- One `<SuperMetrics>` block per (adapterKind, resourceKind) pair, sibling
  to `<Alerts>`, `<Symptoms>`, `<Metrics>`, `<BadgeSymptoms>` under the one
  `<PackageSettings>` of a `<Policy>`.

**The operational catch, which matters more than the shape:** a pak policy
fragment **creates or updates its own named policy**. It does not edit the
instance's Default Policy. The Default Policy's UUID is minted per
instance (devel's is `9c1d42be-...`), so a pak cannot portably address it.
The super metric is therefore enabled only on objects that get the pak's
policy: an admin must assign that policy to a group, or make it the
default. This is exactly what the third-party vCommunity Hardware pak tells
its users to do (its README: assign the "Dell EMC Servers" group to the
"vCommunity Hardware Policy" to enable all alerts).

**What would prove it end to end:** build a throwaway pak carrying one
super metric in `content/supermetrics/` plus a policy fragment with the
block above, install it on devel, then `GET /api/policies/export?id=<new
policy id>` and look for the `<SuperMetrics>` block; uninstall afterward.
That is a write experiment and needs the orchestrator's (and Scott's) go
before it runs.

## 1. Reading a policy's enablement settings: what works and what does not

All calls against devel, Default Policy
`9c1d42be-09b7-4149-92fc-2224e3d778bd` ("vSphere Solution's Default Policy
(Apr 17, 2026 3:50:38 PM)", `defaultPolicy: true` in `GET /api/policies`).

| Call | Result |
|---|---|
| `GET /api/policies/{id}` | `500 {"type":"Error","message":"Internal Server error, cause unknown.","httpStatusCode":500,"apiErrorCode":500}` |
| `GET /api/policies/{id}/settings` (no `type`) | `400 {"type":"Error","message":"Query Parameter \"type\" is required.","httpStatusCode":400,"apiErrorCode":1509}` |
| `GET /api/policies/{id}/settings?type=METRICS` | `400` "Invalid input format." with `"failureMessage":"Cannot convert [METRICS] to the expected type.","violationPath":"type"` |
| `GET /api/policies/{id}/settings?type=WORKLOAD&adapterKind=VMWARE&resourceKind=ClusterComputeResource` | `200 {"capacitySettings":{"criticalityThresholds":{"timeRemainingSettings":[],"capacityRemainingSettings":[],"workloadSettings":[]}}}` |
| `GET /api/policies/export?id={id}` (`Accept: application/zip`) | **`200`**, ZIP with one entry `exportedPolicies.xml` (325,798 bytes, exported 3:15 PM) |
| `GET /internal/policies/export?id={id}` (`X-Ops-API-use-unsupported: true`) | `200`, same content as the public export (element and attribute sets identical; byte order differs) |
| `GET /internal/policies` (unsupported header) | `200`, `policy-summaries[]` with `defaultPolicy` per entry |

Findings:

- **The 500 on `GET /api/policies/{id}` is not a server fault.** Neither
  spec defines that operation: `/api/policies/{id}` has only `DELETE` in
  `reference/docs/operations-api.json` and in
  `reference/docs/operations-api-9.1.json`. The 500 is how the server
  answers an undefined GET. Earlier recon entries
  (`recon_log.md`, 2026-07-16 and 2026-07-23) treated it as a platform bug.
- **`/settings?type=` cannot read metric, property, or super metric
  enablement.** The `type` enum (both 9.0 and 9.1 public specs) is
  pricing, workload automation, and capacity only: `VC_PRICING_*`,
  `WORKLOAD_AUTOMATION_*`, `CAPACITY_ALLOCATION_MODEL`,
  `CAPACITY_CUSTOM_PROFILE`, `CAPACITY_BUFFER`, `TIME_REMAINING`,
  `CAPACITY_REMAINING`, `WORKLOAD`.
- **Policy export is the read path.** It is the same artifact the UI's
  Policies page Export button downloads, and it is what the factory's
  `enable` path already round-trips
  (`knowledge/context/api-surface/internal_supermetrics_assign.md`).
  `/internal/policies/export` is a duplicate of the public one.
  > **Warning:** `/internal/*` endpoints need the
  > `X-Ops-API-use-unsupported: true` header and Broadcom may change them
  > without notice. Use the public `/api/policies/export`.

### Export shape, verbatim (devel Default Policy)

Top level is `<PolicyContent>` with three children in this order:
`<Policies>`, `<alertContent>`, `<superMetrics>`. The one `<Policy>` has
only a `<PackageSettings>` (no `PolicySettings`, no `parentPolicy`
attribute). Its `PackageSettings` held 8 `<Alerts>`, 6 `<SuperMetrics>`,
2 `<Metrics>` blocks (73 `Alert`, 66 `SuperMetric`, 7 `Metric` entries).
Every `SuperMetric` entry carries exactly two attributes, `enabled` and
`id`; none were `enabled="false"` (the 22 disabled entries are all
`Alert`).

```xml
<?xml version="1.0" encoding="UTF-8"?><PolicyContent>
    <Policies>
        <Policy key="9c1d42be-09b7-4149-92fc-2224e3d778bd" name="vSphere Solution's Default Policy (Apr 17, 2026 3:50:38 PM)">
            <PackageSettings>
                <Metrics adapterKind="VMWARE" resourceKind="VirtualMachine">
                    <Metric enabled="true" id="diskspace|snapshot|creator"/>
...
                <SuperMetrics adapterKind="VMWARE" resourceKind="vSphere World">
                    <SuperMetric enabled="true" id="c72131ad-ee25-4e89-8190-1c93d78eeb5a"/>
                    <SuperMetric enabled="true" id="8200eed9-6aa3-480d-bd7e-2b1fa81b8ee5"/>
                    <SuperMetric enabled="true" id="dda97f70-65e0-4c5a-b6f0-7acec936a0bd"/>
                    <SuperMetric enabled="true" id="77dca431-01ec-4a7c-824e-275908b89472"/>
                    <SuperMetric enabled="true" id="a3292c87-15b7-4fcd-beea-1b4510b3ca02"/>
                    <SuperMetric enabled="true" id="faab0b29-40b7-4141-8132-7602b4a93338"/>
                    <SuperMetric enabled="true" id="349307c4-2af7-4d83-90d2-1ad4f60138bf"/>
                </SuperMetrics>
```

`c72131ad-...` is `[VCF Content Factory] Compliance Objects Scored`;
`a3292c87-...` is `[VCF Content Factory] Compliance Average Score`. The
same super metric appears once per kind it is enabled on, for example
`020cf289-...` (`[VCF Content Factory] vCLS vCPU (count)`) shows up under
`ClusterComputeResource`, `Datacenter`, and `VMwareAdapter Instance`.

The trailing `<superMetrics>` section carries the full definition of every
super metric the policy references (lowercase element names, note the
case difference from `<SuperMetrics>`):

```xml
    <superMetrics>
        <superMetric description="..." modificationTime="1790182158521" modifiedBy="29c1613f-..." name="[VCF Content Factory] vCLS vCPU (count)" unitId="" uuid="020cf289-b254-4d8c-9e36-f0925c36e3d8">
            <formula>sum(${adaptertype=VMWARE, objecttype=VirtualMachine, metric=config|hardware|num_Cpu, depth=10, where="summary|parentFolder equals vCLS"})</formula>
            <resourceKinds>
                <resourceKinds adapterKindKey="VMWARE" resourceKindKey="ClusterComputeResource"/>
                <resourceKinds adapterKindKey="VMWARE" resourceKindKey="VMwareAdapter Instance"/>
                <resourceKinds adapterKindKey="VMWARE" resourceKindKey="Datacenter"/>
            </resourceKinds>
        </superMetric>
```

The same shape appears in the 2017-era public sample
`reference/references/AriaOperationsContent/vropstopdashboard/SampleDefaultPolicy.xml`
(lines 259-261 and 4035-4042), so it has been stable across versions.

## 2. Pak policy fragments: two dialects, one importer

### The two dialects in the wild

| | vCommunity Hardware pak (third party) | Broadcom Compliance Pack for PCI 9.0.2 |
|---|---|---|
| File | `reference/references/vmbro_vcf_operations_hardware_vcommunity/Management Pack/content/policies/vCommunity Hardware Policy.xml` | `content/policies/pci.xml`, extract at `reference/docs/extracted/policy-fragment/compliance-pack-pci-9.0.2-ootbpolicies.xml` |
| Wrapper | `<PolicyContent><Policies>` | `<PolicyContent><OOTBPolicies vendorNameKey="14075">` |
| Policy | `<Policy description key="<uuid>" name="vCommunity Hardware Policy">` | `<Policy key="<uuid>" nameKey="14074">` (name localized via `content/resources/resources.properties`: `14074=PCI 3.2.1 / PCI 4.0`) |
| PackageSettings children | `<Alerts>`, `<Symptoms>` | `<Alerts>` only |
| Other sections | `<alertContent>` (full alert and symptom definitions) | `<alertContent adapterSource="VMWARE" ...>` |
| Super metrics | none | none |

The vCommunity file is simply a UI/API policy export dropped into the pak.
Of the six Broadcom compliance paks on the appliance
(`/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/`, CIS, DISA, FISMA,
HIPAA, ISO, PCI), every one ships exactly one `content/policies/*.xml` and
none contains a `<SuperMetric` element. No other pak on the appliance
ships `content/policies/`. **There is no vendor sample of a super metric
entry in a pak policy fragment.** Prod's policy list carries `PCI 3.2.1 /
PCI 4.0` (`recon_log.md`, 2026-07-23), which is that pak's `nameKey`
14074, so a pak policy fragment demonstrably becomes a real named policy.

### Schema: the XSD is narrower than the parser

No standalone `PolicyContent` schema exists on the appliance (only XSDs
found: `VcopsContent.xsd`, the suite-api REST schemas, per-adapter
`describeSchema.xsd`, and a few persistence schemas). The closest is the
describe.xml `OOTBPolicies` schema, `describeSchema.xsd` version 6.3.0
(extract: `reference/docs/extracted/policy-fragment/describeSchema-6.3.0-PackageSettingsType-MetricsType.xsd`).
Its `PackageSettingsType` is a choice of only `BadgeSymptoms`, `Symptoms`,
`Alerts`, `Metrics`. **The XSD does not list `SuperMetrics`.** `Metric`
takes `id`, `enabled`, optional `kpiEnabled`.

The runtime parser accepts more than that. From the constant pools and
bytecode of the 9.0.2 classes on devel (read with `javap`, nothing
decompiled into the repo):

- `com.integrien.alive.common.adapter3.describe.PolicyPackageDescribe`
  (`/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar`) initializes
  `rootElementNames` to six names: `Alerts`, `Symptoms`, `BadgeSymptoms`,
  `Metrics`, **`SuperMetrics`**, `CustomProfiles`, each mapped to a child
  name (`Alert`, `Symptom`, `BadgeSymptom`, `Metric`, **`SuperMetric`**,
  `CustomProfile`). Anything else logs `Unknown policy package element
  name`.
- Its `createPolicyPackageEntryDescribe("SuperMetric")` builds a
  `PolicyMetricDescribe`, the same class as `Metric`. Entry attributes
  read by `PolicyPackageEntryDescribe` are `id` and `enabled`.

### The pak install path reaches that parser

The chain, each step read from the class on devel:

1. `com.vmware.vcops.bridge.plugin.server.SolutionManagerDistributedTask`
   (`/usr/lib/vmware-vcops/controller/plugins/vcops-view-server-1.0-SNAPSHOT.jar`)
   knows the pak subfolders, including `content/policies`. Its
   `installContent` runs, in order: localization, reports, dashboards,
   alertdefs, symptomdefs, LI query configs, recommendations,
   **supermetrics, then policies**, then customgroups, geo regions,
   traversal specs, widgets, solutionconfig, scorecards. Super metrics
   therefore land before the policy that references them.
2. `installPoliciesContent` reads each file in `content/policies/` into a
   string and calls `DataRetrieverInterface.importPolicyDefinition(String
   content, boolean force, String pakId)`. Log line on entry:
   `installContent: policy import started...`. On failure:
   `importPolicyDefinition failed. Error: %s`.
3. `com.vmware.vcops.controller.retriever.PolicyService.importPolicy(String,
   boolean, String)` (`vcops-collector-controller-1.0-SNAPSHOT.jar`)
   walks the root's children case-insensitively for `Policies`,
   `OOTBPolicies`, `AlertContent`, `superMetrics`, `customProfileContent`.
   Neither policy wrapper: `No policy to be imported`. `OOTBPolicies` reads
   `vendorNameKey`. It imports `superMetrics` definitions
   (`importSuperMetric`) and `alertContent` before the policies themselves.
4. `PolicyImportExportHandler.loadPolicy` loads each `<Policy>` through
   `OotbPolicyDescribe.load`, which hands `PackageSettings` to
   `PolicyPackageDescribe` above. It sets the policy id from `key`
   (`UUID.fromString`), `ootbKey`, `nameKey`, `description`,
   `parentPolicy`, and **`pakId`**. Entries whose resource kind does not
   exist on the instance are dropped (`filterOutNotExistingResourceKindKey`).
5. An existing policy with the same key is skipped or updated depending on
   `force` (`OOTB policy with key:... already exist, skip it` versus
   `OOTB policy '%s' already exist, update content`).

`PolicyService` has two public entry points, `importPolicyDefinition(String,
boolean, String)` (the pak path above) and `importPolicy(String, boolean)`,
and both delegate to the same private `importPolicy(String, boolean,
String)`. That the REST `POST /api/policies/import` calls the two-argument
one is inferred, not traced. It is consistent with the factory's working
super metric enable path, which round-trips `<SuperMetrics>` blocks through
that endpoint (`install_and_enable.md`). The export dialect and the pak
fragment therefore go through one parser.

### What a pak fragment for super metrics would look like

Either dialect parses. The export dialect is the easy one to author
because it is what `GET /api/policies/export` emits:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<PolicyContent>
    <Policies>
        <Policy key="<stable-uuid-for-this-pak-policy>" name="<display name>" description="...">
            <PackageSettings>
                <SuperMetrics adapterKind="VMWARE" resourceKind="vSphere World">
                    <SuperMetric enabled="true" id="<super-metric-uuid>"/>
                </SuperMetrics>
            </PackageSettings>
        </Policy>
    </Policies>
</PolicyContent>
```

This is assembled from verified parts (export shape plus parser element
names); it has not been installed. The super metric UUID must be the one
the pak's `content/supermetrics/` file carries, which RULE-007 already
keeps stable.

## 3. Open edges (unverified)

- **End-to-end pak install** with a `<SuperMetrics>` block (see Verdict).
- **Group-to-policy binding from the pak.** `installCustomGroupsContent`
  is called with the `ootbKeyCreatedPolicyIdMap` returned by the policy
  import, which suggests a pak custom group can bind to a pak policy by
  its key. The public `custom-group` schema has a `policy` field. No
  vendor pak on devel uses it, so the JSON field name and value form in
  `content/customgroups/*.json` are unknown.
- **Uninstall.** The pak id is stamped on the policy and the task has a
  `removeObsoleteContent` path; whether uninstall deletes the pak's
  policy was not checked.

## Evidence sources

- Live: `GET /api/policies`, `/api/policies/export`,
  `/internal/policies/export`, `/internal/policies`,
  `/api/policies/{id}/settings` on devel, 2026-10-01 around 3:15 PM.
- Specs: `reference/docs/operations-api.json`,
  `reference/docs/operations-api-9.1.json`,
  `reference/docs/internal-api.json`, `reference/docs/internal-api-9.1.json`.
- Vendor extracts: `reference/docs/extracted/policy-fragment/` (README
  carries provenance).
- Samples: the vCommunity Hardware policy file and `SampleDefaultPolicy.xml`
  cited above.
- Class-level reading (devel 9.0.2, local-only, not reproducible from a
  clone; findings summarized here in full per RULE-015):
  `PolicyPackageDescribe`, `PolicyPackageEntryDescribe`,
  `OotbPolicyDescribe` (vrops-adapters-sdk.jar), `PolicyService`,
  `PolicyImportExportHandler` (vcops-collector-controller jar),
  `SolutionManagerDistributedTask` (vcops-view-server jar).
