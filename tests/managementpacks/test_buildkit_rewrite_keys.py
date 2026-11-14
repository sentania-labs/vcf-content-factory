"""The buildkit's file-keyed dict literals carry each file once.

A second literal key for the same file silently replaces the first in a
Python dict: ``_IMPORT_REWRITES`` defined ``alerts_loader.py`` and
``symptoms_loader.py`` twice, so the first rule list of each (the
``rendered_id_collisions`` rewrites) never applied (review N5, 2026-11-14).
"""
from __future__ import annotations

import ast
import collections
from pathlib import Path

import pytest

BUILDKIT = Path(__file__).resolve().parents[2] / "src" / "vcfcf_managementpacks" / "buildkit.py"


def _dict_literal(name: str) -> ast.Dict:
    tree = ast.parse(BUILDKIT.read_text(encoding="utf-8"))
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else (
            node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None)
        if isinstance(target, ast.Name) and target.id == name and isinstance(node.value, ast.Dict):
            return node.value
    raise AssertionError(f"{name} dict literal not found in buildkit.py")


@pytest.mark.parametrize("name", ["_IMPORT_REWRITES", "_FACTORY_SOURCES"])
def test_no_duplicate_literal_keys(name):
    keys = [k.value for k in _dict_literal(name).keys if isinstance(k, ast.Constant)]
    dups = [k for k, n in collections.Counter(keys).items() if n > 1]
    assert dups == [], f"{name} defines {dups} more than once"


def test_rendered_id_collision_rewrites_apply():
    from vcfcf_managementpacks.buildkit import _IMPORT_REWRITES
    for f in ("alerts_loader.py", "symptoms_loader.py"):
        assert any("rendered_id_collisions" in pattern for pattern, _ in _IMPORT_REWRITES[f]), f
        assert any("naming" in pattern for pattern, _ in _IMPORT_REWRITES[f]), f
