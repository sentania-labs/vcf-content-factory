"""Key differential CLI (vcfcf_common.keydiff): a port's parity check.

No live instance: a fake Suite API serves recorded instance state from
``tests/fixtures/keydiff/two_instances.json`` and implements the three GET
endpoints the CLI reads (paging, the server-side name match, resourceId
filtering). Every request is recorded so the tests can prove the CLI is
read-only.
"""
from __future__ import annotations

import json
from decimal import Decimal
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
    assert cat()["delta"] == Decimal("0.004")  # exact, not a float difference
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


# --- exact numeric comparison (Codex PR 355: no float rounding) -------------

def _doc(props=None, stats=None):
    """A one-object snapshot (a non-VMWARE object, matched on kind plus name)."""
    return {"format": keydiff.SNAPSHOT_FORMAT, "captured_at": NOW, "source": {},
            "scope": {}, "unidentified": [], "objects": [{
                "name": "obj", "adapter_kind": "X", "resource_kind": "K",
                "resource_id": "r1", "identity": ["kind_name", "K", "obj"],
                "properties": {k: {"value": v} for k, v in (props or {}).items()},
                "stats": {k: {"value": v, "ts": NOW} for k, v in (stats or {}).items()}}]}


def _prop_row(va, vb, **kw):
    res = keydiff.compare(_doc(props={"p": va}), _doc(props={"p": vb}), **kw)
    (row,) = res["rows"]
    return row, keydiff.exit_code(res)


def _stat_row(va, vb, **kw):
    res = keydiff.compare(_doc(stats={"s": va}), _doc(stats={"s": vb}), **kw)
    (row,) = res["rows"]
    return row, keydiff.exit_code(res)


def test_reviewer_example_large_integers_differ(tmp_path, capsys):
    row, code = _prop_row("9007199254740992", "9007199254740993")
    assert row["category"] == "differ" and code == keydiff.EXIT_DIFFER == 1
    assert row["delta"] == 1
    # Through the CLI, both output formats, the values shown as read.
    sa, sb = tmp_path / "a.json", tmp_path / "b.json"
    keydiff.write_snapshot(_doc(props={"p": "9007199254740992"}), str(sa))
    keydiff.write_snapshot(_doc(props={"p": "9007199254740993"}), str(sb))
    assert keydiff.main(["--snapshot-in", str(sa), "--snapshot-in", str(sb),
                         "--format", "tsv"]) == 1
    (r,) = _rows(capsys.readouterr().out)
    assert (r["category"], r["value_a"], r["value_b"], r["delta"]) == (
        "differ", "9007199254740992", "9007199254740993", "1")
    assert keydiff.main(["--snapshot-in", str(sa), "--snapshot-in", str(sb)]) == 1
    table = capsys.readouterr().out
    assert "9007199254740992" in table and "9007199254740993" in table


def test_equal_plain_decimals_match():
    assert _prop_row("5", "5.0")[0]["category"] == "match"
    assert _prop_row("-0.50", "-0.5")[0]["category"] == "match"
    assert _stat_row(5, 5.0)[0]["category"] == "match"


def test_thirty_digit_integers_differing_in_last_digit():
    a, b = "123456789012345678901234567890", "123456789012345678901234567891"
    row, code = _prop_row(a, b)
    assert row["category"] == "differ" and code == 1 and row["delta"] == 1
    # As JSON integers (stats): exact too, at any size.
    row, code = _stat_row(int(a), int(b))
    assert row["category"] == "differ" and code == 1 and row["delta"] == 1
    assert _stat_row(int(a), int(a))[0]["category"] == "match"


def test_high_precision_decimals_differ_past_17_significant_digits():
    a, b = "0.123456789012345678901", "0.123456789012345678902"
    assert float(a) == float(b)  # the bug: a float comparison calls these equal
    row, code = _prop_row(a, b)
    assert row["category"] == "differ" and code == 1
    assert row["delta"] == Decimal("1E-21")
    assert keydiff._cell(row["delta"]) == "0.000000000000000000001"


def test_stat_tolerance_at_large_magnitude():
    a = 10 ** 20
    # Absolute tolerance 5: a difference of 5 is within it, 6 is not.
    row, _ = _stat_row(a, a + 5, tolerance=5)
    assert row["category"] == "match" and row["delta"] == 5  # tolerated, not identical
    row, code = _stat_row(a, a + 6, tolerance=5)
    assert row["category"] == "differ" and code == 1
    # Relative 1e-19 of the larger magnitude (1e20 + 10) allows 10.000...001.
    assert _stat_row(a, a + 10, rel_tolerance=1e-19)[0]["category"] == "match"
    assert _stat_row(a, a + 11, rel_tolerance=1e-19)[0]["category"] == "differ"
    # Without tolerance the same large pair is never an exact match.
    assert _stat_row(a, a + 1)[0]["category"] == "differ"
    # Distinct doubles stay distinct.
    assert _stat_row(2.0 ** 53, 2.0 ** 53 + 2)[0]["category"] == "differ"


def test_tolerance_never_applies_to_properties():
    assert _prop_row("100", "100.5", tolerance=1)[0]["category"] == "differ"
    assert _prop_row("100", "101", rel_tolerance=0.5)[0]["category"] == "differ"


@pytest.mark.parametrize("va,vb,category", [
    ("abc", "abc", "match"),
    ("abc", "abd", "differ"),
    ("", "", "match"),
    ("", "0", "differ"),
    ("true", "true", "match"),
    ("true", "1", "differ"),
    ("NaN", "NaN", "match"),
    ("NaN", "nan", "differ"),
    ("Infinity", "inf", "differ"),
    ("1E3", "1000", "differ"),      # exponent forms are strings
    ("1e3", "1e3", "match"),
    (" 5", "5", "differ"),          # whitespace makes a string
    ("5 ", "5 ", "match"),
    ("1,000", "1000", "differ"),    # thousands separators make a string
    ("1,000", "1,000", "match"),
    ("\u0665", "5", "differ"),      # non-ASCII digits are not plain decimals
    (None, None, "match"),
    (None, "", "differ"),
])
def test_non_plain_decimals_compare_as_strings(va, vb, category):
    assert _prop_row(va, vb)[0]["category"] == category


def test_json_booleans_and_non_finite_floats():
    assert _stat_row(True, 1)[0]["category"] == "differ"
    assert _stat_row(True, True)[0]["category"] == "match"
    assert _stat_row(float("nan"), float("nan"))[0]["category"] == "match"
    assert _stat_row(float("inf"), float("-inf"))[0]["category"] == "differ"


def test_large_value_displayed_unchanged_in_both_formats():
    big = "123456789012345678901234567890.123456789"
    res = keydiff.compare(_doc(props={"p": big}), _doc(props={"p": big}))
    (r,) = _rows(keydiff.to_tsv(res))
    assert r["value_a"] == r["value_b"] == big and r["delta"] == "0"
    table = keydiff.to_table(res, show_matches=True, width=200)
    assert big in table and "1.2345678901234568e+29" not in table
    # A JSON integer stat beyond 2^53 too.
    n = 2 ** 64 + 1
    res = keydiff.compare(_doc(stats={"s": n}), _doc(stats={"s": n}))
    (r,) = _rows(keydiff.to_tsv(res))
    assert r["value_a"] == str(n) and r["category"] == "match"
    assert str(n) in keydiff.to_table(res, show_matches=True, width=200)


def test_help_describes_exact_comparison(capsys):
    assert keydiff.main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "values compare exactly" in out
    assert "no tolerance ever" in out
    assert "stats only" in out


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


LIBS = ["--adapter-kind", "vCommunity", "--resource-kind", "Content Library"]


def test_no_differences_exits_zero(capsys):
    rc, _, out = _run(["--profile", "a", "--profile", "a", *LIBS], capsys=capsys)
    assert rc == keydiff.EXIT_OK == 0
    assert "no differences" in out.out
    assert "compared: objects a=2 b=2 on both=2;" in out.out
    rc2, _, out2 = _run(["--profile", "a", "--profile", "a", *LIBS, "--show-matches"],
                        capsys=capsys)
    assert rc2 == 0 and "vCommunity|Items" in out2.out


def _counts(out_text: str) -> str:
    return [line for line in out_text.splitlines() if line.startswith("compared:")][0]


def test_b3a_two_empty_scopes_exit_4(capsys):
    rc, _, out = _run(["--profile", "a", "--profile", "b", "--adapter-kind", "VMWARE",
                       "--resource-kind", "Datastore"], capsys=capsys)
    assert rc == keydiff.EXIT_NOTHING_COMPARED == 4
    assert _counts(out.out) == ("compared: objects a=0 b=0 on both=0; keys a=0 b=0 on both=0"
                                " (stale 0); objects not compared: 0 (a=0 b=0)")
    assert "NOTHING COMPARED (no object is on both sides)" in out.out


def test_b3b_every_object_unidentified_exit_4(capsys):
    # A VMWARE listing without VMEntityVCID/VMEntityObjectID: never name-matched.
    rc, _, out = _run(["--profile", "a", "--profile", "a", "--name", "orphan-host"],
                      capsys=capsys)
    assert rc == 4
    assert "on both=0" in _counts(out.out)
    assert "objects not compared: 2 (a=1 b=1)" in _counts(out.out)
    assert "orphan-host" in out.out


def test_b3c_key_prefix_matching_nothing_exit_4(capsys):
    rc, _, out = _run(["--profile", "a", "--profile", "b", "--adapter-kind", "VMWARE",
                       "--resource-kind", "HostSystem", "--key-prefix", "noSuchGroup|"],
                      capsys=capsys)
    assert rc == 4  # objects on one side only are differences, but no key was compared
    assert "keys a=0 b=0 on both=0" in _counts(out.out)
    assert "no key is on both sides of a matched object" in out.out


def test_b3d_every_compared_row_stale_exit_4(capsys):
    a = keydiff.capture(FakeOps("a"), adapter_kind="VMWARE", resource_kind="HostSystem",
                        names=["esx01.vc1"], key_prefixes=["vCommunity|NIC"], source={},
                        now_ms=NOW + 10 * 86400_000)
    res = keydiff.compare(a, a, stale_hours=24)
    assert res["compared"]["keys_both"] == res["compared"]["keys_stale"] == 1
    assert keydiff.exit_code(res) == 4
    assert "every key on both sides is stale" in keydiff.verdict_line(res)
    # Through the CLI: the live capture time is now, the fixture samples are older.
    rc, _, out = _run(["--profile", "a", "--profile", "a", "--name", "esx01.vc1",
                       "--key-prefix", "vCommunity|NIC", "--stale-hours", "1"], capsys=capsys)
    assert rc == 4 and "(stale 1)" in _counts(out.out)


def test_unidentified_vmware_objects_make_the_run_non_zero(capsys):
    # Everything compared matches, but orphan-host (no VCID) was not compared.
    rc, _, out = _run(["--profile", "a", "--profile", "a", *HOSTS], capsys=capsys)
    assert rc == keydiff.EXIT_NOT_COMPARED == 5
    assert "objects not compared: 2 (a=1 b=1)" in _counts(out.out)
    assert "were not compared; exit 5" in out.out
    # A difference outranks it: exit 1.
    rc1, _, _ = _run(["--profile", "a", "--profile", "b", *HOSTS], capsys=capsys)
    assert rc1 == 1


def test_ambiguous_objects_make_the_run_non_zero():
    a = keydiff.capture(FakeOps("a"), adapter_kind="vCommunity", resource_kind="Content Library",
                        names=[], key_prefixes=[], source={}, now_ms=NOW)
    dup = json.loads(json.dumps(a))
    keyless = [o for o in dup["objects"] if not o["stats"] and not o["properties"]]
    assert keyless and len(dup["objects"]) == 2
    dup["objects"].append(dict(keyless[0], resource_id="dup"))  # Library A stays compared
    res = keydiff.compare(dup, dup)
    assert res["compared"]["objects_both"] == 1 and res["compared"]["keys_both"] >= 1
    assert res["compared"]["not_compared_a"] == 2 and res["compared"]["not_compared_b"] == 2
    assert keydiff.exit_code(res) == 5


def test_tsv_counts_go_to_stderr(capsys):
    rc, _, out = _run(["--profile", "a", "--profile", "a", *LIBS, "--format", "tsv"],
                      capsys=capsys)
    assert rc == 0
    assert out.out.startswith("category\t")
    assert "compared:" not in out.out
    assert "keydiff: compared: objects a=2 b=2 on both=2" in out.err
    assert "keydiff: result: no differences; exit 0" in out.err


def test_help_states_requests_and_exit_codes(capsys):
    assert keydiff.main(["--help"]) == 0
    text = " ".join(capsys.readouterr().out.split())
    assert "GET requests only" not in text
    assert "POST /api/auth/token/acquire" in text and "POST /api/auth/token/release" in text
    for line in ("2 usage error", "3 a fetch or snapshot read failed", "4 nothing compared",
                 "1 a difference was found", "5 no difference, but some objects were not",
                 "0 objects and keys compared"):
        assert line in text
    assert "no credentials or token" in text  # --snapshot-out help
    assert "--timeout" in text


def test_table_escapes_terminal_control_characters():
    a = keydiff.capture(FakeOps("a"), adapter_kind="vCommunity", resource_kind="Content Library",
                        names=[], key_prefixes=[], source={}, now_ms=NOW)
    b = json.loads(json.dumps(a))
    evil = "x\x1b[2J\x1b]0;title\x07\u202e\u2028\x9b\x7fy"
    b["objects"][0]["properties"]["vCommunity|Evil"] = {"value": evil}
    b["objects"][0]["name"] = "lib\x1bname"
    b["unidentified"] = [{"name": "u\x1b[31m", "resource_kind": "K", "resource_id": "r",
                          "reason": "why\x1b"}]
    res = keydiff.compare(a, b)
    table = keydiff.to_table(res, show_matches=True)
    tsv = keydiff.to_tsv(res)
    for text in (table, tsv):
        assert "\x1b" not in text and "\x07" not in text and "\x9b" not in text
        assert "\x7f" not in text and "\u202e" not in text and "\u2028" not in text
    assert "x\\x1b[2J" in table
    assert "u\\x1b[31m" in table  # the not-compared list is escaped too
    assert len(tsv.rstrip("\n").split("\n")) == len(res["rows"]) + 1


def test_b_adapter_kind_needs_a_live_side_b(tmp_path, capsys):
    sb = tmp_path / "b.json"
    assert _run(["--profile", "b", *HOSTS, "--snapshot-out", str(sb)])[0] == 0
    capsys.readouterr()
    rc, clients, out = _run(["--profile", "a", "--snapshot-in", str(sb), *HOSTS,
                             "--b-adapter-kind", "X"], capsys=capsys)
    assert rc == 2 and "side B is a snapshot" in out.err
    assert clients["a"].calls == []
    rc2, clients2, out2 = _run(["--profile", "a", *HOSTS, "--b-adapter-kind", "X",
                                "--snapshot-out", str(tmp_path / "x.json")], capsys=capsys)
    assert rc2 == 2 and "not given" in out2.err
    assert clients2["a"].calls == []
    # Live side B: it is used.
    rc3, clients3, _ = _run(["--profile", "a", "--profile", "b", "--adapter-kind", "vCommunity",
                             "--b-adapter-kind", "vcfcf_vcommunity", "--resource-kind",
                             "Content Library"], capsys=capsys)
    kinds_b = {dict(p).get("adapterKind") for _, path, p in clients3["b"].calls
               if path == "/api/resources"}
    assert kinds_b == {"vcfcf_vcommunity"}


class _SessResp:
    def __init__(self, code: int, body: Any = None):
        self.status_code = code
        self._body = body
        self.text = "" if body is None else json.dumps(body)

    def json(self):
        return self._body


class FakeSession:
    """Stands in for VCFOpsClient's requests.Session: serves FakeOps state,
    records every request with its keyword arguments."""

    def __init__(self, ops: FakeOps, base: str, token: str):
        self.ops, self.base, self.token = ops, base, token
        self.headers: Dict[str, str] = {}
        self.log: List[Tuple[str, str, Dict[str, Any]]] = []

    def post(self, url, **kw):
        self.log.append(("POST", url[len(self.base):], kw))
        if url.endswith("/api/auth/token/acquire"):
            return _SessResp(200, {"token": self.token})
        if url.endswith("/api/auth/token/release"):
            return _SessResp(200)
        return _SessResp(404)

    def request(self, method, url, **kw):
        self.log.append((method, url[len(self.base):], kw))
        r = self.ops._request(method, url[len(self.base):], **kw)
        return _SessResp(r.status_code, r._body)


def _real_client(side: str, password: str, token: str):
    from vcfcf_common.client import VCFOpsClient
    c = VCFOpsClient(host=f"ops-{side}.example.test", username=f"svc-{side}",
                     password=password)
    c._session = FakeSession(FakeOps(side), c.base, token)
    return c


def test_real_client_timeouts_release_and_no_credentials_in_snapshot(tmp_path, capsys):
    pw, tok = "Pa55-SECRET-pw-7731", "TOKEN-SECRET-5521"
    clients = {"a": _real_client("a", pw, tok)}
    snap = tmp_path / "a.json"
    rc = keydiff.main(["--profile", "a", *HOSTS, "--snapshot-out", str(snap),
                       "--timeout", "12.5"], client_factory=lambda p: clients[p])
    assert rc == 0
    log = clients["a"]._session.log
    verbs = [(m, p) for m, p, _ in log]
    assert verbs[0] == ("POST", "/api/auth/token/acquire")
    assert verbs[-1] == ("POST", "/api/auth/token/release")
    assert {m for m, p in verbs[1:-1]} == {"GET"}
    assert all(kw.get("timeout") == 12.5 for _, _, kw in log), log
    assert clients["a"]._token is None  # released
    text = snap.read_text(encoding="utf-8")
    for secret in (pw, tok, "svc-a", "vRealizeOpsToken", "Authorization"):
        assert secret not in text
    doc = json.loads(text)
    assert doc["source"] == {"profile": "a", "base": "https://ops-a.example.test/suite-api"}
    assert "esx01.vc1" in text  # names and values from the instance are there


def test_token_released_when_a_fetch_fails(capsys):
    c = _real_client("a", "pw", "tok")
    c._session.ops.fail = {"/api/resources/properties": 500}
    rc = keydiff.main(["--profile", "a", "--profile", "a", *HOSTS],
                      client_factory=lambda p: c)
    assert rc == 3
    assert c._session.log[-1][:2] == ("POST", "/api/auth/token/release")
    assert "HTTP 500" in capsys.readouterr().err


def test_release_failure_is_one_line_never_fatal(capsys):
    c = _real_client("a", "pw", "tok")

    def boom(url, **kw):
        if url.endswith("release"):
            raise OSError("connection reset with body SECRET-BODY")
        return FakeSession.post(c._session, url, **kw)

    c._session.post = boom
    rc = keydiff.main(["--profile", "a", "--profile", "a", *LIBS], client_factory=lambda p: c)
    assert rc == 0
    err = capsys.readouterr().err
    assert "token release failed (OSError; ignored)" in err
    assert "SECRET-BODY" not in err


def test_timeout_must_be_positive(capsys):
    for v in ("0", "-1", "nan", "inf"):
        rc, clients, _ = _run(["--profile", "a", "--profile", "b", *HOSTS, "--timeout", v],
                              capsys=capsys)
        assert rc == 2 and all(c.calls == [] for c in clients.values())


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
