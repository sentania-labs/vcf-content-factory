"""Deprecated alias: vcfops_symptoms is now vcfcf_symptoms.

Kept for one release so external callers keep working. Import
vcfcf_symptoms instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_symptoms", globals())
