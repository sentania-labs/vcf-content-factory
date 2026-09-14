"""Deprecated alias: vcfops_extractor is now vcfcf_extractor.

Kept for one release so external callers keep working. Import
vcfcf_extractor instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_extractor", globals())
