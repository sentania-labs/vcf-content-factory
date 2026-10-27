# Design: Unifi Switch Connected (symptom)

## Initial prompt

See knowledge/designs/alerts/unifi-poe-budget-nearly-exhausted.md (Scott, 2026-10-27, unifi#30).

## Vision

- Ships inside the unifi SDK pak (`content/sdk-adapters/unifi/`).
- Target: adapterKind `unifi_controller`, resourceKind `UniFiSwitch`.
- Metric symptom: `Status|state` equals 1 (connected). Info; scoping condition only, so the PoE alert does not hold on stale data from a disconnected switch.
