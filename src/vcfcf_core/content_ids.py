"""The id grammar of each content type: the ids VCF Operations accepts on
content import, and the ids the factory's YAML loaders accept.

One definition for the loaders, the pak content gate
(:mod:`vcfcf_core.packaging.pak_content`) and the offline importer's id
minting and ``--id-map`` checks. Evidence and the full statement:
``knowledge/context/wire-formats/alert_fidelity_wire_format.md`` §Id grammar.

Two forms per type:

- the **wire id**, as it appears in the content-import XML or JSON
  (``SymptomDefinition-<x>``, ``<Recommendation key=...>``, a ViewDef
  ``id``); checked by :func:`wire_id_problem`;
- the **YAML id**, the ``id:`` a factory YAML file carries (a symptom or
  alert id is the part after its XML prefix; a recommendation id is the key
  itself); checked by :func:`yaml_id_problem`.

Measured product rule (VCF Operations 9.0.2, the pak install path only: a
pak's ``content/alertdefs/`` file, 2026-11-14; REST and content-zip sync were
not measured, and that content-zip import reaches the same service is an
inference): ``AlertDefinitionServiceImpl.importAlertDefinitions``
refuses a recommendation key ``Recommendation-<uuid>`` with ``Invalid format
of Recommendation Id: ... It should start with Recommendation-df- or
Recommendation-ud-``, and refuses the whole alert file with it (its alerts,
symptoms and recommendations never exist on the instance). A bare key
(``vCommunityCollectionWarnings``, no ``Recommendation-`` prefix) imports
(reported from the same install; the id the product stores for it is not
recorded). The pak's alert schema (``content/alertdefs/alertDefinitionSchema.xsd``,
in every SDK sample pak) types ``Recommendation/@key`` as ``xs:ID`` and every
``ref`` as ``xs:IDREF``, so a key in ``content/alertdefs/`` is also an XML id.
Every other rule here is the form every observed id has and the factory's
loaders already require; none of them has a product error on record. A
VMware-built pak (``vmware-mpforphysicalsan-8.12.0``) ships bare symptom,
alert and recommendation ids in ``content/alertdefs/`` (``SwitchPortDown``),
so the content importer accepts a symptom or alert id without its
``SymptomDefinition-`` / ``AlertDefinition-`` prefix as it does a bare
recommendation key: the wire check does not require the prefix.

Pure: stdlib only, no I/O.
"""
from __future__ import annotations

import re
from typing import Optional

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
UUID_LOWER_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

SYMPTOM_PREFIX = "SymptomDefinition-"
ALERT_PREFIX = "AlertDefinition-"
#: Every recommendation key the product parses as a full id starts with this.
RECOMMENDATION_PREFIX = "Recommendation-"
#: Definition-file (pak, describe.xml, content-import) recommendations:
#: ``Recommendation-df-<adapter kind>-<key>`` in every product export.
RECOMMENDATION_PAK_PREFIX = "Recommendation-df-"
#: User-defined recommendations (created in the UI): ``Recommendation-ud-<uuid>``.
RECOMMENDATION_USER_PREFIX = "Recommendation-ud-"

#: An XML ``xs:ID`` as the recommendation YAML has always accepted it.
_REC_KEY_CHARS = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*$")
#: Characters outside an ``xs:ID``'s, replaced in a minted key's kind segment.
_NOT_ID_CHAR = re.compile(r"[^A-Za-z0-9_.\-]")

#: The product's rule, quoted in every recommendation-key message.
RECOMMENDATION_RULE = (
    "VCF Operations refuses a recommendation key that starts with 'Recommendation-' unless it "
    "starts with 'Recommendation-df-' or 'Recommendation-ud-' (\"Invalid format of Recommendation "
    "Id\", AlertDefinitionServiceImpl.importAlertDefinitions, measured on 9.0.2), and refuses the "
    "whole alert file with it; a key without the 'Recommendation-' prefix imports as is"
)

#: Types whose ids are UUIDs (view, dashboard, report template, super metric).
UUID_TYPES = ("view", "dashboard", "report", "supermetric")


def recommendation_key_problem(key, xml_id: bool = True) -> Optional[str]:
    """Why ``key`` cannot be a recommendation key, or ``None``.

    Accepted: ``Recommendation-df-<rest>`` and ``Recommendation-ud-<rest>``
    (``<rest>`` not empty), and a key that does not start with
    ``Recommendation-`` in any letter case. A key starting with
    ``recommendation-`` in another case is refused too: whether the product
    compares the prefix case-sensitively on content import is not recorded,
    so a lower-case ``recommendation-df-...`` might be refused or might be
    read as a bare key (vendor ``describe.xml`` files carry
    ``recommendation-<n>`` keys, but that is the definition-file path, not
    the content importer that refused ``Recommendation-<uuid>``).
    With ``xml_id`` the key is also an XML ``xs:ID`` (letters, digits,
    ``_ . -``, starting with a letter or ``_``): the recommendation YAML has
    always required it, and the pak alert schema types the key ``xs:ID``.
    Without it (a definition outside ``content/alertdefs/``: the product's
    policy exports carry ``Recommendation-df-vCenter Operations Adapter-...``)
    only the prefix rule applies.
    """
    if not isinstance(key, str) or not key:
        return f"a recommendation key must be a non-empty string; got {key!r}"
    if xml_id and not _REC_KEY_CHARS.match(key):
        return (f"recommendation key {key!r} is not an XML id (letters, digits, _ . -, starting "
                f"with a letter or _)")
    if key[:len(RECOMMENDATION_PREFIX)].lower() == RECOMMENDATION_PREFIX.lower():
        for p in (RECOMMENDATION_PAK_PREFIX, RECOMMENDATION_USER_PREFIX):
            if key.startswith(p):
                if len(key) == len(p):
                    return f"recommendation key {key!r} has nothing after {p!r}"
                return None
        if not key.startswith(RECOMMENDATION_PREFIX):
            return (f"recommendation key {key!r} starts with {key[:len(RECOMMENDATION_PREFIX)]!r}: a factory "
                    f"caution, not the measured product rule (whether the importer compares the prefix "
                    f"case-sensitively is not recorded); use 'Recommendation-df-...' or a key without "
                    f"that prefix")
        return f"recommendation key {key!r}: {RECOMMENDATION_RULE}"
    return None


def mint_kind_segment(adapter_kind: str) -> str:
    """``adapter_kind`` with every character outside an ``xs:ID``'s
    (``[A-Za-z0-9_.-]``) replaced by ``_`` (``EP Ops Adapter`` becomes
    ``EP_Ops_Adapter``), so the minted key is an XML id. A kind that needs no
    change is kept as it is (``VMWARE``)."""
    return _NOT_ID_CHAR.sub("_", adapter_kind)


def mint_recommendation_key(adapter_kind: str, minted_uuid: str) -> str:
    """The key ``--ids mint`` gives a recommendation:
    ``Recommendation-df-<kind segment>-<uuid>`` (:func:`mint_kind_segment`),
    the shape of every definition-file recommendation in the product's
    exports and of the factory's derived key
    (``Recommendation-df-<kind>-<slug>``), which the alert renderer writes
    verbatim as the ``<Recommendation key>`` and every alert's ``ref``.
    Inferred from the error text and the export shape; not yet seen
    installing (``alert_fidelity_wire_format.md`` §Id grammar).

    Two kinds that map to one segment (``EP Ops Adapter``, ``EP_Ops_Adapter``)
    cannot make two recommendations collide: the uuid is the uuid5 of the
    recommendation's own type and source id, so two recommendations never
    share it, and one recommendation gets one kind."""
    return f"{RECOMMENDATION_PAK_PREFIX}{mint_kind_segment(adapter_kind)}-{minted_uuid}"


def yaml_id_problem(content_type: str, yaml_id) -> Optional[str]:
    """Why ``yaml_id`` cannot be the YAML ``id:`` of a ``content_type``
    object, or ``None``. The loaders' own rules: views, dashboards, report
    templates and super metrics carry a lower-case UUID; symptoms and alerts
    a UUID (rendered ``SymptomDefinition-<uuid>`` / ``AlertDefinition-<uuid>``);
    a recommendation its key (:func:`recommendation_key_problem`)."""
    if content_type == "recommendation":
        return recommendation_key_problem(yaml_id)
    s = yaml_id if isinstance(yaml_id, str) else ""
    if content_type in UUID_TYPES:
        if not UUID_LOWER_RE.match(s):
            return f"{content_type} id {yaml_id!r} is not a lower-case UUID, which the {content_type} loader requires"
        return None
    if content_type in ("symptom", "alert"):
        prefix = SYMPTOM_PREFIX if content_type == "symptom" else ALERT_PREFIX
        if not UUID_RE.match(s):
            return (f"{content_type} id {yaml_id!r} is not a UUID, which the {content_type} YAML requires "
                    f"(rendered {prefix}<uuid>)")
        return None
    return None


def wire_id_problem(content_type: str, wire_id, alertdefs: bool = True) -> Optional[str]:
    """Why ``wire_id`` cannot be the id a ``content_type`` definition carries
    in content-import XML or JSON, or ``None``.

    - recommendation: :func:`recommendation_key_problem` (the measured prefix
      rule), with the ``xs:ID`` rule when ``alertdefs`` (a definition in a
      ``content/alertdefs/`` file, whose schema types the key ``xs:ID``);
    - symptom / alert: not empty, and not the bare ``SymptomDefinition-`` /
      ``AlertDefinition-`` prefix (a bare id imports: module docstring);
    - view, dashboard, report template, super metric: a UUID (every one of
      4,438 read in the reference corpora and the registered paks).
    """
    s = wire_id if isinstance(wire_id, str) else ""
    if content_type == "recommendation":
        return recommendation_key_problem(wire_id, xml_id=alertdefs)
    if content_type in ("symptom", "alert"):
        prefix = SYMPTOM_PREFIX if content_type == "symptom" else ALERT_PREFIX
        if not s.strip() or s == prefix:
            return f"{content_type} definition id {wire_id!r} is empty or has nothing after {prefix!r}"
        return None
    if content_type in UUID_TYPES:
        if not UUID_RE.match(s):
            return f"{content_type} id {wire_id!r} is not a UUID (every {content_type} id in content is one)"
        return None
    return None
