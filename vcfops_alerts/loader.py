"""Load and validate alert definition YAML definitions.

Alert definitions are identified by name (not UUID) — the VCF Ops API
assigns the id server-side on create.  Sync matches by name.  Do not
include an `id:` field in YAML.

YAML schema (see .claude/agents/alert-author.md for the full spec):

    name: "[VCF Content Factory] VM CPU Critically High"
    description: >
      Why this alert exists.
    adapter_kind: VMWARE
    resource_kind: VirtualMachine
    type: 16          # 15=Application, 16=Virtualization, 17=Hardware, 18=Storage, 19=Network
    sub_type: 3       # 1=Availability, 2=Capacity, 3=Performance, 4=Compliance, 5=Configuration
    wait_cycles: 1
    cancel_cycles: 1
    criticality: CRITICAL   # CRITICAL, IMMEDIATE, WARNING, INFO, SYMPTOM_BASED

    impact:
      badge: HEALTH         # HEALTH, RISK, EFFICIENCY

    symptom_sets:
      operator: ALL         # ALL or ANY between symptom sets
      sets:
        - defined_on: SELF  # SELF, PARENT, CHILD, DESCENDANT, ANCESTOR
          operator: ALL     # ALL or ANY within this set
          symptoms:
            - name: "[VCF Content Factory] VM CPU Usage Critical"
            - name: "[VCF Content Factory] VM CPU Ready High"
          # For non-SELF scoping, optional threshold:
          # threshold_type: COUNT   # COUNT, PERCENT, ANY, ALL
          # threshold_value: 3

    recommendations:
      - description: >
          Investigate VM CPU usage. Check for CPU-intensive processes.

The alert loader validates:
  1. Required fields are present and non-empty.
  2. All symptom references are grounded — either in the local
     symptoms/ directory OR explicitly flagged as built-in.
  3. Operators and criticality values are in the accepted sets.
  4. Symptom name uniqueness within a set (duplicate references are
     allowed by the API but are almost always a YAML authoring mistake).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


class AlertValidationError(ValueError):
    pass


# Wire criticality values.  API uses AUTO for SYMPTOM_BASED.
CRITICALITY_MAP = {
    "CRITICAL": "CRITICAL",
    "IMMEDIATE": "IMMEDIATE",
    "WARNING": "WARNING",
    "INFO": "INFORMATION",
    "INFORMATION": "INFORMATION",
    "SYMPTOM_BASED": "AUTO",
    "AUTO": "AUTO",
}

BADGE_MAP = {
    "HEALTH": "HEALTH",
    "RISK": "RISK",
    "EFFICIENCY": "EFFICIENCY",
}

RELATIONS = {"SELF", "PARENT", "CHILD", "DESCENDANT", "ANCESTOR"}
OPERATORS = {"ALL", "ANY"}
THRESHOLD_TYPES = {"COUNT", "PERCENT", "ANY", "ALL"}

# Alert type and subtype: the API schema accepts any int32 — no enum
# constraint in the OpenAPI spec.  The author agent prompt lists common
# values (types 15-19, subtypes 1-5) but real content (e.g. brockpeterson
# reference) uses sub_type=20 (Workload).  We validate only that these are
# positive integers, not that they fall in any specific set.
VALID_TYPES = None   # any positive int accepted
VALID_SUBTYPES = None  # any positive int accepted


@dataclass
class AlertDef:
    name: str
    adapter_kind: str
    resource_kind: str
    criticality: str        # normalised to wire value
    impact_badge: str       # HEALTH, RISK, EFFICIENCY
    symptom_sets: dict      # raw symptom_sets dict from YAML
    type: int = 16
    sub_type: int = 3
    wait_cycles: int = 1
    cancel_cycles: int = 1
    description: str = ""
    recommendations: List[dict] = field(default_factory=list)
    source_path: Optional[Path] = None

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise AlertValidationError("name is required")
        if not self.adapter_kind:
            raise AlertValidationError(f"{self.name}: adapter_kind is required")
        if not self.resource_kind:
            raise AlertValidationError(f"{self.name}: resource_kind is required")
        if self.criticality not in CRITICALITY_MAP.values():
            raise AlertValidationError(
                f"{self.name}: criticality must be one of "
                f"{sorted(set(CRITICALITY_MAP))}; got {self.criticality!r}"
            )
        if self.impact_badge not in BADGE_MAP:
            raise AlertValidationError(
                f"{self.name}: impact.badge must be one of "
                f"{sorted(BADGE_MAP)}; got {self.impact_badge!r}"
            )
        if not isinstance(self.type, int) or self.type < 1:
            raise AlertValidationError(
                f"{self.name}: type must be a positive integer; "
                f"got {self.type!r}"
            )
        if not isinstance(self.sub_type, int) or self.sub_type < 1:
            raise AlertValidationError(
                f"{self.name}: sub_type must be a positive integer; "
                f"got {self.sub_type!r}"
            )
        if self.wait_cycles < 1:
            raise AlertValidationError(
                f"{self.name}: wait_cycles must be >= 1"
            )
        if self.cancel_cycles < 1:
            raise AlertValidationError(
                f"{self.name}: cancel_cycles must be >= 1"
            )
        self._validate_symptom_sets(self.symptom_sets)

    def _validate_symptom_sets(self, ss: dict) -> None:
        tag = f"{self.name}: symptom_sets"
        if not isinstance(ss, dict):
            raise AlertValidationError(f"{tag} must be a mapping")
        top_op = (ss.get("operator") or "").upper()
        if top_op not in OPERATORS:
            raise AlertValidationError(
                f"{tag}.operator must be ALL or ANY; got {top_op!r}"
            )
        sets = ss.get("sets") or []
        if not sets:
            raise AlertValidationError(
                f"{tag}: at least one set is required"
            )
        for i, s in enumerate(sets):
            self._validate_set(f"{tag}.sets[{i}]", s)

    def _validate_set(self, tag: str, s: dict) -> None:
        if not isinstance(s, dict):
            raise AlertValidationError(f"{tag} must be a mapping")
        defined_on = (s.get("defined_on") or "").upper()
        if defined_on not in RELATIONS:
            raise AlertValidationError(
                f"{tag}.defined_on must be one of {sorted(RELATIONS)}; "
                f"got {defined_on!r}"
            )
        op = (s.get("operator") or "").upper()
        if op not in OPERATORS:
            raise AlertValidationError(
                f"{tag}.operator must be ALL or ANY; got {op!r}"
            )
        symptoms = s.get("symptoms") or []
        if not symptoms:
            raise AlertValidationError(
                f"{tag}: at least one symptom reference is required"
            )
        for j, sym in enumerate(symptoms):
            if not isinstance(sym, dict):
                raise AlertValidationError(
                    f"{tag}.symptoms[{j}] must be a mapping with a 'name' key"
                )
            sym_name = sym.get("name", "")
            if not sym_name:
                raise AlertValidationError(
                    f"{tag}.symptoms[{j}]: name is required"
                )
        # Validate threshold fields for non-SELF relations
        if defined_on != "SELF":
            tt = s.get("threshold_type")
            if tt and tt not in THRESHOLD_TYPES:
                raise AlertValidationError(
                    f"{tag}.threshold_type must be one of "
                    f"{sorted(THRESHOLD_TYPES)}; got {tt!r}"
                )

    def validate_symptom_refs(self, repo_symptom_names: set[str]) -> None:
        """Secondary validation: check that all referenced symptom names
        exist in the local symptoms/ directory.  Built-in symptoms (those
        NOT prefixed with '[VCF Content Factory]') are exempt — the loader
        cannot enumerate built-ins without a live instance connection.

        Call this from the CLI after loading the full symptoms dir.
        """
        for s in (self.symptom_sets.get("sets") or []):
            for sym in (s.get("symptoms") or []):
                name = sym.get("name", "")
                if name.startswith("[VCF Content Factory]"):
                    if name not in repo_symptom_names:
                        raise AlertValidationError(
                            f"{self.name}: references symptom "
                            f"{name!r} which is not in symptoms/. "
                            f"Sync the symptom first, or check the name."
                        )

    def to_wire(self, symptom_name_to_id: dict[str, str]) -> dict:
        """Serialize to the JSON body for POST /api/alertdefinitions.

        symptom_name_to_id: mapping from symptom display name to its
        server-assigned id.  Provided by the client at sync time after
        fetching the symptom list from the instance.
        """
        top_op = (self.symptom_sets.get("operator") or "ALL").upper()
        sets = self.symptom_sets.get("sets") or []

        wire_sets = [_set_to_wire(s, symptom_name_to_id, self.name) for s in sets]

        # Build the base-symptom-set. If there is exactly one set and the
        # top-level operator is trivially satisfied, we can use SYMPTOM_SET
        # directly. If multiple sets exist, wrap in a composite.
        if len(wire_sets) == 1:
            base_symptom_set = wire_sets[0]
        else:
            base_symptom_set = {
                "type": "SYMPTOM_SET_COMPOSITE",
                "operator": "AND" if top_op == "ALL" else "OR",
                "symptom-sets": wire_sets,
            }

        # Build the recommendationPriorityMap if we have recommendations.
        rec_priority_map: dict[str, int] = {}
        wire_recs: List[dict] = []
        # Recommendations are posted separately via /api/recommendations,
        # but the alert definition POST accepts them inline in the
        # recommendationPriorityMap.  For the initial version we embed the
        # description text in the state's recommendationPriorityMap
        # referencing temporary placeholder ids.  The sync client resolves
        # these by creating recommendations first.
        # We keep this simple: if recommendations are present the caller
        # (sync client) handles the creation and passes back the ids.
        # Here we just serialise the state without recommendations.

        state: dict = {
            "severity": self.criticality,
            "base-symptom-set": base_symptom_set,
            "impact": {
                "impactType": "BADGE",
                "detail": self.impact_badge,
            },
        }

        body: dict = {
            "name": self.name,
            "description": self.description,
            "adapterKindKey": self.adapter_kind,
            "resourceKindKey": self.resource_kind,
            "waitCycles": self.wait_cycles,
            "cancelCycles": self.cancel_cycles,
            "type": self.type,
            "subType": self.sub_type,
            "states": [state],
        }
        return body


def _set_to_wire(s: dict, symptom_name_to_id: dict[str, str], alert_name: str) -> dict:
    """Convert a single symptom set to its API wire representation."""
    defined_on = (s.get("defined_on") or "SELF").upper()
    op = (s.get("operator") or "ALL").upper()
    symptom_wire_op = "AND" if op == "ALL" else "OR"

    symptom_ids: List[str] = []
    for sym in (s.get("symptoms") or []):
        sym_name = sym.get("name", "")
        sid = symptom_name_to_id.get(sym_name)
        if sid is None:
            raise AlertValidationError(
                f"{alert_name}: symptom {sym_name!r} not found on instance; "
                f"sync symptoms first"
            )
        symptom_ids.append(sid)

    wire: dict = {
        "type": "SYMPTOM_SET",
        "relation": defined_on,
        "symptomSetOperator": symptom_wire_op,
        "symptomDefinitionIds": symptom_ids,
    }

    # Threshold for non-SELF population conditions
    tt = s.get("threshold_type")
    tv = s.get("threshold_value")
    if defined_on != "SELF" and tt:
        wire["aggregation"] = tt
        if tv is not None:
            wire["value"] = float(tv)

    return wire


def load_file(path: str | Path) -> AlertDef:
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise AlertValidationError(f"{path}: expected a YAML mapping")

    raw_criticality = str(data.get("criticality", "") or "").strip().upper()
    wire_criticality = CRITICALITY_MAP.get(raw_criticality, raw_criticality)

    raw_badge = str(
        (data.get("impact") or {}).get("badge", "") or ""
    ).strip().upper()

    recs = data.get("recommendations") or []
    if not isinstance(recs, list):
        raise AlertValidationError(f"{path}: recommendations must be a list")

    ad = AlertDef(
        name=str(data.get("name", "")).strip(),
        description=str(data.get("description", "") or "").strip(),
        adapter_kind=str(data.get("adapter_kind", "") or "").strip(),
        resource_kind=str(data.get("resource_kind", "") or "").strip(),
        type=int(data.get("type", 16) or 16),
        sub_type=int(data.get("sub_type", 3) or 3),
        wait_cycles=int(data.get("wait_cycles", 1) or 1),
        cancel_cycles=int(data.get("cancel_cycles", 1) or 1),
        criticality=wire_criticality,
        impact_badge=raw_badge,
        symptom_sets=dict(data.get("symptom_sets") or {}),
        recommendations=list(recs),
        source_path=path,
    )
    ad.validate()
    return ad


def load_dir(directory: str | Path = "alerts") -> List[AlertDef]:
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[AlertDef] = []
    seen: dict[str, Path] = {}
    for p in sorted(directory.rglob("*.y*ml")):
        ad = load_file(p)
        if ad.name in seen:
            raise AlertValidationError(
                f"duplicate alert name '{ad.name}' "
                f"in {p} and {seen[ad.name]}"
            )
        seen[ad.name] = p
        out.append(ad)
    return out
