"""Deprecated entry point: forwards ``python -m vcfops_common`` to ``vcfcf_common``."""
import runpy
import sys

print(
    "vcfops_common is deprecated, use vcfcf_common; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_common", run_name="__main__", alter_sys=True)
