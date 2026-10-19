# Reusable pak test workflow (template, 2026-10-15)

- **Decision (Scott, verbatim, 2026-10-15):** "build them in the template,
  then add the proper calls to synology and unif, and rewire compliance to
  call the central one"
- **Where:** `sentania-labs/vcf-content-factory-sdk-template`
  `.github/workflows/pak-tests.yml` (`workflow_call`), merged in template
  PR #20 (main 3cbbf21). Each pak calls it from a two-line
  `.github/workflows/tests.yml` at `@main`.

## What it runs, and what it cannot

On every push and pull request of a pak repo: an optional no-jar pre-check
(compliance passes its alert-currency generator check), then
`ci/run_java_tests.sh` on a JDK matrix (default 17 and 25, the collector
runtimes of 9.0.2 and 9.1.1). GitHub-hosted, `permissions: contents: read`,
`persist-credentials: false`, inputs reach the shell through `env` only,
actions pinned to full SHAs.

It does not and must not run `validate-sdk`, `build-sdk` or `pak-compare`.
Those need the Broadcom SDK jar, which lives only in the private
`vcf-content-factory-sdk-runtime` repo and is fetched over SSH with a
deploy-key secret by the tag build. A PR workflow runs pull-request code, so
the key and the jar never go near it. The PR gate is the unit tests; the tag
build is the compile and pak gate.

## Callers

| Repo | Caller | Pre-check | First green run |
|---|---|---|---|
| compliance | PR on branch ci/call-template-tests | alert generator --check | 38784651253 |
| unifi | on branch feat/build-14-availability-and-tls | none | 38784656321 |
| synology | on branch feat/build-31-availability-and-tls | none | 38784663179 |
| template (itself) | `tests-local` runs the PR's own copy; `tests` (@main) runs only in instantiated paks | none | 38784542429 |

Check names on a caller are `tests / tests (17)` and `tests / tests (25)`.

## Known limits

- A template PR that edits `pak-tests.yml` is tested by `tests-local`; the
  `@main` job in the same file fails at startup on a template PR until the
  reference exists, which GitHub resolves before evaluating `if:`.
- A pak instantiated from the template carries an unused copy of
  `pak-tests.yml`; it may delete it.
- Changing the gate (a pin bump, the Node 24 runtime move, the two-jar
  compile matrix of factory issue #211) is one template PR; callers follow
  on their next run.
- The tag builds still do not run the unit tests (pak issues unifi #28 CI7,
  synology #32 CI7).
