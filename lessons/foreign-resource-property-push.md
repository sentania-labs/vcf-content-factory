# War Story: Foreign Resource Property Push — ResourceCollection Is a Dead End

**Target:** VCF Compliance Adapter — push compliance properties onto VMWARE HostSystem resources  
**Verdict:** Use `suiteAPIClient.getClient()` via reflection. Do NOT use `ResourceCollection.add()`.  
**Date:** 2026-05-27 (builds 1–10, one session)

## The core problem

A Tier 2 Java SDK adapter that uses ARIA_OPS stitching needs to push
properties and metrics onto resources owned by a different adapter
(VMWARE HostSystem). The obvious approach — add a DTO-backed `Resource`
with a foreign `ResourceKey` to the `ResourceCollection` returned from
`getCurrentMetrics()` — executes without error but silently drops the
data. The platform's collector pipeline filters the `ResourceCollection`
to resources owned by the calling adapter.

## What we tried (in order)

### Attempt 1: Synthesized Resource from ResourceKey (builds 3–4)

```java
ResourceKey vmwareKey = resolver.findByIdentifier("VMWARE", "HostSystem", ...);
Resource hostRes = new Resource(vmwareKey);  // synthesized from key
addProperty(hostRes, "VCF-CF Compliance|score", "95");
result.add(hostRes);
```

**Result:** Adapter logs "Pushed compliance data" but collector receives
`Number of resources: 0`. Properties never appear. The `Resource`
constructed from a bare `ResourceKey` isn't recognized by the platform
as a valid update to an existing foreign resource.

### Attempt 2: DTO-backed Resource from Suite API query (builds 7–9)

Following the vCommunity MP (Python SDK) pattern of querying Suite API
for `ResourceDto` objects and wrapping them:

```java
List<ResourceDto> dtos = suiteApiClient.getResources(
    Arrays.asList("VMWARE"), Arrays.asList("HostSystem"), ...);
Resource hostRes = new Resource(dto);  // DTO-backed
addProperty(hostRes, "VCF-CF Compliance|score", "95");
result.add(hostRes);
```

**Result:** Identical failure. Adapter logs "Pushed compliance data"
with correct UUIDs, but 0 compliance properties appear on the VMWARE
HostSystem. The `ResourceCollection.add()` path simply does not persist
data for foreign-keyed resources in the Java SDK's aria-ops-core
framework, regardless of how the `Resource` object was constructed.

### Attempt 3: Separate VCF Ops admin credentials + direct REST (build 5–6)

Bypassed the SDK entirely and POSTed directly to the Suite API REST
endpoint using separately configured VCF Ops admin credentials:

```
POST /suite-api/api/resources/{uuid}/properties
Authorization: OpsToken <separately-acquired-token>
```

**Result:** Would have worked, but requiring separate Ops admin
credentials on every adapter instance is wrong. No other MP does this.
The vCommunity MP uses the platform-injected `suite_api_client`
without extra credentials.

### Attempt 4: suiteAPIClient.getClient() reflection (build 10) ✓

The `SuiteAPIClient` class has a `getClient()` method that returns the
platform's internal `com.vmware.ops.api.client.Client` REST client —
already authenticated, no extra credentials. The `Client` class is on
the appliance classpath but NOT in our bundled JARs, so it must be
accessed via reflection:

```java
Object client = suiteApiClient.getClass()
    .getMethod("getClient").invoke(suiteApiClient);
Object resourcesClient = getResourcesClient(client);  // reflection
invokeAddProperties(resourcesClient, resourceId, propertyContents);
```

**Result:** `VCF-CF Compliance|profile_name = VMware_SCG_8.0` confirmed
on VMWARE HostSystem. Properties persist. No extra credentials needed.

## Why ResourceCollection doesn't work for foreign resources

The Java SDK's collection pipeline (in `aria-ops-core`) processes the
`ResourceCollection` returned from `LiveCollector.getCurrentMetrics()`
through several gates:

1. **Auto-discovery gate** — new resources not previously discovered by
   THIS adapter are filtered unless `getAutoDiscoveryEnabled()` returns
   `true` (which ours does, but a foreign VMWARE HostSystem was never
   "discovered" by our adapter)
2. **Adapter-kind scoping** — the collector process attributes returned
   resources to the calling adapter kind. A `ResourceKey` with
   `adapterKind=VMWARE` coming from a `vcfcf_compliance` collection
   cycle doesn't match and is silently dropped
3. **No error signal** — `result.add(foreignResource)` succeeds, the
   adapter's `logInfo("Pushed")` fires, but the data never reaches the
   platform's storage layer. The collector log shows
   `Number of resources: 0`.

This is different from the Python Integration SDK, where
`result.add_object(host_obj)` uses a different collection pipeline
that handles foreign resources correctly. And different from the MPB
runtime, which has a dedicated `HttpExternalResourcePropertyAdder`
class for cross-MP attachment.

## The working pattern for Tier 2 Java SDK

```java
// 1. Use ForeignResourceResolver for lookup (proven, uses injected suiteAPIClient)
List<ResourceDto> dtos = suiteApiClient.getResources(
    Arrays.asList("VMWARE"), Arrays.asList("HostSystem"),
    null, null, null, null);
// Index by VMEntityName or VMEntityObjectID (MOID)
// NOTE: suiteAPIClient returns null on the first collection cycle after
// adapter creation — it's not initialized until the second cycle.

// 2. Get the platform's authenticated REST client via reflection
Object client = suiteApiClient.getClass()
    .getMethod("getClient").invoke(suiteApiClient);

// 3. Discover the resources API on the Client (method names vary by version)
Object resourcesClient = findMethod(client, "resourcesClient", "resources");

// 4. Build PropertyContents/StatContents model objects via reflection
//    (classes are on appliance classpath, not in bundled JARs)
Class<?> contentsClass = Class.forName(
    "com.vmware.ops.api.model.property.PropertyContents");

// 5. Invoke addProperties on the resources client
invokeMethod(resourcesClient, "addProperties", resourceUuid, contents);

// 6. Return ONLY your own resources in the ResourceCollection
//    (ComplianceWorld, adapter instance — NOT the foreign hosts)
result.add(complianceWorldResource);
return result;
```

## Additional findings from this campaign

### suiteAPIClient timing

`this.suiteAPIClient` is null or not yet initialized on the **first**
collection cycle after adapter instance creation. It works reliably from
the second cycle onward. Guard with a null check and skip the stitching
push on the first cycle — the next cycle will catch up.

### ResourceDto.getIdentifier() requires reflection

`com.vmware.ops.api.model.resource.ResourceDto` is a stub class in the
bundled JARs (`aria-ops-core-8.0.0.jar`). Only the default constructor
is visible at compile time. The `getIdentifier()` method (which returns
the resource UUID string) exists only on the appliance runtime classpath.
Access it via reflection:

```java
String uuid = (String) dto.getClass()
    .getMethod("getIdentifier").invoke(dto);
```

### Property key separators are safe in Tier 2

The `|` restriction in `known_limitations.md` applies to Tier 1 MPB
metric **labels** only. Tier 2 SDK adapters push raw metric/property
keys and can use `|` freely. The vCommunity MP proves this with
production keys like `vCommunity|Guest OS|Services:{ServiceName}|Status`.
Our `VCF-CF Compliance|CIS|esxi-8.account-lockout|Actual` convention
is standard and correct.

### Build cadence

10 pak builds in one session. Budget Tier 2 stitching work at 2–3x
the effort of a non-stitching adapter. The stitching pipeline has no
error feedback — silent data loss is the failure mode, not exceptions.

## Reference files

- `content/sdk-adapters/compliance/` — the compliance adapter project
- `vcfops_managementpacks/adapter_framework/src/.../stitch/ForeignResourceResolver.java` — proven host lookup
- `context/cleanroom-spec/spec/07-relationships-cross-mp.md` — cross-MP attachment spec (aspirational, not fully accurate for Java SDK)
- `references/vmbro_vcf_operations_vcommunity/Management Pack/app/collectors/host/collectHostData.py` — working Python SDK pattern (different runtime, cannot be replicated in Java SDK)
- `context/investigations/action_wire_format_deep_dive.md` — action research (Phase 2 reference)
- `designs/managementpacks/vcf-compliance-adapter.md` — full design document
