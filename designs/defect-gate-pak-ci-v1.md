# Defect gate at the pak-repo release path — v1

Task #4 / P2 completion. Wires the defect gate (RULE-012) into the place
it actually needs to bite: a pak's own `v*`-tag CI build. Follows
`designs/defect-registry-v1.md` (the registry) and `designs/release-sdk-pointer-v1.md`
(the pointer model).

## Re-scope discovery (2026-06-13)

The original task #4 was "bundle→pak cascade + pak-repo CI wiring."
Reading the code re-scoped it:

- **SDK-pointer-release cascade is ALREADY done.** `_gate_publish`
  (`vcfops_packaging/publish.py:759`) detects an SDK adapter headline
  via `_is_sdk_adapter_source` and gates it by managed-pak name
  (`gate_pak(source_path.parent.name)`). So a factory `/publish` that
  emits a pointer to the synology/unifi pak **already refuses** while
  DEF-001/DEF-002 are open. No new cascade code needed for the path the
  seed defects live on.
- **Bundle→Tier1-MP cascade is a deferred, near-empty gap.** A bundle's
  `managementpacks:` references *Tier 1* MP YAMLs; Tier 1 MPs are not
  managed paks (no `managed_paks.md` entry, no `v*` release). Building a
  speculative lookup table for a set that is empty today would be
  mechanism the problem doesn't need. Stays documented in
  `_gate_publish`'s TOOLSET GAP note; register a `DEF-NNN` with the
  pak name directly to gate a managed pak.

**What's actually missing — and is the real value of task #4:** the
**official** pak release is a `v*` tag on the pak's *own* repo, built by
its own CI with **zero factory involvement**. The factory gate only
guards factory `/publish` (pointers). Nothing today stops a `v*` tag on
`vcf-content-factory-sdk-synology` from building and releasing a `.pak`
while DEF-001 is open. This design closes that.

## Vision

Make the gate run **inside each pak's `build-pak-on-tag.yml`**, before
the build, with no factory checkout:

1. **`defects.py` becomes standalone-runnable.** It is already pure
   stdlib (`re`, `dataclasses`, `pathlib`, `typing`). Add an argparse
   `__main__` so `python3 defects.py --pak <name> --registry <path>`
   works on a bare `curl` of the file — no package, no pip install.
   Contract:
   - `--pak <NAME>` (required for the pak path) · `--registry <PATH>`
     (default `./defects.md`).
   - exit **0** = no open blocking defect affects `<NAME>`.
   - exit **2** = open blocking defect(s) affect `<NAME>` — print one
     line per defect (id + title + first-seen + source).
   - exit **1** = malformed or missing registry.
   - (`--all` mirrors the CLI for completeness.)
   The existing package CLI (`cmd_defect_gate`, `_gate_publish`) and its
   imports of `gate_pak`/`gate_all`/`format_defect_line` are unchanged.

2. **Each pak's CI gates the tag build.** A step in
   `build-pak-on-tag.yml`, before `build-sdk`:
   - derive the managed-pak name from the repo name
     (`vcf-content-factory-sdk-<name>` → `<name>`);
   - run the **vendored, in-repo** `ci/defect_gate.py` (a committed copy
     of the factory gate script) against the **live** registry it fetches
     from main: `python3 ci/defect_gate.py --pak <name> --registry defects.md`
     where only `defects.md` is `curl`'d from
     `raw.githubusercontent.com/sentania-labs/vcf-content-factory/main/`;
   - on non-zero exit, **fail the build** with the printed defect lines,
     so the `.pak` is never produced/attached while a blocking defect is
     open.
   The canonical source is `designs/sdk-template-scaffold/build-pak-on-tag.yml`;
   the change propagates to the 4 pak repos + the template (same flow as
   the README propagation), and propagation **also vendors
   `ci/defect_gate.py`** (a copy of `vcfops_packaging/defects.py`) into
   each repo.

## Code is vendored; only the registry is fetched live

The split matters for security (Codex PR-18 P1):

- **The gate CODE is vendored, never fetched-and-executed from a mutable
  ref.** Fetching `defects.py` from factory `main` and running it on a
  pak's self-hosted release runner — which later holds
  `SDK_RUNTIME_SSH_KEY` — would let any factory-main commit execute
  arbitrary code across the repo trust boundary (tamper with the
  artifact, capture the deploy key, persist into later steps). Instead
  each pak repo carries a committed, reviewable `ci/defect_gate.py` and
  runs that. This mirrors the factory's existing posture for the
  `sdk-buildkit`: executable toolchain is consumed as a pinned/vendored
  artifact, **never** fetched live from main.
- **The registry DATA (`context/defects.md`) is fetched live from main.**
  It is inert markdown, parsed locally by the vendored gate, never
  executed — so a defect closed on main immediately unblocks the next
  tag and one opened on main immediately blocks, with no stale-registry
  window and no code crossing the boundary. The factory repo is public,
  so the `curl` needs no auth.
- **Drift is handled by re-vendoring.** When the gate's parser changes,
  `ci/defect_gate.py` is re-propagated alongside the workflow (the
  parser format is stable, so this is rare). The registry schema and the
  vendored parser are versioned together. A missing `ci/defect_gate.py`
  makes the step hard-fail (it refuses to fetch+execute remote code as a
  fallback).

## Boundaries / who does what

- `tooling` → the `defects.py` standalone entrypoint + tests
  (`vcfops_packaging/`). Triggers the **RULE-013 `framework-reviewer`
  gate** (run via prompt-adoption this session — agent type not yet
  registered).
- orchestrator → the canonical `build-pak-on-tag.yml` gate step
  (infra, `designs/sdk-template-scaffold/`).
- `sdk-adapter-author` → propagate to the 4 pak repos + template (direct
  pushes, infra-only, no version bump): copy the updated
  `build-pak-on-tag.yml` **and** vendor `ci/defect_gate.py` (a copy of
  `vcfops_packaging/defects.py`) into each repo. Post-merge only (main
  must carry the standalone `defects.py` first).

## Acceptance (negative proof)

- `python3 vcfops_packaging/defects.py --pak synology --registry context/defects.md`
  → exit 2, names DEF-001 (the same refusal the package CLI gives).
- A bare copy of `defects.py` run outside the package (no
  `vcfops_packaging` on `PYTHONPATH`) gives the identical result —
  proving the `curl`-and-run contract.
- The canonical workflow's gate step, dry-run against the live registry,
  refuses for synology/unifi and passes for compliance/vcommunity.

## Out of scope

- Bundle→Tier1-MP cascade (deferred gap above).
- Changing how `_gate_publish` already gates SDK pointer releases (works).
