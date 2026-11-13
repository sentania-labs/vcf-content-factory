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


def bundle_external_views(bundle: Bundle) -> list:
    """``(content_type, id, where)`` for each View widget of ``bundle`` that
    names a view by raw id the bundle does not ship."""
    own = [v.id for v in bundle.views]
    return [ref for d in bundle.dashboards for ref in d.external_view_references(own)]


def print_external_view_prerequisites(refs, context: str) -> int:
    """One ``PREREQUISITE:`` line to stderr per View widget that names a view
    by raw id the build does not ship (the external-view passthrough: the
    view must exist on the target), then the stock-id baseline check on
    each, with the wording validate and the report ``view_id`` check use
    (``stock_ids.report_reference_warnings``: not a known product view, or
    absent on a supported line). Returns the number of warnings."""
    from .stock_ids import report_reference_warnings
    for _ctype, oid, where in refs:
        print(f"  PREREQUISITE: {where} names view {oid} by raw id; {context} does not ship it, so it "
              f"must exist on the target instance", file=sys.stderr)
    return report_reference_warnings(list(refs))


def navigation_closure(start, all_dashboards, all_views, all_sms, all_customgroups):
    """Everything a set of dashboards needs to ship with its Dashboard
    Navigation targets: the ``start`` dashboards, every dashboard reachable
    through named ``navigations:`` targets (to a fixed point, cycles
    included: each dashboard is visited once, by id), and the views, super
    metrics and custom groups those dashboards reference (``collect_deps``).

    Returns ``(dashboards, views, supermetrics, customgroups, unresolved)``;
    ``unresolved`` lists every target name absent from ``all_dashboards`` and
    every missing-dependency error, so a caller can refuse instead of
    writing a manifest the builder will reject.
    """
    from vcfcf_common.dep_walker import collect_deps

    by_name: dict = {}
    for d in all_dashboards:
        by_name.setdefault(d.name, d)
    seen: set = set()
    dashboards: list = []
    unresolved: list = []
    queue = list(start)
    while queue:
        d = queue.pop(0)
        key = (d.id or d.name).lower()
        if key in seen:
            continue
        seen.add(key)
        dashboards.append(d)
        for w in d.widgets:
            for nav in w.navigations:
                if not nav.dashboard or nav.dashboard == d.name:
                    continue
                target = by_name.get(nav.dashboard)
                if target is None:
                    msg = f"dashboard {d.name!r} navigates to {nav.dashboard!r}, which does not exist"
                    if msg not in unresolved:
                        unresolved.append(msg)
                else:
                    queue.append(target)
    graph = collect_deps(
        dashboards=dashboards,
        all_views=all_views,
        all_sms=all_sms,
        all_customgroups=all_customgroups,
        project_scope=None,
    )
    print_external_view_prerequisites(graph.external_views, "the navigation closure")
    return (dashboards, graph.views, graph.supermetrics, graph.customgroups,
            unresolved + list(graph.errors))
