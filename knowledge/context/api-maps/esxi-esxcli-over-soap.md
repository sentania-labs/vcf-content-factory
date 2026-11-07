# API Map: ESXi esxcli over the vSphere SOAP endpoint (ReflectManagedMethodExecuter)

## Provenance

- **Authored by:** api-cartographer
- **Target instance:** vcf-lab-vcenter-mgmt.int.sentania.net:443 (vCenter 9.1.1.0100 build 25784172), hosts of cluster `vcf-lab-mgmt-cl01` (esx01 to esx05, `host-6017`, `host-6015`, `host-6011`, `host-15151`, `host-31189`) plus standalone `vcf-lab-mgmt-esx06` (`host-31155`), all ESXi 9.1.1.0100 build 25782009. Read-only property scans on vcf-lab-vcenter-wld01/wld02 (same builds), and one Suite API statkeys GET on VCF Ops `devel`.
- **Last updated:** 2026-11-07
- **Update history:**
  - 2026-11-07 — initial mapping. Live proof of the esxcli path for a Tier 2 "host network stack" question, extended mid-run to VM port stats, vmxnet3 ring/out-of-buffer reachability and RSS settings. Scope cut by the coordinator at ~13:53 UTC (no network pak planned); no calls after the cut. Verbatim captures: `reference/docs/extracted/esxcli-soap/` (see its `PROVENANCE.md`).
- **Evidence basis:** live API calls (raw HTTPS from Python `http.client`, SOAP to `/sdk`, one JSON-API proof). Prior work cross-checked, not relied on: `knowledge/context/investigations/esxcli-soap-reflect-executer-spike.md` (2026-06-03, api-explorer; its §0 encoding is now wire-confirmed) and the compliance adapter's `EsxcliSoapClient.java`, which already ships this path for `system.syslog.config.get`.
- **Notes:** Every lab host is 9.1.1 build 25782009, so there is no version-drift evidence. Timings were taken from a workstation on the lab LAN against a lightly loaded vCenter. Treat them as a floor. Unsupported/internal API: none of these types are in the public vim25 WSDL.

## Verdict

- **The route exists and is cheap.** One vCenter session, no host credentials, no ticket. `HostSystem.RetrieveManagedMethodExecuter` on vCenter returns a vCenter-proxied executer per host, and `ExecuteSoap` on it runs any esxcli `get`/`list` at 4 to 15 ms per call. It works over the vim25 JSON API as well as SOAP `[observed 2026-11-07]`.
- **pNIC counters, per-vNIC port counters and RSS/NetQueue settings are reachable** through esxcli: `network nic stats get`, `network port stats get`, `network nic queue *`, `system module parameters list` `[observed 2026-11-07]`.
- **vmxnet3 ring size, ring-full and out-of-buffers have no agentless path.** No esxcli namespace in the 9.1.1 type tree carries them, and the executer dispatches only to esxcli handlers and `vim.CLIInfo` (the vsish-style moid, `ha-host` and the python DynamicTypeManager all fault). Those figures are vsish-only (`/net/portsets/<ps>/ports/<port>/vmxnet3/rxSummary`), which needs a shell on the host `[observed 2026-11-07: type tree search + executer probes]`.
- **Per-queue drop counters and pNIC ring sizes are also out of reach here.** `network nic ring current/preset get` fault `Not supported: VSI node (240:VSI_NODE_net_pNics_firmware_ringParams)` on every NIC in the lab (i40en, cndi_igc, if_re). No esxcli command carries per-queue drops `[observed 2026-11-07]`. Ring support on other drivers is `[untested]`.

## Route from a vCenter session to a host's executer

Tried in the order requested. Captures `00-01` to `00-12` in `reference/docs/extracted/esxcli-soap/`.

| # | Attempt | Result (verbatim fault) | ms |
|---|---|---|---|
| 1a | vCenter `SessionManager.AcquireCloneTicket`, then the host's own `/sdk` `ha-sessionmgr` `CloneSession(<ticket>)` | Ticket issued (`cst-VCT-...`); host: `InvalidLogin` "Cannot complete login due to an incorrect user name or password." | 18 / 4,007 |
| 1b | vCenter `AcquireGenericServiceTicket` with `SessionManagerHttpServiceRequestSpec{method=httpPost, url=https://<host>/sdk}` (also `:443`) | `InvalidArgument` "A specified parameter was not correct: url" (`invalidProperty` url) | 34 to 140 |
| 1c | vCenter `HostSystem.AcquireCimServicesTicket`, sessionId sent as `vmware_soap_session` to host `/sdk`, then `DynamicTypeMgrQueryTypeInfo` / `ExecuteSoap` on `ha-dynamic-type-manager` / `ha-managed-method-executer` | Ticket issued (service `CimInterfaces`); host: `NotAuthenticated` "The session is not authenticated." with `<privilegeId>System.Read</privilegeId>` on each object | 19 / 5 to 6 |
| 2 | vCenter `/sdk` with the host-scoped moids `ha-dynamic-type-manager`, `ha-managed-method-executer` | `ManagedObjectNotFound` "The object 'vmodl.reflect.DynamicTypeManager:ha-dynamic-type-manager' has already been deleted or has not been completely created" (and the same for `vmodl.reflect.ManagedMethodExecuter:ha-managed-method-executer`) | 10 to 13 |
| 2b | vCenter `/sdk`, dynamic method `<VimEsxCLInetworkniclist>` with bare `_this=ha-cli-handler-network-nic` | `InvalidRequest` "Unable to resolve WSDL method name VimEsxCLInetworkniclist in vim.version.version7 (vim25/5.0) ..." | 12 |
| **3** | **vCenter `/sdk`, `HostSystem.RetrieveDynamicTypeManager` / `RetrieveManagedMethodExecuter` on the host MoRef** | **OK:** `InternalDynamicTypeManager` `DynamicTypeManager-6017`, `ReflectManagedMethodExecuter` `ManagedMethodExecuter-6017` (suffix = host moid number) | 8 to 12 |

All `[observed 2026-11-07]`. The host's `/sdk` port 443 was reachable from the workstation. Reaching it did not help, because no ticket that vCenter issues authenticates there.

### Working envelope (route 3)

Endpoint `POST https://<vCenter>/sdk`. Identity: the vCenter `vmware_soap_session` cookie from an ordinary `SessionManager.Login`. vCenter relays to the host itself; no host session is created by the client `[observed 2026-11-07]`.

```xml
<RetrieveManagedMethodExecuter xmlns="urn:vim25"><_this type="HostSystem">host-6017</_this></RetrieveManagedMethodExecuter>
<!-- returnval type="ReflectManagedMethodExecuter" ManagedMethodExecuter-6017 -->

<ExecuteSoap xmlns="urn:vim25">
  <_this type="ReflectManagedMethodExecuter">ManagedMethodExecuter-6017</_this>
  <moid>ha-cli-handler-network-nic-stats</moid>
  <version>urn:vim25/5.0</version>
  <method>vim.EsxCLI.network.nic.stats.get</method>
  <argument><name>nicname</name><val>&lt;nicname&gt;vmnic1&lt;/nicname&gt;</val></argument>
</ExecuteSoap>
```

- `moid` = `ha-cli-handler-` + namespace joined by `-`; `method` = `vim.EsxCLI.` + full dotted command; `version` constant `urn:vim25/5.0`; each `argument.val` is the XML-escaped `<name>value</name>` element. `[observed 2026-11-07]`, matching spike §0.4.
- The SOAPAction header does not matter: `urn:vim25/5.0`, `/8.0.3.0`, `/9.1.1.0` and `urn:vim25/ExecuteSoap` all returned 200 `[observed 2026-11-07]`.
- Response: `ExecuteSoapResponse/returnval` (namespace prefix `reflect:`, `xmlns:reflect="urn:reflect"`) holds **`reflect:response`**, an XML-escaped `<obj versionId="5.0" xsi:type="...">`. `list`-style results are `xsi:type="ArrayOfDataObject"` with `<DataObject xsi:type="VimEsxCLI...">` rows; single `get` structs put PascalCase fields directly under `<obj>`. A parser must match on local name, because the element is `reflect:response`, not a bare `response` `[observed 2026-11-07]`.
- esxcli-level errors come back as **HTTP 200** with `reflect:fault` (`faultMsg` `EsxCLI.CLIFault.summary`, `faultDetail` carrying `VimEsxCLICLIFault/errMsg`). A missing required argument is a SOAP-level **HTTP 500** `InvalidArgument` "A specified parameter was not correct: argument[0]" (`21-network-nic-stats-get.xml`) `[observed 2026-11-07]`.
- **JSON API works too:** `POST /sdk/vim25/8.0.3.0/HostSystem/host-6017/RetrieveManagedMethodExecuter` `{}` returns the MoRef, and `POST /sdk/vim25/8.0.3.0/ReflectManagedMethodExecuter/ManagedMethodExecuter-6017/ExecuteSoap` with `{"moid":..,"version":"urn:vim25/5.0","method":..,"argument":[{"_typeName":"ReflectManagedMethodExecuterSoapArgument","name":"nicname","val":"<nicname>vmnic1</nicname>"}]}` returns `{"_typeName":"ReflectManagedMethodExecuterSoapResult","response":"<obj ...>"}` in 7 ms (`50-json-executesoap-network-nic-stats-get-vmnic1.json`). Only this one command was tried over JSON; the JSON fault shape was not captured `[observed 2026-11-07]`.

### Type tree (DynamicTypeManager through vCenter)

- `DynamicTypeMgrQueryTypeInfo` with no filter on `DynamicTypeManager-6017`: 92 to 99 ms, 135 KB wire, 1.73 MB decoded. It holds 443 managed types (440 `vim.EsxCLI.*` plus `vim.CLIInfo`, `vim.host.VsanAsyncSystem`, `vim.host.VsanSystemEx`), 857 esxcli methods, 483 data types and 0 enums. Type and method versions: `vim.version.version5`, `version10`, `version11`; every response `<obj>` carries `versionId="5.0"` `[observed 2026-11-07]`.
- `DynamicTypeMgrQueryMoInstances`: 17 ms, 444 instances; the non-esxcli ones are `ha-dynamic-type-manager-local-cli-cliinfo`, `ha-cli-info-python` (vim.CLIInfo), `ha-dynamic-type-manager-python` (vmodl.reflect.DynamicTypeManager), `ha-vsan-async-system` `[observed 2026-11-07]`.
- Search for `rss|netq|queue` in command names: only `network nic queue count get/set`, `queue filterclass list`, `queue loadbalancer list/set`, `queue loadbalancer plugin list/set`, `queue loadbalancer state list/set`. **There is no `network nic rss` namespace.** RSS appears only as fields `RSS`/`RSSLRO` of `queue loadbalancer list` and as the `rsslb`/`rsslrolb` args of its `set` `[observed 2026-11-07]`.
- Search for `vmxnet|ring|rxsummary|oob|outof|buffer|vsish|localcli|sysinfo`: only `network nic ring current/preset get/set` (pNIC rings) and `network sriovnic vf stats` (`RxOutofBufferdrops`, SR-IOV VFs only). Nothing vmxnet3, nothing vsish `[observed 2026-11-07]`.

### Executer reach beyond the esxcli tree

| Probe | Result |
|---|---|
| moid `ha-dynamic-type-manager-local-cli-cliinfo`, `vim.CLIInfo.FetchCLIInfo`, typeName `vim.EsxCLI.network.port.stats` | 200 OK (`35-*`) |
| moid `ha-host`, `vim.HostSystem.retrieveHardwareUptime` (and `RetrieveHardwareUptime`) | 500 `NotSupported` "The operation is not supported on the object." (`36-*`, `36b-*`) |
| moid `ha-cli-handler-vsish`, `vim.EsxCLI.vsish.get` | 500 `InvalidArgument` "A specified parameter was not correct: moid" (`37-*`) |
| moid `ha-dynamic-type-manager-python`, `vmodl.reflect.DynamicTypeManager.queryTypeInfo` | 500 `NotSupported` (`38-*`) |

The executer runs esxcli handlers and CLIInfo, and nothing else that was tried. No vsish or localcli moid exists `[observed 2026-11-07]`.

## Commands captured (esx01, `host-6017`)

esx01 has 4 pNICs: vmnic0 `cndi_igc` (I226-V, link down), vmnic1/vmnic2 `i40en` (X710 10G, up, MTU 9000, **ENS driver**), vmnic3 `if_re` (RTL8125, down) `[observed 2026-11-07]`. "Per NIC" means the command needs one call per vmnic.

| Capture | Command | Scope | Result / shape |
|---|---|---|---|
| 01 | `network nic list` | host | Array `Nic`: AdminStatus, DPUId, Description, Driver, Duplex, Link, LinkStatus, MACAddress, MTU, Name, PCIDevice, Speed |
| 02 | `network nic get -n` | **per NIC** | `NICInfo` struct: AdvertisedLinkModes, AutoNegotiation, CableType, Driver, FirmwareVersion, Version (driver), LinkDetected, LinkStatus, Pause*, Transceiver, VirtualAddress, Wakeon... |
| 03 | `network nic stats get -n` | **per NIC** (nicname required) | Array of 1 `Nic`: Bytes/Packets/Broadcast/Multicast received+sent, ReceiveCRC/FIFO/frame/length/missed/over errors, Receivepacketsdropped, Transmitpacketsdropped, Transmit FIFO/aborted/carrier/heartbeat/window errors, Totalreceiveerrors, Totaltransmiterrors |
| 04 | `network nic queue count get` | host (optional `vmnic`) | `NIC`, `Rxnetqueuecount`, `Txnetqueuecount`. **Lists only vmnic0 and vmnic3**; per-NIC on vmnic1 faults "Netqueue config not supported on ENS driver." (`19`) |
| 05, 06 | `network nic ring current get -n`, `ring preset get -n` | **per NIC** | CLI fault on all 4: "Unable to complete Sysinfo operation. ... Not supported: VSI node (240:VSI_NODE_net_pNics_firmware_ringParams)" |
| 07 | `network nic queue filterclass list` | host | NIC, MacOnly, VlanOnly, VlanMac, Vxlan, Geneve, GenericEncap (all false); vmnic0/3 only |
| 08 | `network nic queue loadbalancer list` | host | NIC, RSS, RSSLRO, DynamicQPool, LRO, GeneveOAM, PreEmptibleQ, RxQPair, RxQLatency, RxQNoFeature, MacLearnLB, RxDynamicLB; values `UA`/`NA`/`ND`; vmnic0/3 only |
| 09 | `network nic queue loadbalancer state list` | host | NIC, Enabled; vmnic0/3 only; vmnic1 faults ENS (`20`) |
| 10 | `network nic queue loadbalancer plugin list` | host | 8 plugins per NIC (filter-packer, queue-allocator, rssflow-mapper, numaaware-affinitizer...): NIC, ModuleName, PluginName, Enabled, Description |
| 11 | `network nic coalesce get` | host | NIC, AdaptiveRX/TX, RX/TX microseconds and max frames, Sampleintervalseconds; all `N/A` here |
| 12, 13, 14 | `network nic tso get`, `sg get`, `cso get` | host | NIC + Value (`on`/`off`/`N/A`); cso has RX/TXChecksumOffload; i40en reports `N/A` |
| 15 | `network nic vlan stats get -n` | **per NIC** | CLI fault: "VLAN stats are disabled for vmnic1 please enable them first." (uplinks) / "vmnic0 is not a valid NIC connected to any virtual switch." Enabling them is a `set` and was not done |
| 16 | `network vswitch standard list` | host | Empty `ArrayOfDataObject` (no standard vSwitch) |
| 17, 30 | `network vm list` | host | `VM`: Name, Networks (dvportgroup moids), NumPorts, WorldID; only VMs with a connected port (7 on esx01) |
| 18 | `system version get` | host | Product, Version 9.1.1, Update 1, Patch 0100, Build Releasebuild-25782009 |
| 22, 23 | `network nic hwCap activated list`, `software list` | host | Activated hardware caps per NIC as one space-separated string; software offload flags |
| 24 | `network ip interface list` | host | vmk rows with `RXDispQueueSize` (4), Portset, VDS name/port, NetstackInstance |
| 25, 34 | `system module parameters list -m <driver>` | **per driver** | Name, Type, Value, Description (i40en: `RSS`, `DRSS`, `VMDQ`, `RxITR`, `TxITR`...; values empty = driver default) |
| 26 | `network vswitch dvs vmware list` | host | VDS row incl. `Client` (e.g. `vcf-lab-vcenter-wld02.eth0`), DVPortgroupID, PortID, Uplinks |
| 27 | `network ens lcore list` | host | Empty |
| 31 | `network vm port list -w <worldId>` | **per VM** | `Port`: PortID, DVPortID, MACAddress, IPAddress, Portgroup, TeamUplink, UplinkPortID, vSwitch, ActiveFilters |
| 32 | `network port stats get -p <portId>` | **per port** | `Port`: Packetsreceived/sent, Bytesreceived/sent, Unicast/Multicast/Broadcast received+sent, **Receivepacketsdropped, Transmitpacketsdropped**, PortID |
| 33 | `network port filter stats get -p <portId>` | **per port** | Empty array on all 3 ports (no dvfilters) |

All `[observed 2026-11-07]`. Field names are PascalCase with irregular casing (`Packetssent`, `TXMaximumframes`). Copy them from the captures; do not guess them.

### Counters vs gauges

- **Counters, need a delta:** every field of `network nic stats get`. vmnic2 sampled 30 s apart: Bytesreceived +1,622,078,823, Packetsreceived +1,317,009, monotonic, cumulative since driver load `[observed 2026-11-07]`. Reset on driver reload or host reboot `[inferred from pattern]`. Every field of `network port stats get` is a counter too. Port counters probably reset when the port is re-created (power cycle, vMotion gives a new PortID) `[inferred from pattern, untested]`. `port filter stats` fields are counters by name `[inferred from docs/type tree]`.
- **Gauges/properties:** `Rxnetqueuecount`/`Txnetqueuecount`, Speed, MTU, link state, ring sizes (if supported), and every settings read (loadbalancer, filterclass, plugins, coalesce, tso/sg/cso, hwCap, software, module parameters, `RXDispQueueSize`).

## VM vNIC port statistics (join path)

- `network vm list` gives WorldID, then `network vm port list -w` gives PortID and **DVPortID**, then `network port stats get -p <PortID>` `[observed 2026-11-07]`.
- Join to vim25: `DVPortID` equals the VM's `config.hardware.device[4000].backing.port.portKey` (vcf-lab-license 72 = 72, avi-wld01-node0 205 = 205, services-runtime-l5mbs 235 = 235) `[observed 2026-11-07, 3/3]`. Join to the VM via vm.list `Name` or the portKey. Name is not unique across vCenters; prefer portKey plus the DVS.
- Example: vcf-lab-license port 67109440 shows Receivepacketsdropped 57,289,340 of Packetsreceived 296,775,433 (`32-...-p67109440.xml`) `[observed 2026-11-07]`.

## Source per screenshot column

The column names come from the coordinator's brief (Nick's screenshot); the screenshot itself was not seen.

| Column | vCenter PerformanceManager (VM) | esxcli via executer | vsish only | Ops devel today (VM vcf-lab-license) |
|---|---|---|---|---|
| client name | VM `name` + device label `Network adapter 1` | `network vm list` Name; DVS `Client` field (`<vm>.eth0`) in `network vswitch dvs vmware list` | | VM object name |
| dvPort id | `config.hardware.device[].backing.port.portKey` (vim25 property, not a counter) | `network vm port list` DVPortID | | not checked |
| pktsTx / pktsRx | `net.packetsTx/Rx.summation`, statsType delta, instance `4000` (vNIC device key) and `""` | `network port stats get` Packetssent / Packetsreceived (cumulative) | | `net\|packetsTx_summation_sum`, `net\|packetsRx_summation_sum` (no per-vNIC instance) |
| droppedTx / droppedRx | `net.droppedTx/Rx.summation`, instance `4000` and `""` | Transmitpacketsdropped / Receivepacketsdropped (cumulative) | | `net\|droppedTx_summation`, `net\|droppedTxPct_max`, aggregate `droppedPct`; **no droppedRx key** |
| multicast | `net.multicastTx/Rx.summation`, instance `4000` | Multicastpacketssent / received | | `net\|multicastTx_summation` only |
| 1stRing size / full | none | none | yes | none |
| 2ndRing size / full | none | none | yes | none |
| out-of-buffers | none | none (`RxOutofBufferdrops` exists only for SR-IOV VFs) | yes | none |

Evidence: `41-perfmanager-perfcounter.xml.gz`, `42-queryavailableperfmetric-vm-17001.xml` (intervalId 20), `32-*`, `31-*`, `26-*` `[observed 2026-11-07]`. The Ops column comes from `GET /suite-api/api/resources/<id>/statkeys` on devel for vcf-lab-license: 338 keys, 18 `net*`. It reflects that VM and devel's current policy only `[observed 2026-11-07]`; whether a policy change turns on the per-instance `net:4000|...` keys was not tested. The host also exposes per-vmnic `net.droppedRx/Tx`, `errorsRx/Tx`, `packetsRx/Tx` and `unknownProtos` (`42-queryavailableperfmetric-host-6017.xml.gz`) `[observed 2026-11-07]`.

## RSS findings

- **pNIC NetQueue/RSS on ENS uplinks is not readable through esxcli.** The i40en uplinks (vmnic1/2) are absent from `queue count get`, `filterclass list`, `loadbalancer list/state list` and `plugin list`, and per-NIC calls fault "Netqueue config not supported on ENS driver." On the non-ENS NICs (vmnic0, vmnic3) the queue count is 0/0, filterclass all false, RSS `UA` `[observed 2026-11-07]`.
- **Driver RSS parameters:** `system module parameters list -m i40en` returns `RSS` ("Number of queues for NetQueue RSS: 0/4/8/16, default = 0"), `DRSS` ("Default Queue RSS ... default = 8 (ENS) or 0 (non-ENS)"), `VMDQ` (default 16 ENS / 8 non-ENS), `RxITR` 50, `TxITR` 100. Every Value is empty (driver default) except `LLDP` `0,0`. `cndi_igc` exposes only `debug`; `if_re` 15 parameters, none RSS. One call per driver `[observed 2026-11-07]`.
- `network ip interface list` gives `RXDispQueueSize` 4 on every vmk `[observed 2026-11-07]`.
- **vmxnet3 RSS lives in the VMX and is readable through vim25**, not esxcli. A keyed path `config.extraConfig["ethernet0.pnicFeatures"]` returns the key when it is set and silently omits it when it is not (no `missingSet`). Scan of 127 VMs over the three vCenters for `ethernet0..3.{pnicFeatures,ctxPerDev,rssOffload,udpRSS}`: none on mgmt (45 VMs). On wld01 (43) and wld02 (39), the NSX Edges `vcf-lab-wld0{1,2}-en0{1,2}` carry `pnicFeatures=4`, `ctxPerDev=3`, `udpRSS=1` on ethernet0 to 3, and the Avi SEs carry `ctxPerDev=3`, `udpRSS=1`. Captures `44-vm-vm-5017-wld01-en01-extraconfig-ethernet-keys.xml` (Edge) and `40-vm-17001-...` (keys absent) `[observed 2026-11-07]`. Use keyed paths: a full `config.extraConfig` read on these appliances returns `guestinfo.ovfEnv`/`userdata`, which can hold credentials.

## Cost

Serial, one vCenter session, one keep-alive connection, 3 repetitions after a warm-up. "Full set" = executer lookup + the 18 commands above with per-NIC fan-out (34 calls on a 4-NIC host). 12 of those calls are the ring and VLAN faults, which cost the same as a success `[observed 2026-11-07]`.

| Host | NICs | Full set calls | Wall median (min to max) ms | per-call p50 ms | VMs/ports | VM-port tier calls | VM-port tier median (min to max) ms |
|---|---|---|---|---|---|---|---|
| esx01 | 4 | 34 | 197 (190 to 222) | 5.7 | 7/7 | 23 | 121 (111 to 132) |
| esx02 | 4 | 34 | 201 (188 to 208) | 5.3 | 2/2 | 8 | 36 (34 to 37) |
| esx03 | 4 | 34 | 210 (205 to 230) | 5.8 | 7/7 | 23 | 98 (98 to 115) |
| esx04 | 4 | 34 | 198 (196 to 211) | 5.6 | 7/7 | 23 | 131 (94 to 143) |
| esx05 | 4 | 34 | 187 (177 to 198) | 5.1 | 7/7 | 23 | 110 (110 to 124) |
| esx06 (standalone, not vSAN) | 2 | 24 | 271 (267 to 297) | 11.7 | 2/2 | 8 | 61 (60 to 64) |

VM-port tier = executer lookup + `vm list` + `vm port list` per VM + `port stats get` and `port filter stats get` per port.

Per-command p50 over esx01 to 05 (n = 15 per host-level command, 60 per per-NIC command): RetrieveManagedMethodExecuter 1.2, `nic list` 14.3, `nic get` 6.8, `nic stats get` 4.2, `queue count get` 7.0, ring get 5.0 to 5.2 (fault), queue/loadbalancer lists 6.3 to 6.5, coalesce/tso/sg/cso 6.0 to 6.5, `vlan stats get` 4.5 (fault), `vswitch standard list` 4.2, `vm list` 4.5, `system version get` 4.5 ms. The type tree (once per host per version) costs 92 to 99 ms `[observed 2026-11-07]`.

Concurrency, full set, 3 cycles each `[observed 2026-11-07]`:

| Run | Cycle wall ms | Per-run median ms | Per-call p50 / p90 / max ms |
|---|---|---|---|
| serial (reference) | | ~200 | 5.5 / 8 / 19 |
| 2 workers, 2 different hosts | 233, 215, 268 | 231 | 6.1 / 8.6 / 16.4 |
| 2 workers, same host | 278, 266, 284 | 275 | 7.5 / 10.6 / 18.7 |
| 4 workers, same host | 300, 370, 399 | 356 | 8.6 / 15.4 / 36.6 |
| 4 workers, 5 hosts (one cycle) | 417, 452, 423 | 246 | 6.2 / 10.0 / 20.5 |

- Different hosts in parallel are close to independent. On one host, hostd adds contention (1.4x per run at 2 threads, 1.8x at 4) but does not serialize: 4 runs finished in ~0.36 s against ~0.8 s serial. No faults or throttling at these levels.
- Throughput: ~170 calls/s serial; ~375 to 410 calls/s with 4 workers over 5 hosts (2.3x). A vCenter-wide ceiling was not measured `[untested]`.

### Projection (arithmetic on the numbers above, not measured at scale)

A counters-only cycle per host = executer (cacheable) + `nic list` + `nic stats get` x N + `vm list` + `vm port list` x V + `port stats get` x P. Lab host (N=4, V=P=7): 21 calls; settings reads (~21 calls) are static and could be hourly. At 6 hosts x 70 clusters = 420 hosts, 4 workers, ~390 calls/s: lab density about 8,800 calls, ~23 s; at 30 VMs per host (67 calls) about 28,000 calls, ~72 s. Not accounted for: per-call RTT from a Cloud Proxy in another site (every call is one round trip), vpxd load at 420 hosts on one vCenter, and disconnected hosts `[untested]`.

## Privilege

- Proven only as a full administrator. No scoped account was tested, because that needs a role write `[untested]`.
- Evidence gathered: the host-side objects demand `System.Read` (`NotAuthenticated` detail `privilegeId System.Read` on `ha-dynamic-type-manager` and `ha-managed-method-executer`, captures `00-06`, `00-07`). The esxcli read methods in the type tree carry **no** `privId`; only `vim.host.VsanSystemEx` methods do (`System.Read`, `Host.Config.Storage`, `Global.VCServer`). `Host.Cim.CimInteraction` exists in this vCenter's 526-privilege catalog `[observed 2026-11-07]`.
- The 2026-06-03 spike names `Host.Cim.CimInteraction` on the HostSystem as the privilege vCenter checks for the executer. That claim is not sourced from vendor docs `[unverified]`. The least-privilege candidate is `System.Read` plus `Host.Cim.CimInteraction` on the hosts `[inferred, untested]`.

## Version drift

Every lab host is ESXi 9.1.1.0100 build 25782009 and every vCenter is 9.1.1.0100 build 25784172. No 8.0.3 or 9.0 host exists, so drift is `[untested]`. The tree mixes `vim.version.version5/10/11` per method, and responses report `versionId="5.0"`, so the type tree is the per-host source of truth for whether a command exists `[observed 2026-11-07]`. The ENS refusal on NetQueue commands depends on the driver mode, not the version.

## Object model candidates

- **HostSystem (VMWARE, stitched):** per-vmnic instanced counters from `nic stats get` (key on `NICName`, the stats response's own field; `Name` is the `nic list` field it joins to); properties driver, firmware, driver version, ENS or not (inferred from the NetQueue fault), RSS/DRSS/VMDQ module parameters.
- **VirtualMachine (VMWARE, stitched):** per-vNIC instanced counters from `port stats get`, keyed by `DVPortID` = `backing.port.portKey`; vmxnet3 RSS keys from vim25 extraConfig.

## Cross-request join keys

- `HostSystem` MoRef `host-<n>` maps to executer `ManagedMethodExecuter-<n>` and `DynamicTypeManager-<n>` `[observed 2026-11-07]`.
- `network nic list` Name = `network nic stats get` NICName = PerformanceManager host instance `vmnicN` = `config.network.pnic[].device` `[observed 2026-11-07]`.
- `network vm port list` DVPortID = `config.hardware.device[].backing.port.portKey` `[observed 2026-11-07, 3/3]`; vNIC device key (4000) = PerformanceManager VM instance `[observed 2026-11-07]`.
- `network vm list` WorldID feeds `vm port list -w`; PortID feeds `port stats get -p` `[observed 2026-11-07]`.

## Gaps / questions

- Least-privilege account for `RetrieveManagedMethodExecuter`/`ExecuteSoap` `[untested]`.
- 8.0.3 / 9.0 hosts: command availability and field names `[untested]`.
- pNIC ring sizes on drivers other than i40en/cndi_igc/if_re, and on non-ENS i40en `[untested]`.
- VLAN stats need `network nic vlan stats set` (a write), not attempted.
- Port counter reset semantics on vMotion and power cycle `[untested]`.
- Throughput ceiling across many hosts on one vCenter, and from a remote Cloud Proxy `[untested]`.
- Whether an Ops policy change enables per-vNIC `net:<instance>|droppedRx` on VMs `[untested]`.
- Run cut short by the coordinator; see `reference/docs/extracted/esxcli-soap/PROVENANCE.md` §Run cut short.
