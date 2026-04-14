"""Load and validate custom group YAML definitions.

Custom groups are an exception to the repo's UUID-stability contract.
The VCF Ops `/api/resources/groups` endpoint assigns the `id` field
on create, so cross-instance identity for custom groups is the
`name` (stored as `resourceKey.name` on the wire), NOT a UUID. The
loader therefore does not generate or persist UUIDs in custom group
YAML; sync matches by name.

YAML schema (terse, expanded to wire JSON by `to_wire()`):

    name: "[AI Content] vSAN Datastores"
    description: >
      Optional human description.
    type: Environment        # group type key, defaults to Environment
    auto_resolve_membership: true   # default true
    rules:
      - resource_kind: Datastore
        adapter_kind: VMWARE
        property:
          - { key: "summary|type", op: EQ, value: "vsan" }
        # Optional, all default to []:
        stat:
          - { key: "cpu|usage_average", op: GT, value: 80 }
        name:
          - { op: NOT_CONTAINS, value: "test" }
        relationship:
          - { relation: DESCENDANT, name: "[Custom] X", op: EQ }
        tag:
          - { category: "Environment", op: EQ, value: "production" }

Multiple `rules[]` entries are OR'd together; condition rules
within one rule entry are AND'd.

For wire format and grammar see context/customgroup_authoring.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

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


class CustomGroupValidationError(ValueError):
    pass


# Compare operators that VCF Ops accepts on custom group rules.
# Sourced from context/customgroup_authoring.md and OpenAPI.
COMPARE_OPS = {
    "EQ", "NOT_EQ", "GT", "GT_EQ", "LT", "LT_EQ",
    "CONTAINS", "NOT_CONTAINS", "STARTS_WITH", "ENDS_WITH",
    "REGEX",
}
RELATIONS = {"PARENT", "CHILD", "ANCESTOR", "DESCENDANT"}

# Mapping from REST compareOperator values to UI ruleStringOperator values.
# Used by CustomGroupDef.to_ui_wire().
_UI_STRING_OP_MAP: dict = {
    "EQ":           "EQUALS",
    "NOT_EQ":       "NOT_EQUALS",
    "CONTAINS":     "CONTAINS",
    "NOT_CONTAINS": "NOT_CONTAINS",
    "STARTS_WITH":  "STARTS_WITH",
    "ENDS_WITH":    "ENDS_WITH",
    "REGEX":        "REGEX",
    # Numeric ops that may appear on property rules with string values
    "GT":    "GREATER_THAN",
    "GT_EQ": "GREATER_THAN_OR_EQUALS",
    "LT":    "LESS_THAN",
    "LT_EQ": "LESS_THAN_OR_EQUALS",
}

# Mapping from REST compareOperator values to UI ruleOperator values
# (used for NumericMetricPropertyRule / stat rules).
_UI_NUMERIC_OP_MAP: dict = {
    "GT":     "GREATER_THAN",
    "GT_EQ":  "GREATER_THAN_OR_EQUALS",
    "LT":     "LESS_THAN",
    "LT_EQ":  "LESS_THAN_OR_EQUALS",
    "EQ":     "EQUALS",
    "NOT_EQ": "NOT_EQUALS",
}


@dataclass
class CustomGroupDef:
    name: str
    rules: List[dict]
    description: str = ""
    type_key: str = "Environment"
    auto_resolve_membership: bool = True
    source_path: Path | None = None

    # ---- validation ------------------------------------------------
    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise CustomGroupValidationError("name is required")
        if not self.type_key or not self.type_key.strip():
            raise CustomGroupValidationError(
                f"{self.name}: type is required (e.g. 'Environment')"
            )
        if not self.rules:
            raise CustomGroupValidationError(
                f"{self.name}: at least one rule is required"
            )
        for i, rule in enumerate(self.rules):
            self._validate_rule(i, rule)

    def _validate_rule(self, idx: int, rule: dict) -> None:
        tag = f"{self.name}: rules[{idx}]"
        if not isinstance(rule, dict):
            raise CustomGroupValidationError(f"{tag} must be a mapping")
        if not rule.get("resource_kind"):
            raise CustomGroupValidationError(
                f"{tag}: resource_kind is required"
            )
        if not rule.get("adapter_kind"):
            raise CustomGroupValidationError(
                f"{tag}: adapter_kind is required"
            )
        # At least one condition list must be non-empty.
        if not any(
            rule.get(k)
            for k in ("stat", "property", "name", "relationship", "tag")
        ):
            raise CustomGroupValidationError(
                f"{tag}: must contain at least one condition "
                f"(stat/property/name/relationship/tag)"
            )
        for c in rule.get("stat") or []:
            self._require_keys(tag + ".stat", c, ("key", "op", "value"))
            self._require_op(tag + ".stat", c["op"])
        for c in rule.get("property") or []:
            self._require_keys(tag + ".property", c, ("key", "op", "value"))
            self._require_op(tag + ".property", c["op"])
        for c in rule.get("name") or []:
            self._require_keys(tag + ".name", c, ("op", "value"))
            self._require_op(tag + ".name", c["op"])
        for c in rule.get("relationship") or []:
            self._require_keys(
                tag + ".relationship", c, ("relation", "name", "op")
            )
            if c["relation"] not in RELATIONS:
                raise CustomGroupValidationError(
                    f"{tag}.relationship: relation must be one of "
                    f"{sorted(RELATIONS)}, got {c['relation']!r}"
                )
            self._require_op(tag + ".relationship", c["op"])
        for c in rule.get("tag") or []:
            self._require_keys(
                tag + ".tag", c, ("category", "op", "value")
            )
            self._require_op(tag + ".tag", c["op"])

    @staticmethod
    def _require_keys(tag: str, c: Any, keys: tuple) -> None:
        if not isinstance(c, dict):
            raise CustomGroupValidationError(
                f"{tag}: each condition must be a mapping"
            )
        missing = [k for k in keys if k not in c]
        if missing:
            raise CustomGroupValidationError(
                f"{tag}: missing keys {missing} in {c}"
            )

    @staticmethod
    def _require_op(tag: str, op: str) -> None:
        if op not in COMPARE_OPS:
            raise CustomGroupValidationError(
                f"{tag}: op must be one of {sorted(COMPARE_OPS)}, "
                f"got {op!r}"
            )

    # ---- wire format ----------------------------------------------

    def to_ui_wire(self) -> dict:
        """Expand the terse YAML into the UI import JSON format.

        The UI import dialog (Environment > Custom Groups > Import) expects a
        different JSON shape from the REST API POST /api/resources/groups. This
        method produces the UI envelope shape, suitable for drag-drop import and
        for the community-native customgroup.json artifact in distribution zips.

        The REST API shape is produced by to_wire().  Both methods must remain
        in sync — this one is for distribution packages, to_wire() is for the
        install-script REST path.

        Top-level envelope: {"customGroups": [...], "customGroupTypes": [...]}
        See context/customgroup_import_format.md for the full format reference.
        """
        group = {
            "name": self.name,
            "description": self.description,
            "resourceKind": self.type_key,
            "adapterKind": "Container",
            "autoResolveMembership": self.auto_resolve_membership,
            "started": True,
            "membershipDefinition": {
                "ruleGroups": [self._rule_to_ui_wire(r) for r in self.rules],
            },
        }
        group_type = {
            "resourceKind": self.type_key,
            "localization": [
                {"resourceKindName": self.type_key, "locale": "en"},
            ],
        }
        return {"customGroups": [group], "customGroupTypes": [group_type]}

    def _rule_to_ui_wire(self, rule: dict) -> dict:
        """Convert one YAML rule entry into a UI ruleGroup dict."""
        ui_rules = []

        # name conditions → ResourceNameRule
        for c in rule.get("name") or []:
            ui_rules.append({
                "ruleType": "ResourceNameRule",
                "ruleStringOperator": _UI_STRING_OP_MAP.get(c["op"], c["op"]),
                "ruleStringValue": c["value"],
            })

        # property conditions → StringMetricPropertyRule or
        # NumericMetricPropertyRule depending on the value type.
        for c in rule.get("property") or []:
            val = c["value"]
            if isinstance(val, bool):
                ui_rules.append({
                    "ruleType": "StringMetricPropertyRule",
                    "ruleMetricKey": c["key"],
                    "isProperty": True,
                    "ruleStringOperator": _UI_STRING_OP_MAP.get(c["op"], c["op"]),
                    "ruleStringValue": "true" if val else "false",
                })
            elif isinstance(val, (int, float)):
                ui_rules.append({
                    "ruleType": "NumericMetricPropertyRule",
                    "ruleMetricKey": c["key"],
                    "isProperty": True,
                    "ruleOperator": _UI_NUMERIC_OP_MAP.get(c["op"], c["op"]),
                    "ruleValue": float(val),
                })
            else:
                ui_rules.append({
                    "ruleType": "StringMetricPropertyRule",
                    "ruleMetricKey": c["key"],
                    "isProperty": True,
                    "ruleStringOperator": _UI_STRING_OP_MAP.get(c["op"], c["op"]),
                    "ruleStringValue": str(val),
                })

        # stat conditions → NumericMetricPropertyRule (isProperty: false)
        for c in rule.get("stat") or []:
            ui_rules.append({
                "ruleType": "NumericMetricPropertyRule",
                "ruleMetricKey": c["key"],
                "isProperty": False,
                "ruleOperator": _UI_NUMERIC_OP_MAP.get(c["op"], c["op"]),
                "ruleValue": float(c["value"]),
            })

        # relationship conditions → RelationshipRule
        for c in rule.get("relationship") or []:
            ui_rules.append({
                "ruleType": "RelationshipRule",
                "ruleRelationshipType": c["relation"],
                "ruleStringOperator": _UI_STRING_OP_MAP.get(c["op"], c["op"]),
                "ruleStringValue": c["name"],
            })

        # tag conditions — no UI ruleType known from reference specimens.
        # Emit StringMetricPropertyRule as the closest approximation and log
        # a comment field so callers can detect the gap.
        for c in rule.get("tag") or []:
            ui_rules.append({
                "ruleType": "StringMetricPropertyRule",
                "_tag_gap": (
                    "Tag rules have no confirmed UI ruleType. "
                    "This is approximated as StringMetricPropertyRule."
                ),
                "ruleMetricKey": c["category"],
                "isProperty": True,
                "ruleStringOperator": _UI_STRING_OP_MAP.get(c["op"], c["op"]),
                "ruleStringValue": str(c["value"]),
            })

        return {
            "resourceKind": rule["resource_kind"],
            "adapterKind": rule["adapter_kind"],
            "rules": ui_rules,
        }

    def to_wire(self) -> dict:
        """Expand the terse YAML into the verbose JSON body the
        `/api/resources/groups` POST endpoint expects.

        See context/customgroup_authoring.md for the grammar.
        """
        return {
            "resourceKey": {
                "name": self.name,
                "adapterKindKey": "Container",
                "resourceKindKey": self.type_key,
                "resourceIdentifiers": [],
            },
            "autoResolveMembership": self.auto_resolve_membership,
            "membershipDefinition": {
                "includedResources": [],
                "excludedResources": [],
                "custom-group-properties": [],
                "rules": [self._rule_to_wire(r) for r in self.rules],
            },
        }

    @staticmethod
    def _rule_to_wire(rule: dict) -> dict:
        return {
            "resourceKindKey": {
                "resourceKind": rule["resource_kind"],
                "adapterKind": rule["adapter_kind"],
            },
            "statConditionRules": [
                {
                    "key": c["key"],
                    "doubleValue": float(c["value"]),
                    "compareOperator": c["op"],
                }
                for c in rule.get("stat") or []
            ],
            "propertyConditionRules": [
                _property_condition_to_wire(c)
                for c in rule.get("property") or []
            ],
            "resourceNameConditionRules": [
                {"name": c["value"], "compareOperator": c["op"]}
                for c in rule.get("name") or []
            ],
            "relationshipConditionRules": [
                _relationship_condition_to_wire(c)
                for c in rule.get("relationship") or []
            ],
            "resourceTagConditionRules": [
                {
                    "category": c["category"],
                    "stringValue": str(c["value"]),
                    "compareOperator": c["op"],
                }
                for c in rule.get("tag") or []
            ],
        }


def _property_condition_to_wire(c: dict) -> dict:
    """Properties carry either a string or a numeric value. Pick the
    right wire field based on the YAML value's Python type."""
    out = {"key": c["key"], "compareOperator": c["op"]}
    val = c["value"]
    if isinstance(val, bool):
        # Treat booleans as strings ("true"/"false") since the API
        # doesn't have a boolean variant.
        out["stringValue"] = "true" if val else "false"
    elif isinstance(val, (int, float)):
        out["doubleValue"] = float(val)
    else:
        out["stringValue"] = str(val)
    return out


def _relationship_condition_to_wire(c: dict) -> dict:
    out = {
        "relation": c["relation"],
        "name": c["name"],
        "compareOperator": c["op"],
    }
    # Note the upstream typo: API field is `travesalSpecId`, NOT
    # `traversalSpecId`. Documented in customgroup_authoring.md.
    if c.get("traversal_spec_id"):
        out["travesalSpecId"] = c["traversal_spec_id"]
    return out


def load_file(path: str | Path) -> CustomGroupDef:
    path = Path(path)
    try:
        data = _strict_load(path.read_text()) or {}
    except yaml.constructor.ConstructorError as exc:
        raise CustomGroupValidationError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CustomGroupValidationError(
            f"{path}: expected a YAML mapping"
        )
    cg = CustomGroupDef(
        name=str(data.get("name", "")).strip(),
        description=str(data.get("description", "") or "").strip(),
        type_key=str(data.get("type", "Environment") or "Environment").strip(),
        auto_resolve_membership=bool(
            data.get("auto_resolve_membership", True)
        ),
        rules=list(data.get("rules") or []),
        source_path=path,
    )
    cg.validate()
    return cg


def load_dir(directory: str | Path = "customgroups") -> List[CustomGroupDef]:
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[CustomGroupDef] = []
    seen: dict[str, Path] = {}
    for p in sorted(directory.rglob("*.y*ml")):
        cg = load_file(p)
        if cg.name in seen:
            raise CustomGroupValidationError(
                f"duplicate custom group name '{cg.name}' in "
                f"{p} and {seen[cg.name]}"
            )
        seen[cg.name] = p
        out.append(cg)
    return out


def collect_required_types(defs: List[CustomGroupDef]) -> List[str]:
    """Return the unique sorted list of group type keys referenced
    by the given definitions. Used by sync to ensure all required
    types exist on the instance before group instances are POSTed.
    """
    return sorted({d.type_key for d in defs})
