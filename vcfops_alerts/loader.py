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
      - name: "[VCF Content Factory] VM CPU Remediation"
        priority: 1

The alert loader validates:
  1. Required fields are present and non-empty.
  2. All symptom references are grounded — either in the local
     symptoms/ directory OR explicitly flagged as built-in.
  3. Operators and criticality values are in the accepted sets.
  4. Symptom name uniqueness within a set (duplicate references are
     allowed by the API but are almost always a YAML authoring mistake).
  5. Recommendation references are grounded — all names with the
     [VCF Content Factory] prefix must exist in the local
     recommendations/ directory.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------

@dataclass
class Recommendation:
    """A standalone recommendation definition loaded from recommendations/*.yaml.

    YAML schema:
        name: "[VCF Content Factory] VM CPU Remediation"
        description: |
          Investigate the VM's CPU workload...
        adapter_kind: VMWARE
    """
    name: str
    description: str
    adapter_kind: str
    source_file: Optional[Path] = None

    @property
    def id(self) -> str:
        """Deterministic ID matching AlertContent.xml ref= convention.

        Pattern: Recommendation-df-<adapter_kind>-<slug>
        where <slug> is the name with [VCF Content Factory] stripped
        and spaces/special chars replaced with underscores.
        """
        # Strip the [VCF Content Factory] prefix
        stripped = re.sub(r"^\[VCF Content Factory\]\s*", "", self.name)
        # Replace characters outside [A-Za-z0-9_-] with underscore
        slug = re.sub(r"[^\w\-]", "_", stripped)
        # Collapse consecutive underscores
        slug = re.sub(r"_+", "_", slug).strip("_")
        return f"Recommendation-df-{self.adapter_kind}-{slug}"


@dataclass
class RecommendationRef:
    """A reference from an alert to a recommendation by name + priority."""
    name: str
    priority: int


# ---------------------------------------------------------------------------
# Alert dataclass
# ---------------------------------------------------------------------------

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
    recommendations: List[RecommendationRef] = field(default_factory=list)
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

    def validate_recommendation_refs(
        self, recommendation_map: Dict[str, "Recommendation"]
    ) -> None:
        """Validate that all recommendation references resolve.

        Only references with the [VCF Content Factory] prefix are checked —
        built-in recommendation names are exempt (cannot enumerate without
        a live instance).

        Raises AlertValidationError with the source file path and missing
        recommendation name on failure.
        """
        for ref in self.recommendations:
            if ref.name.startswith("[VCF Content Factory]"):
                if ref.name not in recommendation_map:
                    src = f" ({self.source_path})" if self.source_path else ""
                    raise AlertValidationError(
                        f"{self.name}{src}: references recommendation "
                        f"{ref.name!r} which is not in recommendations/. "
                        f"Create the recommendation file first."
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

        # Recommendations are passed via AlertContent.xml (content-zip path),
        # not via the REST POST path.  The to_wire() method is used for
        # direct REST sync; recommendation references are omitted here.
        # The sync client resolves recommendations at AlertContent.xml build
        # time, not at REST time.

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


# ---------------------------------------------------------------------------
# Recommendation loading
# ---------------------------------------------------------------------------

def load_recommendation_file(path: str | Path) -> Recommendation:
    """Load a single recommendation YAML file."""
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise AlertValidationError(f"{path}: expected a YAML mapping")

    name = str(data.get("name", "")).strip()
    if not name:
        raise AlertValidationError(f"{path}: 'name' is required")
    description = str(data.get("description", "") or "").strip()
    if not description:
        raise AlertValidationError(f"{path}: 'description' is required")
    adapter_kind = str(data.get("adapter_kind", "") or "").strip()
    if not adapter_kind:
        raise AlertValidationError(f"{path}: 'adapter_kind' is required")

    return Recommendation(
        name=name,
        description=description,
        adapter_kind=adapter_kind,
        source_file=path,
    )


def load_recommendations(directory: str | Path = "recommendations") -> List[Recommendation]:
    """Load all recommendation YAML files from a directory.

    Following the pattern of load_symptoms() / load_alerts():
    - Skips non-YAML files (e.g. .gitkeep)
    - Raises on duplicate names
    - Returns an empty list if the directory does not exist
    """
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[Recommendation] = []
    seen: Dict[str, Path] = {}
    for p in sorted(directory.rglob("*.y*ml")):
        rec = load_recommendation_file(p)
        if rec.name in seen:
            raise AlertValidationError(
                f"duplicate recommendation name '{rec.name}' "
                f"in {p} and {seen[rec.name]}"
            )
        seen[rec.name] = p
        out.append(rec)
    return out


def resolve_alert_recommendations(
    alert: AlertDef,
    recommendation_map: Dict[str, Recommendation],
) -> List[Tuple[int, Recommendation]]:
    """Resolve an alert's recommendation refs to (priority, Recommendation) pairs.

    Called at validate/render time.  Raises AlertValidationError for any
    [VCF Content Factory] recommendation name that is not in the map.

    Returns:
        List of (priority, Recommendation) tuples, sorted by priority.
    """
    result: List[Tuple[int, Recommendation]] = []
    for ref in alert.recommendations:
        rec = recommendation_map.get(ref.name)
        if rec is None:
            if ref.name.startswith("[VCF Content Factory]"):
                src = f" ({alert.source_path})" if alert.source_path else ""
                raise AlertValidationError(
                    f"{alert.name}{src}: references recommendation "
                    f"{ref.name!r} which is not in recommendations/. "
                    f"Create the recommendation file first."
                )
            # Non-VCF prefix: treat as built-in, skip resolution
            continue
        result.append((ref.priority, rec))
    result.sort(key=lambda t: t[0])
    return result


# ---------------------------------------------------------------------------
# Alert file / dir loading
# ---------------------------------------------------------------------------

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

    # Parse recommendations as list of RecommendationRef objects.
    # Supports two forms:
    #   New form: {name: "...", priority: 1}  — references a standalone
    #       recommendations/*.yaml by name; validated at cross-ref time.
    #   Legacy form: {description: "..."}  — inline text from old alert YAML.
    #       These are accepted but produce no RecommendationRef; the inline
    #       text is silently dropped at render time.  Existing alert YAMLs
    #       with this form will still validate without error.
    raw_recs = data.get("recommendations") or []
    if not isinstance(raw_recs, list):
        raise AlertValidationError(f"{path}: recommendations must be a list")

    rec_refs: List[RecommendationRef] = []
    for i, r in enumerate(raw_recs):
        if not isinstance(r, dict):
            raise AlertValidationError(
                f"{path}: recommendations[{i}] must be a mapping"
            )
        rec_name = str(r.get("name", "") or "").strip()
        if not rec_name:
            # Legacy inline-description form — skip silently (no cross-ref).
            continue
        rec_priority = r.get("priority", 1)
        try:
            rec_priority = int(rec_priority)
        except (TypeError, ValueError):
            raise AlertValidationError(
                f"{path}: recommendations[{i}]: 'priority' must be an integer"
            )
        rec_refs.append(RecommendationRef(name=rec_name, priority=rec_priority))

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
        recommendations=rec_refs,
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
