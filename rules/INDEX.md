# Rules Index

Read every rule at session start. Rules are absolute — obey without question.

| ID | Rule | File |
|---|---|---|
| RULE-001 | Use only repo content as source of truth | [no-external-invention.md](no-external-invention.md) |
| RULE-002 | Never fabricate metric or attribute names | [no-fabricated-metrics.md](no-fabricated-metrics.md) |
| RULE-003 | Never write secrets to disk | [no-secrets-on-disk.md](no-secrets-on-disk.md) |
| RULE-004 | Always validate before installing | [validate-before-install.md](validate-before-install.md) |
| RULE-005 | All authored content uses `[VCF Content Factory]` prefix | [content-prefix.md](content-prefix.md) |
| RULE-006 | UUIDs are part of the contract | [uuid-stability.md](uuid-stability.md) |
| RULE-007 | Grep both OpenAPI specs when investigating API support | [check-both-api-specs.md](check-both-api-specs.md) |
| RULE-008 | MP adapter_kind must match MPB derivation | [mp-adapter-kind-derivation.md](mp-adapter-kind-derivation.md) |
| RULE-009 | Auto-memory is disabled by design | [no-auto-memory.md](no-auto-memory.md) |
| RULE-010 | Non-HTTP transport requires Tier 2 | [non-http-requires-tier2.md](non-http-requires-tier2.md) |
| RULE-011 | Client-side multi-endpoint joins require Tier 2 | [multi-endpoint-joins-require-tier2.md](multi-endpoint-joins-require-tier2.md) |
| RULE-012 | Stateful collection requires Tier 2 | [stateful-collection-requires-tier2.md](stateful-collection-requires-tier2.md) |
| RULE-013 | Advanced auth mechanisms require Tier 2 | [advanced-auth-requires-tier2.md](advanced-auth-requires-tier2.md) |
| RULE-014 | Programmatic actions require Tier 2 | [actions-require-tier2.md](actions-require-tier2.md) |
| RULE-015 | Dynamic time parameters require Tier 2 | [dynamic-time-requires-tier2.md](dynamic-time-requires-tier2.md) |
| RULE-016 | Cursor/token-in-body pagination requires Tier 2 | [cursor-pagination-requires-tier2.md](cursor-pagination-requires-tier2.md) |
| RULE-017 | Link-header pagination requires Tier 2 | [link-header-pagination-requires-tier2.md](link-header-pagination-requires-tier2.md) |
| RULE-018 | Custom response transforms require Tier 2 | [custom-transforms-require-tier2.md](custom-transforms-require-tier2.md) |
| RULE-019 | Nested-array iteration in expressions requires Tier 2 | [nested-array-iteration-requires-tier2.md](nested-array-iteration-requires-tier2.md) |
| RULE-020 | Per-instance long-lived state requires Tier 2 | [per-instance-state-requires-tier2.md](per-instance-state-requires-tier2.md) |
| RULE-021 | Exhaust built-in metrics and transformations before creating supermetrics | [exhaust-builtins-first.md](exhaust-builtins-first.md) |
| RULE-022 | Metric labels cannot contain reserved characters | [metric-labels-no-reserved-chars.md](metric-labels-no-reserved-chars.md) |
| RULE-023 | Match MPB wire formats exactly | [match-mpb-wire-formats.md](match-mpb-wire-formats.md) |
| RULE-024 | When wire format is unknown, emit nothing | [emit-nothing-when-format-unknown.md](emit-nothing-when-format-unknown.md) |
| RULE-025 | Verify join key uniqueness across all collection sources | [verify-join-key-uniqueness.md](verify-join-key-uniqueness.md) |
| RULE-026 | Use pak-compare before every install attempt | [pak-compare-before-install.md](pak-compare-before-install.md) |
| RULE-027 | APIs with parent-child encoded in URL paths require Tier 2 | [url-hierarchy-requires-tier2.md](url-hierarchy-requires-tier2.md) |
| RULE-028 | Use human-readable resource names, not internal API IDs | [human-readable-resource-names.md](human-readable-resource-names.md) |
