---
id: RULE-005
---

# RULE-005: Always validate before installing

Run full repo validation before every install. For management packs, also run `pak-compare` against the closest reference pak — zero BLOCKINGs is the install gate.

The orchestrator validates the whole repo after each authoring round. Delegate to `content-installer` which validates before every sync.

**Validation commands:**
```
python3 -m vcfops_supermetrics validate &&
python3 -m vcfops_dashboards validate &&
python3 -m vcfops_customgroups validate &&
python3 -m vcfops_symptoms validate &&
python3 -m vcfops_alerts validate &&
python3 -m vcfops_reports validate &&
python3 -m vcfops_managementpacks validate
```

For MPs additionally: `python3 -m vcfops_managementpacks pak-compare <pak> <reference>`

**If violated:** Malformed YAML or broken cross-references reach production, causing partial installs, broken dashboards, or corrupted policy bindings. For MPs, structural divergence from MPB's format causes install failures that only the analytics log can diagnose.
