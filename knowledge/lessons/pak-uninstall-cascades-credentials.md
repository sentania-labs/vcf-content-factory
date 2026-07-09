# Pak uninstall on VCF Ops cascades into credential deletion

## What happens

When the content-installer agent uninstalls an SDK adapter pak (DELETE
adapter instances → UNINSTALL pak), VCF Ops cleans up the credentials
that referenced the adapter kind. After the uninstall finishes, the
credentials return 404 from
`GET /suite-api/api/credentials?adapterKindKey=<kind>`.

The cleartext usernames + passwords entered via the VCF Ops UI are
*not* recoverable through the API after this point — credentials only
flow one way (write-through-create, read-back returns metadata
only with `password` field redacted).

## Impact observed

Compliance MP v32 → v33 upgrade on devel (2026-05-29):

- v32 had two adapter instances: `vcf-lab-vcenter-wld01` (cred `WLD01`)
  and `vcf-lab-center-mgmt` (cred `mgmt`).
- Installer DELETEd both instances (HTTP 204), then UNINSTALLed v32.
- v33 installed cleanly; adapter kind re-registered on disk and via
  Suite API.
- Post-install: both credentials returned 404 — gone.
- Re-install of adapter instances blocked: cleartext vCenter creds
  not in `.env` and not in repo, so credential recreation needs the
  user to either supply via API or rebuild in the VCF Ops UI.

## The right pre-flight

When the orchestrator approves an SDK-adapter pak round-trip on a
production-like instance, the installer agent should:

1. **Before DELETEing adapter instances**, list credentials for the
   adapter kind and stash a manifest:
   ```
   /tmp/credential-manifest-<adapter-kind>-<timestamp>.json
   ```
   Manifest contains: credential id, name, kind key, list of fields
   (sans values), referenced-by adapter-instance ids and names.
   The manifest lets the installer (or user) deterministically
   recreate instances by name; values still need an out-of-band
   secret source.
2. **Refuse to uninstall** if the manifest shows credentials whose
   values aren't recoverable from `.env` or another known store —
   bail back to the orchestrator with a TOOLSET GAP, not a silent
   data-loss.
3. **Document the credential map** in the pak-install lesson / spec
   so the user can supply replacement values in a structured way
   (env var names per credential) before a destructive round-trip.

## Workaround until installer is fixed

For SDK adapter paks on prod-like instances, store the adapter-instance
credentials in `.env` under known keys:

```
export VCFCF_COMPLIANCE_VCENTER_MGMT_USER=...
export VCFCF_COMPLIANCE_VCENTER_MGMT_PASSWORD=...
export VCFCF_COMPLIANCE_VCENTER_WLD01_USER=...
export VCFCF_COMPLIANCE_VCENTER_WLD01_PASSWORD=...
```

so that `content-installer` can rehydrate credentials post-install
without prompting. Mirror this pattern for any MP whose adapter takes
a `<credential_kind>` block.

## Related

- `knowledge/lessons/pak-content-localization-bundles.md` — content side of MP
  install, separate failure mode.
- `knowledge/context/investigations/v20-step5-silent-drop.md` — earlier MP
  install-cycle investigation.
