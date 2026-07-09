# vCommunity guest-ops — Java port vs Python original, in-guest execution divergence

- **Date:** 2026-06-22
- **Mode:** DIAGNOSIS ONLY (read-only; no Java edited, no build, no install)
- **Adapter:** `content/sdk-adapters/vcommunity` (`vcfcf_vcommunity` build 1.0.0.9)
- **Original:** `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/`
- **Symptom:** all 3 Windows VMs pass the gate; `windows_service_list: 0 check(s)`,
  OsInfoRow null, zero service rows. No fault logged.

## Transport verdict — NOT a wrong-transport bug

Both implementations use the **same channel**: vim25 `GuestOperationsManager`
over the vCenter `/sdk` SOAP endpoint. The original (`vmService.py`,
`collect_windows_event_logs.py`) does exactly:
`CreateTemporaryDirectory` → `InitiateFileTransferToGuest` (HTTP PUT the `.ps1`)
→ `StartProgram` powershell → poll `ListProcessesInGuest` → `InitiateFileTransferFromGuest`
(HTTP GET CSV) → `DeleteDirectoryInGuest`. Ours mirrors this step-for-step.
**We did NOT copy a mechanism the original avoids.** No WinRM/SMB/agent/CSV-drop
in the original. Transport choice is correct; do not rip it out.

Eliminated as causes (parity confirmed):
- **Script bundling** — builder copies `profiles/` → `conf/profiles/` recursively
  (`sdk_builder.py:1006-1024`); loader reads `conf/profiles/scripts/*.ps1`
  (`VCommunityAdapter.java:164-179`). Scripts ship and load. `scripts.services != null`.
- **Session/cookie/URL** — guest-ops reuses the exact authenticated cookie + `/sdk`
  URL the working property collection uses (DATA_RECEIVING). Same cert, same session.
- **Transfer-URL host substitution** — neither side rewrites the returned URL;
  with vCenter as SOAP endpoint the URL targets vCenter (cert matches). Parity.
- **xsi:type bare-name form** — `<selectSet xsi:type="TraversalSpec">` works on this
  same vCenter (property collection succeeds), so bare type names are accepted.

## The observability defect (real, separate from root cause)

`GuestOpsClient.post()` (`GuestOpsClient.java:468`):
```java
if (code < 200 || code >= 300) return null;   // SILENT — no logging
```
The working `VCommunityVSphereClient.post()` (`:937-952`) extracts and logs the
SOAP `<faultstring>` on non-2xx. GuestOpsClient does NOT. A guest-ops fault comes
back as **HTTP 500 + SOAP fault body**; `post()` returns `null`, `createTempDir`/
`runPowershell` return null/false, the collector returns empty — and the
`catch (Exception)` block at `:168` **never fires** (nothing threw). So the
`logWarn("guest-ops services ... failed")` line recon was counting on to name the
fault **never executes**. The fault is swallowed one level deeper than recon
assumed. This is why there is zero signal. **This is the first thing to fix** —
not as the cure, but as the instrument: mirror the vSphereClient faultstring
extraction into `GuestOpsClient.post()` so the next collect cycle prints the exact
vim25 fault per VM. Without it we are guessing.

## Ranked root-cause candidates (the fault itself)

The earliest-failing shared primitive bounds where it breaks. `createTempDir` uses
only `<auth>` + scalar elements and is structurally valid (auth element order
`interactiveSession, username, password` matches the `GuestAuthentication` →
`NamePasswordAuthentication` schema extension; xsi:type present and required there).
So createTempDir most likely *succeeds* and the break is at the PUT or StartProgram.

1. **(HIGHEST) Domain credential format / guest-ops privilege — `vcf@int.sentania.net`.**
   `auth()` sends `username=<winUser>` verbatim (`GuestOpsClient.java:427`) with
   `interactiveSession=false`. The fault is **identical across in-guest account
   tiers** (Administrator on automic, Server Operator on dcint1/2), which points
   *away* from a Windows-ACL/privilege-level cause and *toward* a credential the
   guest-ops layer rejects uniformly — i.e. a format/identity mismatch at the
   vCenter→guest auth boundary, faulting at the FIRST authenticated guest call
   (`CreateTemporaryDirectoryInGuest` → `InvalidGuestLogin` / `GuestPermissionDenied`).
   **Caveat that lowers confidence:** the original authenticates with the *same*
   `vcf@int.sentania.net` against the *same* dcint1/dcint2 for event logs and it
   WORKS. So a pure UPN-rejection theory must explain why pyVmomi's identical
   `NamePasswordAuthentication(username=winUser)` succeeds where ours faults — which
   means if it is auth, the difference is in **how the value is delivered on the
   wire**, not the value. Candidate wire differences vs pyVmomi:
   - **`<password>` XML escaping / character handling.** `auth()` runs the password
     through `xmlEscape` (`:428`). If the live password contains a character that
     our escaper mangles vs pyVmomi's serializer (e.g. a literal that needs CDATA,
     or a trailing/leading whitespace the SDK trims and we do not), the guest sees
     a wrong password → uniform `InvalidGuestLogin` across all VMs/accounts. This
     fits the evidence better than UPN-vs-NetBIOS, because it is a *delivery* bug,
     not a *value* bug, and so explains why the same account works in the original.
   - **NOT confirmable statically** — needs the faultstring (see instrument above)
     or the exact live password characters (do not log the secret).

2. **(MEDIUM) `StartProgramInGuest` `<spec>` missing xsi:type.** `runPowershell`
   (`:358-361`) emits `<spec><programPath>…</programPath><arguments>…</arguments></spec>`
   with **no** `xsi:type="GuestProgramSpec"`. The declared parameter type is the
   concrete `GuestProgramSpec`, so vCenter *should* default it — but some vim25
   binding versions (7/8/9 drift) reject a typeless `<spec>` for guest-process with
   a deserialization fault. If createTempDir+PUT succeed but StartProgram faults,
   this is the spot. Mitigation if confirmed: add `xsi:type="GuestProgramSpec"`.
   Lower than auth because (a) typeless concrete specs usually deserialize and
   (b) it would not explain OsInfo/Services failing *before* any process visibly
   runs unless the fault is at StartProgram specifically.

3. **(MEDIUM-LOW) Empty `<fileAttributes></fileAttributes>` on PUT.** `putFile`
   (`:319`) sends an empty, typeless `<fileAttributes/>`. pyVmomi sends a typed
   `GuestFileAttributes` (or, on Windows, the platform may expect
   `GuestWindowsFileAttributes`). If the PUT faults, the script never lands, the
   later GET returns nothing → empty CSV → zero rows, **and** the
   `InitiateFileTransferToGuest` fault would be the HTTP-500 swallowed at `:468`.
   This is a clean "silent zero rows" path. Confidence held down only because an
   empty base-typed FileAttributes is generally accepted; bump it up if the
   faultstring shows a file-attributes deserialization error.

4. **(LOW) Argument quoting.** Ours produces `-Command "& '…' …"`; the original
   produces `-Command ""& '…' …""` (double-quote-wrapped command). Ours is the
   *more* correct PowerShell; unlikely to zero-row, and would yield a non-zero
   exit code rather than a SOAP fault. Not the cause.

## Single most-likely cause

**A wire-level auth-delivery mismatch in `auth()` (candidate 1) faulting at the
first authenticated guest call**, given that (a) the failure is uniform across
account privilege tiers, (b) it is uniform across all three collectors (shared
primitive), and (c) the original succeeds with the *same account/context*, which
forces the divergence to be in HOW our Java serializes the credential rather than
the credential value. The `<password>` `xmlEscape` path and the absence of any
domain handling are the concrete lines to scrutinize: `GuestOpsClient.java:423-430`.

## Confirming runtime signal (still needed)

The decisive datum is the SOAP `<faultstring>` from the first failing guest call.
After fixing the `post()` silent-null (candidate-0 instrument), the next collect
will log one of:
- `InvalidGuestLogin` / `GuestPermissionDenied` on `CreateTemporaryDirectoryInGuest`
  → confirms **auth** (candidate 1). Then compare wire username/password bytes.
- a deserialization / `RequestCanceled` on `StartProgramInGuest` → candidate 2 (spec xsi:type).
- a fault on `InitiateFileTransferToGuest` → candidate 3 (fileAttributes).
- HTTP 200 + a non-zero powershell exit → candidate 4 (script/arg), NOT a transport bug.

## Precise fix I would make (DO NOT apply yet)

1. **Instrument first (zero behavior risk):** port the `<faultstring>` extraction
   from `VCommunityVSphereClient.post()` into `GuestOpsClient.post()` so non-2xx
   logs the vim25 fault per VM (and optionally surface the last fault as
   `Summary|guestops_last_error` on the world anchor, API-readable). This converts
   the next single collect into ground truth without appliance-log access.
2. **Then** apply the fix the faultstring names — most likely the `auth()`
   credential-delivery correction; secondarily `xsi:type="GuestProgramSpec"` on
   `<spec>` and a typed `<fileAttributes>`.

Do not change the transport. It matches the original and is correct.
