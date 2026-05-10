"""Cross-validate rendered template.json against describe.xml/YAML definitions.

Simulates the consistency rules that ``BuilderFile.Companion.read()`` enforces
at install time, so failures are caught locally before shipping a pak to a live
VCF Ops instance.

The validator renders both the template.json (via ``render_template_json()``)
and derives the describe.xml key-sets from the ManagementPackDef directly
(same data the builder uses).  It does NOT build the actual .pak file.

Rule catalogue
--------------
Rule 1 — Identifier key consistency
    For each resource in template.json, every ``identifiers[].key`` must match
    a ``ResourceIdentifier key=`` in the describe.xml for that resource kind.
    The builder emits ``adapter_instance_id`` plus each ``ot.identifiers[].key``
    for data kinds.  The renderer derives identifier keys from the metric whose
    ID matches each ``identifierIds`` entry.

Rule 2 — Metric/property key consistency
    For each resource in template.json, every ``requestedMetrics[].metrics[].key``
    must match a ``ResourceAttribute key=`` in describe.xml for that resource kind.
    The builder emits each ``m.key`` on the object type's metrics list.

Rule 3 — Relationship matchIdentifier key consistency
    Parent ``matchIdentifiers[].key`` must exist in the parent resource's
    ``identifiers[].key`` set.  Child ``matchIdentifiers[].key`` must exist
    in the child resource's metric key set (from all requestedMetrics).

Rule 4 — objectBinding null-count rule
    At most one ``requestedMetrics`` entry per resource may have
    ``objectBinding: null``.

Rule 5 — ATTRIBUTE_TO_PROPERTY resourceMatchers non-empty
    Any objectBinding with ``type: "ATTRIBUTE_TO_PROPERTY"`` must have a
    non-empty ``resourceMatchers`` array and every UUID referenced in
    ``resourceMatcherExpression`` (inside ``${...}``) must match a
    ``resourceMatchers[].id``.

Rule 6 — SINGLE_SELECTION config default non-empty
    Any ``configuration`` entry with ``type: "SINGLE_SELECTION"`` must have
    a non-empty ``default`` value.

Rule 7 — Metric key format
    All metric keys must match ``/^[a-z][a-z0-9_]*$/`` (lower-case snake_case,
    start with a letter).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from .loader import ManagementPackDef
from .render_template import render_template_json

# Rule 7: valid metric key pattern
_METRIC_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Pattern to extract UUID tokens from ${<uuid>} expressions (Rule 5)
_UUID_TOKEN_RE = re.compile(r"\$\{([^}]+)\}")


def _describe_identifier_keys(mp: ManagementPackDef, resource_kind: str) -> Set[str]:
    """Return the set of ResourceIdentifier keys the builder would emit for a resource kind.

    The builder's ``_append_data_kind()`` always emits ``adapter_instance_id``
    first, followed by each ``ident.key`` from ``ot.identifiers``.

    The adapter instance kind (type=7) uses the adapter_kind key itself and
    carries mpb_* connection identifiers, not the data-kind identifiers.

    Parameters
    ----------
    mp:
        The loaded management pack definition.
    resource_kind:
        The full resource kind key as it appears in template.json
        (e.g. ``mpb_unifi_integration_device``).

    Returns
    -------
    Set of identifier key strings the builder emits for this resource kind,
    or an empty set if the kind is not recognised (adapter instance / world /
    relatives kinds are skipped because the template does not reference their
    identifiers in requestedMetrics).
    """
    ak = mp.adapter_kind

    # The adapter instance kind itself (type=7, key = adapter_kind) uses
    # mpb_* connection identifiers — not data identifiers.  Template resources
    # never reference these via identifiers[], so return the fixed set.
    if resource_kind == ak:
        return {
            "mpb_hostname", "mpb_port", "mpb_connection_timeout",
            "mpb_concurrent_requests", "mpb_max_retries", "mpb_ssl_config",
            "mpb_min_event_severity", "support_autodiscovery",
        }

    # Find the matching ObjectTypeDef.
    for ot in mp.object_types:
        rk_key = f"{ak}_{ot.key}" if not ot.key.startswith(ak) else ot.key
        if rk_key == resource_kind:
            # Data kinds always start with adapter_instance_id, then each declared identifier.
            keys: Set[str] = {"adapter_instance_id"}
            for ident in ot.identifiers:
                ident_key = ident.key if hasattr(ident, "key") else str(ident)
                keys.add(ident_key)
            return keys

    # Relatives and world aggregate kinds have no template resource entries.
    return set()


def _describe_metric_keys(mp: ManagementPackDef, resource_kind: str) -> Set[str]:
    """Return the set of ResourceAttribute keys the builder would emit for a resource kind.

    The builder's ``_append_data_kind()`` emits one ``ResourceAttribute`` per
    metric in ``ot.metrics`` (using ``m.key``), plus directed relationship tracking
    attributes and the generic ``{ak}_parent`` attribute in the relationships group.
    We include all of those here because the template's requestedMetrics can
    reference any of them.

    Parameters
    ----------
    mp:
        The loaded management pack definition.
    resource_kind:
        The full resource kind key as it appears in template.json.

    Returns
    -------
    Set of ResourceAttribute key strings the builder emits for this resource kind.
    """
    ak = mp.adapter_kind

    for ot in mp.object_types:
        rk_key = f"{ak}_{ot.key}" if not ot.key.startswith(ak) else ot.key
        if rk_key == resource_kind:
            keys: Set[str] = set()
            for m in ot.metrics:
                keys.add(m.key)

            # Also include directed relationship tracking attributes that the
            # builder emits in the relationships ResourceGroup:
            #   {ak}_{child_kind}_child  (for each relationship where ot is parent)
            #   {ak}_{parent_kind}_parent (for each relationship where ot is child)
            # and the generic {ak}_parent attribute.
            for rel in mp.relationships:
                if rel.parent == ot.key:
                    keys.add(f"{ak}_{rel.child}_child")
                if rel.child == ot.key:
                    keys.add(f"{ak}_{rel.parent}_parent")
            keys.add(f"{ak}_parent")

            return keys

    return set()


def validate_pak(mp: ManagementPackDef) -> List[str]:
    """Cross-validate rendered template.json against describe.xml key-sets.

    Renders the template.json via ``render_template_json()`` and checks all
    seven rules.  Does NOT build a .pak file or touch the filesystem.

    Parameters
    ----------
    mp:
        The loaded management pack definition.

    Returns
    -------
    List of error strings.  An empty list means the pak artifacts are
    internally consistent and should pass ``BuilderFile.Companion.read()``.
    """
    errors: List[str] = []

    # Render template (uses the default relationship strategy).
    try:
        template = render_template_json(mp)
    except Exception as exc:
        errors.append(f"template render failed: {exc}")
        return errors

    source = template.get("source", {})
    resources: List[Dict[str, Any]] = source.get("resources", []) or []
    configuration: List[Dict[str, Any]] = source.get("configuration", []) or []
    relationships: List[Dict[str, Any]] = template.get("relationships", []) or []

    # Build per-resource-kind lookups for Rule 3 cross-checks.
    # resource_kind -> set of identifier keys (from template identifiers[])
    template_ident_keys_by_rk: Dict[str, Set[str]] = {}
    # resource_kind -> set of metric keys (from all requestedMetrics[].metrics[])
    template_metric_keys_by_rk: Dict[str, Set[str]] = {}

    for resource in resources:
        rk = resource.get("resourceKind", "")
        ident_set: Set[str] = set()
        for ident in resource.get("identifiers", []) or []:
            k = ident.get("key", "")
            if k:
                ident_set.add(k)
        template_ident_keys_by_rk[rk] = ident_set

        metric_set: Set[str] = set()
        for rm in resource.get("requestedMetrics", []) or []:
            for m in rm.get("metrics", []) or []:
                k = m.get("key", "")
                if k:
                    metric_set.add(k)
        template_metric_keys_by_rk[rk] = metric_set

    # ------------------------------------------------------------------ #
    # Per-resource rules                                                   #
    # ------------------------------------------------------------------ #

    for resource in resources:
        rk = resource.get("resourceKind", "")

        # --- Rule 1: Identifier key consistency ---
        describe_ident_keys = _describe_identifier_keys(mp, rk)
        for ident in resource.get("identifiers", []) or []:
            k = ident.get("key", "")
            if not k:
                continue
            if describe_ident_keys and k not in describe_ident_keys:
                errors.append(
                    f"Rule 1 [{rk}]: identifier key '{k}' is in template.json "
                    f"but not in describe.xml for this resource kind. "
                    f"describe.xml keys: {sorted(describe_ident_keys)}"
                )

        # --- Rule 2: Metric/property key consistency ---
        describe_metric_keys = _describe_metric_keys(mp, rk)
        for rm in resource.get("requestedMetrics", []) or []:
            for m in rm.get("metrics", []) or []:
                k = m.get("key", "")
                if not k:
                    continue
                if describe_metric_keys and k not in describe_metric_keys:
                    errors.append(
                        f"Rule 2 [{rk}]: metric key '{k}' is in template.json "
                        f"but not in describe.xml for this resource kind. "
                        f"describe.xml keys: {sorted(describe_metric_keys)}"
                    )

                # --- Rule 7: Metric key format ---
                if k and not _METRIC_KEY_RE.match(k):
                    errors.append(
                        f"Rule 7 [{rk}]: metric key '{k}' does not match "
                        f"/^[a-z][a-z0-9_]*$/ (must be lower-case snake_case, "
                        f"starting with a letter)"
                    )

        # --- Rule 4: objectBinding null-count rule ---
        # Only applies to list resources (isListResource=true).  Scalar/singleton
        # resources (isListResource=false) have no list binding context — all of
        # their metricSets naturally carry objectBinding=null, and the MPB runtime
        # does not enforce the "at most one null" constraint on them.
        requested_metrics = resource.get("requestedMetrics", []) or []
        is_list_resource = resource.get("isListResource", True)
        if is_list_resource:
            null_binding_count = sum(
                1 for rm in requested_metrics if rm.get("objectBinding") is None
            )
            if null_binding_count > 1:
                errors.append(
                    f"Rule 4 [{rk}]: {null_binding_count} requestedMetrics entries "
                    f"have objectBinding=null; at most 1 is allowed "
                    f"(the primary metricSet). "
                    f"BuilderFile.Companion.read() will reject this."
                )

        # --- Rule 5: ATTRIBUTE_TO_PROPERTY resourceMatchers ---
        for rm in requested_metrics:
            ob = rm.get("objectBinding")
            if ob is None:
                continue
            if ob.get("type") != "ATTRIBUTE_TO_PROPERTY":
                continue

            rm_id = rm.get("id", "<unknown>")
            matchers = ob.get("resourceMatchers") or []
            if not matchers:
                errors.append(
                    f"Rule 5 [{rk}] requestedMetrics id={rm_id}: "
                    f"objectBinding type=ATTRIBUTE_TO_PROPERTY has empty "
                    f"resourceMatchers array. "
                    f"BuilderFile.Companion.read() will reject this."
                )
                continue

            matcher_ids: Set[str] = {m["id"] for m in matchers if "id" in m}
            expr = ob.get("resourceMatcherExpression", "")
            referenced_ids = set(_UUID_TOKEN_RE.findall(expr))
            missing = referenced_ids - matcher_ids
            if missing:
                errors.append(
                    f"Rule 5 [{rk}] requestedMetrics id={rm_id}: "
                    f"resourceMatcherExpression references UUID(s) {sorted(missing)} "
                    f"that are not in resourceMatchers[].id. "
                    f"BuilderFile.Companion.read() will reject with "
                    f"'fields referenced in the resource expression but do not "
                    f"have a matching ID in match identifiers'."
                )

    # ------------------------------------------------------------------ #
    # Rule 3: Relationship matchIdentifier key consistency                 #
    # ------------------------------------------------------------------ #

    for rel in relationships:
        parent = rel.get("parent", {})
        child = rel.get("child", {})
        rel_id = rel.get("id", "<unknown>")

        parent_rk = parent.get("resourceKind", "")
        child_rk = child.get("resourceKind", "")

        parent_template_idents = template_ident_keys_by_rk.get(parent_rk, set())
        child_template_metrics = template_metric_keys_by_rk.get(child_rk, set())

        for mi in parent.get("matchIdentifiers", []) or []:
            k = mi.get("key", "")
            if not k:
                continue
            if parent_template_idents and k not in parent_template_idents:
                errors.append(
                    f"Rule 3 [rel id={rel_id}]: parent matchIdentifier key '{k}' "
                    f"is not in parent resource ({parent_rk}) identifiers[]. "
                    f"Parent identifier keys: {sorted(parent_template_idents)}"
                )

        for mi in child.get("matchIdentifiers", []) or []:
            k = mi.get("key", "")
            if not k:
                continue
            if child_template_metrics and k not in child_template_metrics:
                errors.append(
                    f"Rule 3 [rel id={rel_id}]: child matchIdentifier key '{k}' "
                    f"is not in child resource ({child_rk}) metric keys. "
                    f"Child metric keys: {sorted(child_template_metrics)}"
                )

    # ------------------------------------------------------------------ #
    # Rule 6: SINGLE_SELECTION config default non-empty                   #
    # ------------------------------------------------------------------ #

    for cfg in configuration:
        if cfg.get("type") == "SINGLE_SELECTION":
            default_val = cfg.get("default", "")
            if not default_val:
                cfg_id = cfg.get("id", cfg.get("key", "<unknown>"))
                errors.append(
                    f"Rule 6 [config id={cfg_id}]: type=SINGLE_SELECTION "
                    f"has empty default value. "
                    f"BuilderFile.Companion.read() will reject this."
                )

    return errors
