"""Deprecated entry point: forwards python -m vcfops_managementpacks to vcfcf_managementpacks."""
import runpy

runpy.run_module("vcfcf_managementpacks", run_name="__main__", alter_sys=True)
