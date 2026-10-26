"""Post-import dashboard materialization check in install.ps1 (issue #255).

The PowerShell installer re-states the core classifier
(``vcfcf_core.dashboards.materialization``) the same way install.py does,
because it ships standalone in every bundle zip. This file pins the port the
way ``tests/test_install_materialization.py`` pins install.py:

1. Static checks that run everywhere (the flags, the constants, the wiring).
2. A behaviour layer that runs the template's own functions under ``pwsh``
   (``tests/fixtures/install_ps1_materialization_harness.ps1`` extracts them
   with the PowerShell AST) and compares every state, every list and every
   report sentence with the core classifier, the factory wait helper and
   install.py. Skipped when no PowerShell is installed.

Neither layer proves Windows PowerShell 5.1 compatibility: 5.1 is .NET
Framework and does not exist off Windows (RULE-018,
knowledge/context/authoring/guide_powershell.md). No live instance: every
Suite API read is stubbed.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_core.dashboards import materialization as mat  # noqa: E402
from vcfcf_core.extractor import dashboards_from_export_zip  # noqa: E402
from test_install_materialization import (  # noqa: E402
    DONE, ID_DONE, ID_GONE, ID_LICENSE, ID_MSSQL, INSTALLED, LICENSE, LICENSE_DONE,
    MSSQL, PARITY_CASES, WANTED, _export_zip, _rk, install_mod,  # noqa: F401
)

from ps_runner import ps_exe, run_ps_file  # noqa: E402,F401  (ps_exe is a fixture)

TEMPLATE = SRC / "vcfcf_packaging" / "templates" / "install.ps1"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "install_ps1_materialization_harness.ps1"

#: Skips without PowerShell; fails instead under VCFCF_REQUIRE_PWSH=1. The
#: interpreter is VCFCF_PS_EXE (default pwsh; "powershell" for 5.1 on Windows).
needs_pwsh = pytest.mark.usefixtures("ps_exe")


@pytest.fixture(scope="module")
def script_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


# --- static layer ---------------------------------------------------------------

def test_flags_mirror_install_py(script_text):
    params = script_text[script_text.index("param("):script_text.index("Set-StrictMode")]
    assert "[switch]$SkipMaterializationCheck" in params
    assert "[Nullable[int]]$MaterializationWait = $null" in params
    assert ".PARAMETER SkipMaterializationCheck" in script_text
    assert ".PARAMETER MaterializationWait" in script_text


def test_constants_match_the_factory(script_text):
    from vcfcf_dashboards import client as dc

    assert f"$script:MatWaitDefaultS = {dc.MATERIALIZATION_RECHECK_DEFAULT_S}" in script_text
    assert f"$script:MatWaitMaxS     = {dc.MATERIALIZATION_RECHECK_MAX_S}" in script_text
    assert f'$script:MatWaitEnv      = "{dc.MATERIALIZATION_RECHECK_ENV}"' in script_text
    for state in (mat.COMPLETE, mat.SETTLING, mat.INCOMPLETE, mat.STALLED, mat.ABSENT):
        assert re.search(r'\$script:Mat\w+\s*=\s*"%s"' % state, script_text), state


def test_install_runs_the_report_and_prints_notes_in_both_branches(script_text):
    body = script_text[script_text.index("function Invoke-Install {"):
                       script_text.index("function Invoke-Uninstall {")]
    assert "Invoke-MaterializationReport -Dashboards $globalCtx.ImportedDashboards" in body
    assert "-Skip:$SkipMaterializationCheck -RequestedWait $MaterializationWait" in body
    assert body.count("Write-MaterializationTrailer -Notes $matNotes") == 2
    assert "if ($allAdvisories.Count -gt 0 -or $matNotes.Count -gt 0) {" in body
    assert '-not $w.StartsWith("MATERIALIZATION ", [System.StringComparison]::Ordinal)' in body


def test_dashboard_records_only_when_the_import_changed_it(script_text):
    body = script_text[script_text.index("function Install-Dashboard"):
                       script_text.index("function Install-SmEnable")]
    else_at = body.index('Write-Ok "Imported 1 dashboard"')
    assert body.index("Get-DashboardIdNames", else_at) > else_at
    assert "$Ctx.Warnings.Add(" not in body


def test_download_is_basic_parsing(script_text):
    """Windows PowerShell 5.1 Invoke-WebRequest without -UseBasicParsing
    needs the IE engine, which a server core or first-run box lacks."""
    body = script_text[script_text.index("function Export-DashboardsZip"):
                       script_text.index("function Get-AdapterKindKeys")]
    assert "UseBasicParsing = $true" in body


# --- behaviour layer (pwsh) -----------------------------------------------------

def _run(tmp_path: Path, scenario: dict, expect_rc: int = 0):
    scen = tmp_path / "scenario.json"
    out = tmp_path / "out.json"
    scen.write_text(json.dumps(scenario), encoding="utf-8")
    proc = run_ps_file(HARNESS, [TEMPLATE, scen, out])
    assert proc.returncode == expect_rc, f"rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
    result = json.loads(out.read_text(encoding="utf-8-sig")) if out.exists() else None
    return result, proc.stdout


def _zip(tmp_path: Path, name: str, *dashboards) -> str:
    p = tmp_path / name
    p.write_bytes(_export_zip(*dashboards))
    return str(p)


@needs_pwsh
def test_classifier_matches_core(tmp_path):
    cases = []
    for exported, kinds, after in PARITY_CASES:
        cases.append({"exported": exported, "wanted": [[k, v] for k, v in WANTED.items()],
                      "kinds": sorted(kinds) if kinds is not None else [],
                      "kinds_unknown": kinds is None, "after": after})
    # Extra shapes a port gets wrong: ordinal sort (VMWARE before mpb_*,
    # culture sort says otherwise), duplicate resource names, whitespace ids,
    # importComplete false with no entryKeys, a non-list entryKeys member.
    odd = {"id": "  " + ID_MSSQL.upper() + " ", "importComplete": False, "entryKeys": {
        "resourceKind": [_rk("a", "mpb_rubrik", 0), _rk("b", "VMWARE", 1),
                         _rk("c", "Zeta", 2), _rk("d", "  ", 3)],
        "resource": [{"name": "World"}, {"name": "World"}, {"name": " "}, "junk"],
        "uuid": "u", "flag": {"adapterKindKey": "IGNORED"}}}
    cases.append({"exported": [odd], "wanted": [[ID_MSSQL, "Odd"]], "kinds": ["VMWARE"],
                  "kinds_unknown": False, "after": 7})
    cases.append({"exported": [odd], "wanted": [[ID_MSSQL, "Odd"]], "kinds": [],
                  "kinds_unknown": True, "after": 0})
    # entryKeys an empty list: non-null, so incomplete (a naive
    # Get-PropValue read returns $null for an empty array).
    cases.append({"exported": [{"id": ID_DONE, "importComplete": True, "entryKeys": []}],
                  "wanted": [[ID_DONE, "Empty list"]], "kinds": [],
                  "kinds_unknown": False, "after": 0})
    flag_only = {"id": ID_DONE, "importComplete": False}
    cases.append({"exported": [flag_only, DONE], "wanted": [[ID_DONE, "Last wins"]],
                  "kinds": [], "kinds_unknown": False, "after": 0})

    got, _ = _run(tmp_path, {"mode": "classify", "cases": cases})
    assert len(got) == len(cases)
    for case, mine in zip(cases, got):
        kinds = None if case["kinds_unknown"] else set(case["kinds"])
        wanted = {k: v for k, v in case["wanted"]}
        core = mat.finalize_statuses(
            mat.classify_dashboards(case["exported"], wanted, kinds), case["after"])
        assert len(core) == len(mine)
        for c, m in zip(core, mine):
            assert (c.id, c.name, c.state) == (m["id"], m["name"], m["state"])
            assert c.pending_adapter_kinds == m["pending"]
            assert c.missing_adapter_kinds == m["missing"]
            assert c.pending_resources == m["resources"]
            assert c.checked_after_s == m["after"]
            assert c.adapter_kinds_known == m["kinds_known"]
            assert mat.describe_status(c) == m["describe"]
    # The ordinal-sort case really exercised the difference.
    assert got[len(PARITY_CASES)][0]["pending"] == ["VMWARE", "Zeta", "mpb_rubrik"]


def _raw_zip(tmp_path: Path, name: str, dashboard_json: str) -> Path:
    """An export whose one owner's dashboard.json is exactly ``dashboard_json``."""
    import io
    import zipfile

    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("dashboard/dashboard.json", dashboard_json)
    p = tmp_path / name
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("dashboards/29c1613f-3bbe-4aa0-8236-2c74db22c661", inner.getvalue())
        z.writestr("configuration.json", "{}")
    return p


#: (dashboard.json text, install.py raises?) for the N1 shapes.
BAD_SHAPES = [
    (json.dumps([{"id": "a"}]), True),                         # not an object
    (json.dumps({"dashboards": [{"id": "a"}, 7]}), True),      # element not an object
    (json.dumps({"dashboards": {"id": "a"}}), True),           # an object, not a list
    (json.dumps({"dashboards": "abc"}), True),                 # a string
    (json.dumps({"dashboards": {}}), False),                   # falsy: nothing
    (json.dumps({"dashboards": ""}), False),                   # falsy: nothing
    (json.dumps({"dashboards": [{"id": "a"}]}), False),        # one element, fine
]


@needs_pwsh
def test_export_reader_matches_core(tmp_path, install_mod):
    good = _zip(tmp_path, "good.zip", DONE, MSSQL, LICENSE)
    bad = [str(_raw_zip(tmp_path, f"bad{i}.zip", text)) for i, (text, _) in enumerate(BAD_SHAPES)]
    got, _ = _run(tmp_path, {"mode": "exportzip", "good": good, "bad": bad})
    core = [d["id"] for d in dashboards_from_export_zip(Path(good).read_bytes())]
    assert got["ids"] == core == [ID_DONE, ID_MSSQL, ID_LICENSE]
    assert got["error"].startswith("failed to parse dashboard export zip: ")
    # N1: every shape install.py rejects is rejected here (so the run says
    # UNCHECKED, not a false ABSENT); every shape it accepts reads the same ids.
    for (text, py_raises), mine, path in zip(BAD_SHAPES, got["bad"], bad):
        blob = Path(path).read_bytes()
        if py_raises:
            with pytest.raises(ValueError):
                install_mod._mat_dashboards_from_export_zip(blob)
            assert mine["error"].startswith("failed to parse dashboard export zip: "), text
        else:
            py_ids = [d["id"] for d in install_mod._mat_dashboards_from_export_zip(blob)]
            assert mine["error"] == "" and mine["ids"] == py_ids, text


@needs_pwsh
def test_badly_shaped_export_reports_unchecked_not_absent(tmp_path):
    """N1 at the report level, plus the PowerShell-only case: keys that differ
    only in case parse in Python but not in ConvertFrom-Json. Either way the
    operator is told the check could not run, never that the dashboard is gone."""
    for i, text in enumerate([json.dumps({"dashboards": [{"id": ID_DONE}, "x"]}),
                              '{"dashboards": [{"id": "%s", "a": 1, "A": 2}]}' % ID_DONE]):
        z = str(_raw_zip(tmp_path, f"shape{i}.zip", text))
        got, _ = _report(tmp_path, [z], [[ID_DONE, "Done"]])
        assert got["warnings"] == [] and len(got["notes"]) == 1, text
        assert got["notes"][0].startswith(
            "MATERIALIZATION UNCHECKED: could not check whether the imported dashboards "
            "finished building: failed to parse dashboard export zip: "), text


@needs_pwsh
def test_wait_matches_factory(tmp_path, monkeypatch):
    from vcfcf_dashboards.client import materialization_recheck_wait

    cases = [("", None), ("60", None), ("bogus", None), ("5000", None), ("", 0),
             ("", -4), ("", 2000), ("60", 10), (" 42 ", None), ("+5", None),
             ("-3", None), ("1.5", None), ("99999999999999999999999", None),
             ("-99999999999999999999999", None),
             # N2: Python's int() takes single underscores between digits.
             ("1_000", None), ("6_0", None), ("1__0", None), ("_60", None), ("60_", None)]
    got, _ = _run(tmp_path, {"mode": "wait",
                             "cases": [{"env": e, "req": r} for e, r in cases]})
    expected = []
    for env, req in cases:
        monkeypatch.setenv("VCFCF_MATERIALIZATION_WAIT_S", env)
        expected.append(materialization_recheck_wait(req))
    assert got == expected


@needs_pwsh
def test_dashboard_id_names_match_install_py(tmp_path, install_mod):
    docs = [
        json.dumps({"dashboards": [
            {"id": "d1", "name": "VCF Content Factory/[VCF Content Factory] Cap",
             "namePath": "VCF Content Factory", "owner": "PLACEHOLDER_USER_ID"},
            {"id": "d2"}, {"name": "no id"}, {"id": "d3", "name": "x" * 200}]}),
        json.dumps({"dashboards": [{"id": "only", "name": "One"}]}),
        json.dumps({"dashboards": "oops"}),
        "not json",
    ]
    got, _ = _run(tmp_path, {"mode": "idnames", "docs": docs})
    expected = [[list(p) for p in install_mod._extract_dashboard_id_names(
        d.replace("PLACEHOLDER_USER_ID", "u1"))] for d in docs]
    assert got == expected


def _check(tmp_path, exports, dashboards, wait, kinds=INSTALLED, kinds_error=False):
    return _run(tmp_path, {"mode": "check", "fn": "check", "exports": exports,
                           "dashboards": dashboards, "wait": wait,
                           "kinds": sorted(kinds), "kinds_error": kinds_error})


@needs_pwsh
@pytest.mark.parametrize("reads", [
    [LICENSE, LICENSE_DONE],
    [LICENSE, LICENSE],
    [LICENSE, RuntimeError("busy")],
    [MSSQL],
    [DONE],
])
def test_recheck_flow_matches_install_py(tmp_path, install_mod, reads):
    from test_install_materialization import _ExportClient

    did = reads[0]["id"]
    exports = []
    for i, r in enumerate(reads):
        exports.append({"error": str(r)} if isinstance(r, Exception)
                       else _zip(tmp_path, f"r{i}.zip", r))
    got, out = _check(tmp_path, exports, [[did, "X"]], 60)

    queue = list(reads)

    def _next():
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return _export_zip(item)

    client = _ExportClient([])
    client.export_dashboards_zip = _next
    slept = []
    py = install_mod._check_materialization(client, [(did, "X")], 60, _sleep=slept.append)
    assert got["slept"] == slept
    assert [(s["state"], s["after"]) for s in got["statuses"]] == [
        (s["state"], s["after"]) for s in py]
    assert [s["describe"] for s in got["statuses"]] == [install_mod._mat_describe(s) for s in py]
    if slept:
        assert "MATERIALIZATION WAIT: 1 dashboard(s) still building; re-checking once in 60 s" \
            in got["lines"]


@needs_pwsh
def test_regression_8187_incomplete_after_one_recheck(tmp_path):
    lic = _zip(tmp_path, "l.zip", LICENSE)
    got, _ = _check(tmp_path, [lic, lic], [[ID_LICENSE, "License"]], 180)
    assert got["slept"] == [180] and got["export_calls"] == 2 and got["kinds_calls"] == 1
    assert [s["state"] for s in got["statuses"]] == ["incomplete"]
    assert "180 s after the import" in got["statuses"][0]["describe"]


@needs_pwsh
def test_date_like_resource_names_stay_verbatim(tmp_path):
    """N5: pwsh 7 coerces ISO-8601 strings to DateTime unless told not to."""
    dated = dict(LICENSE, entryKeys={
        "resourceKind": [_rk("X", "VMWARE", 0)],
        "resource": [{"name": "2024-01-01T00:00:00Z", "adapterKindKey": "VMWARE"}]})
    got, _ = _check(tmp_path, [_zip(tmp_path, "t.zip", dated)], [[ID_LICENSE, "Dated"]], 0)
    assert got["statuses"][0]["resources"] == ["2024-01-01T00:00:00Z"]
    assert "'2024-01-01T00:00:00Z'" in got["statuses"][0]["describe"]


@needs_pwsh
def test_unreadable_adapter_kinds_is_never_stalled(tmp_path):
    got, _ = _check(tmp_path, [_zip(tmp_path, "m.zip", MSSQL)], [[ID_MSSQL, "MSSQL"]], 0,
                    kinds_error=True)
    st = got["statuses"][0]
    assert st["state"] == "incomplete" and st["kinds_known"] is False
    assert "could not be read" in st["describe"]


def _report(tmp_path, exports, dashboards, **kw):
    scen = {"mode": "check", "fn": "report", "exports": exports, "dashboards": dashboards,
            "requested_wait": 0, "skip": False, "kinds": sorted(INSTALLED),
            "kinds_error": False}
    scen.update(kw)
    return _run(tmp_path, scen)


@needs_pwsh
def test_report_ok(tmp_path):
    got, _ = _report(tmp_path, [_zip(tmp_path, "d.zip", DONE)], [[ID_DONE, "Done"]])
    assert (got["warnings"], got["notes"]) == ([], [])
    assert got["lines"] == ["MATERIALIZATION OK: 1 of 1 dashboard(s) finished building"]


@needs_pwsh
def test_report_stalled_is_a_warning(tmp_path):
    got, _ = _report(tmp_path, [_zip(tmp_path, "m.zip", MSSQL)], [[ID_MSSQL, "MSSQL"]])
    assert len(got["warnings"]) == 1 and got["notes"] == []
    assert got["warnings"][0].startswith("MATERIALIZATION STALLED: ")
    assert "OracleDBAdapter, SqlServerAdapter" in got["warnings"][0]
    assert got["lines"] == ["WARNING: " + got["warnings"][0]]


@needs_pwsh
def test_report_unchecked_absent_and_skip(tmp_path):
    got, _ = _report(tmp_path, [{"error": "export failed (500)"}], [[ID_DONE, "Done"]])
    assert got["warnings"] == [] and got["notes"] == [
        "MATERIALIZATION UNCHECKED: could not check whether the imported dashboards "
        "finished building: export failed (500)"]
    assert got["lines"] == ["WARNING: " + got["notes"][0]]

    got, _ = _report(tmp_path, [_zip(tmp_path, "d.zip", DONE)], [[ID_GONE, "Gone"]])
    assert got["warnings"] == [] and got["notes"][0].startswith("MATERIALIZATION ABSENT: ")

    got, _ = _report(tmp_path, [], [[ID_DONE, "Done"]], skip=True)
    assert (got["warnings"], got["notes"], got["export_calls"]) == ([], [], 0)
    got, _ = _report(tmp_path, [], [])
    assert (got["warnings"], got["notes"], got["export_calls"]) == ([], [], 0)


@needs_pwsh
def test_report_lines_match_install_py(tmp_path, install_mod, capsys):
    """Every printed line, byte for byte, for a mixed run."""
    from test_install_materialization import _ExportClient, _args

    reads = [DONE, MSSQL, LICENSE]
    dashboards = [[ID_DONE, "Done"], [ID_MSSQL, "MSSQL"], [ID_LICENSE, "License"],
                  [ID_GONE, "Gone"]]
    got, _ = _report(tmp_path, [_zip(tmp_path, "all.zip", *reads)], dashboards)
    capsys.readouterr()
    warnings, notes = install_mod._report_materialization(
        _ExportClient([_export_zip(*reads)]), [tuple(d) for d in dashboards], _args())
    assert (got["warnings"], got["notes"]) == (warnings, notes)
    assert got["lines"] == capsys.readouterr().out.splitlines()


def _client(tmp_path, kinds=200, post=200, download=200):
    got, _ = _run(tmp_path, {"mode": "client", "kinds_status": kinds, "post_status": post,
                             "download_status": download})
    return got


@needs_pwsh
def test_client_readers(tmp_path):
    got = _client(tmp_path)
    assert got["kinds"] == ["VMWARE", "mpb_rubrik"] and got["kinds_type"].startswith("HashSet")
    assert got["bytes"] == [80, 75, 9] and got["export_error"] == ""
    posted = json.loads(got["posted"])
    assert posted["scope"] == "CUSTOM" and posted["contentTypes"] == ["DASHBOARDS"]
    assert got["calls"][-1].endswith("/suite-api/api/content/operations/export/zip basic=True")
    # N6: the progress bar is silenced for the download only.
    assert got["progress_during"] == "SilentlyContinue"
    assert got["progress_after"] != "SilentlyContinue"

    got = _client(tmp_path, kinds=403, post=500)
    assert got["kinds_error"] == "adapterkinds read failed (403)"
    assert got["export_error"] == "dashboard export failed (500): " + "x" * 300


@needs_pwsh
def test_download_failure_names_the_status_like_install_py(tmp_path):
    """N3: install.py says "export zip download failed (404)"."""
    assert _client(tmp_path, download=404)["export_error"] == "export zip download failed (404)"
    # No HTTP answer at all: the exception message stands in for the code.
    assert _client(tmp_path, download=-1)["export_error"] == \
        "export zip download failed (connection reset)"


@needs_pwsh
@pytest.mark.parametrize("import_result,recorded", [
    ({"state": "FINISHED", "operationSummaries": [
        {"contentType": "DASHBOARDS", "imported": 1, "skipped": 0}]},
     [["dash-1", "[VCF Content Factory] Cap"]]),
    ({"state": "FINISHED", "operationSummaries": [
        {"contentType": "DASHBOARDS", "imported": 0, "skipped": 1}]}, []),
])
def test_install_dashboard_records_only_changed(tmp_path, import_result, recorded):
    dash_json = json.dumps({"dashboards": [
        {"id": "dash-1", "name": "VCF Content Factory/[VCF Content Factory] Cap",
         "namePath": "VCF Content Factory"}]})
    got, _ = _run(tmp_path, {"mode": "dashboard", "import_result": import_result,
                             "dash_json": dash_json})
    assert got["recorded"] == recorded and got["warnings"] == 0


def _install(tmp_path, exports, dashboards, expect_rc, **kw):
    scen = {"mode": "install", "exports": exports, "dashboards": dashboards,
            "kinds": sorted(INSTALLED), "skip": False, "advisories": [], "warnings": []}
    scen.update(kw)
    _, out = _run(tmp_path, scen, expect_rc=expect_rc)
    return out


@needs_pwsh
def test_install_incomplete_run_does_not_end_on_all_successful(tmp_path):
    out = _install(tmp_path, [_zip(tmp_path, "l.zip", LICENSE)],
                   [[ID_LICENSE, "License"]], expect_rc=0)
    assert "Done. All content installed successfully." not in out
    assert "Done. No failures, but see the attention list at the end of this output." in out
    assert "1 dashboard(s) need a later look" in out
    lines = [ln for ln in out.splitlines() if ln.strip() and ln != "HARNESS DONE"]
    assert lines[-1].startswith("  ATTENTION  MATERIALIZATION INCOMPLETE: ")


@needs_pwsh
def test_install_stalled_run_exits_2(tmp_path):
    stalled = dict(LICENSE, entryKeys={"resourceKind": [_rk("X", "mpb_rubrik", 0)]})
    out = _install(tmp_path, [_zip(tmp_path, "s.zip", stalled)],
                   [[ID_LICENSE, "Enable and Resolve Board"]], expect_rc=2)
    assert "  WARN  MATERIALIZATION STALLED: dashboard 'Enable and Resolve Board'" in out
    assert "super metrics could not be enabled" not in out


@needs_pwsh
def test_install_lists_enable_warnings_first(tmp_path):
    """N4: install.py prints enable warnings, then the rest."""
    stalled = dict(LICENSE, entryKeys={"resourceKind": [_rk("X", "mpb_rubrik", 0)]})
    out = _install(tmp_path, [_zip(tmp_path, "s.zip", stalled)], [[ID_LICENSE, "Board"]],
                   expect_rc=2, warnings=["view import was slow", "could not enable SM One"])
    warn = [ln for ln in out.splitlines() if ln.startswith("  WARN  ")]
    assert warn[0] == "  WARN  could not enable SM One"
    assert warn[1] == "  WARN  view import was slow"
    assert warn[2].startswith("  WARN  MATERIALIZATION STALLED: ")
    assert "Done with 3 warning(s):" in out
    assert "super metrics could not be enabled" in out


@needs_pwsh
def test_install_ok_and_skip(tmp_path):
    out = _install(tmp_path, [_zip(tmp_path, "d.zip", DONE)], [[ID_DONE, "Done"]], expect_rc=0)
    assert "MATERIALIZATION OK: 1 of 1 dashboard(s) finished building" in out
    assert "Done. All content installed successfully." in out
    # Skipped: no export is consumed (the queue is empty, so a read would throw
    # and print UNCHECKED).
    out = _install(tmp_path, [], [[ID_DONE, "Done"]], expect_rc=0, skip=True)
    assert "MATERIALIZATION" not in out
    assert "Done. All content installed successfully." in out


@needs_pwsh
def test_flags_bind_on_the_real_script(tmp_path):
    """The real param block accepts both switches (run in an empty directory:
    it exits 1 at "No bundles found", after parameter binding)."""
    proc = run_ps_file(TEMPLATE, ["-SkipMaterializationCheck", "-MaterializationWait", "42"],
                       cwd=tmp_path)
    assert proc.returncode == 1
    assert "No bundles found" in proc.stderr + proc.stdout
    proc = run_ps_file(TEMPLATE, ["-MaterializationWait", "soon"], cwd=tmp_path)
    assert proc.returncode != 0 and "MaterializationWait" in proc.stderr + proc.stdout
