# Managed paks (SDK adapter registry)

The declared registry of **independently-versioned SDK management-pack
adapters**. Each entry names a pak that lives in its **own git repo** with
its own CI release pipeline — it is *not* stored in this factory repo.

This file is the legible "here is the pak family" surface: a flat,
**SHA-free, version-free** list of `name / remote / target`. Pointers to a
pak's published binary are *derived* from the remote at publish time
(`<remote>/releases/latest`), never stored here — so this registry never needs
editing when a pak ships a new version.

## How it works

- **Bootstrap clones each entry.** `scripts/bootstrap_managed_paks.sh` reads
  this file and clones every registered remote into its target directory under
  `content/sdk-adapters/`. Those directories are **gitignored** by the factory
  (each is an independent repo), so cloning them never dirties the factory tree.
- **Authoring is normal git.** `cd content/sdk-adapters/<name>`, edit, commit,
  push — to the pak's *own* remote. The factory tooling
  (`python3 -m vcfcf_managementpacks build-sdk content/sdk-adapters/<name>`)
  still does local *dev* builds; the **official** release is the pak's own CI
  building on a `v*` tag.
- **Publish emits a pointer.** When a factory bundle references a managed pak,
  `/publish` records a pointer to `<remote>/releases/latest` — it never rebuilds
  or mirrors the `.pak` binary. The pak's own GitHub Release is the single
  source of truth for the artifact.
- **New pak = template + one line here + one secret.** Instantiate the GitHub
  template repo `sentania-labs/vcf-content-factory-sdk-template`, add one
  entry below, and before the first `v*` tag give the new repo its
  `sdk-release` Environment with the `SDK_RUNTIME_SSH_KEY` secret: a fresh
  ed25519 keypair, public half added as a read-only deploy key on the private
  `vcf-content-factory-sdk-runtime` repo (title "CI read-only (<name> pak
  builds)"), private half stored as the Environment secret, private file
  shredded. Without it the tag build fails at "Fetch Broadcom SDK jar"
  (vsanperf v1.0.0.9, 2026-11-06). `gh repo create --template` lands the repo
  under the caller's account unless the name is `sentania-labs/<name>`;
  transfer it before anything is pushed.

## Hard rules

1. **Registered remotes only.** The bootstrap and publish flows act only on
   paks listed under `## Paks` below (entries under `## Retired paks` are
   records, not registrations). The orchestrator adds entries after the pak's repo exists;
   agents do not add entries on their own.
2. **No SHAs, no versions.** Entries name the repo and where it mounts —
   nothing more. "Latest release" is derived, not pinned. (A future opt-in tag
   pin for reproducible bundle snapshots is the only sanctioned exception, and
   is not used by default.)
3. **Local clones are gitignored.** Targets live under `content/sdk-adapters/`,
   which the factory `.gitignore`s. If a registered remote is missing locally,
   bootstrap reports it and continues — it does not block the session.
4. **Naming convention.** Pak repos live in the `sentania-labs` org, named
   `vcf-content-factory-sdk-<name>`. The template repo
   (`…-sdk-template`, seeded from hello-world) is **not** registered here — it
   is a skeleton, not a published pak.

## Clone convention

```
content/sdk-adapters/
  <name>/        # git clone of the pak's remote (gitignored)
```

Automate with:

```bash
scripts/bootstrap_managed_paks.sh          # clone missing only
scripts/bootstrap_managed_paks.sh --update # also git pull existing
```

Each entry below MUST provide a `**Remote:**` line (the clone URL) and a
`**Target:**` line of the form `` `content/sdk-adapters/<name>/` `` — those two
fields are what the bootstrap script parses.

## Paks

<!--
No managed paks registered yet. Entries are added (one per pak) as each
adapter is extracted to its own sentania-labs repo. Template for an entry:

### <name>

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-<name>
- **Target:** `content/sdk-adapters/<name>/`
- **adapter_kind:** vcfcf_<name>
- **Owner:** sentania-labs. Public repo.
- **Notes:** one line on what the pak does.

The hello-world adapter is intentionally absent — it seeds the template repo,
it is not a published pak.
-->

### compliance

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-compliance
- **Target:** `content/sdk-adapters/compliance/`
- **adapter_kind:** vcfcf_compliance
- **Owner:** sentania-labs. Public repo.
- **Notes:** ESXi compliance (VMware SCG / CIS) evaluated via vCenter,
  stitched onto VMWARE HostSystem. Ships bundled view + dashboard and the
  vim25 / JAX-WS vendor libs (Apache-2.0 per vmware/vcf-sdk-java).

### unifi

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-unifi
- **Target:** `content/sdk-adapters/unifi/`
- **adapter_kind:** unifi_controller
- **Owner:** sentania-labs. Public repo.
- **Notes:** Ubiquiti UniFi controller.

### synology

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-synology
- **Target:** `content/sdk-adapters/synology/`
- **adapter_kind:** synology_diskstation
- **Owner:** sentania-labs. Public repo.
- **Notes:** Synology DiskStation.

### vsanperf

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-vsanperf
- **Target:** `content/sdk-adapters/vsanperf/`
- **adapter_kind:** vcfcf_vsanperf
- **Owner:** sentania-labs. Public repo. Instantiated from the sdk-template
  2026-11-06.
- **Notes:** vSAN Performance Service metrics (JSON transport, one wildcard
  spec per entity type per cluster) stitched as instanced metrics onto VMWARE
  HostSystem and ClusterComputeResource (and VirtualMachine when the VM tier
  is on); the Java port of the Python vsanhostmetrics pack. Designs:
  `knowledge/designs/vsanperf-mp-v1.md` (Build 1) and `vsanperf-mp-v2.md`
  (Build 2); plan:
  `knowledge/context/investigations/2026-11-06-vsanhostmetrics-scale-plan.md`.
  Released: `v1.0.0.9` (2026-11-06, pre-release, Build 1, build 9).
  Build 2 (dashboard-scope parity in four tiers, version 1.1.0, builds 10 to
  13, pak PR #8) merged 2026-11-07; build 12 default tiers proven on devel
  9.0.2, 8.18 (analytics-node collector) and 9.1 (records
  `knowledge/context/reviews/vsanperf-t5-devel-*-build-12.md`; reviews
  `vsanperf-build-10-review.md`, `vsanperf-build-11-review.md`); the dev
  previews are build 16 on devel 9.0.2 (VM tier proven there, record
  `vsanperf-t5-devel-9.0-build-16-vm-tier.md`, with live `PERF push`
  timings) and build 18 on 8.18 and 9.1 (records
  `vsanperf-t5-devel-{8.18,9.1}-build-18.md`: T5 of the scale build done). T3/T4 (pak #6) delivered in
  builds 14 to 18 (pak PR #10): review `vsanperf-build-15-review.md`
  (approve, W1 to W4 fixed in build 16, CHANGELOG 1.1.0.16; builds 16 to 18
  reviewed by Codex on #10 only). Default tiers at 70 clusters complete
  under the deadline from cycle 4 at ~7 MB heap, the VM tier ~34 MB.
  Released: `v1.1.0.18` (2026-11-07, Build 2 plus the scale gate; shipped
  without a per-vCenter ceiling measurement because `max_parallel_clusters`
  and `call_timeout_seconds` are Advanced Settings and a slow vCenter shows
  as `clusters_timed_out`; the key grammar stays `vSAN Perf|`, Scott
  2026-11-07).
  Build 3 (`metric_scope` dashboard | all: every catalog key of the 69 vSAN
  perf types, 1,805 keys, no labels filter; version 1.2.0, builds 19 to 22,
  pak PR #11) merged 2026-11-07 (pak main 5528e7d); design
  `knowledge/designs/vsanperf-mp-v3.md`, review
  `knowledge/context/reviews/vsanperf-build-19-review.md` (B1, W1 to W4, N1 to
  N5 fixed in build 20; Codex's case-sensitive `exclude_types` fixed in
  build 21; a stop-during-call-counted-as-timeout engine race found by a JDK
  25 CI flake and fixed in build 22). Dev preview 0.0.0.22 on devel 9.0.2:
  dashboard, all and back to dashboard proven, with the learned-state reset
  (record `vsanperf-t5-devel-9.0-build-22-metric-scope.md`: host 1,282 keys,
  cluster 348, steady 37 calls at `all` with host and cluster tiers, 13
  learned-empty and 4 faulting host types, pctMemUsed an integer percent in
  Ops); not done there: the same-window JSON comparison of the read-back
  values, the browser pass and the host reboot of README check 7. 8.18 and
  9.1 at default scope unchanged from build 18 (records
  `vsanperf-t5-devel-{8.18,9.1}-build-22-default-scope.md`), but the
  per-instance adapter log was checked on neither (8.18: analytics node
  refuses key SSH; 9.1: the new instance's log file was not located,
  collector.log only; the build 24 record found it: `VsanPerfAdapter_2340.log`
  was the live file all along). Disk and VM tiers at scope `all` proven live
  2026-11-07 (record `vsanperf-t5-devel-9.0-build-22-all-scope-all-tiers.md`:
  cl01 alone 39 steady calls, 42 on settled VM cycles, 7,028 series; whole
  cycle 6 to 29 s with the then-failing probe cluster included). v1.2.0.22
  was not tagged; superseded by Build 4.
  Build 4 (1.2.1, builds 23 to 24, pak PR #12, main 726b0b2, merged
  2026-11-08; Scott: "If the performance service is disabled we should
  cleanly skip it and there should be an alert"): one VsanClusterGetConfig
  per cluster per cycle, disabled clusters skipped without counting as
  failed, new self-metrics `clusters_perfsvc_disabled` and
  `required_calls_failed`, cluster key `vSAN Perf|Performance Service|enabled`
  (0/1), first bundled content (symptom, Warning/Risk alert, recommendation
  on VMWARE ClusterComputeResource), per-type fault isolation with
  three-strike 24 h learning for parsed vSphere faults only (design v3
  § 1.2.1 D1 to D8; review `vsanperf-build-23-review.md`, B1 transport
  errors must not strike, fixed in build 24). Dev preview 0.0.0.24 on devel
  9.0.2: phase 1 passed (record `vsanperf-t5-devel-9.0-build-24-perfsvc.md`:
  the OSA probe cluster with six server-side stats DB schema faults counts
  ok from the first cycle (build 22: failed every cycle), its faulting types
  learned at cycle 4 (52 calls while learning, then 37 steady: cl01 23 +
  probe 14), key 1 on both clusters, content installed); phase 2 (service
  off then on: key 0, alert raised, 23 calls, then cancel) waits for Scott's
  vCenter write. Doc gap for the next build: README check 8 lists four
  faulting types, the lab has six (`vsan-cpu`, `vsan-memory` added). 8.18
  and 9.1 previews of build 24 passed 2026-11-08 (records
  `vsanperf-t5-devel-{8.18,9.1}-build-24-default-scope.md`; the probe
  cluster is in scope on both: 43 calls before, 52 while relearning, 37
  steady, clusters_failed 0; on 9.1 after one failed login cycle at the
  restart (30 s vCenter login timeout, recovered unaided); 8.18 adapter log
  still unreadable (analytics node) and its series drift 1,452 to 1,686
  unexplained; key read 1 on mgmt-cl01 on both, probe key read on 9.1 only).
  RULE-019 install record complete on 8.18, 9.0 and 9.1 for build 24; the
  9.1.1.0100 compile leg is still skipped (jar absent). Tag v1.2.1.24 on Scott's word after phase 2.
  Tests: `T.CLOCK` pinned to 2026-11-07T14:00Z; build 22's tests were
  date-bombed from 2026-11-08 (lesson candidate).
  History 2026-11-06: Build 1 merged (builds 5 to 9, pak PRs
  #2 to #5 and #7), proven on the same three instances (records
  `vsanperf-t5-*-build-5/7/9.md`; build 4 review findings fixed in build 5).
  Open: per-vCenter call ceiling (field data or a multi-cluster vCenter;
  retune the `max_parallel_clusters` default in a 1.1.1 if needed); 8.18
  Cloud Proxy placement (jar sync timeout, lesson
  remote-collector-upgrade-start-race.md third mode, factory #314, parked);
  the read-back-vs-`PERF`-log comparison; wrong-credential ERROR check; pNIC
  rendering in the UI; `docs/installing.md` certificate-accept step for
  8.18/9.1; factory #322 (Test
  Connection shadows a logging.properties DEBUG). Closed 2026-11-07: #310
  (#321), #311/#315 (#319), #313 (#323, buildkit 1.0.25).

## Third-party Python Integration SDK paks (forks, contribute upstream)

Registered 2026-10-13 on Scott's instruction ("I would like to fork these so we
can better manage updates to them as opposed to straight cloning"). These are
not factory SDK adapters: they are Python Integration SDK packs by other
authors, forked into `sentania-labs` so tune-up pull requests can be prepared
on a branch and sent upstream. They stay Python. The clone target reuses
`content/sdk-adapters/` only so the bootstrap script manages them; build-sdk,
validate-sdk and pak-compare do not apply. Keep `main` tracking upstream (add
an `upstream` remote and fast-forward from it); do work on branches.

### vsanhostmetrics (fork of nickfirefoot/vsanhostmetrics)

- **Remote:** https://github.com/sentania-labs/vsanhostmetrics
- **Target:** `content/sdk-adapters/vsanhostmetrics/`
- **Upstream:** `https://github.com/nickfirefoot/vsanhostmetrics.git`
- **Release branch:** `main` (the author merged `agent/beta-vsan-host-metrics`
  into `main` on 2026-10-13; before that releases 1.3.1 to 1.4.6 were cut from
  the beta branch)
- **Type:** Python Integration SDK container adapter (upstream's)
- **Status:** forked 2026-10-13; assessed
  (`investigations/2026-10-13-vsanhostmetrics-tuneup-assessment.md`); fork
  issues #1 to #6 track the tune-ups (accepted certificate unused, silent
  collect errors, one cluster aborts all, username outside the credential,
  undeclared pyvmomi, foldered datacenters skipped; #7 README package name); PRs upstream on Scott's go.
  CI: the author merged his beta branch into `main` (ee2c575, 2026-10-13);
  branch `tuneup/ci-ghcr-attestation-main` rebased onto it, proof tag
  `v1.4.6-rc.4` (run 38496680141) green; upstream PR
  nickfirefoot/vsanhostmetrics#1 opened 2026-10-13 on Scott's go; fork issues
  #8 to #11 (his generator tooling) and #12 (object model design question).
  Tune-up round (2026-10-28 to 29): branch `tuneup/upstream-2026-10` resolves
  fork issues #1 to #4, #6, #7, #10, #11 plus the pyVmomi pin guard and the
  msgpack Trivy id; reviews in `reviews/python-packs/`. Username moved into the
  credential as a breaking 2.0.0 (the 1.5.0 fallback design was built, tested
  as rc.2/rc.3 and dropped); `MIGRATION.md` carries the live result. Proven in
  place on 8.18.7, 9.0.2 and 9.1.1 (1.4.6 to 1.5.0-rc.2, then to 2.0.0-rc.1;
  the direct 1.4.7 to 2.0.0 install is unproven and said so). Fork tags
  `v2.0.0-rc.1`, `v2.0.0-rc.2` published. Upstream PR
  nickfirefoot/vsanhostmetrics#2 opened 2026-10-29 on Scott's go.
  2026-11-06: upstream PR #2 still open, no review. Scale assessment for
  a 70-cluster vCenter and the decision to port to a native Java Tier 2
  adapter in a factory SDK repo (MVP: one cluster, host tier, DOM owner /
  DOM client / pNIC stitched onto HostSystem; build 2: parity with the
  451 default-scope keys): `investigations/2026-11-06-vsanhostmetrics-scale-plan.md`,
  API map `api-maps/vsan-performance-service.md`, live footprint, collector
  sizing and stitch test alongside. The Python fork keeps shipping meanwhile.

### cluster-perf-risk (fork of gillaspy/cluster-perf-risk)

- **Remote:** https://github.com/sentania-labs/cluster-perf-risk
- **Target:** `content/sdk-adapters/cluster-perf-risk/`
- **Upstream:** `https://github.com/gillaspy/cluster-perf-risk.git`
- **Release branch:** `main`
- **Type:** Python Integration SDK container adapter (upstream's); credential
  posture already mapped in
  `investigations/2026-10-13-cluster-perf-risk-credential-reuse.md`
- **Status:** forked 2026-10-13; assessed
  (`investigations/2026-10-13-cluster-perf-risk-tuneup-assessment.md`); fork
  issues #1 to #9 track the tune-ups (silent login failure, unverified TLS,
  publish-to-native edges, per-cluster exception, timeouts, request volume,
  token at DEBUG, empty Test Connection, packaging); PRs upstream on Scott's go.
  CI: branch `tuneup/ci-ghcr-attestation` proven by tag `v1.3.0-rc.1` (run
  38471417171, image and pak attested and signed, Trivy gated), see
  `knowledge/designs/ci/python-pack-ghcr-attestation.md`.
  Tune-up round (2026-10-28): branch `tuneup/upstream-2026-10` resolves fork
  issues #1, #3, #5 to #9 and raises #2 (TLS to the Suite API) as a question;
  review in `reviews/python-packs/`. Fork tag `v2.1.0-rc.1` published; proven
  on 8.18.7, 9.0.2 and 9.1.1 via the 1.x to 2.x MIGRATION.md path (9 Suite API
  calls per cycle, 0 ERROR). Upstream PR gillaspy/cluster-perf-risk#13 opened
  2026-10-29 on Scott's go.

### vcommunity (fork of vmbro/VCF-Operations-vCommunity)

- **Remote:** https://github.com/sentania-labs/VCF-Operations-vCommunity
- **Target:** `content/sdk-adapters/vcommunity/`
- **Upstream:** `https://github.com/vmbro/VCF-Operations-vCommunity.git`
- **Release branch:** `main`
- **Type:** Python Integration SDK container adapter (upstream's); the project
  lives in the repo's `Management Pack/` directory, not the repo root
- **Status:** forked 2026-11-12 on Scott's go, to prepare the fix for
  vmbro/VCF-Operations-vCommunity#99 (the pak ships 117 views under built-in
  view ids; install overwrites them, uninstall deletes them). Lesson:
  `knowledge/lessons/pak-content-must-not-reuse-stock-ids.md`. Upstream PR
  vmbro/VCF-Operations-vCommunity#100 opened 2026-11-12 on Scott's go
  (branch `fix/builtin-view-ids`). Later releases of the pack are published
  from the fork `e1-rahabok/VCF-vCommunity-Adapter` (same fork network; it
  ships 120 such ids); the fix was ported and sent there the same day as issue
  #91 and PR #92 (branch `fix/builtin-view-ids-e1`, pushed to this fork).
  Measurements and upgrade behavior by product line:
  `knowledge/context/investigations/2026-11-12-vcommunity-upstream-builtin-view-ids.md`.
  Reviews in `reviews/python-packs/`.
  Target path: the retired Java port (see Retired paks) used the same
  target. Its clones were moved out on 2026-10-27, but a checkout that still
  has one at this path must remove it before bootstrap, because bootstrap
  does not compare an existing clone's origin with the registered Remote
  and would report the wrong repo as current. The defect gate's name check
  cannot tell the two `vcommunity` entries apart either.

## Retired paks

Kept for the record. The bootstrap script and the Python registry reader
(`src/vcfcf_packaging/managed_paks.py`) both stop reading at this heading
(exact text `## Retired paks`, level 2, parsed by both), so nothing below is
cloned, refreshed, reported or published. The one reader that does look
below it is the defect gate's name check (`registered_pak_names()`, issue
#219): it recognises every `Target:` name in every section, forks and retired
paks included, so a defect naming one is attributed to it. Local clones under
`content/sdk-adapters/` may remain; they are gitignored, and
`scripts/path_reference_audit.sh` still counts their paths as known roots on
purpose, because older docs cite them. Retiring a pak is the orchestrator's edit on Scott's word, and
the word is quoted in the entry.

### vcommunity, vcommunity-vsphere, vcommunity-os (retired 2026-10-15)

Scott, verbatim (2026-10-15): "vcommunity <- these are deprecated and
experiemnts that we shouldn't worry about for now. I'm not sure how we
handle/mark this so it doesn't keep coming up."

Three repos, one experiment: the Java rewrite of
vmbro/VCF-Operations-vCommunity and its three-adapter split. The three
unsigned-pak README PRs were squash-merged 2026-10-26 on Scott's word
("just merge the outstanding work on them"); no open PRs remain, open
issues stay as they are, nothing further is scheduled. Scott, verbatim (2026-10-27): "how many times do I have to ask you to
drop the vcommunity ports?" All three GitHub repos were archived that day,
and the local clones were moved out of `content/sdk-adapters/` to
`/mnt/holding/vcf-content-factory/retired-paks/` (clean, nothing unpushed),
so no sweep of that folder finds them. Do not re-clone, survey, release,
or mention them; they are done.

#### vcommunity

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-vcommunity
- **Target:** `content/sdk-adapters/vcommunity/`
- **adapter_kind:** vcfcf_vcommunity
- **Owner:** sentania-labs. Public repo.
- **Notes:** Native Java SDK rewrite of vmbro/VCF-Operations-vCommunity
  (Onur Yuzseven, CC) — vSphere enrichment stitched onto VMWARE
  Cluster/Host/VM under the `vCommunity|` namespace; central
  SolutionConfig check lists; Windows guest-ops monitoring.
  Design: `knowledge/designs/managementpacks/vcommunity-sdk.md`.
  **Being split** (`vcommunity-three-adapter-split.md`): guest-OS surface
  moved to `vcommunity-os`; this entry retires once vsphere+os reach
  devel parity.

#### vcommunity-vsphere

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-vcommunity-vsphere
- **Target:** `content/sdk-adapters/vcommunity-vsphere/`
- **adapter_kind:** vcfcf_vcommunity_vsphere
- **Owner:** sentania-labs. Public repo.
- **Notes:** vSphere half of the vCommunity three-adapter split (Onur
  Yuzseven / vmbro/VCF-Operations-vCommunity, CC) — the large-majority
  surface: full vSphere/vCenter read (clusters, hosts, VMs) plus the
  passive Tools-path `Guest OS|Operating System|*` keys, stitched onto
  VMWARE Cluster/Host/VM via the vim25 vCenter session. Ships the central
  SolutionConfig check lists (incl. `Critical Business Applications`).
  Reviewer APPROVE 0 BLOCKING; migrated onto devel, GREEN. This is the
  primary split artifact; the unified `vcommunity` entry retires once
  vsphere+os reach devel parity.
  Design: `knowledge/designs/managementpacks/vcommunity-three-adapter-split.md`.

#### vcommunity-os

- **Remote:** https://github.com/sentania-labs/vcf-content-factory-sdk-vcommunity-os
- **Target:** `content/sdk-adapters/vcommunity-os/`
- **adapter_kind:** vcfcf_vcommunity_os
- **Owner:** sentania-labs. Public repo.
- **Notes:** Guest-OS half of the vCommunity three-adapter split (Onur
  Yuzseven / vmbro/VCF-Operations-vCommunity, CC). Windows guest-ops —
  services, in-guest CSV OS-info, event logs — stitched onto VMWARE
  VirtualMachine via its OWN vCenter session + GuestOperationsManager.
  Ships the 2 Windows SolutionConfig check lists. **In-guest collection
  is a KNOWN-OPEN, intentionally-shelved blocker** (execution-policy /
  ConstrainedLanguage theory; privilege ELIMINATED) — see README +
  `knowledge/context/investigations/vcommunity-windows-services-empty-2026-06-23.md`.
  Design: `knowledge/designs/managementpacks/vcommunity-three-adapter-split.md`.

