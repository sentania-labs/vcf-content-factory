# Alert content-import: multi-tier SymptomSet encoding

**Date:** 2026-07-10
**Investigator:** api-explorer
**Instance:** vcf-lab-operations-devel (read-only: token acquire + GET only; no mutation)
**Trigger:** vcommunity-vsphere build-8 (`0.0.0.8`) — the ported
`ESXi Host License Expiring` alert declared four severity tiers but
post-import only ONE (Info) survived.

---

## TL;DR / root cause

The Tier-2 alert content-import XML renderer
(`src/vcfops_alerts/render.py::_render_alert_definition`) emits **multiple bare
`<SymptomSet>` siblings directly under `<State>`**, with **no `<SymptomSets>`
compound wrapper**. On import, the platform keeps only the **last** such
sibling and silently drops the rest. A tiered alert (Critical / Immediate /
Warning / Info) collapses to a single tier.

**The encoding that survives** (proven by the identical vendor alert, which
ships in a real, importable pak) is a **single `<SymptomSets operator="…">`
wrapper** inside `<State>`, containing one `<SymptomSet>` per tier. See
"Surviving encoding" below.

---

## Evidence

### 1. Live collapse (confirmed by GET on devel)

`GET /suite-api/api/alertdefinitions/AlertDefinition-VMWARE-ESXi_Host_License_Expiring`
returns exactly one state with a single leaf symptom set:

```
states: 1
  severity: AUTO
  base-symptom-set: { symptomSetOperator: AND,
                      symptomDefinitionIds: ["SymptomDefinition-VMWARE-ESXi_Host_License_Remaining_Days_Info"],
                      symptomSets: [] }
```

Only the **Info** tier — the LAST of the four `<SymptomSet>` siblings our
renderer emitted — is present. Critical / Immediate / Warning were dropped.

### 2. What our renderer emits today (the defect)

`_render_alert_definition` iterates `symptom_sets["sets"]`, and for **each
symptom in each set** appends a flat `<SymptomSet>` child of `<State>`:

```xml
<State severity="automatic">
  <SymptomSet aggregation="any" applyOn="self" operator="and" ref="…Critical"/>
  <SymptomSet aggregation="any" applyOn="self" operator="and" ref="…Immediate"/>
  <SymptomSet aggregation="any" applyOn="self" operator="and" ref="…Warning"/>
  <SymptomSet aggregation="any" applyOn="self" operator="and" ref="…Info"/>
  <Impact key="health" type="badge"/>
</State>
```

Two independent bugs here:
- **No `<SymptomSets>` wrapper** → the importer keeps only the last sibling.
- **One `<SymptomSet>` per symptom** (inner loop over `symptoms`) → a single
  set that AND-combines two symptoms would wrongly become two sibling sets
  (and also collapse). The `aggregation="any"` attribute is not part of the
  vendor grammar either.

### 3. Surviving encoding — vendor ground truth

The identical alert in the vendor pak
(`reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/alertdefs/ESXi Host License Expiring.xml`)
uses ONE `<State>` with ONE `<SymptomSets operator="or">` wrapper holding four
`<SymptomSet>` children. Note two shapes of `<SymptomSet>`:

```xml
<State severity="automatic">
  <SymptomSets operator="or">
    <!-- single-symptom set: bare ref= on the SymptomSet, no child element -->
    <SymptomSet applyOn="self" operator="and" ref="SymptomDefinition-9803e6a3-…"/>
    <!-- multi-symptom set: AND of two Symptoms via child <Symptom> elements -->
    <SymptomSet applyOn="self" operator="and">
      <Symptom ref="SymptomDefinition-7a5c6ce4-…"/>
      <Symptom ref="SymptomDefinition-b0d54ebb-…"/>
    </SymptomSet>
    <SymptomSet applyOn="self" operator="and">
      <Symptom ref="SymptomDefinition-ff8e08f4-…"/>
      <Symptom ref="SymptomDefinition-a3587501-…"/>
    </SymptomSet>
    <SymptomSet applyOn="self" operator="and">
      <Symptom ref="SymptomDefinition-e0fbe746-…"/>
      <Symptom ref="SymptomDefinition-c6e76934-…"/>
    </SymptomSet>
  </SymptomSets>
  <Impact key="health" type="badge"/>
</State>
```

This is a real vendor pak that imports on real instances, so this is the
**proven-surviving** wire shape, not a hypothesis.

### 4. Pattern survey across all reference alertdefs (17 files, 2 vmbro paks)

| Alert (representative) | Alert `<State>` shape |
|---|---|
| Single-tier (majority: NIC Disconnected, Server Down, Windows Service Down, …) | ONE bare `<SymptomSet …ref=…/>` **directly under `<State>`, no wrapper** |
| Single-tier, AND of 2 symptoms (Fan/Memory/Volume/Power Supply Health Degraded) | ONE `<SymptomSet operator="and">` with two `<Symptom ref=…>` children, **no wrapper** |
| Multi-tier OR (ESXi Host License Expiring; Dell EMC Server Warranty Time Remaining) | ONE `<SymptomSets operator="or">` wrapper with N `<SymptomSet>` children |
| Multi-tier (Dell EMC Physical Disk Life Remaining) | ONE `<SymptomSets operator="and">` wrapper with 4 `<SymptomSet ref=>` children |

**Rule:** the `<SymptomSets>` wrapper appears **iff there are ≥2 symptom
sets**. A single set is emitted bare under `<State>`. The wrapper's `operator`
comes from the alert's set-combination operator (`ANY` → `or`, `ALL` → `and`).

### 5. REST model mapping (read-only GET)

The XML `<SymptomSet>` grammar maps to the REST `base-symptom-set` model:
- `<SymptomSet ref="X"/>` → `{ symptomSetOperator: AND, symptomDefinitionIds: ["X"] }`
- `<SymptomSet operator="and"><Symptom ref="X"/><Symptom ref="Y"/></SymptomSet>`
  → `{ symptomSetOperator: AND, symptomDefinitionIds: ["X","Y"] }`
  (confirmed against built-in `SymptomDefinition-VrAdapter-isLicenseExpiring` +
  `…-hasNotCertificateExpired`, one CRITICAL state, two ids AND-combined).
- `<SymptomSets operator="or">` with N children → a `base-symptom-set` whose
  `symptomSetOperator` is `OR` and whose `symptomSets[]` holds the N child sets.

---

## Surviving encoding (the answer)

For a multi-tier alert the renderer MUST produce:

```
<State severity="…">
  <SymptomSets operator="{or|and}">          # ONLY when ≥2 sets
    <SymptomSet applyOn="{self|…}" operator="{and|or}" ref="…"/>   # 1-symptom set
    <SymptomSet applyOn="{self|…}" operator="{and|or}">            # ≥2-symptom set
      <Symptom ref="…"/>
      <Symptom ref="…"/>
    </SymptomSet>
    …
  </SymptomSets>
  <Impact key="…" type="badge"/>
</State>
```

For a single-set alert, omit the wrapper and place the lone `<SymptomSet>`
directly under `<State>` (the current single-set output already survives).

Do NOT emit `aggregation="any"` — it is not part of the vendor grammar.

---

## Code implications (for `tooling`)

**File:** `src/vcfops_alerts/render.py`
**Function:** `_render_alert_definition` (the `for s in sets:` block, ~lines 358-379)

Required changes:
1. **Group by set, not by symptom.** Emit one `<SymptomSet>` per entry in
   `symptom_sets["sets"]`, not one per symptom. Within a set:
   - 1 symptom → `<SymptomSet applyOn="…" operator="…" ref="<id>"/>` (bare ref).
   - ≥2 symptoms → `<SymptomSet applyOn="…" operator="<set op>">` with a
     `<Symptom ref="<id>"/>` child per symptom.
   The per-set `operator` comes from the set's own `operator` (`ALL`→`and`,
   `ANY`→`or`); `applyOn` from `defined_on` (`SELF`→`self`).
2. **Wrap when ≥2 sets.** If `len(sets) >= 2`, wrap all `<SymptomSet>` elements
   in a single `<SymptomSets operator="…">` element (child of `<State>`), with
   `operator` from `symptom_sets["operator"]` (`ANY`→`or`, `ALL`→`and`). When
   `len(sets) == 1`, emit the lone `<SymptomSet>` directly under `<State>`
   (no wrapper) to match vendor single-tier output.
3. **Drop `aggregation="any"`** from the emitted `<SymptomSet>` attributes.
4. Keep `<Impact>` (and any `<Recommendations>`) as direct children of
   `<State>`, ordered AFTER the symptom-set structure (vendor order).

The same `_symptom_id(...)` cross-reference derivation stays — it already
matches the emitted symptomdef `id=` (UUID mode when `sym.id` present, slug
fallback otherwise; see `sdk_pak_content_import_gap.md` FIX B).

**Test guidance:** add a fixture alert with two sets, one of which AND-combines
two symptoms, and assert the rendered XML contains exactly one
`<SymptomSets operator="or">` with two `<SymptomSet>` children (one bare `ref=`,
one with two `<Symptom>` children) — and that a single-set alert emits NO
wrapper.

**Content implication:** once the renderer emits the wrapper, the author can
restore the source's true 4-tier AND-paired-bounds structure (the
`ESXi Host License Expiring` source YAML currently works around this defect by
using 4 independent single-symptom open-threshold sets under
`criticality: SYMPTOM_BASED`; see the `symptom_sets:` block and the long
"rendering necessity" note in
`content/sdk-adapters/vcommunity-vsphere/alerts/ESXi Host License Expiring.yaml`).
The workaround is functionally acceptable but no longer forced after the fix.

---

## Clean-up

Read-only investigation. Devel actions: token acquire, GET
alertdefinitions/reportdefinitions, SSH log grep — no POST/PUT/DELETE, no test
objects created. Scratch pak extraction removed. Nothing to clean on the
instance.
