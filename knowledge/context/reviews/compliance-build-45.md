# SDK Adapter Review — compliance build 45

- **Adapter:** `content/sdk-adapters/compliance` (repo commit `0542c24`)
- **Build reviewed:** 45 (constructor-stored adapter-kind adoption — fixes build-44 install NPE)
- **Baseline:** build 44 (`64b31ee`, APPROVEd in `compliance-build-44.md`)
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-06-10
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 0 NIT

**Scoped delta review.** Build 44 reviewed clean statically (0/0/2-NIT) but
failed install 3/3 on devel: the framework-default `onDescribe()` NPE'd because
the controller instantiates `ComplianceAdapter` BARE via no-arg reflection at
install/describe time, before any platform injection, so `getAdapterKind()` is
null. Framework commit `1fa1e4b` added constructor-stored-kind constructors;
build 45 is the 2-line adapter adoption. I did **not** re-review build-44
collection content (SOAP fix / instrumentation / stitcher) — pak-compare proves
it byte-unchanged; see `compliance-build-44.md`.

## Claims check (re-run independently)

| Claim | Result |
|---|---|
| 44→45 diff is exactly constructor adoption + version bump + changelog/reference docs, no other source drift | **CONFIRMED** — `git diff 64b31ee 0542c24 --numstat`: 4 files only — `CHANGELOG.md` (+4), `REFERENCE.md` (1/1, build-string bump), `adapter.yaml` (build_number 44→45), `ComplianceAdapter.java` (10/7). The Java delta is `super()`→`super(ADAPTER_KIND)`, `super(adapterDir, instanceId)`→`super(ADAPTER_KIND, adapterDir, instanceId)`, and an updated `onDescribe`-removed comment. `ADAPTER_KIND = "vcfcf_compliance"` is a pre-existing constant (line 54), not introduced here. No collection-path source touched. |
| Framework `onDescribe()` resolves `vcfcf_compliance` under bare `new ComplianceAdapter()` with no injected state | **CONFIRMED** — `VcfCfAdapter.onDescribe()` (factory `1fa1e4b`, lines 395–423) resolves kind: (1) constructor-stored `adapterKindKey`, (2) fallback `getAdapterKind()`, (3) if both null throws an **actionable** `RuntimeException` listing both sources. Never reaches `getAdapterDescribeFile(null, …)`, never NPEs, never silently returns null. Under bare instantiation the no-arg ctor calls `super(ADAPTER_KIND)` → `adapterKindKey="vcfcf_compliance"` is set before any injection → resolves via path (1). Skeptic default satisfied: the describe failure mode now surfaces loudly (throw with fix instructions), it does not pass silently. |
| Assembled describe path matches pak layout | **CONFIRMED** — `onDescribe()` calls `getAdapterDescribeFile("vcfcf_compliance", "describe.xml")` → `<adaptersHome>/vcfcf_compliance/conf/describe.xml`. The 45 pak's `adapters.zip` contains exactly `vcfcf_compliance/conf/describe.xml`. The triple `ADAPTER_KIND` / describe.xml `<AdapterKind key>` / pak dir name all = `vcfcf_compliance` (verified). |
| Embedded framework jar is the CURRENT rebuilt one (carries the new constructors), not stale pre-`1fa1e4b` | **CONFIRMED** — `javap -p` on the pak-embedded `vcfcf_compliance/lib/vcfcf-adapter-base.jar` shows all four constructors incl. the two new keyed ones: `protected VcfCfAdapter(String)` and `protected VcfCfAdapter(String, String, Integer)`. sha256 `65ca9523…` is **byte-identical** to the reference `vcfops_managementpacks/adapter_runtime/vcfcf-adapter-base.jar` and **differs** from the build-44 jar (`50e81c0c…` per `compliance-build-44.md`) — i.e. it is a newer, correctly-rebuilt jar. The shipped `vcfcf_compliance.jar`'s no-arg `ComplianceAdapter()` disassembles to `ldc "vcfcf_compliance"` before the super call — the keyed `super(ADAPTER_KIND)` is in the actual shipped bytecode, not just source. `version.txt` = `Implementation-Version=0.45`. |
| `pak-compare` 45 vs 44 = 0/0/0 (author claim) | **CONFIRMED** — re-ran: "No structural divergences found. 0 BLOCKING, 0 WARNING, 0 INFO." |
| `validate-sdk` clean (author claim) | **CONFIRMED** — re-ran: compiles 10 sources, only the benign `-source 11` system-modules warning. "OK: … is a valid Tier 2 SDK adapter project." |

All author claims verified with my own eyes. I did not run `build-sdk` (the 45
pak already present in `dist/` is the binary under review, and avoiding the run
sidesteps the CHANGELOG/REFERENCE clobber). Compliance working tree left clean
(`git status --short` empty).

## Review-dimension notes (delta only)

- **Dim 1 (unreadable is NOT compliant) / Dim 2/3 (no crash-the-cycle, no
  swallowed failure):** This delta concerns the install-time describe path, not
  the collect read path. The previously-approved scoring/ControlEvaluator
  contract is untouched (pak-compare 0/0/0). The new framework resolution chain
  *improves* the failure posture: an unresolvable kind now throws an actionable
  message rather than NPE-aborting the install task. No path where a failed read
  becomes a pass was introduced.
- **Dim 9 (build hygiene / minimal diff):** `build_number` bumped 44→45 in
  `adapter.yaml`; matching `CHANGELOG.md` entry present and accurate; diff is
  minimal (2 functional lines + comment + docs). No drive-by refactor.
- **Dim 5 (MOID stitching), Dim 6 (logging/secrets), Dim 7 (resource hygiene):**
  no change in this delta; covered by `compliance-build-44.md`.

## If shipped as-is

An operator who installs build 45 gets the build-44 collection adapter (SOAP
inventory fix, instrumentation, stitcher — all byte-unchanged per pak-compare)
with the install-time NPE fixed: the controller's bare no-arg describe call now
resolves `describe.xml` from the constructor-stored kind key instead of
dereferencing a null `getAdapterKind()`, so the pak installs cleanly instead of
failing the `DistributedTaskInstallUninstallAdapters` task. If the kind ever
became unresolvable (e.g. a future adapter that forgets `super(ADAPTER_KIND)`),
the operator would see an actionable error naming the fix, never a silent NPE.
The remaining acceptance bar is the live devel install + golden-collection proof
(`qa-tester` / orchestrator devel proof) — nothing in this static review blocks
promotion to that step.

## Report
`knowledge/context/reviews/compliance-build-45.md`
