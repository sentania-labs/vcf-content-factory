"""Deprecated alias: vcfops_managementpacks is now vcfcf_managementpacks.

Kept for one release so external callers keep working. Import
vcfcf_managementpacks instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_managementpacks", globals())
