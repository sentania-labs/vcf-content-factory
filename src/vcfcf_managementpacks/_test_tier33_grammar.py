"""Tier 3.3 grammar test suite.

Tests all five grammar changes in one cohesive script:
  Change 1 — Relationship predicate scopes (scope: field_match / adapter_instance)
  Change 2 — Identifier schema structured form
  Change 3 — Name expression parts grammar
  Change 4 — Metric source structured form
  Change 5 — World-object identity tier

Also tests the render_export.py chainingSettings preservation fix.

Usage:
    python3 -m vcfops_managementpacks._test_tier33_grammar

All tests are self-contained (no external files required) and clean up
after themselves.  Exit code 0 = all passed, non-zero = failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


_failures: list[str] = []


def _load_yaml_str(yaml_str: str):
    """Load a YAML string through the MP loader (validates on load)."""
    from vcfops_managementpacks.loader import load_file

    with tempfile.NamedTemporaryFile(
        suffix=".yaml", mode="w", delete=False
    ) as fh:
        fh.write(textwrap.dedent(yaml_str))
        tmp = Path(fh.name)
    try:
        return load_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def expect_ok(name: str, yaml_str: str):
    """Assert that loading YAML succeeds."""
    try:
        mp = _load_yaml_str(yaml_str)
        print(f"  {PASS}  {name}")
        return mp
    except Exception as exc:
        print(f"  {FAIL}  {name}")
        print(f"         Expected success but got: {exc}")
        _failures.append(name)
        return None


def expect_error(name: str, yaml_str: str, fragment: str):
    """Assert that loading YAML raises an error containing fragment."""
    try:
        _load_yaml_str(yaml_str)
        print(f"  {FAIL}  {name}")
        print(f"         Expected error containing {fragment!r} but no error was raised")
        _failures.append(name)
    except Exception as exc:
        msg = str(exc)
        if fragment.lower() in msg.lower():
            print(f"  {PASS}  {name}")
        else:
            print(f"  {FAIL}  {name}")
            print(f"         Expected fragment {fragment!r} in error, got: {msg!r}")
            _failures.append(name)


# ---------------------------------------------------------------------------
# Shared YAML blocks
# ---------------------------------------------------------------------------

_AUTH_BLOCK = """
  auth:
    preset: none
"""

_SOURCE_BLOCK = """
source:
  port: 443
  ssl: NO_VERIFY
  base_path: "api"
  timeout: 30
  max_retries: 2
  max_concurrent: 10
  auth:
    preset: none
"""

_REQUESTS_BLOCK = """
requests:
  - name: system_info
    method: GET
    path: "system"
    response_path: "data"
  - name: item_list
    method: GET
    path: "items"
    response_path: "data"
  - name: component_list
    method: GET
    path: "components"
    response_path: "data"
"""

# ---------------------------------------------------------------------------
# Full positive fixture (exercises ALL five changes simultaneously)
# ---------------------------------------------------------------------------

_FULL_POSITIVE_FIXTURE = """\
name: "Test Option C Full"
version: "1.0.0"
description: "Tier 3.3 grammar positive test fixture"
adapter_kind: "mpb_test_option_c_full"
author: "tooling-test"

{source}

{requests}

object_types:
  # --- World object: uses identity:, structured identifiers, shorthand name_expression ---
  - name: "System"
    key: system
    type: INTERNAL
    is_world: true
    identifiers:
      - key: serial
        source: "metricset:system_info.serial"
    identity:
      tier: system_issued
      source: "metricset:system_info.serial"
    name_expression: model
    metricSets:
      - from_request: system_info
        list_path: ""
    metrics:
      - key: serial
        label: "Serial Number"
        usage: PROPERTY
        type: STRING
        source: "metricset:system_info.serial"
      - key: model
        label: "Model"
        usage: PROPERTY
        type: STRING
        source:
          metricset: system_info
          path: model

  # --- List object: chained metricSet, structured identifiers, parts name_expression ---
  - name: "Item"
    key: item
    type: INTERNAL
    is_world: false
    identifiers:
      - key: item_id
        source: "metricset:item_list.id"
      - item_path
    name_expression:
      parts:
        - metric: item_id
    metricSets:
      - from_request: item_list
        primary: true
        list_path: "items"
    metrics:
      - key: item_id
        label: "Item ID"
        usage: PROPERTY
        type: STRING
        source: "metricset:item_list.id"
      - key: item_path
        label: "Item Path"
        usage: PROPERTY
        type: STRING
        source:
          metricset: item_list
          path: path
      - key: item_load
        label: "Item Load"
        usage: METRIC
        type: NUMBER
        source: "metricset:item_list.load"

  # --- Second list object: for field_match relationship ---
  - name: "Component"
    key: component
    type: INTERNAL
    is_world: false
    identifiers: [comp_id]
    name_expression: comp_id
    metricSets:
      - from_request: component_list
        primary: true
        list_path: "components"
    metrics:
      - key: comp_id
        label: "Component ID"
        usage: PROPERTY
        type: STRING
        source: "metricset:component_list.id"
      - key: item_ref
        label: "Item Reference"
        usage: PROPERTY
        type: STRING
        source: "metricset:component_list.item_id"

relationships:
  # Change 1a: scope: adapter_instance (no expressions)
  - parent: system
    child: item
    scope: adapter_instance

  # Change 1b: scope: field_match (both expressions present)
  - parent: item
    child: component
    scope: field_match
    child_expression: item_ref
    parent_expression: item_id

content:
  dashboards: []
  views: []
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)


# ---------------------------------------------------------------------------
# Test sections
# ---------------------------------------------------------------------------

def test_positive_fixture():
    print("\n[Positive fixture — all 5 changes]")
    mp = expect_ok("Full positive fixture loads and validates", _FULL_POSITIVE_FIXTURE)
    if mp is None:
        return

    # Verify AST structure
    assert mp.adapter_kind == "mpb_test_option_c_full"

    # Change 2: structured identifiers
    system_ot = next(o for o in mp.object_types if o.key == "system")
    assert len(system_ot.identifiers) == 1
    assert system_ot.identifiers[0].key == "serial"
    assert system_ot.identifiers[0].source == "metricset:system_info.serial"
    print(f"  {PASS}  Change 2: IdentifierDef.source parsed correctly")

    item_ot = next(o for o in mp.object_types if o.key == "item")
    assert len(item_ot.identifiers) == 2
    assert item_ot.identifiers[0].key == "item_id"
    assert item_ot.identifiers[0].source == "metricset:item_list.id"
    assert item_ot.identifiers[1].key == "item_path"
    assert item_ot.identifiers[1].source is None  # shorthand form
    print(f"  {PASS}  Change 2: shorthand identifier parses to source=None")

    # Change 3: name expression
    assert system_ot.name_expression is not None
    assert len(system_ot.name_expression.parts) == 1
    assert system_ot.name_expression.parts[0].metric == "model"
    print(f"  {PASS}  Change 3: shorthand name_expression → single NamePartDef(metric=model)")

    assert item_ot.name_expression is not None
    assert len(item_ot.name_expression.parts) == 1
    assert item_ot.name_expression.parts[0].metric == "item_id"
    print(f"  {PASS}  Change 3: parts form name_expression → NamePartDef(metric=item_id)")

    # Change 4: metric source structured form
    model_metric = next(m for m in system_ot.metrics if m.key == "model")
    assert model_metric.source.metricset == "system_info"
    assert model_metric.source.path == "model"
    print(f"  {PASS}  Change 4: structured source parsed to MetricSourceDef")

    serial_metric = next(m for m in system_ot.metrics if m.key == "serial")
    assert serial_metric.source.metricset == "system_info"
    assert serial_metric.source.path == "serial"
    print(f"  {PASS}  Change 4: shorthand source parsed to MetricSourceDef")

    # Change 5: world identity
    assert system_ot.identity is not None
    assert system_ot.identity.tier == "system_issued"
    assert system_ot.identity.source == "metricset:system_info.serial"
    print(f"  {PASS}  Change 5: WorldIdentityDef parsed correctly")

    # Change 1: relationship scopes
    rels = {(r.parent, r.child): r for r in mp.relationships}
    assert rels[("system", "item")].scope == "adapter_instance"
    assert rels[("system", "item")].child_expression is None
    assert rels[("item", "component")].scope == "field_match"
    assert rels[("item", "component")].child_expression == "item_ref"
    print(f"  {PASS}  Change 1: relationship scopes parsed correctly")


def test_change1_negative():
    print("\n[Change 1 — Relationship scope negative tests]")

    # adapter_instance with child_expression → error
    yaml = """\
name: "Bad Rel"
version: "1.0.0"
adapter_kind: "mpb_bad_rel"
{source}
{requests}
object_types:
  - name: "World"
    key: world
    type: INTERNAL
    is_world: true
    identifiers: [wid]
    identity:
      tier: system_issued
      source: "metricset:system_info.wid"
    name_expression: wid
    metricSets:
      - from_request: system_info
    metrics:
      - key: wid
        label: WID
        usage: PROPERTY
        type: STRING
        source: "metricset:system_info.wid"
  - name: "Child"
    key: child
    type: INTERNAL
    is_world: false
    identifiers: [cid]
    name_expression: cid
    metricSets:
      - from_request: item_list
        primary: true
        list_path: items
    metrics:
      - key: cid
        label: CID
        usage: PROPERTY
        type: STRING
        source: "metricset:item_list.id"
relationships:
  - parent: world
    child: child
    scope: adapter_instance
    child_expression: cid
    parent_expression: wid
content: {{}}
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)
    expect_error(
        "adapter_instance + child_expression → error",
        yaml,
        "adapter_instance",
    )

    # field_match without both expressions → error
    yaml2 = """\
name: "Bad Rel2"
version: "1.0.0"
adapter_kind: "mpb_bad_rel2"
{source}
{requests}
object_types:
  - name: "World"
    key: world
    type: INTERNAL
    is_world: true
    identifiers: [wid]
    identity:
      tier: system_issued
      source: "metricset:system_info.wid"
    name_expression: wid
    metricSets:
      - from_request: system_info
    metrics:
      - key: wid
        label: WID
        usage: PROPERTY
        type: STRING
        source: "metricset:system_info.wid"
  - name: "Child"
    key: child
    type: INTERNAL
    is_world: false
    identifiers: [cid]
    name_expression: cid
    metricSets:
      - from_request: item_list
        primary: true
        list_path: items
    metrics:
      - key: cid
        label: CID
        usage: PROPERTY
        type: STRING
        source: "metricset:item_list.id"
relationships:
  - parent: world
    child: child
    scope: field_match
    child_expression: cid
content: {{}}
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)
    expect_error(
        "field_match without parent_expression → error",
        yaml2,
        "field_match",
    )


def test_change2_negative():
    print("\n[Change 2 — Identifier schema negative tests]")

    # derive → reserved error
    yaml = """\
name: "Bad Ident"
version: "1.0.0"
adapter_kind: "mpb_bad_ident"
{source}
{requests}
object_types:
  - name: "World"
    key: world
    type: INTERNAL
    is_world: true
    identifiers:
      - key: x
        derive:
          expression: "${{serial}}-${{slot}}"
    identity:
      tier: system_issued
      source: "metricset:system_info.serial"
    name_expression: serial
    metricSets:
      - from_request: system_info
    metrics:
      - key: serial
        label: Serial
        usage: PROPERTY
        type: STRING
        source: "metricset:system_info.serial"
content: {{}}
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)
    expect_error(
        "identifier derive: → reserved error",
        yaml,
        "reserved",
    )


def test_change3_negative():
    print("\n[Change 3 — Name expression parts grammar negative tests]")

    # Empty parts list → error
    yaml = """\
name: "Bad Name Expr"
version: "1.0.0"
adapter_kind: "mpb_bad_name_expr"
{source}
{requests}
object_types:
  - name: "World"
    key: world
    type: INTERNAL
    is_world: true
    identifiers: [serial]
    identity:
      tier: system_issued
      source: "metricset:system_info.serial"
    name_expression:
      parts: []
    metricSets:
      - from_request: system_info
    metrics:
      - key: serial
        label: Serial
        usage: PROPERTY
        type: STRING
        source: "metricset:system_info.serial"
content: {{}}
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)
    expect_error(
        "name_expression.parts: [] → at least one part required",
        yaml,
        "at least one part",
    )


def test_change4_negative():
    print("\n[Change 4 — Metric source structured form negative tests]")

    # aggregate → reserved error
    yaml = """\
name: "Bad Source"
version: "1.0.0"
adapter_kind: "mpb_bad_source"
{source}
{requests}
object_types:
  - name: "World"
    key: world
    type: INTERNAL
    is_world: true
    identifiers: [serial]
    identity:
      tier: system_issued
      source: "metricset:system_info.serial"
    name_expression: serial
    metricSets:
      - from_request: system_info
    metrics:
      - key: serial
        label: Serial
        usage: PROPERTY
        type: STRING
        source:
          metricset: system_info
          path: serial
          aggregate: sum
content: {{}}
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)
    expect_error(
        "source.aggregate → reserved error",
        yaml,
        "reserved",
    )


def test_change5_negative():
    print("\n[Change 5 — World-object identity tier negative tests]")

    # is_world: true without identity: → error
    yaml = """\
name: "No Identity"
version: "1.0.0"
adapter_kind: "mpb_no_identity"
{source}
{requests}
object_types:
  - name: "World"
    key: world
    type: INTERNAL
    is_world: true
    identifiers: [serial]
    name_expression: serial
    metricSets:
      - from_request: system_info
    metrics:
      - key: serial
        label: Serial
        usage: PROPERTY
        type: STRING
        source: "metricset:system_info.serial"
content: {{}}
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)
    expect_error(
        "is_world: true without identity: → error",
        yaml,
        "identity",
    )

    # is_world: false with identity: → error
    yaml2 = """\
name: "Bad Identity"
version: "1.0.0"
adapter_kind: "mpb_bad_identity"
{source}
{requests}
object_types:
  - name: "World"
    key: world
    type: INTERNAL
    is_world: true
    identifiers: [serial]
    identity:
      tier: system_issued
      source: "metricset:system_info.serial"
    name_expression: serial
    metricSets:
      - from_request: system_info
    metrics:
      - key: serial
        label: Serial
        usage: PROPERTY
        type: STRING
        source: "metricset:system_info.serial"
  - name: "Child"
    key: child
    type: INTERNAL
    is_world: false
    identifiers: [cid]
    identity:
      tier: system_issued
      source: "metricset:item_list.id"
    name_expression: cid
    metricSets:
      - from_request: item_list
        primary: true
        list_path: items
    metrics:
      - key: cid
        label: CID
        usage: PROPERTY
        type: STRING
        source: "metricset:item_list.id"
content: {{}}
""".format(source=_SOURCE_BLOCK, requests=_REQUESTS_BLOCK)
    expect_error(
        "is_world: false with identity: → error",
        yaml2,
        "must not declare",
    )


def test_render_positive():
    print("\n[Renderer — positive fixture round-trip]")
    from vcfops_managementpacks.render import render_mp_design_json

    mp = _load_yaml_str(_FULL_POSITIVE_FIXTURE)
    try:
        design = render_mp_design_json(mp)
        # Check basic structure
        assert "source" in design
        assert "relationships" in design
        src = design["source"]
        assert "requests" in src
        assert "resources" in src

        # Change 1a: adapter_instance relationship → should produce a relationship
        # (synthetic_adapter_instance strategy) or be present
        # (current renderer uses _render_trivial_relationships)
        # Regardless: design must be a valid dict
        rels = design["relationships"]
        assert isinstance(rels, list), "relationships must be a list"
        # field_match relationship (item → component) should appear
        field_match_rels = [
            r for r in rels
            if "item" in r.get("name", "") and "component" in r.get("name", "")
        ]
        assert len(field_match_rels) >= 1, (
            f"Expected at least one item→component relationship, got: {[r.get('name') for r in rels]}"
        )
        print(f"  {PASS}  Renderer produces valid design JSON")
        print(f"  {PASS}  field_match relationship present in output")

        # adapter_instance relationship also present (synthetic strategy)
        adapter_rels = [
            r for r in rels
            if "system" in r.get("name", "") and "item" in r.get("name", "")
        ]
        assert len(adapter_rels) >= 1, (
            f"Expected adapter_instance relationship, got: {[r.get('name') for r in rels]}"
        )
        print(f"  {PASS}  adapter_instance relationship present in output")

    except NotImplementedError as exc:
        # Multi-part name_expression raises NotImplementedError — that's expected
        # for multi-metric parts. Our fixture uses single-metric parts so this
        # should not fire.
        print(f"  {FAIL}  Renderer raised NotImplementedError: {exc}")
        _failures.append("Renderer positive fixture")
    except Exception as exc:
        print(f"  {FAIL}  Renderer raised unexpected error: {exc}")
        _failures.append("Renderer positive fixture")


def test_render_export_chaining_preserved():
    print("\n[render_export — chainingSettings preserved (cleanup fix)]")
    from vcfops_managementpacks.render_export import render_mpb_exchange_json

    # Build a minimal MP with a chained metricSet
    yaml_chained = """\
name: "Chained Export Test"
version: "1.0.0"
adapter_kind: "mpb_chained_export_test"

{source}

requests:
  - name: pool_list
    method: GET
    path: "pools"
    response_path: "data"
  - name: volume_list
    method: GET
    path: "volumes"
    params:
      - key: pool_id
        value: "${{chain.pool_id}}"
    response_path: "data"

object_types:
  - name: "System"
    key: system
    type: INTERNAL
    is_world: true
    identifiers: [serial]
    identity:
      tier: system_issued
      source: "metricset:pool_list.serial"
    name_expression: serial
    metricSets:
      - from_request: pool_list
    metrics:
      - key: serial
        label: Serial
        usage: PROPERTY
        type: STRING
        source: "metricset:pool_list.serial"

  - name: "Volume"
    key: volume
    type: INTERNAL
    is_world: false
    identifiers: [vol_id]
    name_expression: vol_id
    metricSets:
      - from_request: pool_list
        primary: true
        list_path: pools
      - from_request: volume_list
        chained_from: pool_list
        list_path: volumes
        bind:
          - name: pool_id
            from_attribute: id
    metrics:
      - key: vol_id
        label: "Volume ID"
        usage: PROPERTY
        type: STRING
        source: "metricset:volume_list.id"
      - key: vol_size
        label: "Volume Size"
        usage: METRIC
        type: NUMBER
        source: "metricset:volume_list.size"

relationships: []
content: {{}}
""".format(source=_SOURCE_BLOCK)

    try:
        mp = _load_yaml_str(yaml_chained)
        exchange = render_mpb_exchange_json(mp)

        # Find the chained request (volume_list) in the exchange requests list
        chained_req = None
        for item in exchange.get("requests", []):
            r = item.get("request", {})
            if r.get("name") == "volume_list":
                chained_req = r
                break

        if chained_req is None:
            print(f"  {FAIL}  volume_list request not found in exchange requests")
            _failures.append("render_export chainingSettings preserved")
            return

        # chainingSettings must be present (not stripped)
        assert "chainingSettings" in chained_req, (
            f"chainingSettings was stripped from exchange format! "
            f"Keys present: {list(chained_req.keys())}"
        )
        cs = chained_req["chainingSettings"]
        assert cs is not None, "chainingSettings should be non-null for a chained request"
        assert "parentRequestId" in cs, f"chainingSettings missing parentRequestId: {cs}"
        assert "baseListId" in cs, f"chainingSettings missing baseListId: {cs}"
        assert "params" in cs, f"chainingSettings missing params: {cs}"
        print(f"  {PASS}  chainingSettings preserved in exchange format (not stripped)")
        print(f"  {PASS}  chainingSettings.parentRequestId present")
        print(f"  {PASS}  chainingSettings.baseListId = {cs['baseListId']!r}")
        print(f"  {PASS}  chainingSettings.params count = {len(cs['params'])}")

        # Also confirm pool_list (non-chained) has chainingSettings: null
        pool_req = None
        for item in exchange.get("requests", []):
            r = item.get("request", {})
            if r.get("name") == "pool_list":
                pool_req = r
                break
        if pool_req is not None:
            # Non-chained: chainingSettings should be null (or absent)
            cs_pool = pool_req.get("chainingSettings")
            assert cs_pool is None, (
                f"Non-chained request pool_list should have chainingSettings=null, "
                f"got {cs_pool!r}"
            )
            print(f"  {PASS}  Non-chained request has chainingSettings=null")

    except Exception as exc:
        print(f"  {FAIL}  Unexpected error: {exc}")
        import traceback
        traceback.print_exc()
        _failures.append("render_export chainingSettings preserved")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Tier 3.3 Grammar Test Suite")
    print("=" * 60)

    test_positive_fixture()
    test_change1_negative()
    test_change2_negative()
    test_change3_negative()
    test_change4_negative()
    test_change5_negative()
    test_render_positive()
    test_render_export_chaining_preserved()

    print("\n" + "=" * 60)
    if _failures:
        print(f"RESULT: {len(_failures)} FAILED:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        total = 0  # count from output is approximate
        print("RESULT: ALL TESTS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
