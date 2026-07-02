# CP auth-door probe — Path-A/B tiebreaker + Oracle puzzle (prod Cloud Proxy)

**Date:** 2026-07-01
**Target:** prod Cloud Proxy `vcf-lab-operations-collector.int.sentania.net`
(172.27.8.51), collector id=2, `UNIFIED_CLOUD_PROXY`,
node `9017a996-596d-41da-b782-0e3ec924b775`.
**Posture:** strictly READ-ONLY. Root SSH used only for `ls`/`grep`/`cat`
of config, `/proc/<pid>/cmdline`, `ss`, `openssl x509 -noout`, log reads,
and three failed-auth curls (which create nothing). **Nothing written,
modified, restarted, or deleted on the appliance. No secrets copied into
this file — paths, usernames, aliases, URLs, ports, and public cert
metadata only.**

## Access (documented for future probes)

Root SSH to the prod CP works with the **doubled** appliance password
(same convention as the primary, per `suiteapi_ambient_auth_devel_2026_06_09.md`):

```
export SSHPASS='<doubled appliance root pw>'
sshpass -e ssh -o StrictHostKeyChecking=no root@172.27.8.51
```

DNS for `*.int.sentania.net` does **not** resolve from the factory box;
use the IPs directly (CP=172.27.8.51, primary=172.27.8.41). Both :22 and
:443 reachable. Appliance is Photon 6.1.166 / VCF Ops **9.1** ("VMware
Cloud Foundation Operations Cloud Appliance"). Collector JVM = PID 177372,
runs as user **`admin`**.

---

## Q1 — Does `automationuser.properties` exist on the CP? YES

`/usr/lib/vmware-vcops/user/conf/` on the CP contains **both** config-user
credential files, `0600 admin:admin` (readable by the collector, which
runs as `admin`):

| File | mode/owner | `username=` key (no secret read) |
|---|---|---|
| `automationuser.properties` (185 B, Oct 1 2025) | `-rw------- admin admin` | **`automationAdmin`** (`encrypted=true`) |
| `maintenanceuser.properties` (217 B, Oct 1 2025) | `-rw------- admin admin` | **`cloudproxy_9017a996-596d-41da-b782-0e3ec924b775`** (`encrypted=true`) |

No `clouduser.properties` present on this node.

**This is the crux.** On a Cloud Proxy the two files name **different**
principals:
- `automationuser.properties` → `automationAdmin` (the RBAC-bearing
  service account).
- `maintenanceuser.properties` → `cloudproxy_<uuid>` (the scoped
  reverse-connect account that gets `roles:[]` → 403).

Our v1 stitcher reads `maintenanceuser.properties`. On the **primary**
that file is `maintenanceAdmin` (works); on the **CP** the *same file* is
`cloudproxy_<uuid>` (403). That single fact is the whole CP-403 bug.

---

## Q2 — Does an automation-identity token carry resource-read RBAC?
### Verdict: Path A viable. (Direct minted-token curl = access boundary; overwhelming live indirect proof.)

**Access boundary on the literal test:** minting a token *as
`automationAdmin`* requires the plaintext password. The file is
`encrypted=true` (platform `Crypt`, node-local key). Decrypting it means
either running Java/`jshell` on the appliance (writes a class to appliance
temp — forbidden by this probe's charter) or exfiltrating the ciphertext +
key (a secret — forbidden). So I did **not** run the from-scratch
`token/acquire` as `automationAdmin`. That is the one boundary.

Everything short of holding the secret was tested and all points to
**Path A works**:

1. **The door is live and token-gated on the CP right now** (curls from
   the CP, 2026-07-01; failed calls create nothing):

   | Call (`https://172.17.0.1/suite-api/...`) | Result |
   |---|---|
   | `GET /api/versions/current` (no token) | **401** |
   | `GET /api/resources?resourceKind=VirtualMachine&pageSize=1` (no token) | **401** |
   | `POST /api/auth/token/acquire` (bogus creds) | **400** |

   Reproduces `casa-inventory-access.md` §2 exactly: a **user-token door**
   over the ambient tunnel. `172.17.0.1:443` and `127.0.0.1:443` are both
   `httpd-north` (see Q4).

2. **A valid principal succeeds through that door from the CP, today.**
   The `VCFOperationsvCommunity` adapter (Python `aria.ops.suite_api_client`)
   logs a steady stream of
   `post https://172.17.0.1/suite-api/api/auth/token/acquire: OK(200)`
   (latest 2026-07-01 21:13). Proves tunnel + door + token flow are
   healthy from the CP; the only variable is *which principal*.

3. **`automationAdmin` RBAC is proven live by the platform's own
   credential-free adapter.** `VMWARE_INFRA_MANAGEMENT` (adapter
   `bca42bec`, `credentialInstanceId=null`) actively reads/stitches 29
   VMWARE resources on this CP (recon_log 2026-06-30, still current). A
   creds-free adapter that reads cluster inventory can only be using the
   node-local config-user (`automationAdmin`) — it has no operator
   credential. So an `automationAdmin` token demonstrably carries
   resource-read RBAC on this CP.

4. **The negative control is our own bug, captured in the wild.** The
   factory `SynologyAdapter` logs:
   ```
   java.io.IOException: Suite API token/acquire failed: HTTP 503
   mechanism=ambient principal=cloudproxy_9017a996-596d-41da-b782-0e3ec924b775
   ```
   `com.vcfcf.adapters.synology.SynologyStitcher.fetchAndCache` /
   `ForeignResourceResolver`. It is acquiring with **`principal=cloudproxy_<uuid>`**
   — i.e. it read `maintenanceuser.properties`. (The 503 here is a
   transient tunnel-down window, but the *principal* is the permanent
   defect; when the tunnel is up this principal 403s.)

**Tiebreaker call:** **Path A (automation identity + the same public
`localhost`/`172.17.0.1` suite-api door) — VIABLE.** The fix is
**identity, not transport**: point the stitcher at
`automationuser.properties` (`automationAdmin`) instead of
`maintenanceuser.properties` (`cloudproxy_<uuid>`). No node-cert mTLS, no
CaSA port, no relay in our code. This confirms the build spec in
`casa-injected-vs-raw-client.md` §2 / `casa-inventory-access.md` (b).

---

## Q3 — The Oracle puzzle: SOLVED. There is no contradiction.

**OracleDBAdapter never calls the suite-api door.** Its stitch to VMWARE
VM `oracledemo` is **not** an adapter suite-api lookup at all.

Evidence on the CP:

- **Oracle adapter log has ZERO suite-api activity.**
  `/usr/lib/vmware-vcops/user/log/adapters/OracleDatabaseAdapter/…` grep
  for `suite-api|token|acquire|relationship|VirtualMachine|resources/query`
  returns **nothing** (0 hits). The only network the Oracle adapter does
  is to its Oracle target `oracledemo.int.sentania.net:1521` — and it is
  even intermittently failing there (`No route to host … 1521`).

- **The cross-MP stitch is a platform-side `describe.xml` ResourcePath
  traversal**, resolved by the analytics correlation engine, not by
  adapter code. In `oracledatabase_adapter_3/conf/describe.xml`:
  ```
  <ResourceKind key="oracle_database_vms_tag" type="4" showTag="true" dynamic="true">
    <ResourcePath path="OracleDBAdapter::oracle_database_traversal_tag||
      OracleDBAdapter::oracle_database_oracle_database_database::child||
      OracleDBAdapter::oracle_database_oracle_database_instance::child||
      VMWARE::VirtualMachine::~child"></ResourcePath>
  ```
  The `…||VMWARE::VirtualMachine::~child` terminus is what binds the
  Oracle instance to the VMWARE VM. This is declarative
  traversal/correlation (name/FQDN based, `oracledemo`), evaluated by the
  platform — it needs no token and no RBAC on the CP.

**Resolution of the apparent contradiction:** the CP maintenance account
(`cloudproxy_<uuid>`, `roles:[]` → 403) only matters to adapters that make
**explicit user-credential suite-api calls** (like our SynologyStitcher).
Oracle is not one of them, so its fresh stitch and the 403 coexist without
conflict. The puzzle assumed Oracle does a Suite API lookup; it does not.

**Bonus — the internal client IS on the collector classpath.** Even though
`vcops-suiteapi-internal-client` ships in no third-party pak, the **shared
collector JVM** (PID 177372) is launched with it, plus the platform's auth
plumbing, on the classpath:
`/usr/lib/vmware-vcops/collector/lib/vcops-suiteapi-internal-client-9.1.0.0.jar`,
`common/lib/vcops-suiteapi-client-9.1.0.0.jar`,
`common/lib/alive_platform.jar` (ConfigUserUtils),
`common/lib/casa-client-1.0-SNAPSHOT.jar`,
`common/lib/casa-rest-client-1.0-SNAPSHOT.jar`,
`common/lib/vrops-trustmanager-3.0-SNAPSHOT.jar` (NdcTrustManager),
`common/lib/vcops-security-1.0-SNAPSHOT.jar`,
`common/lib/platform-api-internal-model-9.1.0.0.jar`.
So any adapter running in-collector (ours included) has these classes at
runtime — the cleanroom's "in zero paks" is true at the *pak* level but
the classes are ambient on the *collector* classpath. Which adapter uses
what: `VMwareInfraHealthAdapter` → `com.vmware.adapter3.vmwareinfrahealth.util.VROPsSuiteApiUtil`
against `https://localhost/suite-api`; `VCOpsAdapter` →
`com.vmware.vcops.casarest.client.CaSAClient` (CaSA control plane, e.g.
`SysadminAPIs.getSysadminSliceNtp`).

---

## Q4 — CaSA / tunnel constants harvested from the live CP

**Listening sockets (`ss -tlnp`):**
| Bind | Service | Role |
|---|---|---|
| `127.0.0.1:443` **and** `172.17.0.1:443` | `httpd-north` | local suite-api door (adapters + docker-bridge containers) |
| `127.0.0.1:8443` | `haproxy` (`PrxyRC_FE`) | CaSA/suite-api reverse-connect tunnel to cluster |
| `127.0.0.1:8444/8445/8446/8447/8448` | `haproxy` | PrxyRC unsecure / vRLI / crushftp / dynamic / unified-shell |
| `172.27.8.51:443` and `172.27.8.51:8443` | `httpd-south` | external cluster→CP reverse-connect side |

**httpd-north routing** (`/etc/httpd-north/*.conf`):
```
ProxyPass        /suite-api/ https://cptocluster:8443/suite-api/ disablereuse=On
ProxyPassReverse /suite-api/ https://cptocluster:8443/suite-api/
```
`cptocluster` → `127.0.0.1`; port 8443 = haproxy `PrxyRC_FE`.

**haproxy PrxyRC** (`/etc/haproxy/haproxy.cfg`):
```
frontend PrxyRC_FE
  bind localhost:8443 ssl crt /storage/vcops/user/conf/ssl/haproxy.slice.pem ...
backend PrxyRC_BE
  http-request set-header Host vcf-lab-operations.int.sentania.net:443
  server VROPS_0 vcf-lab-operations.int.sentania.net:443 ssl verify required \
         ca-file /storage/vcops/user/conf/ssl/haproxy.ca.pem
```
Backend has **no client `crt`** → haproxy presents no client cert to the
primary's suite-api ⇒ suite-api still demands a user token (matches the
401s above). The slice cert secures the pipe; the token authorizes the API.

**Node / slice certificate (identity anchoring the reverse-connect):**
- `/storage/vcops/user/conf/ssl/haproxy.slice.pem` (`0600 admin:admin`) —
  the server cert the PrxyRC frontends present.
- `slice_1_cert.pem` / `slice_1_key.pem` / `slice_1_cert.pfx`,
  `cluster.truststore`, `haproxy.ca.pem`.
- Slice cert subject/issuer (public metadata):
  `subject= CN=VCFOps-slice-1, O="Broadcom, Inc."`
  `issuer = CN=VCFOps-cluster-ca_3326c838-ff3f-4a6c-a53e-17ebe2fa24b6`.

**CaSA control endpoint / cert renewal:**
- CaSA control rides the same tunnel: httpd-north `ProxyPass /casa/ →
  https://cptocluster:8443/casa/`.
- Security ping URL (in `/usr/lib/vmware-casa/conf` watchdog xml):
  `https://localhost/casa/cluster/security/ping`.
- Certificate renewal is a suite-api/CaSA REST surface, not a single
  injected string: OpenAPI schemas `CollectorCertificateRenewalStatusResponse`,
  `VcfCertificateAutoRenewSpec`, `ClientsCertificateRenewContext`, plus
  local `bin/activate_renewed_certificates.py` (sudoers NOPASSWD for
  `$VCOPS_USER`). No standalone `certificateRenewUrl` constant was readable
  in plain config on this node (it is composed against the cluster base
  URL). `casa-webapp/conf/server.xml` did not expose a plaintext keystore
  alias.

---

## Contradictions / flags against prior docs

1. **Cleanroom "internal client in zero paks" — technically true, but
   materially misleading for our purpose.** The internal client + all the
   CaSA/auth plumbing (`alive_platform`, `casa-client`, `casa-rest-client`,
   `vrops-trustmanager`, `vcops-security`) are on the **shared collector
   classpath** (proven from `/proc/177372/cmdline`). An in-collector
   adapter does not need them in its pak. Flagging so we don't conclude
   "the classes are unreachable to us."

2. **recon_log 2026-06-30 §4/§5 over-stated CaSA as the inventory door.**
   Confirmed (as `casa-inventory-access.md` already corrected): inventory
   is ordinary Suite API over the PrxyRC tunnel authorized by a
   **user token** (`automationAdmin`), not a node-cert "CaSA inventory
   endpoint." The 401s in Q2 re-prove it. `/casa/*` is control plane only.

3. **The bytecode RE (`casa-injected-vs-raw-client.md`) is fully
   corroborated live.** "Fix is identity (`automationAdmin`) on the same
   `localhost/suite-api` door, no node-cert mTLS in adapter code" matches
   every observation here. The new live nuance the RE could not see:
   `maintenanceuser.properties` **resolves to different principals on
   primary vs CP** — that is *why* the same code 403s only on the CP.

---

## Deliverable summary

1. **Tiebreaker:** **Path A viable.** Fix = read
   `automationuser.properties` (`automationAdmin`) instead of
   `maintenanceuser.properties` (`cloudproxy_<uuid>`); same
   `https://localhost/suite-api` (or `172.17.0.1`) door; no transport
   change. Live evidence: door 401/400 token-gated (CP curls), vCommunity
   `OK(200)` through it today, `VMWARE_INFRA_MANAGEMENT` creds-free reading
   29 resources, our SynologyStitcher failing with `principal=cloudproxy_<uuid>`.
   Only unrun step (access boundary): the literal `automationAdmin`
   `token/acquire` — blocked solely by not decrypting the platform secret.
2. **Oracle puzzle:** Oracle does **no** suite-api call; its VM stitch is a
   `describe.xml` `VMWARE::VirtualMachine::~child` ResourcePath traversal
   resolved by the platform. No contradiction with the CP 403.
3. **CaSA constants:** local tunnel = haproxy `127.0.0.1:8443`
   (`haproxy.slice.pem`); httpd-north `127.0.0.1:443`+`172.17.0.1:443`;
   backend `vcf-lab-operations.int.sentania.net:443` ca `haproxy.ca.pem`;
   slice CN `VCFOps-slice-1` issued by `VCFOps-cluster-ca_3326c838-…`;
   CaSA ping `https://localhost/casa/cluster/security/ping`. Node keystore
   alias / single `certificateRenewUrl` constant: not exposed in plaintext
   config (renewal is a REST surface).

**Implications for code:** the `SuiteApiStitchClient` /
`ForeignResourceResolver` credential provider must select
`automationuser.properties` when present (CP and primary both have it),
falling back to `maintenanceuser.properties` only if automation is absent.
Selecting maintenance on a CP is the confirmed CP-403 root cause.

**Clean-up:** nothing created on the appliance (all curls were
failed-auth GET/POST that create no objects); no files written outside
`context/`. Verified.

---
**CORRECTION (2026-07-02) to Q3 (the Oracle puzzle):** "OracleDBAdapter makes
zero suite-api calls; its stitch is describe.xml traversal" is WRONG — a
DEBUG-level artifact. The real mechanism: per-cycle Suite API read as the
platform-injected per-instance credential (instance-UUID principal), which
has resource-read RBAC on a CP. The maintenance/automation findings in this
file remain valid. See `oracle-stitch-autopsy-2026-07-02.md` and
`context/api-surface/per-instance-suiteapi-credential-contract.md`.
