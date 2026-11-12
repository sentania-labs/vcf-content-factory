# Framework review: buildkit 1.0.28 (#343 known SDK jars, #322 Test Connection logging, VENDOR= UTF-8)

- Branch: `tooling/buildkit-1.0.28`, commits `39b164f`, `8122cd7`, `7925ed8`
  (`git diff origin/main...7925ed8`, base `3cf8448`)
- Area: `src/vcfcf_managementpacks/` (sdk_builder, buildkit, adapter_framework
  shell scripts and `VcfCfAdapter.java`, PROVENANCE.md)
- Reviewer: framework-reviewer, 2026-11-11
- Verdict: **APPROVE** (0 BLOCKING / 3 WARNING / 2 NIT)

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (branch worktree) | all rc 0 |
| pytest default markers, branch vs main | 14 failed each, **identical failure set**; 3611 vs 3560 passed |
| `-m ""` on the five touched test files incl. the Java harness | 284 passed, none skipped (harness ran on the 9.0.2.0 and 8.18.7 jars) |
| build-sdk template, synology, unifi, main vs branch, every leaf compared (nested zips/jars expanded) | only `lib/vcfcf-adapter-base.jar!/META-INF/MANIFEST.MF` (1.0.27 -> 1.0.28, source commit), `VcfCfAdapter.class`, `$CycleOutcome`, `$Enumerated`, `$VanishEntry` differ. `javap -c -p` of the three inner classes identical (line tables only). Matches the claim exactly. |
| validate-sdk on six registered adapters, main vs branch | same rc each (cluster-perf-risk and vsanhostmetrics fail on main too); no known-jar box on known jars |
| CLI scenarios (repacked 9.0.2 jar = unknown, 8.18.7 jar) | hand build: rc 0, exactly one box, pak built. `--release`, `--require-sdk-compat`, `VCFCF_RELEASE_BUILD=" TRUE "`: rc 1 before any compile. 8.18.7 as primary under `--release`: rc 1, named by line. Known primary + unknown `--sdk-compat-jar` under `--release`: rc 1. validate-sdk: hand rc 0 + box; `--require-sdk-compat` rc 1; `VCFCF_RELEASE_BUILD=1` rc 1. |
| #322 probe (own Java harness, real 9.0.2 SDK factory + log4j-core) | instance-path logger with a pak entry at DEBUG and WARN: branch output identical to main (governing entry is the `(id) name` LoggerConfig, `governed=false`, same instance and collector log lines). Claim "instance path unchanged" holds. |
| `resources.properties` VENDOR via configparser (the pak manager's reader) | non-ASCII, `=`, `:`, `#`, `;` read back as written; backslash reads back doubled and `%` raises InterpolationSyntaxError, both pre-existing and documented in tier2_architecture.md; newline impossible (loader rejects C0). |

## WARNING

**W1. Shell and Python disagree on what a release run is, so a release run can compile the framework against an unknown jar.**
`adapter_framework/build-framework.sh:121-138` (`compat_required`, `release_mode`) and `run_stitch_tests.sh:104-109` (`is_true`) lowercase the value but do not strip whitespace. `sdk_builder._is_release_build` / `_compat_required` (`sdk_builder.py:830`, `:1242`) do `.strip().lower()`. In a full `build-framework.sh` build the primary jar is checked **only** by the shell, because the script passes `check_primary=False` to `check_framework_sdk_compat` (`build-framework.sh:188`, `sdk_builder.py:1719`). Reproduced on a scratch copy with an unknown jar under the 9.0.2 name:
- `VCFCF_RELEASE_BUILD="1"`: rc 3, refused. `VCFCF_RELEASE_BUILD="1 "` or `" true"`: rc 0, box only, `vcfcf-adapter-base.jar` written.
- `VCFCF_SDK_COMPAT_REQUIRED="1 " VCFCF_SDK_COMPAT_LEGS=8.18.7`: Python treats the run as required (runs the legs), the shell does not refuse the primary, rc 0, jar **built** against the unknown primary.
- `run_stitch_tests.sh` with `VCFCF_RELEASE_BUILD="1 "` and an unknown jar: rc 0, box only.
No CI path hits this (factory CI uses `--compat-only`, pak CI uses build-sdk), so not BLOCKING, but it is exactly the "shell and Python disagree" seam, and the PROVENANCE/tier2 docs say the shell reads "the same two switches sdk_builder reads". Authority: knowledge/context/tier2_architecture.md "Known jars only in a release build"; RULE-002 (no silent pass).
Fix: make the shell truthiness identical to Python's, e.g. `printf '%s' "$v" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]'` in all three helpers, and add the `"1 "` / `" TRUE"` cases to the shell tests in `tests/managementpacks/test_sdk_known_jars.py`.

**W2. A release build can ship a framework jar compiled against a jar the release rule refuses.**
`sdk_builder.py:4808-4812`: the known-jar check looks at the current primary jar, then `_ensure_framework_jar()` reuses any `vcfcf-adapter-base.jar` that is mtime-fresh. Freshness ignores which SDK jar it was compiled against. Reproduced: remove the framework jar, hand build template with `--sdk-jar <unknown>` (warns, rebuilds the framework against the unknown jar), then `build-sdk --release` with the known 9.0.2 jar: the check passes, the log shows the framework is reused, not recompiled (the run then stopped at pak-compare only because the scratch copy had no reference paks). The pak would ship `lib/vcfcf-adapter-base.jar` built from a refused jar. CI is safe (fresh kit each tag run); the exposure is a local or persistent-tree `--release`, and the factory tree, whose `adapter_runtime/` persists. Authority: owner requirement in the brief ("CI should hardpin"), tier2_architecture.md table row "Primary jar (the one that ships)": the framework jar is part of what ships.
Fix (smallest): write the compile jar's sha256 into the framework jar manifest (`_framework_manifest_text`, e.g. `X-Vcfcf-Sdk-Sha256`) and treat a mismatch with `_primary_compile_jar()`'s sha as stale in `_ensure_framework_jar`; or, in `_sdk_jar_release_mode()`, always rebuild the framework jar. Add a test that a release build after a hand build with another jar recompiles the framework.

**W3. A project `lib/` SDK jar joins the release compile unchecked (follow-up issue; code not touched by this branch).**
`sdk_builder.py:972-976` (`_build_classpath_jars`) appends every `project_dir/lib/*.jar` to the primary classpath, and `:1854-1857` bundles them. A `vrops-adapters-sdk*.jar` there is excluded from the compat legs (`_adapter_compat_inputs`, `:1689`), so the legs would catch API drift; one under another name is on every leg's classpath too, and no known-jar check sees it. That is a way for a release run to compile against SDK classes outside the table. Pre-existing and outside the diff, so per CLAUDE.md delegation rule 9 this is a follow-up issue, not a fix in this PR: refuse (release) / warn (hand) any jar in project `lib/` that contains `com/integrien/alive/common/adapter3/` classes.

## NIT

**N1. Cross-pak `AdapterLoggerConfig` suppresses the raise for a pak without the file.** `VcfCfAdapter.java` `governedByPakLoggingEntry`: `isAdapterLoggerConfig(governing)` returns true for an entry loaded from **another** pak's file whose key is a dotted parent of this logger's name (a user-added `com.vcfcf=WARN` in pak A's `logging.loggers` would stop pak B's Test Connection INFO from being raised). Generated files use `entry_package` only, so no registered pak hits it, but "paks without the file unchanged" is then not strictly true. Fix: either document it in the tier2_architecture.md #322 section, or require the governing entry's name to be a key of this pak's own file before returning true.

**N2. Per-call file read on the Test Connection path.** `componentLogger` calls `raiseToInfo` on every call; on the Test Connection path the bare name reads not-INFO, so each call re-reads `logging.properties` and redoes the reflection. Harmless for the usual "fetch once" pattern; a one-line note in the `componentLogger` Javadoc, or caching the parsed keys per adapter class, would do.

## Proven safe (dimensions walked)

- **Exit codes**: build-sdk/validate-sdk refusals are `SdkBuildError` -> rc 1, same as every other build error. `build-framework.sh` and `run_stitch_tests.sh` reuse 3 ("could not run" / "setup missing"); the overload is documented in both headers and the error text names #343.
- **Table drift**: four copies (Python, two shell scripts, PROVENANCE.md) tied by `test_sdk_known_jars.py` and `test_sdk_jar_names.py` against the real constants; sha comparisons are all lowercase hex (hexdigest, sha256sum, shasum); a missing hash tool fails closed (problem recorded -> refused in release).
- **`--compat-only`**: checks the primary with `check_primary=True`, and the factory CI rows pass (each runtime jar is a known jar of some line).
- **Missing paths**: `VCFCF_SDK_JAR` naming a missing file skips the check but the build then fails in `_ensure_framework_jar` / `_build_classpath_jars`; a missing explicit compat path skips the check but `_sdk_compat_check` raises. Both fail closed.
- **#322 exception handling**: `catch (Exception | LinkageError)` covers NoClassDefFoundError, ExceptionInInitializerError, InaccessibleObjectException, InvocationTargetException; every failure answers false, the pre-#322 raise. The 8.18.7 harness leg confirms the unchanged raise.
- **Global path / stale zips (dims 1, 9)**: no `vcfcf_packaging` templates, builder, assembly or dashboard/alert render touched; `CURRENT_TEMPLATE_VERSION` not implicated. `BUILDKIT_VERSION` bumped to 1.0.28 and stamped into the framework manifest, so distributed kits and paks are distinguishable.
- **Tests (dim 10)**: every behaviour has tests; the harness runs the real SDK factory. Gaps are the W1 whitespace cases and the W2 reuse case.

## If shipped as-is

Every CI path hard-pins as the owner asked, hand builds warn once and build, and pak bytes change only as claimed. The holes need a non-canonical switch value (`"1 "`) or a local `--release` in a tree where a hand build used another jar; in either case a release-labelled framework jar can be compiled against a jar the rule refuses, and nothing says so.
