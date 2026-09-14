"""Deprecated alias: vcfops_packaging is now vcfcf_packaging.

Kept for one release so external callers keep working. Import
vcfcf_packaging instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_packaging", globals())
