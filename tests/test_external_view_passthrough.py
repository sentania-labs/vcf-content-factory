"""External view UUID passthrough — regression tests for the fix in
vcfops_dashboards/loader.py and vcfops_dashboards/render.py.

Three cases per the spec in the task brief:

  Case A — bundled view referenced by NAME:
      Resolves to that view's UUID in the rendered JSON.  (existing behavior,
      must remain working.)

  Case B — bundled view referenced by raw UUID:
      Resolves to the same UUID (the bundled view's id).
      NOTE: the loader stores ``view:`` verbatim as ``w.view_name``.  When the
      YAML supplies a raw UUID that happens to match a bundled view's id, the
      validator (``known_views`` is keyed by name, not id) treats it as an
      EXTERNAL UUID passthrough.  The rendered output still carries the correct
      UUID verbatim — which is equivalent to resolving the bundled view.

  Case C — external UUID (raw UUID, no matching bundled view):
      Emitted verbatim as ``viewDefinitionId`` in the rendered JSON.
      No error is raised.

  Case D — unknown bare NAME:
      Must still raise DashboardValidationError (authoring mistake guard must
      NOT be weakened).

All fixtures are built in-memory using loader/render dataclasses; no disk
content YAML, no network, no install.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from vcfops_dashboards.loader import (
    Dashboard,
    DashboardValidationError,
    Interaction,
    ViewColumn,
    ViewDef,
    Widget,
    WidgetResourceKindRef,
)
from vcfops_dashboards.render import render_dashboards_bundle_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXTERNAL_UUID = "d8a3767e-9d5e-4bf2-b613-9e3bef977502"
_BUNDLED_VIEW_NAME = "vCommunity VM Performance"
_BUNDLED_VIEW_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_OWNER_ID = "00000000-0000-0000-0000-000000000001"


def _make_bundled_view() -> ViewDef:
    """Return a minimal ViewDef representing a bundled view."""
    return ViewDef(
        id=_BUNDLED_VIEW_ID,
        name=_BUNDLED_VIEW_NAME,
        description="",
        adapter_kind="VMWARE",
        resource_kind="VirtualMachine",
        columns=[
            ViewColumn(
                attribute="cpu|usage_average",
                display_name="CPU Usage (%)",
            )
        ],
    )


def _make_view_widget(view_ref: str) -> Widget:
    """Return a minimal View widget with view_name=view_ref."""
    w = Widget(
        local_id="view1",
        type="View",
        title="My View Widget",
        coords={"x": 1, "y": 1, "w": 6, "h": 4},
        view_name=view_ref,
        dashboard_name="Test Dashboard",
    )
    return w


def _make_dashboard(view_ref: str, dash_id: str | None = None) -> Dashboard:
    return Dashboard(
        id=dash_id or str(uuid.uuid4()),
        name="Test Dashboard",
        description="",
        widgets=[_make_view_widget(view_ref)],
        interactions=[],
        name_path="Testing",
        shared=True,
        hidden=False,
    )


# ---------------------------------------------------------------------------
# Case A — bundled view by NAME
# ---------------------------------------------------------------------------

def test_case_a_bundled_view_by_name_renders_to_view_id():
    """A View widget referencing a bundled view by name renders to that view's UUID."""
    view = _make_bundled_view()
    views_by_name = {view.name: view}
    dashboard = _make_dashboard(_BUNDLED_VIEW_NAME)

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    bundle = json.loads(result_json)

    widgets = bundle["dashboards"][0]["widgets"]
    assert len(widgets) == 1
    assert widgets[0]["type"] == "View"
    assert widgets[0]["config"]["viewDefinitionId"] == _BUNDLED_VIEW_ID


# ---------------------------------------------------------------------------
# Case B — bundled view referenced by raw UUID
# ---------------------------------------------------------------------------

def test_case_b_bundled_view_by_uuid_passthrough():
    """A View widget referencing a bundled view's own UUID emits that UUID verbatim.

    The bundled view's id is a valid UUID so the validator accepts it as external;
    render emits it as-is.  Since it equals the actual view's UUID the wire format
    is correct.
    """
    view = _make_bundled_view()
    views_by_name = {view.name: view}
    # Use the bundled view's UUID as the view_name — NOT the view's name string.
    dashboard = _make_dashboard(_BUNDLED_VIEW_ID)

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    bundle = json.loads(result_json)

    widgets = bundle["dashboards"][0]["widgets"]
    assert widgets[0]["type"] == "View"
    assert widgets[0]["config"]["viewDefinitionId"] == _BUNDLED_VIEW_ID


# ---------------------------------------------------------------------------
# Case C — external UUID (not in bundled views) — passthrough, no error
# ---------------------------------------------------------------------------

def test_case_c_external_uuid_passthrough_no_error():
    """A View widget referencing an external UUID emits it verbatim without error."""
    views_by_name: dict = {}  # no bundled views at all
    dashboard = _make_dashboard(_EXTERNAL_UUID)

    result_json = render_dashboards_bundle_json([dashboard], views_by_name, _OWNER_ID)
    bundle = json.loads(result_json)

    widgets = bundle["dashboards"][0]["widgets"]
    assert widgets[0]["type"] == "View"
    assert widgets[0]["config"]["viewDefinitionId"] == _EXTERNAL_UUID


def test_case_c_external_uuid_in_validate_no_error():
    """Dashboard.validate() must not raise when view_name is a raw UUID not in known_views."""
    dashboard = _make_dashboard(_EXTERNAL_UUID)
    # validate() with an empty known_views dict — must NOT raise
    dashboard.validate(known_views={}, enforce_framework_prefix=False)


# ---------------------------------------------------------------------------
# Case D — unknown bare NAME must still error
# ---------------------------------------------------------------------------

def test_case_d_unknown_bare_name_raises():
    """A View widget referencing a bare name that isn't bundled must raise at validate()."""
    dashboard = _make_dashboard("Nonexistent View Name That Has No UUID Format")
    with pytest.raises(DashboardValidationError, match="unknown view"):
        dashboard.validate(known_views={}, enforce_framework_prefix=False)


def test_case_d_unknown_bare_name_also_raises_when_other_views_exist():
    """Same guard fires even when some views ARE bundled."""
    view = _make_bundled_view()
    known = {view.name: view}
    dashboard = _make_dashboard("Some Other View Not In Bundle")
    with pytest.raises(DashboardValidationError, match="unknown view"):
        dashboard.validate(known_views=known, enforce_framework_prefix=False)
