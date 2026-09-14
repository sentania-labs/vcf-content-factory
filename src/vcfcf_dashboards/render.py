"""Moved to ``vcfcf_core.dashboards.render`` (M2 row 2); this path is an alias of it."""
import sys
import vcfcf_core.dashboards.render as _m

sys.modules[__name__] = _m
