"""Deprecated entry point: forwards python -m vcfops_customgroups to vcfcf_customgroups."""
import runpy

runpy.run_module("vcfcf_customgroups", run_name="__main__", alter_sys=True)
