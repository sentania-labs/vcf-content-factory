# Framework review: accept-certificate hook, allowInsecure pulldown, #174 (2026-09-25, round 1)

Branch `feat/framework-cert-accept-hook` (commits 2f6dc5c, 0a45ab6),
reviewed by `framework-reviewer` against origin/main. The reviewer's
harness could not write files, so the orchestrator saved its report here.

```
FRAMEWORK REVIEW
  area: adapter_framework/VcfCfAdapter.java, vcfcf_common/client.py (+3 callers), vcfcf_packaging/templates/install.py, vcfcf_managementpacks/sdk_builder.py (scaffold)
  change: accept-certificate hook + allowInsecure pulldown + VERIFY_SSL=false beats REQUESTS_CA_BUNDLE (#174) + scaffold v2 / removeprefix
  verdict: APPROVE
  findings: 0 BLOCKING / 4 WARNING / 4 NIT
  checks re-run: validate-chain pass (7/7); validate-sdk pass on all 6 SDK adapters built against this branch's framework; Java: CertificateReviewTest 49/49, VcfCfAdapterTest 11/11, stitch 28/28, 8/8, 18/18; pytest 1900 passed / 0 failed with pak clones linked (6 environmental failures in a bare worktree)
```

## WARNING

1. **Synology legacy parity** (`parseAllowInsecure(String, boolean)`
   javadoc; tier2_architecture.md adoption table). Legacy synology parse is
   `!"false".equalsIgnoreCase(v)`, so "yes", "1", " false" mean insecure;
   `parseAllowInsecure(v, true)` makes them secure. Legacy parsers do not
   trim, so a stored " true" is secure today and insecure after adoption.
   `isAllowInsecure(rc)` has no default-when-blank overload. Fix: a
   legacy-compatible parse (or `isAllowInsecure(rc, boolean)`), and state
   exactly which stored values change.
2. **`getCertificateRenewalUrls()` has cost and no benefit.** Every listed
   target fails the renewal protocol (signed `jwt_token` JSON), yet opting
   in makes the collector build a throwaway adapter, run `configure()`
   (whose http client is never discarded) and GET the target from the
   trust-manager path on each unknown certificate for a saved instance.
   Fix: drop the renewal override until a target serves the protocol, or
   prove the path benign.
3. **Buildkit version ordering.** This branch changes kit contents but
   leaves `BUILDKIT_VERSION` to `fix/pipeline-hardening-round` (1.0.11). If
   that merges and 1.0.11 is tagged first, this change ships under no new
   version. Fix: hold the 1.0.11 tag until both branches are merged, and
   say so in the PR.
4. **Stale distribution zips not flagged.** `templates/install.py` changed
   (stamp correctly bumped to 2026-09-25-1), so every bundle needs a full
   content-packager rebuild; say so in the PR.

## NIT

1. The bare-session guard test matches only `requests.Session()`; widen it
   to `requests.session()`, `from requests import Session`, and module-level
   `requests.get/post/...` without `verify=` (no offender today).
2. `getConnectionURLs` does not itself enforce "no URLs when allowInsecure";
   only the hook convention does. Say so in the javadoc.
3. `onTest` calls the user hook on every failure, and an `Error` thrown
   there escapes. Compute declared URLs only after a trust failure is found.
4. The `promptAvailable=false` message says the pack "does not declare its
   endpoint", but an opted-in pack also returns none when allowInsecure is
   true or the host is blank. Reword to cover both.

## What checked out

- Overridden signatures match SDK 2.2 by javap; both overrides present in
  the compiled class; compiles at `-source 11`.
- Non-opted-in paks: SDK defaults preserved (NOT_SUPPORTED, null renewal
  URLs); only the reworded trust-failure message is new for them.
- Hook reads only the passed config on an unsaved instance.
- VERIFY_SSL=true still honours REQUESTS_CA_BUNDLE; per-request verify=
  wins; env proxies untouched; install.py stays pure Python (RULE-018).
- Scaffold compiles; class-name tests pass; `removeprefix` fits Python 3.9.
- `git merge-tree` with `fix/pipeline-hardening-round`: clean.

## Round 2 (commit 02aed95): APPROVE, 0 BLOCKING / 0 WARNING / 3 NIT

Checks re-run: framework compiles at `-source 11`; CertificateReviewTest
83/83, VcfCfAdapterTest 11/11, stitch 28/28, 8/8, 18/18; pytest 1909
passed / 0 failed / 8 skipped with pak clones linked (scaffold compile test
ran); validate chain 7/7 plus `vcfcf_packaging validate`; `validate-sdk` OK
on all six adapters; `git merge-tree` with `fix/pipeline-hardening-round`
clean.

Round 1 status: W1, W2, NIT2, NIT3, NIT4 resolved; W3 resolved as a
documented tagging rule (1.0.11 only after both branches merge); W4
handled in the PR body; NIT1 mostly resolved.

Remaining NITs:
1. `tests/test_verify_ssl_env_override.py` `_requests_misuse` misses
   `import requests as r; r.Session()`, `from requests import get`,
   `requests.sessions.Session()`, and `requests.get(url, verify=None)`
   (none in `src/` today). Resolve aliases, flag any import from
   `requests`, require a non-None `verify=`.
2. `VcfCfAdapter.certificatePromptAvailable` catches `Throwable`,
   swallowing `VirtualMachineError`; rethrow `VirtualMachineError` (and
   `ThreadDeath`), catch the rest.
3. `tier2_architecture.md` adoption paragraph: cite
   `knowledge/context/approvals/2026-09-25-scott-decisions.md` item 15 for
   the secure-default decision; the file must be present on this branch.
