#!/usr/bin/env python3
"""Normalize CIS vSphere benchmark source CSV to the canonical schema.

Usage: scripts/normalize_cis_vsphere.py <input.csv> <output.csv>

The CIS vSphere sample uses the same column layout as SCG 8.x but
with different content semantics: most rows have empty Configuration
Parameter and PowerCLI Command Assessment fields (the published
CIS sample is metadata-only). Those rows still ship in the canonical
output as parameter_kind=manual_audit for traceability — operators
see them in the metric tree but the evaluator skips them.

Source ID format is e.g. 'CIS-1.1.1'. We slug this directly without
stripping a version suffix because the IDs have no version segment.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _compliance_normalize import (
    ADAPTER_KIND,
    classify_parameter_kind,
    clean_priority,
    collapse_remediation,
    infer_value_type,
    log,
    map_component,
    map_setting_location,
    write_canonical,
)

SOURCE_TOKEN = "CIS-vSphere-8"

REQUIRED_COLUMNS = [
    "SCG ID",
    "Component",
    "Implementation Priority",
    "Description/Title",
    "Discussion",
    "Configuration Parameter",
    "Baseline Suggested Value",
    "PowerCLI Command Assessment",
    "PowerCLI Command Remediation Example",
]


def cis_slug(source_id: str) -> str:
    """Slugify a CIS source ID like 'CIS-1.1.1' into 'cis-1-1-1'."""
    s = source_id.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"\.", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def normalize(input_path: str, output_path: str) -> int:
    with open(input_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            log(f"ERROR: {input_path} has no header row")
            return 2
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            log(f"ERROR: {input_path} missing required columns: {missing}")
            return 2

        in_count = 0
        skipped: Counter = Counter()
        by_kind: Counter = Counter()
        unmapped_components: Counter = Counter()
        out_rows = []

        for src in reader:
            in_count += 1
            source_id = (src.get("SCG ID") or "").strip()
            if not source_id:
                skipped["empty_scg_id"] += 1
                continue

            component = (src.get("Component") or "").strip()
            mapped = map_component(component)
            if mapped is None:
                unmapped_components[component] += 1
                skipped["unmapped_component"] += 1
                continue
            resource_kind, prefix = mapped

            slug = cis_slug(source_id)
            if not slug:
                skipped["empty_slug"] += 1
                continue
            control_id = f"{prefix}.{slug}"

            # Setting Location refinement (defensive — CIS source
            # ships with the column empty today; included so future
            # CIS updates that populate it get the same handling
            # as SCG). Re-prefixes the control_id with the
            # Setting Location-derived prefix when one matches.
            setting_location = (src.get("Setting Location") or "").strip()
            sl_override = map_setting_location(setting_location)
            if sl_override:
                resource_kind, sl_prefix = sl_override
                control_id = f"{sl_prefix}.{slug}"

            parameter = (src.get("Configuration Parameter") or "").strip()
            if parameter == "N/A":
                parameter = ""

            assessment = (src.get("PowerCLI Command Assessment") or "").strip()
            parameter_kind = classify_parameter_kind(parameter, assessment)
            by_kind[parameter_kind] += 1

            expected = (src.get("Baseline Suggested Value") or "").strip()
            value_type = infer_value_type(expected)

            priority_raw = src.get("Implementation Priority") or ""
            priority = clean_priority(priority_raw)

            title = (src.get("Description/Title") or "").strip()
            description = (src.get("Discussion") or "").strip()
            remediation = collapse_remediation(
                src.get("PowerCLI Command Remediation Example") or "")

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

        log(f"[normalize_cis_vsphere] in={in_count}  out={written}  "
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
        log("usage: normalize_cis_vsphere.py <input.csv> <output.csv>")
        return 2
    return normalize(argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
