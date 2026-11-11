# Framework review: build-sdk pak vendor, contact and EULA (#336)

- Branch: `tooling/sdk-pak-vendor-contact-336`, commit `def9b5e` (base `9750909`)
- Area: `src/vcfcf_managementpacks/sdk_project.py`, `sdk_builder.py`, `buildkit.py`
- Reviewer: framework-reviewer, 2026-11-11
- Verdict: **APPROVE** (0 BLOCKING / 4 WARNING / 3 NIT). Per delegation rule 9,
  every finding is fixed before the PR opens.

## Checks re-run

| Check | Result |
|---|---|
| Full suite, default markers, base `9750909` (git archive + the same gitignored `adapter_runtime/` jars) | 14 failed / 3306 passed |
| Same, branch | 14 failed / 3363 passed; **identical failure set** |
| `-m slow`, base / branch | 6 failed / 125 passed each; identical set |
| Pre-existing total | 20 (jmespath-missing doctor and `test_gap_b_f_d` tests, real-repo release-naming / packaging-validate integration, one RecursionError test). None new. |
| Seven-package validate chain, branch | all rc=0 |
| Default-path byte identity | Independent harness (`_generate_outer_manifest`, `_generate_outer_resources_properties`, `_build_overview_packed`, `_assemble_adapters_zip`, `_write_outer_pak`), recursive into every nested zip, SHA-256 per member, base vs branch code, on the five real adapter projects with an `adapter.yaml` (compliance, synology, template, unifi, vsanperf): **identical**, 218 to 250 members each, same order. (A full `build-sdk` run was not permitted in this session; the harness covers every generator the change touches, with the real `vcfcf-adapter-base.jar`.) |
| Built-output literal hunt (full override on the template project) | `Acme Labs` lands in both `manifest.txt`, outer `resources.properties`, both overview pages; the contact lands on the two overview pages only; EULA bytes equal both `eula.txt`; notice equals `LICENSE`. The remaining `VCF Content Factory` hits are all the project's own `name:` ("VCF Content Factory Example Adapter"), not a vendor stamp. No missed vendor sink. |
| Process leak | Override project then default project in one process: default vendor, no notice, `eula.txt == LICENSE`. No module state. |
| pak-compare (synthesised default vs override pak against `TVSManager-2.0.0.pak`) | Same 3 BLOCKING (pre-existing, fixture jar), delta is INFO only: `M7`/`I13` vendor differs, `A1` extra `lib/vcfcf-adapter-base-LICENSE.txt`. |
| Buildkit assembly | `test_assembled_kit_reads_kit_license` passes in the suite: assembled kit reads its own `LICENSE` for default eula and for the notice. |

## What holds

- All three sinks escape correctly. JSON: `json.dumps` default `ensure_ascii`. Properties: `\uXXXX` for everything outside printable ASCII, backslash escaped, `#`/`!`/`=`/`:` are inert inside a value. HTML: `html.escape(quote=True)` plus `xmlcharrefreplace`; `</p><script>` comes out as text. C0 controls and newline are rejected at load.
- EULA path: absolute, `..`, `~`, a directory, `.`, a NUL in the path, a missing file, a symlinked file out, a symlinked directory out: all rejected. Latin-1 rejected, whitespace-only rejected.
- Notice is written only when `eula_path` is set. A non-jar in `lib/` is safe: shipping TVS carries dozens of non-jar files in `lib/` (and `bin/curl-LICENSE.txt`), and only `*.jar` is globbed from project `lib/`, so no name collision.
- No consumer keys on the vendor: pak-compare rates it cosmetic (INFO), the installer and validators never read it, no test asserts the old literal.
- Unknown top-level keys are still ignored (pinned by a test).
- `vcfcf-adapter-base.jar` manifest code untouched. Note for requirement 1: a kit-built pak's base jar always differs between kits, because its manifest carries `Implementation-Version` (= kit version) and `X-Vcfcf-Source-Commit`. That is the existing design, not a regression; "byte-identical" holds for every member this change generates.
- `BUILDKIT_VERSION` 1.0.26 is the only recorded constant; the latest published kit is 1.0.25 and no other branch claims 1.0.26. The bump triggers nothing by itself: `publish-buildkit.yml` is tag-driven, and the constant feeds the factory-mode framework jar `Implementation-Version`.
- Stale-zip rule: none of the CLAUDE.md trigger files are touched, and default output is byte-identical, so no `content-packager` rebuild is owed.

## WARNING

### W1. A lone UTF-16 surrogate in `vendor` passes `validate-sdk` and crashes `build-sdk`
- Where: `sdk_project.py` `_parse_one_line` (accepts it); `sdk_builder.py:2233` `_prop_value_escape` (`ch.encode("utf-16-be")`).
- Input: `vendor: "Acme \ud83d Labs"` (YAML double-quoted escape; easy to produce by pasting JSON-escaped text). Observed: `validate-sdk` prints `OK ... is a valid Tier 2 SDK adapter project`, rc=0; `_generate_outer_resources_properties` raises `UnicodeEncodeError: surrogates not allowed`, an uncaught traceback mid-build. The outer `manifest.txt` `writestr` would fail the same way.
- Authority: RULE-005 (validate is the gate before build/install); requirement 4 (reject wrongly typed values).
- Fix: in `_parse_one_line`, reject any character in U+D800 to U+DFFF (for example `val.encode("utf-8")` in a try, raising `SdkProjectError` naming the key). Add the case to `test_one_line_keys_reject`.

### W2. "Empty" EULA check is bypassed by a BOM or by NUL/control bytes
- Where: `sdk_project.py` `_parse_eula_file`, the `if not text.strip()` test.
- Input: an `EULA.txt` of exactly `EF BB BF` (a BOM, what some editors save for an "empty" UTF-8 file) is accepted, because `str.strip()` does not strip U+FEFF; the pak ships a visually empty `eula.txt`. A file of `00 00 00` is also accepted.
- Authority: requirement 4 ("rejects ... an EULA file that is ... empty").
- Fix: strip a leading U+FEFF before the emptiness test, and treat a file whose remaining text has no printable character (or contains NUL) as empty/not text. Add BOM-only and NUL-only cases to `test_eula_file_rejects`.

### W3. Validate-then-reread: the build ships whatever is at the path at assembly time
- Where: `sdk_builder.py:2178-2185` `_pak_eula` calls `project.eula_path.read_bytes()` again, twice (inner and outer), after the javac/compile steps; validation read the bytes at `load_sdk_project` (build step 1) and threw them away.
- Scenario: after load, replace `legal/EULA.txt` with a symlink to a file outside the project, or truncate it. Observed: `_pak_eula` returns the outside file's bytes, and `b''` after truncation. Neither the containment, non-empty nor UTF-8 check applies to what ships, and the two `eula.txt` copies can differ if the file changes between the two reads. Practical risk is low (whoever can write the project can write the source), but the requirement-4 guarantees hold only at load time.
- Fix: keep the validated bytes on `SdkProjectDef` (e.g. `eula_bytes`) and have `_pak_eula` return them; no second read. A test that swaps the file after load and asserts the shipped bytes are the validated ones.

### W4. The kit's release notes say nothing about 1.0.26
- Where: `.github/release-notes-buildkit.md` (not touched by the diff). `publish-buildkit.yml` renders this file as the GitHub Release body; every kit since 1.0.11 with consumer-visible behaviour has a `## Behavior since <ver>` section (1.0.25 has one).
- Effect: the `sdk-buildkit-v1.0.26` release, whose audience is exactly the third-party pak authors #336 is for, will not mention `vendor`, `vendor_contact`, `eula_file` or the notice file. They learn of the keys only by reading this repo.
- Authority: issue #336 ("Document the keys ... wherever `adapter.yaml` is specified"; follow-up "Buildkit release carrying the change"); the per-version section convention in that file.
- Fix: add `## Behavior since 1.0.26` with the three keys, defaults, the notice file, the MIT sentence, and adoption (bump `BUILDKIT_TAG` and the committed SHA256SUMS).

## NIT

- N1. `sdk_project.py` `_ONE_LINE_BAD_CHARS` rejects C0 and DEL only. C1 controls (U+0085 NEL), U+2028/U+2029 line/paragraph separators, and bidi overrides (U+202E) are accepted. Every sink escapes them, so nothing breaks out, but U+202E lets a vendor string display reversed, and `&#133;` in HTML is remapped to windows-1252 "…" by browsers. Fix: also reject `[\x80-\x9f  ‪-‮⁦-⁩]`.
- N2. `sdk_builder.py` `_prop_value_escape`, the `ch == " " and i == 0` branch is unreachable: `_parse_one_line` strips the value. Harmless; either drop it or say in the docstring it is defensive.
- N3. `buildkit.py:1005-1009`: when the repo `LICENSE` is missing at assembly, the kit writes the placeholder `MIT License — see factory repo for full text.`. Before #336 that only reached a default `eula.txt`; now it is also the jar's MIT notice, and MIT requires the actual copyright and permission text. Unreachable in this repo (LICENSE is tracked), but a kit assembled from an incomplete checkout would ship a non-compliant notice. Fix: fail assembly instead of writing the placeholder.

## If shipped as-is

Default paks are unchanged and the override works in every sink. An author who pastes a JSON-escaped vendor gets a green `validate-sdk` and a traceback from `build-sdk`; one whose editor saves a BOM-only EULA ships an empty licence; and kit consumers learn of the feature only from this repo, not from the 1.0.26 release.
