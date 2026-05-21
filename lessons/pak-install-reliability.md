# War Story: Pak Install Reliability — Five Failures Before Success

**Campaign:** vSphere Storage Paths v2.0.0  
**Date:** 2026-05-13 to 2026-05-14

## The promise vs. the reality

The factory's promise is that it produces byte-equivalent output to what MPB's
GUI generates. "A prompt instead of a bad Postman REST GUI." Five consecutive
pak install failures during the v2.0.0 campaign revealed every place the factory
was diverging from MPB's output format. Each failure was a different root cause.

## Failure 1: Adapter kind mismatch

**Symptom:** Pak installed on devel via MPB UI; factory pak failed on prod.

**Cause:** MPB derives `adapter_kind` by slugifying the MP display name:
`mpb_vcf_content_factory_vsphere_storage_paths`. The factory YAML used a
shortened form: `mpb_vsphere_storage_paths`. The MPB-built v1.0.0.1 was already
installed on prod with the long key; our pak with the short key conflicted.

**Fix:** All factory YAML `adapter_kind` values must match MPB's derivation:
`mpb_` + `lowercase(display_name.replace(' ', '_'))`. The factory does not get
to choose its own convention.

## Failure 2: Reserved characters in metric labels

**Symptom:** Collection preview error: "Metric key cannot contain reserved
characters `|` or `:`."

**Cause:** A user-chosen prefix `VCF-CF|` uses `|`, which is the stat key
group separator in VCF Ops.

**Fix:** Metric labels cannot contain `|` or `:`. Validation catches this at
load time now. Use dash-space as a separator (`VCF-CF - `).

## Failure 3: CredentialKinds for no-auth paks

**Symptom:** "Adapter install failed" on earlier pak builds.

**Cause:** Factory emitted `<CredentialKinds>` with an empty `<CredentialKind>`
block for no-auth paks. MPB omits the entire block.

**Fix:** Match MPB exactly. Conditionally skip `CredentialKinds` when
`preset == "none"`.

## Failure 4: ARIA_OPS objects in template.json

**Symptom:** "RESOURCES error … field 'resourceKind'. A lower-case snake-case
value prefixed with `mpb_` is required."

**Cause:** ARIA_OPS objects were emitted as `resources` in template.json with
resourceKind values like `VMWARE_hostsystem`. The runtime validator requires
all resourceKinds to be `mpb_`-prefixed.

**Fix:** ARIA_OPS objects belong only in export.json (ariaOpsConf), never in
template.json or describe.xml ResourceKinds.

## Failure 5: Events in wrong format

**Symptom:** "EVENT error … field 'type'. Missing fields. field 'eventQuery'.
Missing fields." Plus extra fields rejected.

**Cause:** Events were rendered in design-import JSON format (for MPB UI) but
the pak runtime expects a completely different schema. Events were present in
export.json, template.json, AND design.json inside the pak — the runtime parses
every JSON file in the conf directory.

**Fix:** Strip events from all three files when building a pak. Pak-format events
remain a TOOLSET GAP — no ground-truth reference exists; all MPB reference paks
have `events: []`. When you don't know the correct format, emit nothing.

## Bonus failure: MOID collision (silent data corruption)

**Symptom:** wld02 hosts silently lost. wld01 hosts showing wrong metric values.

**Cause:** `host_moid` (VMEntityObjectID) is not unique across vCenters. Both
wld01 and wld02 have `host-20`.

**Fix:** Use `hostname` → `VMEntityName` (FQDN, globally unique). Always verify
join key uniqueness across all collection sources before shipping.

## Process lessons

**Build pak-compare first, not last.** We fixed 7 structural issues by diffing
against a reference pak. This tool should run automatically after every build as
a post-build gate.

**The runtime parses ALL JSON files.** We assumed events only lived in export.json.
They were also in template.json and design.json. When stripping something, grep
the entire pak.

**Get the analytics log, not just the task status.** The Suite API task status had
empty `errorMessages` for all failures. The actual error was in the appliance
analytics log at `/storage/log/vcops/log/analytics/`. The task API is useless for
diagnosing pak install failures.

**Match MPB exactly — don't optimize or abbreviate.** Every divergence (shorter
adapter kind, different icon format, extra scripts, different field values) is a
potential install failure.

**One fix per build number.** Reusing a build number for a rebuilt pak causes
confusion about which pak is installed.

## What's still missing (as of 2026-05-14)

- Pak-format events — rendering to the pak runtime format is a TOOLSET GAP
- Automated pak-compare gate post-build
- Adapter kind auto-derivation with validation warning

## Reference files

- `context/authoring/rules_install_verification.md` — install workflow
- `context/mpb/mpb_pak_structural_reference.md` — structural reference
