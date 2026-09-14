"""Deprecated entry point: forwards ``python -m vcfops_extractor`` to ``vcfcf_extractor``."""
import runpy
import sys

print(
    "vcfops_extractor is deprecated, use vcfcf_extractor; removed next release",
    file=sys.stderr,
)
runpy.run_module("vcfcf_extractor", run_name="__main__", alter_sys=True)
