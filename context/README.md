# Context files index

Topical background for code paths, wire formats, and investigations.
Agents read these on demand — don't paste file contents into
orchestrator context.

## Living references

These are actively maintained and authoritative for their topic.

| Topic | File |
|---|---|
| **Operational rules — delegation & lane discipline** | `rules_delegation.md` |
| **Operational rules — content authoring** | `rules_content_authoring.md` |
| **Operational rules — install & verification** | `rules_install_verification.md` |
| **Operational rules — API & wire format** | `rules_api_wire_format.md` |
| **Operational rules — PowerShell** | `rules_powershell.md` |
| **Operational rules — operational** | `rules_operational.md` |
| Shared vocabulary (Bundle vs Package, Sync/Enable/Install, etc.) | `dictionary.md` |
| Super metric authoring, DSL rules, style | `supermetric_authoring.md` |
| Dynamic custom group + group types authoring | `customgroup_authoring.md` |
| Custom group relationship grammar | `customgroup_relationship_grammar.md` |
| UUIDs, cross-references, rename safety | `uuids_and_cross_references.md` |
| API surface map (public + internal + content-zip) | `content_api_surface.md` |
| Content-zip wire formats (super metrics, dashboards, views, policies) | `wire_formats.md` |
| MPB template.json schema (pak runtime format) | `mpb_template_json_schema.md` |
| MPB adapter JAR reverse engineering (Gen-2 constant pool) | `mpb_adapter_jar_reverse_engineering.md` |
| Reports API surface + wire format | `reports_api_surface.md` |
| Install path + policy enablement | `install_and_enable.md` |
| Internal supermetrics assign endpoint details | `internal_supermetrics_assign.md` |
| Dashboard delete API (UI session auth, Struts/Ext.Direct) | `dashboard_delete_api.md` |
| Widget types survey (supported + unsupported) | `widget_types_survey.md` |
| Widget renderer scoping (next expansion targets) | `widget_renderer_scope.md` |
| Recon metric key patterns | `recon_metric_keys.md` |
| Reference docs inventory + PDF extraction | `reference_docs.md` |
| Allowlisted external reference repos | `reference_sources.md` |
| VKS VM type classification + filter patterns | `vks_vm_classification.md` |
| View column wire format (XML attribute encoding) | `view_column_wire_format.md` |
| Custom group UI import envelope format | `customgroup_import_format.md` |
| UI import format investigation (Struts/SPA) | `ui_import_formats.md` |
| Struts/Ext.Direct endpoint catalog | `struts_import_endpoints.md` |
| Struts exploration backlog | `struts_exploration_backlog.md` |
| Known capability limitations | `known_limitations.md` |
| Management pack authoring conventions | `management_pack_authoring.md` |
| MPB design JSON schema + API surface | `mpb_api_surface.md` |
| MPB chaining YAML authoring grammar | `mp_chain_authoring.md` |
| MPB chaining wire format | `mpb_chaining_wire_format.md` |
| MPB relationships (parent/child) | `mpb_relationships.md` |
| MPB object binding wire format | `mpb_object_binding_wire_format.md` |
| MP schema vs existing MP comparison | `mp_schema_vs_existing_mp.md` |
| .pak wire format + install/uninstall | `pak_wire_format.md`, `pak_install_api_exploration.md`, `pak_uninstall_api_exploration.md` |
| .pak UI upload investigation | `pak_ui_upload_investigation.md` |
| Adapter describe (metric/property source of truth) | `adapter_describe_comparison.md`, `adapter_describe_exploration.md` |
| Auth source wire formats | `auth_vidb_oauth_flow.md`, `auth_source_wire_formats.md` |
| Framework review + VCF Ops API surface snapshot | `framework_review_2026_04_18.md`, `vcf_operations_api_surface.md` |
| Bug report: .pak isUnremovable not enforced | `bug_report_pak_isunremovable_not_enforced.md` |
| QA acceptance audit trail | `qa_log.md` |
| Recon log (live instance queries) | `recon_log.md` |

## Investigation archives

Session-specific artifacts. Valid as historical record but may not
reflect current state.

| File | Date | Topic |
|---|---|---|
| `growth_path_2026_04_29.md` | 2026-04-29 | Growth path planning |
| `mpb_chain_wire_diff_2026_04_19.md` | 2026-04-19 | Chain wire format diff investigation |
| `mpb_synology_import_diff_2026_04_29.md` | 2026-04-29 | Synology import diff |
| `mpb_synology_pickup_2026_04_29.md` | 2026-04-29 | Synology MP session pickup notes |
| `mpb_synology_nas_live_recon_2026_04_22.md` | 2026-04-22 | Synology NAS live recon |
| `session_pickup_2026_04_30.md` | 2026-04-30 | Session pickup notes |
| `unifi_mp_jcox_diff_2026_04_30.md` | 2026-04-30 | UniFi MP diff analysis |
| `mpb_import_diff_unifi_2026_05_07.md` | 2026-05-07 | UniFi MP import diff investigation |
| `unifi_integration_filter_probe_2026_05_08.md` | 2026-05-08 | UniFi Integration API filter syntax probe |
