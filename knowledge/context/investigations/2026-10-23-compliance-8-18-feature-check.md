# Compliance 0.0.0.96 on Aria Operations 8.18.7: 9.x feature check (2026-10-23)

Factory issue #212 step 2, second pass (first pass: `2026-10-15-devel-8-18-compliance-install.md`,
build 95). Agent: content-installer. Approval: `approvals/2026-10-15-all-devel-dev-paks.md`.
Instance: devel_8_18 (VMware Aria Operations 8.18.7, build 25423534). All times
America/Chicago, 2026-10-23. Step 1 of #212 (SSH read of the SDK jar) was not touched.
Playwright MCP failed to connect (CONNECTION_CLOSED), so VISUAL VERIFICATION: SKIPPED;
everything below is API evidence.

## Pak and state

- Pak: `dist/vcfcf_sdk_compliance.0.0.0.96.pak` (built 2026-10-16 12:44 from compliance repo
  982557d, build 96, dev preview; no rebuild needed). Replaced 0.0.0.95.
- Install: started about 10:51, completed 10:56. Installer message: "Install completed and
  verified: VCF Content Factory Compliance 0.0.0.96 (adapterKind='vcfcf_compliance'
  isInstalled=true version='0.0.0.96')". Upload used the installer's default
  `ignoreSignatureChecking=true`; no signing refusal.
- The compliance-mgmt account came back FAILED/NONE after the upgrade (as on earlier
  installs). `PUT /api/adapters/<id>/monitoringstate/start` returned 200 at about 10:57;
  DATA_RECEIVING with fresh stamps at 10:57:09 to 10:57:21.
- Inventory before install (10:50): 8.18.7 platform paks, compliance 0.0.0.95, UniFi 0.0.0.14,
  Synology 0.0.0.31, vSAN Host Metrics 1.4.6, Cluster Performance Risk 1.3.0; adapter
  instances compliance-mgmt, factory-unifi-b14, factory-synology-b31, vsan-mgmt, cpr-8-18 (all
  on collector 2, the Cloud Proxy) plus the three VMWARE vCenter instances.

## Results

| # | Feature | Result | Evidence |
|---|---|---|---|
| 1 | "Allow Unsigned PAK Installation" switch | NOT PRESENT on 8.18 (no gate) | `getIntegrations` has no `isUnsignedPakInstallationAllowed` key (10:50); `GET /casa/upgrade/{cluster,slice}/pak/allow_unsigned_pak` both 404 (10:51); 10-15 recon found no `unsignedPakInstallation.*` bundle keys and an empty `getUPIStatus`. 8.18 presumably uses the older warn-and-confirm (inferred from the 10-15 recon; never seen, because the CLI always sends `ignoreSignatureChecking=true`). Requirement for #216: the installer must treat an absent key or a 404 as "no gate on this platform", not as false; today `installer.py` reads neither. |
| 2 | Pak obtained | PASS | Existing dist pak 0.0.0.96, newest in `dist/`, matches adapter.yaml build 96 |
| 3 | Install on devel_8_18 | PASS | See above. Not tested with the signature flag off (the CLI always sends true). |
| 4a | Certificate accept hook on Validate Connection | NOT RETESTED | Needs the UI. PASS at build 95 on 10-15 ("Untrusted certificate found" dialog, ACCEPT, "Test connection successful"). Account was not recreated today. |
| 4b | Ambient Suite API login for stitching | PASS (functional) | `VCF-CF Compliance|score` stamped 10:57:09 to 10:57:20 on mgmt vCenter objects: HostSystem vcf-lab-mgmt-esx02 64.58, VirtualMachine vcf-lab-operations-collector01 68.18, cluster vcf-lab-mgmt-cl01 100.0, vDS vcf-lab-mgmt-cl01-vds-01 75.0, portgroup ...pg-k8s-nodes 100.0, VMwareAdapter Instance vcf-lab-vcenter-mgmt 50.0. Sample counts (first 3 to 12 per kind) show only mgmt-vCenter objects carry it, as expected (account scans one vCenter). The adapter log line itself is NOT TESTABLE, see below. |
| 4c | ComputedMetrics on the pak singleton | PASS | ComplianceWorld `Rollup|Environment|pass_rate` 73.47, `controls_evaluated` 1327, `scored` 64, `non_compliant` 57, avg_score 76.67, refreshed at 10:57:20 by 0.96 (previously 10:46 and 10:51 under 0.95). `Summary|last_scan_timestamp` stamped 10:57 (field value `15:57:21Z`). badge|compliance still -1 ("?" in UI); not compared with 9.x. |
| 4d | Configuration-file store for the overrides file | PARTIAL | `Summary|overrides_file` empty, `overrides_status` none, `overrides_skipped/overridden/not_loaded` 0. A non-blank overrides file was not loaded; that needs a write into the instance config store (outside the standing approval). |
| 4e | dashboards.properties Summary binding | BOUND (clone may predate build 96); clone rendering NOT TESTABLE | pak ships `content/dashboards/dashboards.properties`: `VCF_Content_Factory_Compliance_World_Summary=vcfcf_compliance:ComplianceWorld`. Live: `getResourceKindList` ComplianceWorld template "[VCF Content Factory] Compliance World Summary 1"; `getSummaryTabId` returns tabId 8b64ddb0-67ae-47a5-876a-def1edb713aa (materialized copy; record this UUID); template config has 7 widgets (3 View, Scoreboard, MetricChart, AlertList, PropertyList) and reports `isLoading: true` while the source dashboard 4e2c777e-9c6c-4c6a-bc16-ab55b6110f33 reports `isLoading: false`; that is the shape of the deferred-clone problem in #200 and may be the 10-15 "not configured" symptom, unresolved here. The build 95 install on 10-15 already created a Summary clone, and nothing read today shows whether this tabId was created by 0.0.0.95 or 0.0.0.96. The API does not expose per-widget view bindings, so the 10-15 "view widgets show 'The widget is not configured'" finding could not be confirmed or cleared without the browser. |
| 4f | Widget-type allowlist | CARRIED FROM BUILD 95, not re-proven | All 5 packaged dashboards (Environment Overview, ESX Hosts, vCenter & Networking, VMs, World Summary) are present on the instance. Build 95 imported the same five on 10-15 and no import-task result or definition timestamp from today's upgrade was captured, so presence does not show the 0.0.0.96 import succeeded. Rendering not checked (no browser). |
| 4g | describe identType 2 Advanced Settings placement | NOT RETESTED | UI only. PASS on 10-15: collapsed "Advanced Settings" expander holding overrides file and VAMI settings. The account's `overrides_file` and `read_appliance_settings` identifiers (isPartOfUniqueness false) are present and readable via `GET /api/adapters`. |
| 4h | DEF-018 (view import with dangling localizationKey) | CARRIED FROM BUILD 95, not re-proven | All 9 views the pak carries are present in `getGroupedViewDefinitionThumbnails` (build 95 imported the same nine on 10-15; no import-task result from today was captured): Clusters, Objects with Unreadable Controls, by vCenter and Object Type, Distributed Portgroups, Distributed Switches, Host Detail, Objects by SCG Version, vCenter Servers, VM Detail. Compliance Host Overview is a repo view the pak does not package (same as build 95). |
| 4i | Adapter log (ambient login line, cert hook line) | NOT TESTABLE | Per the 10-15 pass, Support > Logs on 8.18 listed only the primary node (not re-checked today, no browser); the adapter runs on the Cloud Proxy (172.27.10.15), reachable only by SSH (gated on Scott) or a support bundle. |

## Not tested and why

- Browser-only checks (4a, 4g, 4e render): Playwright MCP server failed to connect.
  Re-run with the browser available.
- Overrides file with real content (4d): needs a config-store write.
- Adapter logs (4i): SSH gated.
- Signature flag off (item 3): CLI always sends it.

## Left on devel_8_18

Compliance 0.0.0.96 with its content and Summary clone, the compliance-mgmt account
started and collecting, plus the other two factory dev paks and the two Python fork paks as inventoried above. Nothing global
was changed; the unsigned-pak switch does not exist on this build.
