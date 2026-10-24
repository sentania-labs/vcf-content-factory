#!/usr/bin/env python3
"""Normalize VMware SCG 8.x source CSV to the canonical schema.

Usage: scripts/normalize_scg_v8.py <input.csv> <output.csv>

SCG 8.x source columns (in order):
  SCG ID, Product, Product Version, Component, Component Version,
  Feature/Function, Implementation Priority, Description/Title,
  Discussion, Configuration Parameter, Installation Default Value,
  Baseline Suggested Value, Is the Default?, Action Needed,
  Setting Location, Potential Functional Impact if Default Value
  is Changed, PowerCLI Command Assessment, PowerCLI Command
  Remediation Example, ...

Header lookup is by name (csv.DictReader); column order is informational.

A thin wrapper (#169): the classifier chain and every scoring fix-up live
in _compliance_normalize.normalize_scg_source, keyed by control_id, and are
shared with every other SCG version. This file supplies only the SCG 8.x
column names and source token. They are module constants read at call
time, so a driver for a sibling version (the compliance repo's SCG 7.0
driver) can set them before calling normalize().
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python3 scripts/normalize_scg_v8.py ...` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _compliance_normalize import (
    classify_parameter_kind,
    log,
    normalize_scg_source,
)

SOURCE_TOKEN = "SCG-8.0"

COL_SCG_ID = "SCG ID"
COL_COMPONENT = "Component"
COL_PRIORITY = "Implementation Priority"
COL_TITLE = "Description/Title"
COL_DESCRIPTION = "Discussion"
COL_PARAMETER = "Configuration Parameter"
COL_EXPECTED = "Baseline Suggested Value"
COL_ASSESSMENT = "PowerCLI Command Assessment"
COL_REMEDIATION = "PowerCLI Command Remediation Example"
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
        label="normalize_scg_v8",
        classify_kind=classify_parameter_kind,
    )


def main(argv: list) -> int:
    if len(argv) != 3:
        log("usage: normalize_scg_v8.py <input.csv> <output.csv>")
        return 2
    return normalize(argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
