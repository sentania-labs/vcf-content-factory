# VM snapshot instanced attributes — row fan-out, property support, ghost instances

- Date: 2026-07-27
- Agent: api-explorer
- Instance: `vcf-lab-operations.int.sentania.net` (prod profile),
  **VCF Operations 9.1.0.0**
- Driving question: for an "Active VM Snapshot Inventory" list view on
  VMWARE VirtualMachine, does the instanced-group column mechanism
  produce **one row per snapshot instance**, do **property** attributes
  participate, and what does the built-in snapshot report already cover?
- Follow-on from `recon_log.md` §"Recon: Active VM Snapshot Inventory
  view/dashboard (2026-07-27)".

> **Unsupported-surface caveat.** The render endpoint used throughout
> (`GET /internal/views/{id}/data/export`) requires
> `X-Ops-API-use-unsupported: true` and carries no backwards-compatibility
> guarantee. See `knowledge/context/api-surface/view_render_internal_endpoint.md`.

---

## Method

1. Enumerated all 50 `VMWARE:VirtualMachine` resources, collected
   `GET /api/resources/{id}/properties`, grouped instanced keys matching
   `diskspace:<dsInternalId>|snapshot:snapshot-<n>|*`. 17 VMs carry them;
   the fattest is `vcf-lab-sddcmgr` with **13** instances.
2. Authored a throwaway view
   `[VCF Content Factory] SCRATCH Snapshot Fanout Probe`
   (`203c22c5-8474-48cd-bf09-423d5a0a8e4e`) with an `instanced_group`
   driver + property/metric member columns, synced it to prod, rendered
   it server-side against three multi-snapshot VMs, then **deleted it**
   (verified: subsequent render returns HTTP 400 "No appropriate view
   definition is found").
3. Exported `REPORT_DEFINITIONS` and `VIEW_DEFINITIONS` via
   `POST /api/content/operations/export` to read the built-in report's
   embedded view definition verbatim.
4. Read attribute metadata via
   `GET /api/adapterkinds/VMWARE/resourcekinds/VirtualMachine/properties`
   and the Default Policy XML via `GET /api/policies/export`.

No instance configuration was changed.

---

## Q1 — Row fan-out: **ONE ROW PER SNAPSHOT INSTANCE. Confirmed.**

The driving wire fields are the ones already documented in
`knowledge/context/wire-formats/view_column_wire_format.md`
§"Instanced-group columns": a **driver Item** with
`attributeKey="Instance Name"`, `isInstancedGroup="true"`,
`showInstanceName="true"`, `instanceGroupName="GROUP_diskspace"`,
`keepInstanceSummary="false"`. There is **no** `elementInstancesConfig`
field — that string appears in neither `operations-api.json` nor
`internal-api.json` nor any reference pak. `isInstancedGroup` is the
whole mechanism.

Rendered output for `vcf-lab-sddcmgr` (13 property instances → **13
rows**, single VM subject), verbatim (abridged to 3 of 13):

```json
{"columns":[{"key":"objId","label":"Name"},{"key":"1","label":"Instance"},
 {"key":"2","label":"Snapshot Name"},{"key":"3","label":"Snapshot MOR"},
 {"key":"4","label":"Age Days"},{"key":"5","label":"Used","unit":"GB"},
 {"key":"6","label":"Parent Cluster"}, ...]}

{"1":"103:snapshot-2",     "2":"VM Snapshot 10/30/2025, 9:02:18 AM","3":"snapshot-2004","4":-1.0,"5":null,"6":"vcf-lab-mgmt-cl01","objId":"vcf-lab-sddcmgr"}
{"1":"356893:snapshot-10", "2":"pre-np01-nfs-vlan-fix-20260608",   "3":"snapshot-22131","4":-1.0,"5":null,"6":"vcf-lab-mgmt-cl01","objId":"vcf-lab-sddcmgr"}
{"1":"356893:snapshot-16", "2":"pre-vcfa-0200-cleanup-20260717-1617","3":"snapshot-29002","4":-1.0,"5":null,"6":"vcf-lab-mgmt-cl01","objId":"vcf-lab-sddcmgr"}
```

Key facts an author needs:

- **Fan-out is per-instance, not per-VM.** `objId` / `objUUID` repeat on
  every row; the `Instance` column carries the instance token.
- The rendered instance token is the **collapsed composite**
  `<dsInternalId>:snapshot-<n>` (e.g. `356893:snapshot-16`) — the wire
  key `diskspace:356893|snapshot:snapshot-16|name` has its `diskspace`
  prefix and `snapshot:` segment stripped for display. It is a
  **two-level** instance (datastore × snapshot slot) rendered as one
  token. This is not a pretty label; if the requester wants a clean
  "Snapshot Name" column, use the `|name` member column, not the driver.
- **Flat (non-instanced) columns coexist fine** and repeat their single
  value on every fanned-out row (`summary|parentCluster` above). So
  Parent Cluster / vCenter / Datastore columns work in a fan-out view.
- The vmbro "VM Snapshots List" pinning to `snapshot-1` is **just how
  that author captured it**, not a limitation: `sample_instance` is
  design-time pattern-identification only. Proof — the probe used
  `sample_instance: "356893|snapshot:snapshot-1"`, a key that does **not
  exist** on `vcf-lab-sddcmgr` (whose instances start at `snapshot-2` /
  `snapshot-3`), and all 13 real instances still rendered. This
  independently reconfirms the 2026-07-10 licensing-view EXPANDS finding
  on a second attribute family.

### Factory YAML that produced it (works as-is)

```yaml
subject: {adapter_kind: VMWARE, resource_kind: VirtualMachine}
columns:
  - display_name: "Instance"
    instanced_group:
      name: GROUP_diskspace          # -> instanceGroupName
      show_instance_name: true
      keep_instance_summary: false
  - display_name: "Snapshot Name"
    is_property: true
    is_string_attribute: true
    instanced_group:
      name: GROUP_diskspace
      prefix: "diskspace"                        # segment before ":"
      suffix: "name"                             # segment after "<instance>|"
      sample_instance: "356893|snapshot:snapshot-1"   # design-time only
```

Note the split: for this family `prefix` is the bare `diskspace` and the
`sample_instance` swallows the whole `<dsId>|snapshot:snapshot-<n>`
composite, because the loader synthesizes
`f"{prefix}:{sample_instance}|{suffix}"`. That yields exactly the vendor
key shape `diskspace:356893|snapshot:snapshot-16|name`.

`GROUP_diskspace` is VMware's own token for this family (per
`View - Set 4.xml`); it is an opaque grouping label, not server-validated.

## Q2 — Properties in instance breakdown: **fully supported, they fan out**

`isProperty=true` member columns are not second-class. In the render
above, `name` (STRING), `mor` (STRING) and `numberOfDays` (numeric)
are all properties and all resolved **per instance**. Metric members
(`used`, `accessTime`) render in the same rows.

Indeed, **the properties are what drive the fan-out set here**: on
`docker` the row set is the union of property instances (6 rows), while
only one instance has live metric data. So a property-only instanced
view fans out fine with no metric member column at all.

## Q1b/Q2b — The trap: **instanced snapshot PROPERTIES are ghosts**

This is the load-bearing design fact for an *Active* snapshot inventory.

**Instanced snapshot properties persist after the snapshot is deleted.**
They are never reaped. Live cross-check (`summary|snapshot_count` +
instanced `|used` metric over 7 days):

| VM | property instances | live `snapshot_count` | instances with current `\|used` |
|---|---|---|---|
| vcf-lab-sddcmgr | 13 | 1 | 0 (one sample on 07-21, value 0.0) |
| docker | 6 | 1 | 1 (`snapshot-69`, 8.11 GB) |
| vcf-lab-operations-networks | 6 | 0 | 0 |
| mssqldemo | 3 | 0 | 0 |
| vcf-lab-avi-wld01-node0 | 3 | 1 | 1 (`snapshot-3`, 4.15 GB) |
| infra | 2 | 0 | 0 |

A naive fan-out view lists **every snapshot the VM has ever had**.
On this 50-VM lab that is ~50 ghost rows vs 2 real ones.

**Discriminator (empirical, and vendor-blessed — see Q3):** the instanced
property `…|numberOfDays` is `-1.0` for a ghost and a real age for a live
snapshot. **⚠ Read the snapshot-ageing section below before relying on
this — `-1` also covers live snapshots younger than **24 hours**, so this
discriminator has a one-day blind spot.** Verbatim from the `docker` render — five ghosts and one live
row, same view, same VM:

```json
{"1":"356893:snapshot-13","2":"pre-bridge-rename-20260505-2343","4":-1.0,"5":null,"6":null}
{"1":"356893:snapshot-2", "2":"pre-gitlab-deploy-20260419-0906","4":-1.0,"5":null,"6":null}
{"1":"356893:snapshot-69","2":"CREATED_FOR_SYNOLOGY_ACTIVE_BACKUP_FOR_BUSINESS-172.16.3.51-1-1784102402",
 "4":12.0,"5":8.11210071016103,"6":1784102400000}
```

(col 4 = `numberOfDays`, 5 = `used` GB, 6 = `accessTime` TIMESTAMP.)

**Views have no per-row filter.** `SubjectType filter=` is an
*object-level* predicate — it can drop whole VMs, never individual
fanned-out rows. So an author has two options and must pick one
consciously:

1. **Accept ghost rows**, and sort/colour by Age so live snapshots
   surface (ghost = `-1`, so ascending sort puts them first — prefer a
   descending sort or red/orange bounds keyed off Age).
2. **Object-level filter** the VM set to those with a live snapshot
   (the built-in idiom in Q3), which removes VMs that have only ghosts
   but still shows ghost rows for VMs that do have a live snapshot.

~~There is no view-level mechanism found that filters instances.~~
**FALSIFIED — see the correction section "Per-row filtering: IT EXISTS"
below.** A `SubjectType` filter clause whose `metricKey` carries an
*instance segment* is evaluated per fanned-out row, and does exactly this.
Option 3 therefore exists and is the recommended fix:

3. **Instanced-key `SubjectType` filter** — e.g. properties
   `diskspace:<any>|snapshot:snapshot-<any>|numberOfDays GREATER_THAN 0`.
   Drops ghost rows *and* ghost-only VMs. This is the answer.

Also note: `numberOfDays` was `-1.0` on **every** instance of every VM
scanned except `docker`'s live one — even `vcf-lab-avi-wld01-node0`
whose `snapshot-3` is live with 4.15 GB. So the `-1` marker is
necessary-but-not-sufficient in the other direction too: a live snapshot
can also read `-1` (see the `snapshotAge` semantics note below). Treat
"Age > 0" as high-precision / low-recall.

*(Superseded on devel post-Q4-enablement: `vcf-lab-avi-wld01-node0`'s
live `snapshot-3` now renders Age `11.0`, not `-1`. The prod reading of
`-1` for that instance appears to have been the same collection lag seen
elsewhere, not a semantic. The "high-precision / low-recall" hedge above
is therefore **weaker than first stated** — but still keep it: a
freshly-taken snapshot legitimately reads `-1` until it crosses the
policy age threshold, so Age>0 will always under-report brand-new
snapshots.)*

---

## Snapshot ageing: the gate is **24 HOURS**, not `RECLAIM_SNAPSHOTS_DAYS`

> **⚠ CORRECTION — 2026-07-27.** An earlier version of this section claimed
> the `-1` → real-value flip was gated by the global
> `RECLAIM_SNAPSHOTS_DAYS` (= 7). **That inference was wrong.** The gate is
> **24 hours**, per Brock Peterson's article (allowlisted reference author;
> verbatim extract committed at
> `reference/docs/extracted/brockpeterson-vm-snapshots-aria-operations/article.txt`,
> source URL in its header).
>
> My sampling could not have distinguished them: the observed VMs were
> **0.1 days** (no instances) and **11–12 days** (instances present). The
> entire 1–6 day band — where a 24 h gate and a 7 day gate disagree — was
> **never sampled**. I flagged the claim "strongly indicated, not proven",
> which was right, but I should have named the specific unsampled interval
> that would discriminate rather than leaving it as generic hedging. Every
> observation is equally consistent with 24 h, and 24 h is what the source
> documents.

### What the source says (short quotes, full text in the extract)

> "Properties appear after the VM Snapshot is 24 hours old."
>
> "Snapshot Age property is -1 by default, even if a Snapshot doesn't
> exist. It remains -1 until a Snapshot is 24 hours old, and gets reset to
> -1 once a Snapshot is deleted."
>
> "After the next collection interval, you now have disk related metrics,
> number of snapshots metric, and the age is still -1. After 24 hours the
> rest of the metrics and properties will appear."
>
> "Summary | Reclaimable Snapshot Space (GB) — reclaimable snapshot space,
> this is only calculated once daily…"

That third quote resolves a detail my own observations showed but I had not
explained: **flat** snapshot metrics (`diskspace|snapshot`,
`summary|snapshot_count`) appear at the **next collection interval**, while
the **instanced** per-snapshot metrics/properties and the Age properties
appear only after **24 hours**. Exactly matches prod `ca`/`dcint1`:
`snapshot_count = 1` and flat disk metrics present, **zero** instanced keys,
2.4 h after the snapshot was taken.

It also independently corroborates two things established here empirically:
Creator/Description are off by default and must be activated (Q4), and the
Age property resets to `-1` on deletion (the ghost mechanism, Q1b).

### `RECLAIM_SNAPSHOTS_DAYS` is real, but scoped elsewhere

The setting exists and is genuinely global — it is simply **not** the
ageing gate. It governs the **reclamation / cost** calculations
(`diskspace|snapshot|olderThanXDays`, Reclaimable Snapshot Space, the
reclaim badges), which per the source are computed **once daily**.

Consistency check that the two are separate: `docker` and
`vcf-lab-avi-wld01-node0` carry 11–12 day snapshots and
`olderThanXDays = 1.0` — i.e. one snapshot older than the 7-day reclaim
threshold. That is the reclaim counter doing its job, independent of the
24 h materialisation gate.

### Pending natural experiment (decisive, available 2026-07-28)

Devel and prod both have snapshots created **2026-07-27** (`ca`, `dcint1`,
`vcf-lab-sddcmgr`'s live one) which currently have **zero instanced keys**.
When they cross **24 h** their instanced properties/metrics and a real
`numberOfDays` should appear. If they do → 24 h confirmed live. If they
remain absent until day 7 → the source's 24 h claim does not hold on 9.1
and this needs reopening. **Cheap to run: re-render the view, or re-check
`/api/resources/{id}/properties` for `diskspace:*|snapshot:*` keys.**

### The setting itself (values verified read-only on both instances)

The following is still accurate — only its *interpretation* changed:

```
GET /api/deployment/config/globalsettings/RECLAIM_SNAPSHOTS_DAYS
  -> {"key":"RECLAIM_SNAPSHOTS_DAYS","values":["7"]}
GET /api/deployment/config/globalsettings/RECLAIM_SNAPSHOTS_ENABLED
  -> {"key":"RECLAIM_SNAPSHOTS_ENABLED","values":["true"]}
```

| setting | devel | prod | metadata |
|---|---|---|---|
| `RECLAIM_SNAPSHOTS_DAYS` | **7** | **7** | `INTEGER`, `unit: days`, `defaultValue: 7`, range **1–365** |
| `RECLAIM_SNAPSHOTS_ENABLED` | `true` | `true` | `BOOLEAN`, `defaultValue: true` |

**Both instances are at the stock default.** UI location: Administration →
Global Settings (the reclamation group). Read via
`GET /api/deployment/config/globalsettings` (54 keys on devel, 61 on prod);
per-key metadata via `…/globalsettings/metadata`; writes are
`PUT /api/deployment/config/globalsettings/{key}/{value}` — **not used here.**

### Scope: global, and the alternatives were positively excluded

- **Not per-adapter-instance.** Dumped all **20** `resourceIdentifiers` on
  the vCenter adapter instances (`AUTODISCOVERY`, `CLOUD_TYPE`,
  `ENABLE_ACTIONS`, `GFS_SKIP_PATTERNS`, `VM_LIMIT`, `VCURL`, …) — **no
  snapshot/age/threshold identifier of any kind** on either instance.
- **Not per-policy.** `GET /api/policies/{id}/settings` has no
  reclamation/snapshot value in its `type` enum (only `VC_PRICING_*`,
  `WORKLOAD_AUTOMATION_*`, `CAPACITY_*`, `TIME_REMAINING`,
  `CAPACITY_REMAINING`, `WORKLOAD`), and the exported Default Policy XML
  contains **zero** occurrences of the string "snapshot".

(These exclusions remain valid and are worth keeping: whatever governs
snapshot ageing, it is **not** an adapter-instance setting and **not** a
policy setting. The 24 h gate appears to be hard-coded collector behaviour,
with no exposed knob found on either instance.)

### Live data — consistent with a 24 h gate (prod)

| VM | real age of oldest snapshot | `snapshotAge` | `olderThanXDays` | instanced `numberOfDays` |
|---|---|---|---|---|
| dcint1 | 0.1 d | `-1.0` | `0.0` | (none) |
| ca | 0.1 d | `-1.0` | `0.0` | (none) |
| vcf-lab-sddcmgr | 0.1 d | `-1.0` | `0.0` | **all 13 = `-1.0`** |
| docker | 12.3 d | `12.0` | `1.0` | 5 × `-1.0`, 1 × `12.0` |
| vcf-lab-avi-wld01-node0 | 11.9 d | `11.0` | `1.0` | 2 × `-1.0`, 1 × `11.0` |

The 0.1 d rows are all below **24 h** (and also below 7 d — which is exactly
why this sample cannot discriminate between the two hypotheses); the 11.9 /
12.3 d rows are above both. **The important, sample-independent finding
stands: the instanced `numberOfDays` obeys the same gate as the flat
property.** Only the gate's *value* was misidentified.

### This materially weakens the ghost heuristic — correction to Q1b

`vcf-lab-sddcmgr` has a **live** snapshot taken today and **all 13** of its
instanced `numberOfDays` read `-1.0`. So:

> **`numberOfDays == -1` does NOT mean "ghost". It means "ghost **OR**
> live-but-younger-than 24 hours".**

The two are indistinguishable in the property data. A view column keyed on
Age therefore reads as *"live snapshots at least a day old"*, not *"live
snapshots"*.

**This is much less damaging than the 7-day version of this claim** that
appeared in the earlier draft. A 24 h blind spot on a snapshot-hygiene
report is largely benign — nobody chases a snapshot taken an hour ago. A
7-day blind spot would have been serious. Correcting the gate therefore
*downgrades* this from a significant caveat to a footnote, and the "the
operator most wants to see exactly this population" framing in the earlier
draft was overwrought.

There is also **no tuning lever** for it — the 24 h gate is collector
behaviour, not the `RECLAIM_SNAPSHOTS_DAYS` setting, and no exposed knob was
found. The earlier claim that recall is "systematic and tunable" was wrong
on the second word: systematic yes, tunable no.

---

## Per-row filtering: **IT EXISTS.** Instanced key in the SubjectType filter

> **⚠ CORRECTION — 2026-07-27, later the same day.** Everything in the
> section below this banner was written before the mechanism was found, and
> its headline verdict ("no per-row filter exists — definitive") is
> **FALSIFIED**. It is kept verbatim, not deleted, because the four surveys
> in it are still accurate and still useful — the *surfaces* it checked
> genuinely have no filter. What it missed is that the filter lives inside a
> surface it had already examined and mis-modelled: **`SubjectType filter=`
> is not purely object-level. Put an INSTANCED key in it and the condition
> is evaluated PER FANNED-OUT ROW.**
>
> **Credit: the user found this empirically on 2026-07-27**, by hand-editing
> view `38957c6d` on devel. I had surveyed 1,233 ViewDefs and 446 widgets and
> concluded "definitive" from the absence of a *new* control — the
> methodological error was treating "no new filter surface exists" as
> equivalent to "no filtering is possible", without re-testing the semantics
> of the surface I had already classified. Absence of a mechanism I was
> looking for is not absence of the capability.

### The mechanism

A `<SubjectType filter=…>` clause whose `metricKey` contains an **instance
segment** (`family:<instance>|attribute`) is evaluated **per instance row**
of the view's instanced group, not per subject object. The instance segment
itself is a **generalized placeholder** — exactly like the `sample_instance`
in a column key — so the literal instance named in the filter is irrelevant.

```yaml
subject:
  adapter_kind: VMWARE
  resource_kind: VirtualMachine
  filter:
    - filter_type: properties
      metric_key: "diskspace:90|snapshot:snapshot-7|numberOfDays"   # snapshot-7 exists on NO VM
      condition: NOT_EQUALS
      value: -1
```

renders as

```json
[[{"condition":"NOT_EQUALS","metricKey":"diskspace:90|snapshot:snapshot-7|numberOfDays",
   "metricValue":{"isStringMetric":false,"value":-1},"filterType":"properties"}]]
```

### Characterization matrix (devel, 15 scratch views, all deleted)

Row counts. Unfiltered baselines: docker 6 instances (1 live), avi-node0 3
(1 live), sddcmgr 12 (0 live), `ca`/`dcint1` 0 instances → 1 flat-only
fallback row each.

| variant | filter key / shape | docker | avi | sddcmgr | ca | dcint1 |
|---|---|---|---|---|---|---|
| f12 | *(no filter — baseline)* | 6 | 3 | 12 | 1 | 1 |
| **f01** | **`diskspace:90\|snapshot:snapshot-7\|numberOfDays` != -1** | **1** | **1** | **0** | **0** | **0** |
| f02 | same, instance `356893\|snapshot:snapshot-1` (foreign ds id) | 1 | 1 | 0 | 0 | 0 |
| f03 | same, instance `zzzz\|snapshot:snapshot-999` (garbage) | 1 | 1 | 0 | 0 | 0 |
| f04 | **flat** key `diskspace\|snapshot\|snapshotAge` != -1 | 6 | 3 | 0 | 0 | 0 |
| f05 | wrong family `guestfilesystem:90\|snapshot:snapshot-7\|numberOfDays` | 0 | 0 | 0 | 0 | 0 |
| f06 | f01 without `transform: CURRENT` | 1 | 1 | 0 | 0 | 0 |
| f07 | f01 AND `diskspace\|snapshot` > 0.0001 (metrics) | 1 | 1 | 0 | 0 | 0 |
| f08 | f01 **OR** `diskspace\|snapshot` > 0.0001 (2 groups) | 1 | 1 | 0 | 0 | 0 |
| f09 | `…\|numberOfDays` **GREATER_THAN 0** | 1 | 1 | 0 | 0 | 0 |
| f10 | **metrics** on instanced `…\|used` > 0 | 1 | 1 | 0 | 0 | 0 |
| f11 | f10 with `transform: CURRENT` | 1 | 1 | 0 | 0 | 0 |
| f13 | other real family `net:zzz\|ip_address` != "nope" | 0 | 0 | 0 | 0 | 0 |
| f14 | other real family `virtualDisk:zzz\|label` != "nope" | 0 | 0 | 0 | 0 | 0 |
| f15 | same family, **bogus suffix** `…\|bogusAttr` | 0 | 0 | 0 | 0 | 0 |

Rows surviving f01 are exactly the live snapshots: docker `90:snapshot-69`,
avi-node0 `90:snapshot-3`.

### Answers to the characterization questions

1. **Reproduced.** f01 = 1 live row per snapshot-bearing VM, 0 elsewhere.
2. **The instance segment is a pure placeholder.** f01/f02/f03 are
   byte-different in the instance segment (`90|snapshot:snapshot-7`,
   `356893|snapshot:snapshot-1`, `zzzz|snapshot:snapshot-999`) and produce
   **identical** results. The *family prefix and attribute suffix must be
   real*, though: a wrong family (f05, f13, f14) or a nonexistent suffix
   (f15) yields **0 rows everywhere** — the filter fails closed, it does not
   degrade to "pass". Practical rule: **use the same family prefix as the
   view's instanced group, and a real attribute suffix; put anything you
   like in the instance segment.**
3. **Flat vs instanced is the whole distinction.** f04 uses the flat
   `diskspace|snapshot|snapshotAge` and behaves exactly as the old
   object-level model predicted: docker/avi keep **all** their rows (6/3)
   because the object passes; sddcmgr/ca/dcint1 drop entirely. So both
   semantics coexist in the same field, selected by whether the key carries
   an instance segment.
4. **AND works as expected** (f07 = f01). **OR did NOT widen the row set**
   (f08 = 1, not 6) even though the second group's flat clause is true for
   docker — and the emitted XML confirms two proper groups were rendered.
   Best-fitting model: the outer array is an **object-level** OR (does this
   VM qualify at all), while any instanced clause **additionally** constrains
   which rows render. **Inferred, not proven — do not rely on OR to relax an
   instanced clause.**
5. **It filters rows AND removes objects with no surviving row.** `ca` and
   `dcint1` have zero instances and render one flat-only fallback row
   unfiltered; with the instanced filter they render **0** — the fallback row
   is not exempt. `vcf-lab-sddcmgr` (12 instances, all ghosts) goes 12 → **0**:
   fully absent, exactly as wanted.
6. **Works for metric conditions too** (f10/f11, `filterType: metrics` on the
   instanced `…|used` key) and for `GREATER_THAN` as well as `NOT_EQUALS`
   (f09).
7. **`transform: CURRENT` is not required** (f06 identical to f01). The UI
   adds it; it is inert here.

### Recommended clause for the production view

```yaml
subject:
  adapter_kind: VMWARE
  resource_kind: VirtualMachine
  filter:
    - filter_type: properties
      metric_key: "diskspace:90|snapshot:snapshot-1|numberOfDays"
      condition: GREATER_THAN
      value: 0
```

- `GREATER_THAN 0` over `NOT_EQUALS -1`: both give identical results today
  (f09 = f01), and `> 0` states the intent ("has a real age") without
  depending on `-1` being the only sentinel.
- Instance segment is arbitrary; `snapshot-1` reads less like a magic value
  than `snapshot-7`. Add a YAML comment saying so, or a maintainer will
  eventually "fix" it.
- Keep it a **single AND group**. Do not add an OR group expecting it to
  widen anything (finding 4).
- **This does not repeal the recall caveat.** The filter selects rows where
  `numberOfDays > 0`, and that property is gated by the global
  the **24 h** materialisation gate — so the view shows only snapshots at
  least a day old. The filter fixes the *ghost* problem, not the
  *sub-24 h* problem. The latter is a footnote, not a blocker.
- With this clause the row-set-steering workaround (metric-only members) is
  **no longer needed** — you can keep `name`, `creator`, `description` and
  still get ghost-free rows. That resolves the "ghost-free XOR Snapshot Name"
  trade-off recorded above.

### Portability warning

The instance segment being a placeholder means the filter key's family
prefix (`diskspace`) and suffix must exist on the target, but the datastore
id inside it need not. Verified across two devel VMs and three
instance-segment spellings. **Not** verified on prod, and not verified for
instanced groups other than `GROUP_diskspace`.

**Cross-environment corroboration (2026-07-27).** A third-party edit of this
view came back carrying the instanced clause
`diskspace:2201|snapshot:snapshot-3|numberOfDays` — datastore internal id
**2201**, which exists on **neither** devel (`90`) nor prod (`356893`); it is
an id from the editor's own lab. Re-rendered on devel it behaves identically
to our own clause (1 live row per snapshot-bearing VM, 0 ghosts). So the
placeholder generalises **across environments**, not just across spellings
within one — a foreign lab's datastore id is a perfectly good placeholder.
This is the strongest evidence yet that the segment is inert, and it removes
most of the portability risk flagged above.

### OR-group ordering does not matter (closes an open question)

The same third-party edit used an **OR of two groups** with the *flat*
clause first:

```json
[[{"condition":"GREATER_THAN","transform":"CURRENT","metricKey":"diskspace|snapshot",
   "metricValue":{"isStringMetric":false,"value":0.0001},"businessHours":false,"filterType":"metrics"}],
 [{"condition":"NOT_EQUALS","transform":"CURRENT","metricKey":"diskspace:2201|snapshot:snapshot-3|numberOfDays",
   "metricValue":{"isStringMetric":false,"value":-1},"filterType":"properties"}]]
```

The f08 probe had tested the **reverse** order (instanced group first) and
found the OR did not widen the row set. Re-tested with this order on devel:
**also 1 row, also 0 ghosts.** So group order is irrelevant — an instanced
clause constrains rows from either position, and a flat clause ORed
alongside it does **not** re-admit the rows the instanced clause excluded.

Measured on devel (rows, ghosts in parentheses):

| filter shape | docker | avi-node0 | sddcmgr | ca | dcint1 |
|---|---|---|---|---|---|
| flat-OR-instanced (third-party) | 1 (0g) | 1 (0g) | 0 | 0 | 0 |
| instanced only (ours) | 1 (0g) | 1 (0g) | 0 | 0 | 0 |
| flat AND instanced | 1 (0g) | 1 (0g) | 0 | 0 | 0 |
| instanced only, foreign ds id 2201 | 1 (0g) | 1 (0g) | 0 | 0 | 0 |

**Consequence:** an added flat clause — whether ANDed or ORed — is **inert**
next to an instanced clause on the same family, because the instanced clause
already excludes every object the flat clause would. Keep the single
instanced clause; extra clauses are noise, not defence-in-depth.

---

## ~~Per-row / per-instance filtering: DOES NOT EXIST. Definitive.~~ (SUPERSEDED — see above)

- Date: 2026-07-27 (follow-up; user-blocking design question)
- Instance: devel, installed view `[VCF Content Factory] VM Snapshot
  Inventory` `38957c6d-0f1d-432e-85fb-683272cf3383`, dashboard
  `9c6a3e0a-2c1b-4d7e-9b0a-9f4b6a2e5d13`.
- Question: is there ANY mechanism — view, widget, report, or render
  endpoint — that can drop individual fanned-out rows, e.g. express
  `numberOfDays > 0` on the instanced column?

**Answer: no. Four independent surfaces checked, all negative.**
No devel content was modified; the dashboard widget config was never
touched, so no restore was needed.

### 1. View widget config surface — 0 filter fields (corpus survey)

Scanned **446 `type: "View"` widgets across 138 dashboard JSONs**
(all `reference/references/**` paks). The View widget config surface is a
closed set of **11 keys**, identical in all 446:

```
refreshInterval, resource, traversalSpecId, refreshContent, isUpdatedView,
chartViewItems, selectFirstRow, selfProvider, title, viewDefinitionId
(+ rare: widgetId, description, titleLocalized, viewDetails, viewType)
```

**Not one filter-ish key.** This is not a "we didn't find one" —
it is a *positive* result, because the same survey shows every OTHER
widget type carries filtering:

| widget type | filter keys present |
|---|---|
| ResourceList | `filter`, `customFilter`, `tagFilter`, `filterMode`, `filterTypes` |
| MetricChart | `filter`, `customFilter` |
| Scoreboard | `filter`, `customFilter`, `filterType(s)` |
| ParetoAnalysis | `filter`, `customFilter`, `tagFilter`, `filterMode`, `filterOldMetrics` |
| HealthChart / Heatmap / AlertList / PropertyList / SparklineChart / ResourceRelationship(Advanced) | `filter`, `customFilter`, `tagFilter`, `filterMode` |
| **View** | **none** |

The View widget is the **only** widget type in the corpus with no filter
surface at all. And even the widgets that have one filter *resources*
(`tagPicker`, `resourceKind`, `includedResources`/`excludedResources`),
never rows within a rendered view.

Widget `states[]` (the ExtJS grid-state blob, key
`permTableView_widget_<dash>_<widget>`) was also decoded across 389 View
widgets: it carries **only** `o:id` / `hidden` / `width` per column.
Zero occurrences of `filter` in any decoded blob.

### 2. View definition Controls — 0 filter properties (1,233 ViewDefs)

Parsed every `<ViewDef>` in the live prod `VIEW_DEFINITIONS` export plus
every vendor pak view XML: **1,233 view definitions**. The complete
`<Control type=…>` vocabulary is five types, nothing else:

| Control type | count | purpose |
|---|---|---|
| `time-interval-selector` | 1229 | view-wide time window |
| `attributes-selector` | 1220 | the columns |
| `metadata` | 955 | `maxPointsCount`, `hideObjectNameColumn`, `listTopResultSize` |
| `pagination-control` | 896 | `start`, `size` |
| `buckets-control` | 398 | distribution buckets/colors |

**Property names containing "filter" or "condition" inside any ViewDef:
zero.** The only filter a view can express is the `filter=` attribute on
`<SubjectType>` — and that is an **object selector**, evaluated per
subject resource, structurally incapable of addressing one fanned-out
row.

### 3. Render / report endpoints — no filter parameter

- `GET /internal/views/{id}/data/export` params (both 9.0 and 9.1
  internal specs): `id`, `resourceId`, `traversalSpec`, `page`,
  `pageSize`. That is all. `page`/`pageSize` slice rows positionally;
  they cannot select by value.
- `POST /api/reports` request schema (`report`): `resourceId`,
  `reportDefinitionId`, `traversalSpec`, `subject`, plus metadata.
  No filter field.
- Report `<Section>` children across all 307 sections in the prod
  `REPORT_DEFINITIONS` export: only `ContentType`, `ContentKey`,
  `ContentOrientation`, `ContentFormatting`. No filter.

**Empirically probed** against the live devel view (docker, baseline 6
rows). Every undocumented filter-shaped param was silently ignored:

| param | rows returned |
|---|---|
| *(baseline)* | 6 |
| `filter=[[{"condition":"GREATER_THAN","metricKey":"diskspace\|snapshot\|numberOfDays",…,"filterType":"properties"}]]` | 6 |
| `instanceFilter=numberOfDays>0` | 6 |
| `rowFilter=numberOfDays>0` | 6 |
| `instanceName=90:snapshot-69` | 6 |

All HTTP 200, all 6 rows. No error, no effect.

### 4. Live confirmation of the actual behaviour on devel

Rendering the installed view against the five snapshot-bearing VMs:

| VM | rows | ghosts (Age `-1`) | live |
|---|---|---|---|
| docker | 6 | 5 | 1 (Age 12.0, 8.18 GB) |
| vcf-lab-avi-wld01-node0 | 3 | 2 | 1 (Age 11.0, 4.17 GB) |
| ca | 0 | — | — |
| dcint1 | 0 | — | — |
| vcf-lab-sddcmgr | 0 | — | — |

The view's `SubjectType` filter is doing its job: **ghost-only VMs
(`ca`, `dcint1`, `vcf-lab-sddcmgr`) are excluded entirely.** What
survives is exactly the irreducible case — ghost rows on VMs that *also*
have a live snapshot. That is the residue no available mechanism can
remove.

(Incidental: this render independently re-confirms the Q4 enablement
result — `Creator` = `VSPHERE.LOCAL\Administrator` and the full Synology
ABB `Description` render per-instance on the live row, blank on ghosts.)

---

## Row-set control: the fan-out set IS steerable — **union over member columns**

- Date: 2026-07-27, devel. 13 scratch views synced, rendered, **all deleted**
  (verified: 0 `SCRATCH` views remain; real view `38957c6d` untouched).
- Question: even though per-row *filtering* doesn't exist, can the row SET be
  restricted to metric-bearing (ghost-free) instances?

**Answer: YES — the row set is the UNION, over every member column, of the
instances that currently hold a value for that member's attribute.** It is
not a fixed property of the group. Change the member list, change the rows.

### Variant → row-count table (target `docker`: 6 property instances, 1 live)

| # | members (driver flags) | rows | instances rendered |
|---|---|---|---|
| v1 | `used` + `accessTime` (metrics only) | **1** | live only (`90:snapshot-69`) |
| v2 | metrics + `name` + `creator` + `description` | 6 | union |
| v3 | = v2, `keepInstanceSummary: true` | 7 | union **+ 1 blank-instance aggregate row** |
| v4 | = v2, `showInstanceName: false` | 6 | union; Instance cell degrades to the raw attributeKey string |
| v5 | metrics + `name` (metric-first ordering) | 6 | union |
| v6 | `instanceGroupName: GROUP_vCommunity` (wrong token) | 1 | **degenerate** — single row, every cell `null` |
| v7 | metrics only, `keepInstanceSummary: true` | 2 | live + blank aggregate row |
| v8 | `name` first, then metrics | 6 | union |
| v9 | metrics + `name` declared `is_property: false` | 6 | union — **value still resolves correctly** |
| v10 | v9 + `creator` as `is_property: false` | 6 | union, values resolve |
| v11 | metrics + `creator` + `description` (**no `name`**) | **1** | **live only, WITH descriptive columns** |
| v12 | v11 + `name` | 6 | union |
| v13 | metrics + `numberOfDays` | 6 | union |

Confirmed identically on `vcf-lab-avi-wld01-node0` (3 instances, 1 live):
v1 → 1, v11 → 1, v2/v12/v13 → 3.

### What drives it

- **Ghosts retain the properties collected while they lived; their metrics
  stop.** So a metric member contributes only live instances; a property
  member contributes live + every ghost that ever had that property.
- `name`, `mor`, `numberOfDays` exist on every ghost → **any one of them
  re-introduces the full union** (v5, v8, v12, v13). Column *order* is
  irrelevant (v5 vs v8).
- The `is_property` flag is **display-only, not row-set-affecting**: v9/v10
  declare properties as `is_property: false` and the server still resolves
  the values correctly, and still unions (v9 = 6 rows). So you cannot trick
  the row set with the flag.
- `keepInstanceSummary: true` **adds** a row (blank instance token,
  aggregate) — it never removes one.
- `showInstanceName: false` only degrades the Instance cell to the raw key.
- A wrong `instanceGroupName` doesn't filter, it **breaks** the render
  (v6: one all-`null` row). Confirms the token must match the real family.

### v11 — the tempting answer, and why it is a trap

**v11 gives exactly what the user asked for: one row per live snapshot,
with Creator, Description, Size and Access Time.** Verbatim:

```json
{"1":"90:snapshot-69","2":8.197130312211812,"3":1784102400000,
 "4":"VSPHERE.LOCAL\\Administrator",
 "5":"This snapshot was created by Synology Active Backup for Business. …",
 "objId":"docker"}
```

**Do not ship it as a ghost filter.** It is ghost-free only because
`creator`/`description` were enabled *today* (Q4) — every existing ghost
predates the enablement and therefore has no value for those keys. **Any
snapshot created from now on will carry `creator`/`description`, and when
it is deleted it becomes a ghost that v11 WILL show — permanently.** The
view would silently rot over the coming weeks, which is worse than a known
limitation because it looks correct at ship time.

### The durable recipe (and its cost)

**Metric-only members are the only durable ghost-free row set** (v1):
metrics stop collecting on deletion, so ghosts can never re-enter. Note
this is driven by *current data presence*, not statkey existence — devel
`docker` has instanced metric statkeys for all 6 instances, yet only the
live one renders.

```yaml
columns:
  - display_name: "Instance"          # driver
    instanced_group: {name: GROUP_diskspace, show_instance_name: true,
                      keep_instance_summary: false}
  - display_name: "Snapshot Space (GB)"
    is_property: false
    instanced_group: {name: GROUP_diskspace, prefix: "diskspace",
                      suffix: "used", sample_instance: "<ds>|snapshot:snapshot-1"}
  - display_name: "Created"
    is_property: false
    transformation: TIMESTAMP
    instanced_group: {name: GROUP_diskspace, prefix: "diskspace",
                      suffix: "accessTime", sample_instance: "<ds>|snapshot:snapshot-1"}
```

**Cost: you lose Snapshot Name.** `name` is a property and always unions.
There is no metric-typed equivalent. So the durable choice is:

| want | get |
|---|---|
| ghost-free rows | Instance token, Size, Access Time — **no Snapshot Name** |
| Snapshot Name / Age | ghost rows return (full union) |

The Instance token (`90:snapshot-69`) is the only per-row identifier that
survives in the ghost-free variant. It is the datastore-internal-id +
snapshot slot, not a human name.

### Recall caveat — young snapshots are invisible either way

`ca` and `dcint1` on prod each have a **live snapshot created today** and
**zero instanced keys of any kind** — no properties, no metric statkeys —
2.4 h after creation. `vcf-lab-sddcmgr`'s live snapshot (also today) has 26
instanced metric statkeys but **zero samples in 6 h**; its 13 property
instances are all aged ghosts.

**Strongly indicated (not proven):** a per-snapshot instance is only
materialised once the snapshot is **24 hours** old — **confirmed by the
cited source**, see the snapshot-ageing section
(`reference/docs/extracted/brockpeterson-vm-snapshots-aria-operations/article.txt`).
(An earlier draft here guessed `RECLAIM_SNAPSHOTS_DAYS` = 7; wrong — the
1–6 day band that would have discriminated was never sampled.) The model
explains every observation — sub-24 h live snapshot → flat metrics only, no
instance; aged live → instance with metrics and a real `numberOfDays`;
deleted-after-aging → frozen ghost. **Live confirmation pending
2026-07-28**, when today's snapshots cross 24 h.

Consequence for the user: **no instanced-group view — ghost-free or not —
shows a snapshot taken in the last 24 hours.** A one-day lag, not a
one-week one.

### Verdict and the closest available levers

**SUPERSEDED.** Per-row filtering **does** exist, via an instanced key in
the `SubjectType` filter — see the correction section above. The surveys in
this section remain valid (no *widget*, *report*, or *render-endpoint*
filter exists, and no new view Control type exists); the error was
concluding "impossible" from them.

Row-set control via member column selection (previous section) also still
works, but is **no longer the recommended answer** — the subject filter
gives ghost-free rows *and* keeps the Snapshot Name column.

Non-solutions, ranked by how close they get (all superseded by the
instanced-key subject filter — kept for the record):

0. **Instanced-key `SubjectType` filter** — THE solution, found after this
   list was written. See the correction section above.
1. **Flat-key (object-level) `SubjectType` filter** — already in place;
   removes ghost-only VMs (3 of 5 here). Cannot touch ghost rows on a VM
   with a live snapshot.
2. **Sort by Age descending + `listTopResultSize`** (the `metadata`
   control's top-N, observed with values 50/20/10 in vendor views).
   Pushes ghosts (`-1`) to the bottom and truncates. **Not a filter** —
   N is a fixed constant, not data-dependent, so it either cuts real
   rows or leaves ghosts depending on the fleet. Also note the authored
   view already records that initial sort order is not settable at
   import (the UI import drops it), so this lever is weaker still.
3. **Colour bounds on the Age column** — cosmetic; ghosts stay in the
   list but read as visually distinct. Honest and cheap.
4. **A supermetric or custom group** cannot help: both operate on
   resources, not on instanced-attribute rows.

If the user requires a true active-only list, the row set has to be
built outside the view layer (e.g. an SDK adapter that emits one
resource per live snapshot). That is a Tier 2 conversation, not a view
authoring one.

### Flat `diskspace|snapshot|snapshotAge` semantics

`snapshotAge` (flat, per-VM) is `-1.0` unless the VM's topmost snapshot
is older than the "older than X days" threshold; the companion
`diskspace|snapshot|olderThanXDays` is the count over that threshold.
Observed: `docker` age=12.0 / olderThanXDays=1.0, `vcf-lab-avi-wld01-node0`
age=11.0 / 1.0, `vcf-lab-sddcmgr` age=-1.0 / 0.0 despite having a live
snapshot. So `snapshotAge != -1` means "has a snapshot older than the
threshold", **not** "has a snapshot". This is exactly what the built-in
report filters on.

That threshold is now identified: the deployment-global
a **24 h** materialisation gate (**not** `RECLAIM_SNAPSHOTS_DAYS`, which
is real but scoped to reclamation/cost maths) — see the dedicated section
above. The same gate applies to the **instanced** `…|numberOfDays`, not
just this flat property.

Field-availability caveat: `oldestSnapshotTimestamp` and `olderThanXDays`
are present on **prod** VMs but **absent on devel**, where only
`snapshotAge` appears. Do not build a view column on either without
checking the target instance first.

## Q3 — Built-in report: **does NOT list per-snapshot detail**

`GET /api/reportdefinitions/796c3661-…` exposes no sections. The
definition had to be pulled from a `REPORT_DEFINITIONS` content export
(`reports.zip` → `content.xml`). Verbatim:

```xml
<ReportDef id="796c3661-522a-4439-8f2f-6b7dfe4b5b95">
  <Title>Optimization Report - Virtual Machines with Snapshot</Title>
  <SubjectType adapterKind="VMWARE" resourceKind="VirtualMachine" type="self"
    filter='[[{"filterType":"metrics","metricKey":"diskspace|snapshot","condition":"GREATER_THAN","metricValue":{"value":0.0001,"isStringMetric":false}}]]'/>
  <Sections><Section>
    <ContentType>View</ContentType>
    <ContentKey>ccc97ab1-5d80-4413-a9e1-e94c167bc01d</ContentKey>
    <ContentOrientation>Landscape</ContentOrientation>
  </Section></Sections>
  <Settings><OutputFormat>csv</OutputFormat><OutputFormat>pdf</OutputFormat></Settings>
</ReportDef>
```

The embedded view `ccc97ab1-5d80-4413-a9e1-e94c167bc01d`
("Virtual Machines with Snapshot") is a plain per-VM list — **no
instanced-group driver, no per-snapshot columns**:

| # | attributeKey | isProperty | display |
|---|---|---|---|
| 0 | `diskspace\|snapshot` | false | Snapshot Space (GB), `preferredUnitId=gb` |
| 1 | `diskspace\|snapshot\|snapshotAge` | true | Snapshot Age (Days) |
| 2 | `summary\|parentCluster` | true | Parent Cluster |
| 3 | `summary\|parentVcenter` | true | Parent vCenter |

plus a `summaryInfos` SUM Total row over indexes 0/2/3.

Its `SubjectType filter` is the **vendor-blessed "has a live, aged
snapshot" predicate** — worth copying verbatim:

```json
[[{"condition":"GREATER_THAN","metricKey":"diskspace|snapshot",
   "metricValue":{"isStringMetric":false,"value":1.0E-4},"filterType":"metrics"},
  {"condition":"NOT_EQUALS","metricKey":"diskspace|snapshot|snapshotAge",
   "metricValue":{"isStringMetric":false,"value":-1},"filterType":"properties"}]]
```

Note the second clause uses `"filterType":"properties"` with the key
still in the `metricKey` field — that is the wire shape for a
property-typed subject filter.

Rendered against `docker` it produced exactly one row (Space 8.112 GB,
Age 12.0, cluster, vCenter) plus a Total row; against `mssqldemo` and
`infra` (ghosts only) it produced **only** the Total row — the filter
works.

**Verdict: authoring a new view is justified.** The built-in gives
per-VM aggregate only; Snapshot Name / MOR / per-snapshot Age / per-
snapshot Size are absent.

## Q4 — Creator / Description enablement: **policy attribute enablement** — RESOLVED same day

Not an adapter advanced setting. Evidence:

`GET /api/adapterkinds/VMWARE/resourcekinds/VirtualMachine/properties?properties=…`

```json
{"resourceTypeAttributes":[
 {"key":"diskspace|snapshot|description","name":"Disk Space|Snapshot|Description",
  "defaultMonitored":false,"instanceType":"INSTANCED","dataType":"STRING","property":true},
 {"key":"diskspace|snapshot|creator","name":"Disk Space|Snapshot|Creator",
  "defaultMonitored":false,"instanceType":"INSTANCED","dataType":"STRING","property":true},
 {"key":"diskspace|snapshot|name","name":"Disk Space|Snapshot|Name",
  "defaultMonitored":true,"instanceType":"INSTANCED","dataType":"STRING","property":true}]}
```

`defaultMonitored:false` on creator/description vs `true` on name —
matching the vendor doc (`reference/docs/vcf9/metrics-properties.md:11412`,
Table 1379 "Properties Collected for Disk Space Objects": *"This property
is disabled by default."*). The three vCenter adapter instances carry no
snapshot-related `resourceIdentifiers` (scanned all; only
`VM_FOLDER_DISABLED` matched the SNAP/DAY/OLD probe), so there is **no
adapter-side toggle**.

**Enablement path = Default Policy → Metrics and Properties → VMWARE /
Virtual Machine → `Disk Space|Snapshot|Creator` → State: Enabled.**
Wire equivalent (what the factory's own
`enable_builtin_metrics_on_default_policy` does): inject into the
exported policy XML under `<PackageSettings>`:

```xml
<Metrics adapterKind="VMWARE" resourceKind="VirtualMachine">
  <Metric enabled="true" id="diskspace|snapshot|creator"/>
</Metrics>
```

The prod Default Policy's existing block, verbatim, shows the shape —
including an extra knob relevant to instanced attributes:

```xml
<Metrics adapterKind="VMWARE" resourceKind="VirtualMachine">
  <Metric enabled="true" id="net|packetspersec" instEnabled="false">
    <InstancedGroupNameCondition condOperator="NONE" instGroupIndex="0"/>
  </Metric>
</Metrics>
```

### RESOLVED 2026-07-27 (devel install close-out) — `instEnabled` is NOT required

The open question above ("does an `instanceType: INSTANCED` property
also need `instEnabled="true"`?") was **answered empirically the same
day** by `content-installer` on devel, and the answer is **no**.

- `enable_builtin_metrics_on_default_policy()` was run for
  `diskspace|snapshot|creator` and `diskspace|snapshot|description`
  against devel's Default Policy. The wire it emits is **only**
  `<Metric enabled="true" id="diskspace|snapshot|creator"/>` — it does
  not set `instEnabled` at all, and does not emit an
  `<InstancedGroupNameCondition>` child.
- **Instanced values populated within one collection cycle**, per
  snapshot instance, on two snapshot-bearing VMs:
  - `docker` — creator `VSPHERE.LOCAL\Administrator`, description
    carrying the Synology Active Backup for Business text.
  - `vcf-lab-avi-wld01-node0` — creator `INT.SENTANIA.NET\navani`.
- One VM (`ca`) had not populated at the same check. Treat as
  **propagation lag, not a contradiction** — enablement takes effect on
  the next collection cycle per resource, so a single-cycle sample can
  show a straggler. Re-check a cycle later before concluding anything
  is wrong.

**Practical rule:** enabling a `defaultMonitored:false` INSTANCED
property is a plain policy attribute enable. `enabled="true"` alone is
sufficient; the `instEnabled="false"` seen on the prod Default Policy's
`net|packetspersec` entry is a *separate, narrower* knob (suppressing
instances of an otherwise-enabled metric) and is not part of the enable
path. The factory's existing
`enable_builtin_metrics_on_default_policy()` needs **no change** to turn
these on.

**Consequence for the Active VM Snapshot Inventory view:** Creator and
Description are now viable columns — they are ordinary instanced
properties and will fan out per snapshot exactly like `name`/`mor`
(Q1/Q2). They remain **empty on prod**, where the enable has not been
performed; prod enablement is still a separate operator-approved action.
An author shipping these columns must state which instances have been
enabled, or the columns render blank with no error.

Attribution: devel install close-out, 2026-07-27 (`content-installer`).
Not re-verified by api-explorer against prod; **no prod policy change
was made by this investigation.**

Note also: `GET /api/policies/export` returns **HTTP 500 unless you send
`Accept: application/zip`** (the session default `Accept: application/json`
500s). The factory client already does this; a hand-rolled probe will not.
(Related but distinct from FB-010's `GET /api/policies/{id}` 500.)
`GET /internal/policies/export` 500s regardless.
`GET /api/policies/{id}/settings` has no attribute-enablement `type`
enum value, so per-attribute state is only reachable via the policy
XML export.

---

## Author checklist for the Active VM Snapshot Inventory view

1. Subject `VMWARE:VirtualMachine`. Copy the built-in's two-clause
   `SubjectType filter` (metrics `diskspace|snapshot > 0.0001` AND
   properties `diskspace|snapshot|snapshotAge != -1`) to drop VMs with
   no live aged snapshot.
2. One `instanced_group` driver column (`name: GROUP_diskspace`,
   `keep_instance_summary: false`) — **required**, or no fan-out happens.
3. Member columns, all with `prefix: "diskspace"` and a
   `sample_instance` of the form `"<dsInternalId>|snapshot:snapshot-<n>"`:
   `name` (property/string), `numberOfDays` (property/numeric),
   optionally `mor` (property/string), `used` (metric, `unit: gb`),
   `accessTime` (metric, `transformation: TIMESTAMP`).
   *(The `preferredUnitId` gap flagged in the first draft of this file
   — `_xml_instanced_group_item()` ignoring `col.unit` — was closed the
   same day by `tooling`; see `src/vcfops_dashboards/render.py` and
   `knowledge/context/reviews/framework/dashboards-render-preferred-unit-instanced-2026-07-27.md`.)*
4. Flat property columns for context: `summary|parentCluster`,
   `summary|parentVcenter`, `summary|datastore`, `summary|parentHost`.
   These repeat per fanned-out row — expected.
5. **Ghost rows: filter them out** with an instanced-key `SubjectType`
   filter (`diskspace:<any>|snapshot:snapshot-<any>|numberOfDays`
   `GREATER_THAN 0`) — see the correction section. Still tell the user the
   other half: that same property only materialises once a snapshot is
   **24 h** old, so the view shows *snapshots at least a day old*, not
   *all live snapshots*. The filter fixes ghosts; the 24 h lag is a
   footnote, not a blocker.
6. Creator / Description: **viable as of the Q4 resolution** — they are
   ordinary instanced properties (`prefix: "diskspace"`, suffix
   `creator` / `description`, `is_property: true`,
   `is_string_attribute: true`) and fan out per snapshot like `name`.
   Enabled on **devel** (2026-07-27); **not enabled on prod** — on prod
   they render blank with no error. Either omit them for a prod-targeted
   view or state the enablement prerequisite explicitly.
7. Keep `description:` **at or under 1024 characters** or the view will
   fail to import with an empty `errorMessages` list — see the
   server-side limit section below.

## Server-side limit: view description >1024 chars imports silently FAILED

Discovered 2026-07-27 during the devel install close-out for this same
work stream (`content-installer` bisect, VCF Ops 9.1 devel). Recorded
here because it bit *this* view, and in full in
`knowledge/context/known_limitations.md` §14 and
`knowledge/context/wire-formats/view_column_wire_format.md`
§"View-level field limits".

`VIEW_DEFINITIONS` content-zip import fails when the view
`<Description>` exceeds **1024 characters**, and the failure is
**silent**:

| description length | result |
|---|---|
| 1024 chars | `state=FINISHED`, `imported=1`, `skipped=0` |
| 1025 chars | `state=FAILED`, `imported=0`, `skipped=1`, `errorMessages` **empty** |

Non-transient. The envelope is indistinguishable from a generic import
failure, so **treat "view import FAILED with zero errorMessages" as a
description-length problem until proven otherwise.** The loader does not
enforce the limit today — flagged for `tooling` as a validate-time check
(api-explorer does not edit `src/vcfops_*/`).

Only `VIEW_DEFINITIONS`/`description` was bisected: dashboards, reports,
symptoms, alerts, and view `Title` are **untested**, as is byte-vs-char
counting (the bisect used ASCII).

## Cross-references

- `knowledge/context/known_limitations.md` §14 — the 1024-char view description trap.
- `knowledge/context/api-surface/view_render_internal_endpoint.md` — the render recipe used here.
- `knowledge/context/wire-formats/view_column_wire_format.md` §Instanced-group columns — YAML/XML shape.
- `knowledge/context/investigations/recon_log.md` §2026-07-27 — the recon that raised these questions.
