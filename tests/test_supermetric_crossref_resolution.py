"""``@supermetric:"<name>"`` must be resolved on every emit and push path.

The resolver used to live only in ``vcfops_managementpacks.sdk_builder`` (the
Tier 2 pak path).  Every other path that emits or pushes a formula copied the
authoring-time token verbatim:

  * ``vcfops_packaging.builder._render_supermetrics_dict`` (native bundle zip,
    and via it the discrete and release builders) did
    ``" ".join(sm.formula.split())`` and nothing else;
  * ``vcfops_supermetrics.client.import_supermetrics_bundle`` (live sync)
    normalized whitespace and pushed the literal token.

VCF Ops cannot parse ``@supermetric:``, so the resulting super metric is silently
broken.  The resolver now lives in ``vcfops_supermetrics.crossref`` and every
path uses it.

Per path this asserts the same three behaviours: a resolvable ref rewrites to
``Super Metric|sm_<uuid>``, an unresolvable one raises with a useful message,
and a formula with no token is unchanged.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REF_UUID = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
CONSUMER_UUID = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
PLAIN_UUID = "cccccccc-3333-4333-8333-cccccccccccc"

REF_NAME = "[VCF Content Factory] Ref SM"
CONSUMER_NAME = "[VCF Content Factory] Consumer SM"
PLAIN_NAME = "[VCF Content Factory] Plain SM"

PLAIN_FORMULA = "avg(${adaptertype=VMWARE, objecttype=HostSystem, metric=cpu|usage_average, depth=5})"
CONSUMER_FORMULA = (
    'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
    'attribute=@supermetric:"' + REF_NAME + '", depth=5})'
)
MISSING_FORMULA = (
    'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
    'attribute=@supermetric:"[VCF Content Factory] Nowhere SM", depth=5})'
)

RESOLVED_TOKEN = f"Super Metric|sm_{REF_UUID}"


def _sm_yaml(sm_id: str, name: str, formula: str) -> str:
    return textwrap.dedent(f"""\
        id: {sm_id}
        name: "{name}"
        formula: '{formula}'
        description: "probe"
        unit_id: percent
        resource_kinds:
          - resource_kind_key: HostSystem
            adapter_kind_key: VMWARE
        """)


def _load(tmp_path: Path, sm_id: str, name: str, formula: str):
    from vcfops_supermetrics.loader import load_file

    p = tmp_path / f"{sm_id}.yaml"
    p.write_text(_sm_yaml(sm_id, name, formula))
    return load_file(p)


@pytest.fixture()
def sms(tmp_path):
    return {
        "ref": _load(tmp_path, REF_UUID, REF_NAME, PLAIN_FORMULA),
        "consumer": _load(tmp_path, CONSUMER_UUID, CONSUMER_NAME, CONSUMER_FORMULA),
        "plain": _load(tmp_path, PLAIN_UUID, PLAIN_NAME, PLAIN_FORMULA),
        "orphan": _load(tmp_path, CONSUMER_UUID, CONSUMER_NAME, MISSING_FORMULA),
    }


# --- the shared resolver itself ---------------------------------------------

class TestSharedResolver:
    def test_resolvable_ref_rewrites(self):
        from vcfops_supermetrics.crossref import resolve_sm_formula

        out = resolve_sm_formula(CONSUMER_FORMULA, CONSUMER_NAME, {REF_NAME: REF_UUID})
        assert RESOLVED_TOKEN in out
        assert "@supermetric:" not in out

    def test_unresolvable_ref_raises_useful_message(self):
        from vcfops_supermetrics.crossref import (
            SuperMetricCrossRefError,
            resolve_sm_formula,
        )

        with pytest.raises(SuperMetricCrossRefError) as exc:
            resolve_sm_formula(MISSING_FORMULA, CONSUMER_NAME, {})
        msg = str(exc.value)
        assert CONSUMER_NAME in msg, "message must name the SM with the bad formula"
        assert "[VCF Content Factory] Nowhere SM" in msg, "message must name the missing SM"

    def test_formula_without_token_unchanged(self):
        from vcfops_supermetrics.crossref import resolve_sm_formula

        assert resolve_sm_formula(PLAIN_FORMULA, PLAIN_NAME, {}) == PLAIN_FORMULA

    def test_already_resolved_token_is_idempotent(self):
        from vcfops_supermetrics.crossref import resolve_sm_formula

        once = resolve_sm_formula(CONSUMER_FORMULA, CONSUMER_NAME, {REF_NAME: REF_UUID})
        twice = resolve_sm_formula(once, CONSUMER_NAME, {REF_NAME: REF_UUID})
        assert once == twice

    def test_fallback_lookup_used_when_map_misses(self):
        from vcfops_supermetrics.crossref import resolve_sm_formula

        out = resolve_sm_formula(
            CONSUMER_FORMULA, CONSUMER_NAME, {},
            fallback_lookup=lambda name: REF_UUID if name == REF_NAME else None,
        )
        assert RESOLVED_TOKEN in out




class TestHandWrittenPrefixIsAbsorbed:
    """PR #142 regression: authored ``metric=Super Metric|@supermetric:"X"``.

    The token supplies its own ``Super Metric|``, so a hand-written prefix used
    to emit ``Super Metric|Super Metric|sm_<uuid>`` — as unparseable as the
    literal token, with the build reporting success throughout.  The match
    absorbs an immediately-preceding prefix instead.
    """

    PREFIXED_FORMULA = (
        'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
        'metric=Super Metric|@supermetric:"' + REF_NAME + '", depth=5})'
    )

    def test_no_doubled_prefix(self):
        from vcfops_supermetrics.crossref import resolve_sm_formula

        out = resolve_sm_formula(
            self.PREFIXED_FORMULA, CONSUMER_NAME, {REF_NAME: REF_UUID}
        )
        assert "Super Metric|Super Metric" not in out, out
        assert out.count(RESOLVED_TOKEN) == 1, out
        assert "@supermetric" not in out

    def test_matches_the_unprefixed_form(self):
        from vcfops_supermetrics.crossref import resolve_sm_formula

        prefixed = resolve_sm_formula(
            self.PREFIXED_FORMULA, CONSUMER_NAME, {REF_NAME: REF_UUID}
        )
        bare = resolve_sm_formula(
            self.PREFIXED_FORMULA.replace("Super Metric|@supermetric", "@supermetric"),
            CONSUMER_NAME,
            {REF_NAME: REF_UUID},
        )
        assert prefixed == bare

    @pytest.mark.parametrize("prefix", [
        "Super Metric|",                 # canonical
        "super metric|",                 # lowercase
        "SUPER METRIC|",                 # uppercase
        "Super Metric| ",                # space after the pipe
        "Super  Metric |",               # extra internal / pre-pipe whitespace
        "Super Metric|Super Metric|",    # already doubled in source
        "super metric|SUPER METRIC|",    # doubled and mixed case
    ])
    def test_prefix_variants_all_absorb_to_one_prefix(self, prefix):
        """Absorption is case- and whitespace-insensitive, and repeats.

        Round-2 review WARNING A: absorption used to be exact-case-and-spacing,
        so each of these spellings emitted a doubled prefix silently while the
        build reported success.
        """
        from vcfops_supermetrics.crossref import resolve_sm_formula

        formula = (
            'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
            'metric=' + prefix + '@supermetric:"' + REF_NAME + '", depth=5})'
        )
        out = resolve_sm_formula(formula, CONSUMER_NAME, {REF_NAME: REF_UUID})

        assert out.count("Super Metric|") == 1, out
        assert out.count(RESOLVED_TOKEN) == 1, out
        assert f"metric={RESOLVED_TOKEN}" in out, out
        assert "@supermetric" not in out
        # Identical to the bare form, whatever the author typed.
        assert out == resolve_sm_formula(
            formula.replace(prefix + "@supermetric", "@supermetric"),
            CONSUMER_NAME,
            {REF_NAME: REF_UUID},
        )

    def test_bundle_builder_emits_no_doubled_prefix(self, tmp_path):
        """End to end through the path that shipped the defect."""
        from vcfops_packaging.builder import _render_supermetrics_dict

        ref = _load(tmp_path, REF_UUID, REF_NAME, PLAIN_FORMULA)
        consumer = _load(tmp_path, CONSUMER_UUID, CONSUMER_NAME, self.PREFIXED_FORMULA)

        class _B:
            supermetrics = [ref, consumer]

        out = _render_supermetrics_dict(_B())
        formula = out[CONSUMER_UUID]["formula"]
        assert "Super Metric|Super Metric" not in formula, formula
        assert f"metric={RESOLVED_TOKEN}" in formula, formula


class TestNearMissSyntaxIsRejected:
    """A near-miss that the regex does not match must not ship the literal."""

    @pytest.mark.parametrize("formula", [
        'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
        'metric=@supermetric: "' + REF_NAME + '", depth=5})',
        'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
        "metric=@supermetric:" + REF_NAME + ", depth=5})",
        # Round-3 review: the near-miss guard was case-sensitive, so a
        # mis-cased near-miss shipped the literal token verbatim.  The
        # dependency audit cannot see it either (``_is_sm_ref`` lowercases),
        # so this was the silent-ship path.
        'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
        'metric=@SuperMetric: "' + REF_NAME + '", depth=5})',
        'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
        "metric=@SUPERMETRIC:" + REF_NAME + ", depth=5})",
    ])
    def test_literal_token_surviving_is_a_hard_error(self, formula):
        from vcfops_supermetrics.crossref import (
            SuperMetricCrossRefError,
            resolve_sm_formula,
        )

        with pytest.raises(SuperMetricCrossRefError) as exc:
            resolve_sm_formula(formula, CONSUMER_NAME, {REF_NAME: REF_UUID})
        assert "@supermetric" in str(exc.value)


class TestSupermetricWithoutIdIsNamed:
    """An in-scope SM with no id gets its own diagnostic, not the generic one."""

    def test_message_names_the_missing_id(self):
        from vcfops_supermetrics.crossref import (
            SuperMetricCrossRefError,
            resolve_sm_formula,
        )

        with pytest.raises(SuperMetricCrossRefError) as exc:
            resolve_sm_formula(CONSUMER_FORMULA, CONSUMER_NAME, {REF_NAME: None})
        msg = str(exc.value)
        assert REF_NAME in msg
        assert "no id" in msg, msg

    def test_map_builder_keeps_the_idless_entry(self):
        from vcfops_supermetrics.crossref import sm_name_to_uuid_map

        class _SM:
            def __init__(self, name, sm_id):
                self.name = name
                self.id = sm_id

        m = sm_name_to_uuid_map([_SM(REF_NAME, None), _SM(PLAIN_NAME, PLAIN_UUID)])
        assert m == {REF_NAME: None, PLAIN_NAME: PLAIN_UUID}

# --- native bundle builder (also feeds discrete + release builders) ---------

class TestNativeBundleBuilder:
    @staticmethod
    def _bundle(supermetrics):
        from vcfops_packaging.loader import Bundle

        return Bundle(
            name="probe", description="", sync_enabled=True,
            supermetrics=list(supermetrics), views=[], dashboards=[],
            customgroups=[], reports=[], symptoms=[], alerts=[],
            recommendations=[], builtin_metric_enables=[], source_path=None,
        )

    def test_resolvable_ref_rewrites(self, sms):
        from vcfops_packaging.builder import _render_supermetrics_dict

        out = _render_supermetrics_dict(self._bundle([sms["ref"], sms["consumer"]]))
        assert RESOLVED_TOKEN in out[CONSUMER_UUID]["formula"]
        assert "@supermetric:" not in out[CONSUMER_UUID]["formula"]

    def test_unresolvable_ref_raises_useful_message(self, sms):
        from vcfops_packaging.builder import _render_supermetrics_dict
        from vcfops_packaging.loader import BundleValidationError

        with pytest.raises(BundleValidationError) as exc:
            _render_supermetrics_dict(self._bundle([sms["orphan"]]))
        msg = str(exc.value)
        assert CONSUMER_NAME in msg
        assert "[VCF Content Factory] Nowhere SM" in msg

    def test_formula_without_token_unchanged(self, sms):
        from vcfops_packaging.builder import _render_supermetrics_dict

        out = _render_supermetrics_dict(self._bundle([sms["plain"]]))
        assert out[PLAIN_UUID]["formula"] == PLAIN_FORMULA


# --- discrete builder: pulls the referent into the component ----------------

class TestDiscreteBuilderCrossRefExpansion:
    def test_referenced_sm_is_pulled_into_the_component(self, sms):
        from vcfops_packaging.discrete_builder import _expand_sm_crossrefs

        expanded = _expand_sm_crossrefs([sms["consumer"]], [sms["ref"], sms["consumer"]])
        assert [s.name for s in expanded] == [CONSUMER_NAME, REF_NAME]

    def test_unresolvable_ref_raises_useful_message(self, sms):
        from vcfops_packaging.discrete_builder import (
            DiscreteBuilderError,
            _expand_sm_crossrefs,
        )

        with pytest.raises(DiscreteBuilderError) as exc:
            _expand_sm_crossrefs([sms["orphan"]], [sms["orphan"]])
        msg = str(exc.value)
        assert CONSUMER_NAME in msg
        assert "[VCF Content Factory] Nowhere SM" in msg

    def test_formula_without_token_is_a_noop(self, sms):
        from vcfops_packaging.discrete_builder import _expand_sm_crossrefs

        expanded = _expand_sm_crossrefs([sms["plain"]], [sms["plain"], sms["ref"]])
        assert [s.name for s in expanded] == [PLAIN_NAME]


# --- live sync path ---------------------------------------------------------

def _fake_client_cls():
    """Subclass the real SM client so _normalize_formula and friends are real.

    Only the pieces the resolver touches are exercised; the HTTP call is stubbed
    out by the caller and the assembled sm_dict is captured from the zip.
    """
    from vcfops_supermetrics.client import VCFOpsClient

    class _FakeClient(VCFOpsClient):
        def __init__(self, remote_by_name=None):  # noqa: D107 - no HTTP session
            self.remote_by_name = remote_by_name or {}
            self.captured = None
            self.find_calls = []
            self._marker_filename = None

        def find_by_name(self, name):
            self.find_calls.append(name)
            uuid = self.remote_by_name.get(name)
            return {"id": uuid, "name": name} if uuid else None

    return _FakeClient



def _run_import(client, sms_wire, monkeypatch):
    """Call the real import_supermetrics_bundle body against _FakeClient."""
    import vcfops_supermetrics.client as sm_client
    import vcfops_dashboards.client as dash_client

    monkeypatch.setattr(dash_client, "get_current_user", lambda c: {"id": "owner"})
    monkeypatch.setattr(dash_client, "discover_marker_filename", lambda c: "marker")

    captured = {}

    def _fake_import(c, zip_bytes):
        import io
        import json
        import zipfile

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            captured.update(json.loads(z.read("supermetrics.json")))
        return {"operationSummaries": [
            {"contentType": "SUPER_METRICS", "imported": len(captured), "skipped": 0}
        ]}

    monkeypatch.setattr(dash_client, "import_content_zip", _fake_import)

    real = sm_client.VCFOpsClient.import_supermetrics_bundle
    client._marker_filename = None
    real(client, sms_wire)
    return captured


def _wire(sm):
    return {
        "id": sm.id, "name": sm.name, "formula": sm.formula,
        "description": sm.description, "unitId": sm.unit_id,
        "resourceKinds": sm.resource_kinds,
    }


class TestLiveSyncPath:
    def test_resolvable_ref_rewrites(self, sms, monkeypatch):
        client = _fake_client_cls()()
        out = _run_import(client, [_wire(sms["ref"]), _wire(sms["consumer"])], monkeypatch)
        assert RESOLVED_TOKEN in out[CONSUMER_UUID]["formula"]
        assert "@supermetric:" not in out[CONSUMER_UUID]["formula"]
        assert client.find_calls == [], "in-batch names must not hit the server"

    def test_ref_resolved_against_existing_instance_sm(self, sms, monkeypatch):
        client = _fake_client_cls()(remote_by_name={REF_NAME: REF_UUID})
        out = _run_import(client, [_wire(sms["consumer"])], monkeypatch)
        assert RESOLVED_TOKEN in out[CONSUMER_UUID]["formula"]
        assert client.find_calls == [REF_NAME]

    def test_unresolvable_ref_raises_useful_message(self, sms, monkeypatch):
        from vcfops_common.client import VCFOpsError

        client = _fake_client_cls()()
        with pytest.raises(VCFOpsError) as exc:
            _run_import(client, [_wire(sms["orphan"])], monkeypatch)
        msg = str(exc.value)
        assert CONSUMER_NAME in msg
        assert "[VCF Content Factory] Nowhere SM" in msg

    def test_formula_without_token_unchanged(self, sms, monkeypatch):
        client = _fake_client_cls()()
        out = _run_import(client, [_wire(sms["plain"])], monkeypatch)
        assert out[PLAIN_UUID]["formula"] == PLAIN_FORMULA


class TestDoubledPrefixIsRejected:
    """Backstop for the class absorption closes: a doubled prefix with no token.

    Absorption only fires where there is an ``@supermetric:`` token to absorb
    into.  A formula can arrive already doubled with no token at all (typed by
    hand, or copied out of a broken export), and emitting that is as unparseable
    as emitting the literal token.  It is a hard error on every emit path.
    """

    @pytest.mark.parametrize("doubled", [
        "Super Metric|Super Metric|",
        "super metric|super metric|",
        "SUPER METRIC|SUPER METRIC|",
        "Super Metric| Super Metric|",
        "Super Metric|super metric|",
        "Super Metric|Super Metric|Super Metric|",
    ])
    def test_doubled_prefix_without_a_token_is_a_hard_error(self, doubled):
        from vcfops_supermetrics.crossref import (
            SuperMetricCrossRefError,
            resolve_sm_formula,
        )

        formula = (
            'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
            'metric=' + doubled + 'sm_' + REF_UUID + ', depth=5})'
        )
        with pytest.raises(SuperMetricCrossRefError) as exc:
            resolve_sm_formula(formula, CONSUMER_NAME, {REF_NAME: REF_UUID})
        msg = str(exc.value)
        assert CONSUMER_NAME in msg, msg
        assert "doubled" in msg, msg

    def test_single_prefix_is_left_alone(self):
        """The guard must not fire on the correct, already-resolved wire form."""
        from vcfops_supermetrics.crossref import resolve_sm_formula

        formula = (
            'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
            'metric=' + RESOLVED_TOKEN + ', depth=5})'
        )
        assert resolve_sm_formula(formula, CONSUMER_NAME, {}) == formula

    def test_two_separate_prefixed_terms_are_left_alone(self):
        """Two resolved terms in one formula are not a doubled prefix."""
        from vcfops_supermetrics.crossref import resolve_sm_formula

        formula = (
            '${this, metric=' + RESOLVED_TOKEN + '} + '
            '${this, metric=Super Metric|sm_' + PLAIN_UUID + '}'
        )
        assert resolve_sm_formula(formula, CONSUMER_NAME, {}) == formula


# --- pak path still delegates to the shared resolver ------------------------

def test_sdk_builder_uses_the_shared_resolver():
    from vcfops_managementpacks import sdk_builder
    from vcfops_supermetrics import crossref

    assert sdk_builder._SM_CROSSREF_RE is crossref.SM_CROSSREF_RE, (
        "sdk_builder must not carry a second copy of the cross-reference regex"
    )
    out = sdk_builder._resolve_sm_formula(
        CONSUMER_FORMULA, CONSUMER_NAME, {REF_NAME: REF_UUID}
    )
    assert RESOLVED_TOKEN in out


class TestTokenCaseInsensitivity:
    """A mis-cased ``@supermetric:`` token resolves; it never ships verbatim.

    Round-3 review BLOCKING: the prefix was case-insensitive but the token was
    not, so ``@SuperMetric:"X"`` passed through ``resolve_sm_formula``
    unchanged and unflagged.  ``vcfops_packaging.deps._is_sm_ref`` lowercases
    before comparing, so the dependency audit classified it as an already-good
    SM reference and skipped it: audit green, build green, literal token in the
    pak, super metric evaluates to nothing on the live instance.
    """

    @pytest.mark.parametrize("token", [
        "@supermetric",   # canonical
        "@SuperMetric",   # camel
        "@SUPERMETRIC",   # upper
        "@SuperMETRIC",   # mixed
    ])
    def test_token_case_variants_all_resolve(self, token):
        from vcfops_supermetrics.crossref import (
            crossref_names,
            has_crossref,
            resolve_sm_formula,
        )

        formula = (
            'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
            'metric=' + token + ':"' + REF_NAME + '", depth=5})'
        )
        assert has_crossref(formula)
        assert crossref_names(formula) == [REF_NAME]

        out = resolve_sm_formula(formula, CONSUMER_NAME, {REF_NAME: REF_UUID})
        assert f"metric={RESOLVED_TOKEN}" in out, out
        assert out.count("Super Metric|") == 1, out
        assert "supermetric" not in out.lower(), out

    @pytest.mark.parametrize("token", ["@SuperMetric", "@SUPERMETRIC"])
    def test_mis_cased_unresolvable_name_still_hard_errors(self, token):
        from vcfops_supermetrics.crossref import (
            SuperMetricCrossRefError,
            resolve_sm_formula,
        )

        formula = (
            'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
            'metric=' + token + ':"[VCF Content Factory] Nowhere SM", depth=5})'
        )
        with pytest.raises(SuperMetricCrossRefError):
            resolve_sm_formula(formula, CONSUMER_NAME, {REF_NAME: REF_UUID})

    @pytest.mark.parametrize("token", ["@SuperMetric", "@SUPERMETRIC"])
    def test_mis_cased_token_survives_nothing_through_the_bundle_builder(
        self, token, tmp_path
    ):
        """End to end through the path that would have shipped the literal."""
        from vcfops_packaging.builder import _render_supermetrics_dict

        formula = (
            'avg(${adaptertype=VMWARE, objecttype=HostSystem, '
            'metric=' + token + ':"' + REF_NAME + '", depth=5})'
        )
        ref = _load(tmp_path, REF_UUID, REF_NAME, PLAIN_FORMULA)
        consumer = _load(tmp_path, CONSUMER_UUID, CONSUMER_NAME, formula)

        class _B:
            supermetrics = [ref, consumer]

        out = _render_supermetrics_dict(_B())
        emitted = out[CONSUMER_UUID]["formula"]
        assert "supermetric" not in emitted.lower(), emitted
        assert f"metric={RESOLVED_TOKEN}" in emitted, emitted
