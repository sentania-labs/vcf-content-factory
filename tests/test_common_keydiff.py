"""Key differential CLI (vcfcf_common.keydiff), toolset gap T5 of the vCommunity
Java port design (section 11).

No live instance: a fake Suite API serves recorded instance state from
``tests/fixtures/keydiff/two_instances.json`` and implements the three GET
endpoints the CLI reads (paging, the server-side name match, resourceId
filtering). Every request is recorded so the tests can prove the CLI is
read-only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from vcfcf_common import keydiff
from vcfcf_common.__main__ import main as common_main

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "keydiff" / "two_instances.json").read_text(
        encoding="utf-8"))
NOW = FIXTURE["now"]
VC1 = FIXTURE["vc1"]
VC2 = FIXTURE["vc2"]


class _Resp:
    def __init__(self, code: int, body: Any):
        self.status_code = code
        self._body = body

    def json(self):
        if isinstance(self._body, str):
            raise ValueError("not json")
        return self._body


class FakeOps:
    """A recorded instance behind the three GET endpoints keydiff reads."""

    def __init__(self, side: str, fail: Dict[str, int] = None):
        self.state = FIXTURE[side]
        self.calls: List[Tuple[str, str, List[Tuple[str, Any]]]] = []
        self.base = f"https://ops-{side}.example.test/suite-api"
        self.fail = fail or {}

    def _resource(self, r: dict) -> dict:
        idents = []
        if "vcid" in r:
            idents.append({"identifierType": {"name": "VMEntityVCID"}, "value": r["vcid"]})
        if "moid" in r:
            idents.append({"identifierType": {"name": "VMEntityObjectID"}, "value": r["moid"]})
        return {"identifier": r["id"], "resourceKey": {
            "name": r["name"], "adapterKindKey": r["ak"], "resourceKindKey": r["rk"],
            "resourceIdentifiers": idents}}

    def _request(self, method: str, path: str, params=None, **kw):
        params = list(params or [])
        self.calls.append((method, path, params))
        if path in self.fail:
            return _Resp(self.fail[path], "error")
        q: Dict[str, List[Any]] = {}
        for k, v in params:
            q.setdefault(k, []).append(v)
        if path == "/api/resources":
            rows = self.state["resources"]
            if "adapterKind" in q:
                rows = [r for r in rows if r["ak"] in q["adapterKind"]]
            if "resourceKind" in q:
                rows = [r for r in rows if r["rk"] in q["resourceKind"]]
            if "name" in q:  # the server's match is a contains match
                rows = [r for r in rows if q["name"][0].lower() in r["name"].lower()]
            page, size = int(q.get("page", [0])[0]), int(q.get("pageSize", [1000])[0])
            chunk = rows[page * size:(page + 1) * size]
            return _Resp(200, {"pageInfo": {"totalCount": len(rows), "page": page},
                               "resourceList": [self._resource(r) for r in chunk]})
        if path == "/api/resources/stats/latest":
            values = []
            for rid in q.get("resourceId", []):
                stats = self.state["stats"].get(rid)
                if not stats:
                    continue
                values.append({"resourceId": rid, "stat-list": {"stat": [
                    {"statKey": {"key": k}, "timestamps": [ts], "data": [v]}
                    for k, (v, ts) in stats.items()]}})
            return _Resp(200, {"values": values})
        if path == "/api/resources/properties":
            out = []
            for rid in q.get("resourceId", []):
                props = self.state["properties"].get(rid)
                if props:
                    out.append({"resourceId": rid, "property": [
                        {"name": k, "value": v} for k, v in props.items()]})
            return _Resp(200, {"resourcePropertiesList": out})
        return _Resp(404, "no such path")


def _factory(clients: Dict[str, FakeOps]):
    return lambda profile: clients[profile]


def _run(argv, clients=None, capsys=None):
    clients = clients or {"a": FakeOps("a"), "b": FakeOps("b")}
    rc = keydiff.main(argv, client_factory=_factory(clients))
    out = capsys.readouterr() if capsys else None
    return rc, clients, out


def _rows(tsv: str) -> List[Dict[str, str]]:
    lines = tsv.rstrip("\n").split("\n")
    header = lines[0].split("\t")
    return [dict(zip(header, line.split("\t"))) for line in lines[1:]]


def _find(rows, category=None, key=None, identity=None):
    return [r for r in rows if (category is None or r["category"] == category)
            and (key is None or r["key"] == key)
            and (identity is None or r["identity"] == identity)]


HOSTS = ["--adapter-kind", "VMWARE", "--resource-kind", "HostSystem",
         "--key-prefix", "vCommunity|"]


def test_live_compare_categories_and_read_only(capsys):
    rc, clients, out = _run(["--profile", "a", "--profile", "b", *HOSTS,
                             "--format", "tsv"], capsys=capsys)
    assert rc == 1
    rows = _rows(out.out)
    h12vc1 = f"vc={VC1} moid=host-12"
    h12vc2 = f"vc={VC2} moid=host-12"
    assert _find(rows, "match", "vCommunity|NIC Count", h12vc1)
    assert _find(rows, "differ", "vCommunity|KPI", h12vc1)  # tolerance 0
    assert _find(rows, "only_a", "vCommunity|Legacy", h12vc1)
    assert _find(rows, "only_b", "vCommunity|Remaining Days", h12vc1)
    assert _find(rows, "match", "vCommunity|HA Enabled", h12vc1)
    assert _find(rows, "differ", "vCommunity|Version", h12vc1)
    assert _find(rows, "object_only_a", identity=f"vc={VC1} moid=host-13")
    # host-12 in vCenter 2 matched to itself despite a different name.
    m = _find(rows, "match", "vCommunity|NIC Count", h12vc2)
    assert m and m[0]["object_a"] == "esx01.vc2" and m[0]["object_b"] == "esx01-renamed.vc2"
    # Key prefix filter: cpu| and summary| keys never compared.
    assert not [r for r in rows if r["key"].startswith(("cpu|", "summary|"))]
    for c in clients.values():
        assert {m for m, _, _ in c.calls} == {"GET"}, "keydiff must only GET"
        assert {p for _, p, _ in c.calls} <= {
            "/api/resources", "/api/resources/stats/latest", "/api/resources/properties"}


def test_moid_never_crosses_vcenters():
    a = keydiff.capture(FakeOps("a"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|"], source={}, now_ms=NOW)
    b = keydiff.capture(FakeOps("b"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|"], source={}, now_ms=NOW)
    res = keydiff.compare(a, b)
    nic = {r["identity"]: (r["value_a"], r["value_b"]) for r in res["rows"]
           if r["key"] == "vCommunity|NIC Count" and r["category"] == "match"}
    assert nic[f"vc={VC1} moid=host-12"] == (4.0, 4.0)
    assert nic[f"vc={VC2} moid=host-12"] == (2.0, 2.0)
    # Upper-case VCID on side A normalized: still one identity for vc1 host-12.
    assert len([r for r in res["rows"] if r["identity"] == f"vc={VC1} moid=host-12"
                and r["key"] == "vCommunity|NIC Count"]) == 1


def test_vmware_without_vcid_is_not_matched_by_name(capsys):
    rc, _, out = _run(["--profile", "a", "--profile", "b", *HOSTS], capsys=capsys)
    assert "orphan-host" in out.out
    assert "not matched by name" in out.out
    a = keydiff.capture(FakeOps("a"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=[], source={}, now_ms=NOW)
    assert [u["name"] for u in a["unidentified"]] == ["orphan-host"]
    assert all(o["name"] != "orphan-host" for o in a["objects"])


def test_tolerances():
    a = keydiff.capture(FakeOps("a"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|KPI"], source={}, now_ms=NOW)
    b = keydiff.capture(FakeOps("b"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|KPI"], source={}, now_ms=NOW)

    def cat(**kw):
        rows = [r for r in keydiff.compare(a, b, **kw)["rows"] if r["key"] == "vCommunity|KPI"]
        assert len(rows) == 1
        return rows[0]

    assert cat()["category"] == "differ"
    assert cat()["delta"] == pytest.approx(0.004)
    assert cat(tolerance=0.01)["category"] == "match"
    assert cat(tolerance=0.001)["category"] == "differ"
    assert cat(rel_tolerance=0.0001)["category"] == "match"  # 0.0001 * 99.004 > 0.004


def test_property_numbers_compare_exactly_without_tolerance():
    a = keydiff.capture(FakeOps("a"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|"], source={}, now_ms=NOW)
    b = keydiff.capture(FakeOps("b"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|"], source={}, now_ms=NOW)
    rows = keydiff.compare(a, b, tolerance=0.01)["rows"]
    by_key = {(r["identity"], r["key"]): r["category"] for r in rows}
    ident = f"vc={VC1} moid=host-12"
    assert by_key[(ident, "vCommunity|Maintenance Mode Required")] == "match"  # "1.0" == "1"
    assert by_key[(ident, "vCommunity|Threshold")] == "differ"  # no tolerance for properties


def test_staleness_window_applies_to_stats_only():
    a = keydiff.capture(FakeOps("a"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|"], source={}, now_ms=NOW)
    b = keydiff.capture(FakeOps("b"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=["vCommunity|"], source={}, now_ms=NOW)
    ident = f"vc={VC1} moid=host-12"
    plain = {r["key"]: r["category"] for r in keydiff.compare(a, b)["rows"]
             if r["identity"] == ident}
    windowed = {r["key"]: r["category"] for r in keydiff.compare(a, b, stale_hours=24)["rows"]
                if r["identity"] == ident}
    assert plain["vCommunity|Old"] == "differ"
    assert windowed["vCommunity|Old"] == "stale"  # B's sample is ~3 days old
    assert windowed["vCommunity|NIC Count"] == "match"
    assert windowed["vCommunity|Version"] == "differ"  # properties never stale


def test_snapshot_round_trip_equals_live(tmp_path, capsys):
    sa, sb = tmp_path / "a.json", tmp_path / "b.json"
    assert _run(["--profile", "a", *HOSTS, "--snapshot-out", str(sa)])[0] == 0
    assert _run(["--profile", "b", *HOSTS, "--snapshot-out", str(sb)])[0] == 0
    capsys.readouterr()
    doc = json.loads(sa.read_text(encoding="utf-8"))
    assert doc["format"] == keydiff.SNAPSHOT_FORMAT
    assert doc["source"]["profile"] == "a"
    assert doc["scope"]["adapter_kind"] == "VMWARE"
    assert "password" not in sa.read_text(encoding="utf-8").lower()
    rc_off = keydiff.main(["--snapshot-in", str(sa), "--snapshot-in", str(sb),
                           "--format", "tsv"])
    off = capsys.readouterr().out
    rc_live, _, live = _run(["--profile", "a", "--profile", "b", *HOSTS, "--format", "tsv"],
                            capsys=capsys)
    assert rc_off == rc_live == 1
    assert off == live.out
    # Mixed: a snapshot taken earlier against a live side now.
    rc_mix, clients, mixed = _run(["--snapshot-in", str(sa), "--profile", "b", *HOSTS,
                                   "--format", "tsv"], capsys=capsys)
    assert rc_mix == 1 and mixed.out == live.out
    assert clients["a"].calls == []


def test_own_kinds_match_on_kind_and_name_across_renamed_adapter_kind(tmp_path, capsys):
    tsv = tmp_path / "out.tsv"
    rc, _, out = _run(["--profile", "a", "--profile", "b", "--adapter-kind", "vCommunity",
                       "--b-adapter-kind", "vcfcf_vcommunity", "--resource-kind",
                       "Content Library", "--tsv-out", str(tsv)], capsys=capsys)
    assert rc == 1
    rows = _rows(tsv.read_text(encoding="utf-8"))
    assert _find(rows, "match", "vCommunity|Items", "kind=Content Library name=Library A")
    assert _find(rows, "object_only_a", identity="kind=Content Library name=Library B")
    assert _find(rows, "object_only_b", identity="kind=Content Library name=Library C")
    # A value carrying a tab and a newline stays on one TSV row, one cell.
    t = _find(rows, "match", "vCommunity|Type")
    assert t and t[0]["value_a"] == "LOCAL\\tsubscribed\\nyes"
    assert "summary:" in out.out


def test_name_scope_keeps_exact_names_only(capsys):
    rc, clients, out = _run(["--profile", "a", "--profile", "b", "--name", "esx01.vc1",
                             "--key-prefix", "vCommunity|NIC", "--format", "tsv"],
                            capsys=capsys)
    rows = _rows(out.out)
    assert {r["identity"] for r in rows} == {f"vc={VC1} moid=host-12"}
    assert rc == 0
    names = [dict(p).get("name") for _, path, p in clients["a"].calls if path == "/api/resources"]
    assert names == ["esx01.vc1"]


def test_ambiguous_identity_is_reported_not_compared():
    a = keydiff.capture(FakeOps("a"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=[], key_prefixes=[], source={}, now_ms=NOW)
    dup = json.loads(json.dumps(a))
    first = dup["objects"][0]
    dup["objects"].append(dict(first, resource_id="dddddddd-0000-4000-8000-000000000001"))
    res = keydiff.compare(dup, a)
    ident = keydiff.identity_label(first["identity"])
    assert not [r for r in res["rows"] if r["identity"] == ident and r["category"] != "object_only_b"]
    assert any("2 objects share" in u["reason"] for u in res["unidentified"])


def test_pagination(monkeypatch):
    monkeypatch.setattr(keydiff, "PAGE_SIZE", 2)
    monkeypatch.setattr(keydiff, "IDS_PER_GET", 1)
    c = FakeOps("a")
    doc = keydiff.capture(c, adapter_kind="VMWARE", resource_kind="HostSystem", names=[],
                          key_prefixes=[], source={}, now_ms=NOW)
    assert len(doc["objects"]) + len(doc["unidentified"]) == 4
    pages = [dict(p)["page"] for _, path, p in c.calls if path == "/api/resources"]
    assert pages == [0, 1]


def test_no_differences_exits_zero(capsys):
    rc, _, out = _run(["--profile", "a", "--profile", "a", *HOSTS], capsys=capsys)
    assert rc == 0
    assert "no differences" in out.out
    rc2, _, out2 = _run(["--profile", "a", "--profile", "a", *HOSTS, "--show-matches"],
                        capsys=capsys)
    assert rc2 == 0 and "vCommunity|NIC Count" in out2.out


@pytest.mark.parametrize("argv", [
    [],
    ["--profile", "a"],
    ["--profile", "a", "--profile", "b", "--profile", "c", *HOSTS],
    ["--profile", "a", "--profile", "b"],  # live without scope
    ["--profile", "a", "--adapter-kind", "VMWARE", "--profile", "b"],  # half a kind scope
    ["--profile", "a", "--profile", "b", *HOSTS, "--snapshot-out", "x.json"],
    ["--snapshot-in", "x.json", "--snapshot-out", "y.json"],
    ["--profile", "a", "--profile", "b", *HOSTS, "--tolerance", "-1"],
    ["--profile", "a", "--profile", "b", *HOSTS, "--tolerance", "nan"],
    ["--profile", "a", "--profile", "b", *HOSTS, "--stale-hours", "0"],
    ["--bogus"],
])
def test_usage_errors_exit_2(argv, capsys):
    rc, clients, _ = _run(argv, capsys=capsys)
    assert rc == 2
    assert all(c.calls == [] for c in clients.values())


def test_fetch_and_snapshot_failures_exit_3(tmp_path, capsys):
    clients = {"a": FakeOps("a", fail={"/api/resources/stats/latest": 500}), "b": FakeOps("b")}
    rc, _, out = _run(["--profile", "a", "--profile", "b", *HOSTS], clients, capsys)
    assert rc == 3 and "HTTP 500" in out.err
    bad = tmp_path / "bad.json"
    bad.write_text('{"format": "something-else"}', encoding="utf-8")
    rc2 = keydiff.main(["--snapshot-in", str(bad), "--snapshot-in", str(bad)])
    assert rc2 == 3
    rc3 = keydiff.main(["--snapshot-in", str(tmp_path / "missing.json"),
                        "--snapshot-in", str(bad)])
    assert rc3 == 3


def test_dispatch_from_vcfcf_common(tmp_path, capsys):
    assert common_main(["keydiff", "--help"]) == 0
    assert "--snapshot-out" in capsys.readouterr().out
    assert common_main(["--help"]) == 0
    assert "keydiff" in capsys.readouterr().out
