"""View-column ``supermetric:"<name>"`` (no ``@``) token case (issue #146).

The formula form ``@supermetric:"<name>"`` was made token-case-insensitive in
PR #141 (``vcfops_supermetrics.crossref.SM_CROSSREF_RE``).  The view-column
form one path over (``vcfops_dashboards.render._xml_attribute_item``) still
tested the prefix with a case-sensitive ``startswith``, while the loader and
``vcfops_packaging.deps._is_sm_ref`` both lowercase before comparing.  A
mis-cased token (``SuperMetric:"X"``) therefore passed validate, passed the
dependency audit, and shipped as a literal ``attributeKey`` with
``rollUpType=AVG``: a blank column in the UI with no diagnostic anywhere.

Boundary pinned here: the TOKEN is case-insensitive, the quoted NAME is
case-sensitive, and an unresolved name is a hard ``ValueError``.

All fixtures are tmp_path-local; no content YAML is touched.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

REF_UUID = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
REF_NAME = "[VCF Content Factory] Ref SM"
RESOLVED_KEY = f"Super Metric|sm_{REF_UUID}"

TOKEN_SPELLINGS = [
    "supermetric",  # canonical
    "SuperMetric",  # camel (the exact spelling reproduced in #146)
    "SUPERMETRIC",  # upper
    "Supermetric",  # sentence
]


def _sm_file(tmp_path: Path, sm_id: str, name: str) -> Path:
    d = tmp_path / "supermetrics"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{sm_id}.yaml"
    p.write_text(textwrap.dedent(f"""\
        id: {sm_id}
        name: "{name}"
        formula: 'avg(${{adaptertype=VMWARE, objecttype=HostSystem, metric=cpu|usage_average, depth=5}})'
        description: "probe"
        unit_id: percent
        resource_kinds:
          - resource_kind_key: HostSystem
            adapter_kind_key: VMWARE
        """))
    return p


def _view(tmp_path: Path, attribute: str, stem: str = "view"):
    from vcfops_dashboards.loader import load_view

    d = tmp_path / "views"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}.yaml"
    p.write_text(yaml.dump({
        "name": "[VCF Content Factory] SM Column Case Probe",
        "description": "probe",
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [
            {"display_name": "Plain", "attribute": "cpu|usage_average"},
            {"display_name": "SM", "attribute": attribute},
        ],
    }, default_flow_style=False))
    return load_view(p, enforce_framework_prefix=False)


def _render(tmp_path: Path, attribute: str, sm_files: list[Path]) -> str:
    from vcfops_dashboards.render import render_view_def_fragments

    return render_view_def_fragments(
        [_view(tmp_path, attribute)],
        sm_scope=sm_files,
        bundle_context="case-probe",
    )


class TestViewColumnTokenCaseInsensitivity:
    @pytest.mark.parametrize("token", TOKEN_SPELLINGS)
    @pytest.mark.parametrize("quote", ['"', "'"])
    def test_every_token_spelling_resolves_to_sm_uuid(self, tmp_path, token, quote):
        ref = _sm_file(tmp_path, REF_UUID, REF_NAME)
        xml = _render(tmp_path, f"{token}:{quote}{REF_NAME}{quote}", [ref])

        assert f'<Property name="attributeKey" value="{RESOLVED_KEY}"/>' in xml, xml
        # The literal token never reaches the wire, in any spelling.
        assert "supermetric:" not in xml.lower(), xml
        # SM columns carry rollUpType NONE, never the AVG default that the
        # mis-cased token used to fall through to.
        sm_item = xml.split(RESOLVED_KEY, 1)[1].split("</Item>", 1)[0]
        assert '<Property name="rollUpType" value="NONE"/>' in sm_item, sm_item

    @pytest.mark.parametrize("token", ["SuperMetric", "SUPERMETRIC"])
    def test_mis_cased_token_unresolved_name_is_a_hard_error(self, tmp_path, token):
        ref = _sm_file(tmp_path, REF_UUID, REF_NAME)
        with pytest.raises(ValueError, match="Nowhere SM"):
            _render(tmp_path, f'{token}:"[VCF Content Factory] Nowhere SM"', [ref])

    @pytest.mark.parametrize("token", ["SuperMetric", "SUPERMETRIC"])
    def test_mis_cased_token_with_empty_scope_is_a_hard_error(self, tmp_path, token):
        # Before #146 this was the reports-green-while-broken path: no SM in
        # scope, mis-cased token, and the renderer emitted the literal.
        with pytest.raises(ValueError, match="not in the bundle scope"):
            _render(tmp_path, f'{token}:"{REF_NAME}"', [])


class TestViewColumnNameCaseIsExact:
    """Issue #148, view-column half.  The token is forgiving, the name is
    not: the SM name map is keyed by exact display name and _SM_COLUMN_REF_RE
    scopes ``(?i:...)`` to the token only.  A hoist to ``re.I`` on the whole
    pattern would not by itself fold the NAME lookup (that is a dict get),
    but the two tests below pin the observable contract either way."""

    OTHER_UUID = "cccccccc-3333-4333-8333-cccccccccccc"

    @pytest.mark.parametrize("token", TOKEN_SPELLINGS)
    @pytest.mark.parametrize("wrong_name", [REF_NAME.lower(), REF_NAME.upper()])
    def test_wrong_case_name_is_a_hard_error(self, tmp_path, token, wrong_name):
        assert wrong_name != REF_NAME
        ref = _sm_file(tmp_path, REF_UUID, REF_NAME)
        with pytest.raises(ValueError, match="not in the bundle scope"):
            _render(tmp_path, f'{token}:"{wrong_name}"', [ref])

    @pytest.mark.parametrize("token", ["supermetric", "SuperMetric"])
    def test_two_sms_differing_only_by_name_case_stay_distinct(self, tmp_path, token):
        lower_name = REF_NAME.lower()
        ref = _sm_file(tmp_path, REF_UUID, REF_NAME)
        other = _sm_file(tmp_path, self.OTHER_UUID, lower_name)

        exact = _render(tmp_path, f'{token}:"{REF_NAME}"', [ref, other])
        assert f'value="Super Metric|sm_{REF_UUID}"' in exact, exact
        assert self.OTHER_UUID not in exact, exact

        lower = _render(tmp_path, f'{token}:"{lower_name}"', [ref, other])
        assert f'value="Super Metric|sm_{self.OTHER_UUID}"' in lower, lower
        assert REF_UUID not in lower, lower
