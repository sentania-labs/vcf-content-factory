# Triage report — first pass — 2026-05-15

**Investigator**: Mraize
**Corpus**: marketplace `Downloads.zip` (extracted) + lab-admin devel
pull (`from-devel/paks/`) + 1 downloaded calibration reference

## Headline

51 unique paks classified. **39 KEEP-C** (native Java adapters, in
scope for SPEC). **12 ELIMINATE-B** (Integration SDK / Cloud Native,
moved to `inputs/_excluded/integration-sdk/`). **0 ELIMINATE-A**. No
Track A content packs were found in the corpus.

## Counts

| Classification | Count | Disposition |
|---|---|---|
| KEEP-C (Track C, native Java adapter) | 39 | Remain in `inputs/from-marketplace/` + `inputs/from-devel/paks/` |
| ELIMINATE-B (Track B, Integration SDK) | 12 | Moved to `inputs/_excluded/integration-sdk/` |
| ELIMINATE-A (Track A, MPB content pack) | 0 | — |
| Duplicates removed | 1 | `vmware-mpforaggregator-...(1).pak`, SHA256 identical |
| **Total triaged** | **52 events / 51 unique paks** | |

## Track C inventory (KEEP)

Ordered by lib/ richness — useful as a heuristic for analysis-order
priority alongside the explicit RE targets in CLAUDE.md.

### Priority RE targets (per CLAUDE.md)
1. **`MPBAdapter-902025137890.pak`** — 2 lib + `mpb-adapter.jar` root. The MPB runtime engine itself. Dual-tier insight.
2. **`vim-902025137884.pak`** — 102 lib + `vim.jar`. Most complex Broadcom MP; calibration anchor for C1.

### Cross-validation set (devel — Broadcom-internal, current-version)
| Pak | Lib jars | Adapter jar | Sub-shape |
|---|---|---|---|
| AppOSUCPAdapter-902025137916.pak | 116 | AppOSUCPAdapter3.jar | C1 |
| ServiceDiscoveryAdapter-902025137923.pak | 113 | ServiceDiscoveryAdapter3.jar | C1 |
| VrAdapter-902025137918.pak | 86 | VrAdapter.jar | C1 |
| ManagementPackforStorageAreaNetwork-902025137912.pak | 81 | VirtualAndPhysicalSANAdapter3.jar | C1 |
| VMwareInfrastructureHealth-902025137903.pak | 81 | VMwareInfrastructureHealthAdapter.jar | C1 |
| VMwarevSphere-902025137897.pak | 72 | vmwarevi_adapter3.jar | C1 |
| ConfigurationManagement-902025137888.pak | 65 | VcfUnifiedConfigAdapter.jar | C1 |
| VCFAutomation-902025137921.pak | 38 | automation_adapter.jar | C1 |
| NetworkInsightAdapter-902025137914.pak | 35 | NetworkInsightAdapter.jar | C1 |
| VCFDiagnostics-902025137871.pak | 30 | DiagnosticsAdapter3.jar | C1 |
| CASAdapter-902025137900.pak | 14 | CASAdapter.jar | C1 |
| NSXTAdapter-902025137922.pak | 13 | NSXTAdapter3.jar | C1 |
| VCFLogAssist-902025137895.pak | 12 | LogAssistAdapter.jar | C1 |
| PingAdapter-902025137875.pak | 2 | PingAdapter.jar | C1 (thin) |
| vcf-902025137906.pak | 2 | VcfAdapter.jar | C1 (thin) |
| **SupervisorAdapter-902025137863.pak** | 0 | SupervisorAdapter.jar | **C2 (SDK-on-classpath)** — calibration anchor for C2 |

### Marketplace Track C (third-party + Broadcom vendor packs)
| Pak | Lib jars | Adapter jar | Sub-shape |
|---|---|---|---|
| vmware-awsadapter-9.0.0.0-24731845.pak | 108 | amazon_aws_adapter3.jar | C1 |
| srmAdapterPak-9.1.0.0.25256726.pak | 103 | SrmAdapter.jar | C1 |
| vmware-vcfaviadapter-9.1.0.0-25407309.pak | 45 | AviAdapter.jar | C1 |
| servicenow_9.0.0.0200.25226290.pak | 38 | servicenow_adapter3.jar | C1 |
| vlcradapter-9.0.0.0-24650510.pak | 38 | VLCRAdapter.jar | C1 |
| vmware-mpforkubernetes-2.2.2-25125643.pak | 35 | KubernetesAdapter3.jar (+ PKSAdapter.jar, TMCAdapter*.jar) | C1 (multi-adapter pak) |
| networkingdevices_9.0.0.0.24730519.pak | 32 | networkingdevices_adapter_3.jar | C1 |
| vmware-diagnostics-9.0.0.0001-24879623.pak | 30 | DiagnosticsAdapter3.jar | C1 |
| oracledatabase_9.0.0.0100.25232927.pak | 28 | oracledatabase_adapter_3.jar | C1 |
| vmware-hcxadapter-5.4.0-21441913.pak | 26 | hcx_adapter.jar | C1 |
| openmanageenterpriseadapter-3.0.68.pak | 24 | OpenManageEnterpriseAdapter.jar | C1 |
| vmw-vcdaadapter-1.4.1-24443579.pak | 23 | VcdaAdapter.jar | C1 |
| mysql_9.0.0.0.24730518.pak | 21 | mysql_adapter3.jar | C1 |
| microsoftsqlserver_9.0.0.0100.24815089.pak | 20 | sql_server_adapter.jar | C1 |
| DellStorageAdapter-01.04.0301_signed.pak | 19 | dellstorage_adapter.jar | C1 |
| mongodb_9.0.0.0.24730517.pak | 18 | mongodb_adapter3.jar | C1 |
| postgresql_9.0.0.0.24730774.pak | 12 | postgres_adapter3.jar | C1 |
| vmware-mpforvro-9.0.0.0-24731678.pak | 12 | vRealizeOrchestratorAdapter3.jar | C1 |
| vmware-vcfhcxadapter-9.1.0.0-25345970.pak | 12 | vcf_hcx.jar | C1 |
| vmware-mpfornsxadvancedlb-1.3.4-25277573.pak | 5 | nsx-alb.jar | C1 (thin) |
| **vmware-mpforaggregator-9.0.0.0-24723247.pak** | 0 | federation_adapter3.jar | **C2 (SDK-on-classpath)** |

## Track B inventory (ELIMINATED)

All 12 share the structural fingerprint: outer pak has JSON manifest,
outer `content/` (dashboards/alertdefs/supermetrics/reports), nested
`adapter.zip` whose contents are `describe.xml` + `describeSchema.xsd`
+ resources + images **and no jars**. Container image lives on an
external registry (`projects.packages.broadcom.com` per Khriss
research) and is pulled by Cloud Proxy at install time.

| Pak | Inner manifest `name` |
|---|---|
| VCFOperationsvCommunity_0.2.8.pak | iSDK_VCFOperationsvCommunity (calibration ref) |
| application-insight-flopsar-vcfmp2026-0.6.1.pak | IndevopsFlopsarAdapter |
| datacenter-insight-uptimedc-2026-0.1.0.pak | UptimeDCAdapter |
| indevopsbrocadeswitches_0.0.3.pak | IndevopsBrocadeSwitches |
| ipam-insight-phpipam-vcfmp-2026.0.0.7.pak | IndevopsPHPIPAM |
| network-insight-checkpoint-vcf-2026-0.0.6.pak | IndevopsCheckPointSmartConsole |
| network-insight-cisco-prime-vcfmp-2026-0.0.7.pak | IndevopsCiscoPrimeInfrastructure |
| network-insight-juniper-vcfmp-2026.0.0.3.pak | IndevopsJunosSpace |
| scc-execution-adapter-vcf-2026.0.0.1.pak | IndevopsScriptControlCenter |
| stretched-cluster-insight-vcfmp-2026-0.0.2.1.pak | IndevopsStretchPerformanceMonitoringServiceEdition |
| tam-mpak_1.2.0.2_signed.pak | TAMManagementPack |
| uptime-checker-vcfmp-2026-0.0.3.pak | IndevopsUptimeKuma |

## Findings that altered the playbook

CLAUDE.md was updated this same date to reflect these.

1. **All paks use JSON manifest format** (VCF Operations 9.x / Aria
   Operations 8.18+). Manifest format is *not* a Track discriminator.
2. **Two-layer wrapper-and-inner-archive structure is universal**:
   every triaged pak is an outer zip containing
   `content/`+`manifest.txt`+`<adapter>.zip`. Triage must recurse
   into the inner archive — outer-level signals are misleading.
3. **Outer-pak `*.py` files are install/lifecycle hooks**, not
   adapter source. Same naming pattern (`post-install.py`,
   `preAdapters.py`, `validate.py`) appears in both Track B and
   Track C paks. Cannot be used as a Track signal.
4. **Released Track B paks do not contain Dockerfile, conf.yml, or
   Python source.** Those signals describe the *source repository*
   (vmware/vmware-vcf-operations-integration-sdk), not the released
   `.pak` artifact. Released Track B paks ship pure declarative
   content (describe.xml + dashboards) and no implementation. The
   container image is pulled separately by Cloud Proxy.
5. **Track A and Track B are structurally indistinguishable** at the
   pak level — both ship zero-jar inner archives. The deployment
   target (appliance mpb-adapter runtime vs. Cloud Proxy container)
   is resolved by the appliance via external metadata, likely keyed
   on `adapter_kind` registration. In this corpus, no clear Track A
   content pack was identified; the zero-jar shape defaulted to
   ELIMINATE-B per the vCommunity calibration anchor.
6. **The legacy "`lib/` contains exactly one jar = `mpb_adapter-*.jar`"
   rule matched zero paks** in either bundle. Likely an older
   packaging convention. Triage criteria revised in CLAUDE.md.
7. **Track C has two sub-shapes**:
   - **C1 (rich lib)** — typical marketplace and most devel paks.
     5–116 jars in `<adapter>/lib/` + custom adapter jar at inner
     root or in lib/. Examples: vim (102), AWSAdapter (108).
   - **C2 (SDK-on-classpath)** — observed for two paks, both
     internal/Broadcom-adjacent: `SupervisorAdapter` and
     `vmware-mpforaggregator`. Single adapter jar at inner root, no
     `lib/` directory; jar entries use `com/vmware/vcops/adapter/...`
     or `com/vmware/adapter/...` packages, relying on the
     appliance's runtime classpath. Same Track C contract; lighter
     packaging.
8. **vCommunity calibration was load-bearing.** Before downloading
   the Track B reference, the 12 zero-jar marketplace paks were on
   track to be misclassified as ELIMINATE-A. The reference
   established the correct shape unambiguously.

## What's next

Per CLAUDE.md workflow steps 1–4:

1. **Decompile selected adapters** into `analysis/decompiled/`. Start
   with the two priority targets:
   - `mpb-adapter` (use Navani's already-decompiled
     `inputs/from-devel/installed/mpb-adapter-installed.tar.gz` to
     skip the decompile step)
   - `vim` (use `vim-installed.tar.gz` from the same source)
2. **Per-adapter analysis notes** in `analysis/per-adapter/`. Cover
   lifecycle, resource model, metric collection, relationships,
   configuration UI rendering, packaging, classloading.
3. **Cross-validate** patterns observed in the priority targets
   against 3–5 secondary adapters drawn from the C1 set. Suggested
   first cross-validation pass: NSXTAdapter (modern Broadcom net),
   SrmAdapter (third-party-distributed, mature), VrAdapter
   (Broadcom internal, 86 lib jars), and one of the database
   adapters (mongodb or oracledatabase) for a contrasting
   non-VMware vendor.
4. **Draft SPEC sections** in `spec/` once enough cross-adapter
   evidence accumulates.

## Open questions for future passes

- Does any Track A content pack actually exist in the marketplace
  today, or has the path been fully superseded by Track B? (Khriss
  research suggests Track A's older packaging convention may be
  end-of-life.)
- The C2 sub-shape (`SupervisorAdapter`, `mpforaggregator`) — is the
  appliance's runtime classpath what the SDK base classes call
  "platform-provided dependencies"? Worth confirming during the
  decompile phase, since this affects how VCF-CF Tier 2 generates
  the adapter packaging.
- `vmware-mpforkubernetes` ships three adapter jars in one pak
  (`KubernetesAdapter3.jar`, `PKSAdapter.jar`, `TMCAdapter*.jar`).
  Multi-adapter packaging pattern — single pak, multiple registered
  adapter_kinds? Worth a focused note when we get to its analysis.
