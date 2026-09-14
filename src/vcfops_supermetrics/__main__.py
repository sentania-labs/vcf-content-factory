"""Deprecated entry point: forwards python -m vcfops_supermetrics to vcfcf_supermetrics."""
import runpy

runpy.run_module("vcfcf_supermetrics", run_name="__main__", alter_sys=True)
