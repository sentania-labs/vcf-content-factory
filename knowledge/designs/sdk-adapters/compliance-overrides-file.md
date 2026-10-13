# Compliance adapter: central overrides file (skip, override, pin) replaces the custom CSV path

- **Type:** managementpack (Tier 2 SDK adapter change), target build 90
- **Slug:** compliance-overrides-file
- **Adapter repo:** `content/sdk-adapters/compliance/` (sentania-labs/vcf-content-factory-sdk-compliance)
- **Date:** 2026-10-13
- **Tracking:** adapter issue #40 (docs trigger); this design supersedes the "custom profile how-to" as written
- **Status:** built as build 90 (rejected by Ops: composite symptom set) and build 91 (installed on devel 2026-10-13 11:33 AM, evaluation PASS except the Skip alert clear, adapter issue #41); doc path corrections and #41 are build 92 items

## Initial prompt (Scott, verbatim, 2026-10-13)

> I clicked on Custom Profile format in the readme, and came here:
> https://github.com/sentania-labs/vcf-content-factory-sdk-compliance/blob/main/CANONICAL_SCHEMA.md
> and immediately when ugh - how do I do anything with this

> The documentation is for the user, not for an engineer. we need clear
> instructions how to create a custom profile to turn alerts/metrics on/off

> we can't expect the user to push a config file to 5-10-20+ collectors.
> shouldn't it go here:
> https://vcf-lab-operations-devel.int.sentania.net/vcf-operations/ui/operations/configurations/management-packs-configuration

> So how does the vcommunity pack do this - the userdefined config:
> sentani_windows_services_list.xml. How can we upload a custom xml there
> that instructions the MP to turn off metrics, or turn them on, or
> instruct it for a different version fo the CSV- or add new alerts, etc?

> We should be able to not just turn metrics/alerts on/off, but allow them
> to have overriden values. for example password trieds to 5 instead of 3,
> etc.

> so it will ship in system defined, and the user will edit that one? how
> do we keep it upgrade safe?

> i feel like we ship a template and the user copies it and then names the
> copy per adapter instnace

## Findings that shaped the design (verified 2026-10-13)

- The current custom profile is a canonical CSV read from a local path on
  whichever collector runs the instance (`BenchmarkLoader.load`, plain file
  read). It replaces Auto (by version) for every object in the instance, the
  manual-review overlay is not applied to it, and `priority`, `title` and
  `remediation_text` have no runtime effect (alert definitions are generated
  at pak build). An operator cannot reasonably maintain it, and cannot stage
  it across a collector group.
- The vcommunity adapter reads named XML files from the VCF Ops central
  configuration-file store (UI: Administration, Configuration Files,
  Management Packs Configuration; API: `GET /api/configurations/files?path=SolutionConfig/<name>.xml`,
  raw body, HTTP 400 / apiErrorCode 1501 when absent) through the
  SDK-injected Suite API channel every cycle, caching the last good parse
  (`SolutionConfigStore.java`). The pak ships defaults under
  `content/files/solutionconfig/`, which SolutionManager imports into the
  store at install (builder support exists in `sdk_builder.py`). One upload
  in the UI reaches every collector. Evidence:
  `knowledge/context/investigations/vcommunity-solutionconfig-400-2026-06-16.md`.

## Vision

Operators tune the compliance pack from one XML file in the VCF Ops
Configuration Files page. Nothing is staged on a collector. Auto (by
version), the bundled SCG profiles and the manual-review overlay keep
working underneath; the file adjusts them.

### The file

The pak ships one **template**,
`content/files/solutionconfig/compliance_overrides_template.xml`, imported
into the store at install, every entry commented out with its
documentation beside it. The user never edits the template. They copy it
in the Configuration Files page, name the copy for the vCenter or group
of vCenters it serves, edit the copy, and point each adapter instance at
its copy by name. Format:

```xml
<ComplianceOverrides>
  <!-- Turn a control off: no metric, no alert, out of the score. -->
  <Skip control="esx.account-lockout-max-attempts"/>

  <!-- Score against a site value instead of the SCG value. -->
  <Override control="esx.account-lockout-max-attempts" expected="5"/>

  <!-- Pin the guide version for the whole instance or one object kind. -->
  <Profile version="SCG 9.0"/>
  <Profile kind="VirtualMachine" version="SCG 8.0"/>
</ComplianceOverrides>
```

- `Skip`: the control is not evaluated and not pushed. Its existing
  per-control key is marked not evaluated (the build 8x stale-key path) so
  an open alert clears; its actual property reads "(skipped by override
  file <name>)".
- `Override`: replaces `expected_value` for that control in every profile
  that carries it. The value is parsed per the control's `value_type` and
  comparison mode (CANONICAL_SCHEMA.md); an unparseable value is reported
  (below) and the control falls back to the SCG value, never to a pass.
  The actual property and the alert text carry "expected 5 (site
  override)" so the alert and the published guide do not silently
  disagree.
- `Profile`: pins the resolved SCG version for the instance, or for one
  resource kind, in place of Auto (by version). Unknown version names are
  reported and ignored.
- Unknown control ids are reported, not fatal. Unknown elements are
  reported, not fatal. A malformed file (XML parse failure) keeps the
  previous cycle's parse, like vcommunity, and reports it.

### Settings

- New instance setting **Overrides file** (`overrides_file`, default
  empty), the name of the user's copy in the store without path or
  extension, same convention as vcommunity. Empty means no overrides and
  no fetch. Different instances point at different copies; several
  instances may share one.
- **Upgrade safety by construction.** The pak writes only
  `compliance_overrides_template`. A user's copy has a name the pak never
  ships, so no install, upgrade or force-update can overwrite it, whatever
  SolutionManager does to the files it owns. The template may be refreshed
  by an upgrade, which is the intent (new controls documented in it). An
  instance that names a file the store does not have reports it
  (status property and alert below) and runs with no overrides, never
  with a stale guess. Pending: what SolutionManager does to store files on
  upgrade and uninstall is being read from the installer bytecode and
  recorded in `summary_dashboard_pak_binding.md`; the design does not
  depend on the answer.
- **Retired:** `custom_profile_path` and the `Custom` profile choice. One
  release of deprecation: an instance still set to Custom logs a WARN
  naming the overrides file as the replacement and keeps working.

### Visibility

- ComplianceWorld and each vCenter: `Summary|overrides_file`,
  `Summary|overrides_status` (none / OK / absent / parse failed, last good
  from <time> / N unknown ids), `Summary|overrides_skipped`,
  `Summary|overrides_overridden` counts.
- One INFO line per cycle listing applied skips and overrides; one WARN per
  cycle for each rejected entry.
- A new pak alert "Compliance overrides file not loaded" on the vCenter
  object (parse failure, or the named file is absent from the store).

### Out of scope for build 90

- **New alerts from the file.** Per-control alert definitions are generated
  at pak build. A control added only through the file would score and push
  but not alert. Second step: a small set of generic "custom control" alert
  slots claimable from the file.
- A full replacement CSV through the store. The store serves any raw body,
  so it is possible; it is dropped until someone needs it, because the
  three entry types cover every case Scott named.

### Docs

`docs/custom-profiles.md` becomes `docs/overrides.md`: open the page,
copy the template and name the copy, set the instance to it, the three
entry types with the password-attempts
example, how to confirm it loaded, and what you see when an entry is
rejected. README link "Tuning controls and thresholds". CANONICAL_SCHEMA.md
stays as the contributor reference, linked from docs/building.md only.
`docs/installing.md` "SCG-format CSV" wording goes with the retired
setting.

## Verification on devel

Upload a file with one Skip, one Override (expected 5 on the lockout
attempts control, where devel hosts are at the SCG value), one Profile pin
for VirtualMachine; wait two cycles; confirm the skipped key is marked not
evaluated and its alert cancels, the overridden control now fails with
"expected 5 (site override)" in the alert, the VM profile property reads
the pinned version, and the status properties and counts match. Then
upload a malformed file and confirm the previous parse is kept and the
alert fires.

## Open questions for Scott

1. Should `Override` also accept a per-kind or per-object scope, or is
   per-instance enough for the first cut? (Design assumes per-instance.)
2. Keep the `Custom` CSV choice for one deprecation release, or remove it
   in build 90 outright? (Design assumes one release of WARN.)
