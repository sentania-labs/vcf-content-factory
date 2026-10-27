# Framework review: SDK bundled-content checks + alert sub_type enum (2026-10-27)

Branch `sdk-bundled-content-checks`, uncommitted diff. Reviewer: `framework-reviewer`.

**Verdict: APPROVE** (0 BLOCKING / 3 WARNING / 4 NIT).

## Scope

- `src/vcfcf_managementpacks/sdk_builder.py`: `check_bundled_content()` (references + describe.xml conformance), called by `validate_sdk_project`, `build_sdk_pak` (pre-compile); `_write_outer_pak` keeps the reference half.
- `src/vcfcf_core/alerts/loader.py`: `VALID_SUBTYPES` = 18-22, default 19.
- `content/alerts/synology_*_alert.yaml` (6 files): 1→18, 2→20, 3→19.
- `.claude/agents/alert-author.md`, `knowledge/context/tier2_architecture.md`, `knowledge/context/wire-formats/alertdef_symptomset_import.md`, tests (new `tests/managementpacks/test_sdk_bundled_content_checks.py`, three fixture edits).

Out of scope per brief: `third_party/idps-planner/PROJECT.yaml`, `content/sdk-adapters/*`.

## Checks re-run (independently)

- Validate chain (7 packages): all rc=0. `vcfcf_managementpacks validate`: 4 SDK projects valid.
- Test suite: **3063 passed, 5 skipped**, 0 failed.
- `validate-sdk` per clone: compliance OK, synology OK, template OK, unifi (branch `feat/poe-budget-used-pct`, dirty tree) OK. cluster-perf-risk and vsanhostmetrics have no `adapter.yaml` (Python packs, not applicable).
- Render regression: no renderer touched. The only emitted-output change is `subType` on the six synology REST alerts (intended). No alert in `content/` or `third_party/` omits `sub_type`, so the 3→19 default change affects no corpus output.
- pak-compare: n/a (checks are read-only; built pak bytes unchanged).
- Stale-zip / version stamp: no file in the stale list touched; templates untouched, so no `CURRENT_TEMPLATE_VERSION` bump due. No bundle in `bundles/` ships the synology alerts.

## Real-pak exercise (how much the green actually proves)

| Pak | bundled symptoms/alerts | What the new checks actually read |
|---|---|---|
| compliance | 0 / 0 (9 views, 5 dashboards) | Nothing. Its 144 stitched VMWARE alerts / 146 symptoms live in describe.xml, not `bundled_content`; only the pre-existing `_validate_describe_symptom_sets` sees them. "Compliance passes" is vacuous for this change. |
| synology | 0 / 0 | Nothing. |
| template | 0 / 0 | Nothing. |
| unifi | 14 / 8, 6 recs | Real exercise: all keys, kinds, metric/property matches, SELF sets. Passes. Alerts use 18/19/20. |

So unifi is the only real-pak positive control. The managed-pak test (`test_managed_paks_pass_the_content_checks`) skips in CI because the clones are gitignored.

## Synthetic probes (unifi project, one symptom mutated, alerts removed)

| Probe | Result | Correct? |
|---|---|---|
| `badge|health` metric | pass | yes |
| `Super Metric|sm_abc` | pass | yes |
| `System Attributes|availability` | pass | yes |
| `Status:foo|state_code` (instanced) | pass | yes |
| `metric_static` on property `Status|state_code` | reject | yes |
| `Status|nope` | reject | yes |
| resource_kind `Nope` | reject | yes |
| `Capacity Analytics Generated|timeRemaining` | reject | debatable (NIT 1) |
| `summary|parentHost` property | reject | yes for an SDK kind |
| VMWARE/VirtualMachine `cpu|usage_average`, pak never names VMWARE | reject | false rejection class (WARNING 3) |

describe.xml structure of all four paks: no duplicate ResourceKind keys, no instanced groups, foreign `adapterKind` only on compliance SymptomDefinition/AlertDefinition (VMWARE). ComputedMetric keys are full paths (compliance describe.xml:134), matching the index's `prefix + key`.

## Findings

### BLOCKING

None.

### WARNING

1. **`.claude/agents/alert-author.md:117-118`**, authority: vendor `alertDefinitionSchema.xsd` subType enum / `wire-formats/alertdef_symptomset_import.md` §Alert subType enum. The YAML reference section still reads "Subtypes: 1=Availability, 2=Capacity, 3=Performance, 4=Compliance, 5=Configuration", contradicting the edited lines 32-36 and the loader. An author reading the reference table writes YAML that now fails validate (loud, but a guaranteed wasted round). Fix: replace with 18 Availability, 19 Performance, 20 Capacity, 21 Compliance, 22 Configuration.

2. **`knowledge/context/tier2_architecture.md:1118`** (new row, Adapter adoption), authority: observed re-run. Says "unifi's bundled alerts use `sub_type` 1-3 and fail until moved to 18-22". Observed: unifi on `feat/poe-budget-used-pct` uses 18/19/20 and `validate-sdk` passes. The same sentence's "compliance, synology and template pass" is true but vacuous: none of them bundles a symptom or alert. Fix: state that unifi already uses 18-22 and passes, and that compliance/synology/template bundle no symptoms/alerts so the checks do not read them.

3. **`src/vcfcf_managementpacks/sdk_builder.py` `_adapter_kind_error`** (in `check_bundled_content_against_describe`), authority: `sdk_project.py:13` / `docs_gen.py:434-467` (`cross_mp_edges` is a documentation stanza rendered as "Cross-MP relationships" in the generated docs). A bundled symptom/alert on a built-in adapter kind that the pak does not stitch (e.g. VMWARE VirtualMachine `cpu|usage_average`) is a hard error, and the error's only remedy is naming the kind in describe.xml or `cross_mp_edges`. The second means inventing a relationship that then appears in the pak's published docs. No current pak hits it, but it is a false rejection with no honest escape. Fix (smallest): an explicit adapter.yaml opt-in list of foreign adapter kinds for bundled content (or a `bundled_content` sibling key), checked here alongside describe.xml/`cross_mp_edges`, and the error message names it instead of `cross_mp_edges`.

### NIT

1. **`sdk_builder.py` `_PLATFORM_METRIC_GROUPS`**: closed allowlist (`badge`, `System Attributes`, `Super Metric`, `System Properties`). Capacity-engine groups (`Capacity Analytics Generated|`, `OnlineCapacityAnalytics|`) are rejected (probed). Whether the platform emits them on SDK kinds is unproven either way; the failure is loud and names the key. Fix: add them, or name the closed list in the error text so the author knows the allowlist is the cause, not a typo.

2. **`src/vcfcf_core/alerts/loader.py:585`** `int(data.get("sub_type", 19) or 19)`: an explicit `sub_type: 0` silently becomes 19 instead of failing the new enum check (pre-existing `or` pattern, on a touched line). Fix: default only when the key is absent or `None`.

3. **`content/alerts/vm_cpu_usage_alert.yaml:15`, `content/alerts/host_compliance_score_alert.yaml:17`**: comment labels 20 "Workload"; per the XSD 20 is Capacity. Value unchanged and valid; comment only. Sibling files to the ones this branch edits; fix the comment in the same round.

4. **`src/vcfcf_packaging/templates/install.py:2370`** `alert_data.get("sub_type", 3)`. Judgment as asked: **does not need to change in this PR.** It is dead: `assembly.py:176` always writes `sub_type` from a validated `AlertDef`, and every distributed zip carries its own embedded `install.py` paired with its own payload, so no zip can reach the fallback. Changing it forces a `CURRENT_TEMPLATE_VERSION` bump and a full `content-packager` rebuild for zero operator-visible effect. The branch does not touch templates, so per delegation rule 9 this is a follow-up issue: change the fallback to 19 (or drop it) with the next templates change.

## sub_type remap: effect on existing installs

The six synology alerts are factory REST content (`mpb_synology_dsm`), not in any bundle.

- **Identity unchanged.** `vcfcf_alerts` sync upserts by name and PUTs with the existing id (`src/vcfcf_alerts/client.py:117-119`); the content-import id is `AlertDefinition-<adapter>-<slug(name)>` (`vcfcf_core/alerts/render.py:107`). `sub_type` feeds neither. Policy enablement, symptom sets, impact badge, recommendations, and active-alert linkage are unchanged.
- **Category changes, on next sync only.** Before: subType 1/2/3, which are not platform subtypes (no category). After: 18 Availability, 20 Capacity, 19 Performance. Visible effects: the Subtype column/filter in the alert list, and any notification rule or alert-list widget filtering on alert type + subtype (e.g. Hardware/Availability) now matches these alerts where it could not before. That is the intended fix, but an operator with such a rule will start getting notifications from them after the resync. Nothing changes on an instance until the alerts are re-synced.

## Versioning

`BUILDKIT_VERSION` stays 1.0.20; #281 (1.0.21) is open and unmerged. The kit ships `sdk_builder.py` and `alerts_loader.py` (regex rewrites at `buildkit.py:224-242` cover the moved `_symptom_id` import unchanged). Built pak bytes are unchanged, so no staleness signal is owed; pak CI just lacks the new guards until the next kit. Whichever of this PR and #281 merges second should make sure its kit bump carries these files. Observation, not a finding.

## Test coverage

`test_sdk_bundled_content_checks.py` covers both commands (validate and build) for each rejection, platform groups, ComputedMetrics, CHILD-set pass, both stitched-VMWARE pass shapes, unnamed foreign kind, the describe index, sub_type accept/reject/default, and a pak-bundled bad sub_type. Adequate. Gap: no test for an instanced `Group:inst|attr` key (probed by hand: passes).
