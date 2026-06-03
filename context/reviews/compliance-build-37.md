# SDK Adapter Review — compliance build 37

- **adapter:** `content/sdk-adapters/compliance`
- **build reviewed:** 37 (`1.0.0.37`)
- **reviewer:** `sdk-adapter-reviewer` (first run — shakedown)
- **date:** 2026-06-03
- **verdict:** **APPROVE** (zero BLOCKING)
- **findings:** 0 BLOCKING / 3 WARNING / 3 NIT

---

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `validate-sdk` clean | **Confirmed.** `OK: ... valid Tier 2 SDK adapter project` (10 java files, 1 javac options warning only). |
| `build-sdk` reproduces at 1.0.0.37 | **Confirmed.** Built `vcfcf_sdk_compliance.1.0.0.37.pak`, adapter JAR 69,953 bytes, 8 lib JARs, describe.xml present at `vcfcf_compliance/conf/describe.xml` inside adapters.zip. |
| `pak-compare` zero BLOCKING | **Differs — but the single BLOCKING is a pak-compare false positive, not an adapter defect.** See process note P1 below. Against build 32, pak-compare reports `[B1] describe.xml: factory has no describe.xml`. The built pak DOES ship describe.xml (inside adapters.zip, the correct SDK-adapter location, same shape as the build-32 reference). pak-compare's directory mode looks for a top-level describe.xml and does not descend into adapters.zip. Not a shippable defect. |

Net: build is reproducible and structurally sound. The unreadable-is-not-compliant
contract holds end-to-end (verified below). No false-pass path found.

---

## BLOCKING

None.

The cardinal rule (unreadable ≠ compliant) is satisfied on every read path I traced:

- **vim_property recipe reader** (`VSphereClient.readByRecipe` → `readVimProperties`):
  every miss (null prefix, missing accessor, unknown style, malformed recipe,
  reflective throw) resolves to the `UNREADABLE` sentinel, which
  `ControlEvaluator.evaluateVimProperties` counts in `unreadableCount` and excludes
  from pass/fail/total. Confirmed `readByRecipe` default branch returns null (never
  guesses), and the catch in `readVimProperties:426-433` folds any unexpected
  reflective failure to `UNREADABLE` rather than throwing.
- **esxcli reader** (`EsxcliSoapClient` + `VSphereClient.readEsxcliRecipe`): a SOAP
  fault, esxcli `<fault>`, missing/empty `<response>`, parse failure, absent field,
  unmatched row, selector-applied-to-non-list, or null session cookie ALL return
  `COMMAND_FAILED`/null → `UNREADABLE` upstream. A failed esxcli read can never
  become a pass. `EsxcliSoapClient.readCommandResult` wraps the whole call in
  try/catch and caches a FAILED result so it is not retried, never throwing into the
  cycle.
- **Zero-divisor contract**: `evaluateControls` / `evaluateVimProperties` /
  `mergeResults` / `emptyResult` all return `score=100.0` with `totalCount=0` when
  nothing was evaluable, and every world-rollup caller gates on `cr.totalCount > 0`
  (`collectHosts:593`, `collectVms:662`, `collectVCenter:714`) before folding a
  score into the fleet average. `pushProfileNamePropertyOnly` / `pushOrProfileName`
  keep no-signal resources out of the rollups while still surfacing them. Verified no
  caller folds a `totalCount==0` sentinel.
- **Evaluable set not widened without a reader**: `BenchmarkProfile.isEvaluableKind`
  admits `esxcli` only when a non-empty `read_recipe` is present, and `esxcli` has a
  real reader as of build 36. No kind is evaluable without a backing read path.
- **MOID trap**: foreign-resource joins use the right keys. HostSystem/VM/DVS/DVPG
  match on `VMEntityObjectID` (the vCenter-scoped moid carried in the Ops resource
  key) plus name, not a bare cross-vCenter moid; `VMwareAdapter Instance` resolves by
  `VMEntityVCID` (instanceUuid) first, then VCURL/FQDN, then singleton. esxcli host
  targeting uses the live per-host MoRef from the same session (no cross-vCenter moid
  reuse). No stitch-corruption path found.
- **No secrets logged**: grep of every `log*`/`logger` call for password/cookie/
  credential/secret → no matches. The vCenter session cookie is passed to
  `EsxcliSoapClient` but never logged.

---

## WARNING

- **[profiles/UNAUDITED_CONTROLS.md:68-80] Gap-honesty / stale in-pak coverage
  statement** (skill § *Gaps — name them, never hide them*; `rules/no-fabricated-metrics.md`).
  Build 37 reclassified ~16 controls to evaluable `esxcli` recipes, but the
  coverage statement that **ships inside the pak**
  (`vcfcf_compliance/conf/profiles/UNAUDITED_CONTROLS.md`) still lists them under
  **"Cannot (genuinely manual — no machine-readable signal)"**. Confirmed stale
  entries: the entire "ESXi SSH daemon (`sshd_config`)" block
  (`esx.ssh-fips-ciphers`, `-gateway-ports`, `-host-based-auth`,
  `-idle-timeout-count`, `-idle-timeout-interval`, `-login-banner`, `-rhosts`,
  `-stream-local-forwarding`, `-tcp-forwarding`, `-tunnels`, `-user-environment` —
  11 controls, all now wired with `esxcli:system.ssh.server.config.list:Value[Key=…]`
  recipes in scg_8.0.csv), plus `esx.key-persistence`, `esx.account-dcui`,
  `esx.account-vpxuser` on lines 79-80 (now wired:
  `keypersistence.get:Enabled`, `account.list:Shellaccess[UserID=dcui|vpxuser]`),
  and the TLS-profile / log-filter reclassifications. The doc's own preamble states
  *"A control being absent here means it is (or is intended to be) audited"* — so
  listing now-audited controls under "Cannot" directly violates the doc's contract
  and ships an operator-facing coverage statement that understates real coverage and
  contradicts the scores the adapter now pushes. This is the inverse of hiding a gap,
  but it is still a dishonest in-pak coverage doc. → **Fix:** move every
  build-36/37-reclassified control out of "Cannot" (and the SSH-daemon "no
  machine-readable signal" framing is now factually wrong — these ARE read via
  esxcli over the vCenter session); reconcile against the canonical CSV recipe set so
  the doc matches what is scored.

- **[EsxcliSoapClient.java:184-203, 345-370 + scg_*.csv list recipes] Unverified
  `list`-command row field names — degrades to UNREADABLE, never false-pass, but
  coverage is unproven** (esxcli spike §0.3/§0.7; skill § *vim25 over JAX-WS*
  reflection-tolerance). The build-37 row-selector grammar
  `Value[Key=ciphers]` / `Shellaccess[UserID=dcui]` assumes PascalCase row fields
  `Key`/`Value` (ssh server config list) and `UserID`/`Shellaccess` (account list).
  The spike only **empirically proved one command on the wire**:
  `system.syslog.config.get` (the build-36 get-struct slice). The list-command row
  field names are **derived, not wire-captured** — the spike itself (§0.7) could not
  re-run live, and its own recipe sketch used a *different* row model
  (`...config.list:gatewayports`, bare key-as-field) than what build 37 implemented
  (`Value[Key=gatewayports]`). If the real field names differ, every affected control
  silently lands as `unreadable` (correct per the cardinal rule — I verified the
  fall-through), but the operator would see a coverage gap where the author believes
  there is coverage. The one indirect data point (session-handoff: devel showed
  `Shellaccess=true` for dcui) supports the account-list shape only. → **Fix:** before
  promoting these out of backlog, wire-capture one `system ssh server config list` and
  one `system account list` response (govc `host.esxcli ... -dump`, or the trace
  command in spike §0.7) and confirm the row element + `Key`/`Value`/`UserID`/
  `Shellaccess` field names. Until confirmed, document the SSH/account list controls as
  "wired but field-names unverified" rather than as proven coverage. (The 8.0 SSH
  cluster is also noted in session-handoff as never directly exercised — devel runs
  9.0 — which compounds this.)

- **[VSphereClient.java:138-158, 186-207, 300-336, 347-368, 842-864] ContainerView
  not released on the exception path — per-cycle server-side leak** (skill § *Memory
  safety & resource hygiene*). Every inventory walker
  (`getHosts`/`getVms`/`getDvSwitches`/`getClusters`/`getDvPortgroups`) does
  `createContainerView(...)` → `getViewMembersTyped(...)` → `destroyView(...)` with
  **no try/finally**. If `getViewMembersTyped` (a PropertyCollector
  `retrieveProperties` call — network I/O) throws, `destroyView` is skipped and the
  view leaks on the vCenter for the session lifetime. Across a long-running collector
  with intermittent SOAP errors this accumulates ContainerView managed objects.
  Not a correctness/false-pass issue, but real resource hygiene. → **Fix:** wrap the
  `getViewMembersTyped` call in try/finally and `destroyView` in the finally (guard
  against a null view).

---

## NIT

- **[EsxcliSoapClient.java:455-465] `drain()` closes the InputStream outside a
  finally** and `post()` calls `conn.disconnect()` after `drain` returns — if `drain`
  throws mid-read, the stream/connection is not closed. Minor (HttpURLConnection is
  GC-reclaimable), but a try/finally would be tidier and matches the hygiene posture.

- **[ControlEvaluator.java:382-395] esxcli string-list controls use exact
  case-insensitive equality** (`ssh-fips-ciphers` expects a specific comma-ordered
  cipher list). A compliant host that returns the same ciphers in a different order,
  or with an extra equivalent cipher, would read as **non-compliant** (false-fail).
  This is conservative (never a false-pass, so not a cardinal-rule violation), but
  operators may see spurious fails. Consider a set/order-insensitive compare mode for
  list-valued controls, or keep these informational until such a mode exists. (Note
  these are also flagged under WARNING-2 as field-name-unverified.)

- **[CHANGELOG.md] build regenerated the top changelog line on `build-sdk`**, which
  dirties the committed file (the builder rewrites the 1.0.0.37 entry from the
  hand-written detailed line to a terser generated one). Cosmetic, but means a clean
  checkout + build leaves an uncommitted diff. Confirm the intended changelog text is
  the committed one, not the regenerated one. (Process note, not adapter behavior.)

---

## Process / toolset shakedown notes (first run of this reviewer)

- **P1 — pak-compare directory mode false-positive on describe.xml.** Comparing a
  built SDK-adapter pak against a reference produces `[B1] describe.xml: factory has
  no describe.xml` even though describe.xml is correctly bundled inside
  `adapters.zip` (`vcfcf_compliance/conf/describe.xml`). pak-compare looks for a
  top-level describe.xml and does not descend into adapters.zip for Tier 2 SDK paks.
  A reviewer who trusted the BLOCKING count verbatim would wrongly fail this build.
  The reviewer prompt's "zero BLOCKING from pak-compare is the install gate" needs a
  carve-out (or a tooling fix) for the SDK-adapter pak layout where describe.xml lives
  inside adapters.zip. Recommend routing P1 to `tooling`.
- **P2 — no reference-pak directory is configured** (`tmp/reference_paks` not found),
  so `build-sdk`'s inline pak-compare is skipped and the reviewer must hand-pick a
  reference from `dist/`. The closest prior build (32) is several builds back and
  predates the build-35/36/37 esxcli + vim_property work, so the compare is low-signal
  for the actual delta. A per-adapter "last reviewed build" reference pointer would
  make the delta comparison meaningful.
- **P3 — `build-sdk` writes REFERENCE.md/CHANGELOG.md back into the source tree**, so
  a reviewer running build-sdk to verify reproduction mutates tracked files. The
  reviewer is read-only on source; running the verify build nonetheless dirtied
  CHANGELOG.md. Reviewer should build to a throwaway `-o` dir (done) AND be aware the
  doc regeneration still touches the source tree. Consider a `--no-doc-write` flag for
  verify-only builds.

---

## If shipped as-is

Operators get correct, conservative compliance scores — no silent false-passes; every
unreadable control is surfaced as a coverage signal, not folded into a score. The two
real costs: (1) the in-pak `UNAUDITED_CONTROLS.md` lies low about coverage — it tells
operators ~16 SSH/account/key/TLS controls are "manual / no machine-readable signal"
when the adapter now scores them, so an operator auditing their coverage gap list will
be misled and may do redundant manual review; and (2) the esxcli `list`-command
controls (SSH daemon hardening, account shell access) rest on unverified row field
names, so some may silently report as `unreadable` rather than evaluating, with no
operator-visible explanation beyond the `unreadable_count` stat. Neither is a wrong
score; both are coverage-honesty issues worth fixing before the next coverage-surfacing
sprint that will read this doc as ground truth.
