# Defect registry + release gate — v1

Governance design (vault orchestration review 2026-06-12, P2). Interviewed
and decided interactively with Scott on 2026-06-12.

## Initial prompt

> We're adding defect tracking with release-gate semantics. Context: the
> foreign HostSystem edge persisted through round-2 devel acceptance in
> BOTH Synology and UniFi, and the secret-in-path hand-back from Synology
> build 14 is still open — review verdicts record warnings, but nothing
> forces open defects to converge before a v* release is cut. The full
> rationale is in the vault at
> scott/reports/vcfcf-orchestration-review-2026-06-12.md (P2).
>
> Design this with me before writing anything — interview me on the
> judgment calls:
> 1. Registry shape: context/defects.md with id, severity, first-seen
>    build, affected paks, status, closing evidence. Challenge or refine
>    the fields.
> 2. Gate semantics: which severities block a v* release? My starting
>    position: anything we'd be embarrassed to ship blocks; cosmetic
>    warnings don't. Help me draw that line concretely against the two
>    live defects.
> 3. Reviewer integration: sdk-adapter-reviewer's prompt gains a
>    mandatory registry-check section — every verdict re-asserts open
>    defects relevant to the pak under review, and a verdict that finds
>    a registry defect resolved proposes closing it with evidence.
> 4. Where the gate lives: /release flow refuses while blocking defects
>    are open. Decide together whether that's a rule (prose), a check in
>    the release CLI (mechanism), or both. I lean both.
>
> Then implement: seed the registry with the two live defects, update the
> reviewer prompt, wire the gate, add a rules/ entry. One PR.
> Acceptance (negative proof in the PR description): a dry-run v* release
> with an open blocking defect is refused naming the defect ids; closing
> the defect lets the same command proceed.

## Vision (interview outcomes)

The registry is the convergence mechanism the review machinery lacked:
warnings that survive acceptance stop being prose and become entries a
release mechanically refuses over.

Decided judgment calls (all four put to Scott; his selections):

- **Granularity: per-pak entries.** One entry = one issue on one
  artifact scope. Shared root causes cross-link via `Related:` and the
  lesson. Status stays scalar; the gate parser stays a pure
  severity x status x affects lookup. (Rationale: the foreign-edge story —
  proven-closed for synology, unproven for unifi — is two entries, not
  one ambiguous half-closed entry.)
- **Severity: binary `blocking | tracked`.** Only `blocking` gates.
  Entry bar: a review finding of WARNING or worse that survives build
  acceptance unfixed gets registered; NITs stay in review docs. No
  `waived` status — the only escape hatch is a severity downgrade with a
  dated note, so the git diff is the audit trail.
- **The two seeds, classified:**
  - DEF-001 secret-in-path (synology) → **blocking**. Plaintext
    credentials reachable from the on-disk adapter log is the definition
    of embarrassed-to-ship.
  - DEF-002 foreign full-set `setRelationships` edge (unifi) →
    **blocking** until unifi's own devel LLDP collect proves the matched
    HostSystem keeps its VMWARE children and gains the port child. The
    synology instance of the same idiom is seeded **closed** (DEF-003)
    on the build-16 devel 9.0.2 proof
    (`lessons/setrelationships-foreign-adapter-scoped.md`), recording
    the convergence and demonstrating the closed-entry shape.
- **Gate surface: rule + factory CLI now; pak-repo CI later.**
  `vcfops_packaging` gains `defect-gate` (standalone, the dry-run /
  pre-tag check) and the `release` / `publish` pipelines refuse over
  open blocking defects, naming ids. RULE-012 mandates a passing
  `defect-gate --pak <name>` before any v* tag is pushed to a managed
  pak repo. Wiring the pak repos' own CI (fetch `context/defects.md`
  from factory main, fail the v* build) is a **named follow-up** — it
  touches five external repos (4 paks + template) and exceeds this PR.

Who writes the registry: the orchestrator (or Scott), only. The
reviewer's verdict re-asserts open defects for the pak under review and
*proposes* openings/closures with evidence; it never edits
`context/defects.md` (its write boundary stays `context/reviews/`).

## Follow-ups (out of this PR)

- Pak-repo CI wiring: v* tag workflow fetches the factory registry and
  fails when an open blocking defect names the pak.
- **Bundle→pak cascade (TOOLSET GAP, reported by `tooling` at
  implementation).** `release bundle <slug>` / `publish` gate only the
  bundle's own `Affects:` token; a bundle's `managementpacks:` field
  holds Tier 1 YAML paths with no reliable mapping to Tier 2 adapter
  names in `managed_paks.md`. Until a lookup lands in
  `vcfops_packaging`, RULE-012 §3 makes the cascade a manual
  orchestrator duty (`defect-gate --pak <name>` per referenced pak).
- Candidate third entry: the MOID cross-stitch fix for **compliance**
  was "queued" as of 2026-06-10
  (`lessons/stitch-moid-not-unique-across-vcenters.md`) — verify and
  register if still unfixed at next compliance review.
