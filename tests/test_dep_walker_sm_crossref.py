"""Issue #144: collect_deps walks SM-to-SM ``@supermetric:"<name>"`` references.

Before this fix the walker only saw view-column ``sm_<uuid>`` references, so a
super metric that depended on another super metric was invisible to it.  The
discrete builder papered over that with its own ``_expand_sm_crossrefs``; that
helper is now a thin adapter over ``dep_walker.expand_sm_crossrefs`` so there
is one walk.

Cases, at the walker level and through the discrete-builder adapter:
  * an SM referencing another SM by name
  * a chain of three (A -> B -> C)
  * a cycle (A -> B -> A) must terminate
  * a reference to a missing SM: recorded in DepGraph.errors (the walk keeps
    going), and fatal on the discrete-build path, matching the hard-fail
    resolver semantics from PR #141 (``resolve_sm_formula`` raises on an
    unresolvable name)
  * token case-insensitivity vs name case-sensitivity (issue #148)

Pure Python, no network, no content YAML touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfops_common.dep_walker import collect_deps, expand_sm_crossrefs  # noqa: E402
from vcfops_dashboards.loader import Dashboard, ViewColumn, ViewDef, Widget  # noqa: E402
from vcfops_supermetrics.loader import SuperMetricDef  # noqa: E402

UUID_A = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
UUID_B = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
UUID_C = "cccccccc-3333-4333-8333-cccccccccccc"

NAME_A = "[VCF Content Factory] SM A"
NAME_B = "[VCF Content Factory] SM B"
NAME_C = "[VCF Content Factory] SM C"
NAME_MISSING = "[VCF Content Factory] Nowhere SM"

RK = [{"resourceKindKey": "HostSystem", "adapterKindKey": "VMWARE"}]


def _sm(sm_id: str, name: str, refs=(), token: str = "@supermetric") -> SuperMetricDef:
    if refs:
        terms = " + ".join(
            f'${{this, attribute={token}:"{r}"}}' for r in refs
        )
    else:
        terms = "${this, metric=cpu|usage_average}"
    return SuperMetricDef(name=name, formula=terms, id=sm_id, resource_kinds=RK)


def _dashboard_over(sm_uuid: str):
    """A dashboard whose single view has one column bound to sm_<uuid>."""
    view = ViewDef(
        id="00000000-0000-0000-0000-000000000001",
        name="[VCF Content Factory] Crossref View",
        description="",
        adapter_kind="VMWARE",
        resource_kind="HostSystem",
        columns=[ViewColumn(attribute=f"Super Metric|sm_{sm_uuid}", display_name="A")],
    )
    widget = Widget(
        local_id="w1",
        type="View",
        title="t",
        coords={"x": 1, "y": 1, "w": 6, "h": 6},
        view_name=view.name,
        dashboard_name="[VCF Content Factory] Crossref Dashboard",
    )
    dash = Dashboard(
        id="00000000-0000-0000-0000-000000000002",
        name="[VCF Content Factory] Crossref Dashboard",
        description="",
        widgets=[widget],
        interactions=[],
    )
    return dash, view


def _names(sms):
    return [s.name for s in sms]


# --- collect_deps (dashboard entry point) -----------------------------------

class TestCollectDepsWalksSmCrossrefs:
    def test_single_reference(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B)
        dash, view = _dashboard_over(UUID_A)
        g = collect_deps([dash], [view], [a, b], [])
        assert not g.errors, g.errors
        assert _names(g.supermetrics) == [NAME_A, NAME_B]

    def test_chain_of_three(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B, refs=[NAME_C])
        c = _sm(UUID_C, NAME_C)
        dash, view = _dashboard_over(UUID_A)
        g = collect_deps([dash], [view], [a, b, c], [])
        assert not g.errors, g.errors
        assert _names(g.supermetrics) == [NAME_A, NAME_B, NAME_C]

    def test_cycle_terminates(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B, refs=[NAME_A])
        dash, view = _dashboard_over(UUID_A)
        g = collect_deps([dash], [view], [a, b], [])
        assert not g.errors, g.errors
        assert sorted(_names(g.supermetrics)) == sorted([NAME_A, NAME_B])

    def test_missing_referent_is_an_error_and_walk_continues(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_MISSING, NAME_B])
        b = _sm(UUID_B, NAME_B)
        dash, view = _dashboard_over(UUID_A)
        g = collect_deps([dash], [view], [a, b], [])
        assert len(g.errors) == 1, g.errors
        assert NAME_A in g.errors[0] and NAME_MISSING in g.errors[0]
        # The good referent is still collected: one pass reports everything.
        assert _names(g.supermetrics) == [NAME_A, NAME_B]

    def test_referent_without_id_is_an_error(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm("", NAME_B)
        dash, view = _dashboard_over(UUID_A)
        g = collect_deps([dash], [view], [a, b], [])
        assert len(g.errors) == 1, g.errors
        assert "carries no id" in g.errors[0] and NAME_B in g.errors[0]
        assert _names(g.supermetrics) == [NAME_A]

    def test_token_case_insensitive_name_case_sensitive(self):
        """Issue #148 semantics via SM_CROSSREF_RE: @SuperMetric resolves,
        a mis-cased NAME does not."""
        a = _sm(UUID_A, NAME_A, refs=[NAME_B], token="@SuperMetric")
        b = _sm(UUID_B, NAME_B)
        dash, view = _dashboard_over(UUID_A)
        g = collect_deps([dash], [view], [a, b], [])
        assert not g.errors, g.errors
        assert _names(g.supermetrics) == [NAME_A, NAME_B]

        a2 = _sm(UUID_A, NAME_A, refs=[NAME_B.lower()])
        g2 = collect_deps([dash], [view], [a2, b], [])
        assert len(g2.errors) == 1 and NAME_B.lower() in g2.errors[0]
        assert _names(g2.supermetrics) == [NAME_A]

    def test_no_token_is_a_noop(self):
        a = _sm(UUID_A, NAME_A)
        b = _sm(UUID_B, NAME_B)
        dash, view = _dashboard_over(UUID_A)
        g = collect_deps([dash], [view], [a, b], [])
        assert not g.errors
        assert _names(g.supermetrics) == [NAME_A]


# --- expand_sm_crossrefs (SM / view / report entry points) -------------------

class TestExpandSmCrossrefs:
    def test_chain_and_order(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B, refs=[NAME_C])
        c = _sm(UUID_C, NAME_C)
        out, errs = expand_sm_crossrefs([a], [c, b, a])
        assert not errs
        assert _names(out) == [NAME_A, NAME_B, NAME_C]

    def test_cycle_terminates(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B, refs=[NAME_A])
        out, errs = expand_sm_crossrefs([a], [a, b])
        assert not errs
        assert _names(out) == [NAME_A, NAME_B]

    def test_missing_referent_reported_not_raised(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_MISSING])
        out, errs = expand_sm_crossrefs([a], [a])
        assert _names(out) == [NAME_A]
        assert len(errs) == 1 and NAME_MISSING in errs[0] and NAME_A in errs[0]


# --- discrete builder: one code path, hard failure on a missing referent -----

class TestDiscreteBuilderUsesWalker:
    def test_chain_pulled_in(self):
        from vcfops_packaging.discrete_builder import _expand_sm_crossrefs

        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B, refs=[NAME_C])
        c = _sm(UUID_C, NAME_C)
        assert _names(_expand_sm_crossrefs([a], [a, b, c])) == [NAME_A, NAME_B, NAME_C]

    def test_cycle_terminates(self):
        from vcfops_packaging.discrete_builder import _expand_sm_crossrefs

        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B, refs=[NAME_A])
        assert _names(_expand_sm_crossrefs([b], [a, b])) == [NAME_B, NAME_A]

    def test_missing_referent_is_fatal(self):
        """Matches the PR #141 resolver: an unresolvable name never ships."""
        from vcfops_packaging.discrete_builder import (
            DiscreteBuilderError,
            _expand_sm_crossrefs,
        )

        a = _sm(UUID_A, NAME_A, refs=[NAME_MISSING])
        with pytest.raises(DiscreteBuilderError) as exc:
            _expand_sm_crossrefs([a], [a])
        assert NAME_A in str(exc.value) and NAME_MISSING in str(exc.value)
