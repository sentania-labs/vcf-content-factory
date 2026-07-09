# Per-instance Suite API credential contract (bytecode-proven)

**Question (the only one this file answers):** By what programmatic
contract does the platform/collector hand an adapter its per-instance
Suite API credential — the one the live Oracle autopsy
(`knowledge/context/investigations/oracle-stitch-autopsy-2026-07-02.md`) saw
acquire a token as the **adapter INSTANCE UUID** `48fb5d76-…` even
though Oracle's pak declares no vROps credential field?

**Verdict (one line):** The collector ships the adapter a **Java-
serialized `AdapterConfig`** whose non-transient field
`adapterCredentials` (`AdapterCredentialConfig{userName, password}`)
is pre-populated with `userName = <adapter instance UUID>` and a
platform-minted secret. aria-ops-core reads it via
`getAdapterConfig().getAdapterCredentials()` and turns it into a
Suite API user-token. **The accessor is SDK-public — a bare
`AdapterBase` adapter can read the exact same credential without any
aria-ops-core class.**

**Confidence:** High for the adapter-visible contract (Tier 1, local
jars, every claim is a `javap -p -c` quote below). The only INFERENCE
is *where the collector obtains the UUID string / provisions the
internal user* — that code is not in these jars (see §6).

Evidence rule honored: every factual claim below is `class + method +
bytecode quote`, or explicitly labeled **INFERENCE**.

Jars (`src/vcfops_managementpacks/adapter_runtime/`): `aria-ops-core-8.0.0.jar`,
`vrops-adapters-sdk-2.2.jar`, `alive_platform.jar`, `alive_common.jar`;
plus `aria-ops-core-7.1.1.jar` extracted from
`reference/references/tvs/OracleDatabase-9.1.0…pak` for version contrast. Tool:
`javap -p -c` / `-p`. Scratchpad-only extraction; **no lab objects
created, nothing to clean up.**

This file **corrects and completes** `casa-injected-vs-raw-client.md`
§4, which labeled the adapter-credentials branch "operator-supplied."
It is not operator-supplied — it is a distinct, platform-populated
slot (see §2).

---

## 1. `SuiteAPICredential.getSuiteApiAdapterCredential` — both branches

`com.vmware.tvs.vrealize.adapter.core.extensions.suiteapi.SuiteAPICredential`,
static factory `getSuiteApiAdapterCredential(AdapterConfig)`, 8.0.0:

```
 0: aload_0
 1: ifnull        11                       // AdapterConfig == null ...
 4: aload_0
 5: invokevirtual AdapterConfig.getAdapterCredentials()  // ... or creds == null
 8: ifnonnull     15
11: invokestatic  getSuiteAPIMaintenanceUserCredential   // FALLBACK branch
14: areturn
15: new           SuiteAPICredential                      // PRIMARY branch
19: aload_0; invokevirtual AdapterConfig.getAdapterCredentials()
23: invokevirtual AdapterCredentialConfig.getUserName()   // <-- username source
26: aload_0; invokevirtual AdapterConfig.getAdapterCredentials()
30: invokevirtual AdapterCredentialConfig.getPassword()   // <-- password source
33: invokespecial SuiteAPICredential.<init>(String,String)
36: areturn
```

So, verbatim from bytecode, in the **primary (adapter-credentials-
first) branch**:

- **username** = `adapterConfig.getAdapterCredentials().getUserName()`
- **password** = `adapterConfig.getAdapterCredentials().getPassword()`

The fallback branch (`getSuiteAPIMaintenanceUserCredential`) is the
`maintenanceuser.properties` file path already documented in
`casa-injected-vs-raw-client.md` §4 — reached **only** when
`AdapterConfig` is null or carries no `adapterCredentials`. Oracle
does **not** hit the fallback (live capture shows the instance-UUID
principal, not the maintenance user).

The `SuiteAPICredential` object itself is a dumb carrier — public
final `username`, `password`, `url` (default constant
`https://localhost/suite-api/`). It adds no logic; it only relays what
`getUserName()/getPassword()` returned.

**Closing the loop to the live capture** — `SuiteAPIClient` uses that
username as the token principal (`SuiteAPIClient`, 8.0.0):

```
57: ldc  "Acquiring Suite API token for user"
63/79/91: getfield SuiteAPICredential.username
96/108:   getfield SuiteAPICredential.password
120: new  com/vmware/ops/api/model/auth/UsernamePassword
132: UsernamePassword.setUsername(...)   // = credential.username
139: UsernamePassword.setPassword(...)   // = credential.password
157: UserAndAuthManagementClient.acquireToken(UsernamePassword)
```

Therefore the token principal == `AdapterCredentialConfig.userName`.
The live autopsy observed that principal == the adapter instance UUID,
which means **the collector serialized the instance UUID into
`AdapterCredentialConfig.userName`.**

---

## 2. The SDK carrier — `AdapterConfig.adapterCredentials`

`getAdapterCredentials()` returns
`com.integrien.alive.common.adapter3.config.AdapterCredentialConfig`
— an **SDK** (`vrops-adapters-sdk-2.2`) class, not an aria-ops-core one:

```
public class AdapterCredentialConfig implements java.io.Serializable {
  private final String userName;
  private final String password;
  public AdapterCredentialConfig(String, String);
  public String getUserName();
  public String getPassword();
}
```

It lives on `AdapterConfig` (`…adapter3.config.AdapterConfig extends
ConfigBase`):

```
private com.integrien...config.AdapterCredentialConfig adapterCredentials;   // NON-transient
public void setAdapterCredentials(AdapterCredentialConfig);
public AdapterCredentialConfig getAdapterCredentials();
```

Two facts make this a **platform-supplied, wire-delivered** slot:

1. **It is serialized.** `ConfigBase implements java.io.Serializable`
   (`javap` class decl), `AdapterConfig extends ConfigBase`, and
   `adapterCredentials` is a **plain (non-`transient`) field** — the
   only `transient` field on `AdapterConfig` is
   `partialCollectInterface`. So `adapterCredentials` rides the Java
   serialization of the config from the collector into the adapter
   process. (Java deserialization sets the private field directly; no
   setter call is needed — which is exactly why the next fact holds.)

2. **`setAdapterCredentials` has no caller in the platform jars.**
   Constant-pool grep (`grep -al`) for `setAdapterCredentials` across
   `alive_platform.jar` (3265 classes) and `alive_common.jar` returns
   **nothing**; the only callers are inside the SDK itself —
   `AdapterCache` and `DiscoveryParam`:
   - `AdapterCache` (config merge/refresh) copies it across configs:
     `…getAdapterCredentials()` immediately feeding
     `…setAdapterCredentials(…)` (bytecode offsets 105→109).
   - `DiscoveryParam.setAdapterCredentials` is a bare field store.

   Neither is an *origin*; both just carry an already-populated value.
   The origin is the deserialized wire payload (fact 1). **This is
   *not* a describe.xml credential-kind** (consistent with Oracle
   declaring only `oracle_database_credentials` and no vROps field).

**aria-ops-core reads it via the SDK accessor, not a private hook.**
`UnlicensedAdapter.onConfigure` (8.0.0):

```
41: useBuiltinSuiteApiClient()          // default: iconst_1 / ireturn -> true
44: ifeq 69
47: new  SuiteAPIClient
57: getAdapterConfig()                  // AdapterBase.getAdapterConfig()  (SDK-public)
60: SuiteAPICredential.getSuiteApiAdapterCredential(AdapterConfig)   // §1
63: SuiteAPIClient.<init>(AdapterLoggerFactory, SuiteAPICredential)
66: putfield suiteAPIClient
```

So the full contract is:
**collector → serialized `AdapterConfig.adapterCredentials`
{userName=<instanceUUID>, password=<secret>} → `AdapterBase.getAdapterConfig()`
→ `AdapterConfig.getAdapterCredentials()` → `AdapterCredentialConfig.getUserName()/getPassword()`.**

---

## 3. Reachability from a bare `AdapterBase` adapter — YES, SDK-public

Every link in the read chain is a **public** method on an **SDK**
(`vrops-adapters-sdk-2.2`) class:

- `AdapterBase.getAdapterConfig()` → `public AdapterConfig` (`javap -p`
  on `AdapterBase.class`).
- `AdapterConfig.getAdapterCredentials()` → `public AdapterCredentialConfig`.
- `AdapterCredentialConfig.getUserName()` / `getPassword()` → `public String`.

Therefore a framework adapter that extends **bare `AdapterBase`** (our
locked decision) can obtain the **identical** username/password the
collector minted for this instance with:

```java
AdapterCredentialConfig c = getAdapterConfig().getAdapterCredentials();
String user = c.getUserName();   // == adapter instance UUID (per live capture)
String pass = c.getPassword();
```

**No aria-ops-core class is required to READ the credential.** What is
aria-ops-core-private is only the *HTTP token client*
(`SuiteAPIClient` → `UserAndAuthManagementClient.acquireToken`) — i.e.
the code that *spends* the credential, not the credential itself. Our
framework already owns an equivalent token-acquire path
(`casa-injected-vs-raw-client.md` Deliverable 2); this credential is
the missing **principal** for it. Classification, precisely:

- Credential value: **SDK-public**, collector-injected into the
  serialized config, reachable by any `AdapterBase` adapter.
- Suite API token HTTP client: **aria-ops-core-private** (would need
  clean-room replication of just the `acquireToken` POST — which we
  already have).

**Consequence:** the instance-UUID principal that has resource-read
RBAC on the Cloud Proxy (the thing our maintenance-user path 403s
without) is **not** something we must provision or guess — it is
handed to us on `getAdapterConfig().getAdapterCredentials()`. This
plausibly closes the CP-403 identity gap without `ConfigUserUtils` or
the maintenance user, using only SDK-public surface.

---

## 4. Version contrast 7.1.1 vs 8.0.0

`getSuiteApiAdapterCredential(AdapterConfig)` in aria-ops-core
**7.1.1** (from the Oracle 9.1.0 pak) is **byte-for-byte identical** to
8.0.0: same null/`getAdapterCredentials()==null` guard → same
maintenance fallback, same `getUserName()/getPassword()` primary
branch (bytecode offsets 0–36 match exactly). `SuiteAPICredential`
fields (`public final username/password/url`) are identical. **No
version difference on this path.** The SDK carrier
(`AdapterConfig.adapterCredentials`, `AdapterCredentialConfig`) is the
same SDK 2.2 type in both paks.

---

## 5. Where the password comes from — from CODE

The password is **not** an env var, system property, or adapter-start
CLI arg. In the entire read path there is no `System.getenv` /
`System.getProperty` / file read — the value is the deserialized
`AdapterCredentialConfig.password` field on the `AdapterConfig` the
collector serialized to the adapter. (The only file-backed credential
in `SuiteAPICredential` is the *maintenance-user fallback*
`maintenanceuser.properties`, §1, which Oracle does not use.) So: the
secret arrives **inside the serialized config payload**, alongside the
instance-UUID username.

---

## 6. The one INFERENCE / residual (not in these jars)

**Where the collector gets the instance-UUID string and provisions the
matching internal Suite API user is NOT bytecode-provable from these
jars.** `setAdapterCredentials` has no caller in `alive_platform.jar`
/ `alive_common.jar`; population is by deserialization, so the
producing code lives in the collector core that *builds and serializes*
the `AdapterConfig` (a component not shipped in `adapter_runtime/`).
The claim "the collector mints a per-instance Suite API user named
after the adapter instance UUID and puts its credential in
`adapterCredentials`" is an **INFERENCE** — strongly supported by the
live capture (principal == instance UUID) plus the proven carrier
mechanism above, but the provisioning code itself was not disassembled.

**Unsupported-endpoint warning:** the downstream Suite API calls this
credential authorizes are the same internal `suite-api` surface that
requires the `X-Ops-API-use-unsupported` (a.k.a.
`X-vRealizeOps-API-use`) header; `AdapterCredentialConfig` /
`SuiteAPIClient` are Broadcom-internal, not a stable public SDK
contract, and may change between releases (7.1.1↔8.0.0 happen to
match).

**Follow-ups a live/cleanroom pull could still tighten:**
1. Confirm on a live CP that `getAdapterConfig().getAdapterCredentials()`
   is non-null for *our* pak's adapter instance (i.e. the collector
   injects the slot for third-party paks, not just first-party ones).
2. Confirm the injected instance-UUID token carries resource-read RBAC
   when minted on the Cloud Proxy (the identity residual from
   `casa-injected-vs-raw-client.md` — this contract supplies the
   principal but not proof of its CP roles).

---

## 7. Correction (2026-07-02, tooling): `getPassword()` is NOT a bare
field accessor — it decrypts via a class our framework does not ship

Live sandbox testing of the identity-v3 `AmbientCredential` change (`tooling`,
this session) disassembled `AdapterCredentialConfig.getPassword()`
end-to-end and found it does **not** simply return the stored field —
`javap -p -c` on `vrops-adapters-sdk-2.2.jar`:

```
public java.lang.String getPassword();
  Code:
     0: invokestatic  Method com/vmware/vcops/security/Crypt.getDefaultCrypt:()Lcom/vmware/vcops/security/Crypt;
     3: astore_1
     4: aload_1
     5: aload_0
     6: getfield      password:Ljava/lang/String;
     9: invokevirtual Method com/vmware/vcops/security/Crypt.decrypt:(Ljava/lang/String;)Ljava/lang/String;
    12: areturn
```

`getPassword()` decrypts the stored value via
**`com.vmware.vcops.security.Crypt`** — a *different* class than
`com.integrien.alive.common.security.Crypt`, the SDK-shipped decrypt path
this framework's `AmbientCredential` already uses for the
`automationuser.properties`/`maintenanceuser.properties` file candidates
(§0/pre-existing code, unrelated to this contract). This corrects §5 above,
which characterized the injected password as arriving "already plaintext…
no decryption needed" — that claim is **false** per this bytecode; the
plaintext only appears after `getPassword()`'s internal decrypt call, not
on the raw deserialized field.

**Consequence — a genuine open residual, not just style:**
`com.vmware.vcops.security.Crypt` is confirmed **absent** from every jar
this repo compiles or ships against
(`vrops-adapters-sdk-2.2.jar`, `aria-ops-core-8.0.0.jar`, `alive_common.jar`,
`alive_platform.jar`, `mpb_adapter3.jar`, `vmware-ops-api-stubs.jar` — a
constant-pool-string grep across `src/vcfops_managementpacks/adapter_runtime/`
returns nothing). If that class is likewise absent from the actual adapter
process's runtime classpath on some collector build (unconfirmed — it may
live in a platform-core jar available only at runtime, never shipped to
adapters, the same pattern `alive_platform.jar`/`alive_common.jar` already
follow for other internal types), calling `getPassword()` throws
**`NoClassDefFoundError`** — a `LinkageError`, not an `Exception` subtype.

**Framework mitigation (already applied):**
`AmbientCredential.tryInjectedCredential(AdapterConfig)` and
`SuiteApiStitchClient.Builder.safeGetAdapterConfig(VcfCfAdapter)` both
`catch (Throwable)`, not `catch (Exception)`, around this accessor chain —
a `catch (Exception)` would silently let `NoClassDefFoundError` escape and
crash the adapter cycle, violating the "any failure reading a source falls
to the next; nothing throws out of construction" guarantee identity v3
commits to. This was caught by the framework's own unit test sandbox
(`com.vmware.vcops.security.Crypt` is absent there too — the SKIP-labeled
assertions in `AmbientCredentialTest.testInjectedCredentialPreferredWhenPresent`
document the graceful-fallthrough behavior directly).

**Follow-up #3 for a live/cleanroom pull:** confirm whether
`com.vmware.vcops.security.Crypt` is resolvable on an actual collector's
adapter classpath. If it is not, the injected-credential source will
*always* silently fall through to automation/maintenance on every real
deployment (safe, per the mitigation above, but means the identity-v3
"prefer injected" ordering never actually activates) — worth confirming
alongside residuals #1/#2.
