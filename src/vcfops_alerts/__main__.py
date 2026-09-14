"""Deprecated entry point: forwards python -m vcfops_alerts to vcfcf_alerts."""
import runpy

runpy.run_module("vcfcf_alerts", run_name="__main__", alter_sys=True)
