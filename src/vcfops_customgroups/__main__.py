"""Deprecated entry point: forwards ``python -m vcfops_customgroups`` to ``vcfcf_customgroups``."""
import runpy
import sys

print(
    "vcfops_customgroups is deprecated, use vcfcf_customgroups; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_customgroups", run_name="__main__", alter_sys=True)
