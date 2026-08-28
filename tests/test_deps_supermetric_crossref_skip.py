"""The dependency auditor must skip the CORRECT ``@supermetric:`` form.

Regression from PR #141/#142: ``_is_sm_ref`` recognised
``Super Metric|@supermetric:"X"`` (via the ``super metric|`` prefix) and the
view-column form ``supermetric:"X"``, but not the SM-formula form
``@supermetric:"X"``, which carries a leading ``@``.  So the audit only ever
tolerated the misspelling.  Once the hand-written ``Super Metric|`` prefix was
dropped from the content (the correct authoring form), the auditor treated
``@supermetric`` as a built-in metric key and failed:

    AUDIT FAILED: VMWARE/HostSystem @supermetric
      (referenced by SM '[VCF Content Factory] Automation Licensed Cores')

forcing ``--skip-audit`` on an otherwise clean build.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

REF_NAME = "[VCF Content Factory] Host Licensed Cores"


def _formula(metric_expr: str) -> str:
    return (
        "sum(${adaptertype=VMWARE, objecttype=HostSystem, "
        f"metric={metric_expr}" + ", depth=5})"
    )


class TestIsSmRef:
    @pytest.mark.parametrize("key", [
        f'@supermetric:"{REF_NAME}"',          # correct SM-formula form
        f"@supermetric:'{REF_NAME}'",
        f'Super Metric|@supermetric:"{REF_NAME}"',  # the buggy doubled form
        f'supermetric:"{REF_NAME}"',           # view-column form
        "Super Metric|sm_aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa",
        "sm_aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa",
    ])
    def test_super_metric_references_are_recognised(self, key):
        from vcfops_packaging.deps import _is_sm_ref

        assert _is_sm_ref(key) is True

    @pytest.mark.parametrize("key", [
        "cpu|usage_average",
        "config|hardware|num_Cpu",
    ])
    def test_builtin_keys_are_not_sm_references(self, key):
        from vcfops_packaging.deps import _is_sm_ref

        assert _is_sm_ref(key) is False


class TestRefsFromFormula:
    def test_correct_crossref_form_produces_no_audit_reference(self):
        from vcfops_packaging.deps import _refs_from_formula

        refs = _refs_from_formula(_formula(f'@supermetric:"{REF_NAME}"'), "probe SM")
        assert refs == [], [r.metric_key for r in refs]

    def test_builtin_metric_in_the_same_shape_is_still_audited(self):
        from vcfops_packaging.deps import _refs_from_formula

        refs = _refs_from_formula(_formula("cpu|usage_average"), "probe SM")
        assert [r.metric_key for r in refs] == ["cpu|usage_average"]
