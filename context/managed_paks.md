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
  (`python3 -m vcfops_managementpacks build-sdk content/sdk-adapters/<name>`)
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
