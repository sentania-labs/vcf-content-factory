---
id: RULE-017
decision_refs: []
---

# RULE-017: Link-header pagination requires Tier 2

When the target API uses RFC 5988 Link headers for pagination (e.g., GitHub, GitLab), route to the Java SDK (Tier 2) pipeline. MPB doesn't parse `Link:` headers.

**If violated:** The MP collects only the first page of results and silently misses remaining data.
