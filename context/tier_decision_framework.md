# Tier Decision Framework (Tier 1 vs Tier 2)

When `mp-designer` is interviewing for a new management pack, it must
decide whether the result is **Tier 1** (MPB / YAML, generated as a
BuilderFile design) or **Tier 2** (native Java SDK adapter). This
document is that decision.

For the architecture itself see
[`tier2_architecture.md`](tier2_architecture.md). For the upstream
trigger list see
[`cleanroom-spec/spec/12-mpb-handoff-for-vcf-cf.md § 6`](cleanroom-spec/spec/12-mpb-handoff-for-vcf-cf.md).

## Default: Tier 1

Tier 1 (MPB) is the default. It's faster to author, easier to review,
needs no JDK on the user's machine, and produces a smaller pak. The
designer should only propose Tier 2 if one or more of the triggers
below applies AND there's no reasonable Tier 1 workaround.

## Triggers (promotion to Tier 2)

If any row is "yes," propose Tier 2 and cite the trigger in the design
artifact's **Promotion reasoning** section.

| # | Trigger | Concrete example | Why Tier 1 can't |
|---|---|---|---|
| 1 | Non-HTTP transport | JDBC, SNMP, gRPC, binary protocol, raw socket | MPB is HTTP-only |
| 2 | Complex data-model stitching | Synology: storage volumes + system info + Docker, joined client-side across unrelated endpoints | MPB chaining is single-axis, no arbitrary join |
| 3 | Stateful collection | WebSocket subscription, event-stream consumption, long-poll | MPB is stateless request/response per cycle |
| 4 | Advanced auth | OAuth2 refresh, Kerberos / SPNEGO, mTLS with cert rotation, AWS SigV4, HMAC-per-request | MPB supports Basic / Token / Custom only |
| 5 | Programmatic actions | "Restart service," "trigger backup," "rotate key" | MPB has no action support |
| 6 | Dynamic time / computed parameters | API requires `from=now-5m&to=now`, signed nonces, request-time HMAC | MPB has no time-variable substitution |
| 7 | Cursor / token-in-body pagination | AWS-style `nextToken`, GraphQL cursors | MPB supports offset/page only |
| 8 | Link-header pagination (RFC 5988) | GitHub, GitLab | MPB doesn't parse `Link:` headers |
| 9 | Custom response transforms | Regex extraction, arithmetic, conditional logic, schema reshape | MPB supports BASE64 / NONE only |
| 10 | Nested-array iteration in expressions | `data.*.metrics.*.value` | MPB grammar is dot-path + single `data.*` only (Pass 25 empirical) |
| 11 | Per-instance long-lived state | Schema cache that survives across cycles, complex token-refresh state machine | MPB has no per-instance cache |

## "Borderline" cases — stay Tier 1 if possible

These look Tier 2-shaped but have known Tier 1 workarounds. Prefer
the workaround.

| Apparent need | Tier 1 workaround |
|---|---|
| "I want one alert that combines two metrics" | Use a super metric, then a symptom on the SM |
| "The vendor's response has a property I need as a metric" | MPB has BASE64 transform and `data.field` pathing for type coercion |
| "Auth needs a header beyond Basic" | MPB supports `Custom` auth scheme with arbitrary header values |
| "I want to filter the resource list before binding" | Use a `where` clause on the request (MPB chaining v2 supports this) |
| "Two requests need to share an ID" | MPB chaining supports parameter passing — model as a chained request |

If any of these are sufficient: stay Tier 1.

## Decision flow (in `mp-designer`)

```
1. Build the API map (api-cartographer)
2. For each trigger row above:
    Does this API or this object model require it?
3. If zero triggers fire AND no borderline workaround is needed:
    -> Tier 1. Author with mp-author.
4. If ≥1 trigger fires:
    -> Propose Tier 2. Write Promotion Reasoning section listing
       which triggers and which API observations justify them.
5. Present tier + reasoning to user. User confirms.
6. Orchestrator routes:
    - Tier 1 -> mp-author -> mp-builder
    - Tier 2 -> sdk-author -> sdk-builder
```

## Promotion: Tier 1 → Tier 2

If a Tier 1 MP is in production and hits a trigger later (e.g.
Cloudflare hitting the dynamic-timestamp trigger), the promotion path
is:

1. Re-run `mp-designer` against the existing API map, declaring the
   new trigger.
2. The new design artifact references the prior Tier 1 design as
   "promoted from."
3. `sdk-author` generates the Tier 2 project; the BuilderFile is used
   as input scaffolding (object kinds, metrics, properties → Java
   POJOs + describe.xml).
4. Old Tier 1 pak is uninstalled; new Tier 2 pak takes its
   `adapter_kind`. Same adapter_kind preserves resource IDs and
   policy bindings.

Mechanical translator from BuilderFile to Tier 2 scaffolding is on the
Phase 3 backlog (see `designs/tier2-mp-architecture-plan.md`).

## Anti-patterns — when NOT to use Tier 2

- "It would be cleaner in Java." — Java is more flexible, but cleaner
  is not a trigger. Cost of Tier 2: a JDK on the build machine, more
  review surface, more failure modes. Don't pay that for taste.
- "I want to use a vendor SDK." — Almost never necessary. If the
  vendor SDK only wraps an HTTP API, model the HTTP API in MPB.
- "I want to combine data from two MPs." — That's a super metric or a
  custom group, not a new MP.
- "I want to write actions." — Actions are a real Tier 2 trigger
  (row 5), but most "I want an action" requests are really "I want a
  symptom + recommendation," which is Tier 1 alerting content, not an
  MP at all.
