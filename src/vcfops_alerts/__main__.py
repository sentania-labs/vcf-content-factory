"""Deprecated entry point: forwards ``python -m vcfops_alerts`` to ``vcfcf_alerts``."""
import runpy
import sys

print(
    "vcfops_alerts is deprecated, use vcfcf_alerts; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_alerts", run_name="__main__", alter_sys=True)
