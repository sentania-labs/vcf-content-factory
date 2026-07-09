# v20 SDK Compliance pak — silent drop of dashboard and view

**Date:** 2026-05-28
**Pak:** `vcfcf_sdk_compliance.1.0.0.20.pak` (pakID `VCFContentFactoryCompliance-10020`)
**Appliance:** `vcf-lab-operations-devel.int.sentania.net`
**Install task ID:** `7048f8d1-1cd8-43ad-8c3d-ada47f49948a`
**Install window:** 2026-05-28T16:03:26.774Z to 2026-05-28T16:04:08Z

## Top-line finding

Step 5 of the pakManager orchestrator (`DeployNewUpgradeContentOperation`)
**did not run** for this pak. The orchestrator logged: `operation
com.vmware.vcops.casa.upgrade.pak.DeployNewUpgradeContentOperation says it
should not run`, 192 ms after the step started. The `content/` tree at the
pak root — which carried the dashboard `dashboard.json` and the report
`content.xml` — was never processed.

Step 15 (`APPLY_ADAPTER` / `DistributedTaskInstallUninstallAdapters`) DID
run for 23 seconds (16:03:34 to 16:03:57) and processed only the
contents of `adapters.zip`: describe.xml, symptom definitions, alert
definitions, recommendations. It does not process the pak-root `content/`
tree at all.

Neither H1 (slash-in-name folder rejection) nor H2 (resourceKindKey="vSphere
World" rejection) is supported by the logs — the importer was never invoked
on the dashboard at all, so it had no chance to reject it.

## Root cause

The pak is structurally a hybrid that the platform does not support:

1. `manifest.txt` declares only `adapters: ["adapters.zip"]`. No
   `pak_format` is declared.
2. The results file says `pak_format = "6.x"` (logged in
   `vcopsPakManager.root.post_apply_adapter.log` line 2071).
3. The pak ZIP root contains BOTH:
   - `adapters.zip` (SDK adapter payload — `vcfcf_compliance.jar`, describe.xml,
     and `vcfcf_compliance/conf/views/views.zip` containing the view ViewDef)
   - A separate `content/` tree with `content/dashboards/VCF_Content_Factory_Compliance_Fleet_Overview/dashboard.json`
     and `content/reports/VCF_Content_Factory_Compliance_Host_Overview/content.xml`
4. For a 6.x adapter-format pak, the orchestrator runs APPLY_ADAPTER
   (processes `adapters.zip` only) and **skips** `DEPLOY_NEW_UPGRADE_CONTENT`
   (which would have processed the pak-root `content/` tree).
5. The view inside `vcfcf_compliance/conf/views/views.zip` also was not
   imported — no `ViewDef`, `views.zip`, or `ContentImport.importFile` log
   line references it in the install window. The SDK adapter describe pipeline
   does not import view content from `conf/views/views.zip` either; that path
   appears to be inert in this code path.

## Evidence

### `/storage/vcops/log/casa/pakManager.actions.log`

```
2026-05-28T16:03:26.774Z INFO  [...] orchestratePak:484 - operationName=DEPLOY_NEW_UPGRADE_CONTENT, step=5, totalSteps=19
2026-05-28T16:03:26.966Z INFO  [...] orchestratePak:489 - operation com.vmware.vcops.casa.upgrade.pak.DeployNewUpgradeContentOperation says it should not run
2026-05-28T16:03:33.166Z INFO  [...] operationName=APPLY_ADAPTER, step=15, totalSteps=19
2026-05-28T16:03:34.536Z INFO  [...] logEvent:60 - Starting operation APPLY_ADAPTER for pakID VCFContentFactoryCompliance-10020
2026-05-28T16:03:57.266Z INFO  [...] logEvent:58 - Completed operation APPLY_ADAPTER for pakID VCFContentFactoryCompliance-10020
```

The 16:48 reinstall run shows the same `says it should not run` message
for step 5 — this is consistent behavior, not a transient.

### `/storage/vcops/log/analytics-0ad8f158-5363-48d4-b6d0-2b50057b279c.log`

`DistributedTaskInstallUninstallAdapters` only processes:
- `processSymptomsAndProblems` — 2 symptoms, 1 alert, 3 recommendations
- adapter kind describe, traversal specs
- No `ViewDef`, `ContentImport`, `DashboardImporter`, `Compliance Host Overview`,
  or `Compliance Fleet Overview` references appear anywhere in the window.

### Pak structure (local `dist/vcfcf_sdk_compliance.1.0.0.20.pak`)

```
manifest.txt
adapters.zip                                    <- processed by step 15
content/dashboards/VCF_Content_Factory_Compliance_Fleet_Overview/dashboard.json   <- IGNORED
content/reports/VCF_Content_Factory_Compliance_Host_Overview/content.xml          <- IGNORED
content/{alertdefs,symptomdefs,...}/                                              <- empty, IGNORED
```

`adapters.zip` interior contains `vcfcf_compliance/conf/views/views.zip` with
the view `[VCF Content Factory] Compliance Host Overview` (`ViewDef
id=a9a4a2bc-0e61-448c-a72c-0bebea2b7961`). This file gets extracted to
`/usr/lib/vmware-vcops/user/plugins/inbound/vcfcf_compliance/conf/views/views.zip`
but **the SDK install path does not invoke any ViewDef import** on it during
this run (analytics log has zero references).

## Implications for code

The packager (`vcfops_packaging/builder.py` or equivalent for SDK adapter paks)
is building a pak that mixes two incompatible distribution shapes:

- **SDK adapter pak (6.x format):** only `adapters.zip` is honored. Content
  must travel inside `adapters.zip` and be hooked into the adapter's describe.
- **Content/MP pak:** `content/` tree at pak root is processed by
  `DeployNewUpgradeContentOperation`, but the pak orchestrator decides this
  step does not run for adapter-only paks where `forceContentUpdate` and the
  `content/` tree are not declared in a way the step's `shouldRun()` accepts.

To get the dashboard and view installed alongside this SDK adapter, one of:

1. **Make the orchestrator run step 5.** Discover what triggers
   `DeployNewUpgradeContentOperation.shouldRun()` to return true. Likely a
   manifest field (e.g. an explicit content list, or a different
   `pak_format`) is needed.
2. **Move content into the adapter's `conf/` tree** so it ships inside
   `adapters.zip` and is published by the adapter's describe (the view's
   `views.zip` is already located here — but isn't being imported either,
   so this path also needs investigation).
3. **Ship two paks** — the SDK adapter pak and a separate content pak —
   so the content pak's manifest triggers step 5.

The `says it should not run` decision happens in the orchestrator's
`shouldRun()` for `DeployNewUpgradeContentOperation`. Worth grepping
Aria source / scripts under `/usr/lib/vmware-vcopssuite/utilities/pakManager/`
for the criterion, but that is a follow-up; the evidence above is sufficient
to conclude that the dashboard never reached the importer (so it cannot be a
slash/folder issue or an unknown-resourceKind issue at this layer).

## Follow-ups

- Examine `DeployNewUpgradeContentOperation.shouldRun()` criteria — what does
  it look for in the manifest or pak contents to decide?
- Why does the SDK describe pipeline ignore `conf/views/views.zip`? Other SDK
  adapters in this repo (`mpb_vcf_content_factory_*`) successfully ship views
  — check what differs in their manifest / describe.xml.
- Confirm whether the v17/v18/v19 paks of this same product had the same
  layout, and if not, what changed at v20 to break the prior install.

## 2026-05-28 (later) — Reference-pak comparison invalidates the step-5 hypothesis

### Method

Pulled manifest.txt and full pak structure for 5 reference paks shipped by VMware
9.0.2.0 that DO install dashboards/views/reports alongside an SDK adapter from the
appliance dist tree `/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/`:

| Pak | Adapter kind | Ships in `content/` | `pak_format` (per `.results`) |
|---|---|---|---|
| `VCFAutomation-902025137921.pak` | VCFAutomation | 2 dashboards + 2 reports | (not extracted, but same structure) |
| `VCFDiagnostics-902025137871.pak` | DiagnosticsAdapter | alertdefs + solutionconfig | same |
| `NetworkInsightAdapter-902025137914.pak` | NETWORK_INSIGHT | content/ + files/ | same |
| `ManagementPackforStorageAreaNetwork-902025137912.pak` | VirtualAndPhysicalSANAdapter | **2 dashboards, customgroups, alertdefs, reports** | **`6.x`**, `contains_system_update: false`, `deploy_new_upgrade_content_result: "no results"` |
| `SynologyDSM-1001.pak` (community) | mpb_synology_dsm | content/ skeleton | **`6.x`**, same as SAN |

### Manifest fields — side-by-side

Every reference manifest declares exactly the same top-level fields ours does:
`display_name`, `name`, `description`, `version`, `vcops_minimum_version`,
`disk_space_required`, `eula_file`, `platform`, `vendor`, `pak_icon`,
`pak_validation_script` (often `{"script": ""}`), `adapter_pre_script`,
`adapter_post_script`, `adapters`, `adapter_kinds`, `license_type`.

**None** declare `pak_format`, `content_format`, `system_update_script`,
`deploy_new_upgrade_content_script`, or any content-tree flag. Ours doesn't
either. There is **no manifest difference** between paks that trigger step 5
and paks that don't.

### `shouldRun()` decompiled

`/usr/lib/vmware-casa/casa-webapp/.../DeployNewUpgradeContentOperation.class`
(decompiled with `javap -p -c`) implements `shouldRun()` as exactly:

```java
PakManDetail detail = pakCommand.queryDetailsOfStagedPak(pakID, null);
return detail.isContainsSystemUpdate();
```

The flag `containsSystemUpdate` is populated in `vcopsPakManager.py` by:

```python
systemUpdateScript = self.pak.loadManifestScriptsValue(
    Actions.APPLY_SYSTEM_UPDATE.manifestScriptKey, 'system_update')
containsSystemUpdate = bool(systemUpdateScript)
```

i.e. true only if the manifest declares `"system_update_script": {"script": "..."}`
with non-empty contents. **This is the platform OS/system-update path used by
core paks like `vim-902025137884.pak` (vSphere) and `vcf-902025137906.pak` (VCF
platform).** Solution / management-pack manifests never set it.

### The smoking gun — peer pak results files

`/storage/db/pakRepoLocal/<pak>/<pak>.results` for the SAN MP and SynologyDSM
(both ship `content/` at pak root, SAN is known-working with dashboards visible
in the UI):

```
"pak_format": "6.x",
"contains_system_update": false,
"deploy_new_upgrade_content_exit_code": "",
"deploy_new_upgrade_content_result": "no results",
```

The SAN MP — which installs dashboards, custom groups, reports, alertdefs from
its pak-root `content/` tree — has the **identical** step-5 outcome as our v20
pak. Step 5 is skipped for **every solution pak in the corpus**, including ones
that successfully install all their content. The "says it should not run" log
line is normal noise, not the failure signal.

Additionally, `pakManager.actions.log` for 2026-04-17 shows
`DeployNewUpgradeContentOperation says it should not run` for non-system-update
paks installed that day — same outcome, different paks, dashboards installed
fine.

### Corrected diagnosis

**Step 5 is not the path content reaches the importer.** For SDK adapter paks
the orchestrator step that delivers `content/` is **step 15, `APPLY_ADAPTER`**,
which delegates to `DistributedTaskInstallUninstallAdapters`. That task is run
on a `DistTaskSolutionManagerDistributedTask` thread (visible in
`/storage/vcops/log/analytics-*.log.*` calling
`ContentImport.importFile` shortly after the casa orchestrator records
`Starting operation APPLY_ADAPTER`).

Our v20 install:
- DID run APPLY_ADAPTER (23s) — symptoms, alert, recommendations all imported.
- DID NOT see `ContentImport.importFile` for the dashboard or report (verified
  by the analytics log — zero references in the install window).

So the real question is: **why did SolutionManager skip the pak-root `content/`
tree for our pak when it processes that same tree for SAN, VCFAutomation,
Synology, etc.?** The "step 5 didn't run" story was a red herring — the
orchestrator-level operation is irrelevant. The fault is inside the APPLY_ADAPTER
content-import path, not in the orchestrator's step gate.

### Likely real differentiators (worth investigating next)

These differ between our pak and the reference paks and are now the top
candidates for the actual gate:

1. **Empty `content/` subdirectories.** Our pak ships
   `content/{alertdefs,symptomdefs,recommendations,supermetrics,customgroups,policies,traversalspecs,files}/`
   as empty entries plus the populated dashboards/reports. SAN, VCFAutomation,
   etc. only ship populated subdirs (e.g. SAN has alertdefs/customgroups/dashboards/files/liqueryconfigs/reports/resources, no empties).
   SolutionManager may walk the tree and bail on empty/unexpected directories.
2. **Missing `content/resources/resources.properties`.** SAN ships a giant
   per-locale resources tree; we ship `resources/resources.properties` at pak
   root (not under `content/`). Importers commonly key off
   `content/resources/`.
3. **Missing `content/dashboards/dashboards.properties`.** SAN's dashboards
   tree includes a top-level `dashboards.properties`. Our tree has only the
   per-dashboard slug subdirectory.
4. **`overview.packed` absent.** SAN and VCFAutomation ship `overview.packed`
   at pak root. Ours does ship `overview.packed` (576 bytes) — so this one is
   not differential.
5. **`files/` subtree absent.** SAN and VCFAutomation declare `files/` at pak
   root (often empty). Ours has `content/files/` but no `files/`. The
   SolutionManager describe path may look at pak-root `files/` for some kinds
   of content (resource-kind metric definitions, solutionconfig overrides).

### Recommendation

The investigation should pivot to APPLY_ADAPTER / SolutionManager content
ingestion. Specifically:

- Capture an `APPLY_ADAPTER` analytics-log slice for a successful SAN-like
  install vs. our failing install and diff the `SolutionManager` /
  `ContentImport` call traces. The SAN logs are not in the appliance's live
  log retention (rotated past `.11`) but a fresh repro by uninstalling and
  reinstalling SAN or another small content-shipping pak would surface the
  expected trace shape.
- Try a minimal test pak: take our exact v20 layout and ADD a populated
  `content/files/reskndmetric/` file (any text) — see if SolutionManager
  starts walking the tree.
- Try removing the empty `content/` subdirectories so only populated ones
  remain. If the importer scans `content/` directory-first and aborts on
  unexpected empty dirs, this will flip behavior.
- Inspect the SolutionManager class (likely in
  `tomcat-enterprise/webapps/vrops-unicorn/WEB-INF/lib/*solutionmanager*.jar`)
  to find the actual content-walk implementation.

### What this means for the original note

The "Root cause" and "Implications for code" sections above are wrong about
step 5 being the gate. Keep them as the original hypothesis trail for posterity,
but treat **this section as the current state**: the manifest is fine, the
pak shape is fine, the orchestrator step-5 skip is fine — the failure is inside
APPLY_ADAPTER's content walk, which is a different beast.

### Reference pak locations on disk

All on `vcf-lab-operations-devel.int.sentania.net`:
- `/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/VCFAutomation-902025137921.pak`
- `/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/VCFDiagnostics-902025137871.pak`
- `/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/NetworkInsightAdapter-902025137914.pak`
- `/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/ManagementPackforStorageAreaNetwork-902025137912.pak`
- `/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/SynologyDSM-1001.pak`

Extracted (post-install) tree for SAN comparison:
- `/storage/db/pakRepoLocal/ManagementPackforStorageAreaNetwork-902025137912/`
- `/storage/db/pakRepoLocal/SynologyDSM-1001/`
- `.results` file inside each shows the post-stage flag values.

Our pak: `/home/scott/projects/vcf-content-factory/dist/vcfcf_sdk_compliance.1.0.0.20.pak`.

HCX manifest (older extraction, structure only): `/tmp/pak-manifest/manifest.txt`
— full HCX/SRM paks are NOT present on this appliance and could not be diffed
against; HCX manifest structure matches the corpus (no `system_update_script`,
no `pak_format` declared in manifest).

### Cleanup

Read-only investigation. No state was mutated. The class files copied to
`/tmp/DeployNewUpgradeContentOperation.class` and `/tmp/PakManDetail.class`
on this workstation are decompilation artifacts and may be removed at the
operator's discretion.
