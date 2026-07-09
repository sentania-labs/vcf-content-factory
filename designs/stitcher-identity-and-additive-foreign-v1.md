# stitcher v3 — automationAdmin identity + additive foreign-parent edges

**CORRECTION (2026-07-09, per 2026-07-02 findings):** the evidence-base
line below citing the cp-auth-door probe's "Oracle puzzle solved
(describe.xml traversal, no suite-api calls)" is disproven: describe.xml
traversal never creates edges; Oracle's edges come from a per-cycle Suite
API read under the platform-injected per-instance credential. See
`context/investigations/oracle-stitch-autopsy-2026-07-02.md` and the
CORRECTION addenda on the probe doc itself
(`context/investigations/cp-auth-door-probe-2026-07-01.md`).

## Initial prompt (verbatim, 2026-07-01 session)

The change emerged over one investigation thread. The load-bearing user
turns, verbatim:

> can you do a recon against prod and see if the relatinoship(s) from the
> oracle paks are fresh or stale?

> this question/research is related to our synology relationship stichting
> issue

> so what does this mean for a tooling, and vcfadapter approach - remember
> the framework is the product.

> we are not shipping unlicenseddapter

> do the recon - may as well hit prod since the oracle pak is there too

(On the write-verb choice, after the full-set-vs-additive tradeoff was
laid out with a middle-path recommendation — full-set for own trees,
additive for foreign parents:)

> Option 2.

## Vision

Two framework changes in `vcfops_managementpacks/adapter_framework/`,
one tooling round, one buildkit republish. Every SDK adapter (synology,
unifi, compliance, vcommunity*) inherits both on its next re-pull.

- **Identity fix (the CP-403 root cause).** The stitcher's ambient
  credential provider must prefer `automationuser.properties`
  (`automationAdmin`, RBAC-bearing) and fall back to
  `maintenanceuser.properties` only when the automation file is absent.
  Unconditional prefer, no node-role detection — both primary and CP
  carry the automation file. On a CP the maintenance file resolves to
  `cloudproxy_<uuid>` (`roles:[]`) which 403s on resource reads; that
  is the entire Synology-on-CP stitch failure. Transport is unchanged:
  same public `https://<gateway>/suite-api` door, same token-acquire,
  no CaSA/node-cert mTLS, no relay, no aria-ops-core, no base-class
  change (`VcfCfAdapter` stays on bare `AdapterBase` — locked decision,
  see `designs/vcfcf-base-v2-adapterbase-rehome.md`).

- **Write-verb split (retires the DEF-002/003 9.1 residual).** In
  `RelationshipBuilder`: edges whose **parent belongs to a foreign
  adapter** (e.g. VMWARE Datastore/HostSystem/VirtualMachine) are
  emitted **additively** (the existing-but-unused delta/add path), never
  via full-set `setRelationships`. **Own-adapter hierarchies keep the
  consolidated one-`setRelationships`-per-parent-per-cycle** idiom —
  that preserves the MP certification checklist item recorded in
  `designs/vcfcf-base-v2-adapterbase-rehome.md`, which is about an
  adapter's own tree, not foreign resources. Additive-on-foreign is
  what all 8 modern Broadcom TVS paks do; it is clobber-safe on any
  platform version, so the 9.1 per-adapter-scoping proof is no longer
  load-bearing.

- **Preserve intact:** foreign-key identity handling — `DataStorePath`
  (not MOID), real `isPartOfUniqueness` propagation
  (`SuiteApiDatastoreBridge`). A refactor that breaks this reintroduces
  the MOID trap.

## Evidence base (read, don't re-derive)

- `context/investigations/cp-auth-door-probe-2026-07-01.md` — live prod
  CP (9.1) probe: automation vs maintenance file, working-door proof
  (`VMWARE_INFRA_MANAGEMENT`, vCommunity 200s), SynologyStitcher caught
  failing as `cloudproxy_<uuid>`, Oracle puzzle solved (describe.xml
  traversal, no suite-api calls), CaSA constants harvested.
- `context/api-surface/casa-injected-vs-raw-client.md` — bytecode RE:
  no CaSA routing in any pak jar; fix is identity, not transport.
- `context/reviews/synology-stitcher-vs-tvs-corpus.md` — the review
  that produced R1 (additive) / R2 (door) / R3 / R4.
- `context/api-maps/tvs-cross-mp-stitching.md` — vendor corpus is
  uniformly additive for foreign parents.

## Out of scope (tracked, not this round)

- R3 (deprecate the 3 `vrops_*` explicit-credential fields) — after the
  identity fix proves out on devel.
- R4 (page the `pageSize=10000` datastore pull) — small, can ride a
  later round.
- Final live proof: first devel build minting the automationAdmin token
  in-JVM (the probe's one un-run step — access boundary, not doubt).
