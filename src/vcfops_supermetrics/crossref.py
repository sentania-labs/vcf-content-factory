"""Shared resolver for ``@supermetric:"<name>"`` formula cross-references.

Authors write SM-to-SM references in a formula by *name*, never by raw UUID
(the ``vcfops-project-conventions`` skill, "Cross-reference syntax"):

    ${this, metric=cpu|demandmhz} / ${this, attribute=@supermetric:"[VCF Content Factory] Cluster Capacity"}

VCF Ops cannot parse ``@supermetric:``.  The wire form is
``Super Metric|sm_<uuid>``, confirmed against the vCommunity source pak whose
``describe.xml``-referenced SM formulas use exactly that prefix.  Every code
path that *emits* a formula into a pak / bundle / zip, or *pushes* one to a
live instance, must therefore resolve the token first.

This module is the single home of that resolution.  It previously lived only
in ``vcfops_managementpacks.sdk_builder`` (Tier 2 pak path), which meant the
native bundle builder, the discrete/release builders and the live sync path
all shipped the literal ``@supermetric:"..."`` token verbatim.

An unresolvable name is always a hard error: emitting the literal token
produces a corrupt super metric that VCF Ops silently fails to evaluate, so
failing loudly at build/push time is strictly safer than shipping it.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Type

__all__ = [
    "SM_CROSSREF_RE",
    "SuperMetricCrossRefError",
    "crossref_names",
    "has_crossref",
    "resolve_sm_formula",
    "sm_name_to_uuid_map",
]


# One hand-written ``Super Metric|`` prefix, in any spelling an author might
# plausibly type: any case (``super metric|``, ``SUPER METRIC|``), any internal
# or trailing whitespace (``Super  Metric |``, ``Super Metric| ``).  Case is
# matched loosely on purpose: ``vcfops_packaging.deps._is_sm_ref`` lowercases
# before comparing, which is this codebase's own admission that authored prefix
# case varies.
_PREFIX_SRC = r"(?:(?i:super\s*metric)\s*\|\s*)"

# Regex matching @supermetric:"<name>" or @supermetric:'<name>' inside a formula.
# Capture group 1 is the bare SM name.
#
# Any number of leading ``Super Metric|`` prefixes are consumed deliberately.
# The token expands to the WHOLE wire term, prefix included, so an author who
# also writes the prefix by hand (``metric=Super Metric|@supermetric:"X"``)
# would otherwise get ``Super Metric|Super Metric|sm_<uuid>``, which VCF Ops
# cannot parse and which no build step would flag.  Absorbing every adjacent
# prefix, in every spelling, makes the substitution prefix-idempotent the same
# way it is already sm_<uuid>-idempotent.
SM_CROSSREF_RE = re.compile(
    _PREFIX_SRC + r'''*@supermetric:["']([^"']+)["']'''
)

# Backstop for the same class: two or more adjacent prefixes surviving
# substitution.  Absorption above should make this unreachable from an
# ``@supermetric:`` token, but a formula can also arrive already doubled with no
# token at all (hand-written, or copied out of a broken export).  Emitting that
# is as unparseable as emitting the literal token, so it is a hard error rather
# than a silent passthrough.
_DOUBLED_PREFIX_RE = re.compile(_PREFIX_SRC + "{2,}")

# Any surviving occurrence of this literal after substitution means the formula
# carried a near-miss of the token syntax (a space after the colon, an unquoted
# name) that SM_CROSSREF_RE did not match.  Shipping it is the exact P1 this
# module exists to eliminate, so it is a hard error rather than a passthrough.
_SM_CROSSREF_LITERAL = "@supermetric"

# Default remediation hint appended to the error message.  Callers that know a
# more specific remedy (e.g. "add it to bundled_content.supermetrics in
# adapter.yaml") pass their own via ``hint``.
_DEFAULT_HINT = (
    "Add that super metric to this bundle, or remove the cross-reference "
    "from the formula."
)


class SuperMetricCrossRefError(Exception):
    """Raised when a formula references an SM name that cannot be resolved."""


def has_crossref(formula: str) -> bool:
    """Return True if ``formula`` carries at least one ``@supermetric:`` token."""
    return bool(SM_CROSSREF_RE.search(formula or ""))


def crossref_names(formula: str) -> List[str]:
    """Return every SM name referenced by ``formula``, in order of appearance."""
    return SM_CROSSREF_RE.findall(formula or "")


def sm_name_to_uuid_map(supermetrics: Iterable) -> Dict[str, Optional[str]]:
    """Build the ``{name: uuid}`` lookup from an iterable of SuperMetricDef.

    Accepts anything exposing ``.name`` and ``.id``.  An SM with no ``id`` is
    kept with a ``None`` value rather than dropped, so that a reference to it
    reports the real cause ("in scope but has no id") instead of the generic
    "could not be resolved".
    """
    return {sm.name: (getattr(sm, "id", None) or None) for sm in supermetrics}


def resolve_sm_formula(
    formula: str,
    sm_name: str,
    sm_name_to_uuid: Mapping[str, Optional[str]],
    *,
    error_cls: Type[Exception] = SuperMetricCrossRefError,
    hint: str = _DEFAULT_HINT,
    fallback_lookup: Optional[Callable[[str], Optional[str]]] = None,
) -> str:
    """Resolve ``@supermetric:"<name>"`` cross-reference tokens in a formula.

    Replaces each ``@supermetric:"<name>"`` (or single-quoted variant) with the
    wire token ``Super Metric|sm_<uuid>`` where ``<uuid>`` is the super metric
    whose ``name`` matches ``<name>`` exactly.

    Args:
        formula:          Raw formula string from the YAML ``formula:`` field.
        sm_name:          Display name of the SM being emitted (error messages).
        sm_name_to_uuid:  Mapping of in-scope SM display name -> UUID.
        error_cls:        Exception type raised on an unresolvable name, so each
                          caller keeps its own error taxonomy (SdkBuildError for
                          the pak path, VCFOpsError for the live sync path).
        hint:             Caller-specific remediation sentence appended to the
                          error message.
        fallback_lookup:  Optional callable ``name -> uuid or None`` consulted
                          only when ``sm_name_to_uuid`` misses.  The live sync
                          path uses this to resolve against super metrics that
                          already exist on the target instance.

    Returns:
        Formula with all ``@supermetric:`` tokens replaced.

    Raises:
        error_cls: If a token references a name that neither ``sm_name_to_uuid``
            nor ``fallback_lookup`` can resolve, or if a literal ``@supermetric``
            survives substitution (malformed reference syntax).

    Already-resolved ``Super Metric|sm_<uuid>`` tokens are left untouched
    (idempotent), so this function is safe to call on already-resolved formulas.
    A formula with no ``@supermetric:`` token is returned unchanged.

    Immediately-preceding ``Super Metric|`` prefixes are absorbed into the
    match, in any case and spacing and however many of them there are, so
    ``metric=Super Metric|@supermetric:"X"`` (and ``super metric| ``,
    ``SUPER METRIC|``, ``Super Metric|Super Metric|``) all resolve to a single
    ``metric=Super Metric|sm_<uuid>`` rather than a doubled prefix.  A doubled
    prefix that survives anyway raises ``error_cls``: it can never be emitted
    silently.

    A malformed near-miss (``@supermetric: "X"`` with a space, ``@supermetric:X``
    unquoted) raises ``error_cls`` instead of passing the literal token through.
    """
    if not formula:
        return formula

    def _replace(m: "re.Match") -> str:
        ref_name = m.group(1)
        uuid = sm_name_to_uuid.get(ref_name)
        if uuid is None and fallback_lookup is not None:
            uuid = fallback_lookup(ref_name)
        if uuid is None:
            if ref_name in sm_name_to_uuid:
                raise error_cls(
                    f"Super metric '{sm_name}': formula references "
                    f"@supermetric:\"{ref_name}\" and that super metric is in "
                    f"scope but carries no id, so it has no sm_<uuid> to "
                    f"reference.  Give it an 'id:' in its YAML."
                )
            raise error_cls(
                f"Super metric '{sm_name}': formula references "
                f"@supermetric:\"{ref_name}\" but that super metric could not "
                f"be resolved.  {hint}"
            )
        return f"Super Metric|sm_{uuid}"

    resolved = SM_CROSSREF_RE.sub(_replace, formula)

    # Post-substitution guards.  Both close the same class of defect: a formula
    # that VCF Ops cannot parse leaving this function without anyone noticing.
    #
    # 1. Near-miss syntax: @supermetric: followed by a space, or an unquoted
    #    name, does not match SM_CROSSREF_RE and would otherwise ship the
    #    literal token into the pak / bundle / live instance.
    if _SM_CROSSREF_LITERAL in resolved:
        raise error_cls(
            f"Super metric '{sm_name}': formula still contains a literal "
            f"'@supermetric' after cross-reference resolution, so the "
            f"reference syntax is malformed.  The only accepted form is "
            f"@supermetric:\"<exact name>\" (double or single quotes, no "
            f"space after the colon)."
        )

    # 2. Doubled wire prefix.  Absorption should have prevented this, so a hit
    #    means the formula arrived already doubled with no token to absorb it.
    if _DOUBLED_PREFIX_RE.search(resolved):
        raise error_cls(
            f"Super metric '{sm_name}': formula contains a doubled "
            f"'Super Metric|Super Metric|' prefix, which VCF Ops cannot parse. "
            f"The wire form carries exactly one prefix: write "
            f"metric=@supermetric:\"<exact name>\" and the resolver supplies "
            f"the single 'Super Metric|' itself."
        )
    return resolved
