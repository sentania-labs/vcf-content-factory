"""The factory content-name prefix: one definition for every loader, renderer,
builder and CLI.

Every factory-authored content object (super metric, view, dashboard, custom
group, symptom, alert, recommendation, report) carries ``FACTORY_PREFIX`` at
the start of its display name. The prefix moved from ``[VCF Content Factory] ``
to ``[VCF CF] `` on 2026-11-12: the Operations dashboard editor caps names at
50 characters and the old prefix spent 22 of them.

This is a hard cut. A name that still carries ``LEGACY_FACTORY_PREFIX`` is a
load error that points at ``MIGRATE_COMMAND``; there is no period in which
both are accepted, because by-name cross-references would split across the
two spellings.

Not covered here, and unchanged by the move:

- management pack display names, which use the prose form
  ``VCF Content Factory <name>`` with no brackets;
- the dashboard folder (``name_path``), ``VCF Content Factory``;
- vendor strings, repo names, the ``vcfcf_`` adapter-kind prefix.

Ids that the renderers derive from a display name (alert and fallback
symptom ids in AlertContent.xml and pak content, recommendation keys) are
computed from :func:`id_basis_name`, which maps the current prefix back to the
legacy one, so the rename does not change any derived id: an installed
object keyed by such an id is updated in place, not duplicated.

The bundled sdk-buildkit ships this module as ``naming.py``
(``vcfcf_managementpacks/buildkit.py``), so it imports nothing.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

#: Current prefix, with its trailing space. Factory content names start with it.
FACTORY_PREFIX = "[VCF CF] "

#: The bracketed label alone (``[VCF CF]``), for messages and near-miss checks.
FACTORY_PREFIX_LABEL = FACTORY_PREFIX.rstrip()

#: Retired prefix (until 2026-11-12). A load error wherever it appears in a name.
LEGACY_FACTORY_PREFIX = "[VCF Content Factory] "

#: The retired bracketed label alone (``[VCF Content Factory]``).
LEGACY_FACTORY_PREFIX_LABEL = LEGACY_FACTORY_PREFIX.rstrip()

#: The command that rewrites the legacy prefix in a checkout.
MIGRATE_COMMAND = "python3 -m vcfcf_common migrate-prefix"

#: The command that removes legacy-named leftovers from an instance.
CLEANUP_COMMAND = "python3 -m vcfcf_common cleanup-legacy-prefix"

# Whitespace runs between the words: prose in a folded YAML block can wrap the
# label across lines ("[VCF Content\n  Factory] ..."), and it parses joined.
_LEGACY_TOKEN_RE = re.compile(r"\[VCF\s+Content\s+Factory\](?!\()")
_FACTORY_LEAD_RE = re.compile(r"^" + re.escape(FACTORY_PREFIX_LABEL) + r"\s*")
_LEGACY_LEAD_RE = re.compile(r"^" + re.escape(LEGACY_FACTORY_PREFIX_LABEL) + r"\s*")


def has_factory_prefix(name: str) -> bool:
    """True when *name* starts with the current prefix (trailing space included)."""
    return isinstance(name, str) and name.startswith(FACTORY_PREFIX)


def has_legacy_prefix(name: str) -> bool:
    """True when *name* starts with the retired bracketed label (space or not)."""
    return isinstance(name, str) and name.startswith(LEGACY_FACTORY_PREFIX_LABEL)


def is_factory_name(name: str) -> bool:
    """True for a name in either spelling of the factory prefix.

    For cross-reference checks: a reference in the legacy spelling must be
    checked (and fail) rather than pass as a built-in.
    """
    return has_factory_prefix(name) or has_legacy_prefix(name)


def strip_factory_prefix(name: str) -> str:
    """*name* without a leading factory prefix in either spelling."""
    return _LEGACY_LEAD_RE.sub("", _FACTORY_LEAD_RE.sub("", name, count=1), count=1)


def legacy_name(name: str) -> Optional[str]:
    """The legacy spelling of a current factory name, or None if not prefixed.

    ``"[VCF CF] X"`` -> ``"[VCF Content Factory] X"``. Used to find the
    objects a rename left behind on an instance.
    """
    if not has_factory_prefix(name):
        return None
    return LEGACY_FACTORY_PREFIX + name[len(FACTORY_PREFIX):]


def id_basis_name(name: str) -> str:
    """The name an id is derived from: the legacy spelling for a factory name.

    Keeps name-derived ids (``AlertDefinition-<kind>-<slug>``) identical
    across the prefix move. Any other name is returned unchanged.
    """
    return legacy_name(name) or name


def rewrite_legacy_prefix(text: str) -> Tuple[str, int]:
    """Replace every bracketed legacy label in *text* with the current one.

    Returns ``(new_text, count)``. The label followed by ``(`` is a Markdown
    link (``[VCF Content Factory](https://...)``), not a name, and is kept.
    A label wrapped across lines (whitespace runs between its words) is
    matched too and rewritten onto one line. Idempotent: the current label
    does not contain the legacy one.
    """
    return _LEGACY_TOKEN_RE.subn(FACTORY_PREFIX_LABEL, text)


def legacy_reference_hint(name: str) -> str:
    """A sentence to append to an unresolved-reference error, or ``""``.

    Non-empty only when the referenced *name* carries the legacy prefix, so
    the error says why the reference no longer resolves.
    """
    if not has_legacy_prefix(name):
        return ""
    return (
        f" The reference carries the retired prefix "
        f'"{LEGACY_FACTORY_PREFIX_LABEL}"; run `{MIGRATE_COMMAND}`.'
    )


def framework_prefix_problem(name: str, src: str) -> Optional[str]:
    """The load-error message for a factory name, or None when it is fine.

    *src* names the file (or the object when there is no file). A legacy
    name gets the migration instruction; any other unprefixed name gets the
    missing-prefix message.
    """
    if has_factory_prefix(name):
        return None
    if has_legacy_prefix(name):
        return (
            f'{src}: name "{name}" carries the retired prefix '
            f'"{LEGACY_FACTORY_PREFIX_LABEL}"; factory content now uses '
            f'"{FACTORY_PREFIX_LABEL}". Run `{MIGRATE_COMMAND}` from the repo '
            f"root to rename this content and every by-name reference to it "
            f"(knowledge/context/authoring/prefix_migration.md)."
        )
    return (
        f'{src}: name "{name}" missing framework prefix '
        f'"{FACTORY_PREFIX_LABEL}". All factory-authored content must carry the literal '
        f'"{FACTORY_PREFIX_LABEL}" prefix (see CLAUDE.md §Hard rules #5). For third-party '
        f"bundle content, ensure the bundle manifest sets factory_native: false."
    )


__all__ = [
    "CLEANUP_COMMAND",
    "FACTORY_PREFIX",
    "FACTORY_PREFIX_LABEL",
    "LEGACY_FACTORY_PREFIX",
    "LEGACY_FACTORY_PREFIX_LABEL",
    "MIGRATE_COMMAND",
    "framework_prefix_problem",
    "has_factory_prefix",
    "has_legacy_prefix",
    "id_basis_name",
    "is_factory_name",
    "legacy_name",
    "legacy_reference_hint",
    "rewrite_legacy_prefix",
    "strip_factory_prefix",
]
