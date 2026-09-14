"""Deprecated entry point: forwards python -m vcfops_packaging to vcfcf_packaging."""
import runpy

runpy.run_module("vcfcf_packaging", run_name="__main__", alter_sys=True)
