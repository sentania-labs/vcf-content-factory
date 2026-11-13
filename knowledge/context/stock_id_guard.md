# Stock content id guard (issue #345)

VCF Operations tracks pak and content-import content by id. Installing
content overwrites any existing object with the same id; uninstalling a pak
deletes every id it shipped. Content that defines a view, dashboard, report
template, super metric, symptom, alert or recommendation under an id the
product ships as its own therefore overwrites the stock object on install
and deletes it on uninstall. That is how the retired factory vCommunity
port deleted 64 stock views from lab-b (9.0.2), and the upstream Python
vCommunity packs ship 117 (v0.2.8 to v0.3.1) and 120 (the e1 0.8.1 build)
stock view ids. Lesson: `knowledge/lessons/pak-content-must-not-reuse-stock-ids.md`.
Investigation:
`knowledge/context/investigations/2026-11-11-devel-stock-views-deleted-by-vcommunity-pak-uninstall.md`.

Only definitions count. A dashboard widget, report section, alert symptom
set or recommendation ref, or a policy enablement that points at a stock id
is a reference and is legal.

## What it is

| Piece | Where |
|---|---|
| Baseline (data: ids, display name, versions) | `src/vcfcf_core/stock_ids/stock_ids_baseline.json` |
| Scanner, loader, allowlist, check, standalone-check body | `src/vcfcf_core/stock_ids/guard.py` (stdlib only, self-contained) |
| Generator (pure) | `src/vcfcf_core/stock_ids/generate.py` |
| Factory CLI, scoped allowlists, validate, import and build helpers | `src/vcfcf_packaging/stock_ids.py` |
| Buildkit copies | `sdk_buildkit/stock_ids.py` (guard.py verbatim) and `sdk_buildkit/stock_ids_baseline.json` |

`guard.py` finds the baseline beside itself
(`Path(__file__).with_name(...)`), so the factory and the kit load the same
file with no repo-layout assumption. Pak repos' CI gets it in the kit
(buildkit 1.0.29 and later; see the buildkit release notes for the pin).
The `vcfcf_core` wheel carries it as package data; a test asserts it is in
the wheel and in the kit tarball, byte-equal to `src/`.

### Baseline format (`vcfcf-stock-ids/1`)

A JSON object: metadata (`about`, `generated`, `regenerate`, `rule`,
`sources`, `counts`, `candidates_not_included`) and
`ids: {<type>: {<id>: {"name": ..., "versions": [...]}}}`. Types:
`view`, `dashboard`, `report`, `supermetric`, `symptom`, `alert`,
`recommendation`. Ids compare case-insensitively, within a type. One line
per id so a regeneration diffs cleanly. Source instances are recorded by
neutral labels, never host names or paths.

### Fail closed

A missing, unreadable, malformed or empty baseline raises
`StockIdBaselineError`; every caller turns that into a failed build, a
failed validate or a refused import or install. Same posture as the defect
gate.

Content the scanner cannot read is never reported clean. Each of these is
an `Unreadable` record (location and reason), and every gate treats one as
"cannot check": a build fails, an import or pak install is refused
(`--allow-stock-ids` does not cover it), and `stock-id-check` lists it as
`CANNOT CHECK` and exits 1:

- an archive nested more than 6 levels deep (a pak is pak > adapters.zip >
  views.zip, three; an export's dashboard zips are two);
- a member that looks like a zip but does not open;
- a member over 512 MB (zip-bomb guard), an encrypted member, a member in
  a compression method the stdlib does not read, or any member read error;
- text with a UTF-16 or UTF-32 byte-order mark (or plainly UTF-16 without
  one) that does not decode, XML in a declared encoding Python cannot
  decode, and JSON that carries a `"dashboards"` or `"formula"` key but
  does not parse.

UTF-16 and UTF-32 XML and JSON are decoded by byte-order mark and checked
like UTF-8. XML that does not parse is still scanned for definition tags,
so a malformed file cannot hide one.

## Where it runs

| Path | What is checked | On a hit |
|---|---|---|
| `validate-sdk` (factory and kit) | bundled content of adapter.yaml (`sdk_builder.check_stock_ids`) | error, exit 1 |
| `build-sdk` (factory and kit) | the same, before the compile; then every definition in the built pak (`_gate_built_pak_stock_ids`) | build fails; a `--release` build deletes the pak |
| `vcfcf_packaging build` / `build-discrete` / `release` / `publish` | the bundle's loaded content, then the assembled zip (`guard_bundle` in `builder.build_bundle` and `discrete_builder._assemble_zip`) | `BundleValidationError`, nothing written |
| `vcfcf_supermetrics`, `vcfcf_dashboards`, `vcfcf_symptoms`, `vcfcf_alerts`, `vcfcf_reports` `validate` | the definitions each loads (symptom, alert and recommendation ids as rendered into AlertContent) | `STOCK-ID:` error, exit 1; the `OK:` line prints only after the check passes |
| every factory content import (`vcfcf_dashboards.client.import_content_zip`: dashboards, views, reports and super metric sync, bundle sync) | the zip about to be posted | refused before any request |
| `vcfcf_managementpacks install <pak>` | every definition in the pak, offline, before login | refused unless `--allow-stock-ids` (then a warning listing them) |
| `python3 -m vcfcf_packaging stock-id-check <path>...` / `python3 -m sdk_buildkit stock-id-check` | read-only report for any packed or unpacked pak, content zip or export | exit 2 (0 clean, 1 cannot check) |

`vcfcf_customgroups` has no check (custom group ids are server-assigned).
`vcfcf_managementpacks validate` and the Tier 1 MPB build have none: MPB
paks ship empty content directories. The distribution zips' `install.py`
is not changed: what it installs passed the bundle build check.

### What the output claims

A pass says what was compared, never just "no stock id". The built-pak
gate and `stock-id-check` print the number of distinct definitions
compared per type, the baseline's size and versions, and the types the
baseline holds no ids for (today super metrics and recommendations): a
definition of such a type is scanned and counted as "not checked", since
no stock id of that type is known. When a path holds no content
definitions at all (a YAML source tree, an adapter-only pak),
`stock-id-check` says "nothing to check" and exits 1; YAML is checked by
`validate` and `validate-sdk`, not by this command. Every `stock-id-check`
run ends with a pointer to "Known holes" below.

### Symptoms and alerts: names, not ids

Symptoms and alerts installed through REST collide by **name**: the
factory clients (`vcfcf_symptoms`, `vcfcf_alerts` `sync`, and the bundle
sync handlers) and the distribution `install.py` all find an existing
definition by exact name and PUT over its id. The id guard cannot see
this. An unprefixed third-party symptom or alert named exactly like a
stock one overwrites the stock object. Their content-zip and pak forms
carry ids and are checked by id above.

What guards it today:

- Factory content carries the RULE-006 `[VCF Content Factory]` prefix,
  which no stock name carries. The per-type `validate` and `sync` commands
  and the bundle-sync handlers load symptoms and alerts with the prefix
  rule on, so through them an unprefixed name never reaches the server.
- Third-party (`factory_native: false`) bundle content is unprefixed by
  design. `vcfcf_packaging validate`, bundle `sync` and the bundle,
  discrete and release builds print a `STOCK-NAME:` warning for every
  bundle symptom or alert whose exact name is a stock symptom or alert
  name in the baseline (`report_stock_name_collisions`). It is a warning,
  not an error: the baseline keeps one display name per id, so a match is
  a prompt to rename.
- Nothing checks names in the distribution `install.py` at install time,
  and nothing checks names against the target instance's own objects.
  Both stay open under #345.

### Unguarded paths

- `vcfcf_supermetrics` policy re-import (`POST /api/policies/import`): it
  re-imports the instance's own exported policy, which embeds
  `<superMetric uuid>` definitions. Not checked. The scanner already counts
  in-policy super metrics as definitions, so once super metric ids enter
  the baseline, a policy export that embeds a stock super metric would be
  flagged if this path were guarded.
- `vcfcf_managementpacks` `uninstall_pak`: no check that the pak's ids are
  not stock before removing it (#345 item 3, open).
- Tier 1 MPB `build_pak` (and the `release` MPB headline): MPB paks ship
  empty content directories, so there is nothing to check today.
- The distribution `install.py`: see above.

## Escape hatch

```yaml
stock_id_allowlist:
  - type: view
    id: 2788178d-7df4-47d7-81de-016f7a1cd18d
    reason: "Why this content must ship under the stock id."
```

In adapter.yaml (paks), a bundle manifest or a third-party `PROJECT.yaml`.
Exactly `type`, `id` and a non-blank `reason`; anything else is refused.
Absent by default. An allowlisted hit prints a warning naming the reason
on every run; on a build of the manifest's own content, an entry that
matches nothing is a warning too.

**An entry covers only content its own manifest owns.** A bundle manifest
owns the files it lists; a `PROJECT.yaml` owns everything under its
project directory; an adapter.yaml owns its pak's bundled content.

- Bundle build: the bundle's entries cover the bundle's content.
- Discrete and release builds of a single item (`build-discrete`, and
  `release` for a third-party component): the item has no manifest of its
  own, so each definition is covered only by the `PROJECT.yaml` of the
  project directory its file sits in.
- Per-type `validate`: each loaded definition is attributed by file to the
  manifest(s) that own it, and only their entries apply. A file no
  manifest owns cannot be allowlisted. Bundle A's entry never covers
  bundle B's file, even for the same id.
- Content import: bundle `sync` declares the bundle's own entries for the
  imports it makes (`import_allowlist`); any other import (a standalone
  per-type `sync`) has no owning manifest and nothing can be allowlisted.
  To import allowlisted content, sync its bundle.
- A pak built with an allowlist still needs `install --allow-stock-ids`.

The allowlist is for the rare deliberate case; it is reviewable in the
diff that adds it.

## How the baseline is generated, and how an id is shown to be stock

```
python3 -m vcfcf_packaging stock-id-baseline \
  --export <version>=<label>=<export dir or zip> ...   # clean scope-ALL exports
  --inventory <version>=<label>=<type>=<id-name list>   # REST inventories of other instances
  --custom-export <scope-CUSTOM export>                 # negative evidence
  --known-content <label>=<pak or content repo>         # third-party packages, judged by presence
  --exclude-content <label>=<fork tree>                 # content whose ids are never stock
  --factory-tree <dir> --factory-artifacts <dist> --factory-git <repo>
  --exclude-name <marker> --exclude-adapter-kind <prefix>
  --out src/vcfcf_core/stock_ids/stock_ids_baseline.json \
  --candidates-out <scratch path>
```

Lab instances hold factory content, third-party content and pak content
beside the product's. A non-stock id in the baseline fails good builds; a
stock id missing is a hole. The rule (full text in the `generate.py`
docstring) is conservative: an id that cannot be shown to be stock is left
out and listed in the candidates report, never guessed in. A source the
scanner cannot fully read stops the run (nothing is written).

1. **Sources.** Scope-ALL exports from clean instances (no pak under test
   installed, and no content imported from elsewhere), each tagged with
   version and instance; id/name inventories of further instances.
   Policy-embedded definitions are not observations.
2. **Exclusions (any one keeps an id out).** A name marker (factory prefix
   in both forms, `[AI Content]`, plus third-party tags passed on the
   command line); an excluded adapter kind; a factory id (YAML `id:` values
   in the factory tree, its git history, the registered pak repos, and
   every id in built factory artifacts); a scope-CUSTOM export lists it;
   `--exclude-content` defines it. The registered, re-identified
   third-party forks are passed as `--exclude-content`: their ids are never
   stock, so no threshold decides them.
3. **Explained presence.** Each `--known-content` package is a group of
   ids. It counts as installed on an instance when 90 percent of its ids
   (of the types that instance's sources cover) are present. Presence
   explained by an installed package is not evidence. This keeps a pak
   installed on every lab out, while a package that merely copied stock
   ids does not hide them. Every package's presence ratio per instance is
   printed on each run, with a `WARNING` when it is within 10 points of
   the threshold.
4. **Evidence.** Present and unexplained on two or more instances: stock.
   On one instance: stock only for a view or report template whose title
   carries the product's `localizationKey` there, or a dashboard whose
   `adapterName` two-instance stock dashboards carry, AND an independent
   third-party package (not installed there) carries the same id: an export
   of its author's own appliance, so a second independent observation.
   Super metrics, symptoms, alerts and recommendations need two instances.
5. **Display name.** The name seen on the most evidence instances, one
   vote per instance however many of its exports carry the id; the latest
   version wins a tie.

The candidates report names non-stock content found on the source
instances, so it is written to a scratch path, never committed.

**Review step on every regeneration:** diff the baseline and read every
added and dropped id and every changed name, and read the presence lines
and the `excluded ...: keeps out N id(s)` lines the run prints.

## The committed baseline (generated 2026-11-12)

Sources (labels as in the file):

| Label | Version | Inputs |
|---|---|---|
| lab-a | Aria Operations 8.18.7 | scope-ALL export taken before the 2026-11-12 vCommunity fix test (B0), a views-only export the same day, and the built-in view set used for the vCommunity PR recon (8.18.7) |
| lab-b | VCF Operations 9.0.2 | scope-ALL exports before the 2026-11-12 fix test (B0) and its repeat (R0), and the 2026-11-11 views export taken before the 64-view restore |
| lab-c | VCF Operations 9.1.1 | scope-ALL export before the 2026-11-12 fix test (B0), the 2026-11-11 upstream-repro baseline, and the built-in view set used for the PR recon (9.1.1) |
| lab-d | VCF Operations 9.1.1 | REST inventories of alerts, symptoms, reports and super metrics (2026-11-11); its scope-CUSTOM export as negative evidence |

Every source above is clean in the generator's sense: taken with no pak
under test installed and with no content imported from outside the
factory and the third-party packages listed below. The labs do hold those
packages' content (vsanhostmetrics is installed on lab-a, b and c); the
exclusions and the presence rule keep it out. One lab-c export is deliberately **not** a source: the B0 export
taken before the 2026-11-12 e1 fix test, because it was taken after a
migration tool had imported customer content into that lab (4 views, 5
super metrics, 1 dashboard). Dropping it leaves the id set unchanged
(4282); it removes the 9.1.1 tag from one view
(`f1aeaa58-ce9a-4456-878e-1d9582a66711`, stock in 8.18.7 and 9.0.2 on
exports that predate the migration) and moves one symptom's display name.

Known packages (`--known-content`): the factory's reference repos and the
released vCommunity paks 0.2.8, 0.3.0, 0.3.2 and 0.8.1. Excluded content
(`--exclude-content`): the three registered Python forks (vsanhostmetrics,
cluster-perf-risk, vcommunity); together they keep out 0 ids that would
otherwise be stock. Factory ids: the factory tree and its YAML history,
the registered pak repos (compliance, synology, unifi, vsanperf, template,
vcommunity-java; working trees only) and the built paks and zips in
`dist/`.

| Type | Ids | 8.18.7 | 9.0.2 | 9.1.1 | Candidates, not included |
|---|---|---|---|---|---|
| view | 771 | 704 | 768 | 741 | 173 |
| dashboard | 148 | 135 | 148 | 141 | 60 |
| report | 62 | 60 | 62 | 62 | 37 |
| super metric | 0 | 0 | 0 | 0 | 83 |
| symptom | 2161 | 1373 | 1762 | 2031 | 1189 |
| alert | 1140 | 533 | 862 | 1131 | 1182 |
| recommendation | 0 | 0 | 0 | 0 | 0 |

4282 ids. The 9.0.2 view count includes the 64 stock views lab-b lost on
2026-10-15 and got back by the 2026-11-11 re-import from a 9.1.1 export:
lab-b's audit log shows them in its first-boot content load, so they are
stock on 9.0.2.

Cross-checks: all 120 ids in the vCommunity fork's
`tests/test_view_ids.py` (branch `fix/builtin-view-ids-e1`) are in the
baseline as views, the three VCF Management Services views only for 9.1.1.
`stock-id-check` reports 120 view hits in the released e1 vCommunity 0.8.1
pak and 117 in the unpacked upstream 0.3.1 pak, none of their other
content, and none in the fixed builds with re-minted ids.

### The exact command for the committed file

Run from the root of the factory checkout the file is committed in. Each
variable names one input; set them to where those inputs are on your
machine (the labels in the table above are what the file records, the
paths never are). `FACTORY` is a clean factory checkout: everything under
its `content/`, `third_party/` and `bundles/` becomes factory ids, so a
tree holding scratch or migrated content there gives a different file.
`PAKS` is a bootstrapped checkout's `content/sdk-adapters/` (the
registered pak repos and forks), `REFS` its `reference/references/` and
`DIST` its `dist/`.

| Variable | Input |
|---|---|
| `LAB_A_B0`, `LAB_A_VIEWS`, `LAB_A_RECON_VIEWS` | lab-a: the B0 export dir, the views-only export dir, the recon view set `views.zip` |
| `LAB_B_B0`, `LAB_B_R0`, `LAB_B_VIEWS_BEFORE_RESTORE` | lab-b: the B0 and R0 export dirs, the views export zip taken before the restore |
| `LAB_C_B0`, `LAB_C_REPRO_BASELINE`, `LAB_C_RECON_VIEWS` | lab-c: the fix-test B0 export dir, the upstream-repro baseline export dir, the recon view set `views.zip` |
| `LAB_D` | lab-d: the dir holding `pre_alerts.txt`, `pre_symptoms.txt`, `pre_reports.txt`, `pre_supermetrics.txt` and the scope-CUSTOM export |
| `PAK_VCOMMUNITY_081`, `PAK_VCOMMUNITY_028` | the released e1 vCommunity 0.8.1 pak and the upstream 0.2.8 pak |
| `VCOMMUNITY_FIX_BUILDS` | the dir holding the four re-identified vCommunity 0.3.x `.pak` builds |

<!-- stock-id-baseline-command: begin -->
```bash
known=()
for d in "$REFS"/*/; do
  known+=(--known-content "ref-$(basename "$d")=$d")
done
for d in vsanhostmetrics cluster-perf-risk vcommunity; do
  known+=(--exclude-content "fork-$d=$PAKS/$d")
done
known+=(--known-content "pak-vcommunity-0.8.1=$PAK_VCOMMUNITY_081")
known+=(--known-content "pak-vcommunity-0.2.8=$PAK_VCOMMUNITY_028")
for p in "$VCOMMUNITY_FIX_BUILDS"/*.pak; do
  known+=(--known-content "pak-$(basename "$p" .pak)=$p")
done
PYTHONPATH=src python3 -m vcfcf_packaging stock-id-baseline \
  --export "8.18.7=lab-a=$LAB_A_B0" \
  --export "8.18.7=lab-a=$LAB_A_VIEWS" \
  --export "8.18.7=lab-a=$LAB_A_RECON_VIEWS" \
  --export "9.0.2=lab-b=$LAB_B_B0" \
  --export "9.0.2=lab-b=$LAB_B_R0" \
  --export "9.0.2=lab-b=$LAB_B_VIEWS_BEFORE_RESTORE" \
  --export "9.1.1=lab-c=$LAB_C_B0" \
  --export "9.1.1=lab-c=$LAB_C_REPRO_BASELINE" \
  --export "9.1.1=lab-c=$LAB_C_RECON_VIEWS" \
  --inventory "9.1.1=lab-d=alert=$LAB_D/pre_alerts.txt" \
  --inventory "9.1.1=lab-d=symptom=$LAB_D/pre_symptoms.txt" \
  --inventory "9.1.1=lab-d=report=$LAB_D/pre_reports.txt" \
  --inventory "9.1.1=lab-d=supermetric=$LAB_D/pre_supermetrics.txt" \
  --custom-export "$LAB_D" \
  "${known[@]}" \
  --factory-tree "$FACTORY/content" --factory-tree "$FACTORY/third_party" \
  --factory-tree "$FACTORY/bundles" \
  --factory-tree "$PAKS/compliance" --factory-tree "$PAKS/synology" --factory-tree "$PAKS/unifi" \
  --factory-tree "$PAKS/vsanperf" --factory-tree "$PAKS/template" \
  --factory-tree "$PAKS/vcommunity-java" \
  --factory-artifacts "$DIST" \
  --factory-git "$FACTORY" \
  --exclude-name "[IDPS]" --exclude-name "IDPS Planner" --exclude-name "[Custom]" \
  --exclude-name "[VHM]" --exclude-name "vCommunity" \
  --exclude-adapter-kind vcfcf_ --exclude-adapter-kind unifi_controller \
  --exclude-adapter-kind synology_diskstation --exclude-adapter-kind example_adapter \
  --exclude-adapter-kind VsanHostMetrics --exclude-adapter-kind ClusterPerfRisk \
  --exclude-adapter-kind vCommunity \
  --generated 2026-11-12 \
  --out src/vcfcf_core/stock_ids/stock_ids_baseline.json \
  --candidates-out "${CANDIDATES_OUT:?set a scratch path outside the repo}"
```
<!-- stock-id-baseline-command: end -->

The generator is deterministic: with the same inputs it writes the same
file byte for byte (the committed file was reproduced that way from the
block above). Some inputs move with the factory: the factory tree, the
YAML history of every ref (`git log --all`), `dist/` and the pak repos'
working trees. A change there can change `rule.factory_ids_considered`
and, rarely, keep a newly minted factory id out; the review step above
catches either.

### Known holes (why a stock id may be missing, or a pass may mislead)

- **Super metrics and recommendations are not checked.** The baseline
  holds no ids of either type (no source export carried
  `RECOMMENDATION_DEFINITIONS`; the labs show no super metric the product
  ships), so a definition of those types always passes. The pass line says
  so.
- **Single-instance content of types with no product signal.** 8.18.7-only
  and 9.0.2-only symptoms and alerts (one lab each) and every 8.18.7-only
  or 9.0.2-only view without an independent copy (for example the 8.18.7
  vRealize Automation pricing views) are candidates. An export of a second
  instance of that version closes the gap.
- **Content the export leaves out.** Scope-ALL exports omit adapter-kind
  `ALL` symptoms and alerts and every badge or capacity-key symptom
  (`2026-11-11-alert-symptom-export-completeness.md`); only lab-d's REST
  inventory sees those, so they are single-instance.
- **The presence threshold fails in both directions.** (a) A package
  installed on every lab that drifts under 90 percent (one more view in
  it) stops explaining its ids, which then become evidence and enter the
  baseline as "stock" on the next regeneration: its own builds are then
  refused and `stock-id-check` calls its content VCF Operations stock.
  (b) A package that copied stock ids and is installed on every lab
  explains those stock ids away, a silent hole on exactly the ids that
  matter. The registered forks are exclusions, not known packages, for
  this reason (vsanhostmetrics sits at 91 percent on lab-a, b and c). The
  run prints every ratio and warns within 10 points of the threshold; the
  current near ones are the released vCommunity paks on lab-d (89
  percent, not installed). For excluded content the run prints how many
  ids it keeps out that the presence rule would have called stock: 0
  today; a non-zero count means a fork checkout carries copied stock ids
  or has drifted, and the review step must read those ids.
- **An unknown third-party pak installed on two labs is accepted as
  stock.** Its ids are corroborated on two instances. Only a name marker,
  an excluded adapter kind, or listing it as `--known-content` or
  `--exclude-content` keeps it out; the review step is the backstop.
- **Versions not measured.** 9.0.2.0200 and 9.1.1.0100 are not separate
  sources; 9.2 is absent.
- **Names, not ids.** See "Symptoms and alerts: names, not ids".

### Adding a version

Take a scope-ALL export (`POST /api/content/operations/export`,
`{"scope":"ALL"}`, all content types including
`RECOMMENDATION_DEFINITIONS`) on a clean instance of the new version, add
it as `--export <version>=<label>=<path>` to the command above (and a
variable for it to the table), run it, read the candidates report, do the
review step, and commit the new baseline with the updated command. The
guard, the kit and pak CI pick it up from the file; no code change. A
regeneration changes only `stock_ids_baseline.json`: no distribution zip
rebuild and no `CURRENT_TEMPLATE_VERSION` bump is needed, because no zip
or template carries the baseline. The same holds for this guard's own
introduction: the bundle builders now refuse stock ids before writing, but
the bytes of every zip they write are unchanged and nothing distributed
carries a stock id, so the distribution zips are not stale.
