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
  symptoms and one recommendation) and the 8.18.7, 9.0.2 and 9.1.1
  built-in exports (9.1.1: 1,319 alert definitions, 2,237 symptom
  definitions).
- Load errors name the file: `load_file` prefixes `AlertDef.validate()` and
  `SymptomDef.validate()` errors with the path.

## Keys an older loader ignored

The alert, symptom and recommendation loaders do not reject unknown keys,
so each of these was read as nothing before 2026-11-12 and now renders:

- Alert: **`id`**, `disable_in_base_policy`.
- Recommendation: **`id`**.
- Symptom: `omit`, `disable_in_base_policy`, `symptom_def_type`.

Riskiest: **`id:` on an alert or recommendation.** The old author prompts
said to leave it out, but a value copied from REST output was harmless
because nothing read it. It now re-keys the definition on the
content-import XML path, so a pak upgrade leaves the old definition (under
the derived id) installed and adds a second one. The other is dashboard
`disabled: true` (`dashboard_fidelity_wire_format.md` §Keys an older
loader ignored, which also lists the report keys).

Also new on the XML path for keys the loader always read: an alert's
`wait_cycles` / `cancel_cycles` other than 1 (above), and symptom-set
`threshold_type` / `threshold_value` (§Symptom-set thresholds), which the
XML used to drop.

SDK-adapter paks: buildkit 1.0.28 and earlier vendor the older loaders,
which ignore these keys, so a pak built with such a kit renders without
them and reports no error. Pak CI pins the kit by tag, so neither these
fields nor the duplicate-id and version checks reach an official pak
release until a newer kit is tagged and the pak bumps its pin.

## Install paths

The content-import XML path (pak builds, `AlertContent.xml`) renders every
field here. The REST path cannot: the Suite API `alert-definition` and
`symptom-definition` schemas have no `disableInBasePolicy` or
`symptomDefType`, and the server assigns ids. Where each path refuses:

- `vcfcf_alerts sync` / `vcfcf_symptoms sync` (and every other caller of
  `to_wire()`): `AlertDef.to_wire()` raises on `disable_in_base_policy`,
  `SymptomDef.to_wire()` on `disable_in_base_policy` and
  `symptom_def_type`, naming the file and field. An explicit alert `id:` is
  dropped there (REST matches by name).
- Bundle, discrete and release builds (`vcfcf_packaging build`,
  `build-discrete`, `release`, `publish`): the zip installs alerts and
  symptoms through `install.py` / `install.ps1`, which POST REST bodies
  built from `content/alerts.json` and `content/symptoms.json`, while the
  same zip's drag-drop `AlertContent.xml` would carry the XML fields.
  `vcfcf_core.packaging.assembly.render_bundle_payloads` therefore fails
  the build (`BundleValidationError`, nothing written) when a bundled alert
  or symptom sets `disable_in_base_policy: true`, or a bundled alert or
  recommendation sets an explicit `id:`, naming each file and saying these
  fields are deliverable only through the content-import XML path of a pak
  build. The installer templates are unchanged. A symptom `id:` predates
  this page and is unaffected.
- Tier 2 pak builds (`build-sdk`): every field renders.

## Alert definition

| YAML | Wire (`<AlertDefinition>`) | Notes |
|---|---|---|
| `id: <uuid>` | `id="AlertDefinition-<uuid>"` | replaces the derived `AlertDefinition-<kind>-<slug>`; must be a UUID (the form every third-party and pak alert uses). Written in the author's case (§Ids). The derived path is unchanged |
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
the key is what the XML carries. `Recommendation.id` returns the explicit
key when one is set, so `vcfcf_alerts validate` (`ref=`), the renderer and
the stock-id guard all read the real key. The stock-id baseline holds no
recommendation keys, so an explicit key equal to a stock recommendation's
key is not caught.

## Ids: case and uniqueness

**Case rule.** Explicit alert, symptom and recommendation ids are written
exactly as the author wrote them (alert ids used to be lowercased; symptom
ids never were). Nothing in the repo's knowledge or the exports settles
whether the content importer compares ids case-sensitively: every export id
is a lowercase UUID or a fixed key, so the exports never show two ids that
differ only in case.

**Uniqueness.** Two definitions of one type that render under the same id,
compared case-insensitively, explicit or derived, are an error naming both
files: on content import the later one silently replaces the earlier, and
every `ref=` resolves to whichever won. Checked at load (`alerts.load_dir`,
`alerts.load_recommendations`, `symptoms.load_dir`) and over the combined
inputs of every render: `render_alert_content_xml` (so `vcfcf_alerts` and
`vcfcf_symptoms validate` report it as `INVALID`), bundle, discrete and
release payloads (`render_bundle_payloads`), and Tier 2 paks
(`sdk_builder.check_bundled_content_references`, which matters because a
pak writes one file per alert with its symptoms inline, so no single render
sees symptoms from two alerts together). The same file listed twice is one
definition. Helper: `alerts.render.rendered_id_collisions`.

## Symptom definition

| YAML | Wire (`<SymptomDefinition>`) | Notes |
|---|---|---|
| `disable_in_base_policy: true` | `disableInBasePolicy="true"` | 483 built-ins, every third-party symptom |
| `symptom_def_type: condition_self` | `symptomDefType` | `condition_self` (161 built-in, 7 third-party) or `condition_population` (37 built-in): the alert editor's inline condition symptoms |
| `omit: [wait_cycles, cancel_cycles]` | no `waitCycle` / `cancelCycle` | only with the value 1 (absent means 1); 1,161 of 2,237 built-ins carry neither |
| `omit: [instanced]` | no `instanced` on `<Condition>` | metric_static and property conditions; error with `instanced: true` |

`id:` already existed (`SymptomDefinition-<uuid>`).

### Omit version floors

Each symptom `omit:` entry's floor is the oldest version whose own built-in
`symptomdefs.xml` shows the attribute absent: `wait_cycles` 8.18.7 (1,327 of
1,685 symptoms carry no `waitCycle`), `cancel_cycles` 8.18.7 (1,209 of
1,685), `instanced` 8.18.7 (934 of 985 metric and property conditions).
Table: `symptoms/loader.SYMPTOM_OMIT_MIN_OPS_VERSION`; check:
`SymptomDef.omit_version_problems(target)`. A Tier 2 pak build fails on an
entry above its oldest supported line and `load_file` warns for one above
8.18.7 with no target, as for dashboards
(`dashboard_fidelity_wire_format.md` §Omit version floors). Nothing trips
it today. Alerts have no `omit:`.

## Symptom-set thresholds

`threshold_type` / `threshold_value` on a set (REST `aggregation` /
`value`) were carried only on the REST body; the XML renderer dropped them.
Product exports write a population condition as `<SymptomSet
aggregation="..." aggregationOperator="..." value="...">` (8.18.7, 9.0.2
and 9.1.1 built-in `alertdefs.xml`): `aggregation="any"` and `"all"` stand
alone on non-SELF sets (for example `aggregation="all" applyOn="parent"`,
on every version); `count` and `percent` always come with an
`aggregationOperator` (`>`, `>=`, `<`, `<=`, `=`) and a `value`
(`aggregation="percent" aggregationOperator="&gt;=" applyOn="child"
value="25.0"`). The XML path now:

| YAML on a non-SELF set | XML |
|---|---|
| `threshold_type: ANY` / `ALL` | `aggregation="any"` / `"all"` before `applyOn` |
| `threshold_type: COUNT` / `PERCENT`, or any `threshold_value` | error: the YAML has no field for `aggregationOperator`, so the XML cannot carry the threshold |
| neither | no `aggregation` (as before) |

A threshold on a SELF set is an error on the XML path too (REST ignores it
there). Check: `AlertDef.xml_symptom_set_problems()`, raised by the
renderer and reported by `validate-sdk` / `build-sdk`. `negateCondition`
(10 built-in sets, and on `<Symptom>` children) has no YAML field and is
not rendered, so nothing is dropped.

## Audit of the third-party definitions

Every attribute and element on the 4 alerts, the 2 standalone symptoms, the
9 inline symptoms and the inline recommendation is expressible. Nothing in
them uses a SymptomSet `aggregation`, `aggregationOperator`, `value` or
`negateCondition`.

Found on the way and closed above (§Symptom-set thresholds): the XML
renderer wrote no SymptomSet `aggregation` / `value` for a non-SELF set
with `threshold_type` / `threshold_value`. Built-ins use them (389
`aggregation`, 10 `negateCondition`); no repo, pak or third-party alert
does yet.

Version-specific value: one third-party alert keys its symptoms on
`vCommunity|Licensing:vSphere 8 Enterprise Plus for VCF|Remaining Days`, an
instanced metric named after an 8.x license edition. It renders verbatim; on
an instance licensed under another edition the instance does not exist and
the symptoms never fire.

## Round trip

Mechanical XML-to-YAML mapping, load, render, compare (ordered element
tree, attributes unordered, text whitespace-collapsed with
`" ".join(text.split())`, which also hides a whitespace-only change): **4
of 4 alerts** (with their 9 inline symptoms and 1 recommendation) and **2
of 2 standalone symptoms** identical. The comparator's mutation check ran
over the report templates only (`template_fidelity_wire_format.md`), not
over this XML.
