# SuiteApiStitcher loopback TLS + auth — spec question for the cleanup

**Status:** DECIDED → **in implementation** (briefed to `tooling` 2026-06-30; `framework-reviewer`
gate to follow). Chosen fix: **Option 2 via a `VcfCfAdapter` shim helper.** Prod cert will **not** be
changed (S1 declined), so we go straight to the code fix.
**Date:** 2026-06-29 (spec §5 landed); 2026-06-30 (root-cause correction + decision)

## 0. Decision & corrected root cause (2026-06-30)

**Corrected root cause — it is NOT CA trust, it is hostname verification.** The framework *already*
uses a trust-all `insecureSslContext()` for Suite API calls, so CA validation is already bypassed
(that is why devel works at all — its cert is issued by a non-public cluster CA). The real gap:
`java.net.http.HttpClient` performs **hostname verification** against the cert SAN *independently of
the trust manager*, and **cannot accept a custom `HostnameVerifier`**. Prod's operator-replaced
org-CA cert has no `localhost` SAN → the loopback call fails `certificate_unknown(46)`. Both the
earlier draft below and cleanroom §5's "relax loopback trust" framing under-described this: trust-all
is present and insufficient; the **hostname-verifier half is what regressed.**

**Why it regressed (the layering).** `AdapterBase` provides raw TLS *primitives*
(`getConnection(url, HostnameVerifier)`, `getVerifier()`, `getSocketFactory()`). The old
`UnlicensedAdapter` (aria-ops-core / BlueMedora) wrapped them into a finished, injected
`SuiteAPIClient` that used `getConnection(url, getVerifier())` — carrying **both** the platform trust
manager AND the platform hostname verifier. The v2 rehome deliberately dropped `UnlicensedAdapter`
for bare `AdapterBase`, so we lost the finished client and re-assembled our own
(`SuiteApiStitchClient`) on `java.net.http.HttpClient` + hand-rolled trust-all — which kept the CA
half and dropped the verifier half.

**Decision — Option 2, in the shim.** Our framework base class **`VcfCfAdapter`** (Layer 1; the
"vcfcf-base", our analog of `UnlicensedAdapter`) already polishes `AdapterBase` primitives into shim
helpers (`getPlatformSslContext()`). Add the missing one: `openPlatformConnection(String url)`, and
switch `SuiteApiStitchClient`'s loopback hop to consume it. This restores SDK parity, keeps the polish
in one place every pak inherits, and **stops violating our own cert-item rule** (which forbids
trust-all as the default Suite API path). `getPlatformSslContext()` alone does NOT fix it — it
polishes trust only, and `java.net.http` still strict-checks the hostname; the `URLConnection` path is
required because it is the only one that carries the hostname verifier. Explicit-remote path stays strict.

> **CORRECTION (2026-06-30, post-review — supersedes the "Noop-class / platform trust manager"
> framing above and in spec §5).** `AdapterBase.getConnection(url, HostnameVerifier)` is
> **package-private** (javap-confirmed) — not callable from `com.vcfcf.adapter` — so the shim must
> replicate it. The decisive authority is **`lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`**
> (live- + javap-confirmed): the accept/TOFU-surviving behavior lives in the platform
> **`CustomSSLSocketFactory` returned by `getSocketFactory()`**, NOT in `getAdapterTrustManager()` —
> which is the **strict TOFU `CustomTrustManager` that throws PKIX** for any cert not already trusted
> (incl. the platform's own localhost cert and the prod org-CA cert). So `openPlatformConnection()`
> MUST be:
> ```
> https.setSSLSocketFactory(getSocketFactory());   // platform CustomSSLSocketFactory — TOFU-surviving, cert-item compliant
> https.setHostnameVerifier((h, s) -> true);        // safe: connection already gated to a resolved loopback peer
> ```
> Do **not** hand-build an `SSLContext` from `getAdapterTrustManager()` (the first implementation did,
> and the review BLOCKED it — it would swap `certificate_unknown(46)` for a PKIX/CA failure). The
> all-true verifier is preferred over `getVerifier()`: `getVerifier()` permissiveness is a live-only
> unknown, and accepting any hostname on a resolved-loopback peer is strictly safe.

## 0.1 Scope expansion (2026-06-30, post-Codex P2 on PR #30) — unify BOTH Suite API paths on TOFU

Codex P2 on PR #30: `openPlatformConnection()` was **public and unconditionally** disabled hostname
verification (the loopback assumption lived only in javadoc + the caller's `isLoopbackUrl` gate). A
future/remote caller could leak platform credentials over a relaxed TLS connection to a non-loopback
host. Valid — and it surfaced the deeper "needle": the framework Suite API transport runs against a
**localhost** endpoint on the primary node *and* a **Cloud Proxy / remote** endpoint off-primary, and
the original fix only addressed the loopback half. The explicit/remote path was still on
`java.net.http.HttpClient` + trust-all `SSLContext`.

**Decision (SME): fix both — shipping the guard without the CP path "doesn't materially improve the
product."** The reference-correct, zero-CA-store mechanism is the platform **`getSocketFactory()`
`CustomSSLSocketFactory` (TOFU)** — the same one every BlueMedora/native pak and the OG `SuiteAPIClient`
use for all outbound HTTPS (`lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`; spec §20:304 "the
platform supplies the trust store; the adapter requests it"). TOFU is a *third* option between
trust-all and an adapter-managed CA store: the platform owns the store and the first-use registration.

**Unified posture — one helper, peer-aware, for both Suite API paths:**

| Peer | Trust (CA) | Hostname |
|---|---|---|
| **localhost** (ambient maint-user) | `getSocketFactory()` TOFU | relaxed `(h,s)->true` (cert may lack `localhost` SAN) |
| **CP / remote** (explicit creds) | `getSocketFactory()` TOFU | **strict** (JDK default — do NOT relax) |

- `openPlatformConnection()` becomes **self-gating**: resolves the peer, relaxes the verifier ONLY when
  `isLoopbackAddress()`, strict otherwise, **fail-closed** on an unresolvable host. Closes the P2.
- `SuiteApiStitchClient` routes **both** ambient and explicit paths through `openPlatformConnection`;
  the `java.net.http.HttpClient` + `insecureSslContext()` Suite API transport is **retired entirely**.
  Ambient-vs-explicit now differs only in **credentials**, not transport. No trust-all anywhere in the
  Suite API path; no adapter-managed CA store.

**Structural root cause (spec §5):** reference MPs (mongodb) **do not re-implement the Suite API
transport** — they consume the **SDK-injected `SuiteAPIClient`**, so the platform owns loopback trust
(`Noop`-class) and auth (ambient-on-primary / explicit-off-primary). Framework v2 chose to
re-implement the transport, which is the *sole* reason it inherited a cert/auth problem the reference
clients structurally never face. The fix is **parity with the SDK contract we replaced**, not novel
policy. (An alternative — revert to the SDK-injected client — is out of scope here; this spec assumes
we keep the re-implementation and match its two contracts.)
**Component:** `vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/SuiteApiStitcher.java`
(the shared framework Suite API client; bundled into the sdk-buildkit, compiled into every Tier 2 pak).
**Scope:** framework-wide — affects **every stitching pak** (synology, compliance, vcommunity, unifi), not synology alone.
**Trigger:** synology cross-MP datastore stitch produces zero relationships on prod while working on devel.

---

## 1. What we observed (empirical, ground truth)

Synology iSCSI-LUN↔Datastore and NFS↔Datastore cross-links form on **devel** and **not on prod**.
The pak binaries are **byte-identical** across the two instances (same sha256 jar, describe.xml,
and icon SVGs), so this is **not** a code/version/stale-build difference. Both instances are
3-vCenter. The difference is entirely in how the framework's loopback Suite API call behaves
against each appliance's TLS/auth posture.

The stitch's datastore load (`SynologyStitcher.loadDatastores` →
`SuiteApiStitcher.get("/api/resources?adapterKind=VMWARE&resourceKind=Datastore…")`) fails
**two different ways** depending on where the adapter runs:

| Where the adapter runs | Suite API result | Cross-link |
|---|---|---|
| Prod **remote collector** (`…-collector`, original placement) | HTTP **403** | 0 datastores, 0 matches |
| Prod **primary node** (`vcf-lab-operations`, after re-home) | TLS **`certificate_unknown(46)`** | 0 datastores, 0 matches |
| **Devel** single node | succeeds | links form ✅ |

Both failures are in the framework client. The 403 is an authorization-scope problem on the
remote collector's ambient maintenance user; the TLS alert is a trust problem on the primary node.

## 2. Root cause of the TLS failure — why devel works without any fix

`localhost/suite-api` presents a **different certificate** on each node:

| | Devel (works) | Prod primary (fails) |
|---|---|---|
| Subject CN | `VCFOps-slice-1` | `vcf-lab-operations.int.sentania.net` |
| Issuer | `VCFOps-cluster-ca_…` (VCOps internal CA) | `sentania Lab Issuing 2` (org PKI) |
| SAN has `localhost` / `127.0.0.1` | **yes** | **no** (only the two FQDNs) |

- **Devel** runs the **stock VCFOps self-signed cert**: issued by the cluster CA that is already in
  the adapter-visible platform truststore, and its SAN includes `localhost`. The loopback call
  validates and the hostname matches → success. It works **by default**, not because of any fix.
- **Prod primary** runs an **operator-replaced, org-CA-signed cert**: issuer `sentania Lab Issuing 2`
  is **not in the adapter's truststore**, and the SAN has **no `localhost`**. The loopback
  `https://localhost/suite-api` call fails CA validation → `certificate_unknown(46)` (and would
  also fail hostname verification even if the CA were trusted).

**Replacing the VCOps cert with an org-CA cert is standard production practice.** So this is a real,
broad product defect: any customer who installs their own cert breaks every stitching pak's Suite
API call the same way. Devel is green only because it never left the stock cert.

## 3. Root cause of the 403 — remote-collector ambient auth

Synology builds its client via `SuiteApiStitcher.create()` — the **ambient localhost path** (reads
`maintenanceuser.properties`, targets `https://localhost/suite-api` as the maintenance user). No
explicit-credential option is wired into the adapter config. On a **remote collector**, the
maintenance user authenticates (we get 403, not 401) but is **not authorized** to read cross-adapter
VMWARE resources from that node's suite-api. On the primary/analytics node that same user reads
VMWARE fine (proven on devel).

## 4. The spec questions (what the cleanup must decide)

**Q1 — Loopback TLS trust.** Should the framework's Suite API call to `localhost/suite-api` perform
strict CA + hostname validation at all?
- It is a **same-appliance loopback** call (127.0.0.1), not a network-exposed path → no meaningful
  MITM exposure.
- "Trust the platform truststore" alone does **not** fix it: the operator's issuing CA may not be
  imported there, and the missing-`localhost`-SAN problem remains.
- **ANSWERED by cleanroom spec `20-suiteapi-client-behavioral-contract.md` §5.** Reference MPs
  (mongodb) never build their own HTTPS client to `localhost/suite-api` — they consume the
  **SDK-injected `SuiteAPIClient`**, whose loopback hop runs a **platform-managed / `Noop`-class
  trust posture** (`vrops-trustmanager`'s `NoopTrustManager` "accepts everything";
  `getAdapterTrustManager()`/`getVerifier()` API surface). There is **no CA/hostname check on the
  loopback hop to fail** — which is exactly why the reference stitch works under both the stock
  cluster-CA cert (devel) and an operator-replaced org-CA cert with no `localhost` SAN (prod).
  Relaxing loopback TLS in `SuiteApiStitcher` therefore **restores the SDK contract we replaced —
  parity, not a factory-invented security regression.**
- **Implementation (per spec §5, two corrections to the earlier draft):**
  1. **Gate on the resolved peer being a loopback address** (`InetAddress.isLoopbackAddress()` /
     `127.0.0.0/8`), **NOT** the literal string `"localhost"` — the string is operator-controllable
     via resolver / `/etc/hosts`, so trust-all keyed on the name would trust-all a redirectable host.
  2. Build the relaxed posture on a **separate `SSLContext` object** so it cannot leak to the
     explicit/remote-host path, which stays strict. Log one line noting loopback-trust was applied.

**Q2 — Auth that works off the primary node.** Two sub-options, not mutually exclusive:
- (a) **Document/require primary-node placement** for stitching adapters (simplest; the maintenance
  user reads VMWARE there). Cheap, but a deployment constraint, and silently wrong if violated.
- (b) **Wire the explicit-credentials path** (`SuiteApiStitcher.explicitCredentials(host, user, pass)`,
  already in the framework) into adapter config so a real read-capable Suite API account is used
  regardless of collector. Robust on remote collectors; costs a config surface + a credential to manage.
- **ANSWERED by spec §5 — with a sharp edge the earlier draft missed.** The 403 is a **platform
  invariant, not a framework defect**: the ambient `maintenanceuser`/localhost mechanism is
  **appliance-only**, and the SDK provides **no forwarding from a collector to the primary**. The
  critical correction: **explicit credentials only fix the collector case if `host` is the
  primary/analytics FQDN.** Explicit creds pointed at `localhost`-on-collector **still read nothing**,
  because the global VMWARE inventory is not served on the collector at all. So (b) is "explicit
  creds → **primary host**," never "explicit creds → localhost."
- **Proposed answer:** ship (a) as the documented default now; offer (b) as opt-in config **whose
  URL must target the primary/analytics Suite API**, for remote-collector deployments.

**Q3 — Fail loud, not silent.** Today a Suite API failure yields an empty datastore index and a
single WARN, and the cycle reports "0 datastores loaded" at INFO — easy to miss; the stitch looks
healthy. Should a Suite-API-load failure surface on the adapter instance (e.g. a collection warning
/ instance health badge) so an admin sees "stitch degraded: cannot read VMWARE resources"?
- **Proposed answer:** yes — at minimum a distinct, actionable WARN naming the cause (403 vs TLS),
  and consider surfacing it on the instance status. Silent-degrade is how this hid.

**Q4 — Generality.** Confirm the fix lands in the **framework** (one place) and not per-pak, so all
four stitching paks inherit it. (They compile the framework source from the buildkit; see §6.)

## 5. Recommended resolution (subject to sign-off on §4 questions)

1. **Loopback insecure (restores SDK parity):** in `SuiteApiStitcher`, when the **resolved peer is a
   loopback address** (`InetAddress.isLoopbackAddress()` / `127.0.0.0/8` — *not* the string
   `"localhost"`), build the HTTPS client on a **separate `SSLContext`** with trust-all +
   no-hostname-verify, and emit a one-line INFO/WARN noting loopback-trust was used. (Answers Q1; per
   spec §5 this matches the SDK-injected client's `Noop`-class loopback trust — parity, not new policy.)
2. **Keep explicit-credential path strict**, on its own `SSLContext`, and expose it as opt-in adapter
   config — **its URL must target the primary/analytics Suite API**, not localhost-on-collector.
   (Answers Q2b.)
3. **Document primary-node placement** as the default for stitching adapters. (Answers Q2a.)
4. **Distinct, actionable failure logging** for Suite API load failures, by cause. (Answers Q3 —
   our policy choice; not constrained by the spec.)

This clears `certificate_unknown(46)`; with the adapter on the primary node the maintenance user
reads VMWARE → the synology cross-link forms. Compliance/vcommunity/unifi inherit the same fix.

## 6. Propagation / rollout

Framework code is single-source in the factory and delivered to paks via the versioned
**sdk-buildkit** (paks pin the floating `sdk-buildkit-v1` and pull it at CI time; they do not vendor
the framework). So the rollout is:

`tooling` fixes `SuiteApiStitcher` → **`framework-reviewer`** gate (blanket, RULE-013) → bump
`BUILDKIT_VERSION`, rebuild + **publish** the `sdk-buildkit-v1` release → re-tag each affected pak
(`v*`) so its CI recompiles against the fixed framework. An already-released pak does **not** get the
fix until it is re-tagged (the kit is pulled at build time, not runtime).

## 7. Codify alongside the fix

- **Lesson:** *loopback Suite API must not strict-validate the platform cert* — production appliances
  routinely carry an operator-replaced, org-CA cert with no `localhost` SAN; devel's stock
  self-signed cert hides this. Generalizes to any framework loopback HTTPS call.
- **Lesson (companion):** *ambient maintenance-user Suite API reads are authorized on the
  primary/analytics node but 403 on remote collectors* — stitching adapters must account for collector
  placement or use explicit credentials.

## 8. References

- **`specs/20-suiteapi-client-behavioral-contract.md` §5** — the authoritative answer to Q1/Q2
  (reference-MP TLS/auth posture; loopback-peer gating caveat; explicit-creds-must-target-primary).
  §1–§4 give the token-lifecycle, retry, cancellation, and remote-collector contracts the
  re-implemented transport must match.
- `context/investigations/recon_log.md` — 2026-06-29 synology prod recon (all four passes:
  version, behavioral fingerprint, jar bytecode, adapter-log 403, re-home → TLS, cert comparison).
- `vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/SuiteApiStitcher.java`
  — `create()` (ambient localhost) vs `explicitCredentials(host,user,pass)`.
- `content/sdk-adapters/synology/src/com/vcfcf/adapters/synology/SynologyStitcher.java` —
  `loadDatastores()`, `SuiteApiDatastoreBridge`.
- `vcfops_managementpacks/buildkit.py` — buildkit assembly; `content/sdk-adapters/synology/.github/workflows/build-pak-on-tag.yml`
  — pak CI pulls `sdk-buildkit-v1`.
- Feedback queue: untrusted-SSL-cert item (this is its framework-side resolution).
