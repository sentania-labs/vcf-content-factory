---
id: RULE-004
---

# RULE-004: Tier routing based on API capabilities

Management packs default to Tier 1 (MPB) unless a Tier 2 trigger fires. MPB requires simple HTTP APIs with key-joinable relationships.

**Route to Tier 2 (Java SDK) when:**
- Non-HTTP transport (JDBC, SNMP, gRPC, binary protocol, raw socket)
- Client-side multi-endpoint joins with no common key
- Stateful collection (WebSocket, event-stream, long-poll)
- Advanced auth (OAuth2 refresh, Kerberos, mTLS with cert rotation, AWS SigV4, HMAC-per-request)
- Programmatic actions ("restart service," "trigger backup")
- Dynamic time/computed parameters (API requires `from=now-5m&to=now`, signed nonces, request-time HMAC)
- Cursor/token-in-body pagination (AWS-style `nextToken`, GraphQL cursors)
- Link-header pagination (RFC 5988)
- Custom response transforms (regex extraction, arithmetic, conditional logic, schema reshape)
- Nested-array iteration in expressions (`data.*.metrics.*.value`)
- Per-instance long-lived state (schema cache surviving across cycles)
- APIs with parent-child relationships encoded in URL paths (Redfish `/Systems/{id}/Processors/{id}`)

See `knowledge/context/tier_decision_framework.md` for the full trigger table and decision flow. Consult `lessons/` for targets that have been evaluated (Synology, Dell Redfish).

**If violated:** The MP will build but produce incomplete data, unjoinable relationships, or fail collection. MPB's limitations surface as runtime failures, not build errors.
