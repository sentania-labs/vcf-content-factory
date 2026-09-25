# Framework review: pak-compare gate, -proc:none, multi-token Affects, buildkit sidecar (2026-09-25, round 1)

Branch `fix/pipeline-hardening-round` (commits 7fb4be8, dbaa4cc, 2381e80),
reviewed by `framework-reviewer` against origin/main. The reviewer's
harness could not write files, so the orchestrator saved its report here
verbatim in substance.

```
FRAMEWORK REVIEW
  area: src/vcfcf_managementpacks/{cli,buildkit,sdk_builder}.py, src/vcfcf_packaging/defects.py, .github/workflows/publish-buildkit.yml, knowledge/context/defects.md
  change: pak-compare and build-sdk now fail on BLOCKING (#181); -proc:none on javac; a multi-token Affects is malformed (#153); buildkit publishes a .sha256 sidecar and runs on GitHub-hosted
  verdict: CHANGES REQUESTED
  findings: 1 BLOCKING / 3 WARNING / 5 NIT
  checks re-run: validate-chain pass (7 packages + packaging); tests 1919 passed / 0 failed / 8 skipped with the managed paks linked; render-regression n/a; pak-compare 0 BLOCKING / exit 0 on all shipped and local paks, exit 1 on every negative case
```

## BLOCKING

1. **`src/vcfcf_packaging/defects.py:499-512` (`_known_pak_names` / `_readable_affects`).**
   RULE-012; pattern of anchor 00d3382 (proven on one path, inert on the
   other). "Fails closed on a known pak name" only works when defects.py is
   imported as a package. Run as a script (how every pak repo runs its
   vendored `ci/defect_gate.py`), the relative import
   `from .managed_paks import` fails, the broad `except` swallows it, the
   known-pak set is empty, and the entry "blocks nothing". Reproduced: open
   blocking DEF-900 with `Affects: synology (the storage adapter)`; script
   mode `--pak synology` returns rc=0, package mode returns DEF-900. Every
   new test monkeypatches `_known_pak_names`. Fix: in `gate_pak`, treat a
   malformed entry whose first token equals the pak being gated as scoped
   to it (no registry lookup needed, works in both modes); add a subprocess
   test running defects.py as a script; warn instead of silently returning
   an empty set when the lookup fails.

## WARNING

1. **Reference selection differs between CLIs and build-sdk.** Directory
   mode fails if any reference has a BLOCKING finding; build-sdk gates
   only against `sorted(...)[0]` (alphabetically first, not closest).
   Reproduced false failure: vcommunity-vsphere 12 against compliance 50,
   unifi 13, synology 30 and MPB unifi_integration 14 (0 BLOCKING against
   each SDK reference, 7 against the MPB one, rc=1). Fails closed, but
   false failures. Fix: one rule everywhere, for example gate on the
   closest reference (results[0] after the existing closest-first sort).
   Authority: `.claude/agents/sdk-adapter-author.md:151`,
   `.claude/skills/vcfops-sdk-adapter/SKILL.md:50`.
2. **Re-vendor requirement unrecorded.** All six pak repos vendor the old
   519-line parser; #153 does not reach the release gate until they are
   re-vendored (after BLOCKING 1 is fixed). Record in the PR and
   `tier2_architecture.md`.
3. **Dangling citation.** DEF-020/021 Severity-notes cite
   `knowledge/context/approvals/2026-09-25-scott-decisions.md` item 14,
   which is not on this branch or main (only on
   `docs/compliance-v3-esx-rename-and-release`, 10f526f). The quote matches
   word for word. Fix: land the approvals doc first or bring it into this
   PR.

## NIT

1. `sdk_builder.py:228`: framework-jar `-proc:none` has no test.
2. `Severity-note` field missing from the defects.md schema table.
3. defects.md schema text (lines 25-29, 49) does not say a multi-token or
   non-`factory:` Affects is malformed, or that a closed entry with a
   malformed Affects now blocks as open.
4. `.github/release-notes-buildkit.md` does not mention the `.sha256`
   sidecar or the new non-zero exits.
5. Follow-up (not in this diff): the scaffold workflow design
   `knowledge/designs/sdk-template-scaffold/build-pak-on-tag.yml` and the
   six pak workflows still carry the grep that falsely passes 10/20/30
   BLOCKING; the exit code under `pipefail` now overrides it, but a
   consumer pinned to a kit older than 1.0.11 still gets the false pass,
   and nothing verifies the sidecar yet. Scheduled for the template and
   pak workflow round.

## What checked out

- No BLOCKING-yields-0 path in pak-compare: manifest.txt removed (2
  BLOCKING), corrupt pak, missing pak and a raising compare all exit 1;
  the six consumer workflows run the gate step under `set -euo pipefail`.
- Shipped paks (compliance 80, synology 30, unifi 13, vcommunity-vsphere
  12) and local vcommunity 1.0.0.11 / vcommunity-os 1.0.0.1: 0 BLOCKING.
- `build-sdk --release` with the rebuilt 1.0.11 kit on all six adapters:
  rc=0, 0 BLOCKING.
- `-proc:none`: all six compile; no annotation processor exists in any
  adapter jar or source.
- Sidecar: `sha256sum -c` passes; the consumer pattern `sdk-buildkit-*.tgz`
  does not match the `.sha256`; floating-release pruning correct.
- Lab to GitHub-hosted: nothing lost; the job reaches only github.com.
- Live registry: 21 entries, 0 errors, only vcommunity-os blocked
  (DEF-004); origin/main's registry would produce 4 synthetic blockers
  under the new parser, so the Affects clean-up was necessary.
- BUILDKIT_VERSION 1.0.11 correct (v1.0.10 tag exists). No em-dashes.
- Test count: 1919 pass with pak clones linked (claimed 1902); 6
  environmental failures in a bare worktree.
