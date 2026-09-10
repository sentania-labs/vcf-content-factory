"""Canonical source of truth for the distribution template version.

Format: YYYY-MM-DD-N, where N increments if multiple template versions
ship on the same day.  Both the install-script template emitter and the
staleness-check CLI read from this single constant.

Bump this value whenever any of the following change:
  - vcfops_packaging/templates/install.py
  - vcfops_packaging/templates/install.ps1
  - vcfops_packaging/builder.py  (output structure changes)
  - vcfops_packaging/discrete_builder.py  (output structure changes)
  - vcfops_packaging/release_builder.py  (output structure changes)
  - vcfops_dashboards/render.py  (dashboard or view wire format changes)

This list is the same one CLAUDE.md carries under "After tooling changes";
keep the two in step.

History (most recent first):
  2026-08-29-1  render.py: multi-subject view columns unbound by default,
                bound only via column `subject:` (view wire format change)
  2026-08-24-2  install.ps1: uninstall residual-else sites warn and continue
"""

CURRENT_TEMPLATE_VERSION = "2026-08-29-1"
