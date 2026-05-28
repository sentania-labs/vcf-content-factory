#!/usr/bin/env python3
"""Normalize VMware SCG 9.x source CSV to the canonical schema.

Usage: scripts/normalize_scg_v9.py <input.csv> <output.csv>

SCG 9.x reordered columns relative to 8.x: 'Secure Controls Framework
ID', 'DISA STIG ID', and 'PCI DSS 4.0.1 ID' were inserted at positions
1, 2, 3, shifting Component to position 4 and renaming it
'Component\\nName'. 'Implementation\\nPriority' (note newline) sits at
position 10 instead of 6. Header lookup is by name, so position
churn is invisible to this script — but downstream loaders that did
positional indexing (the old BenchmarkLoader.java) broke silently on
9.x. That bug is why this normalizer + a header-aware loader exist.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _compliance_normalize import (
    ADAPTER_KIND,
    build_control_id,
    classify_parameter_kind,
    clean_priority,
    collapse_remediation,
    derive_resource_kind,
    infer_value_type,
    log,
    map_component,
    write_canonical,
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
    with open(input_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            log(f"ERROR: {input_path} has no header row")
            return 2
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            log(f"ERROR: {input_path} missing required columns: "
                f"{[m.replace(chr(10), '\\n') for m in missing]}")
            return 2

        in_count = 0
        skipped: Counter = Counter()
        by_kind: Counter = Counter()
        unmapped_components: Counter = Counter()
        out_rows = []

        for src in reader:
            in_count += 1
            source_id = (src.get(COL_SCG_ID) or "").strip()
            if not source_id:
                skipped["empty_scg_id"] += 1
                continue

            component = (src.get(COL_COMPONENT) or "").strip()
            mapped = map_component(component)
            if mapped is None:
                unmapped_components[component] += 1
                skipped["unmapped_component"] += 1
                continue
            fallback_resource_kind, fallback_prefix = mapped

            control_id = build_control_id(fallback_prefix, source_id)
            if not control_id or "." not in control_id:
                skipped["empty_slug"] += 1
                continue
            resource_kind = derive_resource_kind(
                source_id, fallback_resource_kind)

            parameter = (src.get(COL_PARAMETER) or "").strip()
            if parameter == "N/A":
                parameter = ""

            assessment = (src.get(COL_ASSESSMENT) or "").strip()
            parameter_kind = classify_parameter_kind(parameter, assessment)
            by_kind[parameter_kind] += 1

            expected = (src.get(COL_EXPECTED) or "").strip()
            value_type = infer_value_type(expected)

            priority_raw = src.get(COL_PRIORITY) or ""
            priority = clean_priority(priority_raw)
            if not priority_raw.strip():
                log(f"WARN: missing priority for {source_id}, defaulting to P2")

            title = (src.get(COL_TITLE) or "").strip()
            description = (src.get(COL_DESCRIPTION) or "").strip()
            remediation = collapse_remediation(src.get(COL_REMEDIATION) or "")

            out_rows.append({
                "control_id": control_id,
                "priority": priority,
                "resource_kind": resource_kind,
                "adapter_kind": ADAPTER_KIND,
                "parameter": parameter,
                "parameter_kind": parameter_kind,
                "value_type": value_type,
                "expected_value": expected,
                "title": title,
                "description": description,
                "source_ref": f"{SOURCE_TOKEN}:{source_id}",
                "remediation_text": remediation,
            })

        written = write_canonical(output_path, out_rows)

        log(f"[normalize_scg_v9] in={in_count}  out={written}  "
            f"skipped={sum(skipped.values())}")
        if skipped:
            for k, v in sorted(skipped.items()):
                log(f"  skipped {k}: {v}")
        if unmapped_components:
            log("  unmapped Component values (skipped):")
            for k, v in sorted(unmapped_components.items()):
                log(f"    {v:5d}  {k!r}")
        log("  by parameter_kind:")
        for k, v in sorted(by_kind.items()):
            log(f"    {v:5d}  {k}")
        return 0


def main(argv: list) -> int:
    if len(argv) != 3:
        log("usage: normalize_scg_v9.py <input.csv> <output.csv>")
        return 2
    return normalize(argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
