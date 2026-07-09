# Rules Index

Read every rule at session start. Rules are absolute — obey without question.

| ID | Rule | File |
|---|---|---|
| RULE-001 | Use only repo content as source of truth | [source-of-truth.md](source-of-truth.md) |
| RULE-002 | Never fabricate metric or attribute names | [no-fabricated-metrics.md](no-fabricated-metrics.md) |
| RULE-003 | Recon before authoring; reuse before authoring from scratch | [recon-and-reuse.md](recon-and-reuse.md) |
| RULE-004 | Tier routing based on API capabilities | [tier-routing.md](tier-routing.md) |
| RULE-005 | Always validate before installing | [validate-before-install.md](validate-before-install.md) |
| RULE-006 | All authored content uses `[VCF Content Factory]` prefix | [content-prefix.md](content-prefix.md) |
| RULE-007 | UUIDs are part of the contract | [uuid-stability.md](uuid-stability.md) |
| RULE-008 | Never write secrets to disk | [no-secrets-on-disk.md](no-secrets-on-disk.md) |
| RULE-009 | No destructive actions on production instances | [no-destructive-on-prod.md](no-destructive-on-prod.md) |
| RULE-010 | Never write framework output to reference/docs/ | [docs-immutable.md](docs-immutable.md) |
| RULE-011 | Wireframe + plan-mode approval before dashboard authoring | [wireframe-before-dashboard.md](wireframe-before-dashboard.md) |
| RULE-012 | No release while a blocking defect is open in `context/defects.md` | [release-gate-defects.md](release-gate-defects.md) |
| RULE-013 | Framework Python (`src/vcfops_*/`) changes pass `framework-reviewer` before merge | [framework-review-gate.md](framework-review-gate.md) |
| RULE-014 | Pak version lines: `0.x` = hand-built, `1.x+` = CI release only | [pak-version-lines.md](pak-version-lines.md) |
| RULE-015 | Cited artifacts must be committed or registry-fetchable — no ephemeral citations | [cited-artifacts-reproducible.md](cited-artifacts-reproducible.md) |
| RULE-016 | `reference/**` is read-only; corrections live in `context/` | [reference-immutable.md](reference-immutable.md) |
| RULE-017 | Distilled docs carry provenance: verbatim extract → `reference/docs/extracted/`, digest → `context/` with citation | [distilled-doc-provenance.md](distilled-doc-provenance.md) |
