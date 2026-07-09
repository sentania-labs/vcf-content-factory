"""MPB (Management Pack Builder) Suite API client.

Wraps the internal MPB REST namespace:
  /suite-api/internal/mpbuilder/*

All requests require:
  - Bearer token from POST /api/auth/token/acquire (handled by VCFOpsClient)
  - X-Ops-API-use-unsupported: true  (CLAUDE.md Hard Rule 7 — missing header → 404)

Auth is delegated to vcfops_common.client.VCFOpsClient which manages token
acquisition and 401 re-auth transparently.

Documented in knowledge/context/mpb/mpb_api_surface.md.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from vcfops_common.client import VCFOpsClient, VCFOpsError


# The unsupported-API header is REQUIRED for every /internal/mpbuilder/* endpoint.
# Missing it returns 404 (treated as the endpoint not existing), not 401.
# CLAUDE.md Hard Rule 7: "Grep both OpenAPI specs … /internal/* require X-Ops-API-use-unsupported: true"
_UNSUPPORTED_HEADER = {"X-Ops-API-use-unsupported": "true"}

_MPB_BASE = "/internal/mpbuilder"


class MPBClient:
    """Thin wrapper around VCFOpsClient for MPB design operations.

    Usage::

        client = MPBClient.from_env(profile="devel")
        result = client.post_design_import(envelope_json)
        print(result["id"])
    """

    def __init__(self, vcfops_client: VCFOpsClient) -> None:
        self._c = vcfops_client

    @classmethod
    def from_env(
        cls,
        profile: Optional[str] = None,
        *,
        default_profile: str = "devel",
    ) -> "MPBClient":
        """Construct from the active credential profile.

        Delegates to VCFOpsClient.from_env().  Profile resolution order:
          1. ``profile`` argument if non-None.
          2. ``VCFOPS_PROFILE`` env var.
          3. ``default_profile`` argument.
          4. "prod" hard fallback.

        Raises VCFOpsError if required env vars are missing.
        """
        c = VCFOpsClient.from_env(profile=profile, default_profile=default_profile)
        return cls(c)

    # ------------------------------------------------------------------
    # POST /internal/mpbuilder/knowledge/designs/import
    # ------------------------------------------------------------------

    def post_design_import(
        self,
        envelope: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Upload an MPB exchange-format envelope to the import endpoint.

        Endpoint: POST /suite-api/internal/mpbuilder/knowledge/designs/import
        Required header: X-Ops-API-use-unsupported: true

        Args:
            envelope: A dict matching the export.json shape (top-level keys:
                type, design, source, objects, relationships, events, requests).
                Produced by render_mpb_exchange_json() in render_export.py.

        Returns:
            The parsed JSON response body.  On 201 Created this is
            {"id": "<design-uuid>"}.

        Raises:
            VCFOpsError: on any non-2xx response, with the HTTP status code
                and response body included in the message.

        Notes (from knowledge/context/mpb/mpb_api_surface.md):
          - Server mints a fresh UUID for the design regardless of any UUID
            embedded in the input envelope.
          - The design name is sanitised server-side (whitespace and
            non-alphanumerics stripped) for the adapter-kind slug, but the
            human-readable name retains the original value.
          - Two factory imports of the same adapter may collide on
            source.source.id (stable UUID5 per-adapter). The server may
            silently overwrite the earlier design.  See mpb_api_surface.md
            §"Collateral note — import may collide on source.source.id".
        """
        path = f"{_MPB_BASE}/knowledge/designs/import"
        r = self._c._request(
            "POST",
            path,
            json=envelope,
            headers=_UNSUPPORTED_HEADER,
        )
        if r.status_code not in (200, 201):
            raise VCFOpsError(
                f"POST {path} returned HTTP {r.status_code}.\n"
                f"Body: {r.text[:2000]}"
            )
        return r.json()

    @property
    def host(self) -> str:
        """The hostname of the target instance (for URL construction)."""
        # VCFOpsClient stores base as "https://<host>/suite-api"
        base: str = self._c.base  # type: ignore[attr-defined]
        # Strip scheme and path to get bare host
        without_scheme = base.replace("https://", "", 1)
        return without_scheme.split("/")[0]
