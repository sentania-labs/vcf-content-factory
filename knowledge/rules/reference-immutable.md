# RULE-016 — `reference/**` is read-only; corrections live in `context/`

Everything under `reference/` (vendor API docs in `reference/docs/`,
external example repos in `reference/references/`) is authored by
someone else and is **never edited in place**. This generalizes
RULE-010 (which protects `reference/docs/` specifically) to the whole
immutable root.

- **Additions are allowed; modifications are not.** Adding a new vendor
  extract or bootstrap-cloning a new reference repo is fine. Changing a
  byte of an existing file under `reference/` is a violation — even to
  "fix" an obvious vendor error.
- **Corrections, digests, and findings** about reference material live
  in `context/` (or `lessons/` if hard-won) and cite the source by path
  (e.g. "`reference/docs/vcf9/supermetrics.md` says X, but live behavior
  is Y — see investigation Z").
- Framework output, rendered JSON, test artifacts, and anything an agent
  generates never lands under `reference/` (RULE-010).
- `scripts/immutability_guard.sh` enforces the modification ban
  mechanically; the guard failing is not an obstacle to route around —
  it is the rule working.

Rationale: the mutability axis is what RULE-010 was always protecting.
Co-locating our corrections with vendor text destroys provenance — the
next reader can no longer tell what the vendor said from what we think.

Origin: top-level reorg step 2 (2026-07-07), graduated from the
reorg work-plan per the earn-by-move gate; generalization of RULE-010.
