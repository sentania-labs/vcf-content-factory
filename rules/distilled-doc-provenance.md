# RULE-017 — Distilled docs carry provenance: extract vs digest

When knowledge is pulled out of vendor source material, it takes exactly
one of two forms, and each has a home:

1. **Verbatim extract** — unmodified vendor text/data lifted out of a
   larger source (a PDF chapter, an API spec section). Lives under
   `reference/docs/extracted/<source-slug>/`. It is vendor-authored, so
   it inherits `reference/**` immutability (RULE-016). Adding a new
   extract is allowed; editing one is not.
2. **Digest** — our summary, interpretation, or correction of vendor
   material. Lives in `context/` and **must cite the extract or source
   file by path** so the next reader can check the digest against the
   original.

Consequences:

- A digest with no citation to its source is a defect in the digest
  (curator hunts these alongside DEAD-REF).
- Never blend the two: a `context/` file may quote short passages with
  citation, but a wholesale vendor dump belongs in
  `reference/docs/extracted/`, not in `context/`.
- Citations obey RULE-015 — the cited extract must be committed or
  registry-fetchable.

Rationale: provenance is what makes a digest trustworthy. If the reader
cannot trace a claim to the vendor original, the digest is
indistinguishable from a hallucination.

Origin: top-level reorg step 2 (2026-07-07), graduated from the reorg
work-plan per the earn-by-move gate (the `reference/docs/extracted/`
path now exists as a defined convention).
