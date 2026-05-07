"""Tests for Gap B (multi-value extract), Gap F (JMESPath filter predicates),
and Gap D (type coercion hint) in vcfops_managementpacks.

Gap B — multi-value extract on auth.extract (2026-04-30):
  - Single-mapping form (Synology-style) still works.
  - List-of-mappings form (UniFi-style) works and produces multiple
    sessionVariables entries in the render output.
  - Duplicate bind_to keys are rejected.
  - Empty list is rejected.

Gap F — JMESPath filter predicates in metric source paths (2026-04-30):
  - Paths with [?...] predicates parse and validate without error.
  - Paths with hyphenated field names after predicates (e.g. tx_bytes-r) pass.
  - Malformed predicates (single =, unclosed bracket) are rejected.
  - Paths without predicates still split on '.' as before (regression).
  - Rendered attribute key is a single-element list for predicate paths.

Gap D — type coerce hint (2026-04-30):
  - coerce: number is accepted on a NUMBER metric.
  - coerce: number on a STRING metric is rejected.
  - Unknown coerce values are rejected.
  - Metrics without coerce still work (backward compat).
  - coerce: number + JMESPath predicate combo is accepted (mutex-pass).

Regression — Synology NAS YAML:
  - validate passes (session variable rendered as single-element list).
  - render produces sessionVariables with exactly 1 entry.
  - render produces identical IDs on repeated calls (determinism).
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from vcfops_managementpacks.loader import (
    ManagementPackValidationError,
    load_file,
)
from vcfops_managementpacks.render import render_mp_design_json

# ---------------------------------------------------------------------------
# Repository root (for loading production YAML)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# YAML fixture builders
# ---------------------------------------------------------------------------


def _write_and_load(tmp_path: Path, yaml_text: str):
    """Write yaml_text to a temp file and load+validate it."""
    p = tmp_path / "test_mp.yaml"
    p.write_text(textwrap.dedent(yaml_text), encoding="utf-8")
    return load_file(p)


# A single-extract cookie_session MP.  inject only references token_cookie.
_SINGLE_EXTRACT_YAML = """\
    name: Single Extract MP
    version: 1.0.0
    build_number: 1
    author: test
    adapter_kind: mpb_single_extract
    description: Single extract test
    source:
      port: 443
      ssl: NO_VERIFY
      base_path: api
      timeout: 30
      max_retries: 2
      max_concurrent: 10
      auth:
        preset: cookie_session
        credentials:
          - {key: username, label: username, sensitive: false}
          - {key: password, label: password, sensitive: true}
        login:
          method: POST
          path: auth/login
          body: '{"username": "${credentials.username}", "password": "${credentials.password}"}'
        extract:
          location: HEADER
          name: Set-Cookie
          bind_to: session.token_cookie
        inject:
          - type: header
            name: Cookie
            value: "${session.token_cookie}"
        logout:
          method: POST
          path: auth/logout
    requests:
      - name: sysinfo
        method: GET
        path: stat/sysinfo
        response_path: data
    object_types:
      - name: Controller
        key: controller
        type: INTERNAL
        is_singleton: true
        name_expression: hostname
        identifiers:
          - key: hostname
            source: "metricset:sysinfo.hostname"
        metricSets:
          - from_request: sysinfo
        metrics:
          - key: hostname
            label: Hostname
            usage: PROPERTY
            type: STRING
            source: "metricset:sysinfo.hostname"
"""

# A dual-extract cookie_session MP.  inject references BOTH token_cookie and csrf_token.
_DUAL_EXTRACT_YAML = """\
    name: Dual Extract MP
    version: 1.0.0
    build_number: 1
    author: test
    adapter_kind: mpb_dual_extract
    description: Dual extract test
    source:
      port: 443
      ssl: NO_VERIFY
      base_path: api
      timeout: 30
      max_retries: 2
      max_concurrent: 10
      auth:
        preset: cookie_session
        credentials:
          - {key: username, label: username, sensitive: false}
          - {key: password, label: password, sensitive: true}
        login:
          method: POST
          path: auth/login
          body: '{"username": "${credentials.username}", "password": "${credentials.password}"}'
        extract:
          - location: HEADER
            name: Set-Cookie
            bind_to: session.token_cookie
          - location: HEADER
            name: x-csrf-token
            bind_to: session.csrf_token
        inject:
          - type: header
            name: Cookie
            value: "${session.token_cookie}"
          - type: header
            name: x-csrf-token
            value: "${session.csrf_token}"
        logout:
          method: POST
          path: auth/logout
    requests:
      - name: sysinfo
        method: GET
        path: stat/sysinfo
        response_path: data
    object_types:
      - name: Controller
        key: controller
        type: INTERNAL
        is_singleton: true
        name_expression: hostname
        identifiers:
          - key: hostname
            source: "metricset:sysinfo.hostname"
        metricSets:
          - from_request: sysinfo
        metrics:
          - key: hostname
            label: Hostname
            usage: PROPERTY
            type: STRING
            source: "metricset:sysinfo.hostname"
"""


def _jmespath_mp_yaml(metric_source: str, metric_key: str = "test_metric") -> str:
    """Build a minimal singleton MP with a metric using a given source path.

    Uses a none-auth preset to avoid cookie_session complexity.
    The identifier uses a plain dotted path; the metric uses the given source.
    """
    return f"""\
        name: JMESPath Test MP
        version: 1.0.0
        build_number: 1
        author: test
        adapter_kind: mpb_jmespath_test
        description: JMESPath predicate test
        source:
          port: 443
          ssl: NO_VERIFY
          base_path: api
          timeout: 30
          max_retries: 2
          max_concurrent: 10
          auth:
            preset: none
        requests:
          - name: site_health
            method: GET
            path: stat/health
            response_path: data
        object_types:
          - name: Site
            key: site
            type: INTERNAL
            is_singleton: true
            name_expression: site_id
            identifiers:
              - key: site_id
                source: "metricset:site_health.site_id"
            metricSets:
              - from_request: site_health
            metrics:
              - key: site_id
                label: Site ID
                usage: PROPERTY
                type: STRING
                source: "metricset:site_health.site_id"
              - key: {metric_key}
                label: Test Metric
                usage: METRIC
                type: NUMBER
                source: "{metric_source}"
    """


def _coerce_mp_yaml(metric_type: str, coerce_line: str = "", usage: str = "METRIC") -> str:
    """Build a minimal singleton MP with a coerce hint on one metric.

    usage defaults to METRIC; pass "PROPERTY" to test coerce on STRING usage
    without triggering the separate METRIC-requires-NUMBER guard.
    """
    return f"""\
        name: Coerce Test MP
        version: 1.0.0
        build_number: 1
        author: test
        adapter_kind: mpb_coerce_test
        description: Coerce hint test
        source:
          port: 443
          ssl: NO_VERIFY
          base_path: api
          timeout: 30
          max_retries: 2
          max_concurrent: 10
          auth:
            preset: none
        requests:
          - name: sysinfo
            method: GET
            path: stat/sysinfo
            response_path: data
        object_types:
          - name: Controller
            key: controller
            type: INTERNAL
            is_singleton: true
            name_expression: hostname
            identifiers:
              - key: hostname
                source: "metricset:sysinfo.hostname"
            metricSets:
              - from_request: sysinfo
            metrics:
              - key: hostname
                label: Hostname
                usage: PROPERTY
                type: STRING
                source: "metricset:sysinfo.hostname"
              - key: cpu_pct
                label: CPU %
                usage: {usage}
                type: {metric_type}
                source: "metricset:sysinfo.cpu_pct"
                {coerce_line}
    """


# ---------------------------------------------------------------------------
# Gap B: multi-value extract
# ---------------------------------------------------------------------------


class TestGapBSingleMapping:
    """Backward compatibility: single-mapping extract still works."""

    def test_single_mapping_loads(self, tmp_path: Path) -> None:
        mp = _write_and_load(tmp_path, _SINGLE_EXTRACT_YAML)
        assert mp.source is not None
        assert mp.source.auth is not None
        extract_list = mp.source.auth.extract
        assert extract_list is not None
        assert isinstance(extract_list, list)
        assert len(extract_list) == 1
        assert extract_list[0].location == "HEADER"
        assert extract_list[0].name == "Set-Cookie"
        assert extract_list[0].session_key == "token_cookie"

    def test_single_mapping_renders_one_session_variable(
        self, tmp_path: Path
    ) -> None:
        mp = _write_and_load(tmp_path, _SINGLE_EXTRACT_YAML)
        design = render_mp_design_json(mp)
        sv = (
            design["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        )
        assert len(sv) == 1
        assert sv[0]["key"] == "token_cookie"
        assert sv[0]["path"] == ["Set-Cookie"]
        assert sv[0]["location"] == "HEADER"
        assert sv[0]["usage"] == "${authentication.session.token_cookie}"


class TestGapBMultiMapping:
    """New list-of-mappings form for UniFi-style dual-capture."""

    def test_two_extract_bindings_load(self, tmp_path: Path) -> None:
        mp = _write_and_load(tmp_path, _DUAL_EXTRACT_YAML)
        extract_list = mp.source.auth.extract
        assert isinstance(extract_list, list)
        assert len(extract_list) == 2
        assert extract_list[0].session_key == "token_cookie"
        assert extract_list[0].name == "Set-Cookie"
        assert extract_list[1].session_key == "csrf_token"
        assert extract_list[1].name == "x-csrf-token"

    def test_two_extract_bindings_render_two_session_variables(
        self, tmp_path: Path
    ) -> None:
        mp = _write_and_load(tmp_path, _DUAL_EXTRACT_YAML)
        design = render_mp_design_json(mp)
        sv = design["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        assert len(sv) == 2

        keys = {entry["key"] for entry in sv}
        assert keys == {"token_cookie", "csrf_token"}

        by_key = {entry["key"]: entry for entry in sv}
        assert by_key["token_cookie"]["path"] == ["Set-Cookie"]
        assert by_key["token_cookie"]["location"] == "HEADER"
        assert by_key["csrf_token"]["path"] == ["x-csrf-token"]
        assert by_key["csrf_token"]["location"] == "HEADER"
        assert by_key["csrf_token"]["usage"] == "${authentication.session.csrf_token}"

    def test_two_bindings_session_variable_ids_are_stable(
        self, tmp_path: Path
    ) -> None:
        """Same YAML must produce identical IDs on repeated renders (determinism)."""
        mp = _write_and_load(tmp_path, _DUAL_EXTRACT_YAML)
        design1 = render_mp_design_json(mp)
        design2 = render_mp_design_json(mp)
        sv1 = design1["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        sv2 = design2["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        assert sv1 == sv2

    def test_two_bindings_ids_are_distinct(self, tmp_path: Path) -> None:
        """Each session variable entry must have a unique ID."""
        mp = _write_and_load(tmp_path, _DUAL_EXTRACT_YAML)
        design = render_mp_design_json(mp)
        sv = design["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        ids = [entry["id"] for entry in sv]
        assert len(set(ids)) == len(ids), "Session variable IDs must be distinct"

    def test_login_body_credentials_fully_scoped(self, tmp_path: Path) -> None:
        """${credentials.X} in the login body must be rewritten to
        ${authentication.credentials.X} — bare ${credentials.X} causes
        MPB runtime to ship the literal string and get 403."""
        mp = _write_and_load(tmp_path, _DUAL_EXTRACT_YAML)
        design = render_mp_design_json(mp)
        body = design["source"]["authentication"]["sessionSettings"]["getSession"]["body"]
        assert "${credentials." not in body, (
            f"Bare ${{credentials.X}} found in rendered login body: {body!r}"
        )
        assert "${authentication.credentials.username}" in body
        assert "${authentication.credentials.password}" in body

    def test_inject_headers_session_refs_fully_scoped(self, tmp_path: Path) -> None:
        """${session.X} in inject values must be rewritten to
        ${authentication.session.X} when rendered via _render_global_headers."""
        from vcfops_managementpacks.render import _render_global_headers
        mp = _write_and_load(tmp_path, _DUAL_EXTRACT_YAML)
        headers = _render_global_headers(mp)
        for h in headers:
            value = h.get("value", "")
            assert "${session." not in value, (
                f"Bare ${{session.X}} found in rendered header {h['key']!r}: {value!r}"
            )
        # Confirm the full-scoped form is present for the cookie header
        cookie_header = next((h for h in headers if h["key"] == "Cookie"), None)
        assert cookie_header is not None
        assert "${authentication.session.token_cookie}" in cookie_header["value"]

    def test_duplicate_bind_to_rejected(self, tmp_path: Path) -> None:
        yaml_text = """\
            name: Dup Extract MP
            version: 1.0.0
            build_number: 1
            author: test
            adapter_kind: mpb_dup_extract
            description: Duplicate extract test
            source:
              port: 443
              ssl: NO_VERIFY
              base_path: api
              timeout: 30
              max_retries: 2
              max_concurrent: 10
              auth:
                preset: cookie_session
                credentials:
                  - {key: username, label: username, sensitive: false}
                  - {key: password, label: password, sensitive: true}
                login:
                  method: POST
                  path: auth/login
                extract:
                  - location: HEADER
                    name: Set-Cookie
                    bind_to: session.token_cookie
                  - location: HEADER
                    name: x-csrf-token
                    bind_to: session.token_cookie
                inject:
                  - type: header
                    name: Cookie
                    value: "${session.token_cookie}"
                logout:
                  method: POST
                  path: auth/logout
            requests:
              - name: sysinfo
                method: GET
                path: stat/sysinfo
                response_path: data
            object_types:
              - name: Controller
                key: controller
                type: INTERNAL
                is_singleton: true
                name_expression: hostname
                identifiers:
                  - key: hostname
                    source: "metricset:sysinfo.hostname"
                metricSets:
                  - from_request: sysinfo
                metrics:
                  - key: hostname
                    label: Hostname
                    usage: PROPERTY
                    type: STRING
                    source: "metricset:sysinfo.hostname"
        """
        with pytest.raises(ManagementPackValidationError, match="duplicate bind_to"):
            _write_and_load(tmp_path, yaml_text)

    def test_empty_extract_list_rejected(self, tmp_path: Path) -> None:
        yaml_text = """\
            name: Empty Extract MP
            version: 1.0.0
            build_number: 1
            author: test
            adapter_kind: mpb_empty_extract
            description: Empty extract list test
            source:
              port: 443
              ssl: NO_VERIFY
              base_path: api
              timeout: 30
              max_retries: 2
              max_concurrent: 10
              auth:
                preset: cookie_session
                credentials:
                  - {key: username, label: username, sensitive: false}
                  - {key: password, label: password, sensitive: true}
                login:
                  method: POST
                  path: auth/login
                extract: []
                inject:
                  - type: header
                    name: Cookie
                    value: "${session.token_cookie}"
                logout:
                  method: POST
                  path: auth/logout
            requests:
              - name: sysinfo
                method: GET
                path: stat/sysinfo
                response_path: data
            object_types:
              - name: Controller
                key: controller
                type: INTERNAL
                is_singleton: true
                name_expression: hostname
                identifiers:
                  - key: hostname
                    source: "metricset:sysinfo.hostname"
                metricSets:
                  - from_request: sysinfo
                metrics:
                  - key: hostname
                    label: Hostname
                    usage: PROPERTY
                    type: STRING
                    source: "metricset:sysinfo.hostname"
        """
        with pytest.raises(ManagementPackValidationError, match="must not be empty"):
            _write_and_load(tmp_path, yaml_text)

    def test_missing_bind_to_rejected(self, tmp_path: Path) -> None:
        yaml_text = """\
            name: No Bind MP
            version: 1.0.0
            build_number: 1
            author: test
            adapter_kind: mpb_no_bind
            description: Missing bind_to test
            source:
              port: 443
              ssl: NO_VERIFY
              base_path: api
              timeout: 30
              max_retries: 2
              max_concurrent: 10
              auth:
                preset: cookie_session
                credentials:
                  - {key: username, label: username, sensitive: false}
                  - {key: password, label: password, sensitive: true}
                login:
                  method: POST
                  path: auth/login
                extract:
                  - location: HEADER
                    name: Set-Cookie
                    bind_to: ""
                inject:
                  - type: header
                    name: Cookie
                    value: "${session.token_cookie}"
                logout:
                  method: POST
                  path: auth/logout
            requests:
              - name: sysinfo
                method: GET
                path: stat/sysinfo
                response_path: data
            object_types:
              - name: Controller
                key: controller
                type: INTERNAL
                is_singleton: true
                name_expression: hostname
                identifiers:
                  - key: hostname
                    source: "metricset:sysinfo.hostname"
                metricSets:
                  - from_request: sysinfo
                metrics:
                  - key: hostname
                    label: Hostname
                    usage: PROPERTY
                    type: STRING
                    source: "metricset:sysinfo.hostname"
        """
        with pytest.raises(ManagementPackValidationError, match="bind_to"):
            _write_and_load(tmp_path, yaml_text)


# ---------------------------------------------------------------------------
# Gap F: JMESPath filter predicates
# ---------------------------------------------------------------------------


class TestGapFJMESPathPredicates:
    """JMESPath filter predicates in metric source paths."""

    def test_simple_predicate_validates(self, tmp_path: Path) -> None:
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.[?subsystem=='wan'].latency | [0]"
        )
        mp = _write_and_load(tmp_path, yaml_text)
        # The JMESPath metric is the second one (first is site_id)
        jmes_metric = next(
            m for m in mp.object_types[0].metrics if m.key == "test_metric"
        )
        assert "[?" in jmes_metric.source.path

    def test_predicate_with_hyphenated_field_validates(self, tmp_path: Path) -> None:
        """tx_bytes-r has a hyphen in the field name — must not be rejected."""
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.[?subsystem=='wan'].tx_bytes-r | [0]"
        )
        _write_and_load(tmp_path, yaml_text)  # Must not raise

    def test_predicate_on_nested_array_validates(self, tmp_path: Path) -> None:
        """radio_table_stats[...] is a subarray of the response — nested predicate."""
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.radio_table_stats[?radio=='ng'].cu_total | [0]"
        )
        _write_and_load(tmp_path, yaml_text)  # Must not raise

    def test_temperature_predicate_validates(self, tmp_path: Path) -> None:
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.temperatures[?name=='CPU'].value | [0]"
        )
        _write_and_load(tmp_path, yaml_text)

    def test_malformed_predicate_single_equals_rejected(self, tmp_path: Path) -> None:
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.[?subsystem='wan'].latency"
        )
        with pytest.raises(
            ManagementPackValidationError, match="JMESPath filter predicate"
        ):
            _write_and_load(tmp_path, yaml_text)

    def test_malformed_predicate_unclosed_bracket_rejected(
        self, tmp_path: Path
    ) -> None:
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.[?subsystem=='wan'.latency"
        )
        with pytest.raises(
            ManagementPackValidationError, match="JMESPath filter predicate"
        ):
            _write_and_load(tmp_path, yaml_text)

    def test_plain_path_no_predicate_still_works(self, tmp_path: Path) -> None:
        """Paths without predicates must NOT trigger the JMESPath validator."""
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.latency", metric_key="latency"
        )
        _write_and_load(tmp_path, yaml_text)

    def test_predicate_renders_single_element_key(self, tmp_path: Path) -> None:
        """A predicate path must produce a single-element key array in the DML."""
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.[?subsystem=='wan'].latency | [0]"
        )
        mp = _write_and_load(tmp_path, yaml_text)
        design = render_mp_design_json(mp)
        # source.requests is a dict keyed by UUID → iterate values.
        requests_dict = design["source"]["requests"]
        found_predicate_attr = False
        for req in requests_dict.values():
            dml_lists = (
                req.get("response", {}).get("result", {}).get("dataModelLists", [])
            )
            for dml in dml_lists:
                for attr in dml.get("attributes", []):
                    label = attr.get("label", "")
                    if "[?" in label:
                        assert isinstance(attr["key"], list)
                        assert len(attr["key"]) == 1, (
                            f"Expected single-element key for predicate attr, "
                            f"got {attr['key']!r}"
                        )
                        assert attr["key"][0] == label
                        found_predicate_attr = True
        assert found_predicate_attr, (
            "No attribute with JMESPath predicate found in rendered DML"
        )

    def test_plain_path_renders_multi_element_key(self, tmp_path: Path) -> None:
        """Plain dotted paths must still split into multi-element key arrays."""
        # Use a nested plain path so we get a multi-element key.
        # site_id is a single-element (no dot), wan.latency has a dot.
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.wan.latency", metric_key="latency"
        )
        mp = _write_and_load(tmp_path, yaml_text)
        design = render_mp_design_json(mp)
        # source.requests is a dict keyed by UUID → iterate values.
        requests_dict = design["source"]["requests"]
        found_dotted_attr = False
        for req in requests_dict.values():
            dml_lists = (
                req.get("response", {}).get("result", {}).get("dataModelLists", [])
            )
            for dml in dml_lists:
                for attr in dml.get("attributes", []):
                    label = attr.get("label", "")
                    if "." in label and "[?" not in label and label != "@@@id":
                        assert isinstance(attr["key"], list)
                        assert len(attr["key"]) > 1, (
                            f"Expected multi-element key for dotted attr {label!r}, "
                            f"got {attr['key']!r}"
                        )
                        found_dotted_attr = True
        assert found_dotted_attr, (
            "No plain dotted-path attribute found in rendered DML"
        )

    def test_multi_condition_predicate_validates(self, tmp_path: Path) -> None:
        yaml_text = _jmespath_mp_yaml(
            "metricset:site_health.[?subsystem=='wan' && status=='active'].latency | [0]"
        )
        _write_and_load(tmp_path, yaml_text)


# ---------------------------------------------------------------------------
# Gap D: type coercion hint
# ---------------------------------------------------------------------------


class TestGapDCoerceHint:
    """Type coerce hint on metric definitions."""

    def test_coerce_number_on_number_metric_accepted(self, tmp_path: Path) -> None:
        yaml_text = _coerce_mp_yaml("NUMBER", "coerce: number")
        mp = _write_and_load(tmp_path, yaml_text)
        cpu_metric = next(
            m for m in mp.object_types[0].metrics if m.key == "cpu_pct"
        )
        assert cpu_metric.coerce == "number"
        assert cpu_metric.type == "NUMBER"

    def test_coerce_hint_does_not_change_wire_data_type(self, tmp_path: Path) -> None:
        """coerce: number is a documentation hint; rendered dataType must be NUMBER."""
        yaml_text = _coerce_mp_yaml("NUMBER", "coerce: number")
        mp = _write_and_load(tmp_path, yaml_text)
        design = render_mp_design_json(mp)
        resources = design["source"]["resources"]
        metric_found = False
        for obj in resources:
            for ms in obj.get("metricSets", []):
                for metric in ms.get("metrics", []):
                    if metric.get("label") == "CPU %":
                        assert metric["dataType"] == "NUMBER"
                        metric_found = True
        assert metric_found, "cpu_pct metric not found in rendered output"

    def test_no_coerce_field_still_works(self, tmp_path: Path) -> None:
        """Metrics without coerce: key are unaffected (backward compat)."""
        yaml_text = _coerce_mp_yaml("NUMBER", "")
        mp = _write_and_load(tmp_path, yaml_text)
        cpu_metric = next(
            m for m in mp.object_types[0].metrics if m.key == "cpu_pct"
        )
        assert cpu_metric.coerce is None

    def test_coerce_number_on_string_metric_rejected(self, tmp_path: Path) -> None:
        # Use PROPERTY usage so we don't hit the separate METRIC-requires-NUMBER guard.
        # The coerce validator fires independently of the usage/type cross-check.
        yaml_text = _coerce_mp_yaml("STRING", "coerce: number", usage="PROPERTY")
        with pytest.raises(
            ManagementPackValidationError, match="coerce: number requires type: NUMBER"
        ):
            _write_and_load(tmp_path, yaml_text)

    def test_unknown_coerce_value_rejected(self, tmp_path: Path) -> None:
        yaml_text = _coerce_mp_yaml("NUMBER", "coerce: string")
        with pytest.raises(
            ManagementPackValidationError, match="coerce must be 'number'"
        ):
            _write_and_load(tmp_path, yaml_text)

    def test_coerce_number_plus_jmespath_predicate_combo(
        self, tmp_path: Path
    ) -> None:
        """Gap D + Gap F combo: coerce: number on a metric with a JMESPath predicate."""
        yaml_text = """\
            name: Combo Test MP
            version: 1.0.0
            build_number: 1
            author: test
            adapter_kind: mpb_combo_test
            description: coerce + jmespath combo test
            source:
              port: 443
              ssl: NO_VERIFY
              base_path: api
              timeout: 30
              max_retries: 2
              max_concurrent: 10
              auth:
                preset: none
            requests:
              - name: site_health
                method: GET
                path: stat/health
                response_path: data
            object_types:
              - name: Site
                key: site
                type: INTERNAL
                is_singleton: true
                name_expression: site_id
                identifiers:
                  - key: site_id
                    source: "metricset:site_health.site_id"
                metricSets:
                  - from_request: site_health
                metrics:
                  - key: site_id
                    label: Site ID
                    usage: PROPERTY
                    type: STRING
                    source: "metricset:site_health.site_id"
                  - key: wan_tx_bytes
                    label: WAN TX Bytes/s
                    usage: METRIC
                    type: NUMBER
                    source: "metricset:site_health.[?subsystem=='wan'].tx_bytes-r | [0]"
                    coerce: number
        """
        # Must not raise — both coerce hint and JMESPath predicate are valid together.
        mp = _write_and_load(tmp_path, yaml_text)
        wan_metric = next(
            m for m in mp.object_types[0].metrics if m.key == "wan_tx_bytes"
        )
        assert wan_metric.coerce == "number"
        assert "[?" in wan_metric.source.path
        assert wan_metric.type == "NUMBER"


# ---------------------------------------------------------------------------
# Regression: Synology NAS YAML
# ---------------------------------------------------------------------------


class TestSynologyRegression:
    """The existing Synology NAS YAML must validate and render identically."""

    def test_synology_validates(self) -> None:
        mp = load_file(
            _REPO_ROOT / "content" / "managementpacks" / "synology_nas.yaml"
        )
        # auth.extract must be a list with a single binding
        assert mp.source is not None
        assert mp.source.auth is not None
        extract_list = mp.source.auth.extract
        assert isinstance(extract_list, list)
        assert len(extract_list) == 1
        assert extract_list[0].session_key == "set_cookie"

    def test_synology_renders_one_session_variable(self) -> None:
        mp = load_file(
            _REPO_ROOT / "content" / "managementpacks" / "synology_nas.yaml"
        )
        design = render_mp_design_json(mp)
        sv = design["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        assert len(sv) == 1
        assert sv[0]["key"] == "set_cookie"
        assert sv[0]["path"] == ["Set-Cookie"]
        assert sv[0]["location"] == "HEADER"

    def test_synology_session_variable_id_is_stable(self) -> None:
        """Same YAML must produce the same session variable UUID on every render."""
        mp = load_file(
            _REPO_ROOT / "content" / "managementpacks" / "synology_nas.yaml"
        )
        design1 = render_mp_design_json(mp)
        design2 = render_mp_design_json(mp)
        sv1 = design1["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        sv2 = design2["source"]["authentication"]["sessionSettings"]["sessionVariables"]
        assert sv1 == sv2
        # Specific UUID must be stable (derived from stable seed, not random)
        assert sv1[0]["id"] == "fde54940-9fcb-520b-a009-afae9602df42"

    def test_synology_no_jmespath_paths_in_metrics(self) -> None:
        """Synology metrics use plain dotted paths — none should have predicates."""
        mp = load_file(
            _REPO_ROOT / "content" / "managementpacks" / "synology_nas.yaml"
        )
        for ot in mp.object_types:
            for m in ot.metrics:
                assert "[?" not in m.source.path, (
                    f"Unexpected JMESPath predicate in Synology metric {m.key}: "
                    f"{m.source.path!r}"
                )

    def test_synology_no_coerce_hints(self) -> None:
        """Synology metrics have no coerce hints — all coerce fields are None."""
        mp = load_file(
            _REPO_ROOT / "content" / "managementpacks" / "synology_nas.yaml"
        )
        for ot in mp.object_types:
            for m in ot.metrics:
                assert m.coerce is None, (
                    f"Unexpected coerce hint on Synology metric {m.key}: "
                    f"{m.coerce!r}"
                )


# ---------------------------------------------------------------------------
# buildNumber emission in render-export path (2026-05-01 renderer gap fix)
# ---------------------------------------------------------------------------


class TestBuildNumberExport:
    """render_mpb_exchange_json must emit buildNumber at design.buildNumber."""

    def test_build_number_present_and_correct(self, tmp_path: Path) -> None:
        """YAML build_number=2 must appear as design.buildNumber=2 in exchange JSON."""
        from vcfops_managementpacks.render_export import render_mpb_exchange_json

        yaml_text = """\
            name: BuildNum Test MP
            version: 1.0.0
            build_number: 2
            author: test
            adapter_kind: mpb_buildnum_test
            description: buildNumber emission test
            source:
              port: 443
              ssl: NO_VERIFY
              base_path: api
              timeout: 30
              max_retries: 2
              max_concurrent: 10
              auth:
                preset: none
            requests:
              - name: sysinfo
                method: GET
                path: stat/sysinfo
                response_path: data
            object_types:
              - name: Controller
                key: controller
                type: INTERNAL
                is_singleton: true
                name_expression: hostname
                identifiers:
                  - key: hostname
                    source: "metricset:sysinfo.hostname"
                metricSets:
                  - from_request: sysinfo
                metrics:
                  - key: hostname
                    label: Hostname
                    usage: PROPERTY
                    type: STRING
                    source: "metricset:sysinfo.hostname"
        """
        mp = _write_and_load(tmp_path, yaml_text)
        exchange = render_mpb_exchange_json(mp)
        assert "design" in exchange
        assert "buildNumber" in exchange["design"], (
            "buildNumber must be a sibling of design.design in the exchange format"
        )
        assert exchange["design"]["buildNumber"] == 2

    def test_build_number_default_is_one(self, tmp_path: Path) -> None:
        """YAML without explicit build_number must default to 1 in exchange JSON."""
        from vcfops_managementpacks.render_export import render_mpb_exchange_json

        yaml_text = """\
            name: DefaultBuild Test MP
            version: 1.0.0
            author: test
            adapter_kind: mpb_defaultbuild_test
            description: buildNumber default test
            source:
              port: 443
              ssl: NO_VERIFY
              base_path: api
              timeout: 30
              max_retries: 2
              max_concurrent: 10
              auth:
                preset: none
            requests:
              - name: sysinfo
                method: GET
                path: stat/sysinfo
                response_path: data
            object_types:
              - name: Controller
                key: controller
                type: INTERNAL
                is_singleton: true
                name_expression: hostname
                identifiers:
                  - key: hostname
                    source: "metricset:sysinfo.hostname"
                metricSets:
                  - from_request: sysinfo
                metrics:
                  - key: hostname
                    label: Hostname
                    usage: PROPERTY
                    type: STRING
                    source: "metricset:sysinfo.hostname"
        """
        mp = _write_and_load(tmp_path, yaml_text)
        exchange = render_mpb_exchange_json(mp)
        assert exchange["design"]["buildNumber"] == 1

    def test_version_still_emitted_alongside_build_number(
        self, tmp_path: Path
    ) -> None:
        """version in design.design must not be displaced by buildNumber addition."""
        from vcfops_managementpacks.render_export import render_mpb_exchange_json

        yaml_text = """\
            name: VersionCheck Test MP
            version: 2.3.0
            build_number: 5
            author: test
            adapter_kind: mpb_versioncheck_test
            description: version + buildNumber coexistence test
            source:
              port: 443
              ssl: NO_VERIFY
              base_path: api
              timeout: 30
              max_retries: 2
              max_concurrent: 10
              auth:
                preset: none
            requests:
              - name: sysinfo
                method: GET
                path: stat/sysinfo
                response_path: data
            object_types:
              - name: Controller
                key: controller
                type: INTERNAL
                is_singleton: true
                name_expression: hostname
                identifiers:
                  - key: hostname
                    source: "metricset:sysinfo.hostname"
                metricSets:
                  - from_request: sysinfo
                metrics:
                  - key: hostname
                    label: Hostname
                    usage: PROPERTY
                    type: STRING
                    source: "metricset:sysinfo.hostname"
        """
        mp = _write_and_load(tmp_path, yaml_text)
        exchange = render_mpb_exchange_json(mp)
        assert exchange["design"]["buildNumber"] == 5
        assert exchange["design"]["design"]["version"] == "2.3.0"

    def test_unifi_yaml_build_number_is_two(self) -> None:
        """Production UniFi YAML has build_number=2; exchange JSON must reflect it."""
        from vcfops_managementpacks.render_export import render_mpb_exchange_json

        mp = load_file(
            _REPO_ROOT / "content" / "managementpacks" / "unifi_network.yaml"
        )
        exchange = render_mpb_exchange_json(mp)
        assert exchange["design"]["buildNumber"] == 2
