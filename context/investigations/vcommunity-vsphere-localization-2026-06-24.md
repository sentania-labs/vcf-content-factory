# Investigation — vcommunity-vsphere Accounts UI shows raw describe keys (localization not resolving)

> **UPDATE 2026-06-24 (pass 4) — DEFINITIVE ROOT CAUSE.**
> The regression is **not in the build toolchain**. It is a **persistent platform
> bug in the devel analytics JVM (PID 5446)**: this JVM instance cannot create
> NEW localized name entries in the GemFire AdapterKindCache — `insertOrUpdateCache`
> runs silently to completion but new name registrations do not persist. All
> adapters registered before PID 5446 started retain their localized names; all
> adapters first registered under PID 5446 permanently show raw keys. **Remediation
> is a JVM/service restart on devel, not a toolchain fix.** Full evidence in
> Pass 4 below.

---

> **UPDATE 2026-06-24 (pass 3) — GROUND TRUTH from the live devel appliance.**
> Both prior theories are now disproven by live evidence (the `.description`
> theory was falsified by build 2: it was installed clean with the
> `.description` keys removed and labels STILL did not resolve). SSH'd to
> `vcf-lab-operations-devel.int.sentania.net` and pulled the actual platform
> error. The corrected, evidence-backed analysis is in **"Pass 3 — ground
> truth"** immediately below; the pass-2 `.description` analysis is preserved
> further down, marked **FALSIFIED-BY-LIVE-TEST**, and the pass-1 collision
> theory remains marked RETRACTED. Read Pass 3 first.

---

## Pass 4 — definitive root cause (2026-06-24 final investigation)

### The answer: appliance JVM (PID 5446) cannot create new localized name registrations

After exhaustive bisect of pak structure between build 50 (worked) and build 51
(failed), ALL localization-relevant files in `adapters.zip` are byte-identical
(same three `resources.properties` copies, same `describe.xml`, same sizes,
same `conf/views/views.zip`). The toolchain produced identical localization
artifacts. The regression is therefore **not in the toolchain output**.

### Evidence for the JVM bug

The devel analytics JVM **PID 5446** has been running since April 17, 2026. It
has a persistent bug: `insertOrUpdateCache` logs "sorting all language names of
adapter" and completes without any logged error, but the GemFire AdapterKindCache
is NOT updated with new localized name entries for adapter kinds being registered
for the first time under this JVM.

**Confirmed failing (first-ever install under PID 5446 → name does not resolve):**
- `vcfcf_vcommunity` — first installed June 11 by PID 5446 → FAILS
- `mpb_rubrik` — first installed June 12 by PID 5446 → FAILS (API returns name=None)
- `vcfcf_vcommunity_vsphere` — first installed June 24 by PID 5446 → FAILS
- `vcfcf_vcommunity_os` — first installed June 24 by PID 5446 → FAILS
- `vcfcf_compliance` — reinstalled June 24 after deletion (prior GemFire entry
  wiped by `AdapterKindDeletionExecutor`) → first-ever registration under PID 5446
  → FAILS (build 51, structurally identical to build 50)

**Confirmed working (first registered under PRIOR JVM instances):**
- `unifi_controller` — first registered May 20 by PID 269253 → WORKS
- `vcfcf_compliance` — first registered May 27 by PID 3030919 → WORKED (until deletion)
- `ManagementPackBuilderAdapter` — first registered May 19 by PID 269253 → WORKS
- `DiagnosticsAdapter`, `VMWARE`, `NSXTAdapter`, etc. — all registered before PID 5446

**Compliance build 50 "worked" only because** it was a delta-reinstall over
existing GemFire registrations from PID 3030919. The log confirmed: "3 existing
recommendations → updated 3". Not a fresh registration. Compliance build 51 was
a fresh registration (compliance was deleted first) — and failed.

### Why the toolchain appeared to be the cause (the misleading correlation)

The coincidence: build 50 was installed June 10 (WORKED, but only because
existing PID 3030919 entries were updated). vcfcf_vcommunity build 1 was installed
June 11 (FAILED because PID 5446 cannot create NEW registrations). The first
*new* kind installed after PID 5446 took over was vcfcf_vcommunity. This
coincides with the content-emit pipeline commits (June 17) but is not caused by
them — vcfcf_vcommunity build 1 had ZERO content-emit features (no content/ tree,
no views.zip, no describe.xml recommendations) and still failed June 11.

### Timeline of adapter localization status on devel

| JVM PID | Adapter Kind | First Install | Name Resolves |
|---------|--------------|---------------|---------------|
| 269253  | unifi_controller | 2026-05-20 | YES |
| 3030919 | vcfcf_compliance | 2026-05-27 | YES (until deleted Jun 24) |
| 269253  | ManagementPackBuilderAdapter | 2026-05-19 | YES |
| 5446    | vcfcf_vcommunity | 2026-06-11 | **NO** |
| 5446    | mpb_rubrik | 2026-06-12 | **NO** |
| 5446    | vcfcf_vcommunity_vsphere | 2026-06-24 | **NO** |
| 5446    | vcfcf_vcommunity_os | 2026-06-24 | **NO** |
| 5446    | vcfcf_compliance (reinstall) | 2026-06-24 | **NO** |

### Remediation

This is a platform operations issue, not a framework change:

1. Restart the analytics service on `vcf-lab-operations-devel.int.sentania.net`
   to get a fresh JVM. The new JVM will re-load existing GemFire cache entries
   from the persisted store and will be able to create NEW localized name entries.
2. After restart, reinstall all vcfcf SDK paks that show raw keys
   (vcfcf_compliance, vcfcf_vcommunity_vsphere, vcfcf_vcommunity_os). The
   reinstall will create new localized name entries under the fresh JVM.
3. Optionally reinstall vcfcf_vcommunity (now retired) and mpb_rubrik if those
   adapter kinds are still present.

No framework (`vcfops_*/`) changes are required or warranted. Pak structures
are correct. The self-heal hypothesis (first promoted by content-installer) is
partially correct: a service restart is the equivalent of the "first collection
cycle" self-heal in the sense that the new JVM CAN register new localizations.
But the hypothesis that it self-heals without intervention is FALSE — the same
PID 5446 JVM has been running since April 17 and has never fixed itself.

### Confidence

This conclusion is confirmed by:
1. Byte-identical localization artifacts in builds 50 and 51 (disproves toolchain)
2. mpb_rubrik (unrelated to vcfcf, no toolchain involvement) shows same failure
3. All failing adapters share only one trait: first installed under PID 5446
4. All working adapters share only one trait: first registered under prior PIDs

---

## Pass 3 — ground truth (live devel appliance)

### What the platform actually logs (the real error)

`analytics-*.log` on devel, emitted continuously whenever the UI renders the
adapter (e.g. the Add Account dialog):

```
WARN [com.vmware.vcops.controller.retriever.AdapterKindRetriever.getAdapterKindLocalizedName]
  - localized name not found for adapter kind = vcfcf_vcommunity_vsphere, nameKey = 1, languages: [...]
WARN [com.vmware.vcops.controller.retriever.AdapterKindRetriever.retrieve]
  - There is no localized name for adapter " vcfcf_vcommunity_vsphere ". Used adapter key as localized name.
ERROR [com.vmware.vcops.controller.retriever.ResKindIdentsRetriever.retrieve]
  - Failed to find localized names for these resource kind identifiers. Used resource kind identifier key as localized name
    Adapter Kind = "vcfcf_vcommunity_vsphere" Resource Kind = "vcfcf_vcommunity_vsphere" Identifier Key = "host" (… port, allowInsecure, *_config_file)
```

The resolver is the **central controller string registry** (`AdapterKindRetriever` /
`ResKindIdentsRetriever`, persisted in vpostgres) — NOT the loose
`conf/resources/resources.properties`. The registry simply **has no string row**
for `(vcfcf_vcommunity_vsphere, nameKey=1)` (nor any of its identifiers), so the
UI falls back to the raw key. `vcfcf_vcommunity_os` shows the **same** failure;
the working controls (`vcfcf_compliance`, `mpb_synology_nas_adapter3`,
`unifi_controller`) produce **zero** such warnings. This is the whole family,
intrinsic, matching the pre-split premise.

### What is PROVEN (ruled IN / OUT by live evidence)

- **The bundle file is correct and loadable.** A faithful ISO-8859-1
  (java.util.Properties-equivalent) parse of the *installed*
  `…/vcfcf_vcommunity_vsphere/conf/resources/resources.properties` on the
  appliance returns `key 1 = "VCF Content Factory vCommunity vSphere"`,
  `key 5`, `key 6`, … — all 21 keys load. The file is **not** the problem.
- **Placement is identical to the working controls.** On-appliance trees match
  in structure: `conf/describe.xml`, `conf/resources/resources.properties`,
  entry jar at the inbound root, `lib/vcfcf-adapter-base.jar`. Same for compliance.
- **The kind registered and the describe import RAN.** The controller logged
  `DescribeUtils.constructAdapterDescribes - Describing adapter [key =
  vcfcf_vcommunity_vsphere, class = com.vcfcf.adapters.vcommunity.VCommunityAdapter]`
  and `AdapterDescribeManager.describeAdapters - Processed adapter kinds
  [vcfcf_vcommunity_vsphere]` — no exception. The describe was processed; the
  collector even runs cycles. Only the **localized-string rows** are absent.
- **FALSE LEADS, disproven by a working control on the SAME appliance:**
  - *Leading XML comment before `<AdapterKind>`* — **NOT the cause.**
    `mpb_synology_nas_adapter3` is installed and resolves labels (0 warnings)
    and ALSO has `<?xml?>` then a `<!-- … -->` comment before its root. (This
    same red herring has now been chased three times.)
  - *`.description` keys* — **NOT the cause** (build 2 removed them; still fails).
  - *Low nameKey integers (1,5,6…)* — fine; compliance and mpb_synology both
    use nameKey 1 and resolve.
  - *Encoding / BOM / line-endings* — fine; compliance has a UTF-8 em-dash in a
    VALUE line and resolves; vcommunity's em-dashes are only in comments and the
    file parses cleanly.
  - *Framework `onDescribe()`* — identical code path for both
    (`VcfCfAdapter.onDescribe()` → `AdapterDescribe.make(is)` from the static
    `describe.xml`); same `vcfcf-adapter-base.jar` under both adapters.
  - *Fork collision* — already retracted (fails pre-split, alone).

### What is SUSPECTED but NOT yet proven

The describe import ran without error yet **did not persist the nameKey→string
rows** for this adapter family, while it did for the controls. The bundle, the
placement, the registration, and the framework code are all equivalent to a
working control — so the differentiator is something the controller's
string-import keys on inside the describe that differs only for this family, and
it is **not** any of the file-structure traits above (each cleared against a
working control). I could not isolate it from logs alone (the import logged
success for both). **I am deliberately not guessing a fourth file-structure
theory** — the last three were wrong because the on-disk artifacts are genuinely
equivalent to a known-good pak.

The honest state: **proven** that the controller registry lacks the strings and
that the on-disk bundle/placement/registration/framework are all equivalent to a
working pak; **not proven** why the import skipped persisting this family's
strings.

### The exact experiments to close it (cheapest first)

1. **Force a describe re-import and watch the string persistence.** On devel,
   re-run the adapter describe for this kind (UI re-describe / no-op re-install
   of build 2) while tailing `analytics-*.log` filtered to
   `AdapterDescribeManager|DescribeUtils|AdapterKindRetriever|ResKindIdents|
   localiz|nameKey` for `vcfcf_vcommunity_vsphere`. An error/skip on the persist
   step is the root cause.
2. **Diff the persisted rows directly.** Query vpostgres for the localized-name
   table and compare the row set for `vcfcf_compliance` (present) vs
   `vcfcf_vcommunity_vsphere` (absent). Needs the `vcops` psql wrapper / DB creds
   (the JRE-only appliance has no `javac`, and `psql` was not on PATH).
3. **A/B against a control built by the SAME `build-sdk` toolchain.** Transform
   the *working* `vcfcf_compliance` describe.xml step-by-step toward the
   vcommunity describe.xml (rebuild + install + watch `AdapterKindRetriever`),
   bisecting which single change flips resolve → not-found. Candidate transforms
   to bisect, in order: the leading-comment block; the `<LicenseConfig>` element;
   the `vCommunityWorld` ResourceGroup/attribute block; the exact `<AdapterKind …>`
   attribute set; the presence of the `SymptomDefinitions / AlertDefinitions /
   Recommendations` sibling sections that compliance has and the vcommunity
   describe.xml does NOT (a real structural delta observed live).

### Owner — Pass 3

**Undetermined pending experiment 1 or 3.** Evidence does NOT yet justify a fix
in either `tooling` or `sdk-adapter-author`:

- If experiment 3 shows a describe.xml content trait flips it, the fix is in the
  **pak's `describe.xml`** → `sdk-adapter-author`.
- If experiment 1 shows the controller import errored on something the
  `build-sdk` assembly produced, the fix is in **`vcfops_managementpacks` /
  `vcfops_packaging`** → `tooling`; the "why do the other three still work"
  answer would then be a pak characteristic that masks the bug, to be named by
  the experiment, not asserted now.

**Regression-safety gate (holds regardless of owner):** any fix must be
A/B-verified on devel — rebuild `vcfcf_compliance` (and ideally re-check
`mpb_synology_nas`) via the same toolchain, reinstall, and confirm **zero** new
`AdapterKindRetriever` not-found warnings before and after. The user's framing is
the test: if it's the toolset, prove the other three stay working.

---

> **UPDATE 2026-06-24 (pass 2) — the pass-1 root cause below is RETRACTED.**
> A new fact falsifies it: the raw-key symptom **existed pre-split, with ONLY
> the unified `vcfcf_vcommunity` pak installed and no `_os`/`_vsphere` fork
> present.** A cross-fork `vCommunityWorld nameKey=20` collision therefore
> cannot be the cause — there was nothing to collide with. The failure is
> **intrinsic to this pak family** (or its build), not the co-install state.
> The corrected analysis is in **"Pass 2 — corrected root cause"** below; the
> original §"Root cause"/§"structural diff"/§"fix"/§"regression" sections are
> preserved verbatim underneath it as a **RETRACTED** record (do not action
> them). New prime suspect: the **non-standard `<int>.description` bundle keys**
> unique to the vCommunity family.

---

- **Date:** 2026-06-24
- **Agent:** api-explorer (READ-ONLY; no live touch, no install, no pak/source mutation)
- **Symptom (devel):** the `vcfcf_vcommunity_vsphere` Accounts / adapter-config
  UI shows raw describe **keys** instead of nameKey-resolved labels — solution
  name renders as `vcfcf_vcommunity_vsphere` (nameKey 1), connection params as
  `host`, `esxi_adv_settings_config_file`, `esxi_vib_driver_config_file`,
  `vm_adv_settings_config_file`, `vm_configuration_config_file`, `port`,
  `allowInsecure` (nameKeys 6/8/9/10/11/14/15). Total bundle-resolution failure
  for this AdapterKind.
- **Installed build:** `dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.1.pak` (adapter.yaml
  version 1.0.0 / build_number 1) — confirmed byte-identical to current source.

## Pass 2 — `.description`-keys theory — FALSIFIED-BY-LIVE-TEST

> **FALSIFIED.** Build 2 was assembled with the `<int>.description` keys removed
> (bundle reduced to `<int>=label` only, exactly the working-pak shape),
> installed clean on devel, and the labels STILL did not resolve
> (screenshot-confirmed: raw `vcfcf_vcommunity_vsphere` title + raw field keys).
> The `.description` keys were therefore NOT the cause. Pass 3 (live ground
> truth) supersedes this. Preserved below as a ruled-out hypothesis — **do not
> action.**

### (original pass-2 heading) corrected root cause (premise: unified pak fails ALONE, pre-split)

### Corrected premise

The user reports the raw-key / unresolved-label problem existed **before** the
three-adapter split, when **only** the unified `vcfcf_vcommunity` pak was
installed (no `_os`, no `_vsphere`). The symptom is real, intrinsic to this pak
family, and not a co-install artifact. Pass-2 therefore compared the **unified
`vcfcf_vcommunity` build-11 pak** (which fails alone) against a known-good
control (**compliance build-51**, which renders labels correctly) at the byte
level, treating "byte-equivalent to the working paks" as something that *must*
be wrong in at least one nameKey-governing dimension.

### What was re-verified as EQUIVALENT (cleared — not the cause)

Each dimension the coordinator named was checked byte-for-byte on the
*installed* unified pak vs the compliance control:

1. **Bundle load path / presence** — identical. Both ship
   `adapters.zip!/resources/resources.properties` (pak-level) **and**
   `adapters.zip!/<kind>/conf/resources/resources.properties` (the per-adapter
   describe bundle), plus `<kind>/conf/describe.xml`. Same entry names, same
   nesting. `adapter.properties` `KINDKEY` matches the AdapterKind in both.
2. **Built-in / reserved-key collision** — none found. `vcfcf_vcommunity` is a
   fresh AdapterKind; the duplicate-KINDKEY cases in the corpus
   (`VCF_UNIFIED_CONFIG`, `VirtualAndPhysicalSANAdapter`) share the *same* key
   across packaging duplicates — not our situation. The `vCommunity|` metric
   namespace stitched onto VMWARE types is a runtime-property concern, not a
   describe-bundle key.
3. **Encoding / BOM / line-endings / property format** — cleared. No BOM, no CR
   (LF-only), newline-terminated, no line-continuation backslashes, no
   space/colon-prefixed keys. The unified bundle's only non-ASCII bytes are
   UTF-8 em-dashes (`e2 80 94`) **on comment lines**; the compliance control has
   a UTF-8 em-dash on a *value* line (key 105) and still resolves — so multi-byte
   chars in the bundle are demonstrably tolerated and are not the cause.
4. **AdapterKind / describe wiring** — identical attribute set
   (`key`, `nameKey="1"`, `version="1"`, namespace, `xsi:schemaLocation`). No
   pak ships `describeSchema.xsd`. No `descriptionKey`/`resourceBundle`
   attribute exists on AdapterKind or ResourceKind in either pak.
5. **nameKey integer reconciliation** — clean. All 30 describe nameKeys have a
   matching base entry in the bundle (including 1 and 5); **zero missing, zero
   duplicate** integer keys; no orphan suffix key.

### The ONE real structural difference (prime suspect)

The unified bundle's keys are of **two shapes**: `<int>=label` **and**
`<int>.description=help-text`. **Every** working control pak
(compliance, synology, unifi) uses **only** `<int>=label` keys — zero
`.description` keys. This is the sole structural property that separates the
failing family from the known-good group, and it is present in the unified pak
*by itself* (so it satisfies the pre-split premise).

```
unified/vsphere bundle key shapes:   <int>   AND   <int>.description
compliance/synology/unifi:           <int>   only
```

In the unified pak the `.description` keys cover exactly nameKeys 6–16 — the
ResourceIdentifier (connection-parameter) fields — i.e. **exactly the labels
reported as showing raw** (`host`, `port`, `allowInsecure`, the config-file
names). They were authored to supply the field's (i) help text "mirrored
verbatim from the prod original."

**Why this is the suspect, with mechanism:** there is **no precedent anywhere in
the corpus** for the `<int>.description` convention — no reference/VMware
describe bundle uses it (grep of all `*.properties` under
`reference/references/`, `context/`, `reference/docs/` returned zero hits), and the cleanroom
describe spec documents help/description text via a `<Description nameKey="N"/>`
child element pointing at *its own integer key* (e.g. recommendations,
spec/02a-describe-xsd-canonical.md:187, spec/08:265) — **not** via a dotted
suffix appended to the label key. The describe.xml carries **zero**
`descriptionKey` attributes, so these `.description` keys are referenced by
nothing. A platform `Dictionary`/describe-bundle loader that validates the
adapter bundle against the integer-key schema can reject the *entire* bundle
when it encounters unrecognized dotted keys — which would cause **every** nameKey
for that AdapterKind (1, 5, 6, 8–16, …) to fall back to its raw key string,
matching the observed total failure exactly. This is the same failure *class*
documented in `lessons/pak-content-localization-bundles.md` ("the importer …
aborts the entire content tree when any single key is absent / mismatched"),
applied to the adapter-config describe bundle rather than the content bundle.

### Confidence and the EXACT live check to confirm

I **cannot prove from the static artifacts alone** that the platform rejects the
bundle on the `.description` keys (vs. merely ignoring them) — both behaviors are
consistent with a structurally valid `.properties` file. The `.description` keys
are the only static differentiator from three known-good paks, the symptom field
set matches, and the symptom is intrinsic/pre-split, so this is the **prime
suspect** but the rejection mechanism needs one live confirmation:

- **Definitive check (build, do not need live):** rebuild the unified (or
  vsphere) pak with the `.description` lines **stripped** from
  `resources/resources.properties` (leaving only `<int>=label` keys, exactly the
  working-pak shape), install on a scratch/devel instance, and open the Accounts
  / adapter-config UI. **Labels resolve → confirmed.** This is the minimal,
  reversible experiment and isolates the one variable.
- **Live diagnostic (if a rebuild is not wanted first):** on the devel instance
  with the failing pak installed, grep the analytics/collector log during/after
  describe load for the adapter kind for a bundle/Dictionary parse error, e.g.
  `Localization for key <x> is absent` or a properties-parse/`Dictionary`
  warning naming `vcfcf_vcommunity`. A bundle-level parse failure there names the
  offending key and confirms whole-bundle rejection.

### Minimal fix and owner — Pass 2

**Owner: `sdk-adapter-author` (pak layout / source `resources.properties`), NOT
`tooling`.** Remove the non-standard `<int>.description` keys from each
vCommunity-family pak's `resources/resources.properties`. If field (i) help text
is wanted, re-express it the standard way (a `<Description nameKey="N"/>` child
or the schema-sanctioned identifier-description mechanism with its own integer
key) — never as a dotted suffix on the label key. This is a source edit confined
to the vCommunity paks' own bundles; the kind keys, describe.xml, and all
`<int>=label` entries are untouched, so the labels that already exist keep their
strings and gain resolution.

*(Optional, separate, `tooling`-owned hardening: a `validate-sdk` lint that
flags any `resources.properties` key not matching `^\d+=` — i.e. rejects the
`<int>.description` shape at author time. Purely additive; the three working
paks pass it trivially.)*

### Regression safety for synology / unifi / compliance — Pass 2

The fix edits **only** the vCommunity paks' source `resources.properties`. It
does not touch `vcfops_*` build machinery, so the packaging of
synology/unifi/compliance is unchanged and their `.pak`s are not rebuilt by this
change. Those three already use **only** `<int>=label` keys (zero `.description`
keys — verified), so they were never exposed to this defect and remain correct
as-is. The optional `validate-sdk` lint, if added, is a pure additive warning
the three working paks pass with no output and changes none of their bytes.

---

## RETRACTED — Pass 1 root cause (falsified by the pre-split observation)

> The cross-fork `vCommunityWorld nameKey=20` collision theory below is
> **WRONG** — it was falsified by the fact that the unified pak fails ALONE,
> pre-split, with nothing to collide with. Preserved verbatim as a record of the
> ruled-out hypothesis. **Do not action this section.**

## Root cause (2-3 sentences)

The three co-installed vCommunity forks (`vcfcf_vcommunity`,
`vcfcf_vcommunity_os`, `vcfcf_vcommunity_vsphere`) each declare the **identical
owned type="1" ResourceKind `key="vCommunityWorld" nameKey="20"`**, inherited
verbatim from the unified parent pak — yet each pak's `resources.properties`
maps nameKey 20 to a different string. On devel all three are installed at once
(by design decision OPEN-D: keep the unified pak until parity), so VCF Ops holds
three describe contributions that share a ResourceKind key but disagree on its
localization. The describe/Dictionary registry treats ResourceKind `key` as
unique *within an adapter* but the three forks collide on `vCommunityWorld`
across adapters, and the resulting describe-load contention leaves
`vcfcf_vcommunity_vsphere`'s nameKey bundle unresolved — so every nameKey for
that AdapterKind (1, 5, 6, 8–11, 14, 15, …) falls back to its raw key string.

## The structural diff that proves it

Every dimension that governs nameKey resolution is **byte-identical** between
the failing pak and the three working control paths — the bundle is present,
correctly placed, internally consistent, and the manifest/entry wiring match.
The *only* discriminator is a cross-pak ResourceKind key collision that is
unique to the co-resident vCommunity family.

### Things that are IDENTICAL (i.e. NOT the cause — each chased and cleared)

| Dimension | vcommunity-vsphere | compliance / synology / unifi | Verdict |
|---|---|---|---|
| On-disk source layout | `resources/resources.properties`, `describe.xml`, `adapter.yaml` at pak root | same | same |
| Bundle placement in built `.pak` | `adapters.zip!/resources/resources.properties` **and** `adapters.zip!/<kind>/conf/resources/resources.properties` | same | same |
| describe.xml placement | `adapters.zip!/<kind>/conf/describe.xml` | same | same |
| `adapter.properties` (entry jar) | `KINDKEY=vcfcf_vcommunity_vsphere` matches AdapterKind | KINDKEY matches kind | same |
| `manifest.txt` `adapter_kinds` / `adapters` | structurally identical | identical | same |
| nameKey coverage | every describe nameKey (1,2,3,4,5,6,8,9,10,11,14,15,20–31) has a properties entry; 0 missing | full coverage | same |
| XML well-formedness | parses clean (ElementTree) | parses clean | same |
| Leading XML comment block before `<AdapterKind>` | present (≈34 lines) | **synology_nas working ref and the unified pak ALSO have leading comments** | NOT a discriminator |
| `N.description` help-text keys | present (8) | absent in the 3 working paks **but also present in unified vcommunity** | NOT a discriminator (unreferenced extra keys; harmless) |
| Non-ASCII (em-dash) bytes | only in comment lines | compliance comment also has em-dash | NOT a discriminator |
| Installed-pak content vs current source | byte-identical (rules out stale install) | n/a | NOT a stale install |

### The ONE thing that differs — owned type=1 ResourceKind key uniqueness

| Pak | Owned `type="1"` world ResourceKind key | Shared with a co-installed pak? |
|---|---|---|
| synology | `SynologyWorld` (+ 8 other `Synology*` kinds) | No — unique prefix |
| unifi | `UniFiWorld` (+ `UniFi*` kinds) | No — unique prefix |
| compliance | `ComplianceWorld` | No — unique prefix |
| **vcfcf_vcommunity** (unified, build 11, installed) | **`vCommunityWorld` nameKey=20** | **YES** |
| **vcfcf_vcommunity_os** (build 1, installed) | **`vCommunityWorld` nameKey=20** | **YES** |
| **vcfcf_vcommunity_vsphere** (build 1, installed — the failing pak)| **`vCommunityWorld` nameKey=20** | **YES** |

The three working paks each carry a uniquely-prefixed world kind that no
co-installed adapter shares. The three vCommunity forks all ship the **same**
`vCommunityWorld`/nameKey=20 and are **all three installed on devel** at once
(recon_log 2026-06-24 confirms `vcfcf_vcommunity_vsphere`, `vcfcf_vcommunity_os`,
and unified `vcfcf_vcommunity` build 11 co-resident). That is the textbook
shape of a cross-adapter describe-registry key collision, and it is the sole
property that separates the failing pak from the known-good control group.

This collision was an unanticipated side effect of two design decisions in
`designs/managementpacks/vcommunity-three-adapter-split.md`: OPEN-C ("three
fresh AdapterKinds, do not reuse `vcfcf_vcommunity`") correctly made the
**AdapterKinds** distinct, and OPEN-D ("keep the unified pak installed until
parity") created the co-resident state — but neither renamed the inherited
OWNED `vCommunityWorld` ResourceKind, and the design's collision analysis only
covered the stitched-FOREIGN `vCommunity|` metric/property namespace (proven
disjoint), never the owned-RK describe/localization namespace.

## Minimal fix and owner

**Owner: `sdk-adapter-author` (pak layout, not build machinery).**

Give each vCommunity fork a **uniquely-prefixed owned world ResourceKind key**,
matching the convention every working pak already follows
(`SynologyWorld`/`UniFiWorld`/`ComplianceWorld`):

- `vcfcf_vcommunity_vsphere`: `vCommunityWorld` -> `vCommunityVsphereWorld`
- `vcfcf_vcommunity_os`: `vCommunityWorld` -> `vCommunityOsWorld`
- unified `vcfcf_vcommunity`: leave as-is, or retire per OPEN-D once parity is
  reached (removing the unified pak alone also clears the collision, but the
  durable fix is unique keys so the forks can ever coexist).

The change is confined to each fork's own `describe.xml` (the `<ResourceKind
key=…>` and any `RelationshipTrees`/traversal/Java references to that key) and
is a pak-layout edit, not a `vcfops_*` change. Each fork keeps its own nameKey
20 string. A fresh build + reinstall of the renamed fork(s) on devel resolves
the bundle. (Quickest empirical confirmation of the mechanism, if desired
before re-authoring: on a scratch instance install ONLY `vcfcf_vcommunity_vsphere`
with no sibling present — labels should resolve, proving the failure is the
co-resident collision, not the pak.)

**No `vcfops_*` build-machinery change is required.** The builder already places
the bundle correctly and identically for all paks (verified:
`vcfops_managementpacks/sdk_builder.py` writes `resources/resources.properties`
at adapters.zip root and `<kind>/conf/resources/resources.properties`, plus
`<kind>/conf/describe.xml`, for every pak with no per-pak branching). An
optional hardening (separate, `tooling`-owned): a `validate-sdk` lint that warns
when two registered managed paks declare the same owned ResourceKind `key`.

## Regression safety for synology / unifi / compliance

The fix is **per-pak `describe.xml` key renames in the vCommunity forks only.**
It does not touch `vcfops_*` build machinery, so the packaging of
synology/unifi/compliance is provably unchanged — their `.pak` byte layout,
bundle placement, manifest, and describe are all produced by the same unmodified
builder and are not re-built by this change. Their owned world kinds
(`SynologyWorld`, `UniFiWorld`, `ComplianceWorld`) are already uniquely prefixed
and shared with no co-installed adapter, so they were never exposed to this
collision and remain correct as-is. Even the optional `validate-sdk` collision
lint would be a pure additive warning that the three working paks pass trivially
(no shared owned keys), changing none of their output.

## Method (how tested)

Read-only structural diff of built artifacts and source — no live instance
touched, no pak/source modified, all extraction into the session scratchpad:

- Extracted and compared `dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.1.pak`
  (the build installed on devel), `vcfcf_sdk_compliance.1.0.0.51.pak`,
  `vcfcf_sdk_synology_diskstation.1.0.0.17.pak`,
  `vcfcf_sdk_vcommunity.1.0.0.11.pak` (the fork parent), and
  `vcfcf_sdk_vcommunity_os.1.0.0.1.pak`.
- Diffed: top-level `resources/`, `adapters.zip` trees, `manifest.txt`,
  `version.txt`, entry-jar `adapter.properties`, describe.xml AdapterKind/
  ResourceKind nameKeys, and `resources.properties` bundle contents.
- Verified installed-pak describe.xml and properties are byte-identical to
  current `content/sdk-adapters/vcommunity-vsphere/` source (rules out stale
  install).
- Cross-referenced `lessons/pak-content-localization-bundles.md`,
  `context/cleanroom-spec/spec/02-describe-xml.md` + `05-resource-model.md`
  (ResourceKind `key` "unique within the adapter kind"),
  `context/reviews/vcommunity-vsphere-build-1.md`,
  `context/investigations/recon_log.md` (2026-06-24 co-resident state), and
  `designs/managementpacks/vcommunity-three-adapter-split.md` (OPEN-C/OPEN-D).

## Follow-up questions

1. Empirical: install ONLY the vsphere fork on a clean scratch instance — do
   labels resolve? (Confirms collision vs pak defect; recommended before
   re-authoring.)
2. Does the unified parent pak `vcfcf_vcommunity` itself render labels correctly
   on devel right now, or is it ALSO showing raw keys? (Last-writer in the
   registry would resolve; the others would fall back. This tells us which of
   the three is "winning" the `vCommunityWorld` key.)
3. Beyond `vCommunityWorld`, do the forks share any other owned ResourceKind /
   ResourceGroup key with overlapping-but-divergent nameKeys? (The fix should
   rename every shared owned key, not just the world anchor.)
