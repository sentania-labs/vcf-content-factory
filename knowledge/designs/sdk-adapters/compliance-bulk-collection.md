# Compliance adapter: bulk collection (read broad, evaluate locally, push in batches)

- **Type:** managementpack (Tier 2 SDK adapter change) + framework facade addition
- **Slug:** compliance-bulk-collection
- **Adapter repo:** `content/sdk-adapters/compliance/` (sentania-labs/vcf-content-factory-sdk-compliance)
- **Date:** 2026-10-02
- **Status:** drafted, awaiting Scott's review. Nothing built.

## Initial prompt

Scott, 2026-10-02 (verbatim), after seeing the adapter collects every 60
minutes:

> we should dial down the collection so that we get faster turn around, but also so that we can provide more meaningful "admin made a change under the rader to ssh in or some such"

Orchestrator estimated a cycle could reach about 10 minutes at 5,000
objects (a straight-line guess from one 20 second devel cycle). Scott:

> if it takes us 10 minutes to do the collection we need to optimize.  pull back broad chunks of data and select out what we want locally and process rather then hundreds of API calls.

> let's do the design

## What the code does today (read 2026-10-02, build 84)

Counts are per collect cycle, per adapter instance (one per vCenter),
against the SCG 9.1 benchmark.

**vCenter reads (`VSphereClient`).** Inventory listing is already one bulk
`RetrieveProperties` over a ContainerView per kind (`retrieveViewRows`,
VMs get `name` and `runtime.host`). Everything after that is per object:

| Object | Calls | What |
|---|---|---|
| VirtualMachine | about 7 | 1 for `config.extraConfig` (covers the 16 advanced-setting controls), then one `RetrieveProperties` per `vim_property` control (6) |
| HostSystem | about 14 plus esxcli | product version (1), connection state (1), advanced settings (2: `configManager` then `QueryOptions(null)`, covers 38 controls), one per `vim_property` control (6, four of them `service_state`), plus one esxcli call per esxcli recipe (8) |
| DVS, DVPG, Cluster | 2 to 7 | one per `vim_property` control |
| vCenter | a handful | advanced settings, 5 VAMI calls; one object, not a scaling concern |

A property read that fails on its full path retries on shorter prefixes,
so these are floors. There is no `RetrievePropertiesEx` and no paging
anywhere in the client.

**Ops pushes (`SuiteApiStitcher`).** Two POSTs per scored object
(`/api/resources/{id}/properties`, `/api/resources/{id}/stats`). The
bearer token is cached per instance, so auth is not per call. Every
control's Actual / Expected / Description property is re-sent every cycle
whether or not it changed.

**Scale.** At 5,000 VMs and 200 hosts: roughly 35,000 VM reads, 4,400 host
reads, and 10,400 pushes per cycle. Devel today: 164 scored objects, about
20 seconds per cycle (one observation, from collector log stamps; the
adapter logs no duration).

**Interval.** `monitoringInterval="60"` on the adapter kind, no recorded
rationale; the other five SDK paks declare 5.

## Vision

Cycle cost should grow with pages, not objects. Read each object kind in a
few paged bulk requests, evaluate every control locally against what came
back, and push results in batches. Then the interval can come down to
where compliance drift is seen in minutes.

### 1. Measure first (build A)

Add per-phase wall time and call counts to the existing cycle summary log
line: inventory, host reads, VM reads, network reads, vCenter reads,
esxcli, pushes; SOAP calls and Suite API calls as counts. No behaviour
change. This is the baseline every later build is judged against, and it
replaces the 10 minute guess with a number.

### 2. Bulk reads (builds B and C)

One paged property collector request per kind over the ContainerView,
with a pathSet that is the union of what the selected benchmarks need:

- **VirtualMachine:** `config.extraConfig`, `runtime.host`, and each
  `vim_property` path (`config.ftEncryptionMode`,
  `config.flags.enableLogging`, `config.bootOptions.efiSecureBootEnabled`,
  `config.hardware.device`, and so on).
- **HostSystem:** `config.product.version`, `runtime.connectionState`,
  `config.option` (advanced settings), `config.service.service`,
  `config.firewall.defaultPolicy`, `config.lockdownMode`.
- **DVS, DVPG, Cluster:** their `config.*` / `configurationEx.*` paths.

The pathSet is derived from the loaded benchmark's recipes, not hand
listed, so a new control needs no code (the bulk-read dynamic pattern in
the `vcfops-sdk-adapter` skill). The recipe styles (`scalar`, `bool`,
`bool_policy`, `service_state`, `list_empty`, `vlan_id_not`,
`vm_hardware_device_absent`, `string_list_join`) are evaluated against
the per-object result held in memory instead of each issuing a call.

Use `RetrievePropertiesEx` / `ContinueRetrievePropertiesEx` with a page
size per kind (hosts small because `config.option` is large; VMs larger),
and process each page as it arrives rather than holding the whole
inventory in memory.

**Build B is shadow mode.** It runs the bulk path alongside the existing
per-object path, scores from the per-object path as today, and logs every
control where the two disagree. Nothing the user sees changes. Two things
are unproven and this is how they get proven:

- Whether `HostSystem.config.option` matches what `QueryOptions(null)`
  returns from the host's option manager, for every setting the
  benchmarks use.
- Whether vCenter serves these wide property sets at acceptable cost.

**Build C switches** scoring to the bulk path only after shadow mode shows
zero disagreements on devel across all three vCenters.

What stays per object: esxcli recipes (a command executed on a host, not a
property; dedupe so recipes sharing a command call it once per host per
cycle) and the vCenter appliance's own VAMI reads.

### 3. Batched pushes (build D, needs a framework change)

The Suite API has multi-resource endpoints: `POST /api/resources/stats`
(`addStatsForResources`, a list of `{id, stat-contents}`) and
`POST /api/resources/properties` (`addResourcesProperties`, a list of
`{resourceId, property-contents}`), identical in the 9.0 and 9.1 specs.
`SuiteApiStitcher` exposes only the single-resource calls.

- **Framework (tooling, then framework-reviewer):** add batch push calls
  to the facade with a bounded batch size, the same no-throw contract,
  and the one-line failure logging (closes issue #192 for the push paths
  in the same change).
- **Adapter:** accumulate per-object results and flush in batches.
- **Properties on change only:** keep a per-object fingerprint of the last
  pushed property set in memory and send properties only when it
  differs, with a full re-send after an adapter restart and every N
  cycles as a safety net. Stats go every cycle so metrics stay fresh.

Unproven, to be probed on devel before the adapter depends on it: how the
batch endpoints report a partial failure (the spec lists only 200), and
the practical batch size limit.

### 4. Interval (build E)

Decide the shipped `monitoringInterval` from build A through D's measured
numbers, not before. Working assumption: 15 minutes as the default, with
the per-instance override documented, and 5 if the measurements support
it at realistic scale.

## What must not regress

- **Unreadable is not compliant** (`knowledge/lessons/unreadable-is-not-compliant.md`).
  A path absent for an object in a bulk page is UNREADABLE with a reason,
  never skipped and never a pass. Per-control unreadable reasons (build
  74) must survive the move.
- **Failed listing holds back the rollup** (builds 78 and 79). A failed
  page marks its kind incomplete exactly as a failed inventory listing
  does today; the rollup for that kind is not pushed.
- **Per-object fallback.** If a bulk page fails, retry that page's
  objects on the existing per-object path before declaring them
  unreadable, so one bad object cannot blind a kind.
- **The MOID trap.** Bulk reads are per vCenter session, so scoping is
  unchanged; batch pushes address resources by the already-resolved
  Suite API id.
- **A failed batch push** must not silently drop a batch: log which
  resources were in it, and fall back to single-resource pushes once.

## Acceptance

| Measure | Today | Target |
|---|---|---|
| vCenter calls per cycle | grows with objects times controls | grows with pages, plus esxcli per host |
| Suite API pushes per cycle | 2 per object | about 2 per 100 objects, properties only on change |
| Shadow-mode disagreements on devel | n/a | zero, all three vCenters, before build C |
| Scores, rollups, alerts on devel | baseline | identical before and after build C and D |
| Cycle time on devel | about 20 s (one observation) | measured by build A, then lower |

## Out of scope, noted

- **Change detection for transient drift.** An admin who enables SSH and
  disables it between polls is invisible to polling at any interval. The
  answer is tailing vCenter events (service start, config change) since
  the last cycle, or a fast pass over a few volatile controls. That
  changes what the pak claims to do and gets its own design.
- **Edge removal** on ComplianceWorld (see
  `compliance-environment-computed-metrics.md`).

## Sequencing

Starts after the environment computed-metrics change merges: both touch
`ComplianceAdapter.java`, and that change is mid-proof on devel. Builds A
through E each go author, `sdk-adapter-reviewer`, devel install on Scott's
yes. Build D additionally needs the framework change first (`tooling`,
`framework-reviewer`, factory PR, buildkit publish before any `v*` tag).
