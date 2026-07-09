# MPB Synology import — workstream log (2026-04-29)

Status: **READY FOR IMPORT TEST.** Rendered design at
`tmp/synology_rendered_v2.json` matches the working community export
shape (5 objects, no rogue stub, Diskstation as singleton, volume_util
chain wired).

## Backstory (compressed)

Scott imported `tmp/mp-step1/synology_nas_design.json` via the MPB UI on
both labs (primary + devel). Both rejected with "unknown error" toast.
He uninstalled the prior adapter and deleted the prior design — clean
slate, still failed. He provided his pre-clean export inline as the
authoritative working baseline (last successful install).

Static diff agent identified three structural defects:
`context/mpb_synology_import_diff_2026_04_29.md`.

## Defects and resolution

| # | Defect | Resolution | Class |
|---|---|---|---|
| 1 | Rogue "Synology NAS World" object (no metricSets, no identifiers, null nameMetricExpression) | **CLOSED** — author was forced to add the stub because (a) renderer had no singleton-with-identifiers shape, and (b) loader required `world_count == 1`. Both fixed in tooling: new `is_singleton: true` knob; loader rule relaxed to `world_count <= 1`. mp-author deleted the stub. Final YAML has zero `is_world: true` kinds. | Tooling |
| 2 | Diskstation flipped to `isListObject: true` | **CLOSED** — Diskstation now `is_singleton: true` (renders `isListObject: false` with identifiers + metrics). | Tooling + Author |
| 3 | `volume_util` dangling chain (no `chainingSettings`) | **CLOSED** — explicit `chains_from`/`bind` grammar added (see `context/mp_chain_authoring.md`). mp-author wired the chain on Volume's second metricSet. Renderer emits full `chainingSettings` block matching working export. | Tooling + Author |
| 4 | Missing `paging` on 6 requests | **PARKED** — `paging:` grammar declared retired 2026-04-21 per `management_pack_authoring.md`. MPB regenerates paging trees from live API introspection at import time. Existing offset/limit params are the known-working pattern. | Not a defect |
| 5 | `mpb_min_event_severity` default `"WARNING"` ≠ option `"Warning"` | **CLOSED** — `_SRC_OVERRIDES` case fixed in render.py. While in there, `mpb_ssl_config` option list also corrected (uppercase → title case). | Tooling |
| 6 | Missing `Content-Type` on `getSession` | **OPEN GAP** — auth grammar has no `headers:` knob on `login:` block. Likely not a runtime blocker (adapter runtime usually injects Content-Type). Tooling task to add header authoring on auth requests, deferred. | Tooling gap |
| 7 | 21 explicit `null`s in DML descriptors | **PARKED** — lowest priority; defer until evidence it matters. | Tooling cleanup |

## Architecture decision (2026-04-29)

**`is_world` vs `is_singleton` are distinct concepts.** Codified in the
loader.

- `is_world: true` = cross-instance anchor, ONE per Ops deployment,
  empty stub (no identifiers, no metricSets, no metrics). Sits *above*
  the adapter instance level. Validator now rejects any `is_world: true`
  with non-empty identifiers OR non-empty metricSets.
- `is_singleton: true` = one-per-adapter-instance named entity, has
  identifiers, holds device-level metrics. Sits *below* the adapter
  instance.
- `world_count == 0` is now valid (e.g. Synology v2). `world_count == 1`
  remains valid. `world_count >= 2` is a hard error.

Two-adapter sanity check: with `is_singleton`, two Synology adapter
instances produce two parallel isolated trees, each with their own
Diskstation (different serials). With `is_world` on Diskstation (the
broken model mp-author originally produced), two adapters would collide
on a single shared Diskstation object — silent data corruption.

## v2 vs v3 scope

**v2 (now):** No world kind. Diskstation as `is_singleton: true`.
Matches the 2024 community pack's 5-kind topology.

**v3 (deferred):** Add an empty `Synology World` (`is_world: true`)
stub *if and when* fleet-level aggregation supermetrics are authored.
Cheap to add later. The `knowledge/designs/synology-mp-v1.md` file currently
documents Diskstation as `is_world: true — SIDECAR`; that's stale wording
from a prior iteration and gets cleaned up when v3 work begins (a natural
moment for `mp-designer` to revisit the doc).

## Tooling delivered (2026-04-29)

In rough chronological order:

1. New `is_singleton: true` resource-kind shape in loader + renderer
2. Explicit chain grammar (`chains_from` / `bind` / `${chain.X}`) — see
   `context/mp_chain_authoring.md`
3. `_SRC_OVERRIDES` case fixes (mpb_min_event_severity,
   mpb_ssl_config)
4. Validator guardrails: dangling-chain rejection, mutex check on
   is_world+is_singleton
5. Validator tightening: reject `is_world: true` with non-empty
   identifiers or non-empty metricSets (steers author to is_singleton)
6. Loader rule relaxed: `world_count <= 1` (was `== 1`); INFO note when
   `world_count == 0`

## Final render shape (parity check)

```
                       NEW   WORK
objects                  5      5    match
relationships            3      3    match
events                   0      0    match
requests                10     10    match
```

Only legitimate diff: Volume has 2 metricSets in NEW vs 1 in WORK —
that's the chained `volume_util` we added (per-volume IO metrics).
Feature add, not a regression.

## Source-of-truth artifacts

- Final rendered exchange JSON: `tmp/synology_rendered_v2.json`
- Failing original input: `tmp/mp-step1/synology_nas_design.json`
- Working baseline (community export, normalized via MPB):
  `context/mpb_wire_reference/synology_nas_working_export.json`
- Scott's pre-clean export of the last install (pasted inline
  2026-04-29; structurally identical to working baseline)
- Diff diagnostic: `context/mpb_synology_import_diff_2026_04_29.md`
- Chain authoring grammar: `context/mp_chain_authoring.md`
- Design doc (named v1, content is v2 Strategy C):
  `knowledge/designs/synology-mp-v1.md` (stale on the is_world wording — clean up
  in v3)
- Authored YAML: `content/managementpacks/synology_nas.yaml`
- Renderer: `vcfops_managementpacks/render.py`
- Render-export: `vcfops_managementpacks/render_export.py`
- Loader: `vcfops_managementpacks/loader.py`
- Chain wire spec: `context/mpb_chaining_wire_format.md`
- Author memory of architecture: `memory/project_synology_mp_strategy.md`,
  `memory/project_synology_mp_v2_install_state.md`

## End-of-session verdict (2026-04-29)

**Synology MP cannot ship cleanly as MPB.** Empirical evidence across
v2/v3/v4 import iterations confirmed an irreducible data-model
mismatch between Synology's DSM API and MPB's chained-collection wire
format.

### Why

Synology's `SYNO.Core.System.Utilization` endpoint takes `location`
(volume_id) as a URL parameter and returns IO data **without echoing
the volume_id back**. MPB's `objectBinding` mechanism requires the
chained response to contain an attribute that identifies the row
(self-reference). Three failure modes confirmed empirically across
three validation phases:

- **Import-time** (POST /designs/import) — accepts most shapes
  including malformed; not discriminating
- **Per-object validation** (UI drill-down on
  /designs/{id}/objects/{id}) — strips `objectBinding.type` to `null`
  when `originId` crosses metricSets. This tripped v2 and v4.
- **Verify-time** (UI Verify wizard / source-test) — enforces
  per-resource null-count rule: at most one null binding, must be
  chain-parent. This tripped v3.

No `objectBinding` shape passes all three phases when the chained
API doesn't echo the parent identifier. The community Synology pack
worked around this by **not exposing** volume_util's metrics at all.
We attempted to expose them; the wire format won't allow it.

### Current state

`content/managementpacks/synology_nas.yaml` left in v3 state — 5
object kinds, Volume has chained `volume_util` metricSet. Renders
emit the §10.2 cross-metricSet ATTRIBUTE shape (empirically broken
at per-object validation, but harmless until imported). The YAML is
**not in shipping state**.

### Two paths to resolve when Synology returns to active work

- **Path 1 (community-pattern):** Edit YAML to remove Volume's
  chained metricSet. `volume_util` request stays in design but goes
  unbound (matches community pack). Renders/imports/installs cleanly.
  Loses per-volume IO rate metrics. ~10 min of mp-author work.
- **Path 2 (SDK pivot):** Move Synology MP to the Operations
  Adapter SDK queue. Imperative Python matches chained responses by
  holding the chain param in scope. Bigger commit but exposes the IO
  data. See `growth_path_2026_04_29.md` Phase 2.5.

**Decision 2026-04-29:** pivot to Unifi MPB (Phase 1.5) before
deciding Synology's fate. Synology stays in this half-built state
until Scott returns to it.

## Substrate gains today (durable, compound for future MPs)

1. **Three-phase MPB validation model** documented (import →
   per-object → verify), with rules per phase. See
   `mpb_object_binding_wire_format.md` §1, §6, §8.
2. **`is_singleton: true`** singleton-named-entity shape (one per
   adapter instance, identifiers + metrics). Distinct from `is_world`
   (cross-instance anchor, empty stub).
3. **Explicit chain grammar** (`chains_from` / `bind` / `${chain.X}`)
   — see `mp_chain_authoring.md`.
4. **`world_count <= 1`** — MPs without world stubs now valid.
5. **Validator guardrails** — 5+ new rules catch the failure modes
   we hit.
6. **`/jobs` bearer-reachability** — long-standing api_surface gap
   closed; documented in `mpb_api_surface.md`.
7. **Three new reference packs ingested** — Unifi (jcox-au), phpIPAM
   (jcox-au), vSAN-policy (vrealize.it). vSAN-policy validates the
   `me=PARAMETER + ome=ARIA_OPS_METRIC` Aria-stitching pattern.
8. **URL-path-identity API pattern recognition** — recorded in
   auto-memory; mp-designer should detect this at design time and
   recommend SDK pivot.

## Open follow-ups (parked)

- **getSession.headers** — auth grammar gap. Pick up if Unifi auth
  surfaces an issue.
- **21 explicit nulls in DML descriptors** — renderer cleanup,
  lowest priority.
- **Renderer cleanup** — `render.py` chained-secondary branch emits
  the §10.2 shape (broken). Future tooling pass should refuse no-echo
  chains with "use SDK" error, OR detect echo vs no-echo and emit
  appropriately.
- **Design doc** — `knowledge/designs/synology-mp-v1.md` stale `is_world` line.
  Lower priority since Synology is moving SDK-ward.
