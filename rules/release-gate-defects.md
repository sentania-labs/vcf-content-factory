# RULE-012 — No release while a blocking defect is open

No artifact ships while `context/defects.md` carries an **open
`blocking`** defect affecting it. "Ships" means any of:

1. **A v* tag on a managed pak repo.** Before pushing a `v*` tag to any
   pak registered in `context/managed_paks.md`, run:

   ```
   python3 -m vcfops_packaging defect-gate --pak <name>
   ```

   Non-zero exit = the release is refused. Fix or legitimately close the
   named defects first. This applies to the orchestrator, every agent,
   and the user alike — there is no fast path around it.

2. **`/release` and `/publish`.** The `vcfops_packaging` `release` and
   `publish` commands run the same check mechanically and refuse,
   naming the open defect ids, when the item being released has an open
   blocking defect (matched by its `Affects:` token — pak name for
   `sdk-adapter`, `<type>/<slug>` otherwise). Do not work around a
   refusal by editing manifests or bypassing the CLI.

3. **Bundle cascade is manual until the tooling follow-up lands.** The
   CLI does not yet map a bundle's contents to the managed paks it
   references (TOOLSET GAP, see `designs/defect-registry-v1.md`
   follow-ups). Until it does: before releasing or publishing a bundle
   that references a managed pak, the orchestrator MUST run
   `defect-gate --pak <name>` for each referenced pak and treat a
   non-zero exit as a refusal of the bundle.

Supporting obligations that keep the gate honest:

- **Graduation.** Any review finding of WARNING or worse that survives
  build acceptance unfixed MUST be registered in `context/defects.md`
  before the next build of that artifact is briefed. A warning that
  never graduates is how defects outlived acceptance before this rule
  existed.
- **Closing requires evidence.** `Status: closed` without a concrete
  `Closing-evidence:` field is invalid — the gate treats a malformed
  entry as an error, not as closed.
- **No waivers.** There is no `waived` status. A conscious decision to
  ship despite a defect is a severity downgrade to `tracked` with a
  dated note in the entry, made by the orchestrator with the user's
  explicit approval — auditable in the diff.
- **Registry writes are orchestrator-only.** Reviewers and authors
  propose openings and closures in their verdicts; only the
  orchestrator (or the user) edits `context/defects.md`.

Design of record: `designs/defect-registry-v1.md`.
