---
id: RULE-011
decision_refs: [DEC-001]
---

# RULE-011: Client-side multi-endpoint joins require Tier 2

When the target API has no common key or relationship between endpoints and the data model requires joining responses client-side across unrelated endpoints, route to the Java SDK (Tier 2) pipeline. MPB's chaining is single-axis and cannot model arbitrary joins.

Concrete example: Synology DSM — storage volumes, system info, and Docker endpoints share no common identifier and must be joined client-side.

**If violated:** The MP will build but produce incomplete or unjoinable data. Collection cycles return partial object graphs that cannot be assembled into the required resource hierarchy.
