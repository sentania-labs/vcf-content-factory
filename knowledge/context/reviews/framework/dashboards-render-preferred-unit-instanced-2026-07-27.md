# Framework review — `_xml_instanced_group_item()` emits `preferredUnitId`

- **Date:** 2026-07-27
- **Reviewer:** `framework-reviewer` (RULE-013 blanket pre-PR gate)
- **Area:** `src/vcfops_dashboards/render.py`
- **Diff under review:** `src/vcfops_dashboards/render.py` (+10),
  `tests/test_view_instanced_group_columns.py` (+112). Working tree also
  carries new content YAML + knowledge files from the same effort; scoped
  out of the verdict except as a consumer check.
- **Verdict:** **APPROVE** (0 BLOCKING / 3 WARNING / 2 NIT)

## Change

`_xml_instanced_group_item()` now appends
`<Property name="preferredUnitId" value="{col.unit}"/>` immediately after
`attributeKey` on instanced-group **member** columns when `col.unit` is
non-empty. Driver branch returns before the new code. No loader/schema
change (`ViewColumn.unit` predates this).

## Gates re-run (independently, not taken from the tooling report)

| Gate | Result |
|---|---|
| validate chain ×7 (`supermetrics`…`managementpacks`) | all exit 0 |
| full pytest | **611 passed, 4 skipped, 162 deselected** (matches claim) |
| `tests/test_view_instanced_group_columns.py` | **18 passed** (matches claim) |
| render regression, 18 tracked views, `HEAD` worktree vs working tree | **byte-identical** |
| new consumer renders the new path | yes (see below) |
| pak-compare | n/a — no builder/template change |

Render regression harness: rendered every tracked `content/views/*.yaml`
through `load_view` + `render_views_xml` under a `git worktree` at `HEAD`
and under the working tree, JSON-dumped and diffed. Only delta is the new
untracked `vm_snapshot_inventory.yaml` (absent at HEAD). Zero drift on
existing content — the change is provably inert unless `unit:` is set on
an instanced member, which no pre-existing view does.

## Dimension walk

**1. Global-default / pak-specific leak (anchor `00d3382`) — CLEAR.**
The emission is unconditioned on `bundle_context` / `sm_scope` /
pak-vs-standalone; `_xml_instanced_group_item(view, col)` takes neither.
All output paths share `render_views_xml`: `vcfops_dashboards/packager.py:98`
(standalone content-import zip), `vcfops_packaging/builder.py:675` and
`discrete_builder.py:668` (pak), `vcfops_managementpacks/sdk_builder.py`
(SDK pak). Identical behavior on all four, and gated behind `if col.unit`.
No pak-local default leaks global.

**2. Key/label derivation collision (anchor `6c59f6b`) — N/A.**
`preferredUnitId` participates in no key or localization-key derivation;
`attributeKey`, `displayName`, and localization keys are untouched.
Verified byte-identically by the render regression.

**3. Wire-format conformance — CONFORMS, and better-evidenced than the
code claims.** Vendor ground truth, `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/content/reports/View - Set 4.xml:22141-22150`
("VM Snapshots List"):

```
attributeKey = "diskspace:262|snapshot:snapshot-1|used"
id           = "extModel95616-4"
preferredUnitId = "gb"
isStringAttribute = "false"
```

The factory now emits the identical property sequence for the identical
attribute shape and the identical unit value (`id` is an export-time
internal reference the factory omits by design, per the prior instanced-group
review). A full sweep of `View - Set 4.xml` shows **every** unit-bearing
instanced member column places `preferredUnitId` after `attributeKey`
(and after `id` where present) and before `isStringAttribute` — 40+
instances, zero counterexamples. Position is vendor-exact, not analogy.

**4. Loader/validator correctness — no change.** `unit` passthrough and
XML escaping use the same `_xml_property` helper as the generic path
(`render.py:598-599`); no new validation surface, no UUID/prefix impact
(RULE-006/RULE-007 unaffected).

**5. Render regression vs known-good — clean.** See table above.

**6. Builder / pak structure — untouched.** No `template.json`,
`describe.xml`, or C2 shape change.

**7. Corpus regression — clean.** Validate chain exit 0 across all seven
CLIs with the new content present; suite green.

**8. Silent capability change — the opposite, and in the good direction.**
Previously `unit:` on an instanced member was *silently ignored* (flagged
as a known gap in `view_column_wire_format.md` and carried forward as a NIT
in `knowledge/context/reviews/framework/view-instanced-group-and-alerts-instanced-fix.md`).
This closes that silent downgrade. Round-trip is symmetric:
`src/vcfops_dashboards/reverse.py:344` already parses `preferredUnitId`
back into `unit`, so an XML→YAML→XML cycle no longer loses the unit.

**9. Stale-zip discipline — see WARNING 3.**

**10. Test coverage — adequate.** Three cases: positive emission with
full expected property sequence, no-unit regression guard, and an explicit
driver-non-leak guard. The negative guards are the right shape for this
change class.

**Consumer check.** `content/views/vm_snapshot_inventory.yaml` (`unit: "gb"`,
lines 78 and 124) does exercise the new path; rendered member item:

```
<Property name="attributeKey" value="diskspace:356893|snapshot:snapshot-16|used"/>
<Property name="preferredUnitId" value="gb"/>
<Property name="isStringAttribute" value="false"/>
...
```

Property-for-property equal to the vendor item above (minus vendor `id` and
color bounds).

## Findings

### WARNING

1. **[`src/vcfops_dashboards/render.py:458-465`] — RULE-001 source-of-truth /
   `knowledge/rules/cited-artifacts-reproducible.md`.** The new comment states
   *"No vendor instanced-group example was surveyed with a unit set (see
   view_column_wire_format.md 'Instanced-group columns' — flagged as a known
   gap there) … the generic path's ordering is the closest evidenced analog."*
   This is **factually wrong**: `View - Set 4.xml:22141-22150` carries the exact
   consuming case (`diskspace:…|snapshot:…|used`, `preferredUnitId="gb"`), and
   both `view_column_wire_format.md:852-862` and the prior framework review
   explicitly record that vendor members carry `preferredUnitId` right after
   `attributeKey`. The doc it cites says the opposite of what it claims the doc
   says. Understating evidence is not harmless — a future maintainer reading
   "unproven analogy" is invited to rip this out under the fail-closed posture.
   → **Fix:** replace the comment with the real citation (file, line range,
   attributeKey, `preferredUnitId="gb"`), and note that vendor items also carry
   `id` which the factory deliberately omits.

2. **[`knowledge/context/wire-formats/view_column_wire_format.md:852-862`] —
   doc drift.** That section still reads *"`_xml_instanced_group_item()` does
   not emit `preferredUnitId` at all … Flag for a future tooling pass"*. As of
   this diff that is false. The wire-format docs are `tooling`-owned and are the
   authority other agents cite; leaving a resolved gap documented as open is
   exactly the INDEX-ROT class the curator hunts.
   → **Fix:** update the section to record the capability as implemented, with
   the `View - Set 4.xml` citation and the emission position.

3. **[process] — CLAUDE.md "After tooling changes" / stale-zip discipline.**
   `src/vcfops_dashboards/render.py` was modified, so every `dist/` zip is
   formally stale and the change must flag a `content-packager` rebuild of all
   `bundles/` manifests. The tooling result block does not. Real risk is low
   here (render regression proves all 18 existing views are byte-identical, so
   no shipped bundle's content changes), but the rule is categorical and the new
   view/dashboard will need packaging regardless.
   → **Fix:** orchestrator schedules `content-packager` after merge; state the
   byte-identical evidence so the rebuild is recorded as a no-op for existing
   bundles.

### NIT

4. **[`tests/test_view_instanced_group_columns.py`]** No case covers `unit:` on
   an instanced member with `is_property: true` (the branch that omits
   `rollUpType`). Ordering is independent of that branch so behavior is not in
   doubt, but it is the one untested interaction of the new line.

5. **[`src/vcfops_managementpacks/buildkit.py:76`]** `BUILDKIT_VERSION` stays
   `1.0.9` although `render.py` is vendored into the published sdk-buildkit
   tarball as `dashboard_render.py`, so SDK-pak CI will build with a renderer
   whose behavior differs from an identically-versioned kit. Pre-existing
   pattern (none of `9509915`, `0efc80d`, `41aef9f` bumped it either) — systemic,
   out of scope for this diff, worth a dedicated tooling pass.

## If shipped as-is

Correct behavior ships: instanced snapshot-space columns render in GB
exactly as the vendor's own "VM Snapshots List" does, and no existing
rendered view changes by a byte. The residual cost is documentation debt —
one code comment and one wire-format section that both assert the feature
is unimplemented/unevidenced, which will mislead the next agent that reads
them.
