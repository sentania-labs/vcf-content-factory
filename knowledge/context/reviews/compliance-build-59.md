# SDK Adapter Review: compliance build 59 (re-review of build 58)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 59, commit `462623f`, vs build 58 `5e4a476` (delta) and build 56 `32de5aa` (pak-compare reference)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.59.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-58.md` (APPROVE, 1 WARNING / 4 NIT)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **CHANGES REQUESTED**
- **Findings:** 1 BLOCKING / 1 WARNING / 1 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass.** 7 Java suites + generator unittest 12/12. |
| `generate_compliance_alerts.py --check` | **Up to date** (144 / 144 / 144, unchanged). |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file, including the jar's classes, matches `dist/...59.pak`; 1 view, 0 dashboards bundled; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 8 INFO**, identical to build 58 (the intended ComplianceWorld attribute retirement; Fleet Overview dashboard absent; manifest description; five new profile files). |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Endpoint check against `reference/docs/operations-api-9.1.json`

- `GET /api/resources/stats/latest` (`getLatestStatsOfResources`) takes `resourceId` (array of uuid, 1 to 1000) and `statKey` (array of string) as repeated query params. The request matches: repeated `resourceId=` / `statKey=`, URL-encoded (`|` becomes `%7C`).
- `maxSamples` defaults to 1, so taking the last element of `data` takes the only sample.
- `currentOnly` is left unset, so an old stale 0 is still returned. That is what cleanup needs.
- Response schema `stats-of-resources`: `values[]` holds `stats-of-resource`, each with `resourceId` and `stat-list.stat[]`; each `stats` entry has `statKey.key` and `data[]` (number). The parser reads exactly these names (`ComplianceStitcher.latestCompliant`). `SimpleJson.asString` on a number yields its `toString`, so `numeric()` parses `0` / `0.0` correctly and a non-numeric value is skipped, never read as 0.
- Failure handling: any non-2xx raises `IOException` in `SuiteApiStitchClient.urlConnRequest` (401 retried once). The exception is caught and the whole batch returns null, and the batch is skipped with a WARN and counted. An empty or unparseable body also returns null. A 200 with no `values` is read as "no stats" (no cleanup), which is safe.

## Build-58 finding closure

| # | Closed? | Evidence |
|---|---|---|
| W1 union cleanup cardinality | **Closed in code** (live proof still owed, see W1 below) | Union, first-sight and daily sweep are removed. `candidateControlIds` is only queried. `staleZeroControls` iterates over the values actually returned, so a key the object never had cannot appear, and only values `== 0.0` among candidates qualify. Candidates exclude every control the current benchmark evaluates, so a live result is never overwritten. Only `-1` is ever written, never `1`, so cleanup cannot pass a control. `latest == null` cleans nothing. VERSION_UNREADABLE objects are never queued. Tests cover no key creation, -1/1 untouched, failed read, in-benchmark 0 untouched. |
| N1 docs vs code | **Closed** | overview.md and the README key list state that `unreadable_count` is not pushed for version-unreadable objects. |
| N2 sweep timing | **Moot, closed** | No cycle-count or time-based logic remains. |
| N3 memory coupling | **Closed** | `LastBenchmarkMemory` holds only the B2 fallback. It is recorded for every decided object (including unmatched ones), trimmed to inventory, cleared only on configure or restart, and holds no cleanup state. |
| N4 CI on push/PR | **Functionally closed, but introduces B1** | `.github/workflows/tests.yml` added; `contents: read`; both actions pinned to full commit SHAs (same SHAs as the tag workflow); per-ref concurrency. |

## Regression review of the new read path

- **Batching.** Pending objects are grouped by kind, 20 per batch, and each batch's candidate keys are chunked at 30 per request. One failed chunk voids the whole batch (safe: nothing is cleaned). Batches are independent, so one failure does not stop later batches.
- **Cardinal rule.** No new path writes anything but `-1` onto keys that already hold 0 outside the applied benchmark. Scores, counters and non_compliant are untouched by cleanup.
- **Crash-the-cycle.** `latestCompliant` catches all exceptions; `bundledForCleanup` returns null on loader failure; pushes are swallowed by the framework. Cleanup runs after all collectors and before the rollup push, so a cleanup problem cannot stop the rollup.
- **Semantics.** A NO_BENCHMARK object (profile null) uses every bundled control as a candidate. That is correct: an unmapped version has no applicable control, so any leftover 0 is stale.

## BLOCKING

### B1. New PR-triggered workflow runs untrusted code on the self-hosted release runner of a public repo

- **Where:** `.github/workflows/tests.yml` (`on: pull_request`, `runs-on: [self-hosted, Linux, X64, generic]`).
- **Authority:** the user's `github-ci` skill § *Cost: when you pay*, placement rule 4 ("Neither [needs the lab nor Docker], and the repo is public -> GitHub-hosted"), and its § *Using the lab pool* warning that array-form `self-hosted` labels route to legacy runners, not the ephemeral `lab` pool. Also GitHub's Actions security-hardening guidance against self-hosted runners on public repositories. Repo visibility checked: `gh repo view` reports **PUBLIC**.
- **What:** the job compiles and runs code from the PR head (`javac` / `java` / `python3` on repo files). On a public repo, a fork pull request runs that code on the same self-hosted pool that runs `build-pak-on-tag.yml`, whose release job handles `SDK_RUNTIME_SSH_KEY` and `contents: write`. GitHub's default approval gate covers only first-time contributors. A non-ephemeral legacy runner lets a PR leave something behind that a later release job picks up. This job needs neither the lab nor Docker, so nothing justifies the self-hosted pool.
- **Fix (one line):** `runs-on: ubuntu-latest`. Keep the SHA pins and `contents: read`; `setup-java` and `python3` work unchanged on hosted runners.

## WARNING

### W1. The live cleanup read is unproven, and the acceptance plan cannot tell "works" from "silently does nothing"

- **Where:** `ComplianceStitcher.latestCompliant`; CHANGELOG build-59 acceptance plan ("expect NO new Compliant = -1 keys ... completion line reports 0 stale per-control key(s)").
- **Authority:** skill § *Unreadable is NOT compliant* (a cleanup that silently never runs leaves stale 0 alerts open, the build-57/58 W1 harm); `knowledge/lessons/sm-statkey-api-prefix.md` (list what the API actually returns before concluding a key has no data); user rule "done means seen working".
- **What:** on devel, every candidate key is absent (v3 keys hold no stale 0 outside 9.1), so a correct read returns empty maps. A read that fails to match keys also returns empty maps. Both produce "0 stale", no WARN. Wrong key encoding, a server-side `metrics` filtering difference on Suite-API-pushed stats, or a response-shape drift on 9.0 vs 9.1 would all look like success. The code is correct against the spec, but the fix's whole value (cancelling a lingering alert) is never exercised by the plan.
- **Fix:**
  - **Adapter:** log per cycle how many values the read returned (for example "cleanup read: N objects, K Compliant values returned, S stale"), so a read returning nothing on objects known to have candidate keys is visible.
  - **Acceptance, positive proof:** first, a read-only `ops-recon` GET of `/api/resources/stats/latest?resourceId=<devel host>&statKey=VCF-CF Compliance|<a live 9.1 control>|Compliant` to confirm the shape on devel 9.0.2. Then a staged flip on one devel instance: fixed `VMware_SCG_8.0` for one cycle (creates 8.0-only keys, some at 0), then back to 9.1 or Auto. Confirm those zeros flip to -1 and their alerts cancel. Run the same on prod 9.1 when it gets the pak.

## NIT

- **N1.** Request volume and doc accuracy. Hosts need up to 3 GETs per 20 objects (86 candidate keys / 30 per chunk); VMs need 1 per 20. At 5,000 VMs that is 250 serial loopback GETs every cycle, forever, even when nothing is stale. `docs/overview.md` says "one bulk stats/latest request per 20 objects", which undercounts hosts. The spec also offers `POST /api/resources/stats/latest/query`, which carries ids and keys in a body with no URL-length limit, so batches can grow to hundreds of objects per call. Use it, or size batches by URL length, and correct the doc sentence.

## If shipped as-is

Compliance data, scores and alerts are correct, and no keys are created. But any fork pull request on the public adapter repo can run code on the self-hosted runner that builds and publishes releases. And the per-control alert cleanup has not been shown to actually fire.
