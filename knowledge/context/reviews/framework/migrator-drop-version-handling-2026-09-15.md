# Framework review: migrator, drop version handling (feat/drop-version-handling)

- Repo: `content/migrator` (vcf-cf-migrator), branch `feat/drop-version-handling`,
  3 commits over `main` at `v0.1.0` (`920f123` .. `f8ce69d`), not pushed
- Reviewed: 2026-09-15
- Diff: 21 files, 200 insertions, 532 deletions
- Authority: `knowledge/designs/content-migrator-v1.md` Versions row and
  section "Why there is no version handling"; Scott verbatim 2026-09-15
  ("But those could be settings from the export and not necessarily be version
  artifacts. Until we have proof drop all version stuff")
- Prior rounds: `migrator-m3-skeleton-2026-09-14.md`,
  `migrator-m4a-tree-and-build-2026-09-14.md`,
  `migrator-m4b-preview-and-page-2026-09-14.md`,
  `migrator-logging-2026-09-14.md`, `migrator-v0.1.0-2026-09-15.md`
- Verdict: **APPROVE** (0 BLOCKING, 3 WARNING, 4 NIT)

A deletion goes wrong two ways: a caller left behind, or something load-bearing
taken out with it. Neither happened. Every claim in the brief reproduced.

## Checks re-run independently

Clean venv `/tmp/mig-rev-venv`, `pip install .` so the pinned core wheel
(`vcf-cf-tooling-core` **0.1.0**) is what the suite runs against, scratch
`HOME` and `VCFCF_MIGRATOR_CONFIG_DIR` so the workstation settings file is not
this review's. Byte comparisons are against a worktree at the `v0.1.0` tag
(`/tmp/mig-v010`), both sides on the same core.

| Check | Result |
|---|---|
| `pytest -q`, source tree | **543 passed**, 0 failed |
| `pytest -q`, clean venv install of the wheel | **543 passed**, 0 failed |
| `corpus-check`, source tree and wheel install | exit 0, **5 ok**, nothing declared, no version word in the output |
| select-all bundle vs `v0.1.0`, byte compare, 4 exports (8.18.7, 9.0.2 x2, 9.1.1) | **byte-identical**, all four, md5 matched |
| closed-subset bundle vs `v0.1.0`, two dashboards, 8.18.7 and 9.0.2 | **byte-identical**, both |
| wheel-built bundle vs dev-tree bundle | identical, both exports |
| sharing-member synthesis on the 8.x source | intact: subset bundle carries `dashboardsharings/<owner>` = `[]` where the export has the directory entry and no member |
| directory entries in the 8.x subset | `dashboards/` and `dashboardsharings/` both present, stored empty |
| manifest counts in the 8.x subset | `dashboards=2, views=6, dashboardsByOwner[owner]=2`, written fresh, correct for the closure |
| entry-list check fails when the fix is removed (mutation: `bundle.directory_entries` returns `[]`) | **caught**: `error ... the bundle is missing the directory entry dashboards/` |
| closure audit, every node as a seed, all 5 zips | **802 seeds, 0 unclosed edges** (non-vacuous: 54 in-export refs exercised on the 8.x zip alone) |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345 | byte-identical on all five |
| page-built bundle vs CLI-built bundle | byte-identical on all five |
| preview render regression vs `v0.1.0`, 561 objects across three exports | **0 changed** |
| corpus census vs `v0.1.0` | **output identical** |
| residue sweep (`source_version`, `--source-version`, env var, `VERSION_FLOOR`, `UnsupportedExport`, `BadSourceVersion`, `parse_version`, `check_source_version`, `versions.json`, `8.10`) over `.py .md .yml .toml .html` | **no code hits**; only the CHANGELOG's own history and three absence assertions |
| dead-import scan (AST) over every touched module | none |
| legacy `--source-version` on the new CLI | loud usage error, exit 2, not silently accepted |
| stale settings file carrying `source_version: 8.6` (below the old floor) | inert; bundle byte-identical to the clean run |
| run header and `log-render` | no `source_version` field, no version prose; the input fingerprint is the version-free statement the CHANGELOG claims |
| corpus leak scan, 1886 uuid + 1886 compact + 1005 name needles vs the branch diff, every commit message and author line, and every text blob at HEAD | branch diff and messages: **0 instance hits**; HEAD tree: **1 hit, pre-existing, see W3** |
| em-dashes, added lines and whole tree | none |
| Python floor gate (`tests/test_python_floor.py`) | 67 passed |
| `vermin --target=3.9-` over `src tools tests` | clean (minimum 3.8) |
| `actionlint` both workflows | clean |
| README first command, verbatim, clean directory, real 8.18.7 export | `vcfcf-migrator ui my-export.zip` serves the page; no version control, no version word anywhere in the rendered HTML; the only thing between the user and Build is "pick at least one object" |

## Nothing load-bearing left with it

`bundle.py`, `containers.py`, `graph.py`, `selection.py`, `preview.py` and
`rawdoc.py` are **untouched** by the diff. The three things the import test
bought are all still there and still proved: the sharing-member synthesis for
a source that carries none (`bundle.py:274-306`, the one-rule-one-loop
comment intact), the zip directory entries (`bundle.py:171-198`,
`directory_entries`), and the `corpus-check` entry-list check that catches
their absence (`corpus_check.py:96`, `namelist_problems`). The last one was
mutation-tested: remove the fix and the check goes red.

Manifest counts, marker pass-through and document byte-identity all survive:
`corpus-check` reports 83/83, 83/83, 158/158, 49/49 and 434/434 documents
byte-identical, the same figures as the `v0.1.0` review.

## WARNING

### W1. `corpus-check` still advertises a verdict it can no longer emit

`src/vcfcf_migrator/corpus_check.py:10` and `:25-26`. The module docstring says
one line per zip is "ok with counts, **refused** with the reason, or error",
and closes with "Exit status: non-zero only on an error. A refusal is an
answer, not a failure: it is the tool declining to guess."

Both producers of a `refused` line were deleted with the feature: the
`UnsupportedExport` branch of `_check_one` and the `declared is None` branch
that returned "build needs a declared source version". Grep confirms the only
remaining return strings are `ok ` and `error `. The verdict class is
unreachable, and the exit-status paragraph now explains a rule in terms of a
thing that cannot happen. This is the docstring half of "a caller left behind":
harmless to run, wrong to read, and it goes in a PR body.

Fix: drop `refused` from the verdict list and rewrite the exit-status line as
"non-zero only on an error", or keep the sentence only if a refusal path is
deliberately being held open for M5.

### W2. The page-header test is now vacuous for the thing it is named after

`tests/test_log_wiring.py:402-425`,
`test_the_header_the_page_keeps_is_the_one_the_run_is_using`. Its docstring
still describes the real defect it was written for: `open_log` carries the
previous log's events into the new log and then writes the new header, and
first-one-wins left the stale header in place, so "after a truncation the log
stated a setting the run was not using".

The removed assertion was `headers[0]["source_version"] == "9.0.2"`, and it was
the **only** discriminator between the stale header and the fresh one. The page
header now carries tool version, core version, python, platform, `argv=["ui"]`
and cwd, all constant across every `open_log` in one session, so the surviving
`assert len(headers) == 1` cannot tell which header it is looking at.

Proved by mutation: `runlog.py:_keep` changed back to first-one-wins, and this
test **passes**. The regression it is named after is not detected by it any
more. The mechanism is still covered, by
`test_a_head_event_written_twice_keeps_one_slot`, which is the only reason this
is not blocking, but the end-to-end page-path guard is gone and the docstring
still claims it.

Fix: assert on something that differs between the two opens (the log level, or
`log.contents`'s `level` field, both of which the second `save_setting` changes
and the header block carries), or move the docstring's claim onto the unit-level
test that still earns it.

### W3. A corpus-harvested account uuid is committed at HEAD, outside this branch

`tests/test_runlog.py:249` carries the literal
`0c44e115dc214ea58a5601c22f18325b`. That is the compact spelling of
`0c44e115-dc21-4ea5-8a56-01c22f18325b`, which my scan found verbatim in the
marker member of `corpus/prod-9.1.1.0-2026-09-14-full.zip`. It is the same
value the design records under "The corpus leak, and what was done about it",
the built-in `admin` account id on vcf-lab-operations, the one whose dashed
form got `main` rewritten on Scott's "Write main so it's clean." The dashed
form is gone from the tree; the compact one is not.

It is **pre-existing**: it landed with the logging PR, is inside the `v0.1.0`
tag and source archive, and `git diff v0.1.0..HEAD -- tests/test_runlog.py` is
empty, so this branch neither introduced nor touched it. Under CLAUDE.md
delegation rule 9 that makes it a follow-up issue rather than a gate on this
PR, and I am not blocking on it.

It does need a decision, because the recurrence guard the design describes did
not catch it: the `v0.1.0` review's scan ran 342 to 556 needles and reported
zero hits, where a scan harvesting every uuid in every member of all five zips
in both spellings (1886 needles) finds it immediately. The needle set is the
thing to fix, not just the literal.

Fix: replace the literal with an invented 32-hex value (the test only needs a
compact uuid shape), and widen the leak scan's needle harvest to every member
of every corpus zip in both spellings.

## NIT

- **N1.** A `settings.json` written by `v0.1.0` keeps its `source_version` key
  for ever: `settings.save_settings` merges into the existing document and
  nothing reads or clears the key. Proved inert (a file carrying
  `source_version: 8.6`, below the old floor, produced a byte-identical
  bundle), so this is cosmetic, but the file an admin opens will keep claiming
  a setting the tool no longer has. Dropping unknown keys on the next save
  would close it.
- **N2.** `VCFCF_MIGRATOR_SOURCE_VERSION` is now silently ignored, while the
  flag is a loud usage error. The loud half is right. A scripted caller that
  exports the variable gets no signal, which is the correct treatment of a
  removed environment variable and is noted only so the asymmetry is on the
  record.
- **N3.** `corpus/versions.json` is left sitting in the corpus directory and is
  never read or mentioned. It is the admin's own file and the tool never wrote
  it, so nothing needs doing; a line in the release notes telling an admin they
  can delete it would be kind.
- **N4.** No negative test pins the deletion at the CLI surface, for example
  `main(["--source-version", "9.0.2", "inspect", zip]) == 2`. The three absence
  assertions (`test_cli.py:60,77`, `test_log_wiring.py:89`) would catch the
  feature returning through the reader or the header, so this is belt and
  braces rather than a hole.

## If shipped as-is

An admin downloads the next binary and types `vcfcf-migrator ui my-export.zip`.
The page opens, the tree is there, and the only thing standing between them and
a bundle is picking an object. Every bundle the tool writes is the same bytes
`v0.1.0` wrote, including from an 8.18.7 export, so nothing that has been
proved against a live instance changes. The gate that could have refused an
export that would have worked is gone, and no gate that was earning its keep
went with it.
