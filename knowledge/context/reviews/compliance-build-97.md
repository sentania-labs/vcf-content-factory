# Compliance build 97 review

- **Reviewer:** sdk-adapter-reviewer (read-only, static, pre-install)
- **Date:** 2026-10-24, 00:40 Central
- **Adapter:** `content/sdk-adapters/compliance/`, branch `feat/177-scg-regen-62`, 5 commits on `origin/main` (0.0.0.96): `32f0c7d` (#177), `9a0f685` (factory #169, #170), `4d5d9e8` (compliance #62), `82e5cd8` (factory #229), `9266b11` (build 97 bump). HEAD `9266b11`, clean tree.
- **Pak reviewed:** the author's `vcfcf_sdk_compliance.0.0.0.97.pak` (built 2026-10-24 00:26 Central, sha256 `53d1fa82...1b729c`), reference `dist/vcfcf_sdk_compliance.0.0.0.96.pak`.

## Verdict: APPROVE (0 BLOCKING, 5 WARNING, 4 NIT)

The scoring change is correct. `vm.virtual-hardware` now scores as a floor on every profile that has it, and a VM at vmx-17 or vmx-21 passes on 8.0, 9.0 and 9.1 while vmx-13 fails (7.0 keeps its vmx-13 floor, so vmx-13 passes there). The scored control set is unchanged (136), the unreadable path is unchanged, 6.7, 7.0 and 9.1 are byte-identical, and all five canonical profiles regenerate byte for byte from the committed vendor CSVs, which match upstream `ea455b0` exactly. No em-dash was added.

The warnings are about what the operator reads, not about scores: one new recommendation (vc.vami-password-max-age) points at a setting the adapter does not read, one existing recommendation (vm.virtual-hardware) is a PowerShell line that runs nothing when pasted, the #177 widget change is not yet seen on screen, the README still calls that same widget broken, and the CHANGELOG does not mention that this pak is the first to ship framework 1.0.15.

## Independent verification

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` on a clean `git archive HEAD` tree (JDK 17.0.20.1) | Exit 0. 26 `*Test.java` "all assertions passed", Python checks OK. SimpleJson parity skips in the archive and passes in the real clone (4 tests OK). **Confirmed.** |
| `generate_compliance_alerts.py --check` | Up to date: 136 scored controls, 136 symptoms, alerts and recommendations, 6 collection alerts, 1 overrides alert. **Confirmed.** |
| `validate-sdk` | OK, exit 0. Two pre-existing warnings: two dashboard names are 53 characters (issue #198, N4). 9.1.1.0100 compat leg skipped (jar not present). **Confirmed.** |
| `build-sdk` | Built 0.0.0.97. Every file in the author's pak, unpacked recursively (pak, adapters.zip, both jars, overview.packed), is byte-identical to mine. **Confirmed.** |
| `pak-compare` 0.0.0.97 vs 0.0.0.96 | PASS, 0 BLOCKING / 0 WARNING / 0 INFO. **Confirmed.** |
| Canonical regeneration | All five normalizers (`scripts/normalize_scg_v67/70/80/90/91.py` over the factory's #243 pipeline) reproduce `profiles/canonical/scg_*.csv` byte for byte. |
| Vendor provenance | `vmware_scg_8.0.csv` and `vmware_scg_9.0.csv` are byte-identical to `git show ea455b0:` of the upstream files named in CANONICAL_SCHEMA.md (local clone `reference/references/vcf-security-and-compliance-guidelines`). No later upstream commit touches either CSV. |
| 6.7, 7.0, 9.1 profiles | Vendor and canonical CSVs unchanged on the branch (`git diff origin/main HEAD` empty). |
| Bytecode | Adapter jar and framework jar are class major 55 (Java 11). `ControlEvaluator*.class` differ from 96 only in the line table (`javap -c -p` identical): the source change is a comment. |
| `--release 11` | Adapter source compiles clean with `javac --release 11` (against the test stubs). Framework source does not (see N4). |
| describe.xml | Unchanged from 96, so dimension 13 (SymptomSet structure) is not triggered. |
| Em-dashes | None in any added line. Six removed by the docs regenerator (docs/README.md, docs/inventory-tree.md). |

## What changed in the pak (97 vs 96)

- `conf/profiles`: canonical and vendor 8.0 and 9.0, UNAUDITED_CONTROLS.md.
- `resources.properties` (both copies): only nameKey 1359 (vc.vami-password-max-age recommendation).
- `ControlEvaluator` (comment only), version stamps, overview version line.
- Environment Overview dashboard: one key, widget 3.
- `lib/vcfcf-adapter-base.jar`: framework 1.0.15 (`X-Vcfcf-Source-Commit 8ad0911`), not touched by this branch but new in this pak (W1).

## Hunt items from the brief

**vmx-17 or higher, scored through the real evaluator.** I loaded each bundled profile with `BenchmarkLoader.loadAll` and ran `ControlEvaluator.evaluateVimProperties` on the profile's own `vm.virtual-hardware` row:

| Profile | Expected | vmx-13 | vmx-17 | vmx-21 | vmx-22 | garbage | unreadable |
|---|---|---|---|---|---|---|---|
| SCG 6.7 | (control not in profile) | | | | | | |
| SCG 7.0 | `vmx-13 or newer` | PASS | PASS | PASS | PASS | FAIL | unreadable 1, total 0 |
| SCG 8.0 | `vmx-17 or higher` | FAIL | PASS | PASS | PASS | FAIL | unreadable 1, total 0 |
| SCG 9.0 | `vmx-17 or higher` | FAIL | PASS | PASS | PASS | FAIL | unreadable 1, total 0 |
| SCG 9.1 | `vmx-17 or higher` | FAIL | PASS | PASS | PASS | FAIL | unreadable 1, total 0 |

- The parser: `VMX_MINIMUM` (`ControlEvaluator.java:57`) and `VMX_VALUE` (`:60`), compared as integers in `vmxMinimumMatches` (`:730-742`), so vmx-9 is below vmx-13. A value that is not `vmx-<digits>` fails, never passes.
- `vimPropertyMatches` reaches it only after the caller has removed the unreadable sentinel and null (`:524-541`). An absent `config.version` is UNREADABLE from `readScalarRecipe` (`VSphereClient.java:1211-1221`, empty text sets `readFailure`). Unchanged.
- Tests: `ControlEvaluatorTest` covers 21, 17 and 15 against a 17 floor and 9 against 13. `ProfileSetTest` now asserts the minimum mode on 7.0, 8.0, 9.0 and 9.1, and the literal `vmx-17 or higher` on 8.0, 9.0 and 9.1, so a regression to the bare value fails.
- Operator effect on upgrade: on 8.0, VMs at vmx-17 to 20 and at vmx-22 or later stop failing. On 9.0, everything at vmx-17 or later except vmx-19 stops failing. Their open alerts cancel after three cycles. The CHANGELOG says so.

**Scored set.** Comparing every scoring column (`control_id`, `parameter`, `parameter_kind`, `value_type`, `expected_value`, `read_recipe`, `resource_kind`, `priority`) between 96 and 97: 8.0 changes only the vm.virtual-hardware expected value. 9.0 changes that too, plus three unscored rows that swap between `powercli_only` and `manual_audit` with no recipe (`vc.content-library-authentication`, `vc.content-library-ovf`, `vc.vami-firewall-restrict-access`). No recipe was added or removed, so the evaluable set was not widened or narrowed.

**Unreadable is not compliant on the touched controls.**
- vm.virtual-hardware: unchanged path, shown in the table.
- vc.vami-password-max-age: recipe unchanged (`vami:local-accounts/root:max_days_between_password_change?absent=-1`). The `?absent=-1` default applies only to a successful 200 JSON body that lacks the field, per CANONICAL_SCHEMA.md and the appliance spec ("If unset, password never expires"). Any failure stays UNREADABLE.

**vc.vami-password-max-age recommendation.** It is the vendor's 9.0 command verbatim, but it is not proven to fix what the adapter reads (W2).

**`selectFirstRow: false`.** In the built `dashboard.json` the only change from 96 is `widgets[3].config.selectFirstRow.selectFirstRow` true to false. Widget 3 ("Compliance by vCenter and Object Type") is the sole `widgetIdProvider` for the AlertList ("Open Compliance Alerts", `selfProvider: false`). The other two View widgets on the page (Objects with Unreadable Controls, Objects by SCG Version) keep `true`, and no other dashboard changed. Correct widget only. Whether it renders as intended is W4.

**RULE-019 (8.18, 9.0, 9.1, Java 11 bytecode).**
- Nothing on the branch is 9.x-only. It is profile data, one dashboard boolean that the vendor's own Cluster Performance dashboard uses, a comment, and YAML.
- The shipped classes are Java 11 bytecode, and the adapter source compiles with `--release 11`.
- Only the primary compile leg ran. The 9.1.1.0100 leg was skipped and there is no 8.18 leg yet (factory #252).
- The release section of RULE-019 still binds: a `v*` tag needs the three-line install record (devel_8_18, devel, devel_9_1).
- The framework jar carries a Java 16 call, but compliance cannot reach it (N4).

## Findings

### BLOCKING

None.

### WARNING

**W1. The pak ships framework 1.0.15 and the build 97 CHANGELOG does not say so.**
- Where: `CHANGELOG.md` build 97 lines. The delta is visible in the pak at `lib/vcfcf-adapter-base.jar` (manifest `Implementation-Version 1.0.15`, source `8ad0911`). Seven classes were added and seven changed against 96's jar.
- Why it matters: factory #237, #248 and #251 land in this pak for the first time, and ComplianceAdapter extends VcfCfAdapter, so they change what an operator sees:
  - The adapter instance now goes ERROR (or DOWN) with a one-line reason when every resource fails (`VcfCfAdapter.java:2720-2760`). Compliance collects one resource, so any thrown cycle now flips the account status.
  - Push failures are logged as one line, the principal is no longer in the logs, and there is FIPS truststore handling.
- Precedent: builds 52, 53, 54, 83, 84 and 86 each recorded the framework jar they carried. Authority: author hard rule 9 (matching CHANGELOG line); review dimension 9.
- I checked compatibility: the two new exception types (`SuiteApiHttpException`, `SuiteApiStitchClient.ClientClosedException`) extend `IOException`, so the stitcher's existing catches still hold. The framework change itself went through framework-reviewer (the review record is in commit `acd7818`).
- Fix: one CHANGELOG line naming framework 1.0.15 and the account-status behavior.

**W2. The new vc.vami-password-max-age recommendation is not proven to clear its own alert.**
- Where: `resources/resources.properties:393` (nameKey 1359), from `profiles/canonical/scg_9.0.csv` (vendor row `vcenter-9.vami-password-max-age`).
- What changed: the text now reads `(Get-CisService -Name "com.vmware.appliance.local_accounts.policy").set(@{max_days=-1})`. In 96 it said honestly that the guide gives no command.
- Why it may not work:
  - That command sets the appliance's global local-accounts policy. The adapter scores the root account's own `max_days_between_password_change` (`GET /api/appliance/local-accounts/root`).
  - Nothing on record shows that the global policy rewrites an existing root account's setting.
  - The vendor's own 9.1 tooling audits and fixes the policy, not root, and with 9999, not -1 (`reference/references/vcf-security-and-compliance-guidelines/security-configuration-hardening-guide/cloud-foundation/9.1/tools/remediate-vcenter-9.ps1:681-693`).
- What the operator would see: an alert whose recommended fix leaves the alert open. This is not a false pass. Alert 1356 (vc.vami-administration-password-expiration, 7.0 and 8.0) already ships the same text, so this extends an existing unproven claim to two more profiles.
- Authority: skeptic default (unproven is a finding); `knowledge/rules/no-fabricated-metrics.md` in spirit (do not claim a fix the data does not support).
- Fix: on a devel vCenter, read `local-accounts/root` before and after the policy `set`. If root does not change, add a generator note on this control naming the root-account field and its fix (an update of the `root` account with `password_expires` false), or fall back to the 96 "no command" text. **Registration candidate** if it ships unproven.

**W3. The vm.virtual-hardware recommendation is one PowerShell line that does nothing when pasted.**
- Where: `resources/resources.properties:354` (nameKey 1320). The text is unchanged from 96 and comes from SCG 9.1. This build copies the same vendor script into the 8.0 and 9.0 canonicals (`profiles/canonical/scg_8.0.csv`, `scg_9.0.csv`, vm.virtual-hardware `remediation_text`).
- Why it does nothing:
  - The normalizer joins the vendor's multi-line script with ` ; `, and the generator collapses whitespace (`generate_compliance_alerts.py`, `" ".join(rem.split())`).
  - The result starts with `# Upgrade the VM ...`. In PowerShell `#` comments out the rest of the line, so the whole recommendation is one comment.
  - Even with the leading comments removed, `$spec.Version = $max # to pin ... ; $vmObj.ExtensionData.ReconfigVM_Task($spec)` comments out the reconfigure call.
- What the operator would see: a recommendation that silently does nothing.
- This is pre-existing (96 shipped the same 1320), but #62 was the moment to catch it, and it applies to every multi-line vendor script containing `#`.
- Authority: dimension 10 (gap honesty: do not present a fix that is not one).
- Fix: in the factory normalizer, drop whole-line `#` comments and strip trailing `# ...` before joining, or keep line breaks in the recommendation. Then regenerate. **Registration candidate** (`Affects: compliance`).

**W4. The #177 change is not yet seen on screen.**
- Where: `dashboards/compliance-environment-overview.yaml:140`.
- The evidence it cites (`knowledge/context/wire-formats/dashboard_sort_color_default_summary_rows.md`, #177 row) rates its own confidence as "seen in export (vendor dashboard) plus UI source; on-screen render not checked".
- If an AlertList with no input does not fall back to all matching alerts on some line, the overview now opens with an empty alert list, which is worse than 96 (first vCenter's alerts).
- With no selection the list is also environment-wide for type 15/21, not "on the selected object and its children" as `docs/overview.md:155-160` describes.
- Authority: user rule "done means seen working"; RULE-019 release section.
- Fix: no code change. The devel proof on all three lines must open the Environment Overview and record that W6 lists alerts before a row is clicked and narrows after. Add one sentence about the unselected state to `docs/overview.md`.

**W5. The README still lists the widget this build changes as broken.**
- Where: `README.md:292-302` (Known issues #30, #31, #32) and `README.md:98` ("both of those have open bugs").
- All three issues were closed 2026-10-16 (10:30 AM Central). #31 is "the Open Compliance Alerts widget on the overview is empty", the very widget #177 changes, so the landing README contradicts the shipped behavior.
- Pre-existing, not introduced here. It is WARNING rather than BLOCKING for that reason, and because the operator would only be led to distrust a working panel.
- Authority: dimension 11 (docs parity).
- Fix: remove the three closed entries and the "open bugs" clause, and say W6 shows all compliance alerts until a row is clicked.

### NIT

**N1.** `tests/com/vcfcf/adapters/compliance/ControlEvaluatorTest.java:30`: the comment "Bare vmx-N keeps exact equality (8.0 / 9.0 semantics unchanged)" is now stale. The assertion (bare value is equality, used by overrides) is still right.

**N2.** Recommendation 1320's note says "SCG 7.0, SCG 8.0, SCG 9.0 word the fix differently". 9.0's text is now identical to 9.1's, and 7.0 has no fix at all. `recommendation_text` lists every other scored label rather than the ones whose text differs. Pre-existing generator logic, made visible by this re-ingest.

**N3.** The CHANGELOG #62 line does not mention the three 9.0 unscored rows that swap between `powercli_only` and `manual_audit`. CANONICAL_SCHEMA.md does. Informational rows only.

**N4.** RULE-019 build record and two pre-existing items carried in the pak:
- Build legs: only the primary compile leg ran. The 9.1.1.0100 leg was skipped (jar absent) and there is no 8.18 leg (#252). The builder uses `-source 11 -target 11`, not `--release 11` (`sdk_builder.py:341`, `:707`).
- Framework Java 16 call: compiling the framework with `--release 11` fails at `ManagedHttpClient.java:295`, which calls `HttpRequest.newBuilder(HttpRequest, BiPredicate)` (Java 16). On a Java 11 collector (8.18) that throws `NoSuchMethodError` on the DNS round-robin fallback. Compliance never sends through `ManagedHttpClient`: its tester and collector ignore the `http` argument (`ComplianceAdapter.java:324`, `:839-843`), so it is unreachable for this pak, and 96 had it too. It is reachable in any pak that does use the managed client. **Registration candidate under `factory:framework`**, and #252's switch to `--release 11` will fail the framework compile on this line until it is fixed.
- Dashboard names: two are 53 characters (issue #198).
- Em-dashes: CANONICAL_SCHEMA.md and the shipped UNAUDITED_CONTROLS.md still carry em-dashes from earlier builds (30 and 65). None were added here.

## Registry check (knowledge/context/defects.md)

Open defects with `Affects: compliance`: DEF-025 and DEF-026. Both are unchanged by this build. `src/` changes only a comment in `ControlEvaluator.java`, and `RetiredKeyRepeats.java`, `CycleBudget.java`, `ResumeCursor.java`, `ComplianceAdapter.java` and `ComplianceStitcher.java` are identical to `origin/main`.

- **DEF-025** (retired-key -1 repeats): open. The fix is still in place (`RetiredKeyRepeats.java:46-49`, `MAX_PUSHES = 4`), and the devel half of its close condition is still owed. This build retires no control (scored set unchanged), so its install cannot supply that evidence either.
- **DEF-026** (cycle budget and breaker): open. The fix is still in place (`CycleBudget.java:35`). Still owed: a devel cycle actually cut by the budget on a throttled or unreachable vCenter.

No closure proposed. Registration candidates: W2, W3 (`compliance`), and the N4 framework Java 16 call (`factory:framework`).

## If shipped as-is

Scores are right. VMs at vmx-17 or later stop failing on 8.0 and 9.0, and the open alerts cancel in three cycles. An operator who follows the vm.virtual-hardware recommendation runs a comment, and one who follows the vc.vami-password-max-age recommendation may change a setting the alert does not read. The overview's alert list is expected to show all compliance alerts on open, but that has not yet been seen on screen.
