# vcommunity fix/builtin-view-ids-e1 review, 2026-11-12

> Editor's note (committer, 2026-11-12): paths such as `scratchpad/...`, `venv2`,
> build log names and `~/.docker/config.json` refer to the reviewer's session
> scratch and local machine and are not in this repository. Every finding below
> was addressed on the branch before the upstream pull request was opened.

- **Fork:** `content/sdk-adapters/vcommunity/` (clone with remote `rahabok` = e1-rahabok/VCF-vCommunity-Adapter)
- **Branch:** `fix/builtin-view-ids-e1` at `ad6752e`, three commits (`65701c8`, `ec64110`, `ad6752e`) on `rahabok/main` `0ef8586` (0.8.1)
- **Scope reviewed:** e1-rahabok/VCF-vCommunity-Adapter#91. Drop 19 ViewDefs that copy built-ins, re-id 98 (same ids as the reviewed 0.3.x branch `fix/builtin-view-ids` `91169cf`) plus the 3 VCF Management Services views, repoint references, reconcile the two copies of old `9a77a4b5`, test, docs. Content only, no code, no version bump. Draft PR body: scratchpad `e1_port/PR_BODY.md`.
- **Checklist:** `knowledge/context/python_integration_sdk.md`. Dimensions 1, 2, 4, 5 and 8 do not apply (no app code, no workflow). Sibling report: [vcommunity-fix-builtin-view-ids.md](vcommunity-fix-builtin-view-ids.md).
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 4 WARNING, 7 NIT)

The content change is correct. Every check I ran on it passed: none of the 120
ids is still defined, nothing dangles, the only change inside a re-id'd view is
its id, and the pak carries the branch content byte for byte. The findings are
in the docs and the PR body. The 8.18.7 guidance steers users who upgraded into
the same deletion that #91 reports. The upgrade text also counts 117 where this
line shipped 120, and it does not say that the 9.x upgrade breaks 11 widgets in
the pack's own dashboards.

## Claims check

All conclusions come from my own scripts (ElementTree, json, text; `python3 -I`),
run on `git archive` copies of `rahabok/main` and the branch, kept in
`scratchpad/rev_e1/`. The author's TSVs were used only as the list of ids to check.

| Check | How | Result |
|---|---|---|
| 120 ids no longer defined | Every `ViewDef` under `content/` on base and branch | Base: 189 ids / 255 copies, all 120 present and all 120 collide. Branch: 170 / 234, 0 of the 120 defined, 0 collisions with 9.1.1 (851) or 8.18.7 (778) |
| Stray occurrences | Case-insensitive fixed-string scan of the whole branch tree (content, app, tests, tools incl. PowerShell, docs, README) for all 120 | 120 in `tests/test_view_ids.py` (the list). 11 more, all `viewDefinitionId` references to 9 of the 19 dropped ids, in 5 dashboard files. None of the 101 replaced ids appears anywhere else |
| 3 VCF MS ids | Exports | All three are in 9.1.1, none in 8.18.7, as the docs say. Components is equal to the 9.1.1 built-in (strict, minus control ids); Nodes and Volumes differ |
| References resolve | Every `viewDefinitionId` (215), every report `Section` with `ContentType` View (11) or Dashboard (34) | Branch: all resolve to a shipped view or dashboard, or to a built-in view present in BOTH 9.1.1 and 8.18.7 (25 built-in refs: 16 pre-existing + 9 dropped ids). 0 resolve on one version only, on base or on branch. No report references any of the 120 |
| Only intended changes | Rebuilt each changed file from base: removed the 21 dropped `ViewDef` blocks, applied the old->new map as text, compared with the branch | 17 dashboards, 3 VCF MS files, Set 1: byte-identical. Set 2/3/4: identical except one blank separator line per removed block. Collection01: the same, plus the one `9a77a4b5` block. No CRLF/BOM change |
| Re-id'd bodies | Per old id, canonical XML of every copy on base vs the new id on branch, per file | 100/101 identical apart from the id. `9a77a4b5` -> `f0a5f04e`: Set 4 copy unchanged; Collection01 copy now equals the Set 4 copy, including control ids (it gains the Encryption and Snapshot Consolidation columns) |
| Other views untouched | Same, for the 69 views outside the 120 | All unchanged, none vanished, no new unaccounted id |
| The 19 dropped | Element diff vs both exports, ignoring title, description, `localizationKey`, control/data-provider ids | All 19 equal on both versions, except an explicit `isSum=false` in `11dd432d`, `6dbbe2bc`, `0a898851` where the built-in omits it (a default; see sibling report §isSum). 21 blocks removed (two ids in two files). No properties or localization file refers to a view id |
| New ids | `uuid.UUID`, exports, base tree | 101 valid canonical v4, unique, 0 hits in either view export, the 9.1.1 dashboard and report exports, or anywhere in the base tree. Each id has the same value in every file that defines or references the view (text-map rebuild above is exact) |
| Same ids as 0.3.x | Extracted `fix/builtin-view-ids` (`91169cf`) | 98/98 new ids are defined there with the same title; none of the old ids remains there; the same 19 are dropped there |
| Other id collisions | Pack dashboards (52) vs 9.1.1 dashboards export (179); pack reports (16) vs 9.1.1 reports export (62) | 0. **Not covered** by the inputs: 8.18.7 dashboards and reports, and super metrics, alert and symptom definitions on either version. The 2 SMs are a subset of the 0.3.x tree's, which the sibling review checked against a 9.1.1 SM export (not rerun). The alert and symptom ids differ from 0.3.x and are unchecked |
| Well-formed | Parsed every XML and JSON under `content/` | 0 failures |
| New test fails on base, passes here | Copied `test_view_ids.py` into the base tree | Base: 2 of 3 fail (VCF MS + 117 clashes; `9a77a4b5` copies differ). Branch: 3 pass |
| pytest | `python -m pytest tests` in the clone, venv2 (3.12.13) | 487 passed, 2 failed (`test_pinned_rest_login_*`, `CERTIFICATE_VERIFY_FAILED`), as reported. Base archive: the same 2 fail; `test_docs_links` also fails there only because a `git archive` has no `.git` |
| ruff | `ruff check app tests` from `Management Pack` | Clean. `ruff check .` at the root: 2 pre-existing findings in `tools/importer/importer.py`, untouched |
| Link check | `tools/check-docs/check_links.py` | 0 broken |
| Pak = branch | Unzipped `vCommunity_0.8.1-fix-builtin-view-ids-e1.pak`, sha256 of every file | 78/78 content files match a branch file byte for byte; only the 14 empty `.gitkeep` files are absent. `manifest.txt`, `eula.txt`, `resources.properties` identical. Build workspace = branch plus `config.json`/`connections.json` (no secrets) and logs |
| `-releasedimage` pak | Full compare with the built pak and with the released `vCommunity_0.8.1.pak` | Only `vCommunity.conf` differs: REGISTRY/REPOSITORY/DIGEST point at the released `ghcr.io/e1-rahabok/vcf-operations-vcommunity@sha256:78fee0d0...`, equal to the 0.8.1 release apart from line endings. Resource model in `describe.xml` equals the 0.8.1 release (326/326) |
| `mp-build` | Not rerun (registry start was denied on the sibling review; not retried) | Not reproduced. Log shows `Build Succeeded` against `127.0.0.1:5000` |
| Secrets, hosts, em-dashes | Diff, commit messages, PR body, build logs | 0 em/en dashes. No secret. One private IP address [address removed by the committer, 2026-11-12] shows in `+` lines, but it is pre-existing upstream content moved by the diff (N7) |

## BLOCKING

**B1. The 8.18.7 guidance leads upgraded users into the #91 deletion.**
`docs/installation-guide/installation.md:79`, `:84`; `docs/troubleshooting-guide/symptoms.md:181`; PR body line 19.
On 8.18.7 the measured upgrade keeps the old copies. They sit under the 117
built-in ids, so after the upgrade the built-in views are still overwritten.
Line 79 says "The built-in views are no longer overwritten", which is false for
these users. Line 84 and the symptom's "What to do" say only that the old copies
"are deleted when the pack is uninstalled". The duplicates are the user's only
visible symptom, so uninstalling reads as the remedy. Uninstalling deletes the
117 built-in views, which is the bug this PR fixes.
*Fix:* for 8.18.7, say that after the upgrade the built-in ids still hold the
pack's old copies, so the built-in views stay replaced, and that uninstalling
deletes them. Give the same remedy as 9.x: import the views from a clean export
of the same version. Mark it untested on 8.18.7 (W3). Do not present uninstall
as the fix. Line 79 must say which versions it applies to (fresh installs and
9.x upgrades).

## WARNING

**W1. On this line the count is 120, not 117, on 9.1.1.**
`installation.md:73`, `:83`; `symptoms.md:177`, `:179`; PR body line 18.
Tags `v0.4.2` to `v0.8.1` also ship the three VCF Management Services ids, which
are built-in views on 9.1.1. By the same measured rule (the upgrade removes
content the new version no longer ships), an upgrade from 0.4.2 or later on
9.1.1 also deletes the built-in Nodes, Volumes and Components views. Line 73
says 0.8.1 shipped "117", and the table says the upgrade deletes "the 117".
*Fix:* "117, and on 9.1.1 also the three VCF Management Services views (expected
from the 0.3.1 measurements, which did not include them)". Say that the restore
covers them too.

**W2. A 9.x upgrade breaks 11 widgets in the pack's own dashboards. The docs do not say so.**
`installation.md:75`, `:83`; `symptoms.md:177`.
The 19 dropped ids also leave the pack, so the 9.x upgrade deletes them as
well. The pack's dashboards point at those ids. Until the user restores the
built-ins, these widgets show "The view does not exist":

| Dashboard | Widgets |
|---|---|
| VM Capacity 2.0 | 3 |
| vSphere Cluster Performance 2.0 | 3 |
| vSphere Network Configuration 2.0 | 2 |
| `To be used in reports/Input dashboards` | 2 (so the VOA reports are hit too) |
| vSphere Cluster Capacity 2.0 | 1 |

Line 75 ("The pack's dashboards use the built-in view") reads as if those
widgets are unaffected.
*Fix:* say it in both places. A design note for the orchestrator, not a demand
on this branch: dropping is what causes this self-breakage. Re-id'ing the 19
like the others would avoid it, at the cost of 19 more pack copies. The scope
chose to drop them, and the 0.3.x branch did the same.

**W3. The restore procedure is stated as fact but was never tested.**
`installation.md:88`; `symptoms.md:181`; PR body line 18.
The measurements cover upgrade and uninstall only. Nobody has tested that
importing a clean export brings the views back, or that it does so without side
effects. Importing a full view export also overwrites any edits the user made to
built-in views.
*Fix:* exercise it in the pending 9.1.1 lab run, or label it "not tested". Say
to import only the deleted views when possible.

**W4. The releasedimage pak is not "this branch's pak".**
It carries this branch's content on the released 0.8.1 image. `rahabok/main` has
6 app files changed since `v0.8.1` (including #90). The resource model is
identical and the `definition.py` change is a comment, so it is sound for the
content test now running. Report that run as "branch content on the 0.8.1
image". Both paks also say 0.8.1, the same version as the release. An upgrade
test over an installed 0.8.1 needs a bumped test manifest, as
`test/upgrade-0.3.2` did for 0.3.x.

## NIT

- **N1.** PR body line 9 ("none has a column, filter, sort or presentation difference"), commit `65701c8`, and `installation.md:75` ("differed only in title or description"): three of them (`11dd432d`, `6dbbe2bc`, `0a898851`) also carry an explicit default `isSum=false`. Add "(plus one explicit default value in three)".
- **N2.** PR body line 11: the two columns are displayed as "Encryption" and "Snapshot Consolidation" (keys `config|encryptionState`, `config|disk_consolidation_needed`), not "Encryption State and Disk Consolidation Needed".
- **N3.** `installation.md:73` "Versions up to 0.8.1" and `symptoms.md:177` "0.8.1 or earlier": `v0.1.1`/`v0.1.2` ship none of these ids and `v0.1.4`/`v0.1.5` ship 6. From `v0.1.6` on, all 117 ship, and from `v0.4.2` the 3 more as well.
- **N4.** `installation.md:77` is garbled: "were added in this repository, and are not among the 117, with the ids of views that are built into VCF Operations 9.1.1". Suggested: "This repository added three more views ... under ids of views built into 9.1.1; they are not among the 117."
- **N5.** `Management Pack/tests/test_view_ids.py:20-142`: the items are not indented inside the inner `(`, and `frozenset((...))` could be `frozenset({...})`. `ruff check` is clean and the repo is not `ruff format`ed (37 files), so this is cosmetic.
- **N6.** The test does not protect the drop. A later edit could re-add a `ViewDef` for one of the 19, or repoint a widget to an id that no longer exists, and nothing would fail. Consider asserting that every `viewDefinitionId` resolves to a shipped `ViewDef` or to the 25 known built-ins.
- **N7.** Pre-existing, out of scope, raise separately: `View - Set 3.xml` (5) and `vSphere Network Configuration 2.0.json` (1) hard-code a private IP address in `host:<ip>|...` attribute keys [address removed by the committer, 2026-11-12]. Also, 6 dashboard navigation targets in Critical Business Applications and vSphere Cluster Performance 2.0 are neither shipped dashboards nor 9.1.1 built-ins. Both are the same on base.

## If shipped as-is

- **Fresh installs and uninstalls** no longer touch built-in views on 8.18.7 or 9.1.1, and the pack's dashboards render the same.
- **9.x upgrades from 0.4.2 to 0.8.1** lose 120 built-in views, not the 117 the docs name. They also lose 11 widgets in five of the pack's own dashboards (and in the VOA report inputs), with only an untested restore step to go on.
- **8.18.7 upgrades** keep the built-in views overwritten. A user who uninstalls to clear the duplicates, as the troubleshooting entry implies, deletes all 117.
