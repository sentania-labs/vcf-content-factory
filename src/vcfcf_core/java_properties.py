"""Read a ``.properties`` text exactly as ``java.util.Properties.load`` does.

One reader for every factory place that must agree with the VCF Operations
pak installer, which loads ``content/dashboards/dashboards.properties`` with
``Properties.load(new FileReader(...))``
(``knowledge/context/api-surface/summary_dashboard_pak_binding.md``):
the offline importer (``vcfcf_core.importer.inputs``) and the post-install
Summary check (``vcfcf_managementpacks.post_install``).

Java semantics kept on purpose:

- Lines end at ``\\n``, ``\\r`` or ``\\r\\n`` only (not at the other
  characters ``str.splitlines`` treats as line ends).
- Whitespace is space, tab and form feed only.
- A leading byte-order mark is NOT stripped: ``FileReader`` keeps U+FEFF, so
  it becomes part of the first key, and that key matches no directory name.
- ``#`` and ``!`` lines are comments and never continue; a line ending in an
  odd number of backslashes continues on the next, whose leading whitespace
  is dropped.
- The key ends at the first unescaped ``=``, ``:`` or whitespace; then
  whitespace, at most one ``=`` or ``:``, and whitespace again are skipped.
- Escapes: ``\\t \\n \\r \\f``, ``\\uXXXX``, and any other escaped character
  is itself. A malformed ``\\uXXXX`` raises ``ValueError`` (Java throws
  ``IllegalArgumentException``).
- A key given twice keeps the last value (:func:`load`); :func:`load_entries`
  returns every entry in order, so a caller can report the superseded ones.

Pure functions; nothing is read or written here.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

_LINE_END = re.compile(r"\r\n|\r|\n")
_WS = " \t\f"
_ESC = {"t": "\t", "n": "\n", "r": "\r", "f": "\f"}


def unescape(s: str) -> str:
    """Resolve the ``Properties`` backslash escapes of one key or value."""
    out = []
    k = 0
    while k < len(s):
        c = s[k]
        if c != "\\" or k + 1 >= len(s):
            out.append(c)
            k += 1
            continue
        nxt = s[k + 1]
        if nxt == "u":
            hexs = s[k + 2:k + 6]
            if not re.fullmatch(r"[0-9a-fA-F]{4}", hexs):
                raise ValueError(f"malformed \\uxxxx escape {s[k:k + 6]!r}")
            out.append(chr(int(hexs, 16)))
            k += 6
            continue
        out.append(_ESC.get(nxt, nxt))
        k += 2
    return "".join(out)


def load_entries(text: str) -> List[Tuple[int, str, str]]:
    """``(line, key, value)`` of every entry in order (``line`` is the
    1-based line the entry starts on)."""
    lines = _LINE_END.split(text)
    out: List[Tuple[int, str, str]] = []
    i = 0
    while i < len(lines):
        start = i + 1
        line = lines[i].lstrip(_WS)
        i += 1
        if not line or line[0] in "#!":
            continue
        while (len(line) - len(line.rstrip("\\"))) % 2 == 1:
            line = line[:-1]
            if i >= len(lines):
                break
            line += lines[i].lstrip(_WS)
            i += 1
        k = 0
        while k < len(line) and line[k] not in "=:" + _WS:
            k += 2 if line[k] == "\\" else 1
        k = min(k, len(line))
        rest = line[k:].lstrip(_WS)
        if rest[:1] in ("=", ":"):
            rest = rest[1:].lstrip(_WS)
        out.append((start, unescape(line[:k]), unescape(rest)))
    return out


def load(text: str) -> Dict[str, str]:
    """The ``Properties`` map: the last value of every key."""
    return {k: v for _, k, v in load_entries(text)}


def split(text: str, sep: str) -> List[str]:
    """``String.split`` on a one-character literal: trailing empty strings
    dropped, leading ones kept, nothing trimmed."""
    parts = text.split(sep)
    while parts and parts[-1] == "":
        parts.pop()
    return parts
