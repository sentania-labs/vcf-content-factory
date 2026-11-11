# Framework review: build-sdk overview pages escape name and description (#338)

- Branch `tooling/overview-html-escape-338`, commit `7eed5b2`, merge base
  `a53814b` (origin/main has since gained only `e11c908`, a reorder of
  `.github/release-notes-buildkit.md`; `git merge-tree` merges clean).
- Files: `src/vcfcf_managementpacks/sdk_builder.py`,
  `src/vcfcf_managementpacks/buildkit.py`,
  `tests/managementpacks/test_sdk_overview_escape.py`,
  `knowledge/context/tier2_architecture.md`.
- Verdict: **APPROVE** (0 BLOCKING / 2 WARNING / 1 NIT). Per delegation rule
  9 both warnings and the nit are fixed before the PR opens.

## Checks re-run

| Check | Result |
|---|---|
| Seven-package validate chain (branch) | all rc=0 |
| `validate-sdk` on compliance, unifi, synology, vsanperf, template | all rc=0, adapter trees untouched |
| New + #336 tests | 131 passed |
| Full suite, branch vs merge base | 14 failed / 3436 passed vs 14 failed / 3408 passed; **failure sets identical** (jmespath missing; worktree lacks the gitignored `content/sdk-adapters/`). +28 = the new tests |
| New test file run against merge-base code | 14 escape tests fail, the 3 plain-ASCII identity tests and the manifest/properties tests pass: the tests discriminate, and the "captured from origin/main" baseline is real |
| Overview/manifest/properties generated per registered adapter on base and branch | manifest.txt and resources.properties byte-identical for all 5; overview pages identical for template; differ for compliance, synology, unifi, vsanperf, and for each `html.unescape(new) == old` exactly, light and dark bodies identical |
| pak-compare | n/a: `pak_compare.py` does not read `overview.packed` contents |
| Buildkit assembly | not executed (needs a reference pak; my run was not permitted). Static: the kit copies `sdk_builder.py` through import rewrites; the change adds no import (`html` and `_html_text` already existed), so the rewrite set is unaffected |

Hostile-input probe (both fields, base vs branch, via `load_sdk_project` then
`_build_overview_packed`, `_generate_outer_manifest`,
`_generate_outer_resources_properties`): NUL, U+0001, DEL, CR, CRLF, tab,
leading/trailing whitespace, blank lines, U+2028, BOM, NBSP, U+FFFE, astral,
`]]>`, literal `&#x27;`, lone surrogate, C1. Each value escaped exactly once;
no double escape on any path (vendor/contact still one `_html_text` each;
manifest and properties carry the raw value); CR/CRLF/tab/blank lines in the
description are preserved verbatim, so the `<p>` layout is unchanged apart from
escaping. No input raises at build time on the branch that did not raise on
the base. A literal `&#x27;` now reads back as itself (the base rendered it as
`'`), which is the fix, not a regression.

## WARNING

**W1. C1 controls in `name`/`description` now decode as different characters**
(`sdk_builder.py:2225-2231` `_html_text`, applied at `:2291-2292`).
`xmlcharrefreplace` turns U+0080-U+009F into `&#128;`..`&#159;`, and the HTML
character-reference rules remap those through windows-1252: `&#133;` is "…",
`&#128;` is "€", `&#159;` is "Ÿ". The base page carried the code point as raw
UTF-8. Failing input, which `validate-sdk` accepts:
`description: "Pools\Nvolumes"` (YAML `\N` = U+0085 NEL), or `name: "A\x80B"`.
The base page decodes to `Pools\x85volumes`; the branch page shows
`Pools…volumes`. That fails requirement 3 ("decoding the new page gives back
exactly the old text"), and it makes the new docstring (`:2284-2288`, "reads
back as the original text whatever charset") and the tier2 paragraph untrue.
This is the defect the #336 review raised as N1 for vendor, fixed there by
rejecting C1 at load (`sdk_project._ONE_LINE_BAD_CHARS`); `name` and
`description` have no character check (`sdk_project.py:798`, `:822`). No
registered adapter is affected.
Fix: in `load_sdk_project`, reject U+0080-U+009F in `name` and `description`
with the same error shape as vendor (description is multi-line, so reject only
the C1 range there, not newline/tab), add a C1 case to
`test_sdk_overview_escape.py`, and leave the docstring as is once it holds.

**W2. No 1.0.27 section in the buildkit release notes**
(`.github/release-notes-buildkit.md`, not in the diff). `publish-buildkit.yml`
publishes this file as the release body for whatever tag is pushed. The 1.0.25
and 1.0.26 bumps each added a "Behavior since" section. As it stands the
`sdk-buildkit-v1.0.27` release would open with "Behavior since 1.0.26" and
never tell a pak repo that its overview page members change (quotes, `&<>` and
non-ASCII now escaped). Fix: rebase onto origin/main (`e11c908` reordered the
file, newest first) and add a "Behavior since 1.0.27" section directly under
the order comment: what is escaped, the plain-ASCII identity, that manifest and
properties are unchanged, and adoption (bump `BUILDKIT_TAG` and SHA256SUMS; no
adapter.yaml change).

## NIT

**N1. The tier2 change-log row says the doc claim it guards is
"byte-identical"** without saying that this holds for the HTML members, not
the `overview.packed` blob, which differs on every build anyway (CPython
`writestr` stamps the current time). The row says the second half; it should
say both in one sentence so nobody reads "byte-identical pak". Doc-only.

## Out of the branch's code (follow-up issue, not this PR)

- A lone surrogate in `name` or `description` (YAML `"a\ud800b"`) passes
  `validate-sdk` and then crashes `build-sdk` with `UnicodeEncodeError` on the
  `resources.properties` sink. The base crashed on both the overview and the
  properties sink; this change removes the overview crash only. It is the same
  "passes validation, crashes the build" class the #336 review found for
  vendor. If W1 adds a loader check, rejecting U+D800-U+DFFF there too costs
  one character class and closes it.
- Bidi controls (U+202E) and C0 controls/NUL in `name`/`description` reach the
  page raw, as on the base: NUL is dropped by HTML parsers and U+202E reverses
  the displayed name. Not introduced here.
- A multi-line `name` puts line breaks inside `<title>`/`<h1>`, and `name` is
  not stripped: as on the base.

## Design choice: escape quotes in text content, or not

Keep the single helper that escapes quotes. A quote escape in text content
decodes to the same text, so nothing a person or a parser reads changes. The
only cost is member bytes for compliance and vsanperf, and no consumer
compares those: pak-compare ignores the overview, and the `overview.packed`
blob was never reproducible. A second, text-only variant would add a seam, and
the seam fails badly: once someone moves `name` into an attribute (`alt=`,
`title=`, `content=`) with the text helper, a quote breaks out of the
attribute. One rule for all four values, safe in either context, is the better
choice.

## Requirements, as verified

1. Escaped in `<title>`, `<h1>`, `<p>`, light and dark, same non-ASCII
   treatment as vendor: yes.
2. Plain ASCII without `&<>"'`: byte-identical (template adapter; the
   identity tests pass against base code).
3. Decoded text unchanged: yes for every registered adapter and every probe
   except C1 (W1).
4. Description layout: unchanged, including CR, CRLF, tabs and blank lines.
5. `manifest.txt` and `resources.properties`: byte-identical, not HTML-escaped.
6. No other behavior change found. `BUILDKIT_VERSION` is recorded only in
   `buildkit.py` (the kit `VERSION` and the jar `Implementation-Version` derive
   from it); the release notes gap is W2.
