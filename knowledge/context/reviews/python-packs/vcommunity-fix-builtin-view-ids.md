# vcommunity fix/builtin-view-ids review, 2026-11-12

- **Fork:** `content/sdk-adapters/vcommunity/` (sentania-labs/VCF-Operations-vCommunity, fork of vmbro/VCF-Operations-vCommunity)
- **Branch:** `fix/builtin-view-ids` at `5d2edd4`, two commits on `main` `9e27d7d` (= upstream/main, and `Management Pack/` is identical to tag `v0.3.1`)
- **Scope reviewed:** upstream issue vmbro/VCF-Operations-vCommunity#99. Drop 19 ViewDefs, re-id 98, repoint dashboards, align the two copies of old `9a77a4b5`, README note. Content only.
- **Checklist:** `knowledge/context/python_integration_sdk.md` (code dimensions 1-5 and 8 do not apply: no Python, no workflow touched). Lesson: `knowledge/lessons/pak-content-must-not-reuse-stock-ids.md`.
- **Verdict:** CHANGES REQUESTED (0 BLOCKING, 4 WARNING, 5 NIT)

The content change holds up. Every check I ran independently passed. No
shipped view id collides with 9.1.1 or 8.18.7. Nothing dangles. Reversing the
swaps gives back main byte for byte, apart from the dropped blocks and the one
intended block. The 19 drops differ from the built-in only in title and
description, plus `isSum=false` on 3 of them. The findings are in the README
note and the PR body. One README sentence gives advice that does not restore
anything, and the README says nothing about upgrading, which is how most users
will get this change.

## Claims check

All checks used my own scripts (ElementTree and text, `python3 -I`) on
`git archive` copies of `main` and the branch. The author's scripts and TSVs
were used only as the list of what to check.

| Claim | How rerun | Result |
|---|---|---|
| 179 ViewDefs on main, 117 under built-in ids | Parsed every `*.xml` under the tree; compared with 9.1.1 baseline (851 views) and 8.18.7 (778) | 179 ids / 245 copies; 117 collide, the same 117 on both versions. Baselines are clean: all 117 carry `localizationKey` (stock), none of the 62 pak-only ids is present, 0 "vcommunity" strings |
| No shipped id collides after the change | Same | 160 ids / 224 copies; 0 in 9.1.1, 0 in 8.18.7 |
| 98 new ids, valid v4, unique | `uuid.UUID(x).version == 4`, lowercase round-trip; grep of main tree, both view baselines, and every 9.1.1 baseline export (alerts, symptoms, dashboards inner zip, reports, SMs, policies, groups) | All valid, unique, 0 hits anywhere |
| Same new id for every copy; mapping correct | For each old id, the main copies vs the new-id copies, per file, canonical XML minus the ViewDef id | 98/98 match file sets and content, except the intended `9a77a4b5` Collection01 copy. Canonical forms of the 98 are unique, so the match is unambiguous |
| No old id remains | Regex scan of every file in the branch tree for all 117 old ids | **9 remain**, all of them dropped ids referenced by pak dashboards, which is by design. None of the 98 replaced ids remains (see W3) |
| Every `viewDefinitionId` resolves | Walked every `type: View` widget (210) | main: 195 pak + 15 built-in. Branch: 184 pak + 26 built-in (the 15 plus 11 refs to 9 dropped ids). 131 refs to new ids. 0 dangling; every built-in ref exists in both 9.1.1 and 8.18.7, with the same subject kind and presentation type on both |
| Reports | `Section/ContentType=View` keys (11) | All resolve to pak views, unchanged files, none referenced a colliding id |
| Dashboards byte-identical apart from swaps | Reverse substitution new->old on the branch file, byte compare with main | 10/10 identical (no-trailing-newline state preserved) |
| Kept ViewDefs byte-identical | Split each report XML into `<ViewDef>` blocks and gaps; rebuilt main minus dropped blocks; compared with reverse-swapped branch | Set 1-4: identical text, order preserved. Collection01: only the `9a77a4b5` block differs. No CRLF, no BOM, encodings unchanged |
| Collection01 copy of `9a77a4b5` now equals Set 4 copy | Byte compare of the two `f0a5f04e` blocks | Identical (31417 bytes). Set 4 copy is a superset: it adds the Encryption and Snapshot Consolidation columns. The 9.1 after-install export shows the Set 4 copy is the one that won (control ids `_67`/`_68`, `encryptionState` present). No duplicate Control/DataProvider ids in any file |
| 62 non-colliding views untouched | Canonical compare per file | Unchanged, including both `Cluster_VIB_Content.xml` copies (its 5 ids are pak-only; file untouched) |
| 19 drops: 8 identical, 11 title/description only | Semantic diff vs both baselines, ignoring Control/DataProvider id values and `localizationKey` attributes | Confirmed on both versions. The only other difference: explicit `buckets-control isSum=false` in the pak copy of `11dd432d`, `6dbbe2bc`, `0a898851` where the built-in omits it (see below) |
| `72a85fd6` copies differ only in Control/DataProvider ids | Normalized diff | Confirmed, same as main. Harmless: those ids are local to one ViewDef and the content is equal, so whichever copy wins is the same view |
| No localization keyed by old ids | Grep | All 83 `localizationKey` attributes on main sat in the 8 identical Telegraf views in Set 4, all dropped. Branch has 0. No properties file refers to a view id |
| Non-view stock ids | Pak dashboard, report, SM, symptom, alert ids vs every 9.1.1 baseline export | 0 collisions, so #99 covers the whole problem on 9.1.1 |
| Built pak = branch content | Unzipped `...0.3.0-pr-fix-builtin-view-ids.pak` and compared each `content/` file with the branch | 113/113 byte-identical |
| `-releasedimage` differs only in registry lines | Full file-by-file compare of the two paks, including inner `adapter.zip` | Only `VCFOperationsvCommunity.conf` differs (REGISTRY/REPOSITORY/DIGEST set to the released `ghcr.io/vmbro/vcf-operations-vcommunity@sha256:579d8d7b...`) |
| `mp-build` succeeds | **Not reproduced.** My attempt to start a throwaway `registry:2` and build a copy was denied by the permission system | Accepted as not reproduced. The pak's content is verified above; the build only packages it |
| No workaround leaks into the branch | `git diff --name-only`; grep of the diff for registry hosts, paths, credentials, names | 16 files, all in scope. Dockerfile, conf, manifest untouched. 0 hits. `~/.docker/config.json` holds no entry for the throwaway registries |

### Is `isSum` absent the same as `isSum=false`?

The test was not run live. The evidence supports it:
- In the 9.1.1 export, 158 built-in buckets-controls omit `isSum`, 49 say `false` and 10 say `true`. Every buckets-control in the pak (135) says it explicitly. That is what the UI writes when a view is saved, so the pak copies are re-saves of the built-in.
- All three are retitled re-saves of the built-in with nothing else changed. If an absent `isSum` loaded as `true`, re-saving would have kept `true`.
- The built-in description of `11dd432d` reads "Count of VMs, grouped by the capacity remaining". That is a count, not a sum.

The residual risk is low. To close it, render one of the three widgets on a
clean instance before and after.

### The releasedimage paks as a test vehicle

They are sound for testing content. The registry rewrite is the only change.
The resource model in `describe.xml` is identical to the released 0.3.1 pak:
200/200 kinds and attributes. Only the UnitType block order and its `nameKey`
numbers differ. The SDK reorders that block on every build: the PR build and
the test build differ from each other in the same way. `resources.properties`
is regenerated to match.

Two caveats:
- The image is the released 0.3.1 image, not one built from this tree. Upstream's 0.3.1 pak manifest says `0.3.1`, but tag `v0.3.1` says `0.3.0`, so the release came from a tree that is not the tag. That does not matter for a content test.
- Install `0.3.2-test-upgrade-releasedimage` over 0.3.1, not the `0.3.0` variant. The `0.3.0` one is a downgrade against the installed 0.3.1.

The branch carries none of this. `test/upgrade-0.3.2` changes only `manifest.txt` and `version.txt`.

## WARNING

**W1. README: "If you uninstall such a version, export your views first." Following it restores nothing.**
`README.md:53`. While an old version is installed, the 117 built-in ids hold
the pack's copies. An export taken then contains those copies, not the
built-ins. Uninstall deletes only ids the pack shipped, so the user's own views
need no backup either. Importing that export afterwards puts the pack's
modified views back under built-in ids. For example, the pie chart that became
a donut, and the retitled lists.
*Fix:* remove that sentence. Keep the restore sentence and make it the
instruction: "Before uninstalling, get a view export from an instance of the
same VCF Operations version that never had this pack; import it after
uninstalling."

**W2. README and PR body say nothing on upgrading from an old version.**
Most existing users will upgrade, not uninstall. It is the one path not tested
here. Two outcomes are plausible.
- If an upgrade keeps the old content, the 117 built-in ids keep the pack's copies. The 98 re-id'd views then appear twice under the same title, the old copy at the built-in id and the new one, and the stock dashboards keep showing the pack's versions.
- If an upgrade removes content dropped from the pack, the 117 built-ins disappear at upgrade time.

Either way the README needs a sentence. The PR body's "not covered here" is
honest, but a maintainer will ask.
*Fix:* hold the README note and the PR body until the live
install/upgrade/uninstall test is back. Then state the observed upgrade outcome
and what to do about it, for example "after upgrading, import built-in views
from a clean export". Claim only what that test showed.

**W3. PR body: "No old id remains anywhere in the repository." This is false as written.**
Nine of the old ids remain on purpose: the dropped ones that pak dashboards
still reference (`0a898851`, `11dd432d`, `40152c12`, `653ba701`, `6dbbe2bc`,
`7bcdb50d`, `a62de769`, `b963d4b9`, `c9fe7a11`). A maintainer who greps for one
will find it.
*Fix:* "None of the 98 replaced ids remains anywhere in the repository; the 19
dropped ids are still referenced where dashboards used them, and now resolve
to the built-in views."

**W4. Version: `manifest.txt` reads 0.3.0, but the released pak is 0.3.1.**
The README says "Versions up to 0.3.1" and "In this version". If upstream builds
this branch as it stands, the result is 0.3.0. That is a downgrade against the
release users have installed, and Ops will show the same version number as an
affected build. A version bump is out of scope by design, and that is right.
*Fix:* add a line to "What to check" in the PR body: "`manifest.txt` and
`conf/version.txt` still read 0.3.0 while the 0.3.1 release pak reads 0.3.1;
bump past 0.3.1 before releasing." Optionally, have the README name the version
once it is known.

## NIT

- **N1.** PR body: "11 differ only in title or description". Three of the 11 also carry an explicit default `isSum=false` (`11dd432d`, `6dbbe2bc`, `0a898851`). Say "only in title or description (plus one explicit default value in three)" so nobody finds it and loses trust in the rest.
- **N2.** README "Versions up to 0.3.1": `v0.1.1`/`v0.1.2` ship none of these ids and `v0.1.4`/`v0.1.5` ship 6; from `v0.1.6` on, all 117. "Versions 0.1.4 to 0.3.1" is exact. Either wording is acceptable.
- **N3.** The 19 built-ins were checked on 8.18.7 and 9.1.1 only. `vcops_minimum_version` is 8.18.0, and 8.18.0-8.18.6 and 9.0.x were not checked. All 19 are long-standing stock views with the same subject and presentation on both checked versions, so the risk is low. The PR body could say "checked against 8.18.7 and 9.1.1 exports" in the drops bullet, as it already does for the collision check.
- **N4.** The PR body could add one clause to the `9a77a4b5` bullet: the Set 4 copy is also the superset, with two more columns (Encryption, Snapshot Consolidation). That answers "why that one" without the reader having to diff.
- **N5.** Not this branch's problem, but worth saying to the maintainer separately: the upstream `Dockerfile` base `projects.registry.vmware.com/.../base-adapter:python-1.0.0` no longer resolves (`manifest unknown`, `mpbuild_attempt1.log`), so the tree does not build as checked in. Do not fix it in this PR (one concern per branch).

## If shipped as-is

New installs and clean uninstalls on 8.18.7 and 9.1.1 no longer touch built-in
views. Pack dashboards render the same. Ten widgets now show the built-in title
and description of 9 views instead of the pack's retitle. Users who upgrade
from 0.3.1 get no guidance, and the README's "export your views first" leaves
them with the pack's copies where built-ins should be.
