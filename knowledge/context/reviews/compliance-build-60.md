# SDK Adapter Review: compliance build 60 (re-review of build 59)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Build reviewed:** 60, commit `1706d4b`, vs build 59 `462623f` (delta) and build 56 `32de5aa` (pak-compare reference)
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.60.pak`
- **Prior review:** `knowledge/context/reviews/compliance-build-59.md` (CHANGES REQUESTED, 1 BLOCKING / 1 WARNING / 1 NIT)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE**
- **Findings:** 0 BLOCKING / 0 WARNING / 0 NIT

## Claims check (independently re-run)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass.** 7 Java suites + generator unittest 12/12. |
| `generate_compliance_alerts.py --check` | **Up to date** (144 / 144 / 144). |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file, including the jar's classes, matches `dist/...60.pak`; 1 view, 0 dashboards bundled; adapter tree clean; `build_number` 60 with a CHANGELOG entry. |
| pak-compare vs 56 | **0 BLOCKING / 1 WARNING / 8 INFO**, identical to builds 58 and 59 (the intended ComplianceWorld attribute retirement). |
| Registry | No `defects.local.md`; no open defect in `knowledge/context/defects.md` names `compliance`. |

## Build-59 finding closure

| # | Closed? | Evidence |
|---|---|---|
| B1 PR workflow on self-hosted runner | **Closed** | `tests.yml` `runs-on: ubuntu-latest`, matching `github-ci` skill placement rule 4 for a public repo. Delta is the runner line plus comments. |
| W1 cleanup unprovable | **Closed** (live proof owed, correctly planned) | `latestCompliant` returns `LatestRead` (values, requests completed, numeric values returned, error). The adapter logs one "Stale-control cleanup read" line per cycle (objects queried, requests, values returned, zeros cleaned, objects skipped) plus a WARN per failed batch with its error. "Read returned nothing" is now distinguishable from "nothing stale". The CHANGELOG acceptance plan now includes the positive proof: an ops-recon GET of a live key's shape on devel 9.0.2, a fixed-8.0-for-one-cycle flip that must show values returned, zeros set to -1 and alerts cancelled, and the same on prod 9.1. |
| N1 request volume | **Closed** | GETs are packed by URL length (budget 6000) and batches grow to 500 objects. Verified below. POST form deferred because the framework stitcher exposes GET only. That is a framework change owned by `tooling`, and with packing in place it is optional. |

## URL packing check (`ComplianceDecisions.latestCompliantPaths`)

**Code reading.** Every length is measured on the **encoded** string: `part` is built from `enc(...)` before its length is compared.
- **Key chunks:** close before `chunk + part > budget/2`, so a chunk never exceeds half the budget unless a single key alone does.
- **Id packing:** each request packs ids while `base + ids + part + keys <= budget`. The comparison is `>` against the exact final path length (`base + ids + keys`, where `keys` carries its own leading `&statKey=`), so the boundary is inclusive and not off by one.
- **Minimum:** at least one id and one key per request, so a single oversized key still yields requests instead of looping or dropping.

**Independent probe.** I compiled the class and generated paths for 1x1, 5,000x1, 300x86, 7x86, 1x400 and 2,000x23 objects x keys, at budgets 6000, 600 and 200. Every path was decoded and parsed back. Results:
- **Length:** maximum path length never exceeded the budget (5,999 at budget 6,000 for 5,000 VMs: the inclusive boundary is hit exactly).
- **Coverage:** every (resource, key) pair appears exactly once.
- **Well-formed:** no leading, doubled or trailing `&`; only `resourceId` and `statKey` parameters.
- **Request counts:** 5,000 VMs x 1 key take 41 requests (matches the author's figure); 300 hosts x 86 keys take 10.
- **Encoding:** a key containing a space, `+`, `%` and `|` encodes to `%20`, `%2B`, `%25`, `%7C` (the `+` to `%20` substitution applies only to spaces URLEncoder produced).
- **Downstream:** `openPlatformConnection` builds `new java.net.URL(fullUrl)`, which does not re-encode, so there is no double-encoding. The full request line adds only the `https://localhost/suite-api` base (~27 chars), well under an 8 KB front-end limit.
- **API limit:** about 124 UUID ids fit per request, far below the spec's `resourceId` `maxItems: 1000`.

**Behavior note (not a finding).** Each request queries the batch's union of candidate keys for every id in it, so some pairs are over-queried. Results are still filtered per object against its own candidate set (`staleZeroControls(c, latest.get(id))`), so this costs a little response size and never correctness.

## Workflow review for public-repo abuse (`.github/workflows/tests.yml`)

- **Trigger:** `pull_request`, not `pull_request_target`, and no `workflow_run`. A fork PR gets a read-only `GITHUB_TOKEN` and no repository secrets.
- **Permissions:** `contents: read` at the workflow level. The job references no secrets.
- **Runner:** GitHub-hosted and ephemeral, so nothing persists for the release job. `build-pak-on-tag.yml` (self-hosted, holds `SDK_RUNTIME_SSH_KEY`) triggers only on `v*` tag pushes, which fork contributors cannot create.
- **Script injection:** no `${{ github.event.* }}` interpolation into any `run:` step. The only expression is `github.ref` in the concurrency group, which is not executed.
- **Pinning:** `actions/checkout` and `actions/setup-java` are pinned to full commit SHAs, the same pins as the tag workflow. No caches, artifacts or uploads that a PR could poison for a later trusted run.
- **Residual:** `checkout` persists the read-only token in `.git/config` on an ephemeral runner. That grants nothing beyond what the PR's own code already has, so it is not a finding.

## Regression review

Build 60 changes only request sizing, read accounting and logging, plus the runner line. The cleanup semantics are unchanged from build 59, where they were reviewed and found sound:
- only `-1` is written, only onto existing keys outside the applied benchmark that read exactly 0;
- no key is ever created, and a failed read cleans nothing;
- objects whose version could not be read are never queued.

The new early-return paths in `latestCompliant` return a failed `LatestRead` and never throw. Cleanup still runs after all collectors and before the rollup push.

## Still owed (not a finding)

Live proof of the cleanup read, per the build-60 CHANGELOG acceptance plan steps (a) to (d), during devel install and again on prod 9.1. Until then, the stats/latest shape is verified against `reference/docs/operations-api-9.1.json` only.

## If shipped as-is

Correct compliance data, scores and alerts. Alert cleanup costs about 41 loopback GETs per cycle for 5,000 VMs and leaves a per-cycle log line showing it actually read values. PR CI runs off the release runner. The remaining risk is that the cleanup read has not yet been seen working live, which the acceptance plan covers.
