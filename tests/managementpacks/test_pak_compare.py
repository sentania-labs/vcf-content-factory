"""Tests for pak_compare, focusing on the SDK-adapter (Tier 2) describe.xml fix.

Bug fixed: pak-compare directory mode emitted a false-positive BLOCKING
  [B1] describe.xml: factory has no describe.xml
when comparing a Tier 2 SDK-adapter pak against another SDK-adapter pak.

Root cause: _detect_adapter_dir only recognised the Tier 1 (MPB) pattern
  '<something>_adapter3/'
and returned None for SDK-adapter paks whose adapter dir does NOT end in
'_adapter3' (e.g. 'vcfcf_compliance'). With adapter_dir=None the caller
skipped the adapters.zip describe.xml lookup and passed None to
_compare_describe_xml, which then raised the spurious D0 BLOCKING.

Fix: _detect_adapter_dir now falls back to looking for the Tier 2 pattern
  '<adapterkind>/conf/describe.xml'
inside adapters.zip when no _adapter3 directory is found.

Test coverage:
  - _detect_adapter_dir returns correct dir for Tier 1 (_adapter3 layout)
  - _detect_adapter_dir returns correct dir for Tier 2 (SDK layout, no _adapter3)
  - _detect_adapter_dir returns None when adapters.zip is empty
  - _detect_adapter_dir returns None when adapters.zip has no recognisable layout
  - compare_paks: SDK pak vs SDK pak produces zero D0 BLOCKINGs (the regression test)
  - compare_paks: Tier 1 pak vs Tier 1 pak — describe.xml is still found (no regression)
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import pytest

from vcfops_managementpacks.pak_compare import (
    _detect_adapter_dir,
    _read_adapters_zip_inventory,
    compare_paks,
    BLOCKING,
)

# ---------------------------------------------------------------------------
# Repository root (for loading real pak fixtures)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DIST = _REPO_ROOT / "dist"

# Specific paks used for integration tests.  Both are checked into dist/.
_SDK_FACTORY_PAK = _DIST / "vcfcf_sdk_compliance.1.0.0.37.pak"
_SDK_REFERENCE_PAK = _DIST / "vcfcf_sdk_compliance.1.0.0.32.pak"
_MPB_PAK_1 = _DIST / "mpb_synology_nas.1.0.0.1.pak"
_MPB_PAK_2 = _DIST / "mpb_unifi_integration.1.0.0.1.pak"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_adapters_zip(members: list[str]) -> bytes:
    """Build an in-memory adapters.zip containing the given member paths (empty files)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for member in members:
            zf.writestr(member, b"")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Unit tests for _detect_adapter_dir
# ---------------------------------------------------------------------------


class TestDetectAdapterDir:
    """_detect_adapter_dir must correctly identify both Tier 1 and Tier 2 layouts."""

    def test_tier1_adapter3_detected(self) -> None:
        """Tier 1 (MPB): directory ending in _adapter3 is found."""
        members = {
            "mpb_synology_nas_adapter3/conf/describe.xml",
            "mpb_synology_nas_adapter3/conf/export.json",
            "mpb_synology_nas_adapter3/lib/mpb_synology_nas_adapter3.jar",
            "resources/resources.properties",
        }
        result = _detect_adapter_dir(members)
        assert result == "mpb_synology_nas_adapter3"

    def test_tier2_sdk_adapter_detected_by_describe_xml(self) -> None:
        """Tier 2 (SDK): adapter dir found via <adapterkind>/conf/describe.xml pattern."""
        members = {
            "vcfcf_compliance/conf/describe.xml",
            "vcfcf_compliance/conf/version.txt",
            "vcfcf_compliance/lib/vcfcf-adapter-base.jar",
            "vcfcf_compliance.jar",
            "resources/resources.properties",
        }
        result = _detect_adapter_dir(members)
        assert result == "vcfcf_compliance"

    def test_tier1_takes_priority_over_tier2_when_both_patterns_present(self) -> None:
        """If somehow both patterns appear, the _adapter3 pattern wins (Tier 1 first)."""
        members = {
            "mpb_test_adapter3/conf/describe.xml",
            "vcfcf_compliance/conf/describe.xml",
        }
        result = _detect_adapter_dir(members)
        assert result == "mpb_test_adapter3"

    def test_empty_inventory_returns_none(self) -> None:
        """Empty adapters.zip produces None."""
        assert _detect_adapter_dir(set()) is None

    def test_inventory_with_no_recognisable_layout_returns_none(self) -> None:
        """Members with no _adapter3 dir and no conf/describe.xml produce None."""
        members = {
            "resources/resources.properties",
            "manifest.txt",
            "eula.txt",
        }
        assert _detect_adapter_dir(members) is None

    def test_tier2_only_picks_up_from_conf_describe_xml(self) -> None:
        """The fallback only triggers on '<name>/conf/describe.xml', not other paths."""
        members = {
            # describe.xml in a nested location (not the direct conf child) — must be ignored
            "vcfcf_compliance/conf/subdir/describe.xml",
            "resources/resources.properties",
        }
        # len(parts) for 'vcfcf_compliance/conf/subdir/describe.xml'.split('/') == 4, not 3
        assert _detect_adapter_dir(members) is None

    def test_multiple_tier2_dirs_picks_shortest(self) -> None:
        """When multiple SDK adapter dirs are present, the shortest name is returned."""
        members = {
            "vcfcf_abc/conf/describe.xml",
            "vcfcf_abc_extended/conf/describe.xml",
        }
        result = _detect_adapter_dir(members)
        assert result == "vcfcf_abc"


# ---------------------------------------------------------------------------
# Integration tests against real pak files in dist/
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _SDK_FACTORY_PAK.exists() or not _SDK_REFERENCE_PAK.exists(),
    reason="SDK compliance paks not found in dist/ — skipping integration test",
)
class TestSdkAdapterPakCompare:
    """Integration: SDK-adapter pak-compare must not emit a D0 BLOCKING."""

    def test_no_d0_blocking_on_sdk_vs_sdk(self) -> None:
        """[regression] compare_paks on two SDK paks must not emit D0 (factory has no describe.xml)."""
        result = compare_paks(_SDK_FACTORY_PAK, _SDK_REFERENCE_PAK)
        d0_findings = [
            f for f in result.findings
            if f.code == "D0" and "factory has no describe.xml" in f.message
        ]
        assert d0_findings == [], (
            f"False-positive D0 BLOCKING still present: {d0_findings[0].message!r}"
        )

    def test_zero_blockings_sdk_vs_sdk(self) -> None:
        """compare_paks on build 37 vs build 32 must have zero BLOCKINGs."""
        result = compare_paks(_SDK_FACTORY_PAK, _SDK_REFERENCE_PAK)
        blockings = result.blocking()
        assert blockings == [], (
            "Unexpected BLOCKINGs:\n" + "\n".join(f"  {f.message}" for f in blockings)
        )


@pytest.mark.skipif(
    not _MPB_PAK_1.exists() or not _MPB_PAK_2.exists(),
    reason="MPB reference paks not found in dist/ — skipping Tier 1 regression test",
)
class TestTier1RegressionPakCompare:
    """Integration: Tier 1 (MPB) pak-compare must still find describe.xml (no regression)."""

    def test_no_d0_blocking_on_tier1_paks(self) -> None:
        """Tier 1 paks must not emit D0 — describe.xml is found via _adapter3 path."""
        result = compare_paks(_MPB_PAK_1, _MPB_PAK_2)
        d0_findings = [
            f for f in result.findings
            if f.code == "D0" and "factory has no describe.xml" in f.message
        ]
        assert d0_findings == [], (
            f"Regression: D0 BLOCKING appeared on Tier 1 pak: {d0_findings[0].message!r}"
        )
