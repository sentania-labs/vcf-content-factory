# War Story: Synology DSM — No Common Key, MPB Can't Model It

**Target:** Synology DiskStation Manager (DSM) API  
**Verdict:** Tier 2 (Java SDK). Do not attempt Tier 1 (MPB).  
**Date:** 2026-05-19 (first Tier 2 MP end-to-end)

## The core problem

Synology's DSM API exposes storage volumes, system health, and Docker containers
through separate, unrelated endpoints:

- `/webapi/entry.cgi?api=SYNO.Core.System.Status` — system info
- `/webapi/entry.cgi?api=SYNO.Storage.CGI.Storage` — storage volumes
- `/webapi/entry.cgi?api=SYNO.Docker.Container` — Docker containers

These endpoints share no common identifier. A storage volume has no field that
links it to the system's health status. A Docker container has no field linking
it back to the disk it lives on.

MPB's chaining model is single-axis: a parent object feeds an identifier into
a child request, and the child response becomes the child object. There is no
"join unrelated collections on computed keys" mode. Without a joinable key,
MPB cannot model Synology's actual topology.

## What Tier 2 made possible

The Java SDK adapter ended up with 23 object types, 290+ metrics, cross-adapter
Datastore stitching (linking Synology Volumes to VMware Datastores via NFS
export path and NAA transform), a TraversalSpec for hierarchical browsing, and
custom icons. All collecting on the devel VCF Ops instance.

## The hard-won lessons from the first Tier 2 build

### Pak structure (install-time failures)

1. **Inner manifest.txt must be JSON.** The `adapters.zip` inner `manifest.txt`
   must be identical JSON to the outer manifest — not key=value text.

2. **`"adapters": ["adapters.zip"]` is required in manifest.** Without it,
   staging hangs indefinitely.

3. **`default.svg` must be a valid image.** 0-byte files rejected with
   "incorrect format--exiting."

4. **`adapters.zip` must duplicate `default.svg` and `eula.txt`.**

5. **Explicit ZIP directory entries are required.** `zipfile.writestr()` creates
   the file entry but NOT the parent directory entry. Every subdirectory needs a
   zero-byte directory entry.

6. **`vrops-adapters-sdk.jar` must be bundled in `lib/`.** Without it,
   `installSolution` fails in 14ms with empty `errorMessages`.

7. **Build number must increment on each rebuild.** Same version = platform
   skips JAR replacement.

### Adapter runtime (collection-time failures)

8. **Both constructors are required.** No-arg for `describe()` generation;
   `Constructor(String, Integer)` for instance startup.

9. **`getAutoDiscoveryEnabled()` must return `true`.** If `false`, every new
   resource is silently discarded. No error — perpetual "1 object, 0 new objects."
   This was the most insidious bug.

10. **Platform logger ≠ `java.util.logging`.** Use `AdapterLoggerFactory` with
    explicit `setLevel(INFO)`. The inherited `logger` field is WARN-filtered.

11. **`configure()` is the correct hook.** It's abstract on `UnlicensedAdapter`
    — there is no `super.configure()` to call.

### Cross-adapter stitching

12. **`Resource.addParent(foreignResource)` works** — but the foreign
    `ResourceKey` must have correct uniqueness identifiers. Query
    `/suite-api/api/resources`, match locally, use the returned `ResourceKey`.

13. **Cache the foreign resource lookup.** `ForeignResourceResolver` caches with
    configurable TTL (default 300s).

### API behavior

14. **Synology auth uses `_sid` query parameter, not cookies.** `SessionCookieAuth`
    doesn't fit. Append `&_sid=<token>` to every request URL directly.

15. **DNS round-robin can fail silently.** One dead IP causes intermittent
    `ConnectException`. `ManagedHttpClient.sendWithRoundRobin()` resolves all IPs
    and cycles on failure.

16. **`MetricKey.parseMetricKey()` hardcodes `isProperty = false`.** String
    properties are silently dropped. Use `VcfCfAdapter.addProperty()`.

17. **Relationships must be `rel.add()`'d to the ResourceCollection.** Setting
    `parent.addChild(child)` isn't enough if `parent` isn't added to the
    returned collection.

18. **Rebuild `vcfcf-adapter-base.jar` after framework changes.** The SDK
    builder compiles against a pre-built JAR. New methods won't be found until
    `adapter_framework/build-framework.sh` runs.

## What the design doc got wrong

- "ARIA_OPS kinds that push metrics onto VMWARE Datastore" — we push
  *relationships*, not metrics.
- Estimated adapter code at "~50-150 lines" — actual is ~700 lines.
- Assumed `SessionCookieAuth` would handle Synology auth.

## Build statistics (for calibration)

9 pak builds, 8 pak structure fixes, 3 runtime fixes before first successful
collection. 20 commits from first compilable build to feedback-ready. Budget
Tier 2 as roughly 5-10× the effort of a comparable Tier 1 MP.

## Reference files

- `content/sdk-adapters/synology/` — the adapter project
- `context/api-maps/synology-*.md` — API surface maps
- `context/tier2_architecture.md` — Tier 2 architecture doc
- `designs/managementpacks/synology-diskstation.md` — original design intent
