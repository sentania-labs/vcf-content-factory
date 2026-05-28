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

## The fix

Build 16: restructured to subdirectory pattern. Dashboard at
`content/dashboards/<slug>/dashboard.json`, view at
`content/reports/<slug>/content.xml`. All standard empty directories
present.

## References

- NSX-T pak: `/storage/db/casa/pak/dist_pak_files/VA_LINUX/NSXTAdapter-*.pak`
- vSphere pak: `/storage/db/casa/pak/dist_pak_files/VA_LINUX/VMwarevSphere-*.pak`
- vSAN pak: `/storage/db/casa/pak/dist_pak_files/VA_LINUX/ManagementPackforStorageAreaNetwork-*.pak`
- vCommunity: `references/vmbro_vcf_operations_vcommunity/Management Pack/content/`
