# Content authoring rules

Rules for authoring super metrics, views, dashboards, custom groups,
and management packs. Each rule prevents a documented failure mode.

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
