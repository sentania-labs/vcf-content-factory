# SDK Adapter Review — compliance build 41

- **adapter:** `content/sdk-adapters/compliance`
- **build reviewed:** 41 (`1.0.0.41`), delta since build 37 (builds 38–42)
- **reviewer:** `sdk-adapter-reviewer`
- **date:** 2026-06-03
- **verdict:** **APPROVE** (zero BLOCKING)
- **findings:** 0 BLOCKING / 1 WARNING / 2 NIT

---

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean | **Confirmed.** `OK: ... valid Tier 2 SDK adapter project` (11 java files now — VamiApiClient added; 1 javac `-source 11` options warning only). |
| `build-sdk` reproduces at 1.0.0.41 | **Confirmed.** Built `vcfcf_sdk_compliance.1.0.0.41.pak` to a throwaway dir; adapter JAR 78,148 bytes, 8 lib JARs, 11 sources, describe.xml present inside adapters.zip. |
| `pak-compare` zero BLOCKING | **Confirmed (and the build-37 describe.xml false-positive is GONE).** vs build 37 reference dir: `0 BLOCKING, 0 WARNING, 0 INFO — No structural divergences found.` The directory-mode describe.xml false-positive that fired in the build-37 review no longer fires — the tooling fix this session works as the brief stated. |
| Normalizer durability (29 sprint controls reproduce; CRLF-only churn) | **Confirmed independently.** Ran `normalize_scg_v8.py` + `v9.py` from the raw `profiles/vmware_scg_{8,9}.0.csv` sources to temp output; CRLF-normalized diff against the committed canonical CSVs is **byte-identical** (exit 0 both files). Kind tallies: 8.0 = 6 vami_api / 31 vim_property / 36 powercli_only / 10 manual_audit; 9.0 = 6 vami_api / 31 vim_property. |
| Build-38 service_state reconstruction matches the reader | **Confirmed.** 10 `service_state:` recipes total (6 in 8.0, 4 in 9.0). Keys (`sfcbd-watchdog`, `TSM`, `slpd`, `snmpd`, `TSM-SSH`, `ntpd`) are the real ESXi service keys the reader matches against `HostService.getKey()`; grammar `service_state:<key>:running` matches `readServiceStateRecipe` (last-colon split, field ∈ {running,policy}). No reconstruction drift. |
| CSV integrity | **Confirmed.** Both CSVs 13 columns, zero ragged rows; header is name-based and the loader (`BenchmarkLoader`) builds a name→index map and throws on a missing required column (canonical loader contract satisfied). |

---

## Cardinal-rule verification (the reason this gate exists)

Traced every new read path; the unreadable-is-not-compliant contract holds end-to-end:

- **Build 39 — `not:` and `(non-empty)` comparison modes** (`ControlEvaluator`). Verified
  the absent/unreadable case is short-circuited BEFORE the mode helpers in BOTH paths:
  - `evaluateControls` (advanced_setting): the `if (actual == null || actual.isEmpty())`
    guard at line 139 runs before the `isNotEqualMode` branch at line 164. For
    `not:/tmp/scratch`, `allowsUndefined` is false, so an absent ScratchConfig key hits
    `continue` (skip) — NEVER a "not equal to X → pass". Confirmed in code.
  - `evaluateVimProperties` (vim_property/esxcli/vami_api): the UNREADABLE-sentinel fold
    (line 324) and the `actualObj == null` skip (line 336) run before `vimPropertyMatches`
    (line 340) ever calls `notEqualMatches` / `nonEmptyMatches`. A missing/unreadable value
    can never reach the mode helpers. Confirmed.
- **Build 40 — `vm_hardware_device_absent` / `list_empty` / `vlan_id_not`** (highest cardinal
  risk; "empty/absent ⇒ compliant" checks). The `readListConfirmed` → `ListRead{confirmed,list}`
  helper correctly and positively distinguishes a CONFIRMED read of a (possibly empty) list
  from a FAILED fetch: a null container node (`walkToParent` returned null), an absent/wrong-type
  list accessor, and a null accessor return ALL fold to `ListRead.failed()` → `null` → UNREADABLE.
  Only a non-null container yielding an actual `List` instance is `confirmed`. An empty
  confirmed list is the compliant outcome; a failed fetch is NEVER "empty ⇒ compliant".
  `vlan_id_not` returns null→UNREADABLE on an unrecognized spec type (never a guess-pass).
  Verified in `VSphereClient.java:809-1007`.
- **Build 41 — VAMI REST reader** (`VamiApiClient` + `evaluateVamiForVCenter`). Verified the
  full fold chain: `getEndpoint` returns null on no-session / non-200 / 401/403/404/5xx /
  timeout / parse-error / null-or-isNull body; `readField` returns the `FAILED` sentinel on a
  null body OR an absent navigated field, and `listOrNull` returns null on an empty/ non-list
  node. `ComplianceAdapter.evaluateVamiForVCenter:1170-1176` maps BOTH `FAILED` and `null` (and
  a malformed recipe via `parseVamiRecipe`) to `VSphereClient.UNREADABLE` before handing the
  value map to the evaluator. A failed GET of `access/ssh` therefore lands as UNREADABLE, NEVER
  "ssh disabled ⇒ compliant". The "should be disabled" controls are safe.
- **VAMI max_days semantic — NOT inverted (verified against SCG intent).** `vc.vami-administration-
  password-expiration` (8.0) / `vc.vami-password-max-age` (9.0) wire `expected_value = -1`,
  compared via numeric `valuesMatch`. The SCG Discussion text on both rows explicitly cites
  NIST 800-63B §5.1.1.2 (do not force periodic rotation) and the remediation sets
  `max_days=-1` (no expiry). `-1` IS the SCG-intended compliant value; the author's numeric
  equality is correct, not a "≤ N days" reading. No inversion.
- **Zero-divisor contract / merge.** `mergeResults` and `emptyResult` preserve `score=100.0`
  with `totalCount=0` when nothing was evaluable; `unreadableCount` sums and stays out of
  pass/fail/total; every world-rollup caller (`collectHosts:594`, `collectVms:663`,
  `collectVCenter:727`) gates on `cr.totalCount > 0` before folding into the fleet average.
  `pushOrProfileName` pushes the rollup only when `totalCount>0 || unreadableCount>0`, else
  profile-name-only. No `totalCount==0` sentinel reaches an average.
- **Evaluable set not widened without a reader.** `BenchmarkProfile.isEvaluableKind` admits
  `vami_api` only with a non-empty `read_recipe` (build 41) — and that recipe is backed by the
  real `VamiApiClient` reader. No kind is evaluable without a backing read path.
- **MOID / stitching identity.** No change to the join keys this delta; vCenter stitch still
  resolves `VMwareAdapter Instance` by `instanceUuid` (from the live SOAP session) + VCURL/FQDN
  (`collectVCenter:739-749`), never a bare MOID. VAMI attaches to that same resolved
  VCenterAdapterInstance resource. No stitch-corruption path introduced.
- **No secrets logged.** `VamiApiClient` does no logging at all — the Base64-encoded
  `username:password` it builds in `ensureSession` and the returned session token are never
  written to a log. Grep of every `log*`/`logger` call across `src/` for
  password/credential/secret/sessionId/cookie/getBytes/Base64 → no matches.
  `rules/no-secrets-on-disk.md` satisfied.

---

## Gap honesty (RULE-002 / skill § *Gaps — name them, never hide them*)

- **Build 42 SSO STS — CLASSPATH GAP documented honestly, no half-built reader.** No Java was
  added for SSO; `git status` shows no new SSO source. `UNAUDITED_CONTROLS.md:166-208` documents
  the WS-Trust/STS + SSO-admin-SDK classpath gap in detail (no `com.vmware.vim.sso*`, no STS /
  `RequestSecurityToken` bindings on the classpath) and keeps all 10 vCenter SSO
  lockout/password-policy controls **manual ("Cannot")**. Correctly mirrors the vSAN SDK gap.
- **Pending-verification labeling is honest, not inflated.** The in-pak doc has a dedicated
  "Wired — pending live field-name verification" section, distinct from the audited set. Every
  build-40/41 control is labeled "scored but field-name/path/type-unconfirmed" and the VAMI
  transport is explicitly marked "BLIND build — schema confidence MEDIUM, field names derived
  from documentation, not captured on the wire." Because a wrong field name folds to UNREADABLE
  (verified above), these are coverage-honesty labels on safe-by-construction reads — the correct
  posture. The build-37 WARNING (stale "Cannot" entries for now-audited esxcli controls) appears
  addressed: those controls moved into "Wired — pending verification."

---

## WARNING

- **[CHANGELOG.md / adapter.yaml] Build hygiene — no CHANGELOG entry for builds 38, 39, 40, 41**
  (skill § *Build / verify loop* "add a `CHANGELOG.md` line every build"; author hard rule 9;
  `rules/validate-before-install.md`). `adapter.yaml` declares `build_number: 41`, but the top
  CHANGELOG entry is still `## 1.0.0.37`. The only CHANGELOG change in the working tree is a
  re-churn of the existing 1.0.0.37 line (the same regeneration NIT flagged at build 37) — there
  are NO `1.0.0.38/.39/.40/.41` entries. Re-running `build-sdk` did NOT add them (the doc
  generator pulls the changelog from a source that was never updated for these builds). Net: the
  changelog that ships **inside the pak** omits the entire 38–41 sprint (service_state, the two
  comparison modes, the three list/device readers, and the whole VAMI transport) and an operator
  reading it would believe the pak is build 37. Not a read-path-safety defect, but a real hygiene
  violation and an in-pak doc that misrepresents what shipped. → **Fix:** add one CHANGELOG line
  per build 38–41 (and confirm the committed changelog is the one the doc generator emits, so a
  clean checkout + build doesn't re-diverge — the build-37 regeneration NIT is still live).

---

## NIT

- **[EsxcliSoapClient.java:455-470] build-37 NIT resolved.** `drain()` now closes the
  InputStream in a `finally`, so a mid-read throw releases the underlying connection input.
  Correct, behavior-preserving hygiene fix — noted as resolved, no action.

- **[ControlEvaluator.java NTP/list controls] `(non-empty)` list controls (NTP servers, syslog
  forwarding) pass on ANY non-empty value.** Conservative by design (an empty/failed list folds
  to UNREADABLE upstream, never a false pass), and the SCG baseline for these is a site-specific
  sentinel that plain equality would permanently false-fail — so non-empty mode is the right
  call. But an operator should understand "compliant" here means "a remote target is configured,"
  not "the *correct* target." Worth a one-line note in the per-control description or REFERENCE so
  the semantic isn't over-read. (Coverage-clarity, not a correctness defect.)

---

## If shipped as-is

Operators get correct, conservative compliance scores across the expanded surface (ESXi service
state, the not-equal/non-empty advanced-setting controls, the three vim25 list/device checks, and
the new VAMI appliance-REST controls) — every failed, absent, or schema-mismatched read folds to
UNREADABLE and is surfaced as a coverage signal (`unreadable_count` /
`Summary|total_unreadable_controls`), never a silent false-pass. The build-40 "empty ⇒ compliant"
checks and the build-41 blind VAMI transport are the two places a wrong-but-plausible read could
land, and both were verified to fold to UNREADABLE rather than pass. The one real cost is the
in-pak CHANGELOG: it claims the pak is build 37 and omits the entire 38–41 sprint, so an operator
auditing what they installed is misinformed about the build's contents (not its behavior). The
build-40/41 controls correctly carry "pending live verification / MEDIUM confidence" labels, so a
field-name miss surfaces as a coverage gap on the dashboard, not a wrong score — exactly the
honest-denominator posture this sprint was meant to preserve.
