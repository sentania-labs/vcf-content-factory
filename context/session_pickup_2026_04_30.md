# Session pickup — next session start

End of 2026-04-29 session. Long, productive, ended on a pivot
decision: Synology MP cannot ship as MPB; pivoting to Unifi for
Phase 1.5.

## Read first (in this order)

1. **`context/mpb_synology_pickup_2026_04_29.md`** — what happened
   with Synology and why it's parked. The §"End-of-session verdict"
   and §"Substrate gains today" sections are the load-bearing parts.
2. **`context/growth_path_2026_04_29.md`** — the phased plan toward
   "Hi, I'm vcf-cf." Phase 1 terminated; Phase 1.5 is the next move.
3. **`context/mpb_object_binding_wire_format.md`** — substrate
   reference. Three validation phases documented, four shape patterns
   captured from reference packs.
4. **`context/mp_chain_authoring.md`** — author-facing chain grammar.

## First action

Spawn `mp-designer` to propose the Unifi MP design from the existing
api map. Phase 1.5 discipline: api-cartographer's existing map is fair
game (we built it 2026-04-18), but mp-designer and mp-author do NOT
consult `references/jcox-au_vmware/unifi_MP_Builder_Design.json`
during design — that's the post-render diff anchor only.

Inputs ready on disk:

- **API map**: `context/api-maps/unifi-network-api.md` (1056 lines,
  comprehensive — UDM Pro, classic session auth, 25 endpoints probed)
- **Live target**: `unifi.int.sentania.net` (UNIFI_HOST in `.env`)
- **Credentials**: `UNIFI_USER=claude` + password in `.env`. The
  `UNIFI_API_KEY` slot is empty; Scott can generate one in UniFi
  Network → Settings → Control Plane → Integrations if he prefers
  bearer auth over session auth.
- **Diff anchor (post-render only)**:
  `references/jcox-au_vmware/unifi_MP_Builder_Design.json`

## Phase 1.5 sequence

1. `mp-designer` reads the api map → produces
   `designs/unifi-mp-v1.md` (object hierarchy, identifier strategy,
   chain decisions, relationship grammar)
2. **Decision gate**: review the design with Scott before authoring
3. `mp-author` writes `content/managementpacks/unifi.yaml`
4. `python3 -m vcfops_managementpacks validate` (must exit 0)
5. `python3 -m vcfops_managementpacks render-export
   content/managementpacks/unifi.yaml --out tmp/unifi_v1.json`
6. **Diff against jcox-au's design** —
   `references/jcox-au_vmware/unifi_MP_Builder_Design.json`. Note any
   structural divergence; treat divergences as either (a) factory
   gap requiring substrate fix, or (b) legitimate alternative
   architecture
7. Drag into MPB UI on devel for import + verify + install
8. **End state**: working factory-built MP installed on devel with
   Unifi data flowing in

## Things to watch for during Phase 1.5

The 2026-04-18 api-map predates today's substrate work. When
mp-designer runs, watch for:

- **Echo vs no-echo chained APIs.** If any Unifi endpoint chains
  with no parent-id echo, we're back in the Synology pattern. Bail
  to SDK or skip the metric. (Survey of jcox-au's design suggests
  Unifi APIs DO echo — they use `me=ATTRIBUTE` with `ome=METRIC`
  patterns.)
- **Aria stitching.** jcox-au's design uses METRIC-ome stitching
  on 3 of 4 list kinds (Devices, Clients, WiFi Broadcasts) with labels
  like "Uplink Device ID" and "ID_device". This is peer-to-peer
  stitching within the MP itself. Today's renderer has the
  `stitch_to:` knob (added 2026-04-29 morning) but it's untested in
  the wild — Unifi will be the first real exercise.
- **Singleton vs world.** jcox-au's design has 2 unnamed scalar
  objects (probably world + singleton). Confirm the pattern matches
  factory grammar.

## If Scott decides to revisit Synology before Unifi

Two paths from `mpb_synology_pickup_2026_04_29.md` §"Two paths to
resolve":

- **Path 1 (community-pattern, fastest)**: mp-author edits YAML to
  drop Volume's chained `volume_util` metricSet. Volume gets metrics
  from `get_volumes` only (size_total, size_free, etc.). Per-volume
  IO rate metrics are lost. Renders/imports/installs cleanly.
- **Path 2 (SDK pivot)**: Synology becomes the Phase 2.5 SDK
  exercise. The api map and design doc work transfer; only the
  output target changes. Significant new tooling needed —
  `vcfops_sdk_adapter` package alongside `vcfops_managementpacks`.

Default expectation: Phase 1.5 (Unifi) first.

## Things NOT to do next session

- Don't re-attempt Synology MP imports — we have empirical
  confirmation it can't be made to work cleanly. Re-running v4 or
  variants wastes time.
- Don't consult jcox-au's Unifi design while authoring — the
  calibration value of Phase 1.5 depends on us doing it independently
  first.
- Don't skip the design-review gate (step 2 above). Scott reviews
  before authoring; that's where ambiguities get resolved before
  they land in YAML.

## Optional follow-ups (parked, not blocking Phase 1.5)

- **Renderer cleanup** — `render.py` chained-secondary branch emits
  the §10.2 shape, which we know is broken. Could refuse no-echo
  chains at render time with a clear "this API pattern requires SDK"
  error. Substrate hygiene; not blocking.
- **Folding new reference packs into wire-format doc** — the
  `mpb_object_binding_wire_format.md` doc still has §1/§3.4/§4.2
  marked as superseded but not rewritten. ~30 min of doc cleanup.
- **API surface doc** — the `/jobs` bearer-reachability finding from
  api-explorer is in `mpb_api_surface.md` but should be cross-linked
  from `mpb_object_binding_wire_format.md` §8.3.

## Session metadata

- Date: 2026-04-29
- Duration: ~4 hours of substrate work
- Tooling changes shipped: 4 separate `tooling` agent runs
  (is_singleton + chain grammar + case fixes + 5 validator rules;
  later: world_count relaxation; later: drop objectBinding for
  chained; later: cross-metricSet ATTRIBUTE for chained — last one
  empirically broken)
- Authoring runs: 3 mp-author iterations (final state: v3 YAML,
  not in shipping state per above)
- api-explorer runs: 2 (objectBinding wire format + verify-time
  rules; both produced durable substrate doc updates)
- Reference packs ingested: 3 new (Unifi jcox-au, phpIPAM jcox-au,
  vSAN-policy vrealize.it)
- New context files: 3 (`mpb_object_binding_wire_format.md`,
  `mp_chain_authoring.md`, `growth_path_2026_04_29.md`)
- Scope of substrate: import-time validation, per-object validation,
  verify-time validation, three new shape patterns documented
