# 17 — VCF-CF Framework Design Guidance (`vcfcf-adapter-base.jar`)

**Status**: DRAFT (Pass 26, 2026-05-16). Forward-looking architectural
guidance synthesized from the full investigation.

**Audience**: VCF-CF framework architects — the team responsible for
the `vcfcf-adapter-base.jar` library that all VCF-CF-generated Tier 2
adapters will extend. (For the IS-side documentation of what Tier 2
adapters look like once authored, see
[spec/15](15-tier2-handoff-for-vcf-cf.md). For the MPB-side Tier 1
story, see [spec/12](12-mpb-handoff-for-vcf-cf.md).)

**Scope**: Architectural design recommendations for the framework
itself. Concrete API shapes, MVP build order, design tenets, open
decisions. NOT an API reference (the framework doesn't exist yet);
this is the design-decision doc that would inform building it.

## TL;DR

1. **Adopt aria-ops-core's SPI directly** — `Tester` / `Discoverer` /
   `LiveCollector` / `HistoricalCollector` is the canonical
   decomposition, Broadcom-owned, and used by every MPB-generated pak
   already. Build VCF-CF's framework as a thin typed layer on top.
2. **The framework owns everything except source-system glue.** Auth
   strategies, pagination, retry, cache, cross-MP attachment,
   describe.xml emission, pak packaging — all in the framework.
3. **Per-pak code should be ~50–150 lines.** Mostly: config POJO,
   endpoint declarations, response→domain mapping, vendor SDK
   dependency. Everything else is inherited.
4. **The platform does NOT retry failed `collect()` cycles** (Pass 23
   empirical) — so the framework MUST provide a retry decorator;
   otherwise every adapter author would reinvent it.
5. **Build for Tier-1→Tier-2 promotion path** — a `BuilderFile`
   (spec/10) should be mechanically translatable into a thin Tier 2
   adapter using the framework, with TODO markers for the
   promotion-trigger reason that required the upgrade.

---

## 1. Layered architecture

Four layers, bottom-up. Lower layers are Broadcom-owned and frozen;
upper layers are VCF-CF's design space.

```
┌─────────────────────────────────────────────────────────────────────┐
│ Layer 4: PER-PAK adapter (VCF-CF-generated or author-written)       │
│   class ServiceNowAdapter extends VcfCfAdapter<ServiceNowConfig>    │
│     - parseConfig() / buildClient() / discoverer() / liveCollector()│
│     - typed @JsonProperty POJOs for ServiceNow responses            │
│     - declarative describe.xml via framework's builder DSL          │
│   target size: ~50–150 lines of code                                │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 3: vcfcf-adapter-base.jar (THIS DOC'S SUBJECT)                │
│   abstract class VcfCfAdapter<C> extends UnlicensedAdapter          │
│     • typed config binding                                          │
│     • pluggable auth strategies (8+ pre-built)                      │
│     • pluggable pagination (5+ patterns)                            │
│     • retry/backoff decorator (closes the no-platform-retry gap)    │
│     • typed cache helper over AdapterBase.adapterCache              │
│     • cross-MP attachment helpers (ForeignResources DSL)            │
│     • relationship fluent builder over the 18-method API            │
│     • describe.xml typed builder (covers all 19 top-level elements) │
│     • Maven/Gradle plugin for pak packaging                         │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 2: aria-ops-core (Broadcom-owned, ship as-is)                 │
│   abstract class UnlicensedAdapter extends AdapterBase              │
│     - getTester() / getDiscoverer() / getLiveDataCollector() /      │
│       getHistoricalDataCollector()                                  │
│   See spec/01 § Adapter abstraction frameworks for full SPI.        │
├─────────────────────────────────────────────────────────────────────┤
│ Layer 1: vrops-adapters-sdk (Broadcom-owned, on appliance classpath)│
│   class AdapterBase implements AdapterInterface3                    │
│     - ~70 helper methods; Semaphore-locked collect() per instance   │
│   See spec/01 for full enumeration.                                 │
└─────────────────────────────────────────────────────────────────────┘
```

**Critical decision**: never patch or fork Layer 2 (aria-ops-core).
Treat it as a stable third-party dependency. All VCF-CF additions
live at Layer 3.

**Why aria-ops-core?** Three reasons documented in earlier passes:
1. Broadcom-owned (originally BlueMedora, acquired ~2018), so no
   third-party-feel framework risk.
2. Used by every MPB-generated pak already — Tier 1 paks running on
   the same appliance are also using it. Adopting it for Tier 2 means
   one SPI across both tiers.
3. The three-axis collection split (separate `getCurrentMetrics` /
   `getEvents` / `getRelationships`) produces cleaner adapter code
   and clearer error boundaries than a single `onCollect()` doing
   everything.

The trade-off: aria-ops-core feels framework-y vs. raw AdapterBase
extension. Spec/15 § 1.4 documents Option A (AdapterBase direct,
Broadcom-internal style) vs. Option B (aria-ops-core wrapper); this
doc recommends **Option B for VCF-CF specifically**, since the goal
is minimizing author-side code and aria-ops-core does that more
aggressively than AdapterBase alone.

---

## 2. What belongs in the framework (one-time, never per-pak)

The `spec/12 § 6` Tier-1→Tier-2 promotion-trigger list is exactly the
menu of what the framework needs to provide. If a capability is
listed there as "promote to Tier 2," that's because Tier 1 can't
express it — meaning every Tier 2 adapter that needs it would
otherwise re-implement it from scratch. Pre-build it once.

### 2.1 HTTP transport + auth strategies

Most Tier 2 adapters will be HTTP-based (the ones that aren't are the
JDBC/gRPC/SNMP outliers, which need vendor-specific transport
anyway). The framework should provide:

| Capability | Implementations to ship at MVP | Rationale |
|---|---|---|
| Auth strategy SPI | `AuthStrategy` interface | Pluggable for vendor-specific schemes |
| Built-in: Basic | Yes | Universal baseline |
| Built-in: Bearer token | Yes | Most modern REST APIs |
| Built-in: OAuth2 client-credentials with refresh | Yes | Enterprise SaaS APIs |
| Built-in: OAuth2 authorization-code with refresh | Defer to v2 | Less common in adapter context |
| Built-in: Kerberos / SPNEGO | Yes | Required for AD-integrated enterprise systems |
| Built-in: AWS SigV4 | Yes if AWS coverage is in scope | Required for AWS APIs |
| Built-in: HMAC per-request | Defer to v2 | Niche but pre-built shape is clear |
| Built-in: mTLS with cert renewal | Yes | Required for some enterprise APIs |
| Custom escape hatch | `AuthStrategy.custom()` | For everything else |

**Why this is framework territory**: "Auth beyond Basic / SessionToken
/ Custom" is the #2 promotion trigger in spec/12. Every adapter that
needs OAuth2 shouldn't re-implement token refresh, expiry handling,
and race-condition-safe refresh under load.

### 2.2 Pagination

| Pattern | MVP? | Notes |
|---|---|---|
| Offset / limit | Yes | Most REST APIs |
| Page / per-page | Yes | Common alternate spelling |
| Cursor (next-token in body) | Yes | AWS, GCP, modern APIs |
| Link-header (RFC 5988 `Link: <url>; rel=next`) | Yes | GitHub, GitLab, many vendor APIs |
| Range-header | Defer to v2 | Rare in monitoring contexts |

`Paginator` SPI; per-instance pluggable. Adapter author declares
"this endpoint paginates by X" and the framework owns the loop.

**Why**: "Pagination beyond OFFSET/PAGES" is in the spec/12 promotion
trigger list.

### 2.3 Retry / backoff

**Required by Pass 23 finding: the platform does NOT retry failed
`collect()` cycles**. Errors are swallow-and-log at the platform
level; the adapter must own its own retry.

Framework provides:
- `RetryPolicy` builder: max attempts, backoff (exponential / linear /
  jittered), retry-on-status-codes, retry-on-exception-types
- `RetryableCollect` decorator that wraps `onCollect()` and applies a
  policy
- Per-strategy retry: HTTP calls can have their own retry inside the
  cycle (vs. retrying the whole cycle)

Default policy: 3 attempts, exponential backoff with jitter,
retry-on `5xx | 429 | IOException`. Override per-adapter.

### 2.4 Per-instance state cache

`AdapterBase` provides `adapterCache` as an untyped helper. The
framework should provide a typed wrapper:

```
TypedCache cache = new TypedCache(adapterCache);
CachedValue<RemoteSchema> schema = cache.lazy("remoteSchema",
    () -> client.fetchSchema(),
    Duration.ofMinutes(15));

// In onCollect():
RemoteSchema s = schema.get();   // hits remote on first call + after TTL; cached otherwise
```

Plus invalidation hooks: `cache.invalidate("remoteSchema")` from
`onConfigure()` so config changes flush cached state.

**Why**: NSXTAdapter3 (Pass 5) demonstrates per-instance caching at
scale. Every long-lived adapter does this. Typed wrapper prevents
`Map<String, Object>` casts.

### 2.5 Cross-MP attachment

The mechanism is documented in spec/07: construct a `ResourceKey` for
the foreign resource and push metrics/properties/relationships against
it. The framework should provide a typed helper:

```
ForeignResources foreign = vcfCfFramework.foreignResources();

ResourceKey vm = foreign.vSphereVm(
    entityName: "web-server-01",
    objectId:   "vm-1234",
    vcId:       "VC-UUID",
    instanceUuid: "501-abcd...");

pushProperty(vm, "myProperty", "myValue");   // metric write, fire and forget
relationships()
    .parent(myAdapterResource)
    .child(vm)
    .push();
```

Pre-built helpers for the most-cross-referenced foreign kinds (per
spec/07): vSphere VirtualMachine (14 paks reference it), HostSystem,
Datastore, Cluster, NSX LogicalSwitch, etc. Each helper enforces the
correct identifier-tuple shape so adapter authors can't get cross-MP
identity wrong.

Catch-all: `foreign.byKey(adapterKind, resourceKind, identifiers)` for
adapters that need to attach to something not pre-built.

### 2.6 Relationships fluent builder

The 18-method Relationships API (spec/07) is powerful but
surface-heavy. Wrap in fluent builder:

```
relationships()
    .parent(host)
    .children(vmList)
    .withLabel("hosts")
    .namespace("vsphere.runtime")
    .push();   // chooses the right underlying method (add vs set vs merge)

relationships()
    .replace(parent: cluster)
    .children(memberHostList)
    .withLabel("members")
    .push();   // uses set-replacement semantics
```

Builder picks add vs set vs single vs bulk under the hood. Authors
don't need to learn all 18 signatures.

### 2.7 describe.xml typed builder DSL

The most-edited surface in any adapter project. Currently authors
write XML by hand (error-prone, no compile-time validation).
Framework provides a typed builder targeting XSD 6.3.0 from spec/02a:

```
describe()
    .adapterKind("ServiceNow")
        .credentialKind("ServiceNowCredentials")
            .field("username", type: STRING, required: true)
            .field("password", type: STRING, required: true, password: true)
        .resourceKind("Incident", type: ResourceType.GENERAL)
            .identifier("sysId", required: true)
            .attribute("priority", dataType: DataType.INTEGER, defaultMonitored: true)
            .attribute("state", isProperty: true)
            .attribute("assignedTo", isProperty: true)
        .resourceKind("ServiceNowInstance", type: ResourceType.ADAPTER_INSTANCE)
            .credentialKind("ServiceNowCredentials")
    .build();
```

Coverage: all 19 top-level `<AdapterKind>` children documented in
spec/02a. Including:
- `<Methods>` / `<Actions>` (spec/14)
- `<CapacityDefinitions>` (spec/09)
- `<OOTBPolicies>` (spec/09)
- `<Faults>` (spec/14)
- `<LaunchConfigurations>` (spec/14)
- `<TraversalSpecKinds>` (spec/07)
- `<SymptomDefinitions>` / `<AlertDefinitions>` (spec/08)

Validation at build time, not runtime. Compile-time-safe enum values
for all type/subType codes (spec/08 § RESOLVED type/subType table).

### 2.8 CollectResult plumbing helpers

`addMetricData` overload selection is verbose. Provide one-liners:

```
push(resource).metric("cpu.usage", 42.5);
push(resource).property("hostname", "web-01");
push(resource).event(MyEvent.LOGIN_FAILED, "user=jdoe");
push(resource).status(ResourceStatus.OK);
```

Behind: dispatches to the correct `addMetricData` / `addEvent` /
`setResourceStatus` overload, handles timestamps + locale strings.

### 2.9 Lifecycle defaults

Sensible defaults for the boilerplate lifecycle methods:

- `test()` — defaults to "run the configured `Tester`" (aria-ops-core
  pattern). Adapter overrides if they need a different ping.
- `discard()` — defaults to "release the HTTP client + flush cache".
- `checkCertificate()` — defaults to "defer to platform TrustManager".
- `changePassword()` — defaults to "update config, ping with new
  cred, succeed if ping succeeds".

Adapter authors override only what they need.

### 2.10 Action plumbing

Annotation-driven instead of `ActionableAdapterInterface` boilerplate:

```
@Action(key = "RebootIncident", targets = "Incident")
public ActionResult rebootIncident(
        @ActionParam("reason") String reason,
        ActionContext ctx) {
    client.reboot(ctx.resource.identifier("sysId"));
    return ActionResult.ok();
}
```

Framework wires the interface, parses parameters, builds the
`<Actions>` describe.xml entry, dispatches at runtime. Adapter author
writes one method per action.

### 2.11 Pak packaging plugin

The bundle that ships to an appliance. Maven/Gradle plugin that:
1. Compiles the per-pak Java/Kotlin source
2. Resolves dependencies; bundles into `lib/`
3. Generates `<adapter>/conf/describe.xml` from the typed builder
4. Generates `<adapter>/conf/version.txt`, `<adapter>/adapter.properties`
5. Generates outer-pak `manifest.txt`
6. (Optional) signs the pak — Pass 23 confirmed unsigned works
   without admin override, so default is unsigned
7. Produces a Track-C-shaped `.pak` (per spec/16 install pipeline +
   spec/13 packaging layout) ready to install

Standalone task: `mvn vcfcf:pak` produces `target/<name>.pak`. CI/CD
pipelines can drop these directly into the appliance install API.

---

## 3. What stays per-pak (the irreducible minimum)

Only the source-system specifics. For a ServiceNow adapter:

```java
// ~80 lines total
public class ServiceNowConfig {
    public String baseUrl;
    public String tenant;
    public OAuth2ClientCredentials oauth;
    public Duration pollInterval;
}

@JsonProperty class Incident {        // response model
    public String sysId;
    public String priority;
    public String state;
    public String assignedTo;
}

public class ServiceNowAdapter extends VcfCfAdapter<ServiceNowConfig> {
    @Override
    protected ServiceNowConfig parseConfig(AdapterConfig raw) {
        return ConfigBinder.bind(raw, ServiceNowConfig.class);
    }

    @Override
    protected HttpClient buildClient(ServiceNowConfig c) {
        return HttpClients.builder()
            .baseUrl(c.baseUrl)
            .auth(AuthStrategy.oauth2ClientCredentials(
                tokenUrl: c.baseUrl + "/oauth_token.do",
                clientId: c.oauth.clientId,
                clientSecret: c.oauth.clientSecret))
            .pagination(Paginator.offsetLimit(limit: 100))
            .retry(RetryPolicy.default())
            .build();
    }

    @Override
    protected Discoverer discoverer(ServiceNowConfig c, ResourceConfig instance) {
        return new ServiceNowDiscoverer(client, c);
    }

    @Override
    protected LiveCollector liveCollector(ServiceNowConfig c, ResourceConfig instance) {
        return new ServiceNowLiveCollector(client, c);
    }
}

// Discoverer + LiveCollector: maybe 30-50 lines each of straight
// HTTP-fetch-then-map-to-resources logic
```

Plus a `describe.xml`-builder block (could be in the same class):

```java
@Override
protected DescribeAdapterKind describe() {
    return describe()
        .adapterKind("ServiceNow")
            .resourceKind("Incident")
                .identifier("sysId", required: true)
                .attribute("priority", isProperty: true)
                .attribute("state", isProperty: true)
                /* etc */
        .build();
}
```

Plus per-pak `pom.xml`:

```xml
<dependencies>
    <dependency>
        <groupId>com.vmware.vcfcf</groupId>
        <artifactId>vcfcf-adapter-base</artifactId>
        <version>1.0.0</version>
    </dependency>
    <!-- vendor SDK if applicable -->
</dependencies>
<build>
    <plugins>
        <plugin>
            <groupId>com.vmware.vcfcf</groupId>
            <artifactId>vcfcf-maven-plugin</artifactId>
            <executions>
                <execution>
                    <goals><goal>pak</goal></goals>
                </execution>
            </executions>
        </plugin>
    </plugins>
</build>
```

That's a complete VCF-CF-generated Tier 2 adapter. ~150-200 lines of
Java + ~30 lines of Maven config. Compare to a hand-written native
Tier 2 adapter (1000-5000 lines typical for production cases).

---

## 4. MVP build order

If you're starting from scratch, build the framework in this order
for maximum-leverage-per-week:

| Phase | Effort | Deliverable | Why this order |
|---|---|---|---|
| **1. Skeleton + aria-ops-core wiring** | ~1 week | `VcfCfAdapter<C>` base class, end-to-end build of a trivial "ping URL, emit 1 resource" pak that installs successfully on a test appliance | Validates the whole stack: layer 3 + layer 4 + packaging plugin + describe.xml emission + install pipeline (spec/16). De-risks the integration first. |
| **2. describe.xml typed builder DSL** | ~2–3 weeks | Coverage of all 19 top-level elements per spec/02a, with compile-time validation | Highest-leverage piece — it's what authors interact with most. Without this, every adapter author writes XML by hand. |
| **3. HTTP client + auth strategies (Basic, Bearer, OAuth2-client-credentials, Kerberos)** | ~2 weeks | Pluggable `HttpClient` builder + 4 built-in auth strategies | Unblocks the most common adapter targets (REST APIs with enterprise auth). |
| **4. Cache + retry + pagination helpers** | ~1 week | `TypedCache`, `RetryPolicy`, 4 paginator implementations | Smaller scope but each adapter author would otherwise reinvent. |
| **5. Cross-MP helpers + relationship fluent builder** | ~1 week | Typed `ForeignResources` for top 5 foreign kinds + relationship DSL | Closes the cross-MP attachment story (spec/07). |
| **6. Action plumbing** | ~1 week | `@Action` annotation + dispatcher | Enables adapters that expose user-invokable operations. |
| **7. Tier-1→Tier-2 promotion translator** | ~2 weeks | Tool that takes a `BuilderFile` and produces a starter Tier 2 project | The killer feature — designer hits a promotion trigger, framework spits out a starter adapter. |

**Estimated MVP**: 10-12 weeks for a team of 2-3 engineers to ship a
framework that materially reduces Tier 2 adapter authoring cost. After
that, the framework grows incrementally based on author feedback —
adding auth strategies, paginators, foreign-kind helpers as adapters
demand them.

---

## 5. Design tenets

These should be enforced via code review, not just documented:

1. **No required boilerplate.** Every framework method has a sensible
   default. An author should be able to write `class FooAdapter extends
   VcfCfAdapter<FooConfig> { ... }` with no overrides and have a
   compile-successful (if useless) adapter. Each override pays for its
   existence.
2. **No magic.** Annotation-driven is fine for actions, but the rest
   should be explicit method overrides. Authors reading someone else's
   adapter shouldn't need to learn framework internals to understand
   what the code does.
3. **Escape hatches everywhere.** Every typed helper lets the user
   drop down to raw SDK. `getCollectResult()`, `getSDKAdapterBase()`,
   `getRawHttpClient()` all accessible. The framework is opinionated by
   default but never coercive.
4. **Vendor-neutral.** Framework ships zero vendor dependencies. AWS
   SDK, Azure SDK, vCenter SDK — all per-pak Maven dependencies, never
   in the framework jar.
5. **Versioned and pinnable.** Per-pak builds pin a
   `vcfcf-adapter-base.jar` version explicitly. Framework upgrades are
   opt-in per pak. Avoids the "we upgraded the framework and 200 paks
   broke" scenario.
6. **Standalone testable.** Authors can `mvn test` their adapter
   against a mock framework without an appliance. Framework provides
   an in-memory `CollectResult` recorder + `MockAppliance` test
   harness for assertion.
7. **Per-pak code is human-readable.** Generated code (from Tier-1
   promotion or any future codegen path) should look like
   hand-written code. No marker classes named `__Generated_${kindkey}`,
   no opaque dispatch tables. The generated adapter should be one a
   human could maintain after the codegen tool is gone.
8. **Single-source-of-truth describe.xml.** The typed builder is the
   only place adapter authors declare their resource model — never
   hand-edit XML. The builder validates against XSD 6.3.0 at compile
   time (per spec/02a).

---

## 6. Open decisions to make up-front

Two decisions that shape everything else; both should be settled
before MVP work starts:

### 6.1 Kotlin or Java for adapter source?

**Context**: MPB's runtime is Kotlin. aria-ops-core is Kotlin.
`AdapterBase` is Java. The JVM is bilingual; both work seamlessly.

**Recommendation**: **Java by default, Kotlin supported**.
- Java has broader internal talent pool, especially in enterprise
  contexts. Less ramp-up.
- Generated code from the Tier-1 promotion path is easier to keep
  human-readable in Java (fewer linguistic features to chase).
- The framework itself can be written in either; Java is the safer
  default given the audience.
- Kotlin support comes for free — the framework's typed builders
  work as smoothly in Kotlin DSL syntax as in Java method chains.
  Power users can opt in.

### 6.2 Library-only vs. DSL + codegen?

**Context**: Two flavors for the author experience:

- **(A) Library only**: Authors write Java/Kotlin source and import
  the framework. Standard Maven/Gradle project. Familiar to any JVM
  developer.
- **(B) DSL + codegen**: Authors declare adapters in a higher-level
  DSL (YAML / TOML / Kotlin DSL); VCF-CF code-generates the source.
  Closer to Tier 1 (MPB)'s UX where users author declaratively.

**Recommendation**: **Ship (A) first; layer (B) on top later if there's
demand**.
- (A) is simpler, more flexible, and lets adapter authors use full
  JVM tooling (debugger, profiler, test framework, IDE).
- (B) is valuable but requires careful design — the DSL has to cover
  the full surface or it leaks into "drop down to Java for the hard
  cases" anyway, which is fine but means (A) is the foundation.
- (A) → (B) is the natural evolution. (B) → (A) is messy because DSL
  authors stop being able to read what they generated.

### 6.3 Open question for later: vendor-bundling policy

When a vendor SDK (e.g., AWS SDK ~50MB, vCenter SDK ~30MB) is a hard
dependency, where does it live?
- **Per-pak** (the simple answer): each pak bundles its vendor SDK in
  `lib/`. Pak size grows but classloader isolation (spec/13) keeps
  versions clean.
- **Shared in `common-lib/`** (the optimal answer): vendor SDKs ride
  along with the appliance's shared classpath. But appliance ops
  control `common-lib/`, not VCF-CF, so this requires Broadcom
  buy-in.

Default to per-pak. Revisit if pak sizes become an operational pain.

---

## 7. Cross-references

### Foundation sections (start here)
- [`spec/00-overview.md`](00-overview.md) — Track C runtime model + vocabulary
- [`spec/01-adapter-lifecycle.md`](01-adapter-lifecycle.md) — `AdapterInterface3` + `AdapterBase` + aria-ops-core SPI (the framework's Layer 1 + 2)
- [`spec/15-tier2-handoff-for-vcf-cf.md`](15-tier2-handoff-for-vcf-cf.md) — consolidated Tier 2 picture (what adapter authors are building)

### Surface-specific sections (the framework's typed-builder DSL coverage)
- [`spec/02a-describe-xsd-canonical.md`](02a-describe-xsd-canonical.md) — XSD 6.3.0 grammar (target for the describe.xml builder)
- [`spec/03-credential-model.md`](03-credential-model.md) — credential kinds (auth-strategy bindings)
- [`spec/05-resource-model.md`](05-resource-model.md) — ResourceKind / Attribute / Identifier
- [`spec/06-metrics-units-expressions.md`](06-metrics-units-expressions.md) — metric keys + units
- [`spec/07-relationships-cross-mp.md`](07-relationships-cross-mp.md) — 18-method Relationships API + cross-MP attachment
- [`spec/08-alerts-symptoms-recommendations.md`](08-alerts-symptoms-recommendations.md) — Symptom/Alert grammar
- [`spec/09-capacity-and-policy.md`](09-capacity-and-policy.md) — CapacityDefinitions + OOTBPolicies
- [`spec/14-ui-and-operational-surfaces.md`](14-ui-and-operational-surfaces.md) — Methods/Actions/Faults/LaunchConfigurations/PowerState/Icon

### Platform-mechanics sections (the framework's pak packaging plugin builds against)
- [`spec/13-classloading-and-classpath.md`](13-classloading-and-classpath.md) — per-pak classloader isolation + `common-lib/`
- [`spec/16-platform-install-and-signing.md`](16-platform-install-and-signing.md) — install pipeline + empirical signing behavior

### MPB / Tier 1 (for the promotion-path translator)
- [`spec/10-mpb-builderfile-schema.md`](10-mpb-builderfile-schema.md) — BuilderFile vocabulary (translator input)
- [`spec/11-mpb-designer-wire-format.md`](11-mpb-designer-wire-format.md) — designer wire format + Pass 25 grammar bounds
- [`spec/12-mpb-handoff-for-vcf-cf.md`](12-mpb-handoff-for-vcf-cf.md) — Tier 1 handoff + § 6 promotion-trigger list

---

## 8. Open follow-ups for this design doc

1. **Concrete API mockups** — this doc sketches shapes but doesn't
   nail down package names, class names, method signatures. When MVP
   work starts, the first deliverable should be a concrete `interface
   AuthStrategy { ... }` etc. that the framework can be built against.
2. **Test harness specification** — `MockAppliance` is mentioned but
   not specified. Define what it asserts, how it surfaces failures,
   what fixtures it ships with.
3. **Tier-1→Tier-2 promotion translator** — the design is "mechanical
   translation of `BuilderFile` to framework-shaped Tier 2 source."
   Worth a separate spec section to enumerate the mapping rules per
   `BuilderFile` element. Defer until phases 1-6 of the build order
   are done.
4. **Per-pak generated vs. authored** — VCF-CF may want to support
   both "fully generated from a UI" and "authored by hand" Tier 2
   adapters. Same framework either way; the codegen tool just produces
   what an author would have written. Worth a UX design pass.
