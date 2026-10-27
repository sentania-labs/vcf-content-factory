# Synology build 34 review (sdk-adapter-reviewer)

- **Adapter:** `content/sdk-adapters/synology` (repo `sentania-labs/vcf-content-factory-sdk-synology`)
- **Branch reviewed:** `fix/11-device-identity`, uncommitted working tree on top of `e43d10f` (build 33). Read as found; not modified.
- **Fork issue:** #11 (two NASes write into the same objects). Decision (Scott): identity is the DSM serial; a one-time re-creation of objects on upgrade is accepted, with an upgrade note.
- **Reference pak:** `dist/vcfcf_sdk_synology_diskstation.0.0.0.33.pak`
- **Date:** 2026-10-27
- **Verdict:** CHANGES REQUESTED (1 BLOCKING, 3 WARNING, 2 NIT)

## Bottom line

The keying change itself is right. Every object key goes through one
helper (`SynologyAdapter.resourceKey`), enumeration, the topology and the
Datastore cross-link all pass the same identity, the DiskStation key is
byte-for-byte the build 33 key when DSM sends a serial (so its history is
kept), and a serial that disappears mid-run fails the cycle instead of
re-keying. The one blocker is the latch's lifetime: it lives in memory, so
a collector restart, a pak upgrade or any account edit forgets it, and the
very case the docs say "fails the cycle" instead silently moves the whole
tree, the history-bearing DiskStation included, to the fallback identity.
The docs promise a guarantee the code only keeps until the next restart.

## Claims check (independently re-run)

| Claim | Result |
|---|---|
| `ci/run_java_tests.sh` passes | Confirmed: 17 Java (incl. new `DeviceIdentityTest`) + 9 Python (incl. new `test_device_identity_wiring.py`), all pass. |
| validate-sdk OK | Confirmed: `OK: ... valid Tier 2 SDK adapter project` (SDK compat jar check skipped: jars not present, same as prior builds). |
| build-sdk 0.0.0.34 | Confirmed, rebuilt to scratch: `vcfcf_sdk_synology_diskstation.0.0.0.34.pak`. |
| pak-compare vs 33 | Confirmed: PASS, 0 BLOCKING / 0 WARNING / 0 INFO. |
| describe: `diskstation_id` on World + 7 child kinds, not on DiskStation | Confirmed in the built pak's `conf/describe.xml`: 8 occurrences, no `identType` (identifying, same as every existing identifier); DiskStation keeps `serial` only; `310=DiskStation ID` in the packed resources. |
| Dimension 13 (alerts) | Not applicable: the describe has no symptoms, symptom sets or alerts. |
| `build_number` 34 + CHANGELOG line | Confirmed. |

Mutation (full copy, full runner): passing `null` instead of
`s.device.value` to the two Datastore cross-link `resourceKey` calls
(LUN and NFS export) **survives**: every test passes. See W2.

## Probes requested in the brief

**Relationships after the key change.** The tree is anchored on the World
and emitted only when the World carries the current identity
(`SynologyAdapter.java:715`). The DiskStation's own-parent full set
(`setRelationships`) now lists the new pools and UPS, so the old children
are detached from the surviving DiskStation on the first new-World cycle.
The old World emits nothing, so its last full set stays: it remains a
second parent of the DiskStation (whose key did not change) until it is
deleted (N2). Topology keys are cached per `Obj` (which now includes the
identity in `equals`/`hashCode`), so one parent collects all its children.
Correct.

**Datastore cross-link.** The LUN and NFS export child keys are built with
the identity (`SynologyAdapter.java:1367`, `:1403`) and match enumeration
(same kind, id and identifier set; name expression identical). The foreign
Datastore key is untouched. Both own identifiers are flagged unique, which
matches describe (no `identType`, so identifying), so the key is bindable
per `knowledge/lessons/cross-mp-foreign-key-uniqueness-flags.md`. Foreign
edges are additive, so the old LUN/export keep their Datastore link until
deleted; the README says so. Correct statically; live bind owed (W3), and
not pinned by any test (W2).

**Serial missing for one cycle.** `DeviceIdentity.resolve` throws after a
serial has been seen (`DeviceIdentity.java:151`); `Snapshot.build` fails,
the snapshot cache fails every caller for the cycle, discovery emits
nothing, objects go NO_DATA_RECEIVING and the instance ERROR. No orphan,
no duplicate, within one process lifetime. A hollow payload (no `model`)
already fails before the serial is read. Correct, tested
(`serialThatGoesMissingFailsTheCycle`).

**Restart loses the latch.** Not safe: B1.

**Old objects: false alerts or noise.** They get no metrics, but the
framework sets `RESOURCE_STATUS_DATA_RECEIVING` on every object whose
`collect` returns normally (`VcfCfAdapter.java:1005`), so they stay
"Data Receiving" with frozen last values: W1. No pak alerts exist, so the
pak itself fires nothing; user alerts on those objects freeze in their
last state. The INFO line is once per object per configuration
(bounded set), not per cycle. Acceptable log volume.

**DiskStation history kept.** Statically yes: kind, name
(`<model> <serial>`), single `serial` identifier with the raw DSM value,
flag `true`, identical to build 33 (`enumerateResources`, topology).
The `unknown` case is honestly documented as re-created. Live proof owed
(W3).

**Fallback normalisation.** Host trimmed and lower-cased with
`Locale.ROOT`; port is the config's int (blank or non-numeric becomes
5001, the same port the client dials, so the identity follows the real
endpoint). A blank host throws rather than inventing an identity.
IP vs FQDN vs trailing dot are different identities, which the docs cover
("editing the host or port re-creates them"). Correct, tested
(`missingSerialFallsBackToTheEndpointOnce` with `"  NAS1.Lab "`).

## Findings

### BLOCKING

**B1. The no-flip latch is lost on collector restart, pak upgrade or account edit; the docs promise it holds.**
`DeviceIdentity.java:103-104` (in-memory `serialSeen`), constructed per
configuration at `SynologyAdapter.java:269`.
Authority: reviewer dimension 11 (docs that contradict behavior are
BLOCKING); skill § *ARIA_OPS stitching identity* and § *Gaps* (DESIGN GAP:
never let a wrong guess re-key data).

REFERENCE.md "DiskStation identity", `docs/installing.md`
troubleshooting and the CHANGELOG say that once a serial has been read, a
cycle without one fails "instead of moving the objects to the fallback
identity", and the troubleshooting entry tells the operator to restore the
account's rights. After any restart of the collector (including the pak
upgrade itself) or any account edit (a password rotation), the first cycle
without a serial takes the fallback path with one WARN: a full duplicate
tree is created under `host:<host>:<port>`, and every serial-keyed object,
the DiskStation that holds the history included, is retired (no data,
still "Data Receiving", see W1). When the rights come back the objects move
back to the serial and the fallback tree is left orphaned, Datastore links
and all. That is the exact flip-and-back the latch exists to stop, and the
trigger (an account that lost administrator rights) is the scenario the
docs themselves describe.

Smallest correct fix (preferred): seed the latch from state the platform
already holds. On a no-serial answer with no in-memory latch, if this
adapter instance already has a `SynologyDiskstation` whose `serial`
identifier does not start with `host:`, fail the cycle exactly as the
latch does. Pin it with a test. Minimum acceptable alternative: state in
REFERENCE.md, `docs/installing.md`, the CHANGELOG and the
`DeviceIdentity` javadoc that the guard lasts only until the collector
restarts or the account is saved, and what happens then (duplicate tree,
history object retired).

### WARNING

**W1. Retired objects report "Data Receiving" every cycle with frozen values.**
`SynologyAdapter.java:807-811` returns normally; the framework then sets
`RESOURCE_STATUS_DATA_RECEIVING` (`VcfCfAdapter.java:1005`).
Authority: skill § *Unreadable is NOT compliant* (surface it as an
explicit signal); dimension 6 (operator must tell collected from not).
The README says they "stop receiving data" and the troubleshooting entry
calls them "objects with no data", but the Ops collection state says the
opposite, and their last metric values and any user alerts on them stay
frozen as if current. The README's identifier-based cleanup recipe does
work, so this is not BLOCKING. Fix: report them NO_DATA_RECEIVING. There
is no collector hook for a non-failure status today (a thrown exception
would cost a WARN per object per cycle), so either a `tooling` hook, or at
minimum say in the README Upgrading section that the old objects keep
showing Data Receiving and frozen values until deleted. Registration
candidate (RULE-012) if it ships unfixed.

**W2. The cross-link identity is not pinned by any test.**
`SynologyAdapter.java:1367`, `:1403`.
Authority: reviewer dimension 9 (prove behavior, don't assert it);
`knowledge/lessons/cross-mp-foreign-key-uniqueness-flags.md` (a wrong
key there fails silently). Dropping the identity from both cross-link keys
passes the full runner. Such a key would match the retired pre-34
LUN/export, so the Datastore would keep linking the dead object with zero
log trace. Fix: assert in `test_device_identity_wiring.py` (or a unit
test) that both cross-link `resourceKey` calls pass `s.device.value`.

**W3. The upgrade claims in the shipped docs are unproven live.**
Authority: `knowledge/rules/validate-before-install.md`; reviewer doctrine
(unproven is a finding). Owed on devel before a `v*` tag: (a) upgrade from
33 keeps the DiskStation's history; (b) Ops accepts a new identifying
identifier on kinds that already have instances and creates the new
objects; (c) Datastore links bind to the new two-identifier LUN and export;
(d) two instances on two NASes produce two disjoint trees.

### NIT

**N1.** `SynologyAdapter.java:1306`: comment still says "Same edges,
order, names and identifiers as build 30"; names and identifiers changed
in this build.

**N2.** README Upgrading: the old World keeps its last edges, so the
surviving DiskStation shows under two Worlds until the old World is
deleted. Say so, so an operator does not read it as a new bug.

## Registry check (`knowledge/context/defects.md`)

No open defect has `Affects: synology` (DEF-001, -003, -005, -006 are all
closed). Nothing to re-assert or close. Registration candidates if they
ship unfixed: B1, W1.

## If shipped as-is

A collector restart or account edit while the account cannot read the
serial silently re-keys the whole NAS to a host-based tree, retiring the
DiskStation with its history, and leaves duplicate trees behind. Docs say
this cannot happen. Retired objects also look healthy and current in Ops.
