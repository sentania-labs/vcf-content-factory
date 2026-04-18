"""Load and validate symptom definition YAML definitions.

Symptom definitions are identified by name (not UUID) — the VCF Ops API
assigns the id server-side on create.  Sync matches by name.  Do not
include an `id:` field in YAML.

YAML schema (see .claude/agents/symptom-author.md for the full spec):

    name: "[VCF Content Factory] VM CPU Usage Critical"
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    severity: CRITICAL          # CRITICAL, IMMEDIATE, WARNING, INFO
    wait_cycles: 3
    cancel_cycles: 3
    description: >
      Optional description.

    # Metric static threshold (most common):
    condition:
      type: metric_static
      key: cpu|usage_average
      operator: GT              # GT, GT_EQ, LT, LT_EQ, EQ, NOT_EQ
      value: 90
      instanced: false

    # Metric dynamic threshold:
    # condition:
    #   type: metric_dynamic
    #   key: cpu|usage_average
    #   direction: ABOVE        # ABOVE, BELOW, ABNORMAL

    # Property symptom (string):
    # condition:
    #   type: property
    #   key: summary|runtime|powerState
    #   operator: EQ
    #   value: "poweredOff"

Condition type mapping to API wire types:
  metric_static    -> CONDITION_HT  (HT-condition: key, operator, value, instanced, valueType=NUMERIC, thresholdType=STATIC)
  metric_dynamic   -> CONDITION_DT  (DT-condition: key, operator=DT_ABOVE/DT_BELOW/DT_ABNORMAL, instanced)
  property         -> CONDITION_PROPERTY_STRING or CONDITION_PROPERTY_NUMERIC (auto-detected from value type)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml
import yaml.constructor
import yaml.resolver


def _strict_load(stream):
    """yaml.safe_load replacement that raises on duplicate mapping keys."""
    class _StrictKeyLoader(yaml.SafeLoader):
        pass

    def _no_duplicates(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None, None,
                    f"duplicate key '{key}' found at {key_node.start_mark}",
                    key_node.start_mark,
                )
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    _StrictKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _no_duplicates,
    )
    return yaml.load(stream, Loader=_StrictKeyLoader)


class SymptomValidationError(ValueError):
    pass


# Valid severity values accepted by the API (maps YAML -> wire).
# Note: API uses INFORMATION for INFO; we accept both.
SEVERITY_MAP = {
    "CRITICAL": "CRITICAL",
    "IMMEDIATE": "IMMEDIATE",
    "WARNING": "WARNING",
    "INFO": "INFORMATION",
    "INFORMATION": "INFORMATION",
}

CONDITION_TYPES = {
    "metric_static",
    "metric_dynamic",
    "property",
}

STATIC_OPERATORS = {"GT", "GT_EQ", "LT", "LT_EQ", "EQ", "NOT_EQ"}
PROPERTY_OPERATORS = {
    "EQ", "NOT_EQ", "CONTAINS", "NOT_CONTAINS", "STARTS_WITH",
    "ENDS_WITH", "REGEX", "GT", "LT", "GT_EQ", "LT_EQ",
    "NOT_STARTS_WITH", "NOT_ENDS_WITH", "NOT_REGEX",
}
DYNAMIC_DIRECTIONS = {"ABOVE", "BELOW", "ABNORMAL"}


@dataclass
class SymptomDef:
    name: str
    adapter_kind: str
    resource_kind: str
    severity: str          # normalised to API wire value
    condition: dict        # raw condition dict from YAML
    wait_cycles: int = 1
    cancel_cycles: int = 1
    description: str = ""
    source_path: Optional[Path] = None

    def validate(self, enforce_framework_prefix: bool = True) -> None:
        if not self.name or not self.name.strip():
            raise SymptomValidationError("name is required")
        if enforce_framework_prefix and not self.name.startswith("[VCF Content Factory] "):
            src = str(self.source_path) if self.source_path else self.name
            raise SymptomValidationError(
                f'{src}: name "{self.name}" missing framework prefix '
                f'"[VCF Content Factory]". All factory-authored content must carry the literal '
                f'"[VCF Content Factory]" prefix (see CLAUDE.md §Hard rules #5). For third-party '
                f"bundle content, ensure the bundle manifest sets factory_native: false."
            )
        if not self.adapter_kind:
            raise SymptomValidationError(f"{self.name}: adapter_kind is required")
        if not self.resource_kind:
            raise SymptomValidationError(f"{self.name}: resource_kind is required")
        if self.severity not in SEVERITY_MAP.values():
            raise SymptomValidationError(
                f"{self.name}: severity must be one of "
                f"{sorted(set(SEVERITY_MAP))}; got {self.severity!r}"
            )
        if self.wait_cycles < 1:
            raise SymptomValidationError(
                f"{self.name}: wait_cycles must be >= 1"
            )
        if self.cancel_cycles < 1:
            raise SymptomValidationError(
                f"{self.name}: cancel_cycles must be >= 1"
            )
        self._validate_condition(self.condition)

    def _validate_condition(self, cond: dict) -> None:
        tag = f"{self.name}: condition"
        if not isinstance(cond, dict):
            raise SymptomValidationError(f"{tag} must be a mapping")
        ctype = cond.get("type", "")
        if ctype not in CONDITION_TYPES:
            raise SymptomValidationError(
                f"{tag}.type must be one of {sorted(CONDITION_TYPES)}; "
                f"got {ctype!r}"
            )
        key = cond.get("key", "")
        if not key:
            raise SymptomValidationError(f"{tag}: key is required")

        if ctype == "metric_static":
            op = cond.get("operator", "")
            if op not in STATIC_OPERATORS:
                raise SymptomValidationError(
                    f"{tag}: operator must be one of "
                    f"{sorted(STATIC_OPERATORS)}; got {op!r}"
                )
            if "value" not in cond:
                raise SymptomValidationError(
                    f"{tag}: value is required for metric_static"
                )

        elif ctype == "metric_dynamic":
            direction = cond.get("direction", "")
            if direction not in DYNAMIC_DIRECTIONS:
                raise SymptomValidationError(
                    f"{tag}: direction must be one of "
                    f"{sorted(DYNAMIC_DIRECTIONS)}; got {direction!r}"
                )

        elif ctype == "property":
            op = cond.get("operator", "")
            if op not in PROPERTY_OPERATORS:
                raise SymptomValidationError(
                    f"{tag}: operator must be one of "
                    f"{sorted(PROPERTY_OPERATORS)}; got {op!r}"
                )
            # value is required for most operators (EXISTS/NOT_EXISTS don't
            # need it, but we keep it simple and require it always — rare
            # edge cases can be handled when they arise)
            if "value" not in cond:
                raise SymptomValidationError(
                    f"{tag}: value is required for property condition"
                )

    def to_wire(self) -> dict:
        """Serialize to the JSON body expected by POST /api/symptomdefinitions."""
        return {
            "name": self.name,
            "description": self.description,
            "adapterKindKey": self.adapter_kind,
            "resourceKindKey": self.resource_kind,
            "waitCycles": self.wait_cycles,
            "cancelCycles": self.cancel_cycles,
            "state": {
                "severity": self.severity,
                "condition": _condition_to_wire(self.condition),
            },
        }


def _condition_to_wire(cond: dict) -> dict:
    """Map terse YAML condition dict to the API wire condition object."""
    ctype = cond["type"]
    key = cond["key"]
    instanced = bool(cond.get("instanced", False))

    if ctype == "metric_static":
        return {
            "type": "CONDITION_HT",
            "key": key,
            "operator": cond["operator"],
            "value": str(cond["value"]),
            "valueType": "NUMERIC",
            "instanced": instanced,
            "thresholdType": "STATIC",
        }

    if ctype == "metric_dynamic":
        direction = cond["direction"]
        # DT operator values: DT_ABOVE, DT_BELOW, DT_ABNORMAL
        dt_op = f"DT_{direction}"
        return {
            "type": "CONDITION_DT",
            "key": key,
            "operator": dt_op,
            "instanced": instanced,
        }

    if ctype == "property":
        value = cond["value"]
        if isinstance(value, bool):
            # Booleans go as strings
            return {
                "type": "CONDITION_PROPERTY_STRING",
                "key": key,
                "operator": cond["operator"],
                "stringValue": "true" if value else "false",
                "instanced": instanced,
                "thresholdType": "STATIC",
            }
        if isinstance(value, (int, float)):
            return {
                "type": "CONDITION_PROPERTY_NUMERIC",
                "key": key,
                "operator": cond["operator"],
                "value": float(value),
                "instanced": instanced,
                "thresholdType": "STATIC",
            }
        # Default: string
        return {
            "type": "CONDITION_PROPERTY_STRING",
            "key": key,
            "operator": cond["operator"],
            "stringValue": str(value),
            "instanced": instanced,
            "thresholdType": "STATIC",
        }

    raise SymptomValidationError(f"Unknown condition type: {ctype!r}")


def load_file(path: str | Path, enforce_framework_prefix: bool = True) -> SymptomDef:
    path = Path(path)
    try:
        data = _strict_load(path.read_text()) or {}
    except yaml.constructor.ConstructorError as exc:
        raise SymptomValidationError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SymptomValidationError(f"{path}: expected a YAML mapping")

    raw_severity = str(data.get("severity", "") or "").strip().upper()
    wire_severity = SEVERITY_MAP.get(raw_severity, raw_severity)

    sd = SymptomDef(
        name=str(data.get("name", "")).strip(),
        adapter_kind=str(data.get("adapter_kind", "") or "").strip(),
        resource_kind=str(data.get("resource_kind", "") or "").strip(),
        severity=wire_severity,
        condition=dict(data.get("condition") or {}),
        wait_cycles=int(data.get("wait_cycles", 1) or 1),
        cancel_cycles=int(data.get("cancel_cycles", 1) or 1),
        description=str(data.get("description", "") or "").strip(),
        source_path=path,
    )
    sd.validate(enforce_framework_prefix=enforce_framework_prefix)
    return sd


def load_dir(directory: str | Path = "symptoms", enforce_framework_prefix: bool = True) -> List[SymptomDef]:
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[SymptomDef] = []
    seen: dict[str, Path] = {}
    for p in sorted(directory.rglob("*.y*ml")):
        sd = load_file(p, enforce_framework_prefix=enforce_framework_prefix)
        if sd.name in seen:
            raise SymptomValidationError(
                f"duplicate symptom name '{sd.name}' "
                f"in {p} and {seen[sd.name]}"
            )
        seen[sd.name] = p
        out.append(sd)
    return out
