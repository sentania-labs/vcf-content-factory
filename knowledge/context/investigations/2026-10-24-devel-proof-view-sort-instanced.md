# Devel proof: view-level `sort:` on a fanned-out instanced list view and two flat controls

- Run: 2026-10-24, 00:26 to about 00:40 America/Chicago, content-installer.
- Instance: profile `devel`, VCF Operations 9.0.2 (standing approval `knowledge/context/approvals/2026-10-15-all-devel-dev-paks.md`). Main checkout, uncommitted working tree.
- Method: `vcfcf_dashboards --views-dir <temp dir holding only the three view YAMLs> --dashboards-dir <empty temp dir> sync --profile devel --skip-materialization-check` (sync has no path argument, so the directories were narrowed; no dashboards, no enable changes). Then a CUSTOM `VIEW_DEFINITIONS` content export (the factory's own `_run_content_export`) for the stored definition, and `GET /internal/views/{id}/data/export?resourceId=<vSphere World ba1fe374-...>` with `X-Ops-API-use-unsupported: true` for the rendered data. Nothing was deleted; the three views were overwritten in place by name.
- Brief correction: the `datastore_reclaimable_space.yaml` control is `sort: desc` on "Snapshot Space (GB)", not `sort: asc` on "Capacity Remaining %". Only `cluster_capacity_breakdown.yaml` is `asc` on "Capacity Remaining %". Both are still plain one-row-per-object controls.

## Result

| View | Stored `sortCriteria` | Rendered order | Verdict |
|---|---|---|---|
| VM Snapshot Inventory (instanced, `sort: desc` on Total Snapshot Space (GB)) | one Property, `false` (descending), on that column only | 32 rows, column `10` strictly non-increasing; 20 VMs, each VM's snapshots contiguous | PASS |
| Datastore Reclaimable Space (control, `sort: desc` on Snapshot Space (GB)) | one Property, `false`, on that column only | 12 rows, column `4` non-increasing | PASS |
| Cluster Capacity Breakdown (control, `sort: asc` on Capacity Remaining %) | one Property, `true` (ascending), on that column only | 3 rows, column `13` non-decreasing (0.0, 17.33, 34.73) | PASS (only 3 rows, weak) |
| Visual verification | | | VISUAL VERIFICATION: SKIPPED (Playwright MCP failed to connect: CONNECTION_CLOSED) |

Sync output:

```
state: FINISHED
  VIEW_DEFINITIONS     imported=3 skipped=0 failed=0 state=FINISHED
DEP-OK  OOTB metric check: all referenced metrics are defaultMonitored=true
```

Instance IDs (same as the YAML `id:`): Snapshot Inventory `38957c6d-0f1d-432e-85fb-683272cf3383`, Datastore Reclaimable Space `faabf549-64c8-4003-afcc-8966f18f3eb6`, Cluster Capacity Breakdown `0a1c11af-222b-41e0-af4c-dd324d7dacc0`.

## Stored definitions

Each view XML in the export contains exactly one `sortCriteria` Property, on the declared column and no other (counted per `ViewDef`).

VM Snapshot Inventory, column "Total Snapshot Space (GB)" (the last column; the nine columns before it carry none):

```xml
<Property name="sortCriteria" value="false"/>
```

Datastore Reclaimable Space, column "Snapshot Space (GB)":

```xml
<Property name="sortCriteria" value="false"/>
```

Cluster Capacity Breakdown, column "Capacity Remaining %":

```xml
<Property name="sortCriteria" value="true"/>
```

Direction mapping (`true` ascending, `false` descending) is the one in `wire-formats/dashboard_sort_color_default_summary_rows.md` section #175.

## Rendered data

### VM Snapshot Inventory (fanned out, one row per snapshot)

32 data rows, no summary row, 20 distinct VMs. The Total Snapshot Space (GB) column (key `10`) equals its own descending sort, and a VM's rows are one contiguous run (20 runs for 20 distinct `objUUID`s, so no VM is split). First ten rows (columns: VM, Snapshot Name, Age, Snapshot Space GB, Total Snapshot Space GB):

| # | VM (`objId`) | Snapshot Name | Age | Snapshot GB | Total GB |
|---|---|---|---|---|---|
| 1 | worker | pre-log-forwarding-20261006-1153 | 17 | 59.79 | 59.79 |
| 2 | automic | pre-audit-gpo-20261006-1150 | 17 | 0.14 | 17.70 |
| 3 | automic | pre-helper-073-domain-20261006-1154 | 17 | 17.56 | 17.70 |
| 4 | vcf-lab-operations-devel-91 | clean-install-20261014-0949 | 9 | 16.27 | 16.27 |
| 5 | vcf-lab-operations-devel | pre-move-reip-20261014-1118 | 9 | 0.05 | 15.75 |
| 6 | vcf-lab-operations-devel | pre-move-offline-20261014-1123 | 9 | 1.17 | 15.75 |
| 7 | vcf-lab-operations-devel | post-move-reip-20261014-1350 | 9 | 14.52 | 15.75 |
| 8 | vcf-lab-operations-devel-8 | clean-install-20261015-1028 | 8 | 15.54 | 15.54 |
| 9 | dcint2 | pre-audit-gpo-20261006-1150 | 17 | 0.03 | 13.98 |
| 10 | dcint2 | pre-helper-073-domain-20261006-1154 | 17 | 13.95 | 13.98 |

Reading it: `automic` (rows 2 and 3) and `vcf-lab-operations-devel` (rows 5 to 7) each show their snapshots together, all with the VM's total repeated (17.70, 15.75). Within a VM the order is the server's own (row 2 is 0.14 GB and row 3 is 17.56 GB, so the snapshots inside a VM are not sorted by their own size), which is what the view description promises: VM order by total, snapshots grouped, no inner order.

Tail of the list for the same property (VM, total GB): `tg-ubu01` 3.32, `tg-ubu03` 3.25, `console` 2.80, `gce-api` 2.14, `docker` 1.14. Ties between VMs (for example `ca` 9.20 x2, `oracledemo` 4.72 x4) stay grouped by VM.

### Datastore Reclaimable Space (control)

12 rows; column `4` (Snapshot Space GB) is non-increasing. First ten rows (Datastore, Snapshot Space GB):

| # | Datastore | Snapshot Space (GB) |
|---|---|---|
| 1 | vcf-lab-wld02-cl01-iscsi | 0.000921881 |
| 2 | vcf-lab-mgmt-cl01-vsan | 0.000675235 |
| 3 | vcf-lab-mgmt-esx06-local | 0.000615356 |
| 4 | vcf-lab-wld01-cl01-iscsi | 1.41561e-06 |
| 5 | vcf-lab-mgmt-esx04-local | 0 |
| 6 | vcf-lab-mgmt-esx01-local | 0 |
| 7 | vcf-lab-mgmt-esx03-local | 0 |
| 8 | vcf-lab-nfs-wld02 | 0 |
| 9 | vcf-lab-mgmt-esx02-local | 0 |
| 10 | vcf-lab-nfs-wld01 | 0 |

Rows 5 to 12 are all 0.0 (ties).

### Cluster Capacity Breakdown (control)

3 rows; column `13` (Capacity Remaining %) ascending:

| # | Cluster | Capacity Remaining % |
|---|---|---|
| 1 | vcf-lab-wld01-cl01 | 0.00 |
| 2 | vcf-lab-mgmt-cl01 | 17.33 |
| 3 | vcf-lab-wld02-cl01 | 34.73 |

## Verdict

A fanned-out instanced list view honours the view-level `sort:` on a flat column on 9.0.2: the stored `sortCriteria` is on the flat column only, the server sorts the fanned-out rows by that column's per-VM value, and each VM's snapshots stay together. The plain controls behave the same way.

## Not proven

- Any on-screen render (View widget or the view in the list UI): Playwright MCP unavailable.
- Ordering inside a VM's snapshots (not specified by the view; observed unsorted).
- A sort on an instanced column (the loader does not allow it by design, per the view description).
- 9.1.1 and 8.18 devel instances were not exercised.
- Cluster control has only three rows on this instance, so ascending is only weakly demonstrated.

## Notes

- The export file for the `VIEW_DEFINITIONS` scope is a single `content.xml` inside a nested zip; the three views were located by `ViewDef id`.
- `REQUESTS_CA_BUNDLE` was unset for the ad hoc requests.
