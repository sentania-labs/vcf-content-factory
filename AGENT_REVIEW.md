# Repository Review Notes (Code + Agent Config Coherence)

Date: 2026-04-13

## High-impact inconsistencies

1. `.claude/agents/dashboard-author.md` hard-limits authoring to `ResourceList` + `View` widgets, while the codebase and project docs support 10 widget types.
2. Several agent skills/prompts point to `references/*.md` files that do not exist in this repository, creating dead guidance paths.
3. `CLAUDE.md` repository layout omits the `recommendations/` directory even though recommendation YAML is a first-class path in alert tooling.

## Implementation/documentation drift

4. `vcfops_alerts` validates recommendation references but REST sync omits recommendation payload fields by design, so authored recommendations are not applied on the REST install path.
5. `vcfops_alerts.cli` suppresses recommendation/symptom load exceptions during validate preflight, which can hide the real parse error source and surface secondary reference errors instead.

