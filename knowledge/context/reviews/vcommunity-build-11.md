# vCommunity — build 11 review

- **Adapter:** `content/sdk-adapters/vcommunity`
- **Build reviewed:** 11 (`dist/vcfcf_sdk_vcommunity.1.0.0.11.pak`)
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-06-23
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 2 NIT

## Scope

Build 10 → 11. Per the brief and confirmed by source mtimes, the **only**
build-11 source change is `VmCollector.java` (mtime 2026-06-23). The other
three modified source files in the working tree — `GuestOpsClient.java`,
`VCommunityAdapter.java`, `VCommunityVSphereClient.java` (all mtime
2026-06-22) — are the *uncommitted* deltas of builds 8/9/10, already
reviewed in `vcommunity-build-{8,9,10}.md`. They are out of scope here.

> **Process note (NIT, not blocking):** the adapter repo HEAD is still at
> commit `bad8ad4` ("builds 4–7"). Builds 8, 9, 10, and 11 all live in the
> working tree as uncommitted changes — the pak artifacts and CHANGELOG
> entries exist but nothing was committed. A `git diff` against HEAD
> therefore shows builds 8–11 combined, which is misleading and would make
> any future bisect impossible. Before a `v*` tag is cut, these builds
> should be committed. This is the orchestrator/author's to action; it is
> not a correctness defect in build 11.

## Claims check

- **validate-sdk:** CONFIRMED clean. Independently re-ran
  `python3 -m vcfops_managementpacks validate-sdk content/sdk-adapters/vcommunity`
  — compiles 9 source files, only the benign `-source 11` system-modules
  `javac` warning. "OK: … valid Tier 2 SDK adapter project."
- **pak-compare vs build 10:** CONFIRMED, matches author exactly.
  `pak-compare dist/…11.pak dist/…10.pak` → **0 BLOCKING / 0 WARNING /
  0 INFO**, "No structural divergences found." The edit did not touch
  describe.xml / template / profiles / content — structure identical to
  build 10.

## What the diff does (verified)

The build-3 (`a5ef1c2`) resurrected SCSI pipe dual-emit is fully removed:

- `grep -rn '"vCommunity|Config|' src/` → **no matches** (exit 1). No live
  emit of the pipe form (`vCommunity|Config|SCSI Controllers|{bus}|Type`
  property or `…|Count` metric alias) survives anywhere in source. The
  pipe key now appears only inside an explanatory comment
  (`VmCollector.java:252`).
- The canonical colon-instanced form is intact and well-formed
  (`VmCollector.java:247,260`):
  - `vCommunity|Configuration|SCSI Controllers|Count` → `stats.put(…)`
    (a **metric**, matching upstream `with_metric` after `d4633a6`).
  - `vCommunity|Configuration|SCSI Controllers:{busNumber}|Type` →
    `props.put(…)` (a **property**).
  - Separators correct: `:` for the bus instance index, `|` for the
    sub-attribute.
- The replacement comment accurately cites upstream `d4633a6` (2025-11-20)
  retiring the pipe form. Verifiable rationale, not a vibes claim.

## Failure-mode lenses (changed path only)

1. **Unreadable-is-NOT-compliant** (skill § *Unreadable is NOT
   compliant*): PASS for this diff. `vmScsiControllers`
   (`VCommunityVSphereClient.java:680`) returns an empty list when
   `config.hardware` is unreadable (`hw == null → return out`), never a
   sentinel. The `Count` metric is an inventory descriptor pushed onto a
   foreign VMWARE VM — not a compliance score that folds into a pass/fail
   or a fleet average — so a `0` Count is not an unreadable-as-pass
   violation. *(Pre-existing observation, NOT a build-11 finding: a `0`
   Count cannot be distinguished from "hardware config unreadable." This
   is unchanged build-10 behavior and outside this diff's scope; noted for
   completeness only.)*
2. **Reflection-tolerant vim25 reads** (skill § *vim25 over JAX-WS*): PASS.
   `vmScsiControllers` walks `config.hardware.device` as XML elements and
   selects controllers by **`xsi:type` string match** (`friendlyScsiType`,
   line 695) — no cast to a concrete vim25 subclass, no `getX()`/`isX()`
   assumption. A missing `busNumber` degrades to `"unknown"` (line 690),
   so the `props.put` string-concat at `VmCollector.java:260` cannot NPE.
3. **Crash-the-cycle / exception granularity:** PASS. The SCSI read runs
   inside `collectConfig`, inside the per-VM `try/catch` at
   `VmCollector.java:176–197`. A single VM's SCSI read failure is logged
   at WARN with VM-name context (line 195) and isolated — it cannot abort
   the collection cycle.
4. **Stitch corruption / MOID trap** (skill § *ARIA_OPS stitching
   identity*; `lessons/stitch-moid-not-unique-across-vcenters.md`): not in
   this diff. `VCommunityStitcher` (untouched, mtime 06-10) scopes the
   VMWARE MOID match by `VMEntityVCID` (vCenter Instance UUID), not bare
   MOID — already correct. No change in build 11.
5. **Secrets in logs** (`rules/no-secrets-on-disk.md`): PASS. The only log
   line on the changed path (`VmCollector.java:195`) emits VM name +
   exception class/message — no credentials.

## describe.xml note (brief item 4)

The brief asked whether describe.xml still declares a "SCSI Controllers"
instanced group + Type/Count attributes. It does **not** — and that is
correct by design, not a gap. vCommunity is an ARIA_OPS stitching adapter:
the SCSI keys are pushed onto the **foreign VMWARE VirtualMachine**
resource via `VCommunityStitcher.pushProperties/pushStats`
(`VmCollector.java:191–192`), not onto a native kind. describe.xml only
declares this adapter's own kinds (`vcfcf_vcommunity`, `vCommunityWorld`).
Stitched foreign keys do not require a native describe home. The kept keys
have a valid landing spot. No finding.

## Registry check (`context/defects.md`)

No open defect's `Affects:` names `vcommunity`. DEF-001 (synology),
DEF-002 (unifi), DEF-003 (synology, closed) — none affect this pak.
**Nothing to re-assert.**

No new WARNING-or-worse finding in this build → nothing to register per
RULE-012.

## NITs

- **Uncommitted build history.** Builds 8–11 are all uncommitted on top of
  the "builds 4–7" HEAD. Commit before tagging (see Scope note). Owner:
  orchestrator/author.
- **`Count == 0` ambiguity** in `vmScsiControllers` (empty-on-unreadable
  vs genuinely-zero). Pre-existing, out of this diff's scope; harmless for
  an inventory descriptor. Flagged only so it is on record.

## If shipped as-is

An operator sees the SCSI controller Type/Count exactly once per VM under
the canonical `Configuration|SCSI Controllers…` keys, matching current
upstream — the duplicate frozen-ghost `Config|` pipe keys from build 3 are
gone. No behavior regression, no structural change vs build 10.
