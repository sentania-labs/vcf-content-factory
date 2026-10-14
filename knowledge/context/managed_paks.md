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
- **New pak = template + one line here.** Instantiate the GitHub template repo
  `sentania-labs/vcf-content-factory-sdk-template`, then add one entry below.

## Hard rules

1. **Registered remotes only.** The bootstrap and publish flows act only on
   paks listed here. The orchestrator adds entries after the pak's repo exists;
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

### vcommunity

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

### vcommunity-vsphere

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

### vcommunity-os

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
  #8 to #11 (his generator tooling) and #12 (object model design question)

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
  `knowledge/designs/ci/python-pack-ghcr-attestation.md`
