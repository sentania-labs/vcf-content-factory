# Dashboard names over 50 characters install but cannot be edited

## Symptom

The VCF Operations dashboard editor caps the Name field at 50 characters
("The maximum length for this field is 50"). The content-import API and a
pak install accept longer names, so the dashboard installs and renders. The
problem only shows when someone tries to save an edit: the editor refuses
until the name is shortened. Seen on devel 2026-10-12 on the compliance
Environment Overview (issue #198).

## Rule

The `[VCF Content Factory] ` prefix uses 22 of the 50, leaving 28 for the
title, so pick the title with that budget from the start.

Renaming later is expensive: dashboard import identity is the name, so
renaming an installed dashboard ships a second dashboard beside the old one
unless the upgrade removes the old one, and each rename on a shipped pack
needs an explicit go.

## Guard

Validate warns through `DASHBOARD_NAME_MAX_LEN` in
`src/vcfcf_core/dashboards/loader.py`. It is a warning, not an error, until
the existing over-length dashboards are renamed: four factory dashboards
(capacity_assessment, demand_driven_capacity_v2, summary_widget_smoke,
vcf_license_consumption_overview) and two compliance pak dashboards were
over the limit on 2026-10-18.
