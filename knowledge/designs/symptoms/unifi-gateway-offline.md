# Design: Unifi Gateway Offline (symptom)

## Initial prompt

Scott, 2026-10-27, reviewing the drafted alert list (synology#35, unifi#30): "S3: uncorrectable erros above 0 - maybe a dynamic threshold of above normal - meaning it changed, or critical when status is not normal, and warning if sectors is above 0 (but that's not necessarily bad, but when it's increasing it's bad) ... 1> SUre drop those for now. 2> okay. 3. Don't do a supermetric, do a calculated metric we add. 4. those thresholds are good. 5. Not at this time."

Issue: sentania-labs/vcf-content-factory-sdk-unifi#30. Draft list reviewed in session 2026-10-27.

## Vision

- Ships inside the unifi SDK pak (`content/sdk-adapters/unifi/`).
- Target: adapterKind `unifi_controller`, resourceKind `UniFiGateway`.
- Property symptom: `Status|state_code` equals `disconnected` or `heartbeat missed`. Critical.
- Not `Status|state`: upgrading/provisioning must not alert (Scott: "2> okay").
