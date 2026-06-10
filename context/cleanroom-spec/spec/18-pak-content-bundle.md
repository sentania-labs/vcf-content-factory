# 18 — Pak Content Bundle: Dashboards, Alerts, Views, and Declarative Content

**Status**: Pass 27 (2026-05-27).
**Scope**: the declarative content that management packs ship alongside
their adapter implementation — dashboards, alert definitions, views,
supermetrics, custom groups, traversal specs, scorecards, and
configuration files — and the two mechanisms by which that content gets
installed into the Operations platform.

**Evidence base**: all 39 Track C (Java SDK) paks, all 12 Track B
(Integration SDK) paks, and 1 Track A reference (MPBAdapter) from the
2026-05-15 corpus. Structural survey only — no decompiled code.

**Cross-references**:
- Install pipeline mechanics → [§16](16-platform-install-and-signing.md)
- Alert/Symptom/Recommendation schema → [§08](08-alerts-symptoms-recommendations.md)
- UI/operational surfaces in describe.xml → [§14](14-ui-and-operational-surfaces.md)
- Resource model (what dashboards display) → [§05](05-resource-model.md)

---

## TL;DR for VCF-CF

1. **The outer pak's `content/` directory is the declarative content
   manifest.** The platform's pak installer auto-processes well-known
   subdirectory names and imports their contents. This is the modern
   path — Broadcom's own devel-bundle paks (all 18) use it exclusively.

2. **Older and third-party paks duplicate that work imperatively** via
   `post-install.py` / `postAdapters.py` hook scripts that call
   `ops-cli.py` to import content. This is the legacy path. Both paths
   co-exist — the hook scripts are additive, not a replacement.

3. **VCF-CF generated paks should use the declarative `content/`
   directory exclusively** — no install hooks needed. The declarative
   path is simpler, requires no script maintenance, and works across
   all VCF Operations versions that support JSON manifests (8.10+).

4. **Content is independent of adapter track.** Track A, B, and C paks
   all use the same content file formats and the same `content/`
   directory structure. Content installation is a pak-level concern,
   not an adapter-level concern.

5. **Eleven content types are observed** across the corpus. Most paks
   ship 2–4 types. Only 2 of 39 Track C paks ship zero content.

---

## The `content/` directory — canonical structure

The next-gen VCF HCX pak (`vmware-vcfhcxadapter-9.1.0.0-25345970.pak`)
reveals the full template skeleton via `.gitkeep` placeholders. This is
the platform's expected directory tree:

```
content/
├── alertdefs/                    # XML alert + symptom + recommendation defs
├── customgroups/                 # JSON custom group + group type defs
├── dashboards/                   # JSON dashboard defs (one subdir per dashboard)
│   └── <DashboardName>/
│       ├── dashboard.json        # (or <DashboardName>.json)
│       └── resources/
│           ├── resources.properties        # en
│           ├── resources_es.properties     # i18n
│           ├── resources_fr.properties
│           ├── resources_ja.properties
│           └── ...
├── files/
│   ├── reskndmetric/             # XML resource-kind default metric display configs
│   ├── solutionconfig/           # adapter-specific config (limits, rules, signatures)
│   ├── topowidget/               # XML topology widget configs
│   └── txtwidget/                # text widget content files
├── policies/                     # policy definitions (empty in corpus)
├── recommendations/              # recommendation definitions (empty in corpus)
├── reports/                      # XML view definitions (despite the directory name)
│   └── <ViewSetName>/
│       ├── content.xml           # (or <ViewSetName>.xml)
│       └── resources/
│           ├── content.properties
│           └── content_<locale>.properties
├── resources/                    # i18n string bundles for the adapter
│   ├── resources.properties
│   └── resources_<locale>.properties
├── scorecards/                   # JSON compliance scorecard definitions
├── supermetrics/                 # JSON supermetric definitions (one per file)
├── symptomdefs/                  # XML symptom definitions (when separate from alertdefs)
└── traversalspecs/               # XML traversal spec definitions
```

**Note on `content/reports/`**: despite the directory name, every file
observed across all 51 paks is a **View definition** (`<Content><Views>
<ViewDef>...</ViewDef></Views></Content>` XML), not a report definition.
Views are reusable data presentations consumed by both dashboards and
reports. The platform processes them the same way regardless of the
misleading directory name.

---

## Content types — format and purpose

### 1. Alert definitions (`content/alertdefs/`)

XML files bundling three related concepts in a single `<alertContent>`
root:

```xml
<alertContent>
    <AlertDefinitions>
        <AlertDefinition adapterKind="VMWARE" id="..." name="..."
                         resourceKind="VMwareAdapter Instance"
                         subType="22" type="16" nameKey="2401">
            <State severity="automatic">
                <SymptomSet applyOn="self">
                    <Symptom ref="SymptomDefinition-..."/>
                </SymptomSet>
                <Impact key="health" type="badge"/>
                <Recommendations>
                    <Recommendation priority="1" ref="..."/>
                </Recommendations>
            </State>
        </AlertDefinition>
    </AlertDefinitions>
    <SymptomDefinitions>
        <SymptomDefinition adapterKind="VMWARE" id="..." name="..."
                           resourceKind="VMwareAdapter Instance">
            <State severity="info">
                <Condition type="msg_event" eventType="11"
                           eventSubType="5" operator="regex"
                           eventMsg="..."/>
            </State>
        </SymptomDefinition>
    </SymptomDefinitions>
    <Recommendations>
        <Recommendation key="...">
            <Description nameKey="2403"/>
        </Recommendation>
    </Recommendations>
</alertContent>
```

**Corpus stats**: 22 of 39 Track C paks include alertdefs. NSXTAdapter
is the largest (662KB, 571 symptoms, 562 alerts, 1688 recommendations).
Two paks ship zero-content (MPBAdapter, VCFLogAssist).

**VCF-CF implication**: full schema documented in
[§08](08-alerts-symptoms-recommendations.md). Alert content is the
second most common content type after dashboards.

### 2. Dashboards (`content/dashboards/`)

JSON files defining dashboard layouts with widget definitions. Each
dashboard lives in its own subdirectory with an optional `resources/`
subdirectory for i18n strings.

**Naming conventions observed**:
- `dashboard.json` (most common — Broadcom convention)
- `<DashboardName>.json` (also valid — marketplace paks)

**Scale**: VMwarevSphere ships a single 2.7MB dashboard JSON.
NetworkingDevices ships 21 separate dashboards. NSXTAdapter ships 14.

**Cross-pak split**: vSphere dashboards and alerts are split across two
paks — `VMwarevSphere` ships dashboards/reports/views under
`adapter_kinds: ["VMWARE"]`, while `vim` ships alertdefs under
`adapter_kinds: ["VMWARE_INFRA_MANAGEMENT"]`. This is the only observed
case of cross-pak content factoring in the corpus.

**VCF-CF implication**: dashboard JSON is a complex, widget-oriented
format. VCF-CF should treat dashboard generation as a separate concern
from adapter generation — either ship starter dashboards or provide a
dashboard template that users customize in the Operations UI.

### 3. Views / Reports (`content/reports/`)

XML documents containing `<ViewDef>` elements that define reusable data
presentations:

```xml
<Content>
    <Views>
        <ViewDef id="934e9e5f-...">
            <Title>vSphere Namespace</Title>
            <SubjectType adapterKind="VMWARE" resourceKind="NamespaceV2"
                         type="descendant"/>
            <Usage>dashboard</Usage>
            <Usage>report</Usage>
            <Usage>details</Usage>
            <Controls>
                <Control id="..." type="time-interval-selector" visible="false">
                    <Property name="unit" value="DAYS"/>
                    <Property name="count" value="7"/>
                </Control>
                <Control id="..." type="attributes-selector" visible="false">
                    ...
                </Control>
            </Controls>
        </ViewDef>
    </Views>
</Content>
```

Views have a `<SubjectType>` binding to an `adapterKind:resourceKind`
pair and declare which contexts they're valid in (`dashboard`, `report`,
`details`, `content`). They carry their own i18n in `content.properties`
files.

**VCF-CF implication**: generated adapters should include at least a
basic inventory view per ResourceKind. The XML format is
straightforward and templatable.

### 4. Custom groups (`content/customgroups/`)

JSON files defining dynamic resource groupings with membership rules:

```json
{
    "customGroups": [
        {
            "resourceKind": "Environment",
            "adapterKind": "Container",
            "name": "VCF Management World",
            "autoResolveMembership": true,
            "membershipDefinition": {
                "ruleGroups": [{
                    "resourceKind": "VCFDomain",
                    "adapterKind": "VcfAdapter",
                    "rules": [{
                        "ruleType": "StringMetricPropertyRule",
                        "ruleMetricKey": "configuration|DomainType",
                        "isProperty": true,
                        "ruleStringOperator": "EQUALS",
                        "ruleStringValue": "MANAGEMENT"
                    }]
                }]
            }
        }
    ],
    "customGroupTypes": [
        {
            "resourceKind": "Environment",
            "localization": [{"resourceKindName": "Umgebung", "locale": "de"}, ...]
        }
    ]
}
```

**Corpus stats**: 6 of 39 Track C paks include custom groups
(AppOSUCP, vSAN, VMwarevSphere, vcf, AWS, vRO).

### 5. Traversal specs (`content/traversalspecs/`)

XML files defining navigation paths through the resource hierarchy.
These power the "Environment" tree views in the Operations UI:

```xml
<AdapterKind key="SupervisorAdapter">
    <TraversalSpecKinds>
        <TraversalSpecKind name="K8s-Infrastructure"
                           rootAdapterKind="SupervisorAdapter"
                           rootResourceKind="SupervisorWorld"
                           filterType="GENERIC_RELATION">
            <ResourcePath path="SupervisorAdapter::SupervisorWorld||
                SupervisorAdapter::SupervisorCluster::child||
                SupervisorAdapter::KubernetesNode::child||
                SupervisorAdapter::KubernetesPod::child||
                SupervisorAdapter::KubernetesContainer::child"/>
        </TraversalSpecKind>
    </TraversalSpecKinds>
</AdapterKind>
```

The `path` attribute uses `||`-delimited hops, each in the format
`<AdapterKind>::<ResourceKind>::<relationship>`. This declares how the
UI should walk the resource tree from a root kind down to leaves.

**Corpus stats**: 7 of 39 Track C paks include traversal specs (vSAN,
NSXT, SupervisorAdapter, vcf, Kubernetes, vRO, plus vSphere's are
declared in describe.xml directly). These are the paks with complex
multi-level resource hierarchies.

**VCF-CF implication**: any generated adapter with a non-trivial
resource hierarchy (more than 2 levels) should include a traversal
spec to enable proper tree navigation in the UI.

### 6. Supermetrics (`content/supermetrics/`)

JSON files defining computed metrics that aggregate across resources:

```json
{"097c1c3b-...": {
    "resourceKinds": [{
        "resourceKindKey": "NSXAdvancedLBAdapterInstance",
        "adapterKindKey": "NSXAdvancedLBAdapter"
    }],
    "name": "Service Engines Count",
    "formula": "count(${adapterkind=NSXAdvancedLBAdapter,
                  objecttype=ServiceEngine,
                  attribute=badge|health, depth=6})",
    "unitId": "none"
}}
```

**Corpus stats**: only 1 of 39 Track C paks ships supermetrics in the
outer pak (NSX Advanced LB — 13 supermetrics). Others import
supermetrics via hook scripts or define them post-install via the UI.

### 7. Scorecards (`content/scorecards/`)

JSON files defining compliance scorecards:

```json
{
    "scorecards": [{
        "type": "STANDARD",
        "pakId": "NSXTAdapter",
        "adapterKind": "NSXTAdapter",
        "name": "NSX Security Configuration Guide",
        "version": "2.0"
    }]
}
```

**Corpus stats**: 2 of 39 Track C paks (NSXTAdapter, vSAN).

### 8. Resource-kind metrics (`content/files/reskndmetric/`)

XML files configuring dashboard widget metric display — labels, units,
and threshold colors for specific metrics on specific resource kinds:

```xml
<AdapterKinds>
    <AdapterKind adapterKindKey="VirtualAndPhysicalSANAdapter">
        <ResourceKind resourceKindKey="VirtualSANDCCluster">
            <Metric attrkey="summary|total_number_hosts"
                    label="vSAN Hosts" unit=""
                    yellow="" orange="" red="" showState="false"/>
        </ResourceKind>
    </AdapterKind>
</AdapterKinds>
```

**Corpus stats**: 14 of 39 Track C paks. VMwarevSphere has the most
(25 files). These files control "summary page" widget rendering.

### 9. Solution config (`content/files/solutionconfig/`)

Adapter-specific configuration consumed at runtime. Format varies by
adapter — XML config limits, JSON health rules, JSON log signatures:

```xml
<!-- vcf: configuration limits -->
<AdapterKinds>
    <AdapterKind adapterKindKey="VcfAdapter">
        <ConfigLimit>
            <Name>Max workload domains per VCF Instance</Name>
            <Type>Hard</Type>
            <Value>24</Value>
        </ConfigLimit>
    </AdapterKind>
</AdapterKinds>
```

**Corpus stats**: 4 of 39 Track C paks (vcf, PingAdapter,
VCFDiagnostics × 4 files, VMwarevSphere via hook import).

### 10. Log Insight query configs (`content/liqueryconfigs/`)

XML files defining saved queries for VMware Log Insight / Aria
Operations for Logs integration:

```xml
<alertContent>
    <LIQueryConfigs>
        <liQueryConfig id="..." name="vcfa-overall-errors">
            <dateRange range="last5Mins"/>
            <queryFilter operator="and">
                <filterCondition field="product" operator="contains">
                    <filterValue val="prelude"/>
                </filterCondition>
            </queryFilter>
        </liQueryConfig>
    </LIQueryConfigs>
</alertContent>
```

**Corpus stats**: 3 of 39 Track C paks (CASAdapter, vSAN,
VMwarevSphere).

### 11. Text and topology widgets (`content/files/txtwidget/`, `content/files/topowidget/`)

Content files for specialized dashboard widgets. Txtwidgets are HTML/
text content blocks; topowidgets are topology graph configurations.

**Corpus stats**: only AWS ships txtwidgets (3 files) in the outer pak.
Topowidgets are imported via hook scripts (ServiceNow) rather than the
`content/` directory.

### 12. i18n resource bundles (`content/resources/`)

Java `.properties` files providing localized strings for metric names,
resource kind names, and other UI labels. These are the adapter-wide
string bundles (as opposed to per-dashboard or per-view i18n).

**Locale coverage observed**: en (always), es, fr, ja (common), de, ko,
zh_CN, zh_TW (some paks), it (VrAdapter only).

---

## Content installation — two mechanisms

### Mechanism 1: Declarative auto-import (modern path)

The pak installer automatically processes the `content/` directory tree.
When it finds files in well-known subdirectories, it imports them into
the Operations platform without any hook script intervention.

**Evidence**: all 18 Broadcom devel-bundle Track C paks and all 12
Track B paks have empty hook script fields in `manifest.txt` yet ship
rich content that is successfully installed. The next-gen VCF adapters
(VCF Avi, VCF HCX, Diagnostics — `vcops_minimum_version: "9.0+"`)
have no hooks at all.

**manifest.txt fields** (all empty on the modern path):

```json
{
    "pak_validation_script": {"script": ""},
    "adapter_pre_script": {"script": ""},
    "adapter_post_script": {"script": ""}
}
```

### Mechanism 2: Imperative `ops-cli` import (legacy path)

Hook scripts in the outer pak root call `ops-cli.py` (or `ops-cli.sh`)
to explicitly import content. The scripts are invoked by the install
pipeline per the phase documented in [§16](16-platform-install-and-signing.md).

**manifest.txt fields** (legacy path):

```json
{
    "pak_validation_script": {"script": "python validate.py"},
    "adapter_pre_script": {"script": "python preAdapters.py"},
    "adapter_post_script": {"script": "python post-install.py"}
}
```

**Script naming conventions** (not enforced by platform — these are
author conventions):

| Script name | Phase | Purpose |
|---|---|---|
| `validate.py` | Validation | Checks `$VCOPS_BASE` is set; exits non-zero to abort |
| `preAdapters.py` | Pre-install | Usually a no-op (`print("In Pre")`) |
| `post-install.py` | Post-install | Content import via `ops-cli` |
| `postAdapters.py` | Post-install | Same purpose, different naming convention |
| `postAdapter.py` | Post-install | VMware-first-party singular variant |
| `solutionPreScript.py` | Pre-install | vSphere-specific property backup |
| `solutionPostScript.py` | Post-install | vSphere-specific restore + Actions plugin setup |

### The `ops-cli` command vocabulary

The ServiceNow `post-install.py` (the most complete hook in the corpus)
reveals the full import vocabulary. Import order matters — redescribe
must precede dashboard import:

```
ops-cli.py file import topowidget <file> --force
ops-cli.py control redescribe --force
ops-cli.py file import txtwidget <file>
ops-cli.py file import reskndmetric <file> --force
ops-cli.py view import <file> --force
ops-cli.py report import <file> --force
ops-cli.py supermetric import <file> --packages <pkg> --check true
ops-cli.py reskind configure <kind> --smpackage <pkg>
ops-cli.py objtype configure <kind> --smpackage <pkg>
ops-cli.py dashboard import admin <file> --share all --force
ops-cli.py template import <file> --resknd-keys <keys> [--force]
ops-cli.py dashboard delete admin <name>
```

### Which paks use which mechanism

| Group | Count | Mechanism | Content types |
|---|---|---|---|
| Broadcom devel (Track C) | 17 of 18 | Declarative only | Full range |
| Broadcom devel — VMwarevSphere | 1 | Declarative + hooks | Dashboards + property backup/restore + Actions plugin |
| Marketplace — EPOps family | 7 | Declarative + hooks | Dashboards, views, reskndmetric, supermetrics |
| Marketplace — VMware first-party | 7 | Declarative + hooks | Dashboards, summary templates |
| Marketplace — Dell/OME | 2 | Hooks only (Dell) or hooks + content/ | Dashboards |
| Marketplace — next-gen VCF | 3 | Declarative only | Alerts only (minimal) |
| Track B (Integration SDK) | 12 | Declarative only | Full range |

---

## Content richness by pak — corpus-wide summary

### Devel bundle (18 paks)

| Pak | Alerts | Dash | Views | CGroups | TravSpec | Scores | LIQuery | RKMetric | SolCfg | Hooks |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| NSXTAdapter | 571a | 14 | 1 | - | Y | Y | - | - | - | - |
| vSAN (SAN MP) | 163a | 2 | 1 | 2 | Y | Y | Y | 10 | - | - |
| AppOSUCPAdapter | 116a | 2 | 2 | 1 | - | - | - | - | - | - |
| NetworkInsightAdapter | 325a | 1 | 1 | - | - | - | - | - | - | - |
| VMwareInfraHealth | 34a | 1 | 3 | - | - | - | - | - | - | - |
| VMwarevSphere | - | 1 (2.7MB) | 11 | 1 | - | - | Y | 25 | - | 2 |
| vim | 16a | - | - | - | - | - | - | - | - | - |
| vcf | 6a | 1 | 1 | 2 | Y | - | - | - | Y | - |
| CASAdapter | - | 1 | 1 | - | - | - | Y | - | - | - |
| SupervisorAdapter | 2a | 1 | 1 | - | Y | - | - | - | - | - |
| VCFAutomation | - | 2 | 2 | - | - | - | - | - | - | - |
| VCFDiagnostics | 2a | - | - | - | - | - | - | - | 4 | - |
| PingAdapter | 2a | 1 | 1 | - | - | - | - | - | Y | - |
| ServiceDiscovery | - | 1 | 3 | - | - | - | - | 1 | - | - |
| ConfigMgmt | 2a | - | - | - | - | - | - | - | - | - |
| VrAdapter | - | 1 | 2 | - | - | - | - | 2 | - | - |
| MPBAdapter | - | - | - | - | - | - | - | - | - | - |
| VCFLogAssist | - | - | - | - | - | - | - | - | - | - |

### Marketplace bundle (21 paks)

| Pak | Alerts | Dash | Views | CGroups | TravSpec | SMet | RKMetric | Hooks |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| networkingdevices | - | 21 | 8 | - | - | - | 2 | Y |
| AWS | 1 | 10 | 1 | 1 | - | - | 4 | Y |
| mongodb | - | 9 | 10 | - | - | - | 15 | Y |
| Kubernetes | 1 | 6 | 3 | - | Y | - | 4 | Y |
| Aggregator | - | 7 | 1 | - | - | - | 2 | Y |
| MSSQL | - | 4 | 10 | - | - | - | 41 | Y |
| OME | - | 4 | 12 | - | - | - | 2 | Y |
| vLCR | - | 4 | 1 | - | - | - | - | Y |
| mysql | - | 2 | 13 | - | - | - | 2 | Y |
| Oracle | - | 2 | 1 | - | - | - | 2 | Y |
| postgresql | - | 2 | 5 | - | - | - | 7 | Y |
| NSX ALB | 1 | 1 | 1 | - | - | 13 | - | Y |
| SRM | - | 1 | 1 | - | - | - | 1 | Y |
| vRO | 1 | 1 | - | 1 | Y | - | 2 | Y |
| HCX | - | 1 | 6 | - | - | - | - | Y |
| ServiceNow | - | 1 | 3 | - | - | - | - | Y |
| VCDA | 1 | 1 | 1 | - | - | - | - | Y |
| Dell | - | (*) | - | - | - | - | - | Y |
| Diagnostics | 1 | - | - | - | - | - | - | - |
| VCF Avi | 1 | - | - | - | - | - | - | - |
| VCF HCX | 1 | - | - | - | - | - | - | - |

(*) Dell dashboards are inside the inner archive, imported by hook.

---

## VCF-CF design recommendations

### 1. Use the declarative `content/` path exclusively

VCF-CF generated paks should never require install hooks. Place all
content in the `content/` directory tree using the canonical structure
documented above. The platform auto-imports everything.

### 2. Minimum viable content set for a generated adapter

Based on corpus frequency, the typical Track C pak ships:

- **Alert definitions** (22/39 paks = 56%) — at minimum, connectivity/
  health alerts for the adapter instance itself
- **Dashboards** (33/39 = 85%) — at minimum, one overview dashboard
- **Views** (31/39 = 79%) — at minimum, one inventory view per top-
  level resource kind
- **i18n resources** (33/39 = 85%) — at minimum, English string bundle

### 3. Content type selection guidance

| Content type | When to include | Templatable? |
|---|---|---|
| alertdefs | Always — even stub adapters benefit from connectivity alerts | Yes — parameterize `adapterKind` and `resourceKind` |
| dashboards | Always — primary user-facing surface | Partially — layout is adapter-specific but widget types are standard |
| views/reports | Always for adapters with >1 resource kind | Yes — one per ResourceKind is mechanical |
| custom groups | When the adapter defines logical groupings (worlds, environments) | Yes — membership rules reference adapter's own kinds |
| traversal specs | When resource hierarchy has >2 levels | Yes — derived directly from ResourceKind parent/child |
| reskndmetric | When dashboards include metric widgets | Partially — maps metrics to display labels |
| scorecards | When compliance/security posture matters | No — domain-specific |
| supermetrics | Rarely needed in pak — usually defined post-install | Partially |
| LI query configs | Only when Log Insight integration exists | No — requires log schema knowledge |
| solution config | Only for adapter-specific runtime config | No — adapter-specific |

### 4. Traversal spec generation is mechanical

Traversal specs can be derived directly from the ResourceKind hierarchy
in `describe.xml`. The `path` attribute follows a fixed pattern:

```
<AdapterKind>::<RootKind>||<AdapterKind>::<ChildKind>::child||...
```

VCF-CF should auto-generate a traversal spec for any adapter whose
describe.xml declares a resource hierarchy with 3+ levels.

### 5. Dashboard generation is the hardest content problem

Dashboard JSON is a widget-layout format with pixel positioning,
cross-widget interactions, and complex data bindings. Unlike alertdefs,
views, and traversal specs, dashboards are not mechanically derivable
from the resource model.

**Recommended approach**: ship a minimal "starter dashboard" template
with inventory list + health badge widgets, and document how users can
customize it in the Operations UI. Do not attempt to generate complex
dashboards programmatically.

### 6. The `content/reports/` naming is misleading — call them views

In VCF-CF documentation and code, call these "view definitions" not
"reports" to avoid confusion. The directory name is a platform legacy.

---

## Addendum — importer binding requirements (Pass 28, 2026-05-27)

**Provenance**: first negative-case calibration of spec/18. The
VCF-CF-generated `vcfcf_vcfcf_compliance.1.0.0.17.pak` installed
cleanly and registered its describe.xml-side content
(`AlertDefinition`, `SymptomDefinition`, `Recommendation` — counts
1/2/3 as declared), but the platform's post-install content inventory
reported **zero** dashboards, zero views, and zero report templates
despite the outer `content/dashboards/` and `content/reports/`
directories being populated. Diff against `VCFAutomation` and
`AppOSUCPAdapter` dashboard JSON identified the missing fields below.
The pak survey alone could not have caught these — every corpus
sample had them.

### A1. Dashboard JSON: owning-adapter binding is required

The pak survey documented dashboard JSON top-level keys
(`uuid`, `entries`, `dashboards`) but did not enumerate the keys of
`entries` itself or the per-dashboard fields. Both contain binding
metadata that the importer treats as required:

```json
{
    "uuid": "...",
    "entries": {
        "adapterKind": [
            {"internalId": "adapterKind:id:0_::_",
             "adapterKindKey": "<OwningAdapterKey>"}
        ],
        "resourceKind": [ ... ],
        "resource":     [ ... ]
    },
    "dashboards": [
        {
            "id": "...",
            "name": "...",
            "adapterName": "<OwningAdapterKey>",
            "widgets": [ ... ],
            ...
        }
    ]
}
```

Corpus cross-check: confirmed present in `VCFAutomation`,
`AppOSUCPAdapter`. Absence triggers a silent drop — no error surfaces
to the install pipeline; the dashboard simply does not appear in the
post-install inventory.

**VCF-CF generator requirement**: emit `entries.adapterKind` as a
list of one `{internalId, adapterKindKey}` pair, and set
`dashboards[].adapterName` to the owning `adapter_kind` from
manifest.txt.

### A2. View XML: owning-adapter `<SubjectType>` is required

Spec/18 §3 documented `<SubjectType>` as carrying a single
`adapterKind:resourceKind` binding. The corpus actually shows every
ViewDef declaring **two or more** `<SubjectType>` elements:

- one (or more) for the cross-MP target the view *reads from*
- **plus** one for the owning adapter — even when the owning adapter
  is not the data source

VCFAutomation example:

```xml
<ViewDef id="...">
    <SubjectType adapterKind="VMWARE"        resourceKind="VirtualMachine" type="descendant"/>
    <SubjectType adapterKind="VCFAutomation" resourceKind="RegionQuota"    type="descendant"/>
    ...
</ViewDef>
```

The owning-adapter SubjectType registers the view under the adapter's
content namespace; without it, the importer cannot file the view and
drops it (which in turn drops any reports built on top of it).

**VCF-CF generator requirement**: every emitted `<ViewDef>` must
include at least one `<SubjectType>` whose `adapterKind` matches the
pak's owning `adapter_kind`. For pure-stitching adapters (which
declare ResourceKinds only to receive ARIA_OPS property pushes —
e.g. compliance scoring onto `VMWARE/HostSystem`), pair the
cross-MP target SubjectType with one referencing the adapter's own
top-level ResourceKind (the "World" kind, by convention).

### A3. `resources/` subdirectories are de-facto required, not optional

Spec/18 §"The `content/` directory — canonical structure" labels the
per-dashboard and per-view `resources/` subdirectories as optional
based on absence in `.gitkeep` placeholders. The negative case
indicates otherwise: dashboards and views whose display names use
bracket-prefix notation (`[VCF Content Factory] Compliance Fleet
Overview`) appear to be resolved through the i18n bundle, and missing
the bundle correlates with the import failure.

**VCF-CF generator requirement**: always emit a `resources/`
subdirectory alongside each `dashboard.json` and `content.xml`, with
at minimum:

```
content/dashboards/<Name>/resources/resources.properties
content/reports/<Name>/resources/content.properties
```

Even an empty file is safer than no file; populated bundles
(key→display-label pairs) are best. Locale-suffixed siblings
(`resources_es.properties`, etc.) remain optional.

**Spec correction**: amend the "canonical structure" tree above —
the `resources/` subdirectories should be presented as required, not
optional, in the canonical pak-generation contract. (The original
"optional" framing reflected absence in some template scaffolds, not
absence in shipped paks; the corpus has no shipped pak without them.)

### A4. Inner-archive `<AdapterName>/content/` is dead weight

The `vcfcf_compliance` pak duplicated its `content/dashboards/` and
`content/reports/` trees inside the inner archive at
`vcfcf_compliance/content/...`. The platform only auto-imports the
**outer** pak's `content/` (this matches §"Content installation —
two mechanisms"); the inner duplicate is never processed. It is not
harmful at install time, but:

- it doubles the pak's content payload on disk
- it creates two sources-of-truth for the same files (drift risk in
  a generator that updates one but not the other)
- it confuses maintainers reading the pak

**VCF-CF generator requirement**: emit declarative `content/` only at
the outer-pak level. The inner archive should contain only
`<AdapterName>/{conf,lib,...}` and the implementation jar(s) — no
`content/` subtree.

### A5. describe.xml-side vs. content-side are independent import paths

The Pass-28 evidence confirms an architectural point that spec/18 had
implied but not stated outright: **`describe.xml` content
(`AlertDefinition`, `SymptomDefinition`, `Recommendation`) and outer
`content/` content are processed by independent install-pipeline
stages**. A pak can succeed at the describe.xml stage and fail at the
content stage (or vice versa) without either failure aborting the
install. Practical consequences:

- A "successful install" notification does not imply all content
  imported — operators must verify the post-install content
  inventory.
- Two definitions of the same alert/symptom (one in `describe.xml`,
  one in `content/alertdefs/*.xml`) may both survive install. Pick
  one path per definition to avoid duplicate-key conflicts.
- VCF-CF should default to placing alert/symptom/recommendation
  definitions in `describe.xml` (proven to work in Pass 28) rather
  than `content/alertdefs/` until the content-side path is
  separately validated.

### A6. Validation recipe for generated paks

Before shipping a generated pak, the VCF-CF generator (or its test
harness) should validate at least:

1. Every `content/dashboards/<Name>/dashboard.json` parses as JSON
   and contains both `entries.adapterKind[*].adapterKindKey ==
   <owning_kind>` and `dashboards[*].adapterName == <owning_kind>`.
2. Every `content/reports/<Name>/content.xml` parses as XML, every
   `<ViewDef>` contains at least one `<SubjectType
   adapterKind="<owning_kind>" .../>`.
3. Every dashboard and view subdirectory contains a `resources/`
   subdirectory with at least one `.properties` file.
4. The inner archive contains no `content/` subtree.
5. Post-install, the platform's content inventory reports counts
   matching what the pak shipped — zero is the failure signal.

A fixture pak that has been confirmed importable end-to-end (counts
all match) should be promoted to a regression-test artifact for
future generator changes.

---

## Addendum — orchestrator-step gate `overview.packed` (Pass 29, 2026-05-28)

**Provenance**: lab-admin log analysis of the v19 generator output
(`vcfcf_sdk_compliance.1.0.0.19.pak`) against the
vcf-lab-operations-devel appliance. The v19 pak satisfied all four
Pass 28 requirements (A1–A4 verified present pre-install) and the
post-install content inventory still reported zero
dashboards / views / reports. Server-side install logs revealed the
actual gate — one orchestrator step earlier than where the JSON-shape
diff had been looking.

### A0 — `overview.packed` at outer-pak root is the deployment gate

**The platform install pipeline runs 19 sequential orchestrator
steps**, of which step 5
(`com.vmware.vcops.casa.upgrade.pak.DeployNewUpgradeContentOperation`)
is the only step that processes the outer `content/` tree. That
operation's `shouldRun()` predicate checks for the presence of an
`overview.packed` file at the outer-pak root (sibling of
`manifest.txt`). When the file is absent, `shouldRun()` returns
false and the operation logs:

```
operation com.vmware.vcops.casa.upgrade.pak.DeployNewUpgradeContentOperation
says it should not run
```

The pipeline then advances to step 6 (`VALIDATE`) without ever
touching `content/dashboards/`, `content/reports/`,
`content/supermetrics/`, `content/policies/`, `content/customgroups/`,
or any other `content/` subdirectory. The skip is silent —
`pak_install_status` reports `COMPLETED` and the orchestrator marks
the install as `APPLIED_AND_CLEANED`.

**Empirical pattern (calibrated 2026-05-28 against installed paks
on vcf-lab-operations-devel)**:

| Pak | `overview.packed` | content/ entries | DEPLOY_NEW_UPGRADE_CONTENT |
|---|:---:|:---:|---|
| VCFAutomation | present (5,772 B) | 19 | runs |
| AppOSUCPAdapter | present | 40 | runs |
| NSXTAdapter | present | 127 | runs |
| vRealizeCompliancePack (multiple) | present | 10–16 | runs |
| VCFContentFactoryCompliance v19 | absent | 20 | **"should not run"** |
| Other VCF-CF / MPB-generated paks (UniFi, DellPowerEdge, Synology) | absent | 0–4 | **"should not run"** |
| GitLab (MPB) | absent | 5 | **"should not run"** |

Correlation is 1:1 across the surveyed appliance: every pak with
`overview.packed` runs DEPLOY_NEW_UPGRADE_CONTENT; every pak without
it has the operation skip.

**VCF-CF generator requirement**: emit `overview.packed` at the
outer-pak root in every generated pak. The file is a ZIP archive
containing at minimum:

```
overview.packed (ZIP)
  └── light/
      └── overview.html
```

`overview.html` is the HTML overview page rendered in the vROps UI
when a user opens the pak's details. Localized variants
(`<locale>/overview.html`) are optional. The reference
`overview.packed` from `VCFAutomation-902025137921.pak` is 5,772 B —
modest. Content does not appear to be parsed for correctness; the
gate is purely presence-based.

### A0-orch — the install-pipeline orchestrator step list

A side benefit of the Pass 29 log analysis: the platform's install
orchestrator runs a fixed 19-step sequence per pak install. Knowing
the sequence is useful for VCF-CF generator design (which steps
your pak content can influence) and for future install-failure
diagnosis (which step's log line to grep for).

| Step | Operation | Skipped if… |
|---|---|---|
| 1 | VALIDATE_ON_MASTER | always on single-node lab installs |
| 2 | DISTRIBUTE | pak already staged (`node_unchanged=true`) |
| 3 | STAGE | pak already staged |
| 4 | PREAPPLY_VALIDATE | — runs unconditionally |
| **5** | **DEPLOY_NEW_UPGRADE_CONTENT** | **`overview.packed` absent (A0)** |
| 6 | VALIDATE | — runs unconditionally |
| 7 | STAGE_ON_REMOTE_COLLECTOR | no remote collectors configured |
| 8–13 | BRING_CLUSTER_OFFLINE, RENEW_CERTS, OS_UPDATE, SYS_UPDATE, WAIT, BRING_ONLINE | single-node / no cluster ops needed |
| 14 | APPLY_ADAPTER_PRE_SCRIPT | pak ships no pre-script |
| 15 | APPLY_ADAPTER | — runs unconditionally; invokes `suite-api/internal/solution/install` → `DistributedTaskInstallUninstallAdapters` |
| 16 | APPLY_ADAPTER_POST_SCRIPT | pak ships no post-script |
| 17 | RESTART_CLUSTER | single-node |
| 18 | CLEANUP | — runs unconditionally |
| 19 | CLUSTER_WAIT_FOR_CLEANUP | already cleaned |

Critical structural point: **steps 5 and 15 are the only two steps
that deploy pak content, and they process disjoint payload subsets**.
Step 5 owns `content/` (dashboards, views, reports, supermetrics,
policies, custom groups). Step 15 owns describe.xml-side content
(adapter kind schema, resource kinds, symptoms, alert definitions,
recommendations, traversal specs). They share no state and gate
independently — explaining why a pak can register Alert=1
Symptom=2 Recommendation=3 cleanly while shipping zero
dashboards / views / reports.

### A0-logs — appliance log location correction

Spec/18 §A6 referenced `/usr/lib/vmware-vcops/user/log/` as the
canonical log path. That path is a symlink alias; the real log
directory is `/storage/vcops/log/`. The subdirectory layout under
the real path:

```
/storage/vcops/log/
├── casa/
│   ├── casa.log                       — main CASA service log
│   ├── casa.audit.log                 — API audit
│   ├── pakManager.actions.log         — orchestrator step log ← primary
│   └── pakManager.query.log           — status queries
├── pakManager/
│   ├── vcopsPakManager.root.post_apply_adapter.log   ← step 15 detail
│   ├── vcopsPakManager.root.apply_adapter.log
│   ├── vcopsPakManager.root.stage.log
│   └── vcopsPakManager.root.query.log
├── analytics-<uuid>.log               — server-side task execution
├── api.log                            — HTTP access log
└── adapters/<AdapterKindKey>/         — adapter runtime logs
```

**There is no separate "content processing service" log** — the
content-side import that A6 expected to find in a distinct log
runs inside the analytics-engine task `DistributedTaskInstallUninstallAdapters`
when (and only when) DEPLOY_NEW_UPGRADE_CONTENT proceeds.
`pakManager.actions.log` is the source of truth for which
orchestrator steps ran and which were skipped — that is the
first log to grep on any future content-import failure.

### Reframing Pass 28's A1–A4 in light of A0

Pass 28's A1–A4 (dashboard binding, view owning-adapter SubjectType,
`resources/` subdirs, no inner-archive `content/`) were derived by
JSON-shape diff against four working corpus paks. The derivation
was sound — every working pak does have those fields populated —
but the failure mode they explained ("silent drop at content
import") was misdiagnosed. The proximate cause was A0: with
`overview.packed` absent, the importer never ran, so the JSON
shape was never evaluated.

**A1–A4 remain valid** as post-gate requirements: once A0 is
satisfied and the importer runs, the JSON-shape requirements still
apply, and the corpus evidence backing them is unchanged. Treat
the sequence as A0 → A1–A4: A0 is necessary for the import to
attempt at all; A1–A4 are necessary for individual content items
to be accepted once import attempts. The validation recipe in §A6
should be extended with:

0. The outer pak contains `overview.packed` at the root level,
   alongside `manifest.txt`. The file is a valid ZIP and contains
   at least `light/overview.html`.

Pass 28's A5 ("describe.xml-side and content-side are independent
install-pipeline stages") was directionally correct but
under-specified — the stages are not just independent, they have
separate orchestrator-step gates, and only the content-side stage
is gated by `overview.packed`. The describe.xml-side stage (step
15) runs unconditionally on every install.

### Files written

Spec amendment (this section), audit-log Pass 29 entry, and memory
note updates flagging that the Pass 28 hypothesis was correct in
shape but wrong in proximate cause.
