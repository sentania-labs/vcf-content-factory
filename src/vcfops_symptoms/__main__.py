"""Deprecated entry point: forwards python -m vcfops_symptoms to vcfcf_symptoms."""
import runpy

runpy.run_module("vcfcf_symptoms", run_name="__main__", alter_sys=True)
