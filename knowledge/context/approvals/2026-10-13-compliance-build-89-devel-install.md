# Approval: compliance build 89 (drop Section row from World Summary), devel install

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "drop the secon row and do build 89"
- **Context:** build 88 installed on devel 2026-10-12 5:07 PM to 5:11 PM; the
  ComplianceWorld Summary tab stayed stock because the devel 9.0.2 importer has no
  `Section` widget type and aborts the whole World Summary dashboard import
  (`JSONObject["Title"] not found`). Scott confirmed: "sections are not present in
  9.0.x". The Section row is the only widget in any managed pak that uses the type.

## Scope this covers

- Remove the Section header row from
  `content/sdk-adapters/compliance/dashboards/compliance-world-summary.yaml`
  (RULE-011 layout change, approved here; the other five rows stay as approved on
  2026-10-12).
- Build 89 of the compliance adapter (dev preview 0.0.0.89), review, pak-compare.
- Upgrade-install over build 88 on **devel only**, then verify the Summary tab.

## Not covered

- prod or qa installs, PR merges, `v*` release tags, buildkit tag, instance setting
  changes, the hol-db effective-policy POST.
