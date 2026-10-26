# AlertList `depth` and `relationshipMode`: what the server and the editor do

- **Date:** 2026-10-26, America/Chicago. Read-only.
- **Instances:** devel (9.0.2, full run), devel_8_18 (depth replay only; server log not readable, SSH denied). devel_9_1 not touched.
- **Method:** CLI UI login (`VCFOpsUIClient`), POST `/ui/problemalerts.action` `mainAction=getAlertsGroups`, `groupBy=problemDefinitionId`, `contentFilter` = JSON of what `AlertList.buildFilterData` sends: `{"criticality":[2,3,4],"alertType":["15_21"],"isWidget":true,"depth":N,"relationshipMode":[...],"resourceIds":[id]}`. No `alertStatus`, so canceled alerts are included (the live widget has `status: []`). Endpoint and parameter shape came from the 9.0.2 SPA bundle (`dist/js/app.part4.min.js`; the earlier investigation did not record them). Cross-checked against Suite API `GET /api/alerts?resourceId=`. Each run logged out.
- **Objects (devel):** HostSystem `vcf-lab-mgmt-esx04` (`dee43744-bf06-4561-87cc-3db1d5e53d0e`; own esx.* compliance alerts, 8 child VMs with vm.* alerts); vCenter = the `VMwareAdapter Instance` `vcf-lab-mgmt` (`5aa31ee3-39f2-4239-bf4f-840eb0bdc99d`).

## Answer

- **Depth 0 is rejected.** The action returns the generic Struts error panel (HTTP 200, non-JSON). `web.log`: `IllegalArgumentException: depth should be between 1 and 10` at `ResourceSearchParam$RelationResources.<init>` via `BaseServerManager.setRelationshipParam` / `ProblemAlertsManager.constructAlertSearchParam`, then an NPE in `ProblemAlertsAction.getAlertsGroups:3315`. Host and vCenter alike. An AlertList at `depth: 0` shows no list.
- **`relationshipMode [0]` is self only, and it works at depth 1.** Host 37, vCenter 13, exactly the own-alert counts.
- **`[-1]` is children only.** Host 83 (VMs only), vCenter 0. `[-1, 0]` is the union (120 and 13).
- **The editor supports self-only** (details below), so it is a normal UI mode.

## Results, devel (all statuses, criticality 2-4, type 15_21)

| Call | Groups | Alerts | Whose |
|---|---|---|---|
| host depth 0, `[-1,0]` | error | error | `depth should be between 1 and 10` |
| host depth 1, `[0]` | 19 | 37 | self only: 17 esx.* groups x2, "Compliance data not collected (ESX host)" 2, "Host Compliance Score Degraded" 1 |
| host depth 1, `[-1]` | 7 | 83 | VMs only: vm.efi-boot-types 15, vm.ft-encrypted 15, vm.vmotion-encrypted 15, vm.limit-console-connections 13, vm.secure-boot 13, vm.vmrc-lock 10, vm.virtual-hardware 2 |
| host depth 1, `[-1,0]` | 26 | 120 | 37 + 83 |
| host depth 4, `[-1,0]` | 26 | 120 | same as depth 1 (no deeper alerting descendants) |
| vCenter depth 0, `[-1,0]` | error | error | same error |
| vCenter depth 1, `[0]` | 3 | 13 | Compliance data not collected (vCenter) 9, vc.vpxuser-length 2, vc.vpxuser-rotation 2 |
| vCenter depth 1, `[-1]` | 0 | 0 | direct children carry no matching alerts |
| vCenter depth 1, `[-1,0]` | 3 | 13 | self only in effect |
| vCenter depth 4, `[-1,0]` | 34 | 709 | descendants included (708 on 2026-10-24; one alert since) |

Suite API cross-check, all statuses: VMs under the host = 83 (exact). Host own = 38 versus 37 in the replay; the extra one is not in the 15_21 filter (not chased).

## Results, devel_8_18 (8.18.6), depth replay with `[-1,0]`

Host `vcf-lab-mgmt-esx06` (`aece7836-3bb3-45f8-ad76-f492ec308d85`), vCenter `vcf-lab-vcenter-mgmt` (`fc918336-a9a4-472c-9ba3-969d49b8264f`).

| Call | Result |
|---|---|
| host depth 0 | error panel, same as devel (cause INFERRED the same; log not read) |
| host depth 1 / depth 4 | 23 groups, 99 alerts: own 51 + VMs 48 (Suite API exact) |
| vCenter depth 0 | error panel |
| vCenter depth 1 | 3 groups, 8 alerts, own only |
| vCenter depth 4 | 32 groups, 1048 alerts |

The `[0]` and `[-1]` replays were run on devel only.

## What the AlertList widget editor offers (9.0.2, `dist/js/app.part6.min.js`, class `Ext.vcops.dashboard.widget.editor.AlertList`)

- Section "Transformation" (collapsed by default) holds a checkbox group `#relationshipMode` and a number field `#depthField`.
- Checkboxes and values (widget config stores `{relationshipMode: [..]}`):
  - Parent, `1` (`widget.resourceList.parent`), checked by default
  - Children, `-1` (`widget.resourceList.children`), checked by default
  - Self, `0` (`widget.resourceList.self`), unchecked by default
  - Label text is by key name (INFERRED Parents / Children / Self; bundle text not fetched).
- The change handler makes Self and Parent mutually exclusive. Self plus Children is allowed. So the UI can produce `[0]`, `[-1]`, `[1]`, `[1,-1]`, `[0,-1]`.
- Depth field: integer, min 1, max 10, defaults to 1. Disabled when the mode is exactly `[0]`, matching the server (depth irrelevant for self-only).
- The editor cannot produce `depth: 0`, so the server error only hits hand-written or generated content.

## Consequence for the factory

- Never render `depth: 0` on an AlertList; use 1 to 10.
- Self-only: `relationshipMode: [0]`, depth 1.
- Self plus direct children on a host (the object plus its VMs): `[-1, 0]`, depth 1.
- Not tested: `[1]` (parents) and `[1, -1]`.

## Clean-up

Logins on devel and devel_8_18, each logged out. Read-only SSH `grep` of devel `web.log`. Nothing created or changed on any instance.
