# Framework review: build-sdk ships conf/logging.properties (factory #313), 2026-11-07

- **Branch:** `worktree-agent-a0e800a2991d96b24`, uncommitted on base `ce34da8`
- **Reviewer:** framework-reviewer (RULE-013)
- **Verdict:** CHANGES REQUESTED, with 1 BLOCKING, 4 WARNING and 4 NIT findings.

## Scope

| File | Change |
|---|---|
| `src/vcfcf_managementpacks/sdk_builder.py` | `_generate_logging_properties`, `_logging_properties_bytes`, and a write into `adapters.zip` |
| `src/vcfcf_managementpacks/sdk_project.py` | `LoggingConfig`, `_parse_logging`, `entry_package`, and the package-collision check |
| `src/vcfcf_managementpacks/buildkit.py` | `BUILDKIT_VERSION` 1.0.24 to 1.0.25 |
| `tests/managementpacks/test_sdk_logging_properties.py` | 21 tests |
| `knowledge/context/tier2_architecture.md` | §Logging and a changelog row |
| `.claude/skills/vcfops-sdk-adapter/SKILL.md` | §Logging |
| `.github/release-notes-buildkit.md` | §1.0.25 |
| `knowledge/context/investigations/2026-11-07-componentlogger-routing.md` | The investigation, copied in |

Authorities used:
- The investigation above.
- SDK bytecode, read with javap. `vrops-adapters-sdk-2.2.jar` is the 9.0 jar in `adapter_runtime/`. `vrops-adapters-sdk-9.1.1.0100.jar` and `-8.18.7.jar` are under `/mnt/holding/vendor/`. The class read is `AdapterLoggerFactoryImpl` and its inner class `$FileAppenderFactory`.
- RULE-005 and RULE-013.
- `pak_compare.py` A1 severities.
- `.github/workflows/publish-buildkit.yml`.
- The pak repos' `build-pak-on-tag.yml`.

## Checks re-run

- **Validate chain.** All seven packages pass in the worktree.
- **Managementpacks tests.** `tests/managementpacks/`: 437 passed, 2 failed, 12 skipped.
  - The 2 failures are `test_gap_b_f_d.py::TestGapFJMESPathPredicates`. They fail the same way on main.
- **Full test suite.** 3260 passed, 15 failed.
  - 9 of the failures also fail on main: the 2 gap tests, the doctor and setup environment tests, and the nested-json recursion test.
  - The other 6 fail only in the worktree: the release-naming and `packaging validate` real-repo tests. The cause is that `content/sdk-adapters/` clones are not present in a worktree (`artifact source not found: content/sdk-adapters/synology/adapter.yaml`). The change does not cause them.
- **Corpus loader.** Every `adapter.yaml` in the main checkout loads under the new loader. None declares `logging:` and none has a source `conf/`. The generated file per pak:

  | Pak | Generated line |
  |---|---|
  | compliance | `com.vcfcf.adapters.compliance=INFO` |
  | synology | `com.vcfcf.adapters.synology=INFO` |
  | template | `com.vcfcf.adapters.example=INFO` |
  | unifi | `com.vcfcf.adapters.unifi=INFO` |
  | vsanperf | `com.vcfcf.adapters.vsanperf=INFO` |

- **Real pak regression.** Synology was built twice, once from main's `src/` and once from the branch's. Each build used its own copy of the source, so the clone was not touched. Comparing the paks with nested zips and jars expanded:
  - The only new entry is `adapters.zip!synology_diskstation/conf/logging.properties` = `b'com.vcfcf.adapters.synology=INFO\n'`. It uses the same compression and attributes as `version.txt`.
  - Every other entry has identical content, except `vcfcf-adapter-base.jar!META-INF/MANIFEST.MF`. That file differs only in `Implementation-Version` (1.0.24 to 1.0.25) and `X-Vcfcf-Source-Commit`, both expected from the bump.
  - The outer `adapters.zip`, the entry jar and `overview.packed` differ in zip metadata only. Their inner contents are identical.
- **Kit path.** I ran `build-buildkit` (VERSION 1.0.25), then `python3 -m sdk_buildkit build-sdk` on synology. The file is present with the same bytes, and the kit's pak-compare is clean.
- **pak-compare.** The branch pak against the main pak gives 0 BLOCKING, 0 WARNING, 1 INFO (`[I1] adapters.zip: 'conf/logging.properties' present in factory, absent from reference`). A1 is INFO for any path outside `_ADAPTERS_BLOCKING_RELATIVE` / `_ADAPTERS_WARNING_RELATIVE`, so this is the intended result.
- **Properties parse.** The generated files for the default, stanza, non-ASCII entry_class, no-package and vendor-style cases load with `java.util.Properties.load(InputStream)`. Every value resolves with log4j `Level.toLevel(v, null)`. `café` round-trips to `café`.
- **SDK reader.** The 2.2 and 9.1.1 SDKs read the file the same way:
  - The path is `<dir of shortest classloader URL>/<jar base>/conf/logging.properties`. The jar base is `adapter_kind`, which equals `adapter_dir_name`, so the path matches.
  - The file is read with `Properties.load(FileInputStream)`. No header is required.
  - `MaxFileSize` and `MaxBackupIndex` are removed before the logger loop. `MaxFileSize` is parsed by `parseSize` (digits, then GB/MB/KB, upper-cased), which matches the new validator. `MaxBackupIndex` is parsed with `Integer.parseInt`.
  - The defaults with no file are 10 MB and 1 backup.
- **Behavioral harness.** `scratchpad/h/H.java` runs the real `vrops-adapters-sdk-2.2.jar` factory against log4j-core 2.26.1. It uses a root WARN rolling appender and builds the factory through a context-classloader jar URL, as `ComponentLoggerTest` does. With no package entry it reproduces the investigation:
  - Helper INFO is dropped.
  - After a Test Connection the adapter class reaches the instance log and is duplicated into collector.log.

  With `pkg=INFO` and no Test Connection, helper INFO reaches the instance log. The #313 fix works.
- **Render regression and template staleness.** Neither applies. No `vcfcf_core` renderer, template or `builder.py` is touched. Tier 2 paks are not factory content zips, so `CURRENT_TEMPLATE_VERSION` does not apply. The staleness signal for Tier 2 is `BUILDKIT_VERSION`, and it is bumped.
- **Hunt items from the brief.**
  - An entry_class with no package keys its own name (`FooAdapter=INFO`). That covers `FooAdapter.<Simple>` framework children and is consistent with `componentLoggerName`.
  - `adapter_kind` is already restricted to lowercase alphanumerics and underscore, so it cannot hold zip-illegal characters.
  - A non-ASCII entry_class is escaped correctly.

## BLOCKING

### B1. Test Connection INFO lines stop reaching collector.log (silent capability change)

- **Location:** `sdk_builder.py` `_assemble_adapters_zip` and every Tier 2 pak. The doc surfaces are `tier2_architecture.md` §Logging, SKILL §Logging and release notes §1.0.25.
- **Authority:** dimension 8. A silent downgrade is BLOCKING; a loud, documented one is at most a WARNING.

Test Connection has no instance appender, so its lines only ever reach `collector.log`. With a `<package>=INFO` entry loaded, the harness shows the following for the Test Connection bare logger after `raiseToInfo`:

| Line | No package entry | With `com.x.pk=INFO` |
|---|---|---|
| `info("TC-OK")` | reaches collector.log | does not reach collector.log |
| `warn("TC-WARN")` | reaches collector.log | reaches collector.log |

The `AdapterLoggerConfig` the SDK builds for the package (`copyAppenders(root, cfg, root.getLevel())`, plain level WARN) now sits between the bare name and root, and INFO stops there.

Effect on shipped code:
- Compliance's `logInfo("Test OK: connected to ...")` (`ComplianceAdapter.java:382`) and the Suite API Test Connection INFO at `:426` will no longer appear anywhere.
- The investigation's own way of timing Test Connections (bare-name lines in collector.log) stops working.

Vendor paks behave the same way, so this is not wrong. But nothing in the change says it.

**Fix:** make it loud, in one sentence each in:
- tier2 §Logging and its changelog row
- SKILL §Logging
- release notes §1.0.25

The sentence should say:
- With the file shipped, Test Connection INFO is dropped. WARN and ERROR still reach `collector.log`.
- Test Connection diagnostics that must be visible belong in the Test Connection result message or at WARN.
- The "bare-name lines in collector.log" Test Connection evidence technique no longer applies to rebuilt paks.

A code change is not required.

## WARNING

### W1. Test Connection still shadows `logging.level: DEBUG` for new accounts, and the collector.log copy remains

- **Location:** tier2 §Logging "a properties entry does not" and the pre-raise rationale; SKILL §Logging; the `sdk_project.py` `level` docstring.
- **Authority:** dimension 8; harness.

Harness with `com.x.pk=DEBUG`, a Test Connection, then a new instance (the add-account flow):

| Logger in the new instance | DEBUG in instance log | INFO duplicated into collector.log |
|---|---|---|
| Adapter class (`I2-AD-*`) | lost | yes |
| Helper never looked up in Test Connection | kept | no |

Instances created before the Test Connection are unaffected. The cause is the unchanged Test Connection `raiseToInfo`: its `Configurator.setLevel(<bare>, INFO)` adds an exact-name INFO entry that is more specific than the package entry. It lasts until the next log4j reload or a collector restart.

The author's reasoning for not adding the adapter-base pre-raise is correct. Through the SDK API, a covered name reads WARN because `AdapterLoggerConfig`'s plain level is the governing WARN. So a pre-raise would add exactly this shadowing entry for every name. But the same mechanism already runs for Test Connection names. The docs read as if the shadowing and the collector.log copy are gone.

**Fix:**
- State the limit in tier2 §Logging, the SKILL and the `level` docstring: a `logging.level` other than INFO applies to names not raised by a Test Connection since the last reload, and the adapter class plus every Test Connection helper is raised.
- Open a follow-up issue for adapter-base: skip `raiseToInfo` on the no-appender (Test Connection) factory, or only raise when no `AdapterLoggerConfig` covers the name. That is Java the branch does not touch. The follow-up must weigh B1, because skipping the raise also drops the Test Connection INFO that #313 already loses.

### W2. The file is inert on 8.18, and the docs do not say so

- **Location:** tier2 §Logging "every Tier 2 pak gets ... That covers every in-package class"; SKILL.
- **Authority:** javap of `vrops-adapters-sdk-8.18.7.jar` (`/mnt/holding/vendor/vcf-ops-8.18.7/extracted-jars/`, also the factory's `_SDK_COMPAT_JAR_NAME_8_18`).

The 8.18.7 `AdapterLoggerFactoryImpl` has:
- no `Properties.load`
- no `MaxFileSize` or `MaxBackupIndex`
- no `conf/logging.properties` string, in that class or anywhere in the jar

It attaches the instance appender with `AdapterLogger.addAppender` and copies the logger's level. The 9.0 (2.2) and 9.1.1 jars both carry the reader. Shipping the file is harmless on 8.18. The routing rule described here is the 9.x rule, and the doc is stated unscoped while 8.18 is a supported line (devel_8_18).

**Fix:** add one sentence to tier2 §Logging and the SKILL: "SDK 2.2 / 9.1.1 only. The 8.18.7 SDK factory never reads `conf/logging.properties`, so the file is inert there, and 8.18 routing is unchanged and unmeasured."

### W3. The adoption note is wrong for released paks

- **Location:** tier2 changelog row "Rebuild every pak to pick it up; no pak source change"; release notes "no source change needed".
- **Authority:** `publish-buildkit.yml`; the pak repos' `build-pak-on-tag.yml:65` (`BUILDKIT_TAG: sdk-buildkit-v1.0.24`) and committed `ci/sdk-buildkit.SHA256SUMS`.

How the version reaches a release:
- Official releases are built by pak CI pinned to 1.0.24.
- `BUILDKIT_VERSION` only sets the factory-mode default kit version and the framework jar `Implementation-Version`. The published kit's VERSION comes from the tag.
- So nothing reaches a release until two things happen:
  1. The `sdk-buildkit-v1.0.25` tag is pushed after merge.
  2. Each pak repo bumps `BUILDKIT_TAG` and its SHA256SUMS file. That is a pak-repo change.

Nothing in the factory's release path is broken by the bump: `publish-buildkit.yml` is tag-driven and the release-notes template is version-agnostic.

**Fix:** give the changelog row the usual **Versioning:** and **Adapter adoption:** fields. They should say: tag `sdk-buildkit-v1.0.25` after merge, then bump each pak's pin and SHA256SUMS, then rebuild (compliance and vsanperf benefit immediately).

### W4. The branch is one commit behind main

- **Location:** worktree base `ce34da8`; main is `252845d` (#319).
- **Authority:** RULE-013 workflow.

`git diff main` shows this branch reverting #319: `installer.py`, `tests/test_install_account_restart.py`, `.claude/agents/content-installer.md` and its review file. The new tier2 changelog row is also inserted at the same spot as #319's row.

**Fix:** rebase onto main before opening the PR. Keep #319's row and order the 1.0.25 row above it by date.

## NIT

- **N1.** `sdk_project.py` `load_sdk_project` computes `_dot` and `_package` inline, duplicating `SdkProjectDef.entry_package`. **Fix:** use one helper for both.
- **N2.** A source `conf/logging.properties` ships unchecked. Any non-ASCII byte is read as ISO-8859-1, and an unknown level is skipped silently by the SDK (`Level.toLevel(v, null)` returns null, then `continue`). **Fix:** have `validate-sdk` warn on non-ASCII bytes and unknown level values in a source file.
- **N3.** Extra `loggers:` names already covered by the collector's static log4j config are skipped silently. The SDK only creates an `AdapterLoggerConfig` when `getLoggerConfig(key)` is root (`loadAdapterLogConfigs` @169). This matters for names like `com.integrien.*`, which the collector sets to ERROR. **Fix:** add one line to the `loggers` docstring and tier2.
- **N4.** `.github/release-notes-buildkit.md`: the 1.0.25 section is appended after the 1.0.15 "Version note" paragraph. The 1.0.2x sections sit near the top, with 1.0.24 at line 168. **Fix:** move it above §1.0.24.

## Not findings (proven safe)

- **Global-default leak (anchor 00d3382).** The value comes from each pak's own `entry_class`. Tier 1 `builder.py` and factory content zips are untouched.
- **Key collision (anchor 6c59f6b).** The `logging.loggers` key equal to the package is rejected. A parent or child of the package coexists correctly, because the SDK adds entries after the loop, so declaration order is irrelevant.
- **Explicit source file.** It wins byte-for-byte, as exactly one entry, with a warning only when a stanza is declared.
- **Test coverage.** 21 tests cover generation, the stanza, `generate: false`, the source-file precedence, non-ASCII, the only-difference invariant and loader rejects. The coverage is adequate for the Python surface.
