# unifi — switch-port → ESXi host stitch v2 (build 9 redesign)

## Initial prompt

> we need to test the devel install on both devel and prod to make sure the CP fix landed in it

> did the relTIONSHIPS showup?

> check the logs

> Show me the JSON api output from vcenter/operations and unifi that indicate the hosts are not advertising LLDP. i can show you screenshots indicating they are

> what are we missing?
> usw-xg-8-ms# show lldp neighbor
> (CLI output showing te1–te8 = vmnic MACs + full ESXi FQDN sysNames, te9 = UDM uplink)

> if this is a dead end, I guess we do what we gotta do - as long as we can match the right switch + port to the right vmknic

## Vision

- The build ≤8 LLDP cross-link is unfixable as written: on Network App
  10.2.105, `port_table[].lldp_table` does not exist and no controller API
  surface (classic / v2 / Integration) exposes LLDP sysNames. The switch's
  own LLDP daemon sees the ESXi hosts (CLI-proven) but the controller
  filters those neighbors out of every API response.
  Evidence: `knowledge/context/investigations/unifi-lldp-switchport-esxi-2026-07-05.md`.
- Redesign the stitch to match **the right switch + port to the right
  vmnic** — per-NIC accuracy is the user's stated bar, not just per-host.
- **Primary design: vCenter-side join via Suite API.** VCF Ops publishes,
  per HostSystem, `net:vmnic<N>|discoveryProtocol|lldp|systemName` (= UniFi
  switch device name, e.g. `usw-lite-16-nuc`) and `...|portName` (= UniFi
  port resource name, e.g. `Port 14`). These are exact string matches to
  the MP's UniFiSwitch / UniFiSwitchPort resource names. The stitcher
  already queries the Suite API (ForeignResourceResolver), so this inverts
  the join direction with data proven live on DEVEL (all 8 hosts, 16
  vmnic→switch/port pairs).
- **Fallback design (only if primary rejected): UniFi-side MAC/IP join**
  via `stat/sta` wired clients (`mac`, `sw_mac`, `sw_port`). Ops does NOT
  publish vmnic MACs on HostSystem, so the join key would be vmk IPs
  (`net:vmk*|ip_address` ↔ wired-client IP) — more moving parts.
- Constraints carried forward from build 8 (unchanged): additive foreign
  edges only (`parentForeign` → `addRelationships`, never full-set onto
  foreign resources — DEF-002), honest uniqueness flags from the Suite API
  response, crash-the-cycle safety (stitch failure must never cost the
  collect), no fabricated edges.
- DEF-002 remains open; this redesign is the path to its live closing
  evidence (host retains VMWARE children AND gains UniFiSwitchPort child).

---

# Design addendum — build 9: vCenter-side vmnic→port join

*Appended by `mp-designer` 2026-07-05. Targeted redesign of one feature
(the stitch), not a full MP redesign. This is the implementable spec for
`sdk-adapter-author` to cut build 9. The Initial prompt / Vision above are
untouched.*

## 0. What changes in one paragraph

Build ≤8 read LLDP neighbours **off the UniFi controller** (per-port
`port_table[].lldp_table[].lldp_system_name`) and resolved each to a VMWARE
HostSystem by name. On Network App 10.2.105 that table is empty for every port
(investigation, 2026-07-05), so the join matches 0 hosts. Build 9 **inverts the
join**: it enumerates VMWARE HostSystem resources over the Suite API, reads each
host's per-vmnic LLDP properties (published by vCenter/ESXi, live-proven on all 8
DEVEL hosts), and matches `(systemName, portName)` back to the adapter's **own**
UniFiSwitch / UniFiSwitchPort inventory. The edge direction, write verb, foreign
uniqueness handling, and crash-safety are all identical to build 8 — only the
**source of truth for the neighbour pairing** moves from the controller (which
does not have it) to vCenter (which does). No framework change is required; every
call rides plumbing that already exists and is CP-proven by commit `97a9c3f`.

## 1. Suite API calls and how they fit existing plumbing

Two GET shapes, both through `SuiteApiStitcher.get(path)` →
`SuiteApiStitchClient.get()` → `VcfCfAdapter.openPlatformConnection()`. That is
the **BC-mirror transport** (trust-all + ignore-hostname, non-FIPS) with identity
v3 credential resolution (injected per-instance credential first, then
`automationuser.properties`, then `maintenanceuser.properties`). This is exactly
the path the CP fix (`97a9c3f`) hardened, so it works through a Cloud Proxy with
no new transport code and no new endpoint class.

**Call A — enumerate hosts (1 request/cycle).** Reuse the existing
`SuiteApiHostBridge.listResources()` query verbatim:

```
GET /api/resources?adapterKind=VMWARE&resourceKind=HostSystem&pageSize=10000
```

Response `resourceList[]`. Per entry read **both**:
- `identifier` — the VCF Ops **resource UUID** (build 8's bridge ignored this;
  build 9 needs it for Call B). Top-level on each `resourceList[]` element.
- `resourceKey` + `resourceKey.resourceIdentifiers[]` — to build the foreign
  parent `ResourceKey` with **honest uniqueness flags**, using the *exact*
  identifier-parsing loop already in `SuiteApiHostBridge.listResources()`
  (`identifierType.name`, `value`, `identifierType.isPartOfUniqueness` →
  default false on absent/null). See §3.

**Call B — read one host's latest properties (H requests/cycle, H = host count).**

```
GET /api/resources/{identifier}/properties
```

Response `property[]`, each `{ "name": "<statKey>", "value": "<string>" }`. Filter
to the LLDP vmnic keys (§2). On DEVEL H = 8, so a cycle costs **1 + 8 = 9** Suite
API GETs — trivial, all cached-token, all single-401-retry.

**Why not the ForeignResourceResolver index / a bulk POST.** `ForeignResourceResolver`
is a *lookup-by-identifier-value* index; build 9 does the opposite — it
**enumerates** hosts and reads their properties, then matches into the adapter's
own inventory. So the resolver's `findByIdentifier` abstraction is the wrong
shape here. The natural home is a new method on `UniFiStitcher` (§6) that does the
raw enumeration and reuses the identifier-parsing helper. A bulk
`POST /api/resources/properties/latest/query` would collapse Call B to one
request, but the facade only exposes `get()` (GET); adding a `post()` is a
**framework change we do not need** at H=8. If a future target has hundreds of
hosts, raise a TOOLSET GAP for a bulk-properties GET/POST then — not now.

## 2. The vmnic LLDP property keys (live-proven shape)

Per host, vCenter publishes one pair per physical NIC:

```
net:vmnic0|discoveryProtocol|lldp|systemName = usw-lite-16-nuc
net:vmnic0|discoveryProtocol|lldp|portName   = Port 14
net:vmnic1|discoveryProtocol|lldp|systemName = ...
net:vmnic1|discoveryProtocol|lldp|portName   = ...
```

Parsing rules for the author:
- Iterate `property[]`. A key is a **systemName leaf** iff it matches
  `net:vmnic<N>|discoveryProtocol|lldp|systemName`; a **portName leaf** iff it
  matches `net:vmnic<N>|discoveryProtocol|lldp|portName`. Anchor on the literal
  substring `|discoveryProtocol|lldp|` — this deliberately **excludes CDP** hosts
  (`|discoveryProtocol|cdp|...`), whose neighbour naming is different and is out
  of scope for build 9.
- The vmnic token is the segment between `net:` and the first `|` (e.g.
  `vmnic0`). Group the two leaves by that token.
- A vmnic contributes a candidate edge only when **both** `systemName` and
  `portName` are present and non-empty. A vmnic with only one of the two is a
  no-op (debug line, no edge).

## 3. Matching semantics — `(systemName, portName)` → own UniFiSwitchPort

`systemName` equals a UniFi **switch device name** (`dev.name`, e.g.
`usw-lite-16-nuc`); `portName` equals a UniFi **switch-port display name** (the
same string `portDisplayName(port, idx)` produces — `port.name` if set, else
`"Port " + idx`). Build 9 must resolve that pair to the adapter's own
`UniFiSwitchPort` resource key, which is `switchMac + "_" + idx`.

**Build the own-inventory index once per cycle** from the `Snapshot` (the same
`usw` device / `port_table` walk `emitLldpHostCrossLink` already does):

```
key   = normSwitch(dev.name) + " " + normPort(portDisplayName(port, idx))
value = set of portKey  ( switchMac + "_" + idx )
```

Match a vmnic's `(systemName, portName)` by
`normSwitch(systemName) + " " + normPort(portName)`:

- **exactly one** portKey in the set → emit the edge (the happy path; all 16
  DEVEL vmnics).
- **zero** → unmatched; debug line, **no edge** (no fabrication).
- **two or more** → ambiguous; debug line, **no edge** (no fabrication). Counted
  separately in the summary.

**Switch-name ambiguity (duplicate `dev.name`).** Two UniFi switches can share a
display name. Keying the index on the joint `(switch, port)` pair — not switch
alone — means a duplicate name only produces an ambiguous *skip* when the **same
port name also exists on both** switches with that name. In practice the port
name usually disambiguates (host is on `Port 14` of exactly one of them), so the
joint key resolves it correctly and silently. Only a genuine (name, port)
collision is skipped — the honest outcome, since the API gives us nothing to
break the tie. Do **not** emit to all candidates (that fabricates a wrong edge).

**Port-name normalization (`normPort`).** vCenter renders the LLDP port
description TLV the switch advertises; the XG SFP ports come across as `"SFP_ 1"`
(underscore + doubled space) where the UniFi display name is `"SFP 1"`. Normalize
both sides: lowercase → replace `_` with space → collapse runs of whitespace to a
single space → trim. So `"SFP_ 1"` and `"SFP 1"` both fold to `"sfp 1"`, and
`"Port 14"` folds to `"port 14"`. This is narrow on purpose — it must **not**
merge `"Port 1"` and `"Port 11"`. `normSwitch` is the same fold minus the
underscore rule (switch names don't have the SFP quirk); lowercase + collapse +
trim is enough.

**Multi-vmnic (one host ↔ many ports).** Each vmnic is matched and emitted
independently → one `parentForeign(host, portKey)` per matched vmnic. A dual-NIC
host plugged into two ports becomes the foreign parent of **both**
UniFiSwitchPort resources. This *is* the per-vmnic accuracy the user requires. If
two vmnics resolve to the same portKey (shouldn't happen physically), the second
`parentForeign` to the same child is idempotent in `RelationshipBuilder` — one
edge, no dup.

## 4. Edge semantics (unchanged from build 8)

- **Direction / verb:** `rb.parentForeign(host, portKey)` — foreign VMWARE
  `HostSystem` as parent, own `UniFiSwitchPort` as child. `foreignParent=true`
  routes to **additive** `rels.addRelationships` (never full-set
  `setRelationships`) — verified in build-8 review §4 and framework bytecode.
  DEF-002 clobber idiom stays absent.
- **Honest uniqueness flags:** the host `ResourceKey` carries each identifier's
  real `isPartOfUniqueness` read from the Suite API response, default false on
  absent/null — never hardcode true (`knowledge/lessons/cross-mp-foreign-key-uniqueness-flags.md`;
  the synology .18–.21 silent-drop reproducer). Reuse the existing
  `SuiteApiHostBridge` parse loop unchanged; it is already byte-correct per the
  build-8 review.
- **Adapter-scoped additive semantics:** relying on the additive foreign edge
  contract, not on the superseded per-adapter-scoped full-set behaviour
  (`knowledge/lessons/setrelationships-foreign-adapter-scoped.md` — SUPERSEDED banner;
  do **not** reintroduce full-set-onto-foreign). Nothing in build 9 changes the
  write verb, so this constraint survives untouched.
- **Crash-the-cycle safety:** the whole stitch body stays wrapped in
  try/catch → `logWarn`, internal topology returned regardless. Suite API down /
  a bad property payload / an interrupted GET must never throw up the collect
  path. `stitcher == null` → early return (remote collector without resolvable
  Suite API creds).

## 5. Behaviour when the join data is absent

All silent, no fabricated edges, one summary line per cycle at INFO:

```
vmnic→port stitch: <E> edges (<H> hosts, <V> vmnics w/ LLDP, <A> ambiguous, <U> unmatched)
```

- **LLDP off host-side** (ESXi not advertising/receiving LLDP): host has no
  `net:vmnic*|discoveryProtocol|lldp|*` keys → V=0 for that host → no edges. Per
  missing pair logged at **debug** only (no per-cycle WARN spam).
- **Non-VCF / no vCenter in this Ops** (Call A returns empty `resourceList`):
  H=0 → E=0, one INFO summary, done.
- **Suite API unreachable / no creds** (remote collector, `stitcher == null` or
  Call A throws): caught, WARN once, internal UniFi topology still returned.
- **CDP-only hosts:** excluded by the `|lldp|` anchor; counted as unmatched
  vmnics only if they also lack an LLDP pair — effectively invisible, no edge.

## 6. Code deltas for the author (map, not the code)

- **`UniFiAdapter.emitLldpHostCrossLink` (≈1035–1082):** replace body. New flow:
  (a) `stitcher == null` → return; (b) build the own-inventory `(switch,port)`
  index from `Snapshot`; (c) call the new `UniFiStitcher` enumeration (below);
  (d) per host, per vmnic pair, match + `parentForeign`; (e) summary log. Rename
  method → `emitVmnicHostStitch` (and its call site at ≈1018 and the log at
  ≈1020–1022). Update the javadoc (the build-8 NIT about "first neighbour" dies
  with the old body).
- **`UniFiStitcher`:** the `matchHostByName` / `findByIdentifier(VMEntityName)`
  path is **dead** under the inverted join — remove it. Add
  `List<ForeignHost> listHostsWithVmnicLldp()` returning, per host,
  `{ ResourceKey key (honest uniqueness), List<VmnicNeighbour> {vmnic, systemName,
  portName} }`. Internally: Call A (reuse `SuiteApiHostBridge` parse for the key,
  **plus** capture `identifier`), then Call B per host UUID, parse §2. Keep
  `invalidateCache()` semantics (fetch fresh each cycle). The
  `ForeignResourceResolver` field can stay only if still used elsewhere; if not,
  drop it in favour of a direct `SuiteApiHostBridge`-style enumeration — author's
  call, but do not leave an unused resolver wired to a now-unreachable code path.
- **`adapter.yaml` line 5 / `docs/`:** reword "LLDP-based stitching" →
  "vCenter vmnic→port stitching" to keep the description honest. Bump
  `build_number` to 9.

## 7. Dead controller-side LLDP code and the `LLDP|*` describe group

Three artifacts are now orphaned by the source change. Recommendations:

1. **`emitLldpHostCrossLink` controller `lldp_table` walk (≈1049–1066):**
   **REMOVE** — fully replaced by the vmnic join. This is the whole point of
   build 9.

2. **`UniFiStitcher.matchHostByName` + VMEntityName resolve:** **REMOVE** — the
   inverted join never looks a host up by name. Leaving it is a dead public
   method that invites a future caller to reintroduce the broken pattern.

3. **Per-port `LLDP|*` property emission (≈722–728) + describe.xml `LLDP`
   ResourceGroup (213–217: `lldp_system_name`, `lldp_port_id`,
   `lldp_chassis_id`):** the source (`port_table[].lldp_table`) is empty on
   10.2.105, so these three properties are **declared but never populated** today
   — misleading empty attributes in the UI and in every list view.
   **Recommendation: populate-from-new-source (repurpose), don't just remove.**
   Rationale: build 9 already fetches, per matched vmnic, the authoritative
   neighbour identity (real ESXi FQDN as `systemName`, the port as `portName`) —
   strictly *better* data than the controller ever had for these exact fields.
   Hoist the §6 host-property fetch to before per-resource collection, stash a
   `portKey → (systemName, portName)` map, and in `collectSwitchPort` emit
   `LLDP|lldp_system_name = <matched ESXi host name>` and repurpose
   `lldp_port_id = <ESXi vmnic label>`. **Drop `lldp_chassis_id`** from both the
   code and describe.xml — vCenter LLDP properties expose no chassis id, so it can
   never be honestly populated (a kept-but-empty property is exactly the misleading
   declaration we're eliminating). This gives the operator the connected host on
   the port row itself, not only in the dependency graph, from one fetch shared
   with the edge build.
   - *If the author wants to keep build 9 tightly scoped to the edge,* the
     acceptable fallback is **REMOVE** the whole `LLDP` group (code + describe) in
     build 9 and add the repurposed `ConnectedHost|*` group as a fast-follow build
     10. **Do not choose KEEP** — shipping three declared-but-never-populated
     properties is the misleading-metric failure mode the framework forbids.

## 8. Constraints carried forward (checklist for the reviewer)

- Additive foreign edge only (`parentForeign` → `addRelationships`); no full-set
  onto a foreign parent. (DEF-002; `knowledge/lessons/setrelationships-foreign-adapter-scoped.md`.)
- Honest `isPartOfUniqueness` from the Suite API response; default false; never
  hardcode true. (`knowledge/lessons/cross-mp-foreign-key-uniqueness-flags.md`.)
- Stitch wrapped; a stitch fault never costs the collect its own inventory.
- No fabricated edges: zero/ambiguous match → no edge, debug only.
- CP-safe: only `SuiteApiStitcher.get()` / BC-mirror transport / identity-v3
  ambient creds; no new endpoint class, no new transport. (Commit `97a9c3f`.)

## 9. Open questions (decide before/at build 9)

1. **Does `portName` track a *renamed* UniFi port, or only the hardware label?**
   Live evidence proves the default case (`"Port 14"` ↔ default display name). If
   an operator renames a UniFi port, we *expect* the switch to advertise the new
   name in the LLDP port-description TLV (so it still equals `portDisplayName`),
   but this is unverified on 10.2.105. If renamed ports advertise the hardware
   label instead, matching on `portDisplayName` would miss them. **Low risk**
   (edges just don't form for renamed ports; no fabrication), but worth a one-line
   check on DEVEL if any port is custom-named. No design change unless it fails.
2. **`LLDP|*` repurpose vs. remove (§7.3):** recommendation is repurpose, but it
   adds a fetch-hoist + stash to build 9. Orchestrator/user: fold into build 9, or
   ship the edge in 9 and repurpose in 10? Either is honest; **KEEP is not an
   option.**
3. **Remote-collector-only topology (no co-located analytics):** Call A/B inherit
   the exact Suite API reachability envelope build 8 had — if `/api/resources`
   resolves through the CP (as `97a9c3f` established), so does
   `/api/resources/{id}/properties` (same host, same transport). This is **not a
   new risk**, but the first DEVEL/PROD collect after build 9 is the confirmation,
   and it doubles as the DEF-002 live-closure evidence (host keeps its VMWARE
   children AND gains the UniFiSwitchPort child).

## Appendix A — fallback design (documented, not built)

Only if the vCenter-side join is rejected. Join **UniFi-side** off `stat/sta`
(classic wired clients), which the adapter can already reach: each wired client
carries `{mac, sw_mac, sw_port, ip}`. `sw_mac + "_" + sw_port` → own
`UniFiSwitchPort` key directly (no vСenter port name needed). The host binding is
the hard part: **Ops does not publish vmnic MACs on HostSystem**, so the client
`mac` cannot be matched to a host NIC. The only available key is the client `ip`
↔ a host `net:vmk*|ip_address` property — a **vmk-IP** join. Weaknesses vs. the
primary: (a) vmk→vmnic binding depends on NIC teaming, so a vmk IP maps to
*whichever* uplink its traffic currently egresses — **per-vmnic accuracy is not
guaranteed**, which is the user's stated bar; (b) the ESXi hypervisor hosts show
`hostname=null` on UniFi (investigation §stat/sta caveat), so no name shortcut;
(c) more moving parts (two property classes, teaming semantics). Use only as a
last resort; it is a per-host-approximate join, not the per-vmnic-exact one the
primary delivers.

---

# Build 10 amendment — hardware-label alias in the port index

*Appended by orchestrator 2026-07-06 after build 9 devel proof (15/16
edges; DEF-002 closed).*

Open question #1 answered empirically: the switch's LLDP daemon
advertises the **hardware label** (`Port <idx>`), not the UniFi custom
display name. usw-lite-16-nuc port 15 is renamed `Router` in the
controller; vCenter publishes `portName = Port 15`; build 9's
display-name-only index therefore missed that one edge (honest skip).

User-approved fix (their hypothesis, verified against the saved
`stat/device` payload): when building the own-inventory `(switch, port)`
index, register each port under **both** aliases —
`normPort(portDisplayName)` **and** `normPort("Port " + idx)` — same
joint key, same exactly-one/ambiguity-skip discipline. Rationale: covers
current firmware (hardware label) and future firmware that might
advertise the custom label; any alias collision (e.g. a port renamed
"Port 3" colliding with a real Port 3) degrades to the existing
ambiguous-skip, never a fabricated edge. Resource identity (MAC_idx) and
display names are untouched.

---

# Build 11 amendment — conflicted-port property honesty

*Appended by orchestrator 2026-07-06. User-approved
("yes let's do that"). Build 10 (approved, uninstalled) is superseded;
build 11 = build 10 + this.*

Fix the build 9/10 NIT (last-write-wins on `vmnicLldpByPortKey`): when a
second, DIFFERENT host claims a portKey already claimed this cycle, mark
the portKey conflicted — write no `LLDP|lldp_system_name` /
`lldp_port_id` for it, log both claimants at debug, count conflicted
ports in the cycle summary line. Same-host re-claims (alias duplicates,
identical values) stay idempotent and keep writing. Edge emission
discipline is untouched. Converts a cosmetically-wrong property under
contradictory LLDP data into an honest absence plus a diagnostic.

After install proof on DEVEL (expect 16/16 edges), the user will run a
PROD test spin to verify CP stitching — note the PROD instance must be
re-pointed to the UNIFIED_CLOUD_PROXY collector group ("VCF Lab CP
Group 1") for that test to exercise the CP path.
