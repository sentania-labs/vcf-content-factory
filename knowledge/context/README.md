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
| `alertdef_symptomset_import.md` | Alert content-import multi-tier SymptomSet encoding |
| `symptomdef_severity_import.md` | SymptomDefinition severity: content-import XML vs REST JSON divergence |
| `dashboard_section_gauge_viewdetails.md` | Factory mapping for Section (row header, membership by row), gauge scoreboard (`visualTheme: 9`), `viewDetails` link contract, AlertVolume (`IntSummaryAlertVolume`); 9.1.1 / 9.2 captures plus export samples |
| `dashboard_navigations.md` | Dashboard Navigation drill-down: `dashboardNavigations` wire shape, per-widget `navigations:` YAML (`dashboard` by name or raw `dashboard_id`, target `widgets`), validate/render resolution, bundle-must-carry-targets, extract mapping (2026-10-07) |
| `dashboard_view_pin_resolution.md` | Self-provider View pin binds by resource display name, not kind key (live-verified 2026-08-26); `_WORLD_DISPLAY_NAME` table and `pin.name` override |
| `dashboard_sort_color_default_summary_rows.md` | View default sort is per-column `sortCriteria` in the view XML (no View-widget key); Scoreboard lower-is-worse is a descending bound triple (no flag); AlertList shows all until an interaction, so provider `selectFirstRow: false` gives show-all-then-narrow; `summaryInfos` holds several rows. Issues #175/#176/#177/#168 (2026-10-23) |
| `../investigations/policy_fragment_wire_format.md` | Super metric enablement in a policy: `<SuperMetrics adapterKind resourceKind><SuperMetric enabled id="<bare uuid>"/>` under `PackageSettings`; policy export is the only read path (`GET /api/policies/{id}` is undefined, hence 500); a pak's policies directory (`<pak>/content/policies/`) fragments parse it but create their own named policy, not a Default Policy edit (2026-10-01) |

### `tier2_architecture.md`
Tier 2 (Java SDK) framework architecture — read when working on SDK adapters.

### `framework_v2_migration.md`
Tier 2 framework v2 migration record (componentLogger, keyed constructors,
the SPI reshape) — cross-referenced throughout `tier2_architecture.md` and the
SDK adapter reviews.

### `python_integration_sdk.md`
VMware's Python Integration SDK (container adapters, `mp-init` / `mp-test` /
`mp-build`, `aria.ops` lib): REST contract, AdapterDefinition to describe.xml
(identType = advanced = identity), certificate hand-off and how to verify with
pyVmomi / requests, credentials, the Suite API client's insecure defaults,
error reporting, pak layout (image referenced by registry digest, never
embedded), today's fork defects, and a Python pack PR review checklist. Read
before authoring or reviewing a Python pack (the third-party forks in
`managed_paks.md`).

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
| `guide_reviewer_doctrine.md` | Shared posture/discipline for the two review-gate agents |
| `guide_visual_verification.md` | Shared Playwright browser-pass procedure (qa-tester, content-installer) |
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

When you add a file under `api-surface/`, add its row to this table in the
**same commit**. This table drifted from disk for four straight curation
cycles because that did not happen.
| File | Purpose |
|---|---|
| `content_api_surface.md` | Content API (public + internal + content-zip) |
| `dashboard_widgets_alertvolume_section_viewdetails.md` | Alert Volume (`IntSummaryAlertVolume`), Section, `viewDetails` link syntax, Scoreboard gauge (`visualTheme: 9`): stored + export wire shapes, from source and live 9.2/9.1; multi-kind bound Scoreboard/PropertyList entries (server picks by page-object kind, no wildcard) |
| `content_upload_methodology.md` | Digest: which upload path each content type takes, and the import/enable/verify order |
| `content_import_skip_semantics.md` | Bisection of `imported=0/skipped=N` on DASHBOARDS + VIEW_DEFINITIONS: it is `force=false` create-only mode, not ghost state, and re-import does not fix it |
| `vcf_operations_api_surface.md` | VCF Ops API surface snapshot |
| `install_and_enable.md` | Install path + policy enablement |
| `internal_supermetrics_assign.md` | Internal supermetrics assign endpoint |
| `dashboard_delete_api.md` | Dashboard delete API |
| `uninstall_empty_collection_shapes.md` | What the UI API returns for empty report/view/dashboard collections (observed vs unresolved), for uninstaller shape guards |
| `summary_dashboard_assignment.md` | Summary-tab binding, UI route: the Struts "Manage Summary Dashboards" call (no Suite API) for content not in a pak. Opens with a read-this-first box naming both routes; its original "a pak cannot bind" conclusion is retained as a recorded reversal, not as fact |
| `summary_dashboard_pak_binding.md` | Summary-tab binding, pak route (primary record for pak work): `<pak>/content/dashboards/dashboards.properties` (`<dir>=<AdapterKind>:<ResourceKind>`), installer behavior, template-clone semantics, uninstall gap, 9.0 through 9.2; complete 9.0.2 WidgetType key list (Build 25137845) for checking widget types against 9.0.x |
| `reports_api_surface.md` | Reports API surface |
| `pak_install_api_exploration.md` | .pak install API exploration |
| `pak_uninstall_api_exploration.md` | .pak uninstall API exploration |
| `pak_ui_upload_investigation.md` | .pak UI upload investigation |
| `compliance_enablement_markers.md` | Compliance enablement markers (per-profile enablement wire state) |
| `compliance_per_control_alert_first_sample_lag.md` | Compliance per-control alerts "not firing" on build 67 was timing: a symptom on a newly created pushed metric key skips the key's first sample (hourly adapter, so about 1 h plus 5 min to first alert); keys, `EQ` operator, metric condition type, and policy all verified correct |
| `auth_vidb_oauth_flow.md` | VIDB OAuth flow |
| `struts_import_endpoints.md` | Struts/Ext.Direct endpoint catalog |
| `struts_exploration_backlog.md` | Struts exploration backlog |
| `widget_types_survey.md` | Widget types (supported + unsupported) |
| `widget_renderer_scope.md` | Widget renderer expansion targets |
| `view_render_internal_endpoint.md` | Server-side view render (`/internal/views/{id}/data/export`) |
| `ui_deep_links.md` | UI deep-link routes for dashboards/views (global search does NOT deep-link) |
| `distribution_view_no_data.md` | DEF-012 root cause: property distributions rendered as numeric histograms |
| `view_multi_subject_column_binding.md` | Multi-subject views: per-column `adapterKind`/`resourceKind` is a kind filter; `subject:` contract, accepted column kinds (driver and time-segment rejected), DEF-019/DEF-020 pointers |
| `dashboard_selfprovider_pin_wire_format.md` | Self-provider widget pin wire format (View traversalSpecId, HealthChart) |
| `dashboard_import_two_phase_materialization.md` | Dashboard import is a uuid-keyed replace landing deferred: phase 1 writes record/layout/`states`, phase 2 resolves `entryKeys` tokens and writes widget `config`. `importComplete`/`entryKeys` semantics (undocumented in both specs); stalls permanently when an adapter kind is absent |
| `pak_dashboard_import_race.md` | Pak install created a bundled dashboard then lost it within seconds with no delete audit (compliance build 67, ESXi Hosts): phase-2 `DashboardImporter` pass racing the pak's sequential ForceByName imports; content exonerated; verify pak dashboard count after install |
| `resourcelist_column_state_wire_format.md` | ResourceList column-state wire format (widget `states[]` presets) |
| `casa-inventory-access.md` | CaSA / Cloud-Proxy adapter inventory-read mechanism |
| `casa-injected-vs-raw-client.md` | CaSA routing: raw SDK SuiteAPIClient vs injected UnlicensedAdapter client |
| `per-instance-suiteapi-credential-contract.md` | Per-instance Suite API credential contract (bytecode-proven) |
| `2026-08-26-licensing-data-availability-9x.md` | Where license entitlement/consumption lives on 9.x: `/internal/licenses*` only, absent from the resource/metrics plane; verbatim product/cost-unit identifier strings |

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

- `policy_fragment_wire_format.md`: policy super metric enablement wire format and pak policies-directory (`<pak>/content/policies/`) fragment support (also listed under `wire-formats/`).
- `2026-10-23-devel-materialization-check-run.md`: live devel 9.0.2 run of the post-import dashboard materialization check (OK/ABSENT on the factory content, STALLED exit 1 on a throwaway bound to the uninstalled vcommunity adapter kind), with verbatim lines, exit codes, and the departures from the brief.
- `2026-10-12-compliance-pak-summary-binding.md`: compliance build 88 World Summary did not bind on devel 9.0.2 because the pak importer crashes on an unknown widget type (`Section`, missing from that build), and the crash aborts the whole dashboard before `dashboards.properties` is read.
- `2026-10-13-account-dialog-advanced-settings-and-cert-accept.md`: how the Add Account dialog places Advanced Settings and where the certificate-accept hook fires on 9.0.2 (read-only, feeds the build 93 auto-only cert-accept design).
- `2026-10-13-compliance-summary-clone-config-loss.md`: build 89 World Summary tab clone had no widget config because the SUMMARY template clone is taken before the importer finishes parking and resolving widget config, and nothing finishes it for templates.
- `2026-10-13-dashboard-import-deferral-trigger.md`: on 9.0.2 dashboard import deferral is unconditional; only a per-user background importer thread resolves parked config, so a pak cannot bind a complete Summary clone on its own.
- `2026-10-13-first-party-summary-binding.md`: on 9.0.2 exactly one first-party pak (vSAN) ships `dashboards.properties`; why its Summary clone is complete and the factory's was not.
- `2026-10-13-summary-dashboard-parked.md`: stake for the pak-bound Summary dashboard line of thought, parked 2026-10-13 on Scott's word; where it stands and what would reopen it.
- `2026-10-13-cluster-perf-risk-credential-reuse.md`: cluster-perf-risk has no credential and talks only to the Suite API with the platform login; no transferable credential reuse for an adapter that opens its own vCenter session.
- `2026-10-13-cluster-perf-risk-tuneup-assessment.md`: ranked tune-up PRs for the forked cluster-perf-risk pack (silent login failure, unverified Suite API TLS, publish-to-native edges); fork issues #1 to #9.
- `2026-10-13-sdk-upstream-issue-drafts.md`: nine draft issues plus one comment on #161 for the official Python Integration SDK repo (cryptography pin, Suite API client failure handling, token logging, verify default, describe.xml `isKpi`/enum default, `get_objects_by_type`, a leading suite-api path segment prefix, dotless registry host, registry password on argv), each with a repro verified against the PyPI releases; pip's vendored copies dropped as not an SDK defect. Not filed.
- `2026-10-23-devel-proof-summary-sort-bounds.md`: devel 9.0.2 acceptance proof of multi-row list-view `summary:` (#168), column `sort:` (#175) and descending Scoreboard bounds (#176): verbatim wire fragments, server render rows, import phase-2 timing; Playwright skipped.
- `2026-10-15-devel-8-18-recon.md`: Aria Operations 8.18.7 build 25423534 on the new devel_8_18 profile: one node plus a Cloud Proxy in no group, three vCenter instances, no factory pak, no unsigned-pak switch on that build (warn-and-confirm instead), content import and internal supermetrics assign routes present, Summary binding and ComputedMetrics unknown until a pak is installed.
- `2026-10-15-devel-8-18-compliance-install.md`: compliance 0.0.0.95 on Aria Operations 8.18.7: install, certificate dialog, stitching, ComputedMetrics and Advanced Settings all work; the Summary clone binds but its view widgets are unconfigured (same family as the parked 9.0.2 stake); collector group POST needs `systemDefined: false`; installer's forced ignoreSignatureChecking hides 8.18's confirm.
- `2026-10-23-compliance-8-18-feature-check.md`: compliance 0.0.0.96 on Aria Operations 8.18.7 (issue #212 step 2, second pass): no unsigned-pak switch on 8.18; install, ComputedMetrics and stitching pass via API; overrides file partial (no content loaded); Summary binding bound but the clone may predate build 96; widget allowlist and DEF-018 carried from build 95, not re-proven; clone rendering, cert hook UI, Advanced Settings and adapter log not retested (no browser, SSH gated).
- `2026-10-24-devel-8-18-sdk-jar-and-proxy-log.md`: issue #212 step 1 over SSH on devel_8_18: the 8.18.7 SDK jar (Java 11 bytecode, hash, copied to the holding share), collector and Cloud Proxy on OpenJDK 11, javap delta of the 22 imported classes against 2.2 (19 identical, 11 members only 2.2 carries), framework and seven paks compile clean against it, the compliance adapter log on the proxy (0 ERROR, 2 WARN). Basis for RULE-019 and issue #252.
- `2026-10-24-devel-proof-view-sort-instanced.md`: devel 9.0.2 proof that a fanned-out instanced list view (VM Snapshot Inventory, one row per snapshot) honours the view-level `sort:` on a flat column: one sortCriteria property stored, 32 rows strictly descending with each VM's snapshots contiguous; two plain-view controls pass; Playwright skipped.
- `2026-10-15-devel-inventory-sync.md`: devel 9.0.2 brought current on 2026-10-15: vCommunity vSphere uninstalled on Scott's word, compliance 95 and Synology 31 installed, Python fork accounts created on the Cloud Proxy (collector group creation returns 500 on 9.0.2), UniFi deferred to the post-Codex pak.
- `2026-10-14-unsigned-pak-policy-9-1-1.md`: fresh VCF Operations 9.0.x and 9.1.x installs refuse unsigned paks (`unsigned_pak_installation.not.allowed`) until an admin turns on Administrator Settings, Security Settings, Allow Unsigned PAK Installation in `/admin`; `ignoreSignatureChecking=true` only works with the switch on; no third-party signing exists; read the state from `getIntegrations` (`isUnsignedPakInstallationAllowed`).
- `2026-10-16-compliance-52-30-31-recon.md`: read-only devel_9_1 recon for compliance issues #52, #30 and #31 on pak 0.0.0.95: #52 not reproduced (31 of 31 full pages, no incomplete cycle in 43.5 hours; the no-score clusters are a constant), the AlertList widget configurations behind #30 and #31, and the finding that no Suite API path reads an adapter log (admin UI Support Logs browser is the only no-SSH route).
- `2026-10-16-compliance-96-devel-9-1-proof.md`: compliance dev pak 0.0.0.96 on devel_9_1: install, normal cycles, and a forced vCenter login failure that raised Rollup|incomplete to 1 and fired the not-collected alert, both clearing one cycle after the credential was restored; installed pak postdates the last review round.
- `2026-10-16-compliance-cycle-durations.md`: compliance adapter cycle durations over 24 hours on prod, devel, devel_9_1 and devel_8_18 before build 96, to judge the proposed 95 percent per-cycle budget: the worst 5-minute-interval cycle was 15 percent of the 285 s budget, and prod runs a 60-minute interval so the budget does not bind there.
- `2026-10-16-synology-32-devel-9-1-proof.md`: Synology dev pak 0.0.0.32 on devel_9_1: install and collection PASS, memory and free-space units fixed, load averages still at DSM's x100 scale (issue #41), three paths not exercised (NFS off, datastore paging, explicit Suite API path); a credential exposure in the session transcript is recorded for rotation.
- `2026-10-16-unifi-15-devel-9-1-proof.md`: UniFi dev pak 0.0.0.15 on devel_9_1: install and collection PASS, NVR storage key unproven (issue #39), camera key unproven, informing-state gating and pending-adoption skip seen; installed pak postdates the last review round.
- `2026-10-13-vsanhostmetrics-tuneup-assessment.md`: ranked tune-up PRs for the forked vsanhostmetrics Python SDK adapter: accepted certificate ignored (use `get_certificates()` with pyVmomi `serverPemCert`), collect errors silently discarded, one non-vSAN cluster aborts collection, username outside the credential type.

### `reviews/` — Build and framework review reports
Point-in-time review records: per-build SDK adapter reviews written by
`sdk-adapter-reviewer`, and `reviews/framework/` written by
`framework-reviewer` (the pre-PR gate on `src/vcfcf_*/` changes).
Timestamped records, not living docs.

### `approvals/`: owner decision and approval records
Point-in-time records of the repo owner's verbatim decisions and go-aheads:
install and interval approvals per pak build, and dated decision lists
answering pending questions. Destructive and outward-facing actions need
the owner's explicit words preserved as an artifact before execution, and
this is where they live. One file per decision set, dated. Timestamped
records, not living docs.

### `cleanroom-requests/` — Cleanroom investigation requests
Dated request/finding notes feeding the cleanroom reverse-engineering work
(see `cleanroom-spec/`).

### `attic/` — Retired historical artifacts
Superseded files kept for provenance (e.g. `attic/legacy-root-content/` —
the pre-`content/`-era root dashboards/views YAMLs retired in reorg v2
phase 0). Never read for current guidance.

---

## Reference files
| File | Purpose |
|---|---|
| `reference_sources.md` | Allowlisted external reference repos |
| `reference_docs.md` | Reference docs inventory + PDF extraction |
| `managed_paks.md` | SDK pak registry — per-repo Tier 2 adapters cloned by `scripts/bootstrap_managed_paks.sh` |
| `feedback_queue.md` | Intake queue for user feedback/enhancement requests, pre-triage (correctness problems graduate to `defects.md`) |
| `vrops-content-management.md` | Extracted community article (Brock Peterson) on vROps content management via the Suite API |
