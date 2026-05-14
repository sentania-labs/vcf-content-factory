---
date: 2026-05-13
type: reference
category: reference-doc
source: web-research
trust: external
reviewed: false
sources:
  - url: https://github.com/vmware/vmware-aria-operations-integration-sdk
    domain: github.com/vmware
    type: vendor-doc
  - url: https://github.com/vmware/vmware-vcf-operations-integration-sdk
    domain: github.com/vmware
    type: vendor-doc
  - url: https://vmware.github.io/vmware-aria-operations-integration-sdk/
    domain: vmware.github.io
    type: vendor-doc
  - url: https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations/8-18/management-pack-builder.html
    domain: techdocs.broadcom.com
    type: vendor-doc
  - url: https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/management-packs/copy-of-getting-started-with-management-packs-for-vrealize-operations-management-packs.html
    domain: techdocs.broadcom.com
    type: vendor-doc
  - url: https://docs.vmware.com/en/Management-Packs-for-vRealize-Operations/index.html
    domain: docs.vmware.com
    type: vendor-doc
  - url: https://github.com/HewlettPackard/simplivity-vrops-plugin
    domain: github.com
    type: community
  - url: https://github.com/PureStorage-Connect/vROPs-MgmtPak
    domain: github.com
    type: community
  - url: https://github.com/vmware-nsx/vrops-edge-monitoring
    domain: github.com
    type: community
  - url: https://github.com/moffzilla/vrops-k8-monitoring
    domain: github.com
    type: community
  - url: https://www.brockpeterson.com/post/building-a-management-pack-with-the-aria-operations-management-pack-builder
    domain: brockpeterson.com
    type: blog
  - url: https://www.brockpeterson.com/post/vrops-management-pack-builder
    domain: brockpeterson.com
    type: blog
  - url: https://www.brockpeterson.com/post/vcommunity-management-pack-for-vcf-operations
    domain: brockpeterson.com
    type: blog
  - url: https://veducate.co.uk/vrealize-operations-management-pack-builder/
    domain: veducate.co.uk
    type: blog
  - url: https://enterpriseadmins.org/blog/virtualization/learn-how-to-monitor-pi-hole-with-vrops-using-the-management-pack-builder/
    domain: enterpriseadmins.org
    type: blog
  - url: https://vrabbi.cloud/post/monitoring-tap-with-vrops/
    domain: vrabbi.cloud
    type: blog
  - url: https://thomas-kopton.de/vblog/?p=1872
    domain: thomas-kopton.de
    type: blog
  - url: https://vrealize.it/2024/12/20/extend-vcenter-metrics-with-management-pack-builder/
    domain: vrealize.it
    type: blog
  - url: https://medium.com/@lubomir-tobek/deploy-management-pack-builder-for-aria-operations-506aaa77cdce
    domain: medium.com
    type: blog
  - url: https://gibsonvirt.com/2025/12/12/aria-operations-management-pack-builder-phpipam-part-1/
    domain: gibsonvirt.com
    type: blog
  - url: https://rguske.github.io/post/monitoring-the-vmware-event-broker-appliance-with-vrealize-operations-manager/
    domain: rguske.github.io
    type: blog
  - url: https://virtualviking.net/2015/12/15/vraidmon-a-vrealize-operations-adapter-written-in-python/
    domain: virtualviking.net
    type: blog
  - url: https://www.youtube.com/watch?v=fa2QRAcqgVI
    domain: youtube.com
    type: community
  - url: https://www.youtube.com/playlist?list=PLrFo2o1FG9n6W5IEmXqkxgb0v5yQ_Y_nZ
    domain: youtube.com
    type: community
  - url: https://docs.nvidia.com/vgpu/vrops/latest/grid-management-pack-vmware-vrops-user-guide/index.html
    domain: docs.nvidia.com
    type: vendor-doc
  - url: https://github.com/vmware-archive/vrops-restapi-samples
    domain: github.com/vmware
    type: vendor-doc
  - url: https://www.vcrocs.info/aria-operations-servicenow-mp-cmdb/
    domain: vcrocs.info
    type: blog
  - url: https://intersight.com/help/saas/resources/VCF_Operations_Management_Pack
    domain: intersight.com
    type: vendor-doc
  - url: https://community.cisco.com/t5/data-center-and-cloud-knowledge-base/vcf-operations-management-pack-for-cisco-intersight/ta-p/5238962
    domain: community.cisco.com
    type: community
  - url: https://github.com/vineethac/vROps_PowerFlex_Report
    domain: github.com
    type: community
topics: [vmware, aria-operations, vrealize-operations, management-pack, monitoring, SDK, extensibility]
tags: [vmware, vrops, aria-operations, management-pack, SDK, monitoring, extensibility, developer]
---

# VMware/Broadcom Management Pack Build Examples — Comprehensive Reference

Management Packs (MPs) are extensibility plugins for VMware vRealize Operations / Aria Operations / VCF Operations that add monitoring for technologies beyond what ships out of the box. This note catalogs every substantive build example, tutorial, SDK sample, and community implementation found across official, community, and partner sources.

---

## Toolchain Overview

Before the catalog, understand the two distinct paths for building MPs:

### Path 1: Aria Operations Integration SDK (formerly vROps MP SDK)
A **code-first** approach using Python or Java. Produces a containerized adapter bundled into a `.pak` file via the `mp-build` CLI tool. Requires API/programming knowledge. Suited for complex integrations.

- **Current repo (active):** [vmware/vmware-aria-operations-integration-sdk](https://github.com/vmware/vmware-aria-operations-integration-sdk) — GitHub
- **VCF-era fork (same codebase, different branding):** [vmware/vmware-vcf-operations-integration-sdk](https://github.com/vmware/vmware-vcf-operations-integration-sdk) — GitHub
- **Official docs site:** [vmware.github.io/vmware-aria-operations-integration-sdk](https://vmware.github.io/vmware-aria-operations-integration-sdk/) — vendor-doc

Languages supported: Python 3.9+, Java 17. The SDK ships `mp-init` (project scaffolding) and `mp-build` (packaging). The default Python template adapter collects metrics from its own container — a usable "hello world" starting point.

### Path 2: Aria Operations Management Pack Builder (MPB)
A **no-code/low-code** standalone OVA appliance with a web UI. Connects to external REST APIs, maps responses to objects/metrics/relationships, and exports a `.pak` file. No programming required — just REST API knowledge.

- **Official docs (Broadcom TechDocs):** [Management Pack Builder 2.0](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/2-0/management-pack-builder-2-0/management-pack-builder.html) — vendor-doc
- **VCF 9.0 version:** [Management Pack Builder in VCF 9.0](https://techdocs.broadcom.com/us/en/vmware-cis/vcf/vcf-9-0-and-later/9-0/infrastructure-operations/extending-monitoring-capabilities/cloud-foundation-operations-configuration-guide-management-pack-builder.html) — vendor-doc
- **Original 1.0 docs:** [Management Pack Builder 1.0.0](https://docs.vmware.com/en/VMware-vRealize-Operations-Management-Pack-Builder/1.0.0/management-pack-builder/GUID-1C363DCE-5C4A-473D-A519-A55E0371A9F2.html) — vendor-doc
- Beta announced March 2022 on [blogs.vmware.com](https://blogs.vmware.com/management/2022/03/beta-program-vrealize-operations-management-pack-builder.html) — vendor-doc

---

## 1. Official VMware/Broadcom Examples

### 1.1 SDK Sample Packs (in the Integration SDK repo)

The `samples/` directory of the Integration SDK GitHub repo contains the following reference implementations:

| Name | Technology Monitored | Notes |
|------|---------------------|-------|
| **alibaba-cloud-mp** | Alibaba Cloud ECS instances and Security Groups | Walkthrough in official docs; collects 6 properties + relationship to Adapter Instance |
| **mysql-extension-mp** | MySQL (Python) | Extends existing MySQL MP with 5 lock-wait metrics; illustrates "extend existing" pattern |
| **mysql-extension-java-mp** | MySQL (Java) | Java equivalent of the above |
| **nsx-alb-avi-mp** | NSX Advanced Load Balancer (AVI) | Full pack sample |
| **rest-template-mp** | Generic REST API (template) | Starting skeleton for any REST-based integration |
| **snmp-template-mp** | Generic SNMP | Starting skeleton for SNMP-based monitoring |
| **vcenter-extension-mp** | vCenter | Extends built-in vCenter adapter with additional data |

Source: [Integration SDK samples directory](https://github.com/vmware/vmware-aria-operations-integration-sdk/tree/main/samples) — vendor-doc (whitelisted)

### 1.2 Official SDK Guides and Walkthroughs

- **"Creating a New Management Pack"** — Step-by-step walkthrough using Alibaba Cloud as the example. Covers `mp-init`, adapter coding, testing with `mp-test`, and packaging with `mp-build`.
  URL: [vmware.github.io — Creating a New Management Pack](https://vmware.github.io/vmware-aria-operations-integration-sdk/guides/creating_a_new_management_pack/) — vendor-doc

- **"Extending an Existing Management Pack"** — Uses MySQL MP as the example; shows how to add metrics to objects owned by another adapter.
  URL: [vmware.github.io — Extending an Existing Management Pack](https://vmware.github.io/vmware-aria-operations-integration-sdk/guides/extending_an_existing_management_pack/) — vendor-doc

- **"Get Started"** — Installation, environment setup, and first run.
  URL: [vmware.github.io — Get Started](https://vmware.github.io/vmware-aria-operations-integration-sdk/get_started/) — vendor-doc

### 1.3 VMware {code} / Broadcom Developer Samples

- **VMware {code} samples tagged "vRealize Operations Manager"**
  URL (redirects to Broadcom): [developer.broadcom.com/samples](https://developer.broadcom.com/samples?categories=Sample&keywords=&tags=vRealize+Operations+Manager&groups=&filters=&sort=dateDesc&page=) — vendor-doc
  Note: Login required to browse; historically included dashboard samples and API examples.

- **vROps REST API Samples (archived)**
  [vmware-archive/vrops-restapi-samples](https://github.com/vmware-archive/vrops-restapi-samples) — GitHub, now archived
  Contains Postman collections and code samples for the vROps 6.x suite API. Useful for understanding how adapters push data via REST.

- **Aria Operations API Programming Guide (8.18)**
  [techdocs.broadcom.com — API Guide](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations/8-18/vmware-aria-operations-api-programming-guide-8-18.html) — vendor-doc
  Reference for the REST API that adapters use to push objects, metrics, and events.

### 1.4 Official Built-In / Bundled Management Packs (with source docs)

These ship with Aria Operations or Aria Operations for Integrations and serve as reference-quality implementations:

| Pack | What it monitors | Docs |
|------|-----------------|------|
| **MP for Kubernetes** | K8s clusters, nodes, pods, workloads | [techdocs](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/8-18/vrealize--operations-management-pack--for-kubernetes.html) |
| **MP for Docker** | Docker containers, images | [techdocs](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/9-0/management-pack-for-docker-9-0/management-pack-for-docker.html) |
| **MP for SNMP** | Generic SNMP devices (v1/v2c/v3) | [techdocs](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/3-3/vmware-vrealize-operations-management-pack-for-snmp-3-3/vmware-vrealize-operations-management-pack-for-snmp.html) |
| **MP for ServiceNow** | ServiceNow CMDB sync | [techdocs](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/9-0/management-pack-for-servicenow-9-0/management-pack-for-servicenow.html) |
| **MP for vRealize Orchestrator** | vRO workflows and catalog | [techdocs](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/3-3/management-pack-for-vrealize-orchestrator-3-3/introduction-vro.html) |
| **MP for Horizon** | Horizon desktops, sessions | [techdocs](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/2-7-1/vmware-vrealize-operations-management-pack-for-horizon-2-7-1.html) — EOGS March 2025 |
| **MP for Cloud Director Availability** | VCDA replication | [blogs.vmware.com announcement](https://blogs.vmware.com/cloudprovider/2022/10/vmware-vrealize-operations-management-pack-for-cloud-director-availability-12.html) |
| **Full list of integrations** | All official MPs | [docs.vmware.com list](https://docs.vmware.com/en/Management-Packs-for-vRealize-Operations/integrations/getting-started-mp/GUID-06430026-4557-425D-A0A4-C50AAE211B9F.html) |

**Note on EOL:** Broadcom announced end of general support for many legacy MPs effective October 1, 2024 and June 17, 2025. See [KB 373307](https://knowledge.broadcom.com/external/article/373307) and [KB 400934](https://knowledge.broadcom.com/external/article/400934) for the lists.

### 1.5 VMware-Authored Community Repos (non-SDK-samples)

- **vmware-nsx/vrops-edge-monitoring**
  Author: VMware NSX team. Monitors NSX Edge node and ESXi host network performance metrics (CPU, interface errors, flow cache). Python-based; uses vROps REST API to push data. Tested on NSX 4.2.1, ESXi 8.0u3, Aria Operations 8.18.2. No SDK — raw REST push pattern.
  URL: [github.com/vmware-nsx/vrops-edge-monitoring](https://github.com/vmware-nsx/vrops-edge-monitoring) — community

---

## 2. VMware Flings

The Flings program (labs.vmware.com) historically hosted experimental MP-related tools. The main confirmed fling:

- **VMware vRealize Operations Docker 1.0 Adapter**
  Author: VMware Labs. Collects performance data from Docker container environments and container images.
  URL: [labs.vmware.com/flings/vmware-vrealize-operations-docker-1-0-adapter](https://labs.vmware.com/flings/vmware-vrealize-operations-docker-1-0-adapter) — community
  Note: This functionality was later absorbed into the official MP for Docker.

The broader Flings catalog is at [flings.vmware.com](https://flings.vmware.com/flings). An archive of older flings exists at [archive.org/download/flings.vmware.com](https://archive.org/download/flings.vmware.com/Flings/). Post-Broadcom acquisition, Flings has been wound down and content migrated or discontinued.

---

## 3. Hands-On Labs (HOL)

No developer-focused HOL specifically covering MP *building* was confirmed in research. The HOLs that exist are consumption/configuration focused:

- **HOL-1706-SDC-1** — vRealize Operations general configuration lab (2017 era)
  URL: [docs.hol.vmware.com/HOL-2017/hol-1706-sdc-1_html_en/](https://docs.hol.vmware.com/HOL-2017/hol-1706-sdc-1_html_en/) — community
- **HOL-1801-06** — Deploying the vRealize Operations Manager Appliance
  URL: [docs.hol.vmware.com](https://docs.hol.vmware.com/hol-isim/HOL-2018/hol-1801-06-vropsinstall.htm) — community
- **VMware HOL portal (current):** [labs.hol.vmware.com/HOL/](https://labs.hol.vmware.com/HOL/) — vendor

**Assessment:** No HOL specifically teaches MP SDK development. The Management Pack Builder is new enough (GA 2022) that a dedicated HOL may not yet exist. Worth checking the HOL catalog directly for any 2023–2025 additions.

---

## 4. YouTube / Video Resources

- **"vRealize This Live! Episode 19 — Build your own Management Packs for vRealize Operations"**
  Channel: VMware Cloud Management. Published June 9, 2022. Covers the Management Pack Builder tool.
  URL: [youtube.com/watch?v=fa2QRAcqgVI](https://www.youtube.com/watch?v=fa2QRAcqgVI) — community

- **VMware Aria Operations Management Packs playlist**
  Covers installation/configuration walkthroughs for compute and storage management packs (True Visibility Suite era). Multiple episodes.
  URL: [youtube.com playlist](https://www.youtube.com/playlist?list=PLrFo2o1FG9n6W5IEmXqkxgb0v5yQ_Y_nZ) — community

- **"Cloudify Management Pack with VMware vRealize Operations Demo"**
  URL: [youtube.com/watch?v=LAnhtJzmnZA](https://www.youtube.com/watch?v=LAnhtJzmnZA) — community

- **"Pure Storage Management Pack for VMware vRealize Operations"**
  URL: [youtube.com/watch?v=2f7VFRUh5hE](https://www.youtube.com/watch?v=2f7VFRUh5hE) — community

- **"Feature Friday Episode 109 — vRealize NSX Advanced Load Balancer Management Pack"**
  URL: [youtube.com/watch?v=87XhmDPvNF0](https://www.youtube.com/watch?v=87XhmDPvNF0) — community

- **"VCF Operations Management Pack for Cisco Intersight" (video)**
  URL: [youtu.be/fBIF8M4eIzA](https://youtu.be/fBIF8M4eIzA) — community

---

## 5. Blog Posts / Tutorials (Community & VMware Employee Authors)

### 5.1 Management Pack Builder (MPB) Tutorials

| Title | Author/Site | Technology Monitored | Date | SDK/Tool |
|-------|------------|---------------------|------|----------|
| [Building a Management Pack with the Aria Operations Management Pack Builder](https://www.brockpeterson.com/post/building-a-management-pack-with-the-aria-operations-management-pack-builder) | Brock Peterson (VMware TAM/employee) | Rubrik Cloud Data Management | Sept 2024 (updated Aug 2025) | MPB v2.0 |
| [vROps Management Pack Builder — TrueNAS](https://www.brockpeterson.com/post/vrops-management-pack-builder) | Brock Peterson | TrueNAS storage | May 2022 | MPB Beta |
| [vRealize Operations Management Pack Builder — Veeam](https://veducate.co.uk/vrealize-operations-management-pack-builder/) | vEducate.co.uk (Sharon Bhella) | Veeam Backup and Replication | Mar 2022 | MPB (HTTP data source) |
| [Learn how to monitor Pi-hole with vROps using the Management Pack Builder](https://enterpriseadmins.org/blog/virtualization/learn-how-to-monitor-pi-hole-with-vrops-using-the-management-pack-builder/) | Enterprise Admins.org | Pi-hole DNS ad-blocker | Feb 2023 | MPB v1.0.0 |
| [Monitoring TAP with vROps](https://vrabbi.cloud/post/monitoring-tap-with-vrops/) | vRabbi (Terraform/Tanzu blogger) | Tanzu Application Platform (TAP) K8s workloads | Jun 2022 (updated Aug 2022) | MPB (OVA UI) |
| [Extend vCenter metrics with Management Pack Builder](https://vrealize.it/2024/12/20/extend-vcenter-metrics-with-management-pack-builder/) | vRealize.it | vCenter/vSAN (Default Storage Policy property) | Dec 2024 | MPB v1.1+ |
| [Deploy Management Pack Builder for Aria Operations](https://medium.com/@lubomir-tobek/deploy-management-pack-builder-for-aria-operations-506aaa77cdce) | Lubomir Tobek (Medium) | Deployment guide (no target technology) | Jan 2025 | MPB v2.0.0 |
| [Aria Operations Management Pack Builder — phpIPAM (4-part series)](https://gibsonvirt.com/2025/12/12/aria-operations-management-pack-builder-phpipam-part-1/) | Gibson Virtualization | phpIPAM IP address management | Dec 2025 | MPB |

The phpIPAM series is notable for being a 4-part build walkthrough:
  - [Part 1](https://gibsonvirt.com/2025/12/12/aria-operations-management-pack-builder-phpipam-part-1/) — API auth
  - [Part 2](https://gibsonvirt.com/2025/12/12/aria-operations-management-pack-builder-phpipam-part-2/) — API requests and object relationships
  - [Part 3](https://gibsonvirt.com/2025/12/15/aria-operations-management-pack-builder-phpipam-part-3/) — Build, import, dashboards, super metrics
  - [Part 4](https://gibsonvirt.com/2025/12/16/aria-operations-management-pack-builder-phpipam-part-4/) — Export content and rebuild PAK
  - [Showcase post](https://gibsonvirt.com/2025/12/16/aria-operations-management-pack-phpipam-showcase/) — finished dashboards demo

### 5.2 Integration SDK (Code-First) Tutorials

| Title | Author/Site | Technology | Date | SDK/Tool |
|-------|------------|-----------|------|----------|
| [VMware Aria Operations Integration SDK — Part 1, Installation](https://thomas-kopton.de/vblog/?p=1872) | TOMsOps (Thomas Kopton) | "Hello World" container self-monitoring | Aug 2024 | Aria Operations Integration SDK |
| [vraidmon — A vRealize Operations Adapter Written in Python](https://virtualviking.net/2015/12/15/vraidmon-a-vrealize-operations-adapter-written-in-python/) | The Virtual Viking | Linux software RAID (`/proc/mdstat`) | Dec 2015 | nagini Python library (pre-SDK era) |

### 5.3 Specific Technology Monitoring Posts

| Title | Author/Site | Technology | Date | Notes |
|-------|------------|-----------|------|-------|
| [VMware Aria Operations / ServiceNow Management Pack (CMDB)](https://www.vcrocs.info/aria-operations-servicenow-mp-cmdb/) | vCROCS (Dale Hassinger) | ServiceNow CMDB | Feb 2024 | Uses official MP; covers config + customization |
| [Monitoring the VMware Event Broker Appliance with vROps](https://rguske.github.io/post/monitoring-the-vmware-event-broker-appliance-with-vrealize-operations-manager/) | Robert Guske (VMware employee) | VEBA via Kubernetes MP + cAdvisor | May 2020 | Uses official Kubernetes MP; DaemonSet approach |
| [Monitor QNAP NAS devices with vROps SNMP Adapter](https://vmguru.com/2020/05/monitor-qnap-nas-devices-with-vrops-snmp-adapter/) | VMGuru.com | QNAP NAS devices | May 2020 | Uses official SNMP MP |
| [Monitoring TKGs cluster using VMware Aria Operations](https://vmattroman.com/monitoring-tkgs-cluster-using-aria-operations/) | vMattroman | Tanzu Kubernetes (TKGs) | 2024 | Official K8s MP |

### 5.4 Community MP for VCF Operations (Complex SDK Example)

- **vCommunity Management Pack for VCF Operations**
  Author: Onur Yuvseven (Broadcom TAM), content by Iwan Rahabok.
  Ships 44 dashboards, 169 views, 16 reports, 37 super metrics. Built with the Operations Integration SDK (not MPB). Requires Operations 9.0 + Cloud Proxy.
  Published: Nov 2025.
  URL: [brockpeterson.com/post/vcommunity-management-pack-for-vcf-operations](https://www.brockpeterson.com/post/vcommunity-management-pack-for-vcf-operations) — blog

---

## 6. Partner / Vendor-Built Management Packs (Open Source or Documented)

### 6.1 Open Source / GitHub-Available

| Pack | Vendor | GitHub URL | Last Known Active | Notes |
|------|--------|-----------|------------------|-------|
| **HPE SimpliVity Plugin for vROps** | Hewlett Packard Enterprise | [HewlettPackard/simplivity-vrops-plugin](https://github.com/HewlettPackard/simplivity-vrops-plugin) | vROps 8.10 / OmniStack 4.3 | Performance, capacity, efficiency metrics. Includes user guide PDF + demo video. Apache 2.0 license. |
| **Pure Storage Management Pack for vROps** | Pure Storage | [PureStorage-Connect/vROPs-MgmtPak](https://github.com/PureStorage-Connect/vROPs-MgmtPak) | 2022 (v3.2.0 for vROps 8.6) | FlashArray monitoring; multiple release branches for different vROps versions. |
| **vROps Kubernetes Container Monitoring** | moffzilla (VMware employee) | [moffzilla/vrops-k8-monitoring](https://github.com/moffzilla/vrops-k8-monitoring) | ~2019-2020 | Pre-dates official K8s MP; community reference implementation. |
| **vROps PowerFlex Custom Report** | vineethac (community) | [vineethac/vROps_PowerFlex_Report](https://github.com/vineethac/vROps_PowerFlex_Report) | 2021 | Custom storage report for Dell EMC PowerFlex; companion to the official PowerFlex MP. |
| **NSX Edge Monitoring (vmware-nsx)** | VMware NSX team | [vmware-nsx/vrops-edge-monitoring](https://github.com/vmware-nsx/vrops-edge-monitoring) | Late 2024 | Python; raw REST push to Aria Operations 8.18.2. Not SDK-packaged. |

### 6.2 Vendor-Documented but Closed-Source

| Pack | Vendor | Doc URL | Type |
|------|--------|---------|------|
| **NVIDIA Virtual GPU (vGPU) MP** | NVIDIA | [docs.nvidia.com/vgpu/vrops/latest](https://docs.nvidia.com/vgpu/vrops/latest/grid-management-pack-vmware-vrops-user-guide/index.html) | Official vendor-doc; v3.0–3.3 supports Aria Ops 8.18; GPM metrics for Hopper+ GPUs |
| **Cisco UCS Management Pack** | Cisco | [cisco.com UCS MP user guide](https://www.cisco.com/c/en/us/td/docs/unified_computing/ucs/sw/msft_tools/vCOps/User_guide/b_UCS_mgmt_pack_vROps_UG.html) | Official user guide; v2.x for Aria Operations |
| **VCF Operations MP for Cisco Intersight** | Cisco | [intersight.com help](https://intersight.com/help/saas/resources/VCF_Operations_Management_Pack) | Monitors Intersight Managed Mode (IMM) infra; demo video at youtu.be/fBIF8M4eIzA |
| **Dell EMC PowerFlex MP** | Dell Technologies | [infohub.delltechnologies.com product guide](https://infohub.delltechnologies.com/en-us/section-assets/powerflexadapter-for-vrops-product-guide/) | Collects storage metrics from PowerFlex clusters |
| **Dell EMC PowerEdge MP (True Visibility Suite)** | Dell / VMware True Visibility | [docs.vmware.com TVS guide](https://docs.vmware.com/en/VMware-vRealize-True-Visibility-Suite/1.0/dell-emc-poweredge/GUID-E2B443DE-4EC0-4B20-BB95-B1963F358DAA.html) | Part of TVS compute packs |
| **IBM Storage MP for vROps** | IBM | [ibm.com Spectrum Connect 3.10 docs](https://www.ibm.com/docs/en/spectrum-connect/3.10.0?topic=environment-storage-management-pack-vmware-vrealize-operations-manager) | IBM block storage integration |

### 6.3 True Visibility Suite (TVS) Compute and Storage Packs

VMware bundled a large set of partner-built compute/storage MPs into the True Visibility Suite, entitled to vROps Advanced/Enterprise customers (announced 2021, available via VMware Marketplace):

- Cisco HyperFlex, Cisco UCS
- Dell EMC OpenManage Enterprise, Dell EMC PowerEdge
- HPE OneView, HPE ProLiant
- Lenovo Compute
- (Storage: NetApp, Dell EMC PowerFlex, Hitachi, others)

Reference post: [brockpeterson.com/post/vrtvs-compute-and-storage](https://www.brockpeterson.com/post/vrtvs-compute-and-storage) — blog

**Note:** Many TVS packs reached EOL in October 2024. Check [KB 373307](https://knowledge.broadcom.com/external/article/373307) for current status.

---

## 7. Broadcom Developer Portal

- **Broadcom Developer Portal** (post-acquisition home for VMware developer tools):
  [developer.broadcom.com](https://developer.broadcom.com/) — vendor-doc
  Hosts SDK downloads, API explorer, and sample code.

- **Technology Alliance Program (TAP) Portal** — where partners access MP SDK for certified integrations. Not publicly documented in detail.

---

## 8. Pre-SDK Era Reference (Historical)

- **nagini Python library** — Pre-dates the current Integration SDK. A community Python client for pushing data via the vROps REST API. Used in vraidmon (2015) and other early adapters. No longer actively developed; current SDK supersedes it.
  Reference: [virtualviking.net/2015/12/15/vraidmon-a-vrealize-operations-adapter-written-in-python/](https://virtualviking.net/2015/12/15/vraidmon-a-vrealize-operations-adapter-written-in-python/) — blog

- **vROps REST API Samples (archived):**
  [github.com/vmware-archive/vrops-restapi-samples](https://github.com/vmware-archive/vrops-restapi-samples) — Postman collections and code for vROps 6.x API. Useful for understanding the data model adapters write into.

---

## 9. End-of-Support Landscape (2024–2025)

Broadcom has been EOL-ing many legacy VMware-built MPs:
- **October 1, 2024 EOGS batch:** multiple MPs — see [KB 373307](https://knowledge.broadcom.com/external/article/373307)
- **March 28, 2025:** Horizon MP — see [KB 392309](https://knowledge.broadcom.com/external/article/392309)
- **June 17, 2025:** Additional VCF Operations MP batch — see [KB 400934](https://knowledge.broadcom.com/external/article/400934)

The direction is for partners to rebuild using the Integration SDK or MPB, or for customers to build their own with those tools.

---

## Quick-Reference Index by Technology Monitored

| Technology | Source Type | URL/Reference |
|-----------|------------|---------------|
| Alibaba Cloud ECS | SDK sample (official) | GitHub samples/alibaba-cloud-mp |
| Cisco Intersight | Vendor-doc | intersight.com + Cisco Community |
| Cisco UCS | Vendor-doc | cisco.com user guide |
| Dell EMC PowerEdge | Vendor-doc (TVS) | docs.vmware.com TVS |
| Dell EMC PowerFlex | Vendor-doc + community | infohub.delltechnologies.com + vineethac GitHub |
| Docker containers | Official MP | techdocs.broadcom.com |
| HPE SimpliVity | Open source | HewlettPackard/simplivity-vrops-plugin |
| IBM Storage | Vendor-doc | ibm.com Spectrum Connect |
| Kubernetes/TKG | Official MP | techdocs.broadcom.com |
| Linux software RAID | Blog (nagini) | virtualviking.net |
| MySQL | SDK sample (official) | GitHub samples/mysql-extension-mp |
| NVIDIA vGPU | Vendor-doc | docs.nvidia.com/vgpu/vrops |
| NSX AVI / ALB | SDK sample (official) | GitHub samples/nsx-alb-avi-mp |
| NSX Edge (perf) | VMware-NSX GitHub | vmware-nsx/vrops-edge-monitoring |
| phpIPAM | Blog (MPB) | gibsonvirt.com 4-part series |
| Pi-hole | Blog (MPB) | enterpriseadmins.org |
| Pure Storage FlashArray | Open source | PureStorage-Connect/vROPs-MgmtPak |
| QNAP NAS | Blog (SNMP MP) | vmguru.com |
| Rubrik CDM | Blog (MPB) | brockpeterson.com (2024) |
| ServiceNow CMDB | Official MP + blog | techdocs + vcrocs.info |
| SNMP (generic) | Official MP | techdocs.broadcom.com |
| Tanzu App Platform | Blog (MPB) | vrabbi.cloud |
| TrueNAS | Blog (MPB) | brockpeterson.com (2022) |
| vCenter (extend) | SDK sample + blog | samples/vcenter-extension-mp + vrealize.it |
| VEBA (K8s) | Blog (K8s MP) | rguske.github.io |
| Veeam | Blog (MPB) | veducate.co.uk |
| vROps self-monitoring | Blog (SDK Part 1) | thomas-kopton.de |
| vSphere (broad) | SDK sample | samples/vcenter-extension-mp |

---

*Research completed: 2026-05-13. Sources mixed: whitelisted VMware/Broadcom domains and community blogs. Note filed as `reviewed: false` due to community sources. Verify EOL status of any TVS or legacy pack before recommending to Scott.*
