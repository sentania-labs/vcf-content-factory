# Context

Pure documentation: API specs, wire formats, authoring patterns, MP schemas.
When context contradicts a rule, the rule wins.

---

## Always read (every session)

These files cost almost nothing to scan and prevent re-deriving known knowledge.

| File | Purpose |
|---|---|
| `dictionary.md` | Shared vocabulary — Bundle vs Package, Sync/Enable/Install, tier definitions |
| `known_limitations.md` | Capability boundaries — read before proposing anything new |
| `tier_decision_framework.md` | Tier 1 vs. Tier 2 full trigger table and decision flow |
| `api_pattern_catalog.md` | Recognized API shapes with default object models and known gaps |
| `repo_layout.md` | Directory map of the repo |
| `defects.md` | Defect registry — open blocking defects gate releases (RULE-012) |

---

## Read for MP tasks

### `mpb/` — MPB-specific docs
| File | Purpose |
|---|---|
| `mpb_relationships.md` | Parent/child relationship wiring patterns (read before designing any hierarchy) |
| `mpb_api_surface.md` | MPB design JSON schema and API surface |
| `mpb_designer_wire_format.md` | MPB pak generation pipeline and expression grammar |
| `mpb_pak_structural_reference.md` | Canonical pak format from 8+ reference paks |
| `mpb_chaining_wire_format.md` | Chaining YAML wire format |
| `mpb_builderfile_schema.md` | MPB BuilderFile Kotlin runtime model |
| `mpb_describe_xml_emission.md` | describe.xml emission pipeline |
| `mpb_describe_xsd_canonical.md` | describe.xml canonical XSD |
| `mpb_alerts_symptoms_grammar.md` | Alerts/symptoms/recommendations grammar |
| `mpb_template_json_schema.md` | template.json schema (pak runtime format) |
| `mpb_instanced_groups_wire_format.md` | Instanced groups wire format |
| `mpb_object_binding_wire_format.md` | Object binding wire format |
| `mpb_runtime_variable_scopes.md` | Runtime variable scope rules |
| `mpb_pak_signing_chain.md` | Pak signing chain analysis |
| `mpb_explicit_key_investigation_2026_05_16.md` | Label→key derivation algorithm |
| `mpb_handoff.md` | Tier-1 strategic handoff and capability surface |
| `mpb_adapter_runtime_insights.md` | Runtime architecture deep dive |
| `mp_icon_library.md` | Per-ResourceKind SVG hints |
| `mp_format_comparison_2026_05_15.md` | Format comparison (MPB vs factory) |
| `mp_schema_vs_existing_mp.md` | Schema vs existing MP comparison |
| `mpb_import_investigation.md` | MPB design.json import investigation |
| `reference-mpb-research.md` | MPB JSON schema reference (the target format MP YAML compiles to) |
| `wire_reference/` | Reference wire format artifacts (describe.xml, export.json, template.json) |

### `wire-formats/` — Wire format documentation
| File | Purpose |
|---|---|
| `wire_formats.md` | Content-zip wire formats (super metrics, dashboards, views, policies) |
| `customgroup_import_format.md` | Custom group UI import envelope format |
| `customgroup_relationship_grammar.md` | Custom group relationship grammar |
| `view_column_wire_format.md` | View column wire format (XML attribute encoding) |
| `pak_wire_format.md` | .pak wire format |
| `auth_source_wire_formats.md` | Auth source wire formats |
| `ui_import_formats.md` | UI import format investigation |

### `tier2_architecture.md`
Tier 2 (Java SDK) framework architecture — read when working on SDK adapters.

### `framework_v2_migration.md`
Tier 2 framework v2 migration record (componentLogger, keyed constructors,
the SPI reshape) — cross-referenced throughout `tier2_architecture.md` and the
SDK adapter reviews.

---

## Read for content authoring

### `authoring/` — Content authoring patterns
| File | Purpose |
|---|---|
| `supermetric_authoring.md` | Super metric DSL rules and style |
| `view_dashboard_design_guide.md` | View + dashboard design/layout guide |
| `customgroup_authoring.md` | Dynamic custom group authoring |
| `management_pack_authoring.md` | MP authoring conventions |
| `mp_chain_authoring.md` | MPB chaining YAML authoring grammar |
| `mp_authoring_design_principles.md` | MP design principles (codified lessons) |
| `uuids_and_cross_references.md` | UUIDs, cross-references, rename safety |
| `guide_content_authoring.md` | Interview discipline, infer-not-interview |
| `guide_delegation.md` | Orchestrator delegation discipline |
| `guide_codification.md` | How to turn corrections into framework knowledge |
| `guide_install_verification.md` | Install workflow, dependency audit |
| `guide_api_wire_format.md` | API investigation and wire format ground truth |
| `guide_operational.md` | Credentials, labs, distribution |
| `guide_powershell.md` | PS 5.1 compatibility |
| `recon_metric_keys.md` | Recon metric key patterns |
| `vks_vm_classification.md` | VKS VM type classification and filter patterns |
| `federation_breaks_aria_ops_stitching.md` | Federation permanently breaks ARIA_OPS-stitching MPs |
| `vsphere_storage_paths_v2_plan.md` | vSphere Storage Paths v2 design plan |

---

## Read on demand

### `api-surface/` — API endpoint documentation
| File | Purpose |
|---|---|
| `content_api_surface.md` | Content API (public + internal + content-zip) |
| `vcf_operations_api_surface.md` | VCF Ops API surface snapshot |
| `install_and_enable.md` | Install path + policy enablement |
| `internal_supermetrics_assign.md` | Internal supermetrics assign endpoint |
| `dashboard_delete_api.md` | Dashboard delete API |
| `reports_api_surface.md` | Reports API surface |
| `pak_install_api_exploration.md` | .pak install API exploration |
| `pak_uninstall_api_exploration.md` | .pak uninstall API exploration |
| `pak_ui_upload_investigation.md` | .pak UI upload investigation |
| `auth_vidb_oauth_flow.md` | VIDB OAuth flow |
| `struts_import_endpoints.md` | Struts/Ext.Direct endpoint catalog |
| `struts_exploration_backlog.md` | Struts exploration backlog |
| `widget_types_survey.md` | Widget types (supported + unsupported) |
| `widget_renderer_scope.md` | Widget renderer expansion targets |

### `api-maps/` — Per-target API maps
One file per monitored system. Generated by `api-cartographer`.

### `cleanroom-spec/` — Cleanroom findings
Empirical reverse-engineering of MPB runtime. Start at `spec/17` for framework,
`spec/15` for adapter authoring.

### `specimens/` — Example payloads
Live API response samples and working wire format artifacts.

### `adapter_describe_cache/` — Adapter describe cache
Cached `describe` XML and comparison data.

### `exports/` — Export artifacts
Content export snapshots from live instances.

### `investigations/` — Investigation archive
Session-specific research logs, diff analyses, and exploration notes. Read when
debugging a specific issue; not required reading.

---

## Reference files
| File | Purpose |
|---|---|
| `reference_sources.md` | Allowlisted external reference repos |
| `reference_docs.md` | Reference docs inventory + PDF extraction |
| `managed_paks.md` | SDK pak registry — per-repo Tier 2 adapters cloned by `scripts/bootstrap_managed_paks.sh` |
