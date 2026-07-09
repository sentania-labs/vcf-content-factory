# synology SDK adapter — build 21 review

**Reviewer:** `sdk-adapter-reviewer` · **Date:** 2026-06-30
**Adapter:** `content/sdk-adapters/synology` (build 20 → 21, local only — not committed/tagged)
**Verdict:** APPROVE (0 BLOCKING / 1 WARNING / 2 NIT)

## Change under review

Adapter-side wiring of **optional explicit Suite API credentials** so synology can
stitch VMWARE Datastores when deployed on a remote collector / Cloud Proxy (ambient
`cloudproxy_<uuid>` 403s reading the global VMWARE inventory). The framework path
(`SuiteApiStitcher.createExplicit`, strict-hostname + TOFU for non-loopback peers)
already exists (PR #30); this build is adapter wiring only.

Files: `describe.xml` (+3 `required="false"` CredentialFields), `resources/resources.properties`
(nameKeys 300-302), `SynologyConfig.java` (fields + `hasExplicitSuiteApi()` + `suiteApiHost()`
+ back-compat 5-arg ctor), `SynologyAdapter.java` (`buildConfig` reads fields; stitcher
construction branches ambient vs explicit), `adapter.yaml` build_number 21, `CHANGELOG.md`.

## Claims check (independently re-run)

- `validate-sdk content/sdk-adapters/synology` → **OK** (confirmed).
- `build-sdk` → **built `dist/vcfcf_sdk_synology_diskstation.1.0.0.21.pak`** (confirmed).
- `pak-compare 1.0.0.21 vs 1.0.0.20` → **0 BLOCKING, 1 WARNING** (`[W1]` CredentialField
  count factory=5 reference=2 — exactly the +3 new optional fields; ResourceKinds /
  ResourceIdentifiers unchanged). Confirms the author's claim and confirms the structural
  delta is the credential surface only.

## Registry check (`knowledge/context/defects.md`)

- **DEF-001** (synology, secrets-on-disk) — **closed** (build 19). Re-verified not
  re-opened: the new code logs principal/host/path only; no secret on any throw/log path.
- **DEF-003** (synology, `setRelationships` clobber) — **closed** (build 16, devel-proven).
  Untouched by this build (stitch emission code unchanged).
- No **open** defect affects `synology`.

## Gating items

### 1. No primary-node regression — PASS
With all three fields blank, `hasExplicitSuiteApi()` returns false (gate = `vrops_username`
**AND** `vrops_password` both non-blank; URL deliberately excluded). The else-branch calls
`SuiteApiStitcher.create(this, componentLogger(...))` — byte-identical to build 20 — plus a
single additive `logInfo` line (the only permitted addition). The catch-block WARN message
on the non-explicit path is unchanged (`"(remote collector without maintenanceuser.properties?)"`).
Gate cannot trip on a primary install unless an operator fills in both credential fields.
New fields are `CredentialField`s inside `CredentialKind`, **not** `ResourceIdentifier`s —
instance uniqueness is unaffected (describe.xml identifiers unchanged; pak-compare confirms).

### 2. Explicit-path correctness — PASS (live residual noted)
When the gate is true: `createExplicit(this, logger, suiteApiHost(), cfg.suiteApiUser,
cfg.suiteApiPassword)` — signature matches the framework
(`createExplicit(VcfCfAdapter<?>, Logger, String host, String user, String pass)`).
`suiteApiHost()` parsing is sane: `URI`-parses `https://fqdn/suite-api`, bare host,
`host:port`, and trailing-slash forms (falls back to a manual scheme/path/port strip if
`URI.create` throws — and that throw is caught internally, so the parser never propagates).
The framework routes the non-loopback explicit peer through `openPlatformConnection` with the
platform `CustomSSLSocketFactory` (TOFU) + **JDK strict hostname verifier**
(`SuiteApiStitchClient` lines 323-328) — matches design §0.1 Q2 / spec 20 §4.
**Live-only:** that the explicit account actually returns 200 (vs ambient 403) and that the
strict verifier accepts the prod primary cert is provable only on a live CP deployment.

### 3. Security — PASS
`vrops_password` is `password="true"` (masked). The startup `logInfo` logs `path + host +
user` only. Construction does no network/auth (auth deferred to collect), so a
construction-time exception cannot carry the password. Framework contract confirms password
is never logged (`SuiteApiStitchClient` line 126; logs principal/endpoint only at
lines 283-285 / 307-309 / 516-529 — password appears only in the transmitted request body).

### 4. Optionality / back-compat — PASS
5-arg ctor delegates to 8-arg with `null, null, null`; no other `SynologyConfig(` callers
exist (only `buildConfig`, now 8-arg); no test directory. `required="false"` is truly
optional — no validation forces the fields (validate-sdk green with them absent).

### 5. Crash-the-cycle / stitch corruption — PASS
Construction is wrapped in `try { … } catch (RuntimeException e)` → stitcher null, WARN,
all 25 resources still collect. Collect-time `SynologyStitcher.loadDatastores()` (unchanged)
catches `Exception`, WARNs, and degrades to an empty index — a malformed URL, unresolvable
host, or explicit-creds auth failure DEGRADES, never throws out of the cycle. The explicit
path changes only *which credentials/host* the client uses, not the call path or the
ResourceKey construction (uniqueness flags still read from source `id[2]`, unchanged) — no
stitch corruption introduced.

## Findings

### WARNING
- **[SynologyConfig.java:`suiteApiHost()` / SynologyAdapter.java:~150]** spec 20 §4 Q2b /
  design §0.1 Q2 — the gate is `user && pass` with URL excluded, and `suiteApiHost()`
  defaults a blank/garbage URL to `"localhost"`. So the one always-wrong combination
  (explicit creds set, URL blank → explicit creds aimed at `localhost`-on-collector, which
  serves no global VMWARE inventory) is taken **silently as a valid explicit path**. It
  degrades safely (loadDatastores swallows the 403) and the startup `logInfo` does print
  `-> localhost`, so signal exists — but it is INFO-level and easy to miss, and it is
  precisely the sharp edge the spec calls out. **Smallest fix:** when `hasExplicitSuiteApi()`
  is true but `suiteApiHost()` resolves to a loopback/`localhost` value, emit a distinct WARN
  ("explicit Suite API creds set but URL resolves to localhost — point vrops_url at the
  primary/analytics FQDN"). Non-blocking: safe degrade + existing log trail.

### NIT
- **[SynologyAdapter.java catch block]** `cfg.suiteApiHost()` is recomputed in the catch
  branch (already computed as `suiteHost` in the try). Reuse the local to avoid a redundant
  parse and keep the success/failure host strings provably identical.
- **[SynologyConfig.java:`suiteApiHost()`]** silently mapping an unparseable URL to
  `"localhost"` couples to the WARNING above; if the WARNING fix lands, consider returning the
  raw/empty value so the loopback-detection branch can flag it rather than masking it.

## If shipped as-is
A primary-node operator sees no change (byte-identical ambient stitch + one extra INFO line).
A remote-collector operator who fills in URL + username + password gets a working Datastore
cross-link for the first time. The only rough edge: an operator who supplies username +
password but forgets the URL gets a still-broken stitch that *looks* configured — it degrades
safely and is visible in the log, but is not called out as the misconfiguration it is.
