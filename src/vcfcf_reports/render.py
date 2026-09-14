"""Moved to ``vcfcf_core.reports.render`` (M2 row 3); this path is an alias of it."""
import sys
import vcfcf_core.reports.render as _m

sys.modules[__name__] = _m
