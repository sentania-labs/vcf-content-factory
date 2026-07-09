# Design Artifact: vCommunity — split ONE unified SDK adapter into THREE

> Splits the existing single `vcfcf_vcommunity` Tier-2 Java SDK adapter
> (`content/sdk-adapters/vcommunity/`) into **three independently-shippable
> SDK adapters**, each its own `sentania-labs` repo per the
> `context/managed_paks.md` model:
>
> - **`vcommunity-vsphere`** — vSphere/vCenter collection (clusters, hosts,
>   VMs, network) over the vCenter connection.
> - **`vcommunity-os`** — Windows guest-OS collection (services, event logs,
>   guest OS info) via vCenter's GuestOperationsManager, on its OWN vCenter
>   connection.
> - **`vcommunity-hardware`** — physical server hardware (BMC / Redfish /
>   IPMI). **DEFERRED / planned** — no hardware reference source exists yet;
>   scoped here as the planned third adapter, not implementable until we have
>   the hardware API/source.
>
> **Status: DESIGN — open questions listed below must be decided before
> authoring starts.** This is the packaging/structure design. It does NOT
> re-derive the object model, key list, or content inventory — those are
> owned by `vcommunity-sdk.md` and `vcommunity-content-port-worklist.md` and
> are referenced, not restated.

## Original Request

Split the unified `vcfcf_vcommunity` Tier-2 SDK pak into three independent
SDK adapters (vsphere / os / hardware), each its own repo. Produce this
design note. Cover surface allocation, connection model, co-push
coexistence (the load-bearing assumption), per-adapter describe/credential/
config, content allocation, repo/release structure, supersession of the
"stay unified" recommendation, and migration path.

## Intent — Scott's rationale (verbatim, prompt-of-record)

> "At enterprise scale there may be a separation of interest between
> HW/OS/vSphere, so it makes sense to separate them so they can mature at
> different cadences and updates to OS don't negatively affect the others,
> and vSphere-only admins don't need to be burdened with extra fields that
> confuse them."

Distilled drivers:

1. **Separation of concerns by team/domain** — HW, OS, and vSphere are often
   owned by different teams at enterprise scale.
2. **Independent release cadence** — each adapter matures and ships on its
   own `v*` tag; an OS change cannot regress vSphere.
3. **Blast-radius isolation** — a guest-ops crash, a Windows-credential
   problem, or a BMC outage is contained to one adapter's collection cycle.
4. **Per-adapter RBAC / UX** — each adapter ships its own `describe.xml`,
   credential dialog, and config surface. A vSphere-only shop installs only
   `vcommunity-vsphere` and never sees Windows creds or OS toggles.

**This decision is made by Scott (product owner). It is not re-litigated
here.** What this note resolves is *how* to execute it safely.

## Supersession (explicit)

This **supersedes** the "stay UNIFIED for v1" recommendation in
`knowledge/designs/managementpacks/vcommunity-parity-plan.md` §"Architecture decision
— single pak vs vSphere/OS split" (lines 72–89). That section recommended a
single pak with internal modules and listed four reasons; this note's intent
section and the co-push verdict below address each:

| Parity-plan objection (line) | Disposition here |
|---|---|
| (1) split = two adapters co-pushing `vCommunity\|` onto one VM; coexistence "unproven, reopens the clobber question" | **Retired by analysis** (co-push verdict below): the Suite API property endpoint is per-key upsert, not whole-resource replace. Disjoint key namespaces between vsphere and os make clobber structurally impossible. One cheap empirical confirmation specified to close it to zero. |
| (2) OS pak can't stand alone — guest-ops rides vCenter's GuestOperationsManager | **Accepted and embraced.** `vcommunity-os` opens its OWN vCenter connection + vim25 client + stitcher (documented duplication below). It is not "standalone of vCenter" — it is standalone of the vSphere *pak*. |
| (3) diverges from "like-for-like" (original is one pak) | **Intentional.** Parity bar restated below: content/metric parity is preserved; *packaging* deliberately diverges from Onur's unified pak. Like-for-like was a content goal, never a packaging contract. |
| (4) optional-OS benefit already exists via the `Windows Monitoring` enum | True, but the enum does not deliver objections (3)/(4) of the *intent*: RBAC/UX isolation and independent release cadence. The split does. The enum survives **inside** `vcommunity-os`. |

**Restated parity bar:** metric-key parity, super-metric/view/dashboard/
report/symptom/alert parity, and `vCommunity|` namespace fidelity against the
prod original remain the bar — verified per `vcommunity-parity-plan.md`'s
iteration loop, now summed across the three paks. **Packaging is the
deliberate divergence:** three paks where Onur shipped one.

## Tier decision

All three adapters remain **Tier 2 (Java SDK)** — the split changes packaging,
not tier. The Tier-2 triggers from `vcommunity-sdk.md` §"Tier decision" (vim25
SOAP transport, in-guest action execution, foreign-resource stitching with no
MPB request model) are unchanged and still fire for vsphere and os.
`vcommunity-hardware` (BMC/Redfish/IPMI) is also Tier 2 (non-HTTP or
vendor-specific transport, foreign-resource stitching) — confirmed when its
API map exists.

---

## 1. Surface allocation

Every `vCommunity|` pushed key from `vcommunity-sdk.md` §"Object Type Details"
is allocated to exactly one adapter. The allocation principle: **the key goes
to the adapter that owns the connection that reads it.**

### `vcommunity-vsphere` — everything read over the vim25 vCenter session

Pushes onto foreign VMWARE `ClusterComputeResource`, `HostSystem`,
`VirtualMachine`. This is the bulk of the surface.

| Source collector (today) | Foreign kind | Keys |
|---|---|---|
| `ClusterCollector` (HA / DRS / EVC / DRS Score) | ClusterComputeResource | all 13 `Cluster Configuration\|*` keys |
| `HostCollector` — Advanced System Settings | HostSystem | `Configuration\|Advanced System Settings\|{key}` |
| `HostCollector` — Packages / VIBs | HostSystem | `Configuration\|Packages:{name}\|*` |
| `HostCollector` — Install Date | HostSystem | `Configuration\|Install Date\|UTC` |
| `HostCollector` — Licensing | HostSystem | `Licensing:{name}\|*` (+ `Remaining Days` metric) |
| `HostCollector` — NIC uplinks | HostSystem | `Network\|Device:{device}\|*` |
| `VmCollector` — config / options / adv params | VirtualMachine | `Options\|*`, `Configuration\|Advanced Parameters\|*` |
| `VmCollector` — SCSI controllers | VirtualMachine | `Configuration\|SCSI Controllers\|*` |
| `VmCollector` — snapshots | VirtualMachine | `Snapshot\|Count` (metric) |
| `VmCollector` — VMware-Tools Guest OS path | VirtualMachine | `Guest OS\|Operating System\|OS *` (the six `OS `-prefixed keys — see allocation note) |

### `vcommunity-os` — everything read through GuestOperationsManager (in-guest)

Pushes onto foreign VMWARE `VirtualMachine` only.

| Source collector (today) | Foreign kind | Keys |
|---|---|---|
| `GuestOpsClient` / `VmCollector` — Windows services | VirtualMachine | `Guest OS\|Services:{name}\|*` |
| `GuestOpsClient` / `VmCollector` — Windows event logs | VirtualMachine | Windows event-log EVENTS (or property-degraded form per TOOLSET GAP #1) |
| `GuestOpsClient` — guest OS info (CSV path) | VirtualMachine | `Guest OS\|Operating System\|OS *` **iff sourced from the in-guest CSV** (see allocation note) |

### `vcommunity-hardware` — DEFERRED (BMC / Redfish / IPMI)

No keys allocatable yet — no hardware reference source, no API map, no
collector. Planned surface (subject to the hardware API map):

- Physical server inventory (chassis, model, serial, service tag).
- Power/thermal sensors, fan/PSU health, BMC firmware version.
- Likely stitches onto VMWARE `HostSystem` (the physical host backing an
  ESXi node) under a `vCommunity|Hardware|*` sub-namespace — to be designed
  when the source exists.

**Blocked on:** an `api-cartographer` map for the target BMC/Redfish API.
Do not author `vcommunity-hardware` until that map exists.

### Load-bearing allocation calls (the "advanced settings / packages / licensing / install-date / uplink" surfaces)

The request flags these explicitly. **All of them are vSphere-side host
config read over the vim25 session, NOT hardware:**

- **ESXi Advanced System Settings** (`configManager.advancedOption`) →
  **vsphere.** It is ESXi software configuration, not BMC.
- **Software Packages / VIBs** (`imageConfigManager.fetchSoftwarePackages`)
  → **vsphere.** ESXi image/VIB inventory, read over vim25.
- **Install Date** (`imageConfigManager.installDate`) → **vsphere.** ESXi
  install date, not hardware manufacture date.
- **Licensing** (`licenseAssignmentManager`) → **vsphere.** vSphere
  licensing, read over vim25.
- **NIC uplinks** (`config.network.pnic[].device / driverVersion /
  firmwareVersion / status`) → **vsphere.** This is the one with a hardware
  *flavor* (driver/firmware versions of physical NICs), but it is read
  **over the vim25 vCenter session** from `HostSystem.config.network.pnic`,
  not from a BMC. **It stays in `vcommunity-vsphere`.** When
  `vcommunity-hardware` exists, *BMC-sourced* NIC firmware (read from
  Redfish, not vim25) would be a **distinct, additional** `vCommunity|
  Hardware|NIC|*` key namespace — it does not move the existing
  vim25-sourced `Network\|Device:*` keys.

**Allocation rule of thumb for the future hardware adapter:** if a key is
read from the vim25 vCenter session it is vsphere; if it is read from a BMC/
Redfish/IPMI endpoint it is hardware. Source-of-truth, not subject-matter.

### OPEN-A — the `Guest OS\|Operating System\|OS *` keys are dual-sourced

This is the one genuinely ambiguous surface and the only key-set the request's
"map every key to exactly one adapter" cannot resolve without a decision.

The six `Guest OS|Operating System|OS *` keys (`OS Name / OS Version /
OS BuildNumber / OS Architecture / OS Last Boot Up Time / OS Release ID`) are
produced by **two different code paths** in today's unified adapter
(confirmed in `recon_log.md`):

1. **VMware-Tools path** (`guest.detailedData`, build-3 FORK, ALIGNed in
   build-4) — read over the **vim25 session**, no in-guest credential, works
   on any Tools-running guest. Lands on dcint1/dcint2 today.
2. **In-guest CSV path** (`getWindowsOSInformation.ps1` via
   GuestOperationsManager) — the original's path, needs the **Windows
   credential**, Windows-only.

Both write the **same six keys**. In the unified pak this is a harmless
internal superset (Tools path fills them; guest-ops path overwrites with
richer data when available). **In a split, the same key is written by two
different adapters** — which makes it the one real co-push overlap (see §3).

**Decision needed (OPEN-A):** which adapter owns the six `OS *` keys?

- **Option A1 (recommended): vsphere owns them via the Tools path; os does
  NOT write them.** The CSV-path OS-info collector is dropped from
  `vcommunity-os` (os keeps only Services + Event Logs). Rationale: the
  Tools path needs no Windows credential, works for all guests (not just
  Windows), and already lands data on devel. A vSphere-only shop still gets
  OS-version inventory — which is reasonable, it is low-sensitivity vim25
  data. Eliminates the only co-push key overlap entirely → §3 becomes
  trivially safe (fully disjoint namespaces).
- **Option A2: os owns them via the CSV path; vsphere drops the Tools-path
  OS keys.** Stricter "all guest-OS data lives in the OS pak" separation, but
  a vSphere-only shop then sees zero OS info, and it reintroduces a real
  co-push overlap risk if both are ever installed (the empirical test in §3
  becomes mandatory, not optional).
- **Option A3: both write them (status quo superset, now cross-adapter).**
  Last-writer-wins per cycle; ordering is non-deterministic across two
  independent collection schedules. **Not recommended** — it is the only
  configuration that can produce visible flapping.

**Recommendation: A1.** It makes the namespaces fully disjoint and is the
cleanest realization of Scott's "vSphere-only admins shouldn't be burdened"
intent (they keep basic OS inventory; deep guest monitoring is the OS pak).

---

## 2. Connection model

### vsphere and os each open their OWN vCenter connection (documented duplication)

Both `vcommunity-vsphere` and `vcommunity-os` are independent adapters with
independent collection cycles. Each:

- Opens its **own** vim25 `SmartConnect` session to the configured vCenter
  (`VCommunityVSphereClient` — copied into both repos).
- Builds its **own** vim25 container views.
- Resolves foreign resources through its **own** `VCommunityStitcher` +
  `SuiteApiStitcher` instance.

This is **deliberate duplication.** `VCommunityVSphereClient.java`,
`VCommunityStitcher.java`, and the `SuiteApiStitcher` usage are forked into
both repos. The duplication cost (two vCenter sessions per cycle if a shop
installs both, two copies of the SOAP client to maintain) is the explicit
price of blast-radius isolation and independent cadence — Scott's intent
accepts it. Documented here so no one "fixes" it later by re-coupling the
paks.

`vcommunity-hardware` uses a **separate BMC connection** (Redfish HTTPS / IPMI
— TBD by its API map). It does not open a vCenter session at all, unless its
stitch target (VMWARE HostSystem) resolution requires the vCenter UUID for
identity (see below).

### Stitching identity must stay consistent across adapters — the MOID trap

**Binding lesson:** `knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`.
Because vsphere and os (and eventually hardware) all push onto the **same**
foreign VMWARE resources, every adapter's stitcher MUST resolve identity the
same way, or two adapters will disagree about which `HostSystem`/`VM` a key
belongs to in a multi-vCenter deployment:

- Each adapter pins its owning vCenter Instance UUID from its **own** live
  SOAP session (`ServiceContent.about.instanceUuid`) every cycle, exactly as
  `VCommunityStitcher` does today (`setOwningVcUuid` →
  `VMEntityVCID`-scoped load).
- The MOID + `VMEntityVCID` join is **identical** across all three repos
  because the stitcher is forked verbatim. This is the safety property: two
  adapters pinned to the same vCenter UUID, matching the same MOID, resolve
  to the **same** VCF Ops resource UUID — so their pushes land on the same
  resource. If one adapter dropped the `VMEntityVCID` scoping, it could
  resolve a same-MOID resource in a *different* vCenter and the two paks
  would push to different resources for "the same" host. **Keep the build-2
  scoping fix in every fork.** Flag this for `sdk-adapter-reviewer` on each
  pak.
- `vcommunity-hardware`: if it stitches onto VMWARE HostSystem, it must
  resolve identity by the **same** MOID+`VMEntityVCID` join — which means it
  needs the vCenter Instance UUID even though its data comes from a BMC. How
  it learns the MOID↔BMC mapping (service tag? IP? BMC inventory cross-ref?)
  is an **open hardware-design question** deferred with the rest of that
  adapter.

---

## 3. Co-push coexistence — THE load-bearing assumption

**Question:** can two adapters (`vcommunity-vsphere` and `vcommunity-os`)
push `vCommunity|` properties onto the **same** foreign VMWARE VM without
clobbering each other's keys?

### VERDICT: PROVEN BY THE FRAMEWORK MECHANISM (per-key upsert), modulo one cheap confirmation.

**Mechanism evidence (read directly from the framework, not inferred):**

`vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/SuiteApiStitchClient.java`:

- `pushProperties` → `rawPost("/api/resources/" + resourceId + "/properties",
  body, tok)` (line 343–352).
- The body (`buildPropertiesJson`, line 555–567) is
  `{"property-content":[{"statKey":<key>,"timestamps":[ts],"values":[val]}, …]}`
  — a **list of the specific keys being written**, each addressed by
  `statKey`.
- `pushStats` is the identical shape against `/stats` with `stat-content`
  (line 369–379, 569–581).

This is the VCF Ops Suite API **time-series property-content** endpoint. It is
an **upsert of the named keys**: it appends/updates the `statKey`s present in
the payload. It does **not** enumerate the resource's existing properties and
it does **not** delete keys absent from the payload. There is no
"replace-all-properties-for-this-resource" semantic anywhere in the push path.
Two adapters posting **different** `statKey`s to the same `resourceId` each
write their own keys; neither's POST references the other's keys, so neither
can remove them.

**This is already how the platform works in production today**, two
independent ways:

1. The **original Python `iSDK_VCFOperationsvCommunity`** pak and **VMware's
   own VMWARE adapter** both write to the same `HostSystem`/`VM` resources
   right now — VMware writes native metrics, the original writes `vCommunity|`
   properties — without clobbering each other. That is two writers on one
   resource, proven in prod.
2. The **compliance adapter** (`vcfcf_compliance`) pushes `compliance|*`
   keys onto VMWARE `HostSystem` while VMWARE writes native keys to the same
   host — healthy with two DATA_RECEIVING instances on devel. Same upsert
   path (`SuiteApiStitchClient`), same non-clobbering behavior.

The split adds a **third** simultaneous writer pattern (vsphere + os, both
under the `vCommunity|` prefix), but the mechanism is identical and the keys
are **disjoint** (vsphere: `Cluster Configuration|*`, `Configuration|*`,
`Licensing:*`, `Network|*`, `Options|*`, `Snapshot|*`; os: `Guest OS|
Services:*` + events). **Disjoint keys + per-key upsert = structurally
impossible to clobber.**

### The one residual risk and the cheap test to retire it

The only way clobber could occur is if both adapters write the **same**
`statKey` to the same resource — which **only happens for the six
`Guest OS|Operating System|OS *` keys** flagged in OPEN-A. **If OPEN-A is
resolved A1** (vsphere owns those keys, os never writes them), the namespaces
are fully disjoint and **no empirical test is needed** — the framework
mechanism proof above is sufficient.

**If OPEN-A is resolved A2 or A3** (any shared key), one empirical
confirmation is required before release:

> **Co-push empirical test (only if a shared key survives OPEN-A):**
> 1. On devel, install both `vcommunity-vsphere` and `vcommunity-os`,
>    each with an instance against the **same** vCenter.
> 2. Let both run ≥3 collection cycles with staggered schedules (e.g.
>    vsphere 5min, os 5min offset).
> 3. On a Windows VM in scope, confirm the VM resource simultaneously
>    carries **both** a vsphere-only key (e.g. `vCommunity|Snapshot|Count`)
>    **and** an os-only key (e.g. `vCommunity|Guest OS|Services:*`), and that
>    neither disappears across cycles.
> 4. For any shared key, confirm it does not flap (it will last-writer-win;
>    document the cadence dependency).
> Sentinel: both key families present on one VM resource UUID across ≥3
> consecutive recons = coexistence proven empirically.

**Recommendation: resolve OPEN-A as A1 → disjoint namespaces → mechanism
proof is sufficient → the empirical test de-escalates to a nice-to-have
smoke check rather than a release gate.** This is the #1 risk and A1 retires
it by construction.

---

## 4. Per-adapter describe.xml / credential / config (the RBAC/UX win)

Each adapter ships its **own** `describe.xml`, credential kinds, and
adapter-instance form. This is where Scott's "vSphere-only admins don't see
Windows fields" intent is delivered concretely.

### `vcommunity-vsphere` — vCenter only, NO Windows fields

| Element | Value |
|---|---|
| Credential kinds | **vCenter Credential only** (`user`, `password`) |
| Instance fields | Name; vCenter Server (`host`); vCenter Credential ref; port (443) |
| Advanced (config-file NAMEs) | `esxi_adv_settings_config_file`, `esxi_vib_driver_config_file`, `vm_adv_settings_config_file`, `vm_configuration_config_file` (the four **vSphere-side** check-list files) |
| **Absent** | No Windows credential. No `Windows Monitoring` enum. No `win_service_config_file` / `win_event_config_file`. |

A vSphere-only shop installs this and the credential dialog shows **only**
vCenter user/password. Goal met.

### `vcommunity-os` — vCenter credential + Windows credential + the Windows enum

| Element | Value |
|---|---|
| Credential kinds | **vCenter Credential** (required — guest-ops rides the vCenter session) **+ Windows Guest Credential** (`winUser`, `winPass`) |
| Instance fields | Name; vCenter Server (`host`); vCenter Credential ref; Windows Guest Credential ref; **Windows Monitoring** enum (`Disabled` \| `Services` \| `Event Logs` \| `Services + Event Logs`, default `Disabled`); port |
| Advanced (config-file NAMEs) | `win_service_config_file`, `win_event_config_file` (the two **Windows** check-list files) |
| **Absent** | No ESXi/VM advanced-settings config files (those are vSphere's). |

Note `vcommunity-os` **still needs a vCenter credential** — guest-ops runs
*through* vCenter's GuestOperationsManager. That is not a leak of vSphere
concerns into the OS pak; it is the OS pak's own (separate) vCenter
connection. The two credentials have distinct trust boundaries (vCenter SSO
account vs Windows domain/local account), which is exactly why the OS team
owning this pak wants them isolated from the vSphere pak.

### `vcommunity-hardware` — BMC credential (DEFERRED)

| Element | Value |
|---|---|
| Credential kinds | **BMC Credential** (Redfish/IPMI user + password) — TBD by API map |
| Instance fields | Name; BMC endpoint(s) / discovery scope; BMC Credential ref — TBD |
| **Absent** | No vCenter credential *for collection* (may still need vCenter UUID for stitch identity — see §2 open item). No Windows credential. |

**RBAC/UX win summary:** three install footprints. vSphere team installs
vsphere (sees vCenter creds only). OS/Windows team installs os (sees vCenter
+ Windows creds + the OS enum). HW team installs hardware (sees BMC creds).
No team is burdened with another team's fields. Each can be granted to a
different VCF Ops admin role.

### Config-file central-store model is preserved, split by surface

The central-config-store fetch model from `vcommunity-sdk.md` §"Config design"
(OPEN-4 RESOLVED) is unchanged in mechanism; the **six files split four-to-two
across the two paks**:

- **vsphere ships + fetches four:** `esxi_advanced_system_settings.xml`,
  `esxi_packages.xml`, `vm_advanced_parameters.xml`, `vm_options.xml`.
- **os ships + fetches two:** `windows_service_list.xml`,
  `windows_event_list.xml`.

Each pak imports only its own files into the `SolutionConfig/` central store
at install and fetches only its own by name each cycle via the framework
Suite API channel. No shared file, no cross-pak config dependency. (If both
paks are installed they import disjoint files into the same central
`SolutionConfig/` path — fine, names don't collide.)

---

## 5. Content allocation (super metrics / views / dashboards / symptoms / alerts / reports)

Source inventory is owned by `vcommunity-content-port-worklist.md` (37 SMs,
16 views, 16 reports, 2 symptoms, 3 alerts, 13 dashboards). Allocation
principle: **content ships with the adapter whose keys/metrics it reads.**
Content reading only native VMWARE metrics (no `vCommunity|` keys) is
vSphere-aligned by default (it is the vSphere-domain pak).

### Clean allocations

**`vcommunity-vsphere` (the large majority):**

- **All 37 super metrics.** Every SM in the worklist reads native VMWARE
  metrics or other vCommunity SMs on Cluster/Host/VM/DVS/World/Container
  kinds — **none read a `Guest OS|Services` key.** SMs are vSphere-domain.
- **Symptoms:** `ESXi Host NIC Disconnected` (reads `vCommunity|Network|
  Device:*` — a vsphere key).
- **Alerts:** `ESXi Host NIC Disconnected`; `ESXi Host License Expiring`
  (reads `vCommunity|Licensing:*|Remaining Days` — a vsphere key).
- **Views (vSphere-keyed or native):** ESXi Host Details / Hardware Models /
  License Information / Maintenance State / NIC Details / Power State /
  Versions, ESXi Packages, VM Details, nfnic VIB Vendor Distribution, and all
  5 SM-consuming views — **13 of 16 views.**
- **Reports:** all 16 `Report - VOA - *` (they embed vSphere dashboards/views;
  none embed a Windows-services view).
- **Dashboards:** 11 of 13 (Cluster Performance 2.0, ESXi Configuration 2.0,
  ESXi Host Details, VM Capacity 2.0, VM Details, VM Performance 2.0, VM
  Storage Configuration, vSphere Cluster Capacity 2.0, vSphere Cluster
  Configuration 2.0, vSphere Network Configuration 2.0, vSphere Resource
  Management).

**`vcommunity-os`:**

- **Symptoms:** `Windows Service Down` (reads `vCommunity|Guest OS|Services:*`
  — an os key).
- **Alerts:** `Windows Service Down`.
- **Views:** `Windows Services vCommunity` (1 view — reads `Guest OS|
  Services:*`).
- **Dashboards:** none cleanly OS-only. (See mixed below.)

### Mixed-surface content — the cross-adapter problem

One dashboard mixes surfaces and needs a decision:

- **`Critical Business Applications`** — embeds Business-App performance SMs
  (vSphere/Container) **and** an "OS Services" view (Windows/os surface). It
  spans both paks.

**OPEN-B — how to handle mixed-surface content.** Options:

- **Option B1 (recommended): ship mixed content with the dominant pak; the
  cross-surface widget degrades gracefully when the other pak is absent.**
  `Critical Business Applications` ships in `vcommunity-vsphere` (its
  dominant surface is Business-App performance); its embedded OS-Services
  view shows "no data" when `vcommunity-os` isn't installed — which is the
  normal VCF Ops behavior for a view over keys no adapter emits. No hard
  dependency, no install-order constraint. Matches Scott's intent (vSphere
  shop sees the dashboard, just without the OS widget populated).
- **Option B2: split the dashboard — a vSphere-only variant in vsphere and a
  fuller variant in os.** Higher fidelity per-install but doubles a dashboard
  and diverges from the original's single artifact (parity cost).
- **Option B3: a fourth "vcommunity-content" bundle** holding cross-surface
  content. Rejected — reintroduces a coupling the split exists to remove, and
  there is only one mixed artifact.

**Recommendation: B1.** One mixed dashboard does not justify B2/B3 machinery;
graceful "no data" degradation is idiomatic VCF Ops. Document in the dashboard
description that the OS-Services section requires `vcommunity-os`.

A second watch item: the **`Windows Services vCommunity` view** is referenced
by the `Critical Business Applications` dashboard (vsphere) but reads an os
key. Under B1, ship the *view* in vsphere too (so the dashboard's embed
resolves at author time), and let it show no data without the os pak. The os
pak can also ship its own copy for standalone use, OR rely on the vsphere
copy — **OPEN-B1 sub-question:** do we duplicate the `Windows Services` view
across both paks, or ship it once in vsphere? Recommend **ship once in
vsphere** (it resolves the dashboard embed) and have os ship the
`Windows Service Down` symptom/alert + the OS dashboards it owns; a duplicate
view across two paks risks a name collision if both are installed (verify view
name uniqueness is enforced cross-pak — flag for recon).

### Hardware content

None yet. When `vcommunity-hardware` is designed, any hardware-keyed views/
dashboards/symptoms ship with it.

---

## 6. Repo / release structure

Three independent repos in `sentania-labs`, per `knowledge/context/managed_paks.md`,
each instantiated from `sentania-labs/vcf-content-factory-sdk-template`
("Use this template" → skeleton + `build-pak-on-tag` CI), each with its own
`v*` release cadence and its own defect-gate before a tag (RULE-012).

| Pak | Repo | adapter_kind | Target dir | Status |
|---|---|---|---|---|
| vcommunity-vsphere | `vcf-content-factory-sdk-vcommunity-vsphere` | `vcfcf_vcommunity_vsphere` | `content/sdk-adapters/vcommunity-vsphere/` | author next |
| vcommunity-os | `vcf-content-factory-sdk-vcommunity-os` | `vcfcf_vcommunity_os` | `content/sdk-adapters/vcommunity-os/` | author after vsphere |
| vcommunity-hardware | `vcf-content-factory-sdk-vcommunity-hardware` | `vcfcf_vcommunity_hardware` | `content/sdk-adapters/vcommunity-hardware/` | **DEFERRED — blocked on hardware API map** |

**OPEN-C — adapter-kind naming.** Proposed `vcfcf_vcommunity_vsphere` /
`vcfcf_vcommunity_os` / `vcfcf_vcommunity_hardware`. All comply with the
factory lowercase rule (`^[a-z][a-z0-9_]*$`, per `sdk_project.py`). Confirm
Scott is OK with three new kinds (vs. e.g. keeping `vcfcf_vcommunity` for the
vsphere one to ease migration — see §8). Recommendation: three **fresh**
kinds for symmetry and clean RBAC; do not reuse `vcfcf_vcommunity` (avoids any
split-brain ambiguity with the existing installed unified kind).

### `knowledge/context/managed_paks.md` registry changes needed

The orchestrator must (after each repo exists):

1. **Replace** the single `### vcommunity` entry (lines 84–94) — or keep it
   until migration completes and mark it superseded — with up to three new
   entries: `vcommunity-vsphere`, `vcommunity-os`, and (when ready)
   `vcommunity-hardware`, each with `Remote` / `Target` / `adapter_kind` /
   `Notes` lines per the file's template. **OPEN-D:** do we delete the unified
   `vcommunity` entry immediately, or keep it registered during a transition
   so the existing devel install stays bootstrappable? Recommend **keep it
   until vsphere+os reach parity on devel, then remove** (one-line edit).
2. Each entry notes attribution to Onur Yuzseven / `vmbro/
   VCF-Operations-vCommunity` (CC) — unchanged from the unified entry.

Three CI pipelines (one per repo) build the three `.pak`s on their own `v*`
tags. A factory `/publish` referencing any of them emits a pointer to that
repo's `releases/latest`, never a binary (unchanged model).

---

## 7. Migration path (from today's one installed unified adapter to three)

Today: **one** unified `vcfcf_vcommunity` adapter is installed on devel
(`build_number: 9`, two instances DATA_RECEIVING), with an in-flight guest-ops
credential fix (the UPN-vs-SAM `NamePasswordAuthentication` format issue —
`recon_log.md` build-9 diagnosis).

### Step-by-step

1. **Extract `vcommunity-vsphere` first.** Fork the existing
   `content/sdk-adapters/vcommunity/` repo into the new vsphere repo; **remove
   the guest-ops collector** (`GuestOpsClient`, the `Windows Monitoring`
   enum, the Windows credential kind, the two Windows config files, and the
   guest-ops branches of `VmCollector`). Keep `VCommunityVSphereClient`,
   `VCommunityStitcher`, `ClusterCollector`, `HostCollector`, and the
   vSphere-side of `VmCollector`. Resolve OPEN-A (recommend A1: vsphere keeps
   the Tools-path `OS *` keys). Author content per §5.
2. **Extract `vcommunity-os` second.** Fork the same source into the os repo;
   keep `GuestOpsClient` + `VmCollector`'s guest-ops branches + a copy of
   `VCommunityVSphereClient` / `VCommunityStitcher` (it needs its own vCenter
   session + stitcher per §2). Strip everything vsphere-only (cluster/host
   collectors, licensing, packages, adv-settings, snapshots, SCSI). **The
   in-flight guest-ops credential fix lifts directly into this repo** — the
   fixed `GuestOpsClient` (correct `NamePasswordAuthentication` username
   format) is the version that goes into `vcommunity-os`. Land that fix here,
   not in the dying unified pak. Author the os content per §5.
3. **Operator migration on each instance** (document in each pak's README):
   - **Uninstall the unified `vcfcf_vcommunity` pak.** Per
     `knowledge/lessons/pak-uninstall-cascades-credentials.md`, its instances and
     credentials cascade away.
   - **Install `vcommunity-vsphere`** (and `vcommunity-os` if Windows
     monitoring is wanted). Recreate instances + credentials against the new
     kind(s). No instance/credential carry-over across a kind change (same
     constraint as the original→unified migration in `vcommunity-sdk.md`).
   - **Metric-history continuity (convenience, not contract):** because all
     three paks push onto the **same** VMware-owned resource UUIDs under the
     **identical** `vCommunity|` key namespace, historical series on those
     foreign resources remain mechanically continuous through the migration —
     same keys, same resources, just split across more writers. This is a
     happy side effect of key-namespace continuity, **not** an upgrade
     guarantee (same framing as the original→unified migration). Do not sell
     it as a supported upgrade.
4. **Sequencing on devel:** stand up `vcommunity-vsphere` to parity on devel
   first (it is the bulk and is already de-risked — the unified pak is
   DATA_RECEIVING today), then `vcommunity-os` (which is still working through
   the guest-ops session blocker in `recon_log.md` — that investigation
   continues against `vcommunity-os`, not the unified pak). The vsphere pak
   can ship independently while os guest-ops is still being debugged — which
   is precisely the blast-radius-isolation benefit Scott wants.
5. **Retire the unified pak.** Once vsphere+os reach parity on devel, remove
   the `### vcommunity` entry from `knowledge/context/managed_paks.md` (OPEN-D) and
   archive the original unified repo.

---

## Key Risks

1. **OPEN-A (the dual-sourced `OS *` keys) is the hinge.** Resolving it A1
   makes the namespaces disjoint and retires the entire co-push clobber risk
   by construction. Leaving it A2/A3 keeps a shared key and makes the §3
   empirical test a release gate. **Decide A1 before authoring.**
2. **Stitch-identity drift across forks.** Three copies of `VCommunityStitcher`
   must all keep the build-2 `VMEntityVCID` scoping fix
   (`knowledge/lessons/stitch-moid-not-unique-across-vcenters.md`). A fork that drops it
   reintroduces silent multi-vCenter cross-stitch. Flag for
   `sdk-adapter-reviewer` on every pak.
3. **Content duplication / name collision across paks.** If both paks are
   installed, content names must not collide (the `Windows Services` view, any
   shared SM). Recommend ship-once-in-vsphere for the shared view (OPEN-B1);
   verify cross-pak content-name uniqueness is enforced (recon).
4. **Doubled vCenter load.** A shop installing both paks opens two vim25
   sessions + two stitch cycles per cadence against the same vCenter.
   Accepted cost of the split; document it so it is not mistaken for a leak.
5. **Guest-ops blocker travels with os.** The unresolved guest-ops session
   failure (`recon_log.md`: credential-format hypothesis) is now
   `vcommunity-os`'s problem to close. The split does not fix it — but it
   isolates it (vsphere ships regardless).
6. **`vcommunity-hardware` is vapor until a source exists.** Scoped, not
   designed. Do not let it block vsphere/os. Its stitch-identity story (how a
   BMC reading maps to a VMWARE HostSystem MOID) is itself an open design
   problem (§2).

---

## OPEN Questions (decide before authoring)

- **OPEN-A — `Guest OS|Operating System|OS *` key ownership.** A1 (vsphere
  via Tools path, os drops CSV OS-info) / A2 (os via CSV, vsphere drops) / A3
  (both, status-quo superset). **Recommend A1.** This is load-bearing — it
  determines whether §3 needs an empirical co-push test at all.
- **OPEN-B — mixed-surface content (`Critical Business Applications`
  dashboard + `Windows Services` view).** B1 (ship with dominant pak, degrade
  gracefully) / B2 (split per-pak variants) / B3 (separate bundle).
  **Recommend B1.** Sub-question OPEN-B1: duplicate the `Windows Services`
  view across both paks or ship once in vsphere? **Recommend ship once in
  vsphere.**
- **OPEN-C — adapter-kind names.** `vcfcf_vcommunity_vsphere` /
  `_os` / `_hardware`? **Recommend yes, three fresh kinds** (do not reuse
  `vcfcf_vcommunity`).
- **OPEN-D — `managed_paks.md` transition.** Delete the unified `vcommunity`
  entry immediately or keep it registered until vsphere+os reach devel
  parity? **Recommend keep, then remove at parity.**
- **OPEN-E — `vcommunity-hardware` scope confirmation.** Confirm it is
  formally DEFERRED (no work until an `api-cartographer` map for the target
  BMC/Redfish/IPMI API exists). **Recommend confirm DEFERRED.**

## Decisions (resolved 2026-06-22, Scott)

- **OPEN-A → `vcommunity-os` OWNS the six `Guest OS|Operating System|OS *`
  keys via the in-guest CSV path (full parity, populated `OS Name` like
  Onur).** Scott chose parity over the credential-free Tools-only path.
  **Authoring refinement to settle (orchestrator recommends A2 over A3):**
  prefer **A2 — os owns these keys *exclusively*, vsphere DROPS them** →
  namespaces stay fully disjoint → no last-writer-wins flapping on the shared
  keys → the §3 co-push empirical test is **not** required. Consequence of A2:
  a vSphere-only install (os adapter absent) shows no `OS *` keys at all —
  which is consistent with the RBAC/UX driver (a vSphere-only admin opts into
  guest-OS data by installing the os adapter). A3 (both emit, os wins) would
  keep basic Tools-path OS-info on vSphere-only installs but reintroduces the
  shared key + mandates the co-push test. Confirm A2-vs-A3 at authoring start.
- **OPEN-B → B1:** mixed-surface content ships with the dominant (vsphere)
  pak and degrades to "no data" when os is absent. **OPEN-B1:** ship the
  `Windows Services` view **once in vsphere** (no duplication).
- **OPEN-C → yes:** three fresh adapter kinds `vcfcf_vcommunity_vsphere` /
  `_os` / `_hardware`; do not reuse `vcfcf_vcommunity`.
- **OPEN-D → keep, remove at parity:** retain the unified `vcommunity`
  `managed_paks.md` entry until vsphere+os reach devel parity, then remove.
- **OPEN-E → confirmed DEFERRED:** `vcommunity-hardware` does no work until an
  `api-cartographer` BMC/Redfish/IPMI map exists.

## Decisions (resolved 2026-06-23, Scott — EXECUTION of the vsphere/os split)

Triggered by shelving the `vcommunity-os` guest-ops blocker (see below) so the
vSphere value ships now. Hardware stays DEFERRED (OPEN-E unchanged).

- **Execute NOW, before content port.** The unified pak carries only the 6
  SolutionConfig XMLs — no SMs/dashboards ported yet — so the split is a pure
  adapter-Java surgery with almost nothing to re-allocate. Ideal timing.
- **OPEN-C reaffirmed — fresh kinds, unified retires.** Both paks get fresh
  adapter kinds (`vcfcf_vcommunity_vsphere`, `vcfcf_vcommunity_os`); the unified
  `vcfcf_vcommunity` kind is retired. (Scott declined reusing `vcfcf_vcommunity`
  for vsphere — accepts the devel reinstall cost for clean symmetry.)
- **OPEN-A refinement — vsphere KEEPS the passive Tools-path `Guest OS|
  Operating System|*` keys.** These are vim25-sourced (`guest.*`, no Windows
  credential, no in-guest script), so basic OS inventory (name/version/build/
  boot) survives on a vSphere-only install. The `vcommunity-os` pak owns the
  **in-guest CSV** OS-info path (richer, populated `OS Name` like Onur) when
  un-shelved. **While os is shelved, vsphere is the SOLE writer of those six
  keys → no co-push conflict.** The OPEN-A overlap (both writing the six keys =
  A3 last-writer-wins) only re-arises when os is un-shelved — **re-decide OPEN-A
  at os un-shelve** (likely os drops the six and relies on vsphere's Tools path,
  or runs the §3 co-push test). Not a blocker now.
- **Repo mechanics.** Clone current → new `vcf-content-factory-sdk-vcommunity-os`
  FIRST (captures the guest-ops code before it is stripped), then transform the
  current repo → `vcommunity-vsphere`. Matches Scott's "clone to new, then edit
  current" instinct. Each fork MUST retain the build-2 `VMEntityVCID` stitch
  scoping (Risk #2) — flag for `sdk-adapter-reviewer` on both.

### Shelved: the `vcommunity-os` guest-ops blocker (state preserved 2026-06-23)

The OS pak is shipped/built but its in-guest collection is a KNOWN-OPEN blocker,
intentionally shelved. State so it is not re-derived when un-shelved:

- **Symptom:** Windows `Services:*` (and in-guest CSV OS-info, events) return
  zero rows on BOTH our Java port AND Onur's prod Python, on the same Server
  2025 DCs. Passive vim25 OS-info keeps populating (masking it).
- **ELIMINATED:** wrong transport; SolutionConfig gate (fixed, `2 check(s)`);
  service names (`Get-Service DHCPServer,NTDS` returns perfect CSV interactively);
  StartType header-gate / UTF-8 BOM (CSV is well-formed); credential identity
  AND privilege/logon-rights (**domain-admin swap changed nothing** — 2026-06-23
  recon).
- **LEADING UNCONFIRMED theory:** in-guest PowerShell **script execution is
  blocked in the non-interactive, VMware-Tools-launched context** — machine/GPO
  **ExecutionPolicy** (Restricted/AllSigned) or **ConstrainedLanguage mode /
  AppLocker / WDAC** on the hardened DCs. Fits every fact (passive OS-info
  flows; `StartProgram` returns no SOAP fault → `guestops_last_error='none'`;
  no CSV written; prod+devel identical; interactive admin test succeeds in a
  different execution context).
- **NEXT STEP when un-shelved:** (1) on a DC, `Get-ExecutionPolicy -List` +
  `$ExecutionContext.SessionState.LanguageMode` + invoke the script FILE in a
  fresh process with vs without `-ExecutionPolicy Bypass`; (2) if confirmed, the
  fix is OURS and small — add `-ExecutionPolicy Bypass -NonInteractive` to
  `GuestOpsClient.runPowershell` (`args = "-Command \"…\""` today, no policy
  flag); (3) separately, fix the `GuestOpsClient.post()` silent-null so a
  StartProgram fault surfaces instead of empty→DEGRADED.
- Full diagnosis: `knowledge/context/investigations/vcommunity-windows-services-empty-2026-06-23.md`
  and `…-guestops-execution-divergence-2026-06-22.md`.

## Attribution

All three paks credit Onur Yuzseven / `vmbro/VCF-Operations-vCommunity` (CC)
in their MP descriptions and every ported artifact, per
`knowledge/context/reference_sources.md` — unchanged from the unified pak.
