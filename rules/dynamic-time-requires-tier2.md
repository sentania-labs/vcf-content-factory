---
id: RULE-015
decision_refs: []
---

# RULE-015: Dynamic time parameters require Tier 2

When the target API requires time-variable parameters like `from=now-5m&to=now`, signed nonces, or request-time HMAC, route to the Java SDK (Tier 2) pipeline. MPB has no time-variable substitution.

**If violated:** The MP sends static timestamps and collects stale or incomplete data.
