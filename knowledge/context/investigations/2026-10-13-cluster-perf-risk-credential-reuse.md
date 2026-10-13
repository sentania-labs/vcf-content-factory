# cluster-perf-risk: how it "piggybacks" on credentials, and whether compliance can do the same

**Question:** How does `gillaspy/cluster-perf-risk` get at vCenter data
without asking for a credential, and does that approach let our
compliance SDK adapter reuse the vCenter adapter instance's credential?

**Verdict:** It does not reuse any credential, and it never talks to
vCenter. It is a Python Integration SDK adapter with **no credential
kind at all**; it reads only the VCF Ops Suite API using the
platform-injected Suite API client (`AdapterInstance.get_suite_api_client()`),
and computes risk from metrics and properties the native vCenter
adapter (`VMWARE`) already collected. **It does not transfer** to an
adapter that must open its own vSphere SOAP session: nothing in that
path ever holds a vCenter secret.

**Source read:** https://github.com/gillaspy/cluster-perf-risk at commit
`6aa3e100877edaa686a9be315f8a1f8a9dde644c` (committed 2026-10-09 14:35
local), cloned read-only into the session scratchpad; nothing executed.
SDK library source: `vmware-aria-operations-integration-sdk-lib` 1.1.0
sdist from PyPI (the version range the pack pins), read only.

---

## 1. What kind of pak it is

Python Integration SDK (container-based) adapter, not MPB, not Java,
not content-only.

- `requirements.txt`: `vmware-aria-operations-integration-sdk==1.3.1`
- `adapter_requirements.txt`: `vmware-aria-operations-integration-sdk-lib~=1.1.0`
- `Dockerfile`: `FROM base-adapter:python-1.2.0`
- `config.json`: `"container_repository": "docker.io/gillaspy/cluster-perf-risk"`
- `commands.cfg`: `collect=/usr/local/bin/python app/adapter.py collect`
- `manifest.txt`: `"adapter_kinds": ["ClusterPerfRisk"]`

There is no hand-written `describe.xml` in the repo (only
`conf/describeSchema.xsd`); the SDK generates the describe from
`get_adapter_definition()`.

## 2. No CredentialKind is declared

`app/adapter.py`, `get_adapter_definition()` defines three instance
parameters (memory limit, monster-VM threshold, publish-to-native
enum) and then, lines 85 to 88:

```python
# No credential type is defined here. This adapter is self-referential:
# AdapterInstance.get_suite_api_client() automatically returns an
# authenticated client for the VCF Operations instance hosting this
# adapter, with no user-supplied host/username/password needed.
```

No `define_credential_type()` call exists anywhere in `app/`. So the
generated describe has no `<CredentialKinds>` and the adapter instance
has no credential. A repo-wide grep for `credential`, `password`,
`pyvmomi`, `SmartConnect`, or any non-Ops URL finds only these comments.

`test()` (lines 97 to 103) returns an empty `TestResult()`: there is
nothing external to validate.

## 3. How it authenticates, and to what

`app/adapter.py` lines 127 to 133:

```python
client = adapter_instance.get_suite_api_client()
if client is None:
    result.with_error(
        "No Suite API client available. This adapter must run on a "
        "Cloud Proxy with access to its own VCF Operations instance."
    )
```

Where that client comes from, in the SDK library
(`src/aria/ops/adapter_instance.py`, 1.1.0):

```python
cluster_connection_info = json.get("cluster_connection_info")
if type(cluster_connection_info) is dict:
    self.suite_api_client = SuiteApiClient(
        SuiteApiConnectionParameters(
            username=cluster_connection_info.get("user_name"),
            password=cluster_connection_info.get("password"),
            host=cluster_connection_info.get("host_name"),
        )
    )
```

and `src/aria/ops/suite_api_client.py` `get_token()`:

```python
"/api/auth/token/acquire",
json={
    "username": self.credential.username,
    "password": self.credential.password,
    "authSource": self.credential.auth_source,   # default "LOCAL"
},
```

So: the collector hands the container a platform-owned Ops
username/password in the `cluster_connection_info` block of the
per-call input JSON (only for `collect`; the docstring says it is
`None` for `test` and `get_endpoints`). The library mints a normal Suite
API token with it. The adapter's own instance credential, if it had
one, arrives separately in `credential_config` and is only ever the
instance's own credential.

**Which user and privileges:** not determinable from either source
tree; the library just forwards whatever `user_name` the collector
supplies, with `authSource` LOCAL. This matches the platform-internal
user pattern documented for the Java side
(`knowledge/context/api-surface/casa-injected-vs-raw-client.md`:
maintenance user vs `automationAdmin`). It is an **Ops** principal
with Ops RBAC, never a vCenter principal. Not verified live for the
Python container path.

## 4. Where its data comes from

Every data call is in `app/suite_api.py` and targets the Ops Suite API
only:

| Call | Purpose |
|---|---|
| `POST /api/resources/query` `{"resourceKind":[...],"adapterKind":["VMWARE"]}` | enumerate clusters and hosts the vCenter adapter discovered |
| `GET /api/resources/{id}/stats/latest?statKey=...` | latest value of a native metric |
| `GET /api/resources/{id}/properties` | native properties (config / inventory) |
| `GET /api/resources/{id}/relationships?relationshipType=CHILD` | cluster to host to VM walk |

Module docstring: "Self-referential: polls VCF Operations' own Suite
API for native cluster/host stats, classifies each into the risk-matrix
bands, and republishes a composite 0-100 risk score". With
`publish_to_native=true` it also writes write-only attributes back onto
the native `VMWARE` Cluster/Host objects (`target_definition` +
`RelationshipUpdateModes.PER_OBJECT`), still via the collect result, not
via vCenter.

So the "piggyback" is on the **data** the vCenter adapter already
collected, not on its **credential**.

## 5. Transferability to the compliance adapter

Does not transfer for anything compliance must read from vCenter
directly. Reasons, each already established:

1. The pattern never possesses a vCenter secret. The injected client is
   an Ops token, and Ops will not hand out another adapter's stored
   password: public `GET /api/credentials` / `{id}` return no password
   values; the internal `/internal/service/credentials` family is the
   separate service-credential store (outbound plugins, synthetic
   monitoring), not adapter credential instances.
2. Credential instances are scoped by `adapterKindKey` +
   `credentialKindKey` (see the `credential` schema in
   `reference/docs/operations-api.json`), so the `VMWARE` instance's
   credential cannot be attached to a compliance adapter instance.
3. No programmatic VCF SSO token flow to swap an Ops session for a
   vCenter session (`knowledge/context/api-surface/auth_vidb_oauth_flow.md`).

It **does** transfer for any check whose input the `VMWARE` adapter
already collects as a property. Evidence that some hardening inputs are
collected natively: the shipped default policy references
`config|security|security_account_lock_failures` on `HostSystem`
(`reference/references/AriaOperationsContent/vropstopdashboard/SampleDefaultPolicy.xml`
line 3613, a 6.x-era Security Configuration Guide symptom). Coverage is
a curated subset, not the full `HostAdvancedOptionManager` /
`extraConfig` key space, and current 9.x coverage was not inventoried
in this investigation.

## 6. Nearest workable options for compliance

In order of how much user friction they remove:

1. **Hybrid source (CPR pattern where it fits).** For every control
   whose value is already a native `VMWARE` property, read it through
   the Suite API with the platform principal (the door work in
   `casa-injected-vs-raw-client.md`) and drop it from the SOAP path.
   Only controls absent from native properties need a vCenter session.
   Requires a property inventory of a live HostSystem / VM /
   vCenter object against the controls CSV to size it.
2. **One credential, not one per vCenter.** The compliance design
   already specifies "Single instance, multi-vCenter ... shared SSO
   credentials" and "Auto-discover vCenters from VMWARE adapter
   instances" (`knowledge/designs/managementpacks/vcf-compliance-adapter.md`
   lines 57, 285 to 286). Discovering vCenter endpoints from `VMWARE`
   adapter instance identifiers is Suite API reachable; one SSO
   service account then covers every vCenter in the SSO domain. The
   user enters a credential once per SSO domain, not per vCenter.
3. **Pre-filled instance creation.** If per-vCenter instances stay,
   factory or UI tooling can create the compliance instance with the
   vCenter host copied from the `VMWARE` instance, leaving only the
   password for the user. The password itself can never be copied.

No option yields zero-touch credential reuse; that would need Ops to
release a stored secret, which no documented or internal endpoint does.
