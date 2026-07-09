# SDK constants that look like paths are display names — never derive filesystem paths from them

## Rule

`CommonConstants.VCOPS` (and every other string field in
`com.integrien.alive.common.util.CommonConstants` that looks like it
might be a directory or path key) is a **product display-name string**,
not a filesystem path. Never use it to construct a file path.

## What it actually is

`javap -c` on `vrops-adapters-sdk-2.2.jar` (`CommonConstants` static
initializer) shows:

```
ldc  "VCF"                   → productNamePrefix
invokestatic loadNameProps    # may override from name.properties classpath resource
invokedynamic makeConcatWithConstants(productNamePrefix) → VCOPS
```

The `makeConcatWithConstants` bootstrap pattern produces `productNamePrefix + " Ops"`,
so `VCOPS = "VCF Ops"` (or whatever the product-name properties file contains).

Similarly, `USER_CONF`, `ALIVE_BASE`, `STORAGE`, `VCOPS_TEMP`, `COLLECTOR_CONF`,
and all similar-sounding fields carry their own field name as a literal string value
(e.g. `USER_CONF = "USER_CONF"`). These are symbolic keys used in message
formatting, not filesystem directory handles.

The SDK exposes **no install-directory or user-directory path constant** that
could be used to derive `maintenanceuser.properties` location.

## The failure mode

Using `CommonConstants.VCOPS` as a directory prefix:

```java
// WRONG — produces "VCF Ops/conf/maintenanceuser.properties" (nonsense relative path)
return Paths.get(CommonConstants.VCOPS.trim(), "conf", "maintenanceuser.properties");
```

The string is non-null and non-empty, so any null/empty fallback guard is
bypassed. The path resolves to a relative nonsense string; `Files.exists()`
returns false; the adapter logs:

```
maintenance credential file not found: VCF Ops/conf/maintenanceuser.properties
```

This is the live bug that blocked compliance build 43, collection cycle
2026-06-10T04:01:06Z on devel 9.0.2.

## The fix

Use the empirically proven hard-wired default path directly:

```java
static final String DEFAULT_PROPS_PATH =
    "/usr/lib/vmware-vcops/user/conf/maintenanceuser.properties";
```

Confirmed present and owner-readable (by the collector user `admin`) on
VCF Ops 9.0.2 (devel) and 9.1 (prod). See
`context/investigations/suiteapi_ambient_auth_devel_2026_06_09.md`.

Allow a system-property override for test harnesses
(`vcfcf.suiteapi.credential.path`). Do not attempt to derive the path from
any SDK constant.

## Minimum reproducer

```bash
$ javap -c -classpath vrops-adapters-sdk-2.2.jar \
    com.integrien.alive.common.util.CommonConstants 2>/dev/null \
  | grep -A5 "static {}"
# Shows: ldc "VCF" → productNamePrefix → VCOPS via makeConcatWithConstants
# Result: VCOPS = "VCF Ops"  — a display name, not a path.
```

## Scope

Applies to: `AmbientCredential.resolvePropertiesPath()` (fixed in
`src/vcfops_managementpacks/adapter_framework/src/com/vcfcf/adapter/stitch/AmbientCredential.java`
as of 2026-06-10).

Applies to: any future code that needs a platform directory path — do not
look in `CommonConstants` for it; use the known default and allow a
system-property override.
