# synology SDK adapter — build 22 review (WARNING/NIT closeout on build 21)

**Reviewer:** `sdk-adapter-reviewer` · **Date:** 2026-06-30
**Adapter:** `content/sdk-adapters/synology` (build 21 → 22, local only — not committed/tagged)
**Verdict:** APPROVE (0 BLOCKING / 0 WARNING / 0 NIT)
**Predecessor:** `context/reviews/synology-build-21.md` (APPROVE; this build closes its
1 WARNING + 2 NITs).

## Delta reviewed (21 → 22)

Focused. Only the three closeout items moved; the build-21 explicit-credentials surface is
otherwise unchanged.

- **WARNING (silent localhost misconfig) — CLOSED.** New
  `SynologyConfig.suiteApiHostIsLoopback()` resolves `suiteApiHost()` via
  `InetAddress.getByName(h).isLoopbackAddress()` (catches `127.x` / `::1`, and blank /
  malformed / literal-`localhost` URLs that collapse to the `localhost` default); an
  unresolvable host is treated loopback **only** for the literal `localhost` default,
  otherwise left to the explicit path to surface. `SynologyAdapter`'s explicit branch now
  emits a distinct `logWarn` directing the operator to the PRIMARY/analytics FQDN when the
  resolved host is loopback — then **still takes the explicit path as configured** (no silent
  fallback, no behavior change to the transport selection).
- **NIT 2 — CLOSED.** `suiteHost` is hoisted to a `final` local before the `try`; the catch
  block reuses it (no recompute). The success-log and failure-log host strings are now
  provably identical.
- **NIT 3 — CLOSED.** A malformed URL still safe-degrades to `localhost`, but that case now
  trips `suiteApiHostIsLoopback()` → the new WARN, so it is visible rather than silently
  localhost'd.

## Claims check (independently re-run)

- `validate-sdk` → **OK** (confirmed).
- `build-sdk` → built `dist/vcfcf_sdk_synology_diskstation.1.0.0.22.pak` (confirmed).
- `pak-compare 22 vs 21` → **No structural divergences (0/0/0)** — confirms the fix is pure
  Java logic with **no descriptor change** (describe.xml/resources identical to 21).
- `pak-compare 22 vs 20` → **0 BLOCKING, 1 WARNING** (`[W1]` CredentialField count 5 vs 2 —
  the +3 optional fields, unchanged). Confirms the author's claim.

## Confirm items (all PASS)

1. **WARN firing condition is exact.** The `logWarn` is nested `if (explicitSuiteApi) { if
   (cfg.suiteApiHostIsLoopback()) … }`. It fires **only** when explicit creds are set AND the
   resolved host is loopback. A correctly-configured explicit path (real primary FQDN →
   `isLoopbackAddress()` false) does **not** WARN; the ambient/blank path takes the `else`
   branch (`explicitSuiteApi` false) and does **not** WARN. **No false WARN on primary-node
   installs.**
2. **`suiteApiHostIsLoopback()` cannot throw out of construction or the cycle.** It calls
   `suiteApiHost()` (internally guarded — never propagates) then `InetAddress.getByName(h)`,
   whose checked `UnknownHostException` is caught locally and resolved to a literal-`localhost`
   comparison. No exception escapes; and it is only invoked at construction time inside the
   existing `try/catch (RuntimeException)` regardless. Consistent with the build-21
   crash-the-cycle guarantee. (Note: `getByName` performs a DNS lookup at construction on the
   explicit path only — bounded, and construction already does Suite API network work; not a
   finding.)
3. **Ambient/blank path still byte-unchanged.** `suiteHost` is `null` on the ambient path
   (`suiteApiHost()`/`suiteApiHostIsLoopback()` never called); the `else` branch is exactly
   `SuiteApiStitcher.create(this, …)` + the additive `logInfo`, and the catch-block WARN
   message is unchanged on the non-explicit path. The new WARN lives entirely inside the
   explicit branch. No new regression surface for primary-node installs.
4. **Nothing else moved.** Diff is confined to `SynologyConfig.java` (new
   `suiteApiHostIsLoopback()` + the build-21 carry), `SynologyAdapter.java` (hoisted local +
   loopback WARN), and the metadata (`adapter.yaml` build 22, `CHANGELOG.md`, regenerated
   docs). `describe.xml` / `resources.properties` are identical to build 21 (pak-compare 22 vs
   21: no structural divergence).

## Registry check (`context/defects.md`)

- DEF-001 (synology, secrets-on-disk) — closed; not re-opened (new WARN logs the resolved host
  + user only, never a secret).
- DEF-003 (synology, `setRelationships` clobber) — closed; stitch-emission code untouched.
- No **open** defect affects `synology`.

## If shipped as-is
Primary-node operators: no change (ambient stitch + INFO line; the new WARN cannot fire on the
ambient path). Remote-collector operators with a correct primary FQDN: working Datastore
cross-link, no WARN. Remote-collector operators who set creds but leave the URL blank/malformed/
localhost: a clear, actionable WARN pointing them at the primary FQDN — the build-21 rough edge
is closed. Read-path safety and crash-the-cycle guarantees from build 21 are preserved.

**Live residual (unchanged from build 21, not a static finding):** the `cloudproxy_<uuid>`→403
vs explicit-account→200 behavior, and the framework strict-hostname/TOFU accepting the prod
primary cert, are provable only on a live CP deployment — for `qa-tester` / the orchestrator's
devel proof, not this static gate.
