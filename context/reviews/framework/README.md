# Framework reviews

Read-only review reports from the **`framework-reviewer`** agent — the
skeptical correctness/regression gate on `src/vcfops_*/` Python changes
(loaders, renderers, builders, CLIs). The framework-code sibling of the
SDK reviews one directory up (`context/reviews/*.md`).

One report per reviewed change: `<area>-<pr-or-date>.md` (e.g.
`dashboards-render-pr27.md`, `packaging-builder-2026-06-14.md`).

The reviewer is spawned after `tooling` reports a `src/vcfops_*/` change and
**before** the PR is opened (CLAUDE.md delegation step 9 + "After tooling
changes"). Scope is **blanket** — every `src/vcfops_*/` diff. A
**CHANGES REQUESTED** verdict (≥1 BLOCKING) blocks the PR until `tooling`
resolves it. Design of record: `designs/framework-reviewer-v1.md`.
