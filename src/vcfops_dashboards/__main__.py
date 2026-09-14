"""Deprecated entry point: forwards ``python -m vcfops_dashboards`` to ``vcfcf_dashboards``."""
import runpy
import sys

print(
    "vcfops_dashboards is deprecated, use vcfcf_dashboards; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_dashboards", run_name="__main__", alter_sys=True)
