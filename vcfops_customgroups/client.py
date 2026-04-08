"""VCF Operations Suite API client for custom groups + group types.

Custom groups are NOT installed via the content-zip importer used
by super metrics / dashboards / views. They use direct REST against
`/api/resources/groups` and `/api/resources/groups/types`.

Identity model differs from the rest of the repo: the server
assigns the custom group `id` on create, so cross-instance sync
matches by `resourceKey.name`, not by UUID. Group types are
identified by their `key` string, which the server sets equal to
the `name` on POST when `key` is omitted.

See context/customgroup_authoring.md and context/wire_formats.md
§"Custom groups (dynamic)" for the full wire grammar.
"""
from __future__ import annotations

import os
from typing import Iterator, List, Optional

import requests


class VCFOpsCustomGroupError(RuntimeError):
    pass


class VCFOpsCustomGroupClient:
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

    # ---- env constructor ----------------------------------------
    @classmethod
    def from_env(cls) -> "VCFOpsCustomGroupClient":
        try:
            host = os.environ["VCFOPS_HOST"]
            user = os.environ["VCFOPS_USER"]
            pw = os.environ["VCFOPS_PASSWORD"]
        except KeyError as e:
            raise VCFOpsCustomGroupError(
                f"Missing env var: {e.args[0]}"
            ) from None
        return cls(
            host=host,
            username=user,
            password=pw,
            auth_source=os.environ.get("VCFOPS_AUTH_SOURCE", "Local"),
            verify_ssl=os.environ.get("VCFOPS_VERIFY_SSL", "true").lower()
            != "false",
        )

    # ---- auth ----------------------------------------------------
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
            raise VCFOpsCustomGroupError(
                f"auth failed ({r.status_code}): {r.text}"
            )
        self._token = r.json()["token"]
        self._session.headers["Authorization"] = (
            f"vRealizeOpsToken {self._token}"
        )

    def _ensure_auth(self) -> None:
        if not self._token:
            self.authenticate()

    def _request(self, method: str, path: str, **kw) -> requests.Response:
        self._ensure_auth()
        r = self._session.request(method, f"{self.base}{path}", **kw)
        if r.status_code == 401:
            self._token = None
            self._ensure_auth()
            r = self._session.request(method, f"{self.base}{path}", **kw)
        return r

    # ---- group types --------------------------------------------
    def list_group_types(self) -> List[dict]:
        r = self._request("GET", "/api/resources/groups/types")
        if r.status_code != 200:
            raise VCFOpsCustomGroupError(
                f"list types failed ({r.status_code}): {r.text}"
            )
        return r.json().get("groupTypes") or []

    def find_group_type(self, name_or_key: str) -> Optional[dict]:
        for t in self.list_group_types():
            if t.get("key") == name_or_key or t.get("name") == name_or_key:
                return t
        return None

    def create_group_type(self, name: str) -> dict:
        """POST a new group type. Server sets `key=name` and returns
        201 with an empty body, so we GET the list afterward and
        return the matching entry."""
        r = self._request(
            "POST",
            "/api/resources/groups/types",
            json={"name": name},
        )
        if r.status_code not in (200, 201):
            raise VCFOpsCustomGroupError(
                f"create type {name!r} failed ({r.status_code}): {r.text}"
            )
        t = self.find_group_type(name)
        if not t:
            raise VCFOpsCustomGroupError(
                f"created type {name!r} but not found in subsequent list"
            )
        return t

    def ensure_group_type(self, name: str) -> tuple[str, dict]:
        """Idempotent: return ('exists'|'created', type_dict)."""
        existing = self.find_group_type(name)
        if existing:
            return ("exists", existing)
        return ("created", self.create_group_type(name))

    def delete_group_type(self, key: str) -> None:
        r = self._request(
            "DELETE", f"/api/resources/groups/types/{key}"
        )
        if r.status_code not in (200, 204):
            raise VCFOpsCustomGroupError(
                f"delete type {key!r} failed ({r.status_code}): {r.text}"
            )

    # ---- groups -------------------------------------------------
    def list_groups(self, page_size: int = 1000) -> Iterator[dict]:
        page = 0
        while True:
            r = self._request(
                "GET",
                "/api/resources/groups",
                params={"page": page, "pageSize": page_size},
            )
            if r.status_code != 200:
                raise VCFOpsCustomGroupError(
                    f"list groups failed ({r.status_code}): {r.text}"
                )
            body = r.json()
            items = body.get("groups") or []
            for g in items:
                yield g
            info = body.get("pageInfo") or {}
            total = info.get("totalCount", len(items))
            if (page + 1) * page_size >= total or not items:
                return
            page += 1

    def find_group_by_name(self, name: str) -> Optional[dict]:
        """Match on `resourceKey.name`. Filters out built-in container
        resources by requiring `adapterKindKey == 'Container'`."""
        for g in self.list_groups():
            rk = g.get("resourceKey") or {}
            if (
                rk.get("adapterKindKey") == "Container"
                and rk.get("name") == name
            ):
                return g
        return None

    def create_group(self, body: dict) -> dict:
        r = self._request(
            "POST", "/api/resources/groups", json=body
        )
        if r.status_code not in (200, 201):
            raise VCFOpsCustomGroupError(
                f"create group failed ({r.status_code}): {r.text}"
            )
        return r.json()

    def update_group(self, group_id: str, body: dict) -> dict:
        body = dict(body)
        body["id"] = group_id
        r = self._request("PUT", "/api/resources/groups", json=body)
        if r.status_code != 200:
            raise VCFOpsCustomGroupError(
                f"update group failed ({r.status_code}): {r.text}"
            )
        return r.json()

    def delete_group(self, group_id: str) -> None:
        r = self._request(
            "DELETE", f"/api/resources/groups/{group_id}"
        )
        if r.status_code not in (200, 204):
            raise VCFOpsCustomGroupError(
                f"delete group failed ({r.status_code}): {r.text}"
            )

    def upsert_group(self, body: dict) -> tuple[str, dict]:
        """Create or update by `resourceKey.name`. Returns
        ('created'|'updated', group_dict). Refuses to update if the
        existing group's `resourceKindKey` (its type) differs from
        the incoming body's — that's a rename of the group's type,
        which the API has no in-place support for and would orphan
        history. Caller can delete + recreate manually if needed.
        """
        name = body["resourceKey"]["name"]
        existing = self.find_group_by_name(name)
        if existing:
            old_type = (existing.get("resourceKey") or {}).get(
                "resourceKindKey"
            )
            new_type = body["resourceKey"]["resourceKindKey"]
            if old_type != new_type:
                raise VCFOpsCustomGroupError(
                    f"refusing to update {name!r}: existing type "
                    f"{old_type!r} differs from YAML type {new_type!r}. "
                    f"VCF Ops has no in-place type change; delete the "
                    f"group on the instance first if this is intentional."
                )
            updated = self.update_group(existing["id"], body)
            return ("updated", updated)
        created = self.create_group(body)
        return ("created", created)
