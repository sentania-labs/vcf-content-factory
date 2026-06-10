"""Unit tests for vcfops_packaging.managed_paks registry reader.

Tests cover:
  - Parsing a well-formed fixture registry with one entry.
  - Comment-block skipping (the HTML template block is silently ignored).
  - Empty registry (no entries) returns an empty list.
  - Missing registry file raises FileNotFoundError.
  - Lookup helpers (by name, by adapter_kind).
  - URL derivations (latest_release_url, api_latest_url).
  - Partial entry (missing adapter_kind) does not produce a broken record.

Note: these tests use fixture content only — no live GitHub repos are needed.
Full end-to-end verification (actual managed_paks.md with live sentania-labs
repos) cannot be automated until Workstream D is complete and the external
repos exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from vcfops_packaging.managed_paks import (
    ManagedPak,
    load_registry,
    lookup_by_adapter_name,
    lookup_by_adapter_kind,
    derived_latest_release_url,
    derived_api_latest_url,
)


# ---------------------------------------------------------------------------
# Fixture registry helper
# ---------------------------------------------------------------------------

def _write_fixture(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "managed_paks.md"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Full one-entry registry
# ---------------------------------------------------------------------------

_ONE_ENTRY_REGISTRY = """\
# Managed paks (SDK adapter registry)

## Paks

<!--
No managed paks registered yet. Template for an entry:

### template-entry

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-template
- **Target:** `content/sdk-adapters/template-entry/`
- **adapter_kind:** vcfcf_template
- **Owner:** sentania-labs. Public repo.
- **Notes:** This should be skipped — it is inside an HTML comment.

-->

### compliance

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-compliance
- **Target:** `content/sdk-adapters/compliance/`
- **adapter_kind:** vcfcf_compliance
- **Owner:** sentania-labs. Public repo.
- **Notes:** CIS vSphere compliance adapter.
"""


class TestLoadRegistryOneEntry:
    """load_registry with a single live entry."""

    @pytest.fixture
    def registry(self, tmp_path):
        return _write_fixture(tmp_path, _ONE_ENTRY_REGISTRY)

    def test_returns_one_entry(self, registry):
        entries = load_registry(registry)
        assert len(entries) == 1, f"Expected 1 entry, got {len(entries)}: {entries}"

    def test_entry_is_managed_pak(self, registry):
        entries = load_registry(registry)
        assert isinstance(entries[0], ManagedPak)

    def test_name(self, registry):
        pak = load_registry(registry)[0]
        assert pak.name == "compliance"

    def test_remote(self, registry):
        pak = load_registry(registry)[0]
        assert pak.remote == (
            "https://github.com/sentania-labs/vcf-content-factory-sdk-compliance"
        )

    def test_target(self, registry):
        pak = load_registry(registry)[0]
        assert pak.target == "content/sdk-adapters/compliance/"

    def test_adapter_kind(self, registry):
        pak = load_registry(registry)[0]
        assert pak.adapter_kind == "vcfcf_compliance"

    def test_comment_block_not_included(self, registry):
        """The template inside the HTML comment must not produce an entry."""
        paks = load_registry(registry)
        names = [p.name for p in paks]
        assert "template-entry" not in names, (
            f"template-entry should be skipped (it's in a comment); got: {names}"
        )


# ---------------------------------------------------------------------------
# Comment-only registry (no live entries)
# ---------------------------------------------------------------------------

_COMMENT_ONLY_REGISTRY = """\
# Managed paks (SDK adapter registry)

## Paks

<!--
### only-in-comment

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-in-comment
- **Target:** `content/sdk-adapters/only-in-comment/`
- **adapter_kind:** vcfcf_in_comment
-->
"""


class TestLoadRegistryEmpty:
    def test_empty_returns_empty_list(self, tmp_path):
        reg = _write_fixture(tmp_path, _COMMENT_ONLY_REGISTRY)
        entries = load_registry(reg)
        assert entries == [], f"Expected empty list, got: {entries}"


# ---------------------------------------------------------------------------
# Multi-entry registry
# ---------------------------------------------------------------------------

_MULTI_ENTRY_REGISTRY = """\
# Managed paks (SDK adapter registry)

## Paks

### alpha

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-alpha
- **Target:** `content/sdk-adapters/alpha/`
- **adapter_kind:** vcfcf_alpha
- **Notes:** First pak.

### beta

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-beta
- **Target:** `content/sdk-adapters/beta/`
- **adapter_kind:** vcfcf_beta
- **Notes:** Second pak.
"""


class TestLoadRegistryMultiple:
    @pytest.fixture
    def registry(self, tmp_path):
        return _write_fixture(tmp_path, _MULTI_ENTRY_REGISTRY)

    def test_returns_two_entries(self, registry):
        entries = load_registry(registry)
        assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}"

    def test_entry_order(self, registry):
        entries = load_registry(registry)
        assert entries[0].name == "alpha"
        assert entries[1].name == "beta"

    def test_no_cross_contamination(self, registry):
        entries = load_registry(registry)
        assert entries[0].adapter_kind == "vcfcf_alpha"
        assert entries[1].adapter_kind == "vcfcf_beta"


# ---------------------------------------------------------------------------
# Missing file
# ---------------------------------------------------------------------------

class TestLoadRegistryMissing:
    def test_raises_file_not_found(self, tmp_path):
        missing = tmp_path / "does_not_exist.md"
        with pytest.raises(FileNotFoundError):
            load_registry(missing)


# ---------------------------------------------------------------------------
# Partial entry (missing adapter_kind) — must not emit a broken record
# ---------------------------------------------------------------------------

_PARTIAL_REGISTRY = """\
# Managed paks

## Paks

### incomplete-entry

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-incomplete
- **Target:** `content/sdk-adapters/incomplete-entry/`
# adapter_kind deliberately omitted — this entry is not emitted.
"""


class TestLoadRegistryPartial:
    def test_partial_entry_not_emitted(self, tmp_path):
        reg = _write_fixture(tmp_path, _PARTIAL_REGISTRY)
        entries = load_registry(reg)
        assert entries == [], (
            f"A partial entry (missing adapter_kind) must not be emitted; got: {entries}"
        )


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

class TestLookupHelpers:
    @pytest.fixture
    def registry(self, tmp_path):
        return _write_fixture(tmp_path, _MULTI_ENTRY_REGISTRY)

    def test_lookup_by_name_found(self, registry):
        pak = lookup_by_adapter_name("alpha", registry)
        assert pak is not None
        assert pak.name == "alpha"

    def test_lookup_by_name_not_found(self, registry):
        result = lookup_by_adapter_name("gamma", registry)
        assert result is None

    def test_lookup_by_adapter_kind_found(self, registry):
        pak = lookup_by_adapter_kind("vcfcf_beta", registry)
        assert pak is not None
        assert pak.name == "beta"

    def test_lookup_by_adapter_kind_not_found(self, registry):
        result = lookup_by_adapter_kind("vcfcf_unknown", registry)
        assert result is None


# ---------------------------------------------------------------------------
# URL derivations
# ---------------------------------------------------------------------------

class TestUrlDerivations:
    @pytest.fixture
    def pak(self):
        return ManagedPak(
            name="compliance",
            remote="https://github.com/sentania-labs/vcf-content-factory-sdk-compliance",
            target="content/sdk-adapters/compliance/",
            adapter_kind="vcfcf_compliance",
        )

    def test_latest_release_url(self, pak):
        url = derived_latest_release_url(pak)
        expected = (
            "https://github.com/sentania-labs/vcf-content-factory-sdk-compliance"
            "/releases/latest"
        )
        assert url == expected, f"Got: {url!r}"

    def test_latest_release_url_ends_with_releases_latest(self, pak):
        url = derived_latest_release_url(pak)
        assert url.endswith("/releases/latest"), f"Must end with /releases/latest: {url!r}"

    def test_latest_release_url_no_version_pin(self, pak):
        url = derived_latest_release_url(pak)
        assert "/releases/tag/" not in url, (
            f"Must not pin a specific tag (version-free): {url!r}"
        )

    def test_api_latest_url_github(self, pak):
        url = derived_api_latest_url(pak)
        expected = (
            "https://api.github.com/repos/sentania-labs/"
            "vcf-content-factory-sdk-compliance/releases/latest"
        )
        assert url == expected, f"Got: {url!r}"

    def test_api_latest_url_non_github_returns_none(self):
        pak = ManagedPak(
            name="custom",
            remote="https://gitlab.example.com/org/vcf-pak",
            target="content/sdk-adapters/custom/",
            adapter_kind="vcfcf_custom",
        )
        result = derived_api_latest_url(pak)
        assert result is None, f"Expected None for non-GitHub remote; got: {result!r}"

    def test_api_latest_url_from_git_remote(self):
        """Remote ending in .git is still parsed correctly."""
        pak = ManagedPak(
            name="test",
            remote="https://github.com/sentania-labs/vcf-content-factory-sdk-test.git",
            target="content/sdk-adapters/test/",
            adapter_kind="vcfcf_test",
        )
        url = derived_api_latest_url(pak)
        expected = (
            "https://api.github.com/repos/sentania-labs/"
            "vcf-content-factory-sdk-test/releases/latest"
        )
        assert url == expected, f"Got: {url!r}"


# ---------------------------------------------------------------------------
# Inline comment open-and-close on same line
# ---------------------------------------------------------------------------

_INLINE_COMMENT_REGISTRY = """\
# Registry with inline comment

## Paks

<!-- This entire thing is one line --> ### should-not-parse

### real-entry

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-real
- **Target:** `content/sdk-adapters/real-entry/`
- **adapter_kind:** vcfcf_real
"""


class TestInlineComment:
    def test_inline_comment_does_not_produce_entry(self, tmp_path):
        reg = _write_fixture(tmp_path, _INLINE_COMMENT_REGISTRY)
        entries = load_registry(reg)
        names = [p.name for p in entries]
        assert "should-not-parse" not in names, (
            f"Entry after inline comment should be ignored; got: {names}"
        )

    def test_entry_after_comment_line_is_parsed(self, tmp_path):
        reg = _write_fixture(tmp_path, _INLINE_COMMENT_REGISTRY)
        entries = load_registry(reg)
        names = [p.name for p in entries]
        assert "real-entry" in names, (
            f"Entry after comment line should be parsed; got: {names}"
        )
