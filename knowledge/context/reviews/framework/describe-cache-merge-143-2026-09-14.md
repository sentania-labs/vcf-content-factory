# Framework review: describe cache refresh merges instead of replacing (issue #143)

- Branch: `fix/143-describe-cache-merge`, commit `5d0ffe5`, diff vs `main`
- Area: `src/vcfops_packaging/describe.py`, `src/vcfops_packaging/cli.py`
- Verdict: **APPROVE**
- Findings: 0 BLOCKING / 5 WARNING / 3 NIT

## Checks re-run (worktree, independently)

- validate chain (7 packages): PASS
- tests: 1521 passed, 7 skipped, 129 deselected (matches tooling's claim)
- render regression: n/a (no renderer touched)
- pak-compare: n/a (no builder/template touched); dist zips not stale, no template_version bump needed
- Probe A: real `VMWARE/HostSystem.json` refreshed against a fake instance reporting the #142 shape. 817 metrics and 202 properties retained both times; `merged_from` (2 entries) and `merge_note` survive; `source` flips to the fake instance. Identical second refresh emits the identical WARN pair (1431 and 2358 chars).
- Probe B: corrupt cache file. `main` overwrote it; this branch raises `DescribeCacheError ... is corrupt`.

## Claims verified

Merge-not-replace, `prune=False` default as the only removal path, `merged_from` / `merge_note` carried through, issue #75 failed-properties path preserved (and prune is correctly a no-op on that section), one summary line per refresh, `--prune` reaches `refresh_all`. All confirmed from code and tests.

The flipped assertion in `test_audit_views_xml_and_describe_preservation.py` does not weaken #75. That test was the success-path control ("200 replaces"); the #75 guarantee (failure keeps the cached section) is exercised by the unchanged failure tests and by the new `test_properties_fetch_failure_still_merges_metrics`.

Type/shape change on a key: `_merge_section` works at key granularity and the live entry wins wholesale, so a key whose entry changed shape is taken from the live instance intact. A retained key keeps its old shape (including legacy name-only property entries, none present in the current corpus).

## WARNING

- W1 `[describe.py:451-465, audit.py:293, cli.py:413]` The retained-key WARN is structural, not by exception, for any union-grounded file. Probe A: a refresh of `HostSystem.json` against the very instance it was last merged from still prints 38 retained metrics and 55 retained properties, ~3.8 KB on stderr, every time. `build` / `build-discrete` / `analyze` auto-refresh by default when creds are set, so every build that references VMWARE/HostSystem or vSphere World will print this. The list is only useful the first time. Fix: compare against the previous refresh's retained set (persist it, or the `source` host) and print the full list only when it changes; otherwise one line with the count.

- W2 `[describe.py:398-440]` `source` and `fetched_at` now describe the last instance that touched a union file, while `merged_from` is never updated by the tool. After Probe A the file says `source: ro818` at the top and `merged_from[0].role: primary = 9.x lab` below it, and nothing records that the 38 + 55 retained keys came from the primary. The docstring documents this, so it is loud, not silent, but provenance of a retained key is now unrecoverable from the file. Fix: on merge, append (or update in place by host) a `merged_from` entry with `source`, `fetched_at`, and `retained` count; leave `source` / `fetched_at` as-is.

- W3 `[knowledge/context/adapter_describe_cache/VMWARE/HostSystem.json, vSphere World.json: merge_note]` The hand-written `merge_note` still says "Refreshing this file against a single instance will drop the other platform's keys" and that the primary supplies display names on collision. Both statements are now false: refresh retains, and the live instance wins on collision (a refresh against 8.18 rebrands collided names back to "VMware Aria Operations"). `MetricInfo.name` is not consumed by `audit.py` or any builder (only `default_monitored` is), so no emitted artifact changes, but the note is a RULE-001 source-of-truth claim the change invalidates. Fix: update both notes in the same PR.

- W4 `[describe.py:_merge_section; HostSystem.json merge_note]` Instance-local `Super Metric|sm_<uuid>` keys are imported from the live statkeys response unfiltered (pre-existing), and merge now makes them permanent: 10 in HostSystem.json, 37 in ClusterComputeResource.json, retained across every future refresh of every instance. Under replace they at least aged out. The `merge_note` explicitly says these keys were excluded from the hand-merge. A bundle referencing another lab's SM key would pass the existence gate on the strength of a cache entry no instance still reports. Fix: skip `Super Metric|` keys in the live parse (or at merge), and treat the ones already cached as pruneable.

- W5 `[describe.py:404-410]` Corrupt cache file: `main` recovered by overwriting; this branch raises `DescribeCacheError ... is corrupt` from `refresh()`. Inside `audit.py:293` / `cli.py:413` that is caught and demoted to a WARN, then `resolve_metric` raises the same error and the build fails. Loud, so not blocking, but the message names no recovery path. Fix: either overwrite when `prune=True`, or say "delete the file and re-run refresh-describe" in the message.

## NIT

- N1 `[cli.py:1544-1555]` `--no-live-describe` help for build-discrete still says the live path "REWRITES the tracked ... cache files". It merges now. Same wording check on the other two `--no-live-describe` parsers.
- N2 `[describe.py:376-383, 404-410]` The #75 failure path reads the existing file once (swallowing errors) and the merge block reads it again (raising). Harmless, but the failure path could reuse `existing_doc`.
- N3 `[tests/test_describe_cache_merge.py]` No test covers the build-time callers (`audit.py` auto-refresh, `cli.py analyze`) taking merge semantics, and none covers the corrupt-file behavior change. The unit surface is well covered (11 tests).

## Named anchors

- `00d3382` (pak-local default leaking global): not applicable; the change touches no renderer or import path.
- `6c59f6b` (key derivation collision): not applicable; keys are the API's own statkey ids, merge is by exact key.

## If shipped as-is

A refresh can no longer silently delete another platform's keys (the #142 failure is closed). Operators will see a ~4 KB WARN on every live build that touches a union-grounded cache file, and the file's own provenance notes will describe behavior the tool no longer has.

## Round 2: follow-up commit `e2ce460`

- Verdict: **APPROVE**
- Findings: 0 BLOCKING / 0 WARNING / 2 NIT
- Suite re-run in the worktree: 1530 passed, 0 failed, 7 skipped, 129 deselected (matches claim). Validate chain unchanged from round 1 (no content or loader touched).

### Focus points, each verified

- **merged_from host match.** `_host_of()` keeps the port (`host:port` is the first path segment after the scheme), so two instances on the same host but different ports get separate `refresh` entries. Only entries with `role == "refresh"` are matched; the hand-written `primary` / `additive` entries from the same host are never touched, and the tool never creates two `refresh` entries for one host (first match is replaced, then appended). Test `test_refresh_entry_updated_in_place_per_host` covers it.
- **retained_absent shrink-to-empty.** When the retained set becomes empty, `stats.retained` is falsy, nothing prints, and the persisted list becomes `[]`; the next refresh from that host that retains anything compares `[] != nonempty` and prints the full list again. Correct. Shrink to a smaller non-empty set prints the full new list (changed). On the #75 failed-properties path the previous host's `retained_absent.properties` is carried forward, so the next successful refresh compares against the real last set. Correct.
- **Super Metric| drop as a gate risk.** No `resolve_metric` caller can be handed such a key: `deps.py` filters through `_is_sm_ref` at every extraction site (195, 231, 300, 314, 368, 378, 388), `extractor.py:2276` filters the SM orphan check the same way, and `dep_walker.py:294` skips `Super Metric|` attrs before building `MetricRef`s. Templates (`sdk_builder.py`, `builder.py:188`, `discrete_builder.py:121`) resolve SM tokens against the bundle's own SM YAMLs, never the describe cache. The 10 / 37 / etc. cached SM keys in the committed VMWARE files will be dropped, with a WARN, on the first live refresh of each; that is a tracked-file diff a build with creds will now produce once, and it is announced.
- **Corrupt-file overwrite reachability.** `prune=True` exists on one code path only: `cli.py:354` `refresh-describe --prune`. `audit.py:293` and `cli.py:413` call `refresh(ak, rk)` with the default. Not reachable by accident from a build.
- **merge_note edits text-only.** Structural comparison of both JSON files against `5d0ffe5`: the only differing top-level key is `merge_note`; `metrics` and `properties` are equal.

### NIT

- N4 `[describe.py:536-551]` When a host's retained set shrinks to empty (keys reappeared), nothing is printed. A one-line "N previously-retained keys are now reported by <host>" would be by-exception and would close the loop for whoever read the earlier WARN.
- N5 `[describe.py:337-338]` A readable but non-dict cache file (the list-shaped `MSSQL/` and `ORACLE/` `statkeys_*.json` scratch files) is treated as empty and would be overwritten without a WARN. In practice unreachable (the statkeys fetch for those pseudo-kinds fails first and `refresh_all` has no per-pair try/except, both pre-existing), but the corrupt-file branch got a recovery message and this sibling did not.

### If shipped as-is

Round 1 warnings closed as claimed. Operators see the full retained list once per host and one count line thereafter; the cache file records which instance did not report which keys; instance-local SM keys leave the cache on the next refresh with a WARN.
