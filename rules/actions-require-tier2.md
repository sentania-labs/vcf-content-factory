---
id: RULE-014
decision_refs: []
---

# RULE-014: Programmatic actions require Tier 2

When the user wants to implement actions like "restart service," "trigger backup," or "rotate key," route to the Java SDK (Tier 2) pipeline. MPB has no action support.

**If violated:** The requirement cannot be fulfilled. MPB is collection-only.

**Note:** Most "I want an action" requests are really "I want a symptom + recommendation," which is Tier 1 alerting content, not an MP at all. Confirm the user needs an executable action before routing to Tier 2.
