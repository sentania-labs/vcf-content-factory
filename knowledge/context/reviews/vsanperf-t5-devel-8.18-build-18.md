# vsanperf T5, devel 8.18.7, build 18 (scale build, default tiers) (2026-11-07)

Upgrade 0.0.0.12 to `dist/vcfcf_sdk_vsanperf.0.0.0.18.pak` on devel 8.18 by
`content-installer` (own log `install_devel_8_18.log`; the installer's auth
line named `vcf-lab-operations-devel-8`, matching the profile), instance
`vsanperf-mgmt` `5dbd106b-ec5e-444c-9ebe-a4d28069d81e` on collector 1.
Builds 13 to 18 change production only in the VM-read failure path (13, VM
tier, off here) and the watermark commit path (15, 16). Times
America/Chicago.

| Check | Result |
|---|---|
| Solution version | 0.0.0.12 before, 0.0.0.18 after; CLI reported the account collecting; health GREEN |
| Settings | tier_host true, tier_cluster true, tier_disk false, tier_vm false, vm_tier_every_n_cycles 3, perf_timing_logging false |
| a. Self-metrics | **pass**: cycles 02:44:40 / 02:49:40 / 02:54:41 / 02:59:44 / 03:04:44: perf_calls 26, 26, 26, 23, 23 (learned-empty after three consecutive empties, as designed); series_pushed 2,372 then 1,186 x 4; push_batches_failed 0 and optional_calls_failed 0 on every cycle; cycle_seconds 7, 3, 6, 13, 6; last_error `none` |
| b. Host keys, vcf-lab-mgmt-esx01 | **pass**: 219 keys; `vSAN Perf\|DOM Owner\|iops` 17 points from 01:40 to 03:00 at exactly 5-minute spacing, no gap across the upgrade (809, 1074, 847, 902, 1025 at 02:40 to 03:00) |
| c. Cluster keys, vcf-lab-mgmt-cl01 | **pass**: 91 keys at the pushed sample time 03:00:00 |
| d. Tiers off | **pass**: 0 of 126 VMs and 0 of 12 datastores carry a key; no disk-instanced group; VirtualDisk/CacheDisk/CapacityDisk/vSANDiskGroup resources 0; the only instanced host keys are pNIC, vNIC and TCP/IP stack |
| e. Hosts with host-tier keys | **pass**: exactly mgmt-esx01..05, 219 keys each at 03:00:00 |

Cloud Proxy leg still open (#314, parked).
