"""Deprecated alias: vcfops_alerts is now vcfcf_alerts.

Kept for one release so external callers keep working. Import
vcfcf_alerts instead. See vcfcf_common/compat_shim.py.
"""
from vcfcf_common.compat_shim import install as _install

_install(__name__, "vcfcf_alerts", globals())
