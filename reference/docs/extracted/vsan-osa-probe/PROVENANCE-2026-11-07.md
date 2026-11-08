# Provenance: vSAN OSA probe captures (2026-11-07)

Verbatim server responses captured by `api-cartographer` for the OSA
(disk-group) question. Digest: `knowledge/context/api-maps/vsan-osa-host-side.md`.
Immutable under RULE-016; later rounds get their own PROVENANCE file.

## Source

- **vCenter:** `vcf-lab-vcenter-mgmt.int.sentania.net`, `VMware vCenter Server 9.1.1.0100.25784172`, apiVersion 9.1.1.0.
- **OSA cluster:** `vcf-lab-osa-probe-cl01`, MoRef `domain-c39146`, vSAN OSA (`vsanEsaEnabled=false`), vSAN cluster uuid `526f5c80-5b92-4464-0c7a-2a2c74fc2d27`, 3 hosts `vcf-lab-osa-esx01/02/03` (`host-39158`, `host-39155`, `host-39160`), all `VMware ESXi 9.0.0.0.24755229`. One all-flash disk group per host: one 50 GiB NVMe cache disk, one 500 GiB NVMe capacity disk (virtual NVMe, nested hosts).
- **ESA cluster (comparison):** `vcf-lab-mgmt-cl01`, `domain-c6004`, uuid `90d067b8-0077-11f1-af60-000c297e270a`, 5 hosts ESXi 9.1.1.0100.25782009; host-side calls on esx01 `host-6017`.
- **Captured:** 2026-11-07 18:41 to 18:50 America/Chicago (2026-11-08 00:41 to 00:50 UTC).

## Transport

Raw HTTPS from Python `http.client`, vSphere JSON API, release id `8.0.3.0`,
headers `vmware-api-session-id` and `Accept-Encoding: gzip`. Login
`SessionManager/SessionManager/Login`, Logout `204` at the end of every session.
Credentials read in-process from the factory `.env` (`VCENTER_*`); never on
argv, never written.

| Prefix | Path pattern |
|---|---|
| `01`..`05` | `POST /sdk/vim25/8.0.3.0/vsan/<VsanVcClusterConfigSystem\|VsanPerformanceManager>/<moid>/<Method>` |
| `10`..`16` | `POST /sdk/vim25/8.0.3.0/vsan/<VimClusterVsanVcDiskManagementSystem\|VsanSpaceReportSystem\|VsanVcClusterHealthSystem\|VsanObjectSystem>/<moid>/<Method>` |
| `20`..`25` | `POST /sdk/vim25/8.0.3.0/HostVsanInternalSystem/ha-vsan-internal-system-<n>/<Method>`, `GET .../HostVsanSystem/vsanSystem-<n>/config`, `POST .../HostVsanSystem/vsanSystem-<n>/QueryHostStatus` |
| `30` | `POST /sdk/vim25/8.0.3.0/InternalDynamicTypeManager/DynamicTypeManager-<n>/DynamicTypeMgrQueryTypeInfo` with `typeSubstr` `vim.EsxCLI.vsan` |
| `40` | `POST /sdk/vim25/8.0.3.0/ReflectManagedMethodExecuter/ManagedMethodExecuter-<n>/ExecuteSoap`, `moid` `ha-cli-handler-<ns>`, `version` `urn:vim25/5.0`, no arguments |
| `50`..`53` | vSphere Automation REST: `POST /api/session` (basic auth), `GET /api/vapi/metadata/metamodel/{package,component,service}`, `GET /api/vcenter/cluster/domain-c39146`, `DELETE /api/session` |

`06-perfgetsupportedentitytypes.json.gz` is `VsanPerfGetSupportedEntityTypes` with body `{}` (version-wide, no cluster), captured 18:5x local after the rest.

Request bodies are as named in the file name; the `05-*` and `04-*` QueryPerf
bodies used one wildcard spec, 7-minute UTC window, cluster MoRef, no labels.
`12-*` used `fetchFromCache: true`; `16-*` added `fields: ["physicalDisksHealth"]`.
`24-*` passed a 16-name `props` list (see the file for the names returned).
`25-*-t0` and `-t60` are the same `QueryVsanStatistics` call 60 s apart.

## Files

Each `.json` is the gunzipped server body, byte for byte, server pretty-printing
kept. HTTP 500 faults are saved like any other body. `QueryVsanStatistics`
returns a JSON string whose content is itself JSON; it is saved as returned.
`ExecuteSoap` bodies carry the esxcli result as an XML-escaped string in
`response` (or `fault`). Bodies over 300 KB are stored gzip-compressed
(`gzip -9 -n`), content unchanged: `06-perfgetsupportedentitytypes.json.gz`, `12-esa-healthsummary-cached.json.gz`, `20-esa-host-6017-queryvsanstatistics-dom-objects.json.gz`, `21-esa-host-6017-queryphysicalvsandisks.json.gz`, `30-host-39158-typeinfo-vsan.json.gz`, `30-host-6017-typeinfo-vsan.json.gz`.

Not included: anything generated (method lists, summaries, timings); those live
in the digest.

## Redactions

None needed. The session id traveled only in a request header and appears in
no response. All 136 working files were scanned in-process for the vCenter
password, the account name, and session-token patterns: zero matches. The
REST metamodel files are the vendor's public service catalogue.

## Read-only

Only Login/Logout, property GETs, query/retrieve methods, and esxcli `get`/`list`
commands were issued. Nothing was enabled, started, or configured. The vSAN
health summary was read from cache (`fetchFromCache: true`); no health run was
triggered from vCenter. `esxcli vsan health cluster list` does run the host-side
checks when called (57 s on the OSA host, 31 s on the ESA host).
