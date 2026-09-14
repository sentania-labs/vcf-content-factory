"""Deprecated entry point: forwards python -m vcfops_dashboards to vcfcf_dashboards."""
import runpy

runpy.run_module("vcfcf_dashboards", run_name="__main__", alter_sys=True)
