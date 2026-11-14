# A converter must not infer source facts from names; verification must compare against the source

**Date:** 2026-11-13. **Cost:** a converted pak that would have replaced the
Summary page of six vSphere object kinds on install, found by a pak content
review after `import-local` had reported the six dashboards "identical".

## The trap

The vCommunity pak keeps six dashboards in folders named after vSphere kinds:
`content/dashboards/VMFolder/`, `HostFolder/`, `DatastoreFolder/`,
`NetworkFolder/`, `DistributedVirtualPortgroup/`,
`VmwareDistributedVirtualSwitch/`. The names look like a convention for
"Summary page of that kind", and the offline importer treated them as one:
any dashboard in such a folder got `summary_for: VMWARE:<Folder>`.

A pak binds a dashboard to a Summary tab in one place only,
`content/dashboards/dashboards.properties`
(`knowledge/context/api-surface/summary_dashboard_pak_binding.md`). This
pak ships no such file, so it binds nothing. The factory pak built from the
converted YAML did ship one, so installing it would have replaced six
Summary pages the source never touched.

## Why verification did not catch it

Verification rendered the converted dashboard and compared it with the
source dashboard JSON. The binding is not in the dashboard JSON, so the
comparison never saw it, and the only other record of it was the importer's
own output. Checking the converter against its own inference proves only
that the converter is consistent with itself. The dashboards were reported
"identical", and that word was how the run said "no unrecorded difference".

## The rule

1. **A fact about the source is read from the source artifact that carries
   it, in the form the product reads.** A folder name, file name or display
   name is not that artifact. When the product locates a file by path (the
   pak installer finds `dashboards.properties` by name), read that file, the
   way the product reads it. Never fill in a value because the name suggests
   one.
2. **Verification compares the output with the source, never with the
   converter's own intermediate form.** Every key that changes what gets
   installed belongs in the compared wire form, including ones that live
   outside the object's own file (here, the binding file). Source absent and
   output present is a difference, and so is the reverse.
3. **Every entry of a side file is accounted for.** Each binding entry is
   classified (carried, superseded, binds no dashboard, not carried, or a
   GAP), so an entry cannot be dropped or invented without a line saying so.

## Where it is enforced

`src/vcfcf_core/importer/inputs.py` reads `dashboards.properties`
(`SummaryBinding`); the dashboard mapper sets `summary_for` only from it;
`vcfcf_extractor/importer.py` compares the loaded `summary_for` with the
source entry at `dashboard.<summary binding>`; `convert.classify_bindings`
classifies every entry. Tests: `tests/test_import_local_summary_binding.py`
(including one that puts the old inference back and expects verification to
fail). How-to: `knowledge/context/authoring/importer_offline_conversion.md`
§Summary-tab bindings.
