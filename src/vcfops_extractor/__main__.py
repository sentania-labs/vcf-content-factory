"""Deprecated entry point: forwards python -m vcfops_extractor to vcfcf_extractor."""
import runpy

runpy.run_module("vcfcf_extractor", run_name="__main__", alter_sys=True)
