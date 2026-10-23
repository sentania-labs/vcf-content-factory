"""SM sync reports a missing @supermetric referent before importing (#154).

cmd_sync used to run import_supermetrics_bundle first, which hard-errors on
an unresolvable name, so the walker's #144 missing-referent advisory (which
ran after the import) was unreachable on that path. The read-only referent
check now runs first; the policy-writing walker phases still run after the
import.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vcfcf_common import dep_walker  # noqa: E402
from vcfcf_supermetrics import cli as sm_cli  # noqa: E402
from vcfcf_supermetrics.loader import SuperMetricDef  # noqa: E402

RK = [{"resourceKindKey": "HostSystem", "adapterKindKey": "VMWARE"}]
UUID_A = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa"
UUID_B = "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb"
UUID_REMOTE = "eeeeeeee-5555-4555-8555-eeeeeeeeeeee"
NAME_A = "[VCF Content Factory] SM A"
NAME_B = "[VCF Content Factory] SM B"
NAME_MISSING = "[VCF Content Factory] Nowhere SM"
NAME_REMOTE = "[VCF Content Factory] Already Installed SM"


def _sm(sm_id, name, ref=None):
    formula = (f'${{this, attribute=@supermetric:"{ref}"}}' if ref
               else "${this, metric=cpu|usage_average}")
    return SuperMetricDef(name=name, formula=formula, id=sm_id, resource_kinds=RK)


class _FakeClient:
    def __init__(self, remote=None):
        self.remote = remote or {}
        self.events = []

    def find_by_name(self, name):
        self.events.append(("find_by_name", name))
        uid = self.remote.get(name)
        return {"id": uid, "name": name} if uid else None

    def import_supermetrics_bundle(self, bundle):
        self.events.append(("import", len(bundle)))
        return {"operationSummaries": [{"imported": len(bundle)}]}


def _run(monkeypatch, defs, client, capsys):
    monkeypatch.setattr(sm_cli, "_collect", lambda paths: defs)
    monkeypatch.setattr(sm_cli.VCFOpsClient, "from_env",
                        classmethod(lambda cls, **kw: client))
    walked = []
    monkeypatch.setattr(sm_cli, "_run_dep_walker_for_sms",
                        lambda *a, **k: walked.append(True) or 0)
    rc = sm_cli.cmd_sync(argparse.Namespace(paths=[], profile=None))
    return rc, walked, capsys.readouterr()


def test_missing_referent_is_reported_before_import(monkeypatch, capsys):
    client = _FakeClient()
    defs = [_sm(UUID_A, NAME_A, ref=NAME_MISSING)]
    rc, walked, out = _run(monkeypatch, defs, client, capsys)
    assert rc == 1
    assert not any(e[0] == "import" for e in client.events)
    assert walked == []
    assert f'@supermetric:"{NAME_MISSING}"' in out.err
    assert "DEP-ERROR" in out.err
    assert "nothing was imported" in out.err


def test_in_batch_referent_needs_no_lookup_and_imports(monkeypatch, capsys):
    client = _FakeClient()
    defs = [_sm(UUID_A, NAME_A, ref=NAME_B), _sm(UUID_B, NAME_B)]
    rc, walked, _out = _run(monkeypatch, defs, client, capsys)
    assert rc == 0
    assert ("import", 2) in client.events
    assert not any(e[0] == "find_by_name" for e in client.events)
    assert walked == [True]


def test_referent_on_target_passes_then_imports(monkeypatch, capsys):
    client = _FakeClient(remote={NAME_REMOTE: UUID_REMOTE})
    defs = [_sm(UUID_A, NAME_A, ref=NAME_REMOTE)]
    rc, walked, _out = _run(monkeypatch, defs, client, capsys)
    assert rc == 0
    kinds = [e[0] for e in client.events]
    assert kinds.index("find_by_name") < kinds.index("import")
    assert walked == [True]


def test_duplicate_names_in_batch_stop_before_import(monkeypatch, capsys):
    client = _FakeClient()
    defs = [_sm(UUID_A, NAME_A), _sm(UUID_B, NAME_A)]
    rc, walked, out = _run(monkeypatch, defs, client, capsys)
    assert rc == 1
    assert client.events == []
    assert "INVALID" in out.err and NAME_A in out.err


def test_check_sm_referents_is_read_only():
    """Only find_by_name is called: no policy export, no enable."""

    class _Strict:
        def __init__(self):
            self.calls = []

        def find_by_name(self, name):
            self.calls.append(name)
            return None

        def __getattr__(self, attr):
            raise AssertionError(f"check_sm_referents called {attr}")

    c = _Strict()
    res = dep_walker.check_sm_referents(
        c, [_sm(UUID_A, NAME_A, ref=NAME_MISSING)],
        sm_name_map={NAME_A: UUID_A},
    )
    assert not res.ok
    assert c.calls == [NAME_MISSING]
