# VCF Content Factory Compliance — Reference

Generated from `describe.xml` and `resources.properties` for build 1.0.0.5.

## Adapter

| Field | Value |
|---|---|
| Adapter Kind | `vcfcf_compliance` |
| Tier | 2 (Java SDK) |
| Monitoring Interval | 60 minutes |
| License Required | No |

### Credentials

| Field | Key | Type |
|---|---|---|
| Username | `username` | string |
| Password | `password` | string (masked) |
| VCF Ops Password | `ops_password` | string (masked) |

### Connection Settings

| Field | Key | Default | Required |
|---|---|---|---|
| vCenter Host / IP | `vcenter_host` | — | Yes |
| Benchmark Profile (CIS_8.0, CIS_9.0, or Custom) | `benchmark_profile` | CIS_8.0 | No |
| Custom Profile Path (if Custom) | `custom_profile_path` | — | No |
| Allow Insecure SSL (true/false) | `allowInsecure` | true | No |
| VCF Ops Host (blank = localhost) | `ops_host` | — | No |
| VCF Ops Username (for Suite API property push) | `ops_user` | admin | No |
| VCF Ops Auth Source (Local or vIDM) | `ops_auth_source` | Local | No |

---

## Object Types

### Compliance World

**Identifier**: `world_id` (World ID)

#### Summary

| Key | Label | Type | Unit | Monitored |
|---|---|---|---|---|
| `total_hosts` | Total Hosts Scanned | metric | — | yes |
| `avg_host_score` | Average Host Compliance Score | metric | % | yes |
| `hosts_below_threshold` | Hosts Below Threshold | metric | — | yes |
| `profile_name` | Active Profile | property | — | — |
| `last_scan_timestamp` | Last Scan Timestamp | property | — | — |

---
