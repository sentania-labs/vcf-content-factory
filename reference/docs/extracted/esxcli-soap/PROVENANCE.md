# Provenance: esxcli over the vSphere SOAP endpoint (ReflectManagedMethodExecuter)

Verbatim server responses captured for
`knowledge/context/api-maps/esxi-esxcli-over-soap.md`. Added 2026-11-07 by
api-cartographer. Add-only under RULE-016; corrections go in the map.

## Sources

- **vCenter:** vcf-lab-vcenter-mgmt.int.sentania.net, VMware vCenter Server
  9.1.1.0100 build 25784172 (apiVersion 9.1.1.0). The two workload vCenters
  (wld01, wld02) run the same build; wld01 supplied file 44 only.
- **Hosts:** every ESXi host on all three vCenters is VMware ESXi 9.1.1.0100
  build 25782009 (`system version get`: Version 9.1.1, Update 1, Patch 0100,
  Build Releasebuild-25782009). Captures 01 to 38 are from
  vcf-lab-mgmt-esx01.int.sentania.net (`host-6017`, cluster
  `vcf-lab-mgmt-cl01`). No 8.0.3 host exists in the lab.
- **Captured:** 2026-11-07 13:42 to 13:52 UTC (07:42 to 07:52 America/Chicago).
- **Transport:** raw HTTPS from Python `http.client`, no SDK. SOAP POSTs to
  `https://<vCenter>/sdk` with the vCenter `vmware_soap_session` cookie from
  `SessionManager.Login`; `SOAPAction: "urn:vim25/5.0"` on executer calls
  (`urn:vim25/8.0.3.0` on the others); `Accept-Encoding: gzip`. File 50 is
  the vim25 JSON API (`/sdk/vim25/8.0.3.0/...`, `vmware-api-session-id`
  header). Every session was logged out except one, which the probe script
  left behind when it crashed at 13:43 UTC. It was left to expire when idle.
- **Read-only.** The calls issued were Login, Logout, RetrieveServiceContent,
  RetrievePropertiesEx, Create/DestroyView, AcquireCloneTicket,
  AcquireGenericServiceTicket (faulted), HostSystem.AcquireCimServicesTicket,
  host-side RetrieveServiceContent and CloneSession (faulted),
  RetrieveDynamicTypeManager, RetrieveManagedMethodExecuter,
  DynamicTypeMgrQueryTypeInfo, DynamicTypeMgrQueryMoInstances,
  QueryAvailablePerfMetric, and ExecuteSoap for esxcli `get`/`list`
  commands only. No `set` command was sent. Tickets and sessions were
  created and no configuration changed.

## Files

Bodies are the gunzipped server output, byte for byte (full SOAP envelope),
except for the two redactions below. `.gz` files are gzip of the same output
(the type tree is 1.73 MB decoded, the counter list 435 KB, the host metric
list 336 KB).

| Prefix | What | Request |
|---|---|---|
| `00-01` to `00-12` | Route probes (map §Route) | as named; 00-02 host `/sdk`, 00-06/07 host `/sdk` with the CIM ticket cookie, the rest vCenter `/sdk` |
| `00-dynamictypemgr-*` | Full esxcli type tree and MO instance list | `DynamicTypeMgrQueryTypeInfo` / `DynamicTypeMgrQueryMoInstances` on `DynamicTypeManager-6017`, no filter |
| `01`-`18` | Command set on esx01 | `ExecuteSoap` on `ManagedMethodExecuter-6017`, moid `ha-cli-handler-<ns>`, version `urn:vim25/5.0`, method `vim.EsxCLI.<cmd>`; per-NIC files carry the `-vmnicN` suffix |
| `19`-`27` | Extra reads (per-NIC queue args, missing-arg fault, hwCap, software, ip interface, i40en params, DVS list, ENS lcores) | same |
| `30`-`35` | VM port tier and module params | `network vm list`, `network vm port list -w`, `network port stats get -p`, `network port filter stats get -p`, `system module parameters list -m`, `vim.CLIInfo.FetchCLIInfo` |
| `36`-`38` | Executer reach beyond esxcli (faults) | moid `ha-host`, `ha-cli-handler-vsish`, `ha-dynamic-type-manager-python` |
| `40`, `44` | vmxnet3 VMX keys via vim25 | `RetrievePropertiesEx` with keyed paths `config.extraConfig["ethernet0.<key>"]` (40: vm-17001 on mgmt, `config.hardware.device[4000]` too; 44: vm-5017 `vcf-lab-wld01-en01` on wld01) |
| `41`, `42` | vCenter perf counters | `PerformanceManager.perfCounter`; `QueryAvailablePerfMetric` intervalId 20 for vm-17001 and host-6017 |
| `50` | JSON transport proof | `POST /sdk/vim25/8.0.3.0/ReflectManagedMethodExecuter/ManagedMethodExecuter-6017/ExecuteSoap` |

## Redactions

- `00-01`: the `AcquireCloneTicket` return value (`cst-VCT-...`) replaced by
  `<REDACTED>`.
- `00-05`: the `AcquireCimServicesTicket` `sessionId` value replaced by
  `REDACTED`. The host thumbprint is kept.
- Session cookies and tokens never appear in response bodies. Every file was
  scanned for the vCenter and Ops passwords, the vCenter username,
  `vmware_soap_session`, `vmware_cgi_ticket`, `cst-VCT-`, unredacted
  `sessionId` values and `guestinfo.ovfEnv`/`userdata`: no hits.
- **Not captured on purpose:** full `config.extraConfig` reads. On these
  appliances they carry `guestinfo.ovfEnv` and `guestinfo.userdata`, which
  can hold credentials. Files 40 and 44 use keyed paths that return only the
  named `ethernet0.*` keys.
- Bodies keep lab hostnames, MAC addresses, VM names, PCI ids and the host
  SSL thumbprint.

## Run cut short

The coordinator cut scope on 2026-11-07 at about 13:53 UTC (Scott: the
vmxnet3 ring and out-of-buffer figures are unreachable, and no network pak is
planned). No calls were made after the cut. Every capture listed above was
taken before it. Planned steps that did not run:

- Least-privilege test with a scoped vCenter account (needs a role write,
  never in scope); the privilege in the map is inferred.
- 8.0.3 and 9.0 host comparison of the type tree (no such host in the lab).
- `network nic vlan stats get` with data (VLAN stats are disabled on every
  NIC; enabling them is a `set`, a write).
- Parallel timing of the VM-port tier, and any multi-vCenter or large-cluster
  throughput ceiling.
- Re-capture of the full-tree `typeSubstr` filter and of the CLIInfo
  metadata for commands other than `network.port.stats`.

Final scan before hand-off (grep, case-insensitive, all files including `.gz`):
`vmware_soap_session` appears only in this file (as a cookie name);
`ticket` only in element names (`AcquireCloneTicketResponse`,
`AcquireCimServicesTicketResponse`) next to redacted values; `password` only
in the `InvalidLogin` fault text of `00-02` and as esxcli parameter and field
names in the type tree. No cookie, ticket or credential value is present.
