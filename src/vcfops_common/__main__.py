"""Deprecated entry point: forwards python -m vcfops_common to vcfcf_common."""
import runpy

runpy.run_module("vcfcf_common", run_name="__main__", alter_sys=True)
