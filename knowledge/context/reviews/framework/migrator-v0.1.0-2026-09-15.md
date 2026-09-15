# Framework review: migrator v0.1.0 candidate (feat/logging, whole branch)

- Repo: `content/migrator` (vcf-cf-migrator), branch `feat/logging`, **12 commits**
  over `main` (`45adcf1` .. `5b2833c`), frozen, unpushed, working tree clean
- Reviewed: 2026-09-15, against HEAD `5b2833c`
- Supersedes: `migrator-logging-2026-09-14.md` (9 commits, tree moved under it).
  That report is history; this one is the coverage.
- Spec: `knowledge/designs/content-migrator-v1.md` §Logging (Scott verbatim; the
  exclusion list; the content-versus-people agreement of 2026-09-14) and
  §"The corpus leak, and what was done about it"
- Live evidence now available:
  `knowledge/context/api-surface/dashboard_import_two_phase_materialization.md`
- Verdict: **CHANGES REQUESTED** (2 BLOCKING, 5 WARNING, 3 NIT)

## The headline

The two blockers are one root cause and its amplifier, and together they are
the worst shape this codebase can produce: **turning the log on breaks the
tool, and the crash it causes writes the excluded value into the log.**

Everything else on the branch is in good order. The bundle writer is now proven
against a real instance, the directory-entry fix is real and properly gated, all
fourteen findings of the previous round are genuinely resolved, and I could not
construct a bundle that would be unimportable in an untested case.

## Checks re-run independently

Scratch clone `/tmp/migrev/tree`, scratch venv, scratch `HOME` so the settings
file is this review's and not the workstation's. Corpus copied in (it is
gitignored and correctly absent from the repo).

| Check | Result |
|---|---|
| `pytest -q` | **540 passed**, 0 failed |
| `corpus-check`, 5 zips | **exit 0**, 5 ok lines, all round trip, 2 directory entries each |
| closure audit, every node as a seed, all 5 zips | **802 seeds, 0 unclosed edges** |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345 | byte-identical, all 5 |
| page-built bundle vs CLI-built bundle | **byte-identical, all 5** |
| select-all document identity | 83/83, 83/83, 158/158, 49/49, 434/434 (via corpus-check) |
| render regression vs `main`, 797 objects | 40 changed, **all dashboards**, 757 unchanged; sampled diffs are exactly the declared heatmap-label and heat-colour fixes |
| census on `main` vs branch (`--json`) | **identical** (claim holds) |
| mechanism removal, key rules | corpus tier **5 failed**, full suite 9 failed |
| mechanism removal, harvested-people substitution | corpus tier **6 failed**, full suite 9 failed |
| mechanism removal, uuid allow-list | corpus tier **1 failed**, full suite 3 failed (**prior W1 fixed**) |
| mechanism removal, mail rule | corpus tier **1 failed**, full suite 3 failed |
| directory-entry fix deleted | corpus-check **exit 1**, 5 error lines; suite **7 failed** |
| corpus leak scan: 342 uuid + 221 name needles vs all 95 blobs of all 12 revisions, plus commit messages | **0 instance hits** (2 hits are the English words "percentage" and "Administrator") |
| screenshots, read as pixels | real devel owner uuid present, **authorized**, see below |
| em-dashes, tracked text and branch commit messages | **none** |
| Python floor gate (`vermin`, floor 3.9 from `ci_checks.py`) | clean (min 3.8) |
| `actionlint`, both workflows | clean |
| README first command, verbatim | **runs** (prior B5 fixed) |
| **adversarial export, person name in a second case form** | **tool crashes; excluded value reaches the log** (B1, B2) |

## BLOCKING

### B1. A person's name in a second case form makes the redactor raise, and the tool dies with the log on

`src/vcfcf_migrator/runlog.py:322-323`.

```python
out = self._compiled().sub(
    lambda m: self._replacements[m.group(0).lower()], out)
```

The previous round's B1 fix compiled the person alternation with `re.I` and
keyed `_replacements` by the lowercased value. That is correct for ASCII and
wrong in general: `re.IGNORECASE` and `str.lower()` are **two different
definitions of case**, and where they disagree the dictionary lookup misses and
raises `KeyError`. I brute-forced the pairs: 77 of them, including three that
are not academic for a product shipped worldwide.

```
key='i' matches 'İ' (U+0130, Turkish) whose .lower() = 'i̇'   <- two codepoints
key='i' matches 'ı' (U+0131, dotless i)
key='s' matches 'ſ' (U+017F, long s)
```

Proved against the real Redactor:

```
taught: Ilkay Yilmaz
  'Ilkay Yilmaz owns this'  -> '[excluded:person] owns this'
  'ILKAY YILMAZ owns this'  -> '[excluded:person] owns this'
  'İLKAY YILMAZ owns this'  -> RAISED KeyError: 'i̇lkay yilmaz'
```

Proved end to end through the installed console script, on an export built from
the committed fixture with `displayName: "Ilkay Yilmaz"` and one widget title
spelling it `İLKAY YILMAZ`, **at the default log level** (no `--log-level`
given, i.e. exactly `--log run.log` as `README.md:73` instructs):

```
$ vcfcf-migrator --log run.log preview turkish.zip 'dashboard:2d7b8c1e-...@aaaa1111-...'
  ...
  File "src/vcfcf_migrator/runlog.py", line 1604 -> 625 -> 459 -> 352 -> 376 -> 322
KeyError: 'i̇lkay yilmaz'
exit=1, no preview written
```

Same on the page, which is the surface `README.md:30` calls "does the whole
job": `PageState.set_preview` raises for both owner copies of that dashboard.
There is no `except Exception` in `ui.py`'s `do_GET`/`do_POST`, so the admin
gets a dead request and a traceback on stderr.

Without `--log` the same command works. **Enabling the log is what breaks the
tool**, and the module's own docstring sets the bar it misses: `runlog.py:452`,
"A logging call that raises is worse than a missing line." `emit()` has no
guard.

Authority: spec §Logging (the exclusion list is enforced in the layer);
`runlog.py:452` the module's own invariant; house rule 8, done means seen
working.

Fix, smallest correct: make the two definitions one definition. Resolve the
replacement from the pattern rather than from the matched text, by giving each
alternative a named group and looking up by `m.lastgroup`, or by keying
`_replacements` with `str.casefold()` and looking up with
`m.group(0).casefold()` **with a `.get(..., EXCLUDED_PERSON)` fallback** so an
unresolvable match still excludes rather than raises. A bare `.get` default is
the belt; the named group is the braces. And wrap the body of `emit()` so a
redaction failure degrades to an excluded field instead of ending the run.

### B2. The crash handler writes the excluded person value into the log, because `reason` and `detail` are exempt from person redaction and every call site passes an exception string

`src/vcfcf_migrator/runlog.py:183` (`PROSE_FIELDS`), `runlog.py:338`,
`src/vcfcf_migrator/cli.py:427`.

`PROSE_FIELDS = {"reason", "says", "detail"}` are passed `people=False`, on a
stated premise:

> "Fields whose value is a sentence this module wrote. ... never for person
> values ... since a literal in this file cannot carry anyone's name."

The premise is false for almost every call site. `reason` and `detail` are also
the two keys the codebase uses to carry **arbitrary exception text**: 7
`detail=str(e)` and 7 `reason=str(e)` sites across `cli.py`, `ui.py`,
`bundle.py`, `preview.py`, `selection.py`, `export_reader.py`,
`corpus_check.py`, `tools/corpus_census.py`. An exception message is not a
literal in this file. Proved in isolation:

```python
r.person("Marguerite Thornbury"); r.person("mthornbury")
r.field("reason", "cannot read the copy owned by Marguerite Thornbury (mthornbury)")
  -> 'cannot read the copy owned by Marguerite Thornbury (mthornbury)'   # leaked
r.field("detail", ...)  -> leaked
r.field("says",   ...)  -> leaked
r.field("title",  ...)  -> '... owned by [excluded:person] ([excluded:person])'
```

B1 then supplies the exception whose message *is* the person's name, and
`cli.py:427` logs it under exactly that key. The committed artifact from the run
above:

```json
{"lvl":"error","event":"run.crashed","failure":"KeyError",
 "detail":"'i̇lkay yilmaz'","command":"preview"}
```

`excluded:person` appears 0 times in that file. This is the class the whole
branch exists to prevent, reached through the tool's own error path, and it also
reaches `save_diagnostics`, the file `README.md` tells a customer to mail.

B2 is independent of B1 and survives fixing it: any exception whose message
quotes a name (an `OSError` on a share path, a `KeyError` on an owner map, a
parse error quoting a document fragment) leaks the same way.

Authority: spec §Logging, "user names, display names, mail addresses and user or
owner uuids are excluded"; `README.md:76-78`, "They never carry ... anything
about the people in the export"; `runlog.py:33-37`, the module's own statement
that the rule is the layer's and not the caller's.

Fix: the exemption belongs to values the module authored, not to key names a
caller reuses. Pass the tool's own sentences through a marker type
(`runlog.prose("...")`) that `Redactor.field` recognises, and let plain strings
under `reason`/`detail`/`says` take the ordinary person scan. That keeps the B6
fix (the tool's English is not mangled) while closing the hole, and it makes the
distinction a property of the value rather than of a word in a keyword argument.

## WARNING

- **W1. The log's last line reports an exit code the run did not have, on the
  crash path.** `src/vcfcf_migrator/cli.py:416,431`. `code = 2` is the
  initialiser; the exception skips `code = command(args)`, and the `finally`
  calls `log.finish(code, ...)` with 2 still in place. Observed on the B1 run:
  the process exited **1**, the log's `run.end` says `"exit": 2`. This is the
  direct sibling of the defect `1cf5907` fixed on the success path and `3c4c62b`
  fixed in the census, in the one path where the log is all the diagnostician
  has. → Set `code` from the exception handler (or record the exception and let
  `finish` derive it), so `run.end` cannot state a code the process did not
  return.

- **W2. The event cap keeps the input fingerprint by coincidence, and says it
  keeps it unconditionally.** `src/vcfcf_migrator/runlog.py:368-370`.
  `HEAD_EVENTS` names three events, but `_trim` only inspects
  `self.events[:len(HEAD_EVENTS)]`. In a real run the order is `log.contents`,
  `run.start`, `log.level`, `phase.start`, `input.fingerprint`, so the
  fingerprint is outside the window; it survives only because the events in
  front of it are popped exactly one per call and it slides into slot 2 before
  its turn. Break the one-at-a-time assumption and it goes: with a batch drop
  (`event_cap` lowered mid-session), `input.fingerprint kept? False`, while the
  `log.truncated` warn text still reads "the run header and the input
  fingerprint are kept". A claim that outlives the thing it described. → Select
  the head by membership over the whole buffer, not by slot position.

- **W3. Dict keys are never redacted, and the one call site that would leak is
  safe only because the caller remembered.** `src/vcfcf_migrator/runlog.py:379`
  (`{str(k): self.field(str(k), v) ...}`) and `_owner_field`/`_person_field`,
  all of which rebuild dicts with `str(k)` untouched. Demonstrated:
  `r.field("counts", {"29c1613f-...": 12})` returns the owner uuid verbatim as a
  key. No live leak: `bundle.py:256` writes
  `{runlog.owner(o): c for o, c in ...}`, i.e. the call site pseudonymises by
  hand, and the corpus tier (which scans serialized events) is green. But that
  is precisely the arrangement `runlog.py:33` disclaims: "A rule a caller can
  forget is not a rule, and there are several hundred call sites." → Redact keys
  in `value()`/`_owner_field`/`_person_field` the same way values are redacted,
  and drop the hand-rolled comprehension at the call site.

- **W4. The README's promise about people is absolute; the spec's is not.**
  `README.md:76-78` says logs "never carry ... anything about the people in the
  export". The spec now states two deliberate limits: a person value under four
  characters is not excluded, and neither is one that is an ordinary word
  (`COMMON_WORDS` at `runlog.py:154` holds 30 of them, including `admin`,
  `operator`, `support`, `service`, `automation`, `guest`, `root`). Those limits
  are right, and the reasoning behind them is right. But a display name of
  "Support" or a user named `operator` is a person value that reaches the log,
  and the README is the sentence a customer reads before attaching the file.
  (B1 and B2 make it untrue in two further ways; this is listed separately
  because fixing those leaves it still overstated.) → Say what the spec says: no
  credentials, no export password, no encrypted values, no user names, display
  names, mail addresses or account uuids, except values that are ordinary words
  or shorter than four characters, which are left alone so the log can still be
  paired with what VCF Operations says.

- **W5. "A few minutes" understates the settling window by an order of
  magnitude.** `README.md:42-43`. The write-up this paragraph is drawn from says
  phase 2 runs "minutes to **hours** later", and `ui_deep_links.md` records "~3
  min after open, up to ~20 min background". The rest of the paragraph is
  accurate: widgets look empty, it completes on its own, a long stall means a
  missing adapter, all confirmed against
  `dashboard_import_two_phase_materialization.md`. But an admin who reads "a few
  minutes", waits ten, and sees empty widgets will conclude the bundle is broken
  and re-import, which is the exact loop DEF-014 already paid for. → Say minutes
  to hours, and add the write-up's own cheapest remedy (Q5): opening the
  dashboard once in the UI is the fastest observed trigger.

## NIT

- **N1.** `src/vcfcf_migrator/containers.py:64`. The bundle writes directory
  entries **stored**, `external_attr=(0o40700<<16)|0x10`, `create_system=3`. All
  five corpus exports write theirs **deflated**, `external_attr=0`,
  `create_system=0`. The shape used is the factory packager's and is proven to
  import, so this is cosmetic, but the docstring reasons from "the real export
  shape" while diverging from it on three fields. Worth one sentence saying it
  mirrors the packager, not the export.

- **N2.** `src/vcfcf_migrator/bundle.py:399`. `output.fingerprint`'s member list
  omits the two directory entries, so the "what did it actually write"
  fingerprint does not mention the entries whose absence made every bundle this
  tool ever built unimportable. They are in `bundle.directories` at `detail`. One
  count in the fingerprint would close it.

- **N3.** `.github/workflows/ci.yml` drives the console script through eight
  commands and never once passes `--log`. The suite covers the layer well, but
  the integration step that exists to catch wiring cannot see the flag this
  release is named for. B1 reproduces through that exact surface.

## Verified fixed from the previous round

All fourteen, each re-proved rather than taken on the commit message:

| Prior | Status |
|---|---|
| B1 case-insensitive person matching | fixed for ASCII; **re-opened by B1 above for unicode case** |
| B2 page rebuilds an empty redactor on a settings save | fixed, `ui.py:154` carries `old.redactor` |
| B3 compact 32-hex uuid | fixed, `_UUID_RE` second alternative + `_normal_id` |
| B4 owner uuid in committed pixels | **resolved by authorization, not by code.** Both PNGs do still show devel's owner `29c1613f-3bbe-4aa0-8236-2c74db22c661` (I read the pixels; the text scan cannot). `docs/README.md` records Scott verbatim, 2026-09-14, "As long as the references are my devel, who cares", limits screenshots to the devel export, and names the text scan's blindness to images as the reason the rule and not the scan is the control. I verified both images are devel-sourced: `29c1613f` appears only in the two devel exports. Legitimate close. |
| B5 README first command does not run | fixed, `--source-version` is on the shared parent; ran it verbatim |
| B6 substring redaction mangling content and the tool's prose | fixed, left word boundary + `COMMON_WORDS` in the layer. The prose half of the fix is what B2 above turns into a hole. |
| W1 corpus tier blind to the uuid mechanism | fixed, mutation now reds the corpus tier |
| W2 path carve-out lived in the test | fixed, `PATH_FIELDS`/`VERBATIM_FIELDS` in the layer; audited all call sites, all eight genuinely hold paths |
| W3 census hardcodes exit 0 | fixed, observed `"exit": 1` on an unreadable zip, process exits 1 |
| W4 page never calls finish | fixed, `ui.py:556` |
| W5 event cap drops the header | fixed in substance; see W2 above for the residue |
| W6 fingerprint hashes members not documents | **fixed**, 83 `output.document` events with per-document `sha256`, kind, uuid and name |
| W7 hand-picked six of nine fixture needles | fixed, `_fixture_excluded()` derives them from the module |
| W8 README omits cwd and argv | fixed, `README.md:74-75` names the paths |

## The bundle writer against the live evidence

Judged against `dashboard_import_two_phase_materialization.md` rather than
against self-consistency, and I went looking for the untested case that breaks.
I did not find one.

- The directory-entry fix is real and the new gates are real. Deleting the
  `writestr(zip_directory_entry(...))` turns corpus-check red on all five zips
  with exit 1 and fails 7 tests. The replacement checks open both zips with
  `zipfile` rather than through the reader, so they can no longer agree with
  themselves about something neither side can see.
- **The case I expected to break does not.** A selection with no dashboards
  (views and super metrics only) produces a bundle with **zero** directory
  entries, and no live import has ever exercised that. But it is not untested in
  substance: `vcfcf_core/dashboards/packager.py:108` writes `dashboards/` and
  `dashboardsharings/` only inside `if dashboards:`, so the factory's own
  views-only content-import zips have exactly this shape and are known to
  import. Same shape, proven path. No finding.
- The 8.18.7 synthesis is correct and loud. `dashboardsharings/<owner>` is
  created as `[]` where the source has none, and the build report says so in
  full, on the CLI **and** on the page (`ui.py:436` puts `_bundle.render(result)`
  into `build_report`, `uipage.py:443` renders it). The note names the
  consequence the factory packager warns about, that the dashboards import
  private to whoever imports them.
- Member ordering places each directory entry before the members under it and a
  synthesized sharing member beside its `dashboards/<owner>` sibling, which
  matches where all five exports put them.

## If shipped as-is

An admin whose instance carries a name with a Turkish dotted I, a dotless i or a
long s (and this ships worldwide) finds that the tool works until they follow
the README's own instruction to add `--log run.log`, at which point preview dies
with a Python traceback on both the command line and the page. They then mail us
the log, which contains that person's name in clear, under the one key the
redactor was told to leave alone, next to a `run.end` line stating an exit code
the run did not return. The release's headline feature is the thing that breaks
it, and the promise printed at the top of every log is broken by the failure of
the feature that prints it.

Fix B1 and B2 and this is a strong release. Everything else on the branch stands
up: the bundles are proven against a real instance, the gates fail when what they
guard is deleted, the corpus is clean of instance data in text, and the previous
round's findings were genuinely closed rather than papered over.

---

# Round 2: the fix commit (`f53d7e4`), confirmation pass

- Branch `feat/logging`, now **13 commits** over `main`, HEAD `f53d7e4`
- Reviewed: 2026-09-15, one commit over the Round 1 tree (`5b2833c`)
- Scope: the two BLOCKING, five WARNING and three NIT findings above, plus
  whatever the fixes themselves broke. No new lines of enquiry opened.
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 2 WARNING, 2 NIT)

## The headline

**B1 is genuinely and thoroughly fixed. B2's fix reintroduced B6.**

Removing `PROSE_FIELDS` closed the exception-text hole and opened the
mangling hole in the same motion. On the repo's own corpus, a single
`corpus-check --log-level debug` now writes **282 mangled sentences** where
the Round 1 tree wrote **zero**, including, verbatim, the sentence the deleted
`PROSE_FIELDS` comment quoted as its own justification:

```
the tool deciding for the [excluded:person]
```

Everything else on the commit stands up. B1, W1, W2, W3, W4, W5, N1, N2 and
N3 are each independently re-proved below.

## Checks re-run independently

Fresh clone `/tmp/mr2/tree`, fresh venv, scratch `HOME`, corpus copied in. A
second venv at `5b2833c` for the before/after comparison (`main` predates the
log entirely, so the Round 1 tree is the only meaningful baseline for prose).

| Check | Result |
|---|---|
| `pytest -q`, no corpus | 533 passed, 3 skipped |
| `pytest -q`, corpus present | **544 passed**, 0 failed (claim holds) |
| `corpus-check`, 5 zips | exit 0, **5 ok**, stdout **byte-identical to `5b2833c`** |
| select-all bundles vs `5b2833c`, all 5 | **byte-identical** (no bundle shape changed, claim holds) |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345 | byte-identical, all 5 |
| page-built bundle vs CLI-built bundle, all 5 | **byte-identical** |
| select-all document identity | 83/83, 83/83, 158/158, 49/49, 434/434 |
| B1, unicode brute force: every codepoint substituted into a taught name | 18 variants matched, **0 raises, 0 unredacted** |
| B1, adversarial export through the console script at the default level | **exit 0, 0 tracebacks, 0 `log.failed`, 0 occurrences of the name, 46 `[excluded:person]`** |
| B1 guard, injected redactor failure every 17th call | **exit 0**, full stdout, 19 `log.failed`, `run.end` reports `broken: 19`, the exception text itself not written |
| emit guard vs hostile values (`__str__` raises, 20k-deep nesting, bad key) | survives all four, one `log.failed` each |
| named-group count, 2000 owners | compiles and substitutes correctly |
| W1, CLI failing command | process **1**, log `"exit": 1` |
| W1, census crash path | process **1**, log `"exit": 1, "failed": "NotAnExport"` |
| W2, forced batch drop (`event_cap` 10^9 -> 20 mid-session) | `input.fingerprint` **kept**, notice now true |
| W3, owner-keyed call sites audited | all 16 pass genuine owner values or counts; **no caller hand-pseudonymises** |
| B2, 236 field names scanned with a person-bearing exception string | leaks only under the 7 declared `PATH_FIELDS`, which is by design |
| B2, dict keys, nested dicts, lists | all redacted |
| **prose integrity vs `5b2833c`, whole corpus** | **282 mangled sentences, was 0** (B3) |
| mechanism removal, directory entries | corpus-check exit 1, 5 errors; suite **7 failed** |
| mechanism removal, the `emit` guard | suite **1 failed** |
| mechanism removal, `_spellings` | suite **544 passed** (W6) |
| mechanism removal, `_trim` head-by-membership | suite **544 passed** (W7) |
| corpus leak scan, 353 needles vs the new commit and its message | **0 hits** |
| em-dashes, tracked text and branch commit messages | none |
| Python floor gate (`vermin`, floor 3.9) | clean (min 3.8) |
| `actionlint`, both workflows | clean |
| CI log step wiring | log opens `"a"`, both runs land in one file, `check_log` covers both |

## BLOCKING

### B3. Removing the prose exemption reinstated B6: the tool's own English is mangled, 282 times per corpus-check

`src/vcfcf_migrator/runlog.py:195-204` (the comment replacing `PROSE_FIELDS`).

The commit message's claim is the one thing on this branch that does not
survive contact with the corpus:

> "what keeps the tool's own English intact is COMMON_WORDS and the left
> boundary, which are properties of the value"

It does not. The reader harvests person values out of `authsources.json`, and
on `devel-9.0.2.0-2026-09-14-full.zip` the values it teaches are:

```
['member', 'vcf@int.sentania.net', 'userPrincipalName',
 '(&(objectclass=user)(!(objectclass=computer)))', 'VMware Cloud Foundation',
 'CN=vcf,OU=Service Accounts,...', 'v1:oPUb5TI3...', 'VCF Ops MCP',
 'Service Account', 'vcf-ops-mcp', 'vcf-ops-mcp@int.sentania.net']
```

`member` is four characters, so `_MIN_PERSON_LEN` does not stop it, and it is
not in `COMMON_WORDS` (`runlog.py:170`). It is also this tool's own word for a
zip entry, used in most of its explanatory sentences. With the exemption gone,
those sentences are rewritten. Measured, one `corpus-check --log-level debug`
over the five corpus zips:

| | `5b2833c` | `f53d7e4` |
|---|---|---|
| `reason`/`says`/`detail` values containing `[excluded:person]` | **0** | **282** |

The distinct damage:

```
this tool does not read this [excluded:person]'s content, so it is listed and never carried into a bundle
this tool does not read this [excluded:person]'s content, so nothing in it can be selected and none of it is carried
this tool does not understand the [excluded:person], so it cannot be selected and carrying it would be the tool deciding for the admin
policies.xml is in the export but is a [excluded:person] this tool never carries into a bundle
policies.xml is in the export but is a [excluded:person] this tool never carries into a bundle, so it will be missing on import unless the target already has it
the same object in a second [excluded:person]; the first [excluded:person] keeps the node and the bundle still carries both copies
the source export carried no sharing [excluded:person] for this owner and the target requires one; an empty list shares with nobody
one dashboard [excluded:person] per owner, and the manifest counts them the same way
```

This is B6 verbatim, and the third of those lines is the sentence the deleted
comment itself quoted ("the tool deciding for the [excluded:person]") as the
reason the exemption existed. The fix deleted the comment and reproduced the
defect it described.

It misleads in two directions at once. The sentence stops being readable, and
it *asserts a person was found* in a place where the tool found a zip entry.
`reason` is the field the whole log exists for: it is where the tool explains
why it did not carry something. An admin opening a diagnostics file to find
out why `policies.xml` is missing is told it "is a [excluded:person] this tool
never carries".

Nothing catches it: 544 tests pass, the corpus tier passes, and CI's
`check_log` only asserts that fixture needles are absent, never that the
prose is intact.

Authority: Round 1 B6, already fixed once and now regressed; `runlog.py:33`,
the layer owns the rule; the shared reviewer doctrine's silent-downgrade
dimension (unreadable is not compliant); house rule 8.

Fix, smallest correct: make the distinction a property of the value, as the
commit message says it should be, rather than deleting it. Wrap the module's
own literal sentences in a `runlog.prose(...)` marker type that
`Redactor.field` recognises and passes through the uuid and mail rules only.
The exemption's premise was never wrong; only its key was. (Reducing the
reader's over-harvest, so `member` and `userPrincipalName` never enter the
person table, is the root cause and a worthwhile follow-up, but it is the
riskier direction: it trades a readability defect for an under-redaction one,
and it is not the change to make on the release commit.)

## On the judgment call in B2

`tooling` asked us to judge whether removing the exemption outright, rather
than adding the `prose()` marker type, was the right call, arguing "an
exemption nobody uses is a type with no work to do".

**Half right, and the wrong half was acted on.** Removing the *key-based*
exemption is correct and should stand: keying it on a keyword name any caller
can reuse was the defect, and the fourteen `detail=str(e)` sites prove it.

But the premise that nobody uses it is false. It has 282 uses per
corpus-check. They were invisible because it was expressed as a set of key
names instead of a type, which is exactly the argument for making it a type.
`COMMON_WORDS` and the left boundary are not a substitute: they are a
heuristic over a person table that this tool populates with ordinary nouns
harvested from an LDAP config, and a heuristic tuned against harvested content
cannot also protect the tool's own vocabulary, because the two overlap on
`member`.

The marker type is needed. It is also cheap: the values it wraps are literals
in this repo, not caller data.

## WARNING

- **W6. `_spellings` is load-bearing and untested.** `runlog.py:135`.
  Replacing its body with `return [value]` leaves **all 544 tests green**, and
  yet it is the only thing covering values whose case folding changes length:
  a person taught as `Weiß Hausmeister` is redacted from `WEISS HAUSMEISTER`
  with it and **written verbatim without it**. (The Turkish and long-s
  spellings from Round 1 are covered by `re.I` alone; the sharp s is not,
  because Python's `re.I` does not fold `ß` to `ss`.) So the mechanism that
  prevents a person-value leak has no gate, in a codebase that gates the key
  rules, the substitution, the uuid allow-list and the mail rule by exactly
  this mutation. -> Add the `ß`/`SS` case to `tests/test_runlog.py`, so
  deleting `_spellings` reds the suite.

- **W7. The W2 fix made `_trim` O(n) per event at the cap: measured ~1000x
  slowdown, and it too is untested.** `runlog.py:545-570`. Keeping the head by
  membership is correct, but it rescans the whole buffer on **every** event
  once the cap is reached. Measured at the shipped `event_cap = 40000`:
  filling to the cap costs 0.0018 ms/event, the next 5000 events cost **1.67
  ms/event** (8.34 s for 5000). The page keeps events for the whole session,
  so a long `ui` session crosses the cap and then appears to hang. Reverting
  the fix to the old slot-based slice also leaves **all 544 tests green**, so
  neither the correctness nor the cost is gated. -> Compute the head once and
  keep it in its own list (or cache it and invalidate on a head event), and
  add the batch-drop case as a test.

## NIT

- **N4.** `runlog.py:299`. `_compiled`'s docstring still says "Replacements
  are therefore keyed by the lowercased value." That is the sentence that
  described the B1 defect, and it is now false: the body immediately below it
  explains at length that they are keyed by named group. One stale line, but
  it is the one a future reader would trust.

- **N5.** `README.md:43`. "minutes and sometimes longer" is a real improvement
  over "a few minutes", and the remedy is now there. But the evidence
  (`dashboard_import_two_phase_materialization.md`, `ui_deep_links.md`) says
  **hours**, and "sometimes longer" is the one wording that keeps the reader
  from knowing whether to wait ten minutes or come back after lunch. Say
  hours.

## Verified fixed this round

| Round 1 | Status |
|---|---|
| B1 unicode case divergence | **fixed, and structurally.** The pattern names its own replacement, so there is no second definition of case to disagree with. Brute-forced every codepoint: 0 raises, 0 unredacted. Proved through the console script on an adversarial export at the default level: exit 0, no traceback, zero `log.failed`, zero occurrences of the name. |
| B1 `emit()` has no guard | **fixed.** Injected a failure into every 17th redaction: 19 `log.failed`, exit 0, full stdout, and `run.end` reports `broken: 19` so the loss is announced rather than silent. The dropped event is the only loss, and the failing event's own text is correctly not written. Deleting the guard reds one test. |
| B2 exception text under `reason`/`detail` | **hole closed** (236 field names scanned, dict keys, nested dicts, lists: nothing leaks outside the seven declared `PATH_FIELDS`), **new hole opened**: see B3. |
| W1 exit code on the crash path | **fixed in one place.** `finish()` takes the exception and reports 1. CLI and census both: process 1, log 1. |
| W2 event cap keeps the head by coincidence | **fixed.** Forced batch drop keeps `input.fingerprint`; the notice is now true. Cost: see W7. |
| W3 dict keys never redacted | **fixed.** Keys go through the layer; `bundle.py:259` no longer calls `runlog.owner()`; audited all 16 owner-keyed call sites and none passes a non-owner. |
| W4 README's absolute promise | **fixed.** States both limits, and "three characters or fewer" matches `_MIN_PERSON_LEN = 4`. |
| W5 "a few minutes" | **fixed in substance**, see N5 for the residue. |
| N1 directory-entry docstring | **fixed.** Says it mirrors the packager, names the three fields it diverges on, and says why the packager is the shape with evidence. |
| N2 `output.fingerprint` omits directory entries | **fixed.** Observed `"directory_entries": ["dashboards/", "dashboardsharings/"]`. |
| N3 CI never passes `--log` | **fixed.** Two commands at `--log-level debug`, log rendered, and `ci_checks.py log` asserts required codes, no `log.failed`, `run.end` exit 0, and no fixture person or secret with needles derived from the module. The log opens in append mode, so both runs are covered. |

## If shipped as-is

The tool no longer breaks when you turn the log on, which was the release's
one unshippable defect, and that is now proved rather than asserted. What an
admin gets instead is a diagnostics file in which the tool's own explanations
have been overwritten: the line telling them why `policies.xml` did not come
across reads "policies.xml is in the export but is a [excluded:person] this
tool never carries into a bundle". They mail us that file, and the answer to
their question has been redacted out of it by a rule aimed at somebody else's
name. Fix B3 and this is the release.

---

# Round 3: the sign-off pass (`a7dd530`), whole branch as a download

- Branch `feat/logging`, now **14 commits** over `main` (`origin/main` =
  `1e2bfbf`), HEAD `a7dd530`, frozen, unpushed, working tree clean
- Reviewed: 2026-09-15, one commit over the Round 2 tree (`f53d7e4`)
- Scope: the Round 2 BLOCKING, two WARNING and two NIT findings, plus the
  question the brief asks last: is this fit to be downloaded and run by
  someone who is not us. Nothing else opened unless it would mislead an
  admin, ship a wrong number, or make a bundle unimportable.
- Verdict: **CHANGES REQUESTED** (1 BLOCKING, 1 WARNING, 2 NIT)

## The headline

**B3 is fixed, and fixed the way the marker type was supposed to work: the
exemption is now a property that composition cannot inherit.** Every string
operation on a `Prose` value returns a plain `str`, so the only way to mark
computed text is to write `prose(...)` around it, and I checked every place
that does.

The blocker this round is on a different surface and it is the same class the
branch exists to close. **`vcfcf-migrator ui --log run.log` writes a four-line
log containing nothing the page did**, on the one command the README calls
"does the whole job", using the one instruction the README gives for reporting
a problem. The file exists, parses, and ends `"exit": 0`. It is reports-green
while broken, aimed at the admin who cannot see the repo.

## Checks re-run independently

Fresh clone `/tmp/mr3/tree`, fresh venv, scratch `HOME`, corpus copied in.
Second venv at `f53d7e4` and a third at `main` for the comparisons.

| Check | Result |
|---|---|
| `pytest -q`, no corpus | 538 passed, 3 skipped |
| `pytest -q`, corpus present | **549 passed**, 0 failed (claim holds) |
| `corpus-check --log-level debug`, 5 zips | exit 0, **5 ok**, **8063 events** (claim holds) |
| **prose integrity, whole corpus log** | **0 mangled sentences** in `reason`/`says`/`detail`/`note`, **0 `log.failed`** (was 282 and 0) |
| the two sentences Round 2 quoted | both read correctly: "policies.xml is in the export but is a member this tool never carries into a bundle"; "...would be the tool deciding for the admin" |
| the same word as data | `name="member of staff dashboard"` logs as `"[excluded:person] of staff dashboard"` |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345 | byte-identical, all 5 |
| bundles vs the Round 2 tree (`f53d7e4`) | **byte-identical, all 5** (no bundle shape moved) |
| page-built bundle vs CLI-built bundle | **byte-identical, all 5** |
| select-all document identity | 83/83, 83/83, 158/158, 49/49, 434/434 |
| closure audit, every node as a seed, all 5 zips | **802 seeds, 0 unclosed edges, 0 over-carried keys** |
| census on `main` vs branch (`--json`) | **byte-identical**, 1512 bytes (claim holds) |
| `prose()` argument audit, my own AST walk over `src/` + `tools/` | 55 pure literals, **2 f-strings**, both interpolating package constants only (`VERSION_FLOOR_TEXT`, `missing_reason()`); **nothing computed is marked** |
| unmarked literal `reason`/`says`/`detail`/`note` anywhere in `src/` + `tools/` | **0** |
| composition cannot inherit the marker | `+`, f-string, `.join`, `%`, `.format` on a `Prose` all degrade to `str` and are scanned: 5/5 redacted |
| key rules still beat prose | `username=`, `owner=`, `password=`, `value=` given `prose()` still excluded / pseudonymised / dropped |
| mail and uuid rules still apply inside prose | `[excluded:mail]`, `[excluded:id]` |
| mechanism removal, one literal `reason` unwrapped | AST gate **1 failed**, naming the file and line |
| mechanism removal, key-based exemption reintroduced | **4 failed** (`no_field_name_exempts`, `exception_message_carrying_a_person`, `not_prose_however_it_is_keyed`) |
| mechanism removal, `Prose` unrecognised in `value()` | **1 failed** |
| mechanism removal, `_spellings` neutered to `return [value]` | **1 failed** (W6 fixed) |
| mechanism removal, `_trim` O(n) rebuild restored | **1 failed** at 2.20 ms/event against the 0.05 bar (W7 gated) |
| mechanism removal, head-by-membership deleted | **2 failed** |
| mechanism removal, directory entries | corpus-check exit 1, 5 errors; suite **7 failed** |
| `_trim` cost at the shipped cap (40000) | **0.00202 ms/event** past the cap, against 0.0018 filling. The 1000x is gone |
| corpus leak scan, 556 needles vs **all 116 blobs of all 14 revisions**, plus commit messages | **0 instance hits** (3 hits are the English words "summary", "percentage", "Administrator") |
| screenshots, read as pixels | both still devel-sourced, owner `29c1613f-...`, unchanged, covered by the 2026-09-14 authorization |
| em-dashes, tracked text and branch commit messages | **none** |
| Python floor gate (`vermin`, floor 3.9 from `ci_checks.py`) | clean (min 3.8) |
| `actionlint`, both workflows | **exit 0** |
| README first command, verbatim | serves; `GET /` returns **200**, 195954 bytes, correct title, 0 tracebacks |
| README's other commands (`inspect`, `tree`, `preview`, `build`, `--help`) | all exit 0, preview 11951 bytes, bundle 62943 bytes |
| **`ui --log`, the README's own reporting instruction** | **4 events, none of them the page's** (B4) |

## BLOCKING

### B4. `--log FILE` is accepted and advertised on `ui`, and silently ignored: the log of a page session contains nothing the page did

`src/vcfcf_migrator/ui.py:107-134` (`PageState.__init__` calls `self.open_log()`),
`ui.py:147` (`_runlog.resolve_destination(None)`), `src/vcfcf_migrator/cli.py:360-364`
(`cmd_ui` threads `corpus` and `source_version` to the page and not the log).

`main` opens the run log from `--log` and writes the header into it. `PageState`
then builds its **own** log from `resolve_destination(None)`, which reads the
environment and the settings file and never the command line, and repoints
`set_current` at it. The page's log has `stream=None`, so every event the page
writes (read, graph, selection, closure, preview, build) goes to an in-memory
buffer and to no file, while the CLI's log holds the header and nothing else.

Measured, driving exactly what the console script does:

```
$ vcfcf-migrator ui my-export.zip --source-version 9.0.2 --log run.log --log-level debug
   size after header:          0
   size after PageState:       0
   size after a page build:    0
   size after finish/close: 1433      <- 4 lines
{"event":"log.contents", ...}
{"event":"run.start",   ...}
{"event":"log.level", "level":"debug","level_from":"command line"}
{"event":"run.end", "exit":0, "what":"ui", "events":3, ...}
```

Four lines, `"events": 3`, exit 0. The same session with
`VCFCF_MIGRATOR_LOG=run.log` instead writes **427 events**. So the machinery
works; it is the flag that does not reach it.

This is not an undocumented corner. `vcfcf-migrator ui --help` prints, under the
`ui` subcommand's own options:

```
--log FILE   write a run log to FILE (- for stderr; also VCFCF_MIGRATOR_LOG)
```

and `README.md:74`, the only sentence in the README about logging, is
`--log run.log` with no mention of the page control or the environment
variable, under the heading **Reporting a problem**: "records what it did and
why, in enough detail to diagnose a failure without the export." On the
surface `README.md:30` calls "does the whole job", it records none of what it
did, and the export is exactly what the admin will not be sending.

Every other global flag is threaded to the page (`corpus_cli`,
`source_version_cli` at `cli.py:363-364`, and `--source-version 9.0.2` in the
README's first command is honoured). The log destination is the one that is
not, so nothing in the shape of the code says the flag is special, and nothing
in its output says it was ignored.

Authority: spec §Logging (the log is the diagnosis path); `README.md:74`, the
instruction an admin will follow; the tool's own `ui --help`; the shared
reviewer doctrine's silent-downgrade dimension, and reports-green-while-broken;
house rule 8, done means seen working.

Fix, smallest correct: thread the CLI log settings into the page the way the
corpus and the source version already are, so `PageState.open_log` resolves
with the command line's value on first open (`serve(..., log_cli=args.log,
log_level_cli=args.log_level, log_format_cli=args.log_format)`), or have
`PageState` adopt the already-open run log when `main` has opened one rather
than building a second. Either way, one test that runs `ui`'s own path with
`--log` and asserts the file holds more than the header, which is the gate that
would have caught this.

## WARNING

- **W8. The head is kept by membership but never deduplicated, so a settings
  save grows it without bound and the run header that survives truncation is
  the stale one.** `src/vcfcf_migrator/runlog.py:501-510` (the `events`
  setter), `ui.py:160`. The setter partitions a carried-over buffer into
  `_head`/`_tail` with no dedup, while `_keep` dedups first-one-wins. Two
  consequences, both measured:

  ```
  50 settings saves:  head = 101 events  (log.contents x50, run.start x50, input.fingerprint x1)
  1 settings save + truncation: run.start kept = ['OLD']   <- the header from before the change
  ```

  `_trim` never drops from `_head`, so the cap governs the tail only and the
  head grows one `log.contents` and one `run.start` per save in the one
  long-lived process. And because `_keep` keeps the first, the `run.start`
  written *after* the admin changed the log level to diagnose something is the
  one eligible to be dropped, while the pre-change header is preserved. The
  truncation notice this same commit rewrote says "the contents line, the run
  header and the input fingerprint are kept whatever else goes"; it keeps *a*
  run header, and it is the wrong one. Not a hang and not a data loss at
  realistic save counts (101 events against a cap of 40000), which is why this
  is a warning and not a blocker, but it is a defect of the fix under review
  and the diagnostics file is where it shows. → Dedup in the setter the same
  way `_keep` does, and make the rule last-one-wins for `run.start` so the head
  describes the run the events below it came from.

## NIT

- **N6.** `runlog.py:414`. `Redactor._is_prose` is defined and never called;
  `value()` inlines `isinstance(value, Prose)` at line 449. One of the two is
  the answer to "how do I ask whether this is prose", and a future reader will
  find the dead one first.

- **N7.** `CHANGELOG.md:3`. The release commit's changelog is still headed
  `## Unreleased`. The release workflow does not read it (the GitHub Release
  notes are a literal string in `release.yml`), so no wrong number ships, but
  the file a downloader opens to see what `v0.1.0` contains says the contents
  are unreleased.

## Verified fixed this round

| Round 2 | Status |
|---|---|
| B3 the tool's own English mangled 282 times per corpus-check | **fixed, and structurally.** 0 mangled over 8063 events at debug; both quoted sentences read correctly. The exemption is `Prose`, a `str` subclass; `value()` checks the type. Composition cannot inherit it: `+`, f-string, `.join`, `%` and `.format` all return plain `str` and are scanned (5/5 redacted), so the only way to mark computed text is to write `prose()` around it deliberately. I audited every one: 55 pure literals and 2 f-strings, both interpolating package constants only (`VERSION_FLOOR_TEXT`; `missing_reason()`, whose two returns are literals). **Nothing computed is marked.** Removing the type recognition reds 1 test. |
| B3 gate, "the gate they say was missing both times" | **real, and not a tautology.** Unwrapping one literal `reason` reds the AST test and names `corpus_check.py:252`. It would have flagged the key-based version, where all 51 literals were unwrapped. Reintroducing a key-based exemption on top of the marker reds **4** other tests, so both shapes are now gated, not just the one that happened last. Scanned for what the gate cannot see: **0** unmarked literal `reason`/`says`/`detail`/`note` anywhere in `src/` or `tools/`. Two residual limits worth knowing rather than fixing: the gate globs the package directory only, so `tools/corpus_census.py` is outside it (it passes `detail=str(e)` only, correctly unmarked), and it does not inspect the *inside* of a `prose(f"...")`, which is why I audited those two by hand. |
| B2 exception text, still closed | **closed.** A person's name raised as a `KeyError` is excluded under `detail`, `reason`, `says` and `note` alike; no field name exempts anything. |
| W6 `_spellings` load-bearing and ungated | **fixed.** Neutering it to `return [value]` reds the suite. The German sharp s is the right and only case it earns: `re.I` covers Turkish and long s on its own. |
| W7 `_trim` O(n) per event at the cap | **fixed.** 0.00202 ms/event past the shipped cap of 40000, against 0.0018 ms while filling, so the 1000x is gone and the page cannot appear to hang. Restoring the rebuild reds the test at 2.20 ms against a 0.05 ms bar, and the test times at the shipped cap rather than a small one, which is what made the first version of it pass against the defect. The batch-drop case is gated separately (5000 events, cap 200) and deleting the head list reds 2 tests. Residue: W8 above. |
| N4 `_compiled` docstring described the defect it used to have | **fixed.** Now says the replacement comes from the group that matched. |
| N5 "sometimes longer" | **fixed.** `README.md:42` reads "minutes or hours", and the remedy (open the dashboard once) is there. |

## The branch as the thing an admin downloads

Read as a stranger with no context, which is the last thing the brief asks for.

- **The README's claims are true of the code**, with one exception. The
  people paragraph now states both limits and "three characters or fewer"
  matches `_MIN_PERSON_LEN = 4`. The settling paragraph matches
  `dashboard_import_two_phase_materialization.md`. The object kinds listed
  match what the loaders handle. The exception is the logging sentence, which
  is B4.
- **The first command runs**, verbatim, and the page it serves answers `GET /`
  with 200 and 195954 bytes of real listing, titled for the export. Every
  other command the README names runs and produces a file.
- **The screenshots are current and authorized**, unchanged from Round 1,
  devel-sourced, covered by Scott's 2026-09-14 words recorded in
  `docs/README.md`.
- **The release workflow produces what it says.** It refuses a tag not
  reachable from `main`, refuses a tag whose installed version does not match,
  builds four binaries (linux, windows, macos-arm64, macos-x86_64), smokes
  every subcommand the binary claims from a directory holding nothing but the
  binary, asserts the binary reports the tag's version rather than a dev
  version, and publishes idempotently per tag. `actionlint` is clean on both
  workflows and every action is pinned by sha.
- **No instance data reaches the download.** 556 needles derived from the
  corpus against all 116 blobs of all 14 revisions and every commit message:
  three hits, all ordinary English words.

## If shipped as-is

An admin downloads the binary, runs the one command the README gives, uses the
page the README says does the whole job, and builds a bundle that is correct.
Something then goes wrong on import. They follow the README's one instruction
for reporting a problem, add `--log run.log`, reproduce it on the page, and
mail us a file with four lines in it: a contents notice, a start, a level, and
`"exit": 0, "events": 3`. Nothing they did is in it. We ask them to do it
again, and the second file is identical, because the flag they are using does
nothing on the command they are using and neither the tool nor the README says
so.

That is a narrow defect with a small fix, and it is the whole of what stands
between this branch and a release. The logging layer itself is now in good
order and proved rather than asserted: the exemption is a type that
composition cannot spread, every literal is marked and nothing computed is,
both failure shapes are gated by mutation, the buffer is cheap at the cap it
ships with, and the corpus is clean of instance data in text and in pixels.
Fix B4 and W8 and this is the release.


---

# Round 4: the confirmation pass (`6419ea0`), and the release check

- Branch `feat/logging`, now **15 commits** over `main`, HEAD `6419ea0`,
  frozen, unpushed, working tree clean
- Reviewed: 2026-09-15, one commit over the Round 3 tree (`a7dd530`)
- Scope: the four things the brief names (B4, the flush that fell out of
  proving it, the `events` setter dedup, the two nits), plus the full release
  battery re-run. Nothing else opened unless it would mislead an admin, ship a
  wrong number, or make a bundle unimportable.
- Verdict: **APPROVE** (0 BLOCKING, 1 WARNING, 1 NIT)

## The headline

**B4 is fixed, and the flush that fell out of proving it is the most valuable
thing on this commit.** The page now writes the log the flag asks for, and a
page killed outright keeps its tail: on a `SIGKILL` mid-session the file ends
with `run.end` and 327 events where the same session without the flush ends
mid-story on `closure.picked` at 293. That is the difference between a support
case you can answer and one you cannot.

The `events` setter fix half-lands. The unbounded head is genuinely gone (3
events after fifty saves, was 101). The other half, which header survives, does
not hold in the flow the docstring describes it for: `_keep` is first-one-wins
and `header()` runs *after* the setter, so the newly written `run.start` lands
in the tail and the head keeps the previous open's header. The new test asserts
on a synthetic list the page never produces, so it is green while the claim is
false in the page. It is a warning, not a blocker: the wrong field only reaches
an admin in a log truncated past 40000 events.

## Checks re-run independently

Fresh clone `/tmp/mr4/tree` at `6419ea0`, fresh venv, scratch `HOME`, corpus
copied in. A second tree at `a7dd530` for the byte comparison and three
mutation trees.

| Check | Result |
|---|---|
| `pytest -q`, corpus present | **553 passed**, 0 failed (was 549; +4 new) |
| `corpus-check`, 5 zips | **exit 0**, 5 ok lines, all round trip, 2 directory entries each |
| select-all document identity | 83/83, 83/83, 158/158, 49/49, 434/434 |
| closure audit, every node as a seed, all 5 zips | **802 seeds**, closure idempotent on all, 0 over-carry |
| determinism, separate processes, `PYTHONHASHSEED` 0 vs 12345 | byte-identical, all 5 |
| select-all bundles vs the Round 3 tree (`a7dd530`) | **byte-identical, all 5**; no bundle shape moved |
| page-built bundle vs CLI-built bundle | **byte-identical** (page build over HTTP, `b661c611...`) |
| **`ui --log`, end to end over HTTP, SIGINT to stop** | **442 events, 28 kinds, 0 `log.failed`**, `input.fingerprint` / `graph.built` / `closure.picked` / `output.fingerprint` / `bundle.written` / `run.end` all present |
| **137239 of 137493 bytes on disk before any shutdown ran** | the file is current while the page is still up |
| **`SIGKILL` mid-session, flush vs no flush** | **327 events ending `run.end`** vs **293 ending `closure.picked`** |
| flush cost, micro-benchmark, 1k/10k/50k events | **+0.0012 ms/event** (0.0112 with, 0.0100 without) |
| flush cost, `corpus-check --log-level debug`, 8063 events, 3 runs each | 13.97/14.18/14.77 s with, 13.96/14.12/14.18 s without: **inside noise** |
| prose integrity, 24189 events at debug | **0 mangled** `reason`/`says`/`detail`/`note`, **0 `log.failed`** |
| `events` setter, 50 page settings saves | head **3** (was 101); **the head's `run.start` is the previous open's** (W9) |
| mechanism removal, the `_emit` flush | suite **1 failed** (not a tautology) |
| mechanism removal, the `ui` log wiring | suite **1 failed**, names the missing file |
| mechanism removal, the setter dedup | suite **1 failed** |
| mechanism removal, one literal `reason` unwrapped | AST gate **1 failed**, names `corpus_check.py:252` |
| mechanism removal, directory entries | corpus-check **5 error lines**; suite **7 failed** |
| `ui --log -` and `--log-format text`, newly reachable | serve and re-open cleanly; **`sys.stderr` not closed** by a settings save |
| corpus leak scan, 555 needles vs **all 150 blobs of all 15 revisions** plus every commit message | **0 instance hits** (5 hits: `admin`, `administrator`, `custom groups`, `percentage`, `summary`) |
| screenshots | **unchanged since Round 1**, no `docs/` diff on this commit; covered by the 2026-09-14 authorization |
| em-dashes, tracked text and branch commit messages | **none** |
| Python floor gate (`vermin`, floor 3.9 from `ci_checks.py`) | clean (min 3.8) |
| `actionlint`, both workflows | **exit 0** |

## 1. B4, `ui --log`: confirmed fixed

Threaded exactly the way `corpus_cli` and `source_version_cli` already were:
`cli.py:363-368` passes all three to `serve`, `serve` and `make_server` pass
them to `PageState`, and `PageState.open_log`/`log_settings` resolve with them
instead of `None`. No second mechanism, no special case.

Driven end to end through the installed console script over HTTP (select-all,
build, render, then Ctrl-C): **442 events, 28 kinds, 0 `log.failed`**, and every
event the page produced is in the file, `bundle.written` and `run.end` included.
The page-built bundle is byte-identical to the CLI-built one. Reverting just the
three `resolve_*` calls to `None` reds
`test_the_ui_command_writes_the_log_the_flag_asks_for`, so the surface two
rounds proved through `preview` and `build` is now gated at the surface that
failed.

`ui --log -` and `ui --log-format text` are newly reachable through the same
change and I checked them rather than assumed: a settings save closes the old
log without closing `sys.stderr` (`runlog.py:756` excludes it), and the page
keeps working across two re-opens.

One observation, not a finding: the file now holds two `run.start` lines (the
CLI's, `argv` the real command line, and the page's, `argv ["ui"]`) and its last
line is the CLI log's own `run.end` reporting `"events": 5` under `"what":
"ui"`, directly below the page's `"events": 435` under `"what": "page"`. Each
number is true of the log that wrote it and `what` tells them apart, so nothing
is wrong, but a diagnostician reading the tail sees the small number last.

## 2. The flush: confirmed, and it earns its keep

- **Not a tautology.** Removing `self.stream.flush()` from `_emit` reds
  `test_each_event_reaches_the_file_before_the_next_one` with `assert 0 == 2`:
  without it nothing is on disk at all, because two short lines sit well inside
  the 8 KiB text buffer.
- **The benefit is real and I forced the case the commit message describes.**
  A page `SIGKILL`ed mid-session (no unwinding, no `close()`, nothing runs on
  the way out) leaves **327 events ending in `run.end`** with the flush, and
  **293 events ending mid-story on `closure.picked`** without it. The lost tail
  is exactly the part a support case is about.
- **The cost claim is conservative.** Measured delta is **0.0012 ms/event**
  (0.0112 with, 0.0100 without, stable across 1k/10k/50k), not 0.007. At the
  heaviest realistic volume the repo has, `corpus-check --log-level debug` at
  8063 events, three runs each way are indistinguishable from noise
  (13.97/14.18/14.77 s against 13.96/14.12/14.18 s). It is `flush()`, not
  `fsync()`, so it is one write syscall and buys survival of process death,
  which is the stated goal, not of power loss, which is not claimed.
- **Nothing else depends on buffering.** There are exactly two `self.stream.write`
  sites (`runlog.py:600` in `_failed`, `runlog.py:621` in `_emit`) and both now
  flush. Nothing reads a log while it is open: `save_diagnostics` reads events
  from memory, `log-render` reads a finished file. The two-logs-appending-to-one-file
  arrangement that `ui --log` now creates is in fact made safe by this change,
  since ordering between the two streams is now write order.

## 3. The `events` setter: count confirmed, which-survives not

Confirmed fixed, measured on a real `PageState` doing 50 settings saves: head is
**3** (`log.contents`, `run.start`, `input.fingerprint`), was 101. `_keep` and
`_trim` are undisturbed: both their mutation gates still red (the prose,
directory-entry, and setter mutations each red exactly the test that owns them),
and the suite is 553 green.

See W9 for the half that does not hold.

## 4. The two nits: confirmed

- `Redactor._is_prose` is gone, with **no remaining reference** anywhere in
  `src/`, `tests/` or `tools/`; `value()` keeps the single inline
  `isinstance(value, Prose)` at `runlog.py:446`.
- `CHANGELOG.md:3` reads `## v0.1.0 (2026-09-15)`.

## WARNING

- **W9. The head still keeps the header of the *previous* open, not the one the
  log is running under, so the docstring and the new test describe behaviour the
  page does not have.** `src/vcfcf_migrator/runlog.py:508-533` (the setter),
  `runlog.py:544-546` (`_keep`), `src/vcfcf_migrator/ui.py:167-175`.

  The setter is last-one-wins, which is right. But `PageState.open_log` assigns
  the carried events *first* and calls `header()` *after*, and `_keep` is
  first-one-wins, so the fresh `run.start` finds a `run.start` already in the
  head and is appended to the **tail**, where `_trim` may drop it. Measured on a
  real `PageState`:

  ```
  after 50 settings re-opens:  head = 3        (fixed)
                               head run.start  = the previous open's
                               tail run.start  = the current one
  ```

  With content attached, so it is not academic: declare `9.0.2` on the page, then
  change the log level, then truncate.

  ```
  head run.start source_version = None      <- kept
  tail run.start source_version = '9.0.2'   <- dropped by truncation
  after truncation, run.start kept: [None]
  ```

  The header that survives says no source version was declared while the run
  ran under 9.0.2, and the source version is the field the floor check, the
  container rebuild and the build refusal all hang off. The setter's own
  docstring says "the last `run.start` is the one this log is running under, so
  that is the one kept", and in the page that is the one discarded.

  `test_a_head_event_is_kept_once_and_the_newest_one_wins` passes because it
  assigns a synthetic list holding two `run.start`s, which the page never
  produces: in the page the two headers arrive through two different doors, the
  setter and `_keep`, and only the setter was fixed.

  Why this is a warning and not a blocker: the head only decides what survives
  truncation, which needs a page session past `event_cap = 40000`, and
  `save_diagnostics` reads the newest header out of memory (`_last_event`
  scans in reverse and finds the tail copy) so an untruncated diagnostics file
  is correct. It is a wrong number in a rare file, not a broken tool.

  → Let a head event written by `_keep` replace the one in its slot rather than
  fall through to the tail (or call `header()` before the carry-over assignment,
  so the setter sees both and its last-one-wins rule decides). Gate it by driving
  `PageState.open_log` twice and asserting the head's `run.start` is the second
  one, rather than by assigning a list by hand.

## NIT

- **N8.** `runlog.py:600`, the `_failed` write path. Removing *that* flush alone
  leaves all 553 tests green; only the `_emit` one is gated. It is the less
  important of the two (a `log.failed` line is followed by ordinary events that
  flush anyway), but it is the line that records why an event was dropped, and
  it is one assertion away from being covered by the same test.

## Verified fixed this round

| Round 3 | Status |
|---|---|
| B4 `ui --log` accepted and silently ignored | **fixed.** 442 events, 28 kinds, 0 `log.failed` end to end over HTTP through the installed console script; the page's bundle is byte-identical to the CLI's. Threaded the same way as the corpus and the source version, no special case. Reverting the three `resolve_*` calls reds the new test. `ui --log -` and `--log-format text`, reachable for the first time, both behave. |
| W8 head grows without bound on settings saves | **fixed.** 3 after fifty saves, was 101. |
| W8 the surviving header is the stale one | **not fixed**, see W9. Fifty saves stale is now one save stale. |
| N6 `Redactor._is_prose` dead | **fixed**, and no reference remains. |
| N7 `CHANGELOG.md` headed `## Unreleased` | **fixed**, `## v0.1.0 (2026-09-15)`. |
| new: a killed page lost its tail | **fixed, and proved by forcing it.** `SIGKILL` keeps 327 events ending `run.end` against 293 ending mid-story. Cost is inside measurement noise at 8063 events. |

## Is it fit to be downloaded and run by someone who is not us

**Yes.** Asked one last time, and answered against the artifact rather than the
diff.

- The README's claims are now true of the code, including the logging sentence
  that was the last exception. An admin who follows "add `--log run.log`" on the
  command the README says does the whole job gets a file with what they did in
  it, current while the page is still up, and complete even if they kill it.
- What the tool produces has not moved: all five select-all bundles are
  byte-identical to the Round 3 tree and to each other across hash seeds, the
  page builds the same bytes as the CLI, 802 closure seeds are clean, and
  `corpus-check` is green on all five real exports with the directory entries a
  live import refuses a bundle without.
- The gates fail when what they guard is deleted: the log wiring, the flush, the
  setter dedup, the prose marker and the directory entries each red a test that
  names them, and the prose gate names the file and line.
- Nothing of the instance reaches the download. 555 needles against all 150
  blobs of all 15 revisions and every commit message: five hits, all ordinary
  English words. The two screenshots are unchanged and covered by Scott's
  2026-09-14 authorization.
- The workflows lint clean, every action is pinned by sha, and the release job
  refuses a tag that is not on `main` or whose installed version does not match.

W9 and N8 are the residue, both inside the logging layer, neither able to
mislead an admin outside a log truncated past 40000 events. Nothing on this
commit blocks the tag.
