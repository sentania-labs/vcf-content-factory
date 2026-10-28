# Framework review: docs-gen recursive traversal (branch `docs-gen-recursive-traversal`)

- **Date:** 2026-10-28
- **Branch:** `origin/docs-gen-recursive-traversal`, commits a9b4d46, af2d93b, 6ca8d2b on top of 55b781b
- **Area:** `src/vcfcf_managementpacks/docs_gen.py` (generated SDK pak docset: `inventory-tree.md`, `.svg`, `.excalidraw`)
- **Also touched:** `tests/managementpacks/test_docs_gen_recursive_traversal.py` (new, 31 tests), `knowledge/context/tier2_architecture.md`
- **Origin:** UniFi build 18 review W4 (`knowledge/context/reviews/unifi-build-18.md`)
- **Verdict:** APPROVE (0 BLOCKING / 2 WARNING / 7 NIT)

## Checks re-run (scratch worktree at 6ca8d2b; main tree untouched)

| Check | Result |
|---|---|
| Validate chain (7 packages) | pass, all rc=0; managementpacks: `OK: 4 Tier 2 SDK adapter project(s) valid` |
| Full test suite | 3141 passed, 9 skipped, 131 deselected, 0 failed |
| Regenerate docsets, base 55b781b vs branch, from `content/sdk-adapters/` clones (copied to scratch) | compliance and template: `inventory-tree.md`, `.svg`, `.excalidraw`, `README.md` **byte-identical**. synology and unifi: the three inventory-tree files change, `README.md` identical |
| Determinism | synology and unifi regenerated under `PYTHONHASHSEED` 1, 2, 999 and the default: one sha256 per file |
| Malformed-describe probe (13 shapes: rootless cycles, cycle reachable from root, inverse cycle, self-only, empty kind, `/skip`, wildcard, triple modifiers, first-level `~child`, foreign key equal to own key, `/Recursive`) | branch: all terminate. Base 55b781b **hangs** on a cycle reachable from the root (killed by alarm), so the guard fixes a real infinite loop |
| SVG inspection | rasterized base and branch Synology/UniFi SVGs with headless Chrome and read them |
| Excalidraw structure | no dangling bindings, no duplicate ids; unifi 15 arrows (5 multi-point), synology 9 (1 multi-point) |
| pak-compare | n/a (docs only; built pak bytes do not include the regenerated tree) |

## Grammar interpretation

Authorities: spec 07 (`knowledge/context/cleanroom-spec/spec/07-relationships-cross-mp.md` lines 200-209),
`knowledge/context/cleanroom-spec/analysis/per-adapter/vmwarevi_adapter3.md:129` onward, factory PR #290
(SDK `TraversalSpecUtil.validateResKindPath`: `/recursive` and `/preferred` parsed independently;
`/preferred` rejected on first/last level, with `/skip`, or before a wildcard level; its runtime meaning is unconfirmed).

- `::~child` = inverse: the segment's kind is the parent of the previous level. Matches spec 07
  "inverse (child→parent)", and matches the Synology pak's own describe.xml comment (lines 418-426:
  "the VMWARE Datastore is the PARENT of its backing iSCSI LUN ... via the INVERSE modifier") and its
  runtime `parentForeign(ds, lun)`. Base drew Datastore under the LUN, which was wrong. Correct.
- `/recursive` = the level repeats, so a self-edge. Matches spec 07 and the vSphere `HostFolder::child/recursive`
  precedent, and the UniFi describe comment (Switch chains, AP behind AP, live devel 2026-10-28). Correct.
- `/preferred` stripped, no topology. Consistent with PR #290. The code comment overstates its meaning (N2).
- Modifiers in either order, and repeated, strip correctly. Unknown suffixes are left alone (pinned by test).
  `/skip` and wildcard levels are not recognized (N1).

## Output changes (verified by regeneration)

**UniFi.** Tree gains Switch > Switch and AP > AP self lines, plus *(see above)* for Gateway > AP,
Site > Switch, Site > AP. Parent(s): Switch gains Switch; AP gains AP. Every parent > child pair in
the nine ResourcePaths now appears. W4 is closed for docs. SVG: self-loops on Switch and AP (top-right,
clear of the inbound arrow); Gateway > Switch, Gateway > AP, Switch > AP routed in lanes under the row.
Gateway > AP and Switch > AP share an entry point on the AP's bottom edge (readable, two lanes visibly join).

**Synology.** Datastore leaves the LUN subtree and becomes a foreign top-level root with *(see above)*
for iSCSI LUN and NFS Export; Parent(s) for both gain Datastore; Storage Pool > Disk *(see above)* added.
SVG: SSD Cache > Disk is now an upward lane into Disk's bottom. Base drew it as a midpoint path that read
as Disk > NFS Export / SSD Cache, which was wrong, so this is a correctness improvement. Datastore is
not drawn in the diagram (foreign), as before.

**compliance, template:** byte-identical (compliance has no TraversalSpecKind; template paths carry no modifiers).

## Dimension walk

1. Global/pak-specific leak (00d3382): none. Paths without modifiers parse to the same pairs
   (test plus byte-identical compliance/template). The only consumers are `docs-gen` and `build-sdk`'s docs step.
2. Key collisions (6c59f6b): node identity is the bare resource-kind key with the adapter kind dropped (W2).
   Pre-existing in base, but the branch adds own/foreign classification on that bare key.
3. Wire format: docs-only output; no describe.xml/pak emission touched.
4. Loader correctness: the parser is the docs model only; validate chain unaffected.
5. Render regression: only the intended Synology/UniFi deltas; see above.
6. Builder/pak: built pak bytes unchanged.
7. Corpus: validate and suite green.
8. Silent downgrade: none; the base output dropped edges, the branch adds them. A rootless cycle still renders an empty tree silently (N4, pre-existing).
9. Stale-zip / version signal: no trigger file touched (`templates/`, `builder.py`, `assembly.py`, `render.py`).
   `docs_gen.py` ships in the buildkit; `BUILDKIT_VERSION` stays 1.0.20, and the tier2 changelog row says so.
   Pak repo docs are regenerated and committed by the author with the factory CLI, so the deferral is loud and not stale-reporting. Not a finding.
10. Tests: 31 new tests cover the parser, tree, lanes, inverse, ordering and hash-seed determinism. The cycle guard is untested (W1).

## WARNING

- **W1** `src/vcfcf_managementpacks/docs_gen.py:426`. Authority: framework-reviewer dimension 10; the brief claims
  "row calculation is cycle-guarded". The guard fixes a real hang: base 55b781b loops forever in `_assign_depth`
  on a cycle reachable from the root (probe: `ak::ak||A||B||VMWARE::A::~child`). But no test exercises it.
  Mutation proof: I swapped the guard back to the base logic (`min()` plus unconditional child enqueue) in a
  scratch copy. All 42 docs-gen tests (recursive_traversal + cross_mp_edges) still pass. The self-edge test
  does not reach the guard because self-edges are skipped explicitly.
  → Add a test with a multi-node cycle reachable from the root (for example `ak::ak||ak::A::child||ak::B::child||ak::A::child`),
  run `_assign_depth` / `generate_docset` under a subprocess timeout or `signal.alarm`, and assert termination
  and the row placement.

- **W2** `src/vcfcf_managementpacks/docs_gen.py:201`, `:384`. Authority: dimension 2 (anchor 6c59f6b, keys derived
  without context). `levels.append((parts[1], ...))` drops the adapter kind, and the new own/foreign split is
  `k not in model.kind_map`. A foreign kind whose resource-kind key equals one of the pak's own kinds
  (for example a storage pak with its own `Datastore` kind that also references `VMWARE::Datastore::~child`)
  merges into the own kind. The probe shows the foreign parent edge collapsing into own `A > B` with no
  foreign root. No shipped pak trips it today. This is pre-existing, but this branch now builds root
  ordering and row placement on the bare key.
  → Key a level by `(adapter_kind, kind)`, or prefix foreign kinds (`VMWARE::Datastore`) when `parts[0]`
  differs from the pak's adapter kind. Render the foreign label as `Datastore (VMWARE)` so the Parent(s)
  column matches the Cross-MP table's `VMWARE Datastore` (it currently says just `Datastore`).

## NIT

- **N1** `docs_gen.py:142`. Authority: PR #290 (validator names `/skip` and wildcard levels); `knowledge/context/mpb/wire_reference/synology_nas_working_describe.xml:178` (`::child/skip`).
  `/skip` is a known grammar token but is not in `_PATH_MODIFIERS`. On a 3-part segment it is harmless.
  On a 2-part segment the kind key becomes `Kind/skip` (probe). A wildcard level renders as a `*` node.
  → Add `skip` to the stripped set with a comment that it carries no docs topology (or that its meaning is unconfirmed), and decide on and document wildcard handling.
- **N2** `docs_gen.py:140`. Authority: PR #290, RULE-002 (no fabrication). The comment
  "/preferred pick this path when several reach the same kind" restates the meaning PR #290 retracts as
  unconfirmed. The test module docstring repeats it ("path preference").
  → Reword to "runtime meaning unconfirmed (PR #290); no topology, stripped."
- **N3** `docs_gen.py:942`. The Excalidraw arrow keeps `roundness: {type: 2}`, so the 5-point self-loop and 4-point lanes
  render as curves through their points in Excalidraw, unlike the orthogonal SVG. The corners can overshoot.
  → Set `roundness: None` on multi-point arrows.
- **N4** `docs_gen.py:386`. The `if not roots:` fallback uses the same predicate as `candidates`, so it is dead code. A describe
  whose edges form a rootless cycle (or the contradictory `B::~child` + `B::child` pair) renders an
  empty Traversal Tree with no warning. This is pre-existing except for the inverse case.
  → Fall back to the first edge's parent, or raise `DocsGenError` naming the cycle.
- **N5** `docs_gen.py:373`. The docstring says foreign roots are "sorted by label, then key"; the code sorts by key, which is equal to the label for a foreign kind. → Align the docstring.
- **N6** `docs_gen.py:1075`, `:1130`. Canvas height comes from node positions plus `_MARGIN` (40). Same-row
  lanes on the deepest row sit at row bottom + 8·n, so five or more lanes there clip at the canvas edge.
  → Include lane extents (or the final `y`) in `max_y`.
- **N7** `docs_gen.py:1018-1052`, `:1154-1172`. The self-loop and routed-edge blocks are copy-identical in both
  renderers. → One helper per renderer. Also, the tier2 doc's "an upward edge that climbs more than one row
  can still cross" understates it: Synology's one-row SSD Cache > Disk climb crosses Volume's child bus
  at x≈375 with no hop. That is readable, but say "may cross other edges' connectors".

## If shipped as-is

UniFi and Synology docs correctly show self-nesting, every parent, and the Datastore as the LUN/export
parent. The SSD Cache > Disk edge no longer misreads. compliance and template are unchanged. The two
warnings are latent: a hang regression would go uncaught by the suite, and a future pak with a foreign
kind named like one of its own would get a merged node.
