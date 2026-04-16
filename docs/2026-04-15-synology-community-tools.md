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
  - url: https://github.com/N4S4/synology-api
    domain: github.com
    type: community
  - url: https://github.com/mib1185/py-synologydsm-api
    domain: github.com
    type: community
  - url: https://github.com/hacf-fr/synologydsm-api
    domain: github.com
    type: community
  - url: https://github.com/kwent/syno
    domain: github.com
    type: community
  - url: https://github.com/ddiiwoong/synology-prometheus
    domain: github.com
    type: community
  - url: https://github.com/prometheus/snmp_exporter
    domain: github.com
    type: community
  - url: https://hub.docker.com/r/jantman/prometheus-synology-api-exporter
    domain: hub.docker.com
    type: community
  - url: https://github.com/wozniakpawel/synology-grafana-prometheus-overly-comprehensive-dashboard
    domain: github.com
    type: community
  - url: https://grafana.com/grafana/dashboards/14284-synology-nas-details/
    domain: grafana.com
    type: community
  - url: https://grafana.com/grafana/dashboards/18643-synology-snmp/
    domain: grafana.com
    type: community
  - url: https://grafana.com/grafana/dashboards/14364-synology-nas-overview/
    domain: grafana.com
    type: community
  - url: https://grafana.com/grafana/dashboards/13516-synology-snmp-dashboard/
    domain: grafana.com
    type: community
  - url: https://www.home-assistant.io/integrations/synology_dsm/
    domain: home-assistant.io
    type: community
  - url: https://colby.gg/posts/2023-10-17-monitoring-synology/
    domain: colby.gg
    type: blog
  - url: https://mariushosting.com/monitor-your-synology-with-grafana-and-prometheus-dashboard/
    domain: mariushosting.com
    type: blog
  - url: https://community.veeam.com/blogs-and-podcasts-57/how-to-monitor-synology-nas-with-prometheus-and-grafana-8715
    domain: community.veeam.com
    type: blog
  - url: https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/3-3/vmware-vrealize-operations-management-pack-for-snmp-3-3/vmware-vrealize-operations-management-pack-for-snmp.html
    domain: techdocs.broadcom.com
    type: vendor-doc
topics: [vcf-ops, monitoring]
tags: [synology, management-pack, mpb, rest-api, prometheus, grafana, snmp]
---

# Synology Community Tools and Existing Integrations

> **Revision note (2026-04-16):** API count and per-LUN I/O capability notes updated against live API testing on a DS1520+ running DSM 7.3.2-86009 Update 1. Community tool accuracy is unchanged. See also the live-tested brief at `workspaces/sentania-lab-toolkit/docs/reference-synology-api-mp-brief.md`.

## Python API Wrappers

### N4S4/synology-api (Primary Comprehensive Wrapper)

- **Repository**: [github.com/N4S4/synology-api](https://github.com/N4S4/synology-api)
- **Stars**: 533 | **Forks**: 165 | **Commits**: 930
- **Latest**: v0.8.2 (December 2025)
- **License**: MIT
- **Install**: `pip3 install synology-api`
- **DSM Support**: 5.x, 6.x, 7.x

Covers 300+ APIs across all major Synology services per community documentation. **Live API discovery on DSM 7.3.2 returned 674 total API namespaces** — community wrappers document a subset. The [supported APIs page](https://n4s4.github.io/synology-api/docs/apis) documents available namespaces including system, storage, hardware, network, Docker, backup, and more.

Key monitoring-relevant methods:
- `get_all_system_utilization()` -- CPU, memory, network, disk utilization
- `get_cpu_utilization()` -- CPU breakdown (user, system, other)
- `get_disk_utilization()` -- Per-disk I/O stats
- `get_memory_utilization()` -- RAM and swap usage
- Storage info via dedicated storage module

**Relevance for MP**: Useful as a reference implementation for understanding which APIs return which data. The method names map closely to the SYNO.* API namespaces. **Gap**: does not expose the `lun[]` array from `SYNO.Core.System.Utilization` — the per-iSCSI-LUN IOPS/throughput/latency metrics that are the critical bridge for ESXi-to-storage correlation. Use the raw API directly for MP development.

### mib1185/py-synologydsm-api (Home Assistant Integration)

- **Repository**: [github.com/mib1185/py-synologydsm-api](https://github.com/mib1185/py-synologydsm-api)
- **Commits**: 480+ | **Latest**: v2.8.0 (April 2026)
- **License**: MIT
- **Async**: Yes (aiohttp-based)

This is the library powering the [Home Assistant Synology DSM integration](https://www.home-assistant.io/integrations/synology_dsm/). Used by 9.7% of active Home Assistant installations.

Supported modules:
- **Information**: Model, RAM, serial, temperature, uptime, DSM version
- **Utilisation**: CPU load, memory usage, network stats
- **Storage**: Volume status/capacity/usage, disk SMART status/temperature
- **Share**: Shared folder properties
- **System**: CPU info, NTP, timezone, reboot/shutdown
- **Upgrade**: Update availability
- **Download Station**: Task management
- **File Station**: File operations
- **Surveillance Station**: Camera management
- **Photos**: Album and photo operations
- **Virtual Machine Manager**: VM operations
- **External USB**: USB device management

**Relevance for MP**: Best reference for understanding the exact JSON response structure of monitoring APIs, since it's actively maintained and well-tested across many NAS models. **Gap**: Storage module references `SYNO.Core.Storage.*` namespaces which are not present on DSM 7.3.2 — use `SYNO.Storage.CGI.Storage` `load_info` directly. Also does not expose per-LUN I/O metrics from `SYNO.Core.System.Utilization`.

### hacf-fr/synologydsm-api (Archived)

- **Repository**: [github.com/hacf-fr/synologydsm-api](https://github.com/hacf-fr/synologydsm-api)
- **Status**: Archived February 2025
- **Successor**: mib1185/py-synologydsm-api (above)

Previously the Home Assistant integration library. Still useful for historical reference.

## Node.js Wrappers

### kwent/syno

- **Repository**: [github.com/kwent/syno](https://github.com/kwent/syno)
- **DSM Support**: 5.x, 6.x

Node.js wrapper with a critical feature for MP development: the [definitions directory](https://github.com/kwent/syno/tree/master/definitions) contains `.lib` files extracted from DSM that list every API namespace, its methods, supported versions, and access levels. These are the closest thing to a complete API schema that exists outside Synology.

**Relevance for MP**: The API definition files are invaluable for discovering undocumented APIs and their method signatures.

## Prometheus Exporters

### SNMP-Based (Recommended Approach)

**prometheus/snmp_exporter** (official Prometheus project):
- **Repository**: [github.com/prometheus/snmp_exporter](https://github.com/prometheus/snmp_exporter)
- Exposes SNMP data in Prometheus-compatible format
- Requires custom configuration for Synology MIBs (default config does not include Synology)
- SNMPv3 recommended for security (configure in DSM Control Panel)

**ddiiwoong/synology-prometheus**:
- **Repository**: [github.com/ddiiwoong/synology-prometheus](https://github.com/ddiiwoong/synology-prometheus)
- Complete stack: snmp-exporter + Prometheus + Grafana for Synology
- Pre-configured SNMP generator config for Synology MIBs

**Practical walkthrough**: [Monitoring Synology NAS with Prometheus & SNMP](https://colby.gg/posts/2023-10-17-monitoring-synology/) by colby.gg provides a step-by-step guide for setting up SNMP-based monitoring.

### REST API-Based

**jantman/prometheus-synology-api-exporter**:
- **Docker image**: [hub.docker.com/r/jantman/prometheus-synology-api-exporter](https://hub.docker.com/r/jantman/prometheus-synology-api-exporter)
- Uses the Synology REST API via the `synologydsm-api` Python package
- Created because SNMP exporter doesn't expose per-disk and per-volume I/O utilization percentages
- Configuration via environment variables: `DSM_IP`, `DSM_USER`, `DSM_PASS`, `DSM_PORT` (default 5000), `DSM_USE_HTTPS`
- Status: experimental/alpha

**Relevance for MP**: This project demonstrates that the REST API provides richer per-disk/per-volume I/O metrics than SNMP alone. Worth examining for metric definitions.

## Grafana Dashboards

Several pre-built Grafana dashboards for Synology NAS monitoring exist on Grafana Labs:

### SNMP-Based Dashboards

| Dashboard | ID | Notes |
|-----------|------|-------|
| [Synology NAS Details](https://grafana.com/grafana/dashboards/14284-synology-nas-details/) | 14284 | Tested on DSM 6.2/7.0/7.1/7.2; DS1511+/DS918+/DS920+/DS923+ |
| [Synology SNMP](https://grafana.com/grafana/dashboards/18643-synology-snmp/) | 18643 | SNMP-only, no containers needed, works on J-series |
| [Synology NAS Overview](https://grafana.com/grafana/dashboards/14364-synology-nas-overview/) | 14364 | Overview dashboard |
| [Synology SNMP Dashboard](https://grafana.com/grafana/dashboards/13516-synology-snmp-dashboard/) | 13516 | Alternative SNMP dashboard |

### Comprehensive Stack

**wozniakpawel/synology-grafana-prometheus-overly-comprehensive-dashboard**:
- **Repository**: [github.com/wozniakpawel/synology-grafana-prometheus-overly-comprehensive-dashboard](https://github.com/wozniakpawel/synology-grafana-prometheus-overly-comprehensive-dashboard)
- Complete Docker stack: Grafana + Prometheus + cAdvisor + Speedtest Exporter + Node Exporter + SNMP Exporter + UPS stats
- Monitors CPU, memory, network, disk, Docker containers, UPS

**Relevance for MP**: These dashboards define which metrics are most valuable to operators. Use them as a guide for which metrics to prioritize in the management pack.

## Home Assistant Integration

- **URL**: [home-assistant.io/integrations/synology_dsm/](https://www.home-assistant.io/integrations/synology_dsm/)
- **Adoption**: 9.7% of active installations
- **Introduced**: Home Assistant v0.32

Provides sensors for:
- CPU utilization (current, 1min, 5min, 15min load)
- Memory utilization (total, free, percentage)
- Network upload/download rates
- System temperature and uptime
- Per-disk temperature, status, and SMART status
- Per-volume status, size, usage percentage, average/max disk temperature
- Binary sensors for security status, disk health, bad sector threshold, remaining life threshold
- Surveillance Station home mode switch
- Reboot/shutdown buttons

**Relevance for MP**: The most battle-tested consumer of the Synology API, across hundreds of NAS models. If something works in Home Assistant, it will work in your MP.

## SNMP MIBs

Synology publishes official SNMP MIB files. The [SNMP MIB Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Firmware/DSM/All/enu/Synology_DiskStation_MIB_Guide.pdf) (last updated March 2025) is the definitive reference.

All Synology-specific OIDs are under enterprise OID **1.3.6.1.4.1.6574**:
- **SYNOLOGY-SYSTEM-MIB** (.1) -- System status, temperature, fans, CPU/memory utilization, model, version
- **SYNOLOGY-DISK-MIB** (.2) -- Per-disk ID, model, type, status, temperature
- **SYNOLOGY-RAID-MIB** (.3) -- Per-RAID name, status, free/total size
- **SYNOLOGY-UPS-MIB** (.4) -- UPS status (depends on connected UPS capabilities)

MIB files can be browsed online at:
- [Observium MIB Browser - SYNOLOGY-SYSTEM-MIB](https://mibs.observium.org/mib/SYNOLOGY-SYSTEM-MIB/)
- [MIB Browser Online - SYNOLOGY-DISK-MIB](https://mibbrowser.online/mibdb_search.php?mib=SYNOLOGY-DISK-MIB)

Standard MIBs also supported: HOST-RESOURCES-MIB, IF-MIB, UCD-SNMP-MIB.

## Existing vROps / VCF Operations Integrations

### Synology-Specific Management Pack

**No dedicated Synology management pack exists** for VCF Operations (Aria Operations / vROps). This is a gap in the ecosystem.

### SNMP Management Pack (Generic)

The [VMware Aria Operations Management Pack for SNMP](https://techdocs.broadcom.com/us/en/vmware-cis/aria/aria-operations-for-integrations/3-3/vmware-vrealize-operations-management-pack-for-snmp-3-3/vmware-vrealize-operations-management-pack-for-snmp.html) can monitor any SNMP-capable device, including Synology NAS. However:
- It requires manual OID configuration
- Does not provide Synology-specific object types, dashboards, or alerts
- Less rich than a purpose-built REST API management pack

### Approach Comparison: REST API vs SNMP for a Synology MP

| Aspect | REST API | SNMP |
|--------|----------|------|
| Data richness | Higher -- per-disk I/O utilization, per-LUN IOPS/latency, Docker, backup tasks, packages | Lower -- system-level aggregates |
| Per-iSCSI-LUN I/O | Yes -- IOPS, throughput, latency per LUN (`SYNO.Core.System.Utilization` `lun[]`) | Not available |
| ESXi-to-storage mapping | Yes -- LUN name/UUID joins to iSCSI target IQN | Not available |
| Authentication | Session-based (username/password) | Community string or SNMPv3 |
| Setup complexity | Moderate (session management) | Low (enable SNMP on NAS) |
| MPB support | REST adapter (native) | Would need SNMP MP or custom adapter |
| Metrics for volumes | Usage %, status, fs_type (via `SYNO.Storage.CGI.Storage` `load_info`) | Free/total size, basic status |
| Metrics for services | Package status, Docker containers | Not available via SNMP |
| Backup monitoring | Task status, last run (`SYNO.ActiveBackup.*`) | Not available via SNMP |
| Rate limiting | None documented; be conservative | Standard SNMP polling |

**Recommendation**: Use the REST API as the primary data source for a custom management pack built with MPB. The REST API provides significantly richer monitoring data — especially per-iSCSI-LUN I/O metrics (critical for ESXi-to-storage latency correlation), storage details, Docker containers, backup tasks, and service status. SNMP can supplement for basic hardware metrics if needed.
