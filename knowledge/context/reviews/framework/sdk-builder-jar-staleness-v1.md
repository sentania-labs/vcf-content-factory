# Framework Review — sdk_builder.py framework-jar staleness gate

- **Area:** `vcfops_managementpacks/sdk_builder.py` (`_ensure_framework_jar` staleness detection)
- **Change:** jar absent → build; jar present + any `adapter_framework/src/**.java`
  newer (mtime) → loud rebuild; fresh → no-op; src-tree absent (runtime-only
  distribution) → no-op with existing jar; both absent → `SdkBuildError`.
  Adds `_find_stale_framework_sources()`; 5 hermetic tests; regenerated
  (gitignored) `adapter_runtime/vcfcf-adapter-base.jar`.
- **Date:** 2026-07-01
- **Verdict:** APPROVE (0 BLOCKING)
- **Ships with:** the already-APPROVED stitcher diff
  (`stitcher-identity-additive-foreign-v1.md`) in one PR.

## Priority finding — the author/tooling contradiction is resolved as scenario (b)

The build-23 pak carried a stale bundled jar (author's bytecode proof); tooling
found the on-disk `adapter_runtime/` jar current. Both are true at different
times. Resolution: **there is no second jar door in the assembly path — the gate
guards the correct and only door.** Proven three ways:

1. **Static trace.** `build_sdk_pak` calls `_ensure_framework_jar()` at
   `sdk_builder.py:2930` (writes `output_jar = _ADAPTER_RUNTIME_DIR /
   "vcfcf-adapter-base.jar"`), then `_collect_lib_jars` at :2959 reads that
   same path via `_find_jars(_ADAPTER_RUNTIME_DIR, "vcfcf-adapter-base.jar")`
   (:506), and `_assemble_adapters_zip` (:1080-1081) writes those lib_jars into
   the pak. Same file, freshened before it is read, in one invocation.
2. **No per-adapter door.** `content/sdk-adapters/synology/` has no `lib/`
   framework jar; `_collect_lib_jars` only appends project `lib/*.jar` (none
   here). The framework jar comes exclusively from `adapter_runtime/`.
3. **Decisive empirical build.** Ran `build-sdk` for synology NOW (scratchpad,
   not committed/installed). The resulting pak's bundled
   `synology_diskstation/lib/vcfcf-adapter-base.jar` **contains `getSourceLabel`**
   (in `SuiteApiStitchClient$Builder.class` and `AmbientCredential.class`) —
   i.e. fresh. Build-23's stale bundle was produced by the OLD no-op gate
   (`if output_jar.is_file(): return`) over a then-stale `adapter_runtime/` jar;
   this fix rebuilds on staleness and closes it.

Note: the author's proof grepped the outer `SuiteApiStitchClient.class`, where
the `getSourceLabel` reference does not land (it is in the `$Builder` inner
class) — a benign artifact of which class was inspected, not a second jar.

## Checks re-run (independently)

- **validate chain (content):** all 7 modules green (sm/dash/cg/sym/alert/report/mp).
- **validate-sdk (Tier 2 recompile against the rebuilt jar):** all 6 present
  adapters OK — compliance, synology, unifi, vcommunity, vcommunity-os,
  vcommunity-vsphere. Confirms tooling's "6 Tier 2 recompile" claim and
  exercises the second `_ensure_framework_jar()` call site (:3163).
- **new staleness tests:** `tests/test_sdk_builder_framework_jar.py` 5/5 passed.
- **full python suite:** `pytest tests/ -q` → 440 passed, 4 skipped
  (matches the claimed 440).
- **render-regression:** n/a — change is confined to the SDK pak builder; does
  not touch `vcfops_dashboards/render.py` or the standalone content-import path.
- **pak-compare:** n/a (no reference_paks dir present); the decisive per-jar
  bytecode check substitutes.
- **Java suites (18/13/8):** owned by the sibling stitcher review, which already
  re-ran them against this exact jar; `build-framework.sh` does not run them and
  the jar content is that review's surface, not this diff's.

## Dimension walk

- **Global-default / pak-specific leak (00d3382):** inert. Change is entirely
  inside the Tier 2 SDK builder; no default/coord/flag reaches the standalone
  content-import path.
- **Key/label collision (6c59f6b):** n/a — no key/label derivation touched.
- **Wire-format conformance:** pak structure unchanged; the bundled jar is the
  same `adapter_runtime/` artifact, now guaranteed current.
- **Silent capability change / downgrade:** this change *removes* a silent
  downgrade (stale-jar bundling) rather than introducing one. Failure direction
  is safe: any mtime doubt triggers a rebuild (loud, on stderr), never a silent
  stale bundle.
- **Test coverage:** all five branches covered, hermetic, real javac/jar,
  monkeypatched module constants (real trees untouched). The fresh-jar no-op
  test asserts the contract (no build subprocess on fresh input), not internals
  — acceptable and robust.
- **Stale-zip discipline:** `sdk_builder.py` is not in the CLAUDE.md stale-zip
  trigger list (`vcfops_packaging/templates/`, `builder.py`,
  `vcfops_dashboards/render.py`) and SDK paks are not shipped from the factory
  dist/. No factory-owned bundle rebuild required. (See NIT-4 re: the on-disk
  build-23 artifact.)
- **src drift this round:** the 4 modified `adapter_framework/src/.../stitch/*.java`
  files exactly match the already-reviewed stitcher diff scope — no new drift.
- **Jar in the PR diff:** `adapter_runtime/vcfcf-adapter-base.jar` is
  git-ignored and untracked — no stale binary enters the PR.

## Findings

No BLOCKING. No WARNING.

### NIT
- **[sdk_builder.py:93]** Staleness uses strict `>` on mtime. On a
  coarse-granularity filesystem (FAT/2s, or same-second ext2/3) a source edited
  in the same tick as the jar build could tie mtimes and be read as fresh. The
  repo FS is ext-family with fine mtime and the stale unit test sleeps 1.05s, so
  this does not bite here; it self-corrects on the next edit. No change needed;
  noted for the record.
- **[sdk_builder.py:130-141]** A `git checkout`/`pull` that rewrites tracked
  `src/*.java` mtimes to "now" while leaving the gitignored jar untouched can
  trigger a spurious (harmless) framework rebuild with a "STALE" message. This
  errs toward rebuild — the safe direction — and the rebuild reproduces an
  identical jar. Acceptable; a content-hash gate would avoid the noise but is
  not warranted.
- **[sdk_builder.py:3163]** `validate-sdk` now has a write side-effect: it may
  rebuild the gitignored `adapter_runtime/vcfcf-adapter-base.jar` if it detects
  staleness before the adapter compile-check. This makes validate self-healing
  (compile-checks against current framework) and is desirable; worth a one-line
  mention in the tooling notes so it is not mistaken for an unexpected mutation.
- **Operational (not a code defect):** `dist/vcfcf_sdk_synology_diskstation.1.0.0.23.pak`
  (16:46, predating this gate) may carry the stale jar. It is not shipped from
  the factory (release is the pak's own CI on a `v*` tag), but it should be
  rebuilt/discarded before any manual use so a pre-gate artifact is not shipped
  by hand.

## If shipped as-is
Operators get the intended fix: SDK paks now bundle a framework jar rebuilt from
current reviewed source; the build-23 silent-downgrade class is closed at its
only door. No downstream pak or import path regresses. Ship it (with the sibling
stitcher diff).
