"""Moved to ``vcfcf_core.symptoms.loader`` (M2 row 1); this path is an alias of it."""
import sys
import vcfcf_core.symptoms.loader as _m

sys.modules[__name__] = _m
