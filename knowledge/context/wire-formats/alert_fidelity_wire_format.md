# Alert, symptom and recommendation fidelity: wire format and YAML (2026-11-12)

The YAML fields that let existing alert definitions, symptom definitions and
recommendations (content-import XML, `alertContent`) be re-expressed as
factory YAML and render the same. Code: `src/vcfcf_core/alerts/loader.py`,
`src/vcfcf_core/alerts/render.py`, `src/vcfcf_core/symptoms/loader.py`.
Tests: `tests/test_report_alert_fidelity.py`. Related:
`alertdef_symptomset_import.md`, `symptomdef_severity_import.md`,
`symptomdef_dt_condition_import.md`.

## Contract

- Every field is optional; without it the XML is exactly what the renderer
  wrote before (render regression over every alert, symptom and
  recommendation in the repo and the unifi, synology and vsanperf paks:
  identical).
- One existing field now renders: an alert's `wait_cycles` / `cancel_cycles`
  other than 1 become `waitCycle` / `cancelCycle`. The XML path used to drop
  them (only the REST body carried them). The vendor
  `alertDefinitionSchema.xsd` says both default to 1 when absent, so 1 is
  still not written; every alert in the repo and the paks uses 1.
- Evidence: one third-party pak (4 alert files, 2 symptom files, inline
  symptoms and one recommendation) and the 9.1.1 built-in export (1,319
  alert definitions, 2,237 symptom definitions).

## Install paths

The content-import XML path (pak builds, `AlertContent.xml`) renders every
field here. The REST path (`vcfcf_alerts sync`, `vcfcf_symptoms sync`, the
bundle `install.py`, which posts `to_wire()` bodies) cannot: the Suite API
`alert-definition` and `symptom-definition` schemas have no
`disableInBasePolicy` or `symptomDefType`. `to_wire()` therefore raises,
naming the file and field, instead of shipping an alert enabled or a
condition symptom as a library symptom. Explicit ids are identity on the
XML path only; REST still matches by name and the server assigns ids.

## Alert definition

| YAML | Wire (`<AlertDefinition>`) | Notes |
|---|---|---|
| `id: <uuid>` | `id="AlertDefinition-<uuid>"` | replaces the derived `AlertDefinition-<kind>-<slug>`; must be a UUID (the form every third-party and pak alert uses). The derived path is unchanged |
| `disable_in_base_policy: true` | `disableInBasePolicy="true"` | the alert ships disabled in the default policy. On all 4 third-party alerts and 90 built-ins; the XSD calls it "for VMware internal use", the product honours it on import |
| `wait_cycles: 2`, `cancel_cycles: 2` | `waitCycle="2"`, `cancelCycle="2"` | written only when not 1 (above) |

```yaml
id: 5f607182-93a4-4b52-86d7-e8f9a0b1c2d3
disable_in_base_policy: true
wait_cycles: 2
cancel_cycles: 2
```

## Recommendation

| YAML | Wire | Notes |
|---|---|---|
| `id: probeRecommendationKey` | `<Recommendation key="...">` and every alert's `ref="..."` | replaces the derived `Recommendation-df-<kind>-<slug>`; an XML `xs:ID` (letters, digits, `_ . -`, starting with a letter or `_`). Seen: a camel-case key in the third-party pak, `Recommendation-df-...` in built-ins |

The recommendation's `name` stays the YAML cross-reference alerts use;
the key is what the XML carries.

## Symptom definition

| YAML | Wire (`<SymptomDefinition>`) | Notes |
|---|---|---|
| `disable_in_base_policy: true` | `disableInBasePolicy="true"` | 483 built-ins, every third-party symptom |
| `symptom_def_type: condition_self` | `symptomDefType` | `condition_self` (161 built-in, 7 third-party) or `condition_population` (37 built-in): the alert editor's inline condition symptoms |
| `omit: [wait_cycles, cancel_cycles]` | no `waitCycle` / `cancelCycle` | only with the value 1 (absent means 1); 1,161 of 2,237 built-ins carry neither |
| `omit: [instanced]` | no `instanced` on `<Condition>` | metric_static and property conditions; error with `instanced: true` |

`id:` already existed (`SymptomDefinition-<uuid>`).

## Audit of the third-party definitions

Every attribute and element on the 4 alerts, the 2 standalone symptoms, the
9 inline symptoms and the inline recommendation is expressible. Nothing in
them uses a SymptomSet `aggregation`, `aggregationOperator`, `value` or
`negateCondition`.

Not closed, found on the way: the XML renderer still writes no SymptomSet
`aggregation` / `value` for a non-SELF set with `threshold_type` /
`threshold_value` (only the REST body carries them), and no
`negateCondition`. Built-ins use them (389 `aggregation`, 10
`negateCondition`); no repo, pak or third-party alert does yet.

Version-specific value: one third-party alert keys its symptoms on
`vCommunity|Licensing:vSphere 8 Enterprise Plus for VCF|Remaining Days`, an
instanced metric named after an 8.x license edition. It renders verbatim; on
an instance licensed under another edition the instance does not exist and
the symptoms never fire.

## Round trip

Mechanical XML-to-YAML mapping, load, render, compare (ordered element
tree, attributes unordered, text whitespace-collapsed): **4 of 4 alerts**
(with their 9 inline symptoms and 1 recommendation) and **2 of 2 standalone
symptoms** identical.
