"""Moved to ``vcfcf_core.alerts.loader`` (M2 row 1); this path is an alias of it."""
import sys
import vcfcf_core.alerts.loader as _m

sys.modules[__name__] = _m
