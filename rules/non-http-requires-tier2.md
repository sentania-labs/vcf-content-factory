---
id: RULE-010
decision_refs: [DEC-001]
---

# RULE-010: Non-HTTP transport requires Tier 2

When the target API uses JDBC, SNMP, gRPC, binary protocols, or raw sockets, route to the Java SDK (Tier 2) pipeline. MPB is HTTP-only.

**If violated:** The MP will fail to build or produce zero collection data. MPB has no mechanism to handle non-HTTP transports.
