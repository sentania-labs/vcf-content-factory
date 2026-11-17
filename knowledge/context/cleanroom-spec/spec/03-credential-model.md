# 03 — Credential Model

**Status**: DRAFT (pass 1 evidence — mpb-adapter only; expand when multi-credential vendor adapter observed)
**SDK source**: `CredentialKindDescribe`, `CredentialFieldDescribe`, `CredentialFieldMappingDescribe` (in `com.integrien.alive.common.adapter3.describe.*`); `CredentialConfig` (in `.config.*`)

## Concept

A **credential kind** is a named, structured set of fields the platform
collects from the user when configuring an adapter instance. Fields
can be cleartext or password-typed (the platform encrypts the latter
at rest and masks them in the UI / logs).

A credential kind is declared in `describe.xml`:

```xml
<CredentialKinds>
    <CredentialKind key="<cred-kind-key>" nameKey="<int>">
        <CredentialField
            dispOrder="<int>"
            enum="false"
            isAutomaticallyManaged=""
            key="<field-key>"
            nameKey="<int>"
            password="true|false"
            required="true|false"
            type="string"/>
        <!-- ... more fields ... -->
    </CredentialKind>
</CredentialKinds>
```

### `<CredentialKind>` attributes

- `key` — stable identifier referenced by `<ResourceKind>`'s
  `credentialKinds` (a ResourceKind can declare which credential
  kind(s) it requires)
- `nameKey` — i18n key for display name

### `<CredentialField>` attributes

- `dispOrder` — order in the UI form
- `enum` — `"true"` makes the field a fixed-choice dropdown. When
  `true`, nested `<enum>` elements specify the choices:
  ```xml
  <CredentialField enum="true" key="auth_mongos" ...>
      <enum default="true" value="Default" />
      <enum default="false" value="LDAP SASL" />
  </CredentialField>
  ```
  *Observed in mongodb (auth-method selection).*
- `isAutomaticallyManaged` — empty string in mpb-adapter; semantics TBD
  (likely a flag for credentials the platform rotates without user
  intervention)
- `key` — stable field name (used by the adapter to read the value)
- `nameKey` — i18n key
- `password` — `true` to mark as secret (encrypted at rest, masked in
  UI/logs)
- `passwordAlphabet` + `passwordLength` — generation hints for
  auto-generated credentials (empty when not auto-generated). Observed
  empty in mongodb.
- `required` — whether the user must fill it
- `type` — primitive type; observed value: `string`

## Runtime access

The credential is delivered to the adapter via `AdapterConfig`:

```
AdapterConfig.getAdapterCredentials() → AdapterCredentialConfig
ResourceConfig.getResourceCredential() → CredentialConfig
```

`CredentialConfig` (signature inventory pending pass 2) exposes the
per-field values keyed by `<CredentialField key="...">`.

## Multiple credential kinds per adapter

A single adapter kind may declare multiple `<CredentialKind>` elements
under `<CredentialKinds>`. The platform presents the choice to the
user when configuring an adapter instance.

*Observed in mongodb*: two kinds — `mongodb_credentials` (with auth)
and `mongodb_no_credentials` (placeholder for unauthenticated MongoDB
deployments). The user picks one at instance-creation time.

## Observed pattern: multi-slot credential holder

mpb-adapter declares a single credential kind
`ManagementPackBuilderAdapter_Custom_Credential` with **20+
key/value-pair slots** (`sensitiveCredKey1` /
`sensitiveCredValue1` through ...10+). Mix of `password="true"` (the
secret values) and `password="false"` (the key/label fields that name
each credential pair).

**Use case**: one MPB adapter instance can hold credentials for many
target systems referenced by an MPB design. The design refers to
credentials by their key name (the cleartext field), and the runtime
reads the matched password field.

This pattern is unusual among native adapters (most expose a fixed
set of credential fields like `username` / `password`). It's
specifically appropriate for **runtime-loaded design** adapters
where the set of target systems isn't known at install time.

**Implication for Tier 2**: vendor-specific native adapters generated
by VCF-CF typically declare a small fixed credential kind (the
specific auth scheme for the target system). The multi-slot pattern
is reserved for adapters that aggregate over many heterogeneous
targets.

## Open / pass 2+

- Full `CredentialConfig` API surface
- `CredentialFieldMappingDescribe` semantics (per signature: maps
  fields between credential kinds, possibly for credential reuse)
- How a `<ResourceKind>` declares which credential kind it requires
  (the `<credentialKinds>` sub-element in ResourceKind, observable
  once we see a vendor adapter with credential-requiring resource
  kinds)
- The `<enum>` cred-field pattern (fixed-choice dropdown)
- Auto-managed credential semantics
