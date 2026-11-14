"""Checks on a pak's ``content/`` tree, read the way the pak installer reads it.

The pak installer (``SolutionManagerDistributedTask.installContent``) walks
``content/`` in a fixed order (localization, reports, dashboards, alertdefs,
symptomdefs, ..., ``knowledge/context/api-surface/summary_dashboard_pak_binding.md``)
and reports success whatever each step did. The first two defect classes
passed every factory check and were found only in the appliance logs
(vCommunity Java pak 0.0.0.15 on 9.0.2 and 9.1.1, 2026-11-14,
``knowledge/context/investigations/2026-11-14-pak-content-silent-drops.md``):

1. **An empty localization value.** The importer turns each
   ``view.<id>.<key>=<value>`` line of ``content/reports/<dir>/resources/content.properties``
   into a ``<Localization><Locale><Property key value>`` element of that
   ViewDef and validates it against the content schema, whose ``value``
   carries ``minLength 1`` (``cvc-minLength-valid ... for type
   '#AnonType_valuePropertyLocaleLocalizationViewDefViewsContent'``) and whose
   ``key`` carries ``maxLength 64``. One bad line fails the whole directory.
2. **A content id defined twice.** 0.0.0.15 wrote every symptom once in
   ``content/symptomdefs/`` and again inside its alert's ``content/alertdefs/``
   file. That duplicate is harmless on 9.0.2 (probe paks: the second copy
   updates the first,
   ``knowledge/context/investigations/2026-11-14-symptom-duplicate-key-on-902.md``);
   the 9.0.2 losses came from ids purged on that instance. One definition per
   id is factory policy all the same: it is the vendor shape, and which of two
   differing copies the importer keeps is not specified.
3. **An id the importer refuses** (a third class, found the same way in a
   pak built from an ``import-local --ids mint`` tree, 9.0.2, 2026-11-14): a
   recommendation key ``Recommendation-<uuid>`` failed the whole alert file
   (``Invalid format of Recommendation Id ... It should start with
   Recommendation-df- or Recommendation-ud-``). Each definition's id is
   checked against its type's grammar (:mod:`vcfcf_core.content_ids`).

:func:`check_pak_content` returns one error line per problem so a build can
refuse the pak. :func:`read_pak_content_inventory` gives the ids the pak
defines by type, for the post-install count.

Pure: reads the zip it is handed, writes nothing, calls no instance.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

from vcfcf_core import content_ids as _ids
from vcfcf_core import java_properties as _jprops
from vcfcf_core.stock_ids import guard as _guard

CONTENT_DIR = "content/"
REPORTS_DIR = "content/reports/"
DASHBOARDS_DIR = "content/dashboards/"
ALERTDEFS_DIR = "content/alertdefs/"
SYMPTOMDEFS_DIR = "content/symptomdefs/"

#: ``#AnonType_keyPropertyLocaleLocalizationViewDefViewsContent`` maxLength
#: (``cvc-maxLength-valid``, devel 9.0.2, 2026-07-10;
#: ``knowledge/context/investigations/sdk_pak_content_import_gap.md``).
LOCALIZATION_KEY_MAX_LEN = 64

#: The ``view.<id>.<suffix>`` form of a per-view localization key.
_VIEW_KEY = re.compile(r"^view\.([^.]+)\.(.+)$")

#: ``symptomDefType`` values that make a SymptomDefinition an alert's own
#: inline condition: REST shows it only inside the alert, as
#: ``alertConditions[].id = "Condition-<x>"``, and 404s it on
#: ``/api/symptomdefinitions`` (``2026-11-11-alert-symptom-export-completeness.md``).
CONDITION_SYMPTOM_TYPES = frozenset({"condition_self", "condition_population"})

PakSource = Union[str, Path, zipfile.ZipFile]


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def content_members(source: PakSource) -> Dict[str, bytes]:
    """Every file under the pak's top-level ``content/`` (name to bytes).

    Nested archives (``adapters.zip``) are not opened: their content is not
    part of what ``installContent`` walks.
    """
    def _read(zf: zipfile.ZipFile) -> Dict[str, bytes]:
        return {
            info.filename: zf.read(info)
            for info in zf.infolist()
            if not info.is_dir() and info.filename.startswith(CONTENT_DIR)
        }

    if isinstance(source, zipfile.ZipFile):
        return _read(source)
    with zipfile.ZipFile(Path(source), "r") as zf:
        return _read(zf)


# ---------------------------------------------------------------------------
# Duplicate ids
# ---------------------------------------------------------------------------

def content_definitions(members: Dict[str, bytes]) -> Tuple[List["_guard.Definition"], List[str]]:
    """``(definitions, unreadable)``: every content definition in ``members``
    (the stock-id guard's scanner, one member at a time) and a line per
    member it could not read."""
    defs: List[_guard.Definition] = []
    unreadable: List[_guard.Unreadable] = []
    for name in sorted(members):
        defs.extend(_guard.scan_bytes(members[name], name, unreadable=unreadable))
    return defs, [f"{u.location}: {u.reason}" for u in unreadable]


def _significant(text: Optional[str]) -> str:
    """Text or tail as a definition sees it: whitespace-only is nothing,
    anything else is kept exactly (its own whitespace included)."""
    return "" if text is None or not text.strip() else text


def canonical_definition(elem) -> tuple:
    """What "an identical copy" means for the duplicate gate.

    Two copies are the same definition when they have the same tag, the
    same attributes with the same values (order is not part of it), the same
    text, and the same children in the same order, recursively. Not part of
    it: the element's own tail (the whitespace after it, which depends on
    where it sits among its siblings: the renderer indents the last child
    differently), and whitespace-only text or tails between child elements
    (pretty-printing). Text with any non-whitespace character is compared
    exactly, leading and trailing whitespace included, because whether the
    importer trims it is not recorded.
    """
    return (
        _local(elem.tag),
        tuple(sorted(elem.attrib.items())),
        _significant(elem.text),
        tuple((canonical_definition(c), _significant(c.tail)) for c in elem),
    )


def _element_texts(members: Dict[str, bytes], prefix: str, tag: str,
                   id_attr: str) -> Dict[Tuple[str, str], tuple]:
    """``(member, normalized id)`` to the canonical form
    (:func:`canonical_definition`) of each defining ``tag`` element
    (identified by ``id_attr``) in the XML members under ``prefix``."""
    out: Dict[Tuple[str, str], tuple] = {}
    for name, data in members.items():
        if not (name.startswith(prefix) and name.endswith(".xml")):
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue
        for elem in root.iter():
            if (_local(elem.tag) == tag and elem.get(id_attr)
                    and elem.get("ref") is None):
                out[(name, _guard.normalize_id(elem.get(id_attr)))] = canonical_definition(elem)
    return out


#: Types whose identical copies (:func:`canonical_definition`) are allowed,
#: all under one directory: content type to (directory, XML tag, id
#: attribute). Why: the docstring of :func:`duplicate_definition_errors`.
IDENTICAL_COPIES_ALLOWED = {
    "view": (REPORTS_DIR, "ViewDef", "id"),
    "recommendation": (ALERTDEFS_DIR, "Recommendation", "key"),
}


def duplicate_definition_errors(members: Dict[str, bytes],
                                defs: Optional[List["_guard.Definition"]] = None) -> List[str]:
    """An error per content id the pak defines more than once.

    Factory policy: one definition per content id per pak. It is the vendor
    shape, and which copy the importer keeps when two copies differ is not
    specified. A duplicate is not by itself an import failure: on 9.0.2 a
    symptom defined twice updates in place (probe T2,
    ``knowledge/context/investigations/2026-11-14-symptom-duplicate-key-on-902.md``).
    Two exceptions, identical copies only (same definition by
    :func:`canonical_definition`, whitespace layout aside):

    - a ViewDef in its own ``content/reports/<dir>/`` and again in a
      report's directory that embeds the views its sections name (the vendor
      TVS shape). On 9.0.2 and 9.1.1 every such view of vCommunity Java
      0.0.0.15 was present after install; the source vCommunity 0.8.1 pak
      ships 59 such copies;
    - a recommendation carried in the ``content/alertdefs/`` file of each
      alert that names it, so alerts that share only a recommendation keep
      separate files and separate symptom batches. Inferred safe, not
      measured for recommendations: a duplicated symptom updates in place on
      9.0.2 (probe T2), and it is how every factory pak carried a shared
      recommendation before this gate existed (Synology 0.0.0.35 on 8.18.7
      and 9.1.1).

    Differing copies are an error.
    """
    if defs is None:
        defs, _ = content_definitions(members)
    by_key: Dict[Tuple[str, str], List[_guard.Definition]] = {}
    for d in defs:
        by_key.setdefault((d.type, _guard.normalize_id(d.id)), []).append(d)
    texts: Dict[str, Dict[Tuple[str, str], tuple]] = {}
    errors: List[str] = []
    for (ctype, nid), found in sorted(by_key.items()):
        if len(found) < 2:
            continue
        where = [d.location for d in found]
        name = next((d.name for d in found if d.name), "")
        label = _guard.type_label(ctype)
        allowed = IDENTICAL_COPIES_ALLOWED.get(ctype)
        if allowed and all(w.startswith(allowed[0]) for w in where):
            if ctype not in texts:
                texts[ctype] = _element_texts(members, *allowed)
            copies = {texts[ctype].get((w, nid)) for w in where}
            if len(copies) == 1 and None not in copies:
                continue
            errors.append(
                f"{label} {found[0].id} ('{name}') is defined {len(found)} times and "
                f"the copies differ: {', '.join(where)}. Which copy the importer keeps "
                f"is not specified; every copy must be identical."
            )
            continue
        errors.append(
            f"{label} {found[0].id} ('{name}') is defined {len(found)} times in the "
            f"pak: {', '.join(where)}. Factory policy is one definition per content "
            f"id per pak (the vendor shape; which copy the importer keeps is not "
            f"specified)."
        )
    return errors


# ---------------------------------------------------------------------------
# Id grammar
# ---------------------------------------------------------------------------

def id_grammar_errors(defs: List["_guard.Definition"]) -> List[str]:
    """An error per definition whose id its type's grammar refuses
    (:func:`vcfcf_core.content_ids.wire_id_problem`): a recommendation key
    the importer refuses (and the whole alert file with it), an empty
    symptom or alert id, a view, dashboard, report or super metric id that
    is not a UUID. One line per id and file."""
    errors: List[str] = []
    seen: set = set()
    for d in defs:
        problem = _ids.wire_id_problem(d.type, d.id)
        key = (d.type, d.id, d.location)
        if problem is None or key in seen:
            continue
        seen.add(key)
        name = f" ('{d.name}')" if d.name else ""
        errors.append(f"{d.location}: {_guard.type_label(d.type)} {d.id}{name}: {problem}")
    return errors


# ---------------------------------------------------------------------------
# Localization bundles
# ---------------------------------------------------------------------------

def _unit_of(name: str, top: str) -> Optional[str]:
    """``content/reports/<dir>/`` for a member under it, else None."""
    rest = name[len(top):]
    if "/" not in rest:
        return None
    return top + rest.split("/", 1)[0] + "/"


def _view_units(members: Dict[str, bytes]):
    """Per ``content/reports/<dir>/``: its XML members and its properties members."""
    units: Dict[str, Dict[str, List[str]]] = {}
    for name in sorted(members):
        if not name.startswith(REPORTS_DIR):
            continue
        unit = _unit_of(name, REPORTS_DIR)
        if unit is None:
            continue
        rel = name[len(unit):]
        slot = units.setdefault(unit, {"xml": [], "props": []})
        if "/" not in rel and rel.endswith(".xml"):
            slot["xml"].append(name)
        elif rel.startswith("resources/") and rel.endswith(".properties"):
            slot["props"].append(name)
    return units


def _decode(data: bytes, name: str, errors: List[str]) -> Optional[str]:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"{name}: not UTF-8 ({exc}); not checked")
        return None


def _entries(data: bytes, name: str, errors: List[str]):
    text = _decode(data, name, errors)
    if text is None:
        return None
    try:
        return _jprops.load_entries(text)
    except ValueError as exc:
        errors.append(f"{name}: does not read as a Java properties file ({exc})")
        return None


def localization_errors(members: Dict[str, bytes]) -> List[str]:
    """An error per localization entry the importer would reject or misread.

    Per ``content/reports/<dir>/`` (views and reports): every
    ``resources/*.properties`` entry must read as ``view.<id>.<key>=<value>``
    for a ViewDef in the same directory, with a non-empty value and a key of
    at most 64 characters; every ``localizationKey`` a ViewDef's XML carries
    must have its ``view.<id>.<key>`` entry there. Per
    ``content/dashboards/<dir>/``: no entry of ``resources/*.properties`` may
    have an empty value.
    """
    errors: List[str] = []
    for unit, slot in _view_units(members).items():
        views: Dict[str, str] = {}
        xml_keys: List[Tuple[str, str, str]] = []  # (view id, key, member)
        for xml_name in slot["xml"]:
            try:
                root = ET.fromstring(members[xml_name])
            except ET.ParseError as exc:
                errors.append(f"{xml_name}: XML does not parse ({exc})")
                continue
            for elem in root.iter():
                if _local(elem.tag) != "ViewDef" or not elem.get("id"):
                    continue
                vid = elem.get("id")
                title = next((c.text or "" for c in elem if _local(c.tag) == "Title"), "")
                views[vid] = title.strip()
                for sub in elem.iter():
                    k = sub.get("localizationKey")
                    if k:
                        xml_keys.append((vid, k, xml_name))
        present: set = set()
        for props_name in slot["props"]:
            entries = _entries(members[props_name], props_name, errors)
            if entries is None:
                continue
            for line, key, value in entries:
                m = _VIEW_KEY.match(key)
                if not m:
                    errors.append(
                        f"{props_name} line {line}: entry {key!r} is not of the form "
                        f"view.<id>.<key> (an unescaped line break in the value before it?)"
                    )
                    continue
                vid, suffix = m.group(1), m.group(2)
                present.add((vid, suffix))
                label = f"view '{views[vid]}' ({vid})" if vid in views else f"view {vid}"
                if vid not in views:
                    errors.append(
                        f"{props_name} line {line}: {key!r} names view {vid}, which no "
                        f"ViewDef in {unit} defines"
                    )
                if value == "":
                    errors.append(
                        f"{props_name} line {line}: {label} localization entry "
                        f"{suffix!r} has an empty value; the importer rejects the whole "
                        f"directory (cvc-minLength-valid, minLength 1). Omit the entry "
                        f"when the text is empty."
                    )
                if len(suffix) > LOCALIZATION_KEY_MAX_LEN:
                    errors.append(
                        f"{props_name} line {line}: {label} localization key {suffix!r} "
                        f"is {len(suffix)} characters, over the {LOCALIZATION_KEY_MAX_LEN} "
                        f"the importer accepts (cvc-maxLength-valid)"
                    )
        for vid, k, xml_name in xml_keys:
            if (vid, k) not in present:
                errors.append(
                    f"{xml_name}: view '{views.get(vid, '')}' ({vid}) carries "
                    f"localizationKey={k!r} but no view.{vid}.{k} entry ships in "
                    f"{unit}resources/ (8.18 rejects the view)"
                )
    for name in sorted(members):
        if not name.startswith(DASHBOARDS_DIR) or not name.endswith(".properties"):
            continue
        unit = _unit_of(name, DASHBOARDS_DIR)
        if unit is None or not name[len(unit):].startswith("resources/"):
            continue
        entries = _entries(members[name], name, errors)
        for line, key, value in entries or []:
            if value == "":
                errors.append(
                    f"{name} line {line}: dashboard localization entry {key!r} has an "
                    f"empty value. Omit the entry when the text is empty."
                )
    return errors


def check_pak_content(source: PakSource) -> List[str]:
    """Every problem in the pak's ``content/`` tree; empty means none.

    A member the scanner cannot read is a problem too: what was not read
    was not checked.
    """
    members = content_members(source)
    defs, unreadable = content_definitions(members)
    return (
        [f"unreadable: {u}" for u in unreadable]
        + localization_errors(members)
        + duplicate_definition_errors(members, defs)
        + id_grammar_errors(defs)
    )


# ---------------------------------------------------------------------------
# Inventory (post-install count)
# ---------------------------------------------------------------------------

@dataclass
class PakAlert:
    """One alert definition the pak ships and the symptom ids its sets name."""

    id: str
    name: str
    member: str
    symptom_refs: List[str] = field(default_factory=list)


@dataclass
class PakContentInventory:
    """The ids a pak's ``content/`` defines, by type (id to display name).

    ``symptoms`` holds standalone symptom definitions only; an alert's
    inline conditions (``symptomDefType`` set) are in ``conditions`` and are
    checked through their alert, the only place REST shows them.
    """

    views: Dict[str, str] = field(default_factory=dict)
    reports: Dict[str, str] = field(default_factory=dict)
    symptoms: Dict[str, str] = field(default_factory=dict)
    conditions: Dict[str, str] = field(default_factory=dict)
    alerts: Dict[str, PakAlert] = field(default_factory=dict)

    def counts(self) -> Dict[str, int]:
        return {
            "views": len(self.views), "reports": len(self.reports),
            "symptoms": len(self.symptoms), "conditions": len(self.conditions),
            "alerts": len(self.alerts),
        }


def _alert_refs(elem) -> List[str]:
    out: List[str] = []
    for sub in elem.iter():
        if _local(sub.tag) in ("SymptomSet", "Symptom"):
            ref = sub.get("ref") or ""
            if ref.startswith("SymptomDefinition-") and ref not in out:
                out.append(ref)
    return out


def read_pak_content_inventory(source: PakSource) -> PakContentInventory:
    """The views, reports, symptoms, conditions and alerts a pak defines."""
    members = content_members(source)
    defs, _ = content_definitions(members)
    inv = PakContentInventory()
    for d in defs:
        if d.type == "view":
            inv.views.setdefault(d.id, d.name)
        elif d.type == "report":
            inv.reports.setdefault(d.id, d.name)
        elif d.type == "symptom":
            if d.attrs.get("symptomDefType") in CONDITION_SYMPTOM_TYPES:
                inv.conditions.setdefault(d.id, d.name)
            else:
                inv.symptoms.setdefault(d.id, d.name)
    for name in sorted(members):
        if not (name.startswith(ALERTDEFS_DIR) and name.endswith(".xml")):
            continue
        try:
            root = ET.fromstring(members[name])
        except ET.ParseError:
            continue
        for elem in root.iter():
            if _local(elem.tag) == "AlertDefinition" and elem.get("id"):
                inv.alerts.setdefault(elem.get("id"), PakAlert(
                    id=elem.get("id"), name=elem.get("name", "") or "",
                    member=name, symptom_refs=_alert_refs(elem),
                ))
    return inv


def summarize_definitions(defs: Iterable["_guard.Definition"]) -> Dict[str, int]:
    """Count of distinct ids per content type."""
    seen: Dict[str, set] = {}
    for d in defs:
        seen.setdefault(d.type, set()).add(_guard.normalize_id(d.id))
    return {k: len(v) for k, v in sorted(seen.items())}
