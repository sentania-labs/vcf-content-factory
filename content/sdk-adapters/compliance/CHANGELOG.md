# Changelog

## 1.0.0.41 (2026-06-03)

- feat(adapter): build 41 — VAMI appliance REST reader (vami_api kind) for vCenter SSH/password-policy controls; failed/non-200/absent-field reads fold to UNREADABLE

## 1.0.0.40 (2026-06-03)

- feat(adapter): build 40 — vm_hardware_device_absent / list_empty / vlan_id_not filter styles via vim25; confirmed-read vs failed-fetch distinction (empty ≠ unreadable)

## 1.0.0.39 (2026-06-03)

- feat(adapter): build 39 — not: and (non-empty) advanced_setting comparison modes; absent/unreadable short-circuits before mode helpers

## 1.0.0.38 (2026-06-03)

- feat(adapter): build 38 — service_state recipe reader (esxcli HostService running/policy) for ESXi service-state controls

## 1.0.0.37 (2026-06-03)

- feat(adapter): build 37 — esxcli SSH/firewall/account cluster + list/row-select reader

## 1.0.0.36 (2026-06-03)

- feat(adapter): build 36 — esxcli recipe reader via vCenter session + syslog proof slice

## 1.0.0.35 (2026-06-03)

- feat(adapter): build 35 — HostSystem/VM vim_property coverage expansion (+14 SCG8/+16 SCG9 reclassified) + in-pak UNAUDITED_CONTROLS.md

## 1.0.0.34 (2026-06-03)

- feat(adapter): compliance adapter evaluation + canonical profile normalization

## 1.0.0.32 (2026-05-29)

- feat(adapter): build 32 — ClusterComputeResource vSAN evaluation (2 of 14)

## 1.0.0.31 (2026-05-29)

- feat(adapter): build 31 — DVS/DVPG security policy evaluation via vim25

## 1.0.0.30 (2026-05-29)

- feat(adapter): build 30 — vCenter world aggregate + DVS/DVPG profile_name fix + profile-change scaffolding

## 1.0.0.29 (2026-05-29)

- fix(framework): build 29 — Heatmap empty-groupBy + AlertList pin-to-world

## 1.0.0.28 (2026-05-28)

- fix(adapter): build 28 — VMwareAdapter Instance resolver + multi-line param classifier

## 1.0.0.27 (2026-05-28)

- feat(adapter): build 27 — Phase 2 multi-resource stitching (VM, vCenter, DVS, DVPG)

## 1.0.0.26 (2026-05-28)

- feat(adapter): build 26 — canonical compliance schema, Phase 1 working on devel

## 1.0.0.19 (2026-05-27)

- feat(framework): build 19 — pin self-provider Views at world singletons

## 1.0.0.18 (2026-05-27)

- feat(adapter): build 18 — owning-adapter binding per spec §18 Pass 28

## 1.0.0.17 (2026-05-27)

- feat(adapter): build 17 — content inside adapters.zip for DashboardImporter

## 1.0.0.16 (2026-05-27)

- feat(adapter): build 16 — first-party content layout + lessons

## 1.0.0.15 (2026-05-27)

- fix(adapter): SymptomSets requires >=2 children — split into two SymptomSet refs

## 1.0.0.14 (2026-05-27)

- feat(compliance): build 14 — alerts, dashboard, and pak content bundling

## 1.0.0.12 (2026-05-27)

- fix(adapter): component filter matched 'ESXi' but CSV has 'VMware ESXi'

## 1.0.0.11 (2026-05-27)

- feat(adapter): vSphere SOAP collection via vim25 — real compliance scoring

## 1.0.0.10 (2026-05-27)

- feat(adapter): push properties via suiteAPIClient.getClient() reflection

## 1.0.0.9 (2026-05-27)

- fix(adapter): debug logging confirms stitcher works, ResourceCollection drops foreign data

## 1.0.0.7 (2026-05-27)

- feat(adapter): custom compliance icons — shield with checkmark
- fix(adapter): revert to injected suiteAPIClient, drop Ops credential fields

## 1.0.0.6 (2026-05-27)

- feat(adapter): self-contained Suite API stitcher (bypass Java SDK SuiteAPIClient)

## 1.0.0.5 (2026-05-27)

- feat(adapter): rename profiles, add CIS vSphere 8 + SCG 9.0, dropdown UI
- feat(adapter): Suite API direct property push (bypass ResourceCollection)

## 1.0.0.4 (2026-05-27)

- fix(adapter): use DTO-backed Resources for foreign property push

## 1.0.0.3 (2026-05-27)

- fix(adapter): handle vCenter REST 404 gracefully, fix duplicate counter

## 1.0.0.1 (2026-05-27)

- feat(adapter): bundle CIS 8.0 benchmark CSV + builder profiles support
- feat(adapter): VCF Compliance Adapter — Phase 1 scaffold
