"""One defect gate: the module and the kit's shipped script agree (#226).

Two implementations had drifted: the factory's ``vcfcf_packaging/defects.py``
and the ``ci/defect_gate.py`` the sdk-template vendors into every pak repo.
The factory module is now the single implementation: it adopted every
fail-closed rule of the vendored script (inside RULE-012's per-entry
isolation), and the sdk-buildkit ships it, unedited behind a generated
header, as ``sdk_buildkit/defect_gate.py``.

This file holds the fixture matrix, ported from the template's
``tests/ci/test_defect_gate.py`` (sentania-labs/vcf-content-factory-sdk-template
at 49ab82cf, 2026-10-16) plus the factory's isolation and ``--require-registry``
cases, and runs every row against BOTH:

  - the in-tree module run as a bare script (how the hook-free CI path runs it)
  - the defect_gate.py extracted from an assembled sdk-buildkit tarball

and asserts the expected exit code for each.  Where a row's expectation
differs from the vendored script's verdict it says why.  There are exactly
two divergences, both from RULE-012: an absent, empty or unreadable registry
is a warning by default (``--require-registry`` restores the vendored
refusal), and a malformed entry does not block a pak it does not name.  Where
the vendored script refused (exit 1) this gate refuses too (exit 2 for the
named pak).  Where it allowed, this gate allows, trailing heading text
included, with one deliberate exception in the strict direction: an
``Affects:`` token with edge punctuation (``template.``) is malformed here and
refuses the pak it names, where the vendored script read it as a token
matching nothing.  Every row was cross-checked against the vendored script
(template commit 49ab82cf) when written; the disagreements are exactly these.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

import pytest

from vcfcf_packaging import defects
from vcfcf_packaging.defects import (
    gate_all,
    gate_item,
    gate_pak,
    parse_registry,
    reset_warning_state,
)

_MODULE = Path(defects.__file__)

ENTRY = textwrap.dedent("""\
    {heading}

    - **Title:** something broke
    - **Severity:** {severity}
    - **Status:** {status}
    - **Affects:** {affects}
    - **First-seen:** build 1 (2026-10-16)
    - **Source:** review
    - **Summary:** it broke
    """)
PRE = "# Defect registry\n\n## Defects\n\n"


def entry(n: int, affects: str, severity: str = "blocking",
          heading: str = None, status: str = "open") -> str:
    return ENTRY.format(heading=heading or f"### DEF-{n:03d}", affects=affects,
                        severity=severity, status=status)


def registry(*entries: str, pre: str = PRE) -> str:
    return pre + "\n".join(entries)


def under_summary(text: str, extra: str) -> str:
    return text.replace("- **Summary:** it broke", "- **Summary:** it broke\n" + extra)


def indent_fields(text: str, pad: str) -> str:
    return "\n".join(pad + line if line.startswith("- **") else line
                     for line in text.splitlines()) + "\n"


def blocker_then(heading: str) -> str:
    """An open template blocker followed by a tracked entry under ``heading``.

    The Codex P1 shape: the second entry's fields used to overwrite the
    blocker's (Severity: tracked) and the blocker vanished.
    """
    return registry(entry(1, "template"),
                    entry(2, "template", severity="tracked", heading=heading))


_FENCED_HEADING_LATER = registry(under_summary(
    entry(1, "unifi"), "```\n" + entry(2, "template") + "```"))

#: (id, registry text or None for no file, pak, extra flags, expected exit)
MATRIX = [
    # --- registry presence: RULE-012 default, vendored rule as opt-in ---
    ("missing-default", None, "template", [], 0),
    ("missing-required", None, "template", ["--require-registry"], 1),
    ("empty-default", "", "template", [], 0),
    ("empty-required", "", "template", ["--require-registry"], 1),
    ("html-page-required", "<html><body>404: Not Found</body></html>\n",
     "template", ["--require-registry"], 1),
    ("reformatted-required",
     "# Defect registry\n\n## Defects\n\n#### Defect 1\n- **Affects:** template\n",
     "template", ["--require-registry"], 1),
    ("present-required-clean", registry(entry(1, "unifi")), "template",
     ["--require-registry"], 0),

    # --- unchanged behaviour ---
    ("clear", registry(entry(1, "unifi"), entry(2, "template", severity="tracked")),
     "template", [], 0),
    ("other-pak-blocked", registry(entry(1, "unifi"), entry(2, "template", severity="tracked")),
     "unifi", [], 2),
    ("open-blocker", registry(entry(1, "unifi"), entry(2, "template")), "template", [], 2),

    # --- malformed headings: refuse the pak they name, never bleed ---
    ("bad-id", registry(entry(1, "unifi"), entry(2, "template", heading="### DEF-1O2")),
     "template", [], 2),
    # Isolation (RULE-012): the vendored script refused every pak here.
    ("bad-id-other-pak", registry(entry(1, "unifi"), entry(2, "template", heading="### DEF-1O2")),
     "synology", [], 0),
    ("deep-5", blocker_then("##### DEF-002"), "template", [], 2),
    ("deep-6", blocker_then("###### DEF-002"), "template", [], 2),
    ("deep-7-trailing", blocker_then("####### DEF-002 (deep)"), "template", [], 2),
    ("no-space", blocker_then("###DEF-002"), "template", [], 2),
    ("lowercase", blocker_then("### def-002"), "template", [], 2),
    ("indent-1", registry(entry(1, "unifi"), entry(2, "template", heading=" ### DEF-002")),
     "template", [], 2),
    ("indent-3", registry(entry(1, "unifi"), entry(2, "template", heading="   ### DEF-002")),
     "template", [], 2),
    ("indent-4-code", blocker_then("    ### DEF-002"), "template", [], 2),
    ("indent-tab-code", blocker_then("\t### DEF-002"), "template", [], 2),
    ("nbsp-before", blocker_then(" ### DEF-002"), "template", [], 2),
    ("nbsp-after-hashes", blocker_then("### DEF-002"), "template", [], 2),
    ("blockquote", blocker_then("> ### DEF-002"), "template", [], 2),
    ("blockquote-tight", blocker_then(">### DEF-002"), "template", [], 2),
    ("trailing-text-open", registry(entry(1, "unifi"), entry(
        2, "template", heading="### DEF-002 (template build 2)")), "template", [], 2),
    ("prose-heading", registry(entry(1, "unifi")) + "\n### DEFECTS ELSEWHERE\n\nprose\n",
     "template", [], 0),

    # --- field lines ---
    ("fields-indent-2", registry(entry(1, "unifi"), indent_fields(entry(2, "template"), "  ")),
     "template", [], 2),
    ("fields-indent-3", registry(entry(1, "unifi"), indent_fields(entry(2, "template"), "   ")),
     "template", [], 2),
    ("fields-indent-4-code", registry(entry(1, "unifi"),
                                      indent_fields(entry(2, "template"), "    ")),
     "template", [], 2),
    ("fields-indent-tab-code", registry(entry(1, "unifi"),
                                        indent_fields(entry(2, "template"), "\t")),
     "template", [], 2),
    ("one-status-code-indent", registry(entry(1, "unifi"), entry(2, "template").replace(
        "- **Status:**", "    - **Status:**")), "template", [], 2),
    ("nested-status-closed", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "  - **Status:** closed\n  - **Closing-evidence:** fixed")),
     "template", [], 2),
    ("nested-severity-tracked", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "   - **Severity:** tracked")), "template", [], 2),
    ("nested-affects", registry(entry(1, "synology"), under_summary(
        entry(2, "template"), "  - **Affects:** unifi")), "template", [], 2),
    # ...and the nested Affects names unifi too, so it refuses unifi as well.
    ("nested-affects-second-scope", registry(entry(1, "synology"), under_summary(
        entry(2, "template"), "  - **Affects:** unifi")), "unifi", [], 2),
    ("repeated-severity", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "- **Severity:** tracked")), "template", [], 2),
    ("repeated-status", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "- **Status:** closed\n- **Closing-evidence:** x")),
     "template", [], 2),
    ("blockquoted-field", registry(entry(1, "unifi"), entry(2, "template").replace(
        "- **Status:** open", "> - **Status:** closed")), "template", [], 2),

    # --- fences and examples ---
    ("indented-example-intro", registry(entry(1, "template"), pre=(
        "# Defect registry\n\nSchema example:\n\n"
        "    ### DEF-NNN\n    - **Affects:** <pak>\n\n## Defects\n\n")), "unifi", [], 0),
    ("fenced-example-intro", registry(entry(1, "template"), pre=(
        "# Defect registry\n\n```\n### DEF-NNN\n- **Affects:** <pak>\n```\n\n"
        "## Defects\n\n")), "template", [], 2),
    ("fenced-status-closed", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "```\n- **Status:** closed\n- **Severity:** tracked\n```")),
     "template", [], 2),
    ("fenced-heading-later", _FENCED_HEADING_LATER, "template", [], 2),
    ("fenced-numeric-before-first", registry(
        "```\n" + entry(1, "template") + "```\n", entry(2, "unifi", severity="tracked")),
     "template", [], 2),
    ("bom", "﻿" + entry(1, "template"), "template", [], 2),

    # --- Affects shape and case ---
    ("multi-token", registry(entry(1, "unifi"), entry(2, "template (also unifi)")),
     "template", [], 2),
    ("backtick", registry(entry(1, "unifi"), entry(2, "`template`")), "template", [], 2),
    ("comma-spaced", registry(entry(1, "unifi"), entry(2, "template, unifi")),
     "template", [], 2),
    ("comma", registry(entry(1, "synology"), entry(2, "template,unifi")), "template", [], 2),
    ("comma-second-item", registry(entry(1, "synology"), entry(2, "template,unifi")),
     "unifi", [], 2),
    ("case-registry", registry(entry(1, "Template"), entry(2, " TEMPLATE ")),
     "template", [], 2),
    ("case-gated-name", registry(entry(1, "template")), "TEMPLATE", [], 2),

    # --- template cases ported in the review round (W3) ---
    ("t-heading-indent-2", registry(entry(1, "unifi"), entry(2, "template", heading="  ### DEF-002")),
     "template", [], 2),
    ("t-heading-indent-6-code", blocker_then("      ### DEF-002"), "template", [], 2),
    ("t-heading-indent-space-tab-code", blocker_then(" \t### DEF-002"), "template", [], 2),
    ("t-fields-indent-space-tab-code", registry(entry(1, "unifi"),
                                                indent_fields(entry(2, "template"), " \t")),
     "template", [], 2),
    ("t-nested-status-alone-2", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "  - **Status:** closed")), "template", [], 2),
    ("t-nested-status-alone-1", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), " - **Status:** closed")), "template", [], 2),
    ("t-nested-severity-2", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "  - **Severity:** tracked")), "template", [], 2),
    ("t-repeated-status-alone", registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "- **Status:** closed")), "template", [], 2),
    ("t-repeated-affects", registry(entry(1, "synology"), under_summary(
        entry(2, "template"), "- **Affects:** unifi")), "template", [], 2),
    ("t-repeated-affects-second", registry(entry(1, "synology"), under_summary(
        entry(2, "template"), "- **Affects:** unifi")), "unifi", [], 2),
    ("t-indented-example-intro-gated", registry(entry(1, "template"), pre=(
        "# Defect registry\n\nSchema example:\n\n"
        "    ### DEF-NNN\n    - **Affects:** <pak>\n\n## Defects\n\n")), "template", [], 2),
    ("t-no-def-sections-html-default", "<html><body>404: Not Found</body></html>\n",
     "template", [], 0),

    # --- review fixes (2026-10-23 framework review) ---
    # B1: every pak a malformed Affects names is refused, not the first only.
    ("b1-comma-spaced-second", registry(entry(1, "synology"), entry(2, "template, unifi")),
     "unifi", [], 2),
    ("b1-real-paks-second", registry(entry(1, "compliance"), entry(2, "synology, unifi")),
     "unifi", [], 2),
    ("b1-space-list-second", registry(entry(1, "synology"), entry(2, "template unifi")),
     "unifi", [], 2),
    ("b1-backtick-list-second", registry(entry(1, "synology"), entry(2, "`template`, `unifi`")),
     "unifi", [], 2),
    ("b1-prose-list-second", registry(entry(1, "synology"), entry(2, "template and unifi")),
     "unifi", [], 2),
    ("b1-prose-unnamed-pak", registry(entry(1, "synology", severity="tracked"),
                                      entry(2, "template and unifi")), "synology", [], 0),
    # B2: headings kept, field syntax changed: no VALID entry, so refused.
    ("b2-star-bullets-required", registry(
        entry(1, "template").replace("- **", "* **"),
        entry(2, "unifi").replace("- **", "* **")), "template", ["--require-registry"], 1),
    ("b2-table-required", registry(
        "### DEF-001\n\n| Field | Value |\n|---|---|\n| Affects | template |\n"),
     "template", ["--require-registry"], 1),
    # W2: trailing heading text is tolerated, as in the vendored gate, so a
    # closed entry under such a heading no longer blocks.
    ("w2-trailing-text-closed", registry(entry(1, "unifi"), entry(
        2, "template", heading="### DEF-002 (template build 2)", status="closed",
    ).replace("- **Summary:**", "- **Closing-evidence:** fixed in build 3\n- **Summary:**")),
     "template", [], 0),
    ("w2-trailing-text-tracked", registry(entry(1, "unifi"), entry(
        2, "template", severity="tracked", heading="### DEF-002 (template build 2)")),
     "template", [], 0),
    # N1: edge punctuation on a bare token is malformed and still refuses.
    ("n1-trailing-period", registry(entry(1, "unifi"), entry(2, "template.")),
     "template", [], 2),
    ("n1-parenthesised", registry(entry(1, "unifi"), entry(2, "(template)")),
     "template", [], 2),

    # --- value errors stay scoped ---
    ("waived", registry(entry(1, "unifi"), entry(2, "template", status="waived")),
     "template", [], 2),
    ("closed-no-evidence", registry(entry(1, "unifi"), entry(2, "template", status="closed")),
     "template", [], 2),
    ("duplicate-id", registry(entry(1, "unifi"), entry(1, "template")), "template", [], 2),
    # Isolation (RULE-012): a broken unifi entry blocks unifi, not template.
    ("malformed-other-pak", registry(
        entry(1, "template", severity="tracked"),
        entry(2, "unifi").replace("- **Title:** something broke\n", "")),
     "template", [], 0),
    ("malformed-own-pak", registry(
        entry(1, "template", severity="tracked"),
        entry(2, "unifi").replace("- **Title:** something broke\n", "")),
     "unifi", [], 2),
]


def _run(script: Path, tmp_path: Path, case_id: str, text, pak: str, flags):
    case_dir = tmp_path / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    reg = case_dir / "defects.md"
    if text is not None:
        reg.write_text(text, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(
        [sys.executable, str(script), "--pak", pak, "--registry", str(reg), *flags],
        capture_output=True, text=True, cwd=str(case_dir), env=env, timeout=60,
    )


@pytest.fixture(scope="module")
def kit_script(tmp_path_factory) -> Path:
    """defect_gate.py as shipped: assemble a kit tarball and extract it."""
    from vcfcf_managementpacks.buildkit import assemble_buildkit

    work = tmp_path_factory.mktemp("kit")
    ref = work / "reference.pak"
    ref.write_bytes(b"not a real pak; only copied into reference_paks/")
    tarball = assemble_buildkit(work / "out", reference_pak=ref, verbose=False)
    with tarfile.open(tarball) as tf:
        member = tf.getmember("sdk_buildkit/defect_gate.py")
        data = tf.extractfile(member).read()
    script = work / "extracted" / "defect_gate.py"
    script.parent.mkdir()
    script.write_bytes(data)
    return script


@pytest.mark.parametrize(
    "case_id,text,pak,flags,expected", MATRIX, ids=[row[0] for row in MATRIX],
)
def test_module_and_kit_script_agree(tmp_path, kit_script, case_id, text, pak, flags, expected):
    results = {
        "module": _run(_MODULE, tmp_path / "module", case_id, text, pak, flags),
        "kit": _run(kit_script, tmp_path / "kit", case_id, text, pak, flags),
    }
    for who, result in results.items():
        assert result.returncode == expected, (
            f"{who}: rc={result.returncode}, expected {expected}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def test_kit_script_is_the_module_verbatim(kit_script):
    """Generated, never hand-edited: header comments, then the module bytes."""
    shipped = kit_script.read_text(encoding="utf-8")
    source = _MODULE.read_text(encoding="utf-8")
    assert shipped.endswith(source)
    header = shipped[: len(shipped) - len(source)]
    assert header and all(line.startswith("#") for line in header.splitlines()), header


# ---------------------------------------------------------------------------
# In-process checks the exit code alone cannot show
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    reset_warning_state()
    monkeypatch.setattr(defects, "_known_pak_names", lambda: frozenset({"template", "unifi"}))
    yield
    reset_warning_state()


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "defects.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_fenced_fields_are_description_not_fields(tmp_path):
    """The #226 comment's repro: a fenced Status: closed silently closed the blocker."""
    reg = _write(tmp_path, registry(entry(1, "unifi"), under_summary(
        entry(2, "template"), "```\n- **Status:** closed\n- **Closing-evidence:** x\n```")))
    hits = gate_pak("template", reg)
    assert [(e.id, e.status, e.severity, e.synthetic) for e in hits] == [
        ("DEF-002", "open", "blocking", False)
    ]
    assert "**Status:** closed" in hits[0].summary


def test_bleed_shapes_terminate_the_previous_entry(tmp_path):
    """The blocker before a disguised heading survives intact, as itself."""
    for heading in ("##### DEF-002", "###DEF-002", "### def-002", "> ### DEF-002",
                    " ### DEF-002", "    ### DEF-002"):
        reset_warning_state()
        reg = _write(tmp_path, blocker_then(heading))
        registry_ = parse_registry(reg)
        assert [(e.id, e.severity) for e in registry_.entries] == [("DEF-001", "blocking")], heading
        assert len(registry_.errors) == 1, heading


def test_case_insensitive_item_gate(tmp_path):
    reg = _write(tmp_path, registry(entry(1, "Dashboard/My_Dash")))
    assert len(gate_item("dashboard", "my_dash", reg)) == 1


def test_comma_list_fails_closed_for_every_item(tmp_path):
    reg = _write(tmp_path, registry(entry(1, "template,unifi")))
    assert sorted(e.affects for e in gate_all(reg)) == ["template", "unifi"]


def test_digit_bearing_bad_heading_warns_without_dash_fields(tmp_path, capsys):
    """W1: ``### DEF-1O2`` with ``*`` bullets used to be silent."""
    text = entry(2, "template", heading="### DEF-1O2").replace("- **", "* **")
    reg = _write(tmp_path, registry(entry(1, "unifi"), text))
    registry_ = parse_registry(reg)
    assert [e.entry_id for e in registry_.errors] == ["DEF-1O2"]
    gate_pak("template", reg)
    assert "DEF-1O2" in capsys.readouterr().err


def test_digit_free_prose_heading_stays_silent(tmp_path, capsys):
    reg = _write(tmp_path, registry(entry(1, "unifi")) + "\n### DEFECTS 2026\n\n* prose\n")
    assert parse_registry(reg).errors == []
    gate_pak("template", reg)
    assert capsys.readouterr().err == ""


def test_unreadable_vs_empty(tmp_path):
    """B2: errors but no valid entry is unreadable, not empty."""
    reg = _write(tmp_path, registry(entry(1, "template").replace("- **", "* **")))
    registry_ = parse_registry(reg)
    assert registry_.unreadable and not registry_.empty


def test_shipped_registry_still_parses_clean():
    """The new shape rules find nothing to complain about in the real registry."""
    registry_ = parse_registry(defects.REGISTRY_PATH)
    assert registry_.errors == [], [str(e) for e in registry_.errors]
    assert registry_.entries, "the shipped registry must hold entries"
