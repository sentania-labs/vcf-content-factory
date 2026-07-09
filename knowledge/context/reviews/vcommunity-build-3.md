# vCommunity SDK adapter — build 3 review

- **Adapter:** `content/sdk-adapters/vcommunity/`
- **Build reviewed:** 3 (`adapter.yaml` build_number 3, version 1.0.0; commit `538ec24`)
- **Baseline:** build 2 (`1.0.0.2`, `538ec24~1`)
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-06-16
- **Verdict:** APPROVE (0 BLOCKING)

## Scope of delta

`git diff 538ec24~1 538ec24` — 7 files, +270/-12:

- `VCommunityVSphereClient.java` — licenseAssignmentManager lazy resolution
  (build-2 NULL bug fix), `vmGuestOsInfo()`, SOAP `<faultstring>` parse +
  `redactSecrets`, `hostLabel()`, faultstring-bearing Login exception.
- `VmCollector.java` — `Config` SCSI alias keys + Guest OS emission.
- `VCommunityAdapter.java` — `mapCollectException` cause-walk to
  RESOURCE_STATUS_DOWN; `ensureConnected()` wrapped with actionable
  secret-free rethrows.
- `HostCollector.java` — (unchanged in this diff; licensing emission read
  in full as the consumer of `queryAssignedLicenses`).
- `adapter.yaml` build_number 2→3; `CHANGELOG.md` 1.0.0.3 line. Build
  hygiene OK (RULE-005 / author hard rules 8–9): version bumped, changelog
  matches, diff is minimal with no drive-by refactors.

## Independent verification of author claims

| Claim | Result |
|---|---|
| `validate-sdk` clean | **Confirmed.** Compiles 9 sources, 1 benign `-source 11` warning; "valid Tier 2 SDK adapter project". |
| `build-sdk` reproduces | **Confirmed.** Built `/tmp/vcrev/vcfcf_sdk_vcommunity.1.0.0.3.pak`. |
| `pak-compare` 0 BLOCKING vs build 2 | **Confirmed.** `0 BLOCKING, 0 WARNING, 0 INFO` — "No structural divergences found." |
| Pak now contains `content/files/solutionconfig/*.xml` | **Confirmed present** (6 XML + dir inside the 1.0.0.3 pak). **Discrepancy note:** the build-2 pak *already* contained the same 7 solutionconfig entries — so this is "present and retained," not "newly added by a build-3 builder fix." No correctness impact; flagged only for claim accuracy. |

## Review dimensions

### 1. Cardinal correctness — unreadable is NOT compliant (skill § *Unreadable is NOT compliant*)
PASS. This adapter is **pure stitching — no scoring path, no denominator,
no rollup/average** anywhere a skip could be folded into. Verified:
- `remainingDays()` (`HostCollector.java:180`) returns `null` on
  absent/unparseable expiration; caller (`:151-155`) emits the
  `Remaining Days` STAT only when non-null. Clean skip, **no sentinel**.
- `queryAssignedLicenses` returns an empty list when the assignment
  manager is null / host has none / response is null (`VSphereClient.java:475,484`).
  Empty → zero licensing keys, never a fabricated entry.
- `vmGuestOsInfo` (`VSphereClient.java:vmGuestOsInfo`) only `put`s a field
  the guest actually reported (`putShort` rejects null/empty); caller
  (`VmCollector.java:165-168`) iterates only present entries. Skip on
  absence.
The evaluable set is not widened (there is no evaluable set — stitch only).

### 2. Reflection-tolerant vim25 reads (skill § *vim25 over JAX-WS*)
PASS. Every new read is DOM/PropertyCollector-based with **no cast to a
concrete vim25 subclass**:
- `licenseAssignmentManager()` → `getMoRefProperty(licenseManager, "licenseAssignmentManager")`
  → `getRawPropertyElement` + `elementText`; null on absence, no throw.
- `QueryAssignedLicenses` parsed via `descendantsByLocalName`/`childText`/
  `firstDirectChild` over the response DOM — absent `<name>`/`<licenseKey>`/
  `<editionKey>`/`expirationDate` property → null field, never an exception.
- `vmGuestOsInfo` walks `guest.detailedData` and `runtime.bootTime` via
  `walkToNode`/`childrenByLocalName`/`childText`. `getLongestPrefixElement`
  swallows per-segment read exceptions to null (`:777`). A single VM's
  missing field cannot abort the collection cycle.

### 3. Exception & failure granularity
PASS. No broad swallow-into-pass. `mapCollectException`
(`VCommunityAdapter.java:277+`) walks the cause chain and maps the four
connectivity exception types to DOWN, everything else to ERROR — a total
collect failure surfaces as a red instance, not silent-green-empty.
`ensureConnected()` wrapped (`:318+`) rethrows with actionable host/port
context. Login failure now carries the parsed faultstring.

### 4. Canonical loader contract
N/A — no canonical CSV/benchmark loader in this adapter (live vim25 reads only).

### 5. Stitching identity — the MOID trap (skill § *ARIA_OPS stitching identity*)
PASS (unchanged from build 2). The vCenter-scoped foreign-resource
resolution (`instanceUuid` + MOID, the build-2 MOID-trap fix) is untouched
by this delta. New licensing/guest/SCSI keys push onto the VM/Host already
resolved under that scope. No new bare-MOID join introduced.

### 6. Logging quality & secrets (knowledge/rules/no-secrets-on-disk.md — DEF-001 family)
PASS, with a hardening WARNING (non-blocking).
- The cleartext-`<password>` login **request** body (`loginBody`,
  `VSphereClient.java:126`) is **never** folded into any thrown or logged
  message — verified by inspection of every `throw`/`logWarn` on the
  connect path. This is the structural difference from synology DEF-001,
  where the adapter concatenated the secret-bearing request URL into the
  thrown string. Here only the server's **fault response** body is parsed.
- `extractFaultString` runs the parsed faultstring/localizedMessage
  through `redactSecrets` before logging/surfacing. A vim25
  `InvalidLogin`/connection fault is a server-authored human message and
  does not echo client credentials or the session cookie.
- Skip/null reads are not spammed inside the per-resource loop; failures
  log at WARN with the SOAP action + HTTP code.
**Why not blocking:** there is no proven path by which `_sid` / `passwd` /
`account` / `vmware_soap_session` can enter the surfaced text — the only
secret-bearing string (the request body) never reaches the message, and
the response faultstring is server-generated. The redaction is
defense-in-depth on a surface that is not demonstrably reachable by a
secret. See WARNING-1 for the residual hardening gap.

### 7. Memory safety & resource hygiene
PASS. No new sessions/handles opened. `lastFaultString`/`licenseManager`/
`licenseAssignmentManager` are volatile scalar fields nulled in the
existing teardown (`VSphereClient.java:157`). `licenseAssignmentManager`
is cached once after first resolution — bounded. `conn.disconnect()` on
the existing `post()` path is unchanged. No per-cycle leak introduced.

### 8. Performance / API discipline
PASS. The `Config` SCSI alias reuses the **same** `ctrls` list already
read for the `Configuration` path (`VmCollector.java:141`) — no second
PropertyCollector round trip, no divergence (identical `friendlyType`/
count). Guest OS is a single added property walk per VM. Licensing adds
one lazy `licenseAssignmentManager` resolve (cached) + the existing
per-host `QueryAssignedLicenses`. No N+1 re-query introduced.

### 9. Build hygiene & minimal diff
PASS. See verification table. build_number bumped, matching CHANGELOG
line, minimal targeted diff.

### 10. Gap honesty
PASS. No control is silently mapped onto a non-existent field to inflate
coverage. Guest OS sources only the documented `guest.detailedData` keys
(others ignored, not faked). Foreign-resource event push remains an
explicitly named TOOLSET GAP (`HostCollector.java:135`). The `License
Expiration Date` PROP emits the literal string `"null"` on absence — see
NIT-1; it matches prod-verbatim parity and pushes no scored value.

## Registry check (knowledge/context/defects.md)

- **No open defect names `vcommunity` in its `Affects:` line.** Confirmed
  against the registry: DEF-001 (synology, open), DEF-002 (unifi, open),
  DEF-003 (synology, closed). **None affect this pak** — nothing to
  re-assert or propose closing for vcommunity.

## Findings

### WARNING-1 — `redactSecrets` does not cover the full DEF-001 token family
`[VCommunityVSphereClient.java:955 redactSecrets]` — knowledge/rules/no-secrets-on-disk.md;
`knowledge/lessons/synology-dsm-client-side-joins.md` (DEF-001 family). The redactor
covers `vmware_soap_session=` and `password=` only. The brief and the
DEF-001 lesson call out `_sid`, `passwd`, and `account` as part of the
same secret-in-path family. These tokens are **not currently reachable**
in this code path (the surfaced text is a server-authored vim25 fault, not
the client request — hence WARNING, not BLOCKING), but the backstop should
match the family it claims to defend so a future change that widens what
gets surfaced (e.g. echoing a request fragment) stays safe by default.
→ Smallest fix: extend the redaction regex to also strip `(?i)(_sid|passwd|account)\s*[=:]\s*\S+`.

## NITs

### NIT-1 — `License Expiration Date` / `License Key` / `Edition Key` emit literal `"null"`/`"Unknown"` strings on absence
`[HostCollector.java:144-150]` — these PROP values use the string `"null"`
(expiration) and `"Unknown"` (key/edition) sentinels rather than skipping
the key. Because this adapter has no scoring path, no rollup is corrupted,
and the author states prod emits them verbatim for parity — so this is
cosmetic only. Worth a future glance if parity tolerance allows skipping
the key instead (consistent with the `Remaining Days` skip idiom). Not a
correctness defect.

## If shipped as-is

An operator gets the 10 licensing keys, 6 Guest OS props (on any
Tools-reporting VM, Windows or not), and the `Config` SCSI alias, with no
silent false data; an unreachable/NXDOMAIN vCenter now turns the instance
**red with an actionable, secret-free message** instead of silent
green-empty. No secret is exposed on any reachable path. The only residual
is a redaction backstop narrower than the family it cites (WARNING-1) — a
defense-in-depth gap, not an active leak.

## Verdict

**APPROVE** — 0 BLOCKING, 1 WARNING, 1 NIT. The WARNING is a
defense-in-depth hardening on an unreachable surface and does not gate the
build; recommend the author fold the `_sid`/`passwd`/`account` redaction
into the same change as any future fault-surface widening. No registry
defect affects vcommunity.
