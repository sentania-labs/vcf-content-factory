"""Localization key length cap — platform XSD maxLength=64 regression.

Bug (root-caused by api-explorer; see the 2026-07-10 addendum in
knowledge/context/investigations/sdk_pak_content_import_gap.md):
``_attribute_to_localization_key`` (both the live copy in
``vcfops_managementpacks.sdk_builder`` and the dormant twin in
``vcfops_dashboards.render``) derived a ``content.properties`` /
Localization ``key=`` value from an attribute path with no length cap. The
platform's ViewDef ``Localization/Locale/Property`` ``key`` attribute has an
XSD ``maxLength=64``. A 69-char key
(``config_policies_override_network_resourcepool_moving_override_allowed``)
failed JAXB unmarshal for that view AND — because our builder colocates
reports and views under the same ``content/reports/`` tree — aborted the
*entire* colocated ReportDef batch (0/11 reports + 4 views dropped on
vcommunity-vsphere build-8).

Fix: cap the derived key at <=64 chars, preserving uniqueness (truncate +
short hash suffix, never blind truncation — two long keys sharing a 64-char
prefix must not collide). Plus a build-time trip-wire in
``_validate_localization_key_contract`` (consumed by ``validate-sdk``) that
fails loudly if any emitted key exceeds 64 chars.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

# The exact 69-char reproduction key from the investigation's 109-view local
# reproduction (Distributed Virtual Portgroup config-policy property).
_REPRO_69_CHAR_KEY = (
    "config_policies_override_network_resourcepool_moving_override_allowed"
)
assert len(_REPRO_69_CHAR_KEY) == 69


class TestSdkBuilderCap:
    def test_repro_key_maps_to_capped_unique_key(self):
        from vcfops_managementpacks.sdk_builder import (
            _attribute_to_localization_key,
            LOCALIZATION_KEY_MAX_LEN,
        )

        capped = _attribute_to_localization_key(_REPRO_69_CHAR_KEY)
        assert len(capped) <= LOCALIZATION_KEY_MAX_LEN
        # Deterministic: same input always maps to the same capped key.
        assert capped == _attribute_to_localization_key(_REPRO_69_CHAR_KEY)

    def test_short_key_passes_through_unchanged(self):
        from vcfops_managementpacks.sdk_builder import _attribute_to_localization_key

        assert _attribute_to_localization_key("cpu|usage_average") == "cpu_usage_average"

    def test_two_long_keys_sharing_64_char_prefix_dont_collide(self):
        from vcfops_managementpacks.sdk_builder import _cap_localization_key

        prefix = "a" * 64
        key_a = prefix + "_variant_one_suffix"
        key_b = prefix + "_variant_two_suffix_different"
        capped_a = _cap_localization_key(key_a)
        capped_b = _cap_localization_key(key_b)
        assert len(capped_a) <= 64
        assert len(capped_b) <= 64
        assert capped_a != capped_b, (
            "Two long keys sharing a 64-char prefix collided after capping — "
            "the hash suffix must diverge based on the FULL original key."
        )

    def test_cap_is_a_noop_at_or_under_max_len(self):
        from vcfops_managementpacks.sdk_builder import _cap_localization_key

        exactly_64 = "x" * 64
        assert _cap_localization_key(exactly_64) == exactly_64


class TestDashboardsRenderCapTwin:
    """The dormant twin in vcfops_dashboards.render must cap identically."""

    def test_repro_key_maps_to_capped_unique_key(self):
        from vcfops_dashboards.render import (
            _attribute_to_localization_key,
            _LOCALIZATION_KEY_MAX_LEN,
        )

        capped = _attribute_to_localization_key(_REPRO_69_CHAR_KEY)
        assert len(capped) <= _LOCALIZATION_KEY_MAX_LEN

    def test_two_long_keys_sharing_64_char_prefix_dont_collide(self):
        from vcfops_dashboards.render import _cap_localization_key

        prefix = "b" * 64
        key_a = prefix + "_one"
        key_b = prefix + "_two_longer_tail"
        assert _cap_localization_key(key_a) != _cap_localization_key(key_b)


class TestBuildTimeGuard:
    """The validate-sdk consumed guard (_validate_localization_key_contract)
    fails loudly if any emitted localization key exceeds 64 chars — even if
    a future code path bypasses the capping helper."""

    def test_guard_trips_on_synthetic_over_long_key(self, monkeypatch, tmp_path: Path):
        from vcfops_managementpacks import sdk_builder

        # Simulate a bypass of the capping helper: patch
        # _attribute_to_localization_key with an UNCAPPED version so the
        # generated content.properties carries a >64-char key, and confirm
        # _validate_localization_key_contract's length guard (Step 5) trips.
        def _uncapped(attribute: str) -> str:
            key = attribute
            if key.startswith("Super Metric|"):
                key = key[len("Super Metric|"):]
            key = key.replace("|", "_").replace(" ", "_")
            return "".join(c for c in key if c.isalnum() or c in "-_")

        monkeypatch.setattr(sdk_builder, "_attribute_to_localization_key", _uncapped)

        view = SimpleNamespace(
            id="11112222-3333-4444-5555-666677778888",
            name="Synthetic Over-Long Key View",
            description="",
            columns=[
                SimpleNamespace(
                    attribute=_REPRO_69_CHAR_KEY,
                    display_name="Whatever",
                )
            ],
        )

        # _validate_localization_key_contract also renders the view XML via
        # vcfops_dashboards.render.render_views_xml, which needs a real
        # ViewDef — but the length guard (Step 5) only inspects
        # props_suffixes derived from _generate_view_content_properties(view),
        # which only touches view.id/name/description/columns. We bypass the
        # XML-rendering step by monkeypatching render_views_xml to a no-op
        # returning empty XML, isolating the length-guard behavior under test.
        import vcfops_dashboards.render as dash_render

        monkeypatch.setattr(dash_render, "render_views_xml", lambda views, sm_scope=None: "")

        errors = sdk_builder._validate_localization_key_contract([view])
        assert any("localization-key-too-long" in e for e in errors), errors
        assert any(str(len(_REPRO_69_CHAR_KEY)) in e for e in errors), errors

    def test_guard_silent_when_keys_are_capped(self, tmp_path: Path, monkeypatch):
        """Sanity: with the real (capped) _attribute_to_localization_key, the
        same reproduction attribute produces NO length-guard error."""
        from vcfops_managementpacks import sdk_builder
        import vcfops_dashboards.render as dash_render

        monkeypatch.setattr(dash_render, "render_views_xml", lambda views, sm_scope=None: "")

        view = SimpleNamespace(
            id="11112222-3333-4444-5555-666677778888",
            name="Synthetic Capped Key View",
            description="",
            columns=[
                SimpleNamespace(
                    attribute=_REPRO_69_CHAR_KEY,
                    display_name="Whatever",
                )
            ],
        )
        errors = sdk_builder._validate_localization_key_contract([view])
        assert not any("localization-key-too-long" in e for e in errors), errors
