"""Deprecated alias: vcfops_common is now vcfcf_common.

Kept for one release so external callers keep working. Import
vcfcf_common instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_common", globals())
