# Design: Unifi Camera Not Recording (alert)

## Initial prompt

Scott, 2026-10-27, reviewing the drafted alert list (synology#35, unifi#30): "S3: uncorrectable erros above 0 - maybe a dynamic threshold of above normal - meaning it changed, or critical when status is not normal, and warning if sectors is above 0 (but that's not necessarily bad, but when it's increasing it's bad) ... 1> SUre drop those for now. 2> okay. 3. Don't do a supermetric, do a calculated metric we add. 4. those thresholds are good. 5. Not at this time."

Issue: sentania-labs/vcf-content-factory-sdk-unifi#30. Draft list reviewed in session 2026-10-27.

## Vision

- Ships inside the unifi SDK pak (`content/sdk-adapters/unifi/`).
- Target: adapterKind `unifi_controller`, resourceKind `UniFiCamera`.
- U6. All of: unifi-camera-not-recording, unifi-camera-connected. Warning.
- Bundled in the pak; enabled by default (default policy has no overrides for this adapter kind, recon 2026-10-27).
- Scoped to cameras whose recording mode is not never (unifi-camera-recording-enabled).
