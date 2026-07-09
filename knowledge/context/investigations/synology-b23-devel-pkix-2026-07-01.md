# Synology build-23 DEVEL install — root-cause of PKIX stitch failure + zero-INFO

**Date:** 2026-07-01
**Target:** `vcf-lab-operations-devel.int.sentania.net` (9.0.2, single analytics node)
**Adapter instance:** SynologyAdapter, instanceId `5402`, adapter id `816c72ef-84b2-4caf-848c-4b09a6517648`
**Log:** `/usr/lib/vmware-vcops/user/log/adapters/SynologyAdapter/SynologyAdapter_5402.log`
**Posture:** read-mostly. One authorized, reversible change to the collector log level
(record + restore); nothing else touched; nothing on prod.
**Access:** key-based root SSH (BatchMode), `cat`/`grep`/`stat`/`ls`/`ps`/`date` reads.

---

## TL;DR verdict

| Anomaly | Verdict | Owning layer |
|---|---|---|
| `loadDatastores` PKIX every cycle | **REGRESSION at build 19→23** | The **TLS/TOFU transport rework** (PRs #29/#30 — `VcfCfAdapter.openPlatformConnection` / `getSocketFactory()`), **not** this session's 3 diffs |
| Zero INFO from pid 6166 | **Log-level reset by the pak upgrade** | Install-time per-adapter-instance log level reverted to the WARN default; orthogonal to all code diffs |

**This session's three staged diffs — identity fix (`AmbientCredential` automation
preference), additive-foreign verb (`RelationshipBuilder`), version guardrail — are NOT
implicated in either anomaly.** The PKIX failure occurs at the TLS handshake of the very
first Suite API call (`token/acquire`), which is upstream of and independent from which
credential file is read; the diffs do not touch `openPlatformConnection`, `getSocketFactory()`,
or any SSL path.

---

## Q1 — Was `loadDatastores` failing BEFORE the upgrade? **NO. Pre-upgrade build 19 succeeded every cycle. This is a regression, not pre-existing.**

The active log `SynologyAdapter_5402.log` spans BOTH process eras (instanceId `5402` is
stable across the upgrade; the collector JVM pid changes):

| Process | Era | Window | Level histogram |
|---|---|---|---|
| **pid 6387** | pre-upgrade (build 19) | 2026-06-26T21:03 → **2026-07-01T17:00:14** | **5437 INFO**, 1 WARN |
| **pid 6166** | post-upgrade (build 23) | 2026-07-01T22:22:23 → (ongoing) | 0 INFO, 4 NOTICE, 4 WARN |

Build 19 (pid 6387) loaded datastores and formed cross-links **successfully and continuously**
right up to the upgrade:

```
2026-07-01T16:34:16.681Z INFO  ... SynologyAdapter.logInfo - Datastore cross-link: 10 datastores loaded, 2 LUN matches, 3 NFS matches
2026-07-01T16:34:16.681Z INFO  ... SynologyAdapter.logInfo - Relationships built: internal World>Diskstation>Pool>Volume>{LUN,NFS,SSDCache,Disk} tree + Datastore cross-link
...  (repeats every ~5 min) ...
2026-07-01T17:00:14.411Z INFO  ... Datastore cross-link: 10 datastores loaded, 2 LUN matches, 3 NFS matches   <-- LAST successful stitch
```

The **only** WARN in build 19's entire 5-day run was one transient HTTP/2 artifact, **not** a
cert failure:

```
2026-06-28T14:51:31.542Z WARN  ... SynologyStitcher.loadDatastores - VMWARE Datastore load failed: /127.0.0.1:52524: GOAWAY received
```

`GOAWAY` is an HTTP/2 frame — build 19 used `java.net.http.HttpClient` (HTTP/2) with a
trust-all `insecureSslContext()`; there is **zero PKIX** anywhere in the build-19 era.

**Edge freshness:** the Datastore↔LUN/NFS edges currently intact were **last written by build 19
at 2026-07-01T17:00:14** (the last successful "Datastore cross-link … loaded" line). The upgrade
process (pid 6166) started collecting at 22:22 and has **never** succeeded a `loadDatastores`,
so it cannot have refreshed them. The intact edges are **stale carryover** (~5h old at cutover),
consistent with the task's "possibly stale carryover" note.

---

## Q2 — Why PKIX fails and why TOFU acceptance never sticks

### The per-cycle failure sequence (adapter log + collector.log, correlated)

Every 5-minute cycle, pid 6166 produces exactly this in the adapter log:

```
2026-07-01T22:22:23.412Z NOTICE ... com.integrien.alive.common.adapter3.CustomTrustManager.handleUnknownCertificate - Initiating non-disruptive certificate handling for adapter: 816c72ef-...
2026-07-01T22:22:25.464Z WARN   ... com.vcfcf.adapters.synology.SynologyStitcher.loadDatastores - SynologyStitcher: VMWARE Datastore load failed: PKIX path building failed: sun.security.provider.certpath.SunCertPathBuilderException: unable to find valid certification path to requested target
```

The **platform side** of that same flow is in `collector.log` — and it is **failing to persist**:

```
2026-07-01T22:47:47.687Z NOTICE ... NonDisruptiveCertificateHandler.handleUnknownCertificate - Starting certificate renewal for the adapter '816c72ef-...'
2026-07-01T22:47:49.346Z ERROR  ... NonDisruptiveCertificateHandler.createAdapterCertificateRenewalConfig - Adapter certificate renewal url set is empty. Adapter ID: 816c72ef-...
2026-07-01T22:47:49.346Z ERROR  ... NonDisruptiveCertificateHandler.handleUnknownCertificate - Failed to create the adapter certificate renewal configuration.
```
(Same triplet repeats at 22:22, 22:27, 22:32, 22:37, 22:42, 22:47, 22:52, 22:57 — every cycle.)

### Mechanism

1. Build 23 routes the loopback Suite API call through
   `VcfCfAdapter.openPlatformConnection()` →
   `https.setSSLSocketFactory(getSocketFactory())` (the platform `CustomSSLSocketFactory`).
2. That factory delegates cert validation to the platform's strict **TOFU `CustomTrustManager`**,
   which **throws** on any cert not already registered — including devel's own localhost cert —
   surfacing to our caller as `SSLHandshakeException: PKIX path building failed`. (This is exactly
   the failure mode documented in `lessons/suite-api-stitch-ssl-tofu-vs-java-http.md`.)
3. As a side effect it fires the platform's async `NonDisruptiveCertificateHandler` ("initiating
   non-disruptive certificate handling"). **That handler is the thing that is supposed to make the
   cert trusted for future cycles — and it errors out:** `createAdapterCertificateRenewalConfig`
   fails with **"Adapter certificate renewal url set is empty"** because our framework adapter's
   describe/definition declares no certificate-renewal URL set (native adapters like vCenter do).
   Nothing is ever registered → the next cycle re-encounters an "unknown" cert → PKIX again,
   forever.

**So the `getSocketFactory()` "TOFU-survival intercept" the 2026-06-30 transport-rework correction
bet on does NOT function for a framework adapter.** The intercept *fires* (we see the platform
handler start) but it is an **async, best-effort cert-renewal** that requires an adapter-declared
renewal URL set; it is **not** a within-handshake register-and-retry. With no renewal URL, it can
never persist. Net outcome on devel: PKIX every cycle.

### Why devel worked under build 19 and breaks under build 23 (the cert did NOT change)

- Build 19: **trust-all `insecureSslContext()`** → `CustomTrustManager` is never consulted → no
  PKIX, no `NonDisruptiveCertificateHandler` invocation → datastores load. (The
  `suite-api-stitch-tls-auth-cleanup` design §2 hypothesis that "devel's stock cert is in the
  adapter truststore and validates by default" is **contradicted by live evidence** — devel's
  localhost cert is *not* accepted by the strict `CustomTrustManager`; build 19 only worked because
  it bypassed trust entirely.)
- Build 23: **`getSocketFactory()`/`CustomTrustManager` (TOFU)** → PKIX + failing renewal handler.

The regression is therefore a straight **trust-all → strict-TOFU swap** whose persistence
depends on a platform cert-renewal registration that framework adapters do not have. The devel
cert state did not change across the upgrade (build 19 read through it fine all afternoon).

---

## Q3 — The zero-INFO mystery: **log level reset to WARN by the pak upgrade**

### Root cause (structural)

The collector log config, unchanged since install:

```
/usr/lib/vmware-vcops/user/conf/collector/log4j2.properties  (mtime 2025-12-30, sha ea1e0945…)
  line 12: monitorInterval = 60
  line 21: rootLogger.level = WARN
```

There is **no logger entry for `com.vcfcf.*`** — our adapter's loggers inherit `rootLogger =
WARN`. Under WARN, all `logger.info(...)` calls (incl. `SynologyAdapter configured: …` and the
`SuiteApiStitchClient: credential mechanism=…` identity line) are filtered; only WARN + NOTICE
survive — exactly what pid 6166 emits. Meanwhile the *same instanceId 5402* emitted 5437 INFO
lines under build 19, from the *same* logger names — so the effective level for this adapter
instance was **INFO before the upgrade and WARN after**. In VCF Ops the per-adapter-instance log
level is a UI/server-side setting applied via the `AdapterContextSelector`; a **pak reinstall/
upgrade reverts it to the default**. The adapter is otherwise healthy (GREEN; `loadDatastores`
still *runs* every cycle — it just WARN-fails), so this is a level filter, not an unreached
code path.

### Live experiment (authorized, reversed)

To confirm and to try to capture the missing identity proof, I appended a temporary
`logger … com.vcfcf … = INFO` to `collector/log4j2.properties` (hot-reload via `monitorInterval=60`,
no restart), then restored the file byte-exact.

- **Result on Q3:** confirms the diagnosis is log-level (the file governs adapter logger levels;
  `com.vcfcf` had no override → WARN).
- **Identity line NOT captured:** the Synology adapter's *dedicated* log file stopped receiving
  lines from ~22:47 onward (last line 22:42:43), so the `credential mechanism=ambient …` line
  could not be observed there. **Collection was unaffected** — `collector.log` shows the synology
  cert-handling triplet continuing on a clean 5-min cadence (22:47:47, 22:52:53, 22:57:56), and
  all *other* adapters' dedicated logs (including the sibling `com.vcfcf` VCommunity/UniFi
  adapters) kept writing normally throughout, so the change caused no broad harm. The
  Synology-file quiet correlates in time with the reconfigure window but could not be attributed
  to it (VCommunity, same logger namespace, was unaffected); it self-heals on the next adapter/
  collector restart (out of scope here). The missing in-JVM identity proof
  (`principal=automationAdmin`) remains the one un-run step, blocked by the PKIX handshake being
  upstream anyway (see Q4).

### Recommended follow-up for Q3 (not done here — no persistent change intended)

Set the SynologyAdapter instance log level back to INFO via the product UI (Administration →
Support / adapter instance log settings), or add a persistent `logger.comvcfcf.name = com.vcfcf`
/ `.level = INFO` entry to the collector log config if INFO is desired as the framework default.
Either is a settings choice, not a code fix.

---

## Q4 — Verdict for the release train

**The PKIX/stitch regression is owned entirely by the earlier TLS/TOFU transport rework
(PRs #29/#30): `VcfCfAdapter.openPlatformConnection()` +
`SuiteApiStitchClient` switching from `java.net.http.HttpClient`/`insecureSslContext()` to
`URLConnection`/`getSocketFactory()`.** Evidence chain:

- The failing call path is the TLS handshake of `token/acquire` inside `openPlatformConnection`
  → `getSocketFactory()` → strict `CustomTrustManager` → PKIX. This code is 100% from the rework.
- The handshake fails **before** any credential is validated server-side (the username/password
  are in the request body, which is never sent once the handshake throws). Therefore the
  **identity fix (`AmbientCredential` automation-first) cannot affect PKIX** — it only changes
  *which* file supplies the credential *after* a successful handshake.
- The **additive-foreign verb** (`RelationshipBuilder`) runs only *after* `loadDatastores`
  returns matches; with zero datastores loaded it never executes. Not implicated.
- The **version guardrail** is a validate/version check with no runtime transport surface. Not
  implicated.
- Zero-INFO is an install-time settings reset, independent of all three diffs.

**Recommendation:** the three staged diffs are clear to proceed on their own merits; **but the
PKIX regression is a genuine, live-confirmed defect in the shipped transport layer and it will
also break prod** (prod's operator-replaced org-CA cert is even less likely to be TOFU-registered,
and the same "renewal url set is empty" handler failure applies). The prod install that is gated
on this answer should **not** proceed expecting the stitch to work: build 23's Suite API transport
does not read VMWARE datastores on either instance. The transport fix needs revisiting — the
`getSocketFactory()` TOFU-persist assumption is falsified; the paths that actually work are (a)
the build-19 `insecureSslContext()` trust-all for the loopback hop (per the standing lesson), or
(b) genuinely registering an adapter certificate-renewal URL set so the platform's non-disruptive
handler can persist the cert. This is a transport-layer decision, separate from the identity/verb
work.

---

## Cross-references / corrections to existing docs

- **`lessons/suite-api-stitch-ssl-tofu-vs-java-http.md` is VINDICATED by this live run.** Its
  generalizable rule ("`CustomTrustManager` always throws on first contact; for localhost Suite
  API use `insecureSslContext()`") predicted exactly what build 23 now does. The 2026-06-30
  correction in `designs/suite-api-stitcher-tls-auth-cleanup-v1.md` §0 (that `getSocketFactory()`
  carries a working TOFU-survival intercept) is **not supported by the evidence**: the intercept
  fires but the platform renewal step errors with "Adapter certificate renewal url set is empty"
  and never persists.
- New live fact for the transport spec: the platform's `NonDisruptiveCertificateHandler` requires
  an **adapter-declared certificate-renewal URL set**; framework (`com.vcfcf`) adapters declare
  none, so strict-TOFU on the loopback hop can never self-heal for them.

## Clean-up

- `collector/log4j2.properties` restored **byte-exact** (sha `ea1e0945…f5cef9`, == pre-change).
- No diag logger lines remain; on-box backup (`.explorer-bak-DELETE`) consumed by the restore `mv`.
- No on-box `/tmp` artifacts created. Nothing restarted. Prod untouched.
- Residual: SynologyAdapter's dedicated log file has been quiet since 22:42:43 (collection
  healthy per `collector.log`); it resumes on the next routine adapter/collector restart — no
  action taken (out of scope).
