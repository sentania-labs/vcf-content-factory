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
   - `curl` `defects.py` + `defects.md` from
     `raw.githubusercontent.com/sentania-labs/vcf-content-factory/main/`;
   - run `python3 defects.py --pak <name> --registry defects.md`;
   - on non-zero exit, **fail the build** with the printed defect lines,
     so the `.pak` is never produced/attached while a blocking defect is
     open.
   The canonical source is `designs/sdk-template-scaffold/build-pak-on-tag.yml`;
   the change propagates to the 4 pak repos + the template (same flow as
   the README propagation).

## Why fetch from `main`, not pin

The registry is the *live* truth — a defect closed on main should
immediately unblock the next tag; a defect opened on main should
immediately block. Pinning would let a pak release against a stale
registry. (Mirrors `managed_paks.md`'s "latest release derived, not
pinned" stance.) The factory repo is public, so the `curl` needs no auth.

## Boundaries / who does what

- `tooling` → the `defects.py` standalone entrypoint + tests
  (`vcfops_packaging/`). Triggers the **RULE-013 `framework-reviewer`
  gate** (run via prompt-adoption this session — agent type not yet
  registered).
- orchestrator → the canonical `build-pak-on-tag.yml` gate step
  (infra, `designs/sdk-template-scaffold/`).
- `sdk-adapter-author` → propagate the workflow change to the 4 pak
  repos + template (direct pushes, docs/infra-only, no version bump).

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
