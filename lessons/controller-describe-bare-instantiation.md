# Controller-side describe is bare instantiation — no platform injection exists

## Rule

During pak install the controller instantiates the adapter class with
**no-arg reflection** (`Class.newInstance()`) and calls `describe()`.
At that point the platform has NOT injected any adapter config, so
**`getAdapterKind()` returns null** and any other field that depends on
platform injection (credentials, identifiers, adapter-instance config)
is also null.

Never call `getAdapterKind()` or any other injected-state accessor
in the describe path. Always resolve the adapter kind from a static
constant stored at construction time.

## The failure mode (build 44, 3/3 install failures)

```
VcfCfAdapter.onDescribe: failed to load describe.xml from null (adapterKind=null)
→ NullPointerException: Cannot invoke AdapterDescribe.getKey() because conf is null
→ Could not construct adapter describes.
→ DistributedTaskInstallUninstallAdapters failed.
```

The framework `onDescribe()` added in build 44 (commit 750e0ee) called
`getAdapterKind()` to obtain the kind string for
`getAdapterDescribeFile(kind, "describe.xml")`. That method returns null
when `getAdapterInstResource()` is null — which it always is during
controller-side bare instantiation.

Build 43 was immune because `ComplianceAdapter` had its own `onDescribe()`
override that used the static `ADAPTER_KIND` constant directly, never
touching `getAdapterKind()`.

## What UnlicensedAdapter (v1) did

Bytecode inspection of `aria-ops-core-8.0.0.jar`:

```
UnlicensedAdapter.onDescribe():
  Constants.getAdapterHome()          // reads ADAPTER_HOME system property
  + File.separator
  + getAdapterDirectory()             // ABSTRACT — subclass returns "my_kind"
  + File.separator + "conf" + File.separator + "describe.xml"
  → AdapterDescribe.make(path)
```

`getAdapterDirectory()` was abstract in `UnlicensedAdapter`. Every
adapter subclass implemented it with a literal string return
(`return "vcfcf_compliance"`). No injection required.

`ADAPTER_HOME` is set by the platform for **both** the controller and the
collector. It is the only reliable path anchor that works in both contexts.
`AdapterBase.getAdaptersHome()` reads it (confirmed by bytecode).

## The fix (framework v2, 2026-06-10)

`VcfCfAdapter` stores the adapter kind key in a `private final String adapterKindKey`
field, set at construction time via two new protected constructors:

```java
protected VcfCfAdapter(String adapterKindKey) { … }
protected VcfCfAdapter(String adapterKindKey, String adapterDir, Integer instanceId) { … }
```

`onDescribe()` resolves the kind in this order:
1. `adapterKindKey` (constructor-stored — safe under bare instantiation)
2. `getAdapterKind()` (injected — null during controller-side describe)
3. Both null → `RuntimeException` with actionable message listing both sources

## Adapter adoption requirement

**Every adapter subclass must call the keyed constructors:**

```java
private static final String ADAPTER_KIND = "my_adapter_kind";

public MyAdapter() {
    super(ADAPTER_KIND);                       // keyed no-arg
}
public MyAdapter(String adapterDir, Integer instanceId) {
    super(ADAPTER_KIND, adapterDir, instanceId); // keyed three-arg
}
```

The kind key must match:
- The `key` attribute on `<AdapterKind>` in `describe.xml`
- The directory name in the pak layout:
  `<adaptersHome>/<key>/conf/describe.xml`

**Do NOT derive the key from `CommonConstants`** — those are display-name
strings, not filesystem tokens. See `lessons/sdk-constants-are-display-names.md`.

## Scope

Adapters affected (must update constructors before build 45):
- `ComplianceAdapter` — currently calls `super()` / `super(adapterDir, instanceId)`
  with no kind key; must switch to `super(ADAPTER_KIND)` / `super(ADAPTER_KIND, adapterDir, instanceId)`.
- Any future adapter (synology, unifi) migrated to v2 must follow the same pattern.

The framework default `onDescribe()` is the correct path for all v2 adapters.
No adapter should override `onDescribe()` unless it genuinely needs custom
describe construction — and if it does, it must use its own static constant,
never `getAdapterKind()`.

## Pattern name

"Controller-side describe trap" — the second injected-state trap after
`lessons/sdk-constants-are-display-names.md`. Both share the root cause:
code that assumes platform injection has occurred when it hasn't.

The describe-phase trap fires during **pak install** (controller instantiates
bare). The display-name trap fires during **runtime collection** (wrong path
derived from a constant that looks like a path but isn't).
