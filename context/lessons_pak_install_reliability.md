# Lessons learned: pak install reliability

From the vSphere Storage Paths v2.0.0 pak install campaign
(2026-05-13 to 2026-05-14). Five failed installs before success.

## The goal

The factory should be an alternative path to the same outcome as
MPB's GUI. Same adapter kind, same file structure, same wire
formats. "A prompt instead of a bad Postman REST GUI."

## What failed and why

### 1. Adapter kind mismatch (root cause: naming convention)

**Symptom:** Pak installed on devel via MPB UI, factory pak failed
on prod.

**Cause:** MPB derives adapter_kind by slugifying the MP display
name: `mpb_vcf_content_factory_vsphere_storage_paths`. The factory
YAML used a shortened form: `mpb_vsphere_storage_paths`. When
the MPB-built v1.0.0.1 was already installed on prod with the long
key, our pak with the short key conflicted.

**Fix:** Changed all factory YAML `adapter_kind` values to match
MPB's derivation: `mpb_` + lowercase(name.replace(' ', '_')).

**Rule:** adapter_kind must match what MPB would generate from the
MP display name. The factory does not get to choose its own
convention.

### 2. Reserved characters in metric labels

**Symptom:** Collection preview error: "Metric key cannot contain
reserved characters `|` or `:`."

**Cause:** User-chosen prefix `VCF-CF|` uses `|`, which is the
stat key group separator in VCF Ops.

**Fix:** Changed to `VCF-CF - ` (dash separator).

**Rule:** Metric labels cannot contain `|` or `:`. Add validation
in the loader.

### 3. CredentialKinds for preset:none

**Symptom:** "Adapter install failed" on earlier pak builds.

**Cause:** Factory emitted `<CredentialKinds>` with an empty
`<CredentialKind>` and set `credentialKind=` on the adapter
ResourceKind. MPB omits both entirely for no-auth paks.

**Fix:** Conditionally skip CredentialKinds when `preset == "none"`.

**Rule:** Match MPB. If MPB omits it, we omit it.

### 4. ARIA_OPS objects in template.json

**Symptom:** "RESOURCES error ... regarding field 'resourceKind'.
A lower-case snake-case value prefixed with mpb_ is required."

**Cause:** ARIA_OPS objects were emitted as `resources` in
template.json with resourceKind values like `VMWARE_hostsystem`.
The runtime validator requires all resourceKinds to be
`mpb_`-prefixed.

**Fix:** Skip ARIA_OPS objects when building template.json
resources. ARIA_OPS objects exist only in export.json.

**Rule:** ARIA_OPS objects go in export.json (ariaOpsConf), never
in template.json or describe.xml ResourceKinds.

### 5. Events in wrong format (3 files)

**Symptom:** "EVENT error ... field 'type'. Missing fields. field
'eventQuery'. Missing fields." Plus extra fields: listId, message,
severityMap, eventMatchers.

**Cause:** Events were rendered in design-import JSON format
(for MPB UI) but the pak runtime expects a completely different
schema. Events were present in export.json, template.json, AND
design.json inside the pak.

**Fix:** Strip events from all three files when building a pak.
Events in pak-runtime format remain a TOOLSET GAP — no ground-truth
reference exists (all MPB reference paks have `events: []`).

**Rule:** When you don't know the correct format, emit nothing.
Don't guess. The `--no-events` workaround for design import was
the right instinct — it should have been applied to pak builds
from the start.

### 6. MOID collision (join key)

**Symptom:** wld02 hosts silently lost. wld01 hosts showing wrong
metric values.

**Cause:** `host_moid` (VMEntityObjectID) is not unique across
vCenters. Both wld01 and wld02 have `host-20`.

**Fix:** Changed to `hostname` → `VMEntityName` (FQDN, globally
unique).

**Rule:** Always verify join key uniqueness across all vCenters.
MOID is per-vCenter, not global.

### 7. Missing describe.xml structural elements

**Symptom:** Various warnings in pak-compare.

**Cause:** Factory omitted `<ResourceGroup key="summary">` on
adapter/world kinds, `<ComputedMetrics>` on world, `_relatives`
ResourceAttributes.

**Fix:** Added all structural elements to match MPB output.

**Rule:** Use pak-compare against the reference before every
install attempt. Zero BLOCKINGs is the gate.

## Process lessons

### Build pak-compare first, not last
We fixed 7 structural issues by diffing against a reference pak.
We should have had this tool from day one. Every pak build should
run pak-compare as a post-build gate.

### The runtime parses ALL json files
We assumed events only lived in export.json. They were also in
template.json and design.json. The adapter runtime parses every
JSON file in the conf directory. When stripping something, grep
the entire pak.

### Get the analytics log, not just the task status
The Suite API task status had empty `errorMessages` for all
failures. The actual error was in the analytics log on the
appliance (`/storage/log/vcops/log/analytics/`). The task API is
useless for diagnosing pak install failures.

### Match MPB exactly — don't optimize or abbreviate
The factory's job is to produce byte-equivalent output to MPB.
Every divergence (shorter adapter kind, different icon format,
extra scripts, different field values) is a potential install
failure. When in doubt, copy MPB's output exactly.

### One fix per build number
Reusing build number 2.0.0.4 for a rebuilt pak caused confusion
about which pak was installed. Always bump the build number for
each install attempt.

## What's still missing

1. **Pak-format events** — we can define events in YAML and render
   them for design import, but the pak runtime uses a different
   schema. Need a ground-truth MPB-built pak with events to reverse
   engineer the runtime format.

2. **Automated pak-compare gate** — pak-compare should run
   automatically after every `build` command and warn on BLOCKINGs.

3. **Adapter kind auto-derivation** — the loader should derive
   adapter_kind from the MP name using MPB's algorithm and warn if
   the YAML value doesn't match.

4. **Metric label validation** — the loader should reject `|` and
   `:` in metric labels at validate time, not at collection time.
