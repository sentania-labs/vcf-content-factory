# DEF-012 closure — visual render proof (2026-07-16)

**Verdict: DEF-012 CLOSES.** All 14 tracked distribution widgets across the
three affected dashboards render live DISCRETE bucket data on devel under
build-13.

- **Instance:** devel (`vcf-lab-operations-devel.int.sentania.net`,
  VCF Operations 9.0.2.0 build 25137838)
- **Build under test:** `vcfcf_sdk_vcommunity_vsphere.0.0.0.13.pak` (dev
  preview, sha256 `c1f903273f…ccc8d4ec`), built from pak-repo main @
  `72c1b42` (PR #7 merge), installed 2026-07-16 15:44 CDT via
  `vcfops_managementpacks install` (downgrade over released `1.0.0.12`,
  accepted without refusal; all 3 adapter instances healthy post-install).
- **Method:** Playwright browser pass (qa-tester), hard-refresh + wait
  before each verdict, scope datacenter `vcf-lab-mgmt-dc01` (5 ESXi hosts /
  1 cluster / 1 dvSwitch). Bucket values cross-checked against the raw
  per-host / per-portgroup property tables — exact match.
- **Prior state:** same widgets confirmed "No data to display" in the
  2026-07-16 full QA sweep earlier the same day (pre-install), matching the
  DEF-012 registration.

## Per-widget results

### ESXi Configuration 2.0

| Widget | Verdict | Buckets observed |
|---|---|---|
| CPU Model | RENDERS DATA | AMD Ryzen 9 9955HX ×4, Intel Celeron J6412 ×1 |
| ESXi Versions | RENDERS DATA | 9.1.0-25433460 ×5 |
| BIOS Version | RENDERS DATA | 1.02 ×4, EHL30T301 ×1 |
| Power Management (ESXi) | RENDERS DATA | High Performance ×4, Balanced ×1 |
| Power Management (BIOS) | RENDERS DATA | ACPI P-states/C-states ×4, ACPI CPPC/C-states ×1 |
| Hyper Threading | RENDERS DATA | true ×4, false ×1 |

### vSphere Cluster Configuration 2.0

| Widget | Verdict | Buckets observed |
|---|---|---|
| HA Enabled | RENDERS DATA | true ×1 |
| DRS Enabled | RENDERS DATA | true ×1 |
| DPM Enabled | RENDERS DATA | false ×1 |
| DRS Automated | RENDERS DATA | fullyAutomated ×1 |

The separate "HA Admission Control enabled" widget still shows "View
request timed out" — **not** a DEF-012 widget or regression; tracked as
FB-011.

### vSphere Network Configuration 2.0

| Widget | Verdict | Buckets observed |
|---|---|---|
| Switch Version | RENDERS DATA | 9.0.0 ×1 |
| Port Group: Forged Transmit | RENDERS DATA | false ×6, true ×2 |
| Port Group: MAC Address Change | RENDERS DATA | false ×8 |
| Port Group: Promiscuous Mode | RENDERS DATA | false ×8 |

## Observations for the record (not defects)

- **First-open render race:** immediately after clicking a dashboard in the
  tree, all widgets briefly showed "The widget is not configured. Select a
  view to render."; a hard refresh cleared it consistently. Client-side
  race on first tab-open, cleared on every dashboard tested; did not affect
  verdicts.
- Screenshots were session artifacts and are not retained in the repo
  (per the no-troubleshooting-screenshots convention).
