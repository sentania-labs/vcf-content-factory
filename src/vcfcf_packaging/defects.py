"""Registry reader for ``knowledge/context/defects.md``.

Parses the defect registry into :class:`DefectEntry` dataclasses and exposes
the gate logic used by ``defect-gate``, ``release``, and ``publish``.

Registry selection is by FILE PRESENCE, not configuration
---------------------------------------------------------
When no explicit path is given, ``defects.local.md`` beside the default
registry wins over ``defects.md``.  A consumer who wants their own registry
creates that file; the factory never ships it, so a ``git pull`` can never
conflict with it, and a checkout without one behaves exactly as before.
An explicit ``registry_path`` argument always wins over both.
See ``knowledge/designs/defect-isolation-v1.md``.

Per-entry fault isolation
-------------------------
A malformed entry fails closed **only for itself**, never for the whole file:

  - A parse error whose ``Affects:`` token is readable becomes a synthetic
    OPEN BLOCKING defect against exactly that scope, so a broken entry cannot
    silently stop gating what it was meant to block.
  - A parse error whose ``Affects:`` cannot be read blocks nothing, but is
    surfaced loudly on every gate invocation.
  - Either way, every other artifact still gates normally.

An unreadable or absent FILE is a different thing from a malformed entry: an
absent registry, or one holding no ``DEF`` entry at all, warns and passes
(RULE-012 is named in the warning), an unreadable one raises
:class:`DefectRegistryError`.  The standalone entrypoint's
``--require-registry`` refuses (exit 1) on absent or empty instead, for a
caller that fetched the registry on purpose and must never read a failed
fetch as an all-clear (#226).  The copy a pak repo vendors as
``ci/defect_gate.py`` is generated from this file with that flag always on.

Public API
----------
parse_registry(registry_path) -> Registry
    Full parse result: valid entries, per-entry parse errors, and the
    ``gate_entries`` view (valid entries plus the synthetic blocking entries
    described above) that the gates run against.

load_registry(registry_path) -> List[DefectEntry]
    ``parse_registry(...).gate_entries``.  Never raises on a malformed
    ENTRY.  Entries are still validated for:
      - unknown ``Severity:`` (only ``blocking`` or ``tracked`` are valid)
      - ``waived`` status (explicitly rejected, no waivers exist)
      - unknown ``Status:`` (only ``open`` or ``closed`` are valid)
      - ``status: closed`` without a non-empty ``Closing-evidence:`` field
      - duplicate IDs
      - missing required fields (Title, Severity, Status, Affects, First-seen,
        Source, Summary)
      - an ``Affects:`` that is not one scope token (multi-token, or a
        prefix other than ``factory:``); such an entry used to parse as valid
        and silently gate nothing (#153)
      - a ``DEF``-prefixed heading whose id is not ``DEF-NNN`` (a typo such as
        ``DEF-1O2``, or a suffix glued to the id): it always terminates the previous entry,
        so it can never repoint a good entry, and it becomes a parse error of
        its own when it carried field lines.  A DEF-prefixed heading with no
        field lines under it is prose (``### DEFECTS``), has nothing that could
        have bled into the previous entry, and is silent.  The same holds for
        a heading that only looks like one (#226, ported from the template's
        vendored ``ci/defect_gate.py``): any depth (``##### DEF-002``), no
        space (``###DEF-002``), lower case (``### def-002``), behind a
        blockquote or non-breaking space, indented as code (a tab or 4+
        spaces) after the first entry, or inside a fenced code block (a
        digit-free placeholder such as ``### DEF-NNN`` in a fence before the
        first entry is documentation and is skipped)
      - a field line that is not a plain field at the entry's field indent:
        code-indented, blockquoted, behind a non-breaking space, nested at a
        different indent (``  - **Status:** closed`` under Summary), or a
        field repeated within one entry (#226).  Fenced lines are description
        text, never fields.  Up to three spaces of indent before a heading or
        a field are allowed, as in Markdown, and a byte-order mark is ignored
      - an ``Affects:`` holding a comma or a backtick, or a bare token with
        leading or trailing punctuation (``synology.``) (#226)

    A malformed entry fails closed for EVERY pak it names: every token of a
    malformed ``Affects:`` (``template, unifi`` and ``template unifi`` name
    both) and every ``Affects:`` line, repeated or nested ones included.  A
    token that is a known pak, ``<type>/<slug>`` or ``factory:<area>`` is a
    scope; any other pak-shaped token blocks a pak gated by exactly that name.
    Trailing text after a well-formed id (``### DEF-027 (note)``) is
    tolerated, as in the vendored gate, and a malformed heading whose id
    carries a digit is reported even when it collected no dash-bullet field.
    Every gate match is case-insensitive (``Synology`` gates ``synology``).

gate_pak(pak_name, registry_path) -> List[DefectEntry]
    Return all open blocking defects whose ``Affects:`` token is ``pak_name``.

gate_item(content_type, slug, registry_path) -> List[DefectEntry]
    Return all open blocking defects whose ``Affects:`` token is
    ``<content_type>/<slug>``.

gate_all(registry_path) -> List[DefectEntry]
    Return all open blocking defects in the registry.

format_defect_line(entry) -> str
    Format one defect for human output:
    ``DEF-NNN  <title>  (first seen <first_seen>, source <source>)``

vendored_gate_text(source_text) -> str
    The vendorable ``ci/defect_gate.py`` for pak-repo CI, generated from this
    module's text: a checksum header, then this file with
    ``--require-registry`` defaulted on.  See "Vendored copy for pak-repo CI".

verify_vendored_text(text, source_text=None) -> Optional[str]
    Why ``text`` is not a faithful vendored copy (hand-edited, or with
    ``source_text`` stale), or None.

REGISTRY_PATH
    Default registry path (``knowledge/context/defects.md`` relative to repo root).

LOCAL_REGISTRY_NAME
    ``defects.local.md``: the consumer-owned registry filename, preferred
    when present.

Registry file format
--------------------
Each entry is a ``### DEF-NNN`` section.  Field lines are:

    - **Field:** value

Required fields: Title, Severity, Status, Affects, First-seen, Source, Summary.
Optional fields: Closing-evidence (required when Status is ``closed``), Related.

``Affects:`` is exactly one token, a managed-pak name (e.g. ``synology``), a
``<type>/<slug>`` path (e.g. ``dashboard/demand_driven_capacity_v2``), or a
``factory:<area>`` string for framework-level defects.
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Default path to the defect registry, relative to the repo root.
REGISTRY_PATH = Path(__file__).parent.parent.parent / "knowledge" / "context" / "defects.md"

#: Consumer-owned registry filename.  Never shipped by the factory; when a
#: file of this name sits beside the default registry it wins (presence, not
#: configuration).  See knowledge/designs/defect-isolation-v1.md.
LOCAL_REGISTRY_NAME = "defects.local.md"

#: Longest untrusted registry fragment ever echoed back in a message.
_ECHO_MAX = 120

#: Valid severity values.
_VALID_SEVERITIES = frozenset({"blocking", "tracked"})

#: Valid status values.
_VALID_STATUSES = frozenset({"open", "closed"})


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass
class DefectEntry:
    """One entry in the defect registry."""

    id: str                      # e.g. "DEF-001"
    title: str                   # one line; quoted in refusal messages
    severity: str                # "blocking" or "tracked"
    status: str                  # "open" or "closed"
    affects: str                 # single token: pak name, <type>/<slug>, or factory:<area>
    first_seen: str              # build + date string as written in the registry
    source: str                  # path (+ finding label) of the review that found it
    summary: str                 # 2-4 line description
    closing_evidence: str = ""   # non-empty iff status == "closed"
    related: str = ""            # optional cross-links
    # True for an entry SYNTHESIZED from a parse error (fail-closed for the
    # scope the broken entry named).  Never set by a real registry line.
    synthetic: bool = False


@dataclass
class ParseError:
    """One entry that could not be parsed.

    ``affects`` is the entry's ``Affects:`` token when it could be read at
    all, else the empty string.  A readable token is what lets the parser
    fail closed for exactly that scope instead of for everything.
    """

    entry_id: str        # "DEF-NNN", or "" when even the id is unusable
    lineno: int
    reason: str
    affects: str = ""
    #: Every pak-shaped token of a malformed ``Affects:`` that could not be
    #: attributed on its own (not a KNOWN pak, not ``<type>/<slug>`` or
    #: ``factory:<area>``), the name after an unrecognised prefix included
    #: (``pak:synology`` -> ``synology``).  ``gate_pak`` fails closed when the
    #: pak being gated equals any of them, which needs no managed-paks lookup
    #: and so also works when this file runs as a standalone script (#153).
    #: Every token, not the first only: ``template, unifi`` names unifi too
    #: (#226 review B1).
    candidates: Tuple[str, ...] = ()
    #: Further scopes the broken entry names beyond ``affects``: the other
    #: items of a comma list (``template,unifi``), or a second ``Affects:``
    #: line (repeated, nested, fenced into a malformed entry).  The entry
    #: fails closed for every one of them (#226).
    extra_scopes: Tuple[str, ...] = ()

    @property
    def scoped(self) -> bool:
        """True when this error can be attributed to a single artifact."""
        return bool(self.affects)

    @property
    def candidate(self) -> str:
        """The first candidate, or ``""``; see ``candidates``."""
        return self.candidates[0] if self.candidates else ""

    def __str__(self) -> str:  # pragma: no cover - trivial
        who = self.entry_id or "<unnamed entry>"
        return f"{who} (near line {self.lineno}): {self.reason}"


@dataclass
class Registry:
    """Parse result for one registry file."""

    path: Path
    entries: List[DefectEntry] = field(default_factory=list)   # valid only
    errors: List[ParseError] = field(default_factory=list)
    #: False when the file does not exist (gates warn and pass).
    exists: bool = True

    @property
    def gate_entries(self) -> List[DefectEntry]:
        """Valid entries plus one synthetic blocker per scoped parse error.

        Document order is not preserved for the synthetic entries: they are
        appended after the valid ones, which keeps the common (clean) case
        byte-identical to the old behaviour.
        """
        synthetic: List[DefectEntry] = []
        for err in self.errors:
            if not err.scoped:
                continue
            synthetic.append(_synthetic_entry(err, self.path))
            synthetic.extend(
                _synthetic_entry(replace(err, affects=scope), self.path)
                for scope in err.extra_scopes
            )
        return list(self.entries) + synthetic

    @property
    def unscoped_errors(self) -> List[ParseError]:
        """Parse errors that block nothing because ``Affects:`` was unreadable."""
        return [e for e in self.errors if not e.scoped]

    @property
    def empty(self) -> bool:
        """True when the file exists but holds no ``DEF`` entry, good or bad.

        An empty, truncated or reformatted registry (or an error page saved
        in its place) parses to nothing.  The gates warn and pass on it, as
        on an absent file.  ``--require-registry`` refuses on the stronger
        :attr:`unreadable` (#226).
        """
        return self.exists and not self.entries and not self.errors

    @property
    def unreadable(self) -> bool:
        """True when the file exists but not one entry in it is VALID.

        Covers :attr:`empty` and also a registry that kept its ``### DEF-NNN``
        headings while its field syntax changed (``* **Field:**`` bullets, a
        table): every entry is then a parse error, which the default gate
        reports but which is no all-clear for CI that fetched the file on
        purpose (#226 review B2).
        """
        return self.exists and not self.entries


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DefectRegistryError(ValueError):
    """Raised when the defect registry FILE is unusable.

    Since per-entry fault isolation landed (see the module docstring), a
    malformed ENTRY no longer raises: it is isolated to its own scope.  This
    exception is reserved for a file that cannot be read at all, and remains
    exported because ``cli.py`` and ``publish.py`` still catch it.
    """


# ---------------------------------------------------------------------------
# Regex patterns  (mirror managed_paks.py style: per-field regexes)
# ---------------------------------------------------------------------------

# A well-formed entry heading, matched against the line with up to three
# spaces of indent already split off (Markdown allows that much before an ATX
# heading).  Space or tab only between the hashes and the id: a non-breaking
# space there is a disguised heading, caught by _LOOSE_DEF_HEADING_RE.
# Text after the id, past a word break, is tolerated (``### DEF-027 (synology
# build 32)``), as the vendored gate tolerates it (template issue #18 CI4): the
# id is unambiguous, and treating such a heading as malformed turned a closed
# or tracked entry into an open blocker (#226 review W2).  ``DEF-1O2`` still
# fails, since there is no word break between ``1`` and ``O``.
_SECTION_RE = re.compile(r"^#{1,4}[ \t]+(DEF-\d+)\b.*$")

#: Anything that LOOKS like a defect heading (#226, ported from the template's
#: vendored ci/defect_gate.py): any depth of '#', optional whitespace
#: (non-breaking space included), behind any indent or blockquote marker,
#: then ``DEF`` in capitals or ``def-`` in any case.  A line matching this but
#: not _SECTION_RE opens a MALFORMED entry, which terminates the previous one.
#: Before this, ``##### DEF-002``, ``###DEF-002``, ``### def-002``, a
#: blockquoted or code-indented heading all fell through to the
#: continuation branch and their field lines overwrote the previous entry's:
#: an open blocker followed by such an entry marked tracked simply vanished.
_LOOSE_DEF_HEADING_RE = re.compile(r"^[\s>]*#+\s*(?:DEF|(?i:def-))")

#: Leading run of spaces/tabs.  Four or more spaces, or any tab, make a line an
#: indented code block in Markdown, never a heading or a field.
_INDENT_RE = re.compile(r"^([ \t]*)(.*)$")

#: A fenced code block delimiter (indent already split off): three or more
#: backticks or tildes, optional info string on the opening fence.  Fenced
#: lines are description text, never fields (#226: a fenced ``Status:
#: closed`` used to close the open blocker it sat in).
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")

#: The id tail (after ``DEF-``) of a schema placeholder such as the ``NNN`` in
#: ``### DEF-NNN``: no digit.  Only a placeholder may sit in a fence before the
#: first entry; a numeric id there opens a malformed entry instead.
_FENCED_PLACEHOLDER_ID_RE = re.compile(r"^[^\d\s]+(?:\s|$)")

#: Anything that LOOKS like a field line: behind any indent, blockquote
#: marker or non-breaking space.  One that is not a plain field at the
#: entry's field indent marks the entry malformed; it is still read, so the
#: entry fails closed for every Affects scope it names.
_LOOSE_FIELD_RE = re.compile(r"^[\s>]*-\s+\*\*([^:]+):\*\*\s*(.*)")

# Notes on _LOOSE_DEF_HEADING_RE, the malformed-heading detector.
#
# A heading that MEANT to be an entry but whose id is not ``DEF-NNN`` (a typo
# such as ``DEF-1O2``, a suffix glued to the id, or any disguise listed above)
# used to match nothing, fall through to the continuation-line branch, and
# let the following entry's field lines silently overwrite the PREVIOUS
# entry's fields: a real defect stopped gating the artifact it named, with no
# error.  Matching it makes it a ParseError instead, so it goes through the
# same scoped/unscoped isolation as every other malformed entry.
#
# Capital ``DEF`` is matched bare, without the hyphen, on purpose: requiring
# it would let ``### DEF102`` fall back through to the continuation branch
# and reproduce the exact silent field-bleed this exists to remove, on a typo
# from the same keystroke class.  Lowercase needs the hyphen (``def-002``),
# so lowercase prose (``## Defects``, ``## Schema``) never matches at all.
# Matching is only half the contract; ``_flush_entry`` decides whether to
# REPORT, and does so only when the section collected field lines, which is
# what keeps an all-caps prose heading (``### DEFECTS``) silent.

#: A plain field line, matched against the line with its indent split off.
_FIELD_RE = re.compile(r"^-\s+\*\*([^:]+):\*\*\s*(.*)")

#: Characters that make one ``Affects:`` token a list or a quoted token
#: (``template,unifi``, ```template```), ported from the vendored gate's
#: one-token rule (#226).  Whitespace is handled separately (multi-token).
_LIST_CHARS_RE = re.compile(r"[,`]")

#: Splits a malformed ``Affects:`` value into the tokens it names.
_AFFECTS_SPLIT_RE = re.compile(r"[\s,`]+")

#: Punctuation that may wrap a token in prose or a list (``(synology)``,
#: ``synology.``, ``<pak>``); stripped before a token is classified.
_EDGE_PUNCT = "()[]{}<>.,;:!?'\"`"

#: The shape of a bare managed-pak name.
_PAK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")

# DEF-NNN id format.
_ID_RE = re.compile(r"^DEF-\d+$")

#: Required field names (exact, case-sensitive as they appear in the registry).
_REQUIRED_FIELDS = ("Title", "Severity", "Status", "Affects", "First-seen", "Source", "Summary")

#: ``Affects:`` scope shapes that are unambiguous on their own (no registry
#: lookup needed): a content item ``<type>/<slug>`` and ``factory:<area>``.
#: A bare managed-pak name is the third shape; see :func:`_known_pak_names`.
_ITEM_SCOPE_RE = re.compile(r"^[a-z][a-z_]*/[A-Za-z0-9_.\-]+$")
_FACTORY_SCOPE_RE = re.compile(r"^factory:[A-Za-z0-9][A-Za-z0-9_.\-]*$")


# ---------------------------------------------------------------------------
# Registry resolution (by presence, not configuration)
# ---------------------------------------------------------------------------

def _clip(text: str, limit: int = _ECHO_MAX) -> str:
    """Echo-safe truncation of untrusted registry content."""
    text = text or ""
    return text if len(text) <= limit else text[:limit] + "..."


def preferred_registry(base: "str | Path") -> Path:
    """Return ``defects.local.md`` beside ``base`` when it exists, else ``base``.

    The one code path used by both the module default and the standalone
    ``__main__`` entrypoint, so a consumer's local registry is honoured
    identically however the gate is invoked.
    """
    base_path = Path(base)
    local = base_path.with_name(LOCAL_REGISTRY_NAME)
    try:
        if local.exists():
            return local
    except OSError:
        pass
    return base_path


def resolve_registry_path(
    registry_path: "str | Path | None" = None,
) -> Path:
    """Resolve the registry to read.

    An explicit ``registry_path`` always wins, verbatim: a caller that names
    a file means that file.  Otherwise the default location is consulted by
    presence, local-first.  ``REGISTRY_PATH`` is read at call time so tests
    (and any future relocation) can monkeypatch it.
    """
    if registry_path is not None:
        return Path(registry_path)
    return preferred_registry(REGISTRY_PATH)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _synthetic_entry(err: ParseError, registry_path: Path) -> DefectEntry:
    """Fail-closed stand-in for a malformed entry with a readable scope.

    Severity/status are hardcoded open+blocking on purpose: the entry the
    author meant to file is unreadable, so the safe reading is that it
    blocks the scope it names until someone fixes the line.
    """
    return DefectEntry(
        # The line number is part of the fallback id: two entries with
        # unusable ids must not collapse into one when a caller dedupes on
        # id (publish.py builds a `sorted({e.id ...})` summary line).
        id=err.entry_id or f"DEF-???(line {err.lineno})",
        title=f"malformed registry entry: {_clip(err.reason)}",
        severity="blocking",
        status="open",
        affects=err.affects,
        first_seen="unknown (entry is malformed)",
        source=f"{registry_path} near line {err.lineno}",
        summary=(
            "This entry could not be parsed, so it is treated as an open "
            "blocking defect against the scope it names. Fix the entry in "
            "the registry to clear it."
        ),
        synthetic=True,
    )


def load_registry(
    registry_path: "str | Path | None" = None,
) -> List[DefectEntry]:
    """Parse the registry and return the entries the gates run against.

    Equivalent to ``parse_registry(registry_path).gate_entries``: every valid
    entry, plus one synthetic open blocking entry per malformed entry whose
    ``Affects:`` token could be read.  A malformed entry therefore blocks only
    the artifact it names; it no longer raises, and it no longer takes every
    other artifact down with it.

    Entries are still validated for: unknown ``Severity:``, ``waived`` or
    unknown ``Status:``, ``Status: closed`` without ``Closing-evidence:``
    (an unevidenced close is malformed, never closed), duplicate ids, and
    missing required fields.  Use :func:`parse_registry` to see the errors.

    Multi-line field values (``Summary:``, ``Closing-evidence:``,
    ``Related:``) are assembled by appending continuation lines (any line that
    does not start ``- **`` or ``###`` and is not blank between two field
    lines) to the last field seen in the current entry.

    Args:
        registry_path: Path to the registry file.  Defaults to
            ``defects.local.md`` if present, else ``knowledge/context/defects.md``.

    Returns:
        A list of :class:`DefectEntry` objects.

    Raises:
        FileNotFoundError: if the registry file does not exist.
        DefectRegistryError: if the file exists but cannot be read.
    """
    return parse_registry(registry_path).gate_entries


def parse_registry(
    registry_path: "str | Path | None" = None,
) -> Registry:
    """Parse the registry, collecting per-entry errors instead of raising.

    Raises:
        FileNotFoundError: if the registry file does not exist.  Callers that
            want the warn-and-pass behaviour (every gate helper) use
            :func:`_read_registry_for_gate` instead.
        DefectRegistryError: if the file exists but cannot be read/decoded.
    """
    registry_path = resolve_registry_path(registry_path)
    if not registry_path.exists():
        raise FileNotFoundError(f"defect registry not found: {registry_path}")

    try:
        # utf-8-sig: a byte-order mark must not hide a first-line heading
        # (#226; it used to turn a one-entry registry into an empty one).
        lines = registry_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        # A file we cannot read is not the same as an entry we cannot parse:
        # there is nothing to isolate, and silently gating nothing would be
        # a false all-clear.
        raise DefectRegistryError(
            f"defect registry could not be read: {registry_path} "
            f"({type(exc).__name__})"
        ) from exc

    entries: List[DefectEntry] = []
    errors: List[ParseError] = []
    seen_ids: dict[str, int] = {}  # id -> line number for dup detection

    # Parser state for the current entry.
    current_id: Optional[str] = None
    current_fields: dict[str, str] = {}
    current_last_field: Optional[str] = None
    current_id_lineno: int = 0
    # False when the heading that opened this entry was DEF-prefixed but not a
    # well-formed id (or was disguised, code-indented or fenced).  Such an
    # entry can never validate, so it is flushed straight to a ParseError
    # carrying whatever Affects: it managed to state.
    current_id_wellformed: bool = True
    # First structural problem seen inside a well-formed entry (a field line
    # that is code-indented, blockquoted, nested or repeated).  Such an entry
    # is malformed whatever its fields say (#226).
    current_problem: Optional[str] = None
    # Every Affects value stated anywhere in the entry, in order: a repeated
    # or nested Affects line names a scope too, and a malformed entry fails
    # closed for each one.
    current_affects: List[str] = []
    # Indent of the entry's first field line; every later field must match.
    field_indent: Optional[int] = None
    # True when the entry was opened by a heading inside a fence, so the
    # fenced field lines that follow are read (for its scope) rather than
    # treated as description text.
    current_fence_opened: bool = False
    # The opening delimiter while inside a fenced code block, else None.
    fence: Optional[str] = None

    def _open_entry(entry_id: str, lineno: int, wellformed: bool,
                    fence_opened: bool = False) -> None:
        nonlocal current_id, current_id_lineno, current_fields
        nonlocal current_last_field, current_id_wellformed, current_problem
        nonlocal current_affects, field_indent, current_fence_opened
        _flush_entry(lineno)
        current_id = entry_id
        current_id_lineno = lineno
        current_fields = {}
        current_last_field = None
        current_id_wellformed = wellformed
        current_problem = None
        current_affects = []
        field_indent = None
        current_fence_opened = fence_opened

    def _flush_entry(lineno: int) -> None:
        """Validate the current entry, recording either it or its error."""
        nonlocal current_id, current_fields, current_last_field
        nonlocal current_id_wellformed, current_problem, current_affects
        if current_id is None:
            return
        if not current_id_wellformed:
            # Evidential, not lexical: report only when the section actually
            # collected field lines.  Those field lines ARE the harm (they are
            # what used to bleed upward into the previous entry), so a heading
            # with none has nothing to bleed and nothing to say.  This keeps a
            # prose heading that happens to start with uppercase DEF
            # (``### DEFECTS``, ``### DEFINITIONS``) silent, which matters
            # most in the defects.local.md a stranger writes from scratch.
            # Note that TERMINATION of the previous entry is unconditional and
            # happens above: that is the property that removes the corruption.
            # A digit in the id token (``DEF-1O2``, ``DEF102``) is evidence on
            # its own: that heading meant to be an entry, so it is reported
            # even when its fields are in some other syntax (``* **Field:**``
            # bullets) and nothing was collected (#226 review W1).
            id_token = (current_id.split() or [""])[0]
            if current_fields or any(ch.isdigit() for ch in id_token):
                errors.append(_structural_error(
                    _clip(current_id, 40), current_id_lineno,
                    f"heading {_clip(current_id, 40)!r} is not a well-formed "
                    f"defect id (expected '### DEF-NNN' at the start of the "
                    f"line, not fenced, indented as code, blockquoted or "
                    f"behind a non-breaking space), so this entry could not "
                    f"be read",
                    current_fields, current_affects,
                ))
        elif current_problem is not None:
            seen_ids.setdefault(current_id, current_id_lineno)
            errors.append(_structural_error(
                current_id, current_id_lineno, current_problem,
                current_fields, current_affects,
            ))
        else:
            err = _validate_and_emit(
                current_id, current_fields, current_id_lineno, entries, seen_ids
            )
            if err is not None:
                errors.append(err)
        current_id = None
        current_fields = {}
        current_last_field = None
        current_id_wellformed = True
        current_problem = None
        current_affects = []

    def _record_field(fname: str, fval: str) -> None:
        """Record a field line: first value wins, every Affects is kept."""
        nonlocal current_last_field
        if fname == "Affects":
            current_affects.append(fval)
        current_fields.setdefault(fname, fval)
        current_last_field = fname

    def _append(text: str) -> None:
        """Description text: continue the last field's value, if any."""
        if current_last_field is not None and text.strip():
            current_fields[current_last_field] = (
                current_fields[current_last_field] + " " + text.strip()
            )

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()
        # Up to three spaces of indent are allowed before a heading, a field
        # or a fence; four or more, or a tab, make the line an indented code
        # block in Markdown.
        indent, rest = _INDENT_RE.match(line).groups()
        code_indent = "\t" in indent or len(indent) > 3

        # --- Fenced code blocks (#226) ---
        # Fenced lines are description text, never fields or headings.  A
        # defect heading inside a fence opens a MALFORMED entry, so it can
        # neither hide a defect nor be read as a real one; the one exception
        # is a schema placeholder with no digit (``### DEF-NNN``) before the
        # first entry, which is the registry's own documentation.
        m_fence = None if code_indent else _FENCE_RE.match(rest)
        if fence is not None:
            if (m_fence and m_fence.group(1)[0] == fence[0]
                    and len(m_fence.group(1)) >= len(fence)
                    and not m_fence.group(2).strip()):
                fence = None
                continue
            m_fenced_def = _LOOSE_DEF_HEADING_RE.match(line)
            if m_fenced_def and not (
                    current_id is None
                    and _FENCED_PLACEHOLDER_ID_RE.match(line[m_fenced_def.end():])):
                _open_entry(line.strip().lstrip(">#").strip() or "DEF-?",
                            lineno, wellformed=False, fence_opened=True)
                continue
            if current_id is not None and current_fence_opened:
                m_loose = _LOOSE_FIELD_RE.match(line)
                if m_loose:
                    _record_field(m_loose.group(1).strip(), m_loose.group(2).strip())
                    continue
            if current_id is not None:
                _append(line)
            continue
        if m_fence:
            fence = m_fence.group(1)
            continue

        # Before the first entry, indented code (schema examples) is skipped.
        if current_id is None and code_indent:
            continue

        # --- Entry heading, well-formed or not ---
        if _LOOSE_DEF_HEADING_RE.match(line):
            m_section = None if code_indent else _SECTION_RE.match(rest)
            if m_section:
                _open_entry(m_section.group(1), lineno, wellformed=True)
            else:
                # Terminates the previous entry exactly as a valid heading
                # does, so the previous entry's fields are no longer reachable
                # for overwrite, and opens an entry that is already known to
                # be unreadable.
                _open_entry(line.strip().lstrip(">#").strip() or "DEF-?",
                            lineno, wellformed=False)
            continue

        # Skip lines before the first entry.
        if current_id is None:
            continue

        # --- Field line ---
        # Anything field-shaped that is not a plain field at this entry's
        # field indent marks the entry malformed: a code-block indent, a
        # blockquote or non-breaking space prefix, a different indent (a
        # nested sub-bullet such as "  - **Status:** closed" under Summary),
        # or a repeated field.  Each of those used to be able to overwrite or
        # drop a real field.  The line is still recorded, so the malformed
        # entry fails closed for every scope it names.
        m_loose = _LOOSE_FIELD_RE.match(line)
        if m_loose:
            fname = m_loose.group(1).strip()
            fval = m_loose.group(2).strip()
            problem = None
            if code_indent:
                problem = (f"field line {_clip(rest, 60)!r} is indented like a "
                           f"code block (a tab or 4+ spaces)")
            elif not _FIELD_RE.match(rest):
                problem = (f"field line {_clip(line.strip(), 60)!r} is prefixed "
                           f"by a blockquote or a non-breaking space")
            elif field_indent is not None and len(indent) != field_indent:
                problem = (f"field line {_clip(rest, 60)!r} is indented "
                           f"{len(indent)} space(s) but the entry's fields are "
                           f"at {field_indent} (a nested bullet shaped like a "
                           f"field?)")
            elif fname in current_fields:
                problem = f"field {fname!r} appears twice; refusing to pick one"
            if field_indent is None and problem is None:
                field_indent = len(indent)
            if problem is not None and current_problem is None:
                current_problem = f"line {lineno}: {problem}"
            _record_field(fname, fval)
            continue

        # --- Continuation line (part of a multi-line field value) ---
        # A non-blank, non-section, non-field line that follows a field line
        # is appended to the last field's value (handles Summary, Closing-
        # evidence, etc. which can span 2-4 lines in the markdown).
        if line.strip():
            _append(line)
            continue

        # Blank line: clear the continuation pointer so a blank line between
        # fields doesn't accidentally merge separate fields.
        current_last_field = None

    # Flush the last entry.
    _flush_entry(len(lines) + 1)

    return Registry(path=registry_path, entries=entries, errors=errors)


def _known_pak_names() -> frozenset:
    """Every pak name registered in ``knowledge/context/managed_paks.md``.

    Consulted only to attribute a MALFORMED multi-token ``Affects:`` to its
    first token.  Covers every section of the registry: the factory SDK
    paks, the third-party Python forks (which carry no ``adapter_kind:``
    line) and the retired paks, because a defect may name any of them and
    an unrecognised first token fails open for every pak but the one being
    gated (#219).  Best effort: an unreadable managed-paks registry yields
    an empty set, which only means such an entry stays unattributed
    (reported, blocks nothing) rather than failing closed for a pak.
    """
    try:
        from .managed_paks import registered_pak_names
        # Lower-cased: every gate comparison is case-insensitive (#226).
        return frozenset(_norm(name) for name in registered_pak_names())
    except Exception as exc:
        # Expected when this file runs as a standalone script (a pak repo's
        # vendored ci/defect_gate.py): there is no package to import from.
        # gate_pak still fails closed for the pak it is gating via
        # ParseError.candidate, so say what is lost rather than go quiet.
        if not _KNOWN_PAKS_WARNED:
            _KNOWN_PAKS_WARNED.append(True)
            _warn(
                "WARNING: managed-paks registry unavailable "
                f"({type(exc).__name__}); a malformed multi-token Affects is "
                "attributed only to the pak being gated, not to any known pak"
            )
        return frozenset()


#: One-shot flag for the managed-paks lookup warning (list so no ``global``).
_KNOWN_PAKS_WARNED: list = []


def _affects_problem(raw: str) -> Optional[str]:
    """Why an ``Affects:`` value breaks the one-token contract, else None.

    Four shapes are rejected.  A multi-token value (a token plus a
    parenthetical note, a wrapped path, prose) can never equal the pak name
    or ``<type>/<slug>`` a gate matches against, so the entry used to parse
    as valid and silently block nothing (#153).  A single token carrying a
    prefix other than ``factory:`` (``pak:synology``) fails the same way.
    So does one holding a comma or a backtick (``template,unifi``,
    ```template```), ported from the vendored gate (#226), and one with
    leading or trailing punctuation (``synology.``, #226 review N1).
    """
    tokens = raw.split()
    if len(tokens) != 1:
        return (
            f"Affects {_clip(raw)!r} is {len(tokens)} tokens; it must be exactly "
            f"one scope token (a managed pak name, <type>/<slug>, or "
            f"factory:<area>). Move notes such as file paths into Summary or "
            f"Related, and split a multi-artifact entry into one entry each"
        )
    if _LIST_CHARS_RE.search(tokens[0]):
        return (
            f"Affects {_clip(raw)!r} contains a comma or a backtick; it must be "
            f"exactly one bare scope token. One issue on N artifacts is N "
            f"entries"
        )
    if tokens[0].strip(_EDGE_PUNCT) != tokens[0]:
        return (
            f"Affects {_clip(raw)!r} has leading or trailing punctuation; it "
            f"must be exactly one bare scope token"
        )
    if ":" in tokens[0] and not _FACTORY_SCOPE_RE.match(tokens[0]):
        return (
            f"Affects {_clip(raw)!r} is not a recognised scope: the only "
            f"prefixed form is factory:<area>; a pak is named bare (e.g. "
            f"'synology') and a content item as <type>/<slug>"
        )
    return None


def _classify_affects(raw: str) -> Tuple[List[str], List[str]]:
    """``(scopes, candidates)`` for one ``Affects:`` value.

    A valid value (one bare token) is its own single scope.  A malformed one
    is split into tokens on whitespace, commas and backticks, each stripped
    of edge punctuation, and EVERY token is classified (#226 review B1:
    ``template, unifi`` names unifi as much as template):

    - a ``<type>/<slug>`` or ``factory:<area>`` token is a scope;
    - a pak-shaped token is a scope when it is a KNOWN managed pak, or when
      the value has no whitespace at all (``template,unifi``, ``synology.``:
      a list or a decorated token, never prose), and a candidate otherwise;
    - a token with an unrecognised prefix offers the name after the colon
      as a candidate (``pak:synology`` -> ``synology``).

    A scope fails closed for that artifact everywhere.  A candidate fails
    closed only for a pak gated by exactly that name, so a prose word can
    never block anything but a pak literally called that, and needs no
    managed-paks lookup (the standalone-script path).

    Scopes are returned UNCLIPPED: each has to compare equal to a real pak
    name or <type>/<slug> token for the synthetic entry to gate anything, and
    a truncated copy never can.  Callers clip at the point of echo instead.
    """
    raw = (raw or "").strip()
    if not raw:
        return [], []
    if _affects_problem(raw) is None:
        return [raw], []
    no_whitespace = len(raw.split()) == 1
    known = _known_pak_names()
    scopes: List[str] = []
    candidates: List[str] = []
    for token in _AFFECTS_SPLIT_RE.split(raw):
        # Keep an edge colon for the prefix test below: ``pak:`` names no pak.
        token = token.strip(_EDGE_PUNCT.replace(":", ""))
        if not token:
            continue
        if _ITEM_SCOPE_RE.match(token) or _FACTORY_SCOPE_RE.match(token):
            scopes.append(token)
        elif ":" in token:
            name = token.split(":", 1)[1].strip(_EDGE_PUNCT)
            if _PAK_NAME_RE.match(name):
                (scopes if _norm(name) in known else candidates).append(name)
        elif _PAK_NAME_RE.match(token):
            if no_whitespace or _norm(token) in known:
                scopes.append(token)
            else:
                candidates.append(token)
    return scopes, candidates


def _dedupe(values: List[str], exclude: Tuple[str, ...] = ()) -> List[str]:
    """Order-preserving, case-insensitive de-duplication."""
    seen = {_norm(v) for v in exclude}
    out: List[str] = []
    for value in values:
        if _norm(value) not in seen:
            seen.add(_norm(value))
            out.append(value)
    return out


def _affects_attribution(values: List[str]) -> Tuple[List[str], List[str]]:
    """``(scopes, candidates)`` across every ``Affects:`` value of an entry."""
    scopes: List[str] = []
    candidates: List[str] = []
    for value in values:
        s, c = _classify_affects(value)
        scopes += s
        candidates += c
    scopes = _dedupe(scopes)
    return scopes, _dedupe(candidates, exclude=tuple(scopes))


def _value_scopes(raw: str) -> List[str]:
    """The scopes one ``Affects:`` value is attributed to (no candidates)."""
    return _classify_affects(raw)[0]


def _entry_scopes(values: List[str]) -> List[str]:
    """Every distinct scope named by an entry's ``Affects:`` values, in order."""
    return _affects_attribution(values)[0]


def _readable_affects(fields: dict[str, str]) -> str:
    """The entry's first attributable ``Affects:`` scope, else ``""``."""
    scopes = _value_scopes(fields.get("Affects") or "")
    return scopes[0] if scopes else ""


def _candidate_entries(
    registry: "Registry", pak_name: Optional[str] = None,
) -> List[DefectEntry]:
    """Synthetic blockers for the candidates of every parse error.

    ``gate_pak`` passes the pak being gated and gets one per error naming it
    as a candidate (compared case-insensitively, like every gate match);
    ``gate_all`` passes nothing and gets one per candidate, each labelled
    with it, so ``--all`` agrees with ``--pak <candidate>``.  Scoped errors
    count too: ``synology, newpak`` is scoped to a known synology and still
    names newpak.
    """
    out: List[DefectEntry] = []
    for err in registry.errors:
        for name in err.candidates:
            if pak_name is None or _norm(name) == _norm(pak_name):
                out.append(_synthetic_entry(replace(err, affects=name), registry.path))
    return out


def _parse_error(
    entry_id: str,
    lineno: int,
    reason: str,
    affects_values: List[str],
) -> ParseError:
    """A ParseError that fails closed for every scope and candidate named."""
    scopes, candidates = _affects_attribution(affects_values)
    return ParseError(
        entry_id=entry_id,
        lineno=lineno,
        reason=reason,
        affects=scopes[0] if scopes else "",
        candidates=tuple(candidates),
        extra_scopes=tuple(scopes[1:]),
    )


def _structural_error(
    entry_id: str,
    lineno: int,
    reason: str,
    fields: dict[str, str],
    affects_values: List[str],
) -> ParseError:
    """ParseError for an entry malformed in its SHAPE, not its values.

    Covers a bad heading and a disguised, nested or repeated field line.
    The entry fails closed for every scope any of its ``Affects:`` lines
    names, and for a pak gated by exactly any candidate name in them.
    """
    return _parse_error(entry_id, lineno, reason, affects_values)


def _validate_and_emit(
    entry_id: str,
    fields: dict[str, str],
    lineno: int,
    entries: List[DefectEntry],
    seen_ids: dict[str, int],
) -> Optional[ParseError]:
    """Validate one entry's field dict.

    Appends a :class:`DefectEntry` to ``entries`` and returns None when the
    entry is valid; returns a :class:`ParseError` (and appends nothing) when
    it is not.  Never raises: one bad entry must not take the file down.
    """
    affects_values = [fields["Affects"]] if fields.get("Affects") else []

    def _err(reason: str) -> ParseError:
        return _parse_error(entry_id, lineno, reason, affects_values)

    # --- Duplicate ID check ---
    if entry_id in seen_ids:
        return _err(
            f"duplicate defect id {entry_id!r}: first seen near line "
            f"{seen_ids[entry_id]}, duplicate near line {lineno}"
        )
    seen_ids[entry_id] = lineno

    # --- Required fields ---
    for req in _REQUIRED_FIELDS:
        if req not in fields or not fields[req].strip():
            return _err(f"required field {req!r} is missing or empty")

    title = fields["Title"].strip()
    severity = fields["Severity"].strip().lower()
    status = fields["Status"].strip().lower()
    affects = fields["Affects"].strip()
    first_seen = fields["First-seen"].strip()
    source = fields["Source"].strip()
    summary = fields["Summary"].strip()
    closing_evidence = fields.get("Closing-evidence", "").strip()
    related = fields.get("Related", "").strip()

    # --- Affects must be one recognised scope token (#153) ---
    # Checked before severity/status so the reported reason is the one that
    # made this entry silently gate nothing.
    affects_problem = _affects_problem(affects)
    if affects_problem is not None:
        return _err(affects_problem)

    # --- Severity validation ---
    if severity not in _VALID_SEVERITIES:
        return _err(
            f"invalid Severity {severity!r}. "
            f"Allowed: {', '.join(sorted(_VALID_SEVERITIES))}"
        )

    # --- Status validation (waived is explicitly rejected) ---
    if status == "waived":
        return _err(
            "'waived' is not a valid Status. "
            "To ship a defect, downgrade Severity to 'tracked' with a dated note, "
            "the git diff is the audit trail. See knowledge/rules/release-gate-defects.md."
        )
    if status not in _VALID_STATUSES:
        return _err(
            f"invalid Status {status!r}. "
            f"Allowed: {', '.join(sorted(_VALID_STATUSES))}. "
            f"Note: 'waived' is not accepted, see knowledge/rules/release-gate-defects.md."
        )

    # --- Closed-without-evidence check ---
    if status == "closed" and not closing_evidence:
        return _err(
            "Status is 'closed' but Closing-evidence is absent or empty. "
            "A close without evidence is invalid, provide concrete proof "
            "(fix commit/build, devel proof, lesson). "
            "See knowledge/context/defects.md schema and knowledge/rules/release-gate-defects.md."
        )

    entries.append(DefectEntry(
        id=entry_id,
        title=title,
        severity=severity,
        status=status,
        affects=affects,
        first_seen=first_seen,
        source=source,
        summary=summary,
        closing_evidence=closing_evidence,
        related=related,
    ))
    return None


# ---------------------------------------------------------------------------
# Gate helpers
# ---------------------------------------------------------------------------

def _warn(message: str) -> None:
    """Emit a gate warning on stderr, unbuffered.

    stderr so a warning can never be mistaken for gate output on stdout,
    and so it survives a caller that only captures stdout.
    """
    print(message, file=sys.stderr, flush=True)


#: Registry paths already warned about in this process.  ``publish`` calls a
#: gate once per headline artifact, so without this a publish set of N
#: releases prints N copies of every warning, and N-times-loud trains people
#: to skip the warning entirely.  Loud once, not loud N times.
_WARNED_REGISTRIES: set = set()


def reset_warning_state() -> None:
    """Forget which registries have been warned about (tests, long-lived procs)."""
    _WARNED_REGISTRIES.clear()
    _KNOWN_PAKS_WARNED.clear()


def local_registry_hint(
    registry_path: "str | Path | None" = None,
) -> str:
    """One sentence to append to a REFUSAL, or ``""`` when there is nothing to say.

    "Upstream defects may block you" is only information at the moment one
    actually blocks you, so this belongs on the refusal rather than in a
    standing session report.  Silent when the caller already has a
    ``defects.local.md``: they are being refused by their own registry, and
    there is nothing to tell them.
    """
    try:
        resolved = resolve_registry_path(registry_path)
        if resolved.name == LOCAL_REGISTRY_NAME:
            return ""
        if resolved.with_name(LOCAL_REGISTRY_NAME).exists():
            return ""
    except OSError:
        return ""
    return (
        "This refusal came from the factory's own knowledge/context/defects.md. "
        "If these defects are not yours, create knowledge/context/defects.local.md "
        "and keep your own registry there: the factory never ships that filename, "
        "so it gates your work alone and a git pull cannot conflict with it."
    )


def _read_registry_for_gate(
    registry_path: "str | Path | None" = None,
) -> Registry:
    """Registry read used by every gate helper.

    Two behaviours the gates share, both from
    ``knowledge/designs/defect-isolation-v1.md``:

    - An ABSENT registry warns (naming RULE-012) and gates nothing.  A file
      that is not there has nothing to say about any artifact, and refusing
      a release over its absence is the coupling that broke third-party
      users.  This matches ``publish._gate_publish``'s long-standing
      behaviour; the CLI/CI path was the outlier.
    - Every per-entry parse error is surfaced on EVERY gate invocation, so
      a broken entry cannot rot silently, whether or not it blocks the
      artifact being gated.
    """
    resolved = resolve_registry_path(registry_path)
    key = str(resolved)
    first_time = key not in _WARNED_REGISTRIES
    _WARNED_REGISTRIES.add(key)

    if not resolved.exists():
        if first_time:
            _warn(
                f"WARNING: no defect registry at {resolved}, the RULE-012 gate "
                f"has nothing to check and vacuously passes"
            )
        return Registry(path=resolved, exists=False)

    registry = parse_registry(resolved)
    if first_time and registry.empty:
        # Same verdict as an absent file, and just as loud: an empty, truncated
        # or reformatted registry has nothing to say about any artifact.  It is
        # also the normal state of a defects.local.md someone just created.
        # Pak CI that must never pass on this uses --require-registry (#226).
        _warn(
            f"WARNING: defect registry {resolved} holds no '### DEF-NNN' "
            f"entries, the RULE-012 gate has nothing to check and vacuously "
            f"passes"
        )
    if first_time:
        for err in registry.errors:
            names = ", ".join(repr(_clip(c)) for c in err.candidates[:10])
            if err.scoped:
                scopes = ", ".join(
                    repr(_clip(s)) for s in (err.affects,) + err.extra_scopes
                )
                also = (
                    f", and against a pak gated by the exact name {names}"
                    if names else ""
                )
                _warn(
                    f"WARNING: defect registry entry is malformed and is being "
                    f"treated as an open blocking defect against "
                    f"{scopes}{also}: {err}"
                )
            elif err.candidates:
                _warn(
                    f"WARNING: defect registry entry is malformed AND its "
                    f"'Affects:' scope could not be confirmed; it blocks only "
                    f"a pak gated by the exact name {names}, "
                    f"and nothing else: {err}"
                )
            else:
                _warn(
                    f"WARNING: defect registry entry is malformed AND its "
                    f"'Affects:' scope could not be read, so it blocks nothing "
                    f"and no artifact is being gated by it: {err}"
                )
    return registry


def gate_pak(
    pak_name: str,
    registry_path: "str | Path | None" = None,
) -> List[DefectEntry]:
    """Return all open blocking defects that affect ``pak_name``.

    ``pak_name`` is matched against the ``Affects:`` token ignoring case and
    surrounding spaces, so ``Synology`` in the registry still gates the
    ``synology`` pak (#226, as the vendored gate already did).  Otherwise it
    must be the managed-pak name as registered in
    ``knowledge/context/managed_paks.md`` (e.g. ``"synology"``, ``"unifi"``).

    Args:
        pak_name:      Managed pak name to check.
        registry_path: Path to the registry; defaults to ``knowledge/context/defects.md``.

    Returns:
        List of open blocking :class:`DefectEntry` objects.  Empty list = clean.

    Raises:
        DefectRegistryError: only if the registry file exists but cannot be
            read at all.  A MISSING registry warns and returns [] (nothing to
            check), and a malformed ENTRY is isolated to the scope it names,
            so neither raises out of this function.
    """
    registry = _read_registry_for_gate(registry_path)
    # A malformed Affects whose candidate IS this pak: the caller has just
    # told us that name is a pak, so fail closed for it even when the
    # managed-paks lookup is unavailable (script mode).
    entries = registry.gate_entries + _candidate_entries(registry, pak_name)
    want = _norm(pak_name)
    return [
        e for e in entries
        if e.severity == "blocking"
        and e.status == "open"
        and _norm(e.affects) == want
    ]


def gate_item(
    content_type: str,
    slug: str,
    registry_path: "str | Path | None" = None,
) -> List[DefectEntry]:
    """Return all open blocking defects that affect ``<content_type>/<slug>``.

    The ``Affects:`` token is matched, ignoring case, as ``<content_type>/<slug>``.
    ``content_type`` is the singular directory name (e.g. ``"dashboard"``,
    ``"view"``).  ``slug`` is the filename stem (e.g.
    ``"demand_driven_capacity_v2"``).

    Note on slug vs. name: callers should pass the filename stem (slug) of
    the source YAML, not the display name.  The defect registry's ``Affects:``
    field uses the ``<type>/<slug>`` form, not the display name.

    Args:
        content_type:  Singular content type name.
        slug:          Filename stem of the content item.
        registry_path: Path to the registry; defaults to ``knowledge/context/defects.md``.

    Returns:
        List of open blocking :class:`DefectEntry` objects.  Empty list = clean.

    Raises:
        DefectRegistryError: only if the registry file exists but cannot be
            read at all.  A MISSING registry warns and returns [] (nothing to
            check), and a malformed ENTRY is isolated to the scope it names,
            so neither raises out of this function.
    """
    token = _norm(f"{content_type}/{slug}")
    entries = _read_registry_for_gate(registry_path).gate_entries
    return [
        e for e in entries
        if e.severity == "blocking"
        and e.status == "open"
        and _norm(e.affects) == token
    ]


def gate_all(
    registry_path: "str | Path | None" = None,
) -> List[DefectEntry]:
    """Return all open blocking defects in the registry.

    Args:
        registry_path: Path to the registry; defaults to ``knowledge/context/defects.md``.

    Returns:
        List of open blocking :class:`DefectEntry` objects.  Empty list = clean.

    Raises:
        DefectRegistryError: only if the registry file exists but cannot be
            read at all.  A MISSING registry warns and returns [] (nothing to
            check), and a malformed ENTRY is isolated to the scope it names,
            so neither raises out of this function.
    """
    registry = _read_registry_for_gate(registry_path)
    # Include partially attributed malformed entries, labelled with their
    # candidate, so `--all` agrees with `--pak <candidate>`.
    entries = registry.gate_entries + _candidate_entries(registry)
    return [
        e for e in entries
        if e.severity == "blocking"
        and e.status == "open"
    ]


def _norm(token: str) -> str:
    """An ``Affects:`` token or gated name for comparison: trimmed, lower-case."""
    return (token or "").strip().lower()


def format_defect_line(entry: DefectEntry) -> str:
    """Return the human-readable single-line summary for a blocking defect.

    Format::

        DEF-NNN  <title>  (first seen <first_seen>, source <source>)
    """
    return (
        f"{entry.id}  {entry.title}  "
        f"(first seen {entry.first_seen}, source {entry.source})"
    )


# ---------------------------------------------------------------------------
# Vendored copy for pak-repo CI (#226)
#
# A pak repo's release CI runs the gate BEFORE it downloads the buildkit, so
# it cannot use sdk_buildkit/defect_gate.py and carries its own copy as
# ci/defect_gate.py.  That copy is GENERATED from this file, never written by
# hand: ``python3 -m vcfcf_packaging vendor-defect-gate --out <path>``.  The
# generated text is a comment header carrying two SHA-256 checksums, then
# this file with exactly one line changed (_STANDALONE_REQUIRE_REGISTRY).
#
#   source sha256: of this file, the factory module it was generated from
#   body sha256:   of everything below the header, as written
#
# ``python3 ci/defect_gate.py --verify-vendored`` (stdlib, no factory needed)
# proves the body is what was generated; ``--against <defects.py>`` also
# proves it is what that factory module generates today.  The factory side
# checks a copy with ``vendor-defect-gate --check <path>``.  The generator
# lives HERE, not in the CLI, so the vendored copy carries it too and can
# regenerate itself for the comparison.
# ---------------------------------------------------------------------------

#: Default of ``--require-registry`` when this file runs as a script.  False
#: here, so the factory module and the sdk-buildkit's verbatim copy keep the
#: RULE-012 default: an absent or entry-less registry warns and passes.
#: vendored_gate_text() sets it to True in the ci/defect_gate.py a pak repo
#: vendors.  That CI fetched the registry on purpose, so a failed fetch must
#: never read as an all-clear, and a pak repo that regenerates without
#: touching its workflow keeps the refusal its hand-vendored gate had.
_STANDALONE_REQUIRE_REGISTRY = False

#: File name a pak repo vendors the gate under (``ci/defect_gate.py``).
VENDORED_GATE_NAME = "defect_gate.py"

_VENDOR_SOURCE_MARK = "# vcfcf-defect-gate-source-sha256: "
_VENDOR_BODY_MARK = "# vcfcf-defect-gate-body-sha256: "
#: The one line the generator changes.  Anchored to a whole line, so the
#: mentions of the name in comments and code never match.
_VENDOR_DEFAULT_LINE_RE = re.compile(
    r"^_STANDALONE_REQUIRE_REGISTRY = False$", re.MULTILINE
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def vendored_gate_text(source_text: str) -> str:
    """The vendorable ``ci/defect_gate.py`` generated from ``source_text``.

    ``source_text`` is the text of this module (``vcfcf_packaging/defects.py``).
    Deterministic: the same source always yields the same bytes, which is
    what lets a copy be checked by regenerating it.

    Raises:
        ValueError: if ``source_text`` does not carry the require-registry
            default line exactly once (not a defects.py this generator knows).
    """
    body, count = _VENDOR_DEFAULT_LINE_RE.subn(
        "_STANDALONE_REQUIRE_REGISTRY = True", source_text
    )
    if count != 1:
        raise ValueError(
            "source is not vcfcf_packaging/defects.py: expected exactly one "
            f"'_STANDALONE_REQUIRE_REGISTRY = False' line, found {count}"
        )
    header = (
        "# GENERATED FILE, do not edit. The RULE-012 defect gate, vendored for\n"
        "# pak-repo CI from src/vcfcf_packaging/defects.py in\n"
        "# sentania-labs/vcf-content-factory by\n"
        "#   python3 -m vcfcf_packaging vendor-defect-gate --out ci/defect_gate.py\n"
        "# Fix the factory module and regenerate; never edit this copy (#226).\n"
        "#\n"
        "# Pak CI:\n"
        "#   python3 ci/defect_gate.py --verify-vendored\n"
        "#   python3 ci/defect_gate.py --pak <name> --registry defects.md\n"
        "# Exit 0 clear, 1 unusable registry or failed verify, 2 refused.  Unlike\n"
        "# the factory module, this copy refuses (exit 1) an absent, empty or\n"
        "# unrecognised registry by default: --require-registry is always on.\n"
        "#\n"
        f"{_VENDOR_SOURCE_MARK}{_sha256_text(source_text)}\n"
        f"{_VENDOR_BODY_MARK}{_sha256_text(body)}\n"
    )
    return header + body


def _split_vendored(text: str) -> Tuple[str, str]:
    """``(header, body)``: the leading run of ``#`` lines, and the rest."""
    lines = text.splitlines(keepends=True)
    n = 0
    while n < len(lines) and lines[n].startswith("#"):
        n += 1
    return "".join(lines[:n]), "".join(lines[n:])


def verify_vendored_text(
    text: str, source_text: Optional[str] = None,
) -> Optional[str]:
    """Why ``text`` is not a faithful vendored gate, or None when it is.

    Without ``source_text``: the header must carry both checksums and the
    body must hash to the recorded one (no hand edit since generation).
    With ``source_text`` (a factory ``defects.py``): additionally, ``text``
    must be byte for byte what that source generates (not stale, header not
    edited either).
    """
    header, body = _split_vendored(text)
    marks = {}
    for line in header.splitlines():
        for mark in (_VENDOR_SOURCE_MARK, _VENDOR_BODY_MARK):
            if line.startswith(mark):
                marks[mark] = line[len(mark):].strip()
    if _VENDOR_SOURCE_MARK not in marks or _VENDOR_BODY_MARK not in marks:
        return (
            "no generated checksum header: this is not a vendored copy made by "
            "'python3 -m vcfcf_packaging vendor-defect-gate'; regenerate it"
        )
    if _sha256_text(body) != marks[_VENDOR_BODY_MARK]:
        return (
            "edited by hand: the body no longer matches the checksum recorded "
            "when it was generated; regenerate it from the factory module"
        )
    if source_text is not None:
        if _sha256_text(source_text) != marks[_VENDOR_SOURCE_MARK]:
            return (
                "stale: generated from a factory defects.py with sha256 "
                f"{_clip(marks[_VENDOR_SOURCE_MARK], 64)}, the given source is "
                f"{_sha256_text(source_text)}; regenerate it"
            )
        try:
            expected = vendored_gate_text(source_text)
        except ValueError as exc:
            return f"cannot regenerate from the given source: {exc}"
        if text != expected:
            return (
                "differs from what the given factory defects.py generates "
                "although the checksums agree (header edited?); regenerate it"
            )
    return None


# ---------------------------------------------------------------------------
# Standalone entrypoint
#
# This block makes defects.py runnable as a bare script with no package
# install, intended for pak-repo CI that curl's this file alongside
# knowledge/context/defects.md and invokes:
#
#   python3 defects.py --pak <name> [--registry <path>]
#   python3 defects.py --all        [--registry <path>]
#
# The block must NOT use package-relative imports.  All logic it needs
# (gate_pak, gate_all, format_defect_line, DefectRegistryError) is
# defined above in this same file and is therefore available both when
# the file is run as a script and when it is imported as a module.
#
# Exit codes (match cmd_defect_gate in cli.py):
#   0, no open blocking defects affect the named pak / no open blockers at
#      all.  An ABSENT registry also exits 0, with a visible WARNING naming
#      RULE-012: a registry that is not there has nothing to say about this
#      artifact, and refusing over its absence is the coupling that broke
#      third-party releases (knowledge/designs/defect-isolation-v1.md).
#   1, registry file present but unreadable (hard error).  A malformed
#      ENTRY is no longer a whole-file error: it blocks the scope it names
#      (exit 2 for that scope) and nothing else.  With --require-registry,
#      also an absent registry or one with no DEF entry at all: for a caller
#      that fetched the registry on purpose (pak CI), either means the fetch
#      went wrong, never an all-clear (the vendored ci/defect_gate.py rule,
#      kept as an opt-in so the RULE-012 default is unchanged, #226).
#   2, one or more open blocking defects found
#
# --verify-vendored exits 0 when this file is a faithful generated copy (see
# "Vendored copy for pak-repo CI" above) and 1 otherwise.
#
# The sdk-buildkit ships this file, unchanged but for a generated header, as
# sdk_buildkit/defect_gate.py (vcfcf_managementpacks/buildkit.py).  Pak repos
# vendor it as ci/defect_gate.py through vendored_gate_text(), which differs
# only in defaulting --require-registry on.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse as _argparse
    import sys as _sys

    # Default registry: sibling of THIS file, so `curl defects.py` + `curl
    # defects.md` into the same directory and run without --registry works.
    # Resolved through preferred_registry(), the same code path the module
    # uses, so a `defects.local.md` sitting beside it wins here too.
    _DEFAULT_REGISTRY = Path(__file__).parent / "defects.md"

    _p = _argparse.ArgumentParser(
        prog="defects.py",
        description=(
            "Defect gate for pak-repo CI. "
            "Reads a defect registry and exits 0 (clean), 1 (bad registry), "
            "or 2 (open blocking defects found)."
        ),
    )
    _mode = _p.add_mutually_exclusive_group(required=True)
    _mode.add_argument(
        "--pak",
        metavar="NAME",
        default=None,
        help="check a managed pak by name (e.g. synology, unifi, compliance)",
    )
    _mode.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="list every open blocking defect across all artifacts",
    )
    _mode.add_argument(
        "--verify-vendored",
        action="store_true",
        default=False,
        help=(
            "check that this file is an unedited copy generated by "
            "'python3 -m vcfcf_packaging vendor-defect-gate' (exit 0) or not "
            "(exit 1); reads no registry"
        ),
    )
    _p.add_argument(
        "--against",
        metavar="DEFECTS_PY",
        default=None,
        help=(
            "with --verify-vendored: also require this file to be exactly what "
            "the given factory src/vcfcf_packaging/defects.py generates"
        ),
    )
    _p.add_argument(
        "--registry",
        metavar="PATH",
        default=None,
        help=(
            "path to the defect registry; an explicit path always wins "
            f"(default: {LOCAL_REGISTRY_NAME} beside {_DEFAULT_REGISTRY} if "
            f"present, else {_DEFAULT_REGISTRY})"
        ),
    )
    _p.add_argument(
        "--require-registry",
        action="store_true",
        default=_STANDALONE_REQUIRE_REGISTRY,
        help=(
            "exit 1 when the registry is absent or holds no valid DEF entry, "
            "instead of warning and passing (for CI that fetched the registry "
            "on purpose)"
            + ("; always on in this vendored copy"
               if _STANDALONE_REQUIRE_REGISTRY else "")
        ),
    )

    _args = _p.parse_args()

    if _args.against is not None and not _args.verify_vendored:
        _p.error("--against is only valid with --verify-vendored")
    if _args.verify_vendored:
        try:
            _self_text = Path(__file__).read_text(encoding="utf-8")
            _source_text = (
                Path(_args.against).read_text(encoding="utf-8")
                if _args.against is not None else None
            )
        except (OSError, UnicodeDecodeError) as _exc:
            print(f"ERROR: --verify-vendored could not read a file "
                  f"({type(_exc).__name__}: {_exc})", file=_sys.stderr)
            _sys.exit(1)
        _problem = verify_vendored_text(_self_text, _source_text)
        if _problem is not None:
            print(f"ERROR: {Path(__file__).name}: {_problem}", file=_sys.stderr)
            _sys.exit(1)
        print(f"{Path(__file__).name}: vendored defect gate verified"
              + (f" against {_args.against}" if _args.against else ""))
        _sys.exit(0)
    _registry_path = (
        Path(_args.registry) if _args.registry is not None
        else preferred_registry(_DEFAULT_REGISTRY)
    )

    try:
        if _args.require_registry:
            if not _registry_path.exists():
                raise FileNotFoundError(
                    f"--require-registry: no defect registry at {_registry_path}"
                )
            if parse_registry(_registry_path).unreadable:
                raise DefectRegistryError(
                    f"--require-registry: {_registry_path} holds no valid "
                    f"'### DEF-NNN' entry; the registry is empty or in an "
                    f"unrecognised format. Refusing to treat it as clear."
                )
        if _args.all:
            _blockers = gate_all(_registry_path)
            if not _blockers:
                print("no open blocking defects")
                _sys.exit(0)
            for _entry in _blockers:
                print(format_defect_line(_entry))
            print(
                f"\n{len(_blockers)} open blocking defect(s) found. "
                f"See RULE-012 and knowledge/context/defects.md."
            )
            _sys.exit(2)
        else:
            _pak_name = _args.pak
            _blockers = gate_pak(_pak_name, _registry_path)
            if not _blockers:
                print(f"no open blocking defects affecting {_pak_name}")
                _sys.exit(0)
            for _entry in _blockers:
                print(format_defect_line(_entry))
            print(
                f"\n{len(_blockers)} open blocking defect(s) block release of {_pak_name!r}. "
                f"Refused by RULE-012. See knowledge/context/defects.md."
            )
            _sys.exit(2)

    except FileNotFoundError as _exc:
        print(f"ERROR: registry not found: {_registry_path}", file=_sys.stderr)
        print(f"  ({_exc})", file=_sys.stderr)
        _sys.exit(1)
    except DefectRegistryError as _exc:
        print(
            f"ERROR: defect registry malformed: {_registry_path}",
            file=_sys.stderr,
        )
        print(f"  {_exc}", file=_sys.stderr)
        _sys.exit(1)
