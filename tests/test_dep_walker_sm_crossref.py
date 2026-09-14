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


# --- scope: an out-of-scope referent names its referrer, once ----------------

class TestScopedReferent:
    def _scoped(self, referrers, referent, cross_links=None):
        from vcfops_common.dep_walker import CollectDepsCrossLinks

        dash, view = _dashboard_over(UUID_A)
        dash.provenance = "proj"
        view.provenance = "proj"
        cl = CollectDepsCrossLinks(supermetrics=cross_links or []) if cross_links is not None else None
        return collect_deps(
            [dash], [view], [*referrers, referent], [],
            project_scope="proj", cross_links=cl,
        )

    def test_non_cross_linked_factory_referent_names_referrer_once(self):
        # A names B twice in one formula: one line, and it says A.
        a = _sm(UUID_A, NAME_A, refs=[NAME_B, NAME_B])
        a.provenance = "proj"
        b = _sm(UUID_B, NAME_B)
        b.provenance = "factory"
        g = self._scoped([a], b, cross_links=[])
        assert len(g.errors) == 1, g.errors
        assert g.errors[0].startswith(f"super metric '{NAME_A}': scope violation"), g.errors[0]
        assert NAME_B in g.errors[0]
        assert _names(g.supermetrics) == [NAME_A]

    def test_two_referrers_each_get_their_own_line(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        a.provenance = "proj"
        c = _sm(UUID_C, NAME_C, refs=[NAME_B])
        c.provenance = "proj"
        b = _sm(UUID_B, NAME_B)
        b.provenance = "factory"
        # C reaches the walk via A's formula.
        a.formula = a.formula + f' + ${{this, attribute=@supermetric:"{NAME_C}"}}'
        g = self._scoped([a, c], b, cross_links=[])
        assert len(g.errors) == 2, g.errors
        assert any(e.startswith(f"super metric '{NAME_A}':") for e in g.errors)
        assert any(e.startswith(f"super metric '{NAME_C}':") for e in g.errors)

    def test_cross_linked_factory_referent_is_accepted(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        a.provenance = "proj"
        b = _sm(UUID_B, NAME_B)
        b.provenance = "factory"
        g = self._scoped([a], b, cross_links=[NAME_B])
        assert not g.errors, g.errors
        assert _names(g.supermetrics) == [NAME_A, NAME_B]


# --- live-sync advisory: extract_refs_from_supermetrics + walk_and_check ----

class TestLiveSyncAdvisory:
    def test_extract_emits_name_keyed_ref_resolved_from_map(self):
        from vcfops_common.dep_walker import extract_refs_from_supermetrics

        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        sm_refs, _ = extract_refs_from_supermetrics([a], sm_name_map={NAME_B: UUID_B})
        assert [(r.sm_id, r.name) for r in sm_refs] == [(UUID_B, NAME_B)]
        assert NAME_A in sm_refs[0].source

    def test_extract_resolves_from_the_batch_itself(self):
        from vcfops_common.dep_walker import extract_refs_from_supermetrics

        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B)
        sm_refs, _ = extract_refs_from_supermetrics([a, b])
        assert [(r.sm_id, r.name) for r in sm_refs] == [(UUID_B, NAME_B)]

    def test_extract_unknown_name_yields_empty_id(self):
        from vcfops_common.dep_walker import extract_refs_from_supermetrics

        a = _sm(UUID_A, NAME_A, refs=[NAME_MISSING])
        sm_refs, _ = extract_refs_from_supermetrics([a])
        assert [(r.sm_id, r.name) for r in sm_refs] == [("", NAME_MISSING)]

    class _FakeClient:
        """Only what walk_and_check touches with skip_metric_check=True."""

        def __init__(self, remote_by_name=None, enabled=()):
            self.remote_by_name = dict(remote_by_name or {})
            self.enabled = {u.lower() for u in enabled}
            self.lookups = []

        def export_default_policy_xml(self):
            return "<policy/>"

        def verify_supermetrics_enabled(self, policy_xml, uuids):
            return {u: (u.lower() in self.enabled) for u in uuids}

        def find_by_name(self, name):
            self.lookups.append(name)
            uid = self.remote_by_name.get(name)
            return {"id": uid, "name": name} if uid else None

    def _walk(self, client, sms):
        from vcfops_common.dep_walker import walk_and_check

        return walk_and_check(
            client=client, supermetrics=sms, views=[], dashboards=[],
            customgroups=[], skip_metric_check=True,
            sm_name_map={s.name: s.id for s in sms},
        )

    def test_missing_referent_is_named_up_front(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_MISSING])
        client = self._FakeClient()
        res = self._walk(client, [a])
        assert res.ok is False
        errors = [m for lvl, m in res.messages if lvl == "ERROR"]
        assert len(errors) == 1, res.messages
        assert NAME_A in errors[0] and NAME_MISSING in errors[0]
        assert client.lookups == [NAME_MISSING]

    def test_missing_referent_named_twice_reports_once(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_MISSING, NAME_MISSING])
        client = self._FakeClient()
        res = self._walk(client, [a])
        errors = [m for lvl, m in res.messages if lvl == "ERROR"]
        assert len(errors) == 1, res.messages
        assert client.lookups == [NAME_MISSING]  # cached, one GET

    def test_failed_lookup_is_not_also_reported_as_absent(self):
        class _Boom(self._FakeClient):
            def find_by_name(self, name):
                self.lookups.append(name)
                raise RuntimeError("ambiguous: 2 super metrics named that")

        a = _sm(UUID_A, NAME_A, refs=[NAME_MISSING])
        client = _Boom()
        res = self._walk(client, [a])
        assert res.ok is False
        errors = [m for lvl, m in res.messages if lvl == "ERROR"]
        assert len(errors) == 1, res.messages
        assert "lookup" in errors[0] and "failed" in errors[0] and "ambiguous" in errors[0]
        assert not any("is in this sync batch" in m for _, m in res.messages), res.messages

    def test_referent_in_batch_needs_no_lookup(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        b = _sm(UUID_B, NAME_B)
        client = self._FakeClient()
        res = self._walk(client, [a, b])
        assert res.ok is True, res.messages
        assert client.lookups == []
        assert any("in sync batch" in m and NAME_B in m for _, m in res.messages), res.messages

    def test_referent_on_target_is_resolved_and_policy_checked(self):
        a = _sm(UUID_A, NAME_A, refs=[NAME_B])
        client = self._FakeClient(remote_by_name={NAME_B: UUID_B}, enabled=[UUID_B])
        res = self._walk(client, [a])
        assert res.ok is True, res.messages
        assert client.lookups == [NAME_B]
        assert NAME_B in res.sm_already


# --- discrete build, dashboard path, end to end ------------------------------

@pytest.mark.slow
def test_build_discrete_dashboard_carries_sm_referents(tmp_path):
    """collect_deps is now the only expansion on the dashboard path; prove the
    referent still lands in the zip."""
    import json
    import zipfile

    import yaml

    from vcfops_packaging.discrete_builder import build_discrete

    proj = tmp_path / "third_party" / "crossref-proj"
    sm_dir, view_dir, dash_dir = proj / "supermetrics", proj / "views", proj / "dashboards"
    for d in (sm_dir, view_dir, dash_dir):
        d.mkdir(parents=True)
    rks = [{"resource_kind_key": "HostSystem", "adapter_kind_key": "VMWARE"}]
    (sm_dir / "a.yaml").write_text(yaml.dump({
        "id": UUID_A, "name": NAME_A, "resource_kinds": rks,
        "formula": f'${{this, attribute=@supermetric:"{NAME_B}"}}',
    }))
    (sm_dir / "b.yaml").write_text(yaml.dump({
        "id": UUID_B, "name": NAME_B, "resource_kinds": rks,
        "formula": "${this, metric=cpu|usage_average}",
    }))
    view_name = "[VCF Content Factory] Crossref E2E View"
    (view_dir / "v.yaml").write_text(yaml.dump({
        "name": view_name,
        "subject": {"adapter_kind": "VMWARE", "resource_kind": "HostSystem"},
        "columns": [{"attribute": f"Super Metric|sm_{UUID_A}", "display_name": "A"}],
    }))
    dash_name = "[VCF Content Factory] Crossref E2E Dashboard"
    (dash_dir / "d.yaml").write_text(yaml.dump({
        "name": dash_name,
        "widgets": [{
            "id": "11111111-1111-4111-8111-111111111111",
            "type": "View", "title": "w",
            "coords": {"x": 1, "y": 1, "w": 6, "h": 6},
            "view": view_name,
        }],
    }))

    zip_path = build_discrete(
        content_type="dashboard", item_name=dash_name,
        output_dir=tmp_path / "out", extra_search_dirs=[proj], skip_audit=True,
    )
    with zipfile.ZipFile(zip_path) as z:
        member = [m for m in z.namelist() if m.endswith("content/supermetrics.json")][0]
        sms = json.loads(z.read(member).decode("utf-8"))
    names = sorted(v["name"] for v in sms.values())
    assert names == sorted([NAME_A, NAME_B]), names
    assert f"Super Metric|sm_{UUID_B}" in sms[UUID_A]["formula"]
