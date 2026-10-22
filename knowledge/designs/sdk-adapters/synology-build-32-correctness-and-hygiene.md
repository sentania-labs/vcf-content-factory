# Synology build 32: correctness, hygiene and docs findings that need no design call

- **Type:** managementpack (Tier 2 SDK adapter change), build 32 (main is v1.0.0.31, untagged)
- **Slug:** synology-build-32-correctness-and-hygiene
- **Adapter repo:** `content/sdk-adapters/synology/` (branch from `origin/main`)
- **Date:** 2026-10-16
- **Status:** merged to synology main (9c58c4a, PR #40, Codex +1, 2026-10-16), not tagged; 13 issues closed, #33 and #26 closed as fixed in build 31; devel_9_1 proof done (knowledge/context/investigations/2026-10-16-synology-32-devel-9-1-proof.md): no regression, memory x1024 and network total row match DSM exactly, volume free and SSD remain_life now populated; load averages still DSM-scaled by 100 (follow-up issue), 9.1 menu path reading unresolved, NFS-off and datastore paging not exercised

## Initial prompt (Scott, verbatim, 2026-10-16)

> the fork paks are enhancedments we will tackle.  let's focus on the
> compliance, unif, synology, and template.  Triage them, order them, and
> let's fix them all in this session.

## Scope (fork issues, in order)

1. **#33** verify closed by build 31 (`SynologyFailures.isUnreachable` in
   `mapCollectException`); no code change expected, close with evidence.
2. **#26** verify closed by build 31 (one snapshot per cycle keyed off the
   collection cycle, 60 s only as a safety net); close with evidence.
3. **#17** `callRaw` catches `RuntimeException` as well as `IOException`
   and rethrows a redacted exception built from the endpoint label and the
   redacted message, without chaining the cause; unit test feeds a
   secret-bearing URI through a thrown runtime exception.
4. **#27** drop the Suite API username from the INFO line (DEBUG, masked,
   if kept); pass every Suite API exception message through `redact()`
   before logging (adapter :185-191, :1049-1050, stitcher :116-117).
5. **#23** per-instance DSM session name
   (`VCFContentFactory-<adapterInstanceId or short random>`), distinct one
   for the Test Connection client; pass `_sid` on logout.
6. **#18** memory fields multiplied by 1024 before publish (declared unit
   stays bytes); network totals use only the `device == "total"` row, or
   skip bond members when no total row exists.
7. **#24** `cpu_load_1m/5m/15m` lose the `%` unit, display names "Load
   Average (1 min)" and so on. If DSM scales by 100, normalise and say so.
8. **#25** one canonical cache-to-volume join (`mountSpaceId == vol.id`,
   fall back to `path` only when `mountSpaceId` is absent) in one helper
   used by metrics, relationships and the datastore cross-link.
9. **#34** capacity, remaining life and LUN latency mapping: compare each
   key against the DSM response fields in the recorded fixtures under
   tests/ (or the API map in the factory's knowledge/context/api-maps/)
   and fix the mapping; where the fixture lacks the field, publish only
   when present and list it for devel confirmation.
10. **#20** skip the NFS privilege probe loop when `enable_nfs` is false;
    skip hidden and system shares; refresh the rule map at most every 15
    minutes; rate-limit the per-share WARN to once per share per hour.
11. **#28** paginate the Suite API datastore list (page until
    `pageInfo.totalCount`), smaller page size, cache the path index for
    30 minutes or until a miss.
12. **#22** docs: dedicated account without 2-step verification, minimum
    privileges, DSM firewall scoped to the collector; map the OTP-required
    login code to a clear non-retryable message through the existing login
    refusal path.
13. **#31** query `SYNO.API.Info` at login, cache `maxVersion` and `path`
    per API, use `min(maxSupported, desired)`, one clear message when a
    required API is missing; document supported DSM versions.
14. **#29** docs: TLS default (false since build 31), the optional
    `vrops_*` fields and the explicit-path network requirement, the
    account scope sentence (build 31 made the optional endpoints
    non-fatal, say what is now true), key count, drop "drive family",
    GiB label fix in code.
15. **#37** README Configure step 1: Administration > Integrations >
    Accounts.

Waiting on Scott's decision, not in this build: #11 (identity, own
build), #16 (query-string secrets, framework first), #35 (symptoms and
alerts content), #32 (CI, from the template).

## What must not regress

- Build 31 behaviour: TLS default, SnapshotCache back-off and refusal
  codes, SnapshotReads required set, NfsProbes, Teardown, DOWN mapping.
- Metric key names unchanged (units and display names may change; note
  each in the CHANGELOG).

## Proof

- Unit tests per item where SDK-independent (redaction, session name,
  memory scaling, network total row, cache join, NFS skip, pagination,
  API Info version pick).
- `validate-sdk`, `build-sdk` dev build 0.0.0.32, pak-compare against the
  build 31 pak (sha256 8ea76f212cbdc3578dd4525996c1d871aa77b902aea7f4eaebd4af6504e3ce1e)
  with zero BLOCKING.
- Reviewer gate, peer review, PR, Codex round, merge, no tag. devel_9_1
  install under the standing approval: memory values plausible against
  DSM's own UI, network total matches, capacity and remaining life
  populated, one DSM session per instance visible in DSM's connection list.
