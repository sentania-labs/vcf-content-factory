# SDK Adapter Review — compliance build 49

- **Adapter:** `content/sdk-adapters/compliance`
- **Build reviewed:** 49 (commit `eba91b2`) vs build 48 (`20b0fd8` = build 48 + CI-only commits)
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Verdict:** **CHANGES REQUESTED**
- **Findings:** 1 BLOCKING / 2 WARNING / 1 NIT
- **Date:** 2026-06-10

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean (compile) | **Confirmed by direct run.** `validate-sdk content/sdk-adapters/compliance` → "OK: … valid Tier 2 SDK adapter project", 10 source files compiled, 1 benign `-source 11` warning. The new framework SPI surface (`discoverOnCollect`, `enumerateResources`, `com.vcfcf.adapter.spi.ResourceSink`, `getPlatformSslContext`, `insecureSslContext`, `componentLogger`) all resolve against the framework jar — none stubbed in adapter source. |
| `build-sdk` reproduces | **Confirmed by direct run.** Built `vcfcf_sdk_compliance.1.0.0.49.pak` clean; adapter jar `vcfcf_compliance.jar` 75,079 bytes; `aria-ops-core` correctly omitted (v2 adapter); only `vcfcf-adapter-base.jar` in `lib/`. |
| pak-compare vs build 48 = 0/0/0 | **Confirmed by direct run.** `pak-compare 49 48` → "No structural divergences found. 0 BLOCKING, 0 WARNING, 0 INFO." describe.xml / profiles / content structurally identical 48→49 — consistent with `describe.xml` being untouched in the diff (which is itself load-bearing for the BLOCKING below). |
| Adapter clone tree clean after build | **Confirmed.** `git status` clean; the `REFERENCE.generated.md` / `CHANGELOG.generated.md` sidecars landed in the factory build dir (gitignored), not the clone. No hand-authored CHANGELOG/REFERENCE clobber. |
| Diff scope = the four named changes + version/docs | **Confirmed.** `git diff 48→49` touches exactly `ComplianceAdapter.java`, `VSphereClient.java`, `adapter.yaml` (48→49), `REFERENCE.md` (version string), `CHANGELOG.md`. No describe.xml, profile, or content change. |

## BLOCKING

### B1 — Change 2 (task #12) does NOT flip the SSL default; effective default is still trust-all, contradicting the documented "platform trust by default"

- **Where:** `ComplianceConfig.java:21`, `describe.xml:35-36`, `ComplianceAdapter.java:120,193` (`sslSocketFactoryFor`).
- **Authority:** skill § *Gaps — name them, never hide them* + `rules/no-fabricated-metrics.md` (the documented behavior must match the code's actual behavior); security-posture correctness.
- **What's wrong:** The CHANGELOG (1.0.0.49 §2), the `VSphereClient` ctor Javadoc, and `sslSocketFactoryFor`'s Javadoc all assert **"platform trust by default, `allowInsecure=true` as the opt-out."** The code does the opposite at the config layer:
  - `describe.xml:36` — `allowInsecure` identifier carries `default="true"` (unchanged this build; describe.xml is not in the diff).
  - `ComplianceConfig.java:21` — `this.allowInsecure = !"false".equalsIgnoreCase(allowInsecure);`. This is `true` for **everything except the literal string `"false"`** — `null` (absent field), `""`, `"0"`, `"no"`, `"off"` all parse to `allowInsecure = true` (insecure/trust-all).
  - `getIdentifier(resourceConfig, "allowInsecure")` returns `null` when the field is absent (every existing devel/prod instance). `!"false".equalsIgnoreCase(null)` = `!false` = **`true`**.
  - Net: `sslSocketFactoryFor` takes the `cfg.allowInsecure` branch → `insecureSslContext()` (trust-all) for any instance that has not *explicitly* set `allowInsecure=false`. The "secure default" never engages. Security is **opt-in**, not opt-out, and a fresh instance is insecure-by-default.
- **Why BLOCKING:** the build claims to deliver task #12 (secure-by-default vCenter SOAP TLS) and ships documentation asserting it; the code delivers the inverse. That is a fabricated/contradicted security claim, and the headline goal of the change is unmet. (It also means the brief's "default-flip deployment risk" is moot in the *opposite* direction — see the deployment note below.)
- **Smallest correct fix:** make the default strict. Either (a) flip `describe.xml` `allowInsecure` `default="false"` AND change the parse to default-strict on absent/blank, e.g. `this.allowInsecure = "true".equalsIgnoreCase(allowInsecure);` (null/blank/anything-not-"true" → `false` = strict); or (b) if Scott's intent really is "lab stays trust-all by default, security is opt-in," then correct all three docstrings + the CHANGELOG to say so plainly and drop the "platform trust by default / secure default" language — but that contradicts task #12's stated goal, so (a) is the expected fix. Either way the code and the prose must agree.

## WARNING

### W1 — Last-known-score staleness has no first-class world-level visibility; a host unreadable for weeks contributes full-weight to `avg_host_score` and the only signal is an indirect control count

- **Where:** `ComplianceAdapter.java:393-403` (world rollup), `741-755` (`applyLastKnownForUnreadableHost`).
- **Authority:** skill § *Unreadable is NOT compliant* (staleness must never be invisible; coverage must be surfaced every cycle).
- **What's right (verified, not BLOCKING):** never-read hosts are correctly excluded (`last == null` → return, no fold); only real scores enter the map (`put` gated on `cr.totalCount > 0`, line 703-710), so **no sentinel can be cached**; the denominator stays full; `total_unreadable_controls` *is* pushed every cycle (line 428) and rises when a host goes unreadable (`stats.unreadable += cr.unreadableCount` runs in both unreadable branches before the fold), so staleness is **not fully invisible**; each stale-contributing host emits a per-cycle INFO naming it. The cardinal "unreadable becomes a fresh pass" violation does **not** occur — hence WARNING, not BLOCKING.
- **What's wrong:** the *only* world-level staleness signal is `Summary|total_unreadable_controls` — a **control** count, not a host count, and it cannot distinguish "host unreadable but folding a stale score into the average" from "host unreadable and excluded (never-read)." An operator looking at `total_hosts` + `avg_host_score` cannot tell how many of the averaged hosts are fresh vs stale, nor for how long. A host blind for weeks silently holds its old score in the fleet average at full weight with no dedicated metric saying so. The author's restart caveat covers the cold-cache case but not steady-state staleness.
- **Smallest correct fix:** push a dedicated world metric every cycle, e.g. `Summary|hosts_scored_stale` (count of hosts whose `avg_host_score` contribution came from `lastKnownHostScore` this cycle) alongside the existing `scored`. Increment a `staleScored` counter in `applyLastKnownForUnreadableHost` and emit it unconditionally so an operator can see "N of M averaged hosts are stale." (Optionally also emit `hosts_unreadable` distinct from the control count.)

### W2 — `lastKnownHostScore.put(hostId, …)` is not null-guarded while the read side is; latent NPE inside the per-host loop with no per-host catch (crash-the-cycle)

- **Where:** `ComplianceAdapter.java:710` (write, unguarded) vs `743` (read, `hostId == null` guarded); loop `587-725` has **no per-host try/catch** and `collectHosts` declares `throws Exception`.
- **Authority:** skill § *Reflection-tolerant vim25 reads* / review dimension 3 — a single resource's defect must never abort the whole collection cycle.
- **What's wrong:** `applyLastKnownForUnreadableHost` defensively handles `hostId == null` (line 743), but the scored-path `lastKnownHostScore.put(hostId, cr.score)` does not. `ConcurrentHashMap.put(null, …)` throws NPE. Because the per-host loop body has no enclosing try/catch and `collectHosts` propagates, a single host with a null MOID would abort the entire cycle — every other host and the world rollup lost. Likelihood is low (`HostInfo` is only built with `ref.value` and only when `name != null`, so MOID is realistically non-null for any enumerated host), but the asymmetry is a defect this build introduced, and the loop's lack of per-host isolation makes its blast radius the whole cycle.
- **Smallest correct fix:** guard the write to match the read: `if (hostId != null) lastKnownHostScore.put(hostId, cr.score);`. (Independently, wrapping the per-host loop body in a per-host try/catch that logs-and-continues would harden dimension 3 generally, but that is pre-existing structure and out of this build's minimal scope — the guard is the in-scope fix.)

## NIT

### N1 — `lastKnownHostScore` never evicts hosts removed from inventory (slow unbounded growth)

- **Where:** `ComplianceAdapter.java:78-83` (map decl), `710` (put-only; no removal anywhere).
- A host permanently removed from vCenter leaves its entry in the map forever. In a stable fleet the map is bounded by host count, but across long-running collectors with host churn it grows monotonically. Trivial memory, but it is an unbounded-growth-across-cycles smell (review dimension 7). Optional: prune keys not seen in the current `getHosts()` set at end of `collectHosts`. Non-blocking.

## Hunts cleared (verified safe)

- **Discovery idempotency (task #19):** PASS. `worldResourceConfig()` (line 317-323) is a pure constant — `ResourceKey("Compliance World", "ComplianceWorld", ADAPTER_KIND)` + single `world_id=compliance_world` identifier, `isUnique=true`, no host/inventory input. The deleted `getDiscoverer()` called the *same* helper (`dr.addResource(worldResourceConfig())`), so the emitted ResourceConfig is byte-identical old-path vs new-path. Matches framework §22 recipe exactly (`discoverOnCollect() → true`, shared `enumerateResources(ResourceSink)` body, `getDiscoverer()` deleted). §22 states the platform de-dups by identifying identifiers, so re-enumerating the constant unique key every cycle re-registers rather than duplicates. **No duplicate world on devel/prod upgrade.**
- **Sentinel leak into the score cache:** PASS. `lastKnownHostScore.put` is gated on `cr.totalCount > 0` (line 703), so the `score=100` zero-divisor sentinel (totalCount==0 unreadable host) is never cached; only genuine (incl. genuine partial) scores enter the map.
- **Map key collision/leak across hosts:** PASS. Keyed by stable `hostInfo.moid` (= `ref.value`, the PropertyCollector object id), not the renameable display name. Same key used for cache, fold, and `stitcher.matchHost` — consistent.
- **Change 3 (shadow logger deletion):** PASS. `adapterLogger()` removed; `VSphereClient` / `SuiteApiStitcher` / `ComplianceStitcher` now take `componentLogger(Class)` (framework-provided, level-correct). The build-46 dead-logger footgun is removed by construction; no regression.
- **Per-host wire push unchanged:** PASS. The build-48 `totalCount>0` score gate in `pushComplianceViaClient` is untouched; task #16 only changes the *world rollup input*, not the per-host push (docstring updated to scope the v1 byte-identical claim — the build-48 NIT, addressed). pak-compare 0/0/0 corroborates.
- **Stitching identity:** PASS. `matchHost(hostName, hostId)` uses MOID, not bare display name; no foreign-resource join introduced or changed this build.
- **Redaction:** PASS. No new log line or exception in the diff emits password / token / credential. New lines emit hostname, score, connState, and the `allowInsecure` boolean only. `rules/no-secrets-on-disk.md` clean.

## Deployment note for the installer (per brief)

The brief's stated "default-flip deployment risk" does **not** materialize — because the default did not actually flip (finding B1). Existing devel/prod instances have no `allowInsecure` field → parse to `allowInsecure = true` → **trust-all, unchanged from build 48**. So build 49 will **not** break collection at upgrade on a self-signed lab vCenter. The catch is the inverse: the security improvement task #12 advertised is **not delivered** for any instance lacking an explicit `allowInsecure=false`, and a fresh instance is insecure-by-default. Once B1 is fixed (strict default), the brief's original risk becomes real and the installer guidance applies: at upgrade, any instance against a vCenter whose cert is not in the platform trust store must either import the cert or set `allowInsecure=true` explicitly, or collection will fail TLS validation. The failure on the strict path is loud and actionable (the `logWarn` in `sslSocketFactoryFor` names the remedy), but the upgrade runbook must call it out.

## If shipped as-is

An operator upgrading believes (from the CHANGELOG and adapter docs) that vCenter SOAP TLS is now validated against the platform trust store — but every existing instance, and every freshly-created instance, silently keeps trust-all unless someone explicitly typed `allowInsecure=false`. The advertised security hardening is absent and the documentation actively misrepresents the running posture. Separately, the new last-known-score world average is honest at the cardinal level (no fresh-pass for a blind host, never-read hosts excluded, no sentinel cached) but an operator cannot see, from the world metrics, how many averaged hosts are running on weeks-old stale scores — only an indirect control count hints at it.

## Verification artifacts

- `validate-sdk` (direct): OK, 10 sources compiled clean.
- `build-sdk` (direct): `dist/vcfcf_sdk_compliance.1.0.0.49.pak` built; adapter jar 75,079 bytes; lib = `vcfcf-adapter-base.jar` only.
- `pak-compare 49 vs 48` (direct): 0 BLOCKING / 0 WARNING / 0 INFO, "No structural divergences found."
- Adapter clone tree clean post-build; no doc-sidecar clobber.
- Framework SPI (`discoverOnCollect`/`enumerateResources`/`ResourceSink`/`getPlatformSslContext`/`insecureSslContext`/`componentLogger`) confirmed framework-provided, not stubbed in adapter src.
