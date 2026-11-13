"""Read a tree of VCF Operations content files into source objects.

Inputs are files, directories (walked recursively) and archives: a
content-export zip, a ``.pak``, the ``adapters.zip`` / ``views.zip`` /
``reports.zip`` nested in them, and an export's per-owner dashboard zips.
Archives are opened with the stock-id guard's limits and "cannot check"
discipline (``vcfcf_core.stock_ids.guard``): a member nested more than
``_MAX_ZIP_DEPTH`` archives deep, a member over ``_MAX_MEMBER_BYTES``, an
encrypted member, one in a compression method the stdlib cannot read, or a
zip that does not open is recorded as :class:`Unreadable`, never skipped
quietly. Text is decoded by byte-order mark (UTF-8, UTF-16, UTF-32), else by
an XML declaration's ``encoding``, else as UTF-8; text that does not decode
is recorded as unreadable. An XML file carrying a DOCTYPE or an entity
declaration is refused before it is parsed (product exports carry neither,
and refusing it makes entity-expansion safety independent of the host's
libexpat); a JSON file with a repeated object key is unreadable (which copy
the product used cannot be known).

This module reads only what it is handed and writes nothing.

Every file is classified by its content, never by its folder name:

- XML carrying ``ViewDef``, ``ReportDef``, ``AlertDefinition``,
  ``SymptomDefinition`` or a defining ``Recommendation`` element.
- JSON carrying ``dashboards`` (an ``{entries, dashboards[]}`` envelope) or
  a bare dashboard (``widgets`` beside ``id`` and ``name``).
- JSON super metrics: an object keyed by UUID whose values carry
  ``formula`` (pak ``supermetrics/*.json`` and the export
  ``supermetrics.json``), or a list of them.

Content of a type the converter does not support is listed per object as
:class:`Unsupported` (custom groups: an export ``customGroups`` list or a
pak custom group with a ``membershipDefinition``; policies: each
``<Policy>`` of a policy export), so a caller can refuse to report success
over it. Anything else (an XSD, a ``configuration.json``, a marker file, the
``files/solutionconfig`` check lists of a pak, a ``.properties`` bundle) is
*passed over* and listed with the reason, so the caller can show what was
not treated as content.
"""
from __future__ import annotations

import codecs
import io
import json
import re
import zipfile
import zlib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..stock_ids.guard import (
    Unreadable,
    _BOMS,
    _MAX_MEMBER_BYTES,
    _MAX_ZIP_DEPTH,
    _is_zip,
    _utf16_without_bom,
)

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

#: Content types the converter knows, in emission order (dependencies first).
CONTENT_TYPES: Tuple[str, ...] = (
    "supermetric", "view", "dashboard", "report", "symptom", "recommendation", "alert",
)


@dataclass
class SourceObject:
    """One content definition found in the input.

    ``payload`` is the element (XML types) or dict (dashboards, super
    metrics). ``context`` carries what the mapping needs from around the
    object: a dashboard's ``entries`` table and its folder, the defining
    file of an alert's inline symptoms. ``locations`` lists every place the
    same definition was found (several pak files repeat a ViewDef).
    """

    type: str
    id: str
    name: str
    location: str
    payload: object
    context: Dict[str, object] = field(default_factory=dict)
    locations: List[str] = field(default_factory=list)
    #: the location relative to the input it was found under (what
    #: ``--prefer-source`` matches)
    rel: str = ""

    def __post_init__(self) -> None:
        if not self.locations:
            self.locations = [self.location]
        if not self.rel:
            self.rel = self.location


@dataclass
class PassedOver:
    location: str
    reason: str


@dataclass
class Unsupported:
    """One object of a content type the converter does not convert."""
    type: str
    id: str
    name: str
    location: str


@dataclass
class InputScan:
    objects: List[SourceObject] = field(default_factory=list)
    unsupported: List[Unsupported] = field(default_factory=list)
    passed_over: List[PassedOver] = field(default_factory=list)
    unreadable: List[Unreadable] = field(default_factory=list)
    files_read: int = 0
    #: (location, raw bytes) of every content file, for the completeness
    #: cross-check against the stock-id guard's own scanner.
    content_files: List[Tuple[str, bytes]] = field(default_factory=list)


_XML_DECL_ENCODING = re.compile(rb"^\s*<\?xml[^>]*?\bencoding\s*=\s*[\"']([A-Za-z0-9._\-]+)[\"']")


def _decode(data: bytes) -> Tuple[Optional[str], Optional[str]]:
    """``(text, problem)``: the text by byte-order mark, else by the XML
    declaration's encoding, else UTF-8; or a reason."""
    encoding = None
    for bom, enc in _BOMS:
        if data.startswith(bom):
            encoding, data = enc, data[len(bom):]
            break
    if encoding is None:
        guess = _utf16_without_bom(data)
        if guess is not None:
            encoding = guess
    if encoding is None:
        m = _XML_DECL_ENCODING.match(data[:256])
        if m:
            declared = m.group(1).decode("ascii")
            try:
                codecs.lookup(declared)
            except LookupError:
                return None, f"declares an encoding the reader does not know ({declared!r})"
            if codecs.lookup(declared).name not in ("utf-16", "utf-32"):
                encoding = declared
    try:
        return data.decode(encoding or "utf-8"), None
    except (UnicodeDecodeError, LookupError) as exc:
        return None, f"does not decode as {encoding or 'utf-8'} ({exc})"


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


_XML_MARKERS = ("ViewDef", "ReportDef", "AlertDefinition", "SymptomDefinition", "Recommendation", "Policy")
_DTD = re.compile(r"<!\s*(DOCTYPE|ENTITY)", re.IGNORECASE)


def _scan_xml(text: str, location: str, scan: InputScan, raw: bytes) -> None:
    if _DTD.search(text):
        scan.unreadable.append(Unreadable(
            location, "XML with a DOCTYPE or entity declaration, refused before parsing (product exports carry "
                      "neither; entity expansion is not trusted)"))
        return
    if not any(m in text for m in _XML_MARKERS):
        scan.passed_over.append(PassedOver(location, "XML with no content definition element"))
        return
    # The text is already decoded; drop the declaration so a declared
    # UTF-16 encoding does not make the parser re-decode a str.
    body = re.sub(r"^\s*<\?xml[^>]*\?>", "", text, count=1)
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        scan.unreadable.append(Unreadable(location, f"XML that does not parse ({exc})"))
        return
    except (ValueError, LookupError) as exc:
        scan.unreadable.append(Unreadable(location, f"XML the reader cannot decode ({exc})"))
        return
    found = 0
    unsupported = 0
    # Iterative walk: a deeply nested file must not become a RecursionError.
    stack = [(root, None)]
    while stack:
        elem, parent_tag = stack.pop()
        tag = _local(elem.tag)
        if tag == "Policy":
            # A policy is content the converter does not convert (it also
            # embeds definitions, which are the policy's, not content).
            scan.unsupported.append(Unsupported("policy", elem.get("key") or elem.get("id") or "",
                                                elem.get("name") or "", location))
            unsupported += 1
            continue
        if tag == "ViewDef" and elem.get("id"):
            scan.objects.append(SourceObject(
                "view", elem.get("id"), (elem.findtext("Title") or "").strip(), location, elem))
            found += 1
            continue
        if tag == "ReportDef" and elem.get("id"):
            scan.objects.append(SourceObject(
                "report", elem.get("id"), (elem.findtext("Title") or "").strip(), location, elem))
            found += 1
            continue
        if tag == "AlertDefinition" and elem.get("id"):
            scan.objects.append(SourceObject(
                "alert", elem.get("id"), elem.get("name") or "", location, elem))
            found += 1
            continue
        if tag == "SymptomDefinition" and elem.get("id"):
            scan.objects.append(SourceObject(
                "symptom", elem.get("id"), elem.get("name") or "", location, elem))
            found += 1
            continue
        if tag == "Recommendation" and elem.get("ref") is None and (elem.get("key") or elem.get("id")):
            key = elem.get("key") or elem.get("id")
            scan.objects.append(SourceObject("recommendation", key, key, location, elem))
            found += 1
            continue
        stack.extend((c, tag) for c in reversed(list(elem)))
    if found:
        scan.content_files.append((location, raw))
    elif not unsupported:
        scan.passed_over.append(PassedOver(location, "XML with no content definition element"))


def _is_bare_dashboard(obj) -> bool:
    return isinstance(obj, dict) and "widgets" in obj and "id" in obj and "name" in obj


class _DuplicateKey(ValueError):
    pass


def _no_duplicates(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise _DuplicateKey(k)
        out[k] = v
    return out


def _scan_json(text: str, location: str, scan: InputScan, raw: bytes, folder: str) -> None:
    try:
        obj = json.loads(text, object_pairs_hook=_no_duplicates)
    except _DuplicateKey as exc:
        scan.unreadable.append(Unreadable(location, f"JSON with the object key {str(exc)!r} twice in one object "
                                                    f"(which value the product used cannot be known)"))
        return
    except (ValueError, RecursionError) as exc:
        if '"dashboards"' in text or '"formula"' in text or '"widgets"' in text:
            scan.unreadable.append(Unreadable(location, f"JSON with content keys that does not parse ({exc})"))
        else:
            scan.passed_over.append(PassedOver(location, "JSON that does not parse and carries no content keys"))
        return
    found = 0
    if isinstance(obj, dict) and isinstance(obj.get("dashboards"), list):
        entries = obj.get("entries") or {}
        for d in obj["dashboards"]:
            if isinstance(d, dict) and d.get("id"):
                scan.objects.append(SourceObject(
                    "dashboard", str(d["id"]), str(d.get("name") or ""), location, d,
                    context={"entries": entries, "folder": folder, "envelope": True,
                             "file_dashboard_count": len(obj["dashboards"])}))
                found += 1
    elif isinstance(obj, dict) and isinstance(obj.get("customGroups"), list) or (
            isinstance(obj, dict) and "membershipDefinition" in obj):
        groups = obj["customGroups"] if isinstance(obj.get("customGroups"), list) else [obj]
        for g in groups:
            if isinstance(g, dict):
                scan.unsupported.append(Unsupported("custom group", str(g.get("id") or g.get("resourceKey") or ""),
                                                    str(g.get("name") or ""), location))
        if groups:
            return
    elif _is_bare_dashboard(obj):
        scan.objects.append(SourceObject(
            "dashboard", str(obj["id"]), str(obj.get("name") or ""), location, obj,
            context={"entries": obj.get("entries") or {}, "folder": folder, "envelope": False,
                     "file_dashboard_count": 1}))
        found += 1
    else:
        candidates = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict) and "formula" in v:
                    candidates.append((str(v.get("id") or k), v))
            for key in ("superMetrics", "supermetrics"):
                if isinstance(obj.get(key), list):
                    candidates += [(str(v.get("id") or ""), v) for v in obj[key]
                                   if isinstance(v, dict) and "formula" in v]
        elif isinstance(obj, list):
            candidates = [(str(v.get("id") or ""), v) for v in obj if isinstance(v, dict) and "formula" in v]
        for sid, v in candidates:
            if not sid:
                scan.unreadable.append(Unreadable(location, "super metric with no id"))
                continue
            scan.objects.append(SourceObject("supermetric", sid, str(v.get("name") or ""), location, v))
            found += 1
    if found:
        scan.content_files.append((location, raw))
    else:
        scan.passed_over.append(PassedOver(location, "JSON with no dashboard or super metric definition"))


def _folder_of(location: str) -> str:
    """The folder a pak dashboard sits in (``dashboards/<Folder>/dashboard.json``)."""
    parts = re.split(r"[/\\!]", location)
    if len(parts) >= 2 and parts[-1] == "dashboard.json":
        return parts[-2]
    return ""


def _scan_bytes(data: bytes, location: str, scan: InputScan, depth: int) -> None:
    if _is_zip(data):
        if depth >= _MAX_ZIP_DEPTH:
            scan.unreadable.append(Unreadable(location, f"archive nested more than {_MAX_ZIP_DEPTH} levels deep, not opened"))
            return
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError) as exc:
            scan.unreadable.append(Unreadable(location, f"looks like a zip archive but does not open ({exc})"))
            return
        with zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                loc = f"{location}!{info.filename}"
                if info.flag_bits & 0x1:
                    scan.unreadable.append(Unreadable(loc, "encrypted archive member"))
                    continue
                if info.file_size > _MAX_MEMBER_BYTES:
                    scan.unreadable.append(Unreadable(
                        loc, f"archive member of {info.file_size} bytes, over the "
                             f"{_MAX_MEMBER_BYTES // (1024 * 1024)} MB limit (zip-bomb guard)"))
                    continue
                try:
                    member = zf.read(info)
                except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError,
                        EOFError, ValueError, zlib.error) as exc:
                    scan.unreadable.append(Unreadable(loc, f"archive member does not read ({type(exc).__name__}: {exc})"))
                    continue
                _scan_bytes(member, loc, scan, depth + 1)
        return
    scan.files_read += 1
    stripped = data.lstrip(b"\xef\xbb\xbf\xff\xfe\x00 \t\r\n")
    lead = stripped[:1]
    if not data.strip():
        scan.passed_over.append(PassedOver(location, "empty file"))
        return
    looks_text = lead in (b"<", b"{", b"[") or data[:2] in (b"\xff\xfe", b"\xfe\xff")
    if not looks_text:
        scan.passed_over.append(PassedOver(location, "not XML, JSON or an archive"))
        return
    text, problem = _decode(data)
    if text is None:
        scan.unreadable.append(Unreadable(location, f"text that {problem}"))
        return
    body = text.lstrip("﻿ \t\r\n")
    if body.startswith("<"):
        _scan_xml(body, location, scan, data)
    elif body[:1] in ("{", "["):
        _scan_json(body, location, scan, data, _folder_of(location))
    else:
        scan.passed_over.append(PassedOver(location, "not XML, JSON or an archive"))


def scan_inputs(paths: Sequence) -> InputScan:
    """Every content definition under ``paths`` (files, directories, archives).

    Directories are walked recursively in sorted order. Each object's
    ``rel`` is its location relative to the input it was found under (a
    directory input: the path below it; a file or archive input: its file
    name, then ``!member`` for archive members). Raises
    ``FileNotFoundError`` for a path that does not exist.
    """
    scan = InputScan()
    for raw in paths:
        p = Path(raw)
        if not p.exists():
            raise FileNotFoundError(f"input not found: {p}")
        files = sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p]
        for f in files:
            try:
                data = f.read_bytes()
            except OSError as exc:
                scan.unreadable.append(Unreadable(str(f), f"file does not read ({exc})"))
                continue
            n = len(scan.objects)
            _scan_bytes(data, str(f), scan, 0)
            prefix = str(f)
            relbase = f.relative_to(p).as_posix() if p.is_dir() else f.name
            for o in scan.objects[n:]:
                o.rel = relbase + o.location[len(prefix):] if o.location.startswith(prefix) else o.location
    return scan
