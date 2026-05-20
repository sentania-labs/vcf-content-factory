---
id: RULE-001
decision_refs: []
---

# RULE-001: Use only repo content as source of truth

Use only `docs/vcf9/`, the OpenAPI specs (`docs/operations-api.json`, `docs/internal-api.json`), other `docs/` content, and existing YAML under the content directories. Do not invent functions, operators, metric keys, or API endpoints.

**If violated:** The content may validate locally but fail at runtime when VCF Operations encounters undefined functions, unknown metric keys, or invalid API patterns.
