# MPB relationships — design-level wiring patterns

When you design a management pack, the hardest structural decisions are
about edges: which object type is a child of what, which edges should be
implicit, and which should be explicit. This file is the design-level
cheat-sheet for those decisions.

**Companion docs.**
- [`management_pack_authoring.md`](management_pack_authoring.md) — YAML
  field reference for `relationships:` and `metricSets:`.
- [`mpb_chaining_wire_format.md`](mpb_chaining_wire_format.md) — wire-level
  design-export format for chained requests. Read when the question is
  "what does MPB actually serialize?".
- `docs/reference-mpb-research.md` — MPB JSON schema reference.

**Evidence base** (as of 2026-04-21): hand-built MPBs from Scott (Synology
v1, v2), community packs (Unifi, GitLab-Basic, Brock's Rubrik), and the
framework's own rendered designs. Every pattern below is grounded in at
least one live example.

---

## 1. The four ways a child can be attached to a parent

MPB supports four mechanisms for wiring a relationship. They are NOT
interchangeable — each models a different kind of real-world coupling.

| # | Mechanism | When | YAML surface |
|---|---|---|---|
| 1 | **Implicit adapter-instance parentage** | Every object inherits a parent edge from the adapter instance automatically. No YAML. | n/a — happens at render/install |
| 2 | **Chained metricSet** | Parent request returns a list of items; child request needs per-item parameter substitution to fetch enrichment. | `metricSets[].chained_from` + `bind[]` |
| 3 | **Explicit `field_match` relationship** | Two already-discovered objects (each discovered from their own request) share a common value that joins them. | `relationships[]` with `parent_expression` + `child_expression` |
| 4 | **Explicit `adapter_instance` relationship** | Rare. Forces a trivial edge the renderer will synthesize. Used when the implicit parentage isn't enough for your UI story. | `relationships[]` with `scope: adapter_instance` |

### Mechanism 1: Implicit adapter-instance parentage

Every MPB-collected object is automatically a child of the adapter
instance. You do nothing. The UI shows every object under the adapter
instance by default — at the top of the Ops inventory tree, a user
clicking the adapter instance sees everything this MP collected.

**Don't duplicate this with an explicit relationship.** If all you want is
"this object shows up under the adapter instance", the implicit edge
already does it. Writing `scope: adapter_instance` on top is
almost-always a modeling mistake and will either be rejected at render
time or produce visible duplication.

### Mechanism 2: Chained metricSet (per-row fan-out)

Use when:

- A parent request returns a list (say, `data.volumes[]`).
- A child request is needed per-row to fetch enrichment (say,
  `SYNO.Core.System.Utilization?location=<volume_id>`).
- The enrichment values belong on the SAME object instance as the parent
  row (utilization IO on the Volume object, not on some separate
  "VolumeUtilization" object).

Chained metricSets are **per-object enrichment**, not relationship
declarations. The object has two metricSets — one primary (list
membership), one chained (per-row enrichment) — and metrics drawn from
either end up on the same Volume.

```yaml
- name: "Volume"
  metricSets:
    - from_request: get_volumes    # PRIMARY
      primary: true
      list_path: "volumes"        # bare array name; no trailing .*
    - from_request: volume_util    # CHAINED per row
      chained_from: get_volumes
      bind:
        - {name: volume_id, from_attribute: id}
```

Do NOT reach for a chained metricSet to express "Pool contains Volume" —
that's a parent/child **object** relationship (Mechanism 3), not a
parent/child **request** enrichment.

### Mechanism 3: Explicit `field_match` relationship (the normal case)

Use when:

- Both objects are already discovered from their own primary metricSets.
- A field on the child's record carries the parent's identifier value
  (e.g., `volume.pool_path` equals `pool.id`).

```yaml
relationships:
  - parent: storage_pool
    child: volume
    scope: field_match
    parent_expression: id          # pool's "id" metric
    child_expression: pool_path    # volume's "pool_path" metric
```

MPB's collector computes the join at each collection cycle: every volume
whose `pool_path` value equals some pool's `id` value becomes that pool's
child. No per-row HTTP fan-out is needed — the data is already present
on both responses.

**This is the dominant mechanism for real trees.** Pool→Volume,
Volume→LUN, Pool→Disk, SSDCache→Disk — every peer-to-peer edge in the
Synology design is a `field_match` relationship.

### Mechanism 4: Explicit `adapter_instance` relationship (rarely needed)

Forces a trivial edge where the child object is explicitly declared as a
child of the adapter instance. The renderer synthesizes the wire-level
predicate. Because Mechanism 1 (implicit parentage) already covers this
in most cases, use Mechanism 4 only when an integration test or UI story
requires the edge to be rendered explicitly (debug scenarios, diagnostic
MPs, etc.). Don't declare expressions on it — the loader rejects that.

---

## 2. Dual-parent display — when it's normal, when it's ugly

A child object can have multiple parents. MPB supports this
transparently — the UI shows the child under each parent's tree view.
This is a feature, not a bug, **most** of the time.

### 2.1 Peer-level dual-parent: USE FREELY

**Example.** Disk is a child of both `Storage Pool` (data pool membership)
and `SSDCache` (cache pool membership). One sata disk belongs to a pool;
one nvme disk belongs to an SSD cache. A node showing the disk appears
under whichever of those parents is relevant — different navigation
contexts for the same disk.

This is the **same pattern VMs have in vSphere content**: a VM appears
under both its ESXi Host and its Resource Pool. VCF Ops users understand
this visualization natively.

Peer-level dual-parents are **useful** because they provide different
navigation angles:

- "Show me all disks as a flat list" (via an adapter-instance root view)
- "Show me the disks *in this pool*" (via the Pool tree)
- "Show me the disks *in this cache*" (via the SSDCache tree)

**Rule of thumb:** every meaningful dependency edge is worth modeling.
Don't elide a `field_match` relationship to "keep the tree simple" —
you lose navigation the user will actually want.

### 2.2 Root-level same-name dual-parent: AVOID

**Example (what not to do).** If the world object's display name is
similar to the adapter instance's display name (e.g., both show as
"storage"), then explicitly wiring children under the world object
causes the UI to render the child twice under two apparently-identical
roots. This is the "ugly duplication" failure mode.

**The fix** — the **sidecar pattern** — see §3 below.

### 2.3 Decision rule

When you're about to add a dual-parent edge, ask:

| Are both parents at the root level (adapter instance or world)? | Do they display with the same or similar name? | Verdict |
|---|---|---|
| No (one is a peer object, not the root) | n/a | **FINE — use freely.** |
| Yes | No (parents have meaningfully different names) | **FINE — it's a legitimate dual-root context.** |
| Yes | Yes | **AVOID — use the sidecar pattern instead.** |

---

## 3. The sidecar pattern (root-device metrics that can't live on adapter instance)

### 3.1 Why you need it

The adapter instance is collected automatically and holds connection
config + built-in Ops telemetry. MPB does NOT support custom
`metricSets:` at `source.source` level — you cannot attach custom
metrics directly to the adapter instance.

So if your target API exposes rich **root-device** metrics (e.g.,
Synology exposes CPU user load, memory usage, temperature, uptime, model,
serial — all values that describe the device as a whole), those metrics
need an object home. That home can't be the adapter instance itself.

### 3.2 The solution

Declare a root-device object (`is_world: true`) as a **sidecar**:

- It carries all root-device metrics (CPU/mem/temp/uptime/model).
- It is parentless in your explicit peer graph (no `relationships:`
  pointing FROM it to children).
- Its children inherit from the adapter instance implicitly (Mechanism 1).
- Its display name is **visually distinct** from the adapter instance
  display name (e.g., `"${model} System Health"` rather than the raw
  hostname) to avoid the §2.2 ugly-duplication failure mode.

```yaml
object_types:
  - name: "Synology Diskstation"        # the sidecar
    key: "diskstation"
    is_world: true
    icon: "media-changer.svg"
    identity:
      tier: system_issued
      source: "metricset:system.serial"
    name_expression:
      parts:
        - literal: "System Health"      # distinct from adapter instance name
    metricSets:
      - {from_request: system,      list_path: ""}
      - {from_request: filestation, list_path: ""}
      - {from_request: utilization, list_path: ""}
    metrics: [ ... CPU/mem/temp/uptime/... ]

relationships: []   # NO edges from diskstation to anything
```

Children objects (Volume, Pool, Disk, etc.) are discovered at peer
level. They parent the adapter instance implicitly. They peer-parent
each other via `field_match` relationships. The sidecar Diskstation sits
parallel to the peer graph, contributing metrics but not hierarchy.

### 3.3 When you DON'T need a sidecar

If the target API exposes **no** interesting root-device metrics (Unifi's
controller exposes very little — most data is per-device), skip the
sidecar entirely. The world object becomes a thin anchor (one metric, one
metricSet) and real data lives on the peers.

**Rule of thumb.** Create a sidecar only when the target API exposes
root-device metrics that are worth modeling. Thin anchors are fine.

---

## 4. Shallow trees beat deep ones

MPB supports arbitrary nesting, but the UX suffers fast. **Target 2-3
levels.**

Good hierarchies (shallow, observed in real MPs):

```
Adapter Instance
├── Storage Pool      ← 1 level
│   └── Volume        ← 2 levels
│       └── LUN       ← 3 levels (edge)
└── Disk
```

Bad hierarchies (deep, hypothetical):

```
Adapter Instance → Chassis → Enclosure → Slot → Disk → Partition → Block
```

Deep trees make dashboards hard (widgets need to pin to a specific
resource kind, usually at the top of a level's subtree) and make the
inventory-tree UX noisy. Reach for peer-level edges before adding depth.

---

## 5. Chained metricSet vs explicit relationship — the common confusion

Both feel like "this request needs the previous one's data". They're not
the same. Decision tree:

```
Does the child data belong on the SAME logical object instance as the parent row?
├── YES → chained metricSet (Mechanism 2)
│         The object has two metricSets; metrics from both live on the same object.
│         Example: Volume's IO counters live on the Volume object, not a separate one.
│
└── NO → the child data is its own object type
         Now: does the child already come out of its own list request?
         ├── YES → explicit field_match relationship (Mechanism 3)
         │         Both already discovered; relationship joins them by shared value.
         │         Example: Pool→Volume — both come from their own list requests.
         │
         └── NO → ONLY use a chained metricSet to CREATE the child
                  object by iterating per-row. This is the Rubrik LIST
                  pattern. Advanced; see mpb_chaining_wire_format.md.
```

---

## 6. Worked example — Synology MP Strategy C

This is the final architecture for `managementpacks/synology_nas.yaml`
(v2), summarized for the relationship perspective.

### 6.1 Object model

```
Adapter Instance (auto by MPB)
│
├── Synology Diskstation (sidecar, is_world: true, NO children edges)
│     └── root-device metrics: CPU, mem, temp, uptime, model, serial
│
└── [peer graph under adapter instance]
    ├── Storage Pool ── field_match id ──→ SSDCache (SSDCache.mountedPool = Pool.id)
    │                   field_match id ──→ Volume   (Volume.pool_path = Pool.pool_path)
    │                   field_match id ──→ Disk     (Disk.used_by     = Pool.id [sata*])
    │
    ├── SSDCache ────── field_match id ──→ Disk     (Disk.used_by     = SSDCache.id [nvme*])
    │
    ├── Volume   ────── field_match id ──→ LUN      (LUN.location     = Volume.vol_path)
    │                   field_match id ──→ Share    (Share.vol_path   = Volume.vol_path)
    │
    ├── Disk   (peer object; dual-parented under Pool OR SSDCache)
    ├── LUN    (peer)
    └── Share  (peer)
```

### 6.2 How each edge is chosen

| Edge | Mechanism | Why |
|---|---|---|
| Everything → Adapter Instance | Implicit (Mechanism 1) | Free; handled by MPB |
| Diskstation sidecar → children | **None** | Avoids root-level same-name duplication with adapter instance. Diskstation is parentless in peer graph. |
| Pool → SSDCache | Explicit `field_match` (Mechanism 3) | Both already collected from their own lists (`storage_load_info`); join by `id` ↔ `mountedPool`. |
| Pool → Volume | Explicit `field_match` | Same — join on `pool_path`. |
| Pool → sata Disk | Explicit `field_match` | Join on `used_by`. |
| SSDCache → nvme Disk | Explicit `field_match` | Join on `used_by`. Peer-level dual-parent for Disk — NORMAL. |
| Volume → LUN | Explicit `field_match` | Join on `vol_path`. |
| Volume → Share | Explicit `field_match` | Join on `vol_path`. |
| Disk (no chained enrichment) | — | All disk data comes from the single `get_disks` list request. |
| Volume IO (chained enrichment) | **Chained metricSet** (Mechanism 2) | Volume needs per-row IO from `volume_util`. Enrichment goes on the same Volume object — not a new object. |

### 6.3 What was learned along the way (2026-04-21)

Two distinct lessons emerged during the Synology v1 debugging:

1. **Peer-level dual-parent is normal.** Early analysis over-applied the
   "avoid dual-parent" rule that came from the root-level Diskstation
   collision. Peer-level dual-parents (Disk under Pool OR SSDCache) are
   the standard Ops model — VMs live under Host and Resource Pool for
   exactly this reason. Build rich peer relationships freely.

2. **Root-level same-name duplication is the *only* bad dual-parent
   case.** The failure mode is "Storage" under "Storage" — two tree
   nodes with identical labels pointing at the same underlying data.
   Solve it via the sidecar pattern (§3), not by trimming real
   relationships.

---

## 7. Cross-object-type chains are NOT supported

v1 caveat: `chained_from` must reference a **sibling** metricSet on the
**same** object type. The loader rejects cross-object-type chains.

Hypothetical we CANNOT do yet: "every Disk row of the Disk object fans
out into one Disk-SMART-detail row of the DiskSMART object". If you need
this, file a TOOLSET GAP — expect design + renderer work.

Current workaround: put the chained enrichment on the same object type
(e.g., make SMART fields part of Disk, not a separate DiskSMART object).
This matches the Rubrik pattern too.

---

## 8. Relationship validation — common errors

| Loader error | Cause | Fix |
|---|---|---|
| `relationship parent 'X' is not a known object type key` | Typo in the parent/child key | Match the `key:` declared under `object_types[]` |
| `relationship cannot be self-referential` | Parent and child are the same object key | Re-model: you probably mean a chained metricSet, not a relationship |
| `scope 'field_match' requires both child_expression and parent_expression` | Missing expressions | Add both, naming the metric keys on each side of the join |
| `scope 'adapter_instance' must not declare child_expression or parent_expression` | Expressions set on an adapter_instance scope | Remove them — the renderer synthesizes the predicate |
| `metricSet 'X' has chained_from 'Y' which is not a sibling metricSet` | Attempting cross-object-type chaining | Restructure — see §7 |
| `cycle detected in metricSet chained_from graph` | Chain points at itself through a ring | Remove the cycle — a metricSet can only chain from a strict ancestor |
| `uses ${chain.Z} but no 'chained_from' is declared` | Chain token in request but metricSet isn't marked as chained | Either add `chained_from:` + `bind:` or drop the `${chain.*}` token |

---

## 9. Design-time checklist

Before handing a design to `mp-author`, confirm:

- [ ] Exactly one `is_world: true` object type is chosen.
- [ ] Sidecar decision made consciously: does the API expose root-device
      metrics worth modeling? If yes, sidecar with visually distinct
      name. If no, thin world anchor.
- [ ] No explicit edges from the sidecar world object to its would-be
      children (let implicit adapter-instance parentage handle them).
- [ ] Every peer-object edge is modeled as `field_match` with real
      metric keys on both sides.
- [ ] Tree depth ≤ 3 levels wherever possible.
- [ ] Chained metricSets only for per-row enrichment on the SAME object.
      No cross-object chains.
- [ ] Dual-parent situations are all peer-level or distinct-name
      root-level. No same-name root-level dual-parents.
