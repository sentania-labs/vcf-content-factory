# MPB Adapter JAR Reverse Engineering

Investigated 2026-05-08. Decompiled the per-adapter JAR from
`vcfops_managementpacks/adapter_runtime/mpb_adapter3.jar` (1796 bytes,
extracted from the Synology NAS MPB-built pak) and cross-referenced
against three community-authored MPB paks.

## Architecture: two generations

### Generation 1 (pre-9.0): monolithic adapter JAR

Found in: Rubrik-1.1.0.25.pak (234,789 bytes), GitHub-1.0.0.2.pak
(234,784 bytes), Broadcom Security Advisories-1.0.1.6.pak (240,151 bytes).

The adapter JAR contains the entire MPB runtime: hundreds of Kotlin
classes for HTTP collection, resource mapping, relationship creation,
event handling, and validation. The adapter entry class
(e.g. `MPBRubrikAdapter`) extends `UnlicensedAdapter` directly and
contains all lifecycle methods (configure, getTester, getDiscoverer,
getLiveDataCollector) inline. The class file alone is 14,985 bytes.

Package structure: `com.vmware.mpb.mpbrubrik.*` (all runtime classes
are re-packaged per adapter kind).

### Generation 2 (9.0.x): thin adapter JAR + shared runtime

Found in: our `mpb_adapter3.jar` (1796 bytes, from MPB-built Synology
NAS pak on VCF Ops 9.0.2).

The runtime is factored out into `lib/mpb_adapter-9.0.1-patch-1.jar`
(25.9 MB, 15,440 classes). The per-adapter JAR contains exactly ONE
class that extends `com.vmware.mpb.MPBAdapter` (an abstract class in
the shared runtime). The adapter class overrides two abstract methods
and provides two constructors.

## Decompiled source (equivalent Java)

```java
package com.vmware.mpb.mpbsynologynas;

import com.vmware.mpb.MPBAdapter;
import org.jetbrains.annotations.NotNull;

public final class MPBSynologyNASAdapter extends MPBAdapter {

    @NotNull
    public String getAdapterDirectoryName() {
        return "mpb_synology_nas_adapter3";
    }

    @NotNull
    public String getTemplateSHA() {
        return "d92a0933b2faffb59ad04bf74a3d00d7cd4197eb7b5407ab6f75f86feab5d5f3";
    }

    public MPBSynologyNASAdapter() {
        super();
    }

    public MPBSynologyNASAdapter(String instanceName, Integer instanceId) {
        super(instanceName, instanceId);
    }
}
```

That is the entire class. 842 bytes of bytecode.

## Annotated bytecode (full javap -c -p -verbose output)

```
Classfile MPBSynologyNASAdapter.class
  size 842 bytes, SHA-256 21d462d0b21ed66886ff96052df3a05b49f2a36265584e72d6f623f6056880a7
  Compiled from "MPBSynologyNASAdapter.java"
  major version: 50 (Java 6 target)
  flags: ACC_PUBLIC, ACC_FINAL, ACC_SUPER

Constant pool (30 entries):
   #1  Utf8    "com/vmware/mpb/mpbsynologynas/MPBSynologyNASAdapter"   *** CLASS PATH
   #2  Class   -> #1
   #3  Utf8    "com/vmware/mpb/MPBAdapter"                             (fixed)
   #4  Class   -> #3
   #5  Utf8    "SourceFile"                                            (fixed)
   #6  Utf8    "MPBSynologyNASAdapter.java"                            *** SOURCE FILE NAME
   #7  Utf8    "getAdapterDirectoryName"                               (fixed)
   #8  Utf8    "()Ljava/lang/String;"                                  (fixed)
   #9  Utf8    "RuntimeInvisibleAnnotations"                           (fixed)
   #10 Utf8    "Lorg/jetbrains/annotations/NotNull;"                   (fixed)
   #11 Utf8    "mpb_synology_nas_adapter3"                             *** ADAPTER DIRECTORY
   #12 String  -> #11
   #13 Utf8    "java/lang/String"                                      (fixed)
   #14 Class   -> #13
   #15 Utf8    "LocalVariableTable"                                    (fixed)
   #16 Utf8    "LineNumberTable"                                       (fixed)
   #17 Utf8    "StackMapTable"                                         (fixed)
   #18 Utf8    "Code"                                                  (fixed)
   #19 Utf8    "getTemplateSHA"                                        (fixed)
   #20 Utf8    "d92a0933b2faffb59ad04bf74a3d00d7cd4197eb7b5407ab6f..."  *** TEMPLATE SHA256
   #21 String  -> #20
   #22 Utf8    "<init>"                                                (fixed)
   #23 Utf8    "()V"                                                   (fixed)
   #24 NameAndType -> #22:#23                                          (fixed)
   #25 Methodref -> #4.#24  (MPBAdapter.<init>()V)                     (fixed)
   #26 Utf8    "(Ljava/lang/String;Ljava/lang/Integer;)V"              (fixed)
   #27 Utf8    "java/lang/Integer"                                     (fixed)
   #28 Class   -> #27
   #29 NameAndType -> #22:#26                                          (fixed)
   #30 Methodref -> #4.#29  (MPBAdapter.<init>(String,Integer)V)       (fixed)

Entries marked *** are the only ones that vary per adapter.
All other entries are identical across every MPB Gen-2 adapter JAR.
```

Methods (bytecode identical across adapters except for ldc operands):

```
getAdapterDirectoryName(): ldc #12; areturn
getTemplateSHA():          ldc #21; areturn
<init>():                  aload_0; invokespecial #25; return
<init>(String,Integer):    aload_0; aload_1; aload_2; invokespecial #30; return
```

## JAR internal structure

```
META-INF/MANIFEST.MF           -> "Manifest-Version: 1.0\n"
adapter.properties              -> ENTRYCLASS=com.vmware.mpb.<pkg>.<Class>\n
                                   KINDKEY=<adapter_kind>\n
com/vmware/mpb/<pkg>/<Class>.class
```

## How the base class uses these overrides

`MPBAdapter` (in `lib/mpb_adapter-9.0.1-patch-1.jar`) is written in
Kotlin and compiled from `MPBAdapter.kt`. Key methods:

```kotlin
abstract fun getAdapterDirectoryName(): String   // overridden by adapter
abstract fun getTemplateSHA(): String             // overridden by adapter

// Constructs the template path at runtime:
private fun getTemplateFilePath(): String =
    Constants.getAdapterHome() +    // "/usr/lib/vmware-vcops/user/plugins/inbound/"
    getAdapterDirectoryName() +     // "mpb_synology_nas_adapter3"
    "/conf/template.json"           // literal suffix

// In configure():
builderFile = passedBuilderFile ?: BuilderFile.Companion.read(getTemplateFilePath())

// In getTester(), getDiscoverer(), getLiveDataCollector():
// All pass getTemplateFilePath() and getTemplateSHA() to their constructors
// validateSHA defaults to true for production (no-arg constructor)
```

The SHA is validated by `MPBTester`, `MPBDiscoverer`, and
`MBPCollector` (note the typo in the VMware source: MBP not MPB).
When `validateSHA=true` and the SHA256 of the template.json on disk
does not match the hardcoded value, the adapter logs an error and
refuses to collect.

## Derivation rules

Given `adapter_kind` (e.g. `mpb_unifi_integration`):

| Field | Derivation | Example |
|---|---|---|
| Package slug | `adapter_kind` with underscores removed | `mpbunifiintegration` |
| Class name | `MPB` + CamelCase fragment + `Adapter` | `MPBUnifiIntegrationAdapter` |
| Full class path | `com/vmware/mpb/<slug>/<ClassName>` | `com/vmware/mpb/mpbunifiintegration/MPBUnifiIntegrationAdapter` |
| Adapter directory | `<adapter_kind>_adapter3` | `mpb_unifi_integration_adapter3` |
| Source file | `<ClassName>.java` | `MPBUnifiIntegrationAdapter.java` |
| Template SHA | SHA256 of `conf/template.json` | (computed from file) |
| ENTRYCLASS | dot-notation of full class path | `com.vmware.mpb.mpbunifiintegration.MPBUnifiIntegrationAdapter` |
| KINDKEY | `adapter_kind` verbatim | `mpb_unifi_integration` |

**The CamelCase fragment cannot be derived mechanically from adapter_kind
alone** -- "mpb_synology_nas" became "SynologyNAS" (all-caps NAS), not
"SynologyNas". This must be supplied as an explicit parameter.

## Current bug in the factory builder

`builder.py` line 1241: "ENTRYCLASS is left unchanged: it names a real
Kotlin class ... Only KINDKEY is a registration label that can be freely
set." This is correct for KINDKEY but ENTRYCLASS pointing to
`MPBSynologyNASAdapter` means:

1. The class still looks up `mpb_synology_nas_adapter3/conf/template.json`
   via `getAdapterDirectoryName()`.
2. On a box without the Synology pak installed, that path does not exist,
   causing `FileNotFoundException`.
3. Even when the UniFi pak's own directory exists at
   `mpb_unifi_integration_adapter3/`, the class never looks there.

The KINDKEY rewrite alone is necessary but not sufficient. The class
file itself must be regenerated per adapter kind.

## Recommended approach: constant-pool patching

The class file has a clean constant pool with exactly 4 variable strings
(marked *** above). All bytecode references use constant pool indices,
not byte offsets, so changing string lengths does not invalidate any
jump tables or instruction offsets.

**Algorithm (proven by POC):**

1. Read the reference class bytes from `mpb_adapter3.jar` entry
   `com/vmware/mpb/mpbsynologynas/MPBSynologyNASAdapter.class`.
2. Walk the constant pool, identify all Utf8 entries.
3. Replace the 4 variable strings with adapter-specific values.
4. Reassemble: header + patched constant pool + rest-of-file (verbatim).
5. Package into a JAR with:
   - `META-INF/MANIFEST.MF`
   - `adapter.properties` (ENTRYCLASS + KINDKEY)
   - The class at its new package path

The rest of the class file (access flags, method bytecode, attributes,
StackMapTable frames) copies through unchanged because the constant
pool index numbering is preserved -- the same 30 entries in the same
order, just with 4 different UTF-8 values.

**POC output (verified by javap):**

```
$ javap -c com/vmware/mpb/mpbunifiintegration/MPBUnifiIntegrationAdapter.class

public final class com.vmware.mpb.mpbunifiintegration.MPBUnifiIntegrationAdapter
    extends com.vmware.mpb.MPBAdapter {
  public String getAdapterDirectoryName();
    Code: 0: ldc "mpb_unifi_integration_adapter3"   2: areturn
  public String getTemplateSHA();
    Code: 0: ldc "aaa...aaa"   2: areturn
  public MPBUnifiIntegrationAdapter();
    Code: 0: aload_0   1: invokespecial MPBAdapter.<init>()V   4: return
  public MPBUnifiIntegrationAdapter(String, Integer);
    Code: 0: aload_0  1: aload_1  2: aload_2
          3: invokespecial MPBAdapter.<init>(String,Integer)V   6: return
}
```

**Implementation function signature for builder.py:**

```python
def generate_adapter_jar(
    adapter_kind: str,          # "mpb_unifi_integration"
    class_name_fragment: str,   # "UnifiIntegration"
    template_sha256: str,       # hex digest of conf/template.json
    reference_class_bytes: bytes,  # from mpb_adapter3.jar
) -> bytes:
    """Return complete JAR bytes for a per-adapter adapter3.jar."""
```

The function is ~60 lines of pure Python (struct + zipfile + io).
No external dependencies. No JDK required at build time.

## What this replaces

The current `_rewrite_adapter_properties()` in builder.py only patches
KINDKEY in adapter.properties. With constant-pool patching, the builder
would:

1. Patch the .class file (4 string replacements).
2. Rewrite adapter.properties (ENTRYCLASS + KINDKEY).
3. Rebuild the JAR with the new class at the correct package path.

This eliminates the need for per-adapter-kind MPB UI bootstrap
(README section "Adapter JAR gap" workaround steps 1-4).

## Template SHA considerations

The SHA256 hardcoded in the class must match the template.json shipped
in `conf/`. When the factory re-renders template.json from YAML, the
SHA changes. The builder must:

1. Render template.json content.
2. Compute its SHA256.
3. Embed that SHA in the generated class.

If the factory does not produce template.json (relying on design.json
or export.json instead), the SHA can be set to a known dummy value and
`validateSHA` will fail at runtime. The current Synology pak works
because `mpb_synology_nas_template.json` is shipped verbatim from the
MPB build and its SHA matches the hardcoded value exactly.

**For non-Synology adapters that lack a template.json:** the adapter
will fall back to `passedBuilderFile` if one is injected via the
2-arg constructor (used in testing), but the no-arg constructor (used
in production) will attempt to read template.json from disk and
validate its SHA. A missing or mismatched template.json causes
collection failure.

## Cross-reference: older MPB (Gen-1) considerations

The Gen-1 JARs (Rubrik, GitHub, Security Advisories) embed the entire
runtime. If a factory-built pak ships with a Gen-2 thin JAR but the
target VCF Ops instance has the Gen-1 runtime in its classpath, there
is no conflict -- the thin JAR's class extends `com.vmware.mpb.MPBAdapter`
which exists in the Gen-2 shared `lib/` JAR. The Gen-1 runtime classes
are under adapter-specific packages (e.g. `com.vmware.mpb.mpbrubrik.*`)
and do not collide.
