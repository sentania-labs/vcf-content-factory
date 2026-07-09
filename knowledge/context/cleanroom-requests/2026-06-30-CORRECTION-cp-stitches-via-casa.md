# Cleanroom CORRECTION + question — Cloud Proxy adapters DO stitch ambiently (via CaSA, node-cert)

**Filed:** 2026-06-30 (VCF-CF → cleanroom)
**Corrects:** the conclusion in responses `ad419d29` and `98166aec` ("CP adapters can't stitch ambiently; DB adapters are implicitly primary-node-only; explicit creds are the only path off-primary"). **That conclusion is empirically false.** Please correct spec/20 §4 and spec/07 accordingly.

## The disproof (live prod evidence)

The prod Cloud Proxy (`vcf-lab-operations-collector`, collector id=2, `UNIFIED_CLOUD_PROXY`, node `9017a996-…`) runs the **full reference-adapter fleet** — `MicrosoftSQLServerAdapter`, `OracleDatabaseAdapter`, `VsanStorageAdapter`, `NSXTAdapter`, `VcfAdapter`, `VMWARE_INFRA_MANAGEMENT`, etc. These are NOT primary-node-only.

**Smoking gun:** the `VMWARE_INFRA_MANAGEMENT` adapter (id `bca42bec`) on the CP has **`credentialInstanceId=null`** — zero operator credentials — and is *actively managing 29 VMWARE resources* (8 ESXi HostSystems, the 3 vCenter-instance objects) with live current metrics on a 5-minute cycle. A credential-free adapter reading cluster VMWARE inventory from a Cloud Proxy, right now.

## The mechanism the SPEC missed: CaSA

The correct off-primary path is **CaSA (Cluster Aware Service API)** — a local reverse-proxy service on each node that:
- authenticates to the primary using the node's **own certificate** (mutual TLS as the node identity), NOT a user credential;
- bypasses the user-credential/role stack entirely;
- returns authenticated access to the cluster's full resource inventory.

The SPEC's §4 analysis was scoped to the *user-credential* Suite API surface (`localhost/suite-api`, ambient `maintenanceAdmin` vs explicit creds). It never examined the **platform node-cert path**. Our earlier 403 was `localhost/suite-api` called as the scoped `cloudproxy_<uuid>` maintenance account — correct 403 for the *wrong door*. CaSA is the right door and needs no operator creds. This is why the SPEC's ledger #9 ("no forwarding mechanism") was rated Med / absence-of-evidence — the forwarding exists, it's just not in the pak jars, it's a platform runtime service.

## The question (you have the aria-ops-core + BC corpus; we are separately RE'ing the BC paks directly)

**How does the platform-injected `SuiteAPIClient` (aria-ops-core / `UnlicensedAdapter`) route through CaSA on a Cloud Proxy?**
1. What endpoint/port does the injected `SuiteAPIClient` target on a CP vs `localhost/suite-api` on the primary? Is CaSA selection automatic by node role?
2. How does it obtain/present the **node certificate** for CaSA mutual-TLS (keystore path, alias)?
3. Does the **raw** `vrops-adapters-sdk` `SuiteAPIClient` also route through CaSA, or ONLY the aria-ops-core injected one? (Decides whether a bare-`AdapterBase` factory adapter can reach CaSA, or must extend `UnlicensedAdapter`.)
4. Any `SuiteAPICredential` variant that yields a node-cert / CaSA credential rather than the `maintenanceuser.properties` user credential?

## Requested SPEC updates

- **spec/20 §4:** replace "explicit credential fields are the only viable mechanism for remote-collector deployment" with the CaSA node-cert mechanism as the idiomatic no-creds off-primary path; downgrade the explicit-creds path to "only for adapters talking to a foreign *target system* (e.g. vCenter directly), not for reading the Ops cluster inventory."
- **spec/07:** note that cross-MP stitch from a Cloud Proxy is fully supported ambiently via CaSA + SDK `Relationships` push.

We are concurrently reverse-engineering the BC first-party paths directly (permitted — Broadcom-owned); your independent corpus confirmation of the injected-client CaSA routing is the cross-check.
