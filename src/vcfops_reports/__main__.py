"""Deprecated entry point: forwards python -m vcfops_reports to vcfcf_reports."""
import runpy

runpy.run_module("vcfcf_reports", run_name="__main__", alter_sys=True)
