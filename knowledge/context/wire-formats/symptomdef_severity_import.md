# SymptomDefinition severity — content-import (XML) vs REST (JSON) diverge

**Question (2026-07-10):** an "information"-severity symptom + the alert
that referenced it silently vanished during a vcommunity-vsphere pak
install. The Info symptom differed from its three siblings
(warning/critical/immediate, which imported fine) in exactly one field:
`severity`. Why did it fail, and what severity values does the
content-import path actually accept?

## Root cause (server-confirmed)

The content-import XML symptom carried `<State severity="information">`.
The devel analytics log named the failure exactly (2026-07-10, pak
install window):

```
ERROR analytics ... SymptomDefinitionRetriever.importSymptomDefinitions
  - Cannot import Symptom Definitions: Severity or condition is null or
    incorrect, skipping creation of symptom def. severity:null
    condition:...[key=vCommunity|Licensing:Any|Remaining Days,...]
```

`"information"` is **not** a recognized content-import severity token.
The parser resolved it to `severity:null`, judged the def invalid, and
**skipped creation**. The condition parsed fine — severity was the only
problem.

The alert then failed as a pure **dependency cascade** (NOT an
independent failure):

```
ERROR ... UserDataService.createOrUpdateAlertDefinition - Cannot create
  alert definition AlertDefinition-VMWARE-ESXi_Host_License_Expiring
  because dependent symptoms
  [SymptomDefinition-VMWARE-ESXi_Host_License_Remaining_Days_Info]
  are not available
ERROR ... The following Alert Definition(s) [...ESXi_Host_License_Expiring]
  are invalid and won't be imported.
```

**So: fix the symptom severity and the alert imports cleanly** — no
independent alert defect exists. Post-install `GET
/api/symptomdefinitions?name=...` → totalCount 0 and `GET
/alertdefinitions/...Expiring` → "No such AlertDefinition" are both
downstream of the single severity rejection.

## The accepted content-import (XML) severity values

From the vendor reference corpus (`reference/references/**/*.xml`,
`<State severity="...">` inside `<SymptomDefinition>`), the tokens that
actually ship are **lowercase**:

```
critical   immediate   warning   info   automatic
```

`"info"` (73 occurrences across vendor paks) is the informational
value. `"information"` appears **zero** times. Confirmed `<State
severity="info">` nested inside `<SymptomDefinition adapterKind=...>` in
`AriaOperationsContent/.../SampleDefaultPolicy.xml`.

## The trap: JSON REST and XML content-import use DIFFERENT info tokens

This is the whole bug. The two symptom-import paths disagree on the
informational token:

| Path | Endpoint | Info severity token |
|---|---|---|
| REST JSON | `POST /api/symptomdefinitions` (`vcfops_symptoms`) | `INFORMATION` (uppercase) |
| Content-import XML | pak `content/symptomdefs/*.xml` → `SymptomDefinitionRetriever` | `info` (lowercase) |

`vcfops_symptoms/loader.py` `SEVERITY_MAP` maps `INFO → INFORMATION`
because that is correct **for the REST JSON path**. Every other severity
(`WARNING`, `CRITICAL`, `IMMEDIATE`) has the same spelling in both paths
— only INFO diverges.

## Exact code defect

`src/vcfops_alerts/render.py:276` renders the symptom content XML:

```python
state_elem = ET.SubElement(sd_elem, "State", {"severity": sym.severity.lower()})
```

`sym.severity` for a YAML `severity: INFO` is already `"INFORMATION"`
(mapped by the symptoms loader for the REST path). `.lower()` turns it
into `"information"` — the rejected token. For WARNING/CRITICAL/IMMEDIATE
the naive `.lower()` happens to be correct, so those three siblings
imported and only INFO broke.

Compare the sibling alert-State renderer at `render.py:327-329`, which
DOES special-case its divergent token (`auto` → `automatic`). The
symptom-State renderer needs the analogous special-case.

## The fix (renderer, not YAML)

**Fix in `src/vcfops_alerts/render.py:276`** — map the REST wire value
back to the XML token before emitting, e.g. treat `INFORMATION` as
`info`:

```python
_XML_SEVERITY = {"INFORMATION": "info"}   # REST token -> content-import token
sev = _XML_SEVERITY.get(sym.severity.upper(), sym.severity.lower())
state_elem = ET.SubElement(sd_elem, "State", {"severity": sev})
```

Do **not** "fix" this by changing the adapter YAML to `severity: info`
or by altering `vcfops_symptoms` `SEVERITY_MAP` — the loader value is
correct for the REST path, and any other symptom authored to the REST
API would break. The divergence is real; the renderer is the single
place that must translate REST-token → XML-token. This is
`tooling`/`framework-reviewer` work (touches `src/vcfops_*/`), and it
needs a regression test asserting `severity: INFO` → `<State
severity="info">` (guarding against re-introducing `information`).

Once shipped, rebuild the vcommunity-vsphere pak; the Info symptom and
the `ESXi Host License Expiring` alert both import (alert had no
independent defect).

## Investigation posture / cleanup

Read-only against devel: Suite API GETs + root SSH `grep` of
`/storage/log/vcops/log/analytics-*.log`. **No objects created on
devel; nothing to clean up.** The rejected Info symptom + alert were
already absent (that was the reported symptom), and this investigation
added nothing to the instance.

## Cross-reference

- `knowledge/context/wire-formats/wire_formats.md` §Alerts/symptoms — pak
  content layout for `<SymptomDefinitions>` / `<AlertDefinitions>`.
- `src/vcfops_symptoms/loader.py` `SEVERITY_MAP` — the REST-path mapping.
- `src/vcfops_alerts/render.py` — the XML content-import renderer.
