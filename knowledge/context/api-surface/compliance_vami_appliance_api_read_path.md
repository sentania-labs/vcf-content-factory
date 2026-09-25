# Compliance adapter: why the five vCenter VAMI controls are unreadable (devel, SCG 9.1)

**Date:** 2026-09-23, investigated 3:50 PM to 4:40 PM CDT.
**Investigator:** api-explorer. **Posture:** read-only. Root SSH to devel for log
and `/proc` reads, one read-only Suite API GET pair (adapter instances + credential
*username*; password field redacted and never read), unauthenticated probes of
vCenter wld01 (no credentials sent, nothing created). No writes to VCF Ops or vCenter.
**Subject:** compliance pak 0.0.0.69 (installed ~2:12 PM CDT), profile SCG 9.1,
vCenter 9.1.1-25712839 on vcf-lab-vcenter-{mgmt,wld01,wld02}.int.sentania.net.
**Vendor source added (verbatim, RULE-016 addition):**
`reference/docs/vcenter-9.1.1-appliance-api.json`, fetched unauthenticated from
`https://vcf-lab-vcenter-wld01.int.sentania.net/apiexplorer/json/appliance.json`
(Swagger 2.0, "appliance" 2.0.0, 204 paths). Re-fetchable from any vCenter 9.x
at that path.

## Answer

All five fail for a **transport-wide** reason before any field is parsed, and two
of the five recipes (ssh, password-max-age) would still fail after that is fixed:

1. **Authorization (all 3 vCenters, all 5 controls; strong inference, live proof
   pending).** Every instance uses the one credential `vcf@int.sentania.net`, an
   external identity-source user, not `administrator@vsphere.local`. Appliance API
   authorization is not vCenter-role based: it maps to SSO group
   **`SystemConfiguration.Administrators`** (operator and administrator levels both
   map to that group; superAdministrator maps to
   `SystemConfiguration.BashShellAdministrators`), per VCF 9.1 doc
   "Authorization Model Mapping to the vCenter Single Sign-On Domain", Table 1851.
   The 9.1.1 spec documents the failure for `tls/profiles/global`:
   `403 VapiStdErrorsUnauthorized ... "User needs to have operator privileges."`
   The SOAP path works with the same user (hosts, VMs, 972 vCenter advanced
   settings read every cycle), so the password and SSO login are good; only the
   appliance authorization layer differs.
2. **TLS on vcf-lab-mgmt only (possible, UNVERIFIED).** mgmt runs `allowInsecure=false`.
   `VamiApiClient` then uses `SSLContext.getDefault()`, not the
   `getPlatformSslContext()` the SOAP client uses (which is why SOAP works on mgmt).
   What that default trusts is not established:
   - The collector JVM (pid 6190, `/usr/java/jre-vmware-17`) has no
     `javax.net.ssl.trustStore` flag, and JDK `cacerts` holds **0** `sentania` CAs. The
     vCenter chain is `sentania Lab Issuing 2` / `sentania Lab Root 2`.
   - **But** `alive_platform.jar` `com.vmware.vcops.common.util.ssl.DefaultSSLContextSetter.configureAndSetSSLContext()`
     calls `SSLContext.setDefault(vROpsSSL.createSSLContext(SSLOptions.getSSLOptions(ConnectionCategory.VROPS_CLUSTER)))`
     when GemFire SSL is enabled (javap, 4:45 PM CDT). `FederationManager` in
     `vcops-collector-controller` also calls a default setter. So the JVM default is
     likely the intra-cluster (VROPS_CLUSTER) context. Whether that trust store
     contains the lab CA has not been checked.
   Either way, the VAMI client should use the same platform adapter context as SOAP,
   rather than depend on a cluster-category default. wld01 and wld02 run
   `allowInsecure=true` (trust-all), so TLS is not their blocker, and finding (1)
   alone explains all 15 failures.
3. **Recipe defects (evidence: vendor spec + SimpleJson code).**
   `access/ssh:enabled` and `local-accounts/policy:max_days` can never yield a value
   even with a working session. Details per control below.

### Why the logs show nothing

`VamiApiClient` catches every failure (non-2xx session, non-200 GET, exception) and
caches it silently; it has no logger. The latest cycle (4:13 PM CDT) on each instance
shows only the rollup, verbatim:

```
2026-09-23T21:13:24.675Z ... vCenter vcf-lab-vcenter-mgmt.int.sentania.net [VMware_SCG_9.1]: score=25.0% (2 pass, 1 fail, 5 unreadable, 3 total)
2026-09-23T21:13:22.002Z ... vCenter vcf-lab-vcenter-wld01.int.sentania.net [VMware_SCG_9.1]: score=25.0% (2 pass, 1 fail, 5 unreadable, 3 total)
2026-09-23T21:13:20.959Z ... vCenter vcf-lab-vcenter-wld02.int.sentania.net [VMware_SCG_9.1]: score=25.0% (2 pass, 1 fail, 5 unreadable, 3 total)
```

(4:13 PM CDT.) `grep -i "vami\|appliance"` across `ComplianceAdapter_5379/5381/5382.log`
returns 0 lines. No HTTP status, URL or TLS error is recoverable from the adapter logs.
The PKIX traces in `collector.log` belong to the native vmomi client
(`VlsiCertificateException`), not this adapter. (`total` excludes unreadable by
design, so "5 unreadable, 3 total" is not a bug.)

## Client trace (as built, pak 0.0.0.69)

| Aspect | Behaviour |
|---|---|
| Base URL | `ComplianceConfig.baseUrl()` = `https://<vcenter_host>` (port 443) |
| Session | `POST /api/session`, `Authorization: Basic <user:pass>`, body empty; token = JSON string body, quotes stripped. 200/201 accepted. Never `DELETE`d (one leaked session per vCenter per cycle, idle-expires) |
| GET | `GET /api/appliance/<path>`, headers `vmware-api-session-id`, `Accept: application/json`, 30 s timeout. Only 200 accepted |
| TLS | `allowInsecure=true`: trust-all `X509TrustManager`. `false`: `SSLContext.getDefault()`, which the platform may have replaced with the VROPS_CLUSTER context (see finding 2); not the platform adapter context the SOAP client uses |
| Not used | port 5480, `/rest/appliance/...`, root/VAMI-local credentials |
| Mapping | `field == "(list)"`: body must be a JSON array, elements `asString()` comma-joined, empty array returns null (UNREADABLE). Otherwise `SimpleJson.path(field)`; on a non-object body `get(key)` returns null, so a scalar root body is **always** UNREADABLE |

443 `/api/appliance` with an SSO session is the right surface: the vendor SCG 9.1
assessment commands are `Get-CisService com.vmware.appliance.*` (CIS/vAPI over 443,
SSO session). The 5480 `/rest/appliance/logging/forwarding` text in the 9.1 guide
("authenticate with root credentials") is the VAMI-port variant; not needed.

## Endpoints on vCenter 9.1.1 (evidence)

Unauthenticated probe on wld01 (4:26 PM CDT): all five paths return
`401 {"error_type":"UNAUTHENTICATED",...,"id":"com.vmware.vapi.endpoint.method.authentication.required"}`,
while `/api/appliance/bogus-xyz/nothing` returns `404 com.vmware.vapi.rest.httpNotFound`.
The router resolved a method for each path. Caveat: `local-accounts/policy` resolves
only because it matches `local-accounts/{username}` with username `policy`.

| Path (GET) | 9.1.1 spec 200 body | Since |
|---|---|---|
| `/api/appliance/access/ssh` | bare `boolean` (the `/rest` variant wraps as `{"value":bool}`) | 6.7 |
| `/api/appliance/ntp` | `array` of `string` | 6.7 |
| `/api/appliance/timesync` | enum string `DISABLED`/`NTP`/`HOST` | 6.7 |
| `/api/appliance/logging/forwarding` | `array` of `{hostname, port, protocol(TLS/UDP/TCP)}` | 6.7 |
| `/api/appliance/tls/profiles/global` | `{"profile": string}` (401/403 documented; 403 = "needs operator privileges") | **8.0.3.0** |
| `/api/appliance/local-accounts/policy` | **not in spec** | never existed |
| `/api/appliance/local-accounts/global-policy` | `{max_days, min_days, warn_days, ..., managed_at_fleet}`; 9.1 extends PUT to existing users | 6.7 |
| `/api/appliance/local-accounts/{username}` | `{enabled, roles, password_expires_at, max_days_between_password_change, ...}`, 404 if absent | 6.7 |

No path changed between 8.x and 9.x for these endpoints; `tls/profiles/global` does
not exist before 8.0 U3, so the SCG 8.0 `vc.tls-profile` row is UNREADABLE on older 8.0.

## Per control

| Control | Recipe today | Root cause | Fix |
|---|---|---|---|
| vc.ssh | `vami:access/ssh:enabled` | (1)+(2), and **recipe can never read**: body is bare `true`/`false`, `path("enabled")` on a Boolean is null (evidence: spec + `SimpleJson.get`) | Grammar + code: add a root-scalar token, e.g. `vami:access/ssh:(value)`, returning the body itself (Boolean stays Boolean) |
| vc.time | `vami:ntp:(list)` | (1)+(2) only; recipe shape correct | None required to become readable. Two notes: empty array (timesync HOST, no servers) is a definitive 200, currently folds to UNREADABLE; 9.1 control text also wants `timesync == NTP`, unaudited today |
| vc.log-forwarding | `vami:logging/forwarding:(list)` | (1)+(2) only; readable once authorized. Elements are objects, so value becomes Java `Map.toString()` (e.g. `{hostname=..., port=..., protocol=...}`), which passes `(non-empty)` but is ugly | Optional: project a field (`(list).hostname` style) for a clean actual value. Treat 200 + `[]` as FAIL (not configured), not UNREADABLE |
| vc.tls-ciphers | `vami:tls/profiles/global:profile` | (1)+(2) only; recipe correct | None for readability. Separate content issue: 9.1 canonical expects `NIST_2024`, vendor SCG 9.1 baseline is `NIST_2024_TLS_13_ONLY` |
| vc.vami-password-max-age | `vami:local-accounts/policy:max_days` | (1)+(2), and **path does not exist**: after auth it is a lookup of an account named `policy`, i.e. 404 | Recipe: `vami:local-accounts/root:max_days_between_password_change` matches the 9.1 control ("root account password expiration disabled", vendor has no assessment command). Fallback `vami:local-accounts/global-policy:max_days` reads the global default, not root. Expected value for "never expires" (-1 vs 99999 vs field absent) is **unverified**; capture on the wire before setting it |

## Can the credential be made to work, and at what cost

Yes, by an operator, with no code change for the auth part: add
`vcf@int.sentania.net` (or an AD group containing it) to the vsphere.local SSO group
**`SystemConfiguration.Administrators`** on each vCenter (Administration > Single Sign
On > Users and Groups > Groups). Blast radius: there is no read-only appliance role
for SSO principals. Per Table 1851 operator and administrator both come from that
group, so the collection account also gains appliance **write** level (for example
`services.control`, `shutdown.reboot`, firewall and networking changes), not bash
or local-account management. Whether `local-accounts/root` GET needs superAdmin
(`SystemConfiguration.BashShellAdministrators`) is **unknown**; do not grant
BashShellAdministrators for this (SCG `vcenter-9.bashshelladministrators` itself
restricts that group). If `local-accounts/root` returns 403 at admin level,
vc.vami-password-max-age should stay unreadable-by-design with the reason
documented rather than escalate the account.

The VAMI client's TLS context selection should be aligned with SOAP regardless of the
grant. If mgmt still fails after the grant while wld01 and wld02 succeed, that is
finding (2) confirmed.

## Live proof still needed (not run: no vCenter credential exists in the factory env, and the adapter's stored password was deliberately not extracted)

Run by a human in their own terminal, from any host that reaches vCenter. `curl -u user`
with no `:password` prompts silently, so nothing lands in argv or history:

```
V=https://vcf-lab-vcenter-wld01.int.sentania.net
SID=$(curl -sk -u 'vcf@int.sentania.net' -X POST "$V/api/session" | tr -d '"')
for p in ntp access/ssh logging/forwarding tls/profiles/global \
         local-accounts/global-policy local-accounts/root timesync; do
  printf '%s ' "$p"; curl -sk -w ' HTTP %{http_code}\n' \
    -H "vmware-api-session-id: $SID" "$V/api/appliance/$p"
done
curl -sk -X DELETE -H "vmware-api-session-id: $SID" "$V/api/session"; unset SID
```

Hypothesis (1) is confirmed if the session POST returns a token and every GET returns
`403` with `"error_type":"UNAUTHORIZED"`. Repeat as `administrator@vsphere.local` for
the positive control and to capture real bodies (especially `access/ssh` and the
root-account fields). For hypothesis (2), the adapter-side proof is the PKIX
exception once `VamiApiClient` logs its failures (see below).

## What sdk-adapter-author must change

1. `VamiApiClient`: accept the platform `SSLContext` (same selection as
   `ComplianceAdapter.sslSocketFactoryFor`, passed in from `evaluateVamiForVCenter`)
   instead of `SSLContext.getDefault()` when `allowInsecure=false`. Same defect in
   `VCenterApiClient` (Test Connection).
2. `VamiApiClient`: log once per cycle per vCenter the failure class, with no secrets:
   session HTTP status, per-path GET status plus vAPI `error_type`, or exception class
   and message (PKIX, timeout). Without this the next failure is again invisible.
3. `VamiApiClient`: `DELETE /api/session` at end of cycle.
4. Grammar (CANONICAL_SCHEMA.md `vami` row + `readField`): a root-scalar token such as
   `(value)`; optionally a list-projection form for `logging/forwarding`; decide that a
   200 with `[]` under `(non-empty)` is FAIL, not UNREADABLE (it is a definitive answer,
   not a missing read).
5. Profiles (all of `scg_7.0/8.0/9.0/9.1` canonical CSVs): `access/ssh:enabled` to the
   root-scalar form; `local-accounts/policy:max_days` to
   `local-accounts/root:max_days_between_password_change` (expected value pending wire
   capture).
6. Operator step, not code: SSO group membership above, or accept the controls as
   unreadable with the documented reason.
