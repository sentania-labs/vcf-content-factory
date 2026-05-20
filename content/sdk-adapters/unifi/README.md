# VCF Content Factory UniFi Controller

Monitors UniFi infrastructure via the classic Network API and Protect API. Discovers sites, gateways, switches, access points, NVR, and cameras. Per-switch-port and per-AP-radio child objects with PoE tracking. LLDP-based stitching to ESXi hosts. Replaces the Tier 1 UniFi Network and UniFi Network Integration management packs.

## Installation

Upload the `.pak` file via **Administration → Solutions** in VCF Operations.

## Configuration

Create an adapter instance under **Integrations → Repository** and provide:

| Field | Description | Default |
|---|---|---|
| Host / IP Address | | — |
| Port (HTTPS) | | 443 |
| Allow Insecure SSL | | true |

### Credentials

| Field | Description |
|---|---|
| Username | |
| Password | |

## Object Types

- UniFi World
- UniFi Site
- UniFi Gateway
- UniFi WAN Interface
- UniFi Switch
- UniFi Switch Port
- UniFi Access Point
- UniFi Radio
- UniFi Wireless Summary
- UniFi NVR
- UniFi Camera
