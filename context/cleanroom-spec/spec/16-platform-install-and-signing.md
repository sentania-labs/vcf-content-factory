# 16 — Platform Install Pipeline + Signature Validation

**Status**: DRAFT (Pass 23, 2026-05-16). Field-confirmed against the
devel ops appliance via cross-workspace request (request_id
`6d25e88d-...`); evidence bundle at
`workspaces/lab-admin/exports/vcf-mp-cleanroom-2026-05-16/`.

**Source appliance**: `vcf-lab-operations-devel` running VCF Operations
9.0.2.0.25137838.

**Scope**: This section documents how the appliance ingests, validates,
and installs a `.pak` — i.e., the platform side of the contract, not
the adapter side. The adapter lifecycle contract (configure / discover
/ collect / discard) lives in [§01](01-adapter-lifecycle.md). The
on-disk cryptographic format of pak signatures lives in
[`analysis/pak-signing-chain.md`](../analysis/pak-signing-chain.md).
This section is about *what the appliance does with the signature*.

## TL;DR

1. The install pipeline is **two layers**: a Java CASA orchestrator
   drives a 7-phase state machine that invokes a Python subprocess
   (`vcopsPakManager.py --action <phase>`) per phase.
2. Adapter-supplied hook scripts (`pak_validation_script`,
   `adapter_pre_script`, `adapter_post_script` declared in
   `manifest.txt`) are invoked *inside* their respective phases. The
   appliance does NOT use the file names `validate.py` /
   `preAdapters.py` / `postAdapters.py` as install gates — those are
   conventional script names that pak authors choose, not platform
   contract.
3. **The appliance accepts unsigned paks and installs them in full.**
   42 unsigned-install records across the devel log corpus, including
   community paks (GitLab, Rubrik, Synology, etc.) going through the
   complete STAGE → CLEANUP lifecycle.
4. **The appliance does NOT enforce cert validity dates.** Paks built
   in 2025-12 and signed with the VMware self-signed cert that expired
   2026-01-03 (see `analysis/pak-signing-chain.md`) are still trusted
   when uploaded in 2026-04+. Behavior is "skip dates" — either
   `notBefore`/`notAfter` checks are explicitly disabled, or the
   appliance pins by SHA-1 fingerprint and the validity window is
   never consulted.
5. **Signature validation is opt-in at the API layer.** The
   `findPakInformation` / `getPakInformation` calls take an optional
   `checkSignature` parameter; the common case is
   `checkSignature=null` (no check requested). Even when a check IS
   requested, an unsigned/invalid result is recorded but does not gate
   install.

## The install pipeline — two-layer architecture

### Layer 1: CASA orchestration (Java)

A Java service drives the install through a 7-phase state machine,
recording the per-phase start/completed timestamps to:

```
/storage/log/vcops/log/casa/casa_pak_history_<pakID>.json
```

The phases are:

```
STAGE
  ↓
PREAPPLY_VALIDATE
  ↓
VALIDATE
  ↓
APPLY_ADAPTER_PRE_SCRIPT
  ↓
APPLY_ADAPTER          ← describe.xml registration happens here
  ↓
APPLY_ADAPTER_POST_SCRIPT
  ↓
CLEANUP
```

Sample timing (cycle 2008, observed 2026-05-16 03:46 UTC, full
lifecycle ~26 minutes wall-clock): all 7 phases complete sequentially
with non-overlapping wall-clock windows.

### Layer 2: per-phase Python subprocess

For each phase, CASA forks a fresh Python interpreter running:

```
/usr/lib/vmware-python-3/bin/python \
  /usr/lib/vmware-vcopssuite/utilities/pakManager/bin/vcopsPakManager.py \
  --action <stage|post_stage|validate|post_validate|apply_adapter|
            post_apply_adapter|apply_adapter_pre_script|
            post_apply_adapter_pre_script|apply_adapter_post_script|
            post_apply_adapter_post_script|cleanup|estimate_install_time|
            query|new_validate> \
  --pak <pakID> [...]
```

Each `--action` writes a separate top-level log under:

```
/usr/lib/vmware-vcops/user/log/pakManager/vcopsPakManager.root.<action>.log
```

13+ top-level logs observed (one per --action subcommand). Per-pak
hook-stdout subdirectories also exist for capturing the output of
adapter-supplied scripts (see § Adapter hook scripts below).

### What lives in `apply_adapter`

The `apply_adapter` phase is where the platform parses the adapter's
`describe.xml` and registers the adapter kind. To inspect describe
registration directly:

```
grep -iE "describe|register|adapter kind" \
  /usr/lib/vmware-vcops/user/log/pakManager/vcopsPakManager.root.apply_adapter.log
```

This is the empirical answer to the open question in spec/01 about
WHEN the platform reads describe.xml: **at install time, during the
`apply_adapter` phase, before any adapter-instance configure() can
happen.**

### Adapter hook scripts

The pak's `manifest.txt` declares any number of hook scripts (filename
chosen by the pak author):

```
pak_validation_script   → invoked during VALIDATE
adapter_pre_script      → invoked during APPLY_ADAPTER_PRE_SCRIPT
adapter_post_script     → invoked during APPLY_ADAPTER_POST_SCRIPT
```

The pak's `validate.py` / `preAdapters.py` / `postAdapters.py` you may
see at the outer-pak top level are just conventional names that
Broadcom-internal paks use; **the appliance routes by the
`*_script` keys in `manifest.txt`, not by filename**. Community paks
can name them anything (`my_validate.sh`, `init_adapter.py`, etc.) so
long as `manifest.txt` references them.

## Signature validation — empirical behavior

### The `uploadLocal` audit record

Every `.pak` upload produces a DEBUG record in
`/usr/lib/vmware-vcops/user/log/pakManager/pakManager.actions.log`
with a JSON object summarizing what the validator found:

```json
{
  "signed":               <bool>,    // both signature.cert and signature.mf present?
  "signatureValid":       <bool>,    // RSA verification of signature.mf passed?
  "certificateUntrusted": <bool>,    // signer chain considered untrusted?
  "is_signed":            <bool>,    // duplicates "signed"
  "invalid_reason":       <string>   // human-readable reason or ""
}
```

This record is **descriptive, not prescriptive**. It tells the
operator what the validator saw; it does not gate install on the
result.

### Devel corpus distribution

Across the devel appliance's rotated `pakManager.actions.log` files
(back to 2026-04-17):

| signed | signatureValid | certificateUntrusted | count |
|---|---|---|---|
| false | false | false | **42** |
| true  | true  | false | 21 |
| true  | false | —     | 0 |
| —     | —     | true  | 0 |

**Zero entries** with `certificateUntrusted: true`, despite the
signing cert having expired 2026-01-03 and paks being uploaded
months later. The appliance trusts the cert. (See `analysis/pak-signing-chain.md`
for the cert in question.)

### Finding A: unsigned paks install fully

Unsigned paks observed flowing through the complete install pipeline:
`GitLab-1001`, `Rubrik-11025`, `SynologyDSM-1001`, `SynologyNAS-1001`,
`VCFContentFactoryUniFiIntegration-1005`,
`VCFContentFactoryvSphereStoragePaths-{2002, 2005, 2007, 2008}`.

Each shows up in `casa_pak_history_<pakID>.json` with a complete
STAGE → CLEANUP record. The Rubrik-11025 record specifically:

- `signed: false`
- `invalid_reason: "The PAK file ... is not signed. It is missing
  required signature files signature.mf and signature.cert"`
- Adapter directory currently sitting in
  `/usr/lib/vmware-vcops/user/plugins/inbound/`

**The "invalid_reason" message is recorded but not enforced as a
gate.** The pak completed the full lifecycle.

This empirically answers the question raised in
`analysis/pak-signing-chain.md`: yes, the appliance accepts unsigned
paks. No admin flag was required for these installs — the default
behavior is "accept".

### Finding B: cert validity dates are not enforced

The VMware self-signed signing cert
(SHA-1 fp `53:D8:32:35:CE:BC:C5:5D:70:AD:D0:3A:3E:46:2A:F3:B2:D9:6F:2F`,
expired 2026-01-03 — see `analysis/pak-signing-chain.md`) was used to
sign paks dated 2025-12-30, and those paks have been uploaded
post-expiry (April 2026 timestamps). Every such record comes back:

- `signed: true`
- `signatureValid: true`
- `certificateUntrusted: false`

The cert is still trusted. The appliance is either explicitly
skipping `notBefore` / `notAfter` checks, or it pins by SHA-1
fingerprint against a hardcoded VMware root and never consults the
cert's own validity window.

**Operational implication**: Broadcom does not need to roll the
signing cert urgently — the appliance treats it as permanently
trusted. The cryptographic posture is unchanged from the
analysis/pak-signing-chain.md writeup; the *enforcement* posture
makes the expiry a non-event.

### Finding C: signature check is opt-in at the API layer

`/usr/lib/vmware-vcops/user/log/pakManager/pakManager.query.log` shows
the `findPakInformation` / `getPakInformation` calls with a
`checkSignature` parameter:

```
findPakInformation, pakID=<X>, checkSignature=<true|false|null>
```

The common case is `checkSignature=null` (UI calls that don't ask for
signature info). When a check IS requested with `true`, the result
populates the `uploadLocal` JSON above — but again, the result is
informational, not gating.

This is consistent with Finding A: signature validation is a
platform-side capability that the UI/API may surface to the operator,
but it is not mandatorily enforced on the install path.

## Implications for VCF-CF

### Install-pipeline implications

1. **VCF-CF-generated paks need to declare their hook scripts in
   `manifest.txt`** — using whatever filenames you prefer. The
   appliance routes by manifest keys, not by filename convention.
2. **`describe.xml` is parsed during the `apply_adapter` phase, not
   at adapter-instance configure time.** A malformed describe.xml
   fails install (not first collect). The error surface is the
   `vcopsPakManager.root.apply_adapter.log`.
3. **CLEANUP runs unconditionally** after the adapter-specific
   phases — even if APPLY_ADAPTER failed. VCF-CF-generated paks must
   tolerate partial-install scenarios in their (optional) cleanup
   hook.
4. **Install is long-running** (~26 min observed for the worked
   example). The CASA `casa_pak_history_<pakID>.json` is the
   authoritative source of truth for "is this install done"; UI
   polling should reference that, not just process liveness.

### Signing-and-trust implications

1. **VCF-CF can ship unsigned paks for internal lab use without
   needing an admin override.** The appliance accepts them as-is.
   Confirmed empirically across 42 distinct install records.
2. **For production marketplace distribution**, paks still need to be
   re-signed at upload with VMware's private key — the appliance
   trusts it permanently, but the trust path is via the
   `signature.cert` mechanism documented in
   `analysis/pak-signing-chain.md`. This re-signing happens on the
   marketplace side, not in VCF-CF.
3. **For customer-controlled "self-signed by IT" deployments**, the
   honest answer is "ship unsigned and let the appliance accept it"
   — there's no infrastructure for trusting customer-provided certs,
   but there's also no enforcement that would block an unsigned pak.
   This is the path of least resistance.
4. **The empirical "skip dates" behavior is not a contract** — a
   future appliance hardening pass could turn it on without warning.
   VCF-CF should not bake in assumptions about validity-date
   enforcement either way.

## Provenance — Pass 23 evidence bundle

All findings in this section are sourced from Navani's lab-admin
bundle at `/home/scott/vault/workspaces/lab-admin/exports/vcf-mp-cleanroom-2026-05-16/`,
specifically:

| Subdir | Files | Use |
|---|---|---|
| `install-logs/cycle-2008/full-lifecycle.log` | 497 lines, single pak's complete trace | Phase sequence + timing example |
| `install-logs/cycle-2008/phase-checkpoints.txt` | 7 lines | Distilled phase view |
| `install-logs/pakManager-root/` | 13 top-level `--action` logs | Per-phase invocation pattern |
| `sig-logs/sig-uploadlocal.log` | 200 raw `uploadLocal` lines | Source for the corpus-wide signature distribution table |
| `sig-logs/casa_pak_history_*.json` | 3 sample histories | Unsigned-and-installed (Rubrik, GitLab) + signed-and-installed (Synology) |
| `sig-logs/sig-pakManager-query.log` | Full query log | `checkSignature` flag distribution |
| `sig-logs/signature-validation-summary.md` | Navani's writeup | Cross-check for this section |

Cross-workspace request: `agents/riker/inbox/archive/2026-05-16-1500-vcf-mp-cleanroom-to-navani-tier2-spec-gap-asks.md`,
response in `agents/riker/inbox/archive/2026-05-16-1526-lab-admin-to-vcf-mp-cleanroom-response-tier2-spec-gap-asks.md`.

## Open follow-ups

1. **Confirm appliance behavior under explicit admin signature-enforcement
   mode** if one exists — i.e., is there a system property or
   `pakManager` config that flips the gate from "informational" to
   "enforcing"? The empirical observation says no enforcement; the
   absence of evidence isn't the same as proof of absence.
2. **Verify signing-cert successor exists or doesn't.** Given the
   appliance skips validity dates, Broadcom has no urgency to issue a
   successor — but if one does land in a future VCF Operations
   release, the trusted-fingerprint set changes and this writeup
   needs an update.
3. **Cross-confirm the phase model against a Cloud Proxy adapter
   install** — does the same CASA→Python pattern run on Cloud Proxy,
   or does Cloud Proxy use a different install pipeline for the paks
   it consumes? Out of corpus.
