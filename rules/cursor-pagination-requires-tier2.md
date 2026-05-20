---
id: RULE-016
decision_refs: []
---

# RULE-016: Cursor/token-in-body pagination requires Tier 2

When the target API uses AWS-style `nextToken` or GraphQL cursors for pagination, route to the Java SDK (Tier 2) pipeline. MPB supports offset/page-based pagination only.

**If violated:** The MP collects only the first page of results and silently misses remaining data.
