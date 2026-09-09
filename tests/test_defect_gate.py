"""Tests for vcfops_packaging.defects (RULE-012 defect registry + gate).

Design principle (2026-07-06 rework)
-------------------------------------
Every *behavior* assertion (parsing, gating logic, exit codes, open-blocks,
closed-passes, gate-all semantics) runs against a small **fixture** registry
built inline or in a ``tmp_path`` file for that test case.  Fixture registries
never change, so these tests are stable regardless of what happens to any
real defect in ``knowledge/context/defects.md`` — a defect graduating from open to
closed (the registry doing its job) must never turn a green CI red.

Against the **live** ``knowledge/context/defects.md`` we only assert *structural*
invariants that must hold no matter which defects are currently open or
closed: the file parses without error; every entry carries the required
fields; every ``Status: closed`` entry carries a non-empty
``Closing-evidence``; severities/statuses are drawn from the allowed
vocabulary; and ids are unique with no gaps in the numbering. We do NOT
assert which specific DEF ids exist or what their open/closed state is —
see ``knowledge/lessons/`` for why pinning tests to mutable registry data is a test
design defect.

Coverage map (old behavior -> new fixture test)
------------------------------------------------
  Parser happy path (multi-entry, all fields captured)
      -> TestParserFixture.test_parses_multi_entry_registry
  Malformed entries (bad severity / waived / closed-without-evidence /
  duplicate id / missing field / unknown status)
      -> TestMalformedEntries (already fixture-based; unchanged)
  gate_pak: blocked / clean / unaffected pak
      -> TestGatePak (rewritten onto a fixture registry)
  gate_item: blocked / tracked-not-blocked / unaffected item
      -> TestGateItem (already fixture-based; unchanged)
  gate_all: open blockers returned, closed excluded, empty registry
      -> TestGateAll (rewritten onto a fixture registry + existing
         test_gate_all_empty_registry)
  CLI defect-gate (--pak / --all / <type> <name> / malformed / missing)
      -> TestCLIDefectGate (rewritten: REGISTRY_PATH monkeypatched to a
         fixture registry for every case)
  cmd_release refusal for an open blocking defect
      -> TestReleaseRefusal (rewritten: REGISTRY_PATH monkeypatched to a
         fixture registry instead of relying on a live DEF id)
  _gate_publish: raises for open blocker / passes for closed-or-tracked /
  malformed raises / vacuous pass when registry absent / fires on a
  fixture repo's own registry
      -> TestGatePublish (already mostly fixture-based; the remaining
         REPO_ROOT-coupled cases are rewritten onto tmp_path fixtures)
  Standalone entrypoint (--pak / --all / missing registry / bare-copy
  curl-and-run proof)
      -> TestStandaloneEntrypoint (rewritten: fixture registries written
         to tmp_path rather than copying/reading the live registry
         content; the bare-copy proof still copies the real defects.py
         script — only the *registry* is now synthetic)
  Real-registry structural contract
      -> TestRealRegistryStructural (new: format/shape invariants only)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repo root and real registry path
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
REAL_REGISTRY = REPO_ROOT / "knowledge" / "context" / "defects.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_registry(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "defects.md"
    p.write_text(content, encoding="utf-8")
    return p


# A small, self-contained fixture registry used across the fixture-based
# gate/CLI/publish tests below.  Two open blocking defects (against two
# different paks), one closed defect (with evidence), and one tracked
# (non-blocking) defect.
_FIXTURE_REGISTRY_TEXT = """\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture pak alpha has an open blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** fixture-pak-alpha
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Open blocking defect used to prove the gate fires.

### DEF-002

- **Title:** Fixture pak beta has an open blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** fixture-pak-beta
- **First-seen:** build 2 (2026-01-02)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Second open blocking defect, different pak.

### DEF-003

- **Title:** Fixture pak gamma had a defect, now closed
- **Severity:** blocking
- **Status:** closed
- **Affects:** fixture-pak-gamma
- **First-seen:** build 3 (2026-01-03)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Closed defect; must never appear as a blocker.
- **Closing-evidence:** Fixture proof — closed for this test suite.

### DEF-004

- **Title:** Fixture pak delta has a tracked (non-blocking) issue
- **Severity:** tracked
- **Status:** open
- **Affects:** fixture-pak-delta
- **First-seen:** build 4 (2026-01-04)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Tracked severity must never gate a release.
"""


def _fixture_registry(tmp_path: Path) -> Path:
    return _write_registry(tmp_path, _FIXTURE_REGISTRY_TEXT)


# ---------------------------------------------------------------------------
# Parser happy path (fixture)
# ---------------------------------------------------------------------------

class TestParserFixture:
    """Happy-path parsing against a synthetic multi-entry registry."""

    def test_parses_multi_entry_registry(self, tmp_path):
        from vcfops_packaging.defects import load_registry
        reg = _fixture_registry(tmp_path)
        entries = load_registry(reg)
        ids = [e.id for e in entries]
        assert ids == ["DEF-001", "DEF-002", "DEF-003", "DEF-004"]

        by_id = {e.id: e for e in entries}
        assert by_id["DEF-001"].severity == "blocking"
        assert by_id["DEF-001"].status == "open"
        assert by_id["DEF-001"].affects == "fixture-pak-alpha"
        assert by_id["DEF-001"].title

        assert by_id["DEF-002"].affects == "fixture-pak-beta"

        assert by_id["DEF-003"].status == "closed"
        assert by_id["DEF-003"].closing_evidence.strip()

        assert by_id["DEF-004"].severity == "tracked"


# ---------------------------------------------------------------------------
# Real registry: structural invariants only (no assertions about which
# specific defects exist or their open/closed state — see module docstring).
# ---------------------------------------------------------------------------

class TestRealRegistryStructural:
    """Format/shape contract that knowledge/context/defects.md must satisfy regardless
    of which defects are currently filed or their status."""

    _ALLOWED_SEVERITIES = {"blocking", "tracked"}
    _ALLOWED_STATUSES = {"open", "closed"}

    def test_registry_exists(self):
        assert REAL_REGISTRY.exists(), (
            f"knowledge/context/defects.md not found at {REAL_REGISTRY}"
        )

    def test_parses_without_error(self):
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        assert isinstance(entries, list)

    def test_no_entry_parse_errors(self):
        """Per-entry isolation must not let real rot go unnoticed.

        Since a malformed entry no longer raises, "it parsed" is no longer
        proof the file is clean: the errors list is. This is the assertion
        that keeps the live registry honest.
        """
        from vcfops_packaging.defects import parse_registry
        registry = parse_registry(REAL_REGISTRY)
        assert registry.errors == [], (
            "knowledge/context/defects.md has malformed entries: "
            + "; ".join(str(e) for e in registry.errors)
        )

    def test_no_synthetic_entries_in_a_clean_registry(self):
        from vcfops_packaging.defects import load_registry
        assert not [e for e in load_registry(REAL_REGISTRY) if e.synthetic]

    def test_every_entry_has_required_fields(self):
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        assert entries, "registry must have at least one entry"
        for e in entries:
            assert e.id, "entry missing id"
            assert e.title.strip(), f"{e.id}: empty title"
            assert e.affects.strip(), f"{e.id}: empty affects"
            assert e.first_seen.strip(), f"{e.id}: empty first-seen"
            assert e.source.strip(), f"{e.id}: empty source"
            assert e.summary.strip(), f"{e.id}: empty summary"

    def test_every_closed_entry_has_closing_evidence(self):
        """The registry's own format contract (see header table in
        knowledge/context/defects.md): Status: closed requires Closing-evidence.
        The loader also enforces this at parse time, so this test is a
        second, explicit assertion of the same invariant on live data.
        """
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        for e in entries:
            if e.status == "closed":
                assert e.closing_evidence.strip(), (
                    f"{e.id} is closed but has no Closing-evidence"
                )

    def test_severities_and_statuses_are_from_allowed_vocabulary(self):
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        for e in entries:
            assert e.severity in self._ALLOWED_SEVERITIES, (
                f"{e.id}: unexpected severity {e.severity!r}"
            )
            assert e.status in self._ALLOWED_STATUSES, (
                f"{e.id}: unexpected status {e.status!r}"
            )

    def test_ids_unique_and_sequential(self):
        """Ids are unique (guaranteed by the loader) and numbered
        contiguously from DEF-001 with no gaps — the registry's own
        sequential-numbering discipline, not a statement about which
        defects exist."""
        from vcfops_packaging.defects import load_registry
        entries = load_registry(REAL_REGISTRY)
        ids = [e.id for e in entries]
        assert len(ids) == len(set(ids)), f"duplicate ids found: {ids}"

        numbers = sorted(int(i.split("-")[1]) for i in ids)
        assert numbers == list(range(1, len(numbers) + 1)), (
            f"defect ids must be sequential starting at DEF-001 with no "
            f"gaps; got numbers: {numbers}"
        )


# ---------------------------------------------------------------------------
# Malformed entry rejections: per-entry fault isolation
#
# A malformed entry no longer raises out of the whole file (that was the
# reported bug: one sloppy edit broke the gate for every artifact everywhere).
# It is recorded as a ParseError and, when its Affects: token is readable,
# fails CLOSED for exactly that scope as a synthetic open blocking defect.
# See knowledge/designs/defect-isolation-v1.md.
# ---------------------------------------------------------------------------

def _one_error(reg) -> object:
    """Parse a fixture registry expected to hold exactly one bad entry."""
    from vcfops_packaging.defects import parse_registry
    registry = parse_registry(reg)
    assert len(registry.errors) == 1, (
        f"expected exactly one parse error; got {[str(e) for e in registry.errors]}"
    )
    return registry.errors[0]


class TestMalformedEntries:
    """Each fixture is recorded as a parse error, never raised for the file."""

    def test_bad_severity(self, tmp_path):
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Some defect
- **Severity:** critical
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Test defect with bad severity.
""")
        err = _one_error(reg)
        assert "invalid Severity" in err.reason
        assert err.affects == "synology"

    def test_waived_status_explicitly_rejected(self, tmp_path):
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Some defect
- **Severity:** blocking
- **Status:** waived
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Test defect with waived status.
""")
        err = _one_error(reg)
        assert "waived" in err.reason

    def test_closed_without_evidence(self, tmp_path):
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Closed without evidence
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** This entry is closed but has no Closing-evidence.
""")
        err = _one_error(reg)
        assert "Closing-evidence" in err.reason

    def test_duplicate_ids(self, tmp_path):
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** First entry
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** First.

### DEF-001

- **Title:** Duplicate id
- **Severity:** tracked
- **Status:** open
- **Affects:** unifi
- **First-seen:** build 2 (2026-01-02)
- **Source:** knowledge/context/reviews/<synthetic-fixture-2>.md
- **Summary:** Duplicate id, must be rejected.
""")
        err = _one_error(reg)
        assert "duplicate" in err.reason

    def test_missing_required_field_title(self, tmp_path):
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Missing Title field.
""")
        err = _one_error(reg)
        assert "Title" in err.reason
        # Affects is still readable, so the broken entry still gates synology.
        assert err.affects == "synology"

    def test_unknown_status(self, tmp_path):
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Bad status
- **Severity:** blocking
- **Status:** pending
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Unknown status.
""")
        err = _one_error(reg)
        assert "invalid Status" in err.reason


class TestPerEntryFaultIsolation:
    """The reported bug: one bad entry must not gate unrelated artifacts."""

    _MIXED = """\
# Defect registry

## Defects

### DEF-001

- **Title:** Broken entry for pak X
- **Severity:** critical
- **Status:** open
- **Affects:** fixture-pak-x
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Severity is not a legal value, so this entry cannot be parsed.

### DEF-002

- **Title:** Healthy tracked entry for pak Y
- **Severity:** tracked
- **Status:** open
- **Affects:** fixture-pak-y
- **First-seen:** build 2 (2026-01-02)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Nothing wrong with this one.
"""

    def test_malformed_entry_for_x_does_not_block_y(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _write_registry(tmp_path, self._MIXED)
        assert gate_pak("fixture-pak-y", reg) == [], (
            "a malformed entry naming pak X must not gate pak Y"
        )

    def test_malformed_entry_with_readable_affects_blocks_that_scope(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _write_registry(tmp_path, self._MIXED)
        blockers = gate_pak("fixture-pak-x", reg)
        assert len(blockers) == 1, (
            f"the broken entry must fail closed for its own scope; got {blockers}"
        )
        assert blockers[0].synthetic is True
        assert blockers[0].severity == "blocking"
        assert blockers[0].status == "open"
        assert "malformed" in blockers[0].title

    def test_unreadable_affects_blocks_nothing_but_is_reported(self, tmp_path, capsys):
        from vcfops_packaging.defects import gate_all, parse_registry
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** No scope at all
- **Severity:** blocking
- **Status:** open
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Affects is missing entirely, so this entry names no artifact.
""")
        registry = parse_registry(reg)
        assert len(registry.unscoped_errors) == 1
        assert gate_all(reg) == [], (
            "an entry whose scope cannot be read must block nothing"
        )
        combined = capsys.readouterr()
        text = combined.out + combined.err
        assert "WARNING" in text and "DEF-001" in text, (
            f"an unscoped parse error must still surface loudly; got:\n{text}"
        )

    def test_prose_affects_is_not_a_readable_scope(self, tmp_path):
        """Affects: is exactly one token. A sentence names no artifact."""
        from vcfops_packaging.defects import parse_registry
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Prose scope
- **Severity:** blocking
- **Status:** pending
- **Affects:** all of the dashboards, probably
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** The Affects field is prose, not a token.
""")
        registry = parse_registry(reg)
        assert len(registry.unscoped_errors) == 1

    def test_gate_all_reports_every_parse_error(self, tmp_path, capsys):
        from vcfops_packaging.defects import gate_all
        reg = _write_registry(tmp_path, self._MIXED + """
### DEF-003

- **Title:** Second broken entry
- **Severity:** blocking
- **Status:** sideways
- **Affects:** fixture-pak-z
- **First-seen:** build 3 (2026-01-03)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Status is not a legal value either.
""")
        gate_all(reg)
        text = capsys.readouterr().err
        assert "DEF-001" in text and "DEF-003" in text, (
            f"every parse error must be surfaced; got:\n{text}"
        )


class TestMalformedHeadingIsolation:
    """A DEF-prefixed heading that is not a valid id must not repoint a good entry.

    Regression for framework review W3 (defects-doctor-2026-09-09): a heading
    such as ``### DEF-1O2`` (letter O for zero) matched neither the section
    regex nor the field regex, so it fell through to the continuation-line
    branch and the FOLLOWING entry's field lines overwrote the PREVIOUS
    entry's fields.  DEF-001 silently began gating pakB instead of pakA, with
    no error, no warning and no synthetic blocker: fail-open registry
    corruption.
    """

    # The reviewer's own repro, verbatim in shape.
    _TYPO_HEADING = """\
# Defect registry

## Defects

### DEF-001

- **Title:** Good entry
- **Severity:** blocking
- **Status:** open
- **Affects:** pakA
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** never gates anything.

### DEF-1O2

- **Title:** Typo'd id, letter O for zero
- **Severity:** blocking
- **Status:** open
- **Affects:** pakB
- **First-seen:** build 2 (2026-01-02)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** second entry.
"""

    def test_typod_heading_does_not_overwrite_previous_entry(self, tmp_path):
        """The corruption repro: DEF-001 must keep its own fields."""
        from vcfops_packaging.defects import parse_registry
        reg = _write_registry(tmp_path, self._TYPO_HEADING)
        registry = parse_registry(reg)

        valid = {e.id: e for e in registry.entries}
        assert "DEF-001" in valid, (
            f"the good entry must still parse; got {sorted(valid)}"
        )
        assert valid["DEF-001"].affects == "pakA", (
            "DEF-001 must still gate the artifact it names, not the typo'd "
            f"entry's scope; got {valid['DEF-001'].affects!r}"
        )
        assert valid["DEF-001"].summary == "never gates anything.", (
            f"DEF-001's fields were overwritten: {valid['DEF-001'].summary!r}"
        )
        assert len(registry.errors) == 1, (
            f"the typo'd heading must be a ParseError; got {registry.errors}"
        )

    def test_typod_heading_gates_its_own_scope_and_nothing_else(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _write_registry(tmp_path, self._TYPO_HEADING)

        assert [e.id for e in gate_pak("pakA", reg)] == ["DEF-001"], (
            "the good entry must still gate its own scope"
        )
        blockers = gate_pak("pakB", reg)
        assert len(blockers) == 1, (
            f"the typo'd entry must fail closed for its readable scope; got {blockers}"
        )
        assert blockers[0].synthetic is True
        assert blockers[0].severity == "blocking"
        assert blockers[0].status == "open"
        assert gate_pak("pakC", reg) == [], (
            "a malformed heading must not gate an unrelated artifact"
        )

    def test_typod_heading_without_readable_affects_blocks_nothing(self, tmp_path, capsys):
        from vcfops_packaging.defects import gate_all, parse_registry, reset_warning_state
        reset_warning_state()
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Good entry
- **Severity:** blocking
- **Status:** closed
- **Affects:** pakA
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** closed, so it gates nothing.
- **Closing-evidence:** fixed in build 2.

### DEF-1O2 and then some trailing prose

- **Title:** Typo'd id with no readable scope
- **Severity:** blocking
- **Status:** open
- **Affects:** all of the dashboards, probably
- **First-seen:** build 2 (2026-01-02)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Affects is prose, so this names no artifact.
""")
        registry = parse_registry(reg)
        assert len(registry.unscoped_errors) == 1, (
            f"an unreadable scope must be unscoped; got {registry.errors}"
        )
        assert gate_all(reg) == [], (
            "a malformed heading with no readable scope must block nothing"
        )
        combined = capsys.readouterr()
        text = combined.out + combined.err
        assert "WARNING" in text and "DEF-1O2" in text, (
            f"it must still be reported loudly; got:\n{text}"
        )

    # One well-formed entry, reused by the heading-shape cases below.
    _GOOD_ENTRY = """\
### DEF-001

- **Title:** Good entry
- **Severity:** blocking
- **Status:** open
- **Affects:** pakA
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Still parses cleanly.
"""

    def test_non_def_headings_and_prose_are_unaffected(self, tmp_path):
        """Section headings and prose must keep their current no-op behaviour."""
        from vcfops_packaging.defects import parse_registry
        reg = _write_registry(tmp_path, """\
# Defect registry

## How it works

Some prose about the registry.

## Schema

### Fields

More prose, and a heading that is not DEF-prefixed.

## Defects

""" + self._GOOD_ENTRY)
        registry = parse_registry(reg)
        assert registry.errors == [], (
            f"non-DEF headings must not become parse errors; got {registry.errors}"
        )
        assert [e.id for e in registry.entries] == ["DEF-001"]
        assert registry.entries[0].affects == "pakA"

    def test_lowercase_def_prose_heading_never_matches(self, tmp_path):
        """`## Defects` is prose. The match is case-sensitive; assert that.

        The suppression here is LEXICAL: a lowercase heading is not
        DEF-prefixed at all, so it is skipped before the malformed-heading
        branch is ever reached.  Stated explicitly because the previous
        version of this test relied on it without saying so.
        """
        from vcfops_packaging.defects import _BAD_SECTION_RE, parse_registry
        assert _BAD_SECTION_RE.match("## Defects") is None
        assert _BAD_SECTION_RE.match("### Definitions") is None
        assert _BAD_SECTION_RE.match("## Schema") is None

        reg = _write_registry(
            tmp_path,
            "# Defect registry\n\n## Defects\n\n" + self._GOOD_ENTRY,
        )
        registry = parse_registry(reg)
        assert registry.errors == []
        assert [e.id for e in registry.entries] == ["DEF-001"]

    def test_uppercase_def_prose_heading_matches_but_is_silent(self, tmp_path):
        """`### DEFECTS` IS DEF-prefixed, and is silenced evidentially, not lexically.

        The regex deliberately anchors on bare ``DEF`` rather than ``DEF-``,
        because requiring the hyphen would let ``### DEF102`` fall through to
        the continuation branch and reproduce the field-bleed.  The cost of
        the wider anchor is paid at report time instead: a section that
        collected no field lines has nothing that could have bled into the
        previous entry, so it says nothing.  This matters for the
        ``defects.local.md`` a stranger writes from scratch, where
        ``### DEFECTS`` is a natural first-draft heading.
        """
        from vcfops_packaging.defects import _BAD_SECTION_RE, parse_registry
        for heading in ("### DEFECTS", "### DEFECT LOG", "### DEFINITIONS"):
            assert _BAD_SECTION_RE.match(heading) is not None, (
                f"{heading!r} is DEF-prefixed and must match the regex"
            )

        for heading in ("### DEFECTS", "### DEFECT LOG", "### DEFINITIONS"):
            reg = _write_registry(tmp_path, (
                "# Defect registry\n\n"
                + self._GOOD_ENTRY
                + f"\n{heading}\n\nSome prose about defects.\n"
            ))
            registry = parse_registry(reg)
            assert registry.errors == [], (
                f"{heading!r} carries no field lines and must be silent; "
                f"got {[str(e) for e in registry.errors]}"
            )
            assert [e.id for e in registry.entries] == ["DEF-001"]
            assert registry.entries[0].affects == "pakA"

    def test_uppercase_def_heading_with_fields_is_a_scoped_error(self, tmp_path):
        """The other half of the split: same heading shape, but it has fields.

        ``### DEF102`` (missing hyphen, same keystroke class as the letter-O
        typo) followed by real field lines is exactly the corrupting case, so
        it must be a scoped, fail-closed ParseError.
        """
        from vcfops_packaging.defects import gate_pak, parse_registry
        reg = _write_registry(tmp_path, (
            "# Defect registry\n\n"
            + self._GOOD_ENTRY
            + """
### DEF102

- **Title:** Missing hyphen
- **Severity:** blocking
- **Status:** open
- **Affects:** pakB
- **First-seen:** build 2 (2026-01-02)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** second entry.
"""
        ))
        registry = parse_registry(reg)
        assert len(registry.errors) == 1, (
            f"a DEF-prefixed heading WITH field lines must be reported; "
            f"got {[str(e) for e in registry.errors]}"
        )
        assert registry.errors[0].scoped is True
        assert registry.errors[0].affects == "pakB"
        assert registry.entries[0].affects == "pakA", (
            "and the previous entry must be untouched"
        )
        assert [e.id for e in gate_pak("pakB", reg)] == ["DEF102"]

    def test_prose_shaped_heading_still_terminates_the_previous_entry(self, tmp_path):
        """Termination is unconditional; only REPORTING is conditional.

        A heading that reads as prose (``### DEFECTS``) but is followed by
        field lines is the case where the two conditions disagree.  It must
        still terminate DEF-001 (that is the property that removes the
        corruption) and, because it did collect field lines, it must also be
        reported and gate the scope it names.
        """
        from vcfops_packaging.defects import parse_registry
        reg = _write_registry(tmp_path, (
            "# Defect registry\n\n"
            + self._GOOD_ENTRY
            + """
### DEFECTS

- **Affects:** pakB
- **Summary:** these lines must not bleed upward into DEF-001.
"""
        ))
        registry = parse_registry(reg)
        good = [e for e in registry.entries if e.id == "DEF-001"]
        assert len(good) == 1
        assert good[0].affects == "pakA", (
            f"DEF-001 was repointed by a silent heading; got {good[0].affects!r}"
        )
        assert good[0].summary == "Still parses cleanly.", (
            f"DEF-001's fields were overwritten; got {good[0].summary!r}"
        )
        assert len(registry.errors) == 1, (
            "field lines were collected, so this heading is NOT the silent case"
        )
        assert registry.errors[0].affects == "pakB"

    def test_valid_registry_is_unaffected(self, tmp_path):
        """The clean case must parse byte-identically to before the fix."""
        from vcfops_packaging.defects import parse_registry
        reg = _write_registry(tmp_path, _FIXTURE_REGISTRY_TEXT)
        registry = parse_registry(reg)
        assert registry.errors == []
        assert len(registry.entries) == len(registry.gate_entries)


class TestRegistryResolution:
    """Selection by presence: defects.local.md wins, explicit path wins over both."""

    def _local_and_shipped(self, tmp_path):
        shipped = _write_registry(tmp_path, _FIXTURE_REGISTRY_TEXT)
        local = tmp_path / "defects.local.md"
        local.write_text("""\
# Local defect registry

## Defects

### DEF-001

- **Title:** Local-only blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** local-only-pak
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Only present in the consumer's own registry.
""", encoding="utf-8")
        return shipped, local

    def test_local_registry_wins_when_present(self, tmp_path, monkeypatch):
        from vcfops_packaging import defects as _defects_mod
        shipped, local = self._local_and_shipped(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", shipped)
        assert _defects_mod.resolve_registry_path() == local
        # The shipped registry's blockers are invisible; the local one's fire.
        assert _defects_mod.gate_pak("fixture-pak-alpha") == []
        assert [e.id for e in _defects_mod.gate_pak("local-only-pak")] == ["DEF-001"]

    def test_falls_back_to_shipped_registry_when_absent(self, tmp_path, monkeypatch):
        from vcfops_packaging import defects as _defects_mod
        shipped = _write_registry(tmp_path, _FIXTURE_REGISTRY_TEXT)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", shipped)
        assert _defects_mod.resolve_registry_path() == shipped
        assert [e.id for e in _defects_mod.gate_pak("fixture-pak-alpha")] == ["DEF-001"]

    def test_explicit_path_beats_both(self, tmp_path, monkeypatch):
        from vcfops_packaging import defects as _defects_mod
        shipped, local = self._local_and_shipped(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", shipped)
        # An explicit path is honoured verbatim, even though a local
        # registry sits right beside it.
        assert _defects_mod.resolve_registry_path(shipped) == shipped
        assert [e.id for e in _defects_mod.gate_pak("fixture-pak-alpha", shipped)] == ["DEF-001"]
        assert _defects_mod.gate_pak("local-only-pak", shipped) == []


class TestAbsentRegistryWarnsAndPasses:
    """RULE-012 gate has nothing to check, so it must not refuse."""

    def test_gate_pak_warns_and_passes(self, tmp_path, capsys):
        from vcfops_packaging.defects import gate_pak
        missing = tmp_path / "no_such_dir" / "defects.md"
        assert gate_pak("anything", missing) == []
        err = capsys.readouterr().err
        assert "WARNING" in err, f"absent registry must WARN; got:\n{err}"
        assert "RULE-012" in err, f"WARNING must name RULE-012; got:\n{err}"


# ---------------------------------------------------------------------------
# Gate helper exit codes (fixture registry)
# ---------------------------------------------------------------------------

class TestGatePak:
    """gate_pak() against a fixture registry."""

    def test_open_blocking_pak_is_blocked(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-alpha", reg)
        ids = [b.id for b in blockers]
        assert ids == ["DEF-001"]

    def test_second_open_blocking_pak_is_blocked(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-beta", reg)
        ids = [b.id for b in blockers]
        assert ids == ["DEF-002"]

    def test_closed_defect_does_not_gate_its_pak(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-gamma", reg)
        assert blockers == [], (
            f"closed DEF-003 must not block fixture-pak-gamma; got: "
            f"{[b.id for b in blockers]}"
        )

    def test_tracked_defect_does_not_gate_its_pak(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("fixture-pak-delta", reg)
        assert blockers == [], (
            f"tracked severity must not block; got: {[b.id for b in blockers]}"
        )

    def test_unregistered_pak_is_clean(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        reg = _fixture_registry(tmp_path)
        blockers = gate_pak("nonexistent-pak", reg)
        assert blockers == [], (
            f"Unknown pak must return empty list; got: {[b.id for b in blockers]}"
        )


class TestGateItem:
    """gate_item() with a fixture registry."""

    _REGISTRY_TEXT = """\
# Defect registry

## Defects

### DEF-001

- **Title:** Dashboard has rendering bug
- **Severity:** blocking
- **Status:** open
- **Affects:** dashboard/my_dashboard
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Blocking dashboard defect.

### DEF-002

- **Title:** Tracked view issue
- **Severity:** tracked
- **Status:** open
- **Affects:** view/my_view
- **First-seen:** build 2 (2026-01-02)
- **Source:** knowledge/context/reviews/<synthetic-fixture-2>.md
- **Summary:** Non-blocking tracked issue — must not gate.
"""

    def test_blocked_item(self, tmp_path):
        from vcfops_packaging.defects import gate_item
        reg = _write_registry(tmp_path, self._REGISTRY_TEXT)
        blockers = gate_item("dashboard", "my_dashboard", reg)
        assert len(blockers) == 1
        assert blockers[0].id == "DEF-001"

    def test_tracked_item_not_blocked(self, tmp_path):
        from vcfops_packaging.defects import gate_item
        reg = _write_registry(tmp_path, self._REGISTRY_TEXT)
        blockers = gate_item("view", "my_view", reg)
        assert blockers == [], (
            "tracked severity must not block; got: "
            + str([b.id for b in blockers])
        )

    def test_unaffected_item_clean(self, tmp_path):
        from vcfops_packaging.defects import gate_item
        reg = _write_registry(tmp_path, self._REGISTRY_TEXT)
        blockers = gate_item("dashboard", "other_dashboard", reg)
        assert blockers == []


class TestGateAll:
    """gate_all() returns every open blocking defect (fixture registry)."""

    def test_gate_all_returns_open_blockers_only(self, tmp_path):
        from vcfops_packaging.defects import gate_all
        reg = _fixture_registry(tmp_path)
        blockers = gate_all(reg)
        ids = sorted(b.id for b in blockers)
        assert ids == ["DEF-001", "DEF-002"], (
            f"expected exactly the two open blocking defects; got: {ids}"
        )

    def test_gate_all_empty_registry(self, tmp_path):
        from vcfops_packaging.defects import gate_all
        reg = _write_registry(tmp_path, "# No entries\n")
        assert gate_all(reg) == []


# ---------------------------------------------------------------------------
# CLI exit codes via build_parser + cmd_defect_gate (fixture registry via
# REGISTRY_PATH monkeypatch)
# ---------------------------------------------------------------------------

class TestCLIDefectGate:
    """Integration tests for the defect-gate subcommand via the CLI layer.

    REGISTRY_PATH is monkeypatched to a fixture registry for every case so
    these tests are independent of the live corpus's current defect states.
    """

    def _run(self, argv: list[str]) -> int:
        from vcfops_packaging.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(argv)
        return args.func(args)

    def test_pak_clean_exits_0(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--pak", "fixture-pak-gamma"])
        assert rc == 0, f"Expected exit 0 for a clean pak; got {rc}"
        out = capsys.readouterr().out
        assert "fixture-pak-gamma" in out

    def test_pak_blocked_exits_2(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--pak", "fixture-pak-alpha"])
        assert rc == 2, f"Expected exit 2 for a blocked pak; got {rc}"
        out = capsys.readouterr().out
        assert "DEF-001" in out

    def test_pak_tracked_only_exits_0(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--pak", "fixture-pak-delta"])
        assert rc == 0, f"tracked severity must not gate; got {rc}"

    def test_all_exits_2_and_lists_open_blockers_only(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "--all"])
        assert rc == 2, f"Expected exit 2 (two open blockers); got {rc}"
        out = capsys.readouterr().out
        assert "DEF-001" in out
        assert "DEF-002" in out
        assert "DEF-003" not in out, "closed defect must not be listed"

    def test_malformed_entry_blocks_its_own_scope_exits_2(self, tmp_path, monkeypatch, capsys):
        """A malformed entry fails CLOSED for the scope it names: exit 2.

        This used to be exit 1 for EVERY artifact, which is the bug
        knowledge/designs/defect-isolation-v1.md was written to remove. The
        entry below names synology and cannot be parsed, so synology is
        refused (and the reason says "malformed"), while every other
        artifact gates normally.
        """
        from vcfops_packaging import defects as _defects_mod
        bad_reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** No evidence
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Closed without evidence — malformed.
""")
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", bad_reg)
        rc = self._run(["defect-gate", "--pak", "synology"])
        assert rc == 2, f"Expected exit 2 (scope blocked); got {rc}"
        captured = capsys.readouterr()
        combined = (captured.out + captured.err).lower()
        assert "malformed" in combined, combined
        # An unrelated pak in the same file still gates cleanly.
        rc_other = self._run(["defect-gate", "--pak", "unifi"])
        assert rc_other == 0, (
            f"a malformed entry naming synology must not block unifi; got {rc_other}"
        )

    def test_missing_registry_warns_and_passes(self, tmp_path, monkeypatch, capsys):
        """An absent registry warns and passes; it never refuses.

        A registry that is not there has nothing to say about this artifact.
        Refusing over its absence is the fail-closed coupling that broke
        third-party releases (defect-isolation-v1, leak 3), and it already
        was the publish path's behaviour: the CLI was the outlier.
        """
        from vcfops_packaging import defects as _defects_mod
        missing = tmp_path / "does_not_exist" / "defects.md"
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", missing)
        rc = self._run(["defect-gate", "--pak", "synology"])
        assert rc == 0, (
            f"Missing registry must warn and pass; got {rc}"
        )
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "WARNING" in combined, combined
        assert "RULE-012" in combined, combined

    def test_content_item_gate(self, tmp_path, monkeypatch, capsys):
        """<type> <name> mode gates by the Affects: token."""
        from vcfops_packaging import defects as _defects_mod
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Dashboard bug
- **Severity:** blocking
- **Status:** open
- **Affects:** dashboards/demand_driven_capacity_v2
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Blocking dashboard defect.
""")
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "dashboards", "demand_driven_capacity_v2"])
        assert rc == 2
        captured = capsys.readouterr()
        assert "DEF-001" in captured.out

    def test_content_item_unaffected_exits_0(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Dashboard bug
- **Severity:** blocking
- **Status:** open
- **Affects:** dashboards/demand_driven_capacity_v2
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Only affects demand_driven_capacity_v2.
""")
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        rc = self._run(["defect-gate", "dashboards", "some_other_dashboard"])
        assert rc == 0


# ---------------------------------------------------------------------------
# Release refusal (cmd_release) — fixture registry via REGISTRY_PATH
# ---------------------------------------------------------------------------

class TestReleaseRefusal:
    """cmd_release must refuse and name defect ids when an open blocking
    defect exists.  REGISTRY_PATH is monkeypatched to a fixture registry so
    this is independent of any live defect's current state.
    """

    def _run_release(self, tmp_path, pak_dir_name: str):
        adapter_dir = tmp_path / "content" / "sdk-adapters" / pak_dir_name
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text(
            f"name: VCF Content Factory {pak_dir_name.title()} Adapter\ndescription: Test.\n",
            encoding="utf-8",
        )

        import argparse
        args = argparse.Namespace(
            content_type="sdk-adapter",
            name=str(adapter_yaml),
            version=None,
            notes=None,
            deprecates=None,
            slug=None,
            no_commit=True,
        )

        from vcfops_packaging.cli import cmd_release
        (tmp_path / "releases").mkdir()
        import os
        orig_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            rc = cmd_release(args)
        finally:
            os.chdir(orig_cwd)
        return rc

    def test_sdk_adapter_release_refused_for_open_blocker(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg_dir = tmp_path / "registry"
        reg_dir.mkdir()
        reg = _fixture_registry(reg_dir)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)

        rc = self._run_release(tmp_path, "fixture-pak-alpha")

        assert rc == 2, f"Expected exit 2 (blocked by DEF-001); got {rc}"
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "DEF-001" in combined, (
            f"Refusal must name DEF-001; got output:\n{combined}"
        )

    def test_sdk_adapter_release_passes_for_clean_pak(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        reg_dir = tmp_path / "registry"
        reg_dir.mkdir()
        reg = _fixture_registry(reg_dir)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)

        rc = self._run_release(tmp_path, "fixture-pak-gamma")

        # DEF-003 (fixture-pak-gamma) is closed, so the defect gate itself
        # must not refuse (rc != 2).  cmd_release may still fail later for
        # unrelated reasons (e.g. no git repo present) — we only assert the
        # gate does not fire.
        assert rc != 2, (
            f"clean pak must not be refused by the defect gate; got rc={rc}"
        )


# ---------------------------------------------------------------------------
# _gate_publish raises on open blockers (fixture registries)
# ---------------------------------------------------------------------------

class TestGatePublish:
    """_gate_publish raises PublishError naming defect ids."""

    def _make_mock_release(self, source_path: Path, release_name: str = "test-release"):
        """Build a minimal mock ReleaseDef + artifact."""
        from vcfops_packaging.releases import ReleaseDef, ReleaseArtifact
        art = ReleaseArtifact(
            source=str(source_path),
            source_path=source_path,
            headline=True,
        )
        return ReleaseDef(
            name=release_name,
            version="1.0",
            description="test",
            release_notes="",
            artifacts=[art],
            deprecates=[],
            manifest_path=source_path.parent / "release.yaml",
        )

    def test_passes_when_pak_defect_is_closed(self, tmp_path):
        """A pak whose only registered defect is closed passes _gate_publish."""
        from vcfops_packaging.publish import _gate_publish

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture pak: closed defect
- **Severity:** blocking
- **Status:** closed
- **Affects:** fixturepak
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Closed for test.
- **Closing-evidence:** Test proof — closed for this fixture.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "fixturepak"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "fixturepak-managementpack")
        # Must not raise — the only registered defect is closed.
        _gate_publish([release], tmp_path)

    def test_raises_for_pak_with_open_blocker(self, tmp_path):
        """A pak release triggers _gate_publish to raise when it has an open
        blocking defect registered against it."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-002

- **Title:** Fixture pak: open blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** fixturepak
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Open blocker used to prove the gate raises.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "fixturepak"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "fixturepak-managementpack")

        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], tmp_path)

        msg = str(exc_info.value)
        assert "DEF-002" in msg

    def test_passes_for_pak_with_no_registered_defects(self, tmp_path):
        """A pak with no entries at all in the registry passes cleanly."""
        from vcfops_packaging.publish import _gate_publish

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Unrelated pak's defect
- **Severity:** blocking
- **Status:** open
- **Affects:** some-other-pak
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Does not affect the pak under test.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "unaffected-pak"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "unaffected-pak-managementpack")
        # Must not raise.
        _gate_publish([release], tmp_path)

    def test_passes_when_defects_all_closed_or_tracked(self, tmp_path):
        """A registry with only closed/tracked defects lets _gate_publish pass."""
        from vcfops_packaging.publish import _gate_publish

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        reg = reg_dir / "defects.md"
        reg.write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Synology: closed defect
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Closed for test.
- **Closing-evidence:** Test proof — closed for this fixture.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        # Must not raise because the defect is closed.
        _gate_publish([release], tmp_path)

    def test_malformed_registry_raises_publish_error(self, tmp_path):
        """A malformed registry raises PublishError (never silently passes)."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        reg = reg_dir / "defects.md"
        reg.write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** No evidence
- **Severity:** blocking
- **Status:** closed
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Closed without evidence — malformed.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        with pytest.raises(PublishError, match="malformed"):
            _gate_publish([release], tmp_path)

    def test_vacuous_pass_when_registry_absent(self, tmp_path, capsys):
        """When factory_repo has no knowledge/context/defects.md the gate vacuously
        passes with a clearly visible WARNING — never raises, never falls
        back to the package-relative registry."""
        from vcfops_packaging.publish import _gate_publish

        # tmp_path has no knowledge/context/ directory — registry is absent.
        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        # Must NOT raise, regardless of what the real registry says about
        # synology — the registry is absent in this fixture repo.
        _gate_publish([release], tmp_path)

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "WARNING" in combined, (
            f"Vacuous pass must emit a WARNING; got:\n{combined}"
        )
        assert "RULE-012" in combined, (
            f"WARNING must mention RULE-012; got:\n{combined}"
        )

    def _fixture_adapter(self, tmp_path, pak: str = "synology"):
        adapter_dir = tmp_path / "content" / "sdk-adapters" / pak
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")
        return adapter_yaml

    def test_local_registry_overrides_the_shipped_one(self, tmp_path):
        """B1: /publish must honour defects.local.md like every other gate.

        _gate_publish hand-builds the registry path, and an explicit path
        correctly wins verbatim, so this was the one gate a consumer's local
        registry never reached: an upstream blocker on a pak they inherited
        refused their publish. That is the exact harm the whole change exists
        to remove.
        """
        from vcfops_packaging.publish import _gate_publish

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Upstream blocking defect for synology
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Filed upstream; not this consumer's defect.
""", encoding="utf-8")
        # The consumer's own registry: empty of defects, and it wins.
        (reg_dir / "defects.local.md").write_text(
            "# Local defect registry\n\n## Defects\n", encoding="utf-8"
        )

        release = self._make_mock_release(
            self._fixture_adapter(tmp_path), "synology-managementpack"
        )
        # Must NOT raise: nothing in the consumer's registry blocks synology.
        _gate_publish([release], tmp_path)

    def test_local_registry_still_gates_its_own_blockers(self, tmp_path):
        """Selection is replacement, not a bypass: a local blocker refuses."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        (reg_dir / "defects.md").write_text(
            "# Defect registry\n\n## Defects\n", encoding="utf-8"
        )
        (reg_dir / "defects.local.md").write_text("""\
# Local defect registry

## Defects

### DEF-001

- **Title:** The consumer's own blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Filed by the consumer against their own pak.
""", encoding="utf-8")

        release = self._make_mock_release(
            self._fixture_adapter(tmp_path), "synology-managementpack"
        )
        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], tmp_path)
        msg = str(exc_info.value)
        assert "DEF-001" in msg
        # Refused by their own registry: nothing to tell them about creating one.
        assert "create knowledge/context/defects.local.md" not in msg

    def test_refusal_from_the_shipped_registry_names_the_local_option(self, tmp_path):
        """B2: the "keep your own registry" sentence lives on the refusal,
        where it is actionable, not on every session's standing report."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Upstream blocking defect for synology
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Filed upstream.
""", encoding="utf-8")

        release = self._make_mock_release(
            self._fixture_adapter(tmp_path), "synology-managementpack"
        )
        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], tmp_path)
        msg = str(exc_info.value)
        assert "defects.local.md" in msg
        assert "If these defects are not yours" in msg

    def test_fires_on_fixture_repo_own_registry(self, tmp_path):
        """When the fixture repo HAS its own knowledge/context/defects.md with an open
        blocking defect, _gate_publish must raise naming the defect — it must
        not use the package-relative registry."""
        from vcfops_packaging.publish import _gate_publish, PublishError

        # Write a fixture registry that blocks synology.
        reg_dir = tmp_path / "knowledge" / "context"
        reg_dir.mkdir(parents=True)
        (reg_dir / "defects.md").write_text("""\
# Defect registry

## Defects

### DEF-001

- **Title:** Fixture blocking defect for synology
- **Severity:** blocking
- **Status:** open
- **Affects:** synology
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Blocking defect created by the test fixture.
""", encoding="utf-8")

        adapter_dir = tmp_path / "content" / "sdk-adapters" / "synology"
        adapter_dir.mkdir(parents=True)
        adapter_yaml = adapter_dir / "adapter.yaml"
        adapter_yaml.write_text("name: test\n", encoding="utf-8")

        release = self._make_mock_release(adapter_yaml, "synology-managementpack")
        with pytest.raises(PublishError) as exc_info:
            _gate_publish([release], tmp_path)

        msg = str(exc_info.value)
        assert "DEF-001" in msg, (
            f"Error must name the fixture defect DEF-001; got:\n{msg}"
        )
        assert "RULE-012" in msg


# ---------------------------------------------------------------------------
# Standalone entrypoint: python3 vcfops_packaging/defects.py
# ---------------------------------------------------------------------------

class TestStandaloneEntrypoint:
    """Verify the __main__ block in defects.py.

    Tests use subprocess so they exercise the real script execution path,
    not the import path.  This is the load-bearing proof for the curl-and-run
    contract.  The registry files used here are synthetic fixtures written to
    tmp_path — only the real defects.py *script* is copied/invoked, never the
    live knowledge/context/defects.md content — so these tests are independent of the
    live corpus's current defect states.
    """

    _DEFECTS_SCRIPT = REPO_ROOT / "src" / "vcfops_packaging" / "defects.py"

    def _run_script(self, script_path: Path, argv: list, cwd: Path | None = None):
        """Run defects.py as a bare script; return (returncode, stdout, stderr)."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)] + argv,
            capture_output=True,
            text=True,
            cwd=str(cwd or REPO_ROOT),
        )
        return result.returncode, result.stdout, result.stderr

    # --- In-package invocations -------------------------------------------------

    def test_pak_clean_exits_0(self, tmp_path):
        """--pak <clean-pak> with a fixture registry → exit 0."""
        reg = _fixture_registry(tmp_path)
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "fixture-pak-gamma", "--registry", str(reg)],
        )
        assert rc == 0, f"Expected exit 0; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "fixture-pak-gamma" in out, f"Output must mention pak name; got:\n{out}"

    def test_pak_blocked_exits_2(self, tmp_path):
        """--pak <blocked-pak> with a fixture registry → exit 2, names the id."""
        reg = _fixture_registry(tmp_path)
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "fixture-pak-alpha", "--registry", str(reg)],
        )
        assert rc == 2, f"Expected exit 2; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "DEF-001" in out, f"Output must name DEF-001; got:\n{out}"

    def test_all_exits_2_lists_open_blockers_only(self, tmp_path):
        """--all → exit 2, lists only the open blocking defects."""
        reg = _fixture_registry(tmp_path)
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--all", "--registry", str(reg)],
        )
        assert rc == 2, f"Expected exit 2 for --all; got {rc}\nstdout: {out}\nstderr: {err}"
        assert "DEF-001" in out, f"Output must list DEF-001; got:\n{out}"
        assert "DEF-002" in out, f"Output must list DEF-002; got:\n{out}"
        assert "DEF-003" not in out, "closed defect must not be listed"

    def test_missing_registry_warns_and_passes(self, tmp_path):
        """--registry pointing at a nonexistent path -> exit 0 with a WARNING.

        The pre-push hook that replaces the pak CI gate runs in clones that
        may have no registry beside them; it must warn and pass, never
        refuse a push over a file that is not there.
        """
        missing = tmp_path / "no_such_dir" / "defects.md"
        rc, out, err = self._run_script(
            self._DEFECTS_SCRIPT,
            ["--pak", "anything", "--registry", str(missing)],
        )
        assert rc == 0, f"Expected exit 0 for missing registry; got {rc}\nstdout: {out}\nstderr: {err}"
        combined = out + err
        assert "WARNING" in combined, combined
        assert "RULE-012" in combined, combined

    def test_local_registry_beside_the_script_wins(self, tmp_path):
        """A bare copy with a defects.local.md sibling reads the local file."""
        import shutil
        script_copy = tmp_path / "defects.py"
        shutil.copy2(str(self._DEFECTS_SCRIPT), str(script_copy))
        (tmp_path / "defects.md").write_text(_FIXTURE_REGISTRY_TEXT, encoding="utf-8")
        (tmp_path / "defects.local.md").write_text("""\
# Local defect registry

## Defects

### DEF-001

- **Title:** Local-only blocking defect
- **Severity:** blocking
- **Status:** open
- **Affects:** local-only-pak
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Only present in the consumer's own registry.
""", encoding="utf-8")

        # The shipped fixture's blocker is invisible once a local file exists.
        rc, out, err = self._run_script(
            script_copy, ["--pak", "fixture-pak-alpha"], cwd=tmp_path
        )
        assert rc == 0, f"local registry must win; got {rc}\nstdout: {out}\nstderr: {err}"
        rc, out, err = self._run_script(
            script_copy, ["--pak", "local-only-pak"], cwd=tmp_path
        )
        assert rc == 2, f"local registry blocker must fire; got {rc}\nstdout: {out}"
        assert "DEF-001" in out

    # --- Bare-copy invocation: the load-bearing curl-and-run proof --------------

    def test_bare_copy_matches_in_package_run(self, tmp_path):
        """Copy defects.py (the real script) alongside a synthetic fixture
        registry into a clean temp dir; run it there.

        The pak-repo CI workflow does:
          curl .../defects.py -o defects.py
          curl .../knowledge/context/defects.md -o defects.md
          python3 defects.py --pak <name> --registry defects.md

        This test reproduces that mechanism exactly (bare script, no
        vcfops_packaging on sys.path, no package structure present) using a
        synthetic registry so the assertions are independent of the live
        corpus's current defect states.
        """
        import shutil

        script_copy = tmp_path / "defects.py"
        registry_copy = tmp_path / "defects.md"
        shutil.copy2(str(self._DEFECTS_SCRIPT), str(script_copy))
        registry_copy.write_text(_FIXTURE_REGISTRY_TEXT, encoding="utf-8")

        # Run from the temp dir; cwd has NO factory repo structure.
        rc, out, err = self._run_script(
            script_copy,
            ["--pak", "fixture-pak-alpha", "--registry", str(registry_copy)],
            cwd=tmp_path,
        )

        assert rc == 2, (
            f"Bare-copy run must exit 2 (blocked by DEF-001); "
            f"got {rc}\nstdout: {out}\nstderr: {err}"
        )
        assert "DEF-001" in out, (
            f"Bare-copy run output must name DEF-001; got:\n{out}"
        )
        assert "RULE-012" in out, (
            f"Bare-copy run output must name RULE-012; got:\n{out}"
        )

    def test_bare_copy_clean_pak_exits_0(self, tmp_path):
        """Bare-copy run for a clean pak → exit 0."""
        import shutil

        script_copy = tmp_path / "defects.py"
        registry_copy = tmp_path / "defects.md"
        shutil.copy2(str(self._DEFECTS_SCRIPT), str(script_copy))
        registry_copy.write_text(_FIXTURE_REGISTRY_TEXT, encoding="utf-8")

        rc, out, err = self._run_script(
            script_copy,
            ["--pak", "fixture-pak-gamma", "--registry", str(registry_copy)],
            cwd=tmp_path,
        )
        assert rc == 0, (
            f"Bare-copy run must exit 0 for a clean pak; "
            f"got {rc}\nstdout: {out}\nstderr: {err}"
        )


# ---------------------------------------------------------------------------
# Refusal hint and warning volume
# ---------------------------------------------------------------------------

class TestLocalRegistryHint:
    """B2: the "keep your own registry" sentence rides on the refusal."""

    def test_hint_offered_when_gating_from_the_shipped_registry(self, tmp_path, monkeypatch):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        hint = _defects_mod.local_registry_hint()
        assert "defects.local.md" in hint
        assert "If these defects are not yours" in hint

    def test_silent_when_the_caller_has_their_own_registry(self, tmp_path, monkeypatch):
        from vcfops_packaging import defects as _defects_mod
        reg = _fixture_registry(tmp_path)
        (tmp_path / "defects.local.md").write_text("# local\n", encoding="utf-8")
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        assert _defects_mod.local_registry_hint() == "", (
            "a user being refused by their own registry has nothing to be told"
        )

    def test_cli_refusal_carries_the_hint(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        from vcfops_packaging.cli import build_parser
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        parser = build_parser()
        args = parser.parse_args(["defect-gate", "--pak", "fixture-pak-alpha"])
        assert args.func(args) == 2
        out = capsys.readouterr().out
        assert "defects.local.md" in out

    def test_clean_run_says_nothing_about_the_local_registry(self, tmp_path, monkeypatch, capsys):
        from vcfops_packaging import defects as _defects_mod
        from vcfops_packaging.cli import build_parser
        reg = _fixture_registry(tmp_path)
        monkeypatch.setattr(_defects_mod, "REGISTRY_PATH", reg)
        parser = build_parser()
        args = parser.parse_args(["defect-gate", "--pak", "fixture-pak-gamma"])
        assert args.func(args) == 0
        captured = capsys.readouterr()
        assert "defects.local.md" not in (captured.out + captured.err), (
            "the hint is for refusals only, never a standing line"
        )


class TestWarningVolume:
    """W2: loud once, not loud N times."""

    def test_parse_warning_is_emitted_once_per_registry_per_process(self, tmp_path, capsys):
        from vcfops_packaging.defects import gate_pak, reset_warning_state
        reset_warning_state()
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** Broken
- **Severity:** critical
- **Status:** open
- **Affects:** fixture-pak-x
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Malformed entry.
""")
        for _ in range(5):
            gate_pak("fixture-pak-x", reg)
        err = capsys.readouterr().err
        assert err.count("WARNING") == 1, (
            f"N-times-loud trains people to skip the warning; got:\n{err}"
        )

    def test_absent_registry_warning_is_emitted_once(self, tmp_path, capsys):
        from vcfops_packaging.defects import gate_pak, reset_warning_state
        reset_warning_state()
        missing = tmp_path / "nope" / "defects.md"
        for _ in range(4):
            gate_pak("anything", missing)
        err = capsys.readouterr().err
        assert err.count("WARNING") == 1, err

    def test_a_second_registry_still_warns(self, tmp_path, capsys):
        """Dedupe is per resolved path, not a global mute."""
        from vcfops_packaging.defects import gate_pak, reset_warning_state
        reset_warning_state()
        gate_pak("anything", tmp_path / "a" / "defects.md")
        gate_pak("anything", tmp_path / "b" / "defects.md")
        assert capsys.readouterr().err.count("WARNING") == 2


class TestSyntheticEntryIdentity:
    """N2/N3: the synthetic entry must match what the warning claims."""

    def test_over_length_affects_token_still_matches_its_scope(self, tmp_path):
        from vcfops_packaging.defects import gate_pak
        long_token = "p" * 300
        reg = _write_registry(tmp_path, f"""\
# Defect registry

## Defects

### DEF-001

- **Title:** Broken
- **Severity:** critical
- **Status:** open
- **Affects:** {long_token}
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Malformed entry with a very long scope token.
""")
        blockers = gate_pak(long_token, reg)
        assert len(blockers) == 1, (
            "the warning claims this entry blocks that scope, so it must"
        )

    def test_over_length_token_is_clipped_in_the_warning(self, tmp_path, capsys):
        from vcfops_packaging.defects import gate_pak, reset_warning_state
        reset_warning_state()
        long_token = "p" * 300
        reg = _write_registry(tmp_path, f"""\
# Defect registry

## Defects

### DEF-001

- **Title:** Broken
- **Severity:** critical
- **Status:** open
- **Affects:** {long_token}
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Malformed entry with a very long scope token.
""")
        gate_pak(long_token, reg)
        err = capsys.readouterr().err
        assert long_token not in err, "untrusted content is clipped at the echo"
        assert "WARNING" in err

    def test_two_id_less_entries_do_not_collide(self, tmp_path):
        from vcfops_packaging.defects import parse_registry
        reg = _write_registry(tmp_path, """\
# Defect registry

## Defects

### DEF-001

- **Title:** First
- **Severity:** blocking
- **Status:** open
- **Affects:** pak-a
- **First-seen:** build 1 (2026-01-01)
- **Source:** knowledge/context/reviews/<synthetic-fixture>.md
- **Summary:** Fine.
""")
        from vcfops_packaging.defects import ParseError, _synthetic_entry
        from pathlib import Path as _P
        a = _synthetic_entry(ParseError("", 10, "bad", "pak-a"), _P("x"))
        b = _synthetic_entry(ParseError("", 40, "bad", "pak-b"), _P("x"))
        assert a.id != b.id, "id-less entries must not dedupe into one"
        assert parse_registry(reg).errors == []
