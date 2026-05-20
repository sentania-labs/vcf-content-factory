---
id: DEC-001
status: decided
decided_date: 2026-05-19
decided_by: scott
rules_derived: [RULE-011]
supersedes: null
---

# DEC-001: Synology DSM → Tier 2 (Java SDK)

## Decision

Synology DSM management packs are Tier 2 (Java SDK adapter), not Tier 1 (MPB).

## Rule basis

Falls under RULE-011: Client-side multi-endpoint joins require Tier 2.

## Evidence

The Synology DSM API has no common identifier linking storage volumes, system info, and Docker containers. The data model requires client-side joins across unrelated endpoints:

- `/webapi/entry.cgi?api=SYNO.Core.System.Status` — system info
- `/webapi/entry.cgi?api=SYNO.Storage.CGI.Storage` — storage volumes
- `/webapi/entry.cgi?api=SYNO.Docker.Container` — Docker containers

MPB's chaining is single-axis (parent → child via ID) and cannot model arbitrary joins. The stitching requires programmatic state management and custom join logic, which only the Java SDK provides.

Confirmed in:
- `context/lessons_synology_sdk_2026_05_19.md` — First Tier 2 MP end-to-end implementation
- `context/tier_decision_framework.md` — Trigger row 2: "Complex data-model stitching"

## Trade-offs

**Gained:**
- Full data model with correctly stitched relationships
- Ability to handle future DSM API changes requiring custom logic

**Gave up:**
- Faster authoring (MPB YAML is faster than Java SDK)
- No JDK requirement on build machine

The trade-off is justified — without Tier 2, the MP cannot model Synology's actual topology.

## Relitigation

This decision is binding. To override:
1. Create `decisions/overrides/DEC-001-override.md`
2. Document which evidence changed (e.g., Synology added a common key, MPB gained arbitrary join support)
3. Reference new API documentation or framework capability
4. The override must be approved by the framework maintainer.

Casual users cannot relitigate. The override directory is the expert gate.
