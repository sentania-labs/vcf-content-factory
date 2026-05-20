---
id: RULE-007
decision_refs: []
---

# RULE-007: Grep both OpenAPI specs when investigating API support

When answering "does the API support X?", grep both `docs/operations-api.json` and `docs/internal-api.json`. The internal spec contains `/internal/*` endpoints (require `X-Ops-API-use-unsupported: true`) that often do things the public surface can't.

**If violated:** You miss supported functionality and implement inferior workarounds, or declare something impossible when an internal endpoint already handles it.
