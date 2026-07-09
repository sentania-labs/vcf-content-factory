# Review — vcommunity-vsphere build 2

- **Adapter:** `content/sdk-adapters/vcommunity-vsphere`
- **Build reviewed:** 2 (`adapter.yaml` build_number 2, version 1.0.0)
- **Branch / commit (pak's own repo):** `fix/localization-raw-keys-build-2` / `db39289`
- **Reviewer:** `sdk-adapter-reviewer` (read-only static gate; no install, no live touch)
- **Verdict:** **APPROVE** (0 BLOCKING)
- **Findings:** 0 BLOCKING / 0 WARNING / 1 NIT
- **Date:** 2026-06-24

## What this build is

A pure localization-bundle edit. Build 1's Accounts/adapter-config UI rendered
raw describe keys (`vcfcf_vcommunity_vsphere`, `host`, `port`, `allowInsecure`,
the four config-file keys) instead of friendly labels. Build 2 removes the seven
non-standard `<int>.description=` help-text keys (nameKeys 6/8/9/10/11/14/15)
from `resources/resources.properties`, leaving only the standard `<int>=label`
shape that the known-good control paks (compliance/synology/unifi) use. No Java,
no `describe.xml`, no profile, no collection/stitch change.

## Independent verification (did not trust the report)

### 1. The actual diff (`git diff f1dd9ca db39289`)

Confirmed the diff is exactly what the author described and nothing more:

- `resources/resources.properties`: the **only** value-line change is the
  removal of the seven `<int>.description=` lines (6/8/9/10/11/14/15). **Every**
  `<int>=label` entry is intact with a non-empty value. The header comment was
  rewritten to explain the change (cosmetic).
- `adapter.yaml`: `build_number 1 → 2` (hard-rule 8 satisfied).
- `CHANGELOG.md`: matching build-2 entry (hard-rule 9 satisfied).
- `docs/README.md`, `docs/inventory-tree.md`: version-string bumps to 1.0.0.2
  (generated docs).
- `describe.xml`: **unmodified** — correct, since it carries zero
  `descriptionKey`/`resourceBundle` attributes (verified) and never referenced
  the removed keys.

Minimal diff, no drive-by refactor. Clean.

### 2. nameKey reconciliation (the symptom-recreation risk)

The one way this edit could re-create the raw-key symptom is by orphaning a
nameKey — leaving a `describe.xml nameKey="N"` with no `N=label` entry. Checked
both directions:

- describe.xml nameKeys: `1 2 3 4 5 6 8 9 10 11 14 15 20 21 22 23 24 25 29 30 31`
  (21 distinct).
- `resources.properties` integer keys: **identical set, 21 distinct, all
  non-empty, zero duplicates.**
- Verified in the **built** pak too — both bundle copies
  (`adapters.zip!/resources/resources.properties` and
  `…/vcfcf_vcommunity_vsphere/conf/resources/resources.properties`) carry the
  same 21 keys and **zero** `.description` keys remain.

Zero missing, zero orphaned, zero duplicate. The removal touched only keys that
`describe.xml` referenced from nothing.

### 3. Format / encoding regressions

- No CR bytes (LF-only), no BOM, no non-ASCII bytes anywhere in the file, no
  stray non-`<int>=` key lines, no duplicate keys. The em-dash bytes noted in
  the investigation are gone (they were on the removed/rewritten comment lines);
  this is harmless. No trailing-comma/format breakage (it is a `.properties`
  file, not JSON).

### 4. Gate re-run (independent)

| Gate | Author claim | My result | Match |
|---|---|---|---|
| `validate-sdk` | pass | **OK** (8 sources compiled; only the standard `-source 11` system-modules javac notice) | ✓ |
| `build-sdk` | `dist/…1.0.0.2.pak` | **Built `dist/vcfcf_sdk_vcommunity_vsphere.1.0.0.2.pak`** | ✓ |
| `pak-compare` vs build-1 | 0/0/0 | **0 BLOCKING / 0 WARNING / 0 INFO** | ✓ |
| `pak-compare` vs compliance build-51 | 0 BLK / 1 WARN (7 vs 4 ids) / 279 INFO | **0 BLOCKING / 1 WARNING / 279 INFO** | ✓ |

The single WARNING is `[W1] adapter instance identifier count: factory=7,
reference=4` — the benign structural difference between this adapter's
connection-param set and compliance's, not anything new this build introduced.
**Not a regression.** All author gate claims reproduce exactly.

### 5. Schema claim verification (`describeSchema.xsd`)

The author claims there is **no schema-valid way** to attach help text to a
connection identifier/credential field, so the tooltips were dropped (not
re-expressed). I verified this against the canonical schema
(`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/conf/describeSchema.xsd`):

- `ResourceIdentifierType` (line 318): `<xs:sequence>` permits **only**
  `<enum>` (minOccurs=0, maxOccurs=unbounded). Attributes: `dispOrder`, `key`,
  `RequiredNameKeyGroup`, `required`, `type`, `length` — no `descriptionKey`.
- `CredentialFieldType` (line 81): same — `<enum>`-only child, attributes
  `dispOrder`, `default`, `key`, plus the nameKey group. No `descriptionKey`.
- `RequiredNameKeyGroup` (line 2282): the single required `nameKey` integer
  attribute, label only. No description sibling.
- No `descriptionKey` attribute anywhere in the schema (the one `description`
  hit, line 1489, is unrelated documentation prose about an event-map value).

**The author is correct.** There is no schema-sanctioned mechanism to attach
help text to a connection parameter; `<Description nameKey>` exists only under
`<Recommendation>`. Dropping the tooltips (vs. re-expressing them) is the
schema-valid choice. Re-adding them in any form would be schema-invalid and
would risk re-introducing the same bundle problem.

## Honesty check on the root-cause claim

The whole-bundle-rejection mechanism (a strict Dictionary/describe loader
aborting the entire bundle on unrecognized dotted keys → every nameKey falls
back to raw) is the **prime suspect, not statically proven** — both the author
and the investigation say so explicitly, and that is honest. The relevant
failure *class* is documented in `knowledge/lessons/pak-content-localization-bundles.md`
("the importer … aborts the entire content tree when any single key is
absent/mismatched"), which is the content bundle rather than the adapter-config
describe bundle — analogous, not identical, but a real precedent.

The key point that makes the fix correct **regardless of mechanism**: the seven
`<int>.description` keys are **dead** — `describe.xml` references them from
nothing (zero `descriptionKey`/`<Description>` attributes, verified), and the
schema offers no way to ever reference them. They are unreachable text. Removing
unreachable keys cannot remove any working label and cannot change collection or
stitch behavior. So the edit is safe whether or not it is *also* the cure: if the
loader was rejecting the bundle, this fixes it; if it was merely ignoring the
keys, this is a harmless cleanup that aligns the pak with the three working
controls. There is no scenario in which this build is worse than build 1 on the
label surface.

It is fair and correct that final confirmation requires install-on-devel +
visually verifying the labels resolve in the Accounts UI. No static artifact can
prove a platform-side loader's behavior; that is `qa-tester` / orchestrator
devel-proof territory, not this gate's.

## Registry check (`knowledge/context/defects.md`)

Open defects whose `Affects:` names **this** pak (`vcommunity-vsphere`):

- **none affect this pak.** DEF-001 (synology), DEF-002 (unifi), DEF-003
  (synology, closed), DEF-004 (vcommunity-**os**) — none name
  `vcommunity-vsphere`. DEF-004 is the sibling fork's guest-ops defect and does
  not extend to the vsphere fork. No re-assertion owed.

No new finding of WARNING-or-worse arises from this build, so there is no
registration candidate to graduate.

## Findings

### NIT-1 — investigation's earlier `vCommunityWorld` cross-fork-collision concern is unaddressed by this build (out of scope, informational)

The retracted Pass-1 root cause raised a real durable concern: all three forks
ship the same owned `type="1"` ResourceKind `key="vCommunityWorld"`. Pass 2
retracted that as the *cause* of the raw-key symptom (the unified pak failed
alone, pre-split), and build 2 correctly scopes itself to the localization
bundle only. But the shared owned-RK key across co-resident forks remains a
latent concern flagged in the investigation (follow-up Q3). This is **not** a
finding against build 2 — the build is right to stay minimal — but the
orchestrator may want a separate design decision on unique-prefixing the owned
world kind before all three forks are intended to coexist long-term. Purely
informational; does not affect this verdict.

## If shipped as-is

An operator installs build 2, opens the Accounts UI, and — if the prime-suspect
mechanism is correct — sees friendly labels (vCenter Server, Port, Allow
Insecure SSL, the config-file names) where build 1 showed raw keys. Worst case
(mechanism wrong): labels still raw, but no regression vs build 1 and no other
behavior changed. The connection-param help tooltips are gone in either case
(schema does not permit them). No collection, stitch, or scoring impact.

## Safe to install on devel for label-resolution confirmation?

**Yes.** Build 2 is a pure, minimal, dead-key removal that is structurally
verified clean (every nameKey mapped, no orphans, no dupes, bundle clean in the
built pak), passes all gates (validate-sdk, build-sdk, pak-compare 0 BLOCKING),
makes a correct and honest schema call, and carries zero open registry defects
for this pak. It is exactly the reversible single-variable experiment the
investigation prescribed. Installing it on devel to confirm labels resolve is
the correct and safe next step.
