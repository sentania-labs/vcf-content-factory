"""M1 compatibility shims: the old ``vcfops_*`` names still work for one release.

The SDK adapter repos' READMEs document ``python3 -m vcfops_packaging ...``
and ``python3 -m vcfops_managementpacks ...`` (their CI runs the published
sdk_buildkit instead, so it is unaffected). The shim packages under
``src/vcfops_<name>/`` must forward to ``vcfcf_<name>``, warn exactly once
on import, and print one deprecation line on the ``-m`` path. See
``vcfcf_common/compat_shim.py``; retirement tracked in issue #159.
"""
from __future__ import annotations

import os
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

OLD_PACKAGES = [
    "vcfops_alerts", "vcfops_common", "vcfops_customgroups",
    "vcfops_dashboards", "vcfops_extractor", "vcfops_managementpacks",
    "vcfops_packaging", "vcfops_reports", "vcfops_supermetrics",
    "vcfops_symptoms",
]


def _run_old_module(module: str, *args: str, default_filters: bool = False) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    if default_filters:
        env.pop("PYTHONWARNINGS", None)
    else:
        # DeprecationWarning is silenced by default outside __main__; surface it
        # so the test can count it.
        env["PYTHONWARNINGS"] = "default::DeprecationWarning"
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(REPO_ROOT), env=env,
        capture_output=True, text=True, timeout=120,
    )


@pytest.mark.parametrize("old_module", ["vcfops_packaging", "vcfops_managementpacks"])
def test_old_module_help_exits_zero_and_warns_once(old_module):
    new_module = old_module.replace("vcfops_", "vcfcf_", 1)
    result = _run_old_module(old_module, "--help")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "help text should still print through the shim"
    assert result.stderr.count("DeprecationWarning") == 1, result.stderr
    assert new_module in result.stderr, result.stderr


@pytest.mark.parametrize("old_pkg", OLD_PACKAGES)
def test_shim_package_exists_for_every_old_name(old_pkg):
    assert (SRC / old_pkg / "__init__.py").is_file()
    assert (SRC / old_pkg / "__main__.py").is_file()
    assert (SRC / old_pkg.replace("vcfops_", "vcfcf_", 1) / "__init__.py").is_file()


def test_old_submodule_import_is_same_object_as_new():
    """``vcfops_common.client`` must be the very same module as ``vcfcf_common.client``."""
    for name in ("vcfops_common", "vcfops_common.client"):
        sys.modules.pop(name, None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        import vcfops_common.client as old_client  # noqa: PLC0415
        import vcfcf_common.client as new_client  # noqa: PLC0415
    assert old_client is new_client
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) == 1
    assert "vcfcf_common" in str(deprecations[0].message)


@pytest.mark.parametrize("old_module", ["vcfops_packaging", "vcfops_managementpacks"])
def test_old_module_prints_deprecation_line_under_default_filters(old_module):
    """Operators running the old command with no -W flag still get one notice."""
    new_module = old_module.replace("vcfops_", "vcfcf_", 1)
    result = _run_old_module(old_module, "--help", default_filters=True)
    assert result.returncode == 0, result.stderr
    expected = f"{old_module} is deprecated, use {new_module}; removed next release"
    assert result.stderr.count(expected) == 1, result.stderr
    assert "DeprecationWarning" not in result.stderr, "default filters should hide the warning object"


def test_old_common_name_exposes_lazy_client_names():
    """vcfcf_common lazy-loads VCFOpsClient/VCFOpsError via module __getattr__; the shim must forward it."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from vcfops_common import VCFOpsClient, VCFOpsError  # noqa: PLC0415
        import vcfops_common  # noqa: PLC0415
        import vcfcf_common  # noqa: PLC0415
    assert VCFOpsClient is vcfcf_common.VCFOpsClient
    assert VCFOpsError is vcfcf_common.VCFOpsError
    assert vcfops_common.VCFOpsError is vcfcf_common.VCFOpsError
    assert "VCFOpsClient" in dir(vcfops_common)
    with pytest.raises(AttributeError):
        vcfops_common.no_such_name  # noqa: B018


def test_old_common_star_import_resolves_every_all_name():
    ns = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        exec("from vcfops_common import *", ns)  # noqa: S102
        import vcfcf_common  # noqa: PLC0415
    for name in vcfcf_common.__all__:
        assert ns[name] is getattr(vcfcf_common, name), name


def test_old_non_common_package_attribute():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import vcfops_packaging  # noqa: PLC0415
        import vcfcf_packaging  # noqa: PLC0415
    assert vcfops_packaging.CURRENT_TEMPLATE_VERSION == vcfcf_packaging.CURRENT_TEMPLATE_VERSION


# ---------------------------------------------------------------------------
# Dotted `python -m vcfops_<x>.<sub>` runs (Codex P2 on PR #160): runpy asks
# the alias loader for get_code, so the old dotted names must execute the
# real module's code and print the notice. The four --help modules are every
# runnable submodule with an argparse entry; _test_tier33_grammar is the one
# dotted form documented in the repo (its own docstring).
# ---------------------------------------------------------------------------

DOTTED_HELP_MODULES = [
    "vcfops_common.doctor",
    "vcfops_common.setup_credentials",
    "vcfops_packaging.defects",
    "vcfops_managementpacks.buildkit",
]


def _notice(old_module: str) -> str:
    new_module = old_module.replace("vcfops_", "vcfcf_", 1)
    return f"{old_module} is deprecated, use {new_module}; removed next release"


@pytest.mark.parametrize("old_module", DOTTED_HELP_MODULES)
def test_old_dotted_module_help_runs_through_alias_loader(old_module):
    new_module = old_module.replace("vcfops_", "vcfcf_", 1)
    old = _run_old_module(old_module, "--help", default_filters=True)
    new = _run_old_module(new_module, "--help", default_filters=True)
    assert new.returncode == 0, new.stderr
    assert old.returncode == 0, old.stderr
    assert old.stdout == new.stdout
    assert old.stderr.count(_notice(old_module)) == 1, old.stderr
    assert "AttributeError" not in old.stderr


def test_old_dotted_grammar_suite_matches_new_name():
    """The documented `-m vcfcf_managementpacks._test_tier33_grammar` form, via the old name.

    The suite's own pass/fail is not under test here (it exits 1 on main
    today); what matters is that the old dotted name runs the same code and
    lands on the same result as the new one, with the notice on stderr.
    """
    old_module = "vcfops_managementpacks._test_tier33_grammar"
    old = _run_old_module(old_module, default_filters=True)
    new = _run_old_module("vcfcf_managementpacks._test_tier33_grammar", default_filters=True)
    assert old.returncode == new.returncode
    assert old.stdout == new.stdout
    assert old.stderr.count(_notice(old_module)) == 1, old.stderr
    assert "_AliasLoader" not in old.stderr and "AttributeError" not in old.stderr


def test_old_dotted_subpackage_alias_is_a_package():
    import importlib.util  # noqa: PLC0415

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        spec = importlib.util.find_spec("vcfops_managementpacks.adapter_framework")
        import vcfops_managementpacks.adapter_framework as old_pkg  # noqa: PLC0415
        import vcfcf_managementpacks.adapter_framework as new_pkg  # noqa: PLC0415
    assert spec is not None and spec.submodule_search_locations is not None
    assert old_pkg is new_pkg
    leaf = importlib.util.find_spec("vcfops_packaging.defects")
    assert leaf.origin and leaf.origin.endswith("vcfcf_packaging/defects.py")
    assert leaf.has_location


# ---------------------------------------------------------------------------
# Round 3 (framework review of 698845a): the alias must not clobber the real
# module's spec, must not execute a module body twice on the -m path, and
# must handle subpackage __main__ once. A scratch old/new package pair with
# an import-time side-effect log makes each of those observable.
# ---------------------------------------------------------------------------

_SIDE_MODULE = '''import os
with open(os.environ["SIDE_LOG"], "a") as f:
    f.write(f"EXEC side name={__name__}\\n")
if __name__ == "__main__":
    print("side main ran")
'''
_SUBPKG_MAIN = '''import os
with open(os.environ["SIDE_LOG"], "a") as f:
    f.write(f"EXEC subpkg.__main__ name={__name__}\\n")
print("subpkg main ran")
'''


@pytest.fixture
def scratch_pair(tmp_path, monkeypatch):
    """Create ``<new>/side.py``, ``<new>/subpkg/__main__.py`` and a shim ``<old>``.

    Names are unique per test so in-process imports never collide across
    tests; sys.path/sys.modules are restored afterwards.
    """
    tag = tmp_path.name.replace("-", "_").lower()
    new_name, old_name = f"cfnew_{tag}", f"cfold_{tag}"
    new_pkg = tmp_path / new_name
    (new_pkg / "subpkg").mkdir(parents=True)
    (new_pkg / "__init__.py").write_text("")
    (new_pkg / "side.py").write_text(_SIDE_MODULE)
    (new_pkg / "subpkg" / "__init__.py").write_text("")
    (new_pkg / "subpkg" / "__main__.py").write_text(_SUBPKG_MAIN)
    old_pkg = tmp_path / old_name
    old_pkg.mkdir()
    (old_pkg / "__init__.py").write_text(
        "from vcfcf_common.compat_shim import install as _install\n"
        f"_install(__name__, {new_name!r}, globals())\n"
    )
    log = tmp_path / "side.log"
    log.write_text("")
    monkeypatch.setenv("SIDE_LOG", str(log))
    monkeypatch.syspath_prepend(str(tmp_path))
    yield {"old": old_name, "new": new_name, "log": log, "root": tmp_path}
    for name in list(sys.modules):
        if name.startswith((old_name, new_name)):
            del sys.modules[name]


def _log_lines(log: Path):
    return [line for line in log.read_text().splitlines() if line]


def _run_scratch(pair, module: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(SRC), str(pair["root"])])
    env["SIDE_LOG"] = str(pair["log"])
    env.pop("PYTHONWARNINGS", None)
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=120,
    )


def test_old_dotted_run_executes_module_body_once(scratch_pair):
    """W1: `-m old.sub` must not import the module under the new name first."""
    old, new, log = scratch_pair["old"], scratch_pair["new"], scratch_pair["log"]
    result = _run_scratch(scratch_pair, f"{old}.side")
    assert result.returncode == 0, result.stderr
    assert _log_lines(log) == ["EXEC side name=__main__"]
    assert result.stdout.strip() == "side main ran"
    assert result.stderr.count(f"{old}.side is deprecated, use {new}.side; removed next release") == 1
    log.write_text("")
    result = _run_scratch(scratch_pair, f"{new}.side")
    assert result.returncode == 0 and _log_lines(log) == ["EXEC side name=__main__"]
    assert result.stderr == ""


def test_old_dotted_subpackage_main_runs_once(scratch_pair):
    """N1: `-m old.subpkg` runs subpkg/__main__.py exactly once and names the package."""
    old, new, log = scratch_pair["old"], scratch_pair["new"], scratch_pair["log"]
    result = _run_scratch(scratch_pair, f"{old}.subpkg")
    assert result.returncode == 0, result.stderr
    assert _log_lines(log) == ["EXEC subpkg.__main__ name=__main__"]
    assert result.stdout.strip() == "subpkg main ran"
    assert result.stderr.count(f"{old}.subpkg is deprecated, use {new}.subpkg; removed next release") == 1
    assert "__main__ is deprecated" not in result.stderr


def test_old_import_keeps_real_spec_name_and_reload_reexecutes(scratch_pair):
    """B1: aliasing must not turn importlib.reload on the new name into a no-op."""
    import importlib  # noqa: PLC0415

    old, new, log = scratch_pair["old"], scratch_pair["new"], scratch_pair["log"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        old_side = importlib.import_module(f"{old}.side")
    new_side = sys.modules[f"{new}.side"]
    assert old_side is new_side
    assert new_side.__spec__.name == f"{new}.side"
    assert new_side.__name__ == f"{new}.side"
    assert _log_lines(log) == [f"EXEC side name={new}.side"]
    importlib.reload(new_side)
    assert _log_lines(log) == [f"EXEC side name={new}.side"] * 2
    assert new_side.__name__ == f"{new}.side"
    assert sys.modules[f"{old}.side"] is sys.modules[f"{new}.side"]


def test_real_package_spec_name_survives_old_import():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import vcfops_common.client  # noqa: F401,PLC0415
        import vcfcf_common.client  # noqa: PLC0415
    assert vcfcf_common.client.__spec__.name == "vcfcf_common.client"
    assert vcfcf_common.client.__spec__.origin.endswith("vcfcf_common/client.py")


def test_old_import_then_in_process_runpy_completes(scratch_pair, capsys):
    """B1: runpy on an already-imported old dotted name must not recurse."""
    import importlib  # noqa: PLC0415
    import runpy  # noqa: PLC0415

    old, new, log = scratch_pair["old"], scratch_pair["new"], scratch_pair["log"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        importlib.import_module(f"{old}.side")
    runpy.run_module(f"{old}.side", run_name="__main__")
    captured = capsys.readouterr()
    assert captured.err.count(f"{old}.side is deprecated, use {new}.side; removed next release") == 1
    assert "side main ran" in captured.out
    assert _log_lines(log) == [f"EXEC side name={new}.side", "EXEC side name=__main__"]


def test_alias_loader_forwards_source_without_recursion():
    import importlib.util  # noqa: PLC0415
    import inspect  # noqa: PLC0415

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import vcfops_packaging.defects as old_defects  # noqa: PLC0415
    spec = importlib.util.find_spec("vcfops_packaging.defects")
    source = spec.loader.get_source("vcfops_packaging.defects")
    assert source and "def gate_all(" in source
    assert inspect.getsource(old_defects) == source
    assert spec.loader.get_filename("vcfops_packaging.defects").endswith("vcfcf_packaging/defects.py")
