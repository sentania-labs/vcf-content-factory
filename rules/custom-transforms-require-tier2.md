---
id: RULE-018
decision_refs: []
---

# RULE-018: Custom response transforms require Tier 2

When collection requires regex extraction, arithmetic computation, conditional logic, or schema reshaping beyond MPB's BASE64/NONE transforms, route to the Java SDK (Tier 2) pipeline.

**If violated:** The MP cannot extract the required metrics or properties from the API response. Data appears malformed or missing.
