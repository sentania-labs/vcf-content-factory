"""A multi-token or unrecognised Affects: is malformed, never silently valid (#153).

Before this fix an otherwise complete entry whose Affects: wrapped onto a
continuation line (a token plus a parenthetical path or note) parsed as a
VALID entry.  Its affects string could never equal a pak name or
<type>/<slug>, so every gate matched nothing and printed nothing: DEF-020
(open, blocking) let `defect-gate --pak vcommunity-vsphere` exit 0.  The
one-token check only ran for entries that had already failed to parse.

Contract under test:
  - multi-token Affects is a ParseError, reported loudly on every gate run;
  - it fails closed for its FIRST token when that token unambiguously names
    a scope (known managed pak, <type>/<slug>, factory:<area>);
  - otherwise it is unscoped: reported, blocks nothing (prose stays prose);
  - a single token with a prefix other than factory: (pak:x) is malformed
    and unscoped;
  - single-token entries, including factory:<area>, are unchanged;
  - the shipped registry has no parse errors.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vcfcf_packaging import defects
from vcfcf_packaging.defects import (
    REGISTRY_PATH,
    gate_all,
    gate_item,
    gate_pak,
    parse_registry,
    reset_warning_state,
)


def _entry(affects_lines: str, *, status: str = "open", severity: str = "blocking") -> str:
    return f"""\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture entry
- **Severity:** {severity}
- **Status:** {status}
- **Affects:** {affects_lines}
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Fixture summary.
"""


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "defects.md"
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _fresh_warnings(monkeypatch):
    reset_warning_state()
    # A fixed managed-pak list so the tests do not depend on the live
    # knowledge/context/managed_paks.md contents.
    monkeypatch.setattr(
        defects, "_known_pak_names", lambda: frozenset({"fixturepak", "vcommunity-vsphere"})
    )
    yield
    reset_warning_state()


class TestMultiTokenIsMalformed:

    def test_wrapped_affects_is_a_parse_error(self, tmp_path):
        """The DEF-020 shape: token, then a wrapped note on a continuation line."""
        reg = _write(tmp_path, _entry(
            "fixturepak (dashboard `VM Details.yaml`\n  line ~606)"
        ))
        registry = parse_registry(reg)
        assert registry.entries == [], "a multi-token Affects must not parse as valid"
        assert len(registry.errors) == 1
        assert "exactly one scope token" in registry.errors[0].reason

    def test_known_pak_first_token_fails_closed(self, tmp_path):
        reg = _write(tmp_path, _entry("fixturepak (see the dashboards/ folder)"))
        blockers = gate_pak("fixturepak", reg)
        assert len(blockers) == 1, "the broken entry must still gate the pak it names"
        assert blockers[0].synthetic is True
        assert gate_pak("otherpak", reg) == []

    def test_closed_entry_with_multi_token_still_fails_closed(self, tmp_path):
        """Malformed means unreadable: the parser cannot trust its Status."""
        reg = _write(tmp_path, _entry(
            "fixturepak (note)", status="closed", severity="tracked"
        ).replace("- **Summary:**", "- **Closing-evidence:** fixed.\n- **Summary:**"))
        assert len(gate_pak("fixturepak", reg)) == 1

    def test_item_scope_first_token_fails_closed(self, tmp_path):
        reg = _write(tmp_path, _entry("dashboard/my_dash (render path)"))
        assert len(gate_item("dashboard", "my_dash", reg)) == 1

    def test_factory_scope_first_token_fails_closed(self, tmp_path):
        reg = _write(tmp_path, _entry("factory:dashboards (`src/vcfcf_dashboards/render.py`)"))
        blockers = gate_all(reg)
        assert [b.affects for b in blockers] == ["factory:dashboards"]

    def test_unknown_first_token_is_unscoped_and_loud(self, tmp_path, capsys):
        """Prose must not be guessed into a scope; it blocks nothing, loudly."""
        reg = _write(tmp_path, _entry("all of the dashboards, probably"))
        registry = parse_registry(reg)
        assert len(registry.unscoped_errors) == 1
        assert gate_all(reg) == []
        err = capsys.readouterr().err
        assert "WARNING" in err and "DEF-001" in err and "blocks nothing" in err

    def test_the_original_def020_value_is_reported(self, tmp_path, capsys):
        """`pak:` prefix plus a note: unattributable, but never silent."""
        reg = _write(tmp_path, _entry("pak:vcommunity-vsphere (VM Details.yaml line ~606)"))
        assert gate_pak("vcommunity-vsphere", reg) == []
        err = capsys.readouterr().err
        assert "DEF-001" in err and "WARNING" in err


class TestSingleToken:

    def test_single_token_pak_is_valid(self, tmp_path):
        reg = _write(tmp_path, _entry("fixturepak"))
        registry = parse_registry(reg)
        assert registry.errors == []
        assert [e.id for e in gate_pak("fixturepak", reg)] == ["DEF-001"]

    def test_single_token_unregistered_pak_is_still_valid(self, tmp_path):
        """A consumer's own pak (defects.local.md) need not be in managed_paks.md."""
        reg = _write(tmp_path, _entry("local-only-pak"))
        assert parse_registry(reg).errors == []
        assert len(gate_pak("local-only-pak", reg)) == 1

    def test_single_token_factory_scope_is_valid(self, tmp_path):
        reg = _write(tmp_path, _entry("factory:packaging-cli"))
        assert parse_registry(reg).errors == []

    def test_unrecognised_prefix_is_malformed_and_unscoped(self, tmp_path, capsys):
        reg = _write(tmp_path, _entry("pak:fixturepak"))
        registry = parse_registry(reg)
        assert registry.entries == []
        assert len(registry.unscoped_errors) == 1
        assert "not a recognised scope" in registry.errors[0].reason
        assert gate_pak("fixturepak", reg) == []
        assert "DEF-001" in capsys.readouterr().err


def test_known_pak_names_survives_unreadable_managed_paks(monkeypatch):
    """Best effort: a broken managed-paks registry means no attribution, not a crash."""
    monkeypatch.undo()
    import vcfcf_packaging.managed_paks as mp

    def _boom(*_a, **_k):
        raise OSError("synthetic")

    monkeypatch.setattr(mp, "load_registry", _boom)
    assert defects._known_pak_names() == frozenset()


def test_shipped_registry_has_no_parse_errors():
    """Regression guard: DEF-013/014/018/019 carried multi-token Affects."""
    registry = parse_registry(REGISTRY_PATH)
    assert registry.errors == [], [str(e) for e in registry.errors]
