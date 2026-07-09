# Framework Review — SDK pak version-line guardrail (RULE-014)

- **area:** `vcfops_managementpacks/sdk_builder.py`, `vcfops_managementpacks/cli.py`
- **change:** default `build-sdk` stamps `0.0.0.<build_number>` on every version
  surface; the real `adapter.yaml` version is used only on explicit release
  opt-in (`--release` → `VCFCF_RELEASE_BUILD`).
- **governing authority:** `rules/pak-version-lines.md` (RULE-014)
- **verdict:** APPROVE (0 BLOCKING)
- **findings:** 0 BLOCKING / 1 WARNING / 2 NIT
- **ships with:** `stitcher-identity-additive-foreign-v1.md`,
  `sdk-builder-jar-staleness-v1.md` (one PR)

## Checks re-run (independently)

- **validate chain (content):** all 7 modules green (sm/dash/cg/sym/alert/report/mp).
- **managementpacks test suite:** `pytest tests/managementpacks/ -q` →
  125 passed, 4 skipped. Includes the version-stamp tests AND the sibling
  jar-staleness tests, so the two rounds pass together.
- **version-stamp tests:** `tests/managementpacks/test_sdk_version_stamp.py`
  → 17 passed (matches tooling's claim of 17).
- **sibling jar-staleness tests:** `tests/test_sdk_builder_framework_jar.py`
  → 5 passed, run together with the version-stamp file (22 passed combined).
- **render-regression:** n/a — the diff does not touch
  `vcfops_dashboards/render.py` or the standalone content-import path.
- **pak-compare:** n/a (no `tmp/reference_paks/` present); the decisive
  per-surface extraction below substitutes.
- **smoke build (both paths):** synology (declares `1.0.0`, build 23), built
  from a scratchpad copy so the tracked tree stays clean.

## Completeness of the stamp — PROVEN on both paths

Stamp is applied at `sdk_builder.py:2944` (`_stamp_build_version`), immediately
after `load_sdk_project` (:2938) and **before every** downstream version-surface
consumer:

| surface | code site | reads after stamp? |
|---|---|---|
| pak filename | `SdkProjectDef.pak_filename` (property) → used at :1646 | yes |
| outer + inner manifest `version` | `_generate_outer_manifest` :1237 | yes |
| `conf/version.txt` Major/Minor/Impl | `_generate_version_txt` :783 | yes |
| `overview.packed` HTML `Version` | `_build_overview_packed` :1188/:1208 | yes |
| generated docs `version_string` | :3031 | yes |

The only pre-stamp read of `project.version` is the cosmetic
`declared_version=` log line at :2939. No persisted surface is derived before
the mutation.

**Empirical proof — cracked open both built paks:**

| surface | dev build (default) | release build (`--release`) |
|---|---|---|
| filename | `...0.0.0.23.pak` | `...1.0.0.23.pak` |
| outer manifest version | `0.0.0.23` | `1.0.0.23` |
| inner manifest version | `0.0.0.23` | `1.0.0.23` |
| version.txt Major/Minor/Impl | `0` / `0` / `0.23` | `1` / `0` / `0.23` |
| overview.packed Version | `0.0.0.23` | `1.0.0.23` |

Every surface agrees per path; nothing leaked the declared `1.0.0` onto the dev
path. RULE-014 §1 (default 0.x on ALL surfaces) and §2 (real line only via
explicit CI opt-in) are both satisfied.

`describe.xml version="1"` was checked and is **not** in scope — it is the
hand-authored describe-schema/AdapterKind version (an integer, per-ResourceKind),
not the pak version line, and is copied verbatim from the project dir.

## Opt-in leakage — bounded

`--release` sets `VCFCF_RELEASE_BUILD` transiently in-process only when the flag
is explicitly passed (`cli.py:_apply_release_flag`, mirroring the established
`_apply_sdk_jar_flag` pattern). Tests use an `autouse` `monkeypatch.delenv`
fixture, so no test leaks the var into another. The release path prints a loud
`INFO: version stamp -> release build` line on every invocation. See WARNING and
NIT-1 below for the residual ambient-export consideration.

## Dimension walk

1. **Global-default / pak-specific leak (anchor 00d3382):** the default is the
   *safe* direction (0.x), applied uniformly to every adapter and every surface;
   the opt-in is the narrow, explicit path. No pak-local choice leaks onto a
   shared path. Clean.
2. **Key/label collision (anchor 6c59f6b):** n/a — no key/label derivation.
3. **Wire-format conformance:** manifest `version` and `version.txt` fields match
   the documented format (`{version}.{build_number}`, Impl = `{patch}.{build}`);
   verified against the emitted paks. Clean.
4. **Loader/validator correctness:** `SdkProjectDef` is a non-frozen dataclass;
   in-place mutation is legitimate. `validate_sdk_project` does not build a pak
   and does not stamp (correct — validate must report the *declared* version).
5. **Builder/pak structure:** unchanged apart from the version fields.
6. **Corpus regression:** validate chain + managementpacks suite green.
7. **Silent capability change:** none — the behavior change is loud (one INFO
   line, every build) and rule-mandated.
8. **Stale-zip discipline:** n/a — `sdk_builder.py` is not in the stale-zip
   trigger set (`vcfops_packaging/templates/`, `vcfops_packaging/builder.py`,
   `vcfops_dashboards/render.py`); SDK paks are not in `bundles/`.
9. **Test coverage:** 17 new tests cover env parsing, default→0.0.0.N regardless
   of declared version, opt-in→declared, and cross-surface agreement on both
   paths. Adequate.
10. **Sibling coherence:** same file as the jar-staleness fix; the combined
    working tree compiles and the full managementpacks suite passes together.

## WARNING

- [designs/sdk-template-scaffold/build-pak-on-tag.yml + 6 external pak-repo CI
  copies] `rules/pak-version-lines.md` §"Operational consequences" —
  **rollout-sequencing hazard.** The factory source-of-truth workflow now passes
  `--release`, but the six pak-repo copies are (per the brief) intentionally left
  stale as a follow-up. The moment a new `sdk-buildkit` tarball carrying this
  default-0.x behavior is published and a pak repo cuts a `v*` release **without**
  first updating its CI to pass `--release`, that release builds a `0.0.0.N` pak
  and attaches it to a GitHub Release — which is precisely the defect RULE-014
  §"Operational consequences" names ("A 0.x pak found attached to a release ...
  is a defect"). This diff is correct in-tree; the risk is purely in the external
  rollout order. → **Fix:** gate/sequence the six pak-repo CI updates to land
  *before or with* the buildkit republish that carries default-0.x, and track the
  follow-up explicitly (a defect entry or a checklist item) so it cannot be
  silently dropped.

## NIT

- [sdk_builder.py:299 `_is_release_build`] A durable `export VCFCF_RELEASE_BUILD=1`
  in a user's shell profile would silently convert every local `build-sdk` to the
  release line — the exact indistinguishability RULE-014 guards against. Mitigated
  by (a) the loud per-build `INFO` line and (b) RULE-014 itself, which assigns
  setting the flag outside CI to the user as a rule violation, not a tooling
  defect. The `--release` flag sets the var only transiently in-process, matching
  the `VCFCF_SDK_JAR` convention. Acceptable as-is; noted so the mitigation is on
  record. No change required.
- [sdk_builder.py:3031-3032 `_generate_docs`] A hand `build-sdk` run **in place**
  (not against a copy) rewrites the project's committed `*.generated.md` docs to
  the `0.0.0.N` dev line. This is rule-correct for a dev build, but it dirties the
  tracked tree and a developer could accidentally commit `0.0.0` generated docs
  over the release version. Consider building from a copy, or documenting
  "discard generated-doc changes after a dev build." Minor.

## If shipped as-is

An operator hand-building any SDK adapter gets a `0.0.0.<build>` pak on every
surface (filename, both manifests, version.txt, overview) — installable over a
`1.x` release only via the deliberate clobber path, exactly as RULE-014 intends.
The one thing to watch is external: until the six pak-repo CI copies also pass
`--release`, a release tag on one of those repos (built with a default-0.x
buildkit) would ship a `0.x` pak on its GitHub Release — the WARNING above.
