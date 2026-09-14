"""The vcf-cf-tooling-core contract: ``vcfcf_core`` stays a library.

Design: ``knowledge/designs/tooling-core-carveout-v1.md`` §The contract.

Two halves:

1. Dynamic: every module under ``src/vcfcf_core`` imports in a subprocess
   whose working directory is an empty temp dir and whose environment is
   empty except ``PATH`` and a ``PYTHONPATH`` pointing at ``src/``. A module
   that needs the factory tree, a ``.env``, or the repo cwd fails here.

2. Static (AST, so prose in docstrings and comments never trips it): every
   ``.py`` under ``src/vcfcf_core`` is rejected for
   - ``os.environ`` / ``os.getenv`` reads (any spelling of the import),
   - a path that escapes the package: ``.parents[...]`` anywhere, or
     ``.parent.parent`` anywhere, or ``<name>.parent`` where ``<name>`` was
     bound at module level from an expression mentioning ``__file__``,
   - a default argument value naming a factory directory
     (``content/...``, ``knowledge/...``, ``dist...``, or exactly
     ``supermetrics`` / ``views`` / ``dashboards`` / ``bundles``),
   - ``import requests`` in any form,
   - an import of any ``vcfcf_*`` package other than ``vcfcf_core``,
   - a file write (``open(..., "w"/"a"/"x")``, ``.write_text``,
     ``.write_bytes``) inside a function whose name starts with ``load``.

``ALLOWLIST`` is the only escape hatch: explicit ``(relative path, line)``
pairs, each expected to carry a reason in a comment next to it. It is empty
and should stay that way unless a reviewer agrees otherwise.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
CORE = SRC / "vcfcf_core"

# (path relative to src/, 1-based line number) pairs exempt from the static
# checks. Empty on purpose; see the module docstring.
ALLOWLIST: set[tuple[str, int]] = set()

_DIR_DEFAULT_PREFIXES = ("content/", "knowledge/", "dist")
_DIR_DEFAULT_EXACT = {"supermetrics", "views", "dashboards", "bundles"}
_WRITE_MODES = ("w", "a", "x")


def _core_py_files() -> list[Path]:
    files = sorted(CORE.rglob("*.py"))
    assert files, f"no .py files under {CORE}"
    return files


def _module_name(path: Path) -> str:
    rel = path.relative_to(SRC).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _rel(path: Path) -> str:
    return str(path.relative_to(SRC))


# ---------------------------------------------------------------------------
# Dynamic half
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "module", [_module_name(p) for p in _core_py_files()], ids=lambda m: m,
)
def test_core_module_imports_with_no_environment(module: str, tmp_path: Path) -> None:
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(SRC)}
    result = subprocess.run(
        [sys.executable, "-c", f"import importlib; importlib.import_module({module!r})"],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"{module} failed to import from an empty cwd with an empty environment:\n"
        f"{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Static half
# ---------------------------------------------------------------------------

def _is_str_const(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _names_bound_from_file(tree: ast.Module, source: str) -> set[str]:
    """Module-level names whose value expression mentions ``__file__``."""
    bound: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        if value is None:
            continue
        segment = ast.get_source_segment(source, value, padded=False) or ""
        if "__file__" in segment:
            for t in targets:
                if isinstance(t, ast.Name):
                    bound.add(t.id)
    return bound


def _open_write_mode(call: ast.Call) -> bool:
    if not (isinstance(call.func, ast.Name) and call.func.id == "open"):
        return False
    mode: ast.expr | None = None
    if len(call.args) >= 2:
        mode = call.args[1]
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    return _is_str_const(mode) and any(m in mode.value for m in _WRITE_MODES)  # type: ignore[union-attr]


def _static_findings(path: Path) -> list[tuple[int, str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    findings: list[tuple[int, str]] = []
    file_bound = _names_bound_from_file(tree, source)

    def hit(node: ast.AST, msg: str) -> None:
        findings.append((node.lineno, msg))

    # Track the innermost enclosing function name so writes inside load*
    # functions can be attributed. Nested defs are walked explicitly.
    def walk(node: ast.AST, func_stack: list[str]) -> None:
        for child in ast.iter_child_nodes(node):
            check(child, func_stack)
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child, func_stack + [child.name])
            else:
                walk(child, func_stack)

    def check(node: ast.AST, func_stack: list[str]) -> None:
        # Imports.
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top == "requests":
                    hit(node, "imports requests")
                if top.startswith("vcfcf_") and top != "vcfcf_core":
                    hit(node, f"imports non-core package {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            top = mod.split(".")[0]
            if node.level == 0:
                if top == "requests":
                    hit(node, "imports requests")
                if top.startswith("vcfcf_") and top != "vcfcf_core":
                    hit(node, f"imports non-core package {mod}")
                if top == "os":
                    for alias in node.names:
                        if alias.name in ("environ", "getenv"):
                            hit(node, f"imports os.{alias.name}")
        # os.environ / os.getenv attribute reads.
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr in ("environ", "getenv"):
                hit(node, f"reads os.{node.attr}")
            if node.attr == "parent":
                if isinstance(node.value, ast.Attribute) and node.value.attr == "parent":
                    hit(node, "escapes the package via .parent.parent")
                if isinstance(node.value, ast.Name) and node.value.id in file_bound:
                    hit(node, f"escapes the package via {node.value.id}.parent (bound from __file__)")
        elif isinstance(node, ast.Subscript):
            if isinstance(node.value, ast.Attribute) and node.value.attr == "parents":
                hit(node, "escapes the package via .parents[...]")
        # Default argument values naming a directory.
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            defaults = list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]
            for d in defaults:
                if _is_str_const(d):
                    v = d.value  # type: ignore[union-attr]
                    if v.startswith(_DIR_DEFAULT_PREFIXES) or v.rstrip("/") in _DIR_DEFAULT_EXACT:
                        hit(d, f"default argument names a directory: {v!r}")
        # Writes inside load* functions.
        elif isinstance(node, ast.Call):
            in_load = any(name.startswith("load") for name in func_stack)
            if in_load:
                if _open_write_mode(node):
                    hit(node, f"open() for writing inside {func_stack[-1]}()")
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("write_text", "write_bytes"):
                    hit(node, f".{node.func.attr}() inside {func_stack[-1]}()")

    walk(tree, [])
    rel = _rel(path)
    return [(ln, msg) for ln, msg in findings if (rel, ln) not in ALLOWLIST]


@pytest.mark.parametrize("path", _core_py_files(), ids=_rel)
def test_core_module_static_contract(path: Path) -> None:
    findings = _static_findings(path)
    assert not findings, "\n".join(
        f"{_rel(path)}:{ln}: {msg}" for ln, msg in findings
    )


def test_allowlist_entries_point_at_real_lines() -> None:
    """A stale allowlist entry would silently widen the contract."""
    for rel, line in ALLOWLIST:
        p = SRC / rel
        assert p.is_file(), f"ALLOWLIST names a missing file: {rel}"
        assert 1 <= line <= len(p.read_text(encoding="utf-8").splitlines()), (
            f"ALLOWLIST line out of range: {rel}:{line}"
        )


# ---------------------------------------------------------------------------
# Self-check: the static checker must actually catch each violation class.
# ---------------------------------------------------------------------------

_VIOLATION_SAMPLES = {
    "os.environ": "import os\nX = os.environ.get('A')\n",
    "os.getenv": "import os\nX = os.getenv('A')\n",
    "from os import environ": "from os import environ\n",
    ".parent.parent": "from pathlib import Path\nR = Path(__file__).parent.parent\n",
    ".parents[": "from pathlib import Path\nR = Path(__file__).parents[2]\n",
    "bound .parent": "from pathlib import Path\nH = Path(__file__).parent\nR = H.parent\n",
    "default content/": "def f(root='content/supermetrics'):\n    pass\n",
    "default bare dir": "def f(*, kind='views'):\n    pass\n",
    "import requests": "import requests\n",
    "from requests": "from requests import Session\n",
    "non-core vcfcf": "from vcfcf_common.client import Client\n",
    "open w in load": "def load_x(p):\n    with open(p, 'w') as fh:\n        fh.write('')\n",
    "write_text in load": "def load_y(p):\n    p.write_text('')\n",
}


@pytest.mark.parametrize("label", sorted(_VIOLATION_SAMPLES), ids=lambda s: s)
def test_static_checker_catches_each_violation_class(label: str, tmp_path: Path, monkeypatch) -> None:
    sample_root = tmp_path / "src" / "vcfcf_core"
    sample_root.mkdir(parents=True)
    sample = sample_root / "sample.py"
    sample.write_text(_VIOLATION_SAMPLES[label], encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "SRC", tmp_path / "src")
    assert _static_findings(sample), f"checker missed the {label!r} class"


def test_static_checker_accepts_clean_module(tmp_path: Path, monkeypatch) -> None:
    sample_root = tmp_path / "src" / "vcfcf_core"
    sample_root.mkdir(parents=True)
    sample = sample_root / "clean.py"
    sample.write_text(
        "import os\nfrom pathlib import Path\nimport yaml\n"
        "def load_z(p: Path, mode='r'):\n    return yaml.safe_load(p.read_text())\n"
        "def write_out(p: Path, text):\n    p.write_text(text)\n"
        "HERE = Path(__file__).parent\nSIBLING = HERE / 'x'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "SRC", tmp_path / "src")
    assert _static_findings(sample) == []
