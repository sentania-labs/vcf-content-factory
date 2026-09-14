"""Deprecated entry point: forwards ``python -m vcfops_supermetrics`` to ``vcfcf_supermetrics``."""
import runpy
import sys

print(
    "vcfops_supermetrics is deprecated, use vcfcf_supermetrics; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_supermetrics", run_name="__main__", alter_sys=True)
