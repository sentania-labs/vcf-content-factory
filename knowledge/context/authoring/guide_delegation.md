# guide_delegation.md — moved

The delegation rules that previously lived here have been promoted
into `CLAUDE.md` itself. They are the spine of the orchestrator's
job and need to be in the always-loaded prompt rather than a file
the agent reads on demand.

See in `CLAUDE.md`:

- **You are the foreman** — the agent roster and the negative
  rules ("you do not write YAML / edit `src/vcfops_*/` / etc.")
- **Delegation protocol** — the eight numbered rules that govern
  recon-first, bottom-up authoring, serial authors, and parallel
  research
- **When the toolset is inadequate** — the punt / api-explorer /
  tooling decision tree
- **Workflow patterns** — the canonical flow per request type

This file is kept as a redirect because earlier sessions and other
context files reference it. Do not put delegation content back
here — that's the regression we just fixed.