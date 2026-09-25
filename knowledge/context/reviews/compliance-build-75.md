# SDK Adapter Review: compliance builds 74-75 (reading the permanently unreadable controls)

- **Adapter:** `content/sdk-adapters/compliance` (branch `feat/v3-version-aware`)
- **Builds reviewed:** 74 `226094a` (adapter, profiles, VAMI client), 75 `ba636f6` (dashboard lists), vs build 73 `1575478`; pak-compare vs build 56 `32de5aa`
- **Pak:** `dist/vcfcf_sdk_compliance.0.0.0.75.pak`
- **Sources:** `knowledge/context/api-surface/compliance_config_encryption_and_vsan_checksum_reads.md`, `compliance_vami_appliance_api_read_path.md` (vendor spec `reference/docs/vcenter-9.1.1-appliance-api.json`)
- **Closes:** build-73 W1 (host `config.encryptionState.*` reads) and the live finding of 9 controls unreadable on healthy devel objects
- **Reviewer:** `sdk-adapter-reviewer` (static, pre-install gate)
- **Date:** 2026-09-23
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 1 NIT

## Claims check (independently re-run, at build 75)

| Check | Result |
|---|---|
| `ci/run_java_tests.sh` | **Pass, exit 0.** 8 Java suites (new `Build74ReadPathsTest`), generator unittest 14/14, drift test 3/3. |
| `generate_compliance_alerts.py --check` | **Up to date.** 136 per-control alerts (Cluster 1). |
| describe.xml totals | **Confirmed:** 150 / 143 / 140; no `object_checksum` alert remains. |
| Dashboard lists | **Confirmed:** 142 / 87 / 24 / 31; the drift test passes. |
| Profiles reproduce | **Confirmed.** All five drivers (6.7, 7.0, 8.0, 9.0, 9.1) regenerate byte-identical CSVs. A parsed old-vs-new diff shows only the intended rows changed: the encryption rows moved to esxcli (7.0: 1, 8.0: 2, 9.0/9.1: 3); the VAMI recipe fixes (`access/ssh:(value)`, `local-accounts/root:max_days_between_password_change`, `system/global-fips:enabled` in 8.0/9.0); 9.1 `vc.tls-ciphers` expected `NIST_2024_TLS_13_ONLY`; nothing else. `manual_review.csv` adds `cluster.object-checksum` for 8.0/9.0/9.1. |
| `validate-sdk` | **OK.** |
| `build-sdk` | **Reproduces.** Every extracted file matches `dist/...75.pak`; adapter tree clean. |
| pak-compare vs 56 | **0 BLOCKING / 2 WARNING / 38 INFO.** New W1, "adapter instance identifier count 5 vs 4", is the intended `read_appliance_settings`. It is `identType="2"` (not part of instance identity, per `knowledge/context/api-maps/tvs-declarative-stitching.md`) and `required="false"` with a default, so existing instances keep their identity on upgrade. W2 is the known ComplianceWorld attribute retirement. |
| Registry | No `defects.local.md`; no open defect names `compliance`. |

## Focus areas

### Secrets in the rewritten VAMI client: clean

`VamiApiClient` logs through `warnOnce` only:
- the base URL (`https://<vcenter>`, no user info);
- the appliance path;
- HTTP status and vAPI `error_type`, or `exception class: message`.

Credentials exist only as the Base64 `Authorization` header of `POST /api/session`, which is never logged. The session token (`vmware-api-session-id`) is never logged. `UnreadableReasons.summary()` prints only reason **categories** (the text before the first colon) and counts; full reasons go out at DEBUG only. The new SOAP `lastFault` captures vCenter's `<faultstring>` from response bodies (capped at 200 chars), never a request body. `VCenterApiClient` lost its private trust-all manager and takes the adapter's context. No secret reaches any log path (RULE-008).

### Session handling on failure paths: correct

- `evaluateVamiForVCenter` wraps every read in `try { ... } finally { client.close(); }`, so `DELETE /api/session` runs on success, on read failures and on exceptions.
- `close()` is a no-op when no session was opened (the POST failed), best-effort with a 10 s timeout, and never throws.
- A failed session is cached per client (one cycle), so N controls cause one POST, not N.
- A new client per cycle means no stale session carries over.

### Trust

REST clients now get `insecureSslContext()` on the `allowInsecure` opt-out, otherwise the platform context. This is the same decision the SOAP client makes, and the lesson `suite-api-stitch-ssl-tofu-vs-java-http.md` endorses the platform context for target-system endpoints (the vCenter cert is platform-approved, and VAMI is the same host and port). A bare Test Connection instance falls back to the JDK default via the caught `RuntimeException`.

### `read_appliance_settings`: upgrade, change and restore all correct

- **Upgrade:** no stored value, so `getIdentifier` returns null and `parseReadAppliance` gives `DEFAULT_READ_APPLIANCE` (false). A test asserts the describe `default="false"` equals the constant.
- **Off:** `BenchmarkLoader.applyApplianceSetting` turns every `vami_api` control into manual review in both bundled and Custom loads. The loader cache keys include `appliance=<bool>`, and `configureAdapter` builds a fresh loader on every instance edit, so a change takes effect on the next cycle.
- **Cleanup when off:** manual-review controls are stale-cleanup candidates, so any lingering `Compliant = 0` on the vCenter object flips to -1. The values actually there are -1 (they were unreadable), which cleanup correctly leaves alone.
- **Restore when turned on:** the controls are evaluated and pushed live again.
- **Score effect:** the vCenter stops counting five failing-because-unreadable controls. This is documented in the CHANGELOG.

### esxcli parser with a missing field: UNREADABLE, never a pass

`EsxcliSoapClient.fieldIgnoreCase` returns null when the field is absent under either exact or case-insensitive match. `VSphereClient` then records `esxcli-field-missing: <command> <field> (fields: [...])`, returns null, and `readVimProperties` stores `UNREADABLE`. `COMMAND_FAILED` is handled separately, also as UNREADABLE. The one-time WARN lists the fields actually returned, which is exactly what acceptance item (i) needs. The case-insensitive fallback only runs when no exact key exists, so it cannot shadow a correct match.

### vSAN gate when the probe fails: UNREADABLE

`hasVsanConfig` now **throws** on a null cluster MoRef or a null `configurationEx` (a SOAP fault or missing propSet), including `lastFault`. `probeVsan` catches it and returns null, and `collectVimObject` folds the controls to UNREADABLE. Only a *successful* read with `vsanConfigInfo/enabled` absent, false or not `true` means "not enabled", which gives N/A (no score, no unreadable). `VsanGate` is SDK-free and XML-tested.

### Other changes checked

- The three host encryption controls now read `esxcli:system.settings.encryption.get:{Mode, RequireSecureBoot, RequireExecutablesOnlyFromInstalledVIBs}`. The read-path guard now rejects `config.encryptionState.*`, and `esxcli` rows are host-only, which closes build-73 W1.
- The field names come from the vendor SCG audit script and have not been seen on the wire. The failure mode is UNREADABLE, never a pass, and the WARN names the returned fields (acceptance (i)).
- `(value)` token: a bare JSON scalar body becomes the value. A 200 with an empty list is `""` and fails `(non-empty)`, a real answer not a read failure, which is correct. An absent field is UNREADABLE.
- `cluster.object-checksum` goes to manual review with a documented reason. It is also a cleanup candidate, so the 0s that builds up to 73 wrote on clusters flip to -1 and their alerts cancel.

## WARNING

### W1. Non-vSAN clusters keep the `cluster.managed-disk-claim` value from the false-pass era

- **Where:** `ComplianceDecisions.candidateControlIds` / `staleZeroControls` together with the new N/A path (`collectVimObject`, where `probeVsan` false gives `emptyResult`).
- **Authority:** skill § *Unreadable is NOT compliant* (no stale pass left on an object); the build-57 W1 / build-59 cleanup contract ("controls the object is no longer evaluated on get -1").
- **What:** build 74 fixes a false pass: non-vSAN clusters used to be scored on `cluster.managed-disk-claim` (and object-checksum, now demoted and cleaned). From build 74 a non-vSAN cluster is N/A and pushes only profile_name and zeroed counters. But the cleanup candidate set removes every control the *current benchmark* evaluates, and `managed-disk-claim` is still evaluated by 9.0/9.1 for the cluster kind. So it is never a candidate on a non-vSAN cluster, even though it is no longer pushed there. On top of that, cleanup only flips 0s. The result on each non-vSAN cluster:
  - typically a retained `Compliant = 1` (`autoClaimStorage` false), which is the old false pass left permanently in the metric browser;
  - where `autoClaimStorage` read true, a retained 0, which keeps a per-control alert with a remediation runbook **open forever** on a cluster where vSAN is off.
- **Fix:**
  - **Candidates:** build the keep set from the controls actually pushed this cycle (the `ControlResult` ids), not from the benchmark's evaluated set. Equivalently, pass `current = null` for an N/A / nothing-evaluated push.
  - **Values:** for those N/A objects, retire both 0 and 1 to -1. The keys exist, so no key is created.
  - **Test:** a non-vSAN cluster holding an old 1 and an old 0 ends at -1 on both.

## NIT

- **N1.** `vc.vami-password-max-age` / `vc.vami-administration-password-expiration` expect `-1`. Per the vendor spec an unset `max_days_between_password_change` means "never expires", which is the SCG-compliant state for 9.x ("Disable forced password expiration"). The adapter reads an absent field as UNREADABLE. Once someone turns `read_appliance_settings` on, a correctly configured vCenter would show that control unreadable (failing) with a "Compliance data not collected" alert. The CHANGELOG discloses this, and the setting is off by default. Settle the wire behavior (acceptance (iv)) before the owner flips the default, and add it to that item.

## Still owed at install

CHANGELOG acceptance plan (a)-(h), (e2) and (i)-(iv), plus W1's check: on wld01 / wld02 (non-vSAN), confirm the `cluster.managed-disk-claim|Compliant` value is -1 after the fix, and that the `cluster.object-checksum` value is -1.

## If shipped as-is

Host encryption controls are attempted through esxcli (UNREADABLE with a named reason if the field names are wrong). Non-vSAN clusters stop being scored on vSAN controls. The VAMI controls are off, not attempted, and no longer drag the vCenter score. Nothing leaks credentials, and appliance sessions are closed each cycle. The leftover is that non-vSAN clusters keep their old managed-disk-claim value from the false-pass era: usually a stale "compliant" 1, and in the rare case of a 0, an alert that never closes.
