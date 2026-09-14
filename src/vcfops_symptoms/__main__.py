"""Deprecated entry point: forwards ``python -m vcfops_symptoms`` to ``vcfcf_symptoms``."""
import runpy
import sys

print(
    "vcfops_symptoms is deprecated, use vcfcf_symptoms; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_symptoms", run_name="__main__", alter_sys=True)
