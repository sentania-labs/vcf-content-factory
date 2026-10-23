#!/usr/bin/env python3
"""Normalize VMware SCG 9.x source CSV to the canonical schema.

Usage: scripts/normalize_scg_v9.py <input.csv> <output.csv>

SCG 9.x reordered columns relative to 8.x: 'Secure Controls Framework
ID', 'DISA STIG ID', and 'PCI DSS 4.0.1 ID' were inserted at positions
1, 2, 3, shifting Component to position 4 and renaming it
'Component\\nName'. 'Implementation\\nPriority' (note newline) sits at
position 10 instead of 6. Header lookup is by name, so position
churn is invisible to this script, but downstream loaders that did
positional indexing (the old BenchmarkLoader.java) broke silently on
9.x. That bug is why this normalizer + a header-aware loader exist.

A thin wrapper (#169): the classifier chain and every scoring fix-up live
in _compliance_normalize.normalize_scg_source, keyed by control_id, and are
shared with every other SCG version. This file supplies only the SCG 9.x
column names, source token and parameter_kind classifier. They are module
attributes read at call time, so a driver for a sibling version (the
compliance repo's SCG 9.1 driver) can set them before calling normalize().
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _compliance_normalize import (
    classify_parameter_kind,
    log,
    normalize_scg_source,
)

SOURCE_TOKEN = "SCG-9.0"

# SCG 9.x uses embedded newlines in some header cells (csv.DictReader
# preserves them as part of the field name). We declare them exactly
# as they appear in the source.
COL_SCG_ID = "SCG ID"
COL_COMPONENT = "Component\nName"
COL_PRIORITY = "Implementation\nPriority"
COL_TITLE = "Description/Title"
COL_DESCRIPTION = "Discussion"
COL_PARAMETER = "Configuration Parameter"
COL_EXPECTED = "Baseline Suggested Value"
COL_ASSESSMENT = "PowerCLI Command Assessment"
COL_REMEDIATION = "PowerCLI Command Remediation"
COL_SETTING_LOCATION = "Setting Location"

REQUIRED_COLUMNS = [
    COL_SCG_ID,
    COL_COMPONENT,
    COL_PRIORITY,
    COL_TITLE,
    COL_DESCRIPTION,
    COL_PARAMETER,
    COL_EXPECTED,
    COL_ASSESSMENT,
    COL_REMEDIATION,
]


def normalize(input_path: str, output_path: str) -> int:
    return normalize_scg_source(
        input_path, output_path,
        columns={
            "scg_id": COL_SCG_ID,
            "component": COL_COMPONENT,
            "priority": COL_PRIORITY,
            "title": COL_TITLE,
            "description": COL_DESCRIPTION,
            "parameter": COL_PARAMETER,
            "expected": COL_EXPECTED,
            "assessment": COL_ASSESSMENT,
            "remediation": COL_REMEDIATION,
            "setting_location": COL_SETTING_LOCATION,
        },
        required_columns=REQUIRED_COLUMNS,
        source_token=SOURCE_TOKEN,
        label="normalize_scg_v9",
        classify_kind=classify_parameter_kind,
    )


def main(argv: list) -> int:
    if len(argv) != 3:
        log("usage: normalize_scg_v9.py <input.csv> <output.csv>")
        return 2
    return normalize(argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
