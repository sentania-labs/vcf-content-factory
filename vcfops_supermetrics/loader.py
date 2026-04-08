"""Load and validate super metric YAML definitions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List

import yaml


class SuperMetricValidationError(ValueError):
    pass


# Looping functions accepted by VCF Ops super metric DSL.
LOOPING_FUNCS = {"avg", "sum", "min", "max", "count", "combine"}
SINGLE_FUNCS = {
    "abs", "acos", "asin", "atan", "ceil", "cos", "cosh",
    "exp", "floor", "log", "log10", "pow", "rand", "sin",
    "sinh", "sqrt", "tan", "tanh",
}


@dataclass
class SuperMetricDef:
    name: str
    formula: str
    description: str = ""
    resource_kinds: list = None  # list of {"resourceKindKey","adapterKindKey"}
    source_path: Path | None = None

    def validate(self) -> None:
        if not self.name or not self.name.strip():
            raise SuperMetricValidationError("name is required")
        if not self.formula or not self.formula.strip():
            raise SuperMetricValidationError(f"{self.name}: formula is required")
        if not self.resource_kinds:
            raise SuperMetricValidationError(
                f"{self.name}: resource_kinds is required "
                f"(e.g. [{{resource_kind_key: VirtualMachine, adapter_kind_key: VMWARE}}])"
            )
        for rk in self.resource_kinds:
            if not isinstance(rk, dict):
                raise SuperMetricValidationError(
                    f"{self.name}: each resource_kinds entry must be a mapping"
                )
            if not rk.get("resourceKindKey"):
                raise SuperMetricValidationError(
                    f"{self.name}: resource_kinds entry missing resource_kind_key"
                )
            if not rk.get("adapterKindKey"):
                raise SuperMetricValidationError(
                    f"{self.name}: resource_kinds entry missing adapter_kind_key"
                )

        f = self.formula

        # Balanced parens / braces / brackets.
        for opener, closer in (("(", ")"), ("{", "}"), ("[", "]")):
            if f.count(opener) != f.count(closer):
                raise SuperMetricValidationError(
                    f"{self.name}: unbalanced '{opener}{closer}' in formula"
                )

        # Must contain at least one resource entry.
        resource_entries = re.findall(r"\$\{[^}]*\}", f)
        if not resource_entries:
            raise SuperMetricValidationError(
                f"{self.name}: formula contains no ${{...}} resource entry"
            )

        for entry in resource_entries:
            self._validate_resource_entry(entry)

        # depth=0 is illegal per VCF docs.
        for m in re.finditer(r"depth\s*=\s*(-?\d+)", f):
            if int(m.group(1)) == 0:
                raise SuperMetricValidationError(
                    f"{self.name}: depth=0 is not allowed"
                )

    def _validate_resource_entry(self, entry: str) -> None:
        inner = entry[2:-1].strip()  # strip ${ }
        if not inner:
            raise SuperMetricValidationError(
                f"{self.name}: empty resource entry ${{}}"
            )
        # Either 'this, ...' bound to assigned object, or must specify
        # adaptertype + (objecttype OR resourcename).
        head = inner.split(",", 1)[0].strip().lower()
        if head == "this":
            return
        lower = inner.lower()
        if "adaptertype" not in lower:
            raise SuperMetricValidationError(
                f"{self.name}: resource entry must include 'adaptertype=' "
                f"or start with 'this': {entry}"
            )
        if "objecttype" not in lower and "resourcename" not in lower:
            raise SuperMetricValidationError(
                f"{self.name}: resource entry must include 'objecttype=' "
                f"or 'resourcename=': {entry}"
            )
        if "metric=" not in lower and "attribute=" not in lower:
            raise SuperMetricValidationError(
                f"{self.name}: resource entry must include 'metric=' "
                f"or 'attribute=': {entry}"
            )


def load_file(path: str | Path) -> SuperMetricDef:
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SuperMetricValidationError(f"{path}: expected a YAML mapping")
    raw_rks = data.get("resource_kinds") or []
    rks: list = []
    for rk in raw_rks:
        if not isinstance(rk, dict):
            raise SuperMetricValidationError(
                f"{path}: resource_kinds entries must be mappings"
            )
        rks.append(
            {
                "resourceKindKey": str(
                    rk.get("resource_kind_key") or rk.get("resourceKindKey") or ""
                ).strip(),
                "adapterKindKey": str(
                    rk.get("adapter_kind_key")
                    or rk.get("adapterKindKey")
                    or "VMWARE"
                ).strip(),
            }
        )
    sm = SuperMetricDef(
        name=str(data.get("name", "")).strip(),
        formula=str(data.get("formula", "")).strip(),
        description=str(data.get("description", "") or "").strip(),
        resource_kinds=rks,
        source_path=path,
    )
    sm.validate()
    return sm


def load_dir(directory: str | Path = "supermetrics") -> List[SuperMetricDef]:
    directory = Path(directory)
    if not directory.exists():
        return []
    out: List[SuperMetricDef] = []
    seen: dict[str, Path] = {}
    for p in sorted(directory.rglob("*.y*ml")):
        sm = load_file(p)
        if sm.name in seen:
            raise SuperMetricValidationError(
                f"duplicate super metric name '{sm.name}' "
                f"in {p} and {seen[sm.name]}"
            )
        seen[sm.name] = p
        out.append(sm)
    return out
