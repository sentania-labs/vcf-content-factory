# vcf-mp-cleanroom — full bundle (2026-05-16, post-Pass-26)

Complete deliverable bundle from the vcf-mp-cleanroom investigation.
26 RE passes across 2026-05-15 → 2026-05-16. Reverse-engineers VCF
Operations management pack architecture (native Java adapter "Track C"
+ MPB Track A runtime engine) to feed VCF-CF's Tier 1 (MPB design
generator) + Tier 2 (Native Java adapter generator) pipelines.

**Source workspace**: `/home/scott/vault/workspaces/vcf-mp-cleanroom/`
(local-only; never had a git remote, per clean-room rules).

## What's new since the previous bundle

- **Pass 26**: forward-looking design guidance for VCF-CF's
  `vcfcf-adapter-base.jar` framework (`spec/17`). 4-layer architecture,
  11-capability framework inventory, MVP build order with effort
  estimates, 8 design tenets, 3 open decisions. Answers "how do we
  build the framework so VCF-CF isn't constantly rewriting core
  Tier 2 logic." Audience: VCF-CF framework architects (complementary
  to `spec/15` which is for adapter authors).
- **Pass 25**: empirical grammar bounds on MPB's `@@@MPB_QUOTE_BODY`
  parser. Surveyed 54 distinct compiled paths across UniFi + phpIPAM:
  pure dot-notation + `data.*` only — NOT JMESPath, NOT Jayway
  JsonPath. Documented in `spec/11 § Grammar bounds (empirical, Pass 25)`
  with workarounds for "iterate sibling array by predicate."

## Clean-room boundary

What's IN this bundle:
- The SPEC (`spec/`) — 20 markdown sections, the formal deliverable
- Per-adapter analysis notes (`analysis/per-adapter/`) — human-written
  observations that informed the SPEC
- Pak-signing format analysis (`analysis/pak-signing-chain.md`) +
  appliance-side empirical findings (in `spec/16`)
- SDK public-API survey (`analysis/sdk-survey/v2.2-public-api.md`)
- Chronological audit-log (`audit-log.md`)
- Workspace-level README + mission/clean-room rules (CLAUDE.md)

What's NOT in this bundle (per clean-room rules):
- Source `.pak` files (the inputs were `/inputs/from-devel/` +
  `/inputs/from-marketplace/`, gitignored)
- Decompiled jar source (was `/analysis/decompiled/`, gitignored —
  CFR / jadx / javap output)
- Internal session state (.git, .pka, hidden scratchpads)

**The SPEC sections do NOT quote decompiled source code.** They
describe the API surface, lifecycle contracts, and patterns observed
— never implementation. This is the clean-room boundary.

## Suggested reading order

### For VCF-CF framework architects (designing `vcfcf-adapter-base.jar`)
1. `spec/17-vcfcf-framework-design-guidance.md` — **start here**;
   self-contained design-guide with 4-layer architecture, 11-capability
   framework inventory, MVP build order, design tenets
2. `spec/15-tier2-handoff-for-vcf-cf.md` — what Tier 2 adapters look
   like once authored (the framework's "user" perspective)
3. `spec/01-adapter-lifecycle.md` — the SDK contract the framework
   wraps
4. `spec/02a-describe-xsd-canonical.md` — XSD grammar (target for the
   framework's describe.xml typed builder)
5. Pull in spec/03..14 for surface-specific authoring needs

### For Tier 2 (Native Java adapter) implementers (what an adapter IS)
1. `spec/00-overview.md` — vocabulary + Track C runtime model
2. `spec/15-tier2-handoff-for-vcf-cf.md` — **consolidated Tier 2
   handoff**; stands alone for strategic picture
3. `spec/01-adapter-lifecycle.md` — `AdapterInterface3` + `AdapterBase`
   contract + concurrency model
4. `spec/02a-describe-xsd-canonical.md` — authoritative XSD grammar
5. `spec/16-platform-install-and-signing.md` — appliance install
   pipeline + empirical signing behavior
6. Pull in spec/03..14 for specific topic depth as needed

### For Tier 1 (MPB design generator) implementers
1. `spec/00-overview.md`
2. `spec/12-mpb-handoff-for-vcf-cf.md` — **consolidated MPB handoff**;
   stands alone for strategic picture
3. `spec/10-mpb-builderfile-schema.md` — runtime BuilderFile vocabulary
4. `spec/11-mpb-designer-wire-format.md` — designer JSON wire format +
   pak generation pipeline + **§ Grammar bounds (Pass 25)** documenting
   the empirical parser limits
5. Pull in spec/13-classloading-and-classpath.md for packaging strategy

### For investigation-history archaeology
1. `audit-log.md` — chronological pan-out/disprove ledger across all
   26 passes
2. `spec/99-summary-and-vcf-cf-recommendations.md` — synthesis

## SPEC section index

| § | File | What it covers |
|---|---|---|
| 00 | `spec/00-overview.md` | Vocabulary + Track C runtime model + section index |
| 01 | `spec/01-adapter-lifecycle.md` | `AdapterInterface3` + `AdapterBase` + concurrency (per-instance Semaphore, no platform retry) + adapter.properties + packaging |
| 02 | `spec/02-describe-xml.md` | declarative model overview + MPB-runtime emission model |
| 02a | `spec/02a-describe-xsd-canonical.md` | authoritative XSD-derived grammar; full enum vocabularies; never-observed-but-permitted surfaces |
| 03 | `spec/03-credential-model.md` | credential kinds + fields |
| 04 | `spec/04-actions.md` | legacy actions AND modern NMP tasks |
| 05 | `spec/05-resource-model.md` | ResourceKind / Group / Attribute / Identifier |
| 06 | `spec/06-metrics-units-expressions.md` | metric keys, units, computed-metric expression language |
| 07 | `spec/07-relationships-cross-mp.md` | TraversalSpec/ResourcePath + cross-MP attachment + full 18-method Relationships API |
| 08 | `spec/08-alerts-symptoms-recommendations.md` | Symptom/Alert/Recommendation grammar; 10 condition types, 20 operators, RESOLVED type/subType int codes |
| 09 | `spec/09-capacity-and-policy.md` | CapacityDefinitions + Policy + OOTBPolicies full ladder |
| 10 | `spec/10-mpb-builderfile-schema.md` | MPB BuilderFile runtime model (Tier 1 vocabulary) |
| 11 | `spec/11-mpb-designer-wire-format.md` | MPB designer JSON wire format + pak generation pipeline + the **Track-C-shape revelation** + **§ Grammar bounds (Pass 25)** documenting parser limits |
| 12 | `spec/12-mpb-handoff-for-vcf-cf.md` | **CONSOLIDATED MPB → VCF-CF Tier 1 handoff** |
| 13 | `spec/13-classloading-and-classpath.md` | appliance shared classpath + per-pak classloader isolation |
| 14 | `spec/14-ui-and-operational-surfaces.md` | Methods + Actions + Faults + LaunchConfigurations + PowerState + Icon |
| 15 | `spec/15-tier2-handoff-for-vcf-cf.md` | **CONSOLIDATED Tier 2 (Native Java) → VCF-CF handoff** |
| 16 | `spec/16-platform-install-and-signing.md` | appliance install pipeline (CASA→Python 7-phase state machine) + empirical signature-validation behavior |
| 17 | `spec/17-vcfcf-framework-design-guidance.md` | **FRAMEWORK DESIGN GUIDE for `vcfcf-adapter-base.jar`** — 4-layer architecture, framework-vs-per-pak split, MVP build order, design tenets |
| 99 | `spec/99-summary-and-vcf-cf-recommendations.md` | final synthesis across all passes |
| — | `spec/triage-report-2026-05-15.md` | per-pak Track A/B/C classification for the 51-pak input corpus |

## Per-adapter analysis index (`analysis/per-adapter/`)

Reference detail on specific adapters that informed cross-validation:

| Adapter | File | Why it matters |
|---|---|---|
| mpb-adapter | `mpb-adapter.md` + `mpb-adapter-insights-for-vcf-cf.md` | MPB runtime engine — Tier 1 + Tier 2 leverage |
| vim (vSphere) | `vim.md` | Largest / most complex (102 lib jars), pushes SDK to limits |
| vmwarevi_adapter3 | `vmwarevi_adapter3.md` | Cross-MP TraversalSpec calibration |
| NSXTAdapter3 | `NSXTAdapter3.md` | Modern clean architecture; runtime-pushed topology |
| VCFAutomation | `VCFAutomation.md` | 9/9 cross-MP ResourcePaths; aggregator archetype |
| mongodb | `mongodb.md` | aria-ops-core wrapper canonical example |
| vcf-ops-data-sdk | `vcf-ops-data-sdk.md` | Modern Reactive-Streams middleware (NOT a successor SDK) |
| (corpus surveys) | `_bulk-devel-survey.md`, `_bulk-survey-2026-05-15.md` | Pattern-conformance scan across remaining adapters |

## Status

**Spec is shippable.** Three handoff/guide docs (`spec/12` Tier 1,
`spec/15` Tier 2, `spec/17` framework design) reflect post-Pass-26
empirical + design knowledge:
- Install pipeline + signing field-confirmed against live VCF
  Operations 9.0.2 appliance (Pass 23 via Navani/lab-admin)
- Collect concurrency empirically confirmed: per-instance Semaphore(1),
  no platform retry on collect() failure (Pass 23)
- MPB `@@@MPB_QUOTE_BODY` parser grammar bounds empirically known:
  dot-path + `data.*` only (Pass 25)
- VCF-CF framework architecture sketched with 11-capability inventory
  + MVP build order (Pass 26)

**Remaining open questions** (genuinely unresolved):
- `<CustomGroupMetrics>` runtime usage example — confirmed-negative
  across 2 lab appliances; needs external pak (e.g. ServiceNow MP)
- Cloud Proxy install pipeline cross-confirmation (out of corpus)
- A handful of XSD-permitted but never-observed surfaces
  (FavoriteGroups, Names, TraversalSpecExtensionKinds,
  `Severity="Automatic"`)
- Whether MPB's parser can do nested array iteration
  (`data.*.X.*`) — structurally consistent with the design but
  0 observed examples in either built pak
- A few static-analysis follow-ups (Action result handling, full
  expression language grammar, full `adapter.properties` key
  catalogue)
- spec/17 design-guide follow-ups: concrete API mockups, test
  harness specification, Tier-1→Tier-2 promotion translator
  enumeration

See `spec/15-tier2-handoff-for-vcf-cf.md § 13` for the authoritative
unresolved-questions list; `spec/17 § 8` for design-guide-specific
follow-ups.
