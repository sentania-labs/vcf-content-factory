# Compliance Adapter — esxcli Recipe Reader (via vCenter session)

**Date**: 2026-06-03
**Status**: Approved for build (sprint focus)
**Type**: Tier 2 SDK adapter enhancement (compliance)
**Owner agent**: `sdk-adapter-author`
**Parent designs**:
- `designs/managementpacks/vcf-compliance-adapter.md`
- `designs/managementpacks/compliance-vim-property-reader.md` (read_recipe engine)
- `designs/managementpacks/compliance-control-coverage-expansion.md` (build 35)
**Investigation of record**: `context/investigations/esxcli-soap-reflect-executer-spike.md` §0 (the proven encoding)

---

## Initial prompt

User pursued whether esxcli-class controls could be audited without a
PowerCLI/esxcli runtime ("audit everything without powercli + esxcli"),
then proved empirically — connected only to vCenter as
`administrator@vsphere.local`, no host login —

```
$esxcli = Get-EsxCli -VMHost (Get-VMHost "vcf-lab-mgmt-esx01...") -V2
$esxcli.system.syslog.config.get.Invoke()
→ LocalLogOutput=/scratch/log, LocalLogOutputIsPersistent=true, RemoteHost=tcp://...:514, ...
```

then: **"okay let's focus this sprint on the esxcli side of things."**

---

## Vision

Add an **`esxcli:<namespace.command>:<ResultField>` recipe style** so ESXi
host-CLI state (syslog, sshd, accounts, firewall) is auditable via the
adapter's **existing vCenter-only session** — unlocking ~25–35 SCG controls
currently classified `esxcli` or `manual_audit`, with **no host credentials,
no per-host fan-out, no tickets**.

## Technical basis (the cracked encoding — see spike §0)

esxcli executes over a vCenter session because vCenter relays the call to the
host via its own vpxuser channel. Working sequence, one vCenter session:
1. `RetrieveManagedMethodExecuter` on the `HostSystem` MoRef → executer MoRef.
2. `ExecuteSoap(_this=executer, moid="ha-cli-handler-"+namespace-dashed,
   version="urn:vim25/5.0", method="vim.EsxCLI."+namespace-dotted, args)`.
   - The prior `NotSupported` was wrong `version` (never tried `5.0`) + the
     executer MoRef used as the call target instead of the `ha-cli-handler`.
3. Response: `returnval/response` carries XML-escaped inner `<obj>`; unescape
   and parse. **Fields are PascalCase** (unlike camelCase vim25 props) — the
   recipe must carry the exact field name. `get`→struct; `list`→
   `ArrayOfDataObject` rows.

Derivation is mechanical, so it maps cleanly to a recipe style.

## Scope (this sprint) — proven-slice-first, like build 35

**A. Foundation (one-time Java):**
- An esxcli SOAP reader (extend `VSphereClient` or a new `EsxcliSoapClient`):
  RetrieveManagedMethodExecuter → ExecuteSoap (raw-SOAP, bare `_this`, no
  `xsi:type`, per spike §0) → parse inner `<obj>` to a field map.
- A **per-cycle, per-host, per-command result cache** — one esxcli command
  yields many fields/controls; never call the same command twice in a cycle.
- New `esxcli:` branch in the recipe reader; `UNREADABLE` on miss/unknown
  command/absent field (loud, never a false pass — build-35 contract).
- Wire into the existing `collectHosts()` (already fires for vim_property).

**B. Proof slice (build 36):** reclassify ONLY the **syslog persistence**
controls (`esx.log-persistent`/`esx.logs-persistent`,
`esx.log-audit-persistent`/`esx.logs-audit-persistent`, + remote-syslog if
clean) to `esxcli:system.syslog.config.get:<Field>` via the normalizers. This
is the smallest slice that proves the whole chain — encoding, response parse,
recipe style, AND the scoped-account privilege — against a command whose live
output we already have. Absorbs the parked Tier A persistent-log item
(`LocalLogOutputIsPersistent` as a clean boolean — strictly better than the
ScratchConfig not-equal hack).

**C. Held for build 37 (after the slice proves on devel):** the big win —
the **SSH-daemon hardening cluster** (the bulk `system ssh server config
list` read → ~12 controls: fips, ciphers, gatewayports, host-based-auth,
idle-timeout x2, login-banner, rhosts, stream-local-forwarding,
tcp-forwarding, tunnels, user-environment), plus key-persistence, account
shell access (dcui/vpxuser), and firewall ruleset reads. Same loop.

## Dependencies / risks

- **Scoped-account privilege.** Proven as full admin; the adapter uses the
  scoped `WLD01`/`mgmt` service accounts, which likely need vCenter-level
  `Host.Cim.CimInteraction` on the hosts (NOT host credentials). If absent,
  the proof-slice controls return `UNREADABLE` on devel → grant the privilege
  and re-collect. **The devel prove-step is the gate that confirms both the
  encoding and the privilege.**
- **Encoding is derived from govmomi + matches the user's PowerCLI proof, not
  re-captured on the wire** this round. Devel proves it for real; the
  `UNREADABLE` signal makes a wrong encoding fail safe.
- **Per-host call overhead** — mitigated by the per-cycle command cache.

## Out of scope

- `vc.vpxuser-length` (`config.vpxd.hostPasswordLength`) — vCenter *daemon*
  config, absent from the OptionManager surface on 9.1; esxcli is a host
  surface and cannot reach it. Stays manual; record in UNAUDITED_CONTROLS.md.
- Remediation; the VAMI-REST / SSO-SOAP reader tiers; vCommunity (separate
  worktree, parked pending licensing).

## Gate

`validate-sdk` (cheap loop) → `build-sdk` → `pak-compare` (zero new BLOCKING)
→ orchestrator installs on devel + confirms the syslog controls evaluate
(and the scoped-account privilege) before build 37 expands the bucket.
