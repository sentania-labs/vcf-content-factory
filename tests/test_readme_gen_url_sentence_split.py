"""Regression test: release catalog descriptions must not be truncated
mid-URL by the README first-sentence summarizer.

Bug (Codex P2, vcf-content-factory-bundles PR #19): the summarizer treated
every period in the description as a sentence boundary, including periods
inside embedded URLs (e.g. Broadcom KB links), so
``https://knowledge.broadcom.com/...`` was chopped to ``https://knowledge.``
in the generated catalog cell.

Fix: ``_first_sentence()`` only treats a period as a sentence boundary when
it's followed by whitespace or end-of-string, so dots inside URL tokens
(never followed by whitespace) are never mistaken for sentence ends.
"""
from __future__ import annotations

from vcfops_packaging.readme_gen import _first_sentence


def test_first_sentence_preserves_embedded_url():
    desc = (
        "CPU support/deprecation posture per Broadcom KB 318697 "
        "(https://knowledge.broadcom.com/external/article/318697/"
        "cpu-support-deprecation-and-discontinuat.html) — source of record "
        "for the underlying coded classification. Scope tier (Row 1) lists "
        "vSphere World and vCenter rows."
    )
    result = _first_sentence(desc)

    # The full URL must survive intact, not be truncated at "knowledge.".
    assert (
        "https://knowledge.broadcom.com/external/article/318697/"
        "cpu-support-deprecation-and-discontinuat.html"
    ) in result
    assert "https://knowledge." not in result.replace(
        "https://knowledge.broadcom.com/external/article/318697/"
        "cpu-support-deprecation-and-discontinuat.html",
        "",
    )
    # Only the first sentence is kept — the second sentence is dropped.
    assert "Scope tier" not in result
    assert result.endswith(
        "source of record for the underlying coded classification."
    )


def test_first_sentence_simple_description_unchanged():
    desc = "A simple dashboard. It has two sentences."
    assert _first_sentence(desc) == "A simple dashboard."


def test_first_sentence_no_trailing_period_gets_one_appended():
    desc = "A description with no terminal period"
    assert _first_sentence(desc) == "A description with no terminal period."


def test_first_sentence_empty_string():
    assert _first_sentence("") == ""
    assert _first_sentence(None) == ""


def test_first_sentence_kb_url_no_trailing_sentence():
    # Description ends immediately after the URL, no trailing space/sentence.
    desc = (
        "Reference Broadcom KB 318697: "
        "https://knowledge.broadcom.com/external/article/318697/foo.html"
    )
    result = _first_sentence(desc)
    assert result.endswith(
        "https://knowledge.broadcom.com/external/article/318697/foo.html."
    )
