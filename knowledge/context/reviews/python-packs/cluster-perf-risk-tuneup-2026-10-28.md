# cluster-perf-risk tune-up review, 2026-10-28

- **Fork:** `content/sdk-adapters/cluster-perf-risk/` (sentania-labs/cluster-perf-risk)
- **Branch:** `tuneup/upstream-2026-10` at `ec1b312`, 7 commits on `origin/main` `741c520` (equal to `upstream/main`, tag `v2.0.3`, gillaspy/cluster-perf-risk)
- **Scope reviewed:** fork issues #1, #2 (no code, question in the PR body), #3, #5, #6, #7, #8, #9, planned as one upstream PR, version 2.1.0 set by the tag
- **Checklist:** `knowledge/context/python_integration_sdk.md` section 10
- **PR body reviewed:** the author's `scratchpad/PR_BODY.md`
- **Verdict:** CHANGES REQUESTED (0 BLOCKING, 3 WARNING, 7 NIT)

There are no blocking defects. Every failure path now reaches the platform, the
token stays out of the log, every request including the SDK's own token calls
has a timeout, and the bulk snapshot gives the same values and the same object
identity as 2.0.3. I proved that on devel with my own old/new/new runs, with
pages forced down to 2 items, and with a nonexistent ID mixed into the bulk
reads. The three warnings are small. Fix them, along with the nits, before the
upstream PR opens. Warning 1 is commit-message hygiene only.

## Claims check (what was rerun)

| Claim | Rerun | Result |
|---|---|---|
| Unit tests: 39 pass in the adapter image; each commit passes alone | Built the image from `git archive ec1b312` and ran the CI `TEST_COMMAND` exactly (read-only mount, `--entrypoint bash`). Then ran the suite against each of the 7 commits' trees | `39 passed, 1 skipped` (the skip is the pre-existing `host_statkeys.json` fixture test). Per commit: 9, 11, 16, 20, 25, 33, 39 passed, each with 1 skip. Reproduced |
| `mp-build` builds and validates, manifest stamped 2.1.0 | Scratch copy, manifest stamped by the CI's own logic (2.0.1 committed, 2.1.0 stamped). Ran a throwaway `registry:2` on `127.0.0.1:5098`, logged in with a dummy user via `--password-stdin`, then `mp-build --no-ttl -r/--push-registry 127.0.0.1:5098/cluster-perf-risk`. The registry was stopped afterwards and the login removed | `Build Succeeded`, `ClusterPerfRisk_2.1.0.pak`: manifest `version` 2.1.0, `adapter_kinds` `["ClusterPerfRisk"]`. The image digest in `adapter.zip` (`sha256:f789d25b...cf73`) resolves in the registry (HTTP 200). One first attempt failed only because another agent's `mp-test` held port 8080 |
| Identical values old vs new (474 attributes, 12 objects) | My own `mp-test collect` on devel, run new, then 2.0.3, then new, back to back. Credentials came from the factory profile loader into a 0600 `/dev/shm` file, symlinked as `connections.json` into scratch copies and shredded afterwards. The comparison covered every metric, every property **and every object key including `identifiers` and `isPartOfUniqueness`** | 486 entries each (474 attributes plus 12 identities), **0 differences** for new/new, old/new1 and old/new2. The author compared values only. My comparison adds identity: the host `resourceKey` now comes from `bulk/relationships`, not the HostSystem query, and it projects onto the same objects |
| Paging over the 1,000 limit (not exercised by a 3-cluster lab) | Scratch copy with `PAGE_SIZE = 2` (drives query pages, relationship pages and the stats and properties chunk size), `adapter.log` captured | 232 `bulk/relationships` pages, 55 stats calls, 5 property calls, 2 query pages. Result identical to a normal run (0 differences). `page`/`pageSize`/`totalCount` on `bulk/relationships` behave as the code assumes, at least on devel |
| A 404 means "none of these resources exist" | Scratch copy that adds a nonexistent UUID to the VM stats list and to the host stats and properties lists | All calls 200. Values identical to a normal run. A mixed list returns partial results, so the 404 branch is reached only when a whole chunk is gone (see WARNING 3) |
| 779 (803) calls on 2.0.3 vs 9 on the branch | Counted `suite_api_client` request lines in the author's `n1-a`, `o1-b`, `devel_9_1-n1-a` and `devel_9_1-o1-b` adapter logs | 9 / 779 / 9 / 803. Matches the PR body |
| 8.18 and 9.1 comparisons | Not rerun (devel only, as briefed). I read the author's `devel_8_18-*` and `devel_9_1-*` artifacts | Consistent with the claim. Not independently reproduced |
| Failure paths: refused login, unreachable host, bad threshold | Not rerun. Read the author's `fail-devel_nouser`, `fail-blackhole`, `old-fail-nouser` and `connect-devel_badparam` outputs | Branch: "Collection Failed: Could not get a Suite API token ..."; a `ConnectTimeout (connect timeout=15)` on the acquire; "Monster VM Threshold (%) must be a number from 1 to 100, not '150'". 2.0.3: `errorMessage: null`, `objects: {}`. Matches |
| DEBUG redaction | Not rerun on a live collector. Scanned the author's `debug-new` artifacts. Probed `log_filter` in the image with a synthetic token | Author's logs: `Acquired token <redacted>` and `"token":"<redacted>"`, and no Ops token pattern (`uuid::uuid`) anywhere in `runs/`. Probe: redaction runs before truncation, so a token past character 2000 is still removed. Two gaps are in NIT 1 and NIT 2 |
| Secret hygiene | Scanned the author's `runs/`, `PR_BODY.md`, the fork tree and all my outputs in-process against the devel, devel_8_18 and devel_9_1 passwords. Nothing was printed | 0 hits. Fork tree clean (`git status` shows only `__pycache__`). No `connections.json` left anywhere. `/dev/shm` clean |
| Em-dashes | Grepped added lines, commit messages and the PR body | None |
| Base branch | `merge-base` with `upstream/main` | `741c520` = `v2.0.3`, the registry's release branch `main` |

Workflow: the diff does not touch `.github/workflows/`, so actionlint and the Trivy gate do not apply.

## Hunt results (the brief's list)

- **Latest semantics of the bulk stats query.** Same sample as the per-stat GET: identical values on devel back to back, and the author saw the same on 8.18 and 9.1. Missing keys are absent from the dict, and `Snapshot.stat()` returns `None`, never 0. Resources with no stats read `None`. `Snapshot.stat()` raises for a key nobody asked it to fetch.
- **Paging past 1,000.** Proven on devel with forced 2-item pages (above). Not proven on an estate that is really large; that is a call-volume question, not a correctness one.
- **0/None flips.** None introduced. Numeric `linkspeed` from the properties query is cast correctly (tested both ways). One pre-existing 0.0 case is in NIT 6.
- **All vs some clusters failed.** Correct: `with_error` only when every cluster failed, one warning listing the failed ones otherwise. The pre-read bulk snapshot is all-or-nothing, though: a 5xx on any of the 7 reads loses the whole cycle (NIT 7).
- **403 on some objects vs all.** There is no per-object call left. A 403 on a bulk call is the account lacking the endpoint, and failing the cycle is right. The Suite API filters objects by RBAC rather than returning 403, and the ghost-ID probe shows unknown IDs are dropped silently.
- **Timeouts vs a 5-minute cycle.** (15, 120) per request. A hung node fails the first call within 135 s, and the cycle ends there. There is no cycle budget, and the "9 calls" wording undercounts on large estates (NIT 4).
- **Log filter.** It is installed on the root handlers, so it covers `aria.ops.*` and every other logger. Truncation runs after redaction, so it never hides the redaction. The token never goes in a URL (the SDK sends it as an `Authorization` header). Gaps are in NIT 1 and NIT 2.
- **Threshold check vs collect.** Inconsistent (WARNING 2).
- **#2 certificates.** No code, by design. The analysis in the PR body matches section 3 of the SDK doc (certificates only for `get_endpoints` URLs, and `get_endpoints` gets no `cluster_connection_info`). The residual risk is unchanged from 2.0.3: the token-acquire POST carries the platform password over `verify=False`. That is acceptable as an open question to the upstream author, not a finding against this branch.

## BLOCKING

None.

## WARNING

1. **Fork references in every commit body.** All 7 commits end with `Refs: sentania-labs/cluster-perf-risk#N`. `96b3255` also says in its body "like the other queries since sentania-labs/cluster-perf-risk#1". These land in upstream history pointing at another repository's issues. The PR body already links every issue in full. Fix: reword the 7 messages without trailers, and change the `96b3255` sentence to "since the previous commit" or similar. No code change. Re-verify with `git log --format=%B origin/main.. | grep -c sentania-labs` = 0.

2. **Collect still accepts an out-of-range Monster VM Threshold without a word** (`app/adapter.py:161-171` vs `:92-99`). Test Connection now rejects 150, but `collect()` still takes any float. With a threshold above 100, no VM can ever be a monster, so both Monster VM Ratio metrics and every host's Monster VM Count read 0 and band green. This hits accounts upgraded from 2.0.x, which are never re-validated, and accounts saved without Validate. The PR body names the gap but leaves it. Fix: one helper shared by `_parameter_problems` and `collect`. In collect, treat an out-of-range value like a non-numeric one: log a warning naming the value and fall back to the default. Add a unit test.

3. **An estate-wide empty read passes in silence** (`app/suite_api.py:209-211`, `:238-240`; `tests/test_collect_failures.py:63-68`). A 404 on a stats or properties chunk is a bare `continue`. My probe shows a mixed list returns 200, so a 404 means the whole chunk of up to 1,000 resources is gone. More generally, if the stats queries return 200 with no values for any resource (stats unreadable for this principal, collection stopped platform-wide), every object gets band `unknown`, the account stays green, and `adapter.log` has no line saying so. #3 makes this visible on the objects, but nothing tells the admin why. The test `test_vanished_resources_read_as_no_data_not_a_failure` makes the silence part of the contract. Fix: log a warning on a 404 chunk (call, chunk size). In `snapshot.read` (or `collect`), warn with counts when a kind with N > 0 resources came back with 0 stats. Extend the test to assert the warning. Whether the all-empty case should be `with_error` is the author's call; a warning is the minimum.

## NIT

1. **`log_filter.RedactingFilter.filter` can raise into the caller** (`app/log_filter.py:41`). It calls `record.getMessage()` outside logging's error handling, so a record whose args do not match its format (`logger.info("a %s %s", 1)`) raises `TypeError` at the call site instead of logging's usual "--- Logging error ---" to stderr. Probe confirmed. No such call exists today, but if one ever ran inside `collect()`'s `except` block, it would escape to `main()`'s `sys.exit(0)` and turn into the silent "No result from adapter" that #1 removes. Wrap the body in `try/except Exception: return True`.

2. **Tracebacks are not redacted** (`app/log_filter.py:39-55`). The filter rewrites `record.msg` only. `logger.exception(e)` text (`exc_info`) passes through untouched (probe: `RuntimeError("Authorization: vRealizeOpsToken <token>")` was logged in full). No current path puts the token in an exception, because requests exceptions carry the URL, not headers. Either redact `record.exc_text` after formatting, or say in the module docstring that exception text is not covered.

3. **Test token looks real** (`tests/test_log_filter.py:7`). `8f868cca-27cc-43d6-a838-c5467e73ec45::77cea9b2-...` has the shape of a live Ops token. It appears in none of the run artifacts, so it is probably generated. Use an obviously fake value (`00000000-0000-0000-0000-000000000000::...`) so no upstream reader has to wonder.

4. **Call count and time bound wording** (`app/snapshot.py:9-10`, PR body #5 and #6). "9 calls whatever the size of the estate, plus one per further 1000 resources of a kind" leaves out relationship pages, which are one per 1,000 relations (host to VM edges on a large estate). "The per-request timeouts already bound it" is true per call, and the bound is calls x 135 s. Say "9 calls on a 3-cluster lab; one more per 1,000 resources per kind and per 1,000 relationships".

5. **PR body test count.** "39 pass" should be "39 pass, 1 skipped (`host_statkeys.json` fixture not in the repo, as on 2.0.3)".

6. **Pre-existing, not this branch:** `app/traversal.py` host overcommit ratios (`host_total_vcpu / host_cores`) read 0.0, band green, when a host has VMs but none returned `config|hardware|num_Cpu` or memory. That is the "unknown as 0" class #3 fixed for the composite. `get_endpoints`' comment ("VCF Operations itself, which does not need certificate handling here") is contradicted by the PR's own #2 analysis. Open fork issues rather than widen this PR.

7. **Say what the bulk read trades** (PR body #6). 2.0.3 lost one value silently on a failed per-resource read. The branch fails the whole cycle when any of the 7 bulk reads fails, because `with_error` drops every object. That is the right trade, but the loop's "One cluster failing must never lose the others" no longer covers read failures. One line under #6 or "What I'd like you to check".

## Checklist (section 10)

| Item | State |
|---|---|
| Certificates | Unchanged from 2.0.3. `get_endpoints` empty. The Suite API stays `verify=False` (SDK default). This is open question #2 in the PR body, not a regression |
| Credentials | No new parameters or credential fields. No secret in `with_error` text (host only), logs, fixtures or artifacts. `connections.json`, `logs`, `build` gitignored |
| Error reporting | `collect` and `test` catch, `logger.exception`, `with_error`. Per-cluster isolation with all-failed = error. Empty token and non-2xx detected. `test` checks parameters and tables, and the README says what it cannot check. Unknown composite omitted (#3). Gaps: WARNING 3, NIT 1 |
| Timeouts | (15, 120) on every request through `_to_vrops_request`, including token acquire and release. A failed release is logged, not raised (unit-tested) |
| Token handling | `suite_api.session()` is equivalent to `with client:` plus a guarded release. Token presence checked after entry. Redaction filter installed right after `setup_logging()`/`rotate()`. Nothing raises the DEBUG level |
| Definition and identity | Not touched. No identifier, `advanced` or credential change. Version set by the tag (CI stamp proven in my `mp-build`) |
| Dependencies | No new imports beyond stdlib (`re`, `logging`, `contextlib`). `adapter_requirements.txt` unchanged (`~=1.1.0`). `FROM base-adapter:python-1.2.0` unchanged |
| Packaging | `manifest.txt` and resources unchanged. Pak builds |
| Scope and style | One commit per issue, upstream's module layout and comment style kept, no factory conventions. Commit trailers: WARNING 1 |

## If shipped as-is

Users get honest failures (refused login, 403/5xx, unreachable Ops) as collection errors with the cause, about 1% of the Suite API load and under a second of reads per cycle, no token in a DEBUG log, and a Test Connection that catches a bad threshold. Three things would surprise them. An account upgraded with a Monster VM Threshold above 100 quietly reports zero monster VMs, green. A platform-wide stats outage shows every cluster and host as `unknown` with nothing in `adapter.log` to say why. And the upstream history carries seven references to another repository's issues.

## Cleanup

My scratch only (`scratchpad/review-cpr/`): exported trees, `tools/` (connection writer, comparator, secret scanner, log-filter probe), `out/` run logs. The throwaway registry is stopped (`--rm`), the `127.0.0.1:5098` login removed, the review image removed, the `/dev/shm` credential file shredded after each use. Nothing was written to the fork, pushed, installed or tagged.
