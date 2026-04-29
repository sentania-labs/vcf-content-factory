# VCF Content Factory — Distribution Package

This archive is a VCF Content Factory distribution package.  It may contain
one or more **bundles**, each of which packages a set of super metrics, views,
dashboards, custom groups, symptoms, alerts, and/or report definitions for a
specific use-case.

---

## Package layout

```
install.py          Python installer (recommended)
install.ps1         PowerShell installer
README.md           This file
LICENSE
bundles/
  <bundle-slug>/
    bundle.json     Bundle metadata and content manifest
    README.md       Bundle-specific description and instructions
    supermetric.json        Drag-drop: Super Metrics > Import
    customgroup.json        Drag-drop: Custom Groups > Import
    Views.zip               Drag-drop: Views > Import
    Dashboard.zip           Drag-drop: Dashboards > Import
    Reports.zip             Drag-drop: Reports > Import
    AlertContent.xml        Drag-drop: Alerts/Symptoms/Recommendations import
    content/                Installer source (read by install.py at runtime)
      supermetrics.json
      dashboard.json
      views_content.xml
      customgroup.json
      symptoms.json
      alerts.json
      reports_content.xml
```

Not all bundles include every file — only those relevant to the bundle's
content are present.

---

## Authentication

The install scripts authenticate to VCF Operations using local accounts and
auth-source-attached identity providers that support server-side password
validation.

**Supported** (programmatic install):
- **Local** — a local VCF Ops admin or service account (recommended)
- **vCenter SSO** (`VC` / `VC_GROUP`) — vCenter SSO credentials, configured
  as an auth source in VCF Ops
- **Active Directory** — domain credentials in UPN form
  (`user@corp.example.com`)
- **LDAP** — per the VCF Operations Suite API documentation; bind-validatable
  LDAP credentials should work, but this path is not yet covered by our
  test matrix

**Not supported** (use a Local service account instead):
- **VCF Identity Broker** ("VCF SSO" / `VIDB`) — federated SSO; the Suite API
  refuses programmatic password authentication for VIDB-typed sources. A
  future VCF Operations release is expected to address this; check Broadcom
  support documentation for updates.
- **VMware Identity Manager / Workspace ONE Access** (`VIDM`) — federated SSO;
  programmatic password authentication was empirically refused on the
  Ops versions we tested. Treat as unsupported until verified against your
  specific environment.

If your VCF Operations instance is configured only with `VIDB` or `VIDM`
auth sources, create a local service account for automation use.

> The auth-source landscape evolves with each Ops release. Watch this
> README and the framework's documentation for updates.

---

## Install paths

### Automated install (recommended)

The Python installer handles all content types in the correct order,
stamps instance-specific values at install time, enables super metrics on
the Default Policy, and verifies enablement.

```
python3 install.py
```

PowerShell equivalent (PS 5.1+ compatible):

```powershell
.\install.ps1
```

Both scripts:
- Prompt interactively for host, user, auth source, and password.
- Accept CLI flags (`--host`, `--user`, `--password`, `--auth-source`).
- Accept environment variables (`VCFOPS_HOST`, `VCFOPS_USER`,
  `VCFOPS_PASSWORD`, `VCFOPS_AUTH_SOURCE`).
- Support `--uninstall` / `-Uninstall` to remove all content.
- Exit 0 on full success, 2 on partial failure (warnings).

When multiple bundles are present (multiple zips extracted into the same
directory), the installer presents a checklist of discovered bundles
(all pre-selected) and prompts for confirmation.

Run with `--help` (Python) or `-?` (PowerShell) for all options.

> **Policy enablement caveat.** The install script enables imported super
> metrics on the **Default Policy** only. If your deployment uses
> non-default, non-inheriting policies, you may need to manually enable the
> imported super metrics in those policies — otherwise dashboard cells and
> view columns that depend on those metrics will appear blank for resources
> scoped under those policies. Check `Administration > Policies` after
> install to confirm enablement on every policy that needs to see the
> bundle's data.

### Manual drag-drop import

Each bundle subdirectory ships community-convention artifacts for per-object
UI import in the VCF Operations web console.  Navigate to the bundle
directory and drag the relevant file into the matching UI dialog:

| File | VCF Ops UI location |
|---|---|
| `supermetric.json` | Administration > Super Metrics > Import |
| `Views.zip` | Manage > Views > Import |
| `Dashboard.zip` | Manage > Dashboards > Import |
| `customgroup.json` | Environment > Custom Groups > Import |
| `AlertContent.xml` | Alerts > Alert Definitions > Import |
| `Reports.zip` | Administration > Content > Reports > Import |

**Why manual import is limited:**

The installer handles steps that cannot be pre-baked into the drag-drop
artifacts:

- **Instance marker file** — The VCF Ops content-zip importer requires a
  per-instance marker file (a filename that ends `L.v1`) to be present in
  the outer zip.  This value is instance-specific and is discovered by the
  installer at runtime.  Drag-drop zips cannot carry this value.

- **Owner UUID stamping** — Dashboard JSON embeds the importing user's UUID.
  The installer resolves the real UUID at runtime; the drag-drop
  `Dashboard.zip` uses the nil UUID (`00000000-0000-0000-0000-000000000000`)
  as a best-effort placeholder that the UI may replace on import.

- **Super metric policy enablement** — After importing super metrics the
  installer automatically enables them on the Default Policy via the internal
  API.  Manual import requires a separate enablement step in
  Administration > Policies > Default Policy > Super Metrics.

- **Symptom/alert REST ordering** — The installer syncs symptoms before
  alerts (alerts reference symptoms by server-assigned ID).  When importing
  manually, import symptoms first, then alerts.

---

## Uninstall

To remove all content installed by this package:

```
python3 install.py --uninstall
```

```powershell
.\install.ps1 -Uninstall
```

**Admin account required for dashboards and views.**  VCF Ops locks
imported dashboards and views to the `admin` account.  Only the admin
user's UI session can delete them.  Re-run with `--user admin`
(or `VCFOPS_USER=admin`) if your install used a different account.

Report definitions are deleted via the Ext.Direct UI session endpoint
(same mechanism as dashboards and views). The `admin` account is required.

---

## Source

This package was generated by the
[sentania-labs/vcf-content-factory](https://github.com/sentania-labs/vcf-content-factory)
framework (VCF Content Factory).  The authoritative YAML source for all
content in this package lives in that repository.  Administrators who
prefer to audit or customise content before importing can find the full
YAML definitions there.

---

## Requirements

- Python 3.8+ **or** PowerShell 5.1+
- Network access to your VCF Operations instance
- VCF Operations account with write access to content and policies

---

_Generated by vcfops_packaging._
