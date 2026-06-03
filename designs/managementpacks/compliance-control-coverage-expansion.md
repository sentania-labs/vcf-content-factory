# Compliance Adapter — Control Coverage Expansion (existing-style)

**Date**: 2026-06-03
**Status**: Approved for build
**Type**: Tier 2 SDK adapter enhancement (compliance)
**Owner agent**: `sdk-adapter-author`
**Parent designs**:
- `designs/managementpacks/vcf-compliance-adapter.md`
- `designs/managementpacks/compliance-vim-property-reader.md` (the read_recipe engine this builds on)
**Recon of record**: `context/investigations/scg89-audit-coverage-recon.md`

---

## Initial prompt

Across this session the user asked, in order:

> Going back to the controls — how do we dynamically ensure we are able
> to get the proper controls ... when a new control is introduced capture
> that "data" without resorting to code changes?

Then, scoping the next increment:

> 1> Let's do it.
> 2> Let's drop CIS, since there is no 8 yet. Roadmap: possibly separate
>    project: to convert control documentation to our expected input CSV
> 3> Remediation is future, we should be able to determine how to audit
>    everything without powercli + esxcli
> 4> Create a MD report of SCG 8/9 manual audits (after doing the recon
>    for VIM/advanced settings)

And on batch scope, after the recon landed:

> DO all of it, including create a doc that ships with the pak on the list
> of controls we do not audit (basically our lists of we don't do this
> either because we can't or haven't fully explored our options yet)

---

## Vision

Convert every SCG 8.0 / 9.0 control that the recon classified as
**reclassifiable with an *existing* read_recipe style** (`scalar`, `bool`,
`bool_policy`, `string_list_join`) from `powercli_only` / `esxcli` /
`manual_audit` into `vim_property` — moving control knowledge into the
canonical CSV, not Java. Pair it with the single architectural Java change
the recon identified as the unlock, and ship an in-pak doc that is honest
about what we do *not* audit.

CIS is dropped from this increment (the `cis_vsphere_8.csv` profile is an
all-`manual_audit` stub — "no real 8 yet"; doc→CSV conversion is a separate
roadmap project).

## In scope (do now)

1. **Architecture: extend `collectHosts()` and `collectVms()`** in
   `ComplianceAdapter` to call `vsphere.readVimProperties(ref, controls)`
   in addition to `getAdvancedSettings()`. One-time Java change; without it
   any HostSystem/VM `vim_property` recipe loads but never evaluates. This
   is the unlock for the two most populous resource kinds.

2. **All existing-style reclassifications (~23 controls)** — edit the
   canonical CSVs + re-run the normalizers to set `parameter_kind:
   vim_property` and populate `read_recipe`. Per the recon tables:
   - **DVS/DVPG (pure CSV — collectors already read vim props):**
     `vds.network-reset-port`, `vds.network-restrict-discovery-protocol`,
     `vds.network-restrict-netflow-usage` (8.0 + 9.0); `vds.network-nioc`
     (9.0); `dvpg.network-mac-learning` (8.0 + 9.0).
   - **DVPG partial-coverage (MEDIUM — include, but caveat):**
     `dvpg.network-restrict-port-level-overrides` (8.0 + 9.0). The single
     recipe `bool:config.policy.securityPolicyOverrideAllowed` covers only
     one of the ~7 override flags the control intends. **Record this partial
     coverage explicitly** in the control description / the in-pak doc so a
     `pass` is never read as full-control fidelity.
   - **HostSystem (need the collectHosts extension):** `esx.lockdown-mode`,
     `esx.firewall-incoming-default`, `esx.timekeeping-sources`/`esx.time`
     (NTP sources), `esx.secureboot-enforcement`, `esx.tpm-configuration`
     (8.0 + 9.0); `esx.tpm-trusted-binaries` (9.0). Recipes per recon.
   - **VirtualMachine (need the collectVms extension):** `vm.secure-boot`,
     `vm.vmotion-encrypted`, `vm.ft-encrypted`, `vm.log-enable` (8.0 + 9.0);
     `vm.virtual-hardware` (9.0). Recipes per recon.

   Exact final set + recipe strings come from the recon tables; reconcile
   against the live CSVs (recon notes a 12-vs-13 pure-CSV count drift —
   trust the CSV rows, not the prose).

3. **In-pak doc: "Controls We Do Not Audit"** — ships *inside* the pak so
   any operator sees coverage honestly. Two sections, exactly the user's
   framing:
   - **Cannot** — the ~153 genuinely manual controls (in-guest
     `tools.conf`, `sshd_config`, off-box hardware/firmware, BMC/iDRAC,
     separate products NSX / VCF Ops / VCF Logs / Networks, vSAN
     Management SDK gap, organizational policy/design decisions).
   - **Haven't fully explored yet** — API-reachable but needing readers we
     have not built: the ~46 new-style controls (service_state, VAMI REST,
     SSO SOAP, device-absent, list-empty, vlan-id-type), the 16 other-API
     controls, and the 24 uncertain ones.
   Source the content from the recon's residue + new-style + uncertain
   tables. If the pak build cannot bundle a standalone doc, **report a
   TOOLSET GAP** — do not silently drop it.

4. **Build bump** (`adapter.yaml` + `CHANGELOG.md`), `CANONICAL_SCHEMA.md`
   touch only if the recipe surface changes (it should not — existing
   styles only).

## Out of scope (held — documented, not built)

- **The 6 new read_recipe styles A–F** (service_state, vm_hardware_device_
  absent, list_empty, vlan_id_not, SSO STS SOAP reader, VAMI REST reader).
  Each is a separate Java effort with live-schema uncertainty. They are the
  "haven't yet" backlog in the in-pak doc; bring back as their own
  design(s) per highest-value-first (recon ranks `service_state` top).
- **Two promising `advanced_setting` reclassifications** flagged uncertain
  — `vc.vpxuser-length` (`config.vpxd.hostPasswordLength`) and the
  persistent-log pair (`ScratchConfig.CurrentScratchLocation`,
  `LocalLogOutputIsPersistent`). A quick live check on devel could promote
  these to pure-CSV `advanced_setting`; do that opportunistically if cheap,
  else leave in "haven't yet."
- Remediation actions (future, separate effort — needs an execution runtime).

## Proof gate / anti-rework

- **Equivalence preserved**: existing evaluable vim controls must still
  produce identical pass/fail/score (parent design's acceptance rule).
- **devel is the proving instance** (2 vCenters collecting). Cheap loop:
  `validate-sdk`. Then `build-sdk` → `pak-compare` against the closest
  reference (zero BLOCKING is the install gate).
- **The `unreadable` signal is the safety net**: a wrong recipe surfaces as
  a non-zero `unreadable_count` on devel — never a false `pass`. A bad
  conversion is loud and is a one-commit CSV revert, grouped by
  resource/style cluster.
- Install on devel and confirm the converted controls evaluate (and the
  unreadable count is sane) before treating the pattern as proven.

## Files in play

- `src/.../ComplianceAdapter.java` — `collectHosts()` / `collectVms()` call
  `readVimProperties()`.
- `profiles/canonical/scg_8.0.csv`, `scg_9.0.csv` — reclassified rows +
  `read_recipe` values.
- `scripts/normalize_scg_v8.py`, `normalize_scg_v9.py` — emit the
  reclassified `parameter_kind` + `read_recipe`.
- New in-pak doc (path/mechanism per sdk-adapter-author; e.g. a bundled
  `UNAUDITED_CONTROLS.md`).
- `adapter.yaml`, `CHANGELOG.md` — build bump.
