---
id: RULE-010
---

# RULE-010: Never write framework output to reference/docs/

The `reference/docs/` directory contains immutable vendor source material — OpenAPI specs, PDFs, and vendor documentation. Framework-generated content belongs in `context/`, `lessons/`, or the repo root.

**If violated:** Vendor documentation becomes mixed with framework output, breaking the trust boundary. Users can no longer distinguish authoritative vendor specs from framework-generated content.

RULE-016 (`reference-immutable.md`) generalizes this to all of
`reference/**` (including the gitignored `reference/references/`
clones): additions allowed, modifications never.
