# esxcli over vim25 SOAP — ReflectManagedMethodExecuter spike

**Date:** 2026-06-03
**Analyst:** api-explorer
**Target:** devel **mgmt** vCenter `vcf-lab-vcenter-mgmt.int.sentania.net`
(vCenter Server **9.1.0** build 25370922, instanceUuid
`4ff53df1-d47a-4fb9-b6f8-b96c6ce8ae8e`) and host
`vcf-lab-mgmt-esx03.int.sentania.net` (ESXi **9.1.0** build 25370933,
`host-6011`).
**Goal:** Prove esxcli is reachable over the vSphere Web Services SOAP
API (the `Get-EsxCli` mechanism) and decide whether the compliance
adapter's Java/JAX-WS vim25 stack can emulate it.
**Proof target:** invoke esxcli `system syslog config get` and read back
`LocalLogOutput` + `LocalLogOutputIsPersistent`.

> ⚠️ **Unsupported / internal API.** Everything below uses
> `InternalDynamicTypeManager`, `ReflectManagedMethodExecuter`, and the
> `vim.EsxCLI.*` dynamic managed types. These are NOT in the public
> vim25 WSDL and are not covered by API-compatibility guarantees. They
> are the same surface PowerCLI's private bindings use. Treat as
> internal: no `X-Ops-API` header is involved (this is vCenter/ESXi
> SOAP, not the Ops Suite API), but the stability caveat is the same
> class of risk as an Ops unsupported endpoint — pin versions, expect
> drift across releases.

---

## Verdict (CORRECTED 2026-06-03): **GO via vCenter session — no host credentials**

> ⚠️ **The "host-direct only / vCenter refuses to proxy" verdict below
> (and everything in §§1-5 that flows from it, plus the two ticket
> probes) is WRONG and is superseded.** It was caused by a malformed
> `ExecuteSoap` call — the wrong `version` string and the executer's own
> MoRef used as the `moid` — not by any platform limitation. See the new
> **§0 — Corrected verdict & working encoding** immediately below. The
> old sections are retained (annotated `SUPERSEDED`) for the audit trail
> only; do not act on them.

esxcli executes over a **vCenter-only** SOAP session. The user proved it
empirically from a PowerCLI connection bound to the mgmt vCenter as
`administrator@vsphere.local` with **no host login and no host
credentials** — `(Get-EsxCli -VMHost … -V2).system.syslog.config.get.Invoke()`
returned the full syslog struct including `LocalLogOutputIsPersistent=true`.
PowerCLI uses no host ticket: it invokes the host's
`ReflectManagedMethodExecuter` over the *vCenter* session and vCenter
relays it to the host on its own `vpxuser` management channel.

The authoritative open-source reference is **govmomi**'s esxcli flow
(`govc host.esxcli`). Its `esx.NewExecutor(ctx, c, host)` takes the
**vCenter** `*vim25.Client` `c` and the target host *MoRef* — it never
opens a connection to the host. `RetrieveManagedMethodExecuter`,
`RetrieveDynamicTypeManager`, and every `ExecuteSoap` ride that one
vCenter client. esxcli over a vCenter session is vCenter-only **by
construction** in VMware's own SDK. This alone refutes the old verdict.

The compliance adapter's existing **vCenter-only** `VSphereClient` is
therefore sufficient. No new host-credential field, no per-host SOAP
fan-out, no clone-ticket / generic-service-ticket avenue (those were
chasing the wrong mechanism — ignore them). An `esxcli:` reader is a
clean **GO** built on the session the adapter already has.

---

## 0. Corrected verdict & working ExecuteSoap encoding

### 0.1 Why the prior `NotSupported` was a malformed call

The old §1 sent, against the executer:

| field | prior (WRONG) | correct (per govmomi) |
|---|---|---|
| `_this` | `ManagedMethodExecuter-<n>` ✓ | `ManagedMethodExecuter-<n>` ✓ (the executer MoRef — this part was right) |
| `moid` | **omitted / set to the executer** ✗ | **`ha-cli-handler-<ns-with-dashes>`** — the *target esxcli handler* MoRef, e.g. `ha-cli-handler-system-syslog-config` |
| `version` | `urn:vim25/8.0.2.0`, `urn:vim25`, `/7.0.0.0`, `/6.7`, `/6.5` ✗ | **`urn:vim25/5.0`** — the only version govmomi ever sends; the reflect/esxcli dynamic types live in `vim.version.version5` |
| `method` | `VimEsxCLIsystemsyslogconfigget` (WSDL name) ✗ | **`vim.EsxCLI.system.syslog.config.get`** (dotted FQN) |
| `argument` | various inner-envelope shapes ✗ | list of `{<name>, <val>}` where `val` is *inner-XML fragments*; **empty for a no-arg `get`** |

The prior spike never tried `version=urn:vim25/5.0`, and used the
executer's own MoRef as the call target instead of supplying the esxcli
handler moid in the `moid` field. With the dotted method name it got
`InvalidArgument: method` *because the version was wrong* (the v5 dynamic
method isn't resolvable under v8/v7 namespaces); it then "fixed" that by
switching to the WSDL name, which the parameter validator accepts but the
executer can't dispatch → `NotSupported`. Both errors are encoding bugs.

### 0.2 The three-call sequence (all on the **vCenter** `/sdk`, one vCenter session)

All requests POST to `https://<vCenter>/sdk` with the vCenter
`vmware_soap_session` cookie from a normal `SessionManager.Login`. No
host connection at any step.

**Call 1 — get the per-host executer MoRef** (`HostSystem` method, not a
property):

```xml
<RetrieveManagedMethodExecuter xmlns="urn:vim25">
  <_this type="HostSystem">host-6011</_this>
</RetrieveManagedMethodExecuter>
```
→ `<returnval type="ReflectManagedMethodExecuter">ManagedMethodExecuter-6011</returnval>`
(suffix tracks the host moid; `host-6011` → `ManagedMethodExecuter-6011`).
Do this once per host per cycle and cache it.

**Call 2 — execute esxcli `system syslog config get`** via `ExecuteSoap`
on that executer. This is the call the prior spike got wrong; this is the
shape govmomi sends:

```xml
<ExecuteSoap xmlns="urn:vim25">
  <_this type="ReflectManagedMethodExecuter">ManagedMethodExecuter-6011</_this>
  <moid>ha-cli-handler-system-syslog-config</moid>
  <version>urn:vim25/5.0</version>
  <method>vim.EsxCLI.system.syslog.config.get</method>
</ExecuteSoap>
```
(`<argument>` is omitted for a no-arg `get`. For commands that take args,
each is `<argument><name>NAME</name><val>&lt;NAME&gt;VALUE&lt;/NAME&gt;</val></argument>`
— the `val` is the *XML-escaped inner element*, per govmomi's
`Command.Argument`.)

**Response** — `returnval` is a `ReflectManagedMethodExecuterSoapResult`
with either `<fault>` (esxcli-level error: `faultMsg`/`faultDetail`) or
`<response>` holding the **escaped inner XML** of the result object:

```xml
<ExecuteSoapResponse xmlns="urn:vim25">
 <returnval>
  <response>&lt;obj versionId="5.0" xsi:type="VimEsxCLIsystemsyslogconfiggetSyslogConfiguration"&gt;
    &lt;LocalLogOutput&gt;/scratch/log&lt;/LocalLogOutput&gt;
    &lt;LocalLogOutputIsConfigured&gt;false&lt;/LocalLogOutputIsConfigured&gt;
    &lt;LocalLogOutputIsPersistent&gt;true&lt;/LocalLogOutputIsPersistent&gt;
    &lt;LogLevel&gt;info&lt;/LogLevel&gt;
    &lt;RemoteHost&gt;tcp://…:514?…&lt;/RemoteHost&gt;
    …&lt;/obj&gt;</response>
 </returnval>
</ExecuteSoapResponse>
```

The consumer must (a) read `returnval/response` as text, (b) XML-unescape
it, (c) parse the resulting `<obj>` element. The proof-target fields
`LocalLogOutput` and `LocalLogOutputIsPersistent` are direct children of
`<obj>`.

### 0.3 Response shapes (`get` vs `list`)

The inner `<obj>` (govmomi sometimes calls it `root`) carries an
`xsi:type` that disambiguates:

- **`get`** → a single struct. `xsi:type="VimEsxCLI…<Result>"`, fields as
  direct child elements (PascalCase: `LocalLogOutputIsPersistent`).
- **`list`** → `xsi:type="ArrayOfDataObject"` containing repeated
  `<DataObject xsi:type="VimEsxCLI…">…</DataObject>` rows; each row's
  fields are child elements. (Confirmed by govmomi fixtures
  `network_vm_list.xml`, and the `system ssh server config list` shape the
  payoff table in §6 relies on.)
- **scalar** → `xsi:type` of `xsd:string` / `xsd:boolean` / `xsd:long`,
  value is the element text.

Field names in the inner XML are **PascalCase**, unlike vim25 properties
(camelCase). The recipe grammar must carry the exact PascalCase field
name. Reflection-tolerant parsing (missing field → UNREADABLE, never a
default) still applies.

### 0.4 Moid / method / version derivation (from govmomi `cli/esx/command.go`)

For an esxcli command whose name parts are `[p0 … pN]` (e.g.
`["system","syslog","config","get"]`):

```
namespace = p0 … p(N-1) joined by "."         e.g. system.syslog.config
moid      = "ha-cli-handler-" + (p0 … p(N-1) joined by "-")
                                              e.g. ha-cli-handler-system-syslog-config
method    = "vim.EsxCLI." + (p0 … pN joined by ".")
                                              e.g. vim.EsxCLI.system.syslog.config.get
version   = "urn:vim25/5.0"     (constant)
_this     = the host's ReflectManagedMethodExecuter MoRef (Call 1)
```

(Optional discovery of params/result fields is `ExecuteSoap` with
`moid=ha-dynamic-type-manager-local-cli-cliinfo`,
`method=vim.CLIInfo.FetchCLIInfo`, arg `typeName=vim.EsxCLI.<namespace>` —
also over the vCenter session. Not required to *read* a known command.)

### 0.5 Proposed `esxcli:` recipe recipe-style mechanics

```
esxcli:<namespace.command>:<ResultField>
```
- `<namespace.command>` (dotted) → `moid` and `method` by §0.4.
- `<ResultField>` is the PascalCase child of the inner `<obj>` for `get`.
- For `list`, a row-selecting variant pulls the named field per
  `<DataObject>` (e.g. SSH config rows).
- Bulk-read friendly: one `ExecuteSoap` per (host, namespace) per cycle is
  cached; many recipes against the same namespace cost one call.

Examples:
```
esxcli:system.syslog.config.get:LocalLogOutputIsPersistent   -> Boolean
esxcli:system.syslog.config.get:LocalLogOutput               -> String
esxcli:system.ssh.server.config.list:gatewayports            -> row value
```

### 0.6 Privilege requirement (vCenter-session privilege, NOT host creds)

This is a **vCenter-level** privilege on the *calling session*, since the
call rides the vCenter session and vCenter relays to the host as
`vpxuser`. Proven working as full `administrator@vsphere.local`. The
privilege that backs the executer dispatch is **`Host.Cim.CimInteraction`**
("Host > CIM > CIM interaction") on the target `HostSystem` — this is the
privilege PowerCLI/govmomi documents as required for `Get-EsxCli` /
`host.esxcli` over vCenter. A least-privilege service account needs that
privilege granted at vCenter on the host (or a containing folder/cluster),
**not** an ESXi root account.

> **NEEDS LIVE CONFIRMATION with a scoped account.** The compliance
> adapter's scoped service accounts (`WLD01` / `mgmt`) must be tested:
> grant `Host.Cim.CimInteraction` on the host(s) and re-run Call 2. Until
> then, treat "scoped account can execute esxcli" as *probable but
> unverified*. The full-admin path is proven.

### 0.7 Live confirmation status & the one command to capture the trace

I could **not** re-run the live `ExecuteSoap` myself this round: the only
vCenter access available was two cached `govc` SOAP sessions for
`vcf-lab-vcenter-mgmt`, both expired (`NotAuthenticated`), and no vCenter
password is stored in the repo (`.env` has only VCF Ops + Synology/UniFi
creds). The encoding above is therefore **derived verbatim from the
govmomi source** (the implementation PowerCLI-equivalent `Get-EsxCli`
mirrors) plus the user's empirical PowerCLI proof — not yet re-captured on
the wire by this agent.

To capture the exact live request/response (govc *is* the govmomi
reference; pointing `GOVC_URL` at the vCenter and running `host.esxcli`
proves the vCenter-only path and dumps the raw SOAP):

```bash
export GOVC_URL='administrator@vsphere.local:<PASSWORD>@vcf-lab-vcenter-mgmt.int.sentania.net'
export GOVC_INSECURE=1 GOVC_DEBUG=1 GOVC_DEBUG_PATH=/tmp/govc-esxcli-trace
govc host.esxcli -host vcf-lab-mgmt-esx01.int.sentania.net system syslog config get
# the raw ExecuteSoap request/response envelopes land in /tmp/govc-esxcli-trace/*.req.xml / *.res.xml
```

Expected: the command prints the syslog struct (incl.
`LocalLogOutputIsPersistent: true`) and the trace files show the §0.2
`ExecuteSoap` with `version=urn:vim25/5.0`, `moid=ha-cli-handler-system-syslog-config`,
`method=vim.EsxCLI.system.syslog.config.get`. (If a fresh govc session is
established in this repo, re-run and paste the trace here to upgrade this
section from "derived" to "wire-captured".)

---

## 1. Reachability through vCenter — the riskiest unknown, PINNED

> 🛑 **SUPERSEDED by §0.** The discovery findings here (the two
> `Retrieve*` methods, the `InternalDynamicTypeManager` working through
> vCenter) are correct and still useful. The **"execution does not
> proxy / `NotSupported`"** conclusion and the clone-ticket item are
> WRONG — see §0.1 for the malformed-call root cause.

### What IS reachable through vCenter

Connected to vCenter as `administrator@vsphere.local`, the per-host
executer / type-manager MoRefs are obtained via two **HostSystem
methods** (NOT properties — `configManager` does **not** expose them):

```
HostSystem.RetrieveManagedMethodExecuter()
  -> returnval type="ReflectManagedMethodExecuter"  value="ManagedMethodExecuter-6011"
HostSystem.RetrieveDynamicTypeManager()
  -> returnval type="InternalDynamicTypeManager"    value="DynamicTypeManager-6011"
```

(`-6011` is the host Moid suffix `host-6011`.) Confirmed: the
`HostConfigManager` returned by the `configManager` property enumerates
~40 child managers (storageSystem, firewallSystem, advancedOption =
`EsxHostAdvSettings-6011`, etc.) but **contains neither** the executer
nor the dynamic type manager. They are only reachable via the two
`Retrieve*` methods above.

The `InternalDynamicTypeManager` proxied through vCenter **works fully**
for discovery:

- `DynamicTypeMgrQueryMoInstances` with `typeSubstr=syslog` returned the
  esxcli MO instances, e.g.
  `id=ha-cli-handler-system-syslog-config`,
  `moType=vim.EsxCLI.system.syslog.config`.
- `DynamicTypeMgrQueryTypeInfo` with
  `typeSubstr=vim.EsxCLI.system.syslog.config` returned the complete
  method + result-field model: method `get` (wsdlName
  `VimEsxCLIsystemsyslogconfigget`) and its result data object
  `vim.EsxCLI.system.syslog.config.get.SyslogConfiguration` with fields
  including `LocalLogOutput`, `LocalLogOutputIsConfigured`,
  **`LocalLogOutputIsPersistent`**, `RemoteHost`, `LogLevel`, etc.

So **type/command discovery by reflection works through vCenter.**

### What is NOT reachable through vCenter — the blocker

**Execution does not proxy.** Two independent attempts, both definitive:

1. `ReflectManagedMethodExecuter.ExecuteSoap` against
   `ManagedMethodExecuter-6011` (fresh vCenter session). With the WSDL
   method name (`method=VimEsxCLIsystemsyslogconfigget`) accepted by the
   parameter validator, vCenter returns:
   ```
   ServerFaultCode: The operation is not supported on the object.
   detail: NotSupportedFault (NotSupported)
   ```
   Tried across `version` = `urn:vim25/8.0.2.0`, `urn:vim25`,
   `urn:vim25/7.0.0.0`, `/6.7`, `/6.5`, and with bare element / full
   inner-envelope / no-arg argument shapes. **All return `NotSupported`.**
   (A dotted `method=vim.EsxCLI...get` instead yields
   `InvalidArgument: method` — i.e. the validator wants the WSDL name;
   the WSDL name is accepted, and only then does execution refuse.)

2. Direct invocation of the dynamic method on vCenter's `/sdk` endpoint
   (`<VimEsxCLIsystemsyslogconfigget>` with `_this` = the host MO) fails
   with `Unable to resolve WSDL method name VimEsxCLIsystemsyslogconfigget
   in vim.version.v8_0_2_0` — vCenter's `/sdk` does not host the host's
   dynamic esxcli WSDL in any version namespace tried.

3. vCenter→host **clone-ticket tunnel** also fails: `SessionManager.
   AcquireCloneTicket` on vCenter returns a ticket
   (`cst-VCT-...`), but the host's `SessionManager.CloneSession` rejects
   it with *"Cannot complete login due to an incorrect user name or
   password."* The standalone VCF host does not honor the vCenter clone
   ticket. (This is the path a vCenter-only client would have used to
   reach the host without host creds — it is closed here.)

**Conclusion:** vCenter is a discovery proxy for the dynamic type
system but **not** an execution proxy for esxcli. `Get-EsxCli` works
from a vCenter PowerCLI connection because PowerCLI opens a **separate
direct connection to the ESXi host**; it does not tunnel ExecuteSoap
through vCenter.

---

## 2. Captured wire format — host-direct, PROVEN

> 🛑 **SUPERSEDED framing.** The *response field data* captured here
> (`LocalLogOutput=/scratch/log`, `LocalLogOutputIsPersistent=true`) is
> real and matches what the vCenter path returns. But the "execution
> **must** be host-direct" claim is wrong — the same data comes back over
> a vCenter-only session via the §0.2 `ExecuteSoap`. Note the host-direct
> wire shape below differs from the vCenter-session shape: host-direct
> invokes the dynamic `Vim…get` element with a bare `_this`, whereas the
> vCenter path wraps it in `ExecuteSoap` (moid + version + dotted method).
> The adapter uses the **§0 vCenter path**, not this one.

Login direct to the host (`root` / lab password) → invoke the dynamic
method on its own `/sdk`. The `_this` MoRef must be sent **without** an
explicit `type=` attribute (the dynamic moType `vim.EsxCLI.system.
syslog.config` is not a parse-time-registered MoRef type; supplying it
triggers *"Error processing attribute type … while parsing MoRef"*).
Bare `_this` works.

**Request** (POST `https://vcf-lab-mgmt-esx03.int.sentania.net/sdk`,
`SOAPAction: "urn:vim25/8.0.2.0"`, with the host `vmware_soap_session`
cookie from a prior `Login` on `ha-sessionmgr`):

```xml
<?xml version="1.0"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:vim25="urn:vim25">
 <soapenv:Body>
  <vim25:VimEsxCLIsystemsyslogconfigget>
   <vim25:_this>ha-cli-handler-system-syslog-config</vim25:_this>
  </vim25:VimEsxCLIsystemsyslogconfigget>
 </soapenv:Body>
</soapenv:Envelope>
```

**Response** (abridged to the proof fields; full object had 18 fields):

```xml
<VimEsxCLIsystemsyslogconfiggetResponse xmlns="urn:vim25">
 <returnval>
   <AllowVsanBacking>false</AllowVsanBacking>
   <EnforceSSLCertificates>true</EnforceSSLCertificates>
   <LocalLogOutput>/scratch/log</LocalLogOutput>
   <LocalLogOutputIsConfigured>false</LocalLogOutputIsConfigured>
   <LocalLogOutputIsPersistent>true</LocalLogOutputIsPersistent>
   <LogLevel>info</LogLevel>
   <RemoteHost>tcp://vcf-lab-operations-logs.int.sentania.net:514?formatter=RFC_3164&amp;framing=non_transparent</RemoteHost>
   <StrictX509Compliance>false</StrictX509Compliance>
   ...
 </returnval>
</VimEsxCLIsystemsyslogconfiggetResponse>
```

**Proof-target values read back:**
- `LocalLogOutput` = `/scratch/log`
- `LocalLogOutputIsPersistent` = `true`

This **corrects the prior recon's "LocalLogOutputIsPersistent is dead"
claim** — that recon only checked the OptionManager/advanced-settings
surface. The field is alive and well in the esxcli `system.syslog.config`
namespace, readable over SOAP.

### Reproduce in three calls (host-direct)

1. `Login(ha-sessionmgr, root, <pw>)` — keep the `vmware_soap_session`
   cookie. (Use a **fresh** session per probe; the cookie is short-lived
   — a stale cookie returns *"Permission to perform this operation was
   denied"*, which looks like an authz ceiling but is just expiry.)
2. (Optional / one-time per host) `DynamicTypeMgrQueryMoInstances` on
   `ha-dynamic-type-manager` (host-direct name) or via the
   vCenter-discovered `DynamicTypeManager-6011` to map command → moid +
   moType. The moid `ha-cli-handler-<ns>` is derivable by convention.
3. Invoke `Vim<NamespaceCommand>` with bare `_this=<moid>`.

> Discovery (step 2) can be done once through vCenter; **execution
> (step 3) must be host-direct.**

---

## 3. Bindings availability — a real gap in BOTH stacks

The adapter's bundled bindings **do not** contain the reflect/dynamic
types:

- `content/sdk-adapters/compliance/lib/vim25.jar` — a **2016-era**
  (vSphere 6.x) vim25 jar. `unzip -l | grep` finds only
  `DynamicProperty` / `ArrayOfDynamicProperty` (the generic
  PropertyCollector dynamic-value type). It has **no**
  `ReflectManagedMethodExecuter`, **no** `InternalDynamicTypeManager`,
  **no** `DynamicTypeMgr*` classes.
- `content/sdk-adapters/compliance/lib/vim-vmodl-bindings-8.0.2.jar` —
  also **none** of those types.

Independent corroboration: stock **pyVmomi** likewise lacks them —
`vim.ReflectManagedMethodExecuter` and `vim.InternalDynamicTypeManager`
raise `AttributeError` / `KeyError ('urn:vim25', 'ReflectManagedMethod
Executer')`. These types live in the *internal* reflect WSDL
(`urn:reflect`, version `vim.version.version5`), which neither stock
binding ships.

**Implication for cost:** an `esxcli` reader cannot be built by calling
generated stubs — those stubs do not exist on the classpath. Two
buildable options:

- **(Preferred) Raw-SOAP reader, no new bindings.** The dynamic methods
  are trivially expressible as hand-built SOAP: a `Vim<...>get` element
  with a bare `_this`. The adapter already trusts-all SSL and maintains
  sessions (`VSphereClient.connect()`). A small `EsxcliSoapClient` that
  (a) opens a direct host session, (b) POSTs the dynamic-method
  envelope, (c) parses the `returnval` for the wanted field would need
  **no regenerated stubs** — it bypasses JAX-WS for these calls the same
  way `SuiteApiPropertyPusher` bypasses the SDK's SuiteAPIClient. This is
  the lowest-cost path and matches the skill's
  "reflection-tolerant / never cast" posture by construction (there is
  no concrete type to cast to).
- **(Heavier) Regenerate vim25 stubs from a fuller WSDL** that includes
  the reflect service. The vSphere Management SDK ships
  `reflect-messagetypes.wsdl` / `reflect-types.wsdl`. Regenerating would
  give typed `ReflectManagedMethodExecuter` / `DynamicTypeManager` stubs,
  but (a) the esxcli *result* types are still **dynamic per host/version**
  and not in any static WSDL, so you'd be reflecting over them anyway,
  and (b) it bloats `lib/` and re-opens binding-drift risk. Not worth it
  for this — the raw-SOAP reader subsumes it.

---

## 4. Reflection-tolerant call shape (sketch)

Because the result is a dynamically-typed object, the reader should
parse the XML `returnval` generically and never bind to a concrete
class. Conceptually (host-direct):

```
// one direct host session per host per cycle
EsxcliSoapClient esx = new EsxcliSoapClient(hostFqdn, hostUser, hostPw); // trust-all SSL
esx.login();                          // ha-sessionmgr
// command -> (moid, element). moid by convention: "ha-cli-handler-" + ns.replace('.','-')
String moid    = "ha-cli-handler-system-syslog-config";
String element = "VimEsxCLIsystemsyslogconfigget";   // Vim + namespace + command, no dots
Element returnval = esx.invoke(element, moid);        // POST envelope, return <returnval> node
String persistent = text(returnval, "LocalLogOutputIsPersistent"); // "true"/"false"
String localOut   = text(returnval, "LocalLogOutput");
esx.logout();
```

`invoke()` builds `<vim25:ELEMENT><vim25:_this>MOID</vim25:_this>…args…
</vim25:ELEMENT>`, sends it, and returns the parsed `<returnval>` DOM
node. The recipe reader then pulls a named child element as
String/Boolean — exactly the "missing field → null/unreadable, never a
default" contract `readByRecipe` already enforces. No `xsi:type`,
no cast, tolerant to extra/missing fields across ESXi versions.

**Note:** field names in the result are **PascalCase**
(`LocalLogOutputIsPersistent`), unlike vim25 properties (camelCase).
The recipe grammar must carry the exact result field name.

---

## 5. Caveats / risks

> 🛑 **Caveat 1 below is SUPERSEDED — it is the inverted verdict.**
> vCenter *can* execute esxcli (§0); there is no host-credential design
> gap and no per-host fan-out. Caveats 2-6 still apply *with vCenter as
> the transport* (e.g. caveat 4 version-tolerance, caveat 5
> internal-API stability, caveat 6 now reframed as the §0.6 vCenter-level
> `Host.Cim.CimInteraction` privilege rather than a host account).

1. **vCenter cannot execute esxcli — host-direct only (the headline
   caveat).** [SUPERSEDED — FALSE. See §0.] The adapter today is vCenter-only. An `esxcli` style needs
   **per-host SOAP sessions with host credentials**. That means either
   (a) a new credential field on the adapter instance (ESXi root or a
   service account with the CLI privilege), or (b) acquiring per-host
   tickets — and the **clone-ticket tunnel is closed** on these
   standalone VCF hosts (proven: host `CloneSession` rejects the vCenter
   `AcquireCloneTicket`). `AcquireGenericServiceTicket` for a host SOAP
   service was not separately proven and is the only remaining
   ticket-style avenue worth a follow-up probe; absent that, **explicit
   host creds are required.** This is a DESIGN GAP to put to the user
   before any code: "are we willing to give the compliance adapter ESXi
   host credentials and let it fan out direct host sessions?"
2. **Per-host collection overhead / fan-out.** One direct session +
   login per host per cycle, on top of the existing vCenter session. For
   each esxcli control you either make one `get` call per namespace
   (cache the whole `…config.get` object and read many fields from it —
   the bulk-read pattern the skill prefers) or one call per command.
   Login/logout per host per cycle is the dominant cost; sessions should
   be reused within a cycle.
3. **Auth path.** Host login is `SessionManager` MoRef `ha-sessionmgr`
   (vs vCenter's `SessionManager`). Trust-all SSL already handled by the
   existing client. Host session cookies are short-lived — re-login on
   any *"Permission … denied"* / `NotAuthenticated`, do not treat as a
   real authz failure (this bit the spike: a stale cookie produced a
   false "permission denied" that a fresh login immediately resolved).
4. **vSphere 8 vs 9.** Proven on ESXi/vCenter **9.1**. The esxcli
   namespace set and result fields differ by version (e.g. fields added
   over time). The reader must be reflection-tolerant (field absent →
   unreadable) and the recipe→namespace map may need per-version notes.
   The dynamic type model is queryable per host
   (`DynamicTypeMgrQueryTypeInfo`) so a content author can confirm a
   field exists before writing a recipe.
5. **Internal/unsupported-API stability.** `urn:reflect` /
   `vim.EsxCLI.*` are private. They have been stable for ~a decade
   (PowerCLI depends on them) but carry no compatibility guarantee.
   Document every esxcli recipe as resting on an internal API.
6. **Throttling / privilege.** Not hit in the spike (single host, single
   call). At fleet scale, watch host session limits. The host account
   needs the privilege that backs esxcli `get` (root has it; a scoped
   service account would need `Host.Cim.CimInteraction` /
   `Global.Settings`-class rights — verify before recommending a
   least-privilege account).

---

## 6. Payoff sketch — controls an `esxcli` style would unlock

Primary value was proving the mechanism; this maps the parked buckets
from `scg89-audit-coverage-recon.md` to esxcli namespaces. The
**syslog** ones are now confirmed reachable (this spike); the **sshd**
ones live under `system.ssh.server.config` (esxcli
`system ssh server config`-class) which the same mechanism reaches.

| recon bucket | esxcli namespace (command) | result field(s) | controls |
|---|---|---|---|
| syslog persistence (`esx.logs-persistent`, `esx.logs-audit-persistent`) | `system syslog config get` | `LocalLogOutput`, `LocalLogOutputIsPersistent` | 2 ×2 profiles = ~4 |
| syslog remote/loghost (`fleet.log-forwarding` per-host part) | `system syslog config get` | `RemoteHost` | partial |
| SSH daemon hardening (`esx.ssh-fips`, `-fips-ciphers`, `-gateway-ports`, `-host-based-auth`, `-idle-timeout-count`, `-idle-timeout-interval`, `-login-banner`, `-rhosts`, `-stream-local-forwarding`, `-tcp-forwarding`, `-tunnels`, `-user-environment`) | `system ssh server config list` (key/value rows: `ciphers`, `gatewayports`, `hostbasedauthentication`, `clientalivecountmax`, `clientaliveinterval`, `banner`, `ignorerhosts`, `allowstreamlocalforwarding`, `allowtcpforwarding`, `permittunnel`, `permituserenvironment`, fips mode) | the matching row value | ~12 ×~2 = up to ~24 |
| account shell access (`esx.account-dcui`, `esx.account-vpxuser`) | `system account list` / `system permission list` | per-account shell flag | ~2–4 |
| key persistence (`esx.key-persistence`) | `system security keypersistence get` | enabled bool | ~1–2 |
| firewall per-ruleset (`esx.firewall-restrict-access`) | `network firewall ruleset list` / `… ruleset allowedip list` | allowedAll / IP list | partial (still org-specific) |

**Rough unlock:** the ~33 esxcli-class controls the recon parked, plus
several syslog/ssh items it marked "genuinely manual," become
**API-auditable host-direct**. The biggest single win is the SSH-daemon
cluster (`system ssh server config list` returns *every* sshd setting in
one call — a perfect bulk-read namespace: many controls, zero extra code
per control once the style exists). Realistic estimate: **~25–35
controls across both SCG profiles** move from "can't" to "API-auditable
(host-direct)", contingent on the host-credential design decision in §5.

---

## 7. Proposed recipe grammar + what to build

> 🛑 **UPDATED by §0.** Recipe grammar (§0.5) stands. The build list
> below assumed a host-direct `EsxcliSoapClient` with host credentials —
> **that is no longer needed.** The corrected build is: an `ExecuteSoap`
> helper that rides the adapter's **existing vCenter `VSphereClient`
> session** (§0.2 envelope), a per-(host,namespace) result cache, an
> `esxcli:` branch in the recipe reader that XML-unescapes
> `returnval/response` and pulls the PascalCase field, and a Call-1
> executer-MoRef lookup per host. **No host credentials, no per-host
> session, no `collectHosts()` credential plumbing.** Read the items
> below as "raw-SOAP, no new bindings" — which is still true — but
> substitute "vCenter session" for every "direct host session".

If the host-credential design gap is accepted, propose a new canonical
read style:

```
esxcli:<namespace.command>:<ResultField>
```

Examples:
```
esxcli:system.syslog.config.get:LocalLogOutputIsPersistent   -> Boolean
esxcli:system.syslog.config.get:LocalLogOutput               -> String
esxcli:system.ssh.server.config.list:gatewayports            -> row value (list-of-rows style)
```

- `<namespace.command>` maps to moid `ha-cli-handler-<namespace-with-
  dashes>` and element `Vim<NamespaceCommandConcatenated>`.
- `<ResultField>` is the **PascalCase** child of `returnval` for `get`
  commands; for `list` commands that return rows of `{Key,Value}` or
  named rows, a secondary `list` variant of the style selects the row.
- Bulk-read friendly: cache the whole `…get` / `…list` result per
  (host, namespace) per cycle; multiple recipes against the same
  namespace cost one call.

**sdk-adapter-author would build (Tier 2 Java):**
1. `EsxcliSoapClient` — direct-to-host SOAP session (login on
   `ha-sessionmgr`, trust-all SSL reusing `VSphereClient`'s factory),
   `invoke(element, moid, args)` → parsed `<returnval>` DOM, with
   re-login-on-stale-cookie. **No new bindings** (raw SOAP).
2. A per-cycle host-session cache + namespace-result cache.
3. An `esxcli:` branch in the recipe reader (sibling to `scalar` /
   `bool` / `bool_policy`) that pulls the named child element and types
   it (Boolean for "true"/"false", else String), returning
   `UNREADABLE` on miss — same contract as `readByRecipe`.
4. `ComplianceAdapter.collectHosts()` to pass host credentials /
   construct the `EsxcliSoapClient` (the host-credential plumbing).

**No tooling/bindings change is required first** — the raw-SOAP approach
keeps everything inside `content/sdk-adapters/compliance/`. The only
hard prerequisite is the **DESIGN decision on host credentials** (§5,
caveat 1), which the orchestrator must put to the user before
sdk-adapter-author starts.

**Open follow-up (cheap, would tighten the verdict):** probe
`HostSystem`/`SessionManager.AcquireGenericServiceTicket` for a host SOAP
service ticket usable from a vCenter session — if that works, the
adapter could reach hosts with **vCenter creds only**, removing the
host-credential design gap entirely and upgrading this to a clean GO.
Not tested in this spike.

---

## AcquireGenericServiceTicket probe

> 🛑 **SUPERSEDED / IRRELEVANT.** This whole probe chased a ticket-to-host
> mechanism that esxcli-over-vCenter never uses. The executer call rides
> the existing vCenter session directly (§0); no host ticket is involved.
> The findings here are accurate *about service tickets* but answer the
> wrong question. Ignore for the esxcli design.

**Date:** 2026-06-03 · **Analyst:** api-explorer · same targets
(mgmt vCenter `vcf-lab-vcenter-mgmt.int.sentania.net` 9.1.0 build
25370922, host `vcf-lab-mgmt-esx03` `host-6011`).

**Question (binary):** Can an authenticated vCenter session use
`SessionManager.AcquireGenericServiceTicket` to reach the ESXi host's
SOAP endpoint and run esxcli **without separate host credentials**?

### Verdict: **NO — host credentials required (design gap stands).**

The ticket `AcquireGenericServiceTicket` issues is **scoped to vCenter
itself**, not to the host, and the host rejects it as a credential. This
is the same outcome class as the clone-ticket (§1 item 3): vCenter will
not hand a vCenter-only client an identity on a standalone VCF host.

### Evidence

**1. The spec only accepts vCenter-local URLs; host URLs are rejected at
validation.** `AcquireGenericServiceTicket` takes a
`SessionManagerHttpServiceRequestSpec` (`xsi:type` required —
`{method, url}`). Requesting any host URL fails before a ticket is even
minted:

```
spec.url = https://vcf-lab-mgmt-esx03.int.sentania.net/sdk
  -> ServerFaultCode: A specified parameter was not correct: url
     InvalidArgument (invalidProperty=url)
```
Same for `/downloads` on the host. A vCenter-local URL succeeds and
reveals the ticket's scope:

```
spec.method = httpGet ; spec.url = https://vcf-lab-vcenter-mgmt.../sdk  (or /ui, /folder, /health)
  -> AcquireGenericServiceTicketResponse:
       id          = 52041978-ef9e-6eed-... (one-time-use)
       hostName    = vcf-lab-vcenter-mgmt.int.sentania.net   <-- the vCenter, never the host
       sslThumbprint = A2:5F:35:...                          <-- vCenter's cert
       ticketType  = VcServiceTicket
```
The `hostName`/`sslThumbprint` in the returned ticket are **always the
vCenter's**. There is no spec field, and no accepted URL, that points the
ticket at an ESXi host. This API is for proxying to vCenter-local HTTP
services (the /ui, /folder, nfc-style endpoints), not for cross-hopping
to a host.

**2. The issued `VcServiceTicket` is not a valid credential on the
host.** Taking a freshly minted ticket and presenting it to the host's
`/sdk` three ways, then invoking the already-proven esxcli call
(`VimEsxCLIsystemsyslogconfigget` on `ha-cli-handler-system-syslog-config`):

| attempt | how the ticket was presented to host `/sdk` | host response |
|---|---|---|
| A | `Cookie: vmware_soap_session="<ticket>"` then esxcli `get` | `NoPermission` — `System.Read` denied on `ha-folder-root` (anonymous; no identity attached) |
| B | host `SessionManager.CloneSession(cloneTicket=<ticket>)` | `InvalidLogin` — *"incorrect user name or password"* |
| C | `Cookie: vmware_soap_session=<ticket>` (unquoted) then esxcli `get` | `NoPermission` — `System.Read` denied |

A returns `NoPermission` rather than `NotAuthenticated`: the host treats
the unknown cookie as an anonymous session with zero privileges, so even
read fails. B is the explicit ticket-login path and the host rejects the
ticket outright — identical to the clone-ticket rejection in §1.3. No
host session was ever established (nothing to log out host-side).

### Why this closes the question

`AcquireGenericServiceTicket` is structurally a **vCenter-local proxy
ticket** (`ticketType=VcServiceTicket`, bound to vCenter's hostName +
thumbprint). It cannot be aimed at a host (url validation blocks it) and,
even when force-fed to the host, carries no host identity. Combined with
the already-failed clone-ticket tunnel (§1.3), **both vCenter-only
ticket avenues to the host are now closed.** The compliance adapter
cannot fan out to ESXi hosts on vCenter credentials alone; it needs
**explicit ESXi host credentials** (root or a scoped service account) to
open the direct host SOAP sessions esxcli execution requires.

### Net effect on the overall conclusion

The §5 caveat-1 open follow-up is resolved: it does **not** upgrade to a
clean GO. The headline verdict stands as **GO-WITH-CAVEATS — host-direct
only, host credentials required**. The host-credential design gap is real
and is a decision for the user before any `esxcli`-style code is written:
*"are we willing to give the compliance adapter ESXi host credentials and
let it fan out direct host sessions?"* There is no vCenter-creds-only
shortcut.

---

## Clean-up

All SOAP sessions created (3 host `ha-sessionmgr`, 2 vCenter
`SessionManager`) were explicitly `Logout`-ed; all `/tmp` artifacts
removed. **No objects were created or mutated** on either system — only
`Login`/`Logout` and read-only `get` / query calls. Verified: no
residual sessions or temp files.

**AcquireGenericServiceTicket probe clean-up:** the one vCenter session
(`administrator@vsphere.local`) was `Logout`-ed and verified dead
(follow-up call → *"The session is not authenticated"*); no host session
was established (all host attempts rejected); all `/tmp` XML/cookie
artifacts removed. Calls were read-only (`Login`, `AcquireGenericService
Ticket`, `FindByDnsName`, `Logout`) — no objects created or mutated.
