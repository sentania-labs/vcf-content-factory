# Cross-MP stitching: the injected instance credential and how edges actually form

**Status:** Proven live (devel 9.0.2 + prod 9.1, 2026-07-02, synology
build 26 — DEF-006 closing evidence). Written for a future session
implementing cross-MP stitching in ANY Tier 2 adapter (unifi is next)
with no memory of the investigation that produced it.

## The three facts that matter

1. **Ambient identity: the collector hands every adapter instance its
   own Suite API credential.** Read it via the pure SDK-public chain
   `AdapterBase.getAdapterConfig().getAdapterCredentials()
   .getUserName()/.getPassword()`. The principal is the adapter
   instance UUID and it has resource-read RBAC **on every node role,
   including Cloud Proxies**. This is what every Broadcom pak uses
   (aria-ops-core reads it credentials-first). The framework does this
   for you since ambient identity v3: `AmbientCredential` order is
   injected-instance → `automationuser.properties` →
   `maintenanceuser.properties`, logged as
   `file=instance|automation|maintenance` with an
   `instance-credential not used reason=…` breadcrumb on fallthrough.
   **Do not read credential files off the node yourself; do not use
   maintenance/automation identities on a CP** (maintenance =
   `cloudproxy_<uuid>`, roles:[], 403s reads; automation's local
   secret 401s at token acquire — both live-proven dead on CPs).
   Caution: `AdapterCredentialConfig.getPassword()` internally
   decrypts via `com.vmware.vcops.security.Crypt`, absent from the
   adapter classpath in some environments → `NoClassDefFoundError`
   (a LinkageError, not Exception). The framework catches
   `Exception | LinkageError` and falls through; keep it that way.

2. **Edges are created ONLY by resolving the foreign resource's
   uniqueness identifiers.** The platform's single edge-writer
   (`DiscoveryProcessor` → `RelationshipManager`) resolves each pushed
   relationship against an identity cache keyed on
   (adapterKind, resourceKind, **uniqueness identifiers**) — resource
   NAME is ignored; non-matching items are **silently dropped**. For
   `VMWARE::Datastore` that means (VMEntityObjectID, VMEntityVCID).
   Names, paths, NAA ids are `identType=2` — search keys, never
   endpoints. Therefore the working pattern is: Suite API read (under
   the injected identity) to find the foreign resource by a
   target-system-derivable value → take the resolved resource's TRUE
   key → push the edge **additively** (framework `RelationshipBuilder`
   `parentForeign` — never full-set onto a foreign parent).

3. **Two seductive non-mechanisms — both proven inert, do not
   rebuild them:** (a) reporting a `relationships|<Kind>_parent`
   property does NOTHING (no property→edge code path exists in the
   platform; those properties are the platform *reflecting* existing
   edges — effect, not cause); (b) describe.xml `TraversalSpecKind`
   declarations are UI/navigation metadata over existing edges and
   never create them. Both were tested live on a virgin instance
   (synology build 25) and produced zero edges, including with a
   byte-perfect identifier-value match.

## Search values that work (datastore case)

The `DataStrorePath` identifier (platform's own spelling): block =
`VMFS:|naa.<id>|`, NFS = `<nas-ip>/<export-path>`. All derivable from
the target system — but try EVERY candidate interface IP for NFS (the
NAS's first NIC is often not the one ESXi mounts; synology build 25's
single-IP shortcut was a real bug).

## Evidence chain (read before deviating)

- `context/api-surface/per-instance-suiteapi-credential-contract.md` —
  the credential contract, bytecode receipts.
- `context/investigations/oracle-stitch-autopsy-2026-07-02.md` — live
  DEBUG capture of the vendor mechanism (and the log-level artifact
  that misled three earlier investigations: stitch lines are DEBUG;
  absence of evidence at INFO is not evidence of absence).
- `context/investigations/platform-edge-engine-2026-07-02.md` — the
  edge-writer bytecode: identifier-keyed cache, silent drop, no
  property path, traversal inert.
- `context/defects.md` DEF-005/DEF-006 — the full failure/fix history.
- Reference implementation: synology adapter (build 26) +
  `adapter_framework` stitch layer (`AmbientCredential`,
  `SuiteApiStitchClient`, `RelationshipBuilder`).
