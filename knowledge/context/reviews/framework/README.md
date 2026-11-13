# Framework reviews

Read-only review reports from the **`framework-reviewer`** agent — the
skeptical correctness/regression gate on `src/vcfops_*/` Python changes
(loaders, renderers, builders, CLIs). The framework-code sibling of the
SDK reviews one directory up (`knowledge/context/reviews/*.md`).

One report per reviewed change: `<area>-<pr-or-date>.md` (e.g.
`dashboards-render-pr27.md`, `packaging-builder-2026-06-14.md`).

The reviewer is spawned after `tooling` reports a `src/vcfops_*/` change and
**before** the PR is opened (CLAUDE.md delegation step 9 + "After tooling
changes"). Scope is **blanket** — every `src/vcfops_*/` diff. A
**CHANGES REQUESTED** verdict (≥1 BLOCKING) blocks the PR until `tooling`
resolves it. Design of record: `knowledge/designs/framework-reviewer-v1.md`.

## Index

Started 2026-11-12; earlier reports are in this directory by filename only.

| Report | Change | Verdict |
|---|---|---|
| `stock-id-guard-2026-11-12.md` | `tooling/stock-id-guard`: stock content id guard and baseline (#345) | APPROVE (0 B / 9 W / 7 N) |
| `stitch-post-events-numeric-keydiff-2026-11-12.md` | `tooling/stitcher-post-events-numeric`: stitcher `post`, `pushEvents`, numeric properties, icon hints, `keydiff` | CHANGES REQUESTED (3 B / 6 W / 5 N); all fixed in one pass |
