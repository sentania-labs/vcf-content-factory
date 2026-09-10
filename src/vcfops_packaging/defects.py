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
absent registry warns and passes (RULE-012 is named in the warning), an
unreadable one raises :class:`DefectRegistryError`.

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
      - a ``DEF``-prefixed heading whose id is not ``DEF-NNN`` (a typo such as
        ``DEF-1O2``, or trailing text): it always terminates the previous entry,
        so it can never repoint a good entry, and it becomes a parse error of
        its own when it carried field lines.  A DEF-prefixed heading with no
        field lines under it is prose (``### DEFECTS``), has nothing that could
        have bled into the previous entry, and is silent.

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

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


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

    @property
    def scoped(self) -> bool:
        """True when this error can be attributed to a single artifact."""
        return bool(self.affects)

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
        return list(self.entries) + [
            _synthetic_entry(err, self.path) for err in self.errors if err.scoped
        ]

    @property
    def unscoped_errors(self) -> List[ParseError]:
        """Parse errors that block nothing because ``Affects:`` was unreadable."""
        return [e for e in self.errors if not e.scoped]


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

_SECTION_RE = re.compile(r"^#{1,4}\s+(DEF-\d+)\s*$")

#: A heading that MEANT to be an entry but whose id is not ``DEF-NNN``: a typo
#: (``DEF-1O2``, letter O), a suffix, or trailing text.  Without this, such a
#: heading matched nothing, fell through to the continuation-line branch, and
#: the following entry's field lines silently overwrote the PREVIOUS entry's
#: fields: a real defect stopped gating the artifact it named, with no error.
#: Matching it here makes it a ParseError instead, so it goes through the same
#: scoped/unscoped isolation as every other malformed entry.
#:
#: Anchored on bare ``DEF`` rather than ``DEF-`` on purpose: requiring the
#: hyphen would let ``### DEF102`` fall back through to the continuation
#: branch and reproduce the exact silent field-bleed this exists to remove,
#: on a typo from the same keystroke class.  Matching here is only half the
#: contract; ``_flush_entry`` decides whether to REPORT, and does so only
#: when the section collected field lines, which is what keeps an all-caps
#: prose heading (``### DEFECTS``) silent.  Lowercase prose (``## Defects``,
#: ``## Schema``) never matches at all.
_BAD_SECTION_RE = re.compile(r"^#{1,4}\s+(DEF.*?)\s*$")

_FIELD_RE = re.compile(r"^-\s+\*\*([^:]+):\*\*\s*(.*)")

# DEF-NNN id format.
_ID_RE = re.compile(r"^DEF-\d+$")

#: Required field names (exact, case-sensitive as they appear in the registry).
_REQUIRED_FIELDS = ("Title", "Severity", "Status", "Affects", "First-seen", "Source", "Summary")


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
        lines = registry_path.read_text(encoding="utf-8").splitlines()
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
    # well-formed id.  Such an entry can never validate, so it is flushed
    # straight to a ParseError carrying whatever Affects: it managed to state.
    current_id_wellformed: bool = True

    def _flush_entry(lineno: int) -> None:
        """Validate the current entry, recording either it or its error."""
        nonlocal current_id, current_fields, current_last_field
        nonlocal current_id_wellformed
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
            if current_fields:
                errors.append(ParseError(
                    entry_id=_clip(current_id, 40),
                    lineno=current_id_lineno,
                    reason=(
                        f"heading {_clip(current_id, 40)!r} is not a well-formed "
                        f"defect id (expected 'DEF-NNN'), so this entry could not "
                        f"be read"
                    ),
                    affects=_readable_affects(current_fields),
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

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()

        # --- New entry section heading ---
        m_section = _SECTION_RE.match(line)
        if m_section:
            _flush_entry(lineno)
            current_id = m_section.group(1)
            current_id_lineno = lineno
            current_fields = {}
            current_last_field = None
            current_id_wellformed = True
            continue

        # --- Malformed entry heading (DEF-prefixed, but not a valid id) ---
        # Terminates the previous entry exactly as a valid heading does, so the
        # previous entry's fields are no longer reachable for overwrite, and
        # opens an entry that is already known to be unreadable.
        m_bad_section = _BAD_SECTION_RE.match(line)
        if m_bad_section:
            _flush_entry(lineno)
            current_id = m_bad_section.group(1)
            current_id_lineno = lineno
            current_fields = {}
            current_last_field = None
            current_id_wellformed = False
            continue

        # Skip lines before the first entry.
        if current_id is None:
            continue

        # --- Field line ---
        m_field = _FIELD_RE.match(line)
        if m_field:
            fname = m_field.group(1).strip()
            fval = m_field.group(2).strip()
            current_fields[fname] = fval
            current_last_field = fname
            continue

        # --- Continuation line (part of a multi-line field value) ---
        # A non-blank, non-section, non-field line that follows a field line
        # is appended to the last field's value (handles Summary, Closing-
        # evidence, etc. which can span 2-4 lines in the markdown).
        if current_last_field is not None and line.strip():
            # Only append if we are inside a known entry.
            current_fields[current_last_field] = (
                current_fields[current_last_field] + " " + line.strip()
            )
            continue

        # Blank line: clear the continuation pointer so a blank line between
        # fields doesn't accidentally merge separate fields.
        if not line.strip():
            current_last_field = None

    # Flush the last entry.
    _flush_entry(len(lines) + 1)

    return Registry(path=registry_path, entries=entries, errors=errors)


def _readable_affects(fields: dict[str, str]) -> str:
    """The entry's ``Affects:`` token when it can be read, else ``""``.

    A token is readable when it is present, non-empty, and a single
    whitespace-free token (the registry's own contract: exactly one token).
    Anything else, including a missing field or a prose sentence, means the
    error cannot be attributed to one artifact, so it must block nothing.
    """
    raw = (fields.get("Affects") or "").strip()
    if not raw or len(raw.split()) != 1:
        return ""
    # Returned UNCLIPPED: this value has to compare equal to a real pak name
    # or <type>/<slug> token for the synthetic entry to gate anything, and a
    # truncated copy never can.  Callers clip at the point of echo instead,
    # so an over-length token cannot dump the whole field into output while
    # the warning still tells the truth about what it blocks.
    return raw


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
    affects_hint = _readable_affects(fields)

    def _err(reason: str) -> ParseError:
        return ParseError(
            entry_id=entry_id, lineno=lineno, reason=reason, affects=affects_hint
        )

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
    if first_time:
        for err in registry.errors:
            if err.scoped:
                _warn(
                    f"WARNING: defect registry entry is malformed and is being "
                    f"treated as an open blocking defect against "
                    f"{_clip(err.affects)!r}: {err}"
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

    ``pak_name`` is matched against the ``Affects:`` token directly,
    it must be the exact managed-pak name as registered in
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
    entries = _read_registry_for_gate(registry_path).gate_entries
    return [
        e for e in entries
        if e.severity == "blocking"
        and e.status == "open"
        and e.affects == pak_name
    ]


def gate_item(
    content_type: str,
    slug: str,
    registry_path: "str | Path | None" = None,
) -> List[DefectEntry]:
    """Return all open blocking defects that affect ``<content_type>/<slug>``.

    The ``Affects:`` token is matched exactly as ``<content_type>/<slug>``.
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
    token = f"{content_type}/{slug}"
    entries = _read_registry_for_gate(registry_path).gate_entries
    return [
        e for e in entries
        if e.severity == "blocking"
        and e.status == "open"
        and e.affects == token
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
    entries = _read_registry_for_gate(registry_path).gate_entries
    return [
        e for e in entries
        if e.severity == "blocking"
        and e.status == "open"
    ]


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
#      (exit 2 for that scope) and nothing else.
#   2, one or more open blocking defects found
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

    _args = _p.parse_args()
    _registry_path = (
        Path(_args.registry) if _args.registry is not None
        else preferred_registry(_DEFAULT_REGISTRY)
    )

    try:
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
