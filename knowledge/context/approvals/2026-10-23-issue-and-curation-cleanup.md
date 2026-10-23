# Owner approval: issue list and curation cleanup, 2026-10-23

Scott's go for the outward-facing GitHub changes in this round, recorded
before execution per the owner rule that such actions need his words
preserved as an artifact.

## Verbatim

- **2026-10-22, status question:** "is our list of open issues accurate?"
- **2026-10-23, the go:** "let's clean up the issues and curator refernces
  so they reflect rality"

## Scope executed under these words

1. Close the nine factory issues whose fixes merged in PR #234 (196, 189,
   152, 186, 207, 190) and PR #236 (202, 198, 199) but stayed open because
   the PR bodies used the comma form of the closing keyword, which GitHub
   honors only for the first number. Each close carries a comment naming
   the merging PR.
2. Reconcile tracker #182 against the pak repos and release tags as of
   2026-10-23: tick what shipped, annotate what merged but has not been
   released, strike the vcommunity items closed on retirement.
3. Apply the 2026-10-22 curation report's findings in the repo: the
   retired `qa` profile wording, the buildkit 1.0.12 conditional, DEF-017
   closure, the retired-pak defects, the unsigned-pak correction banners
   on the cleanroom spec files, and the ghcr design status line.

## Not covered

- Any pak release or tag.
- Closing any issue in a pak repo.
- Prod, in every form.
