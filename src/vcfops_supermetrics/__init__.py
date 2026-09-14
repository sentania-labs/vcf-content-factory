"""Deprecated alias: vcfops_supermetrics is now vcfcf_supermetrics.

Kept for one release so external callers keep working. Import
vcfcf_supermetrics instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_supermetrics", globals())
