# Installing & Configuring: Baseline Stitch-Only Pak

> **Scaffold:** edit this file with actual prerequisites and steps. It is generated
> once and not overwritten on subsequent builds.

## Prerequisites

- VCF Operations 8.0 or later
- <!-- describe target system access requirements here -->

## Permissions Required

<!-- List permissions the adapter credential account needs. -->

## Network Requirements

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 443  | HTTPS    | Outbound  | <!-- describe target endpoint --> |

## Configuration Fields

When adding a new adapter instance in VCF Operations, you will be prompted for:

| Field | Key | Required | Default | Notes |
|-------|-----|----------|---------|-------|
| vCenter Host | `vcenter_host` | Yes | - | |

## Step-by-Step Installation

1. Install the `.pak` file via **Administration > Solutions > Add**.
2. After installation, navigate to **Data Sources > Integrations > Accounts**.
3. Click **Add Account** and select **Baseline Stitch-Only Pak**.
4. Fill in the configuration fields above.
5. Click **Validate Connection**, then **Add**.

## Troubleshooting

<!-- Common issues and solutions. -->
