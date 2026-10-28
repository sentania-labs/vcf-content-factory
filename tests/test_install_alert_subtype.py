"""Alert subType in the shipped installers agrees with the core loader (#282).

install.py and install.ps1 ship standalone inside distribution zips, so they
cannot import ``vcfcf_core.alerts.loader`` and restate its subType enum.  These
tests pin the copies in step with the loader and check the behaviour: an
absent or null ``sub_type`` posts 19 (Performance), not the 3 both installers
used to fall back to, and a value outside 18-22 skips that alert with a WARN
while the rest of the alerts still install.  No live instance.

The PowerShell half runs under whatever interpreter tests/ps_runner.py finds
and is skipped without one (unless VCFCF_REQUIRE_PWSH=1).
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from ps_runner import ps_exe, run_ps_file  # noqa: F401  (ps_exe is a fixture)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.alerts import loader as alert_loader  # noqa: E402

TEMPLATES = SRC / "vcfcf_packaging" / "templates"
INSTALL_PY = TEMPLATES / "install.py"
INSTALL_PS1 = TEMPLATES / "install.ps1"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "install_ps1_alert_subtype_harness.ps1"

_ABSENT = object()

# (id, raw sub_type or _ABSENT).  Every value survives a JSON round trip, which
# is how the installers receive it (content/alerts.json).
CASES = [
    ("absent", _ABSENT),
    ("null", None),
    ("18", 18),
    ("19", 19),
    ("20", 20),
    ("21", 21),
    ("22", 22),
    ("str19", "19"),
    ("str20_padded", " 20 "),
    ("zero", 0),
    ("three", 3),
    ("seventeen", 17),
    ("twentythree", 23),
    ("negative", -19),
    ("str_negative", "-19"),
    ("true", True),
    ("false", False),
    ("float19", 19.0),
    ("text", "Performance"),
    ("empty_str", ""),
    # Unicode decimal digits: Python's int() reads them, so the loader does.
    ("arabic_indic19", "\u0661\u0669"),
    # Past Int64: rejected with the enum message, not a cast error.
    ("over_int64", "99999999999999999999999"),
]

# isdigit() passes these but int() does not.  The loader raises a bare
# ValueError on them (outside this change); both installers must reject them
# with the enum message instead.
INSTALLER_ONLY_REJECTS = [
    ("superscript2", "\u00b2"),
    ("double_minus", "--19"),
]

# Symptom-set threshold shapes for a non-SELF set: both fields are optional
# in the loader (_validate_set), so every shape must install, not throw.
THRESHOLD_SHAPES = [
    ("child_no_threshold", {}),
    ("child_type_only", {"threshold_type": "ANY"}),
    ("child_type_and_value", {"threshold_type": "PERCENT", "threshold_value": 50}),
]


def _load_install_py():
    spec = importlib.util.spec_from_file_location("_install_template_subtype", INSTALL_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_install_template_subtype"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def inst():
    return _load_install_py()


def _alert(case_id, raw):
    a = {
        "name": f"[VCF Content Factory] Subtype {case_id}",
        "description": "",
        "adapter_kind": "VMWARE",
        "resource_kind": "HostSystem",
        "type": 16,
        "wait_cycles": 1,
        "cancel_cycles": 1,
        "criticality": "WARNING",
        "impact_badge": "HEALTH",
        "symptom_sets": {
            "operator": "ALL",
            "sets": [{"defined_on": "SELF", "operator": "ALL",
                      "symptoms": [{"name": "Sym A"}]}],
        },
        "recommendations": [],
    }
    if raw is not _ABSENT:
        a["sub_type"] = raw
    return a


def _loader_verdict(raw):
    """What the core loader does with this raw YAML value: int or None (rejected)."""
    value = alert_loader._sub_type(None if raw is _ABSENT else raw)
    alert = alert_loader.AlertDef(
        name="[VCF Content Factory] x", adapter_kind="VMWARE",
        resource_kind="HostSystem", criticality="WARNING", impact_badge="HEALTH",
        symptom_sets=_alert("verdict", _ABSENT)["symptom_sets"], sub_type=value,
    )
    try:
        alert.validate()
    except alert_loader.AlertValidationError as exc:
        assert "sub_type" in str(exc), f"verdict fixture invalid for another reason: {exc}"
        return None
    return value


# --- enum parity ----------------------------------------------------------------

def test_install_py_enum_matches_loader(inst):
    assert inst._ALERT_SUBTYPES == alert_loader.VALID_SUBTYPES
    assert inst._ALERT_SUBTYPE_DEFAULT == 19
    assert alert_loader.AlertDef.__dataclass_fields__["sub_type"].default == 19


def test_install_ps1_enum_matches_loader():
    text = INSTALL_PS1.read_text(encoding="utf-8")
    body = re.search(r"function Get-AlertSubType \{.*?\n\}", text, re.S).group(0)
    lo, hi = min(alert_loader.VALID_SUBTYPES), max(alert_loader.VALID_SUBTYPES)
    assert sorted(alert_loader.VALID_SUBTYPES) == list(range(lo, hi + 1)), (
        "install.ps1 checks a contiguous range; a non-contiguous enum needs a set there"
    )
    assert f"-lt {lo}" in body and f"-gt {hi}" in body
    assert "return 19" in body
    allowed = ", ".join(f"{k}={v}" for k, v in alert_loader.VALID_SUBTYPES.items())
    assert allowed in body


def test_no_fallback_to_three_left():
    for path in (INSTALL_PY, INSTALL_PS1):
        text = path.read_text(encoding="utf-8")
        assert '"sub_type", 3' not in text
        assert "else { 3 }" not in text


# --- install.py -------------------------------------------------------------------

@pytest.mark.parametrize("case_id,raw", CASES, ids=[c[0] for c in CASES])
def test_install_py_agrees_with_loader(inst, case_id, raw):
    payload = json.loads(json.dumps(_alert(case_id, raw)))
    expected = _loader_verdict(raw)
    if expected is None:
        with pytest.raises(ValueError, match="sub_type must be one of"):
            inst._alert_to_wire(payload, {"Sym A": "sym-a"})
    else:
        wire = inst._alert_to_wire(payload, {"Sym A": "sym-a"})
        assert wire["subType"] == expected


@pytest.mark.parametrize("case_id,raw", INSTALLER_ONLY_REJECTS,
                         ids=[c[0] for c in INSTALLER_ONLY_REJECTS])
def test_install_py_rejects_isdigit_only_strings(inst, case_id, raw):
    with pytest.raises(ValueError, match="sub_type must be one of"):
        inst._alert_sub_type(raw)


def _threshold_alert(case_id, extra):
    a = _alert(case_id, _ABSENT)
    a["symptom_sets"]["sets"][0].update({"defined_on": "CHILD", **extra})
    return a


class _Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


class _FakeClient:
    def __init__(self):
        self.posted = []

    def _req(self, method, path, params=None, json=None):
        if method == "GET" and path == "/api/symptomdefinitions":
            return _Resp(200, {"symptomDefinitions": [{"name": "Sym A", "id": "sym-a"}],
                               "pageInfo": {"totalCount": 1}})
        if method == "GET" and path == "/api/alertdefinitions":
            return _Resp(200, {"alertDefinitions": [], "pageInfo": {"totalCount": 0}})
        if method == "POST" and path == "/api/alertdefinitions":
            self.posted.append(json)
            return _Resp(201, {})
        raise AssertionError(f"unexpected {method} {path}")


def test_install_py_skips_out_of_enum_and_installs_the_rest(inst, tmp_path, capsys):
    alerts = [_alert("absent", _ABSENT), _alert("three", 3), _alert("twentyone", 21)]
    (tmp_path / "alerts.json").write_text(json.dumps(alerts), encoding="utf-8")
    client = _FakeClient()
    ctx = {"bundle_dir": tmp_path,
           "manifest": {"content": {"alerts": {"file": "alerts.json"}}},
           "client": client, "warnings": []}
    inst._install_alerts(ctx)
    assert [(p["name"], p["subType"]) for p in client.posted] == [
        ("[VCF Content Factory] Subtype absent", 19),
        ("[VCF Content Factory] Subtype twentyone", 21),
    ]
    assert len(ctx["warnings"]) == 1
    assert "Subtype three" in ctx["warnings"][0]
    assert "sub_type must be one of" in ctx["warnings"][0]
    assert "got 3" in ctx["warnings"][0]
    assert "WARN" in capsys.readouterr().out


# --- install.ps1 ------------------------------------------------------------------

@pytest.mark.usefixtures("ps_exe")
def test_install_ps1_agrees_with_loader(tmp_path):
    cases = [{"id": cid, "alert": _alert(cid, raw)}
             for cid, raw in CASES + INSTALLER_ONLY_REJECTS]
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(cases), encoding="utf-8")
    threshold_alerts = [_threshold_alert(cid, extra) for cid, extra in THRESHOLD_SHAPES]
    (tmp_path / "alerts.json").write_text(
        json.dumps([c["alert"] for c in cases] + threshold_alerts), encoding="utf-8")
    out_path = tmp_path / "out.json"
    proc = run_ps_file(HARNESS, [str(INSTALL_PS1), str(cases_path), str(out_path)])
    assert proc.returncode == 0, f"harness failed:\n{proc.stdout}\n{proc.stderr}"
    out = json.loads(out_path.read_text(encoding="utf-8-sig"))

    expected_posted = []
    for cid, raw in CASES:
        got = out["sub_types"][cid]
        expected = _loader_verdict(raw)
        if expected is None:
            assert got["ok"] is False, f"{cid}: install.ps1 accepted {raw!r} as {got.get('value')!r}"
            assert "sub_type must be one of" in got["error"]
        else:
            assert got["ok"] is True, f"{cid}: install.ps1 rejected {raw!r}: {got.get('error')}"
            assert got["value"] == expected, cid
            expected_posted.append((f"[VCF Content Factory] Subtype {cid}", expected))

    for cid, _raw in INSTALLER_ONLY_REJECTS:
        got = out["sub_types"][cid]
        assert got["ok"] is False and "sub_type must be one of" in got["error"], cid

    # Threshold shapes post (no StrictMode throw) with the same
    # base-symptom-set install.py builds.
    inst = _load_install_py()
    expected_posted += [(alert["name"], 19) for alert in threshold_alerts]
    posted = out["posted"]
    assert [(p["name"], p["subType"]) for p in posted] == expected_posted
    by_name = {p["name"]: p for p in posted}
    for alert in threshold_alerts:
        py_base = inst._alert_to_wire(alert, {"Sym A": "sym-a"})["states"][0]["base-symptom-set"]
        ps_base = by_name[alert["name"]]["base"]
        assert ps_base == py_base, alert["name"]
    assert "aggregation" not in by_name["[VCF Content Factory] Subtype child_no_threshold"]["base"]

    rejected = [cid for cid, raw in CASES if _loader_verdict(raw) is None]
    rejected += [cid for cid, _raw in INSTALLER_ONLY_REJECTS]
    assert len(out["warnings"]) == len(rejected)
    for cid, warning in zip(rejected, out["warnings"]):
        assert f"Subtype {cid}'" in warning and "wire conversion failed" in warning
