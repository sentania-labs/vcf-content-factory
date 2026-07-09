# vim — per-adapter analysis

**Adapter kind**: `VMWARE_INFRA_MANAGEMENT` (per describe.xml AdapterKind and `adapter.properties` KINDKEY; the legacy pak/directory/class names are `vim` / `vim` / `ManagementAdapter`)
**Source pak**: `inputs/from-devel/paks/vim-902025137884.pak`
**Decompiled at**: `analysis/decompiled/vim/` (from `inputs/from-devel/installed/vim-installed.tar.gz`)
**Analysis date**: 2026-05-15
**Priority**: HIGH — most complex Broadcom MP (102 lib jars); SDK-limits calibration

## Structure (deployed form)

```
vim.jar                                                # entry-point — 792 classes, partially obfuscated
vim/
    conf/
        describe.xml                                   # 102 lines (compact!)
        describeSchema.xsd
        version.txt
        resources/messages/                            # 4 locales
        images/                                        # AdapterKind, ResourceKind icons
    lib/
        vrops-adapters-sdk-1.0.jar                     # ← adapter ships its OWN SDK
        vcops-common-1.0.jar                           # ← provides com.vmware.vrops.nmp.task
        vcops-suiteapi-internal-client-1.0.jar         # internal SuiteAPI client (NOT public)
        vcops-vlsi-1.0.jar
        vcenter-bindings-internal-8.0.2.jar            # vSphere VMODL — vendor SDK
        vim-vmodl-bindings-8.0.2.jar
        vlsi-client-8.0.2.jar, vlsi-core-8.0.2.jar     # vSphere VLSI
        wstClient-7.0.3.18452985.jar, admin-interfaces-7.0.3.18452985.jar
        grpc-{api,core,protobuf,netty-shaded,…}-1.64.0.jar  # gRPC stack (newer vCenter API)
        commons-{beanutils,codec,collections,configuration,digester,lang,validator}.jar
        guava-32.1.3-android.jar, gson-2.10.1.jar
        byte-buddy-1.14.15.jar, byte-buddy-agent-1.14.15.jar  # runtime bytecode (puzzling — flag below)
        + ~75 other deps
```

Sub-shape: **C1 rich-lib**, vendor-SDK-bundling. 102 lib jars including
the vSphere VMODL bindings (the "vendor SDK" for vSphere).

## `adapter.properties` (root of vim.jar)

```
ENTRYCLASS=com.vmware.adapter.management.ManagementAdapter
KINDKEY=VMWARE_INFRA_MANAGEMENT
```

**This is the platform's adapter-registration mechanism**. mpb-adapter
has the same file at its jar root. The platform reads this file to
locate the entry-point class.

## `pom.xml` (in vim.jar META-INF/maven/.../)

Embedded Maven POM. Key data:
- `groupId=com.vmware.adapter.management`,
  `artifactId=management-adapter`, `version=1.0`, `name=vim`
- `java.version=17`
- Uses lombok 1.18.30 (compile-time), TestNG 7.7.0, JUnit 4.13.2 + Jupiter 5.10.1,
  Mockito 2.23.0/2.28.2 (in deps), modelmapper 3.2.1, mapstruct 1.5.5.Final
- Spring 5.3.46 (likely as DI within the adapter — not the platform)
- Jackson 2.17.1 (JSON parsing)
- gRPC 1.64.0, Protobuf 3.25.3
- vcenter-bindings 8.0.2

The pom is build-time metadata; reading it stays inside the
clean-room boundary (it's not implementation source).

## What ManagementAdapter implements

```
public class ManagementAdapter extends AdapterBase
    implements TaskHandler, AsyncTaskHandler {

    // SDK lifecycle (overrides on AdapterBase)
    public onConfigure(ResourceStatus, ResourceConfig);
    public onDescribe();
    public onDiscover(DiscoveryParam);
    public onTest(TestParam);
    public onCollect(ResourceConfig, Collection<ResourceConfig>);
    public onStopCollection();
    public onDiscard();

    // SDK capability flag (override)
    public boolean isResourceRenameAllowed(ResourceKey);

    // New task system (com.vmware.vrops.nmp.task)
    public TaskResult onTask(TaskParam);
    public void onAsyncTask(UUID, TaskParam, AsyncTaskHandler$AsyncNMPCallback);

    // Public accessors (custom)
    public String getClusterId();
    public CollectResult getCollectResult();

    // Constants
    public static final String ADAPTER_FOLDER_NAME;
    public static final String ADAPTER_KIND_VMWARE;
    public static final String VIM_ADAPTER;
}
```

Overrides 7 SDK hooks (one more than mpb-adapter — `onStopCollection`).
Does NOT override: `onChangePassword`, `onCheckCertificate`,
`onStopResources`, `onRemoveResources`, `onConfigure(AdapterStatus,
Collection)`.

Implements `isResourceRenameAllowed(ResourceKey)` — declares the
capability (vim supports resource renaming).

**Crucially**: vim implements `TaskHandler` and `AsyncTaskHandler`
**from a different package** than the SDK's `ActionableAdapterInterface`:

| Protocol | Package | Implemented by | Method shape |
|---|---|---|---|
| **Legacy actions** | `com.integrien.alive.common.adapter3.action.ActionableAdapterInterface` | mpb-adapter | `onAction(ActionParam) → ActionResult` + `checkActionStatus(...)` async poll |
| **Modern tasks (NMP)** | `com.vmware.vrops.nmp.task.{TaskHandler, AsyncTaskHandler}` | vim | `onTask(TaskParam) → TaskResult` + `onAsyncTask(UUID, TaskParam, AsyncNMPCallback)` callback-style async |

The two protocols co-exist. **vim's `<Actions>` block in describe.xml
is empty** — modern NMP tasks are NOT declared in describe.xml. They
are dispatched on the runtime type of `TaskParam` (a Java
marker-interface hierarchy under `com.vmware.vrops.nmp.task.*` with
subdomains for `config/desiredstate/`, `diagnostics/evaluation/`,
`diagnostics/troubleshoot/`, `vcf/`, `appos/`).

## NMP task subsystem (in `vcops-common-1.0.jar`)

`com.vmware.vrops.nmp.task.*` has structured task-type families:

- `config.desiredstate.*` — desired-state config tasks
  (`ConfigDesiredStateTaskParam`, `ConfigDesiredStateTaskType`,
  `ConfigDriftResults` with `DriftStatus` enum)
- `diagnostics.evaluation.*` — diagnostic evaluation
- `diagnostics.troubleshoot.*` — troubleshooting
- `vcf.*` — VCF-specific
- `appos.*` — AppOS-specific

`TaskParam` and `TaskResult` are **marker interfaces** (no methods).
Each task type subclasses them with its own structured data.

**Routing pattern (inferred)**: the platform calls
`adapter.onTask(taskParam)`; the adapter uses `instanceof` to dispatch
to the appropriate handler. Subdomain packages suggest a hierarchical
naming convention.

## describe.xml shape

- AdapterKind: `VMWARE_INFRA_MANAGEMENT`, schema version 9
- 1 CredentialKind: `VidbCredentials` (OAuth2 client-credentials grant
  — `CLIENT_ID`, `CLIENT_SECRET`, `TRUSTED_ROOT_CERT`, `TLS_CERT`)
- 6 ResourceKinds (only 102 lines total — compact)
- Adapter instance is **`isSingleton="true"`** (NEW attribute observed)
  — only one configured instance per appliance
- 29 ResourceAttributes across all kinds
- 0 Actions (NMP tasks instead)

## Theories — pan-out / disprove ledger

### CONFIRMED — `adapter.properties` is the entry-point registration mechanism

Pass 1 open question resolved. Both mpb-adapter and vim ship
`adapter.properties` at the adapter jar's root with `ENTRYCLASS` and
`KINDKEY` lines. The platform reads it to find the
`AdapterInterface3` implementation and the matching describe.xml
adapter kind.

### CONFIRMED — adapters CAN pin SDK version

vim's lib/ contains `vrops-adapters-sdk-1.0.jar` (full
`AdapterBase` + `AdapterInterface3` classes — package-identical to
the platform's 2.2). mpb-adapter's lib/ does NOT contain the SDK;
it relies on the platform's runtime classpath. Both adapters work.

**Implication for VCF-CF Tier 2**: the generator can choose to
bundle a known-tested SDK version for ABI stability, or rely on the
platform's. Bundling is safer for generated adapters intended to
work across multiple platform versions.

### NEW + CONFIRMED — there are TWO task/action protocols

- **Legacy**: `ActionableAdapterInterface` (Integrien-namespaced), declared in describe.xml's `<Actions>`, polled async via `checkActionStatus`. mpb-adapter uses this.
- **Modern (NMP)**: `TaskHandler`/`AsyncTaskHandler` (vrops-namespaced), NOT declared in describe.xml, dispatched on TaskParam runtime type, callback-style async. vim uses this.

Tier 2 SPEC should document both. Generator should prefer NMP for new
adapters.

### NEW THEORY — implementation-heavy vs declaration-heavy adapter dichotomy

vim has a **compact describe.xml** (102 lines, 6 resource kinds, 29
attributes, 0 actions) but a **huge implementation** (792 classes, 102
lib jars). Compare to mpb-adapter or hypothetical Track A content
packs which are declaration-heavy and implementation-thin.

This is a major axis of variation for Track C adapters:
- **Imperative-heavy** (vim): describe.xml is structural skeleton; resource discovery, metric extraction, relationships, and tasks all live in Java code.
- **Declarative-heavy**: describe.xml carries the substantive model; Java code is glue.
- Most production adapters likely sit in between.

VCF-CF Tier 2 should be opinionated about which style it generates —
likely declaration-heavy with extension points for imperative logic
(matching the MPB philosophy but at the native-Java layer).

### PARTIALLY DISPROVEN — "vcops-suiteapi-client-*.jar is THE Suite API client"

mpb-adapter has `vcops-suiteapi-client-2.2-all.jar` (public client).
vim has `vcops-suiteapi-internal-client-1.0.jar` (internal client).
These are different artifacts. Refined theory: there are public and
internal Suite API clients; adapters choose based on the access level
they need. Internal probably exposes more (likely the way vim
accesses things only first-party Broadcom adapters can).

### CONFIRMED — "vim is the SDK-limits stress test" (CLAUDE.md hypothesis)

Evidence:
- 102 lib jars (most in corpus)
- 792 classes in entry-point jar (20x mpb-adapter)
- Uses both legacy lifecycle AND modern NMP tasks
- Implements optional capability `isResourceRenameAllowed`
- Bundles its own SDK version
- Multiple obfuscated subsystems (`certpassword`, `components/iam`,
  `components/A`, etc.)

If anything in the platform is reachable via Java code, vim probably
touches it.

### NEW THEORY — partial-obfuscation pattern: keep adapter-class names + data models clear; obfuscate internals

vim.jar contains:
- Clear: `ManagementAdapter`, `model.sddc.SDDCTaskModel`, `model.sddc.SubTask`, `endpoint.standard.VCEndpoint`, `endpoint.standard.NSXEndpoint`, etc.
- Obfuscated: `common.certpassword.A.class`, `B.class`, `C.class`, `components/A/A/A.class`, etc.

This selective obfuscation makes sense:
- Adapter entry-point class must be findable via `adapter.properties` (cannot obfuscate)
- Data model classes must serialize/deserialize cleanly (often need fixed names for JSON keys)
- Internal logic is fair game for obfuscation (Proguard/R8-style)

VCF-CF generated adapters will be clear (they're generated, not
secret); but the SPEC should note that production adapters in the
field may be obfuscated, which limits future RE.

## Tier 2 implications (VCF-CF native adapter SPEC additions)

1. **Entry-point registration** — every adapter jar must have
   `adapter.properties` at root with `ENTRYCLASS` and `KINDKEY`.
2. **Two task protocols** — section in SPEC documenting both legacy
   actions and modern NMP tasks; recommend NMP for new adapters.
3. **SDK pinning** — adapters can bundle their own SDK; classloader
   prefers lib/.
4. **NEW capability flag observed**: `isResourceRenameAllowed`. May
   need a separate "capability declarations" section in lifecycle.
5. **`<AdapterKind version>` schema attribute** — vim uses `version="9"`,
   mpb-adapter uses `version="8"`. The schema is versioned; pass 3
   should check what changed.
6. **`isSingleton="true"`** — ResourceKind attribute for adapter
   instances that should exist exactly once per appliance.
7. **`hidden="true"` and `readOnly="true"`** — UI hints on
   ResourceIdentifier elements.

## Open / pass 3+

1. **NMP task taxonomy** — full inventory of `com.vmware.vrops.nmp.task.*`. What task types exist? Are they extensible (third-party adapters declaring new task types) or platform-defined only?
2. **`vcops-vlsi-1.0.jar`** — VLSI is "VMware Local Services Interface" (legacy vCenter API). Likely cross-references with `vlsi-client-8.0.2.jar`. What does vcops add over vlsi-client?
3. **What's `byte-buddy` doing in production lib?** Could be runtime mock injection for testing (unusual to ship) or actual runtime bytecode (e.g., dynamic proxy generation).
4. **vim's 102-lib trim down**: how many of those 102 jars are *actually* used at runtime vs. transitive deps the build pulled in? Could be useful when generating a minimal-lib Tier 2 output.
5. **Maven `groupId=com.vmware.adapter.management`** — is there a public Maven repo serving adapter SDK artifacts? Khriss research said no published Maven coordinates were found; confirm.
6. **`adapter.properties` schema** — only seen `ENTRYCLASS` and `KINDKEY`. Are there other keys (e.g., `MIN_SDK_VERSION`, `REQUIRES_FEATURE`)?
7. **Schema version 9 changes** — what's new in describe.xml v9 vs v8? Probably the `isSingleton` attribute is one of them.

## Confidence

- Adapter registration mechanism: **High** (clear evidence in two
  independent adapters).
- NMP task protocol existence: **High** (interface signatures observed).
- NMP task semantics / dispatch: **Medium** (inferred from package structure; needs `onTask` body or actual dispatch logic for full confidence).
- Adapter packaging variability: **High** (two distinctly different sub-shapes observed).
