"""Build the content-import ZIP the VCF Ops Suite API accepts at
POST /api/content/operations/import (multipart field `contentFile`).

This layout was reverse-engineered by exporting a known-good bundle
from a live VCF Ops 9 instance via POST /api/content/operations/export
and inspecting the resulting zip. See
`memory/vcfops_content_import_wire_format.md` for the full reference.

Outer zip, combining VIEW_DEFINITIONS + DASHBOARDS in one bundle:

    <digits>L.v1                         # marker; content = owner user UUID
    configuration.json                   # manifest, merged keys for all types
    views.zip                            # if any views: nested zip with one
                                         #   content.xml holding every ViewDef
    usermappings.json                    # if any dashboards
    dashboards/<ownerUserId>             # nested zip: dashboard/dashboard.json
                                         #   with ALL owner's dashboards plus
                                         #   empty i18n property bundles
    dashboardsharings/<ownerUserId>      # JSON list (empty = private)

The previous implementation produced an AriaOperationsContent-style
nested-per-item layout (dashboards/<dashboardId> holding a per-dashboard
inner zip, viewdefinitions/<viewId>, no marker, no configuration.json)
which the importer rejected with INVALID_FILE_FORMAT. The real wire
format groups all of one owner's dashboards into a single inner zip
keyed by the owner's user UUID and requires the marker +
configuration.json + usermappings.json siblings.
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from typing import Iterable

from .loader import Dashboard, ViewDef
from .render import render_dashboards_bundle_json, render_views_xml


# Synthetic owner UUID used when no real user id is supplied. The
# importer appears to accept any well-formed UUID here; the marker
# file's content did not have to match the importing user in the
# round-trip test that first proved the wire format. Override by
# passing ``owner_user_id`` to :func:`build_import_zip` once the sync
# path knows the real current-user id.
DEFAULT_OWNER_USER_ID = "00000000-0000-0000-0000-00a1c0ffee01"


def _default_marker_filename() -> str:
    # Fallback for offline `package` invocations: a 19-digit prefix in
    # the right shape. The importer will reject this as
    # INVALID_FILE_FORMAT — the marker filename is a per-instance
    # fingerprint, so the sync path must discover the real value from
    # the target cluster (see client.discover_marker_filename) and
    # pass it in via `marker_filename=`.
    return f"{time.time_ns()}L.v1"


def _build_views_inner_zip(xml_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.xml", xml_text)
    return buf.getvalue()


def _build_dashboards_inner_zip(dashboard_json: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("dashboard/dashboard.json", dashboard_json)
        # Empty i18n bundles — present in every real export, kept
        # defensively in case the importer expects them.
        for lang in ("", "_es", "_fr", "_ja"):
            z.writestr(f"dashboard/resources/resources{lang}.properties", "")
    return buf.getvalue()


def build_import_zip(
    views: Iterable[ViewDef],
    dashboards: Iterable[Dashboard],
    owner_user_id: str = DEFAULT_OWNER_USER_ID,
    marker_filename: str | None = None,
) -> bytes:
    views = list(views)
    dashboards = list(dashboards)
    views_by_name = {v.name: v for v in views}

    config: dict = {"type": "CUSTOM"}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as outer:
        # Marker is the exporting user's UUID with no trailing
        # newline — real exports are exactly 36 bytes.
        outer.writestr(marker_filename or _default_marker_filename(), owner_user_id)

        if views:
            xml = render_views_xml(views)
            outer.writestr("views.zip", _build_views_inner_zip(xml))
            config["views"] = len(views)

        if dashboards:
            # Explicit directory entries mirror the real export shape.
            outer.writestr(zipfile.ZipInfo("dashboards/"), b"")
            outer.writestr(zipfile.ZipInfo("dashboardsharings/"), b"")
            dj = render_dashboards_bundle_json(
                dashboards, views_by_name, owner_user_id
            )
            outer.writestr(
                f"dashboards/{owner_user_id}",
                _build_dashboards_inner_zip(dj),
            )
            # Share every imported dashboard with the built-in
            # "Everyone" group so other logged-in users see it. An
            # empty list here imports the dashboards as private to
            # the API user (the owner), which looks like the import
            # silently failed from any other account.
            outer.writestr(
                f"dashboardsharings/{owner_user_id}",
                json.dumps(
                    [
                        {
                            "groupName": "Everyone",
                            "sourceType": "LOCAL",
                            "dashboards": [{"dashboardId": d.id} for d in dashboards],
                        }
                    ]
                ),
            )
            outer.writestr(
                "usermappings.json",
                json.dumps(
                    {
                        "sources": [],
                        "users": [
                            {
                                "userName": "admin",
                                "userId": owner_user_id,
                            }
                        ],
                    },
                    indent=3,
                ),
            )
            config["dashboards"] = len(dashboards)
            config["dashboardsByOwner"] = [
                {"owner": owner_user_id, "count": len(dashboards)}
            ]

        outer.writestr("configuration.json", json.dumps(config, indent=3))

    return buf.getvalue()
