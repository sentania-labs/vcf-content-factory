# Lessons Learned: Synology DiskStation SDK Adapter (2026-05-19)

First Tier 2 (native Java SDK) management pack built end-to-end in the
VCF Content Factory framework. Started from zero, ended with 23 objects,
290+ metrics, cross-MP Datastore stitching, custom icons, and a
TraversalSpec — all collecting on the devel VCF Ops instance.

This document captures the hard-won lessons for future adapter authors
and framework maintainers. Every numbered item cost at least one failed
build, failed install, or silent runtime failure to discover.

## Pak structure lessons (install-time)

These prevent the `.pak` from installing at all. Each was discovered
by reading appliance logs after a failed install.

1. **Inner manifest.txt must be JSON.** The `adapters.zip` inner
   `manifest.txt` must be identical JSON to the outer manifest —
   not key=value text. The install handler parses it as JSON.

2. **`"adapters": ["adapters.zip"]` is required in manifest.** The
   STAGE phase locates the adapter archive via this key. Without it,
   staging hangs indefinitely.

3. **`default.svg` (pak icon) must be a valid image.** The validate
   phase calls `verifyPakIconFileFormat()` and rejects 0-byte files
   with "incorrect format--exiting." Use a real SVG.

4. **`adapters.zip` must duplicate `default.svg` and `eula.txt`.**
   The validate phase checks for these inside the inner zip.

5. **Explicit ZIP directory entries are required.** Python's
   `zipfile.writestr("path/file", data)` creates the file entry but
   NOT the parent directory entry. The platform's
   `SyncAdapters.extractFiles()` uses `Files.copy()` which requires
   parent dirs to exist. Every subdirectory needs a zero-byte
   directory entry (`"resources/"`, `"<adapter>/conf/"`, etc.).

6. **`vrops-adapters-sdk.jar` must be bundled in `lib/`.** Despite
   being on the appliance shared classpath, every working SDK adapter
   (HPE SimpliVity, Pure Storage, NSX, vSAN) bundles it. Without it,
   `installSolution` fails in 14ms with empty `errorMessages`.

7. **`eula.txt` should contain the license text.** Empty EULA shows
   a blank acceptance page in the UI.

8. **Build number must increment on each rebuild.** Same
   version = platform reports "Folder digests are not different" and
   skips JAR replacement. The old buggy code persists.

## Adapter runtime lessons (collection-time)

These prevent the adapter from starting, discovering, or collecting
even after a successful install.

9. **Both constructors are required.** The analytics engine uses
   `Class.newInstance()` (no-arg) for `describe()` generation. The
   collector uses `Constructor(String, Integer)` for instance startup.
   Missing the no-arg → `InstantiationException`, adapter kind not
   registered. Missing the two-arg → `NoSuchMethodException`, adapter
   won't start.

10. **`getAutoDiscoveryEnabled()` must return `true`.** If `false`,
    `UnlicensedAdapter.processMetrics()` silently drops every new
    resource returned by `getCurrentMetrics()`. The adapter runs,
    metrics cycle, but zero resources ever register. Perpetual
    "1 object, 0 new objects." This was the most insidious bug —
    no error anywhere, just silent discard.

11. **Platform logger ≠ `java.util.logging`.** The adapter log files
    (`SynologyAdapter_3008.log`) use Log4j via `AdapterLoggerFactory`.
    The inherited `logger` field from `UnlicensedAdapter` is
    WARN-filtered by the appliance root config — INFO messages are
    silently dropped. Use `getAdapterLoggerFactory().getLogger()` with
    explicit `setLevel(INFO)`. JUL and `System.err` go to
    `collector-wrapper.log` — useful for debug, wrong for production.

12. **`configure()` is the correct hook.** It's abstract on
    `UnlicensedAdapter` — there is no `super.configure()` to call.
    `onConfigure()` runs first (framework setup), then calls
    `configure()`. The `ResourceConfig` passed to `configure()` has
    all identifiers populated.

## Cross-MP stitching lessons

13. **`Resource.addParent(foreignResource)` works for cross-adapter
    relationships** — but the foreign `ResourceKey` must have the
    correct uniqueness identifiers. You cannot construct a foreign
    ResourceKey with only a non-unique identifier (like
    `DataStrorePath`) and expect the platform to find the match.

14. **Use the Suite API to look up foreign resources.** Query
    `/suite-api/api/resources` for the target adapter/resource kind,
    match by identifier value locally, then use the returned
    `ResourceKey` (with all uniqueness identifiers) for the
    relationship. This is how Pure Storage's `VSphereResourceUtil`
    works. The `ForeignResourceResolver` framework helper encapsulates
    this pattern.

15. **The `SuiteAPIClient` is available on `UnlicensedAdapter`.** The
    `suiteAPIClient` field provides access to the Suite API from inside
    the adapter — no external auth or URL configuration needed. Use
    `suiteAPIClient.getClient()` for raw API access.

16. **Cache the foreign resource lookup.** Datastore inventory doesn't
    change every 5 minutes. `ForeignResourceResolver` caches by
    (adapterKind, resourceKind, identifierName) with a configurable
    TTL (default 300s).

## Icon lessons

17. **SVG is the universal format.** All adapters (native and SDK) use
    SVG for `conf/images/`. PNG appears only in `TraversalSpec/` on
    some native adapters. Use `viewBox="0 0 400 400"` and `#0098c7`
    palette to match the existing library style.

18. **Icon filenames match ResourceKind keys exactly.** No
    adapter_kind prefix needed. `SynologyDisk.svg`, not
    `synology_diskstation_SynologyDisk.svg`.

## API/infrastructure lessons

19. **DNS round-robin can fail silently.** If a hostname resolves to
    multiple IPs and one is unreachable, `java.net.http.HttpClient`
    picks randomly. A single dead IP causes intermittent
    `ConnectException: No route to host`. The
    `ManagedHttpClient.sendWithRoundRobin()` fallback resolves all IPs
    and cycles through them on `ConnectException`.

20. **Synology auth uses `_sid` query parameter, not cookies.** The
    framework's `SessionCookieAuth` doesn't fit. The adapter manages
    auth directly by appending `&_sid=<token>` to every request URL.

21. **The framework needs a JSON parser.** Every real adapter parses
    API responses. `SimpleJson` (recursive-descent, zero-dep) is now
    in the framework at `com.vcfcf.adapter.json.SimpleJson`.

## What the design doc got right

- Hybrid architecture (INTERNAL + cross-adapter stitching) was the
  right call. Pure ARIA_OPS wouldn't work (NAS health metrics have
  no home on VMware objects). Pure INTERNAL misses the unified view.
- The Tier 2 trigger assessment was correct: cross-endpoint joining,
  custom response transforms (NAA), session-based auth.
- The API maps were thorough and accurate. Every endpoint, field
  name, and join key worked as documented.
- The stitching research (NAA transform, NFS export path) was
  verified end-to-end with zero corrections needed.

## What the design doc got wrong

- "ARIA_OPS kinds that push metrics onto VMWARE Datastore" — we
  don't push metrics, we push relationships. The unified view comes
  from clicking through the relationship graph, not from metrics
  appearing on the Datastore's timeseries.
- Estimated adapter code at "~50-150 lines" — actual is ~700 lines.
- Assumed `SessionCookieAuth` would handle Synology auth — it doesn't.
- Did not anticipate the SSD cache object (v1 scope said "defer to
  v2") — but the data was already in `load_info`, so we added it.

## Framework components built during this exercise

| Component | Package | Lines | Purpose |
|---|---|---|---|
| `ForeignResourceResolver` | `c.v.a.stitch` | ~150 | Cross-MP resource lookup via Suite API |
| `RelationshipBuilder` | `c.v.a.stitch` | ~100 | Fluent relationship construction |
| `SimpleJson` | `c.v.a.json` | ~230 | Zero-dep JSON parser |
| `ManagedHttpClient` DNS retry | `c.v.a.http` | ~50 | Round-robin IP fallback |
| `VcfCfAdapter` logging | `c.v.a` | ~30 | AdapterLoggerFactory + INFO override |
| `sdk_builder.py` fixes | tooling | ~100 | 8 pak structure fixes |

## Session statistics

- **20 commits** from first compilable build to feedback-ready state
- **9 pak builds** (1.0.0.1 through 1.0.0.9)
- **8 pak structure fixes** before the first successful install
- **3 runtime fixes** (constructors, auto-discovery, logging)
- **3 framework helpers** added to `vcfcf-adapter-base.jar`
- **6 new SVG icons** added to the library
- **23 resources** collecting on devel with 290+ metrics
- **3 cross-MP Datastore relationships** confirmed

## Files reference

| File | Purpose |
|---|---|
| `content/sdk-adapters/synology/` | The adapter project |
| `vcfops_managementpacks/adapter_framework/src/` | Framework Layer 3 source |
| `context/tier2_architecture.md` | Living architecture doc (updated throughout) |
| `context/api-maps/synology-*.md` | API surface maps (5 files) |
| `context/api-maps/synology-vcfops-stitching.md` | Stitching join recipes |
| `designs/managementpacks/synology-diskstation.md` | Original design intent |
| `context/cleanroom-spec/spec/01-adapter-lifecycle.md` | Updated with Pass 24 discovery findings |
| `context/cleanroom-spec/spec/16-platform-install-and-signing.md` | Pak install pipeline reference |
