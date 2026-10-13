# Review: compliance build 93 (Auto only, certificate accept dialog)

- **Reviewer:** sdk-adapter-reviewer
- **Date:** 2026-10-13
- **Adapter:** `content/sdk-adapters/compliance/`, branch
  `feat/build-93-auto-only-cert-accept`, HEAD `8021a1c` (six commits
  `296db83..8021a1c` on top of build 92 at `f22c3d8`)
- **Design:** `knowledge/designs/sdk-adapters/compliance-build-93-auto-only-cert-accept.md`
- **Pak reviewed:** `dist/vcfcf_sdk_compliance.0.0.0.93.pak`, sha256
  `55b45435bf0864da14280a646d07d64a46101aa5a939db6b8fa3a40d4029f3aa`
  (built 3:27 PM today), reference `0.0.0.92` (`d212c970...`)
- **Verdict:** CHANGES REQUESTED (2 BLOCKING / 1 WARNING / 5 NIT)

## Bottom line

The trust-all code is gone everywhere and the hook is wired correctly, but
the build's promise that a hostname mismatch fails is not true on any path.
VCF Operations' trust manager checks the certificate chain only, and both
JDK HTTP clients the adapter uses hand the name check to that trust
manager, so no name is ever matched. The docs, code comments and CHANGELOG
say the opposite. Separately, the INFO and WARN lines that the upgrade
notes tell operators to rely on will probably never fire, because the
build 92 devel upgrade showed the platform drops a removed identifier's
stored value. Both fixes are text-only unless Scott wants a real name
check (a design decision, see B1).

## Claims check (independent re-runs)

| Check | Result |
|---|---|
| `validate-sdk` | OK (javac `-source 11` options warning only) |
| `build-sdk` from HEAD (scratch output) | builds 0.0.0.93. All 177 nested entries (adapters.zip, jars, content) hash-identical to the author's pak; `overview.packed` differs only as an archive (extracted contents identical). The pak's describe.xml is byte-identical to HEAD. Adapter work tree clean afterwards. |
| `pak-compare` 93 vs 92 | gate PASS, 0 BLOCKING / 1 WARNING (instance identifier count 3 vs 5) / 1 INFO (manifest description). Matches the author's 0 B / 1 W / 1 I. |
| `ci/run_java_tests.sh` | all 14 Java suites pass (CertificateTest included), all 6 Python suites pass |
| `pytest` | adapter `tests/`: 37 passed; factory `tests/`: 2063 passed, 5 skipped |
| Bytecode scan of `vcfcf_compliance.jar` | no reference to `insecureSslContext`, `X509TrustManager`, `HostnameVerifier` in any adapter class |
| Bundled `vcfcf-adapter-base.jar` | carries `certificateCheckUrls`, `getConnectionURLs`, `declaredCertificateUrls`; the adapter class overrides `certificateCheckUrls` |

## Brief items

### (a) Trust-all removal and hostname verification

**Trust-all: confirmed gone.** Source grep across the whole adapter repo
(excluding `.git`) finds no TrustManager implementation, no
`setHostnameVerifier`, no `insecureSslContext`, no trust-all factory. The
only `allowInsecure` strings left are the retired-key constant, the WARN
text, describe comments and upgrade docs. Every vCenter HTTPS path takes
the platform context or, if that is unavailable, the JDK default (never
trust-all):

- vCenter REST (`VCenterApiClient`, `java.net.http.HttpClient`):
  `sslContextFor()` (`ComplianceAdapter.java:222`).
- VAMI (`VamiApiClient`, `HttpClient`): `sslContextFor()` (`ComplianceAdapter.java:2039`).
- vim25 SOAP (`VSphereClient`, `HttpsURLConnection`): `sslSocketFactoryFor()`
  (`ComplianceAdapter.java:241`).
- esxcli SOAP (`EsxcliSoapClient:620`): the same factory, threaded from `VSphereClient`.

**Strict hostname verification: refuted.** See B1.

### (b) `certificateCheckUrls`

Correct. `@Override` sits directly on the method (`ComplianceAdapter.java:274`),
so a 1.0.10 buildkit fails to compile, which is the intent and is stated
in `docs/building.md`. The URL comes only from the passed config
(`getIdentifier(rc, "vcenter_host")`), never instance state. Port: an
entered `host:port` is kept and matches what `VSphereClient` and
`ComplianceConfig.baseUrl()` dial; no port means 443. Blank, null, a
scheme, a path, an out-of-range port or a bare IPv6 literal return an
empty list. Nothing inside can throw (`\d{1,5}` bounds the `parseInt`),
and the framework wraps the call in `catch (RuntimeException | LinkageError)`
anyway (`VcfCfAdapter.java:1388-1393`). `VCenterCertificates` has no SDK
import, so the CI test compile (`-sourcepath src:tests`) builds it with a
plain JDK; confirmed by the run above. N1 covers a dead parameter.

### (c) Test Connection path, and the TOOLSET GAP grade

Correct. Only a failure the adapter classifies as a certificate problem is
rethrown without its cause (`ComplianceAdapter.java:313-327`); the
original is logged first with its stack (`logWarn(..., e)`), and the
framework's `onTest` logs the rethrown one too. Every other failure is
rethrown unchanged (`if (f == null) throw e;`), cause intact. The
replacement message carries no PKIX trigger text, and the adapter's
classifier is a superset of the framework's `findCertificateTrustFailure`
(same three types, same two strings, plus "PKIX path validation failed"),
so nothing the framework would have rewritten slips through with a cause.
No secret reaches the log: `VCenterApiClient` exceptions carry only HTTP
status and path.

**TOOLSET GAP grade: genuine, correctly worked around.** The framework's
`certificateTrustFailureMessage` (`VcfCfAdapter.java:1530-1547`) hardcodes
"set Allow Insecure SSL to true" advice in both branches, which is wrong
for any pak that removes the setting. The workaround is sound for
compliance. It will recur in unifi and synology under the same design, so
it should be filed for `tooling` before those builds (suggested fix: omit
that advice when the pak declares no `allowInsecure` identifier, or let
the pak supply the advice text).

### (d) Auto only

Correct in code. `BenchmarkSelector` has no fixed mode, no `fixed()` factory
and no `isAuto()`; `select` checks the pin, then Auto. The manual-review
overlay still applies (`buildSelector` loads `loadAll` and logs
`lastManualReviewApplied`). Pins: a kind-less `<Profile>` sets
`instancePin`; `Resolved.pinFor` returns the kind pin first, then the
instance pin, and `pins()` resolves every kind through it, so kind wins
regardless of file order; a duplicate instance pin is rejected. A stored
fixed value or stored `allowInsecure=true` is read only for a log line
and has no effect on behavior, so those accounts run Auto and validate
strictly. A blank stored profile runs Auto (it used to fall back to fixed
`VMware_SCG_8.0`, see N4). Whether the log lines fire at all is B2.

### (e) describe.xml (dimension 13 included)

Correct. Built pak parsed independently: identifiers are `vcenter_host`
(no identType), `overrides_file` and `read_appliance_settings`
(`identType="2"`, optional, with defaults, so Advanced Settings per the
investigation's rule). `read_appliance_settings` is byte-for-byte the same
as in 0.0.0.92 (`enum="true"`, `false`/`true`, default `false`). nameKeys
7 and 9 are removed from describe.xml and `resources.properties` and not
reused (8 stays retired). 152 symptom definitions, 152 `SymptomSet`
references all resolve, 7 `SymptomSets` containers each with two or more
children, every `waitCycles`/`cancelCycles` is an integer. Alerts are
untouched by this build.

### (f) Docs

`building.md` states the 1.0.11 prerequisite accurately. No em-dash in
any authored line of the diff (the one hit is the `docs_gen` banner, N5).
"Custom" and "Allow Insecure SSL" appear only in upgrade notes that say
they were removed, which is reasonable for upgraders; nothing presents
either as a choice. But the TLS section states hostname behavior that does
not exist and lacks the mismatch caveat (B1), and four docs promise
upgrade log lines that are likely never written (B2).

### (g) Cardinal rule

Nothing in the certificate change can turn a failed read into a pass. A
certificate failure at cycle start throws before any push
(`ensureVCenterConnected`, `ComplianceAdapter.java:476-486`); a VAMI
certificate failure goes through the existing per-control unreadable
path (build 74). The certificate classifier only changes message text. The
one cardinal-adjacent effect is W1: a whole-cycle failure leaves old scores
in place, and this build creates a new group of accounts that will hit it.

## Findings

### BLOCKING

**B1. No path checks the certificate name, but docs, comments and
CHANGELOG say the SOAP connection does.** Dimension 11 (docs contradicting
behavior); skill § vim25 over JAX-WS (SSL convention);
`knowledge/context/tier2_architecture.md` "Accepting an untrusted target
certificate", hostname bullet.

Evidence:

1. The platform trust manager is chain-only. `javap -c` on
   `CustomTrustManager` in `adapter_runtime/vrops-adapters-sdk-2.2.jar`:
   the `Socket` and `SSLEngine` overloads of `checkServerTrusted` reduce
   the peer to an `InetSocketAddress` and delegate to
   `X509TrustManager.checkServerTrusted(chain, authType)`, the 2-argument
   form with no endpoint identification. tier2_architecture.md records
   the same for 9.1.1.
2. The JDK hands the name check to that trust manager. With the default
   `HostnameVerifier`, `HttpsURLConnection` sets the endpoint
   identification algorithm to HTTPS and skips its own hostname check,
   expecting the trust manager to do it. `HttpClient` does the same.
3. Local reproduction (scratch dir, no lab): a JDK 17 HTTPS server with a
   certificate for `othername.example`, reached as `localhost`, through an
   `X509ExtendedTrustManager` that does chain checks only. Result:
   `HttpsURLConnection` with the default verifier returned HTTP 200, and
   `java.net.http.HttpClient` returned HTTP 200. The control (JDK PKIX
   trust manager) rejected with "No subject alternative DNS name matching
   localhost found."

So vim25, esxcli, REST and VAMI all accept a certificate the trust
manager trusts, whatever name it carries. The `NAME_MISMATCH` branch of
`VCenterCertificates.classify` and its message can only fire on the
JDK-default fallback (no platform context). This is not a regression:
build 92's `allowInsecure=false` path behaved the same way. But the build
now tells operators the opposite:

- `docs/installing.md:79-82`: "the vSphere SOAP connection checks the
  name and fails, and the error tells you to re-enter the host"
- `docs/overview.md:315`: "The name must still match"
- `VSphereClient.java:1410-1411`: "the certificate must carry the name
  vCenter is entered by"; `ComplianceAdapter.java` `sslSocketFactoryFor`
  javadoc ("The JDK's default hostname verifier stays in place")
- CHANGELOG build 93 line ("a name mismatch has its own text")

The brief's expected caveat, that a hostname mismatch passes Validate
Connection, appears nowhere.

What this means operationally: an account entered by IP whose certificate
lacks that IP collects normally once the certificate is trusted, and any
certificate signed by a CA in the VCF Operations trust store is accepted
for this vCenter, whatever name it was issued for.

Smallest correct fix (text only): say that the chain is validated
(trust store plus accepted certificates) but the name is not matched
during collection or Test Connection. Keep "enter vCenter by the name on
its certificate" as advice, since the platform's review probe uses
`CustomHostnameVerifier` (devel will show what the dialog does on a
mismatch). Correct the two code comments and the CHANGELOG line. Mark
`NAME_MISMATCH` as fallback-only in its javadoc, or delete it.

Alternative, Scott's call (a design change, not this review's): enforce
the name by wrapping the platform trust manager in an
`X509ExtendedTrustManager` that runs the platform chain check and then a
hostname check against the `SSLEngine`/`Socket` peer host, used for all
four clients.

Registration candidate if shipped as-is.

**B2. The upgrade log lines the docs promise will probably never fire.**
Dimension 11; dimension 1 (the burden is on the code to prove the
behavior it claims); design item 1 ("logs one INFO line naming the stored
value").

`configureAdapter` reads `benchmark_profile` and `allowInsecure` from the
`ResourceConfig` (`ComplianceAdapter.java:134-139`), but both identifiers
are gone from describe.xml. The only devel evidence on this exact
question says the platform drops the stored value of a removed
identifier on upgrade:
`knowledge/context/approvals/2026-10-13-compliance-build-92-devel-install.md`
says "stored settings unchanged except custom_profile_path no longer
stored", observed right after the build 92 install. If that holds here,
`getIdentifier` returns null, `retiredProfileNotice` and
`retiredAllowInsecureNotice` return null, nothing is logged, and
`zeroCustomBucket` is never set (an account going straight from 91 to 93
with `Custom` keeps its old `Rollup|Benchmark|Custom|objects`).

The operator impact: an account on a fixed SCG silently switches to Auto
and its scores move, and the old value is gone from the account. Yet the
docs tell the operator to rely on the log line:

- `docs/installing.md:104` and `:201`
- `docs/overrides.md:171` ("The upgrade log line for the account names
  the entry to add")
- `docs/data-reference.md:20` and `:27`
- `README.md:184-185`
- CHANGELOG build 93 line

Smallest correct fix: add a pre-upgrade step to installing.md (and
point to it from README and overrides.md): before upgrading, record each
account's Compliance Profile and Allow Insecure SSL values (edit dialog,
or `GET /api/adapters/{id}` resourceIdentifiers), then after the upgrade
add `<Profile version="SCG X.Y"/>` for each fixed account and Validate
Connection each formerly insecure one. Reword the log-line claims as
"if the platform still passes the stored value". The code can stay.
Proving on devel that the lines fire after a 92-to-93 upgrade would also
close this, but the 92 evidence points the other way.

### WARNING

**W1. A certificate failure at cycle start leaves the last scores showing
as current, with no compliance-side signal, and this build creates a new
group of accounts that will hit it.** Dimension 1 (skill § Unreadable is
NOT compliant); the adapter's own build 85 comment ("a stale pass is a
false pass").

`ensureVCenterConnected` throws, the cycle ends before any push, and the
account goes to ERROR. Nothing pushes `collection_failed` or
`Rollup|incomplete`, so none of the six collection alerts fire, and the
per-object scores (passes included) and the vCenter rollup keep their
last values on every dashboard.

This was already true of any vCenter connect failure, but every account
upgraded with `allowInsecure=true` and an untrusted certificate lands in
this state on its first cycle. B2 means it may not even get its WARN.
Fix: at minimum, an upgrade-note step to Validate Connection on every
formerly insecure account straight after the upgrade and to check
account status. Better: push `Rollup|incomplete=1` on the vCenter when
the cycle fails at connect, if the vCenter's resource id can be
resolved without vCenter (a follow-up build). Registration candidate
(pre-existing class, newly reachable on upgrade).

### NIT

- **N1** `VCenterCertificates.java:1036-1048`. The `readAppliance`
  parameter adds `rootUrl(vcenterHost)` a second time, and the set drops
  the duplicate, so the branch does nothing, and the hook reads
  `read_appliance_settings` for nothing. Drop the parameter, or keep it
  with a comment that it is deliberately a no-op.
- **N2** `ComplianceOverrides.java`. Stale javadoc: the class doc says
  Profile replaces "Auto (by version) or the fixed choice"; the `resolve`
  `@param profiles` says "and the instance's own when it is not
  bundled"; the `pinFor` doc says "the instance's mode applies". None of
  these exist since build 92/93.
- **N3** `CertificateTest.sourceContract`. The no-trust-all source pins
  cover `ComplianceAdapter` and `VSphereClient` only. Extend "no
  `TrustManager` / `HostnameVerifier` / `insecureSslContext`" to
  `EsxcliSoapClient`, `VCenterApiClient` and `VamiApiClient`. My bytecode
  scan shows none today; the pin keeps it that way.
- **N4** `ComplianceConfig.retiredProfileNotice`. A blank stored profile
  used to mean fixed `VMware_SCG_8.0` (the pre-v3 fallback) and now means
  Auto with no notice. This is intended per the brief, but it is a
  silent benchmark change for those accounts. Mention it in the upgrade
  note.
- **N5** `docs/README.md` / `docs/inventory-tree.md` banner ("Do not edit", then an em-dash, then
  "regenerated") carries an em-dash. It comes from the factory `docs_gen`
  generator, not this build: a `tooling` item.

## Review dimensions

1. Cardinal: no new path to a pass; W1 is the stale-score exposure. 2.
   vim25: no accessor change. 3. Exceptions: certificate wrapping keeps the
   cause on the cycle path and logs the original on the test path; no
   empty catch added. 4. Loader: only the error text changed
   (`BenchmarkLoader.java:320`). 5. Stitching: untouched
   (`ComplianceStitcher.java` not in the diff). 6. Logging: one INFO and
   one WARN per configure at most, no secrets; the configure line still
   prints `profile=Auto (by version)`. 7. Memory: one platform context per
   configure for REST and SOAP, one per cycle for VAMI as before; no new
   long-lived state. 8. Performance: host version reads now run on every
   account (they used to be skipped in fixed mode), which is the normal
   Auto cost; `loadAll` is reused rather than called twice. 9. Build
   hygiene: `build_number` 93, CHANGELOG line present, diff limited to the
   design scope; behavior preservation for pins is shown by the updated
   `OverridesTest`/`BenchmarkSelectorTest` (both pass). 10. Gaps: the
   framework message gap is genuine and named in the code comment; file
   it (see (c)). 11. Docs: B1, B2. 13. describe: clean (see (e)). 12.
   Registry: below.

## Registry check (`knowledge/context/defects.md`)

- **DEF-023** (single-page resource list): still open, unchanged.
  `ComplianceStitcher.fetchResources` (`ComplianceStitcher.java:277`) is
  not in the `f22c3d8..8021a1c` diff. Still owed: devel proof of the paging
  or the vCenter collection alert path.
- **DEF-025** (retired control alert never cancels): still present,
  unchanged. `cleanBatch` (`ComplianceAdapter.java:1147`) and
  `ComplianceDecisions.staleControls` (called at `:1194`) are not in the
  diff. This build makes it more reachable: an account that ran a fixed
  SCG and now runs Auto changes guide version on upgrade, so controls
  retired by that change get the one-time -1 and any open alert on them
  stays open. Not closable.
- No other open defect names compliance.
- Registration candidates: B1 if shipped as-is; W1.

## Devel verification still owed (after the fixes, under its own go)

The design's list, plus:

1. After the upgrade, check whether `benchmark_profile` and `allowInsecure`
   are still stored on the three accounts, and whether the INFO/WARN
   lines appear (settles B2).
2. Validate Connection on wld01 by FQDN (dialog, accept, test passes,
   next cycle collects), then by IP. Record what the platform probe does
   with a name the certificate lacks, and confirm collection succeeds by
   IP once the certificate is trusted (settles B1's wording).
3. Before the upgrade, confirm no two accounts differ only in
   `benchmark_profile` or `allowInsecure` for the same vCenter: the
   uniqueness tuple shrinks to `vcenter_host`.
