"""Canonical source of truth for the distribution template version.

Format: YYYY-MM-DD-N, where N increments if multiple template versions
ship on the same day.  Both the install-script template emitter and the
staleness-check CLI read from this single constant.

Bump this value whenever any of the following change:
  - vcfops_packaging/templates/install.py
  - vcfops_packaging/templates/install.ps1
  - vcfops_packaging/builder.py  (output structure changes)
  - vcfops_dashboards/render.py  (dashboard wire format changes)
"""

CURRENT_TEMPLATE_VERSION = "2026-04-18-1"
