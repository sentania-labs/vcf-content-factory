# Design: unifi-wan-link-up (symptom)

## Initial prompt

See knowledge/designs/alerts/unifi-wan-degraded.md and unifi-camera-not-recording.md (Scott, 2026-10-27, unifi#30).

## Vision

- Ships inside the unifi SDK pak (`content/sdk-adapters/unifi/`).
- Target: adapterKind `unifi_controller`, resourceKind `UniFiWanInterface`.
- Property symptom: `Status|up` equals `true`. Info; scoping condition so WAN Degraded does not fire on an unplugged/unused WAN (unifi build 16 review round 2, B1).
