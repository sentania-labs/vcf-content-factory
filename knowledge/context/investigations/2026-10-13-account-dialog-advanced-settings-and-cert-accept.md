# Account dialog: Advanced Settings placement, and the certificate-accept hook (2026-10-13)

Investigator: `api-explorer`. Target: VCF Operations 9.0.2 (devel,
`vcf-lab-operations-devel`). Read-only: no lab writes, the Add Account dialog
was opened and cancelled without saving, appliance files were read with ssh
and scp only. Feeds `knowledge/designs/sdk-adapters/compliance-build-93-auto-only-cert-accept.md`
item 4 and its "Out of scope" buildkit question; closes the mechanism question
in FB-003 and part of FB-004 (`knowledge/context/feedback_queue.md`).

## 1. How an identifier lands under "Advanced Settings"

### The rule (from the 9.0.2 platform bytecode)

The controller builds each identifier's UI flags in
`com.vmware.vcops.controller.retriever.ResKindIdentsRetriever`
(`/usr/lib/vmware-vcops/common/lib/vcops-collector-controller-1.0-SNAPSHOT.jar`
on devel, bytecode offsets 260 to 338). Decompiled to Java:

```java
if (describeIdentifier.isAdvanced() != null) {          // explicit advanced="..." attribute
    ident.advanced = describeIdentifier.isAdvanced();
} else {
    boolean hasDefault = ident.defaultValue != null && !ident.defaultValue.isEmpty();
    ident.advanced = !ident.isIdentifying() && (!ident.required || hasDefault);
}
```

- `isIdentifying()` (`ResourceKindIdents$ResourceKindIdent`, `alive_platform.jar`)
  is true when `identType` is absent **or** `IDENTIFYING` (1). So an
  identifier with no `identType` is never advanced by default, whatever its
  `required` or `default`.
- `defaultValue` is the enum default for `enum="true"` identifiers, else the
  `default` attribute.
- `hidden="true"` identifiers are dropped before the split
  (`com.vmware.vcops.ui.action.ManageResourceAction`, ui webapp, offsets 759
  to 767), so hidden wins over advanced.
- The UI then renders `identifiers` in the main form and
  `advancedIdentifiers` inside the "Advanced Settings" expander
  (`ManageResourceAction` offsets 1231 to 1249;
  `ui/js/components/integrations/AdapterGenericViewPanel.js` lines 690 to 725,
  1142 to 1160; the expander header is shown only when the advanced list is
  non-empty).

The explicit `advanced` attribute is parsed by the SDK describe model
(`com.integrien.alive.common.adapter3.describe.ResourceIdentifierDescribe`,
`/usr/lib/vmware-vcops/common/lib/vrops-adapters-sdk.jar`, offsets 656 to 733):
absent or empty means "no information" (falls through to the default rule);
`false` (any case) means not advanced; any other value means advanced.

So, stated plainly: **an identifier goes under Advanced Settings when
`advanced="true"` is set, or, with no `advanced` attribute, when it has
`identType="2"` and is either `required="false"` or carries a non-empty
default.** `required="false"` alone does nothing, `dispOrder` does nothing,
there is no group element.

### Schema and SDK evidence

- `describeSchema.xsd` v8.3.0 (the copy under
  `reference/references/vmbro_vcf_operations_vcommunity/Management Pack/conf/`,
  identical to the one in the Python integration SDK 1.3.1) has no `advanced`
  or `hidden` attribute on `ResourceIdentifierType`; `identType` is documented
  only as "1 - part of uniqueness, 2 - not part of uniqueness". The appliance's
  own `describeSchema.xsd` copies (vim, VrAdapter, SupervisorAdapter,
  VMwareInfrastructureHealthAdapter, version 1.0) have `hidden` but not
  `advanced`. The attribute exists only in the parser.
- VMware's Python integration SDK (`vmware-aria-operations-integration-sdk-lib`
  1.0.0, `aria/ops/definition/parameter.py`) documents `advanced` as "True if
  the parameter should be collapsed by default" and emits it as
  `"ident_type": 1 if not self.advanced else 2`; the describe generator
  (`vmware-aria-operations-integration-sdk` 1.3.1, `describe.py` line 382)
  writes that as `identType`, always with `required` and `default`. VMware's
  own tooling therefore uses `identType="2"` as the advanced switch.
- MPB paks (`dist/mpb_vcf_content_factory_unifi_integration.1.0.0.14.pak`,
  `..._vsphere_storage_paths.2.0.0.5.pak`): `mpb_hostname` is `identType="1"`;
  port, timeout, concurrency, retries, SSL mode, event severity and
  autodiscovery are `identType="2" required="true"` with a non-empty default.
  Those are exactly the MPB "advanced" config params
  (`knowledge/context/mpb/mpb_adapter_runtime_insights.md`, `BuilderConfigParam.advanced`).
  Fits the rule through the has-default branch.
- Native vCenter adapter (`vmwarevi_adapter3/conf/describe.xml` on devel,
  adapter kind `VMWARE`, resource kind `VMwareAdapter Instance`): `VCURL` has
  no `identType` (main form); every other identifier is `identType="2"`; one
  (`VMC_CONFIG_LIMITS_FILE_NAME`) carries `advanced="true"` together with
  `hidden="true"`, the only use of the attribute found anywhere.

### Live confirmation on devel (compliance Add Account dialog, build 92)

Opened Integrations, Accounts, VCF Content Factory Compliance, ADD ACCOUNT,
expanded Advanced Settings, cancelled.

| Field | describe.xml | Rule predicts | Seen |
|---|---|---|---|
| `vcenter_host` | no identType, required true | main | main |
| `benchmark_profile` | no identType, required true, enum | main | main |
| `allowInsecure` | **no identType, required false**, default `false` | main | main |
| `overrides_file` | identType 2, required false, default `""` | advanced | Advanced Settings |
| `read_appliance_settings` | identType 2, required false, default `false` | advanced | Advanced Settings |

`allowInsecure` and the two advanced fields are all `required="false"`; the
only difference is `identType`. That rules out `required` as the mechanism.
(The native vCenter dialog was not opened: its account page in 9.0.2 is a
custom VCF panel, so it would not test the generic dialog.)

### Two ways to move a field, and what each costs

1. **`identType="2"`** (plus `required="false"` or a default). Proven live.
   Side effect: the field leaves the account's uniqueness tuple. For
   `allowInsecure` today (no `identType`, so identifying) that is an identity
   change on existing accounts, the same class of risk build 92 raised for
   removing `custom_profile_path` (`knowledge/context/reviews/compliance-build-92.md` §(a)).
2. **`advanced="true"`** with `identType` unchanged. The platform honours it
   and the split does not look at identity, so the uniqueness tuple is
   untouched. Not proven for a third-party pak: no non-hidden use exists
   and the attribute is outside every shipped XSD. The import path does not
   reject it, though (traced in a second pass, same day):
   `AdapterDescribe` parses describe.xml with plain DOM
   (`XMLParserUtil.getDocument`, no schema validator on that path; the
   validator helper `getSecureSchemaValidator` is not called from the
   describe classes), `DescribeConversionUtil`
   (`persistence-1.0-SNAPSHOT.jar`) copies `ResourceIdentifierDescribe.isAdvanced()`
   into the persisted `ResourceKindIdentifier.setAdvanced`, and
   `ResKndIdentDescriber` copies it again on a describe upgrade, so an
   upgraded pak should update existing accounts' placement. Still needs one
   devel install to see it render.

## 2. The `certificateCheckUrls` hook

### (a) Compliance does not override it

`content/sdk-adapters/compliance/` (branch `feat/build-90-overrides-file`,
HEAD `f22c3d8`): no `certificateCheckUrls`, `getConnectionURLs` or
`isAllowInsecure` anywhere in `src/`. `ComplianceAdapter extends
VcfCfAdapter<ComplianceConfig>` (line 53) so it inherits the default (empty
list, so the SDK default `getConnectionURL` returns `null` and Validate
Connection gets `NOT_SUPPORTED`, no review dialog). It parses Allow Insecure
itself: `ComplianceConfig.java:79`, `"true".equalsIgnoreCase(allowInsecure)`
(untrimmed), and `sslContextFor` picks trust-all or `getPlatformSslContext()`
(`ComplianceAdapter.java` around 217).

### (b) Buildkit versions: CI cannot use the hook yet; local builds can

- The hook landed in factory commit `c97bee4` (2026-09-25 14:08 local,
  "feat(framework): accept-certificate on Validate Connection, allowInsecure
  pulldown, VERIFY_SSL=false beats CA bundle (#174) (#183)").
- Newest buildkit release: `sdk-buildkit-v1.0.10`, 2026-08-17 (commit
  `04f665d`). The floating `sdk-buildkit-v1` tag on origin also points to
  `04f665d` (the local tag is stale at `6e199eb`; origin is what CI reads).
  `git show sdk-buildkit-v1.0.10:src/vcfcf_managementpacks/adapter_framework/src/com/vcfcf/adapter/VcfCfAdapter.java`
  has zero `certificateCheckUrls`. Downloaded release asset
  `sdk-buildkit-1.0.10.tgz`: `VERSION` 1.0.10, bundled `VcfCfAdapter.java`
  has no `certificateCheckUrls`.
- Compliance CI (`.github/workflows/build-pak-on-tag.yml`):
  `BUILDKIT_TAG: sdk-buildkit-v1`, `BUILDKIT_REPO: sentania-labs/vcf-content-factory`,
  so an official `v*` tag build compiles against 1.0.10. A compliance
  override annotated `@Override` would fail to compile there; without the
  annotation it would compile but never be called.
- Local `build-sdk` (`src/vcfcf_managementpacks/sdk_builder.py`,
  `_ADAPTER_FRAMEWORK_SRC_DIR = _HERE / "adapter_framework" / "src"`)
  compiles the framework from the factory checkout. `c97bee4` is on `main`
  and on the current branch, so the devel builds (`dist/vcfcf_sdk_compliance.0.0.0.NN.pak`,
  build 92 included per `knowledge/context/approvals/2026-10-13-compliance-build-92-devel-install.md`)
  already compile against a framework with the hook.
- Platform side: devel 9.0.2's `vrops-adapters-sdk.jar` has
  `AdapterBase.checkCertificate`, `onCheckCertificate`,
  `getConnectionURLs(AdapterConfig)` and `getConnectionURL`, so the override
  point exists on 9.0.2, not only on the 9.1.1 jars the original analysis used.

- The released build is already blocked on a buildkit release for a
  separate reason: compliance calls `SuiteApiStitcher.addChild` and
  `findSingletonResourceId` (`ComplianceAdapter.java` 845 to 847), added to
  the framework in `e2720b7` (2026-10-06, #193), also after 1.0.10. The
  newest compliance release tag is `v1.0.0.80`; nothing since has been built
  by CI.
- All five other managed paks (synology, unifi, vcommunity, vcommunity-os,
  vcommunity-vsphere) also pin `BUILDKIT_TAG: sdk-buildkit-v1`, so moving
  the floating tag changes the framework under every pak's next tag build.
  Framework commits since 1.0.10: `6045435` and `70b44de` (the
  `vcfops_*` to `vcfcf_*` package rename), `c97bee4`, `e2720b7`.

Answer: a devel build can use the hook now; a released (`v*` tag) build
needs a buildkit release (1.0.11 or later, which moves `sdk-buildkit-v1`)
first. That release also carries the rest of `c97bee4` (allowInsecure
parsers, the `VERIFY_SSL=false` change in `vcfcf_common/client.py`) and
anything else merged since 2026-08-17 to every pak that floats on `v1`.

### (c) No managed pak overrides it, and it has never been seen working

Grep of every clone under `content/sdk-adapters/` (compliance, synology,
unifi, vcommunity, vcommunity-os, vcommunity-vsphere) finds no
`certificateCheckUrls`. The adoption table in `knowledge/context/tier2_architecture.md`
says "recorded 2026-09-25, not yet applied". The only repo documents naming
the hook are that file, the framework review
(`knowledge/context/reviews/framework/adapter-framework-cert-hook-2026-09-25.md`,
unit tests only: CertificateReviewTest 49/49, VcfCfAdapterTest 11/11, no
live run), FB-004 (still open) and the build 93 design. The synology, unifi
and vcommunity-os clones are on feature branches behind `origin/main`, so the
remotes were checked too: GitHub code search for `certificateCheckUrls` across
the `sentania-labs` org returns only factory files (`VcfCfAdapter.java`,
`CertificateReviewTest.java`, `sdk_builder.py` scaffold,
`tests/managementpacks/test_scaffold_sdk_cert_review.py`,
`tier2_architecture.md`); no pak repo's default branch overrides it.

Gap: `tier2_architecture.md` cites
`knowledge/context/investigations/tls_certificate_unknown_2026_09_25.md` as
its evidence. That file exists only on the unmerged branch
`docs/compliance-v3-esx-rename-and-release` (commit `10f526f`), not on `main`.

## Recommendation

Do not keep `allowInsecure` and move it; remove it, as the build 93 design
already decides, because once the adapter always validates and offers the
accept dialog an "insecure" switch has nothing left to do. The compliance
build then needs: a `certificateCheckUrls` override returning
`https://<vcenter_host>:443` (empty when the host is blank), the REST, VAMI
and SOAP clients all on `getPlatformSslContext()` with the trust-all branch
deleted, a one-time WARN for accounts that stored `allowInsecure=true`, and
error text telling the admin to open the account and Validate Connection
(hostname mismatch is not fixed by accepting, so the docs must say to use the
name on the certificate). For the two fields that stay, keep
`overrides_file` and `read_appliance_settings` as they are
(`identType="2" required="false"` with a default), which is proven to land
under Advanced Settings. If the build 92 identity result says removing an
identifying field is unsafe, keep `allowInsecure` (and `benchmark_profile`)
as `hidden="true"` identifiers with their old defaults rather than switching
them to `identType="2"`, since that also changes identity; `advanced="true"`
is the identity-neutral way to merely move a field, but it needs one devel
proof first. The devel build can be cut now with local `build-sdk`; the
released build waits on a buildkit 1.0.11 tag so `sdk-buildkit-v1` carries
the hook (it already waits on one for the 2026-10-06 stitch facade, and that
tag moves the framework under all six paks at once), and the devel verification is the first time anyone will have seen
the accept dialog driven by this framework.
