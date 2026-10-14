# Review: compliance build 94 (prod hotfix: name check against the dialled host)

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-13
- **Adapter:** `content/sdk-adapters/compliance/`, branch
  `fix/build-94-name-check-expected-host`, HEAD `7cdc0d8` (one commit on
  `main` `9d0e985`, which is v1.0.0.93)
- **Incident:** `knowledge/context/approvals/2026-10-13-compliance-v1.0.0.93-prod-install.md`
  (sections "Root cause and remediation" and "After Start Collecting"),
  adapter issue #48
- **Pak reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.94.pak`, sha256
  `97b08b4c4517897e7c77b3f5304267bfd9b3f739a70e226baa23b8656687dbd6`
  (matches the brief), reference `0.0.0.93`
- **Verdict:** APPROVE (0 BLOCKING / 1 WARNING / 1 NIT)

## Bottom line

The fix is correct and I reproduced both halves myself: the build 93 class
fails under BouncyCastle JSSE with the exact prod text ("the connection has
no peer host", `certificate_unknown(46)`) on the HttpsURLConnection (SOAP)
path, and the build 94 class passes the same handshake, while a wrong name
and an untrusted chain are still refused. Every TLS context the adapter
builds now gets the host its client dials, and every client dials the
account's vCenter Host / IP (esxcli included: it goes through vCenter's
`/sdk`, never to an ESXi host directly). One WARNING: the host parser
accepts `?`, `#` and similar characters, so a malformed vCenter Host entry
can make the name check compare against a different string than the host
actually dialled, which a wildcard certificate can then satisfy. Reachable
only through an operator typo, not a regression against v1.0.0.80 (no name
check at all), but cheap to close.

## Claims check (independent re-runs)

| Check | Result |
|---|---|
| `validate-sdk` | OK (javac `-source 11` options warning only) |
| `build-sdk` from HEAD `7cdc0d8` (scratch output) | builds 0.0.0.94; all 180 nested entries hash-identical to the author's pak. Adapter work tree clean afterwards. |
| `pak-compare` 94 vs 93 | gate PASS, 0 BLOCKING / 0 WARNING / 0 INFO. Matches the author. 93 to 94 differs only in the adapter jar's `ComplianceAdapter*` / `VCenterCertificates*` classes, version/manifest files and the overview HTML; describe.xml identical. |
| `ci/run_java_tests.sh` (JDK 17) | all Java suites pass including CertificateTest and BcHandshakeTest; generator `--check` up to date; all Python suites OK |
| `pytest` | adapter `tests/`: 37 passed; factory `tests/`: 2063 passed, 5 skipped |
| Shipped class | the pak's `VCenterCertificates.class` carries the build 94 `NO_HOST_MESSAGE` text, not the build 93 "no peer host" text |

## Brief items

**(a) Overloads and fail-closed.** `NameCheckingTrustManager`
(`VCenterCertificates.java:338-373`): all three `checkServerTrusted`
overloads (Socket, SSLEngine, 2-arg) run the platform chain check first,
unchanged from 93 (extended overload when the platform manager is an
`X509ExtendedTrustManager`, else the 2-arg), then `checkName(expectedHost,
chain)`. `expectedHost` is fixed at construction from `expectedHost(vcenterHost)`.
A null host throws `NO_HOST_MESSAGE` in `checkName` (`:420`); there is no
path that returns without a match. The 2-arg overload now checks the name
too (93 refused it outright); that is correct now that the host does not
come from the connection. Untrusted chain: the platform throws before the
name check, so `classify` still returns UNTRUSTED (CertificateTest and
BcHandshakeTest both assert it, and both pass).

**(b) Every context gets the right host.** `nameChecking` has one caller,
`sslContextFor(dialledHost)` (`ComplianceAdapter.java:237`), and every call
passes the host its client dials: REST `VCenterApiClient` (`:172`,
`config.baseUrl()` = `https://` + `vcenterHost`), vim25 SOAP
`VSphereClient` (`:176`, `https://<vcenterHost>/sdk`), esxcli (built inside
`VSphereClient` at `:187` on the same `vcenterUrl` and the same factory, so
it dials vCenter's `/sdk`, which relays to the host; the vCenter name is the
right expected host), Test Connection (`:322`, `testCfg.vcenterHost` with
`testCfg.baseUrl()`), VAMI (`:2107`, `config.baseUrl()`). No client follows
redirects (HttpClient default NEVER), so no connection can land on a
second host under this context. No other class builds a TLS context.

**(c) Normalization.** Probed the build 94 class directly against a
`*.example.org` certificate and compared `expectedHost` to the host
`URI` (HttpClient) and `URL` (HttpsURLConnection) actually dial: port
stripping, IPv6 brackets (`[::1]:443` to `::1`, IP SAN compared by
`InetAddress`, never DNS), case and a single trailing dot are all safe;
`https://...`, a path and a zone-id literal yield null and fail closed;
`u@vc.example.org` cannot widen (the dialled host is the suffix, so any
certificate matching the entered string also matches the dialled one). The
exception is W1 below.

**(d) Reproduction.** Independent harness (my own code, not the author's
test) compiling the 93 and 94 `VCenterCertificates.java` from git against a
local SunJSSE HTTPS server, client JVM with BCJSSE 1.82 installed:

| Build / provider | HttpsURLConnection (SOAP path) | HttpClient (REST path) |
|---|---|---|
| 93 / SunJSSE | 200 (peer host present) | 200 |
| 93 / BCJSSE | **FAIL** `TlsFatalAlert certificate_unknown(46)`, cause "The vCenter certificate name cannot be checked: the connection has no peer host", peer host seen by the trust manager `null` | 200 (peer host present) |
| 94 / SunJSSE | 200 | 200 |
| 94 / BCJSSE | 200, peer host still `null` | 200 |

This matches prod exactly (SOAP fails, Validate Connection's HttpClient
path works). Checksums: downloaded the three jars myself; the pinned
SHA-256s equal Maven Central's published `.sha256` files and the `.sha1`
files match; all three jars pass `jarsigner -verify`. CI behavior: with a
`curl` shim that always fails, `GITHUB_ACTIONS=true ci/run_java_tests.sh`
exits 1 ("could not be fetched"); without it the run exits 0 and prints
"BcHandshakeTest NOT EXERCISED". A checksum mismatch exits 1 in both. Both
workflows (`tests.yml`, `build-pak-on-tag.yml`) run the script on
GitHub-hosted runners, so the tag build cannot ship with the test skipped.
Only JDK 17 exists on this workstation; the JDK 25 leg is CI's.

**(e) Test-only jars.** The jars land in the script's `mktemp` output dir;
the pak has no BouncyCastle entry at any nesting depth and no test class.

**(f) Docs and CHANGELOG.** CHANGELOG line matches the code on every claim
I checked (overloads, normalization, fail-closed text, unchanged chain
check and strict verifier, the test inventory, the 93 repro). `docs/`
only bumps the generated version; `installing.md:255` and
`overview.md:322-333` already describe the name check accurately and
nothing in them says "peer host". The only em dash in the diff is the
generated `inventory-tree.md` banner (factory issue #204, pre-existing).

## Findings

### W1 (WARNING): the host parser lets the name check compare a string the client never dials

`VCenterCertificates.java:70-71` (`HOST_PORT`, host class
`[^:\[\]/\s]+`) feeds `expectedHost` (`:301-309`). Characters that end the
authority in a URL (`?`, `#`) are accepted, so for an entered host of
`vc?.example.org`: `expectedHost` = `vc?.example.org`, but both HttpClient
and HttpsURLConnection dial `vc`; `dnsMatches` lets the wildcard label
match `vc?`, so a platform-trusted `*.example.org` certificate presented by
whatever answers at `vc` passes. Verified with the probe above (same for
`vc#.example.org`). On the HttpsURLConnection paths the strict hostname
verifier still refuses (it checks `vc`), but the HttpClient paths (REST
login, which sends the credentials, VAMI, Test Connection) rely on this
trust manager alone. Build 93 on SunJSSE checked the dialled `vc` and
would have refused. Authority: skill "vim25 over JAX-WS" / the build 93
B1 contract (the certificate must carry the host the adapter connects to);
`knowledge/rules/no-secrets-on-disk.md` spirit for the credential exposure.
Not BLOCKING: it needs a malformed operator entry plus a wildcard
certificate plus an interposer, and v1.0.0.80 (prod's fallback) checks no
name at all. **Fix:** restrict the unbracketed host class in `HOST_PORT` to
hostname characters (`[A-Za-z0-9._-]+`), which also stops `checkUrls`
handing such a URL to Validate Connection; or derive the expected host from
`URI.create(config.baseUrl()).getHost()` and fail closed when it differs
from the parsed entry. Add the two probe inputs to CertificateTest.
Recommend closing it in 94 before the tag since it is one line; not a
registration candidate if fixed now, registration candidate if deferred.

### N1 (NIT): workstation run silently passes with the BC test skipped

`ci/run_java_tests.sh` exits 0 offline with a stderr line. Correct per its
comment and CI cannot take that path, but an author reading only the exit
code would not notice. Optional: print the NOT EXERCISED line last or to
stdout.

## Dimension walk (delta only)

1, 3 (cardinal / failure granularity): no read path changed; a TLS failure
still aborts the cycle with `Rollup|incomplete` (build 93 W1), never a
pass. 2 (vim25 reflection): not touched. 4, 5 (loader, stitching): not
touched. 6 (logging): no new log lines; no secrets. 7 (resources): no new
long-lived state; one context per client as before. 8: no new round trips.
9 (hygiene): `build_number` 93 to 94, CHANGELOG line, minimal diff (two
source files, tests, script, CI comment, generated docs). 10 (gaps): none
introduced. 11 (docs parity): see (f). 13 (describe import rules): describe
unchanged (pak-compare and nested-entry diff), no alert change.

## Registry check (`knowledge/context/defects.md`)

- **DEF-023** (open, tracked): unchanged; `ComplianceStitcher.fetchResources`
  (`ComplianceStitcher.java:152` call site) is not in this diff. Still owes
  its paging proof.
- **DEF-025** (open, tracked): unchanged; `cleanBatch`
  (`ComplianceAdapter.java:1215`) is not in this diff.
- DEF-022 and DEF-024 are closed; not re-opened by this build.

## If shipped as-is

Prod 9.1.1 collectors collect again on correctly named accounts, wrong
names and untrusted chains are still refused, and only an account whose
vCenter Host contains `?` or `#` gets a weaker name check than intended.

## Warning fix confirmation

APPROVE, 0/0/0: a9eba2e (one commit on 7cdc0d8, PR #49) changes only the HOST_PORT pattern, its javadoc, CertificateTest cases, the run_java_tests.sh SKIPPED banner and the CHANGELOG line; my old-vs-new probe accepts every previously valid form (FQDN, short name, trailing dot, IPv4, IPv4:port, bracketed and bare IPv6, host:port, underscore, punycode) and refuses `vc?`, `vc#`, `user@`, `%2e` and raw-Unicode hosts (the last never dialable by java.net.URI); ci/run_java_tests.sh passes locally with BcHandshakeTest exercised, PR #49 CI green on JDK 17 and 25 (push and pull_request, both at a9eba2e), validate-sdk OK, DEF-023 and DEF-025 untouched.
Final pak `dist/vcfcf_sdk_compliance.0.0.0.94.pak` sha256 121e8b96fc4d4358a5d8b56111a8239f4ad9af49f224b6be8a7a8de91d95c1ee; my build-sdk from HEAD hashes differently (zip timestamps) but every nested entry (adapter jars, views.zip, overview.packed) is byte-identical to it.
