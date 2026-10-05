# policy-fragment

Two verbatim vendor extracts that bound what a management pak's
`content/policies/*.xml` fragment may carry.

1. `compliance-pack-pci-9.0.2-ootbpolicies.xml`: the whole
   `<OOTBPolicies>` element of `content/policies/pci.xml` from the
   Broadcom pak `vRealizeOperationsCompliancePackforPCI-902025137908.pak`
   (VCF Operations 9.0.2 bundled compliance pack). This is the only
   vendor-authored pak policy fragment found on the appliance (the CIS,
   DISA, FISMA, HIPAA, ISO siblings use the same layout).
   - **Source:** `/storage/db/casa/pak/dist_pak_files/NON_VA_LINUX/` on
     the devel appliance (`vcf-lab-operations-devel.int.sentania.net`).
     Local-only artifact: Broadcom pak, not in any fetch registry. The
     surrounding `<alertContent>` (about 47 KB of alert and symptom
     definitions) was trimmed; the extracted element is unmodified.
2. `describeSchema-6.3.0-PackageSettingsType-MetricsType.xsd`: the
   `PackageSettingsType` and `MetricsType` complex types, verbatim, from
   `/usr/lib/vmware-vcops/user/plugins/inbound/vim/conf/describeSchema.xsd`
   (schema `version="6.3.0"`) on the same appliance. File lines
   4249-4264 and 4457-4519, joined by one blank line.

- **Extracted:** 2026-10-01 (RULE-016, immutable once added).
- **Digest:** `knowledge/context/investigations/policy_fragment_wire_format.md`.

What it shows: the vendor fragment is the OOTB dialect
(`<PolicyContent><OOTBPolicies vendorNameKey><Policy key nameKey><PackageSettings>`),
and the published XSD lists only `BadgeSymptoms`, `Symptoms`, `Alerts`,
`Metrics` under `PackageSettings`. No `SuperMetrics` child appears in
either. The runtime parser accepts more than the XSD lists; see the
digest.
