# Design: Compliance Host List View

## Initial prompt

"Author compliance dashboards: Compliance Overview (heatmap + scoreboard) and Drift Timeline."

The dashboard needs an upstream list view showing HostSystem compliance data.

## Vision

- List view targeting VMWARE/HostSystem resources.
- Shows compliance score, pass/fail/total counts, profile name per host.
- Serves as the resource picker and data table for the compliance dashboard.
- Columns: Host Name, Compliance Score (%), Pass Count, Fail Count, Total Count, Profile Name.
- Compliance score column uses color-coded thresholds (green >95, yellow >80, red <=80).
- Sort by compliance score ascending (worst first) so non-compliant hosts surface to top.
