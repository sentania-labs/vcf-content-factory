"""Load and validate symptom definition YAML definitions.

Symptom definitions are identified by name (not UUID) for the VCF Ops API
sync path (the API assigns the id server-side on create; sync matches by
name).  However, an optional ``id:`` field IS accepted for third-party /
ported content whose original UUID must be preserved for pak content-import
to resolve cross-references (e.g. symptomdef XML ``id="SymptomDefinition-<uuid>"``).

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

import re
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

# symptomDefType values seen in product exports (built-ins: 161 / 37) and one
# third-party pak (7 condition_self).
SYMPTOM_DEF_TYPES = {"condition_self", "condition_population"}
SYMPTOM_OMIT = {"wait_cycles", "cancel_cycles", "instanced"}
#: Oldest VCF Operations version whose own built-in export shows each
#: ``omit:`` entry's attribute absent (symptomdefs.xml of the 8.18.7, 9.0.2
#: and 9.1.1 exports; alert_fidelity_wire_format.md §Omit version floors).
#: A Tier 2 pak build fails on an entry whose floor is above its oldest
#: supported line; ``None`` would mean no product export shows it absent.
SYMPTOM_OMIT_MIN_OPS_VERSION = {
    "wait_cycles": (8, 18, 7),    # 1,327 of 1,685 8.18.7 symptoms carry no waitCycle
    "cancel_cycles": (8, 18, 7),  # 1,209 of 1,685 carry no cancelCycle
    "instanced": (8, 18, 7),      # 934 of 985 metric / property conditions carry none
}
#: The oldest export set the floors above were read from.
OLDEST_OMIT_EVIDENCE = (8, 18, 7)


_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


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
    version: str = "1.0.0"  # internal semver (released not applicable to symptoms)
    id: Optional[str] = None  # UUID preserved from original for pak content-import
    # Fidelity (alert_fidelity_wire_format.md), content-import XML only:
    # disableInBasePolicy, symptomDefType (condition_self / condition_population,
    # the alert editor's inline condition symptoms), and omit (YAML names of
    # attributes the source leaves out: wait_cycles, cancel_cycles, instanced).
    disable_in_base_policy: bool = False
    symptom_def_type: Optional[str] = None
    omit: List[str] = field(default_factory=list)

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
        if self.id is not None and not _UUID_RE.match(self.id):
            raise SymptomValidationError(
                f"{self.name}: id must be a UUID (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx); "
                f"got {self.id!r}"
            )
        if self.wait_cycles < 1:
            raise SymptomValidationError(
                f"{self.name}: wait_cycles must be >= 1"
            )
        if self.cancel_cycles < 1:
            raise SymptomValidationError(
                f"{self.name}: cancel_cycles must be >= 1"
            )
        self._validate_fidelity()
        self._validate_condition(self.condition)

    def omit_version_problems(self, target_version=None) -> List[str]:
        """``omit:`` entries whose floor (SYMPTOM_OMIT_MIN_OPS_VERSION) is
        above ``target_version`` (a dotted version or int tuple). With no
        target, entries whose floor is above the oldest export read
        (OLDEST_OMIT_EVIDENCE) or unknown."""
        target = _version_tuple(target_version) if target_version is not None else OLDEST_OMIT_EVIDENCE
        src = f"{self.source_path}: " if self.source_path else ""
        out: List[str] = []
        for entry in self.omit:
            floor = SYMPTOM_OMIT_MIN_OPS_VERSION.get(entry)
            if floor is not None and _version_tuple(floor) <= target:
                continue
            seen = (f"absent only from VCF Operations {'.'.join(map(str, floor))} and later exports"
                    if floor is not None else "absent from no product export")
            out.append(
                f"{src}symptom {self.name!r}: omit: {entry} leaves out an attribute {seen}; "
                f"whether VCF Operations {'.'.join(map(str, target))} imports the symptom "
                f"without it is unproven"
            )
        return out

    def _validate_fidelity(self) -> None:
        src = f"{self.source_path}: " if self.source_path else ""
        if self.symptom_def_type is not None and self.symptom_def_type not in SYMPTOM_DEF_TYPES:
            raise SymptomValidationError(
                f"{src}{self.name}: symptom_def_type must be one of {sorted(SYMPTOM_DEF_TYPES)}; "
                f"got {self.symptom_def_type!r}"
            )
        bad = [o for o in self.omit if o not in SYMPTOM_OMIT]
        if bad or len(set(self.omit)) != len(self.omit):
            raise SymptomValidationError(
                f"{src}{self.name}: omit accepts {sorted(SYMPTOM_OMIT)}, each once; got {self.omit!r}"
            )
        # An absent waitCycle / cancelCycle means 1 (alertDefinitionSchema.xsd),
        # so only a value of 1 can be left out without changing the symptom.
        for o, val in (("wait_cycles", self.wait_cycles), ("cancel_cycles", self.cancel_cycles)):
            if o in self.omit and val != 1:
                raise SymptomValidationError(
                    f"{src}{self.name}: omit {o} needs {o}: 1 (an absent attribute means 1); got {val}"
                )
        if "instanced" in self.omit:
            cond = self.condition if isinstance(self.condition, dict) else {}
            if cond.get("instanced"):
                raise SymptomValidationError(f"{src}{self.name}: omit instanced contradicts instanced: true")
            if cond.get("type") not in ("metric_static", "property"):
                raise SymptomValidationError(
                    f"{src}{self.name}: omit instanced applies to metric_static and property conditions"
                )

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
            # A DT on a super metric is a different condition type on both
            # wires (XML type="dtsuper", REST CONDITION_DT_SUPER). The factory
            # emits dtmetric / CONDITION_DT only, and a wrong DT condition is
            # dropped silently at content import with its alerts, so refuse
            # it here. See
            # knowledge/context/wire-formats/symptomdef_dt_condition_import.md.
            if str(key).startswith("Super Metric|"):
                raise SymptomValidationError(
                    f"{tag}: metric_dynamic on a super metric key ({key!r}) "
                    f"is not supported (needs dtsuper / CONDITION_DT_SUPER, "
                    f"which the factory does not emit)"
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
        xml_only = [k for k, v in (("disable_in_base_policy", self.disable_in_base_policy),
                                   ("symptom_def_type", self.symptom_def_type)) if v]
        if xml_only:
            # The Suite API symptom-definition schema has neither field.
            raise SymptomValidationError(
                f"{self.source_path or self.name}: {', '.join(xml_only)} is only rendered on "
                f"the content-import XML path (pak builds, AlertContent.xml); the REST "
                f"symptom-definition body has no such field"
            )
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


def _version_tuple(v) -> tuple:
    parts = [int(x) for x in (v if isinstance(v, tuple) else str(v).split("."))]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


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

    version = str(data.get("version", "1.0.0") or "1.0.0").strip() or "1.0.0"

    raw_id = data.get("id")
    sym_id: Optional[str] = str(raw_id).strip() if raw_id is not None else None

    disable_raw = data.get("disable_in_base_policy", False)
    if not isinstance(disable_raw, bool):
        raise SymptomValidationError(f"{path}: disable_in_base_policy must be a bool")
    sdt_raw = data.get("symptom_def_type")
    if sdt_raw is not None and not isinstance(sdt_raw, str):
        raise SymptomValidationError(f"{path}: symptom_def_type must be a string")
    omit_raw = data.get("omit") or []
    if not isinstance(omit_raw, list) or not all(isinstance(o, str) for o in omit_raw):
        raise SymptomValidationError(f"{path}: omit must be a list of names")

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
        version=version,
        id=sym_id,
        disable_in_base_policy=disable_raw,
        symptom_def_type=sdt_raw,
        omit=list(omit_raw),
    )
    try:
        sd.validate(enforce_framework_prefix=enforce_framework_prefix)
    except SymptomValidationError as exc:
        # Field errors name the symptom; prefix the file so every message
        # names both (some already start with the path).
        if str(exc).startswith(str(path)):
            raise
        raise SymptomValidationError(f"{path}: {exc}") from None
    import warnings
    for _problem in sd.omit_version_problems():
        warnings.warn(_problem, UserWarning, stacklevel=2)
    return sd


def load_dir(directory: str | Path, enforce_framework_prefix: bool = True) -> List[SymptomDef]:
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
    # Two symptoms under one rendered id (case-insensitive): the later
    # replaces the earlier on content import. Same check as the alert loader.
    from vcfcf_core.alerts.render import rendered_id_collisions
    problems = rendered_id_collisions(symptoms=out)
    if problems:
        raise SymptomValidationError("\n".join(problems))
    return out
