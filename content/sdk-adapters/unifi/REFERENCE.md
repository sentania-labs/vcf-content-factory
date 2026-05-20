# VCF Content Factory UniFi Controller — Reference

Generated from `describe.xml` and `resources.properties` for build 1.0.0.2.

## Adapter

| Field | Value |
|---|---|
| Adapter Kind | `unifi_controller` |
| Tier | 2 (Java SDK) |
| Monitoring Interval | 5 minutes |
| License Required | No |

### Credentials

| Field | Key | Type |
|---|---|---|
| Username | `username` | string |
| Password | `password` | string (masked) |

### Connection Settings

| Field | Key | Default | Required |
|---|---|---|---|
| Host / IP Address | `host` | — | Yes |
| Port (HTTPS) | `port` | 443 | No |
| Allow Insecure SSL | `allowInsecure` | true | No |

---

## Object Types

### UniFi World

**Identifier**: `world_id` (World ID)

---

### UniFi Site

**Identifier**: `site_name` (Site Name)

#### Configuration

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `description` | Description | property | — | — |
| `version` | Version | property | — | — |
| `timezone` | Timezone | property | — | — |
| `device_count` | Device Count | property | — | — |

---

### UniFi Gateway

**Identifier**: `mac` (MAC Address)

#### System

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `cpu_pct` | CPU % | metric | % | yes |
| `mem_pct` | Memory % | metric | % | yes |
| `uptime` | Uptime | metric | sec | yes |
| `num_sta` | Connected Clients | metric | — | yes |

#### Temperature

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `temp_cpu` | CPU Temperature | metric | C | yes |
| `temp_local` | Board Temperature | metric | C | yes |
| `temp_phy` | PHY Temperature | metric | C | no |

#### Speedtest

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `xput_up` | Upload Speed | metric | Mbps | yes |
| `xput_down` | Download Speed | metric | Mbps | yes |
| `speedtest_latency` | Speedtest Latency | metric | ms | yes |

#### Configuration

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `model` | Model | property | — | — |
| `firmware` | Firmware | property | — | — |
| `serial` | Serial Number | property | — | — |
| `ip` | IP Address | property | — | — |
| `mac_address` | MAC Address | property | — | — |
| `name` | Name | property | — | — |

---

### UniFi WAN Interface

**Identifier**: `wan_name` (Interface Name)

#### Traffic

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `tx_bytes` | TX Bytes | metric | bytes/s | yes |
| `rx_bytes` | RX Bytes | metric | bytes/s | yes |

#### Health

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `latency` | Latency | metric | ms | yes |
| `availability` | Availability | metric | % | yes |
| `speed` | Speed | metric | Mbps | no |

#### Configuration

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `type` | Type | property | — | — |
| `ip` | IP Address | property | — | — |
| `netmask` | Netmask | property | — | — |
| `gateway_ip` | Gateway IP | property | — | — |
| `dns` | DNS | property | — | — |

---

### UniFi Switch

**Identifier**: `mac` (MAC Address)

#### System

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `cpu_pct` | CPU % | metric | % | yes |
| `mem_pct` | Memory % | metric | % | yes |
| `uptime` | Uptime | metric | sec | yes |
| `num_sta` | Connected Clients | metric | — | yes |
| `satisfaction` | Satisfaction | metric | % | yes |

#### PoE

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `total_max_power` | PoE Budget Max | metric | W | yes |
| `poe_consumption` | PoE Consumption | metric | W | yes |
| `poe_budget_remaining` | PoE Budget Remaining | metric | W | yes |

#### Configuration

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `model` | Model | property | — | — |
| `firmware` | Firmware | property | — | — |
| `serial` | Serial Number | property | — | — |
| `ip` | IP Address | property | — | — |
| `mac_address` | MAC Address | property | — | — |
| `name` | Name | property | — | — |
| `port_count` | Port Count | property | — | — |
| `poe_capable` | PoE Capable | property | — | — |
| `has_fan` | Has Fan | property | — | — |

---

### UniFi Switch Port

**Identifier**: `port_key` (Port Key)

#### Traffic

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `tx_bytes` | TX Bytes | metric | bytes | yes |
| `rx_bytes` | RX Bytes | metric | bytes | yes |
| `tx_errors` | TX Errors | metric | — | yes |
| `rx_errors` | RX Errors | metric | — | yes |

#### Status

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `satisfaction` | Satisfaction | metric | % | yes |
| `mac_table_count` | MAC Table Count | metric | — | no |
| `up` | Link Up | property | — | — |
| `speed` | Speed | property | — | — |
| `duplex` | Duplex | property | — | — |
| `is_uplink` | Is Uplink | property | — | — |
| `media` | Media | property | — | — |
| `stp_state` | STP State | property | — | — |
| `port_name` | Port Name | property | — | — |

#### PoE

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `poe_power` | PoE Power | metric | W | yes |
| `poe_voltage` | PoE Voltage | metric | V | no |
| `poe_current` | PoE Current | metric | mA | no |
| `poe_enable` | PoE Enabled | property | — | — |
| `poe_class` | PoE Class | property | — | — |
| `poe_mode` | PoE Mode | property | — | — |

#### LLDP

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `lldp_system_name` | LLDP System Name | property | — | — |
| `lldp_port_id` | LLDP Port ID | property | — | — |
| `lldp_chassis_id` | LLDP Chassis ID | property | — | — |

---

### UniFi Access Point

**Identifier**: `mac` (MAC Address)

#### System

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `cpu_pct` | CPU % | metric | % | yes |
| `mem_pct` | Memory % | metric | % | yes |
| `uptime` | Uptime | metric | sec | yes |
| `num_sta` | Connected Clients | metric | — | yes |
| `satisfaction` | Satisfaction | metric | % | yes |

#### Configuration

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `model` | Model | property | — | — |
| `firmware` | Firmware | property | — | — |
| `serial` | Serial Number | property | — | — |
| `ip` | IP Address | property | — | — |
| `mac_address` | MAC Address | property | — | — |
| `name` | Name | property | — | — |

---

### UniFi Radio

**Identifier**: `radio_key` (Radio Key)

#### RF

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `channel` | Channel | metric | — | yes |
| `tx_power` | TX Power | metric | dBm | yes |
| `cu_total` | Channel Utilization | metric | % | yes |
| `satisfaction` | Satisfaction | metric | % | yes |
| `tx_retries_pct` | TX Retries % | metric | % | yes |

#### Clients

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `user_num_sta` | Client Count | metric | — | yes |

#### Traffic

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `tx_bytes` | TX Bytes | metric | bytes | yes |
| `rx_bytes` | RX Bytes | metric | bytes | yes |

#### Configuration

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `radio_type` | Radio Type | property | — | — |
| `radio_name` | Radio Name | property | — | — |
| `ht` | HT Mode | property | — | — |
| `min_txpower` | Min TX Power | property | — | — |
| `max_txpower` | Max TX Power | property | — | — |

---

### UniFi Wireless Summary

**Identifier**: `aggregate_id` (Aggregate ID)

#### Clients

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `num_user` | Users | metric | — | yes |
| `num_guest` | Guests | metric | — | yes |
| `num_iot` | IoT Devices | metric | — | yes |
| `num_disconnected` | Disconnected | metric | — | yes |

#### Performance

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `num_ap` | AP Count | metric | — | yes |
| `tx_bytes_r` | TX Rate | metric | bytes/s | yes |
| `rx_bytes_r` | RX Rate | metric | bytes/s | yes |

---

### UniFi NVR

**Identifier**: `nvr_mac` (MAC Address)

#### System

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `uptime` | Uptime | metric | sec | yes |

#### Storage

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `used_bytes` | Used | metric | bytes | yes |
| `total_bytes` | Total | metric | bytes | yes |
| `usage_pct` | Usage % | metric | % | yes |

#### Configuration

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `model` | Model | property | — | — |
| `firmware` | Firmware | property | — | — |
| `name` | Name | property | — | — |
| `host_type` | Host Type | property | — | — |
| `recording_retention_mode` | Retention Mode | property | — | — |
| `camera_count` | Camera Count | property | — | — |

---

### UniFi Camera

**Identifier**: `camera_mac` (MAC Address)

#### Status

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `uptime` | Uptime | metric | sec | yes |
| `last_motion` | Last Motion | metric | sec | no |
| `state` | State | property | — | — |
| `is_connected` | Connected | property | — | — |
| `is_recording` | Recording | property | — | — |

#### Hardware

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `model` | Model | property | — | — |
| `firmware` | Firmware | property | — | — |
| `type` | Type | property | — | — |
| `is_wireless` | Wireless | property | — | — |
| `phy_rate` | PHY Rate | property | — | — |

#### Network

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `ip` | IP Address | property | — | — |
| `mac_address` | MAC Address | property | — | — |

---

## Traversal Spec

**Name**: UniFi Controller Infrastructure

```
unifi_controller
    └── UniFi World
        └── UniFi Site
            ├── UniFi Gateway
            │   └── UniFi WAN Interface
            ├── UniFi Switch
            │   └── UniFi Switch Port
            ├── UniFi Access Point
            │   └── UniFi Radio
            ├── UniFi NVR
            │   └── UniFi Camera
            └── UniFi Wireless Summary
```
