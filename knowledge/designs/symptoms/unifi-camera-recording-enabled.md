# Design: unifi-camera-recording-enabled (symptom)

## Initial prompt

See knowledge/designs/alerts/unifi-wan-degraded.md and unifi-camera-not-recording.md (Scott, 2026-10-27, unifi#30).

## Vision

- Ships inside the unifi SDK pak (`content/sdk-adapters/unifi/`).
- Target: adapterKind `unifi_controller`, resourceKind `UniFiCamera`.
- Property symptom: `Configuration|recording_mode` is not `never`. Info; scoping condition so Camera Not Recording skips cameras deliberately set never to record (review round 2, W1).
