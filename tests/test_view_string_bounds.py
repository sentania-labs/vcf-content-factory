"""Color bounds on a string attribute column are text (2026-11-13).

On a column with ``is_string_attribute: true`` (the wire's
``isStringAttribute="true"``) VCF Ops matches a bound as a string, so the
view loader keeps the bound exactly as written and the renderer writes it
verbatim; an unquoted YAML number or bool there is a load error (it would be
respelled). Bounds on every other column behave as before. Wire format:
knowledge/context/wire-formats/view_fidelity_wire_format.md §String-column
bounds. All fixtures are synthetic.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from vcfcf_core.dashboards.loader import DashboardValidationError, load_view
from vcfcf_core.dashboards.render import render_views_xml

REPO = Path(__file__).resolve().parents[1]
VID = "7a000000-0000-4000-8000-0000000005b0"


def _view(tmp_path: Path, columns: str, name: str = "Probe String Bounds") -> Path:
    p = tmp_path / "view.yaml"
    p.write_text(textwrap.dedent(f"""\
        id: {VID}
        name: {name}
        description: synthetic string-bound probe
        subject:
          adapter_kind: VMWARE
          resource_kind: ClusterComputeResource
        columns:
        """) + textwrap.indent(textwrap.dedent(columns), "  "))
    return p


def _bounds(xml: str, attribute: str) -> dict:
    item = re.search(r'<Item><Value>(?:(?!</Item>).)*?name="attributeKey" value="%s".*?</Item>' % re.escape(attribute),
                     xml, re.S).group(0)
    return dict(re.findall(r'<Property name="(yellowBound|orangeBound|redBound|ascendingRange)" value="([^"]*)"/>',
                           item))


STRING_COLUMNS = """\
- attribute: configuration|dasConfig|admissionControlEnabled
  display_name: Admission Control
  is_property: true
  is_string_attribute: true
  yellow_bound: "false"
  orange_bound: "1"
  red_bound: "2"
  ascending_range: true
- attribute: config|policies|security|vlan_id
  display_name: VLAN
  is_property: true
  is_string_attribute: true
  orange_bound: "0"
  red_bound: none
  ascending_range: true
- attribute: summary|guest|toolsRunningStatus
  display_name: Tools
  is_property: true
  is_string_attribute: true
  red_bound: " Not Running "
"""


def test_quoted_bounds_on_a_string_column_render_verbatim(tmp_path):
    v = load_view(_view(tmp_path, STRING_COLUMNS), enforce_framework_prefix=False)
    c0, c1, c2 = v.columns
    assert (c0.yellow_bound, c0.orange_bound, c0.red_bound) == ("false", "1", "2")
    assert (c1.orange_bound, c1.red_bound) == ("0", "none")
    assert c2.red_bound == " Not Running "  # the exact text, surrounding spaces included
    xml = render_views_xml([v])
    assert _bounds(xml, "configuration|dasConfig|admissionControlEnabled") == {
        "yellowBound": "false", "orangeBound": "1", "redBound": "2", "ascendingRange": "true"}
    assert _bounds(xml, "config|policies|security|vlan_id") == {
        "orangeBound": "0", "redBound": "none", "ascendingRange": "true"}
    assert _bounds(xml, "summary|guest|toolsRunningStatus") == {"redBound": " Not Running "}


@pytest.mark.parametrize("raw,kind,coerced", [
    ("Off", "a boolean", ('"false"', "False")),   # a real vendor string-column bound
    ("yes", "a boolean", ('"true"', "True")),
    ("true", "a boolean", ("True",)),
    ("010", "a number", ('"8"', " 8")),                # YAML 1.1 octal
    ("1.50", "a number", ("1.5",)),
    ("0", "a number", ()),
])
def test_an_unquoted_number_or_bool_on_a_string_column_is_an_error(tmp_path, raw, kind, coerced):
    """The error says what YAML read the scalar as and asks for the exact
    text quoted; it never echoes a spelling built from the converted value
    (``Off`` is False, ``010`` is 8), which would be a different match."""
    p = _view(tmp_path, f"""\
        - attribute: config|hyperThread|active
          display_name: HT
          is_property: true
          is_string_attribute: true
          red_bound: {raw}
        """)
    with pytest.raises(DashboardValidationError) as exc:
        load_view(p, enforce_framework_prefix=False)
    msg = str(exc.value)
    assert "string attribute column" in msg and f"YAML read it as {kind}" in msg, msg
    assert 'red_bound: "..."' in msg, msg
    for spelling in coerced:
        assert spelling not in msg, (spelling, msg)


def test_is_string_attribute_must_be_a_bool(tmp_path):
    """A quoted 'false' is not truthy-coerced into a string column."""
    p = _view(tmp_path, """\
        - attribute: cpu|usage_average
          display_name: CPU
          is_string_attribute: 'false'
          red_bound: 90
        """)
    with pytest.raises(DashboardValidationError, match="is_string_attribute must be a bool"):
        load_view(p, enforce_framework_prefix=False)


@pytest.mark.parametrize("attribute", ["config|policies|security|vlan_id", "cpu|usage_average"])
def test_a_red_only_bound_on_a_string_column_takes_the_property_match_ascending_rule(tmp_path, attribute):
    """Every bound on a string column is text, so a red-only ``'0'`` is a
    property-match bound: ascending_range may be omitted or true, never
    false (no export carries false there). This holds whatever the
    attribute is, a metric key flagged as a string attribute included."""
    base = f"""\
        - attribute: {attribute}
          display_name: Probe
          is_string_attribute: true
          red_bound: '0'
        """
    with pytest.raises(DashboardValidationError, match="ascending_range may be omitted or true"):
        load_view(_view(tmp_path, base + "  ascending_range: false\n"), enforce_framework_prefix=False)
    v = load_view(_view(tmp_path, base + "  ascending_range: true\n"), enforce_framework_prefix=False)
    assert _bounds(render_views_xml([v]), attribute) == {"redBound": "0", "ascendingRange": "true"}


def test_a_string_column_needs_no_ascending_range_and_cannot_omit_it(tmp_path):
    """Its bounds are not numbers, so the numeric-bound rules do not apply:
    three bounds without ascending_range load (and render none), and
    ``omit: [ascending_range]`` names a Property the column does not emit."""
    v = load_view(_view(tmp_path, """\
        - attribute: summary|configStatus
          display_name: Status
          is_string_attribute: true
          yellow_bound: "0"
          orange_bound: "1"
          red_bound: "2"
        """), enforce_framework_prefix=False)
    assert _bounds(render_views_xml([v]), "summary|configStatus") == {
        "yellowBound": "0", "orangeBound": "1", "redBound": "2"}
    with pytest.raises(DashboardValidationError, match="no numeric color bound"):
        load_view(_view(tmp_path, """\
            - attribute: summary|configStatus
              display_name: Status
              is_string_attribute: true
              yellow_bound: "0"
              orange_bound: "1"
              red_bound: "2"
              omit: [ascending_range]
            """), enforce_framework_prefix=False)


def test_numeric_column_bounds_are_unchanged(tmp_path):
    """Numbers (quoted or not) on a numeric column are floats as before; a
    non-numeric string there is accepted and rendered as written (stripped),
    as before: vendor exports and third-party views carry it."""
    v = load_view(_view(tmp_path, """\
        - attribute: cpu|usage_average
          display_name: CPU
          yellow_bound: 70
          orange_bound: "80"
          red_bound: 90.5
          ascending_range: false
        - attribute: summary|runtime|powerState
          display_name: Power
          red_bound: " Powered Off "
        """), enforce_framework_prefix=False)
    assert (v.columns[0].yellow_bound, v.columns[0].orange_bound, v.columns[0].red_bound) == (70.0, 80.0, 90.5)
    xml = render_views_xml([v])
    assert _bounds(xml, "cpu|usage_average") == {
        "yellowBound": "70.0", "orangeBound": "80.0", "redBound": "90.5", "ascendingRange": "false"}
    assert _bounds(xml, "summary|runtime|powerState") == {"redBound": "Powered Off"}


# ------------------------------------------------- import-local, end to end
def _cli(*args) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONPATH=str(REPO / "src"))
    return subprocess.run([sys.executable, "-m", "vcfcf_extractor", "import-local", *map(str, args)],
                          cwd=REPO, env=env, capture_output=True, text=True)


@pytest.fixture()
def source(tmp_path) -> Path:
    """A product-shaped source view XML with string-column bounds, rendered
    from the synthetic YAML above."""
    v = load_view(_view(tmp_path, STRING_COLUMNS), enforce_framework_prefix=False)
    src = tmp_path / "src"
    src.mkdir()
    (src / "View - Probe.xml").write_text(render_views_xml([v]))
    return src


def test_import_local_converts_string_bounds_identically(source, tmp_path):
    out = tmp_path / "out"
    r = _cli(source, "--out", out, "--layout", "third-party", "--project-name", "probe", "--ids", "keep",
             "--naming", "unprefixed")
    text = r.stdout + r.stderr
    assert r.returncode == 0, text
    assert re.search(r"view +1 of 1 identical", text), text
    cols = yaml.safe_load((out / "views" / "probe-string-bounds.yaml").read_text())["columns"]
    assert (cols[0]["yellow_bound"], cols[0]["orange_bound"], cols[0]["red_bound"]) == ("false", "1", "2")
    assert (cols[1]["orange_bound"], cols[1]["red_bound"]) == ("0", "none")
    assert cols[2]["red_bound"] == " Not Running "


@pytest.mark.parametrize("old,new", [("orange_bound: '1'", "orange_bound: '7'"),
                                     ("orange_bound: '0'", "orange_bound: 'O'")])
def test_import_local_catches_a_one_character_change_of_a_bound(source, tmp_path, old, new):
    """import-local's verification compares the written YAML's render with
    the source exactly: a bound changed by one character in the written tree
    is reported as differing."""
    from types import SimpleNamespace
    from vcfcf_core.importer.convert import ConvertOptions, plan_conversion
    from vcfcf_core.importer.inputs import scan_inputs
    from vcfcf_extractor import importer as I

    def status(plan, tree):
        v = I._verify(plan, tree, "third-party")
        assert not v["load_errors"], v["load_errors"]
        return {d["file"]: d["status"] for d in v["objects_detail"]}["views/probe-string-bounds.yaml"]

    plan = plan_conversion(scan_inputs([source]), ConvertOptions(ids="keep", naming="unprefixed",
                                                                 layout="third-party"))
    I._load_check(plan, "third-party", None)
    tree = tmp_path / "tree"
    I._write_tree(plan, tree, SimpleNamespace(layout="third-party", project_name="probe", naming="unprefixed"),
                  tmp_path / "absent", None)
    assert status(plan, tree) == "identical"
    p = tree / "views" / "probe-string-bounds.yaml"
    text = p.read_text()
    assert old in text, text
    p.write_text(text.replace(old, new, 1))
    assert status(plan, tree) == "differs"
