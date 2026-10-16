# Template: close the 2026-09-24 review findings so new paks start clean

- **Type:** managementpack (Tier 2 SDK adapter template change)
- **Slug:** template-build-2-review-findings
- **Adapter repo:** `content/sdk-adapters/template/` (branch from `origin/main`)
- **Date:** 2026-10-16
- **Status:** done, not tagged: build 2 merged (df34aea, PR #21), the release workflow hardening merged (f2f7ea8, PR #22) and the gate follow-up (indented and disguised headings, fences, BOM, unit tests in the tag build) merged (743ce31, PR #23) on 2026-10-16, plus the Codex fenced-first-entry gate fix (49ab82c, PR #24); the workflow, gate and gate tests are byte-identical on compliance (91991d7, ae94bdc), synology (acbd2a2) and unifi (df3d4aa, 8f0aa31) main; CI2 and CI5 settings remain open on template #18 and the three CI issues

## Initial prompt (Scott, verbatim, 2026-10-16)

> the fork paks are enhancedments we will tackle.  let's focus on the
> compliance, unif, synology, and template.  Triage them, order them, and
> let's fix them all in this session.
>
> Do any of them require design decisions?

## Why

Every pak instantiated from the template inherits its defaults and its
shape. UniFi build 14 and Synology build 31 just fixed, in each child, the
TLS default, the DOWN mapping, the 0.0 sentinel and the per-cycle snapshot
that the template still teaches. The template goes first so the next pak
does not start with the same findings.

## Scope (template issues, in order)

Code and docs (one PR):

1. **#8** `allowInsecure` default `false` in `describe.xml`; strict parse
   stays (`"true"` only); one WARN per configure while insecure; docs table
   default column `false`; CHANGELOG upgrade note.
2. **#13** `mapCollectException` walks the cause chain and maps
   `ConnectException`, `UnknownHostException`, `NoRouteToHostException`,
   `HttpConnectTimeoutException`, `HttpTimeoutException`,
   `SocketTimeoutException` to DOWN. Mirror the `UniFiFailures` /
   `SynologyFailures` helper shape.
3. **#10** publish `Status|value` only when the field is present and
   numeric; add a `metricIfPresent(out, key, SimpleJson)` helper and use it.
4. **#9** one immutable snapshot per collection cycle with a `Map<id,item>`
   index; `rediscover` and every `collect` in the cycle read it. Keep the
   shape small: the template is a teaching artifact, not UniFi's
   `SnapshotCache`. A short comment points at the children for the
   failure-caching version.
5. **#14** `currentSnapshot()` copies the volatile `api` field to a local
   and throws `InterruptedException("discarded")` when null; `rediscover`
   checks `isAbortRequested()` at entry.
6. **#12** bounded response body in `ExampleApiClient.get()` (default cap
   8 MB, one constant), `IOException` over the cap; reject a non-JSON
   `Content-Type` before parsing.
7. **#16** `ExampleConfig` validates host (hostname, IPv4, bracketed IPv6;
   no `/ @ ? #` or whitespace) and port (1 to 65535); clear
   `IllegalArgumentException` surfaced by `getTester`; URL built with
   `new URI(...)`.
8. **#15** `password` private with a package-private accessor used only by
   `buildHttpClient`; `toString()` prints host, port, username,
   allowInsecure and `password=***`.
9. **#17** docs: CHANGELOG correction for the deploy key, README jar-source
   wording (clone, not release), buildkit download with a full version tag
   plus `sha256sum -c`, jar storage "private repo only, never a workflow
   artifact", installing.md TLS default.

CI (second PR, `github-ci` skill applies):

10. **#11** back-port the tag-vs-adapter.yaml version check and `--release`
    from the compliance workflow.
11. **#18** CI1 (`persist-credentials: false`, split build and publish
    jobs), CI3 (gate on `pak-compare` exit code or exact count), CI4
    (defect gate fails closed, case-insensitive Affects, heading suffix),
    CI6 (no `--clobber`, `SHA256SUMS`, provenance attestation), CI7
    (pinned pyyaml). CI2 (pinned buildkit with checksum) needs a factory
    buildkit release first and CI5 (protected Environment, tag ruleset,
    per-repo deploy keys) is a GitHub settings change for Scott; both stay
    open on the issue with a comment.

## What must not regress

- `validate-sdk` and `build-sdk` on the template still produce a loadable
  example pak.
- `ci/run_java_tests.sh` still auto-discovers `tests/**/*Test.java` and the
  reusable `pak-tests.yml` callers (compliance, UniFi, Synology) still pass.

## Proof

- Unit tests for strict parse and default, DOWN mapping through a wrapped
  cause, missing-field skip, snapshot served once per cycle, body cap,
  host/port validation, redacting toString.
- `validate-sdk`, `build-sdk` dev build, pak-compare zero BLOCKING against
  the previous template build.
- Reviewer gate (`sdk-adapter-reviewer`), peer review, PR, Codex round,
  merge to main, no tag.
