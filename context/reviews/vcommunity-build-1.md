# SDK Adapter Review — vcommunity build 1

- **Adapter:** `content/sdk-adapters/vcommunity` (uncommitted working tree — review-before-commit gate)
- **Build reviewed:** 1 (`vcfcf_sdk_vcommunity.1.0.0.1.pak`)
- **Reviewer:** `sdk-adapter-reviewer`
- **Design:** `designs/managementpacks/vcommunity-sdk.md` (APPROVED)
- **Ground truth:** `references/vmbro_vcf_operations_vcommunity/Management Pack/` (Python source)
- **Reference impl:** `content/sdk-adapters/compliance/`
- **Verdict:** **APPROVE** (zero BLOCKING)
- **Findings:** 0 BLOCKING / 1 WARNING / 3 NIT

## Independent claims verification (re-run, not trusted)

| Author claim | My result | Status |
|---|---|---|
| validate-sdk passes, 9 sources, only a `-source 11` warning | `OK: ... valid Tier 2 SDK adapter project`, 9 `.java`, 1 warning (`system modules path not set in conjunction with -source 11`) | **CONFIRMED** |
| build-sdk produced `dist/vcfcf_sdk_vcommunity.1.0.0.1.pak` | Built; JAR 60,372 B; adapters.zip 121,328 B; aria-ops-core correctly omitted (no `com.vmware.tvs.*` ref) | **CONFIRMED** |
| pak-compare vs compliance 1.0.0.50 = exactly 1 BLOCKING / 2 WARNING, all from the 2nd CredentialKind | `Score: 1 BLOCKING, 2 WARNING, 28 INFO` — B1 = CredentialKind count 2 vs 1; W1 = CredentialField 4 vs 2; W2 = identifier count 10 vs 4. All three trace to the design-mandated Windows Guest Credential + 6 config-file identifiers. | **CONFIRMED (exact)** |
| `CredentialKind maxOccurs="unbounded"` validates against describeSchema.xsd | `tmp/describeSchema.xsd:122` `CredentialKind ... maxOccurs="unbounded"`; `:334` `credentialKind` is optional `xs:string` (comma list legal) | **CONFIRMED** |

Build metadata correct: `build_number: 1`, `version: 1.0.0`, CHANGELOG `1.0.0.1` entry present, kind `vcfcf_vcommunity` lowercase-compliant. Six bundled `content/files/solutionconfig/*.xml` filenames match the six describe.xml identifier defaults byte-for-byte.

## Recommendation on pak-compare B1 — ACCEPT

**B1 is a reference-topology divergence, not an install defect. Accept it.**

Independently verified, not taken on the author's word:
- describeSchema.xsd permits ≥1 `CredentialKind` (`maxOccurs="unbounded"`) and a comma-delimited `credentialKind` attr on the type=7 ResourceKind. The describe.xml is schema-valid.
- pak-compare's "CredentialKind count: factory=2, reference=1" is a *structural delta vs the single-credential compliance pak*, which is the only reference in the corpus — it is mechanically flagged BLOCKING because credential-count mismatches have historically caused install failures (`lessons/pak-install-reliability.md`), but that lesson's failure mode was a *malformed/duplicate* credential binding, not a legitimate second kind. The second kind here is design-mandated (OPEN — Windows Guest Credential, distinct trust boundary), correctly defined (`windows_guest_credentials`, two optional fields), and correctly bound on the instance ResourceKind.
- W1/W2 are the same divergence's downstream field/identifier counts. Same disposition.

This is the expected and intended shape; B1/W1/W2 are noise from comparing a 2-credential adapter against a 1-credential reference. **EMPIRICAL-VERIFY at install** (not a static blocker): confirm VCF Ops renders both credential kinds in the instance dialog and accepts an instance with the Windows Guest Credential left unset — `lessons/pak-install-reliability.md` makes credential handling the single most install-fragile surface, so this is the one thing `qa-tester` must watch on first install.

## WARNING

- **[VCommunityStitcher.java:104-124, 126-148] — skill § *ARIA_OPS stitching identity — the MOID trap*.** Foreign HostSystem/VirtualMachine/ClusterComputeResource resolution loads `/api/resources?adapterKind=VMWARE&resourceKind=<kind>` with **no vCenter scoping**, then `match()` keys on **bare MOID first** (`byMoid.get(moid)`). MOID (`host-12`, `vm-42`) is **not unique across vCenters**; in a multi-vCenter VCF Ops the load returns every vCenter's `host-12` and `byMoid.put(moid, entry)` keeps only the last writer — so a push can land on the wrong vCenter's host. The client already resolves `getVCenterInstanceUuid()` (`VCommunityVSphereClient.java:163`) but never uses it to disambiguate.

  **Why WARNING, not BLOCKING (honest disposition):**
  1. This is **not a divergence from the reference** — the compliance adapter's per-host matcher (`ComplianceStitcher.matchResource`, lines 304-330; `loadHostResources` unscoped) is byte-for-byte the same bare-MOID-first logic, and compliance ships healthy with two DATA_RECEIVING instances. vCommunity faithfully copied the proven reference idiom; blocking vCommunity for a pattern the named reference enshrines would be inconsistent.
  2. It **IS a behavioral regression from the original Python**, which scoped its Suite API query by `adapterInstanceId` (`collectHostData.py:40`, `collectClusterData.py`) — restricting the resource set to the single vCenter this instance monitors, which makes bare MOID safe *there*. The Java port dropped that scope.

  **Smallest correct fix:** scope the foreign-resource match by vCenter instance UUID — either add `VMEntityVCID == vsphere.getVCenterInstanceUuid()` to the `match()` predicate (compliance already indexes `vcByVcUuid` for its vCenter-instance lookup; mirror it per-host), or filter `fetchResources` to the owning vCenter. This is a cross-adapter correctness item: it should be fixed in **both** compliance and vCommunity (and probably codified as a lesson), but it does not block *this* build any more than it blocks the shipped compliance reference. Single-vCenter deployments (the common lab/PoC case, and the devel instance) are unaffected. Hand back to the orchestrator as a tracked correctness item, not an install gate.

## NIT

- **[VmCollector.java:236-242] — degradation-fallback property churn.** Windows events are surfaced as positional `vCommunity|Guest OS|Last Event|<n>|...` properties. The index `<n>` is per-cycle positional, so a cycle with fewer events than the prior cycle leaves stale `|<n>|` keys in the property browser until they age out. Acceptable for the user-accepted TOOLSET GAP #1 property-degradation (superseded by real foreign events in v1.1), but note for v1.1: prefer a stable key (event ID / source+record) over a positional index. Faithful to the original's per-row emission; level→criticality map matches `collect_windows_event_logs.py:168-179` line-for-line.

- **[GuestOpsClient.java:359-370] — guest-ops poll is a fixed 60×2s = 120s ceiling per script per VM, single-threaded.** With Services + OS-info + Events on many Windows VMs this serializes; a slow/hung guest consumes up to 120s before the bounded poll gives up. Isolation is correct (loop continues, design Failure-isolation § satisfied — verified at two layers: `GuestOpsClient` catch-and-return-empty AND per-VM `try` in `VmCollector.collect:75-96`), but a large Windows fleet could blow the 5-min `monitoringInterval`. Not a correctness defect; flag for operability tuning. v1 mirrors the original's "all Windows VMs when enabled" (per-VM scoping deferred to v2, OPEN-3).

- **[VCommunityAdapter.java:354 / :418-421] — timestamp split.** World metrics use `ts` captured at `collectWorld` entry (line 296); `prop()` re-reads `System.currentTimeMillis()` per property (line 420), and `Summary|last_scan_timestamp` uses `Instant.now()` (line 354). Cosmetic intra-cycle skew only; no correctness impact.

## Failure-mode hunt — cleared

- **Unreadable-is-NOT-compliant (skill cardinal rule):** N/A in the scoring sense (pure stitching, no compliance score / no zero-divisor rollup). Read-failure discipline still verified throughout: ClusterCollector skips unread scalars rather than emitting sentinels (`putHa`/`putDrs` skip on null; DRS Score null→skip, never a 0 sentinel except the *intentional* DRS-disabled 0 which mirrors `drs_properties.py`); HostCollector license `Remaining Days` is omitted when expiration is null (never a sentinel); SCSI/snapshot 0 is a genuine reading (absence of node), not an unread default. **No path turns a failed read into a fabricated value.**
- **SolutionConfigStore last-good cache (design Config §):** Correct. Transient fetch failure / first-cycle null Suite API client → `degradeList` returns last-good cache (`usable=true, stale=true`); first cycle with no cache → `usable=false` and the caller (`HostCollector:88`, `VmCollector:119/129`) **skips the gated collection** rather than collecting with an empty list. An all-commented-out file is a *successful* read → empty list with `usable=true` (correctly distinguished from a failed fetch). `test()` reports per-file configured names; per-cycle counts surface on the world anchor `config_file_status`. **Never silently collects with empty lists.**
- **Crash-the-cycle isolation (design highest-risk §):** Verified at every layer. Per-VM/host/cluster `try` blocks in each collector loop; guest-ops double-wrapped; guest temp-dir cleanup in `finally` on every guest-ops path (`collectServices`/`collectOsInfo`/`collectEvents` all `finally deleteDirQuietly`). One unreachable/mis-credentialed guest logs WARN and the loop continues. No empty catches that swallow a real error into a pass.
- **Reflection-tolerant vim25 (skill § *vim25 over JAX-WS*):** Raw-SOAP DOM walk by local-name; no concrete vim25 cast anywhere; SCSI type discrimination by wire `xsi:type` string match, not `instanceof`; missing field → null → skip (`readScalar`/`readBool`/`getStringProperty` all return null, never throw on absence). `getLongestPrefixElement` swallows per-prefix read exceptions to null. The one intentional throw (`fetchInstallDate` on SOAP fault) is caught at the call site and degraded to a property — does not abort the cycle.
- **Canonical loader / header-name parsing (skill § *Canonical data loader contract*):** Guest CSV parsed by header NAME (`idx(header,"Name")` etc.), never column position; missing required column → `return out` (empty, skip), matching the original's `header.index(...)`. SolutionConfig XML parsed structurally (root text comma-split), mirroring `get_config_file_data`.
- **Secrets in logs (RULE-008):** Clean. `password`/`winPassword` flow only into constructors and the SOAP `Login`/`auth()` envelope bodies (legitimate consumers); audited every `log*`/`Exception(`/URL construction — no secret reaches a log line, exception message, or URL. Session cookie set as a header, never logged. `// REDACT-SECRET` markers consistent.
- **describe.xml bare-describe safety (`lessons/controller-describe-bare-instantiation`):** `super(ADAPTER_KIND)` no-arg constructor supplies the kind; no injected-state accessor called in the describe path. Enum identifiers/defaults correct; six config-file defaults match bundled filenames; localization keys (nameKey 1-42) all resolve in `resources.properties` with no gaps.
- **SSL discipline (`lessons/suite-api-stitch-ssl-tofu-vs-java-http`):** vCenter SOAP uses `getPlatformSslContext()` (admin-pre-approved cert) by default, `insecureSslContext()` only on explicit `allowInsecure=true` (lab opt-out, WARN-logged); Suite API stitching rides the framework's injected ambient channel. Guest-ops file transfers reuse the SOAP SSLSocketFactory + session cookie.
- **Resource hygiene:** `onDiscard` disconnects vsphere + discards the stitcher; ContainerViews destroyed in `finally` (`destroyViewQuietly`); guest temp dirs deleted in `finally`; all HTTP streams drained-and-closed. No per-cycle leak.

## If shipped as-is

An operator installs cleanly (pending the EMPIRICAL-VERIFY that VCF Ops accepts the two-credential instance dialog), and a **single-vCenter** deployment collects and stitches `vCommunity|` data correctly onto the right Cluster/Host/VM resources. The only latent risk is a **multi-vCenter** VCF Ops, where bare-MOID matching could push a host's properties onto a same-MOID host in a different vCenter — but that risk is identical to the already-shipped, healthy compliance adapter, so it is a corpus-wide correctness item to track, not a vCommunity-specific blocker.
