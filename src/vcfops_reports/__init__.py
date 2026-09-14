"""Deprecated alias: vcfops_reports is now vcfcf_reports.

Kept for one release so external callers keep working. Import
vcfcf_reports instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_reports", globals())
