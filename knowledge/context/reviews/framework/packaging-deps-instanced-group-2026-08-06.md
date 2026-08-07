# Framework review: `src/vcfops_packaging/deps.py` instanced_group member-column auditing

- Date: 2026-08-06
- Reviewer: `framework-reviewer` (read-only, pre-PR gate, RULE-013 sibling)
- Branch: `feat/vm-snapshot-inventory` (working tree, uncommitted)
- Change author: `tooling`, in response to external Codex P1 on PR #70
- Predecessor review: `knowledge/context/reviews/framework/packaging-discrete-builtin-metric-enables-2026-07-27.md`

## Verdict

**CHANGES REQUESTED** — 1 BLOCKING, 3 WARNING, 1 NIT.

The normalization logic itself is correct and I verified it against the full
vendor corpus. The blocker is not the algorithm: it is that the diff lands
without the CLI wiring that keeps a *shipped* release building under a
documented flag, so a previously-passing build gate on committed content now
hard-fails.

## Scope of diff reviewed

```
 src/vcfops_packaging/deps.py                       | 63 ++++++++++++++++----
 tests/test_discrete_builder_builtin_metric_enables.py | 13 +++--
 tests/test_deps_instanced_group_columns.py         | new, 9 tests
```

(The working tree also carries unrelated `content/` and `knowledge/designs/`
edits for fleet-capacity-rightsizing; out of this reviewer's surface, not
reviewed.)

## Checks re-run independently

| Check | Result |
|---|---|
| `vcfops_{supermetrics,dashboards,customgroups,symptoms,alerts,reports,managementpacks} validate` | all PASS (managementpacks: 6 Tier 2 SDK projects valid, exit 0) |
| Default suite (`pytest -q`, `-m "not slow"`) | **642 passed, 4 skipped**, 177 deselected |
| deps/audit/packaging/release/builder/view tests incl. slow-marked (`-m ""`) | **207 passed** |
| Remaining slow files (`test_cli_phase4`, `test_publish_*`, `test_third_party_*`, `test_validate_content_hook`) | still running at report time; **none imports `vcfops_packaging.deps` or `.audit`** (verified by grep), so off the change's import path |
| `build-discrete --no-live-describe` on all 6 released headline dashboards | all OK, no regression |
| `build-discrete --no-live-describe --strict-deps` on the same 6 | 5 OK, **`vm_snapshot_inventory` FAIL (new)** |
| Shipped artifact drift (`dist/dashboards/vm-snapshot-inventory-dashboard.zip`) | `content/builtin_metric_enables.json` byte-identical to what the release path still produces; **no stale-zip rebuild required** |
| Normalizer vs. 119 distinct vendor instanced `attributeKey` values in `reference/references/**` | 119/119 normalize correctly |

## Dimension (a): normalization correctness — PROVEN CORRECT

I extracted every distinct colon-bearing `attributeKey` from every
`reference/references/**/*.xml` file containing `isInstancedGroup` (RULE-016
read-only vendor ground truth, the same corpus
`knowledge/context/wire-formats/view_column_wire_format.md` §"Instanced-group
columns" is derived from) and ran `_normalize_instanced_group_key()` over all
119. Every one produces a correct flat describe key, including the shapes the
brief asked about and several harder ones the brief did not:

| Vendor key (ground truth) | Normalized |
|---|---|
| `vCommunity|Licensing:Evaluation Mode|Edition Key` | `vCommunity|Licensing|Edition Key` |
| `vCommunity|Configuration|Packages:atlantic|Package Name` | `vCommunity|Configuration|Packages|Package Name` |
| `vCommunity|Guest OS|Services:DHCP Client|Service Name` | `vCommunity|Guest OS|Services|Service Name` |
| `diskspace:262|snapshot:snapshot-1|used` | `diskspace|snapshot|used` |
| `virtualDisk:scsi0:0|configuredGB` (instance contains `:`) | `virtualDisk|configuredGB` |
| `disk:C:|Percent.Free.Space` (instance ends in `:`) | `disk|Percent.Free.Space` |
| `net:isatap.{4B39…GUID}|Bytes.Sent.persec` | `net|Bytes.Sent.persec` |
| `Hardware|Cooler|Fans:Fan 1A|Fan Health` | `Hardware|Cooler|Fans|Fan Health` |

Multi-segment prefixes round-trip correctly: the split-on-`|`-then-take-up-to-
first-`:` rule is segment-local, so a prefix's earlier segments (which carry no
`:`) pass through untouched and only the boundary segment sheds its instance
token. The nested-instance case (`sample_instance` itself containing `|` and
`:`, as in vm-snapshot's `356893|snapshot:snapshot-16`) works because *each*
pipe-segment of a real instanced key carries its own `:<instance>` token.

I also confirmed the derived keys resolve: all 5 vm-snapshot member keys
(`diskspace|snapshot|{name,numberOfDays,used,creator,description}`) resolve
against `knowledge/context/adapter_describe_cache/VMWARE/VirtualMachine.json`,
with `creator`/`description` correctly reported `default_monitored=False` —
which is the whole point of the fix. No VMWARE cache key anywhere contains a
`:`, so the normalizer cannot corrupt a legitimate key in this corpus.

`vm_snapshot_inventory.yaml` is the only view in `content/views/` using
`instanced_group`, so the behavior delta is bounded to it, and I swept all of
its member columns individually.

## BLOCKING

### B1 — `build-discrete --strict-deps` now hard-fails on a shipped release whose enables *are* declared

`src/vcfops_packaging/deps.py:234-243` (new emission) + `src/vcfops_packaging/cli.py:436-444`

Reproduced:

```
$ python3 -m vcfops_packaging build-discrete --no-live-describe --strict-deps \
    dashboard "[VCF Content Factory] VM Snapshot Inventory"
AUDIT FAILED  strict-deps mode: the following defaultMonitored=false metrics are
referenced but not declared in builtin_metric_enables:
  VMWARE/VirtualMachine  diskspace|snapshot|creator   (from view '…VM Snapshot Inventory')
  VMWARE/VirtualMachine  diskspace|snapshot|description
Add these entries to the 'builtin_metric_enables' section of the bundle manifest, …
exit 1
```

Proven to be **introduced by this diff**, by re-running the same strict audit
in-process against an emulated pre-change `_refs_from_view` (skip all
instanced_group columns):

```
PRE-CHANGE   strict audit: PASS
POST-CHANGE  strict audit: FAIL
```

Blast radius measured across all 6 released headline dashboards under
`--strict-deps`: 5 pass, `vm_snapshot_inventory` is the only regression.

**Why this is a false positive, not correct strictness.** The remedy the error
prints is already done: `bundles/releases/vm-snapshot-inventory-dashboard.yaml:4-12`
declares both keys with reasons. `build_discrete()` already accepts a
`builtin_metric_enables` parameter for exactly this
(`src/vcfops_packaging/discrete_builder.py:373,391-392,441`), and
`release_builder._build_component_headline` already threads it
(`src/vcfops_packaging/release_builder.py:219`, fed from
`release.builtin_metric_enables` at `:468,:476`). Only `cmd_build_discrete`
(`cli.py:436-444`) omits it — it never loads the release manifest at all. So
`--strict-deps` on `build-discrete` is structurally unsatisfiable for any
released item with a `default_monitored=false` reference: the operator is told
to declare something they cannot declare anywhere the command reads.

Authority: dimension 7 (corpus regression — a framework change that makes
previously-good committed content fail a build gate is BLOCKING); and the
predecessor review on this exact surface, which explicitly warned the fix must
not "leave the same false positives latent for `--strict-deps` users"
(`packaging-discrete-builtin-metric-enables-2026-07-27.md:129`).

**Smallest correct fix:** in `cmd_build_discrete`, use
`vcfops_packaging.releases.load_all_releases()` to find the release whose
headline artifact `source` resolves to the requested item, and pass
`release.builtin_metric_enables` into `build_discrete(...)` — mirroring what
`release_builder.py:219` already does. Add one test asserting
`build-discrete --strict-deps dashboard "[VCF Content Factory] VM Snapshot
Inventory"` succeeds. (If `tooling` argues manifest-threading is out of scope
for this diff, the alternative minimum is a guard that keeps the pre-change
strict outcome for this item, but threading is the smaller and more honest fix
since the plumbing already exists.)

## WARNING

### W1 — Two divergent normalizers for the same wire-format key shape

`deps.py:99` (`_INSTANCED_KEY_RE` / `_normalize_metric_key`) vs `deps.py:102-122`
(`_normalize_instanced_group_key`)

The new function is correct for all 119 vendor shapes. The old one, still used
for every *non*-instanced_group path — direct `attribute:` columns
(`deps.py:250`), SM formula `metric=` values (`deps.py:187`), all widget keys
(`deps.py:291-339`), and the staged-bundle XML path (`audit.py:385`) — is not.
Verified side-by-side:

| Input (real vendor key) | `_normalize_instanced_group_key` | `_normalize_metric_key` (old) |
|---|---|---|
| `diskspace:262|snapshot:snapshot-1|used` | `diskspace|snapshot|used` | `diskspace|snapshot:snapshot-1|used` ✗ |
| `vCommunity|Licensing:Evaluation Mode|Edition Key` | `vCommunity|Licensing|Edition Key` | unchanged ✗ |

Reproduced end-to-end: a plain view column authored as
`attribute: "diskspace:262|snapshot:snapshot-1|used"` loads and validates fine,
then derives `diskspace|snapshot:snapshot-1|used`, which resolves to `None` →
`unknown` → hard `AuditError` in **every** mode including `lax`
(`audit.py:141-155` raises before the mode switch). So the same wire key
audits correctly if authored via `instanced_group:` and hard-fails the build if
authored via `attribute:`. That authoring-form-dependent behavior is exactly
the "unproven is a finding" seam, and the predecessor review's own suggested
fix was to "extend `_INSTANCED_KEY_RE` to strip `:<instance>` from any segment"
(`packaging-discrete-builtin-metric-enables-2026-07-27.md:124-126`) — only half
of which was done.

→ Make `_normalize_metric_key()` delegate to the segment-local rule (it is a
strict superset: it produces identical output for every non-instanced key and
for the simple `group:instance|stat` form, as I verified on the 119-key corpus),
or document in the module docstring why two rules coexist.

### W2 — The `analyze` staged-bundle path extracts **zero** view references

`audit.py:380-381` reads `col.get("attributeKey")` off `<Column>` elements. The
factory's own emitted `views_content.xml` has no `<Column>` element and no
`attributeKey` XML attribute; the real shape (confirmed by dumping the zip this
change produces) is:

```xml
<Item><Value>
  <Property name="attributeKey" value="diskspace:356893|snapshot:snapshot-16|creator"/>
```

Measured: `python3 -m vcfops_packaging analyze` on the freshly built
vm-snapshot bundle reports `references: 2 total` (both from `dashboard.json`)
where the build-time audit on the same content sees 10. Every view column
silently dodges the analyze gate — the identical defect class to the Codex P1
this change fixes, on a sibling code path in the module under change.

Pre-existing, not introduced here — but it means the diff closes the loader
path and leaves the staged path reporting a clean bill of health it did not
earn. → Rewrite `_refs_from_views_xml` against the documented wire shape in
`knowledge/context/wire-formats/view_column_wire_format.md` (walk
`Property[@name='attributeKey']/@value` under `attributeInfos`), and normalize
with the same rule as W1. Fine as a follow-up issue, but it should be filed,
not lost.

### W3 — New test docstring asserts a mechanism that does not exist

`tests/test_discrete_builder_builtin_metric_enables.py:381-388`

The added docstring says the Creator/Description keys "are corroborated — not
conflicted — by the release manifest's manual `builtin_metric_enables`
declarations, so the audit still passes." That is not why it passes. The test
calls `build_discrete(...)` with default `audit_mode="auto"` and no
`builtin_metric_enables` argument (`:390-396`); the release manifest is never
read on that path (see B1). It passes because auto mode auto-*adds* the two
entries. A future reader will trust this docstring and conclude the strict path
is covered when it is not — and the strict path is precisely what B1 shows is
broken. RULE-002 (no fabrication) applied to a test's own claim about what it
proves. → Correct the docstring to say auto-mode auto-add, and add the strict
coverage the docstring implies.

## NIT

### N1 — View subject-filter metric keys are still never audited

`content/views/vm_snapshot_inventory.yaml:36` filters on
`diskspace:90|snapshot:snapshot-1|numberOfDays`, but `_refs_from_view()` walks
only `view.columns`. A view whose *only* reference to a
`default_monitored=false` key is a subject filter still dodges the gate
entirely — same blind-spot class as the P1, benign in the current corpus only
because that key is also a column. Pre-existing; worth an issue, not a blocker
on this diff.

## What is provably fine

- No global-default / pak-specific leak (anchor `00d3382`): the change adds no
  default, flag, or coordinate convention; it is confined to the
  `instanced_group is not None` branch of one extractor and is inert for every
  view without instanced columns (verified by sweeping all of `content/views/`).
- No key/label collision (anchor `6c59f6b`): the derived key is deduplicated on
  `(adapter_kind, resource_kind, metric_key)` in `extract_metric_references`;
  distinct suffixes produce distinct keys — all 5 vm-snapshot member columns
  produce 5 distinct refs, none colliding with the flat `diskspace|snapshot`
  summary column.
- No wire-format drift: `deps.py` emits no wire artifact. The one artifact
  whose content could shift, `content/builtin_metric_enables.json`, is
  byte-identical in the committed `dist/` zip to what the release path still
  produces, because the release path passes the manifest enables and defaults
  `skip_audit=True`.
- No stale-zip trigger: `deps.py` is not in the CLAUDE.md "After tooling
  changes" set (`templates/`, `builder.py`, `discrete_builder.py`,
  `release_builder.py`, `render.py`), and I confirmed the shipped artifact is
  unchanged. No `content-packager` rebuild needed.
- Test coverage of the changed behavior is present and real (9 new tests,
  including two that read committed content and the real describe cache).
  Gap: no test for the derived-key-not-in-cache failure path, and none for the
  strict path B1 breaks.
- DEF-016 `builtin_metric_enables` flow intact: all 6 released headline
  dashboards build clean in default (auto) mode; auto mode correctly auto-adds
  the two newly-detected keys with accurate provenance in `reason`.
- `pak-compare`: n/a, no pak surface touched.

## If shipped as-is

The default `build-discrete` and the `release`/`publish` paths are fine and the
shipped zip does not change — but any operator (or future CI step) running the
documented `--strict-deps` flag on the VM Snapshot Inventory dashboard gets a
hard build failure telling them to add declarations that are already sitting in
`bundles/releases/vm-snapshot-inventory-dashboard.yaml`, with no way to satisfy
the flag short of `--skip-audit`.
