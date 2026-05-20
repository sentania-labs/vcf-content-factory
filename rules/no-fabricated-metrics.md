---
id: RULE-002
decision_refs: []
---

# RULE-002: Never fabricate metric or attribute names

Metric and property keys must come from existing YAML, `docs/vcf9/metrics-properties.md`, or a name the user provided. Ask if you can't ground it.

**If violated:** The content installs cleanly but produces zero data. VCF Operations silently ignores unrecognized metric keys.
