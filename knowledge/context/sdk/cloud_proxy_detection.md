# Telling a Cloud Proxy from an analytics node, from inside an adapter

Investigated 2026-10-28 by `tooling` for compliance#58. Read-only SSH and GETs
only. UNKNOWN means not established.

**Answer.** Read `/usr/lib/vmware-vcops/user/conf/collector/collector.properties`.
The collector is a Cloud Proxy when `isUnifiedCloudProxy=true` or
`httpRelayEnabled=true`. A missing or unreadable file, or neither key true,
means "not known to be a proxy". The framework uses this rule in
`AmbientCredential.isCloudProxy` (buildkit 1.0.22).

## Evidence: six devel nodes

`GET /api/collectors` gave the collector types. File reads used SSH as root.
Only key names and role flags were printed; no secret values.

| Node | Version | API `collectorType` | `remote` | `isUnifiedCloudProxy` | `httpRelayEnabled` | `roleState` `remotecollectorroleenabled` |
|---|---|---|---|---|---|---|
| devel-8-collector (172.27.10.15) | 8.18.6 | `CLOUD_PROXY` | true | absent | true | true |
| devel-8 (172.27.10.14) | 8.18.6 | `INTERNAL` | false | absent | absent | false |
| devel-collector (172.27.10.13) | 9.0.2 | `UNIFIED_CLOUD_PROXY` | true | true | true | true |
| devel (172.27.10.12) | 9.0.2 | `INTERNAL` | false | false | absent | false |
| devel-91-collector (172.27.10.11) | 9.1.1 | `UNIFIED_CLOUD_PROXY` | true | true | true | true |
| devel-91 (172.27.10.10) | 9.1.1 | `INTERNAL` | false | false | absent | false |

`roleState.properties` is
`/usr/lib/vmware-vcopssuite/utilities/sliceConfiguration/data/roleState.properties`.
On the nodes the admin, data and UI roles are all enabled; on the proxies all three are disabled.

## What the platform does with these keys (javap, 9.1.1 jars from the proxy)

- `com.integrien.alive.collector.CollectorProperties` (`vcops-collector-1.0-SNAPSHOT.jar`)
  sets `isUnifiedCloudProxy = false` in its constructor and reads it with
  `getBoolean("isUnifiedCloudProxy", isUnifiedCloudProxy)`. It also reads
  `httpRelayEnabled`. The property file's own comment describes the HTTP relay as
  "One-Way collector communication over a single port of the suite api
  tomcat (443)".
- `com.vmware.vrops.collector.CollectorType` (`alive_common.jar`, 9.1.1) has
  `INTERNAL`, `CLOUD_PROXY` and `UNIFIED_CLOUD_PROXY`. `isRemote(t)` returns
  `isCloudProxy(t)`, which is true for either proxy type.
- An older `alive_common.jar` copy in `adapter_runtime/` (May 2026, line not
  recorded) also has a `REMOTE` type, the classic remote collector. That is why
  `remote=true` is **not** used: it may also mean a classic remote collector,
  whose ambient credential behaviour is UNKNOWN.
- The SDK exposes no node-role API. `com.integrien.alive.common.util.Module.isInRemoteCollector()`
  is a fixed per-module enum flag, not the node's role.

## Why it matters: the ambient file credential on a proxy

- No Broadcom adapter on the 9.1.1 proxy reads `automationuser.properties` or
  `maintenanceuser.properties`. A scan of 987 jars found only the platform's
  `ConfigUserUtils` and our `vcfcf-adapter-base.jar`.
- The file credentials do not authenticate from a Cloud Proxy (DEF-006;
  `knowledge/lessons/cross-mp-stitch-cp-identity-and-edge-mechanics.md`).
  On devel 9.1 the automation password does not even decrypt there.
- `com.vmware.vcops.security.Crypt.decrypt_impl_v2` (`vcops-security-1.0-SNAPSHOT.jar`)
  catches its own `Exception`, logs `Crypt.decrypt_impl_v2: <message>` at
  ERROR (the "pad block corrupted" line), logs the trace at INFO, and returns
  null. The caller cannot stop the ERROR line after calling it; only not
  calling it avoids the line. The ciphertext format is `<keyId>:<iv>:<data>`,
  keyed by `user/conf/cluster_master_key.txt`. A pad-block failure means the key
  id matched and the key bytes did not, so a key-id pre-check would not help.
- The file timestamps are not a usable signal. On every proxy,
  `cluster_master_key.txt` is newer than `automationuser.properties`, but the
  same holds on the 9.0.2 node, where the file is from April and the key is from October.

## Open

- A classic remote collector (`REMOTE` type) was not available to test.
- `httpRelayEnabled=true` on an analytics node was not seen. If it occurs,
  that node also skips the file credentials. Collection there still uses
  the injected per-instance credential.
