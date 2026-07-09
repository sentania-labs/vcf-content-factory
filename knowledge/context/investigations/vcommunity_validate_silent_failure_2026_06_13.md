# vCommunity — "fails to validate, no useful error in UI" (instance 5186)

- **Date:** 2026-06-13
- **Investigator:** api-explorer (read-only code + wire trace; no live mutation)
- **Adapter:** `content/sdk-adapters/vcommunity` HEAD `71c88d1`, installed pak
  build `1.0.0.2` on devel
- **Instance:** 5186 → `vcf-lab-mgmt-vcenter.int.sentania.net`, `winCred=false`,
  `allowInsecure=true`
- **Symptom (user 2026-06-13 12:05Z):** "Test Connection" goes red with no error
  text. Adapter log shows ONLY `configureAdapter` lines (`allowInsecure=true`
  warn, then `VCommunityAdapter configured: ... stitcher=true`). **No SOAP
  connect result line, no onTest outcome line.**

> Reminder: `vcfcf_vcommunity` is a factory dev pak; nothing here uses an
> unsupported endpoint, but if a future hotfix touches `internal-api`
> test-status reads, the `X-Ops-API-use-unsupported` header warning applies.

---

## TL;DR

- **Most likely root cause:** the empty-error is **not produced by the adapter's
  test code**. Every throw path in the tester and in `VCommunityVSphereClient.connect()`
  carries a non-empty message, and the framework `onTest` wrapper *defends against
  a null/empty message* (`getClass().getSimpleName() + " (no message)"`) before
  calling `param.setErrorMsg`. A contentless red therefore means **`onTest`'s
  tester body never ran to a throw or a success** — consistent with the user's
  observation that *no onTest log line of either kind appears*. The trigger that
  fits all evidence is the **two-credential-kind instance dialog**: the reviewer's
  open EMPIRICAL-VERIFY (vcommunity-build-1 review) — VCF Ops must accept an
  instance with the optional Windows Guest Credential left unset. If the platform
  rejects/!binds the credential set on a 2-kind type=7 ResourceKind, validation
  fails in the controller **before `onTest` is dispatched**, which is exactly a
  red button with no adapter-side message and no onTest log.
- **Collection is independently OK (almost certainly):** `configureAdapter` ran
  and logged `stitcher=true`; collection (`onCollect` → `collectWorld`) is a
  *separate controller call* from `onTest`. A failing/unreached `onTest` does
  **not** block `onCollect`. So "fails to validate" is most likely **cosmetic**
  (the Test button), while the instance collects and stitches normally — pending
  ops-recon confirming instance 5186 is `DATA_RECEIVING`.
- **No defect found in `VCommunityConfig` parsing.** It is defensively coded
  end-to-end; the "settings/cloud-account porting" the user suspects is clean.

---

## 1. The onTest / test-connection path — full trace

### Framework wrapper (authoritative)
`vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java:593`

```java
public final boolean onTest(TestParam param) {
    VcfCfTester<C> tester = getTester();
    if (tester == null) return true;
    try {
        tester.test(config, httpClient, param);
        return true;
    } catch (Exception e) {
        String msg = e.getMessage();
        if (msg == null || msg.isEmpty())          // <-- empty-message GUARD
            msg = e.getClass().getSimpleName() + " (no message)";
        param.setErrorMsg(msg);                     // <-- always populated
        logWarn("onTest: connection test failed: " + msg, e);  // <-- always logged
        return false;
    }
}
```

**Consequence:** if `tester.test(...)` is ever entered and throws, the UI gets
text (worst case the exception class name) AND a `logWarn("onTest: connection
test failed...")` line appears. If it succeeds, the tester itself logs
`logInfo("Test OK: ...")`. **Either outcome leaves a log line.** The user sees
neither → the tester body did not run to completion under `onTest`.

### Tester body (`VCommunityAdapter.java:189-229`)
Every exit is either a throw-with-message or a logInfo:

| Path | Behavior | Message non-empty? |
|---|---|---|
| `testResourceConfig(param) == null` (no `AdapterConfig` / no `getAdapterInstResource`) | `throw new Exception("Test-connection: no adapter-instance ResourceConfig …")` | yes |
| `testVs.connect()` throws (see §below) | propagates a descriptive `Exception` | yes |
| inventory walk + success | `logInfo("Test OK: connected to …")` | n/a (success) |
| `finally testVs.disconnect()` | swallows internally, never masks the outer throw | — |

There is **no blank-message path and no swallowed exception** in the tester.
The one subtle point: the tester rebuilds config from `param` via `buildConfig(rc)`
and ignores `this.config`, so it is robust even if `onConfigure` had not run.

### connect() throw paths (`VCommunityVSphereClient.java:83-121`)
All four failure exits carry text:
- no `RetrieveServiceContent` response → `"RetrieveServiceContent failed (no response)"`
- no `returnval` → `"RetrieveServiceContent: no returnval"`
- incomplete content → `"RetrieveServiceContent: incomplete content"`
- login no response / SOAP fault → `"Login failed (no response / SOAP fault)"`
- login 200 but no cookie → `"Login succeeded but no session cookie returned"`

**Wire note (not the bug, but worth recording):** `post()` (line 791)
`if (code < 200 || code >= 300) return null;` **discards the SOAP fault body** on
any non-2xx (a vim25 `InvalidLogin` is HTTP 500). So a *bad-credential* test
surfaces only the generic `"Login failed (no response / SOAP fault)"` — it never
shows the actual vCenter fault string (`InvalidLogin`, `NoPermission`, cert
error). That is a **diagnostics-quality defect, not the silent-validate cause**
(the message is non-empty, so the UI would still show *something* and onTest
would log). See fix F2.

**Conclusion for §1:** the adapter cannot itself produce a *contentless* red via
`onTest`. A truly empty UI error + zero onTest log lines means the failure is
upstream of `tester.test()` — i.e. the controller's pre-test instance/credential
validation, not the adapter code.

---

## 2. VCommunityConfig parsing (the "settings/cloud account" code) — clean

`VCommunityConfig.java` + `VCommunityAdapter.buildConfig` (84-141) audited against
`describe.xml`. No required-read-that-throws, no fail-closed enum, no field-name
mismatch:

- **Field names match describe.xml exactly.** Identifiers read in `buildConfig`:
  `vcenter_host, port, windows_monitoring, allowInsecure,
  esxi_adv_settings_config_file, esxi_vib_driver_config_file,
  vm_adv_settings_config_file, vm_configuration_config_file,
  win_service_config_file, win_event_config_file` — all ten present in
  describe.xml (lines 47-78). Credential fields `user/password` (vcenter_credentials)
  and `winUser/winPass` (windows_guest_credentials) — all present (26-38). ✓
- **winCred unset is safe.** `getCredentialField` returns `null` when the cred or
  field is absent (`VcfCfAdapter.java:236`); the POJO maps null → `""`;
  `hasWindowsCredential()` = `!winUser.isEmpty()` = false → guest-ops simply
  short-circuits in `buildGuestOps()` (372-374). No throw, no mis-default. ✓
- **Enum fails OPEN to DISABLED, not closed.** `WindowsMonitoring.parse` returns
  `DISABLED` for null/blank/unexpected (default branch). A bad enum value cannot
  abort config or test. ✓
- **Six config-file identifiers default correctly** via `nonBlank(...)` to the
  bundled base names, matching the describe.xml `default=` attrs and the bundled
  `content/files/solutionconfig/*.xml`. ✓
- **Port parsing** clamps to 443 on any non-numeric / out-of-range. ✓

The user's hypothesis ("settings/cloud-account porting could use polishing") does
**not** hold at the parsing layer. The polish that *is* warranted is the
two-credential **dialog/binding** behavior at the platform layer (§4 F1), which is
config-adjacent but not in `VCommunityConfig`.

---

## 3. Is it collecting? — validate vs collect are independent

- `configureAdapter` logging proves `onConfigure` ran (`VcfCfAdapter.onConfigure`
  → `configureAdapter`). That is the **collect/config** lifecycle, not the test
  lifecycle.
- `onTest` is a **separate controller call on a bare instance**
  (`VcfCfAdapter.java:593`). It does not gate `onCollect`
  (`VcfCfAdapter.java:660`) — there is no code path where a failed/blank `onTest`
  short-circuits collection. `discoverOnCollect()=true` means the world anchor +
  stitching run every cycle regardless of test state.
- Therefore the most probable reality: **instance 5186 is collecting and
  stitching fine; only the Test-Connection button reports a contentless
  failure.** "Fails to validate" = **cosmetic**, not fatal — *if* recon confirms
  collection.

**What ops-recon must confirm (in parallel):**
1. Instance 5186 collection state = `DATA_RECEIVING` (not `DOWN`/`NO_DATA`).
2. `Number of Resources` ≥ 1 (the `vCommunityWorld` anchor exists).
3. `vCommunity|...` properties present on at least one VMWARE Host/VM (stitch
   landed).
4. The instance's bound credential set: is the Windows Guest Credential row
   present-but-empty, or did the platform refuse to save the instance without it?
   This is the deciding datum between "cosmetic" and "the 2-cred dialog rejected
   the instance".

If recon shows 5186 is NOT collecting either, escalate: the failure is then a
genuine connect failure and F2 (surface the real vCenter fault) becomes the
priority so the next test attempt is diagnosable.

---

## 4. Smallest correct fixes (for sdk-adapter-author — do NOT apply here)

Ranked by likelihood of being THE cause.

**F1 — two-credential-kind instance acceptance (MOST LIKELY ROOT).**
The reviewer's open EMPIRICAL-VERIFY (`context/reviews/vcommunity-build-1.md`):
confirm VCF Ops renders both credential kinds and accepts an instance with the
optional Windows Guest Credential **unset**. If the platform's controller-side
instance validation rejects/!binds a 2-kind `credentialKind="vcenter_credentials,windows_guest_credentials"`
type=7 ResourceKind when the second kind is empty, validation fails *before*
`onTest`, producing exactly: red button, no message, no onTest log.
- *Smallest fix if confirmed:* make the second credential kind not participate in
  instance validation when empty — likeliest concrete form is to **drop the
  Windows Guest Credential from the instance `credentialKind` list** and instead
  read winUser/winPass from a non-credential identifier pair, OR move guest-ops
  credentials to a separate (optional) mechanism. This is a `describe.xml` /
  design change, not a Java-logic change. **Needs the live confirmation first —
  do not change describe.xml on speculation.**
- *This is the only candidate that explains zero onTest log lines.* It is also
  the one the reviewer already pre-flagged as the single most install-fragile
  surface (`lessons/pak-install-reliability.md`).

**F2 — surface the real vCenter fault on connect failure (diagnostics, do
regardless).**
`VCommunityVSphereClient.post()` discards the SOAP fault body on non-2xx
(line 791 `return null`) and `connect()` collapses every login failure to the
generic `"Login failed (no response / SOAP fault)"`. Even once F1 is resolved, a
*real* bad-credential or cert test will be undiagnosable.
- *Smallest fix:* in `post()`, on non-2xx parse the error-stream body for a
  `<faultstring>` / `localizedMessage` and either return it or throw a
  `SoapFaultException(faultstring)`; have `connect()` include that string in the
  thrown message. Keep `// REDACT-SECRET` discipline (never echo the password).
  This converts "Login failed (no response / SOAP fault)" into
  "Login failed: InvalidLogin (Cannot complete login due to an incorrect user
  name or password)".

**F3 — (NIT) onTest does not pre-`configureAdapter`.**
`onTest` uses `this.config`/`this.httpClient` but the tester ignores them and
rebuilds from `param`, so this is currently harmless. No change needed unless a
future tester relies on `this.config`. Recorded for completeness, not actionable.

---

## TOOLSET GAP / open items

- **No TOOLSET GAP in the build/validator surface.** validate-sdk, build-sdk,
  pak-compare all behaved (per build-1 review).
- **Open empirical question (F1)** is a *live-platform* behavior, not a repo
  tooling gap: only a real install of build 1.0.0.2 with the Windows Guest
  Credential left blank, watched at the instance-save / Test-Connection step,
  confirms it. ops-recon (instance 5186 state) is the cheapest probe; a
  controlled re-save of 5186 with/without the Windows cred is the definitive one.

---

## Clean-up

Read-only investigation. No instances, credentials, or objects created on any
lab system. Nothing to delete.
