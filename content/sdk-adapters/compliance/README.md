# VCF Content Factory Compliance Adapter

Monitors ESXi hosts for CIS benchmark compliance by querying vCenter
configuration and evaluating controls against a user-selectable security
profile. Pushes per-control compliance properties and aggregate scores
onto existing VMWARE HostSystem resources via ARIA_OPS stitching.

## Quick start

1. Build: `python3 -m vcfops_managementpacks build-sdk content/sdk-adapters/compliance`
2. Install the `.pak` from `dist/` via VCF Ops UI or CLI
3. Add adapter instance: provide vCenter host, credentials, select benchmark profile
4. Wait one collection cycle (default 60 minutes)
5. Check host compliance: Environment > select host > All Metrics > VCF-CF Compliance

## Adapter instance configuration

| Field | Required | Default | Description |
|---|---|---|---|
| vCenter Host | Yes | - | vCenter FQDN or IP |
| Username | Yes | - | vCenter SSO credentials |
| Password | Yes | - | vCenter SSO credentials |
| Benchmark Profile | No | CIS_8.0 | CIS_8.0, CIS_9.0, or Custom |
| Custom Profile Path | No | - | Filesystem path to CSV if Custom |
| Allow Insecure SSL | No | true | Accept self-signed certificates |

## Benchmark profiles

Bundled profiles ship with the pak under `profiles/`:
- `cis_esxi_8.0.csv` — CIS vSphere 8.0 Security Configuration Guide

Custom profiles must follow the VMware SCG CSV format (27 columns).
Upload the CSV to the VCF Ops appliance and reference the path.

## Property naming

Per-control properties on VMWARE HostSystem:
```
VCF-CF Compliance|<profile>|<scg-id>|Actual
VCF-CF Compliance|<profile>|<scg-id>|Expected
VCF-CF Compliance|<profile>|<scg-id>|Compliant   (0 or 1)
VCF-CF Compliance|<profile>|<scg-id>|Description
```

Aggregate metrics:
```
VCF-CF Compliance|score          (0-100%)
VCF-CF Compliance|pass_count
VCF-CF Compliance|fail_count
VCF-CF Compliance|total_count
VCF-CF Compliance|profile_name
```

## Phase 1 limitations

- REST-only vCenter API access — controls requiring SOAP (advanced
  host settings) are skipped as N/A until Phase 1.1
- Hosts only (VMs are a stretch goal)
- No remediation actions (Phase 2)
