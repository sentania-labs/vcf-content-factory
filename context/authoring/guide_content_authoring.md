# Content authoring rules

Rules for authoring super metrics, views, dashboards, custom groups,
and management packs. Each rule prevents a documented failure mode.

## Interview discipline — infer, don't interview

The framework's UX promise is "you write sentences, the framework
figures out the rest." Author agents that interrogate the user for
information they could infer break that promise. The Dell PowerEdge
v4 MP — built by someone outside this repo cloning the framework —
became the reference failure: the design walked the user through
every minor decision and still produced a structurally wrong result.
The lesson is structural, and applies to every author agent in
this repo.

### The rule

**Default to proposing. Interview only when the user's intent is
genuinely ambiguous AND the answer would change the output AND no
recon, doc lookup, or sensible default can resolve it.**

### What you do NOT ask the user about

- **Naming.** Every authored object is `[VCF Content Factory] <Name>`
  (MPs use the prose prefix without brackets). No questions.
- **File placement and folder.** Loaders handle the directory; the
  `name_path` convention puts dashboards in `VCF Content Factory`.
- **UUID generation.** The validator mints IDs on first run.
- **Whether to ground metric or property keys.** Always yes;
  ungrounded → refuse to author.
- **Default rollups, default chart types, default sharing, default
  severity tier, default container pinning.** Pick a sensible
  default and state it in the proposal. The user overrides if it
  matters.
- **Whether a value is a metric or a property.** Numeric
  time-series with a unit → metric. String/enum metadata or
  rarely-changing identity fields → property. Decide and move on.
- **Anything `ops-recon` already answered.** The orchestrator's
  brief contains the recon result. Don't re-ask the user.

### What you DO ask about — and how

Real ambiguities are decisions where two reasonable users would
pick differently and the choice materially changes the output.
Examples that genuinely warrant a question:

- Two existing super metrics already compute the requested thing
  with different rollups → "use the cluster-level rollup or write
  a new one for hosts?"
- The user says "production VMs" → "by folder name (`PROD-*`),
  by tag (`env=prod`), by name pattern, or by membership in an
  existing custom group?"
- A hardware adapter's components can be modeled per-component
  (alertable per PSU, more graph nodes) or as properties on the
  parent (compact, simpler) — the Dell-shape pattern. Default to
  per-component for hardware; propose otherwise with a reason.
- The MP can stitch to an existing VCF Ops kind (ARIA_OPS) or
  stand alone (INTERNAL) — major topology choice. Propose based
  on whether a sensible match exists in the live instance; ask
  only when there are multiple plausible parents.

**Always ask with a proposal on the table.** Bad: "How should I
model the firmware?" Good: "I'm modeling firmware as properties on
the System kind because they rarely change and are easy to read
at-a-glance. Switch to a separate Firmware kind if you want
per-component alerting."

### Probe before asking

When a recon call would answer the question, run recon. Don't ask
the user "what's the resource kind for VMs?" — the orchestrator
already ran ops-recon, the answer is in the brief. Don't ask
"does this property exist?" — search `docs/vcf9/metrics-properties.md`
or call the live `/statkeys` endpoint.

### Batch the real ambiguities

Don't ping-pong. Collect every genuinely ambiguous decision that
will materially change the output, present them together with
proposed defaults, and act on the user's response in one round.
One round trip, not five.

### Track-specific examples

Each author agent's prompt expands this section with concrete
"infer / ask" examples for that track. The shared rule is here;
the track-specific bullets live in
`.claude/agents/<agent>.md` under "Interview discipline."

## Super metrics

### No compound && in string where clauses
Compound `&&` silently fails with string operators (`equals`,
`contains`). Use the SM subtraction pattern instead: create
single-condition SMs and subtract overlapping populations via
`${this, metric=Super Metric|sm_<uuid>}`.

### SM view columns need "Super Metric|" prefix
View column `attributeKey` must be `Super Metric|sm_<uuid>`, not bare
`sm_<uuid>`. Bare form validates but renders blank. The renderer
auto-prefixes; YAML authors write bare `sm_<uuid>`.

### SM references must resolve to UUIDs at render time
View columns using `supermetric:"<name>"` MUST resolve to
`Super Metric|sm_<uuid>` when the view XML is rendered. The
renderer hard-fails if resolution fails. Unresolved name references
produce broken XML that VCF Ops silently ignores (blank column, no
error). The renderer loads SMs from `content/supermetrics/` — if
the SM YAML doesn't exist or has no `id` field, resolution fails.
Never ship a view with an unresolved SM name reference.

### Metric labels cannot contain | or :
The VCF Ops stat key format uses `|` as the group separator.
MPB rejects metric labels containing `|` or `:` at collection
time with "Metric key cannot contain reserved characters." Use
`-` or spaces instead.

### Percentiles are view transforms, not SMs
Statistical transforms (95th percentile, avg over window) are view
column transformations. Don't author SMs for single-metric rollups
over time. SMs are for computing across objects.

### Groups vs SMs — reach for SMs first
For "sum metric X across objects matching property Y," use one SM with
a where-clause and multi-kind assignment. Reach for custom groups only
when the set needs a name (view scope, alert target, browsing).

## Dashboards and views

### Self-provider View needs pinned container root
`selfProvider: true` with `resource: null` renders blank. Pin to a
container (e.g., `{VMWARE, vSphere World}`).

### Dashboard pin prefix is per-adapter
`resourceKindId` format: `<6-digit prefix><adapterKey><resourceKey>`.
Wrong prefix installs cleanly but widget silently fails to render.
Known prefixes: VMWARE=002006, Container=002009, NSXTAdapter=002011.
Dashboards default to `shared: true`.

### Heatmap — omit max_value
Leave `max_value` blank. Setting it hardcodes the color scale ceiling
and makes threshold guardrails unreliable.

## Management packs

### Request paths must be full from root
Every `path:` in MP YAML must be a full path (e.g.,
`/proxy/network/api/...`). Set `base_path: ""`. MPB does NOT normalize
`../` segments.

### Bump version per shipped render
Bump `build_number` before every render shipped to a live instance.
MPB UI can't distinguish identical version+build pairs. Bump `version`
for substantive changes; `build_number` for iteration tweaks.

### Dual-parent display is normal at peer level
Only problematic at ROOT level with same display name. Peer-level
dual-parents (different names) are normal and useful — same as VMs
under both Host and Resource Pool.

### URL-path-identity — CHAINED_REQUEST resolves it
When the chained response doesn't echo the parent ID, use
CHAINED_REQUEST objectBinding. The renderer auto-detects this. No
SDK pivot needed.

### ARIA_OPS objects are export.json-only
ARIA_OPS objects appear in export.json (ariaOpsConf block) but NOT
in describe.xml ResourceKinds or template.json resources. The pak
runtime validator rejects non-`mpb_`-prefixed resourceKind values.
Skip ARIA_OPS objects when generating template.json and describe.xml.

### Events are stripped from pak builds
MPB events defined in YAML render correctly for the design import
path but the pak runtime expects a different schema. All factory pak
builds emit `events: []` in export.json, template.json, and
design.json. This is a known TOOLSET GAP — no ground-truth reference
exists for the pak runtime event format.

### pak-compare is the install gate
Run `pak-compare` against the closest MPB reference pak after every
build. Zero BLOCKINGs = safe to install. The tool checks manifest,
describe.xml, export.json, and template.json structure against a
reference. See `context/mpb_pak_structural_reference.md` for the
reference inventory.
