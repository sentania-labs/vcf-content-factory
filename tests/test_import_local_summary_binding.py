"""``import-local``: the Summary-tab binding comes from the source's binding
file, never from a folder name, and verification compares it with the source.

A pak binds a dashboard to a resource kind's Summary tab only through
``content/dashboards/dashboards.properties`` (``<dir>=<AK>:<RK>[,...]``,
``knowledge/context/api-surface/summary_dashboard_pak_binding.md``). Before
this, the importer set ``summary_for: VMWARE:<Folder>`` on any dashboard in a
folder named after one of six vSphere kinds, and verification compared the
YAML with that inference, so the invented binding verified "identical".

Every test drives the real CLI on small synthetic fixtures ("Probe ..."
names, made-up UUIDs) rendered by the factory's own renderer.
"""
from __future__ import annotations

import io
import json
import sys
import textwrap
import zipfile
from pathlib import Path

import pytest
import yaml

from vcfcf_core.dashboards.loader import load_dashboard
from vcfcf_core.dashboards.render import render_dashboards_bundle_json

FOLDERS = ("VMFolder", "HostFolder", "DatastoreFolder", "NetworkFolder",
           "DistributedVirtualPortgroup", "VmwareDistributedVirtualSwitch")


def _did(i: int) -> str:
    return f"1d5b0000-0000-4000-8000-{i:012d}"


def _dashboard(tmp: Path, i: int, name: str) -> dict:
    """One bare dashboard JSON (a TextDisplay only: no view needed)."""
    y = tmp / f"_y{i}.yaml"
    y.write_text(textwrap.dedent(f"""
        id: {_did(i)}
        name: {name}
        description: probe {i}
        name_path: ""
        shared: false
        widgets:
          - id: note
            type: TextDisplay
            title: Note {i}
            html: "<b>probe {i}</b>"
            coords: {{x: 1, y: 1, w: 12, h: 2}}
    """).lstrip())
    d = load_dashboard(y, enforce_framework_prefix=False, default_name_path="")
    y.unlink()
    env = json.loads(render_dashboards_bundle_json([d], {}, "0"))
    bare = dict(env["dashboards"][0])
    bare["entries"] = env["entries"]
    return bare


def _pak_tree(tmp: Path, binding: str = None, extra=()) -> Path:
    """``<tmp>/pak/content/dashboards/<Folder>/dashboard.json`` for the six
    folders plus one ordinary directory; ``binding`` is the text of
    ``dashboards.properties`` (no file when ``None``)."""
    root = tmp / "pak"
    dash = root / "content" / "dashboards"
    for i, f in enumerate(FOLDERS + ("Other Things",) + tuple(extra)):
        (dash / f).mkdir(parents=True)
        (dash / f / "dashboard.json").write_text(json.dumps(_dashboard(tmp, i, f"Probe Summary {f}"), indent=1))
    if binding is not None:
        (dash / "dashboards.properties").write_text(binding)
    return root


def _cli(argv, capsys):
    from vcfcf_extractor.cli import main
    old = sys.argv
    sys.argv = ["vcfcf_extractor"] + [str(a) for a in argv]
    try:
        with pytest.raises(SystemExit) as exc:
            main()
    finally:
        sys.argv = old
    cap = capsys.readouterr()
    return exc.value.code, cap.out + cap.err


def _run(src, out, capsys, layout="pak", *extra):
    return _cli(["import-local", src, "--out", out, "--layout", layout, "--ids", "keep", "--naming",
                 "unprefixed", *extra], capsys)


def _summary_for(out: Path) -> dict:
    return {p.name: yaml.safe_load(p.read_text()).get("summary_for")
            for p in sorted((out / "dashboards").glob("*.yaml"))}


def _report(out: Path) -> dict:
    return json.loads((out / "import-report" / "report.json").read_text())


# ------------------------------------------------------------ no binding
@pytest.mark.parametrize("layout", ["pak", "third-party"])
def test_six_kind_folders_without_a_binding_file_bind_nothing(tmp_path, capsys, layout):
    src = _pak_tree(tmp_path)
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys, layout)
    assert rc == 0, text
    sf = _summary_for(out)
    assert len(sf) == 7 and all(v is None for v in sf.values()), sf
    assert "summary bindings: 0 binding file(s), 0 entries (no dashboard is bound" in text
    assert "compared 7 object(s)" in text and "7 identical" in text and "0 differ" in text, text
    assert _report(out)["summary_bindings"] == {"files": [], "entries": []}


# ------------------------------------------------------- binding for two
def test_binding_file_for_two_dashboards_carries_exactly_those(tmp_path, capsys):
    src = _pak_tree(tmp_path, "# probe bindings\nVMFolder=VMWARE:VMFolder\nHostFolder : VMWARE:HostFolder\n")
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    sf = _summary_for(out)
    assert sf.pop("probe-summary-vmfolder.yaml") == "VMWARE:VMFolder"
    assert sf.pop("probe-summary-hostfolder.yaml") == "VMWARE:HostFolder"
    assert all(v is None for v in sf.values()), sf
    assert "summary bindings: 1 binding file(s), 2 entries: 2 carried" in text
    assert ("BINDING content/dashboards/dashboards.properties:2 VMFolder=VMWARE:VMFolder: carried: "
            "dashboards/probe-summary-vmfolder.yaml: summary_for VMWARE:VMFolder") in text
    assert "7 identical" in text and "0 differ" in text, text
    rep = _report(out)["summary_bindings"]
    assert [e["status"] for e in rep["entries"]] == ["carried", "carried"]
    assert [e["line"] for e in rep["entries"]] == [2, 3]


def test_multi_kind_and_non_vmware_bindings_are_carried(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder,VMWARE:HostFolder\nOther\\ Things=ProbeAdapter:ProbeKind\n")
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    sf = _summary_for(out)
    assert sf["probe-summary-vmfolder.yaml"] == ["VMWARE:VMFolder", "VMWARE:HostFolder"]
    assert sf["probe-summary-other-things.yaml"] == "ProbeAdapter:ProbeKind"
    assert "7 identical" in text, text


def test_superseded_key_keeps_the_last_line(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:HostFolder\nVMFolder=VMWARE:VMFolder\n")
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    assert _summary_for(out)["probe-summary-vmfolder.yaml"] == "VMWARE:VMFolder"
    assert "dashboards.properties:1 VMFolder=VMWARE:HostFolder: superseded: line 2 has the same key" in text


# ------------------------------------------------ binding names an absent dir
def test_binding_naming_an_absent_dashboard_is_reported(tmp_path, capsys):
    src = _pak_tree(tmp_path, "Gone=VMWARE:ClusterComputeResource\n")
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    assert all(v is None for v in _summary_for(out).values())
    assert ("WARNING: BINDING content/dashboards/dashboards.properties:1 Gone=VMWARE:ClusterComputeResource: "
            "binds no dashboard: no dashboard of the input is in a directory named 'Gone' next to the file") in text
    assert _report(out)["summary_bindings"]["entries"][0]["status"] == "binds no dashboard"


def test_binding_of_a_dropped_dashboard_is_not_carried(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\n")
    drop = tmp_path / "drop.tsv"
    drop.write_text(_did(0) + "\n")
    rc, text = _run(src, tmp_path / "out", capsys, "pak", "--drop", drop)
    assert rc == 0, text
    assert f"WARNING: BINDING content/dashboards/dashboards.properties:1 VMFolder=VMWARE:VMFolder: not carried: " \
           f"dashboard {_did(0)} was dropped (--drop)" in text


# ---------------------------------------------------- what the YAML cannot carry
@pytest.mark.parametrize("binding,expect", [
    ("VMFolder=VMWARE\n", "does not split into exactly two ':' tokens"),
    ("VMFolder=VMWARE: VMFolder\n", "has an empty token or whitespace"),
    ("VMFolder=VMWARE:VMFolder,VMWARE:VMFolder\n", "lists VMWARE:VMFolder twice"),
    ("VMFolder=VMWARE:VMFolder\nHostFolder=VMWARE:VMFolder\n", "VMWARE:VMFolder is also bound by"),
])
def test_binding_the_yaml_cannot_carry_stops_the_dashboard_with_a_gap(tmp_path, capsys, binding, expect):
    src = _pak_tree(tmp_path, binding)
    rc, text = _run(src, tmp_path / "out", capsys, "pak", "--allow-partial")
    assert rc == 0, text
    assert f"FAILED dashboard {_did(0)} 'Probe Summary VMFolder': Summary binding VMFolder=" in text, text
    assert expect in text and "TOOLSET GAP" in text
    assert "not carried" in text
    assert "probe-summary-vmfolder.yaml" not in _summary_for(tmp_path / "out")


def test_bound_directory_holding_two_dashboards_is_a_gap(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\n")
    (src / "content" / "dashboards" / "VMFolder" / "second.json").write_text(
        json.dumps(_dashboard(tmp_path, 40, "Probe Second In Folder")))
    rc, text = _run(src, tmp_path / "out", capsys, "pak", "--allow-partial")
    assert rc == 0, text
    assert "holds 2 dashboards; the installer binds the first tab of its import result" in text
    assert "FAILED dashboard " + _did(0) in text and "FAILED dashboard " + _did(40) in text


def test_generic_templates_directory_is_a_gap(tmp_path, capsys):
    src = _pak_tree(tmp_path, extra=("GenericTemplatesProbe",))
    rc, text = _run(src, tmp_path / "out", capsys, "pak", "--allow-partial")
    assert rc == 0, text
    assert (f"FAILED dashboard {_did(7)} 'Probe Summary GenericTemplatesProbe': the dashboard sits in the pak "
            f"directory 'GenericTemplatesProbe'") in text


def test_copies_that_differ_only_in_binding_do_not_merge(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\n")
    dup = src / "content" / "dashboards" / "Copy"
    dup.mkdir()
    (dup / "dashboard.json").write_text((src / "content" / "dashboards" / "VMFolder" / "dashboard.json").read_text())
    rc, text = _run(src, tmp_path / "out", capsys, "pak", "--allow-partial")
    assert f"FAILED dashboard {_did(0)} 'Probe Summary VMFolder': the same id is defined differently" in text, text
    rc, text = _run(src, tmp_path / "out2", capsys, "pak", "--prefer-source", "Copy/")
    assert rc == 0, text
    assert _summary_for(tmp_path / "out2")["probe-summary-vmfolder.yaml"] is None


def test_dashboard_given_without_its_binding_file_binds_nothing(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\n")
    dash = src / "content" / "dashboards"
    rc, text = _run(dash / "VMFolder", tmp_path / "out", capsys, "pak", "--allow-partial")
    assert rc == 0, text
    assert _summary_for(tmp_path / "out") == {"probe-summary-vmfolder.yaml": None}, \
        "a dashboard given without its binding file has no binding in the source handed over"


# ------------------------------------------------------- packed pak and export
def test_packed_pak_binding_is_read_from_the_archive(tmp_path, capsys):
    src = _pak_tree(tmp_path, "NetworkFolder=VMWARE:NetworkFolder\n")
    pak = tmp_path / "probe.pak"
    with zipfile.ZipFile(pak, "w") as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.writestr(p.relative_to(src).as_posix(), p.read_bytes())
    out = tmp_path / "out"
    rc, text = _run(pak, out, capsys)
    assert rc == 0, text
    sf = _summary_for(out)
    assert sf.pop("probe-summary-networkfolder.yaml") == "VMWARE:NetworkFolder"
    assert all(v is None for v in sf.values())


def test_content_export_shaped_source_has_no_binding(tmp_path, capsys):
    """A content export carries no binding file (a content import cannot
    install one); dashboards in kind-named folders inside it bind nothing."""
    owner = io.BytesIO()
    with zipfile.ZipFile(owner, "w") as zf:
        for i, f in enumerate(FOLDERS):
            zf.writestr(f"{f}/dashboard.json", json.dumps(_dashboard(tmp_path, i, f"Probe Export {f}")))
    export = tmp_path / "export.zip"
    with zipfile.ZipFile(export, "w") as zf:
        zf.writestr("configuration.json", json.dumps({"dashboardsByOwner": {"admin": ["x"]}}))
        zf.writestr("dashboards/admin", owner.getvalue())
    out = tmp_path / "out"
    rc, text = _run(export, out, capsys, "third-party")
    assert rc == 0, text
    sf = _summary_for(out)
    assert len(sf) == 6 and all(v is None for v in sf.values()), sf
    assert "summary bindings: 0 binding file(s)" in text and "6 identical" in text


def test_third_party_layout_carries_the_binding_with_a_note(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\n")
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys, "third-party")
    assert rc == 0, text
    assert _summary_for(out)["probe-summary-vmfolder.yaml"] == "VMWARE:VMFolder"
    assert "a content import does not (only a pak's dashboards.properties does)" in text
    assert "python3 -m vcfcf_dashboards bind-summary" in text


# ------------------------------------- verification compares with the source
def test_verify_catches_a_binding_the_source_does_not_have(tmp_path, capsys, monkeypatch):
    """The old inference, put back: verification now compares the written
    binding with the source's binding file, so it shows as a difference."""
    from vcfcf_core.importer import dashboards as _d
    real = _d._DashMapper.map

    def inferred(self):
        y = real(self)
        folder = self.location.replace("\\", "/").split("/")[-2]
        if folder in FOLDERS:
            y["summary_for"] = f"VMWARE:{folder}"
        return y

    monkeypatch.setattr(_d._DashMapper, "map", inferred)
    src = _pak_tree(tmp_path)
    rc, text = _run(src, tmp_path / "out", capsys)
    assert rc == 5, text
    assert "6 differ" in text, text
    assert "dashboard.<summary binding>: extra \"VMWARE:VMFolder\"" in text
    assert "summary_for VMWARE:VMFolder has no binding entry in the source (an invented binding" in text
    # never accepted, and caught without a render compare too
    for i, extra in enumerate((("--allow-partial",), ("--allow-partial", "--no-verify"), ("--dry-run",))):
        o = tmp_path / f"o{i}"
        rc, text = _run(src, o, capsys, "pak", *extra)
        assert rc == 5, (extra, text)
        assert text.count("(no entry): mismatch") == 6, (extra, text)
        assert not o.exists()


def test_verify_catches_a_dropped_source_binding(tmp_path, capsys, monkeypatch):
    from vcfcf_core.importer import dashboards as _d
    real = _d._DashMapper.map

    def dropped(self):
        y = real(self)
        y.pop("summary_for", None)
        return y

    monkeypatch.setattr(_d._DashMapper, "map", dropped)
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\n")
    rc, text = _run(src, tmp_path / "out", capsys, "pak", "--allow-partial")
    assert rc == 5, text  # a written summary_for that is not the source's is a converter error
    assert "dashboard.<summary binding>: missing \"VMWARE:VMFolder\"" in text
    assert "VMFolder=VMWARE:VMFolder: mismatch" in text


# ---------------------------------------------------------- the file reader
def test_java_properties_reader():
    from vcfcf_core.java_properties import load_entries as _java_properties
    text = ("# comment\n! also a comment\n\n  a=1\nb : 2\nc 3\nd\\ e=4\nf=line\\\n    continued\n"
            "g=\\u0041\\t\nh==x\nlast")
    assert _java_properties(text) == [
        (4, "a", "1"), (5, "b", "2"), (6, "c", "3"), (7, "d e", "4"), (8, "f", "linecontinued"),
        (10, "g", "A\t"), (11, "h", "=x"), (12, "last", "")]
    with pytest.raises(ValueError):
        _java_properties("a=\\u12")


def test_binding_file_outside_a_dashboards_directory_is_passed_over(tmp_path, capsys):
    src = _pak_tree(tmp_path)
    (src / "content" / "dashboards.properties").write_text("VMFolder=VMWARE:VMFolder\n")
    rc, text = _run(src, tmp_path / "out", capsys)
    assert rc == 0, text
    assert ("content/dashboards.properties: a dashboards.properties that is not the pak's "
            "content/dashboards/dashboards.properties") in text
    assert all(v is None for v in _summary_for(tmp_path / "out").values())


def _pack(src: Path, tmp: Path) -> Path:
    pak = tmp / "probe.pak"
    with zipfile.ZipFile(pak, "w") as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                zf.writestr(p.relative_to(src).as_posix(), p.read_bytes())
    return pak


# ------------------------------------------------- the installer's exact reading
def test_bom_keeps_the_first_entry_from_binding(tmp_path, capsys):
    """FileReader keeps a UTF-8 BOM, so the first key carries U+FEFF and
    matches no directory; the second entry binds (OpenJDK 17, review B1)."""
    src = _pak_tree(tmp_path)
    (src / "content" / "dashboards" / "dashboards.properties").write_bytes(
        "﻿VMFolder=VMWARE:VMFolder\nHostFolder=VMWARE:HostFolder\n".encode("utf-8"))
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    sf = _summary_for(out)
    assert sf["probe-summary-vmfolder.yaml"] is None
    assert sf["probe-summary-hostfolder.yaml"] == "VMWARE:HostFolder"
    assert "binds no dashboard" in text and "starts with a byte-order mark" in text


@pytest.mark.parametrize("eol", ["\r\n", "\r"])
def test_crlf_and_cr_line_ends(tmp_path, capsys, eol):
    src = _pak_tree(tmp_path)
    (src / "content" / "dashboards" / "dashboards.properties").write_bytes(
        eol.join(["# c", "VMFolder=VMWARE:VMFolder", "HostFolder=VMWARE:HostFolder", ""]).encode())
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    sf = _summary_for(out)
    assert sf["probe-summary-vmfolder.yaml"] == "VMWARE:VMFolder"
    assert sf["probe-summary-hostfolder.yaml"] == "VMWARE:HostFolder"
    assert "2 carried" in text


@pytest.mark.parametrize("key", [".", "", "VMFolder/", "./VMFolder", "../dashboards/VMFolder", "VMFolder//",
                                 "vmfolder", "VMFolder\\ "])
@pytest.mark.parametrize("packed", [False, True])
def test_key_must_equal_the_directory_name_exactly(tmp_path, capsys, key, packed):
    """The installer looks a directory up by its exact name (review W1): no
    path normalization, the same on a directory input and a packed pak."""
    src = _pak_tree(tmp_path, f"{key}=VMWARE:VMFolder\n")
    if packed:
        src = _pack(src, tmp_path)
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    assert all(v is None for v in _summary_for(out).values()), text
    assert "1 binds no dashboard" in text, text


@pytest.mark.parametrize("rel,read", [
    ("content/dashboards/dashboards.properties", True),
    ("content/dashboards/dashboards/dashboards.properties", False),
    ("other/dashboards/dashboards.properties", False),
    ("dashboards/dashboards.properties", False),
])
@pytest.mark.parametrize("packed", [False, True])
def test_only_the_pak_binding_file_is_read(tmp_path, capsys, rel, read, packed):
    """Review W3: only content/dashboards/dashboards.properties under the
    pak root is read."""
    src = _pak_tree(tmp_path)
    nested = src / "content" / "dashboards" / "dashboards" / "VMFolder"
    nested.mkdir(parents=True)
    (nested / "dashboard.json").write_text(json.dumps(_dashboard(tmp_path, 50, "Probe Nested")))
    f = src / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("VMFolder=VMWARE:VMFolder\n")
    if packed:
        src = _pack(src, tmp_path)
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys)
    assert rc == 0, text
    sf = _summary_for(out)
    assert sf.get("probe-summary-vmfolder.yaml") == ("VMWARE:VMFolder" if read else None), text
    assert sf["probe-nested.yaml"] is None
    if not read:
        assert "that is not the pak's content/dashboards/dashboards.properties" in text


@pytest.mark.parametrize("given", ["content", "dashboards"])
def test_content_or_dashboards_directory_given_directly(tmp_path, capsys, given):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\n")
    root = src / "content" if given == "content" else src / "content" / "dashboards"
    out = tmp_path / "out"
    rc, text = _run(root, out, capsys)
    assert rc == 0, text
    assert _summary_for(out)["probe-summary-vmfolder.yaml"] == "VMWARE:VMFolder"


def test_gap_message_names_the_binding_file_relative_to_its_input(tmp_path, capsys):
    src = _pak_tree(tmp_path, "VMFolder=VMWARE\n")
    rc, text = _run(src, tmp_path / "out", capsys, "pak", "--allow-partial")
    line = next(ln for ln in text.splitlines() if ln.startswith("FAILED dashboard"))
    assert "(content/dashboards/dashboards.properties:1)" in line, line
    assert str(tmp_path) not in line


def test_partial_kind_map_on_a_bound_dashboard(tmp_path, capsys):
    """One of two bound kinds mapped: that dashboard stops; the other entry
    stays carried."""
    src = _pak_tree(tmp_path, "VMFolder=VMWARE:VMFolder\nHostFolder=VMWARE:HostFolder\n")
    km = tmp_path / "k.tsv"
    km.write_text("VMWARE\tVMFolder\tprobe_new\tProbeFolder\n")
    out = tmp_path / "out"
    rc, text = _run(src, out, capsys, "pak", "--allow-partial", "--map-kind", km)
    assert rc == 0, text
    assert "Summary page for VMWARE:VMFolder (its binding content/dashboards/dashboards.properties:1)" in text
    sf = _summary_for(out)
    assert "probe-summary-vmfolder.yaml" not in sf
    assert sf["probe-summary-hostfolder.yaml"] == "VMWARE:HostFolder"
    assert "HostFolder=VMWARE:HostFolder: carried" in text


def test_post_install_uses_the_shared_java_reader():
    """post_install reads dashboards.properties through the same reader:
    \\uXXXX decoded, the BOM kept, only \\n and \\r end a line, a malformed
    \\u escape refused (review N1)."""
    from vcfcf_managementpacks import post_install as pi
    props = pi.parse_properties("﻿a=1\n\\u0056MFolder=VMWARE:VMFolder\nb=x y\n")
    assert props == {"﻿a": "1", "VMFolder": "VMWARE:VMFolder", "b": "x y"}
    with pytest.raises(ValueError):
        pi.parse_properties("a=\\u12")
