---
id: RULE-013
decision_refs: []
---

# RULE-013: Advanced auth mechanisms require Tier 2

When the target API requires OAuth2 refresh flows, Kerberos/SPNEGO, mTLS with cert rotation, AWS SigV4, or HMAC-per-request, route to the Java SDK (Tier 2) pipeline. MPB supports Basic, Token, and Custom header auth only.

**If violated:** Authentication fails at collection time. MPB cannot implement the required auth flow.
