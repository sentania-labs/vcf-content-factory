# Approval: development and build paks on devel_9_1

- **Date:** 2026-10-14
- **From:** Scott, in session
- **Verbatim:** "vcenter accounts are added to devel 9.1 - so you should be
  clear to install any development/build paks"
- **Instance:** devel_9_1, vcf-lab-operations-devel-91.int.sentania.net
  (VCF Operations 9.1.1.0 build 25795063; primary plus Cloud Proxy
  vcf-lab-operations-devel-91-collector).

## Standing scope

- Install, upgrade and reinstall factory dev-preview paks (0.0.0.N) and the
  Python fork rc paks on devel_9_1, and the adapter accounts and the Cloud
  Proxy collector group they need to be exercised.
- Read-only log access through the UI Support Logs browser or SSH.

## Not covered

- Uninstalling Broadcom's stock packs, changing the vCenter accounts Scott
  added, global settings, prod, devel (9.0.2).

## Note

No vCenter credential is held in `.env`, so compliance and vsanhostmetrics
accounts need a credential Scott enters once in the UI (or Scott creates those
accounts); cluster-perf-risk needs none.

## Unsigned paks enabled (2026-10-14, about 2:35 PM)

devel_9_1 refused every factory pak upload with `unsigned_pak_installation.not.allowed`
even with ignoreSignatureChecking=true. Scott, verbatim: "i've enabled allowing
unsigned paks" (changed by Scott himself in the UI). Installs resume under the
standing scope. Investigation of the setting and its customer impact:
`investigations/2026-10-14-unsigned-pak-policy-9-1-1.md` (in progress).

## Outcome (2026-10-14, 2:33 to 3:20 PM)

- Compliance 0.0.0.94: three accounts on factory-cloud-proxy (the Cloud
  Proxy), certificate accepted, full cycles with no certificate error;
  Rollup mgmt 66/59/76.6, wld01 61/38/84.7, wld02 52/46/78.1; Environment 179
  scored after one lag interval. The framework's "FIPS-approved-only mode
  detected" WARN appears on the Cloud Proxy: devel_9_1 runs FIPS, so it
  reproduces prod's TLS conditions, and build 94 collects there.
- cluster-perf-risk rc.3: container on the Cloud Proxy runs
  ghcr.io/sentania-labs/cluster-perf-risk at the pak's digest; 3 clusters,
  9 hosts; metrics landed (mgmt-cl01 risk 74.8, yellow). End-to-end proof of
  the fork CI design.
- vsanhostmetrics rc.4: container at the pak's digest; one account on the
  vSAN cluster (verify vCenter certificate set false for the lab, the gap fork
  issue #1 covers); objects attached under native hosts; first cycle wrote no
  stats, second cycle about 200 objects with stats.
