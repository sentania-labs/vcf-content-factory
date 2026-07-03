# RULE-014 — Pak version lines: 0.x = hand-built, 1.x+ = CI release only

A hand-built SDK pak must never be version-indistinguishable from a CI
release. Two version lines, no exceptions:

1. **`0.0.0.<build_number>` — dev preview.** Every locally-invoked
   `build-sdk` (orchestrator, any agent, the user's shell) stamps the
   `0.x` line on all version surfaces (pak filename, pak metadata,
   manifest `Implementation-Version`, generated docs). `0.x` paks are
   for devel/prod *testing* only. They are never tagged, never attached
   to a GitHub Release, never referenced by `/publish`, and never left
   as the long-term installed version — after a test cycle passes, the
   next CI release supersedes them.

2. **`<adapter.yaml version>.<build_number>` (the `1.x+` line) — CI
   release builds only.** Produced exclusively by the tag-triggered CI
   release path (`build-pak-on-tag.yml` on a `v*` tag), which sets the
   explicit release opt-in for the builder. No human runs a release
   build by hand; if the release flag is being set outside CI, that is
   a violation of this rule, not a workaround.

Operational consequences:

- Installing a `0.x` test pak over an installed `1.x` release is a
  **version downgrade** — expect and use the platform's force/overwrite
  ("clobber") install path deliberately, and record the previously
  installed release version so the roll-forward target is known.
- A `0.x` pak found attached to a release, referenced in a bundle, or
  installed as the standing version on prod after its test window is a
  defect — file it in `context/defects.md`.
- RULE-012 (defect gate before `v*` tags) is unchanged and runs before
  any CI release build exists.

Enforced mechanically by `vcfops_managementpacks` `build-sdk` (default
`0.x` stamp; release line requires the explicit CI opt-in). The
mechanical guardrail does not relax the rule: if the tooling is ever
found stamping `1.x` on a local build, that is a blocking framework
defect.
