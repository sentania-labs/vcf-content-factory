# Compliance build 103: bulk-first reads vs build 102 per-object reads, devel (2026-10-28)

Evidence for compliance adapter issue #17 build 2 (the bulk `RetrieveProperties` read
becomes the scoring path). Cited from the adapter's CHANGELOG (build 103). Answers
build 103 review W1 (what the `config.option` = `QueryOptions` comparison ran on) and
W2 (the evidence lived only in a scratch directory).

## How it was run

- Tool: `tests/com/vcfcf/adapters/compliance/DevelBulkEquivalence.java` in the
  compliance adapter repo (committed in build 103; CI compiles it, never runs it). Run
  from the repo root against the build-103 source; the javadoc has the command.
- Read-only. One login per vCenter, logout in `finally`. No property, setting or
  object was changed. Credentials came from the environment (`VCENTER_CREDENTIAL`,
  `VCENTER_PASSWORD`) and were not printed. Certificates were checked against the
  system CA bundle.
- Per vCenter, three passes over every host, VM (Pods excluded), vDS, portgroup and
  cluster, each scored against the benchmark the adapter would pick ("Auto (by
  version)"):
  1. OLD: build 102 per-object reads (`QueryOptions` for host advanced settings,
     `config.extraConfig` per VM, one `RetrieveProperties` per property).
  2. NEW: build 103 bulk-first reads (one `RetrieveProperties` per page, hosts 10,
     VMs and clusters 50, switches and portgroups 100; `config.option` for host
     advanced settings), per-object fallback for anything missing.
  3. NEW again (steady state, the accepted path sets remembered).
- Compared, per object: every control's outcome (actual value plus pass/fail, or
  unreadable), each host's version and connection state, each host's full advanced
  option map (size and hash of `QueryOptions` vs `config.option`), each VM's
  `extraConfig` map (hash), each cluster's vSAN state.
- Runs: 2026-10-28 around 03:40 (the original run, output not kept) and 04:21
  America/Chicago (the run below, adapter commit 73ad393 plus the identity block). Same
  numbers in both.

## What it ran on

| | |
|---|---|
| vCenters | vcf-lab-vcenter-mgmt, vcf-lab-vcenter-wld01, vcf-lab-vcenter-wld02 (int.sentania.net), all vCenter 9.1.1 |
| Account | `INT.SENTANIA.NET\vcf` |
| Effective role | `Admin` (role id -1, the Administrator system role) on the root folder and on every host |
| mgmt hosts (6) | vcf-lab-mgmt-esx01 to esx06: ESXi 9.1.1.0100, build 25782009 |
| wld01 hosts (2) | vcf-lab-wld01-esx01, esx02: ESXi 9.1.1.0, build 25714478 |
| wld02 hosts (2) | vcf-lab-wld02-esx01, esx02: ESXi 9.1.1.0, build 25714478 |

**Limits.** Every compared host is ESXi 9.1.1; no ESXi 6.7, 7.x, 8.x or 9.0 host exists
behind the devel vCenters. The only vCenter credential available is the Administrator
account; no Read-only-role account exists, and none was created (that is a change to the
lab's SSO). So `config.option` = `QueryOptions` is shown for ESXi 9.1.1 read as
Administrator, and nothing else. Why a gap would not pass silently: none of the 146
HostSystem `advanced_setting` rows in the five canonical CSVs (SCG 6.7 / 7.0 / 8.0 / 9.0
/ 9.1: 12 / 29 / 32 / 35 / 38) has an expected value `ControlEvaluator.allowsUndefined`
accepts ("X or Undefined", "X or Not Present", "Not Present"), so a key `config.option`
leaves out scores "(undefined)" FAIL, a false FAIL rather than a false pass (build 103
review W1; rechecked on the CSVs for this file). The one row whose prose mentions
empty, SCG 9.1 `esx.ad-admin-group-name` ("Site-Specific Active Directory group, or
empty for non-AD-joined hosts"), is demoted to manual review
(`profiles/manual_review.csv`) and is not scored unless a site override gives it a
value. The dev-preview shadow compares the two every cycle on any
devel instance (`Bulk shadow disagreement:` lines).

## Results

| vCenter | Objects | Outcomes compared | Disagree | Fallbacks (adv / version-conn-vsan / controls / failed-page objects) |
|---|---|---|---|---|
| mgmt | 6 hosts, 45 VMs, 1 vDS, 12 DVPG, 1 cluster | 1,437 | 0 | 0 / 0 / 0 / 0 |
| wld01 | 2 hosts, 25 VMs, 1 vDS, 32 DVPG, 1 cluster | 908 | 0 | 0 / 0 / 0 / 0 |
| wld02 | 2 hosts, 36 VMs, 1 vDS, 14 DVPG, 1 cluster | 1,035 | 0 | 0 / 0 / 0 / 0 |
| **Total** | | **3,380** | **0** | |

On all three, the second bulk pass produced exactly the outcomes of the first.

Control outcomes by kind (the outcomes count above also includes the per-object
version, connection, advanced-map and vSAN checks): mgmt host 288, VM 990, dvs 4,
dvportgroup 84, cluster 1; wld01 host 96, VM 550, dvs 4, dvportgroup 224; wld02 host 96,
VM 792, dvs 4, dvportgroup 98. wld01 and wld02 clusters are not vSAN, so no cluster
control applied.

SOAP calls per cycle (listing 15 and esxcli included; keepalive and the vCenter object
excluded):

| vCenter | Host | VM | vDS | Portgroup | Cluster | esxcli | Total OLD | NEW first cycle | NEW steady |
|---|---|---|---|---|---|---|---|---|---|
| mgmt | 60 to 1 | 315 to 1 | 6 to 3 | 180 to 7 | 5 to 4 | 42 | 623 | 73 | 62 |
| wld01 | 20 to 1 | 175 to 1 | 6 to 3 | 480 to 7 | 1 to 4 | 14 | 711 | 45 | 34 |
| wld02 | 20 to 1 | 252 to 1 | 6 to 3 | 210 to 7 | 1 to 4 | 14 | 518 | 45 | 34 |

The per-kind NEW figures are the first bulk pass (it pays the InvalidProperty path
fixes); the steady state is 1 call per kind. A non-vSAN cluster costs 1 call per object
the old way (the probe) and 4 on the first bulk pass (the path fixes).

## Raw output (2026-10-28 04:21)

```
=== vcf-lab-vcenter-mgmt.int.sentania.net
account [INT.SENTANIA.NET\vcf] (session row [currentSession] missing {}, roles known 82), effective role on the root folder [-1=Admin]
  host host-6011 vcf-lab-mgmt-esx03.int.sentania.net: VMware ESXi 9.1.1.0100.25782009 (build 25782009), effective role [-1=Admin]
  host host-6015 vcf-lab-mgmt-esx02.int.sentania.net: VMware ESXi 9.1.1.0100.25782009 (build 25782009), effective role [-1=Admin]
  host host-15151 vcf-lab-mgmt-esx04.int.sentania.net: VMware ESXi 9.1.1.0100.25782009 (build 25782009), effective role [-1=Admin]
  host host-31189 vcf-lab-mgmt-esx05.int.sentania.net: VMware ESXi 9.1.1.0100.25782009 (build 25782009), effective role [-1=Admin]
  host host-6017 vcf-lab-mgmt-esx01.int.sentania.net: VMware ESXi 9.1.1.0100.25782009 (build 25782009), effective role [-1=Admin]
  host host-31155 vcf-lab-mgmt-esx06.int.sentania.net: VMware ESXi 9.1.1.0100.25782009 (build 25782009), effective role [-1=Admin]
vCenter 9.1.1: 6 hosts, 45 VMs, 1 vDS, 12 DVPG, 1 clusters; listing 15 calls
compared 1437 outcome(s) (controls + version/conn/adv-map/vsan checks): 1437 agree, 0 disagree; control outcomes by moid prefix {domain-c6004|cluster.managed-disk-claim=1, dvportgroup=84, dvs=4, host=288, vm=990}
  Host: OLD 60 calls, NEW 1 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  VM: OLD 315 calls, NEW 1 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  vDS: OLD 6 calls, NEW 3 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  Portgroup: OLD 180 calls, NEW 7 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  Cluster: OLD 5 calls, NEW 4 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  second bulk cycle equal to first: true; steady-state calls per kind [1, 1, 1, 1, 1]
  esxcli (unchanged path): OLD 42, NEW 42
  TOTAL incl. listing 15 and esxcli: OLD 623, NEW first cycle 73, NEW steady state 62
=== vcf-lab-vcenter-wld01.int.sentania.net
account [INT.SENTANIA.NET\vcf] (session row [currentSession] missing {}, roles known 78), effective role on the root folder [-1=Admin]
  host host-20 vcf-lab-wld01-esx01.int.sentania.net: VMware ESXi 9.1.1.0.25714478 (build 25714478), effective role [-1=Admin]
  host host-18 vcf-lab-wld01-esx02.int.sentania.net: VMware ESXi 9.1.1.0.25714478 (build 25714478), effective role [-1=Admin]
vCenter 9.1.1: 2 hosts, 25 VMs, 1 vDS, 32 DVPG, 1 clusters; listing 15 calls
compared 908 outcome(s) (controls + version/conn/adv-map/vsan checks): 908 agree, 0 disagree; control outcomes by moid prefix {dvportgroup=224, dvs=4, host=96, vm=550}
  Host: OLD 20 calls, NEW 1 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  VM: OLD 175 calls, NEW 1 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  vDS: OLD 6 calls, NEW 3 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  Portgroup: OLD 480 calls, NEW 7 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  Cluster: OLD 1 calls, NEW 4 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  second bulk cycle equal to first: true; steady-state calls per kind [1, 1, 1, 1, 1]
  esxcli (unchanged path): OLD 14, NEW 14
  TOTAL incl. listing 15 and esxcli: OLD 711, NEW first cycle 45, NEW steady state 34
=== vcf-lab-vcenter-wld02.int.sentania.net
account [INT.SENTANIA.NET\vcf] (session row [currentSession] missing {}, roles known 72), effective role on the root folder [-1=Admin]
  host host-17 vcf-lab-wld02-esx01.int.sentania.net: VMware ESXi 9.1.1.0.25714478 (build 25714478), effective role [-1=Admin]
  host host-19 vcf-lab-wld02-esx02.int.sentania.net: VMware ESXi 9.1.1.0.25714478 (build 25714478), effective role [-1=Admin]
vCenter 9.1.1: 2 hosts, 36 VMs, 1 vDS, 14 DVPG, 1 clusters; listing 15 calls
compared 1035 outcome(s) (controls + version/conn/adv-map/vsan checks): 1035 agree, 0 disagree; control outcomes by moid prefix {dvportgroup=98, dvs=4, host=96, vm=792}
  Host: OLD 20 calls, NEW 1 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  VM: OLD 252 calls, NEW 1 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  vDS: OLD 6 calls, NEW 3 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  Portgroup: OLD 210 calls, NEW 7 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  Cluster: OLD 1 calls, NEW 4 calls (fallbacks: adv 0, version/conn/vsan 0, controls 0, objects in failed bulk 0)
  second bulk cycle equal to first: true; steady-state calls per kind [1, 1, 1, 1, 1]
  esxcli (unchanged path): OLD 14, NEW 14
  TOTAL incl. listing 15 and esxcli: OLD 518, NEW first cycle 45, NEW steady state 34
```
