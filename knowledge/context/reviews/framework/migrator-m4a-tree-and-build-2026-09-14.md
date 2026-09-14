# Framework review: migrator M4a, tree and build

- Repo: `content/migrator` (vcf-cf-migrator), branch `feat/m4a-tree-and-build`, 9 commits over `main`
- Reviewed: 2026-09-14
- Spec: `knowledge/designs/content-migrator-v1.md` (Pass-through is the contract; subsetting; Versions; M4/M5)
- Prior review: `knowledge/context/reviews/framework/migrator-m3-skeleton-2026-09-14.md`
- Verdict: **CHANGES REQUESTED** (4 BLOCKING, 7 WARNING, 3 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | 91 passed, 0 failed, none reading `corpus/` |
| select-all over all five corpus zips | builds; item counts equal source (83, 83, 158, **48**, 430) |
| document byte identity (my own extractor, not the tool's) | 552 documents compared across five zips, 0 document mismatches |
| container identity on select-all | **1 mismatch**, 8.x `notificationrules.json` (B4) |
| closure audit, every node in every zip | **symptom to supermetric edge missing**, 3 of 5 zips (B3) |
| corpus-check | exit 0, 5 ok lines |
| refusal paths | unknown uuid exit 1 no bundle; no `--source-version` exit 1 no bundle; below floor exit 1 |
| corpus-leak scan, all 12 revs, all 44 blobs | **2 real leaks found** (B1, B2) |
| em-dashes in added lines | none |

## BLOCKING

### B1. A real corpus owner uuid is on pushed `main` and inside release tag `v0.0.1`

`0c44e115-dc21-4ea5-8a56-01c22f18325b` is verbatim from
`corpus/prod-9.1.1.0-2026-09-14-full.zip`: it is the `admin` entry's `userId` in
`usermappings.json`, the marker file's content, the `modifiedBy` on super metrics,
and the largest `dashboardsByOwner` owner in `configuration.json`.

It entered at `31f38a6` (m3 branch), survived `7e6b0f9`, and was **merged to
`origin/main` in `3d6268a` and is reachable from tag `v0.0.1`**. On this branch it
rides `935b95b` through `d385b8e` and is removed only at `163dd8a`.
`b58a71ee-e909-5b40-a355-9e199e6f0f53` (the other `OWNER`) has the same history;
the author's own commit message states both were lifted from corpus zips.

The author's framing ("earlier commits on this branch") understates it. Rewriting
this branch does not remove it. The published GitHub source archive for `v0.0.1`
contains `tests/fixtures/make_export_fixture.py` with the value. The wheel does not
(`packages.find` takes `src/vcfcf_migrator*` only), so this is a git-history and
source-archive exposure, not a binary one.

This is above the author's and this gate's authority to resolve. It needs Scott's
verbatim decision (global rule 12) between rewriting `main` plus re-cutting `v0.0.1`,
or accepting a single opaque user uuid as published. Do not open the PR before that
decision is recorded.

Fix: escalate, one sentence, before anything else.

### B2. Real corpus display names and uuid prefixes in this branch's README

`d385b8e` put into `README.md` the real super metric names `Failed ESXi Host
Capacity` and `CPU Free after 1 Failed Host`, and the real uuid prefixes `303829ed`
(an owner), `e7518cbe`, `47a9fcc8`, all verbatim from
`corpus/scott-b-9.0.2-2026-09-14.zip`. `163dd8a` replaced them, so HEAD is clean, but
`d385b8e` still carries them.

Unlike B1 this is branch-local and unpushed, so the fix is available and cheap.

Fix: rewrite `935b95b..HEAD` so no commit ever holds the values (reword `d385b8e`
with the sanitized README and drop `163dd8a`'s README hunk), before the PR opens.
Not another commit on top.

### B3. Closure misses the symptom to super metric edge, so bundles reference what they do not carry

`graph.py:_REF_EXTRACTORS` has no entry for `symptom`. A symptom whose condition is
on a super metric attribute carries `Super Metric|sm_<uuid>` in its document and that
edge is never walked. Proven on 3 of 5 corpus zips.

Worked case, `devel-9.0.2.0-2026-09-14-full.zip`:

```
$ echo alert:AlertDefinition-b629aa88-1672-4c46-b8ae-584f87143646 > sel.txt
$ vcfcf-migrator --source-version 9.0.2 build ... --select sel.txt --out alert-subset.zip
selected: 1 named, 2 after closure
carrying: alert=1, symptom=1
```

The carried symptom `[VCF Content Factory] Cluster Storage Paths Inconsistent`
references `sm_b394eb82-d4d4-47d1-bd7e-0ef267457e52`
(`[VCF Content Factory] Storage Path Variance (max-min)`), **which is in the same
export** and is not carried and is not reported as missing. `g.edges[symptom:...]`
is `[]`.

Spec, subsetting paragraph: "A bundle whose documents reference objects it does not
carry is the one failure mode subsetting can introduce on its own, and the walker is
what prevents it." `graph.py`'s own module docstring gives that same sentence as the
reason the three extra edges were added. This is the fourth one, on the same
evidence, missed.

Fix: add `"symptom": lambda entry: _sm_refs(entry.raw, "symptom condition Super
Metric|sm_")` to `_REF_EXTRACTORS`, and a test that selecting the alert above closes
to 3.

### B4. select-all does not round trip the 8.x `ruleNameToTemplateNameMap`

`containers.py:_filter_name_map` rebuilds the map from a parsed value and always
emits `entry` as a list. The 8.x export writes it as a single object.

```
source (scott-8.18.7): [{"entry":  {"string": ["Guest OS Experiencing CPU Queue", "Email Template"]} }]
bundle:                [{"entry": [{"string": ["Guest OS Experiencing CPU Queue", "Email Template"]}]}]
```

On a select-all, where nothing is dropped, the tool still changes the 8.x container's
shape. The author demonstrably knows this distinction is load-bearing:
`_nested_list` exists solely to preserve object-versus-list for `NotificationRule`
and `NotificationTemplateData` ("8.x writes one object per entry, 9.1.1 writes one
entry holding the list"). The same care was not applied one function away. Whether
the 8.x importer accepts the list shape is unproven, and under the skeptic default
unproven is a finding, on the version the spec's own Versions row singles out.

The document byte-identity claim survives, because the map is container material.
The round-trip claim does not.

Fix: preserve the source shape, emit the single object when the source held one, and
skip the filter entirely when nothing is dropped. Add an 8.x-shaped name map to the
fixture (it currently carries only the 9.x list form, which is why this survived).

## WARNING

- **W1. `corpus_check.py:check_one` compares documents only.** It diffs
  `containers.documents()` on both sides, so it verifies documents and is blind to
  container-level material, which is the one place the tool re-serializes. It printed
  `ok ... 49 documents byte-identical` for the very zip carrying B4. The regression
  tier does not cover the thing most likely to regress. Fix: also compare the parsed
  top-level container structure on select-all, where source and bundle must agree.
- **W2. `rawdoc.py` has no unit tests.** No test file imports it. The module the
  whole pass-through contract stands on is exercised only through one fixture, and
  the self-closing-adjacency bug fixed on this branch has no direct regression test,
  so a future fixture edit silently removes the coverage. I verified by hand that the
  slicer is correct for CDATA containing `</V>`, nested same-name elements, `>` and
  `/>` inside attribute values, comments, processing instructions, entities and UTF-8
  multibyte. Fix: `tests/test_rawdoc.py` pinning those shapes and both fixed bugs.
- **W3. `XmlContainer.rebuild` is not encoding-safe.** It emits `b"\n"` separators and
  `f"</{tag}>".encode("ascii")` close tags, which corrupt any document not in an
  ASCII-compatible encoding, while the module docstring claims the XML side is never
  decoded precisely so other encodings survive. Latent only: every content XML in all
  five corpus zips is UTF-8. Fix: narrow the docstring claim, or refuse a non-UTF-8
  declaration outright.
- **W4. Namespace-prefixed tags never match.** `expat.ParserCreate()` with no
  namespace separator reports `n:ViewDef`, so `wanted_tags=["ViewDef"]` finds nothing.
  Fails safe (the member lands in "carried, not inspected" rather than being carried
  empty) and no corpus XML uses a prefixed root. Record the limit in the docstring.
- **W5. `_filter_name_map` drops silently.** Any key other than `entry` in a block, any
  block with no kept pairs, and any pair whose `string` is not a 2-list are dropped
  with no note, even on select-all. Fix: carry unrecognized material through, or say
  in the build report what was dropped.
- **W6. The marker's content is the source instance's user uuid**, copied byte for
  byte (`bundle.py`). The spec proves the marker *filename* is format-only, and the
  corpus confirms it (identical across all five zips), but the *content* differs per
  instance (five distinct uuids). The factory's own packagers write the target owner's
  uuid there (`src/vcfcf_core/dashboards/packager.py`,
  `src/vcfcf_core/reports/render.py`). Pass-through says copy it; whether the target
  accepts a foreign owner uuid is an M5 live question. Fix: name it in the M5
  verification list.
- **W7. Claimed counts do not match.** The 8.x zip is **48** items, not 49; 49 is its
  *document* count (its one notification template appears in both
  `notificationrules.json` and `payloadtemplates.json`). The author drew exactly this
  distinction for scott-b's 434 and then quoted the document count in the item list.
  Fix the number in the PR body.

## NIT

- **N1.** `rawdoc.xml_container`'s comment says that with no match it "still report[s]
  the root so a caller can write an empty container of the right shape". It does not:
  `ancestors = []` yields no root tag and `rebuild` returns the prologue alone, which
  is not well-formed. Unreachable today (`build_bundle` never rebuilds an unpicked
  container and guards on empty bytes). Fix the comment or the behaviour.
- **N2.** `ui.py` puts the `PAGE_PENDING` constant above the `export_reader` import
  block, splitting the imports.
- **N3.** Three page buttons whose only action is to answer "run it on the command
  line for now". Honest and documented, so not a silent downgrade, but a button that
  cannot do its job reads worse than no button until the next PR lands.

## Settled, not findings

- **`configuration.json` without the source signature is safe, and does not need to go
  to Scott.** Known-good reference: the factory's own proven content-import path
  (`src/vcfcf_core/dashboards/packager.py:157`,
  `src/vcfcf_core/reports/render.py:150`, `src/vcfcf_packaging/templates/install.py`)
  writes `configuration.json` with no signature, the same `indent=3`, the same
  `"type": "CUSTOM"` and the same `dashboardsByOwner` shape, and those zips import.
  I verified the migrator's manifest counts equal what is carried (2 dashboards,
  2 views, per-owner counts) on a real two-owner subset. Worth citing the reference in
  the build note so the question stays closed.
- **`versions.json` is clean.** Read-only (`read_versions` only reads), inside the
  gitignored `corpus/`, absent from every blob in every commit, and its absence
  degrades to a refusal line with exit 0, not an error.
- **The three added edges are real.** Verified against the corpus: dashboard straight
  to super metric via `sm_<uuid>` widgets; rule to outbound endpoint via `PluginID`
  (`StandardEmailPlugin/...`, `WebhookPlugin/...`, `GenericRestPlugin-slack/...`);
  rule to template via `ruleNameToTemplateNameMap`. My closure audit found no other
  missing edge class besides B3.
- **Two-owner selection is correct.** For shared uuid
  `a04dfafe-3411-4b19-9ddd-9af081b4c595`, both copies are carried, each byte-identical
  to its own owner member, and the two source copies genuinely differ.
- **README matches actual behaviour**, including the "one dashboard needs 11" claim:
  exactly one dashboard in scott-b closes to 11 (dashboard=1, view=2, supermetric=8).
- **CHANGELOG** is accurate and complete for the branch.
- **No em-dashes** in any added line or any tracked file.

## If shipped as-is

An admin migrating an alert would get a bundle whose symptom silently points at a
super metric the bundle does not carry, and the build report would say nothing, which
is the exact failure the milestone exists to prevent. An 8.x source would import with
a reshaped rule-to-template map that nothing has ever tested. And a real customer's
admin user uuid would stay published in the repo's history and in the `v0.0.1` source
archive.

---

# Round 2: re-review of the rewritten branch

- Branch `feat/m4a-tree-and-build`, rewritten, 9 new SHAs: `9e251f5` (sanitization,
  first), `a47d0a2`, `a60c5ab`, `d65d38a`, `3e39844`, `d714739`, `3673ead`,
  `826702c`, `8319fa0`
- Reviewed: 2026-09-14
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 2 WARNING, 1 NIT)
- **B1 remains with Scott** and was not in scope for this round. It is not
  re-verified here and it is not resolved: the PR still must not open before his
  decision is recorded.

## Checks re-run independently

| Check | Result |
|---|---|
| leak scan, my own needles (4554, harvested from all five zips: uuids, JSON string values, XML attribute values and text, member names, small-file contents) over all 35 unique blobs in all 9 branch trees | **0 corpus values.** The only uuid hit in the whole scan sits in the parent blob at `3d6268a` (main), which is B1 |
| hostname / IP scan over branch blobs | 3 hits, all `broadcom.com` (LICENSE) and `github.com` (README, pyproject). No instance data |
| branch commit messages | 4 hits, all schema key names (`ruleNameToTemplateNameMap`, `configuration.json`, `customGroupTypes`, `serviceCredentials`) |
| pytest | **123 passed**, 0 failed (matches the claim) |
| corpus-check | exit 0, 5 ok lines, now reporting `N containers unchanged` |
| select-all identity, my own extractor and comparator, all five zips | 807 documents, **0 mismatches**; every JSON container parses equal; `configuration.json` is the only structural difference and is by design |
| `notificationrules.json` / `payloadtemplates.json` on select-all | **byte-identical on all three zips that carry them**, 8.x `entry` object shape and 9.x list shape both preserved |
| closure audit, 21 seeds over two zips, verified by my own parser against the bundle | **6 seeds produce a bundle referencing a super metric it does not carry** (B5) |
| slicer break attempts (7 encoding and namespace cases) | 1 corrupting case, 1 uncaught crash (W3, still open) |
| em-dashes, all tracked files | none |

## Resolved this round

- **B2 is fixed and fixed correctly.** Sanitization is the first commit, and my own
  scan confirms no blob in any of the 9 branch trees carries a corpus value. The
  removal lines visible in `git show 9e251f5` are the parent blob's content, which
  is B1's scope, not a new exposure.
- **B3 is fixed.** The symptom to super metric edge is real and correctly extracted.
  My round 1 worked case now closes to 4, not 3: it chains a second super metric
  (`Storage Active Path Count`) that my round 1 note missed. The author's number is
  right and mine was low.
- **B4 is fixed, and so is the second bug their container-identity check found.** I
  verified both by construction, not from their report: select-all returns the 8.x
  `ruleNameToTemplateNameMap` byte for byte with `entry` as a single object; and on a
  zip I built with `notificationTemplateDataSet` removed from `notificationrules.json`
  so templates live only in `payloadtemplates.json`, the mapping survives select-all
  intact. Partial selection preserves each source's shape and drops are announced.
- **W1** (`corpus-check` now compares container shapes), **W2** (24 tests in
  `tests/test_rawdoc.py` covering every shape I checked by hand in round 1),
  **W4** (namespace limit documented, and I confirmed it fails safe end to end:
  a namespaced `views.zip` lands in `unknown`, never carried empty), **W5** (drops
  named in the build report, unrecognised material carried through), **W6** (marker
  caveat now printed as a build note), **W7** (48 items, 49 documents, kept
  distinct), **N1**, **N2**, **N3**: all addressed.
- README is accurate. Its invented `Acme` names and uuids appear nowhere in the
  corpus; its `430 objects`, `197` missing edges and `one dashboard out of it needs
  11` all still verify exactly (exactly one dashboard closes to 11), and its edge
  list does include symptom to super metric.

## BLOCKING

### B5. The twelfth edge: a super metric formula that names another super metric

`graph.py:SM_REF_RE` matches only `sm_<uuid>`. The 8.18.7 corpus export carries the
other wire spelling, `Super Metric|@supermetric:"<Name>"`, in eight formulas across
six super metrics, and **every one of those targets is another super metric in the
same export**:

```
[VCF Content Factory] VCF Total License Usage (%)   [45c6c9c3-...]
   tool edges: []
   by-name ref -> '[VCF Content Factory] VCF Total License Capacity (cores)' : supermetric:e2560d5e-...
   by-name ref -> '[VCF Content Factory] VCF Total License Usage (cores)'    : supermetric:c43ec7e3-...
```

Proven end to end, not inferred. Of 12 seeds I built on `scott-8.18.7`, **6 produce a
bundle whose carried super metric references a super metric the bundle does not carry
and that the source did carry**, with no MISSING line either:

```
[8.x] supermetric:c99ede65-6c99-4419-9054-a0f26a788144: carried 1, UNCLOSED 2
[8.x] supermetric:45c6c9c3-7d83-41ff-b936-22d896b939d7: carried 1, UNCLOSED 2
[8.x] supermetric:2f9fa681-..., ca78bf94-..., 4b01a4b4-..., 1691cba3-...: UNCLOSED 1 each
```

All nine seeds on `scott-b-9.0.2` closed cleanly, and uuid-based closure is clean on
both zips. This is the 8.x spelling only, on the one version the spec's Versions row
singles out.

This is B3's failure mode, on B3's evidence, one spelling over. The authority is the
module `graph.py`'s own docstring cites: `vcfcf_core.supermetrics.crossref` documents
`@supermetric:"Name"` as a super metric reference. Spec, subsetting paragraph: "A
bundle whose documents reference objects it does not carry is the one failure mode
subsetting can introduce on its own."

It also refutes the audit claim in the docstring and the result block ("every
identifier in every document of all five zips resolved against the other objects...
the only hits not already an edge were the symptom one and prose uuids"). A by-name
audit over the same five zips finds this in a minute.

Fix: resolve `Super Metric\|@supermetric:"<name>"` to a super metric node by name in
`_supermetric_refs` (and, for safety, wherever `_sm_refs` runs, since the same
spelling can reach a view column or a widget), and add a test on an 8.x-shaped
fixture formula that selecting the referring super metric closes to two.

## WARNING

- **W3 is not resolved; the fix does not catch the case it names.** `rawdoc.py`'s
  docstring now says a document declaring a non-ASCII-compatible encoding "is refused
  outright rather than rebuilt into something subtly wrong". `_declared_encoding`
  requires `data[:200]` to start with the ASCII bytes `<?xml`, which a real UTF-16
  document never does. So the guard fires only on a self-contradictory document
  (ASCII bytes declaring UTF-16), which expat would reject anyway, and a genuine
  UTF-16 document sails past: I sliced one, rebuilt it, and the result is **not
  well-formed**, because the `b"\n"` separators are lone `0x0A` bytes in a UTF-16
  stream. `tests/test_rawdoc.py:139` pins exactly the case that works
  (`'...encoding="UTF-16"...'.encode("utf-8")`) and so goes green over the case that
  does not. Separately, `_ASCII_COMPATIBLE` whitelists `shift_jis`, `euc-` and
  `koi8`, which expat cannot parse at all: such a document reaches expat and raises a
  bare `ValueError`, uncaught. I reproduced a CLI crash with a raw traceback by
  re-declaring the real 8.18.7 `views.zip` content as Shift_JIS (`rc=1`, `ValueError:
  multi-byte encodings are not supported`, surfacing from
  `export_reader.py:174`). Still latent: every corpus XML is UTF-8, and `discover`
  routes a real UTF-16 member into "carried, not inspected" before any rebuild, so
  the corrupting path is unreachable today. But the docstring and the test now assert
  a safety that is not there. Fix: detect the encoding from the bytes (BOM, or a NUL
  in the first two bytes) rather than from an ASCII-readable declaration; drop the
  multi-byte encodings from the whitelist or catch `ValueError` as `RawDocError`; and
  make the test use real UTF-16 bytes.
- **W8. Description prose is followed, though the docstring says it is not.**
  `graph.py`'s docstring says super metric uuids quoted inside a description's prose
  "are not references and are deliberately not followed". `_sm_refs` is a regex over
  the whole raw document, so they are followed. On `scott-8.18.7`, **4 of the 8 lines
  under "referenced but not in this export" are prose-only**: the uuid appears in
  `description` and not in `formula`. Today they only add noise to the one report
  that tells an admin what will break on import; nothing guards against a prose uuid
  that does resolve, which would silently over-carry. Fix: extract from `formula`
  rather than the whole document for super metrics, or narrow the docstring claim.

## NIT

- **CHANGELOG omits the edge this round added.** Its edge list is the 11 from round 1;
  symptom to super metric, the B3 fix, is not in it, though the README's list has it.

## Still open

1. **B1**, with Scott, unchanged and unverified this round.
2. **B5**, above.
3. **W3**, carried over from round 1 and not resolved.
4. **W8** and the CHANGELOG nit, both new.

## If shipped as-is

An admin subsetting super metrics out of an 8.18.7 export, the version the spec calls
out, gets a bundle whose formulas point at super metrics the bundle does not carry,
with no warning, while the same report shows four warnings that are not references at
all. The tool would be right on 9.x and quietly wrong on 8.x, which is the harder case
to notice and the one a migration exists for.

---

# Round 3: re-review of the four new commits

- Branch `feat/m4a-tree-and-build`, 13 commits. New this round: `ebaaf82`
  (rawdoc encoding from bytes), `d492694` (follow by-name references), `98c2de0`
  (tests), `dc59ccf` (docs)
- Reviewed: 2026-09-14
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 6 WARNING, 2 NIT)
- **B1 remains with Scott**, out of scope this round, not re-verified, not
  resolved. The PR still must not open before his decision is recorded.

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | **138 passed**, 0 failed (matches the claim) |
| corpus-check | exit 0, 5 ok lines; 8.18.7 now **4** missing edges, was 8 |
| my own export reader, independent of `export_reader.py` / `containers.py` | item counts equal the tool's on all five zips, every kind |
| the two new by-name classes, read out of the corpus documents myself | **both real, extraction correct, counts exact**: dashboard to group 1 / 3 / 2 on 8.18.7 / prod / scott-b; group to group 6 on prod (8 `RelationshipRule`s total, the other 2 name ordinary resources) |
| my own by-name and by-uuid cross-reference audit, every kind, all five zips | one class the tool does not follow (**B6**); every other candidate proved to be prose or a coinciding title |
| my own closure audit, **all 719 nodes** in all five zips, references re-derived by my own extractor from the bundle | **1 unclosed edge, silent** (B6). 718 clean |
| `@supermetric` closure on the six 8.18.7 seeds | closes to 2, 3, 2, 3, 3, 2 with **0 missing**; the author's multiset, confirmed |
| SM to SM edges vs my own formula-only extraction | **exact match** on all five zips (5, 5, 8, 8, 25). The prose change dropped no real reference |
| the 4 surviving 8.18.7 missing edges | all four are `AlertDefinition-VMWARE-...` / `-DISA-...` ids wanted by a notification rule, in an export that carries **no alerts at all**. Out of the box, as claimed |
| encoding, 17 cases built from the real 8.18.7 `views.zip` bytes | **W3 fixed**. UTF-16 (LE/BE, with and without BOM), UTF-32, Shift_JIS, EUC-JP, KOI8, UTF-7, IBM037 and real EBCDIC all refused cleanly; UTF-8, UTF-8 BOM, no declaration, ISO-8859-1, windows-1252 all accepted and rebuilt well-formed; **no uncaught exception on any case** |
| 15 further slicer break attempts | all correct: CDATA holding `</ViewDef>`, `>` and `/>` in attribute values, self-closing abutting the parent, comment and PI holding a fake element, DOCTYPE with an internal entity, nested same-name, UTF-8 BOM, no declaration, multibyte tag names, CRLF, newlines inside a start tag, empty document, trailing whitespace |
| leak scan, my own needles (2113: uuids, emails, lab hostnames, IPs, every custom group and super metric display name) over all 39 blobs in all 13 branch revisions, plus all branch commit messages | **0 hits** |
| em-dashes, tracked files and commit messages | none |
| README numbers | 430 objects, 197 missing edges, and **exactly one** dashboard closing to 11 (`Cluster Capacity Details v7`). All still verify |
| dashboard localization bundles | `resources.properties` and the `_es` / `_fr` / `_ja` siblings survive a subset build intact (`knowledge/lessons/pak-content-localization-bundles.md`) |

## Resolved this round

- **B5 is fixed, and fixed with the right authority.** `_sm_refs` resolves the
  by-name spelling through `vcfcf_core.supermetrics.crossref.crossref_names`,
  which is where `@supermetric:"<name>"` is defined, not a second regex. I also
  confirmed the author's negative claim: across all five exports there are 659
  `Super Metric|sm_<uuid>` and 24 `@supermetric:` occurrences and **zero** bare
  `Super Metric|<Name>`. Two spellings is the whole set.
- **W8 is fixed.** Reading super metric references from `formula` alone loses
  nothing: my independent formula-only extraction matches the tool's SM to SM
  edges exactly on every zip.
- **W3 is fixed.** The refusal now comes off the bytes and the whitelist no
  longer promises encodings expat cannot parse. I could not construct a
  document that is accepted and rebuilds into something not well-formed.
- **The two new classes are real and correctly extracted.** The `Container`
  marker on the dashboard binding is load-bearing and earns its keep:
  `002009ContainerUniverse` on a `Universe` binding and `002006VMWAREvSphere
  World` on a world binding both fall through correctly, and the 8.x case uses
  `002009ContainerEnvironment` rather than `...Function`, which the marker
  still catches.

## BLOCKING

### B6. The third spelling: a widget scoped to a custom group by a list-shaped `resource`

`graph.py:RESOURCE_BINDING_RE` matches only the object-shaped binding
(`"resource": {"resourceName": ..., "resourceKindId": "...Container..."}`). A
Scoreboard widget writes its scope differently, as a **list of
`{"name", "id"}`**, with no `resourceName` and no resource kind at all:

```
scott-b-9.0.2, dashboard "Custom Dashboards/Telegraf Agent Health"
  widget type=Scoreboard title="Telegraf Agents"
  "resource": [{"name": "Telegraf Agents", "id": "resource:id:4_::_"}]
```

`Telegraf Agents` is a custom group in the same export (`customgroups.json`,
with its own policy). The edge is not followed. Proven end to end:

```
$ vcfcf-migrator --source-version 9.0.2 build scott-b-9.0.2-...zip \
      --select sel.txt --out telegraf.zip
selected: 1 named, 4 after closure
carrying: dashboard=1, supermetric=1, view=2
```

The bundle carries the dashboard and not the group, and **says nothing**: no
MISSING line, no note. The scoreboard lands on the target scoped to a resource
that is not there.

This is B3's and B5's failure mode, on B3's and B5's evidence, one spelling
over, for the third round running. It also refutes this round's claim that the
redone by-name audit "found two more classes": there were three. My own closure
audit over every one of the 719 nodes in all five corpus zips found exactly one
unclosed edge in the whole corpus, and it is this one.

Authority: spec `content-migrator-v1.md`, subsetting paragraph, "A bundle whose
documents reference objects it does not carry is the one failure mode
subsetting can introduce on its own, and the walker is what prevents it";
`graph.py`'s own module docstring repeats it.

Corpus scope: the list shape occurs 8 times across four exports. The other 7
name worlds and adapter instances (`vSphere World`, `NSX World`, `License
Usage`, `Automation World`, `Rubrik Virtual Machine`), which correctly resolve
to nothing. So this is one live case, and one is enough.

Fix: in `_dashboard_refs`, also walk a list-shaped `resource` and take each
item's `name` as an `optional=True` customgroup ref (optional, because 7 of the
8 corpus instances name ordinary resources). Add the shape to the fixture
widget and a test that selecting that dashboard closes to include the group.

## WARNING

- **W10. `GROUP_RULE_RE` ignores `ruleType`, so a name rule can fake a group
  edge.** The regex takes every `"ruleStringValue"` in the document, but only a
  `RelationshipRule` names another group. Across the corpus there are 8
  `RelationshipRule`s, 15 `ResourceNameRule`s and 5
  `StringMetricPropertyRule`s, and the latter 20 carry values like `template`,
  `vms`, `group`, `hosts`, `logs`, `photon`. A custom group named any of those
  would be pulled into a bundle that does not depend on it, and the tree would
  print an edge that is not there. Latent today only because no group name
  collides. The asymmetry is the tell: the dashboard binding one function away
  was given a structural guard (the `Container` marker) for exactly this
  hazard, and this one was not. Fix: parse `membershipDefinition.ruleGroups[].rules[]`
  and take `ruleStringValue` only where `ruleType == "RelationshipRule"`.
- **W11. `build` never mentions an ambiguity, so the command that writes the
  bundle is the one that does not say.** `graph.ambiguous` is rendered only by
  `render_tree` (the `tree` command) and by `graph.as_dict`. Neither
  `selection.render` nor `selection.as_dict` carries it, so `build` and
  `build --json` are both silent. Demonstrated on an 8.18.7 export with one
  super metric duplicated under a second uuid and the same display name:

  ```
  selected: 1 named, 3 after closure
  carrying: supermetric=3
  pulled in by dependency: 2
    supermetric [VCF Content Factory] Host VCF Licensed Cores (16-core minimum) added: required by ...
    supermetric [VCF Content Factory] Host VCF Licensed Cores (16-core minimum) added: required by ...
  ```

  Two identical lines, no uuid, no word "ambiguous". Carrying every match is
  the right call and I agree with the reasoning: over-carrying is recoverable
  and guessing wrong is not. But "reports the ambiguity" is only true of `tree`.
  Fix: carry `graph.ambiguous` into `selection.render` and `as_dict`, and print
  the node uuid in the "pulled in by dependency" reason so twins are
  distinguishable.
- **W12. The ambiguity guard is inert, and fires on the case it was written to
  suppress.** `build_graph`'s condition is
  `len(hits) > 1 and ref.ident not in (h.split(":", 1)[1] for h in hits)`. For a
  dashboard the node key is `dashboard:<uuid>@<owner>`, so the split yields
  `uuid@owner`, which never equals the bare `uuid` a reference carries. The
  deliberate, documented, correct two-owner case therefore reports as an
  ambiguity, and the guard suppresses nothing. On the tool's own fixture:

  ```
  AMBIGUOUS: ["report [Fixture] Cluster Report [...] names dashboard
  '2d7b8c1e-...' and 2 objects answer to that name; all are carried"]
  ```

  It is also worded wrong: that is a uuid, printed under the heading
  "references by name that more than one object answers to".
  `_resolve_index`'s docstring says this case is correct by design, so the
  report contradicts the code's own stated intent. Corpus-clean (all five zips
  report `ambiguous: []`), so latent. `test_two_super_metrics_sharing_a_name_are_both_carried`
  asserts only that `ambiguous[0]` contains a phrase both entries share, so it
  goes green over the spurious one. Fix: compare against the node's own `ident`,
  not the key suffix, and skip the note when every hit shares one ident.
- **W13. The CHANGELOG was not updated, and the commit message says it was.**
  `dc59ccf`'s message reads "The CHANGELOG's edge list was the round 1 one and
  had already fallen behind the README's. Both now carry the same table." The
  diff touches `README.md` only; `git log -- CHANGELOG.md` still ends at
  `8319fa0`. The CHANGELOG's edge list is still the round 1 set: no symptom to
  super metric, no dashboard to custom group, no custom group to custom group,
  no mention of the by-name spelling. The round 2 NIT is unresolved and the
  commit record is now inaccurate about it. Fix: put the table in the CHANGELOG
  and reword `dc59ccf`.
- **W14. A carried custom group points at a policy the bundle never carries,
  and the missing-edge report does not say so.** Five custom groups across two
  exports carry `"policy": "<uuid>"`, and all three distinct uuids resolve
  inside that same export's `policies.xml`
  (`a596a124...` in 8.18.7, `51359772...` twice and `89daa47b...` once in
  scott-b). `policies.xml` is an unknown member and is never carried, so the
  bundle ships a group referencing a policy that will not exist on the target.
  This is a WARNING and not BLOCKING only because the drop is loud: the build
  note names `policies.xml` among the members not carried. But the admin is not
  told that something they selected depends on it. Fix: report the `policy`
  uuid as a missing edge, so the one report that says what will break says it.
- **W15. The same by-name resource binding exists in a notification rule and is
  not followed.** A `RESOURCE_AND_CHILD` condition writes
  `NotificationRuleResourcesCondition.ResourceItems[].NotificationRuleResourceItem[].ResourceID.resourceName`,
  which is the dashboard binding in a different document and under a different
  key (`resourceKind`, not `resourceKindId`). The condition type is live in the
  corpus (prod, one rule, naming two NSXT adapter instances), so only the
  group-valued instance is absent, not the class. `_rule_refs` reads
  `AlertDefinitionID` and `PluginID` and nothing else. Unproven safe, therefore
  a finding. Fix: extract it as an `optional=True` customgroup ref, or record in
  the `graph.py` docstring that this binding is deliberately not followed and
  why.

## NIT

- **`_customgroup_refs`'s docstring contradicts its own code.** It says a value
  naming no group "resolves to nothing and is reported as missing, which is
  right". The code passes `optional=True`, so it is **not** reported, which is
  what the module docstring, the `Ref` docstring and
  `test_a_membership_rule_naming_no_group_here_is_not_a_missing_edge` all
  require. The function docstring is the odd one out and would lead a future
  reader to "fix" the code back into the noise this round removed.
- **The prose exclusion is super metric only.** `_sm_refs` still scans the whole
  document for views, symptoms and dashboards, so a `sm_<uuid>` quoted in a
  view's `<Description>` would be followed and would over-carry. The docstring
  is literally accurate (it claims the exclusion only for super metrics) and the
  corpus is clean: no view, symptom or report description quotes a super metric
  uuid or an `@supermetric:` token in any of the five zips. Worth one line in
  the docstring so the asymmetry is a decision rather than an oversight.

## Still open

1. **B1**, with Scott, unchanged and unverified this round.
2. **B6**, above.
3. **W10** through **W15**, and the two NITs, all new.

## If shipped as-is

An admin moving the Telegraf Agent Health dashboard gets a bundle with the
dashboard, its two views and its super metric, and no custom group, so the
scoreboard lands on the target scoped to a resource that does not exist, and
nothing in the build output ever mentioned the group. An admin whose export has
two super metrics sharing a display name gets both, correctly, and a build
report that prints the same line twice and never says why. And the CHANGELOG
tells a reader the tool follows eleven edges when it follows fourteen.

---

# Round 4: re-review of the five new commits, and of the method itself

- Branch `feat/m4a-tree-and-build`, 17 commits. New this round: `c14c44c`
  (README edge table), `ae68882` (references read from the parsed document),
  `7de62b2` (build reports what tree reports), `9fd17dc` (tests for every
  shape), `ab4178c` (CHANGELOG table)
- Reviewed: 2026-09-14
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 5 WARNING, 4 NIT)
- **B1 remains with Scott**, out of scope this round. B7 below is not a
  re-litigation of it; it is a new mechanical fact about this branch that
  appeared during the review.
- Reviewed at `ab4178c` in a throwaway clone, because the live clone under
  `content/migrator/` switched itself to `main` mid-review (see B7).

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | **143 passed**, 0 failed (matches the claim) |
| corpus-check | exit 0, 5 ok lines; 8.18.7 **6** missing edges, scott-b **201** (both match the claim) |
| my own field shape enumeration, every JSON key in every document of all five zips | reproduced independently; agrees with theirs on the widget scope, and finds two fields theirs does not name (**W17**) |
| my own cross-reference audit, every uuid and every string leaf of every document, all five zips, resolved against every object | **0 real edges the tool does not follow.** Every candidate adjudicated: self-references, twins sharing a display name, or description prose |
| my own closure audit, every node in all five zips | **0 unclosed.** The bar is met |
| group to group and dashboard to group edges vs my own extraction | **exact match** on all five zips: group to group 6 on prod, dashboard to group 3 / 1 / 3 on prod / 8.18.7 / scott-b |
| over-carry: whole-document vs widgets-only super metric scan | identical on all five zips, 0 extra references |
| over-carry: marker as negative filter | the 3 no-kind bindings and the 7 world and adapter bindings all resolve to nothing; no false edge on any zip |
| B6 end to end | Telegraf Agent Health closes to **5** including `customgroup Telegraf Agents`, and its policy is reported |
| select-all, my own recursive extractor, all five zips | 219 source blobs; every carried member present; **380 XML document byte-spans carried verbatim**, 0 missing; every JSON container parses equal; `configuration.json` the only by-design difference |
| unhandled-shape probe, 9 constructed widget scopes plus 2 constructed dashboard shapes | 3 handled, 6 dropped, **0 reported** (**W16**) |
| leak scan, my own needles (2827: uuids, IPs, hostnames, emails, every name-like JSON value in all five zips) over all 47 blob paths in all 18 revisions, plus commit messages | branch's own 17 commits **clean**; one hit, in `3d6268a`, which is B7 |
| em-dashes, tracked files and branch commit messages | none |
| README and CHANGELOG edge tables vs the code | both accurate and now identical (W13 fixed); the worked example's numbers are not (**W18**) |

## Two corrections to my own round 3 counts: they were right, I was wrong

- **The list-shaped widget scope is 3 occurrences across 2 exports, not 8
  across 4.** My round 3 note said 8, and it was wrong: 8 is the count of
  `dashboards[].entryKeys.resource` and top-level `entries.resource`, two
  different fields whose values are the worlds and adapter instances I listed
  (`vSphere World`, `NSX World`, `License Usage`, `Automation World`, `Rubrik
  Virtual Machine`). The widget field `widgets[].config.resource` is
  list-shaped exactly 3 times (2 in prod, 1 in scott-b) and empty-list 422
  times, which is where my 8 did not come from but where my reasoning had
  drifted. Their count is the correct one.
- **The group policy references are 6 across 2 exports over 3 distinct uuids,
  not 5 groups.** My round 3 W14 said five groups and miscounted scott-b as
  `51359772` twice and `89daa47b` once. It is twice each: `VIH Certificates`
  and `VIH Certificates including Aria VMs` on `a596a124` in 8.18.7, then
  `Telegraf Agents` and `Custom Group of VMs` on `51359772`, `All VMs` and
  `Brocks VMs` on `89daa47b` in scott-b. Six. Their correction is right, and
  the rise in the missing-edge totals (8.18.7 four to six, scott-b 197 to 201)
  is exactly those six.

## The method: genuinely structural, with one claim it does not earn

The extraction is real. Documents are parsed and descended by named field, and
the two surviving regexes both match inside a single value, which is where a
metric key and a formula genuinely are text. I could not find a regex that had
merely moved. `_sm_refs_in` resolving the by-name spelling through
`vcfcf_core.supermetrics.crossref.crossref_names` rather than a second regex is
the right call and is the reason the 8.x spelling stays in step with the
factory.

The shapes the table claims are handled, are handled: object with a Container
kind, object with no resource kind at all, list of objects, null, empty list,
absent, and an object whose kind is present and is not a Container correctly
falls through. I verified each by construction, and my own enumeration over all
five zips finds no widget scope shape outside that set.

What it does not earn is the claim in the module docstring that an unhandled
shape "shows up as one you have not handled". It does not. See W16.

## BLOCKING

### B7. This branch still reaches the pre-sanitization merge commit, and `origin/main` no longer does

During this review the clone under `content/migrator/` switched from
`feat/m4a-tree-and-build` to `main`, amended `3d6268a` into `4505a68`, and that
rewrite is now on `origin/main`. `4505a68` is clean. `3d6268a` is not: its
`tests/fixtures/make_export_fixture.py` blob (`5dadccc2`) carries
`0c44e115-dc21-4ea5-8a56-01c22f18325b`, the real corpus owner uuid, and my leak
scan over all 47 blob paths in all 18 revisions finds that value in that one
blob and nowhere else.

`feat/m4a-tree-and-build` still has `3d6268a` as an ancestor. Its merge base
with the rewritten `origin/main` is now `69618e2`, the bootstrap commit. So
pushing this branch as it stands re-uploads `3d6268a` and re-publishes, on the
remote, the value that was just force-removed from it.

The branch's own 17 commits are clean. This is not a finding about the code and
not a reopening of B1, whose decision is Scott's and appears to have been taken:
it is the mechanical consequence, and it is the reason the PR cannot open from
this branch in its current shape.

Fix: rebase `feat/m4a-tree-and-build` onto `4505a68` so `3d6268a` is not in its
history, confirm `git merge-base` with `origin/main` is `4505a68`, then push.
Re-run the leak scan over the rebased revisions before opening the PR.

## WARNING

- **W16. A shape nobody has seen is dropped, not reported, so the method's
  headline claim is not backed by the code.** `graph.py`'s module docstring
  says walking the parsed structure "cannot miss a sibling shape: it either
  handles it or shows up as one you have not handled", and `ae68882`'s message
  says each field handles "the value being an object, a list of objects, a bare
  string, null or absent". A bare string is not handled and nothing surfaces.
  Proven by construction on the real extractor:

  ```
  "resource": {"resourceName": "G", "resourceKindId": "...Container..."} -> [('customgroup', 'G')]
  "resource": {"resourceName": "G", "resourceId": "..."}                 -> [('customgroup', 'G')]
  "resource": [{"name": "G", "id": "..."}]                               -> [('customgroup', 'G')]
  "resource": "G"                                                        -> []
  "resource": ["G"]                                                      -> []
  "resource": {"resources": [{"name": "G"}]}                             -> []
  widgets as an object rather than a list                                -> []
  widgets under "tabs"                                                   -> []
  ```

  `_resource_names` skips a non-dict item with a bare `continue`, and a bare
  string is then indistinguishable from `null` and from `[]`, of which the
  corpus has 279 and 422. The same silence is in `_dashboard_refs` when
  `widgets` is not a list, in `_rule_refs` when `entry` is not a list, and in
  `_customgroup_refs` when the document is not an object. `Graph` already has
  two channels for telling an admin something (`missing`, `ambiguous`) and
  neither is used for this. The author knows the right pattern: only
  `_supermetric_refs` has it, falling back to every string value with a comment
  saying why, when `formula` is not the expected shape.

  Latent, and no corpus shape is affected. But the claim is this round's whole
  thesis, it is what a future maintainer will trust instead of re-enumerating,
  and it is the same family as round 2's W3: a docstring asserting a safety the
  code does not have. Fix: handle a string item in `_resource_names` (one
  line), and collect an unhandled-shape note on `Graph` the way `missing` is
  collected, so the sentence becomes true. Or narrow the docstring and the
  commit message to what the code does.

- **W17. The enumeration is not exhaustive: two fields in the same document
  carry the same binding in a third shape, and are not in the table.** The
  dashboard container writes the resource binding in two more places than
  `widgets[].config.resource`:

  ```
  dashboard.json .dashboards[].entryKeys.resource   8 occurrences, 10 names
  dashboard.json .entries.resource                  8 occurrences, 19 names
  ```

  Both are lists of `{resourceKindKey, internalId, adapterKindKey, identifiers,
  name}`, a shape with neither `resourceKindId` nor the list shape's bare
  `{name, id}`. Six of those names are custom groups in the same export
  (`[Custom] VMs on only Standard PGs`, `[Custom] VMs on only NSX PGs`,
  `[Custom] VMs on Both NSX and Standard PGs` in prod, `VIH Certificates` in
  8.18.7, `Custom Group of Custom Groups of VMs` and `Telegraf Agents` in
  scott-b).

  No edge is missed on this corpus, and I proved it rather than assuming it:
  every group named in `entries` is also bound by a widget scope in the same
  container, which the tool does follow, and `entryKeys` names only worlds and
  adapter instances. So this is not a B6 repeat. It is a hole in the claim that
  "every field read is enumerated", on the one field class that has now been
  missed three rounds running, in the one document where it lives twice more.
  `entryKeys` is per dashboard: a dashboard that binds a group there and not in
  a widget would be missed exactly as B6 was.

  Fix: enumerate the two fields, and either read `entryKeys.resource` through
  `_resource_names` as an optional customgroup ref, or say in the docstring
  that it is a derived index of the widget bindings and is deliberately not
  read, with the corpus evidence that makes that safe.

- **W18. The README's worked example still prints the pre-round-4 numbers.**
  `README.md:59` shows `edges to objects this export does not carry: 197`, and
  line 64 says the counts are from a real 9.0.2 export. That export now reports
  **201**, because of this round's own policy edges. `c14c44c` reworded the
  edge table four lines below without refreshing the sample. The same sentence,
  "one dashboard out of it needs 11", is still literally true (exactly one
  closes to 11) but no longer reads true: the new edges mean that export now
  has dashboards closing to 12, 13 and 16, so the number it offers as the worst
  case is no longer the worst case. Fix: 201, and either quote the largest
  closure or drop the superlative reading.

- **W19. The shape this round discovered is the one shape with no test.** The
  object with no resource kind at all (`{"resourceId": ..., "resourceName":
  ...}`, 3 occurrences in scott-b, all `vSphere World`) is what forced the
  marker from a positive test to a negative filter, and it is the only
  enumerated shape `tests/test_tree_build.py` does not pin:
  `test_a_dashboard_scoped_to_a_custom_group_reaches_it_by_name` uses the
  object shape "next to a Container resource kind", and
  `test_a_list_shaped_resource_scope_reaches_the_group_too` uses the list
  shape. Re-tightening `_resource_names` to require a Container kind would
  silently stop resolving the no-kind shape and the suite would stay green.
  Given `9fd17dc`'s message ("every shape of a reference"), and that an
  untested render surface is how both of this factory's named escapes shipped,
  this one needs its own fixture widget and test. Fix: add the no-kind object
  to the fixture and a test that it reaches the group.

- **W20. The notification rule reads the same binding with a weaker rule than
  the widget does, which is the asymmetry that produced B6.** `_rule_refs`
  matches on a raw key name:

  ```python
  elif key in RESOURCE_NAME_KEYS and key == "resourceName" \
          and value not in seen_groups:
  ```

  The first clause is dead (`key == "resourceName"` implies it) and it reads as
  if both spellings in `RESOURCE_NAME_KEYS` are accepted, when only one is. So
  a rule condition that spelled the scope `name`, which is exactly what the
  widget list shape does, would be missed, and no kind filter is applied at all
  where the widget path applies one. The docstring claims the opposite: "read
  with the same `resourceName` spelling a widget uses ... the same binding in a
  different document". Corpus-safe today: the two live `ResourceID` values are
  NSXT adapter instances, the third is `""`, and all three resolve to nothing.
  Fix: pass the `ResourceID` value through `_resource_names` so there is one
  reader for one binding, and drop the dead clause.

## NIT

- **The edge table says "any widget string value"; the code scans the whole
  dashboard document.** `_dashboard_refs` runs `_json_strings(doc)`, not
  `doc["widgets"]`, so a `sm_<uuid>` anywhere outside a prose key is followed
  and is labelled `via widget metric`. Inert: I compared the whole-document and
  widgets-only scans on every dashboard in all five zips and they agree
  exactly, 0 differences. Worth one word in the table, or scan `widgets`.
- **`policy` is reported under a heading that says it is not in the export,
  when it is.** `tree` prints it under "edges to objects this export does not
  carry", and `policies.xml` is right there in the member list two lines below.
  `build` rescues it with "it will be missing on import unless the target
  already has it"; `tree` has no such clause. The count and the wording of the
  `via` are otherwise correct and do not drown the signal: 2 of 6 on 8.18.7 and
  4 of 201 on scott-b, against 131 and 153 genuine out-of-the-box view
  references.
- **`selection.close` matches ambiguity notes by string prefix**
  (`note.startswith(node.label())`) rather than carrying the source node's key
  on the note. It is correct today because a label ends in a uuid, but it
  couples the selection report to the exact wording of a string built in
  `graph.py`.
- **The container rebuild drops the indentation between documents in XML
  containers.** Source `\n        <Recommendation` comes back as
  `\n<Recommendation`. Pre-existing, not this round, and harmless: I confirmed
  all 380 XML document byte-spans are carried verbatim and every JSON container
  parses equal, so the contract holds and only inter-document whitespace moves.
  Noted so the "containers structurally identical" claim is read as structural
  rather than byte for byte.

## Resolved this round

- **B6 is fixed, and fixed structurally rather than with a fourth regex.**
  Telegraf Agent Health closes to 5 and carries the group, and I confirmed the
  fix generalises: the object shape, the no-kind object shape and the list
  shape all resolve through one `_resource_names`.
- **W10 is fixed and is exactly right.** Only a `RelationshipRule` yields a
  group name now, and my own extraction agrees edge for edge: 6 group-to-group
  on prod, 0 elsewhere, with the 20 name and metric rules correctly ignored.
- **W11 and W12 are both fixed.** The ambiguity guard compares the nodes' own
  idents, so the two-owner case no longer reports; all five zips report
  `ambiguous: []`; and `selection.render`, `selection.as_dict` and the
  dependency reasons all carry it now, pinned by a test that asserts on the
  selection path rather than only on the tree.
- **W14 is fixed**, with the count corrected against me, and the report wording
  names the member the policy lives in.
- **W15 is fixed**, subject to W20 above.
- **W13 is fixed**: the CHANGELOG now carries the same 13-row edge table as the
  README, and both match the code.
- **Both round 3 NITs are fixed**: `_customgroup_refs`'s docstring no longer
  contradicts `optional=True`, and the prose exclusion is now one rule over
  every kind rather than super metrics only.
- **No over-carrying in either direction I could find.** The string-leaf super
  metric scan adds nothing on any zip, and the marker as a negative filter
  produces optional references for the 3 no-kind bindings and the 7 world and
  adapter bindings, every one of which resolves to nothing.

## Still open

1. **B1**, with Scott. The rewrite of `main` appears done; B7 is what is left
   of it on this branch.
2. **B7**, above.
3. **W16** through **W20**, and the four NITs.

## If shipped as-is

The tool itself would behave correctly: my own audit over every node in all
five exports finds nothing it fails to carry and nothing it carries without
cause. What ships wrong is around it. Pushing the branch would put a real
customer's admin uuid back on the remote the day it was removed. An admin
reading the README would be told an export has 197 dangling references when it
has 201. And the next person to add a reference class would read a docstring
promising that an unhandled shape announces itself, write the field walk on
that promise, and get the silence that B3, B5 and B6 each got.

# Round 5: re-review of the two new commits, and of the closure guarantee

- Branch `feat/m4a-tree-and-build`, 19 commits over `main` at `4505a68`. New
  this round: `054a873` (unhandled shapes are reported, one reader for one
  binding), `9721d28` (README numbers, two overstated table rows)
- Reviewed: 2026-09-14, at `9721d28` in the live clone, tree clean
- Verdict: **APPROVE** (0 BLOCKING, 2 WARNING, 4 NIT)

## Checks re-run independently

| Check | Result |
|---|---|
| pytest | **164 passed**, 0 failed (matches the claim) |
| corpus-check | exit 0, 5 ok lines; missing edges **0 / 0 / 143 / 6 / 201**, matching the claim zip for zip |
| graph output, round 4 (`5955beb`) vs round 5 (`9721d28`), all five zips | **byte-identical**: same nodes, same edges, same per-node refs including `optional` and every `via` string, same missing list. This round changes no corpus behaviour, so nothing in it could regress select-all identity or the counts |
| select-all round trip | every document byte-identical, every container unchanged, on all five zips |
| my own closure audit, **every** node in all five zips | **802 seeds, 0 genuinely unclosed.** 62 raw textual candidates, every one adjudicated: 39 a group name that is a substring of the carrier's own name, 10 the deliberate two-owner dashboard copy, 5 a widget title or metric name that coincides with a group name (`Custom Groups`, `All VMs`), 8 a group name quoted in view prose |
| my own over-carry audit, same 802 closures | **0 carried without cause.** The 13 raw flags are all outbound settings and notification templates, whose link is a composite `pluginType/pluginName` or the container-level `ruleNameToTemplateNameMap`, neither of which is a single token in the rule document |
| adversarial unhandled-shape probe, **43 constructed shapes** nobody has tried | 15 handled and resolved, 22 reported as unhandled, 6 silently inert. Of the 6, 4 are genuinely empty (`null`, `[]`, `widgets: null`, `config: null`) and 2 are the shapes in **W21** and **W22** |
| the 36 bare widget ids, my own extraction | **confirmed: all 36, all on prod-9.1.1, every one resolves to a widget id in the same document.** None is a content reference. Zero on the other four zips |
| `entries.resource` exclusion, re-proved my own way | **6 group names across the corpus, all 6 widget-bound in the same container, 0 not.** I would ship the exclusion, and for a stronger reason than the one in the docstring: see below |
| whole-document vs walked-subtree scan, every dashboard in all five zips | **0 super metric and 0 view references anywhere in a dashboard document that the walk does not already carry**, including inside `dashboardNavigations` |
| re-tightening the kind filter to require a Container | **12 tests fail**, including the no-kind shape test, the rule reader test and two closure tests. W19's guard is real and loud |
| unhandled channel end to end, doctored export | `tree`, `tree --json` (`unhandled_shapes`), `build` and `build --json` (`selection.unhandled_shapes`) all carry it. The claim holds on all four surfaces |
| leak scan, my own needles (3942: every uuid, hostname, IP, email, display name, XML name value and view title in all five zips) over all 465 blob paths in all 21 revisions of `main`, `v0.0.1` and the branch, plus every commit message | **zero corpus values.** The only hits are `github.com` in the README and pyproject, and the author's own address in the LICENSE |
| em-dashes, tracked files and branch commit messages | none |
| README and CHANGELOG vs actual behaviour | the corrected numbers are right: 430 objects, 201 edges a bundle cannot carry, dashboard closures **1 to 16**, all reproduced. Both edge tables match the code |

## B7 is closed

Merge base with `origin/main` is **`4505a68`**, `3d6268a` is **not** an
ancestor of the branch, and the leaked value appears in no blob and no commit
message of `main`, `v0.0.1` or `feat/m4a-tree-and-build`. Scott authorised the
rewrite mid-review, `main` was amended to `4505a68`, `v0.0.1` was re-cut from
it, and the branch was rebased. Nothing of B1 or B7 remains on this branch.

One correction to the record, from Scott: the value was a uuid from **his own
lab prod instance, the built-in admin account**, not a customer's. Round 4's
"a real customer's admin uuid" overstated it. The handling was right either
way, and the discipline it produced (invented fixture values, a leak scan per
round) is worth keeping.

## Resolved this round

- **W16 is fixed, and fixed as the channel it should have been**, not as a
  patch on one function. `Graph.unhandled` collects notes the way `missing`
  does, attributed to the node, deduplicated, and surfaced by `tree`,
  `tree --json`, `build` and `build --json`. All eight of my round 4 cases now
  either resolve or report. Turning it on found a real corpus shape on its
  first run, which is the strongest evidence a diagnostic channel can give.
- **W17 is fixed on the field that needed it, and argued on the field that
  did not.** `entryKeys.resource` is read through `_resource_names` and would
  catch a dashboard that scoped a group there and not in a widget.
- **W18, W19 and W20 are fixed**, and W19's test genuinely guards: retightening
  the filter reds 12 tests rather than passing silently.
- **All three live NITs are fixed**: the policy heading now says which of the
  two cases each missing edge is, `selection.close` matches notes on
  `source_key` rather than on a label prefix, and the edge tables say what the
  code reads.

## The `entries.resource` exclusion: ship it

Read the block and the reason is stronger than "all six are widget-bound
anyway". `entries` is an **interning table for the whole container**: on
`scott-b`'s 303829ed owner it is one `{resource, resourceKind}` dictionary
sitting beside **57** dashboards, with no attribution to any of them. Reading
it would attach every name in it to all 57. The per-dashboard `entryKeys`
block, by contrast, carries its names inline and is attributable, which is
exactly why reading that one and not this one is the right split. I confirmed
the safety claim independently (6 group names, all 6 widget-bound in the same
container, 0 not), and the block is copied verbatim into the rebuilt inner zip
either way, so nothing is lost on import. Ship the exclusion.

## WARNING

- **W21. A bare widget id is skipped on a comment, not on evidence, which is
  the one place the new channel is asserted rather than checked.**
  `graph.py:459-465` skips any string in a `widgets` list with
  `continue` and a comment saying all 36 on this corpus resolve to a sibling
  widget id. I verified that claim and it is true today (36 bare ids, all on
  prod-9.1.1, all resolving to a widget id in the same document, 0 elsewhere).
  But the code does not check it: any string in a `widgets` list is dropped,
  and a future export that wrote a nested widget by name, or by a content
  uuid, would be dropped the same silent way that B3, B5 and B6 were. This is
  the only branch of the new channel whose correctness rests on a comment.
  Fix, three lines: collect the document's own widget ids, and report a bare
  string that is not one of them as an unhandled shape. Then the sentence in
  the docstring is true at runtime and not only on this corpus.

- **W22. `dashboardNavigations` is a second place a dashboard document holds
  `widgets`, and it is neither read nor reported.** The walk starts at
  `doc["widgets"]` and recurses only through `config.widgets`. prod-9.1.1
  carries `dashboardNavigations.<widget-uuid>[].widgets`, **15 widget-shaped
  objects** across 8 dashboards, which no reader touches and no channel names.
  Nothing is missed on this corpus and I proved it rather than assuming it:
  the 58 distinct ids in those blocks are `{interactionType, id}` pairs, and
  **not one of them is a content object uuid in any of the five exports**; my
  whole-document scan finds 0 super metric and 0 view references there. So it
  is not a B6 repeat. It is the same gap in the claim that W17 was: the method
  only protects fields whose shapes have been enumerated, and this field was
  never enumerated, so the protection does not reach it. Fix, and it is the
  one the author already used for `entries.resource`: either walk `widgets`
  wherever it appears in the document, or name `dashboardNavigations` in the
  deliberate-exclusions list with the evidence above.

## NIT

- **The docstring attributes this round's 36 to the wrong branch.**
  `_dashboard_refs` says nested widgets are "either inline objects (36 such on
  this corpus, none carrying a reference today) or bare widget ids". The corpus
  has **zero** inline nested widget objects and **36** bare ids. The code
  handles both; only the count is misfiled, and it is the sentence the next
  contributor will read as the survey.
- **The kind filter vetoes on either key, where the docstring describes one.**
  `_resource_names` breaks out of the loop on the first of `resourceKindId`,
  `adapterKindKey` that is present and not a Container, so an object with a
  Container `resourceKindId` and a non-Container `adapterKindKey` is skipped,
  and positive evidence loses to negative. Inert today, and I checked rather
  than assumed: **no object in any of the five exports carries both keys**.
  Worth one sentence saying the veto is deliberate, or an `all()` over the
  keys that are present.
- **`graph.py`'s own edge table still names one spelling for the rule scope.**
  Line 36 reads `condition ``ResourceID.resourceName``` where the code now
  reads every shape `_resource_names` knows. `9721d28` corrected the two
  dashboard rows in the README and the CHANGELOG and left this one; the README
  row for the same edge is already right.
- **`tree` says 4 unhandled notes where `build --select-all` says 2, on the
  same export.** `Graph` deduplicates on `(source_key, text)` and
  `selection.close` on text alone, and a note's text carries `node.label()`,
  which has no owner in it, so the two copies of one dashboard under two
  owners collapse in `build` and not in `tree`. Nothing is lost, only counted
  differently, but "build says what tree says" was W15's whole point. Either
  put the owner in the note the way `render_tree` puts it on the line, or
  deduplicate on the source key in `close`.
- (Not a finding, noted for the record: the test at
  `tests/test_tree_build.py:256` asserts
  `len(notes) == 1 and A in notes[0] or B in notes[0]`, which binds as
  `(len and A) or B`. It fails loudly on an empty list either way, so it is
  not hiding anything; parentheses would make it say what it means.)

## The closure guarantee

**Established for the corpus on hand.** 802 seeds, one per node in all five
exports, every closure audited against my own extraction rather than against
the tool's: 0 unclosed and 0 over-carried, with every raw candidate on both
sides adjudicated by hand to prose, a coinciding title, a substring of the
carrier's own name, the deliberate two-owner case, or a composite identity the
token match could not see. The two warnings above are about shapes this corpus
does not contain: they bound how far the guarantee travels to the **next**
export, not how well it holds on these.

## If shipped as-is

An admin gets a tool that carries what it says it carries on every export in
this corpus, tells them what a bundle cannot carry and why, and, new this
round, tells them when it met a field it does not understand rather than
quietly resolving it to nothing. What ships unproven is the edge of that
promise: a bare widget id and a `dashboardNavigations` block are skipped
without a check, so on an export shaped differently from these five the tool
would go quiet exactly where it now promises to speak.
