"""Executing-branch tests for the extractor's ${this, metric=...} handling
(PR #137 Codex P1 regression fix).

The packaging-audit change made deps._refs_from_formula raise AuditError on a
this-bound metric key with no usable resource_kinds.  The extractor calls that
helper at two sites (the orphan check and the enablement walk); both must:

  - resolve this-refs against the SM's own assignment metadata (Default
    Policy scope preferred, then the REST resourceKinds field, then the
    formula-parse fallback), so a live-lab SM using ${this} is audited; and
  - NEVER abort the extraction workflow when no kinds resolve: loud per-SM
    WARN (the extractor's existing error convention), explicit
    ${adaptertype=...} refs from the same formula still extracted, this-ref
    surfaced again by _write_sm_yaml's resource_kinds WARN + validator reject.
"""
from __future__ import annotations

import pytest

from vcfops_extractor.extractor import (
    _sm_formula_refs_for_audit,
    _sm_kinds_for_audit,
)

_THIS_FORMULA = "${this, metric=cpu|usage_average}"
_MIXED_FORMULA = (
    "${this, metric=cpu|usage_average} + "
    "${adaptertype=VMWARE, objecttype=VirtualMachine, metric=mem|usage_average}"
)


class TestSmKindsForAudit:
    """Resolution order mirrors _write_sm_yaml: policy, REST field, formula."""

    def test_policy_assignment_wins(self):
        kinds = _sm_kinds_for_audit(
            {"id": "AAAA-1", "resourceKinds": [{"resourceKindKey": "Datastore",
                                               "adapterKindKey": "VMWARE"}]},
            "aaaa-1",
            _THIS_FORMULA,
            {"aaaa-1": [{"adapter_kind_key": "VMWARE",
                         "resource_kind_key": "HostSystem"}]},
        )
        assert kinds == [{"adapter_kind_key": "VMWARE",
                          "resource_kind_key": "HostSystem"}]

    def test_rest_field_fallback_normalized(self):
        kinds = _sm_kinds_for_audit(
            {"id": "bbbb-2", "resourceKinds": [{"resourceKind": "VirtualMachine",
                                                "adapterKind": "VMWARE"}]},
            "bbbb-2", _THIS_FORMULA, {},
        )
        assert kinds == [{"resource_kind_key": "VirtualMachine",
                          "adapter_kind_key": "VMWARE"}]

    def test_formula_parse_last_resort_and_empty(self):
        kinds = _sm_kinds_for_audit({"id": "cccc-3"}, "cccc-3", _MIXED_FORMULA, None)
        assert kinds == [{"adapter_kind_key": "VMWARE",
                          "resource_kind_key": "VirtualMachine"}]
        assert _sm_kinds_for_audit({"id": "dddd-4"}, "dddd-4", _THIS_FORMULA, None) == []


class TestSmFormulaRefsForAudit:

    def test_this_ref_with_kinds_resolves(self):
        """Pass case (both extractor sites use this path): the this-bound key
        is audited against the SM's own assignment."""
        refs = _sm_formula_refs_for_audit(
            _THIS_FORMULA, "Extracted SM",
            [{"adapter_kind_key": "VMWARE", "resource_kind_key": "HostSystem"}],
        )
        assert [(r.adapter_kind, r.resource_kind, r.metric_key) for r in refs] == [
            ("VMWARE", "HostSystem", "cpu|usage_average"),
        ]

    def test_no_metadata_warns_and_never_raises(self, capsys):
        """No-metadata case: loud per-SM WARN, no AuditError escapes, the
        extraction-side walk continues (empty ref list for a this-only
        formula)."""
        refs = _sm_formula_refs_for_audit(_THIS_FORMULA, "Bare Extracted SM", [])
        assert refs == []
        err = capsys.readouterr().err
        assert "WARN" in err
        assert "Bare Extracted SM" in err
        assert "cannot be audited" in err
        assert "extraction continues" in err.lower() or "extraction continues" in err

    def test_no_metadata_keeps_explicit_refs(self, capsys):
        """Mixed formula, no kinds: the unauditable this-entry is stripped
        after the WARN, but the explicit ${adaptertype=...} ref survives."""
        refs = _sm_formula_refs_for_audit(_MIXED_FORMULA, "Mixed Extracted SM", None)
        assert [(r.adapter_kind, r.resource_kind, r.metric_key) for r in refs] == [
            ("VMWARE", "VirtualMachine", "mem|usage_average"),
        ]
        assert "WARN" in capsys.readouterr().err

    def test_with_kinds_no_warning(self, capsys):
        _sm_formula_refs_for_audit(
            _MIXED_FORMULA, "Quiet SM",
            [{"adapter_kind_key": "VMWARE", "resource_kind_key": "VirtualMachine"}],
        )
        assert capsys.readouterr().err == ""
