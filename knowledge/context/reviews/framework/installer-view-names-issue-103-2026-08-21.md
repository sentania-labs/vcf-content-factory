# Framework review: installer `_extract_view_names` (issue #103)

- **Branch:** `fix-installer-view-names` (uncommitted vs `HEAD` = `5bc8c5a`)
- **Area:** `src/vcfops_packaging/templates/install.py`, `tests/test_dashboard_import_all_skipped.py`
- **Change:** `_extract_view_names()` moves from a `re.findall(r"<Title>(.*?)</Title>", ..., re.DOTALL)`
  scan to an `xml.etree.ElementTree` parse modelled on `src/vcfops_packaging/audit.py:500-512`,
  plus a 120-char per-name clip and a 20-name list bound. Closes issue #103
  (N-14 through N-18 from `phase2-guardrails-issues-2026-08-20.md`).
- **Verdict: APPROVE** (0 BLOCKING, 1 WARNING, 5 NIT)
- **Reviewer note:** this file ships inside every bundle zip and runs on the
  customer's machine, so everything below was verified by driving the code,
  not by reading it. `knowledge/context/known_limitations.md` also shows
  modified in the tree; per the brief it is an unrelated doc edit and was
  excluded from this review.

## Checks re-run

| Check | Result |
|---|---|
| Validate chain (7 packages) | **all OK** |
| `pytest -q` | **879 passed, 4 skipped, 178 deselected** (matches the claim exactly) |
| New tests actually execute in the default tier | **27 new node IDs, all PASSED**, none silently deselected |
| `scripts/path_reference_audit.sh` | **exit 0** |
| `python3 install.py --help`, standalone, outside the repo tree | **exit 0** |
| `python3 -m py_compile` / import under `python3 -O` | clean |
| Em-dash scan (both files) | **0 hits** |
| Bare `re.` usage after the module-level `import re` removal | **0 hits**; the two survivors are function-local `import re as _re` (`:525`, `:685`) |
| Real-corpus render regression (19 views) | **clean** (see below) |
| Mutation kill on the new tests | **3/3 mutants killed** |
| Dist zip staleness (dimension 9) | **3 of 3 stale** (see W-1) |

## Claim verification

### N-14 latency: confirmed, and reproduced independently

Measured on this box, old implementation reconstructed verbatim from `HEAD`:

| Input | Old | New | Result |
|---|---|---|---|
| `"<Title>" * 5000` (35,000 ch) | 1.552s | **0.0052s** | both `[]` |
| `"<Title>" * 20000` (140,000 ch) | 21.318s | **0.0163s** | both `[]` |

Matches the author's numbers (21.263s -> 0.0191s; 1.327s -> 0.0054s) within
noise. Pure latency fix on that input, as claimed: the return value is
identical in both implementations.

### Real-corpus render regression: clean, and it proves N-17 is a live defect

Rendered all **19** views in `content/views/` through the real
`vcfops_dashboards.loader.load_view` + `render.render_views_xml` and ran both
the old regex and the new parse over each:

- Title count in the corpus document: **19**. Old extracted 19, new extracted 19. **1:1, no drift.**
- **3 views differ, and all 3 differences are exactly the intended unescape:**
  - `[VCF Content Factory] Cluster Demand &amp; Capacity Overview v2` -> `... Demand & Capacity ...`
  - `[VCF Content Factory] Cluster Quarterly CPU &amp; Memory Demand` -> `... CPU & Memory ...`
  - `[VCF Content Factory] vSAN Cluster Health &amp; Resync` -> `... Health & Resync`
- Zero unintended drift across the other 16.

So N-17 was not hypothetical: three views shipping today print `&amp;` to the
operator beside unescaped dashboard names. Against the one real
`views_content.xml` in `dist/` (`vks-core-consumption-bundle.zip`), old and
new are byte-identical (`['[VCF Content Factory] VKS Core Consumption by vCenter']`).

### Unescaping: correct, and it cannot double-unescape

Driven directly:

- `CPU &amp; Memory &lt;top&gt;` -> `CPU & Memory <top>`. Correct.
- **Double-unescape is impossible.** `CPU &amp;amp; Mem` -> `CPU &amp; Mem`.
  Exactly one decode, performed by the parser during parsing. There is no
  second `unescape()` call to stack on it.
- **A name containing legitimate markup-looking text survives intact.**
  Authored name `<Title>fake</Title>` (rendered as `&lt;Title&gt;fake&lt;/Title&gt;`)
  extracts as the literal string `<Title>fake</Title>`, unmangled. The old
  regex was the implementation that could be confused by this shape, not the
  new one.
- CDATA (`<![CDATA[A & B <x>]]>`) -> `A & B <x>`; numeric charrefs
  (`&#65;&#x42;`) -> `AB`; a comment inside the title (`A<!--c-->B`) -> `AB`.
  All correct XML semantics.

### Never-raise contract: held under 25 further hostile inputs

The 18 parametrized cases all pass. I tried to break it with 25 more that the
suite does not cover. **None raised; every return was a `list` of `str`:**

`float("nan")`, `True`, an object raising `RuntimeError` in `__bool__`, an
object raising `ValueError` in `__len__`, `bytearray`, `memoryview`,
generator, tuple, set, an exception instance, XXE via `file:///etc/passwd`,
XXE via `http://127.0.0.1:1/`, 100,000-deep nesting (0.105s), `<Title>`
outside a `ViewDef`, `ViewDef` nested in `ViewDef`, `<Title>` with child
markup, CDATA, double-escaped text, markup-looking text, namespaced
`ViewDef`, whitespace-only title, numeric charrefs, comment-in-title,
UTF-16 bytes, and a UTF-16 encoding declaration on a `str`.

Two notable positives:

- **XXE is refused.** Both the file-read and the HTTP forms return `[]`.
  `ElementTree`'s default parser does not resolve external entities, so
  neither a local file disclosure nor an SSRF callback is reachable. The
  installer runs against a customer's Ops instance from inside their network,
  so this was worth proving rather than assuming.
- The object raising inside `__bool__` is caught by the bare `except` around
  the `if not views_xml` guard, so even the early-return path is covered.

I also confirmed the caller contract: `_extract_view_names` is consumed at
`:1537` by `", ".join(view_names)`. Every hostile return is `list[str]`, so
the join cannot raise. With more than 20 views the sentence reads
`... were NOT updated: View 0, ..., View 19, and 20 more.` which is correct
prose. Joined advisory length over the whole real 19-view corpus: 958 chars,
comfortably bounded.

### N-18: the wording claim is true

Verified by reading the control flow rather than trusting the test.
`_print_advisories()` is the final statement of **both** branches of the
summary block (`:2500` warning branch, `:2518` success branch), and
`_run_install(...)` at `:2730` is the last statement of `main()`. Nothing
prints after it. The advisory genuinely is the last non-blank line, so
"at the end of this output" is accurate where "below" was not. The new test
asserts `lines[-1].startswith("  ATTENTION  ")` and that the NOTE block sits
between the pointer and the header, which pins the claim rather than the
wording. Agreeing with leaving the ordering alone: the NOTE is boilerplate,
the advisory is the delta.

### The renderer round-trip test is NOT circular

`test_extraction_matches_real_renderer_output` genuinely pins the coupling to
`render.py:761`. Reasoning:

- The extractor and the renderer **share no code**. The renderer is f-string
  concatenation with `xml.sax.saxutils.escape`; the extractor is an
  independent expat parse. A round trip through two independent
  implementations is a real test, not a tautology.
- The test **guards its own premise** with two assertions on the renderer's
  raw output before extraction runs: `"CPU &amp; Memory &lt;top&gt;" in xml_text`
  (the renderer really escapes) and `xml_text.count("<Title") == len(names)`
  (one Title per ViewDef, none elsewhere). Those are what make it
  non-circular. If `render.py` stopped escaping, the first fails; if it
  started emitting a second `<Title>` anywhere, the second fails.
- `count("<Title")` counts the prefix, not `"<Title>"`. That is the right
  choice: it stays true if DEF-018 is ever revisited and attributes return,
  which the extractor is now immune to anyway.

I widened it beyond the test's two synthetic views by running the same round
trip over all 19 real repo views (above). The coupling holds.

### The two intentional behavior changes: both correct

1. **Names arrive unescaped.** Correct, and it fixes a real defect affecting
   3 of 19 shipped views. Cannot double-unescape. Restores fidelity parity
   with `_extract_dashboard_names`, which reads JSON and prints raw.
2. **`<Title>` outside a `ViewDef` is no longer extracted.** Inert on the
   real path, verified rather than assumed: `views_content.xml` has exactly
   one producer (`builder.py:765` writes `render_views_xml(...)` output
   verbatim), and `<Title>` is emitted at exactly one site
   (`render.py:761`, inside the ViewDef header fragment). Grep confirms no
   other `<Title` emission in `render.py` or `vcfops_packaging/`. The real
   corpus is 1:1 (19 titles, 19 views, 19 extracted). `audit.py` has always
   had this same `ViewDef`-child scope, so the change moves the installer
   *toward* the established convention, not away from it.

### Mutation kill: the new tests are load-bearing

Run against mutated implementations in a scratch copy (source untouched):

| Mutant | Killed by |
|---|---|
| Revert to the old regex | attribute test, unescape test, perf test, clip test, and-n-more test (**5**) |
| Drop the 120-char clip | clip test |
| Drop the 20-name cap | and-n-more test |
| *(control)* current implementation | nothing; passes all |

Each bound has its own killing test. The suite is not decorative, and a
silent revert of this fix cannot land.

## Review dimensions

| # | Dimension | Result |
|---|---|---|
| 1 | Global-default / pak-specific leak (`00d3382`) | **Clean.** No pak-specific default introduced. The two new constants are module-level and unconditional; there is no pak-vs-standalone branch in this function or its caller. The standalone content-import path is the *only* path this code runs on. |
| 2 | Key / label derivation collision (`6c59f6b`) | **Not applicable, and adjacent-safe.** These are display-only names for an advisory sentence, never used as keys, IDs, or for resolution. Duplicate names would print twice and resolve nothing. |
| 3 | Wire-format conformance | **Clean.** Read-only consumer. Emits no wire artifact; `views_content.xml` is unchanged by this diff. |
| 4 | Loader / validator correctness | **Not applicable.** No cross-reference resolution, no UUIDs, no prefix enforcement touched. Validate chain green. |
| 5 | Render regression vs known-good | **Clean.** 19/19 real views, 1:1 extraction, only the 3 intended unescape deltas. |
| 6 | Builder / pak structure | **Not applicable** (no `pak-compare` surface touched). |
| 7 | Corpus regression | **Clean.** 7/7 validate packages OK; 879 passed / 4 skipped. |
| 8 | Silent capability change / downgrade | **Clean, and net upward.** The scope narrowing (N-4 below) is the only reduction and it is unreachable from the single producer. Against the shape that actually matters (`<Title localizationKey=...>`) the change is a strict capability *gain*: zero names before, correct names now. |
| 9 | Stale-zip discipline | **Applies. Confirmed stale (see W-1).** |
| 10 | Test coverage of the change | **Strong.** 27 new tests, all in the fast tier, all mutation-verified. This is the surface that had none when the escapes shipped. |

## W-1 (WARNING): all three dist zips are stale; the fix currently reaches nobody

`src/vcfops_packaging/templates/install.py` changed, so per CLAUDE.md
"After tooling changes" every zip in `dist/` is stale. Verified by SHA-256
against the repo template:

| Zip | Bundled `install.py` | Still carries the quadratic regex? |
|---|---|---|
| `VCF Content Factory Compliance.zip` | `b90012b0e83b` (stale) | no |
| `storage-path-monitoring.zip` | `8f59cee8cdd9` (stale) | **yes** |
| `vks-core-consumption-bundle.zip` | `8f59cee8cdd9` (stale) | **yes** |

Repo template: `ff9f01b75801`. All three differ.

Note these were **already** stale before this diff (round-3 finding W-5 said
3 of 3 carried a different `install.py`), so this change does not create the
condition, but it does add to it. Confirming the rebuild need as the brief
requested: **`content-packager` must rebuild every manifest in `bundles/`
before this ships**, or the customer-facing code that this entire change
exists to fix is still the old regex on 2 of 3 zips. Not blocking, because
the rebuild is already the stated next step.

## NITs

- **N-1. The sibling `_extract_dashboard_names` is still unbounded, and can
  crash the caller.** `install.py:1275-1280`. Issue #103 item 2 explicitly
  named it ("`_extract_dashboard_names` shares the shape"), and the fix
  bounded views only, so the asymmetry my round-3 N-15 flagged is now
  *inverted* rather than resolved: view names are clipped and capped,
  dashboard names on the very next line of the same advisory are neither.
  Worse, it returns `d.get("name")` unconverted, so a non-string JSON `name`
  makes the caller's `", ".join(dash_names)` at `:1526` raise `TypeError`
  **outside any `try`**, verified by driving it:
  `_extract_dashboard_names('{"dashboards":[{"name":123}]}')` -> `[123]` ->
  join raises `TypeError: sequence item 0: expected str instance, int found`.
  That would abort the installer at the advisory-printing step, *after*
  content was already imported. Unreachable from factory-rendered JSON
  (`name` is always a string), same provenance argument as everything else
  here, hence a NIT. But it is exactly the class of defect the changed
  function was just hardened against, sitting one function above it in the
  same printed sentence. `str(...)` plus the same two bounds is a one-line
  close. Suggest a follow-up issue rather than scope creep on this PR.
- **N-2. Decoded text is a strictly wider channel to the operator's
  terminal.** Now that names are decoded, characters that the old regex
  passed through as inert literal text (`&#13;`) arrive as real control
  characters. Driven: `&#13;` -> `\r`, `U+202E` (RTL override) -> survives,
  `U+0085` (NEL) -> survives. **No ANSI escape injection is possible**: XML
  1.0 forbids C0 controls both literally and as character references, so
  ESC/BEL/BS all return `[]` (verified). `render.py` emits no character
  references (`escape()` produces only `&amp; &lt; &gt;`), so reaching this
  requires a hand-edited `views_content.xml` in the same zip as `install.py`
  itself. Contained; recorded so it is not re-derived. Note the code comment
  claims parity with the doctor's `_clip`, and that claim is accurate:
  `vcfops_common/doctor.py:752-757` is length-only too, with no control-char
  scrubbing anywhere in the repo's echo-safety discipline.
- **N-3. Internal DTD entity expansion is newly reachable.** The regex never
  expanded entities; `ET.fromstring` does. A billion-laughs document with a
  5 MB nominal expansion parses and returns the expanded name (0.061s, 46 MB
  RSS, then clipped to 120 chars). Larger bombs are refused: expat 2.6.1's
  input-amplification guard raises `ParseError: limit on input amplification
  factor (from DTD and entities) breached`, caught by the existing `except`,
  returning `[]` (verified at a nominal 5x10^9 expansion: 0.07s, 46 MB). Two
  reasons this is a NIT and not a warning: (a) `install.py` declares "Requires
  Python 3.8+" and libexpat before 2.4 has no amplification guard, but the
  document comes from the same zip as `install.py` itself, so an attacker who
  can plant it can simply edit the installer; (b) `install.py` **already**
  calls `ET.fromstring` on server-supplied policy XML at `:284`, a strictly
  more exposed trust boundary than a bundle-local file. The diff adds an
  instance of a class already present on a more exposed input, not a new
  class. No action needed; recorded because the change's own stated purpose
  is DoS hardening, so the new parser had to be shown not to reintroduce one.
- **N-4. `<Title>` containing child markup loses everything after the first
  child.** `<Title>CPU <b>hot</b> path</Title>` -> `['CPU']`, because only
  `.text` is read (`itertext()` would give the full string). The old regex
  returned the full inner markup. Unreachable: `escape()` at `render.py:761`
  cannot produce child elements. Same for a namespaced `<ViewDef>`, which
  `root.iter("ViewDef")` does not match; the renderer emits no namespace and
  `audit.py:502` has the identical limitation. Both are faithful to the
  `audit.py` model the change deliberately copied. No action.
- **N-5. `scripts/check_framework_review.sh` cannot see this change yet.** It
  diffs `origin/main...HEAD` (`:22`, `:28`), so with the work uncommitted it
  reports `no vcfops_*/ changes; framework review not required`. It will fire
  once the branch is committed, and this document satisfies it. Flagging only
  so the green guard output is not mistaken for coverage.
- **N-6 (informational).** The perf test asserts `elapsed < 1.0` against a
  measured ~0.016s, roughly 60x headroom. Not flaky on a loaded runner.

## If shipped as-is

An operator whose import skips its views sees the correct view names in the
"NOT updated" advisory, at the same fidelity as the dashboard names printed
beside them, instead of `&amp;`-mangled names or the generic "view(s)". A
bundle with many views gets a bounded 21-item list rather than an unbounded
one. The `Done.` line no longer points "below" at a list seven lines away.
Nothing regresses on the 19-view real corpus. **Caveat:** none of this
reaches a customer until `content-packager` rebuilds `dist/`, where 2 of 3
zips still carry the old quadratic regex (W-1).
