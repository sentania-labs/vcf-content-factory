"""Deprecated alias: vcfops_customgroups is now vcfcf_customgroups.

Kept for one release so external callers keep working. Import
vcfcf_customgroups instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_customgroups", globals())
