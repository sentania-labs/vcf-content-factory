# Investigation Plan: Cloudflare Pak Silent-Fail on Production

**Created:** 2026-05-17
**Status:** Not started
**Pak:** `dist/mpb_vcf_content_factory_cloudflare.1.0.0.1.pak`
**Target:** `vcf-lab-operations.int.sentania.net` (profile: qa)

## Symptom

Pak uploads successfully (`pakId='VCFContentFactoryCloudflare-1001'`), install
task runs and completes (`isPakInstalling` goes True → False), but adapter kind
`mpb_vcf_content_factory_cloudflare` never appears in `getIntegrations`.

No error surfaces through the UI install polling. This is the "silent-fail"
pattern.

## What's been ruled out

- **adapters.zip directory entries:** Tooling agent confirmed the factory
  builder already emits explicit directory entries matching the reference pak
  structure (16 entries, `external_attr=0o20`, correct order). Not the cause.
- **Pak structure (pak-compare):** Only 1 BLOCKING — missing `"content": []`
  in export.json. This is a known-accepted divergence (strip audit 2026-05-14).
  The latest UniFi factory paks also omit it and have installed successfully
  in the past. However, this has NOT been verified on this specific VCF Ops
  build — it remains a candidate.
- **Design import on devel:** Succeeded (design ID
  `fcb6c418-8240-4daf-be0e-6d4f90256a10`). Test connection + collection
  preview both pass. The design is structurally valid.

## Investigation steps

1. **Check if a prior install left ghost state.** Query
   `GET /suite-api/api/solutions/adaptertypes` on prod (profile qa) and grep
   for `cloudflare`. A partial/failed prior install may block re-install
   silently. If found, uninstall first.

2. **Check the pak install log on the appliance.** SSH to
   `vcf-lab-operations.int.sentania.net`, look at:
   - `/var/log/vmware/vcops/analytics*.log` for adapter registration errors
   - `/var/log/vmware/vcops/collector/collector.log` for pak deployment errors
   - `/storage/vcops/user/plugins/inbound/` for whether the pak was extracted

3. **Try installing via the Suite API instead of the UI path.** The current
   installer uses the `/ui/` upload + install flow. Try the public API:
   `POST /suite-api/api/solutions` with the pak as multipart upload. Different
   code path may surface a different error.

4. **Test the `"content": []` hypothesis.** Manually patch the built pak to
   add `"content": []` to export.json and retry install. If that fixes it,
   the strip audit decision needs to be revisited for the pak format
   (distinct from the exchange format).

5. **Compare against a known-good factory pak install.** Install the latest
   UniFi pak (`dist/mpb_vcf_content_factory_unifi_integration.1.0.0.13.pak`)
   on prod. If it also silent-fails, the problem is environment-level (VCF Ops
   build, permissions, collector state). If it succeeds, the problem is
   Cloudflare-pak-specific.

6. **Check the `manifest.txt` adapter_kinds field.** Ensure it lists
   `mpb_vcf_content_factory_cloudflare` exactly. A mismatch between
   manifest.txt and the adapter directory name inside adapters.zip would
   cause silent-fail.

7. **Check pak size.** The pak is 22.4 MB (mostly the adapter3.jar stub).
   Verify there isn't a size limit on the upload endpoint that causes
   truncation.

## Likely root causes (ranked)

1. Ghost state from the first install attempt blocking the second
2. `content: []` actually required in pak export.json (not just exchange)
3. manifest.txt / adapters.zip naming mismatch
4. Environment-level issue (collector not picking up new adapters)
