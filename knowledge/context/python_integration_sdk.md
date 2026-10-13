# Python Integration SDK (container adapters): factory reference

**What this is.** The working reference for VMware/Broadcom's VCF Operations
Integration SDK, Python flavour: the `mp-init` / `mp-test` / `mp-build` CLI
plus the `aria.ops` adapter library. A Python pack is a container image (the
adapter) plus a small `.pak` that points at it. Written 2026-10-13 so a Python
pack author agent and a reviewer can work without rereading the SDK source.

**Status in the factory.** Python packs are a secondary vehicle. The factory's
own Tier 2 path is Java (`tier2_architecture.md`). We meet Python packs as
third-party forks we contribute to (`managed_paks.md`, third-party section):
`content/sdk-adapters/vsanhostmetrics/` and
`content/sdk-adapters/cluster-perf-risk/` are the worked examples here.

**Sources and citation prefixes.**

| Prefix | Path | Version |
|---|---|---|
| `sdk:` | `reference/references/vmware-vcf-operations-integration-sdk/` (official repo, clone at commit `9619df8`, 2026-09-28) | CLI 1.3.1 (`pyproject.toml:10`), lib 1.1.0 (`lib/python/setup.cfg:3`), base image `python-1.2.0` (`vmware_aria_operations_integration_sdk/container_versions.json`) |
| `lib:` | shorthand for `sdk:lib/python/src/aria/ops/` | lib 1.1.0 |
| `cli:` | shorthand for `sdk:vmware_aria_operations_integration_sdk/` | CLI 1.3.1 |
| `srv:` | shorthand for `sdk:images/base-python-adapter/` (the REST server baked into the base image) | base image 1.2.0 |
| `docs:` | shorthand for `sdk:docs/` (rendered at https://vmware.github.io/vmware-vcf-operations-integration-sdk/sdk/latest/) | |

The clone matches the PyPI releases (`vmware-aria-operations-integration-sdk`
1.3.1, `vmware-aria-operations-integration-sdk-lib` 1.1.0, both the newest on
PyPI as of 2026-10-13) except for docstring typos and the replacement of
`pkg_resources` with `importlib.metadata` in the CLI entry points; no
behavioural difference was found by `diff -r`. Line numbers below are the
clone's. Nothing in the SDK was executed for this document; it is a source
read plus today's investigations.

---

## 1. The container adapter contract

### 1.1 Runtime shape

- One container per adapter instance (account), long-lived, run by the
  collector on a **Cloud Proxy**. A throwaway container is started for each
  Validate Connection and for the save of a new account
  (`docs:references/architecture.md` §Adapter Container Lifecycle).
  Containerized packs run only on a Cloud Proxy and need VCF Operations 8.10+
  on-prem (`docs:get_started.md` §VCF Operations).
- Inside the container: a Flask/connexion REST server (`srv:swagger_server/`)
  that, per request, spawns the adapter as a **fresh subprocess**
  (`srv:swagger_server/controllers/controller.py:161-273`). The adapter is
  therefore stateless between calls; files written to the container survive
  only until the container is recreated (instance restart, collector move)
  (`docs:references/architecture.md` §Calling the Adapter/Collection Code).
- Server listens on 443 with `/etc/ssl/certs/dockerized.crt` + `.key` if
  present, else 8080 (`srv:swagger_server/__main__.py:24-33`). The pak tells
  the collector which: `API_PROTOCOL=https` / `API_PORT=443`, or `http` /
  `8080` when built with `mp-build -i` (`cli:mp_build.py:489-494`).
- Memory: the collector reads the special adapter-instance identifier
  `container_memory_limit` (MB); if the describe does not define it, the
  container gets 1024 MB (template comment,
  `cli:adapter_configurations/adapter_templates/python/new_adapter/app/adapter.py.template:31-45`).
  Swap is capped at limit + 512 MB, which `mp-test` mirrors
  (`cli:docker_wrapper.py:320-329`).
- **No collector-side timeout.** "The Cloud Proxy's `Adapter Handler` ... does
  not have any timeout. Thus, it is possible when running on a Cloud Proxy for
  a collection to wait forever" (`docs:references/architecture.md` §Rest
  Server Collection Sequence). `mp-test` has 5 minute (collect) and 30 second
  (others) defaults, so a hang seen on the proxy may never show locally
  (`cli:mp_test.py:196, 235`).

### 1.2 HTTP endpoints the platform calls

Spec: `srv:swagger_server/swagger/swagger.yaml` (Collector Framework 2,
`cli:api/vmware-aria-operations-collector-fwk2.json`; the definition endpoint
is an SDK addition, `cli:api/integration-sdk-definition-endpoint.json`).

| Endpoint | Verb | `commands.cfg` key | Body in | Result out | Who calls it |
|---|---|---|---|---|---|
| `/apiVersion` | GET | (none, served by the server) | none | `{major:1, minor:0, maintenance:0}` (`controller.py:112-123`) | collector; `mp-build` writes it into `API_VERSION` |
| `/test` | POST | `test` | `AdapterConfig` | `{}` or `{"errorMessage": ...}` | collector on Validate Connection |
| `/collect` | POST | `collect` | `AdapterConfig` plus `collection_number`, `collection_window` added by the server (`controller.py:50-65`) | `{"result": [...], "relationships": [...], "nonExistingObjects": []}` or `{"errorMessage": ...}` | collector each cycle |
| `/endpointURLs` | POST | `endpoint_urls` | `AdapterConfig` | `{"endpointUrls": [...]}` | collector, before `test` (template comment `adapter.py.template:118-125`) |
| `/adapterDefinition` | GET | `adapter_definition` | none | AdapterDefinition JSON, or 204 when the adapter writes nothing (`controller.py:68-85`) | `mp-build` and `mp-test` only, to generate `describe.xml` (`docs:references/architecture.md` §Adapter/Collection Code) |

`AdapterConfig` (swagger `components.schemas.AdapterConfig`, lines 494-519):
`adapterKey` (adapter kind, object kind, name, identifiers with
`isPartOfUniqueness`), `credentialConfig` (`credentialKey`,
`credentialFields[]`), `clusterConnectionInfo` (nullable: `userName`,
`password`, `hostName` of the Ops cluster), `certificateConfig.certificates[]`
(`certPemString`, `isInvalidHostnameAccepted`, `isExpiredCertificateAccepted`),
`collectionNumber`, `collectionWindow`. The server converts it to snake_case
before handing it to the adapter.

**Suite API credentials arrive only for `collect`.** SDK 1.1.0 changelog: "on
the platform the SuiteAPI credentials are only sent during a Collection"
(`sdk:CHANGELOG.md`, 1.1.0); the lib docstring agrees (`lib:adapter_instance.py:71-80`).
Note `mp-test` still sends them to `endpoint_urls` (it withholds them only for
`test`, `cli:containerized_adapter_rest_api.py:46`), so local runs are more
permissive than the platform there.

### 1.3 How the server runs the adapter

`commands.cfg` maps each key to a command; the server appends two named-pipe
paths and runs it (`controller.py:153-196`). Default Python mapping:

```
[Commands]
test=/usr/local/bin/python app/adapter.py test
collect=/usr/local/bin/python app/adapter.py collect
adapter_definition=/usr/local/bin/python app/adapter.py adapter_definition
endpoint_urls=/usr/local/bin/python app/adapter.py endpoint_urls
```

The server writes the request JSON to the input pipe and reads one JSON value
from the output pipe. Consequences a reviewer must know:

- **Exit code is ignored.** Only the output pipe matters
  (`controller.py:206-269`).
- If nothing is written, the server answers **500 `No result from adapter`**,
  appending captured stdout and stderr (`controller.py:256-269`). That text
  goes back to the collector.
- Stdout is logged at DEBUG and stderr at WARNING into `server.log`
  (`controller.py:206-212`).
- At DEBUG the server logs the whole input with `credential_config` and
  `cluster_connection_info` replaced by `REDACTED`, but **identifiers are not
  redacted** (`controller.py:300-305`).

### 1.4 `adapter.py` entry points

Template: `cli:adapter_configurations/adapter_templates/python/new_adapter/app/adapter.py.template`.

| Function | Returns | Gets |
|---|---|---|
| `get_adapter_definition()` | `AdapterDefinition` | nothing |
| `test(adapter_instance)` | `TestResult` | identifiers, credential, certificates; no Suite API client |
| `collect(adapter_instance)` | `CollectResult` | everything, including the Suite API client, `collection_number`, `collection_window` |
| `get_endpoints(adapter_instance)` | `EndpointResult` | identifiers, credential; no Suite API client |
| `main(argv)` | dispatches on `argv[0]`, reads `AdapterInstance.from_input()` (input pipe is `sys.argv[-2]`, `lib:adapter_instance.py:142-145`), calls `.send_results()` (output pipe is `sys.argv[-1]`) | |

The template's `main` ends in `finally: sys.exit(0)` (`adapter.py.template:168-170`).
That is safe only because the template's `test` and `collect` catch every
exception and convert it to `with_error`. See §6.

---

## 2. AdapterDefinition and how it becomes describe.xml

### 2.1 The definition API (`lib:definition/`)

- `AdapterDefinition(key, label, adapter_instance_key, adapter_instance_label, version)`
  (`adapter_definition.py:22-73`). `key` must start with a letter, contain only
  alphanumerics and `_`, and be unique across all packs. Instance kind defaults
  to `<key>_adapter_instance`. `version` becomes describe `version`; bump it
  per release.
- Instance parameters (the account dialog fields):
  `define_string_parameter`, `define_int_parameter`, `define_enum_parameter`,
  each with `required` (default `True`) and `advanced` (default `False`)
  (`adapter_definition.py:106-220`). Display order is definition order.
- Credential types: `define_credential_type(key="default_credential", label)`
  then `define_string_parameter`, `define_int_parameter`,
  `define_password_parameter`, `define_enum_parameter` on it
  (`credential_type.py:481-597`). Only `define_password_parameter` sets
  `password: true` (`credential_type.py:410-431`). An account holds exactly
  one credential; several types means the user picks one
  (`adapter_definition.py:237-280`; `docs:troubleshooting_and_faq/adapter_design.md`).
- Object types: `define_object_type(key, label)` with
  `define_string_identifier` / `define_int_identifier` /
  `define_enum_identifier(..., is_part_of_uniqueness=True)`; with no
  uniqueness identifier the object name is the identity
  (`object_type.py:33-161`). Metrics and properties via `define_metric`,
  `define_string_property`, `define_numeric_property`, groups via
  `define_group` / `define_instanced_group` (`group.py`).
- Enums: values are plain strings or `(key, label)` tuples; a `default` not in
  the list is appended (`parameter.py:125-182`, `credential_type.py:434-478`).
  Enum values are case-sensitive and not localizable.

### 2.2 The JSON-to-XML mapping (`cli:describe.py`)

`mp-build` (and `mp-test`) start the container, GET `/adapterDefinition`, and
convert with `json_to_xml` (`describe.py:86-120, 242-289`). **If
`conf/describe.xml` exists in the project, it is used as is and the
definition endpoint is not called** (`describe.py:64-69`; `mp_build.py:443-460`).

| Definition | describe.xml |
|---|---|
| adapter `key`, `label`, `version` | `<AdapterKind key nameKey version>` |
| each credential type | `<CredentialKind>` with `<CredentialField required dispOrder password enum type>` (`describe.py:298-329`) |
| adapter instance | `<ResourceKind type="7" credentialKind="<all credential type keys, comma-joined>">` (`describe.py:262-273, 340-346`) |
| parameter / identifier | `<ResourceIdentifier default key nameKey required dispOrder enum type identType>` (`describe.py:360-387`) |
| metric / property | `<ResourceAttribute ... isProperty isRate isDiscrete isImpact keyAttribute defaultMonitored="true">` (`describe.py:430-449`) |
| group | `<ResourceGroup instanced instanceRequired>` (`describe.py:452-468`) |
| units | a fixed `<UnitDefinitions>` block (`describe.py:471-488`) |
| labels, descriptions | numeric `nameKey`s into `conf/resources/resources.properties` (`describe.py:510-527`) |

Extra XML fragments in `conf/*.xml` are merged only for `CustomGroupMetrics`,
`Faults`, `LaunchConfigurations`, `BasePolicyAnalysisSettings`,
`OOTBPolicies`, `FavoriteGroups` (`describe.py:122-175`). Policy and capacity
models need a hand-written `describe.xml` (`docs:troubleshooting_and_faq/adapter_design.md`).
The result is validated against the project's `conf/describeSchema.xsd`
before packaging (`cli:validation/describe_checks.py:278-285`).

### 2.3 identType and "advanced": the trap

The library has **no separate "advanced" flag in the output**. `advanced=True`
is emitted as `ident_type: 2`, `advanced=False` as `ident_type: 1`
(`lib:definition/parameter.py:50`). For object identifiers,
`is_part_of_uniqueness=False` is turned into `advanced=True`, so the same bit
(`object_type.py:61, 94, 131`). `describe.py:382` writes it as `identType`,
always with `required` and `default`.

What the platform does with that (9.0.2 bytecode plus a live dialog check,
`investigations/2026-10-13-account-dialog-advanced-settings-and-cert-accept.md` §1):

- `identType="1"` (or absent): part of the account's **uniqueness tuple**,
  shown in the main form.
- `identType="2"`: not part of uniqueness; lands under **Advanced Settings**
  only if it is also `required="false"` or has a non-empty default. A
  `required=True, advanced=True` parameter with no default stays in the main
  form.
- The platform also honours an explicit `advanced="true"` attribute that
  moves a field without touching identity, but the SDK cannot emit it, the
  shipped XSD does not declare it (so a hand-written describe carrying it may
  fail `mp-build`'s schema check; not tested), and it is unproven for a
  third-party pak.

So for a Python pack, **"collapse this field" and "remove it from account
identity" are one decision**. Flipping `advanced` on an existing field of a
released pack changes the identity of existing accounts; treat it as a
breaking change (same mechanism as the vsanhostmetrics `verify_certs` and
username notes, `investigations/2026-10-13-vsanhostmetrics-tuneup-assessment.md`
§4, §9).

### 2.4 SDK defects in the definition path (found reading source)

- `is_kpi` is accepted by `define_metric` and serialized by the lib
  (`lib:definition/attribute.py:53-63`) but `describe.py` never writes
  `isKpi` (`describe.py:430-449`; the attribute exists in
  `describeSchema.xsd:694`). KPI flags silently vanish. Workaround: a
  hand-written `describe.xml`.
- Every attribute is `defaultMonitored="true"` (`describe.py:444`); there is
  no way to ship an attribute off by default from the definition.
- Per-value enum `default` is computed as `value == default` where `value` is
  a dict and `default` a string (`describe.py:424`), so every `<enum>` gets
  `default="false"`. The `default` attribute on the `ResourceIdentifier`
  itself is correct, which is what the dialog uses (not verified live).

### 2.5 Platform semantics that apply to any pak

These are not SDK features but bind a Python pak the same way they bind a
Java one:

- `describe.xml` is parsed and the adapter kind registered at install time in
  the `APPLY_ADAPTER` phase (`cleanroom-spec/spec/16-platform-install-and-signing.md`).
- A pak can bind a shipped dashboard to a resource kind's Summary tab with
  `content/dashboards/dashboards.properties`, with the 9.0.2 caveats on widget
  types and unresolved widget config
  (`api-surface/summary_dashboard_pak_binding.md`). `mp-build` copies
  `content/` verbatim but moves any loose file in `content/dashboards/` into
  its own subdirectory and **fails the build on a loose `.properties` file
  there** (`cli:mp_build.py:92-134, 537-539`), so check how a
  `dashboards.properties` survives before relying on it (not tested).
- A `<SymptomSets>` wrapper must hold two or more children or Ops rejects
  the whole describe at install (compliance build 90, lesson
  `pak-content-bundling.md`); a single symptom set goes bare under `<State>`.
  Multi-tier alerts need one `<SymptomSets>` wrapper inside `<State>`; bare
  sibling `<SymptomSet>`s collapse to the last one
  (`wire-formats/alertdef_symptomset_import.md`).
- Files under `content/files/solutionconfig/` survive a non-force upgrade and
  are overwritten by a force-content upgrade
  (`api-surface/summary_dashboard_pak_binding.md` §Pak upgrade).

---

## 3. Certificate flow, end to end

### 3.1 What happens

1. The adapter's `get_endpoints()` returns HTTPS URLs via
   `EndpointResult.with_endpoint(url)` (`lib:result.py:78-123`). Only
   `https://` URLs are valid (`cli:validation/endpoint_url_validator.py:15-29`),
   so normalize a host identifier that may already carry a scheme, port or
   path (official sample: `sdk:samples/rest-template-mp/app/adapter.py:106-117`).
2. The platform fetches each URL's certificate. If its trust store does not
   already trust it, the account dialog shows "Review and accept
   certificate" (template comment `adapter.py.template:118-125`; the Java-side
   platform mechanics are in `tier2_architecture.md` §Accepting an untrusted
   target certificate). Returning an empty list means no prompt and the
   adapter "will handle certificates manually"
   (`srv:controllers/controller.py:131`).
3. Accepted certificates are stored on the adapter instance and passed in
   every later `test` and `collect` as `certificate_config.certificates`.
   `AdapterInstance.get_certificates()` returns them as `CertificateInfo`
   (`lib:adapter_instance.py:60-66, 82-90`): "all certificates that have been
   validated by a CA or manually accepted by a user".
4. `CertificateInfo` (`lib:certificate_info.py`):
   `get_certificate_string()` (PEM), `get_certificate_object()`
   (`cryptography` x509), `is_expired_certificate_accepted()`,
   `is_invalid_hostname_accepted()`. The platform contract says: on a hostname
   failure with `isInvalidHostnameAccepted` true, compare the presented
   certificate with the accepted one (for example by thumbprint); on an
   expiry failure with `isExpiredCertificateAccepted` true, continue
   (`srv:docs/Certificate.md`).
5. **The adapter must do the verification itself.** Nothing in the SDK
   applies these certificates to any HTTP client. No official sample uses
   `get_certificates()`; the REST sample points to a blog post and suggests
   `verify=False` as the alternative
   (`sdk:samples/rest-template-mp/app/adapter.py:209-216`). Both forks show
   the result: vsanhostmetrics prompts and then ignores the answer;
   cluster-perf-risk never prompts.

What `mp-test` emulates: it calls `endpoint_urls`, fetches each URL's
**leaf** certificate with `ssl.get_server_certificate`, and stores it with
`isInvalidHostnameAccepted: false`, `isExpiredCertificateAccepted: true`,
"mirror[ing]" the platform defaults (`cli:serialization.py:274-295`). It
caches the result in `connections.json` and reuses it until the
`certificates` key is deleted (`cli:mp_test.py:373-397`), so a renewed target
certificate is not picked up locally until you delete that key.

Things to assume about the list: it is not keyed by URL (match by trying
each), it may contain a CA-validated certificate as well as user-accepted
ones, and the PEM is the presented leaf, not a CA. Whether the platform ever
sends a chain, and what it sends after the target renews its certificate, was
not established.

### 3.2 Using the accepted certificate with pyVmomi

pyVmomi (verified in 9.1.1.0, `pyVmomi/SoapAdapter.py:1092-1142`) does
exactly the platform's semantics: pass `serverPemCert=<pem>` to
`SmartConnect` or `SoapStubAdapter`. It first tries normal verification with
the context you give it; only on `SSLCertVerificationError` does it reconnect
and require the peer certificate to **exactly equal** the pinned PEM. An exact
pin makes hostname and expiry moot.

```python
ctx = ssl.create_default_context()          # one context per connection
pems = [c.get_certificate_string() for c in adapter_instance.get_certificates()]
si = SmartConnect(host=host, user=user, pwd=pwd, sslContext=ctx,
                  serverPemCert=pems[0] if pems else None)
```

Caveats from the source:

- The fallback **mutates the context you passed** (`check_hostname=False`,
  `verify_mode=CERT_NONE`, `SoapAdapter.py:1137-1141`). Never share that
  context object with another client afterwards; build one per connection.
- One PEM per call. With several accepted certificates, try each.
- The vSAN helper `vsanapiutils.GetLatestVmodlVersion` sets
  `ssl._create_default_https_context = ssl._create_unverified_context`
  process-wide, in the vendored 2021 copy and in the copy pyVmomi 9.1.1.0
  bundles (`investigations/2026-10-13-vsanhostmetrics-tuneup-assessment.md`
  §1 item 3). Do not call it.
- The first pyVmomi release with `serverPemCert` was not checked; pin a
  version that has it.

### 3.3 Using the accepted certificate with requests

`requests` has no "trust this leaf" switch. Two patterns, in order of
preference:

1. **CA first, then exact pin** (same semantics as pyVmomi). Try the request
   with normal verification. On `requests.exceptions.SSLError`, retry through
   a session whose adapter pins the SHA-256 fingerprint of an accepted
   certificate, with `verify=False`. urllib3 enforces `assert_fingerprint` even
   when `cert_reqs` is `CERT_NONE` and treats the socket as verified
   (urllib3 2.0.7 `connection.py:746-827`, read locally):

   ```python
   class PinnedAdapter(requests.adapters.HTTPAdapter):
       def __init__(self, fingerprint, **kw):
           self._fp = fingerprint
           super().__init__(**kw)
       def init_poolmanager(self, *a, **kw):
           kw["assert_fingerprint"] = self._fp
           return super().init_poolmanager(*a, **kw)
   # fp = cert.get_certificate_object().fingerprint(hashes.SHA256()).hex()
   ```

   Pattern derived from urllib3 and requests source; not run against a live
   target in this investigation.
2. **Trust the accepted leaf as an anchor.** Build an `ssl.SSLContext` with
   `load_verify_locations(cadata=pem)` for each accepted PEM and set
   `ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN`; without the flag
   OpenSSL will not accept a leaf as a trust anchor. The base image is Python
   3.11 (`srv:Dockerfile:1`, `python:3.11.12-slim-bookworm`), where the flag
   exists but is off by default. Clear `check_hostname` only when
   `is_invalid_hostname_accepted()` is true. This cannot honour
   `is_expired_certificate_accepted()` (no expiry-only skip in the stdlib),
   which `mp-test` sets true by default; that is why pattern 1 is preferred.

Never pass the accepted PEM as `verify=<file>` and expect it to work for a
self-signed or VMCA-issued leaf: that is pattern 2 without the partial-chain
flag, and it fails the same way the system bundle does.

`verify=False` set explicitly also defeats `REQUESTS_CA_BUNDLE`; requests
consults the environment only when `verify` is True or unset.

### 3.4 When the pack has nothing to verify

If the pack only talks to the Ops Suite API (cluster-perf-risk), there is no
target to advertise and the Ops certificate is never offered for acceptance.
The SDK client then talks to Ops unverified (§5). Advertising the Ops host
needs a new identifier, because `get_endpoints` receives no
`cluster_connection_info`. Open questions recorded in
`investigations/2026-10-13-cluster-perf-risk-tuneup-assessment.md` §2.

---

## 4. Credential handling

- **Where a secret belongs.** In a credential type, as
  `define_password_parameter`. The platform stores password-typed credential
  fields encrypted and masked; plain credential fields are stored in clear
  (`cleanroom-spec/spec/03-credential-model.md:10, 56`). Public
  `GET /api/credentials` returns no password values
  (`investigations/2026-10-13-cluster-perf-risk-credential-reuse.md` §5).
- **Identifiers are not secrets.** There is no password-type identifier in
  the SDK. Identifier values are stored and shown in clear on the account,
  dumped unredacted in `server.log` at DEBUG (`controller.py:300-305`), and
  identifying ones are part of account identity.
- **Put the username in the credential too.** A username kept as an
  identifier becomes part of account uniqueness, so rotating a service
  account edits account identity, and the credential cannot be reused as a
  complete login. vsanhostmetrics shows the anti-pattern
  (`investigations/2026-10-13-vsanhostmetrics-tuneup-assessment.md` §4).
  Moving it later is a breaking change; read with a fallback to the old
  identifier.
- **Reading it.** `adapter_instance.get_credential_type()` and
  `get_credential_value(field_key)` (`lib:adapter_instance.py:123-140`). The
  values arrive only in the per-call input pipe and live in memory for that
  subprocess.
- **What reaches logs.** The server redacts the credential and the Suite API
  block in its own DEBUG dump. It does not redact identifiers, subprocess
  stdout (DEBUG) or stderr (WARNING), and it returns stdout and stderr to the
  collector in the 500 message (`controller.py:206-269`). The lib writes every
  result it sends to DEBUG (`lib:pipe_utils.py:40`, `logger.debug(repr(result))`),
  so a `TestResult` or `CollectResult` that embeds a secret in an error
  message or property is logged. The Suite API client logs its token and all
  response bodies at DEBUG (§5).
- **Do not:** print or log `adapter_instance.credentials`, the input JSON,
  request bodies, or `requests` exception objects that carry URLs with
  embedded credentials; put a credential in a URL; put a secret in an
  identifier; write secrets to the container filesystem (it outlives the
  call); echo a target's error body verbatim into `with_error` without checking
  it for secrets.
- **Local loop secrets.** `mp-test` stores connection passwords **in
  plaintext** in the project's `connections.json`
  (`docs:references/mp-test.md` §Connection), including the Suite API
  password. `mp-init` writes `connections.json`, `logs` and `build` into
  `.gitignore` (`cli:adapter_configurations/adapter_config.py:179-185`); keep
  it that way. `mp-build --registry-password` passes the registry password to
  `docker login --password` on the command line (`cli:docker_wrapper.py:48-69`),
  where it is visible in the process list; log in to the registry beforehand
  instead.

---

## 5. The Suite API client the platform hands the adapter

`adapter_instance.get_suite_api_client()` returns a `SuiteApiClient` built
from `cluster_connection_info` (platform-supplied Ops username, password and
host) in `collect`, and `None` in `test` and `get_endpoints`
(`lib:adapter_instance.py:48-58, 71-80`). Which Ops principal that is was not
established from source (`investigations/2026-10-13-cluster-perf-risk-credential-reuse.md` §3).

Source: `lib:suite_api_client.py`.

| Behaviour | Where | Consequence |
|---|---|---|
| `verify` defaults to `False`; `InsecureRequestWarning` disabled process-wide at import | `:22, :360` | TLS to Ops is unverified unless every call passes `verify=`. `setdefault` means a caller value wins. The `auth/token/acquire` POST carries the platform password over that link |
| No timeout | `_request_wrapper`, `:338-352` | A hung Ops node holds the call; with no collector timeout (§1.1) it can hang forever. Pass `timeout=` on every call |
| Token acquired on `with client:` (`__enter__`), released in `__exit__` | `:73-95, :97-129` | Use the client only inside `with`. A killed process leaks the token until server-side expiry. No refresh: a collection that outlives the token lifetime fails (lifetime not checked) |
| Token acquire failure only logs a WARNING and leaves the token empty | `:114-120` | Every later call goes out without `Authorization` and gets 401. Check `client.token` after entering `with`, and `with_error` if empty |
| Paged calls return `{key: []}` on a non-2xx first page | `:314-322` (`TODO: How should we communicate to caller that request(s) have failed?`) | A 401/403/5xx looks like "zero results". cluster-perf-risk's "healthy empty collection" defect |
| A failed later page reuses the previous page's body, or raises `UnboundLocalError` if no later page succeeded yet | `:329-335` | Duplicated or crashing results on partial failure |
| `query_for_resources` catches every exception and returns `[]` | `:261-294` | Same silent-empty failure mode |
| `logger.debug("Acquired token " + self.token)` and `logger.debug(result.text)` | `:116, :351` | At DEBUG (via `loglevels.cfg`) a usable bearer token and every response body land in `adapter.log` and its rotations |
| URLs: `api/...`, `internal/...`, `/api/...` are prefixed with `https://<host>/suite-api/`; anything else gets `api/` inserted | `:362-377` | A `suite-api/...` path is stripped into a local variable but never written back, so the request goes out with a relative URL and fails (`:371-372`). Use `/api/...` |
| `internal/` paths get `X-vRealizeOps-API-use-unsupported: true` | `:363-365` | Internal endpoints are unsupported and can change without notice. Current docs use the header name `X-Ops-API-use-unsupported`; whether 9.x still honours the older `X-vRealizeOps-` name was not checked |
| Module-level `requests.get/post`, no `Session` | throughout | No connection reuse; a pinned adapter (§3.3) cannot be mounted without subclassing |

Hostname normalization: `SuiteApiConnectionParameters` treats any host
string containing `http` as already a URL (`:39-42`).

---

## 6. Result objects and error reporting

### 6.1 The objects (`lib:result.py`)

- `TestResult`: `with_error(msg)` marks the test failed; last call wins;
  `get_json()` is `{}` on success (`:24-75`).
- `EndpointResult`: `with_endpoint(url)` (`:78-123`).
- `CollectResult`: `object(adapter_kind, object_kind, name, identifiers)`
  gets or creates (preferred), `add_object` raises
  `ObjectKeyAlreadyExistsException` on a different object with the same key
  (`:196-302`). `with_error(msg)` puts the **adapter instance** in an error
  state and **drops every object and relationship** in the result
  (`:304-314, :327-368`).
- `update_relationships`: `AUTO` (default; behaves as `ALL` if any object got
  children this cycle, else `NONE`), `ALL`, `NONE`, `PER_OBJECT` (only objects
  whose children were set this cycle are sent; required when writing onto
  objects the adapter does not own) (`:126-160`).
- `target_definition=` makes the result drop external objects (other adapter
  kinds) that carry no content (`:193-194, :332`).
- SDK defect: `get_objects_by_type(object_type)` compares
  `obj.adapter_type() == object_type` (`:253-258`), so it matches on adapter
  kind, not object kind. Do not rely on it.

### 6.2 How failures get hidden

The only signal the platform reads is the JSON on the output pipe.

1. **Unhandled exception plus `sys.exit(0)` in `finally`.** If `collect` lets
   an exception escape, `main`'s `finally: sys.exit(0)` replaces it: the
   process exits 0, nothing is written, and the traceback is never printed or
   logged (`Timer.__exit__` logs only elapsed time). The server returns 500
   `No result from adapter` with empty stdout/stderr, so the operator sees a
   generic collection failure and `adapter.log` has no cause. This is
   vsanhostmetrics finding 2: `collect()` is `try/finally` with no `except`
   (`investigations/2026-10-13-vsanhostmetrics-tuneup-assessment.md` §2).
   Fix: catch, `logger.exception(...)`, `result.with_error(...)`, return the
   result, as the template does (`adapter.py.template:94-101`).
2. **Errors swallowed below the adapter.** SDK client calls that return empty
   on 401/403/5xx (§5) yield a valid, empty `CollectResult`; the instance looks
   healthy while every object goes stale (cluster-perf-risk finding 1).
3. **One exception blanks everything.** Because `with_error` drops all
   objects, a catch-all around a multi-target loop turns one bad cluster into
   a lost cycle for all (cluster-perf-risk finding 4; vsanhostmetrics finding
   3). Catch per target, log with the target name, count failures, and call
   `with_error` only when every target failed (or a stated threshold).
4. **Test Connection that tests nothing.** An empty `TestResult` always
   passes. In `test`, at least validate parameters, and say in the docs what a
   green test does not prove (the Suite API cannot be checked there).
5. **"Unknown" emitted as a number.** A 0.0 score for "no inputs"
   reads as best-possible on a heatmap (cluster-perf-risk finding 3). Omit
   the metric instead.

---

## 7. The local loop

### 7.1 Requirements

Docker 20.10+ with the default socket reachable; a container registry with
push access for you and **anonymous pull** for the Cloud Proxies; Python 3.9
to 3.12 for the tools per the docs (`docs:get_started.md` §Prerequisites;
the CLI's own `pyproject.toml:33` says `>=3.10,<3.13`); Git. Install with
`pipx install vmware-aria-operations-integration-sdk`.

### 7.2 `mp-init`

Interactive generator (`cli:mp_init.py`, `docs:references/mp-init.md`).
Writes `manifest.txt`, `config.json`, `commands.cfg`, `Dockerfile`,
`adapter_requirements.txt` (`vmware-aria-operations-integration-sdk-lib~=1.1.0`),
`app/adapter.py`, `conf/` (XSDs, images), `content/`, `resources/`, a git
repo and `.gitignore` (§4). An adapter key prefixed `iSDK_` has the prefix
removed from the pak name (`cli:mp_build.py:328-329`); cluster-perf-risk's
`manifest.txt` name is `iSDK_ClusterPerfRisk`.

### 7.3 `mp-test`

`mp-test [connect|collect|long-run|endpoint_urls|adapter_definition|version|wait]`
(`docs:references/mp-test.md`, `cli:mp_test.py`). It builds the image locally
with the label `mp-test`, runs it with the memory limit from `config.json`
(`default_memory_limit`), posts the same body the collector would
(`cli:containerized_adapter_rest_api.py:88-156`) and validates the response
against the collector API spec. Connection emulation: identifiers and
credential from `connections.json`; Suite API host, user and password from
the same file (placeholders if unset), sent for `collect` and `endpoint_urls`
but not `connect`. Certificate emulation as in §3.1. Logs (`server.log`,
`adapter.log`, `test.log`, `validation.log`) go to the project's `logs/`.

Gaps between `mp-test` and the proxy: timeouts (local 5 min / 30 s versus
none on the proxy), Suite API credentials for `endpoint_urls`, cached
certificates, and the Suite API principal (whatever you configured versus the
platform's own).

### 7.4 `mp-build`

Flow (`cli:mp_build.py:332-583`):

1. Start the container, get the definition, generate and schema-validate
   `describe.xml` (unless a static one exists).
2. Check `manifest.txt` `adapter_kinds` holds exactly one key equal to the
   describe key (offers to rewrite it otherwise, `:370-396`).
3. Build the adapter image with `nocache=True` (`cli:docker_wrapper.py:167-219`);
   `pip install --upgrade` in the Dockerfile therefore resolves floating
   requirements fresh at every build. The `FROM base-adapter:python-1.2.0`
   base is **built locally** from source bundled with the CLI the first time
   and then reused from the local image store (`cli:docker_wrapper.py:469-536`;
   `cli:constant.py:11-14` notes the remote base images are deprecated). Its
   OS patch level is the date it was first built on that host
   (`apt-get upgrade` in `srv:Dockerfile:4-7`).
4. Tag `<version>_<epoch>`, `docker login`, push, record the **digest**
   (`:172-240`; `cli:docker_wrapper.py:120-164`). The local image is removed.
5. Assemble the pak (§8.1).

Headless use: `--no-ttl` plus `--registry-tag`, and pre-run `docker login`
rather than `--registry-password` (§4). `config.json` keys:
`container_repository` (pull path written into the pak),
`container_push_repository` (where to push, if different),
`use_default_registry`, `default_memory_limit` (`sdk:CHANGELOG.md` 1.2.0;
`cli:constant.py:36-44`).

---

## 8. The built pak and how it installs

### 8.1 Layout (`cli:mp_build.py:427-581`; `docs:references/mp-build.md` §Pak file)

```
<name>_<version>.pak
  manifest.txt
  eula.txt, icon               (if set in manifest)
  validation / pre / post scripts (if set in manifest)
  resources/                   (manifest localization)
  content/                     (dashboards, reports, alerts, ... verbatim; dashboards/reports split into subdirectories)
  adapter.zip
    <AdapterKind>.conf
    manifest.txt, eula, icon, resources/
    <AdapterKind>/conf/describe.xml
    <AdapterKind>/conf/resources/resources.properties
    <AdapterKind>/conf/version.txt     (Major/Minor/Implementation from manifest version)
    <AdapterKind>/conf/...             (XSDs, images, fragments)
```

`<AdapterKind>.conf` (`cli:mp_build.py:469-504`):

```
KINDKEY=<adapter kind>
API_VERSION=1.0.0
API_PROTOCOL=https
API_PORT=443
REGISTRY=<registry host[:port]>      # omitted when use_default_registry
REPOSITORY=/<path>
DIGEST=sha256:<...>
```

### 8.2 The image is referenced, never embedded

Evidence, all pointing the same way:

- The builder writes only `REGISTRY`, `REPOSITORY` and `DIGEST`; no image
  bytes go into the pak (`cli:mp_build.py:495-504`). There is no embed option
  in 1.3.1.
- "Within a Pack File, the adapter container image is referenced by the
  registry location and image digest SHA ... the VCF Operations Cloud Proxy
  needs anonymous pull access to the registry"
  (`docs:references/architecture.md` §Management Pack Distribution); "During
  installation, VCF Operations uses the information inside the
  `<ADAPTERNAME>.conf` file to pull the container from the registry"
  (`docs:troubleshooting_and_faq/container_registries.md`).
- Private registries are unsupported; the documented workaround is to
  `docker pull` the exact digest on the Cloud Proxy by hand before install,
  because proxies look up images locally first
  (`docs:troubleshooting_and_faq/container_registries.md` §I can't use a public
  repository). On this factory that is a manual infra change (CLAUDE.md
  rule 11) and only for development.
- Upstream author's lab tests on a Cloud Proxy (third-party evidence, not
  reproduced by the factory), `content/sdk-adapters/vsanhostmetrics/docs/OFFLINE-DELIVERY.md`
  and `docs/DELIVERY-PIVOT.md`: the container `dockerized_adapter_<Kind>_<id>`
  runs `Config.Image = <registry>/<repo>@sha256:<digest>`; `docker load` of a
  saved image does not create the RepoDigest so a pull is still attempted;
  editing the proxy's `.conf` is undone because Operations re-syncs the
  plugin directory from its database. Conclusion recorded there: every
  container pack needs a registry the Cloud Proxy can reach.
- `use_default_registry` omits `REGISTRY` so the platform's default registry
  is used (`sdk:CHANGELOG.md` 1.2.0). What that default is on 9.x, and
  whether it can be pointed at an internal mirror, was not established.

Operational consequence for anything the factory ships or recommends: a
Python pack is two artifacts (pak plus image), the image must stay pullable
at that digest for as long as anyone installs or re-creates instances, and
air-gapped sites need a reachable registry. Publish the digest with the
release; cluster-perf-risk uses Docker Hub (`config.json`,
`docker.io/gillaspy/cluster-perf-risk`), which rate-limits anonymous pulls
(`docs:guides/container_registry_setup.md` §Using Docker Hub).

### 8.3 Install path

Same pipeline as any pak (`cleanroom-spec/spec/16-platform-install-and-signing.md`):
CASA phases `STAGE`, `PREAPPLY_VALIDATE`, `VALIDATE` (runs
`pak_validation_script`), `APPLY_ADAPTER_PRE_SCRIPT`, `APPLY_ADAPTER`
(describe registered), `APPLY_ADAPTER_POST_SCRIPT`, `CLEANUP`; unsigned paks
install; certificate validity dates are not enforced; content then installs
from `content/` (`api-surface/summary_dashboard_pak_binding.md` §Where it
lives). Upload and install over `/admin/solution.action`
(`api-surface/pak_install_api_exploration.md`).

What the install checks that is specific to container paks, and **when** the
image is pulled (install time on every proxy, or first container start), was
not established from source; the SDK docs say "during installation", the
upstream author's notes observe the pull at container start. Logs on the
proxy: `$ALIVE_BASE/user/log/adapters/<ADAPTERKEY>/<internal instance id>/`
with `adapter.log`, `server.log` and `loglevels.cfg`
(`docs:troubleshooting_and_faq/logs.md`).

---

## 9. Defects seen today and their fixes

From `investigations/2026-10-13-vsanhostmetrics-tuneup-assessment.md` (V)
and `investigations/2026-10-13-cluster-perf-risk-tuneup-assessment.md` (C).

| Defect | Seen in | Fix |
|---|---|---|
| Accepted certificate never read; default `verify=true` fails on every VMCA-signed vCenter, so users turn verification off | V §1 | Read `get_certificates()`, pass PEMs as pyVmomi `serverPemCert` (§3.2) |
| Helper flips stdlib HTTPS to unverified process-wide | V §1.3 | Do not call `GetLatestVmodlVersion`; fetch with the verified context or skip the probe |
| Accept prompt shown when verification is off | V §1.4 | Return endpoints only when the answer matters |
| `collect` exceptions vanish (`try/finally`, `sys.exit(0)`) | V §2 | `except Exception: logger.exception; result.with_error` (§6.2) |
| One bad target aborts the whole cycle; test probes only the first | V §3, C §4 | Per-target `try`, `with_error` only when all fail; test per target |
| Username as an identifier | V §4 | Move into the credential with a fallback; breaking, flag it |
| pyVmomi undeclared; `adapter_requirements.txt` not committed | V §5 | Commit requirements with pins |
| Host field not normalized (`https://https://...`) | V §8 | One normalizer for endpoints and connects |
| Suite API auth/query failure looks like an empty healthy collection | C §1 | Check `client.token`; check status before paging; `with_error` |
| TLS to Ops unverified, platform password crosses it | C §2 | Pass `verify=`; option to advertise the Ops host for acceptance; upstream SDK issue |
| No timeouts; hung call leaks the token | C §5 | `timeout=(connect, read)` everywhere |
| Token and bodies logged at DEBUG (SDK) | C §7 | `logging.Filter` on `aria.ops.suite_api_client`; upstream SDK issue |
| 0.0 emitted for "unknown" | C §3 | Omit the metric when the band is unknown |
| `DISPLAY_NAME` / `DESCRIPTION` / `VENDOR` in manifest | C §9 (corrected) | Not a defect: localization keys resolved via `resources/resources.properties`; check that file carries the real values |

SDK-side defects found while writing this document (candidates for upstream
issues, none reported yet): `isKpi` not emitted (§2.4); enum per-value
default always false (§2.4); `get_objects_by_type` compares the wrong field
(§6.1); `suite-api/` URL prefix never applied (§5); later-page failure in
`_paged_request` (§5); the lib imports `requests` and `urllib3` but declares
only `aenum==3.1.11` and `cryptography==44.0.0`
(`sdk:lib/python/setup.cfg:25-27`, confirmed in the PyPI 1.1.0 wheel
metadata). The base image does supply `requests` (and so `urllib3`)
transitively: connexion 3.3.0 declares `requests>=2.27`, so the import only
fails outside the image (verified 2026-10-13; a clean venv with lib 1.1.0
raises `ModuleNotFoundError: requests`). Declare it anyway. Draft upstream
issues for all of these, plus the cryptography pin, the Suite API client
defaults and two `mp-build` defects, verified with repros against the PyPI
releases, are in `investigations/2026-10-13-sdk-upstream-issue-drafts.md`
(not filed). Trivy's findings for pip's vendored msgpack, urllib3 and
setuptools in the base image are **not** an SDK defect: they ship inside
current pip (26.2.1), so a base-image rebuild cannot clear them.

---

## 10. Review checklist for a Python pack PR

**Certificates**
- [ ] `get_endpoints` returns `https://` URLs for every TLS target the adapter
      verifies, built from a normalized host, and nothing when verification
      is deliberately off.
- [ ] `test` and `collect` use `get_certificates()`: pyVmomi `serverPemCert`,
      or CA-then-pin for `requests` (§3). No accepted-PEM-as-`verify=`
      without the partial-chain flag.
- [ ] No `ssl._create_unverified_context`, no global
      `ssl._create_default_https_context` change, no
      `urllib3.disable_warnings` added by the pack, no `verify=False` outside
      a documented, opt-in insecure path.
- [ ] One SSL context per pinned connection (pyVmomi mutates it).

**Credentials**
- [ ] Every secret is a `define_password_parameter` in a credential type;
      usernames live in the credential, not an identifier.
- [ ] No secret in identifiers, URLs, log lines, `with_error` text,
      properties, stdout/stderr, or files on the container.
- [ ] `connections.json`, `logs/`, `build/` gitignored; nothing secret
      committed (check history too).

**Error reporting**
- [ ] `collect` and `test` catch, `logger.exception`, and `with_error`; no
      code path lets an exception reach `main`'s `sys.exit(0)`.
- [ ] Multi-target work is isolated per target; `with_error` only when every
      target failed or above a stated threshold.
- [ ] Every SDK Suite API call's failure is detected (empty token, non-2xx
      on the first query); an all-failed cycle is an error, not an empty
      success.
- [ ] `test` checks something real, and the docs say what it cannot check.
- [ ] Unknown values are omitted, not emitted as 0.

**Timeouts**
- [ ] Every outbound call (Suite API client, `requests`, pyVmomi) has an
      explicit timeout; the proxy has none (§1.1).

**Token handling**
- [ ] Suite API client used only inside `with`; token presence checked after
      entering.
- [ ] Nothing raises the SDK client logger to DEBUG by default; if DEBUG
      support matters, a redaction filter is installed after `setup_logging`.

**Definition and identity**
- [ ] Any change to `advanced`, `is_part_of_uniqueness`, identifier keys or
      credential fields of a released pack is called out as an account
      identity change (§2.3).
- [ ] `version` in `AdapterDefinition` and `manifest.txt` bumped together.
- [ ] No reliance on `isKpi` from the definition (§2.4).

**Dependencies and SDK pins**
- [ ] `adapter_requirements.txt` committed, lists every import that is not
      stdlib (including `requests`, `pyVmomi`), with pins or tight ranges.
- [ ] `vmware-aria-operations-integration-sdk-lib~=1.1.0`; build host pins
      `vmware-aria-operations-integration-sdk==1.3.1`; `FROM
      base-adapter:python-1.2.0` matches the CLI's
      `container_versions.json`.
- [ ] No vendored copy that shadows a maintained package of the same module
      name.

**Packaging and distribution**
- [ ] `manifest.txt` keeps the localization keys and `resources/resources.properties` carries the real display name, description and vendor,
      `version`; `adapter_kinds` equals the describe key.
- [ ] The release states the registry path and image digest, and the
      registry allows anonymous pull from Cloud Proxies.

---

## Not established from source

- What the install path checks for a container pak, and whether the image is
  pulled at install or at first container start (§8.3).
- What `use_default_registry` resolves to on 9.x (§8.2).
- Whether the platform sends a chain or only the leaf in
  `certificate_config`, how the list relates to multiple endpoints, and what
  happens after the target renews its certificate (§3.1).
- Which Ops principal `cluster_connection_info` carries, its token lifetime,
  and the `host_name` form (FQDN, IP, local name) (§5).
- Whether 9.x honours `X-vRealizeOps-API-use-unsupported` (§5).
- Whether the base image provides `requests` without the pack declaring it
  (§9).
- Whether a `dashboards.properties` file survives `mp-build`'s content
  handling (§2.5).
- Whether a hand-written describe with `advanced="true"` passes `mp-build`
  schema validation and renders under Advanced Settings (§2.3).
- The first pyVmomi release with `serverPemCert` (§3.2).
- The urllib3 version inside the base image; the fingerprint-pin pattern was
  read in urllib3 2.0.7 (§3.3).

## Correction 2026-10-13: manifest localization keys

`DISPLAY_NAME`, `DESCRIPTION` and `VENDOR` in `manifest.txt` are
localization keys resolved through `resources/resources.properties`
(mp-init docs: set to "DISPLAY_NAME" for localization). Every official
sample and the vcommunity paks ship them that way. Do not "fill" them with
literal strings; check that `resources.properties` carries the real values.
Any earlier line in this document or in the MPB notes
(`mpb_handoff.md`, `mpb_designer_wire_format.md`) calling them unfilled
placeholders is wrong.
