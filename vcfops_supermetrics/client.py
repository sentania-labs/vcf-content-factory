"""Minimal VCF Operations Suite API client for super metric management.

Auth: POST /api/auth/token/acquire returns a token. Subsequent calls send
`Authorization: vRealizeOpsToken <token>`. Token TTL is sliding (6h from
last call).

SuperMetric endpoints used:
  GET    /api/supermetrics              list (paged)
  GET    /api/supermetrics/{id}         fetch one
  DELETE /api/supermetrics/{id}         delete
  POST   /api/content/operations/import install bundle (UUID-preserving)

Install goes through the content-import zip path, not POST
/api/supermetrics, because the latter reassigns UUIDs server-side and
breaks sm_<uuid> cross-references. See import_supermetrics_bundle.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from typing import Iterable, Iterator, Optional

import requests

from ._env import load_dotenv


class VCFOpsError(RuntimeError):
    pass


class VCFOpsClient:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        auth_source: str = "Local",
        verify_ssl: bool = True,
    ):
        self.base = f"https://{host}/suite-api"
        self._username = username
        self._password = password
        self._auth_source = auth_source
        self._session = requests.Session()
        self._session.verify = verify_ssl
        self._session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self._token: Optional[str] = None
        # Cached per-instance content marker filename (discovered via a
        # throwaway export). Re-probing it triggers export<->import task
        # contention, so discover once per client lifetime.
        self._marker_filename: Optional[str] = None

    # ---- env constructor ------------------------------------------------
    @classmethod
    def from_env(cls) -> "VCFOpsClient":
        load_dotenv()
        try:
            host = os.environ["VCFOPS_HOST"]
            user = os.environ["VCFOPS_USER"]
            pw = os.environ["VCFOPS_PASSWORD"]
        except KeyError as e:
            raise VCFOpsError(f"Missing env var: {e.args[0]}") from None
        return cls(
            host=host,
            username=user,
            password=pw,
            auth_source=os.environ.get("VCFOPS_AUTH_SOURCE", "Local"),
            verify_ssl=os.environ.get("VCFOPS_VERIFY_SSL", "true").lower() != "false",
        )

    # ---- auth -----------------------------------------------------------
    def authenticate(self) -> None:
        r = self._session.post(
            f"{self.base}/api/auth/token/acquire",
            json={
                "username": self._username,
                "password": self._password,
                "authSource": self._auth_source,
            },
        )
        if r.status_code != 200:
            raise VCFOpsError(f"auth failed ({r.status_code}): {r.text}")
        self._token = r.json()["token"]
        self._session.headers["Authorization"] = f"vRealizeOpsToken {self._token}"

    def _ensure_auth(self) -> None:
        if not self._token:
            self.authenticate()

    def _request(self, method: str, path: str, **kw) -> requests.Response:
        self._ensure_auth()
        r = self._session.request(method, f"{self.base}{path}", **kw)
        if r.status_code == 401:  # token expired -> reauth once
            self._token = None
            self._ensure_auth()
            r = self._session.request(method, f"{self.base}{path}", **kw)
        return r

    # ---- super metrics --------------------------------------------------
    def list_supermetrics(self, page_size: int = 1000) -> Iterator[dict]:
        page = 0
        while True:
            r = self._request(
                "GET",
                "/api/supermetrics",
                params={"page": page, "pageSize": page_size},
            )
            if r.status_code != 200:
                raise VCFOpsError(f"list failed ({r.status_code}): {r.text}")
            body = r.json()
            items = body.get("superMetrics") or []
            for it in items:
                yield it
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(items))
            if (page + 1) * page_size >= total or not items:
                return
            page += 1

    def get_supermetric(self, sm_id: str) -> dict:
        r = self._request("GET", f"/api/supermetrics/{sm_id}")
        if r.status_code != 200:
            raise VCFOpsError(f"get failed ({r.status_code}): {r.text}")
        return r.json()

    def find_by_name(self, name: str) -> Optional[dict]:
        r = self._request("GET", "/api/supermetrics", params={"name": name})
        if r.status_code != 200:
            raise VCFOpsError(f"find failed ({r.status_code}): {r.text}")
        for sm in r.json().get("superMetrics") or []:
            if sm.get("name") == name:
                return sm
        return None

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        # API rejects newlines / multi-line formulas: collapse all whitespace.
        return " ".join(formula.split())

    # ---- policies -------------------------------------------------------
    def get_default_policy_id(self) -> str:
        r = self._request("GET", "/api/policies")
        if r.status_code != 200:
            raise VCFOpsError(f"policy list failed ({r.status_code}): {r.text}")
        for p in r.json().get("policySummaries") or []:
            if p.get("defaultPolicy"):
                return p["id"]
        raise VCFOpsError("no default policy found in /api/policies response")

    def export_default_policy_xml(self) -> str:
        """Export the Default Policy and return the raw XML content."""
        zip_bytes, _xml_name = self._export_default_policy_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    return zf.read(name).decode("utf-8")
        raise VCFOpsError("policy export ZIP contained no XML file")

    def _export_default_policy_zip(self) -> tuple:
        """Export the Default Policy ZIP.  Returns (zip_bytes, xml_filename).

        Unlike export_default_policy_xml, this preserves the raw ZIP bytes
        so the caller can edit the XML and re-import the whole archive.
        """
        policy_id = self.get_default_policy_id()
        # Must override the session-level Accept header for this one call.
        r = self._request(
            "GET", "/api/policies/export",
            params={"id": policy_id},
            headers={"Accept": "application/zip"},
        )
        if r.status_code != 200:
            raise VCFOpsError(
                f"policy export failed ({r.status_code}): {r.text}"
            )
        zip_bytes = r.content
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            xml_names = [n for n in zf.namelist() if n.endswith(".xml")]
        if not xml_names:
            raise VCFOpsError("policy export ZIP contained no XML file")
        return zip_bytes, xml_names[0]

    def _import_policy_zip(self, zip_bytes: bytes) -> None:
        """Re-import a (possibly edited) policy ZIP.

        Uses POST /api/policies/import?forceImport=true — a PUBLIC endpoint
        that does not require X-Ops-API-use-unsupported.

        The endpoint expects multipart/form-data with a 'policy' field
        carrying the ZIP bytes (spec: requestBody schema has required field
        'policy' of type string/binary inside multipart/form-data).

        The session-level 'Content-Type: application/json' header must be
        absent for multipart uploads — if present it overrides the
        multipart boundary header that requests generates for the files=
        argument, causing a server-side 500. We remove it temporarily and
        restore it after the call.
        """
        self._ensure_auth()
        # Temporarily remove session-level Content-Type so requests can set
        # the multipart/form-data boundary correctly.
        saved_ct = self._session.headers.pop("Content-Type", None)
        try:
            r = self._session.post(
                f"{self.base}/api/policies/import",
                params={"forceImport": "true"},
                files={"policy": ("exportedPolicies.zip", zip_bytes, "application/zip")},
            )
        finally:
            if saved_ct is not None:
                self._session.headers["Content-Type"] = saved_ct
        if r.status_code not in (200, 201, 204):
            raise VCFOpsError(
                f"policy import failed ({r.status_code}): {r.text}"
            )

    @staticmethod
    def verify_supermetrics_enabled(
        policy_xml: str, sm_ids: list,
    ) -> dict:
        """Check which SM IDs appear as enabled in the policy XML."""
        import xml.etree.ElementTree as ET
        root = ET.fromstring(policy_xml)
        enabled_ids = set()
        for elem in root.iter("SuperMetric"):
            if elem.get("enabled", "").lower() == "true":
                enabled_ids.add(elem.get("id", ""))
        return {sm_id: sm_id in enabled_ids for sm_id in sm_ids}

    def enable_supermetric_on_default_policy(
        self,
        sm_id: str,
        resource_kinds: list,
    ) -> None:
        """Assign a super metric to resource kinds and enable it in the
        Default Policy.

        Two-step approach required for content-zip-imported SMs:

        Step 1 — resource-kind assignment via PUT /internal/supermetrics/assign
          (no policyIds param).  This wires the SM to the adapter/resource kind
          so it can appear in views and dashboards.  NOTE: the policyIds variant
          returns 200 but does NOT enable content-zip-imported SMs on any policy
          — it only works for SMs created via POST /api/supermetrics.

        Step 2 — policy enablement via policy export → edit XML → re-import.
          Export the Default Policy ZIP, inject
          <SuperMetric enabled="true" id="<sm_id>"/> under each
          <SuperMetrics adapterKind="X" resourceKind="Y"> block, then POST
          the modified ZIP back via POST /api/policies/import?forceImport=true.

        See context/internal_supermetrics_assign.md for the full investigation.
        """
        import xml.etree.ElementTree as ET

        if not resource_kinds:
            raise VCFOpsError("enable requires at least one resource kind")

        # Normalise resource kind dicts — accept both key name styles.
        normalised_rks = [
            {
                "adapterKind": rk.get("adapterKindKey") or rk.get("adapterKind"),
                "resourceKind": rk.get("resourceKindKey") or rk.get("resourceKind"),
            }
            for rk in resource_kinds
        ]

        # --- Step 1: resource-kind assignment --------------------------------
        # policyIds is intentionally omitted — it does nothing for content-zip
        # SMs and would only add noise.
        body = {
            "superMetricId": sm_id,
            "resourceKindKeys": normalised_rks,
        }
        r = self._request(
            "PUT",
            "/internal/supermetrics/assign",
            json=body,
            headers={"X-Ops-API-use-unsupported": "true"},
        )
        if r.status_code != 200:
            raise VCFOpsError(
                f"resource-kind assignment failed ({r.status_code}): {r.text}"
            )

        # --- Step 2: policy enablement via export/edit/import ----------------
        zip_bytes, xml_name = self._export_default_policy_zip()

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            raw_xml = zf.read(xml_name)
            other_files = {
                n: zf.read(n) for n in zf.namelist() if n != xml_name
            }

        # Parse — preserve namespace declarations by registering any xmlns
        # found in the raw bytes, then round-trip through ET.
        # ET.register_namespace keeps the prefix intact on serialise.
        ns_map: dict = {}
        import re as _re
        for prefix, uri in _re.findall(
            r'xmlns(?::([A-Za-z_][A-Za-z0-9_.-]*))?=["\']([^"\']+)["\']',
            raw_xml.decode("utf-8"),
        ):
            ns_map[prefix if prefix else ""] = uri
            ET.register_namespace(prefix if prefix else "", uri)

        root = ET.fromstring(raw_xml)

        # Locate <PackageSettings> inside the first (default) <Policy>.
        # Structure: PolicyContent/Policies/Policy/PackageSettings
        pkg_settings = root.find(".//{*}PackageSettings") or root.find(
            ".//PackageSettings"
        )
        if pkg_settings is None:
            # Fallback: walk to Policy element and create PackageSettings.
            policy_elem = root.find(".//{*}Policy") or root.find(".//Policy")
            if policy_elem is None:
                raise VCFOpsError(
                    "policy XML has no <Policy> element — cannot inject SM"
                )
            pkg_settings = ET.SubElement(policy_elem, "PackageSettings")

        # Before adding fresh entries, purge any stale <SuperMetric id="sm_id">
        # from ALL <SuperMetrics> blocks in PackageSettings.  A stale entry
        # (e.g. from a prior broken /assign call) causes the policy import to
        # be a no-op — the server sees no change and silently skips enablement.
        # Removing first guarantees the import reflects a real state change.
        all_sm_blocks = (
            pkg_settings.findall("{*}SuperMetrics")
            or pkg_settings.findall("SuperMetrics")
        )
        for block in all_sm_blocks:
            for entry in list(block):
                entry_tag = entry.tag.split("}")[-1] if "}" in entry.tag else entry.tag
                if entry_tag == "SuperMetric" and entry.get("id") == sm_id:
                    block.remove(entry)

        for rk in normalised_rks:
            adapter_kind = rk["adapterKind"]
            resource_kind = rk["resourceKind"]

            # Find existing <SuperMetrics> block or create one.
            sm_block = None
            for candidate in (
                pkg_settings.findall("{*}SuperMetrics")
                or pkg_settings.findall("SuperMetrics")
            ):
                if (
                    candidate.get("adapterKind") == adapter_kind
                    and candidate.get("resourceKind") == resource_kind
                ):
                    sm_block = candidate
                    break

            if sm_block is None:
                sm_block = ET.SubElement(
                    pkg_settings,
                    "SuperMetrics",
                    {"adapterKind": adapter_kind, "resourceKind": resource_kind},
                )

            # Always add a fresh entry — any stale copy was removed above.
            ET.SubElement(
                sm_block,
                "SuperMetric",
                {"enabled": "true", "id": sm_id},
            )

        # Serialise back to bytes — ET.tostring produces ASCII-safe XML.
        edited_xml = ET.tostring(root, encoding="unicode", xml_declaration=False)
        # Prepend the XML declaration that ET strips by default.
        if not edited_xml.startswith("<?xml"):
            edited_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + edited_xml
        edited_xml_bytes = edited_xml.encode("utf-8")

        # Rebuild ZIP with edited XML in place.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(xml_name, edited_xml_bytes)
            for name, data in other_files.items():
                zf.writestr(name, data)

        self._import_policy_zip(buf.getvalue())

    # ---- content-zip import (UUID-preserving) ---------------------------
    def import_supermetrics_bundle(self, supermetrics: Iterable[dict]) -> dict:
        """Install super metrics via the content import endpoint, which
        preserves caller-supplied UUIDs verbatim.

        Each dict must carry: id, name, formula, description, unitId,
        resourceKinds=[{resourceKindKey, adapterKindKey}, ...]. Unlike
        POST /api/supermetrics, this path keeps ``sm_<uuid>`` formula
        cross-references stable across re-installs and across instances.

        Wire format verified by api-explorer against a live instance —
        see context/wire_formats.md §"Super metrics zip".
        """
        # Imported lazily to avoid a hard package dep at import time.
        from vcfops_dashboards.client import (
            discover_marker_filename,
            get_current_user,
            import_content_zip,
        )

        sms = list(supermetrics)
        if not sms:
            raise VCFOpsError("import_supermetrics_bundle: empty bundle")

        owner = get_current_user(self)["id"]
        if self._marker_filename is None:
            self._marker_filename = discover_marker_filename(self)
        marker = self._marker_filename

        sm_dict: dict = {}
        for sm in sms:
            sm_id = sm.get("id")
            if not sm_id:
                raise VCFOpsError(
                    f"super metric '{sm.get('name')}' has no id — cannot "
                    f"round-trip via content-zip import"
                )
            sm_dict[sm_id] = {
                "name": sm["name"],
                "formula": self._normalize_formula(sm["formula"]),
                "description": sm.get("description", "") or "",
                "unitId": sm.get("unitId", "") or "",
                "resourceKinds": sm.get("resourceKinds") or [],
            }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(marker, owner)
            z.writestr("supermetrics.json", json.dumps(sm_dict, indent=3))
            z.writestr(
                "configuration.json",
                json.dumps({"superMetrics": len(sm_dict), "type": "ALL"}, indent=3),
            )
        zip_bytes = buf.getvalue()
        result = import_content_zip(self, zip_bytes)

        # Ghost-state recovery: the content-zip importer will "skip" an SM
        # that already exists in the DB but failed to fully register in the
        # internal SM catalog (e.g. from a previous partial import). The SM
        # is queryable by GET /{id} but absent from the list API and invisible
        # to the assign endpoint, so enable returns 404.  A second import of
        # the same bundle re-registers the SM fully and the importer then
        # reports it as "imported".  Detect the all-skipped signal and retry
        # once automatically.
        summaries = result.get("operationSummaries") or []
        sm_summaries = [s for s in summaries if s.get("contentType") == "SUPER_METRICS"]
        if sm_summaries:
            total_imported = sum(int(s.get("imported") or 0) for s in sm_summaries)
            total_skipped = sum(int(s.get("skipped") or 0) for s in sm_summaries)
            if total_imported == 0 and total_skipped > 0:
                # All entries were skipped — likely ghost-state SMs.  Re-import
                # once to force catalog re-registration.
                result = import_content_zip(self, zip_bytes)

        return result

    def delete_supermetric(self, sm_id: str) -> None:
        r = self._request("DELETE", f"/api/supermetrics/{sm_id}")
        if r.status_code not in (200, 204):
            raise VCFOpsError(f"delete failed ({r.status_code}): {r.text}")
