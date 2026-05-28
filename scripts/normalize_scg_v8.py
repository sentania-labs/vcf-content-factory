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
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

# Allow `python3 scripts/normalize_scg_v8.py ...` from repo root.
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

SOURCE_TOKEN = "SCG-8.0"

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
            fallback_resource_kind, fallback_prefix = mapped

            control_id = build_control_id(fallback_prefix, source_id)
            if not control_id or "." not in control_id:
                skipped["empty_slug"] += 1
                continue
            resource_kind = derive_resource_kind(
                source_id, fallback_resource_kind)

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
            if not priority_raw.strip():
                log(f"WARN: missing priority for {source_id}, defaulting to P2")

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

        log(f"[normalize_scg_v8] in={in_count}  out={written}  "
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
        log("usage: normalize_scg_v8.py <input.csv> <output.csv>")
        return 2
    return normalize(argv[1], argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
