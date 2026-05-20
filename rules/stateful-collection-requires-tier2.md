---
id: RULE-012
decision_refs: []
---

# RULE-012: Stateful collection requires Tier 2

When collection requires WebSocket subscriptions, event-stream consumption, or long-polling, route to the Java SDK (Tier 2) pipeline. MPB is stateless request/response per cycle.

**If violated:** The MP cannot maintain the required connection state and fails to collect data that depends on persistent subscriptions or event streams.
