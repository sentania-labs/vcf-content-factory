# API and wire format rules

Rules for working with VCF Ops APIs and wire formats. Each rule
prevents a documented failure mode.

## API investigation

### Grep both OpenAPI specs
Always search both `reference/docs/operations-api.json` (public) and
`reference/docs/internal-api.json` (internal, 180 extra paths under
`/internal/*`). Internal endpoints require
`X-Ops-API-use-unsupported: true`.

### Don't extrapolate CLI to UI
Don't claim "the UI cannot do X" based on CLI code or api-explorer
findings. The UI's path is observable ground truth. Prefer "I don't
know" over reasoning from incomplete data.

## Wire format ground truth

### Reference repos are ground truth for UI import
The `reference/references/` directory contains community packages authored for
drag-drop use. Check them before designing any wire format. Key
patterns: super metrics = bare `supermetric.json`; views =
`Views.zip`; dashboards = `Dashboard-*.zip`; alerts = `.xml` with
`<alertContent>` root.

### Check reference/references/ before UI claims
Before asserting what the VCF Ops UI supports, inspect `reference/references/`
first. Community packages there are ground truth for what formats and
structures the UI dialogs accept.

## QA and testing priorities

### Struts priority: framework=last-ditch, QA=primary
Framework code (src/vcfops_*/) should use REST Suite API first, Struts
last-ditch. QA testing should prefer Struts/Ext.Direct paths that
replicate real admin experience.

### Community repackage SOP
When repackaging non-Factory content: (1) query Scott for author
attribution, (2) README carries "Packaging contribution" section,
(3) `bundle.json` has `source_attribution` schema. Personal contact
info stays in PKA, not in bundles.
