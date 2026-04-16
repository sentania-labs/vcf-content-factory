---
date: 2026-04-15
type: reference
category: reference-doc
source: web-research, live-tested
trust: external
reviewed: false
status: filed
last_verified: 2026-04-16
sources:
  - url: https://global.download.synology.com/download/Document/Software/DeveloperGuide/Os/DSM/All/enu/DSM_Login_Web_API_Guide_enu.pdf
    domain: synology.com
    type: vendor-doc
  - url: https://kb.synology.com/en-global/DG/DSM_Login_Web_API_Guide/2
    domain: synology.com
    type: vendor-doc
  - url: https://www.synology.com/en-us/support/developer
    domain: synology.com
    type: vendor-doc
  - url: https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/FileStation/All/enu/Synology_File_Station_API_Guide.pdf
    domain: synology.com
    type: vendor-doc
  - url: https://gist.github.com/ivaniskandar/5c9d00d7577b49c43ce960a18971ab81
    domain: github.com
    type: community
  - url: https://github.com/kwent/syno
    domain: github.com
    type: community
  - url: https://github.com/N4S4/synology-api
    domain: github.com
    type: community
  - url: https://n4s4.github.io/synology-api/docs/apis
    domain: github.io
    type: community
  - url: https://blog.jbowen.dev/synology/photostation/references/errors/
    domain: jbowen.dev
    type: blog
topics: [vcf-ops, monitoring]
tags: [synology, management-pack, mpb, rest-api]
---

# Synology DSM Web API Reference

> **Revision note (2026-04-16):** Several API namespaces in the storage and backup sections were corrected against live API testing on a DS1520+ running DSM 7.3.2-86009 Update 1. Corrected sections are marked. See also the live-tested brief at `workspaces/sentania-lab-toolkit/docs/reference-synology-api-mp-brief.md`.

## Overview

Synology DiskStation Manager (DSM) exposes a comprehensive REST-style Web API over HTTP/HTTPS. The API is used internally by the DSM web UI and is available for third-party integration. Synology officially documents only a subset of the APIs (Login, File Station, Download Station, Calendar, SSO Server). The majority of SYNO.* namespaces are undocumented but discoverable and stable enough for community projects to rely on. Live API discovery on a DS1520+ running DSM 7.3.2 returned **674 APIs** — community documentation referencing "300+" is an undercount of the full namespace set on modern DSM.

## Official Documentation Sources

Synology publishes developer guides as PDFs from their [Developer portal](https://www.synology.com/en-us/support/developer):

- [DSM Login Web API Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Os/DSM/All/enu/DSM_Login_Web_API_Guide_enu.pdf) (last updated April 2023, based on DSM 7.0)
- [File Station API Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/FileStation/All/enu/Synology_File_Station_API_Guide.pdf)
- [Download Station Web API](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/DownloadStation/All/enu/Synology_Download_Station_Web_API.pdf)
- [Calendar API Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/Calendar/All/enu/Calendar_API_Guide_enu.pdf)
- [SSO Server Development Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/SSOServer/All/enu/Synology_SSO_API_Guide.pdf)
- [SNMP MIB Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Firmware/DSM/All/enu/Synology_DiskStation_MIB_Guide.pdf) (last updated March 2025)

The [Synology Knowledge Center developer guide section](https://kb.synology.com/en-sg/search?sources%5B%5D=developer_guide) also hosts these in HTML form but content rendering can be inconsistent.

## API Endpoint Structure

### Base URL

All API requests go to:
```
http(s)://<NAS_IP>:<PORT>/webapi/<CGI_PATH>
```

Default ports: 5000 (HTTP), 5001 (HTTPS).

### CGI Paths

Three primary CGI endpoints:
- `/webapi/query.cgi` -- used exclusively for `SYNO.API.Info` (API discovery)
- `/webapi/auth.cgi` -- used for `SYNO.API.Auth` (older DSM versions; DSM 6+ uses entry.cgi)
- `/webapi/entry.cgi` -- the main endpoint for all API calls in DSM 6+

### Request Parameters

Every API call requires three core parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `api` | The API namespace name | `SYNO.Core.System.Utilization` |
| `method` | The method to call within the API | `get` |
| `version` | The API version number | `1` |

Additional parameters are method-specific. Parameters can be passed as query strings (GET) or form data (POST).

### Response Format

All responses are JSON with this structure:
```json
{
  "success": true,
  "data": { ... }
}
```

On error:
```json
{
  "success": false,
  "error": {
    "code": 119
  }
}
```

## API Discovery (SYNO.API.Info)

Before calling any API, query the NAS to discover what APIs are available and their current versions:

```
GET /webapi/query.cgi?api=SYNO.API.Info&version=1&method=query&query=all
```

This returns every available API with its `path`, `minVersion`, and `maxVersion`. This is essential because:
- Different DSM versions expose different APIs
- Installed packages add new API namespaces
- API versions increment across DSM updates

Example response entry:
```json
{
  "SYNO.API.Auth": {
    "path": "entry.cgi",
    "minVersion": 1,
    "maxVersion": 7,
    "requestFormat": "JSON"
  }
}
```

## Authentication

### Login Flow

1. **Query SYNO.API.Info** to confirm SYNO.API.Auth is available and get its current version
2. **Call SYNO.API.Auth login method**:

```
GET /webapi/entry.cgi?api=SYNO.API.Auth&version=7&method=login&account=<USER>&passwd=<PASS>&session=<SESSION_NAME>&format=sid
```

> **Note:** Example uses version=7 (max on DSM 7.3.2). Use version=6 as fallback if targeting mixed DSM 6/7 environments.

Key parameters:
- `account` / `passwd` -- credentials
- `session` -- arbitrary session name (e.g., "MonitoringSession")
- `format` -- `cookie` (set session in HTTP cookie) or `sid` (return session ID in JSON response)
- `otp_code` -- required if 2-factor authentication is enabled
- `enable_syno_token` -- set to `yes` to get a CSRF SynoToken

3. **Use the session ID** in subsequent requests:
   - As query parameter: `&_sid=<SESSION_ID>`
   - As cookie: `id=<SESSION_ID>`

### Session Management

- Sessions expire after **7 days** by default
- Sessions can be terminated by duplicate logins (error 107)
- To logout: call `SYNO.API.Auth` with `method=logout&session=<SESSION_NAME>`
- Without cookie: pass `_sid` parameter to logout

### CSRF Protection (SynoToken)

When CSRF protection is enabled on the NAS:
- Request a SynoToken during login by setting `enable_syno_token=yes`
- Include the token in subsequent requests as:
  - Query parameter: `&SynoToken=<TOKEN>`
  - HTTP header: `X-SYNO-TOKEN: <TOKEN>`

### DSM 7.x Authentication Changes

> **Live-tested correction:** On DSM 7.3.2, `SYNO.API.Auth` reports `maxVersion: 7`. Version 7 is the recommended auth version for DSM 7.x; v6 works as a fallback for backward compatibility. Earlier documentation recommending v6 as the primary target was based on community docs, not live testing.

- SYNO.API.Auth supports versions 1-7 on DSM 7.3.2; **version 7 is the maximum** (v6 also works as fallback)
- DSM 7.2 introduced an additional `ik_message` parameter (encoded timestamp) in some authentication flows
- The core authentication mechanism remains backward-compatible from DSM 6 to DSM 7
- API path consolidated: DSM 7 uses `entry.cgi` exclusively (older versions had separate `auth.cgi`)

### Two-Step Authentication (2SA)

If the account has 2SA enabled:
- The initial login returns an error indicating 2SA is required
- Re-submit the login with the `otp_code` parameter containing the TOTP code
- Device tokens can be used to skip 2SA on trusted devices after initial verification

## API Versioning

- Each API independently tracks `minVersion` and `maxVersion`
- Use `SYNO.API.Info` to discover the supported range
- Always request a specific version; the NAS will reject requests for unsupported versions
- Higher versions generally add parameters but maintain backward compatibility

## Key API Namespaces

Based on [SYNO.API.Info query=all responses from DSM 6.x](https://gist.github.com/ivaniskandar/5c9d00d7577b49c43ce960a18971ab81) and the [N4S4 synology-api documentation](https://n4s4.github.io/synology-api/docs/apis), the major namespaces are:

### Core System
- `SYNO.API.Info` -- API discovery (v1)
- `SYNO.API.Auth` -- Authentication (v1-7; v7 max on DSM 7.3.2)
- `SYNO.API.Encryption` -- Encryption info (v1)
- `SYNO.Core.System` -- Reboot, shutdown, system info (v1-3)
- `SYNO.Core.System.Status` -- Operational state
- `SYNO.Core.System.Utilization` -- CPU/memory/network/disk utilization (v1). **Live-tested:** also returns `lun[]` array with per-iSCSI-LUN IOPS, throughput, and latency — critical for ESXi-to-storage mapping. See monitoring metrics doc for full field list.
- `SYNO.Core.System.Process` -- Running processes
- `SYNO.Core.System.ProcessGroup` -- Process grouping
- `SYNO.Core.System.SystemHealth` -- System integrity

### Hardware
- `SYNO.Core.Hardware.FanSpeed` -- Fan speed monitoring
- `SYNO.Core.Hardware.PowerRecovery` -- Power recovery settings
- `SYNO.Core.Hardware.BeepControl` -- Beep/buzzer control
- `SYNO.Core.Hardware.DCOutput` -- DC output control

### Storage

> **Live-tested correction:** `SYNO.Core.Storage.Volume`, `SYNO.Core.Storage.Disk`, and `SYNO.Core.Storage.Pool` do not exist on DSM 7.3.2. The actual storage APIs are under `SYNO.Storage.CGI.*`. The primary call is `SYNO.Storage.CGI.Storage` method `load_info`, which returns all storage data (disks, pools, volumes, SSD caches, SMART basics) in a single response.

- `SYNO.Storage.CGI.Storage` `load_info` -- **Primary storage API.** Returns disks, pools, volumes, SSD caches, SMART status all in one call. Replaces separate disk/pool/volume calls.
- `SYNO.Storage.CGI.Volume` -- Volume-level operations (subset of what `load_info` provides)
- `SYNO.Storage.CGI.Pool` -- Pool-level operations (subset of what `load_info` provides)
- `SYNO.Storage.CGI.HddMan` -- Hard drive management settings (bad sector threshold, health config)
- `SYNO.Storage.CGI.Smart` -- Detailed SMART data (requires specific disk parameter format; basics already in `load_info`)
- `SYNO.Core.ISCSI.LUN` -- iSCSI LUNs
- `SYNO.Core.ISCSI.Target` -- iSCSI targets
- `SYNO.Core.ISCSI.Node` -- iSCSI initiator nodes

### Networking
- `SYNO.Core.Network` -- Network configuration
- `SYNO.Core.Network.Bond` -- Network bonding
- `SYNO.Core.Network.Bridge` -- Network bridging
- `SYNO.Network.DHCPServer` -- DHCP services

### File Services
- `SYNO.Core.FileServ.FTP` -- FTP configuration (v1-3)
- `SYNO.Core.FileServ.SMB` -- SMB/CIFS configuration (v1-3)
- `SYNO.Core.FileServ.NFS` -- NFS configuration (v1-2)
- `SYNO.Core.FileServ.AFP` -- AFP configuration (v1-2)

### External Devices
- `SYNO.Core.ExternalDevice.Storage.USB` -- USB storage devices
- `SYNO.Core.ExternalDevice.UPS` -- UPS status and configuration

### Packages & Services
- `SYNO.Core.Package` -- Installed packages
- `SYNO.Core.Service` -- System services
- `SYNO.Core.Share` -- Shared folders
- `SYNO.Core.Share.Crypto` -- Encrypted shares

### Security
- `SYNO.Core.Security.Firewall` -- Firewall configuration (v1)
- `SYNO.Core.Security.DSM` -- DSM security settings (v1-4)
- `SYNO.SecurityAdvisor.Report` -- Security advisor reports (v1)

### Backup

> **Live-tested correction:** `SYNO.Backup.Task` is not the correct namespace for Active Backup for Business. The actual backup API tree on DSM 7.3.2 is `SYNO.ActiveBackup.*`. The `SYNO.Backup.*` namespace may exist for older Hyper Backup tasks, but Active Backup operations use the `SYNO.ActiveBackup.*` namespace.

- `SYNO.ActiveBackup.Task` -- Active Backup for Business tasks (primary backup API on DSM 7.3.2)
- `SYNO.ActiveBackup.*` -- Full Active Backup namespace tree
- `SYNO.Backup.Task` -- Hyper Backup tasks (older backup package; separate from Active Backup for Business)
- `SYNO.Backup.Repository` -- Backup repositories

### Containers & Virtualization
- `SYNO.Docker.Container` -- Docker container management
- `SYNO.Docker.Image` -- Docker image management
- `SYNO.Virtualization.API.Guest` -- Virtual Machine Manager

### Surveillance
- Surveillance Station APIs (separate package, extensive set)

### File Station (25+ APIs)
- `SYNO.FileStation.List` (v1-2), `SYNO.FileStation.Download` (v1-2), `SYNO.FileStation.Upload` (v2-3), `SYNO.FileStation.Search` (v1-2), `SYNO.FileStation.Sharing` (v1-3), and many more

### Download Station
- `SYNO.DownloadStation.Task` (v1-3), `SYNO.DownloadStation2.Task.BT` (v1-2), `SYNO.DownloadStation2.Settings.Global` (v2)

## Error Codes

### Common API Error Codes

From the [official API guides](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/FileStation/All/enu/Synology_File_Station_API_Guide.pdf) and [community documentation](https://blog.jbowen.dev/synology/photostation/references/errors/):

| Code | Constant | Description |
|------|----------|-------------|
| 100 | `WEBAPI_ERR_UNKNOWN` | Unknown error |
| 101 | `WEBAPI_ERR_BAD_REQUEST` | No parameter of API, method, or version |
| 102 | `WEBAPI_ERR_NO_SUCH_API` | The requested API does not exist |
| 103 | `WEBAPI_ERR_NO_SUCH_METHOD` | The requested method does not exist |
| 104 | `WEBAPI_ERR_NOT_SUPPORTED_VERSION` | The requested version is not supported |
| 105 | `WEBAPI_ERR_NO_PERMISSION` | The logged-in session does not have permission |
| 106 | `WEBAPI_ERR_SESSION_TIMEOUT` | Session timeout |
| 107 | `WEBAPI_ERR_SESSION_INTERRUPT` | Session interrupted by duplicate login |
| 119 | (SID not found) | Session ID not found / invalid |

API-specific error codes start at 400+ and vary per API namespace.

## Rate Limits and Pagination

### Rate Limits

Synology does not document explicit rate limits on the API. However:
- The NAS has limited CPU/memory; aggressive polling will degrade performance
- A collection interval of 5 minutes is reasonable for monitoring
- Avoid querying SMART data more than every 15-30 minutes (disk I/O impact)

### Pagination

APIs that return lists (File Station, etc.) support pagination via:
- `offset` -- starting index (0-based)
- `limit` -- maximum number of records to return

System utilization APIs return current-state data and do not require pagination.

## DSM 7.x vs 6.x API Differences

| Aspect | DSM 6.x | DSM 7.x |
|--------|---------|---------|
| Auth API versions | v1-6 | v1-7 (v7 is max on DSM 7.3.2; v6 also works) |
| Primary CGI path | `entry.cgi` (+ `auth.cgi` legacy) | `entry.cgi` exclusively |
| CSRF token | Optional | May be enforced depending on config |
| 2SA support | Basic | Enhanced with device tokens |
| `ik_message` param | Not present | Added in DSM 7.2 |
| Package APIs | Vary by package version | Some namespaces reorganized |
| Storage APIs | `SYNO.Core.Storage.*` | `SYNO.Storage.CGI.*` — **Note: `SYNO.Core.Storage.*` not present on DSM 7.3.2** |

> **Live-tested note:** `SYNO.Core.Storage.Volume/Disk/Pool` APIs from community docs do not appear on DSM 7.3.2. Use `SYNO.Storage.CGI.Storage` `load_info` instead. Total APIs on DSM 7.3.2: **674** (not 300+ as community docs suggest).

The core authentication and request structure is backward-compatible. Most code written for DSM 6 works on DSM 7 without modification.

## Community Documentation and Wrappers

### Python Libraries
- [N4S4/synology-api](https://github.com/N4S4/synology-api) -- 300+ APIs, 533 stars, MIT license, latest v0.8.2 (Dec 2025)
- [mib1185/py-synologydsm-api](https://github.com/mib1185/py-synologydsm-api) -- async Python, used by Home Assistant, latest v2.8.0 (Apr 2026)
- [hacf-fr/synologydsm-api](https://github.com/hacf-fr/synologydsm-api) -- archived Feb 2025, succeeded by mib1185

### Node.js Libraries
- [kwent/syno](https://github.com/kwent/syno) -- Node.js wrapper with full API definition files for DSM 5.x and 6.x (useful for discovering method signatures)

### API Definition Files
The [kwent/syno definitions directory](https://github.com/kwent/syno/tree/master/definitions) contains `.lib` files that map every SYNO.* namespace to its methods, versions, and access levels. These were extracted from DSM itself and serve as the closest thing to a complete API reference for undocumented APIs.

### Complete API List (DSM 6.x)
A [GitHub Gist by ivaniskandar](https://gist.github.com/ivaniskandar/5c9d00d7577b49c43ce960a18971ab81) contains the full `SYNO.API.Info query=all` response from DSM 6, listing 800+ API namespaces with paths and version ranges.

## Practical Notes for Management Pack Development

1. **Always start with SYNO.API.Info query=all** to discover what's available on the target NAS — DSM 7.3.2 returns 674 APIs
2. **Use SYNO.API.Auth v7** for authentication on DSM 7.x (v7 is max on 7.3.2); use v6 as fallback for older DSM versions
3. **Use `format=sid`** rather than cookies for API-based integrations (simpler session management)
4. **Use `entry.cgi`** as the single CGI endpoint for all API calls
5. **Session lifetime is 7 days** -- implement session refresh logic; re-auth on error codes 106 and 119
6. **Error handling**: check `success` field first, then `error.code` for specific handling
7. **Storage data**: use `SYNO.Storage.CGI.Storage` `load_info` (single call returns disks, pools, volumes, caches, SMART) — do NOT use `SYNO.Core.Storage.*` (not present on DSM 7.3.2)
8. **Backup monitoring**: use `SYNO.ActiveBackup.*` namespace, not `SYNO.Backup.Task`, for Active Backup for Business
9. **Most monitoring APIs use the `get` method** with no required parameters beyond the session
