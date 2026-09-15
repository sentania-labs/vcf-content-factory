# Framework review: migrator logging (feat/logging)

- Repo: `content/migrator` (vcf-cf-migrator), branch `feat/logging`, 9 commits over `main` (45adcf1 .. 5620444), not pushed
- Reviewed: 2026-09-14/15
- Spec: `knowledge/designs/content-migrator-v1.md` §Logging (Scott verbatim; the exclusion list; the content-versus-people agreement of 2026-09-14) and §"The corpus leak, and what was done about it"
- Prior rounds: `migrator-m3-skeleton-2026-09-14.md`, `migrator-m4a-tree-and-build-2026-09-14.md`, `migrator-m4b-preview-and-page-2026-09-14.md`
- Verdict: **CHANGES REQUESTED** (6 BLOCKING, 8 WARNING, 5 NIT)

## A note on the tree under review

The working tree changed under this review. At 00:07-00:09, while checks were
running, uncommitted edits appeared in `src/vcfcf_migrator/export_reader.py`,
`bundle.py`, `containers.py`, `cli.py`, `ui.py`, `tests/fixtures/make_export_fixture.py`
and `tests/test_log_redaction_corpus.py`: zip directory entries carried into the
bundle, against an importer refusing `INVALID_FILE_FORMAT`. That work is **not
part of the nine commits reviewed here** and is not assessed. Everything below
is against `feat/logging` HEAD `5620444`.

`runlog.py` was not touched by that drift. B1, B2 and B3 were each re-proved
against the current working tree after it appeared, and reproduce unchanged
(B1: three leaked titles; B2: `mthornbury` 0 before the settings change, 12
after; B3: 9 occurrences of the compact account uuid in one build log).

## Checks re-run independently

Scratch venv `/tmp/mig-rev-venv` (editable install of this tree), scratch `HOME`
so the settings file is this review's and not the workstation's.

| Check | Result |
|---|---|
| `pytest -q` | **518 passed**, 0 failed (includes the 10 corpus-redaction tests) |
| `corpus-check` | exit 0, 5 ok lines, all five zips round trip |
| select-all document identity | 83/83, 83/83, 158/158, 49/49, 434/434 byte-identical |
| closure audit, every node as a seed, all five zips | 802 seeds, 0 unclosed edges |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345 | byte-identical on all five |
| page-built bundle vs CLI-built bundle | byte-identical on all five |
| render regression vs `main`, all 802 corpus objects | 41 pages changed in body; every change is one of the four declared fixes; 761 unchanged |
| census on `main` vs branch | **identical** (claim holds) |
| heat hexes vs corpus | `#74B43B` 38, `#ECC33E` 42, `#E07720` 6, `#DE3F30` 38 occurrences; shape documented at `knowledge/context/api-surface/widget_types_survey.md:441`. Not fabricated. |
| **adversarial export, every command at debug** | **person values reached the log** (B1, B3) |
| mechanism removal, corpus tier | key rules removed: 5 failed. Harvest removed: 6 failed. **Uuid rule removed: 10 passed (green)** (W1) |
| mechanism removal, full suite | all three caught (`test_runlog.py::test_a_uuid_nobody_declared_to_be_content_is_excluded` catches the third) |
| page path across a log-setting change | **redaction lost** (B2) |
| exit code on a failing run | fixed on the CLI; **not on the census** (W3) |
| log cost, 430-object select-all build | none 0.44 s, info 0.44 s / 8 KB, detail 0.50 s / 401 KB, debug 0.48 s / 527 KB (66 KB gzipped). Full page session incl. 430 previews: 2114 events, 826 KB diagnostics. Mailable. |
| corpus leak scan, 1886 uuids + 1886 prefixes + 1867 names, all 68 blobs of all 9 revisions, plus commit messages | 0 text hits; **1 hit in pixels the scan cannot see** (B4) |
| em-dashes, added lines and whole tree | none |
| Python floor gate | 67 passed |
| `actionlint` both workflows | clean; CI untouched by this branch |

## BLOCKING

### B1. A person's name in a different case reaches the log, on the default level

`src/vcfcf_migrator/runlog.py:224`. `_compiled()` builds the person/owner
alternation with `re.escape` and **no `re.IGNORECASE`**, so the substitution is
case-sensitive. The export declares the person once, in whatever case
`usermappings.json` writes it; content spells names any way it likes.

Proved end to end. An export whose `usermappings.json` declares
`displayName: "Marguerite Thornbury"` and `userName: "mthornbury"`, with those
names in widget titles, run at `--log-level debug` (`widget.classified.title`
is emitted at `detail`, the default):

```
"title": "MARGUERITE THORNBURY runs this"      <- leaked
"title": "marguerite thornbury owns this"      <- leaked
"title": "vm-[excluded:person]-01 and MTHORNBURY"  <- half redacted, half leaked
```

Authority: spec §Logging, "user names, display names, mail addresses and user
or owner uuids are excluded"; `README.md:69`, "They never carry ... anything
about people." Nothing in either is conditioned on case.

Fix: compile the alternation with `re.I` and key `_replacements` by lowercased
value, so the pseudonym/marker is chosen case-insensitively.

### B2. The page throws away everything it learned about people whenever a log setting changes, and then logs people verbatim into the diagnostics file

`src/vcfcf_migrator/ui.py:137-157` (`PageState.open_log`). `open_log()` builds a
brand new `Log`, and therefore a brand new `Redactor` with an empty people list,
an empty owner table and an empty allow-list. It is called from `__init__` and
again from `_act_settings` on **every** `log_file` or `log_level` save
(`ui.py:489-503`). The export already open is not re-read, so
`harvest_identity` never runs again and the new redactor is never taught
anything.

Measured over one page session on an export carrying a declared person, driving
the real HTTP server with a valid Origin:

```
before the settings change: mthornbury 0   [excluded:person] 6
after  the settings change: mthornbury 12  [excluded:person] 0
```

and the same 12 occurrences land in the file the README tells a customer to
send: `save_diagnostics` writes the whole in-memory event list, so the
diagnostics document carried the person's user name 12 times.

Two further consequences of the same line: `ui.py:151` splices the old events
onto the new log, so `owner-1` means one person before the change and a
different person after it, in one file; and the allow-list reset means every
content uuid logged afterwards prints as `[excluded:id]` (55 of them in my run),
which is the diagnostic half going dark at the same moment the protective half
does.

Authority: spec §Logging (the exclusion list, and "a dashboard's owner is
logged as a stable per-run pseudonym"); the page is the surface the README
tells the admin to use ("That opens the page, which does the whole job").

Fix: carry the `Redactor` across a re-open (`Log(redactor=old.redactor)`),
rather than constructing a new one. `Log.__init__` already accepts one.

### B3. A uuid written without hyphens defeats the third mechanism entirely

`src/vcfcf_migrator/runlog.py:120` (`_UUID_RE`). The rule that is sold as "a
call site cannot log an account uuid by accident" only recognises the canonical
`8-4-4-4-12` form. The 32-hex compact form is not matched, is not in
`_allowed`, and passes straight through.

Proved: a dashboard whose name carries the person's account id compacted
(`[Fixture] Cluster Overview [cccc333300004000800000000000000c]`) printed the id
verbatim in **every** command's log: `inspect` 1, `tree` 7, `build` 9,
`preview` 7 occurrences. Uppercase canonical and brace-wrapped forms are handled
correctly; only the undashed form is blind.

Authority: spec §Logging, "user or owner uuids are excluded";
`runlog.py:33-37`, the module's own statement of the mechanism.

Bounding it honestly: no corpus export carries an owner uuid in this form today
(I checked all five), so this is a reachable gap rather than an observed leak on
Scott's data. The promise is unconditional, and so is the fix.

Fix: add the compact form to `_UUID_RE` (`[0-9a-fA-F]{32}` as a second
alternative), and normalise by stripping hyphens before the `_allowed` lookup so
a content id written either way still resolves.

### B4. A real owner account uuid from the devel export is committed to the public repo, as pixels

`docs/preview-dashboard.png` (added in `752226f`) shows, in its header line:

```
owner 29c1613f-3bbe-4aa0-8236-2c74db22c661 | from dashboards/29c1613f-3bbe-4aa0-8236-2c74db22c661
```

plus dashboard uuid `be78532e-5cde-4cb9-8eb3-6b9e16b18c73`.
`docs/selection-and-dependencies.png` shows the owner prefix `29c1613f` and the
uuid prefix `3c1e8aae`. All three are verbatim in
`corpus/devel-9.0.2.0-2026-09-14-full.zip` (and the first two in
`devel-9x-...`; `3c1e8aae` and `be78532e-...` also in the prod export).

Provenance of both images is as claimed: image 2 names
`corpus/devel-9.0.2.0-2026-09-14-full.zip` in its own Export-zip field, image 1
carries devel's owner. No prod-only owner appears. So the "devel only" half of
the claim holds; the "no owner uuid" half does not.

This is the M4a B1/B2 class recurring: spec §"The corpus leak" records that
one owner uuid on `main` cost a history rewrite and a re-cut tag, on Scott's
verbatim "Write main so it's clean". It also demonstrates the guard's limit: my
own 1886-needle scan over all 68 blobs of all 9 revisions found **zero** hits,
because a uuid rendered as pixels is not text. The recurrence guard is a
procedure someone runs, not an artifact in this repo, and it is blind to the one
file type this branch added.

Cheap to fix: the branch is unpushed.

Fix: regenerate both screenshots from the committed fixture
(`tests/fixtures/make_export_fixture.py` invents owners, names and secrets
precisely so this is possible), or from a devel export with the owner line
masked, and rewrite `752226f` so no revision holds the image. Then extend the
pre-PR scan to refuse an image under `docs/` that was not produced from the
fixture, since a text scan cannot judge one.

### B5. The README's first command does not run

`README.md:27`:

```
vcfcf-migrator ui my-export.zip --source-version 9.0.2
```

```
vcfcf-migrator: error: unrecognized arguments: --source-version 9.0.2
```

`--source-version` is on the main parser only; `_SubParser.parents` carries the
three log flags and nothing else (`cli.py:53-83`). This branch went to real
trouble to make `--log` work on both sides of the subcommand and then published
a README whose headline command uses the post-subcommand form for a *different*
global. It is also M3 N3 ("`--corpus` must precede the subcommand") returning in
the surface an operator meets first.

Authority: house rule 8, done means seen working; the M3 review's own N3.

Fix: either put `--corpus` and `--source-version` on the shared parent the way
`--log` already is (preferable: it is what an admin types), or write the README
line as `vcfcf-migrator --source-version 9.0.2 ui my-export.zip`.

### B6. The redactor rewrites content names and the tool's own sentences, so the log cannot be paired with what Ops says

`src/vcfcf_migrator/runlog.py:126,170,231`. Any harvested person value of four
characters or more is substituted **anywhere it appears as a substring**, with
no word boundary and no distinction between a value read out of a document and a
fixed English string the tool wrote itself.

On `corpus/scott-b-9.0.2-2026-09-14.zip` (`admin` is a real `userName` in
`usermappings.json`), 9 of the 968 distinct content strings the log emits come
out mangled:

```
"name": "DX O2 Webhook Notification - [excluded:person] (WebhookPlugin)"
"name": "Guest Filesystem Alert to DX02 - [excluded:person]"
"name": "[excluded:person] alert"
"name": "[excluded:person][excluded:mail] password changed"
"name": "[excluded:person]s VMs"
"ident": "Condition_[excluded:id]"
```

and the tool's own reason text is rewritten too:

```
"reason": "... carrying it would be the tool deciding for the [excluded:person]"
"reason": "... would preview an object the [excluded:person] did not ask for"
```

Scott's bar is verbatim in the spec: the log plus what VCF Operations said has
to be enough to diagnose. Ops will name the rule `"... admin alert"`; the log
says `"[excluded:person] alert"`, and the pairing that is the entire point of
the release fails for exactly the notification rules and alerts a support case
is about. The corpus test cannot see this: `COMMON` (`tests/test_log_redaction_corpus.py:62`)
drops `admin` from its needles, so the one gate over real data is blind to the
one value that causes it.

Authority: spec §Logging, "content identity is in scope ... that is what makes
the log diagnostic"; reviewer doctrine dimension 8, a silent downgrade of a
declared capability.

Fix, two parts, both small: (a) never run the substitution over the tool's own
literals (redact the values a call site passes, not the `reason`/`note` strings
the module authored, or pass those through a marker type the redactor skips);
(b) require a word boundary for non-uuid person values, and drop values that are
also ordinary words (the `COMMON` set the test already maintains belongs in the
layer, not only in the test).

## WARNING

- **W1** `tests/test_log_redaction_corpus.py`. The corpus tier does not fail
  when the uuid mechanism is deleted. I replaced the `_UUID_RE.sub` in
  `Redactor.text` with `return out` in a throwaway copy: **10 passed**. The
  other two mechanisms turn it red (5 and 6 failures). The full suite does catch
  all three, via `test_runlog.py::test_a_uuid_nobody_declared_to_be_content_is_excluded`,
  so the mechanism is not ungated, but the file that is presented as the
  customer-facing proof over real exports is not the gate for a third of what it
  claims to prove. Cause: this corpus's person uuids all reach the log through
  the owner-key rule or the harvest first, so the uuid rule is never the thing
  that saves it. → Add a case that plants a uuid nobody declared into a real
  run over a corpus zip (the same way B3's export does) and asserts it is
  excluded.

- **W2** `tests/test_log_redaction_corpus.py:74,78` (`PATH_FIELDS`,
  `without_paths`). The carve-out is bounded in the *test* and nowhere in the
  layer: `without_paths` strips eight key names from every event before
  scanning, so any value that ever lands under `path`, `cwd`, `argv`, `out`,
  `zip`, `dir`, `file` or `corpus_dir` is invisible to the only gate over real
  exports. I audited today's call sites and all eight genuinely hold paths, so
  this is latent rather than live, but nothing stops the next call site from
  logging content under `file=`. Same shape as the prior rounds' "a gate that
  passes when the thing it guards is removed". → Mark path fields at the call
  site (a `runlog.path()` wrapper, or a naming rule the layer enforces) so the
  exemption is a property of the value, not of a list of key names a test keeps.

- **W3** `tools/corpus_census.py:310`. `log.finish(0, what="census")` sits in a
  `finally` and hardcodes 0. Reproduced: a census over a directory with one
  unreadable zip exits 1 with a traceback while its log's last line reads
  `"event": "run.end", "exit": 0`. This is a sibling of the very defect
  `1cf5907` claims to have fixed on the CLI (`cli.py` now does
  `log.count("exit", code)`, which I confirmed reports `exit: 1` on both a
  refusal and an unreadable input). The reports-green-while-broken class, in the
  second call site. → Capture the real code (or the exception) and pass it.

- **W4** `src/vcfcf_migrator/ui.py`. The page's log never gets a `run.end`:
  `PageState` calls `log.header(...)` but nothing calls `log.finish(...)`, so a
  page-written log file has no terminating event, no event total and no
  `owners_seen`. A log that is truncated and a log that ended look the same. →
  Emit `run.end` per page action, or on shutdown.

- **W5** `src/vcfcf_migrator/runlog.py:325,365-367` with `ui.py:144`. The page's
  event cap drops the **oldest** events and records the count in `self.dropped`,
  which nothing reads and nothing logs. The oldest events are `log.contents`,
  `run.start` and `input.fingerprint`, which are exactly what
  `save_diagnostics` looks up by `_last_event` to build the diagnostics head, so
  past the cap the diagnostics file quietly loses its header, its fingerprint
  and its self-description. Not reachable on this corpus (largest full session:
  2114 events against a 40000 cap), so this is a latent one. It also breaks the
  spec's own rule that nothing the tool keeps quiet about in its output may be
  quiet in the log. → Never drop the header events, and emit a `log.truncated`
  warn when the cap bites.

- **W6** `src/vcfcf_migrator/bundle.py:375`, `runlog.py:649`. The spec asks the
  build fingerprint for "member list, per member size, and **the hash of each
  carried document**". `output_fingerprint` hashes members, not documents:
  `views.zip` is one 343 KB entry with one sha256 covering 181 views. When Ops
  rejects one view, the log answers "views.zip, 343110 bytes, <hash>" and
  nothing more, which is short of the stated bar. The CHANGELOG is honest about
  this ("a hash per member"); the spec is not satisfied. → Add a per-document
  hash list for the container members, or record the spec gap as a deliberate
  v0.1.0 limit with Scott's agreement.

- **W7** `tests/test_log_wiring.py:30`. `EXCLUDED_FROM_THE_FIXTURE` is a
  hand-picked tuple of six fixture constants. The fixture also defines
  `PERSON_DISPLAY_NAME_2`, `PERSON_SERVICE_ACCOUNT` and `OWNER_2`, and none of
  the three is asserted absent. They are excluded today (I checked a real
  fixture build at debug: zero occurrences), so this is drift, not a leak, but
  it is the drift the corpus file's own docstring warns against, in the tier CI
  actually runs. → Derive the tuple from the fixture module's person/secret
  constants rather than listing six of nine.

- **W8** `README.md:69`. "Logs carry content names and ids. They never carry
  credentials, the export password, encrypted values, or anything about
  people." The tool's own contents line is more honest than the README: it names
  "the file paths you gave the tool" as a class it carries. Every log opens with
  `cwd` and `argv` verbatim, which on a customer workstation is
  `/home/<their user name>/...` or `C:\Users\<name>\...`, and can be worse than
  a user name: an MSP's path carries the customer's name, a UNC path carries a
  domain and a share. The README sentence is the promise a customer reads before
  attaching the file, and it is not true as written. (B1, B2 and B3 make it
  untrue in three further ways, which is the point of listing it separately: fix
  those and this sentence is still wrong about paths.) → Say what the contents
  line says: content names and ids, plus the file paths you gave it; never
  credentials, the export password, encrypted values or people.

## NIT

- **N1** `src/vcfcf_migrator/runlog.py:170`. A person value under four
  characters is never taught, so a three-letter user name is never excluded.
  Defensible (`_MIN_PERSON_LEN`'s comment argues it), but the corpus test mirrors
  the same floor at `:157`, so the layer and its gate agree by construction and
  neither can see the case. Worth one sentence in the spec's exclusion list
  rather than only in a code comment.

- **N2** The carve-out is described as "file paths are logged as typed", but
  they are not: paths go through `Redactor.text` like everything else, so the
  same path appears verbatim in `run.start.argv` (written before the harvest)
  and redacted in `input.fingerprint.path` (written after). One of my runs shows
  `.../Marguerite Thornbury-export.zip` in `argv` and
  `.../[excluded:person]-export.zip` in `path`, in one file. Decide which it is
  and make both events agree.

- **N3** `bundle.py` logs the written bundle's members as
  `dashboards/owner-2`, which is not a member name that exists in the zip the
  customer has in hand. Correct for the exclusion list, confusing for the person
  comparing the log to the artifact. One line in the contents note would cover
  it.

- **N4** At the default `detail` level no event ties an object to the member
  that carried it (`node.found`, which carries `member`, is `debug`). Given the
  bar is "answer it from the log alone", the member belongs on
  `closure.picked`/`closure.added`.

- **N5** `preview.py:911`. The truncation `shown.rsplit(" ", 1)[0]` drops the
  whole string when the first 600 characters contain no space (CJK text, one
  long token). Guard with a fallback to the unsplit prefix.

## Author claims vs observed

Held: `--log`/`--log-level`/`--log-format` accepted before and after the
subcommand; `-` writes to stderr; `log-render` renders a captured jsonl;
`--log-format text` matches it; levels behave as documented; default is
`detail` when a log is asked for and off otherwise; the diagnostics file is one
file with a self-describing JSON head carrying run header, input fingerprint and
bundle manifest; logging methods are positional-only; owners are first-seen
pseudonyms with no table on disk; the four rendering fixes are each real and
visible on the corpus (23 heatmaps, 17 text widgets, 31 health charts, 6
truncation notes, 41 pages total, 761 unchanged); the census is byte-identical
to `main`; heat colours are corpus values, not invented.

Corrected: the exit-code fix is real on the CLI but not in `tools/corpus_census.py`
(W3). The `AlertDefinition-<uuid>` fix is real (`content_id` now harvests uuids
out of longer strings, `runlog.py:187`) and I found no surviving case of a
*content* identifier mangled for that reason, but a symptom condition id
(`Condition_<uuid>`) still prints as `Condition_[excluded:id]`, which is the same
sibling in a place the fix did not reach (folded into B6). The exclusion
enforcement claim is three mechanisms, and all three have a hole: case (B1),
lifetime on the page (B2), and uuid shape (B3).
