# Internal review — ops-PM fresh-eyes feedback (2026-06-29)

**Source:** an operations PM read the repo file-by-file and provided
stream-of-consciousness feedback (English second language; disconnected because
typed while scrolling). Captured from `tmp/Untitled document.pdf`. This doc is
the disposition/tracking backbone for the internal review it seeds.

## 1. Domain corrections (the gold)

| Feedback | Disposition |
|---|---|
| **SM time-misalignment:** a SM that depends on other SMs reads the *previous* collection's value; ideally don't split a complex SM into multiple SMs. | **CODIFIED** — `context/authoring/supermetric_authoring.md` §3 (cross-SM one-cycle lag + prefer single self-contained formula) + `.claude/agents/supermetric-author.md` pitfall list. |
| **view-author only does List View** (not Distribution/Trend) — state it. | **CODIFIED** — `.claude/agents/view-author.md` hard rule 8 (List View only; non-list → BLOCKED/TOOLSET GAP). |
| **Dashboards:** deprecate Object Picker (`ResourceList`) in favor of self-provider `View`; recommend Heat Map + Health Chart. | **DEFERRED — design consideration.** SME wants to be thoughtful (self-provider View is more flexible long-term but not a blanket deprecation yet). Do NOT codify a deprecation. Decide deliberately, then update `dashboard-author` defaults. → TODO. |

## 2. Reachability / corpus-navigability findings → `curator` pass (running)

| Feedback | Disposition |
|---|---|
| `view_dashboard_design_guide.md` is index-listed in `context/README.md` but NOT reachable from the `view-author → guide_content_authoring.md` chain (orphaned from its fire point). | Seeded into the **curator** audit (2026-06-29) as the lead "reachability" finding; generalize to all agents. Fix per the curator report. |
| Wants connected files (agent ↔ skill ↔ guide) to be clickable links. | Tied to the **doc-site** TODO (§4); GitHub markdown already renders relative links — partial win possible by adding explicit links in prompts/guides. |

## 3. Onboarding / credibility questions → answers (to document)

- **"Define *the framework* (add a link)."** → README polish TODO.
- **"The YAML is validated against the live wire format — what is the wire format itself validated against?"** (the deep one). **Answer:** our YAML is validated against the renderer's wire-format *model*; that model's ground truth bottoms out in three layers — (a) reference export specimens under `references/`, (b) the cleanroom spec (`context/cleanroom-spec/`, reverse-engineered from the SDK + live Ops), and ultimately (c) **does it install and render on a live VCF Ops instance** (the QA / install-verify loop). Not circular — it terminates in empirical install verification. → document in an onboarding/architecture note.
- **"How does the SM agent know the DSL — told, or deductive?"** **Answer:** the `.claude/agents/<agent>.md` prompt + the matching skill (e.g. `vcfops-supermetric-dsl`) + `context/` guides, loaded at delegation time. The model's general capability helps; the *domain correctness* is curated in the repo. → make explicit in onboarding.

## 4. Strategic initiatives (parked / scoping)

- **Doc-site → TODO (GitHub Pages).** SME envisions GitHub Pages, possibly via Samir Roshan's "architecture-to-autonomy" template; wants HTML+SVG, big-picture-while-drilling-down, clickable cross-links. SME thinking more before scoping. Open decision: **auto-generated** (stays in sync) vs hand-curated; who owns it (Samir vs factory). **Do not build yet.**
- **Top-level reorg → measured 4-bucket; scope before executing.** SME buckets: **content / tooling / internal-factory-reference / external-reference**. "Room for improvement, but don't over-clean." First-cut mapping + risk in §5.

## 5. Top-level reorg — first-cut mapping + risk (for SME review, NOT executed)

Proposed conceptual buckets and current dir mapping:

| Bucket | Dirs | Move risk |
|---|---|---|
| **content** | `content/`, `bundles/`, `releases/`, repo-root `dashboards/` (SDK-adapter pak content) | MEDIUM — referenced by loaders, `.gitignore`, agent prompts |
| **tooling** | `vcfops_*/` (10+ packages), `scripts/`, `tests/` | **HIGH — effectively immovable.** `vcfops_*` are Python module paths (`python3 -m vcfops_supermetrics`) wired into CLAUDE.md, CI, every agent. Moving breaks imports without a packaging refactor. |
| **internal / factory / reference** | `context/`, `lessons/`, `rules/`, `designs/`, `diagrams/`, `.claude/`, `memory/` | HIGH for `.claude/` (Claude Code expects root); MEDIUM for the rest (referenced across prompts) |
| **external reference** | `docs/` (vendor), `references/`, `third_party/` | **LOW — the safest to group.** Referenced in a few prompts (`docs/vcf9/...`) but a contained blast radius |
| **must stay at root** | `.github/` (GitHub requirement), `CLAUDE.md`, `ADMIN.md`, `Memory.md`, `README*`, `.env`, `.gitignore` | n/a |

**Recommendation:** deliver the comprehension win as a **top-level architecture map** (a `STRUCTURE.md` or README section that groups the existing dirs into the 4 buckets) — **zero risk, full clarity.** Then, optionally, the *only* low-risk physical move is grouping the **external-reference** dirs under one parent. The `vcfops_*` packages and `.claude`/`.github`/`content` are not worth the churn to move. Awaiting SME's pick: map-only, or map + the external-reference consolidation.

## Deferred / minor

- Mangled DSL formula ("Extra close brace") in the PM's doc — almost certainly their Google-Doc math-mode rendering of our `funct(...)` example, not a bug in our docs. Verify which; low priority.
