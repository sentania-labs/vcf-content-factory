# Pak Content Bundling — Views, Dashboards, Alerts

## The dead end

Build 14: put views in `content/views/views.zip` and dashboards as flat
JSON files at `content/dashboards/<slug>.json`. The pak installed but
neither the view nor the dashboard appeared on the instance.

Build 14 also failed for a separate reason: `<SymptomSets>` with only
one `<SymptomSet>` child throws `IllegalArgumentException: A composite
symptom set should contain at least two Symptom Sets`. Fixed by using
two ref-style `<SymptomSet>` elements (one per symptom).

Build 15: symptoms/alert installed from describe.xml. Dashboard/view
still did not auto-import — the CASA framework ignored our content/
directory layout.

## What actually works

Examined three VMware first-party paks on the devel appliance
(vSphere, NSX-T, vSAN) plus the vCommunity Integration SDK pak.
All use the same content/ directory layout and none use post-install
scripts for content import — the CASA framework processes content/
natively.

### Canonical content/ directory layout

```
content/
  dashboards/<slug>/dashboard.json     # one subdirectory per dashboard
  reports/<slug>/content.xml           # views as <Content><Views> XML
  alertdefs/alert-content.xml          # combined <alertContent> XML
  customgroups/                        # JSON
  supermetrics/                        # JSON
  traversalspecs/                      # XML
  scorecards/                          # JSON
  files/                               # reskndmetric configs
  resources/                           # localization properties
  policies/                            # policy configs
```

### Key rules

1. **Dashboards**: each gets its own **subdirectory** under
   `content/dashboards/`. The JSON file can be named `dashboard.json`
   or `<slug>.json`. Flat files at `content/dashboards/<slug>.json`
   were NOT processed.

2. **Views**: go in `content/reports/`, NOT `content/views/`. Each
   view group gets a **subdirectory** containing `content.xml`. The
   XML format is `<Content><Views><ViewDef id="...">...`. This is the
   same format `render_views_xml()` produces.

3. **Alerts/symptoms/recommendations**: can go in describe.xml
   (works — confirmed build 15) OR in `content/alertdefs/` as a
   combined `<alertContent>` XML file containing all three types.
   First-party paks use content/alertdefs/; our adapter uses
   describe.xml. Both work.

4. **SymptomSets constraint**: `<SymptomSets>` (plural) MUST have
   ≥2 `<SymptomSet>` children. Use one ref-style `<SymptomSet>` per
   symptom. A single `<SymptomSet>` with multiple `<Symptom>` children
   inside a `<SymptomSets>` wrapper is rejected.

5. **No post-install scripts needed**: the CASA pak framework
   processes the content/ directory natively during APPLY_ADAPTER.
   VMware first-party paks have empty script fields in manifest.txt.

6. **Standard empty directories**: include all standard content/
   subdirectories (even empty) so the platform recognizes the
   content/ tree.

## The fix (partial)

Build 16: restructured to subdirectory pattern. Dashboard at
`content/dashboards/<slug>/dashboard.json`, view at
`content/reports/<slug>/content.xml`. All standard empty directories
present. Still didn't auto-import.

## The actual fix

Build 17: placed content INSIDE `adapters.zip` at
`<adapter_kind>/content/dashboards/<slug>/dashboard.json` and
`<adapter_kind>/content/reports/<slug>/content.xml`.

The `DashboardImporter` in vcops-bridge runs at boot time and scans
`/usr/lib/vmware-vcops/user/plugins/inbound/<adapter>/content/dashboards/`.
When `adapters.zip` is extracted during pak install, its contents go
to that directory. VrAdapter's dashboard imports this way — its
`adapters.zip` contains `VrAdapter/content/dashboards/`.

Content at the outer pak `content/` directory may work for first-party
paks installed during the VCF OVA deployment, but for third-party pak
install/upgrade the inner adapters.zip path is what DashboardImporter
scans. Keep content in BOTH locations (belt-and-suspenders).

## The third dead end — entries.resource[] placeholder names

Build 18 (A1–A6 fixes from spec/18 Pass 28 addendum): all binding fields
present, `entries.adapterKind` set, `resources/` subdirs emitted, inner
archive content removed.  Still silent import failure on the dashboard.

Root cause: the renderer was adding self-provider pinned widgets to
`entries.resource[]` using the resource KIND name as the resource display
name.  The DashboardImporter resolves `entries.resource[]` entries by NAME
against running resources on the instance.  A resource named "HostSystem"
(the kind name) does not exist on any vSphere instance — individual hosts
have names like "esxi01.example.com".  The View widget's `resourceId` field
references `resource:id:N_::_`, which maps to the placeholder entry, which
fails to resolve, so `isEntityFound()=false` and the dashboard silently
does not appear post-install.

### What actually works for self-provider View widget pinning

Evidence from three confirmed-working reference paks:
- **VCFAutomation**: View widget pinned to `entries.resource[name="Automation World"]`.
  The "Automation World" resource exists on every instance with VCFAutomation
  installed — it is the adapter's world singleton.
- **AppOSUCP/UCP dashboard**: View pinned to `entries.resource[name="Universe"]`.
  Same pattern — "Universe" is the Container adapter's world singleton.
- **idps-planner**: View pinned to `entries.resource[name="vSphere World"]`.

Pattern: **self-provider View widgets must be pinned to a world/singleton
resource whose display name is known to exist on every target instance.**
Leaf resource kinds (HostSystem, VirtualMachine, etc.) have per-instance
names — they cannot be pre-resolved in a pak.

### The fix (build 19)

Added `_VIEW_PIN_CONTAINER` table to `vcfops_dashboards/render.py` mapping
`(adapter_kind, leaf_resource_kind)` to the world-singleton container
`(container_adapter_kind, container_resource_kind, container_resource_name)`.

Added `_resolve_view_pin()` helper that checks the table and falls back to
`(adapter_kind, resource_kind, resource_kind)` for world kinds (where the
resource name equals the kind name — e.g., ComplianceWorld, VRMS World).

Changed the `resource_index` building loop to:
- Only include View and ProblemAlertsList widgets (the only types that
  reference `resource:id:N_::_` in their widget config)
- Use the resolved container key instead of the raw pin key

The compliance dashboard View pinned to `VMWARE/HostSystem` now generates:
- `entries.resource[name="vSphere World", resourceKindKey="vSphere World"]`
- View widget `resourceId: "resource:id:0_::_"`, `resourceName: "vSphere World"`
- View widget `resourceKindId: "002006VMWAREvSphere World"`

The idps-planner reference confirmed this exact pattern works end-to-end.

### Extend _VIEW_PIN_CONTAINER for new adapters

When authoring a dashboard with a self-provider View widget pinned to a
leaf kind for a new adapter, add an entry to `_VIEW_PIN_CONTAINER` in
`vcfops_dashboards/render.py`.  The container resource name must be a
resource that will always exist when the owning adapter is installed
(typically the adapter's "world" singleton).

## References

- NSX-T pak: `/storage/db/casa/pak/dist_pak_files/VA_LINUX/NSXTAdapter-*.pak`
- vSphere pak: `/storage/db/casa/pak/dist_pak_files/VA_LINUX/VMwarevSphere-*.pak`
- vSAN pak: `/storage/db/casa/pak/dist_pak_files/VA_LINUX/ManagementPackforStorageAreaNetwork-*.pak`
- vCommunity: `references/vmbro_vcf_operations_vcommunity/Management Pack/content/`
- VCFAutomation (devel): `vault/workspaces/vcf-mp-cleanroom/inputs/from-devel/paks/VCFAutomation-*.pak`
- AppOSUCP (devel): `vault/workspaces/vcf-mp-cleanroom/inputs/from-devel/paks/AppOSUCPAdapter-*.pak`
- VrAdapter (devel): `vault/workspaces/vcf-mp-cleanroom/inputs/from-devel/paks/VrAdapter-*.pak`
- idps-planner: `dist/ThirdPartyContent/dashboards/idps-planner.zip`
