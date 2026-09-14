"""Deprecated entry point: forwards ``python -m vcfops_reports`` to ``vcfcf_reports``."""
import runpy
import sys

print(
    "vcfops_reports is deprecated, use vcfcf_reports; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_reports", run_name="__main__", alter_sys=True)
