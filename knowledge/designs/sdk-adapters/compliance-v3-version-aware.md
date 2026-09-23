# Compliance adapter v3: version-aware SCG selection, per-control compliance alerts, dashboard set

- **Type:** managementpack (Tier 2 SDK adapter change) + bundled dashboards
- **Slug:** compliance-v3-version-aware
- **Adapter repo:** `content/sdk-adapters/compliance/` (sentania-labs/vcf-content-factory-sdk-compliance)
- **Date:** 2026-09-23
- **Status:** adapter built (build 61, feat/v3-version-aware); devel install pending

## Initial prompt

Scott, 2026-09-23 (verbatim):

> OK - the SDK compliance pak.  Let's brainstorm where we are at:
> we currently read the SCG repo - and monitor all the controls we can.
>
> we have an alert that triggered when object compliance is below certain thresholds.
>
> Instead of making each vCenter connection all or nothing, I'd like to dynamically detect the ESX/object version and monitor based on the appropriate SCG.
>
> We need to add a SCG compliance dashboard that let's a user dive into the status of things.  I want them to be able to scope it by object type: show me hosts that are not compliant, clusters, etc.  I don't know off the top of my head the right mix of objecs to view by - maybe it shoudl be different dashboards.  Like a Top level: Environment overview with a breakdown by object type and then different dashboards that drill into each object: vCenter Server, ESXi host, vDS, VM, etc.
>
> The host dashbaord for example should allow a user to see hosts that are in/out of compliance based on some scope World and vCenter maybe, view hosts and their compliance %, and select a host and see which metrics are not compliant (this may not be possible with ops dashboarded?, i.e. list metrics where compliance ~=1?
>
> Let's brainstorm and plan here.

Orchestrator proposed (same session): per-object version detection (host
by its ESXi version, VM by its host, vCenter/cluster/vDS/portgroup by
vCenter version, unmapped version = "no benchmark", unscored); drop the
profile from per-control metric keys; failing-control exposure via
native compliance alerts (Option A); four dashboards (Environment
Overview, ESXi Hosts, VMs, vCenter & Networking).

Scott's decisions (verbatim):

> Decisions:
> 1> Agreeed if there isn't an SCG in the repo (we can mine the repo git history for older versions), we should always use the latest "commit" of each version, but just because 7 isn't in main anymore....
> 2> Breaking names is fine
> 3> I like a - this allows us to create recommendations for every alert - basically give them the run book to fix it.
> 4> Works for me, does the framework have the pipeline to buidl the dashboard and bundle it into the pak vs. publish seperately?
>
> Problems:
> Fix them as part of this.

Scott, follow-up (verbatim):

> 1> let's do 6.7 and newer.
> 2> Let's start with one per control
>
> Besure to scan prod and devel ops to account for drift between 9.0 and 9.1 ops.
>
> we probably should put the dashboards first, otherwise we are just building paks without the dashboards - at least the previews, and then interweave it.

Scott, on testing (verbatim, after recon showed a single ESXi build in both labs):

> tests to fake is good, and then once built we can test in different environments, and assume the bones are good, and work from there

## Vision

1. **Version-aware benchmark selection.** Each object is scored against
   the SCG matching its own version: HostSystem by its ESXi version,
   VirtualMachine by its host's ESXi version, vCenter / cluster / vDS /
   portgroup by the vCenter version. An object whose version has no SCG
   gets `profile_name` = "no benchmark for <product> X.Y" and no score.
   Connection setting gains `Auto (by version)` as the default; the
   fixed profiles stay as an override.
2. **Benchmark set sourced from upstream history.** Every SCG version is
   taken from the latest upstream commit that carries it, including
   versions since removed from upstream main. SCG 7.0 was removed in
   upstream `8300517` (2026-07-27); its last form is
   `vsphere/7.0/... Controls.xlsx` (703-20250422-01) at `8300517^`.
   Normalized through the existing canonical-profile pipeline.
3. **Profile-free metric keys (breaking).** Per-control keys become
   `VCF-CF Compliance|<control_id>|{Actual,Expected,Compliant,Description}`;
   `profile_name` says which SCG applied. No migration of old history.
4. **Native compliance alerts with runbooks.** Generated from the
   canonical profiles: one symptom per evaluable control
   (`Compliant == 0`), compliance-subtype (subType 21) alert definitions,
   and a recommendation per control carrying the profile's
   `remediation_text`, so every failing control arrives with its fix.
   Existing score alert re-checked for subtype (appears to be 20,
   Capacity).
5. **Summary per object type, per vCenter.** Rollups per kind and per
   benchmark (scored, average score, non-compliant, no-benchmark count)
   are pushed onto each vCenter object. Recon found one ComplianceWorld
   shared by all adapter instances, so its Summary values were
   last-writer-wins; build 57 retired them (World keeps only
   last_scan_timestamp).
6. **Dashboards bundled in the pak** via `adapter.yaml`
   `bundled_content` (build-sdk already bundles views, dashboards,
   symptoms, alerts, recommendations): Environment Overview, ESXi Hosts,
   VMs, vCenter & Networking. Each passes the RULE-011 wireframe gate.
7. **Fixes carried in:** `detectProfileChange` counts resources under
   wrong kind names; README and adapter.yaml description still say
   "hosts only".

## Decided

- **Benchmark set:** SCG 6.7 and newer (6.7, 7.0, 8.0, 9.0, 9.1). 6.7
  and 7.0 come from upstream history (xlsx), everything older is out of
  scope.
- **Alerts:** one alert definition per control, each with its own
  recommendation. Severity tracks the SCG control priority to keep
  alert volume usable.
- **Ops drift:** recon covers both devel and prod; content must work on
  both Ops 9.0 and 9.1.
- **Unreadable controls push Compliant = -1** (approved 2026-09-23 with
  the VMs / vCenter & Networking mock plan): no per-control alert for a
  setting nobody could read; the object still counts as non-compliant,
  and the unreadable control is excluded from the score (numerator and
  denominator), as the adapter already did before v3.
- **Average score when nothing is scored** (owner answer to review 57
  W2): avg_score is not pushed when scored = 0; a retained old average
  is identifiable from the non_compliant / scored columns beside it.
- **Version unreadable is not "no benchmark"** (review 57 B2, build 58):
  the object reuses last cycle's SCG, else counts as non-compliant in
  the `unknown` benchmark bucket.
- **Dashboard set approved:** Environment Overview, ESXi Hosts, VMs,
  vCenter & Networking (mocks and tables under designs/dashboards/).
- **Order:** dashboard mocks (RULE-011) first, then the adapter work
  interleaved with authoring, so no pak is built without its
  dashboards. In practice builds 57 to 60 were adapter-only dev builds
  for review (not installed); build 61 is the first to carry the
  dashboards and the first intended for install.

## Future (considered, not in v3 scope)

Scott (verbatim):

> One thing I forgot - can we provide a way to turn certain controls off, or modify them (lockouts, tiemouts, etc) - we are not going to include it at this point, but it's something we should consider

- **Per-site control overrides:** disable a control, or replace its
  expected value (lockout threshold, session timeouts, log server).
  Likely shape: an override file per adapter connection, keyed by the
  profile-free `control_id`, so one override applies across SCG
  versions. A disabled control emits no result and raises no alert; an
  overridden one records both the SCG value and the site value.
- **Related defect to solve alongside it:** some scored controls in the
  profiles carry prose instead of a value as the expected result
  (`Site-Specific Log Server`, "Consult your organization's ..."), so
  every object fails them today (false fails, never false passes).
  Overrides are the natural home for the site value; until then these
  controls should become unscored. Affected control_ids per profile
  are listed by the 6.7/7.0 profile work.

## Prose expected values (false fails), v3 action: make unscored

Found by the 6.7/7.0 profile work, 2026-09-23. The adapter can read
these settings, but the expected value is prose, so no real value
matches and every object fails:

| Profile | control_ids |
|---|---|
| 6.7 | `esx.logs-remote`, `esx.lockdown-dcui-access`, `esx.account-password-policies`, `vm.transparentpagesharing-inter-vm-enabled` |
| 7.0 | `esx.annotations-welcomemessage`, `esx.etc-issue` (see note), `esx.logs-remote`, `vc.etc-issue` |
| 8.0 | `esx.annotations-welcomemessage`, `esx.etc-issue`, `esx.logs-remote`, `vc.etc-issue` |
| 9.0 | `esx.etc-issue`, `esx.log-forwarding`, `esx.login-message`, `vc.etc-issue`, `esx.ad-admin-group-name` |
| 9.1 | `esx.ad-admin-group-name`, `esx.etc-issue`, `esx.log-forwarding`, `esx.login-message`, `vc.etc-issue`, `vm.virtual-hardware` |

Notable: 9.1 `vm.virtual-hardware` is live today and fails every VM
(expects the text "vmx-17 or higher"). 7.0 `esx.etc-issue` names the
key with the wrong case, so it is silently skipped instead of failing.
In v3 these become unscored (reported as manual review) until control
overrides supply site values; `vm.virtual-hardware` gets a real
version comparison if cheap, else unscored.

## Owner go: totals rows and issue filing

Scott, 2026-09-23 (verbatim), in answer to the single-aggregation
totals-row TOOLSET GAP and the list of issues to file:

> ship without average for now, and open an issue - and file the other issues

Effect: views ship with SUM-only totals rows (no row count or average);
seven issues filed on sentania-labs/vcf-content-factory.

Scott, 2026-09-23 (verbatim), authorizing the factory PR:

> file the factory PR when ready
