# RULE-012 — No release while a blocking defect is open

No artifact ships while `knowledge/context/defects.md` carries an **open
`blocking`** defect affecting it. "Ships" means any of:

1. **A v* tag on a managed pak repo.** Enforced by the `pre-push` hook
   in `.githooks/`, which runs the gate automatically when a `v*` tag is
   pushed from a pak clone. Bootstrap points every registered clone at it
   via `core.hooksPath`, so this needs no per-repo setup. To check ahead
   of a push:

   ```
   python3 -m vcfops_packaging defect-gate --pak <name>
   ```

   Non-zero exit = the release is refused. Fix or legitimately close the
   named defects first. This applies to the orchestrator, every agent,
   and the user alike; `git push --no-verify` bypasses the hook and is a
   deliberate, auditable end-run, in the same category as a force-push,
   not a fast path.

   The hook fails safe: a missing interpreter, an absent registry or an
   unfindable factory checkout warns and allows the push. Only an open
   blocking defect naming that pak refuses it. An infrastructure problem
   must never stop someone pushing a fix.

2. **`/release` and `/publish`.** The `vcfops_packaging` `release` and
   `publish` commands run the same check mechanically and refuse,
   naming the open defect ids, when the item being released has an open
   blocking defect (matched by its `Affects:` token — pak name for
   `sdk-adapter`, `<type>/<slug>` otherwise). Do not work around a
   refusal by editing manifests or bypassing the CLI.

3. **Bundle cascade is manual until the tooling follow-up lands.** The
   CLI does not yet map a bundle's contents to the managed paks it
   references (TOOLSET GAP, see `knowledge/designs/defect-registry-v1.md`
   follow-ups). Until it does: before releasing or publishing a bundle
   that references a managed pak, the orchestrator MUST run
   `defect-gate --pak <name>` for each referenced pak and treat a
   non-zero exit as a refusal of the bundle.

Supporting obligations that keep the gate honest:

- **Graduation.** Any review finding of WARNING or worse that survives
  build acceptance unfixed MUST be registered in `knowledge/context/defects.md`
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
  orchestrator (or the user) edits `knowledge/context/defects.md`.
- **Which registry.** Selection is by file presence, not configuration:
  a `defects.local.md` sibling of `knowledge/context/defects.md` wins
  when it exists, otherwise that file. The local sibling is how someone
  working from a clone of this framework gates their own artifacts
  without inheriting, or being blocked by, upstream's registry.
  Upstream never ships a `defects.local.md`, which is why a `git pull`
  cannot conflict with one. It is a registered RULE-015 standing
  exception in `scripts/path_reference_audit.sh` for exactly that
  reason: cited by name across the gate, the doctor and this rule, but
  present only in a downstream checkout.
- **A malformed entry blocks only itself.** The parser isolates per
  entry: a bad entry whose `Affects:` is readable gates exactly that
  artifact, and one whose `Affects:` cannot be read gates nothing and is
  reported loudly. One sloppy edit must never stop every release
  everywhere, which is what it used to do.
- **An absent registry warns, it does not refuse.** Gating nothing is
  reported; it is not treated as a clean bill of health.

Design of record: `knowledge/designs/defect-registry-v1.md`.
