# Compliance build 46 — wld01-esx04 host-scoped partial-collection regression (root cause)

**Date:** 2026-06-10
**Investigator:** api-explorer (VCF Ops specialist)
**Instance:** devel `vcf-lab-operations-devel.int.sentania.net` (VCF Ops 9.0.2.0)
**Pak under test:** compliance build 46 (framework v2, raw-SOAP `VSphereClient`)
**Posture:** strictly READ-ONLY. Root SSH (`sshpass`, key-auth) for `grep`/`ls`/`awk`
reads of `collector.log`; local read of the adapter source + canonical profile CSV.
No writes, restarts, or deletes on the appliance. Suite API token acquire was not
needed — the connection-state evidence was already conclusive in the collector log.
**Constraint honored:** the v2 host-walk INFO breadcrumbs are dark (known logging
defect). This verdict rests entirely on WARN/ERROR residue, the *absence* of specific
WARNs, code reading, channel arithmetic, and the native infra-health adapter's
per-host connection telemetry — **not** on the dark INFO lines.

---

## TL;DR / VERDICT

**Mechanism: host-state-triggered SILENT EMPTY-MAP on the advanced_setting channel.**
Not a channel-wide failure. Not an early-break. Not a timeout.

`vcf-lab-wld01-esx04` (`host-8024`) is intermittently **not-connected** to its vCenter
(`vcf-lab-vcenter-wld01`) — it is the *only* wld01 host the native VMware infra-health
adapter ever flags `isConnectedOrNotIssueCount=1`, and it does so on **every** cycle in
the regression window. When the host's vCenter link is down at read time,
`PropertyCollector` returns the host's `configManager` **without a live
`advancedOption` MoRef**. The adapter's `VSphereClient.getAdvancedSettings()` hits its
quiet guard:

```java
MoRef optMgr = getMoRefProperty(hostRef, "configManager.advancedOption");
if (optMgr == null) return result;   // <-- returns an EMPTY map, NO exception
```

`collectHosts()` therefore receives an **empty** advanced-settings map for esx04 — with
**no exception**, so the `catch` that would log `"Failed to read settings for ..."`
never fires (confirmed: 0 such WARNs in the log). In `ControlEvaluator.evaluateControls`,
every one of the **35 advanced_setting host controls** then hits `actual == null` and,
because **none** of the SCG-9.0 host advanced_setting controls carry an
"X or Undefined" / "Not Present" expected value, each one is **silently `continue`-d**
(line ~150) — excluded from pass, fail, total, AND unreadable. They simply vanish from
the denominator. This is the "~28 never-attempted" set.

The vim_property and esxcli channels degrade *visibly* on the same disconnected host:
the 3 `config.encryptionState.*` vim reads and all 5 esxcli reads fail and fold to the
explicit **UNREADABLE** sentinel (8 unreadable). The 6 cheaper vim reads
(`service_state:` TSM/TSM-SSH/snmpd/ntpd, `scalar:config.lockdownMode`,
`bool:config.firewall...`) still resolve from vCenter's cached host config → the
6 scored.

**The arithmetic closes exactly:**

| Channel (49 evaluable SCG-9 host ctrls) | Count | esx04 outcome under empty-adv-map |
|---|---|---|
| advanced_setting | 35 | **35 silently dropped** (no `allowsUndefined` matches → `continue`) |
| vim_property | 9 | 6 resolve (scored) + 3 `encryptionState` fail (unreadable) |
| esxcli | 5 | 5 fail (unreadable) |
| **observed** | | **total_count=6, unreadable=8, score=83.33 (5/6)** |

This reproduces the recon numbers byte-for-byte (score 83.33, pass 5, fail 1, total 6,
unreadable 8). v1 read esx04 fully because it tolerated the missing/partial advanced
config differently (or read at a moment the link was up); v2's silent empty-map guard
turns a transient host-link gap into a persistent 35-control denominator collapse.

---

## EVIDENCE

### E1 — esx04 is the connection-flap outlier (native infra-health adapter)

Every collection cycle, `com.vmware.adapter3.vmwareinfrahealth` logs ESXi issue counts
for all four wld01 hosts. esx04 is the **only** host that ever shows
`isConnectedOrNotIssueCount=1`, and it appears on the second log emission of *every*
cycle from 06:10Z onward (06:10, 06:15, 06:21, 06:26, 06:31, 06:36, 06:41, 06:46,
06:51, 06:56 …). esx01/02/03 are always `=0`.

```
…esx04…IssueCount{… isConnectedOrNotIssueCount=1 …}    <- every cycle, esx04 only
…esx03…IssueCount{… isConnectedOrNotIssueCount=0 …}    <- always clean
```

This is an independent, non-compliance source confirming esx04 has an intermittent
vCenter connection problem coincident with the regression window. (Baseline already
flagged esx04 as the cluster outlier — different lockdown-mode / log-level-global,
score 66.67 vs 61.90. The connection flap is the new, build-46-window factor.)

### E2 — the compliance adapter throws NO per-host exception on esx04 (silent path)

- Per-host WARNs `"Failed to read settings for vcf-lab-wld01-esx04"` and
  `"Failed to read vim properties for vcf-lab-wld01-esx04"`: **0 occurrences**
  in the 06:10–06:59Z window. These are `logWarn` calls that route through the
  framework base (NOT the dead helper-logger) — they WOULD appear if thrown.
  Their absence proves `getAdvancedSettings()` returned normally (empty map),
  it did not throw.
- No SOAP-fault / HTTP-500 / SSLHandshake / timeout WARN from the compliance walk
  (instance `(3240)` / `(3235)`) post-06:10. (The one `SSLHandshakeException` at
  06:05:26 is the *stitcher's* `fetchResources(HostSystem)` Suite-API load — a
  separate, transient concern, not the vCenter SOAP collection path.)

### E3 — world-level unreadable count is constant, not timing-jittery

The wld01 instance `(3240)` logs `Profile 'VMware_SCG_9.0' declares 25 vim_property
control instance(s) … could not read this cycle` on **every** cycle (constant 25);
the mgmt instance `(3235)` logs a constant 18. A timeout/batch-failure mode would
produce a *varying* count cycle to cycle. A constant count is the signature of a
**deterministic, host-state-driven** loss — esx04's encryptionState+esxcli controls
fail the same way every cycle because the host is in the same flapped state.

### E4 — no timeout pressure

Compliance cycle elapsed times are ~16–18 s (`TasksManager` Elapsed Time 16526 /
16819 msecs; SOAP read timeout is 120 s). The cycle is nowhere near a timeout bound.
The `vapi …/stats … Read timed out` lines belong to the **native** VMware adapter,
not compliance. The channel-wide-timeout hypothesis is **ruled out**.

### E5 — channel classification (canonical `profiles/canonical/scg_9.0.csv`)

74 HostSystem controls; 49 evaluable: 35 advanced_setting, 9 vim_property, 5 esxcli
(plus manual_audit/powercli_only which are never read). The 8 confirmed-unreadable
controls on esx04 map exactly to: 5 esxcli (disable-accounts-dcui, key-persistence,
log-filter, log-persistent, tls-ciphers) + 3 vim_property `config.encryptionState.*`
(secureboot-enforcement, tpm-configuration, tpm-trusted-binaries). The 6 scored map
to the 6 vim_property `service_state:` / `config.lockdownMode` / `config.firewall`
reads. The 35 advanced_setting controls are the dropped set. The 3 named
confirmed-missing controls in the brief — `esx.account-lockout-duration`,
`esx.ad-admin-group-name`, `esx.log-forwarding` — are **all advanced_setting**,
i.e. exactly the silently-dropped channel.

---

## CODE PATH (precise)

1. `ComplianceAdapter.collectHosts()` — per-host loop, **no early break**, each host
   independent. For esx04:
   - `advSettings = vsphere.getAdvancedSettings(hostInfo.moRef)` →
     `getMoRefProperty(hostRef,"configManager.advancedOption")` returns **null**
     (disconnected host has no live advancedOption MoRef) →
     `getAdvancedSettings` returns an **empty `HashMap`**, no throw
     (`VSphereClient` line ~301). The `try/catch` at ComplianceAdapter ~530 never
     trips → no WARN.
   - `evaluateVimForResource(...)` runs `readVimProperties` once; inside, each control
     is individually try/caught (so per-control failure → UNREADABLE, never aborts the
     batch). esx04's encryptionState vim reads + all esxcli reads → UNREADABLE (8);
     the service_state/lockdown/firewall reads resolve (6).
2. `ControlEvaluator.evaluateControls(advanced_setting, EMPTY_MAP, esx04)`:
   - For all 35 controls, `advancedSettings.get(param) == null`.
   - `allowsUndefined(expected)` is **false** for every SCG-9 host advanced_setting
     control → `continue` (line ~150). **Dropped: not pass, not fail, not total, not
     unreadable.** No log line.
3. `mergeResults(advCr, vimCr)` → total = 0 (adv) + 6 (vim) = **6**; unreadable =
   0 (adv) + 8 (vim) = **8**; score = 5/6 = 83.33.

The cardinal "unreadable is not compliant" rule is *technically* upheld for the vim/
esxcli channels, but the advanced_setting channel has a **third, worse outcome the
contract never intended: silent disappearance.** An empty advanced-settings map is
indistinguishable, in `evaluateControls`, from "every key legitimately absent" — and
absent-with-no-`allowsUndefined` means skip, not unreadable. So a whole-channel read
failure masquerades as "nothing to evaluate" instead of "could not read."

---

## WHAT BUILD 47 MUST CHANGE

The fix is to make the advanced_setting channel **fail loud and honest**, the same
way vim/esxcli already do — never silently drop a declared control because the
*transport* returned nothing.

1. **Distinguish "channel unreadable" from "key legitimately absent" in
   `getAdvancedSettings`.** Today both collapse to an empty map. The `optMgr == null`
   guard (host disconnected / no advancedOption MoRef) is a **read failure**, not an
   empty result. Signal it — either:
   - throw a checked exception from `getAdvancedSettings` when `optMgr == null`
     (so `collectHosts`' existing catch logs `"Failed to read settings for esx04"`
     and the host can be marked channel-unreadable), **or**
   - return a typed "unreadable" marker the evaluator can fold to UNREADABLE for
     every advanced_setting control (preferred — keeps the per-control coverage
     signal instead of zeroing the whole host).
2. **In `ControlEvaluator.evaluateControls`, when the advanced_setting map is
   known-unreadable (vs known-empty), count each control as UNREADABLE, not skip.**
   This restores denominator honesty: esx04 would then report total=6, unreadable=8+35
   = 43 — a loud "this host's advanced settings could not be read" — instead of a
   flattering score=83.33 on a 6-control denominator. (Matches the v1 "no control v1
   read should silently leave the denominator" hard bar.)
3. **Guard the connection-flap explicitly.** Before per-host evaluation, check the
   host's `runtime.connectionState` (`getRawPropertyElement(hostRef,
   "runtime.connectionState")` — one cheap RetrieveProperties). If it is
   `disconnected` / `notResponding`, mark the whole host channel-unreadable for the
   cycle (all 49 controls UNREADABLE) rather than scoring a partial subset. A flapping
   host should read as "coverage gap," never as a partial score.

Any one of (1)+(2) closes the silent-drop; (3) is the robust belt-and-suspenders that
also prevents a half-connected host from producing a misleadingly-high partial score.

### Is the dark INFO breadcrumb a blocker? No.

The verdict did **not** require the dark host-walk INFO lines. The WARN *absence*
(E2), the constant world unreadable count (E3), the channel arithmetic (E5), and the
native connection telemetry (E1) were sufficient. **However**, for build-47
verification (confirming the host actually flapped at each compliance read), the
minimal instrumentation that would have made this a 5-minute diagnosis instead of a
reconstruction is:

- **Promote two existing breadcrumbs from INFO to WARN-on-degradation in
  `collectHosts`:** when `advSettings.isEmpty()` for a host that returned hosts in the
  inventory walk, emit
  `logWarn("Host " + hostName + ": advanced settings map EMPTY (advancedOption MoRef "
  + "null — host likely disconnected); " + N + " advanced_setting controls excluded")`.
  This is a one-line guard on a value already in hand; it does not depend on the dead
  helper-logger because `logWarn` routes through the framework base.
- Independently, the dead-helper-logger fix tracked as a known defect would restore the
  `VSphereClient`/`EsxcliSoapClient` INFO host-walk breadcrumbs; with those, the
  per-host `RetrieveManagedMethodExecuter` failures on esx04 would be directly visible.
  But that is a *nice-to-have* for this class of bug, not a *blocker* — the degradation
  WARN above is the load-bearing instrumentation.

---

## Clean-up

Nothing created on the appliance. Read-only throughout (`grep`/`ls`/`awk` over logs).
No Suite API writes, no test objects. Clean-up verified: yes (nothing to remove).

---

*Captured by api-explorer. Read-only against VCF Ops devel. No writes performed.*
*Source read locally: `content/sdk-adapters/compliance/src/.../{ComplianceAdapter,*
*VSphereClient,EsxcliSoapClient,ControlEvaluator}.java`,*
*`profiles/canonical/scg_9.0.csv`. Recon basis:*
*`knowledge/context/investigations/compliance_build46_golden_comparison.md`.*
