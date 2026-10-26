"""``supermetric:"<name>"`` view columns bind to the SM of the view's own
content set (issues #270 and #266).

#270: the renderer resolved name-form columns only against
``content/supermetrics``, so a third-party project's (or an SDK-adapter
pak's) column either failed or silently bound to a same-named factory SM.
Resolution is now the view's own content set first, then the factory; an
ambiguous or unresolved name fails loudly.

#266: the post-import walker classified a name-form column as an OOTB metric,
so its SM was never checked or enabled on the Default Policy.  It is now an
SM reference, resolved through the same resolver the renderer used.

No network: every client is a fake, and every repo is a ``tmp_path`` tree.
"""
from __future__ import annotations

import argparse
import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from vcfcf_core.supermetrics.column_resolver import (
    SM_COLUMN_PREFIX_RE,
    SM_COLUMN_REF_RE,
    SmColumnResolutionError,
    SmColumnResolver,
)

SHARED = "Shared Capacity SM"
UUID_FACTORY = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
UUID_ACME = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
UUID_ACME_2 = "cccccccc-3333-4333-8333-cccccccccccc"
UUID_PAK_A = "dddddddd-4444-4444-8444-dddddddddddd"
UUID_PAK_B = "eeeeeeee-5555-4555-8555-eeeeeeeeeeee"
FACTORY_ONLY = "Factory Only SM"
UUID_FACTORY_ONLY = "ffffffff-6666-4666-8666-ffffffffffff"
RK = [{"resource_kind_key": "HostSystem", "adapter_kind_key": "VMWARE"}]


# --- tmp repo helpers ---------------------------------------------------------

def _write_sm(path: Path, sm_id, name: str) -> None:
    doc = {"name": name, "description": "d", "resource_kinds": RK,
           "formula": "${this, metric=cpu|usage_average}"}
    if sm_id:
        doc = {"id": sm_id, **doc}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _write_view(path: Path, name: str, sm_name: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'name: "{name}"\n'
        "description: probe\n"
        "subject: {adapter_kind: VMWARE, resource_kind: HostSystem}\n"
        "columns:\n"
        "  - {display_name: Plain, attribute: cpu|usage_average}\n"
        f"  - {{display_name: SM, attribute: 'supermetric:\"{sm_name}\"'}}\n",
        encoding="utf-8",
    )
    return path


def _load_view(path: Path):
    from vcfcf_dashboards.loader import load_view
    return load_view(path, enforce_framework_prefix=False)


def _repo(tmp_path: Path) -> Path:
    """content/supermetrics and third_party/acme both define SHARED; only
    the factory defines FACTORY_ONLY."""
    _write_sm(tmp_path / "content/supermetrics/shared.yaml", UUID_FACTORY, SHARED)
    _write_sm(tmp_path / "content/supermetrics/only.yaml", UUID_FACTORY_ONLY, FACTORY_ONLY)
    _write_sm(tmp_path / "third_party/acme/supermetrics/shared.yaml", UUID_ACME, SHARED)
    (tmp_path / "content/views").mkdir(parents=True, exist_ok=True)
    (tmp_path / "content/dashboards").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _views_xml(blob: bytes) -> str:
    outer = zipfile.ZipFile(io.BytesIO(blob))
    inner = zipfile.ZipFile(io.BytesIO(outer.read("views.zip")))
    return inner.read("content.xml").decode("utf-8")


def _key(sm_id: str) -> str:
    return f'name="attributeKey" value="Super Metric|sm_{sm_id}"'


def _package(monkeypatch, tmp_path, views):
    from vcfcf_dashboards import cli as dash_cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dash_cli, "_load", lambda args: (views, []))
    out = tmp_path / "out.zip"
    args = argparse.Namespace(output=str(out), allow_external_navigation_targets=False)
    rc = dash_cli.cmd_package(args)
    return rc, (out.read_bytes() if out.exists() else None)


# --- #270: renderer resolution -----------------------------------------------

def test_regexes_match_the_renderer():
    from vcfcf_core.dashboards import render

    assert SM_COLUMN_PREFIX_RE.pattern == render._SM_COLUMN_PREFIX_RE.pattern
    assert SM_COLUMN_REF_RE.pattern == render._SM_COLUMN_REF_RE.pattern


def test_third_party_column_resolves_to_its_own_sm(monkeypatch, tmp_path):
    """The acme view binds to acme's SM; the same-named factory SM in
    content/supermetrics does not hijack it."""
    _repo(tmp_path)
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", SHARED))
    assert view.provenance == "acme"
    rc, blob = _package(monkeypatch, tmp_path, [view])
    assert rc == 0
    xml = _views_xml(blob)
    assert _key(UUID_ACME) in xml
    assert UUID_FACTORY not in xml


def test_factory_column_still_resolves_to_the_factory_sm(monkeypatch, tmp_path):
    """A factory view never sees a third-party SM of the same name."""
    _repo(tmp_path)
    view = _load_view(_write_view(
        tmp_path / "content/views/v.yaml", "[VCF Content Factory] V", SHARED))
    rc, blob = _package(monkeypatch, tmp_path, [view])
    assert rc == 0
    xml = _views_xml(blob)
    assert _key(UUID_FACTORY) in xml
    assert UUID_ACME not in xml


def test_mixed_import_binds_each_view_to_its_own_set(monkeypatch, tmp_path):
    _repo(tmp_path)
    tp = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", SHARED))
    fac = _load_view(_write_view(
        tmp_path / "content/views/v.yaml", "[VCF Content Factory] V", SHARED))
    rc, blob = _package(monkeypatch, tmp_path, [tp, fac])
    assert rc == 0
    xml = _views_xml(blob)
    assert _key(UUID_ACME) in xml and _key(UUID_FACTORY) in xml


def test_third_party_column_falls_back_to_a_factory_sm(monkeypatch, tmp_path):
    _repo(tmp_path)
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", FACTORY_ONLY))
    rc, blob = _package(monkeypatch, tmp_path, [view])
    assert rc == 0
    assert _key(UUID_FACTORY_ONLY) in _views_xml(blob)


def test_unresolved_name_fails_and_writes_nothing(monkeypatch, tmp_path, capsys):
    _repo(tmp_path)
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", "Nowhere SM"))
    rc, blob = _package(monkeypatch, tmp_path, [view])
    err = capsys.readouterr().err
    assert rc == 1
    assert blob is None
    assert 'names super metric "Nowhere SM"' in err
    assert "'acme' then 'factory'" in err


def test_a_third_party_column_never_binds_to_another_projects_sm(monkeypatch, tmp_path, capsys):
    """Only the view's own set and the factory are in reach."""
    _repo(tmp_path)
    _write_sm(tmp_path / "third_party/other/supermetrics/x.yaml", UUID_ACME_2, "Other Only SM")
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", "Other Only SM"))
    rc, blob = _package(monkeypatch, tmp_path, [view])
    assert rc == 1
    assert blob is None
    assert 'names super metric "Other Only SM"' in capsys.readouterr().err


def test_duplicate_name_in_the_views_own_set_fails(monkeypatch, tmp_path, capsys):
    """Two acme SMs share the name.  The SM loader rejects the directory
    (duplicate display name), and a set that did not load stops the search:
    the column must not fall through to the same-named factory SM."""
    _repo(tmp_path)
    _write_sm(tmp_path / "third_party/acme/supermetrics/twin.yaml", UUID_ACME_2, SHARED)
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", SHARED))
    rc, blob = _package(monkeypatch, tmp_path, [view])
    err = capsys.readouterr().err
    assert rc == 1
    assert blob is None
    assert "content set 'acme' did not load" in err
    assert "duplicate super metric name" in err


def test_unloadable_own_set_does_not_fall_back_to_the_factory(monkeypatch, tmp_path, capsys):
    _repo(tmp_path)
    (tmp_path / "third_party/acme/supermetrics/broken.yaml").write_text(
        "name: [unclosed\n", encoding="utf-8")
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", SHARED))
    rc, blob = _package(monkeypatch, tmp_path, [view])
    assert rc == 1
    assert blob is None
    assert "content set 'acme' did not load" in capsys.readouterr().err


def test_renderer_raises_on_unresolved_and_ambiguous_resolver_answers():
    """The renderer itself never downgrades: None from the resolver is an
    unresolved reference, a resolver ValueError names the column."""
    from vcfcf_core.dashboards.loader import ViewColumn, ViewDef
    from vcfcf_core.dashboards.render import render_views_xml

    col = ViewColumn(attribute=f'supermetric:"{SHARED}"', display_name="SM")
    view = ViewDef(id=UUID_FACTORY, name="V", description="",
                   adapter_kind="VMWARE", resource_kind="HostSystem", columns=[col])
    with pytest.raises(ValueError, match="could not be resolved to a UUID"):
        render_views_xml([view], sm_resolver=lambda v, n: None)

    def _ambiguous(v, n):
        raise SmColumnResolutionError("ambiguous")

    with pytest.raises(ValueError, match=r'View "V" column 0: ambiguous'):
        render_views_xml([view], sm_resolver=_ambiguous)
    with pytest.raises(ValueError, match="not both"):
        render_views_xml([view], sm_map={SHARED: UUID_FACTORY}, sm_resolver=lambda v, n: None)


def test_idless_sm_named_by_a_column_fails_loudly(monkeypatch, tmp_path, capsys):
    """The corpus is loaded read-only, so an id-less SM gets an in-memory
    stand-in id; rendering that id would bind the column to nothing on the
    instance, so it is an error instead, and the YAML is not touched."""
    _repo(tmp_path)
    sm_file = tmp_path / "third_party/acme/supermetrics/idless.yaml"
    _write_sm(sm_file, None, "Idless SM")
    before = sm_file.read_bytes()
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", "Idless SM"))
    rc, blob = _package(monkeypatch, tmp_path, [view])
    assert rc == 1
    assert blob is None
    assert "has no id yet" in capsys.readouterr().err
    assert sm_file.read_bytes() == before


def test_views_handler_fails_an_unresolved_column_without_importing(monkeypatch, tmp_path):
    from vcfcf_dashboards import handler as dash_handler

    _repo(tmp_path)
    path = _write_view(tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", "Nowhere SM")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dash_handler, "load_view",
                        lambda p: _load_view(Path(p)))
    imported = []
    monkeypatch.setattr(dash_handler, "import_content_zip",
                        lambda s, b: imported.append(b) or {"state": "FINISHED"})
    result = dash_handler.ViewsHandler().sync([str(path)], session=object())
    assert [i.status for i in result.items] == ["failed"]
    assert "Nowhere SM" in result.items[0].message
    assert imported == []


# --- SDK-adapter paks ---------------------------------------------------------

def test_sdk_adapter_paks_are_separate_content_sets(monkeypatch, tmp_path):
    """Two paks under content/sdk-adapters ship an SM of the same name (both
    read as "factory" provenance); each pak's view binds to its own."""
    from vcfcf_dashboards import sm_columns

    _repo(tmp_path)
    _write_sm(tmp_path / "content/sdk-adapters/pak-a/supermetrics/s.yaml", UUID_PAK_A, SHARED)
    _write_sm(tmp_path / "content/sdk-adapters/pak-b/supermetrics/s.yaml", UUID_PAK_B, SHARED)
    va = _load_view(_write_view(
        tmp_path / "content/sdk-adapters/pak-a/views/v.yaml", "A View", SHARED))
    vb = _load_view(_write_view(
        tmp_path / "content/sdk-adapters/pak-b/views/v.yaml", "B View", SHARED))
    assert sm_columns.content_set_of(va) == "sdk-adapter:pak-a"
    monkeypatch.chdir(tmp_path)
    resolver = sm_columns.load_sm_corpus().resolver()
    assert resolver.column_errors([va, vb]) == []
    assert resolver.uuid_for(va, SHARED) == UUID_PAK_A
    assert resolver.uuid_for(vb, SHARED) == UUID_PAK_B


def test_sdk_pak_views_never_fall_back_to_content_supermetrics(monkeypatch, tmp_path):
    """The pak builder's scope is the pak's bundled SMs, empty when it
    bundles none; a column naming a factory SM is a build error, not a
    silent bind to an SM the pak does not ship."""
    from vcfcf_managementpacks import sdk_builder

    _repo(tmp_path)
    view = _load_view(_write_view(
        tmp_path / "content/sdk-adapters/pak-a/views/v.yaml", "A View", SHARED))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="not in the bundle scope"):
        sdk_builder._build_views_zip_bytes([view])
    with pytest.raises(ValueError, match="not in the bundle scope"):
        sdk_builder._build_views_zip_bytes([view], sm_scope=[])
    pak_sm = tmp_path / "content/sdk-adapters/pak-a/supermetrics/s.yaml"
    _write_sm(pak_sm, UUID_PAK_A, SHARED)
    blob = sdk_builder._build_views_zip_bytes([view], sm_scope=[pak_sm])
    xml = zipfile.ZipFile(io.BytesIO(blob)).read("content.xml").decode()
    assert _key(UUID_PAK_A) in xml


def test_scoped_sm_id_map_rejects_a_duplicate_name(tmp_path):
    from vcfcf_supermetrics.loader import sm_id_map

    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    _write_sm(a, UUID_ACME, SHARED)
    _write_sm(b, UUID_ACME_2, SHARED)
    with pytest.raises(ValueError, match="ambiguous"):
        sm_id_map([a, b], "probe")
    # The same SM listed twice is one SM, not an ambiguity.
    assert sm_id_map([a, a], "probe") == {SHARED: UUID_ACME}


# --- core resolver ------------------------------------------------------------

def _ns_sm(sm_id, name, prov):
    return SimpleNamespace(id=sm_id, name=name, provenance=prov)


def test_resolver_rules():
    sms = [_ns_sm(UUID_FACTORY, SHARED, "factory"), _ns_sm(UUID_ACME, SHARED, "acme"),
           _ns_sm(UUID_FACTORY_ONLY, FACTORY_ONLY, "factory"),
           _ns_sm(UUID_ACME, SHARED, "acme")]  # same SM twice: not ambiguous
    r = SmColumnResolver(sms)
    acme = SimpleNamespace(name="v", provenance="acme")
    fac = SimpleNamespace(name="v", provenance="factory")
    assert r.uuid_for(acme, SHARED) == UUID_ACME
    assert r.uuid_for(fac, SHARED) == UUID_FACTORY
    assert r.uuid_for(acme, FACTORY_ONLY) == UUID_FACTORY_ONLY
    assert r.uuid_for(acme, "nope") is None
    with pytest.raises(SmColumnResolutionError, match="ambiguous"):
        SmColumnResolver(sms + [_ns_sm(UUID_ACME_2, SHARED, "acme")]).resolve(acme, SHARED)
    assert SmColumnResolver(sms, fallback_set=None).resolve(acme, FACTORY_ONLY) is None
    broken = SmColumnResolver(sms, broken_sets={"acme": "bad yaml"})
    with pytest.raises(SmColumnResolutionError, match="did not load"):
        broken.resolve(acme, FACTORY_ONLY)
    assert broken.uuid_for(fac, SHARED) == UUID_FACTORY  # factory views unaffected


# --- #266: the post-import walker ---------------------------------------------

class _WalkClient:
    """What walk_and_check touches with skip_metric_check=True, plus the
    enable path."""

    def __init__(self, enabled=(), remote_by_name=None):
        self.enabled = {u.lower() for u in enabled}
        self.remote_by_name = dict(remote_by_name or {})
        self.lookups = []
        self.enabled_calls = []
        self.requests = []

    def export_default_policy_xml(self):
        return "<policy/>"

    def verify_supermetrics_enabled(self, policy_xml, uuids):
        return {u: (u.lower() in self.enabled) for u in uuids}

    def find_by_name(self, name):
        self.lookups.append(name)
        uid = self.remote_by_name.get(name)
        return {"id": uid, "name": name} if uid else None

    def get_supermetric(self, uid):
        return {"id": uid, "name": "?", "resourceKinds": [
            {"adapterKindKey": "VMWARE", "resourceKindKey": "HostSystem"}]}

    def enable_supermetric_on_default_policy(self, uid, rks):
        self.enabled_calls.append((uid, rks))
        self.enabled.add(uid.lower())

    def _request(self, method, path, **kw):  # describe: must not be asked about SM columns
        self.requests.append(path)
        return SimpleNamespace(status_code=200, json=lambda: {"resourceTypeAttributes": []})


def _walk(client, views, resolver=None, skip_metric_check=True):
    from vcfcf_common.dep_walker import walk_and_check
    return walk_and_check(
        client=client, supermetrics=[], views=views, dashboards=[],
        customgroups=[], skip_metric_check=skip_metric_check,
        sm_column_resolver=resolver,
    )


def _ns_view(sm_attr, prov="acme"):
    col = SimpleNamespace(attribute=sm_attr, display_name="SM col")
    return SimpleNamespace(name="[Acme] View", columns=[col], adapter_kind="VMWARE",
                           resource_kind="HostSystem", provenance=prov)


@pytest.mark.parametrize("attr", [
    f'supermetric:"{SHARED}"', f'@supermetric:"{SHARED}"', f'SuperMetric:"{SHARED}"',
])
def test_extract_refs_treats_a_name_form_column_as_an_sm(attr):
    from vcfcf_common.dep_walker import extract_refs_from_views

    r = SmColumnResolver([_ns_sm(UUID_FACTORY, SHARED, "factory"),
                          _ns_sm(UUID_ACME, SHARED, "acme")])
    sm_refs, metric_refs = extract_refs_from_views([_ns_view(attr)], column_resolver=r)
    assert metric_refs == []
    assert [(x.sm_id, x.name, x.token) for x in sm_refs] == [(UUID_ACME, SHARED, "supermetric")]


def test_walker_enables_the_name_form_columns_own_sm(monkeypatch):
    """Not enabled on the target: the walker enables the acme SM (the one
    the renderer bound), never the same-named factory SM, and sends no
    describe lookup for the column."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    r = SmColumnResolver([_ns_sm(UUID_FACTORY, SHARED, "factory"),
                          _ns_sm(UUID_ACME, SHARED, "acme")])
    client = _WalkClient()
    res = _walk(client, [_ns_view(f'supermetric:"{SHARED}"')], r, skip_metric_check=False)
    assert res.ok, res.messages
    assert [uid for uid, _ in client.enabled_calls] == [UUID_ACME]
    assert res.sm_enabled == [SHARED]
    assert client.lookups == []
    assert client.requests == []  # no describe for an SM column


def test_walker_checks_an_already_enabled_name_form_sm():
    r = SmColumnResolver([_ns_sm(UUID_ACME, SHARED, "acme")])
    client = _WalkClient(enabled=[UUID_ACME])
    res = _walk(client, [_ns_view(f'supermetric:"{SHARED}"')], r)
    assert res.ok, res.messages
    assert res.sm_already == [SHARED]
    assert client.enabled_calls == []


def test_walker_looks_up_a_name_the_repo_does_not_know(monkeypatch):
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    client = _WalkClient(remote_by_name={SHARED: UUID_FACTORY})
    res = _walk(client, [_ns_view(f'supermetric:"{SHARED}"')], SmColumnResolver([]))
    assert res.ok, res.messages
    assert client.lookups == [SHARED]
    assert [uid for uid, _ in client.enabled_calls] == [UUID_FACTORY]


def test_walker_reports_a_name_form_sm_found_nowhere():
    client = _WalkClient()
    res = _walk(client, [_ns_view('supermetric:"Nowhere SM"')], SmColumnResolver([]))
    assert res.ok is False
    errors = [m for lvl, m in res.messages if lvl == "ERROR"]
    assert len(errors) == 1, res.messages
    assert 'supermetric:"Nowhere SM"' in errors[0]
    assert "view column" in errors[0]


def test_dashboards_sync_walker_gets_the_renderers_resolver(monkeypatch, tmp_path):
    """End to end through cmd_sync: the post-import walker enables the
    third-party SM the renderer bound the column to."""
    import time
    from vcfcf_dashboards import cli as dash_cli

    monkeypatch.setattr(time, "sleep", lambda s: None)
    _repo(tmp_path)
    view = _load_view(_write_view(
        tmp_path / "third_party/acme/views/v.yaml", "[Acme] View", SHARED))
    monkeypatch.chdir(tmp_path)
    client = _WalkClient()
    captured = {}

    def _build(views, dashboards, **kw):
        captured["xml_key"] = kw["sm_resolver"](views[0], SHARED)
        return b"zip"

    monkeypatch.setattr(dash_cli, "_load", lambda args: ([view], []))
    monkeypatch.setattr(dash_cli, "_resolve_import_navigations", lambda args, d: (0, None))
    monkeypatch.setattr(dash_cli.VCFOpsClient, "from_env",
                        classmethod(lambda cls, **kw: client))
    monkeypatch.setattr(dash_cli, "get_current_user", lambda c: {"id": "u"})
    monkeypatch.setattr(dash_cli, "discover_marker_filename", lambda c: "m")
    monkeypatch.setattr(dash_cli, "build_import_zip", _build)
    monkeypatch.setattr(dash_cli, "import_content_zip",
                        lambda c, blob: {"state": "FINISHED", "operationSummaries": []})
    args = argparse.Namespace(profile=None, skip_materialization_check=True,
                              skip_metric_check=True)
    assert dash_cli.cmd_sync(args) == 0
    assert captured["xml_key"] == UUID_ACME
    assert [uid for uid, _ in client.enabled_calls] == [UUID_ACME]
