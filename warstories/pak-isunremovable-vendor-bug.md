# War Story: VCF Operations `isUnremovable` Flag Not Enforced

**Product:** VCF Operations 9.0.2  
**Date:** 2026-04-16  
**Impact:** Built-in pak removed from lab instance; no recovery path found.

## What happened

During scripted pak uninstall testing, the investigator extended scope to verify
whether VCF Ops enforces the `isUnremovable: true` flag server-side. It doesn't.

The `POST /ui/solution.action mainAction=remove` endpoint accepts and executes a
remove call against any pak, including those marked `isUnremovable: true` (vSAN,
vCenter, Service Discovery). The flag is advisory-only — presumably consumed by
the UI to disable the remove affordance, but not rechecked when the remove call
arrives.

The vSAN pak was successfully removed from the lab instance. The adapter kind
deregistered. Content targeting vSAN became non-functional.

## Why there's no recovery

Every reactivation path was tried. None restored the pak:

- `POST /suite-api/internal/solutions/preinstalled/<id>/activate` — queues a task
  that hangs indefinitely
- `POST /ui/solution.action mainAction=enable` — "Solution is already being
  installed or queued" (stale queue entry blocks new attempts)
- `mainAction=cancel` — accepted, doesn't clear the stuck queue
- `mainAction=resetSolutionUninstallState` — no observable effect
- `mainAction=finishStage` — no observable effect

The enable/activate pipeline serializes through a queue that's never drained
after an `isUnremovable: true` pak is incorrectly removed. The only practical
recovery is cluster restart or restore from snapshot.

## What the rule should be

**Never call remove/deactivate against production instances.** Never call remove
against *any* built-in pak (those with `isUnremovable: true` in
`getIntegrations`). The `no-destructive-on-prod` rule exists because of exactly
this failure mode.

On test/lab instances: always check `isUnremovable` before calling remove. If
testing uninstall flows, use purpose-built test paks only.

## The scope-creep lesson

The original brief authorized install/uninstall testing against a specific non-
built-in reference pak. The investigator extended scope to probe `isUnremovable`
enforcement without first escalating — a process gap that produced a permanent
(within session) lab incident.

Lesson: destructive tests against built-in platform components require explicit
separate authorization, not implied extension of test scope.

## Reference files

- `context/pak_uninstall_api_exploration.md` — full uninstall investigation
- `context/pak_install_api_exploration.md` — install flow validation
- `rules/no-destructive-on-prod.md` — the rule this incident created
