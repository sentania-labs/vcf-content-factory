# vCommunity Windows Services collection returns zero rows — diagnosis

**Date:** 2026-06-23
**Adapter:** `vcfcf_vcommunity` build 11 (devel)
**Mode:** DIAGNOSIS ONLY — no source edited, no build, no install.
**Author:** `sdk-adapter-author`

## Scope

Why does the Windows guest-ops **Services** collector produce zero
`vCommunity|Guest OS|Services:*` keys on all 3 VMs while the **OsInfo**
collector — running over the *same* guest-ops session in the same
per-VM block — succeeds? Service names (`DHCPServer`, `NTDS`) are
confirmed valid (DHCP role installed, DC), the SOAP session works, and
all 3 VMs report `Collection Status = DEGRADED`, `guestops_last_error =
'none'`, no `Services:*` keys (neither name present).

## Files examined (all absolute)

- `/home/scott/claude/vcf-content-factory/content/sdk-adapters/vcommunity/src/com/vcfcf/adapters/vcommunity/GuestOpsClient.java`
- `/home/scott/claude/vcf-content-factory/content/sdk-adapters/vcommunity/src/com/vcfcf/adapters/vcommunity/VmCollector.java`
- `/home/scott/claude/vcf-content-factory/content/sdk-adapters/vcommunity/profiles/scripts/getWindowsServices.ps1`
- `/home/scott/claude/vcf-content-factory/content/sdk-adapters/vcommunity/profiles/scripts/getWindowsOSInformation.ps1`
- `/home/scott/claude/vcf-content-factory/references/vmbro_vcf_operations_vcommunity/Management Pack/app/properties/vm/vmService.py`
- `/home/scott/claude/vcf-content-factory/references/vmbro_vcf_operations_vcommunity/Management Pack/app/properties/vm/vmOSInformation.py`

## The execution paths diff cleanly — the divergence is narrow

The Services and OsInfo paths in `GuestOpsClient` are step-for-step
identical (createTempDir → putFile → runPowershell → getFile →
parseCsv) and share the SAME transport (`post`, `httpPut`, `httpGet`),
the SAME `parseCsv`, and the SAME `idx`/header-lookup helpers. Since
OsInfo works, every shared primitive is proven good on these guests:
the SOAP session, the file PUT/GET, `StartProgramInGuest`, the
`ListProcessesInGuest` exit-code poll, `parseCsv`, and `-Command "..."`
wrapping in `<arguments>`.

That eliminates a whole class of theories. Only **three** things differ
between the two paths:

1. The Services command carries a positional **array argument**
   `@('DHCPServer', 'NTDS')`; OsInfo takes no argument.
2. The Services script pipes **`Get-Service | Select-Object`**
   (`System.ServiceProcess.ServiceController` objects); OsInfo pipes a
   hand-built **`[PSCustomObject]`** with fixed property names.
3. Consequently the expected CSV **header** differs: Services parser
   hard-requires all four of `Name, DisplayName, Status, StartType`
   (`GuestOpsClient.java:188-192`); OsInfo tolerates missing columns
   (each `idx` independently, no all-or-nothing gate).

The root cause must live in one of those three. Ranked below.

---

## Hypothesis ranking

### #1 (PRIME) — `StartType` column absent from the CSV → hard header gate returns empty

`GuestOpsClient.java:188-192`:
```java
int ni = idx(header, "Name");
int di = idx(header, "DisplayName");
int si = idx(header, "Status");
int ti = idx(header, "StartType");
if (ni < 0 || di < 0 || si < 0 || ti < 0) return out;   // ALL-OR-NOTHING
```

The script (`getWindowsServices.ps1:10-11`) does
`Get-Service -Name $service | Select-Object Name, DisplayName, Status,
StartType`. `Get-Service` returns `System.ServiceProcess.ServiceController`
objects. **`StartType` is NOT a native property of `ServiceController`
on Windows PowerShell 4.0 / .NET < 4.6.1** — it was added to the type in
PowerShell 5.0 (WMF 5.x). On a guest running stock PowerShell 4.0
(Server 2012 R2 baseline, common on older DCs), `Select-Object … StartType`
silently yields a **null/absent** column. `Export-Csv -NoTypeInformation`
on such objects can then emit a header **without** a `StartType` field
(Export-Csv derives columns from the union of present `NoteProperty`s;
a property that never materialized is not emitted). With `ti < 0`, the
parser hits line 192 and returns **empty for the whole batch** — exactly
the observed symptom: BOTH names absent, not a per-name skip.

This is the single best fit because it is the *only* difference that (a)
zeroes the entire batch at once rather than per-name, (b) leaves the CSV
non-empty (so the `csv.trim().isEmpty()` early-out at line 183 does NOT
fire and no fault is raised — consistent with `guestops_last_error =
'none'`), and (c) does not exist on the OsInfo path (whose
`[PSCustomObject]` always emits all six named columns regardless of PS
version).

**Why the original Python "works" here but Java doesn't:** the original
parser (`vmService.py:148-152`) does `header.index('"Name"')` etc., which
also requires `StartType` — BUT (i) the original's proven-working
deployments may run PowerShell 5.x where the column exists, and (ii) the
original raises an *uncaught* `ValueError` from `.index()` if a column is
missing, which propagates to the `except` at `vmService.py:169` and is
*logged*, not silently swallowed. Our Java converts the same missing
column into a clean empty-return with no error. So this hypothesis also
predicts the original would fail identically on a PS 4.0 guest — it is
not "Java-only," it is "PS-version-dependent, and Java hides it harder."

- **Status: STATICALLY CONFIRMABLE that the gate is all-or-nothing and
  that `StartType` is the fragile column. NOT statically confirmable
  that this guest's PowerShell omits it — needs the raw CSV header
  bytes from the guest** (PS version on dcint1/dcint2).
- Evidence: `GuestOpsClient.java:188-192` (hard gate);
  `getWindowsServices.ps1:11` (`StartType` in Select-Object);
  contrast OsInfo `getWindowsOSInformation.ps1:6-13` (PSCustomObject,
  version-independent columns).

### #2 (PLAUSIBLE) — script emits no CSV rows / wrong stream → empty but non-faulting

Two sub-variants:

- **2a. `return $output` with `Write-Host` noise.** The script writes
  "Service not found" / "Error retrieving service" via `Write-Host`
  (`getWindowsServices.ps1:15,19`). `Write-Host` goes to the *information*
  stream, NOT stdout, so it does NOT pollute the `Export-Csv` pipeline —
  good. But if `Get-Service -Name DHCPServer` errors (e.g. name actually
  unresolved despite the role being present — service short name could be
  `Dhcp`/`DHCPServer` ambiguity), `-ErrorAction SilentlyContinue` swallows
  it and `$svc` is `$null`, so nothing is appended. If *both* names fail
  to resolve, `$output` is empty → `Export-Csv` of an empty array writes
  an **empty file** → `getFile` returns it → line 183
  `csv.trim().isEmpty()` returns empty list, `degraded=true`, no fault.
  This ALSO matches the symptom.

  However, Scott confirmed the DHCP role is installed and `NTDS` is
  expected on a DC, so at least one name *should* resolve — which argues
  against full-empty-output unless the short names are wrong (`DHCPServer`
  vs `Dhcp`; the AD DS service is `NTDS` only on a DC, correct). This is
  why #2a ranks below #1: #1 explains zero rows *even when the services
  resolve fine*.

- **2b. Double-`@()` wrap differs from Python.** Python passes
  `@(@('DHCPServer','NTDS'))` (double-wrapped, `vmService.py:139-140`);
  Java passes `@('DHCPServer','NTDS')` (single, `GuestOpsClient.java:171-177`).
  Both flatten identically in PowerShell to a `[string[]]` of two
  elements, so this is NOT a functional difference. Ruled out as a cause;
  noted only to forestall a red herring.

- **Status: NOT statically confirmable — needs the raw CSV bytes AND/OR
  the in-guest `Get-Service -Name DHCPServer` result.**
- Evidence: `getWindowsServices.ps1:8-21`, `GuestOpsClient.java:183`.

### #3 (UNLIKELY here, but a real instrumentation gap) — swallowed services-specific fault

Build-10 fault surfacing IS wired into the shared `post()`
(`GuestOpsClient.java:500-522`), so it covers `CreateTemporaryDirectory`,
`InitiateFileTransferTo/FromGuest`, `StartProgramInGuest`,
`ListProcessesInGuest`, `DeleteDirectory` — i.e. **all SOAP calls on BOTH
the Services and OsInfo paths.** A SOAP fault on the services batch WOULD
be captured in `lastFault` and surfaced.

BUT there are TWO silent-empty exits on the services path that are NOT
SOAP faults and therefore record NOTHING in `guestops_last_error`:
- `httpPut`/`httpGet` returning a non-2xx **HTTP transfer** code
  (`GuestOpsClient.java:587, 597`) — returns false/null with no fault
  capture (these are the file-transfer URLs, not the SOAP endpoint).
- The `csv == null || csv.trim().isEmpty()` early-out (line 183) and the
  header-gate early-out (line 192) — both `return out` with no fault.

So `guestops_last_error = 'none'` does NOT imply "no problem"; it only
implies "no SOAP fault on the wire." It is fully consistent with #1 and
#2, which both exit through a non-faulting `return out`. This is an
**observability gap**, not the root cause: the adapter cannot currently
distinguish "CSV parsed, zero rows" from "CSV had an unexpected header"
from "GET returned 500."

- **Status: STATICALLY CONFIRMED that header-gate / empty-CSV exits emit
  no fault, hence `'none'` is expected under #1/#2.**
- Evidence: `GuestOpsClient.java:183, 192` (silent returns);
  `:500-522` (fault capture only on the SOAP `post`, not the early-outs).

### #4 — DEGRADED logic: empty alone trips it; DEGRADED does NOT imply a fault

`VmCollector.java:333-335`: `if (rows.isEmpty()) { degraded = true; }`.
DEGRADED is set whenever the services collector returns **zero rows**,
with or without any fault. `VmCollector.java:406-411` then writes
`Collection Status = DEGRADED`. So the observed `DEGRADED` +
`guestops_last_error='none'` is precisely "services returned 0 rows and
nothing faulted" — it tells us the batch came back empty cleanly, which
points at #1/#2, NOT at a transport/auth fault.

- **Status: STATICALLY CONFIRMED.**
- Evidence: `VmCollector.java:333-335, 406-411`.

---

## (a) Single most-likely root cause

**Hypothesis #1: the `StartType` column is absent from the guest's
`Get-Service | Export-Csv` output (PowerShell 4.0 / pre-5.0
`ServiceController` has no `StartType` property), so the Java parser's
all-or-nothing header gate (`GuestOpsClient.java:192`) discards the
entire batch and returns empty.** This uniquely explains zero rows for
BOTH names simultaneously, a non-empty CSV, no SOAP fault, and the
DEGRADED+`'none'` combination — and it is the one column the OsInfo path
(version-independent `[PSCustomObject]`) never depends on.

Second most likely is #2a (services genuinely resolve to nothing because
the configured short names don't match the guest's service registry),
but Scott's confirmation that the DHCP role is installed makes a *total*
empty less likely than a parse-side drop.

## (b) Precise fix I would make (NOT applied)

Two-part, smallest-footprint:

1. **Make the script emit a stable, version-independent CSV shape**, the
   way OsInfo already does. Replace the `Get-Service | Select-Object`
   with an explicit `[PSCustomObject]` projection that computes
   `StartType` defensively, e.g. per service build
   `@{ Name=$svc.Name; DisplayName=$svc.DisplayName;
   Status=$svc.Status; StartType = (Get-CimInstance Win32_Service
   -Filter "Name='$($svc.Name)'").StartMode }` (or guard
   `$svc.StartType` with a null-coalesce to `'Unknown'`). This
   guarantees all four columns regardless of PowerShell version —
   exactly why OsInfo is robust. (`getWindowsServices.ps1`.)

2. **Soften the parser's all-or-nothing gate** so a missing OPTIONAL
   column (`StartType`) degrades that one field to empty/`"Unknown"`
   rather than discarding the whole batch — but keep the hard
   requirement on the identity columns (`Name`, `DisplayName`). Per the
   cardinal rule this must NOT invent a value: a missing `StartType`
   becomes an explicit empty/unreadable marker on that one property,
   the row still emits, and the batch is not silently zeroed.
   (`GuestOpsClient.java:188-197`.)

3. **(Observability, optional but recommended)** when the CSV is
   non-empty but the header gate would have failed, capture a
   non-secret diagnostic (the actual header line) into `lastFault`/a
   new `guestops_last_error` channel so `'none'` stops masking a
   header-shape mismatch. This closes the #3 gap so the next
   occurrence is self-describing without SSH.

I would NOT touch transport, the session, the gate predicate, or the
OsInfo path.

## (c) The one decisive runtime datum + cheapest way to get it

**Decisive datum: the raw bytes of `C:\Windows\Temp\…-Services-TEMP\Services.csv`
on dcint1 — specifically its header line.** That single line discriminates
all live hypotheses:

- Header `"Name","DisplayName","Status","StartType"` present **with data
  rows** → parser bug elsewhere (re-examine `parseCsv`/`idx` trimming of
  quoted headers) — but note OsInfo proves `parseCsv` works, so this is
  improbable.
- Header present but **missing the `StartType` column** (e.g.
  `"Name","DisplayName","Status"`) → **confirms #1.**
- **Empty file / no rows under a valid header** → confirms #2a (services
  not resolving) — then check `Get-Service -Name DHCPServer` directly.

Cheapest acquisition (Scott has SSH, we don't): on the guest, run the
exact pipeline by hand and dump the header:
```
powershell -Command "& 'C:\path\getWindowsServices.ps1' @('DHCPServer','NTDS') | Export-Csv -Path C:\Temp\s.csv -NoTypeInformation -Encoding UTF8; Get-Content C:\Temp\s.csv"
```
and separately `$PSVersionTable.PSVersion`. That is one SSH session, no
adapter rebuild, no install cycle.

### Does the `Dnscache` single-service isolation test discriminate #1 vs #2/role?

**Partially — and usefully.** `Dnscache` exists on EVERY Windows host
(no role required) and its `ServiceController.StartType` has the SAME
version-dependency as any other service. So:

- If a `Dnscache`-only run **still returns zero rows** → the failure is
  NOT name/role-specific (Dnscache always resolves) → it is the
  **parse/CSV-shape path (#1)**. Strong confirmation of #1, and it rules
  out #2a/role entirely.
- If a `Dnscache`-only run **returns a row** → the CSV shape is fine on
  this guest (header has all four columns) → #1 is FALSE, and the
  `DHCPServer`/`NTDS` emptiness is a **name-resolution/role issue (#2a)**
  after all.

So the `Dnscache` test cleanly separates "Java-side parse/shape bug
(#1)" from "the configured names don't resolve (#2a)." It does NOT, by
itself, distinguish #1 from a hypothetical generic parser bug — but
OsInfo already exonerates the shared parser, so in practice a zero-row
`Dnscache` result points squarely at the `StartType`-column gate.
**Recommended as the first runtime test**, ideally captured together
with `Get-Content` of the resulting CSV header (which then also confirms
the exact mechanism, not just the location).

## Net

- Root cause (most likely): version-fragile `StartType` column dropped
  from the guest CSV → hard header gate at `GuestOpsClient.java:192`
  zeroes the whole batch. Static analysis confirms the *mechanism is
  possible and uniquely fits*; one CSV-header byte-grab (or the
  `Dnscache` isolation run) confirms it.
- `guestops_last_error='none'` is expected and not reassuring: the
  empty-CSV and header-gate exits emit no fault by construction
  (`GuestOpsClient.java:183, 192`). That is the #3 observability gap to
  close alongside the fix.
- DEGRADED here means only "services returned 0 rows," not "a fault
  occurred" (`VmCollector.java:333-335`).

No source changed. Returned for review; fix proposed but not applied.
