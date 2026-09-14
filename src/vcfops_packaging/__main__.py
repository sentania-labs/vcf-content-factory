"""Deprecated entry point: forwards ``python -m vcfops_packaging`` to ``vcfcf_packaging``."""
import runpy
import sys

print(
    "vcfops_packaging is deprecated, use vcfcf_packaging; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_packaging", run_name="__main__", alter_sys=True)
