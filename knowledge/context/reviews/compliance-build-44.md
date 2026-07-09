# SDK Adapter Review — compliance build 44

- **Adapter:** `content/sdk-adapters/compliance` (repo commit `64b31ee`)
- **Build reviewed:** 44 (raw-SOAP inventory-enumeration regression fix + instrumentation)
- **Baseline:** build 43 (`dbb6df4`, APPROVEd in `compliance-build-43.md`)
- **Reviewer:** `sdk-adapter-reviewer`
- **Date:** 2026-06-10
- **Verdict:** APPROVE (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 2 NIT

Build 43 reviewed clean statically, then live devel testing exposed a defect a
static pass could not see: multi-`returnval` SOAP reads searched for `<returnval>`
as a *direct child* of the `<Envelope>` document element, but the returnvals nest
two levels deeper (`Envelope > Body > <op>Response`). Every ContainerView walk
returned an empty inventory with no fault and no parse error — "connects clean,
zero results." Build 44 is the fix plus SOAP-walk instrumentation. I scoped the
review to the 43→44 delta and verified the fix deeply, including a full audit of
every other response-parsing site for the same direct-vs-deep asymmetry.

## Claims check (re-run independently)

| Claim | Result |
|---|---|
| `validate-sdk` (compliance) clean | **CONFIRMED** — compiles 10 sources; one benign `-source 11` system-modules warning only. No deprecation note (the `Crypt`/`AmbientCredential` deprecation now lives in the framework jar, not adapter source). |
| `build-sdk` → `dist/vcfcf_sdk_compliance.1.0.0.44.pak` reproduces | **CONFIRMED** — reproduces; 311,450 bytes (vs 43's 310,303 — consistent with ~1 KB of added helper + instrumentation). `lib/` = `vcfcf-adapter-base.jar` only (C2 v2 shape preserved); aria-ops-core correctly auto-omitted. |
| `pak-compare` 44 vs 43 = 0/0/0 (author claim) | **CONFIRMED** — `pak-compare dist/...44.pak dist/...43.pak` → "No structural divergences found. 0 BLOCKING, 0 WARNING, 0 INFO." Matches the author's claim exactly. |
| Embedded framework jar carries the AmbientCredential fix | **CONFIRMED** — embedded `lib/vcfcf-adapter-base.jar` is **byte-identical (same sha256, `50e81c0c…`)** to the reference `vcfops_managementpacks/adapter_runtime/vcfcf-adapter-base.jar`. `AmbientCredential.class` constant pool contains the hard-wired default `/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties` and **no** `VCOPS` / `CommonConstants` string — the VCOPS-derived path is gone, as intended. |

All author claims verified with my own eyes.

## Scope of the delta (git diff `dbb6df4..64b31ee`)

Five files: `CHANGELOG.md`, `REFERENCE.md`, `adapter.yaml` (build_number 43→44),
`ComplianceAdapter.java`, `VSphereClient.java`. No other source touched.

## 1. The fix — deep-search returnval

**Both multi-`returnval` sites now deep-search.** `retrieveViewMembers` (VSphereClient.java:986)
and `queryOptions` (VSphereClient.java:350) both switched from
`childrenByLocalName(resp.getDocumentElement(), "returnval")` (direct child of the
Envelope — the bug) to the new `descendantsByLocalName(...)`. Confirmed in the diff.

**Full asymmetry audit — every `getDocumentElement()`-rooted returnval read is now
deep.** I traced all six response-root parse sites:

| Site | Reader | Search |
|---|---|---|
| :123 | RetrieveServiceContent | `firstByLocalName` (deep) — unchanged, already correct |
| :201 | CurrentTime keepalive | `firstByLocalName` (deep) — unchanged |
| :350 | QueryOptions | `descendantsByLocalName` (deep) — **fixed** |
| :840 | getRawPropertyElement (single-object props) | `firstByLocalName` (deep) — unchanged, this is what masked the bug |
| :937 | createContainerView | `firstByLocalName` (deep) — unchanged |
| :986 | retrieveViewMembers (inventory walk) | `descendantsByLocalName` (deep) — **fixed** |

No `childrenByLocalName(resp.getDocumentElement(), ...)` call remains anywhere. The
other `childrenByLocalName` call sites (`:568` over an already-unwrapped
`serviceInfo`, `:635`/`:682` over an already-unwrapped property element, `:844`
over an already-unwrapped `returnval`) are correctly *direct-child* — they parse the
children of an element that is itself already extracted, not the Envelope. No
remaining direct-vs-deep asymmetry.

**`descendantsByLocalName` is well-defined; no double-count.** It walks
`getElementsByTagName("*")` over the subtree and filters by `localName`. The
double-count concern (`returnval` inside `returnval`) does not arise in either real
shape: a RetrieveProperties `<returnval>` (ObjectContent) contains `<obj>` + one or
more `<propSet>` — never a nested `<returnval>`; a QueryOptions `<returnval>`
(OptionValue) contains `<key>` + `<value>` — never a nested `<returnval>`. So the
"flatten the whole subtree" approach returns exactly the N top-level returnvals.
Even if a stray deeper element existed, the consumer reads its payload via
`firstDirectChild(rv, "obj")` (:991) — direct-child-scoped, so a misnested match
could not corrupt the obj extraction. The helper's doc comment slightly oversells
("direct children first, then deeper" — the implementation is a single flat subtree
walk in document order), but the behavior is correct; see NIT-1.

**`localName` is namespace-prefix tolerant** (:1282): `getLocalName()` with a
`getTagName()`-prefix-strip fallback — matches `returnval` regardless of the
`soapenv:`/`vim25:` prefix or whether the parser is namespace-aware. Correct.

**Empty-walk WARN cannot fire spuriously on a legitimately-empty kind.** The
zero-result WARN exists *only* in `getHosts()` (VSphereClient.java:224) — "0
HostSystem" is illegitimate for any real vCenter. The VM/DVS/DVPG/cluster getters
log an INFO count only, no WARN — so a vCenter with zero DVS (legal) or zero DVPG
(legal) produces no false alarm. Scoping matches the brief exactly. (Minor: the DVS
fallback path — try `VmwareDistributedVirtualSwitch`, then base
`DistributedVirtualSwitch` — will emit one INFO "0 objectContent" line for the empty
first attempt even when the fallback succeeds; harmless, noted as NIT-2.)

## 2. Instrumentation — no PII, sane volume, NPE-safe

**No PII / credential leakage.** The new log lines carry: inventory counts
(`"N hosts"`, `"N VMs"`, …), the vim25 *type string* (a constant like `"HostSystem"`),
the per-RetrieveProperties objectContent count, and at DEBUG the first object's
`type` + MoRef `value` (e.g. `host-42` — a MOID, not a hostname, username, or
secret). No credential, token, vCenter FQDN, or user-identifying value appears in any
new line. RULE-008 (no secrets to logs) holds.

**Log volume sane at INFO.** One INFO per inventory kind (counts, not per-object) and
one INFO per RetrieveProperties call (`listView(type): -> N objectContent`). No
per-object INFO spam.

**DEBUG gating correct.** The first-object breadcrumb (:994) is guarded by
`refs.isEmpty() && log != null && log.isDebugEnabled()` — fires at most once per
walk and only when DEBUG is on.

**Nullable-Logger NPE-safe.** The constructor now takes a `Logger log` that may be
null (standalone/test use). Every new log call routes through the null-checking
wrappers `logInfo`/`logDebug`/`logWarn` (:96–98), and the one direct
`log.isDebugEnabled()` call is explicitly `log != null`-guarded. No new call can NPE
on a null logger. The 3-arg legacy constructor delegates to the 4-arg with
`log = null`, preserving the standalone contract.

## 3. onDescribe removal — covered by framework default, no dead refs

The removed `onDescribe()` override is genuinely covered by the framework default:
`javap -p com.vcfcf.adapter.spi.VcfCfAdapter` on the *current*
`vcfcf-adapter-base.jar` shows `public AdapterDescribe onDescribe();` present. The
removed body resolved `getAdapterDescribeFile(getAdapterKind(), "describe.xml")` +
`AdapterDescribe.make(is)`, and `getAdapterKind()` returns `"vcfcf_compliance"`, so
the framework default targets the identical conf path.

The removed imports (`AdapterDescribe`, `InputStream`, `Files`) leave **no dead
references**: a grep finds them only in the explanatory comment and a still-valid,
*unrelated* use of `getAdapterDescribeFile(...).getParent()` at
ComplianceAdapter.java:223 (the benchmark loader's conf-dir resolution — pre-existing,
returns a `Path`, does not need any of the removed imports). The clean compile
(validate-sdk green) is positive proof the imports were safely removable.

*Verification limit:* `javap -c` (full disassembly) of the base class returns empty
in this environment (the base's transitive SDK deps are not on the disassembly
classpath), so I could confirm the default's *signature* but not byte-compare its
*body* against the old override. The CHANGELOG cites base commit `750e0ee` as
byte-identical; the behavioral equivalence (describe.xml actually loads at runtime)
is a live concern for `qa-tester`, not a static gate. The static evidence (signature
match + clean compile + same conf path) supports the removal.

## 4. Build claims — re-run

See the Claims check table above. validate-sdk green, build-sdk reproduces the 44
pak, pak-compare 44-vs-43 is 0/0/0, and the embedded framework jar is byte-identical
to the reference runtime jar and carries the AmbientCredential VCOPS-path fix.

## 5. Scope discipline — ControlEvaluator and SSL untouched

`ControlEvaluator`: **0 changes** in the 43→44 diff (not in the changed-files list).
The unreadable-is-NOT-compliant scoring contract verified in build 43 is byte-for-byte
intact.

SSL trust: the only trust-related line in the diff is `this.sslFactory =
trustAllSslFactory();` — the existing assignment *relocated verbatim* into the new
4-arg constructor. No change to `trustAllSslFactory`, the `X509TrustManager`, or the
hostname verifier. The build-43 SSL-posture WARNING (trust-all on the vCenter SOAP
socket, ignoring `allowInsecure`) is unchanged — it remains a pre-existing latent
item, not a build-44 regression, and is out of scope for this delta.

## Findings

### NIT

- **NIT-1 [VSphereClient.java:1218–1234]** `descendantsByLocalName`'s doc comment
  says "direct children first … then any remaining deeper matches … without
  double-counting a direct child," but the implementation is a single flat
  `getElementsByTagName("*")` subtree walk (document order, no separate direct-child
  pass). Behavior is correct and double-count-free for the real vim25 shapes; only the
  comment is misleading. Tidy the comment in a future touch.

- **NIT-2 [VSphereClient.java:251–259]** The DVS fallback (`VmwareDistributedVirtualSwitch`
  then base `DistributedVirtualSwitch`) emits an INFO `listView(...): -> 0
  objectContent` line for the empty first attempt on every cycle in environments that
  expose only the base type. Harmless log noise; consider demoting the
  per-RetrieveProperties count line to DEBUG, or only INFO-logging the final resolved
  count.

## If shipped as-is

An operator who installs build 44 gets the build-43 framework-v2 adapter with the
inventory-enumeration regression fixed: ContainerView walks now return the real
host/VM/DVS/DVPG/cluster sets instead of silently empty, so compliance actually scores
the fleet on prod 9.1. The new INFO breadcrumbs let an operator confirm at a glance
that each inventory kind was enumerated (and a "0 HostSystem" WARN flags the failure
mode that previously hid), with no PII or secrets in the logs and no NPE risk from the
nullable logger. The metric tree, stat/property keys, MOID stitching identity, and
unreadable-is-NOT-compliant scoring are unchanged (pak-compare 0/0/0; ControlEvaluator
untouched). The remaining acceptance bar is the live golden comparison on devel —
`qa-tester` / the orchestrator's devel proof — which is where the onDescribe-default
and the actual non-empty inventory walk get their runtime confirmation. Nothing in
this static review blocks promotion to that step.

## Report
`knowledge/context/reviews/compliance-build-44.md`
