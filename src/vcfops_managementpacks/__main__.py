"""Deprecated entry point: forwards ``python -m vcfops_managementpacks`` to ``vcfcf_managementpacks``."""
import runpy
import sys

print(
    "vcfops_managementpacks is deprecated, use vcfcf_managementpacks; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_managementpacks", run_name="__main__", alter_sys=True)
