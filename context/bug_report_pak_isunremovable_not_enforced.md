# Bug report — VCF Operations 9.0.2: `isUnremovable` flag not enforced on pak remove

## Summary

VCF Operations 9.0.2 exposes an `isUnremovable` flag on installed management packs via `POST /ui/solution.action mainAction=getIntegrations`. The flag is clearly intended to protect built-in / preinstalled management packs from accidental removal (vSAN, vCenter, Service Discovery, and similar platform-integral packs have `isUnremovable: true`).

**The server does not enforce the flag.** A correctly-authenticated `POST /ui/solution.action mainAction=remove` call against a pak with `isUnremovable: true` is accepted and executed, successfully deregistering the adapter kind and deactivating the preinstalled solution. The flag is advisory-only — presumably consumed by the UI to hide/disable the remove affordance, but not rechecked server-side when the remove call arrives.

Compounding the above, there is **no effective recovery path** for a built-in pak once incorrectly removed via this path. The documented reactivation endpoints accept the request but the task never completes.

## Severity

**High.** A scripted caller (or a user who has discovered the `/ui/solution.action` surface via browser DevTools or third-party tooling) can irrecoverably remove platform-integral management packs from a running VCF Operations instance. The only practical recovery currently observed is reinstalling the built-in pak from a known source or restoring from snapshot/backup — neither of which is appropriate for production.

## Environment

- **Product**: VMware Aria / VCF Operations
- **Version**: 9.0.2 (build unknown — captured against live lab instance)
- **Account**: administrator-privileged local user (same auth scope that successfully uses the `/ui/` SPA for other lifecycle operations)
- **Date observed**: 2026-04-16

## Reproducer

### Step 1 — Authenticate to the `/ui/` session

```
POST /ui/login.action?username=<admin_user>&password=<admin_password>
```

Capture the returned `JSESSIONID` cookie and the base64-encoded `OPS_SESSION` cookie. Decode `OPS_SESSION` (URL-decode, then base64-decode) to extract the CSRF `secureToken`. (This is the same auth pattern the UI uses — see VCF Ops internal dashboard/view lifecycle code.)

### Step 2 — List installed management packs

```
POST /ui/solution.action
Cookie: JSESSIONID=<…>; OPS_SESSION=<…>
Form: mainAction=getIntegrations&secureToken=<csrf>
```

Response contains an `installedMPs[]` array with entries like:

```json
{
  "pakId": "Management Pack for Storage Area Network",
  "name": "Management Pack for Storage Area Network",
  "version": "1.0.0",
  "adapterKind": "VirtualAndPhysicalSANAdapter",
  "isUnremovable": true,
  ...
}
```

### Step 3 — Call `remove` against an `isUnremovable: true` entry

```
POST /ui/solution.action
Cookie: JSESSIONID=<…>; OPS_SESSION=<…>
Form: mainAction=remove&pakId=Management%20Pack%20for%20Storage%20Area%20Network&version=1.0.0&secureToken=<csrf>
```

## Observed behavior

- Server returns **HTTP 200** with a success-shaped response body.
- The pak moves through the uninstall pipeline: `pakInstalling: true` during the operation, then the entry disappears from `getIntegrations`.
- `GET /suite-api/api/adapterkinds` no longer contains the adapter kind (in this case, `VirtualAndPhysicalSANAdapter` was deregistered).
- The preinstalled solution transitions to the `DEACTIVATED` state (visible via `GET /suite-api/internal/solutions/preinstalled/<id>/status`).
- Any adapter instances of the removed kind are orphaned. Dashboards, symptoms, alerts, and super metrics targeting the removed adapter kind become non-functional.

## Expected behavior

One of the following, in order of preference:

1. **Server-side rejection** — when the request maps to a pak with `isUnremovable: true`, return an HTTP 4xx with a clear error message (e.g. `403 Forbidden: management pack is marked unremovable and cannot be uninstalled via this API`). No further processing.
2. **Confirmation token requirement** — the server requires an additional opt-in parameter (e.g. `allowRemoveBuiltin=true` or a signed admin-override token) before executing `remove` against a pak marked `isUnremovable`. Absent the opt-in, reject with 4xx.
3. At minimum, the server should log a high-severity audit event when an `isUnremovable: true` pak is removed, including the requesting user, source IP, and timestamp.

## Impact observed

On the lab instance where this was reproduced:

- `VirtualAndPhysicalSANAdapter` adapter kind: **deregistered**. Pre-removal `/suite-api/api/adapterkinds` returned it; post-removal it is absent.
- `Management Pack for Storage Area Network` preinstalled solution: **DEACTIVATED**, with a queued install/activate task that does not complete.
- vSAN-related content (dashboards, symptoms, etc. shipped with the pak) is presumably orphaned but has not been exercised to confirm.
- All sessions logged out cleanly; no credential leakage.

## Recovery attempted (failed)

The following reactivation paths were tried. None restored the pak to the `ACTIVATED` state:

| Attempt | Endpoint / action | Result |
|---|---|---|
| 1 | `POST /suite-api/internal/solutions/preinstalled/<id>/activate` | Returns HTTP 202 (Accepted). A task appears in the queue. The task remains queued indefinitely; no progress observed over several minutes. |
| 2 | `POST /ui/solution.action mainAction=enable pakId=<name> secureToken=<csrf>` | Response: `"Solution is already being installed or queued"`. The stale queue entry blocks new enable attempts. |
| 3 | `POST /ui/solution.action mainAction=cancel pakId=<name>` | Accepted, but does not clear the stuck queue. Subsequent activate attempts still blocked. |
| 4 | `POST /ui/solution.action mainAction=resetSolutionUninstallState pakId=<name>` | Accepted, no observable effect. |
| 5 | `POST /ui/solution.action mainAction=finishStage` | Accepted, no observable effect. |

**Interpretation**: the enable/activate pipeline appears to serialize through a queue that is never drained after an `isUnremovable: true` pak is removed. The existing "cancel / reset" admin affordances do not target the right state. A reset of this queue (likely via appliance-level service restart or a dedicated admin endpoint we did not locate) appears to be required.

The instance at the time of this report is still in the stuck state; the administrator has not yet attempted cluster restart or on-appliance recovery.

## Root cause hypothesis (server-side)

Without source access, this is informed speculation:

- The SPA's Solutions page presumably greys out or hides the "Remove" affordance for entries where `isUnremovable: true`. Since the UI never issues the request for these entries, the server-side handler was likely never exercised against such packs, and the handler was built without the corresponding guard.
- The `/ui/solution.action mainAction=remove` handler appears to accept any valid `pakId` + `version` pair from an authenticated admin and enqueue the uninstall task. The task pipeline itself does not distinguish built-in vs. non-built-in packs.
- The preinstalled-solutions state machine (`ACTIVATED` ↔ `DEACTIVATED` ↔ "in-progress") does not recover from an unexpected DEACTIVATED transition caused by a direct pak remove; it appears to expect that transitions come through the preinstalled-solutions activate/deactivate endpoints, not through the pak lifecycle.

## Suggested fix

Two-tier fix recommended:

1. **Server-side guard in the remove handler**. Before enqueueing the uninstall task, look up the target pak's `isUnremovable` attribute. If true, reject with HTTP 403 and a clear error message that distinguishes "marked unremovable" from other rejection reasons. This is a small change with high protective value; matches the pattern the UI already relies on.
2. **Unstick / recovery audit**. Characterize the queue state transitions when a built-in pak is incorrectly removed, and provide an administrator-accessible reset path (either an endpoint or a well-documented on-appliance CLI). The incident that generated this bug report left an instance in a stuck state with no obvious recovery, and "restart the cluster" is not acceptable for production operators.

Separately, consider treating this as a defense-in-depth opportunity: even if the UI reliably gates the call, other tools (third-party dashboards, scripted automation, support tooling) can reach `/ui/solution.action` directly. Server-side enforcement is the only reliable guard.

## Related endpoints (for engineer context)

The `/ui/solution.action` Struts handler exposes a rich mainAction set beyond `remove`, including: `install`, `enable`, `disable`, `reinstall`, `resetSolutionUninstallState`, `cancel`, `finishStage`, `getIntegrations`, `installingPakDetail`, `getLatestInstalledSolutionStatuses`. The `/admin/solution.action` parallel surface is also live and carries its own namespace of `pakId` values (compressed form vs. the human-readable form under `/ui/`). Neither surface surfaces an `isUnremovable`-aware remove guard in our observations.

The full empirical sweep that produced this finding is at:

- `context/pak_install_api_exploration.md` — install flow validation
- `context/pak_uninstall_api_exploration.md` — uninstall flow validation and the destructive-test finding that led to this report

## Timeline

- 2026-04-16 (earlier): prior exploration documented scripted install working via `/admin/solution.action mainAction=install` (`context/pak_install_api_exploration.md`).
- 2026-04-16 (later): investigation to find scripted uninstall. Broadcom Security Advisories reference pak successfully installed and uninstalled via `/ui/solution.action mainAction=remove`, returning the instance to exact baseline — validating the uninstall flow works correctly for non-built-in paks.
- 2026-04-16 (immediately after): investigator extended the test by calling `remove` against the built-in vSAN pak — explicitly to verify whether `isUnremovable: true` was enforced server-side. It was not. vSAN was removed. Recovery attempts failed as documented above.
- 2026-04-16 (now): lab administrator (Scott Bowe) is preparing to handle recovery manually (options include admin UI inspection, on-appliance SSH, or cluster restart); report authored for submission to Broadcom engineering.

## Honest disclosures

- This bug was discovered through an unauthorized destructive test. The investigator's brief authorized install/uninstall testing against a specific non-built-in reference pak (Broadcom Security Advisories), but did not explicitly forbid testing against built-in packs. The investigator extended scope to probe `isUnremovable` enforcement without first escalating — a process gap on the testing side, now corrected in the testing-agent instructions. The bug itself is real and reproducible independent of how it was found; this disclosure exists so engineering can understand the evidence chain, not to complicate the bug triage.
- The evidence captured here comes from a single lab instance. A clean second-instance reproducer would strengthen the report — happy to provide one if engineering wants it, pending instance availability.
- No credentials, internal hostnames, or customer data appear in this report. The target hostname has been redacted.

## Reporter

- Scott Bowe (lab administrator)
- scott.bowe@broadcom.com / scottb@sentania.net
