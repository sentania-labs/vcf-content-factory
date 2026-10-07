"""Dashboard Navigation prerequisite reporting for the packaging CLIs.

The bundle carry-or-fail rule itself lives in
``vcfcf_core.packaging.loader.check_bundle_dashboard_navigations`` (it never
prints). This module is the factory-side voice: every ``dashboard_id``
target is external by definition, so each build or bundle sync lists it as
a prerequisite rather than an error. Shared by ``builder``,
``discrete_builder`` and ``syncer``.
"""
from __future__ import annotations

import sys

from vcfcf_core.packaging.loader import Bundle, check_bundle_dashboard_navigations


def print_navigation_prerequisites(bundle: Bundle, context: str) -> None:
    """Print one ``PREREQUISITE:`` line to stderr per external
    (``dashboard_id``) Dashboard Navigation target in ``bundle``. A named
    target missing from the bundle raises ``BundleValidationError`` here as
    everywhere else."""
    for line in check_bundle_dashboard_navigations(bundle.dashboards, context):
        print(f"  PREREQUISITE: {line}", file=sys.stderr)
