"""Deprecated alias: vcfops_dashboards is now vcfcf_dashboards.

Kept for one release so external callers keep working. Import
vcfcf_dashboards instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_dashboards", globals())
