# Compliance 0.0.0.95 on Aria Operations 8.18.7 (devel_8_18), 2026-10-15

Factory issue #212 step 2. Approval `approvals/2026-10-15-all-devel-dev-paks.md`.
Agent: content-installer. Times America/Chicago.

| # | Check (proven on 9.x only before today) | 8.18.7 result |
|---|---|---|
| 1 | Install | PASS. 1:33 to 1:34 PM, pakId VCFContentFactoryCompliance-00095, read back 0.0.0.95. DEF-018 (dangling localizationKey) did not trigger; all 9 views and 5 dashboards imported. No warn-and-confirm surfaced because installer.py sends ignoreSignatureChecking=true on upload; untested with the flag off. |
| 2 | Collector group | PASS with a quirk: POST /api/collectorgroups returns 500 unless the body carries `"systemDefined": false`. Group factory-cloud-proxy (collector 2 only) created with it. The same 500 was seen on 9.0.2 today without that key, so it is probably the same cause there. |
| 3 | Certificate accept hook on Validate Connection | PASS. "Untrusted certificate found" dialog with thumbprint, issued to/by, expiry; ACCEPT then "Test connection successful". |
| 3 | Collection and ComputedMetrics | PASS. First scan about 1:47 PM, cycles at 1:57:08 and 2:02:10. ComplianceWorld carries Rollup|Environment|pass_rate 73.33, avg_score 76.59, controls_evaluated 1305, controls_passed 957, scored 63; Summary|last_scan_timestamp stamped. badge|compliance reads -1 (shown as "?"); not compared with 9.x. |
| 4 | Stitching through the ambient Suite API login | PASS. 6 mgmt hosts carry 57 VCF-CF Compliance metrics each (scores 64.6 to 66.7); VMs, cluster, vDS and portgroups carry a score; the vCenter object has 88 Rollup keys (Rollup|All|pass_rate 73.33). |
| 5 | Widget-type allowlist | PASS as far as checked: Environment Overview and the World Summary clone rendered every widget type; the other three dashboards not diffed widget by widget. |
| 5 | dashboards.properties Summary binding | BINDS, clone FAILS. ComplianceWorld resourceKindTemplate is the World Summary dashboard and the Summary clone tab exists, but on the clone the three view widgets (Objects with Unreadable Controls, Compliance by vCenter and Object Type, Objects by SCG Version) show "The widget is not configured. Select a view to render" while the same views render on Environment Overview. Hypothesis (unconfirmed): the clone is materialized at install before the views exist. Same family as the parked 9.0.2 stake (`2026-10-13-summary-dashboard-parked.md`); a re-bind would test it. |
| 6 | describe identType 2 Advanced Settings placement | PASS. Collapsed "Advanced Settings" expander below Validate Connection holding the overrides file and VAMI settings; main form has only Name, Description, Host, Credential, Collector. |
| 7 | Overrides file configuration store | PARTIAL. Setting shown; adapter exposes Summary|overrides_file '', overrides_status none, counters 0. A non-blank file not tested (needs a write into the config store). |
| 8 | Adapter log | NOT TESTED. Support > Logs on 8.18 lists only the primary node's logs; the adapter runs on the Cloud Proxy, whose log needs a support bundle or SSH to 172.27.10.15 (SSH still gated on Scott). |

Also seen: a transient built-in "Objects are not receiving data from adapter
instance" alert on ComplianceWorld at about 2:00 PM, cleared by 2:02 PM; the
shared Chrome refused a second devel_9_1 UI login with
concurrentSessionDetected (another agent's session); logout URLs ended on a
Chrome error page, so the 8.18 admin and product sessions may be open until
they time out.

Left on devel_8_18: pak 0.0.0.95 with its content and the Summary clone,
collector group factory-cloud-proxy, credential vcenter-lab-cred, account
compliance-mgmt, the mgmt vCenter certificate accepted.

Step 1 of #212 (SDK jar hash, bytecode level, class diff) and the Cloud Proxy
log still need SSH.
