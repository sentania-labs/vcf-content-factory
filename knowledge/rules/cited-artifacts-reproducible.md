# RULE-015 — Cited artifacts must be reproducible

Any file cited by path from the governance corpus (`rules/`, `lessons/`,
`context/`, `designs/`, agent prompts, skills, CLAUDE.md) must be either:

1. **committed** to this repository, or
2. **deterministically re-fetchable** via a registry the bootstrap runs
   (`context/reference_sources.md`, `context/managed_paks.md`, or a
   successor registry).

No citation may point at an ephemeral local file — a download that lives
only on one machine, a scratch path, or gitignored session debris. A
fresh clone plus bootstrap must be able to resolve every citation in the
corpus, or the corpus is lying to the next user.

Consequences:

- Before citing a local-only artifact (e.g. a vendor pak you downloaded
  by hand), either add it to a fetch registry with a stable source, or
  commit the relevant extract, or describe the finding in enough detail
  in `context/` that the citation is unnecessary. If the source cannot
  be redistributed or re-fetched (licensing), the citing document must
  say so explicitly ("local-only artifact; not reproducible — findings
  summarized here in full").
- Known standing exception to fix or annotate: `reference/references/tvs/`
  (Broadcom TVS paks — manual downloads, cited by
  `context/api-maps/tvs-*.md` and used as pak-compare references).
  Any new citation of a TVS pak must carry the local-only disclaimer
  until a fetch path exists.
- The curator hunts violations as DEAD-REF; treat a citation that a
  fresh clone cannot resolve as a defect in the citing document.

Origin: the top-level reorg review of 2026-07-06 (working from the
ops-PM fresh-eyes review, `context/reviews/pm-feedback-2026-06-29.md`,
whose open hole #1 was exactly this class of citation), confirmed live
the same day when `reference/references/tvs/` paks were load-bearing for a design
decision (switch-port naming convention) while absent from every fetch
registry.
