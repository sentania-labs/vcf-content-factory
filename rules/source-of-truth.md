---
id: RULE-001
---

# RULE-001: Use only repo content as source of truth

Use only `docs/`, OpenAPI specs (`docs/operations-api.json`, `docs/internal-api.json`), `context/`, and existing YAML under content directories. Do not invent functions, operators, metric keys, API endpoints, or wire format details.

**If violated:** Content may validate locally but fail at runtime when VCF Operations encounters undefined functions, unknown metrics, or invalid patterns.
