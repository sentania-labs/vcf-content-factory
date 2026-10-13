# cluster-perf-risk: tune-up assessment for upstream PRs (2026-10-13)

Investigator: `api-explorer`. Read-only source review; nothing executed, no
lab calls, clone untouched (`git status` clean after the review).

**Target:** `content/sdk-adapters/cluster-perf-risk/` (fork of
`gillaspy/cluster-perf-risk`, upstream `main` at `6aa3e10`, pak version
1.3.0 per `manifest.txt`). Python Integration SDK container adapter.

**SDK source read:** `vmware-aria-operations-integration-sdk-lib` 1.1.0
sdist (the version `adapter_requirements.txt` pins with `~=1.1.0`) and the
`vmware-aria-operations-integration-sdk` 1.3.1 wheel (tool plus bundled
base-image source), both from PyPI, in the session scratchpad. Paths below
prefixed `sdk-lib:` are `src/aria/ops/...` in the lib; `sdk-tool:` is the
1.3.1 wheel.

**Prior work, not repeated:** the credential posture (no credential kind;
platform-injected Suite API principal from `cluster_connection_info`; Ops
principal, never vCenter) is in
`knowledge/context/investigations/2026-10-13-cluster-perf-risk-credential-reuse.md`.

**Scope caveat.** Scott's request mentions "certificate validation options
and credential storage". This adapter has neither a certificate option nor
a stored credential, so finding 2 below is about the TLS it does not
verify, not about an option it gets wrong. The sibling fork
`content/sdk-adapters/vsanhostmetrics/` matches that description much more
closely (see "Follow-up" at the end).

---

## Ranked findings

| # | Finding | Where | PR size |
|---|---|---|---|
| 1 | A Suite API auth or query failure produces a "successful" empty collection | `adapter.py:147-150`, `suite_api.py:16-28`, `sdk-lib: suite_api_client.py:114-120, 314-322` | Small |
| 2 | TLS to the Ops Suite API is never verified, and the platform principal's password crosses it | `sdk-lib: suite_api_client.py:22, 360`; no `verify` anywhere in `app/` | Medium (needs one live probe first) |
| 3 | Publish-to-native leaves stale values behind, and projects a fake 0.0 score | `cluster.py:185`, `host.py:144`, `native_projection.py:181-189`, `adapter.py:116-125` | Small |
| 4 | One unexpected exception discards the whole cycle, every cluster | `adapter.py:241-244`, `sdk-lib: result.py:304-314` | Small |
| 5 | No request timeout; a hung call leaks the session token | all `client.get`/`paged_post` calls; `sdk-lib: suite_api_client.py:338-360` | Small |
| 6 | Request volume scales as one HTTPS call per (resource, statKey) | `traversal.py`, `cluster.py:129-292` | Medium |
| 7 | The SDK logs the Suite API token and every response body at DEBUG | `sdk-lib: suite_api_client.py:116, 351` | Small (adapter-side filter) or upstream SDK PR |
| 8 | Test Connection checks nothing | `adapter.py:97-103` | Small |
| 9 | Packaging hygiene: placeholder manifest strings, one-line README, stray `.gitignore` line | `manifest.txt:2,4,14`; `README.md`; `.gitignore:4` | Trivial |
| 10 | Versions and base image are current; nothing to bump | `requirements.txt`, `adapter_requirements.txt`, `Dockerfile:2` | None |

---

### 1. Auth or query failure looks like a healthy, empty collection

**What happens.** `collect()` enters `with client:` (`adapter.py:148`),
which calls `get_token()`. On a non-2xx from `/api/auth/token/acquire` the
SDK only warns and leaves the token empty:

```python
else:
    logger.warning(f"Could not acquire SuiteAPI token: {token_response}")
```
(`sdk-lib: suite_api_client.py:117-120`)

Every later call then goes out without an `Authorization` header and gets a
401. `paged_post` swallows that and returns an empty list
(`suite_api_client.py:316-322`, with the SDK's own "TODO: How should we
communicate to caller that request(s) have failed?"). `fetch_resources`
(`suite_api.py:20-28`) turns that into zero clusters, the loop does nothing,
and `collect()` returns a result with no objects and **no `with_error`**.
The adapter instance shows as collecting fine while every risk object goes
stale. The same path fires for a 403 (principal lacks read on `VMWARE`
objects) or a 5xx on the resource query.

`latest_stat`, `get_property` and `fetch_children_of_kind` likewise return
`None`/`[]` on any non-2xx (`suite_api.py:61-62, 80-81, 97-98`). Per-metric
`None` is handled well downstream (`scoring.py:49-62` reports "unknown"
rather than a false green), but nothing counts the failures, so a cycle
where 100% of stat calls 401'd is indistinguishable from "no data yet".

**SDK mechanism.** `CollectResult.with_error()` (`sdk-lib: result.py:304`)
is the only way to put the instance into an error state. Use it when the
pre-loop calls fail.

**PR (small, about 30 lines):**
- After `with client:`, check `client.token`; if empty,
  `result.with_error("Could not acquire a Suite API token ...")` and return.
- Make `fetch_resources` call `client.post` directly (or check status
  before paging) so a non-2xx on the cluster query raises or returns a
  sentinel; `with_error` when the cluster query failed, versus a genuine
  zero-cluster environment, which stays a clean empty result.
- Count non-2xx responses in `latest_stat`/`get_property` and log one
  summary line per cycle (and `with_error` above a threshold if the
  maintainer wants the instance to go red).

### 2. TLS to the Ops Suite API is unverified

**What happens.** No file in `app/` passes `verify`. Every call goes through
the SDK client, which defaults it off and silences the warning
process-wide:

```python
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
...
kwargs.setdefault("verify", False)
```
(`sdk-lib: suite_api_client.py:22, 360`)

So the container talks to `https://<host_name>/suite-api/` with no chain or
hostname check, and the first request of every cycle is the
`/api/auth/token/acquire` POST carrying the platform-supplied Ops username
and password (`suite_api_client.py:106-112`). Anyone able to intercept
cloud-proxy-to-Ops traffic can harvest that principal. `get_endpoints`
returns nothing (`adapter.py:250-254`, comment: "does not need certificate
handling here"), so the platform's certificate-accept flow never runs for
this adapter and `adapter_instance.get_certificates()` stays empty.

Note `verify=False` is explicit, so the `REQUESTS_CA_BUNDLE` environment
variable cannot rescue it either (requests only consults the environment
when `verify` is `True`/unset).

**SDK mechanisms available.**
- `setdefault` means a caller-supplied `verify=` wins: every
  `client.get/post/paged_post(..., verify=<CA path or True>)` call can turn
  verification on without touching the SDK.
- `AdapterInstance.get_certificates()` (`sdk-lib: adapter_instance.py:82-90`)
  returns the certificates the platform has validated or a user accepted,
  each with `get_certificate_string()` (PEM),
  `is_invalid_hostname_accepted()` and `is_expired_certificate_accepted()`
  (`sdk-lib: certificate_info.py`). The base-image API doc
  (`sdk-tool: images/base-python-adapter/docs/Certificate.md`) says that when
  hostname verification fails and `is_invalid_hostname_accepted` is true the
  adapter "should do the verification by comparing the certificates ... for
  example ... by thumbprint". Those certificates are only populated for URLs
  the adapter returns from `get_endpoints`.
- `get_endpoints` and `test` receive no `cluster_connection_info` (the
  client is `None` there, `adapter_instance.py:71-80`), so the adapter
  cannot learn the Ops host to advertise without a new instance parameter.

**Unknowns that block a confident PR (need one live probe on a lab with the
pak installed):** what `host_name` the collector actually sends in
`cluster_connection_info` (FQDN, IP, or a local name on the cloud proxy),
and therefore whether the Ops certificate would pass a hostname check at
all; and whether `certificate_config` carries anything for an adapter that
advertises no endpoints. Neither is answerable from source.

**PR options, smallest first:**
- (a) **Opt-in verify, default unchanged** (small). Advanced enum parameter
  "Verify VCF Operations certificate" (`false`/`true`, default `false` so
  existing installs behave the same). When `true`, pass `verify=True` (system
  trust in the container, which is Debian's bundle in
  `python:3.11.12-slim-bookworm`, so only works with a publicly or
  corporately chained Ops cert that the image trusts). Honest, but weak for
  the common self-signed or VMCA case.
- (b) **Platform-accepted certificate** (medium). Add an advanced
  "VCF Operations host" identifier, return `https://<it>` from
  `get_endpoints` so the standard accept dialog runs at instance creation,
  then in `collect` write `get_certificates()` PEMs to a temp file and pass
  it as `verify=`. When `is_invalid_hostname_accepted` is set, a plain
  `verify=` path will still fail on hostname, so that branch needs a
  thumbprint pre-check (for example `ssl.get_server_certificate` compared
  against the accepted PEM) before the token call. The SDK client uses
  module-level `requests.get/post`, not a `Session`, so a pinned
  `HTTPAdapter` cannot be mounted without subclassing `SuiteApiClient`.
- (c) **Upstream SDK issue** (separate venue). The insecure default lives in
  VMware's lib, not in this adapter; every Python SDK adapter using
  `get_suite_api_client()` inherits it. Worth filing against
  `vmware/vmware-aria-operations-integration-sdk` regardless of (a)/(b).

Recommendation for the first PR: (a) plus a README paragraph stating the
posture, then (b) once the live probe answers the two unknowns.

### 3. Publish-to-native: stale values, fake zero, phantom-object risk

The design is careful where it matters most: projected keys live under a
pack-unique root `Performance Risk|...` with a test enforcing no collision
with native statkeys or the `vCommunity|` root
(`constants_native.py:12-16, 58-59`, `tests/test_native_projection.py`);
external object identity is copied verbatim from the Suite API
`resourceKey`, never hand-built (`native_projection.py:137-156`);
`RelationshipUpdateModes.PER_OBJECT` is set so native objects, which never
get `add_child`, have their relationships left alone
(`adapter.py:121-124`; `sdk-lib: result.py:146-153, 338-366`); and
`target_definition` makes the SDK drop external objects that carry no
content (`sdk-lib: result.py:193-194, 332`). Per-cluster projection errors
are isolated (`adapter.py:197-229`). Idempotence is fine: each cycle writes
one new datapoint per metric and the same property values, no
accumulation.

What a maintainer would want fixed:

- **Composite score of 0.0 when every input is unknown.** `compute_composite`
  returns `(0.0, "unknown", ...)` (`scoring.py:59-62`) and the builders emit
  that 0.0 unconditionally (`cluster.py:185`, `host.py:144`); projection then
  copies it to the native object (`native_projection.py:181-185`). On a
  heatmap or scoreboard keyed on `Risk Score`, a broken collection reads as
  the best possible score, which is exactly what the scoring module's own
  comment says must not happen. Fix: skip the metric when the band is
  `unknown`. Small, a few lines in each builder.
- **Turning the flag off (or deleting the instance) leaves the last values
  on `VMWARE` objects.** Metrics simply stop; properties such as
  `Performance Risk|Composite|Risk Band` keep their last value on the native
  Cluster and Host objects indefinitely, because this adapter does not own
  those objects and the SDK has no "remove attribute from external object"
  call. A host that was `red` the day the flag went off stays `red` in any
  view or symptom keyed on that property. Not tested live; reasoning from
  SDK behaviour. Smallest fix: document it in the parameter description
  and README. Optional: when the flag is off, write a one-time sentinel
  (`disabled`) to the projected band properties, which needs the previous
  state remembered somewhere (the adapter is stateless per call), so it is
  a judgement call, not an obvious PR.
- **Key drift between query and write.** Keys come from one query at the
  start of `collect` (`adapter.py:153-159`). If a cluster or host is
  removed from Ops mid-cycle, the result still carries an external object
  of kind `VMWARE` with that key. Whether the collector then creates a
  ghost resource or drops it is **unverified**; worth one live check
  (remove a host from inventory between cycles with the flag on) before
  claiming either way. No PR proposed without that evidence.
- **Minor:** `fetch_resources` and `fetch_resource_keys` run the identical
  `/api/resources/query` (`suite_api.py:20-24, 36-40`, called at
  `adapter.py:150, 154`); with the flag on the cluster query runs twice per
  cycle. One query returning both id/name and key removes a call. Trivial.

### 4. One exception discards every cluster's results

The outer `except Exception` (`adapter.py:241-244`) calls
`result.with_error(...)`, and the SDK then returns only the error message,
dropping all objects already built ("If error_message is set, no results
(objects, relationships) will be returned", `sdk-lib: result.py:304-314`).
Any raise inside `gather_metric_values` or the traversal for one cluster
(a `requests.ConnectionError`, a non-JSON body from a proxy, a `KeyError`
on an unexpected payload in `suite_api.py:26, 101`) blanks the whole cycle.
Native projection already has its own per-cluster `try`; the own-object
path does not.

**PR (small):** wrap the per-cluster body (`adapter.py:165-229`) in its own
`try/except`, log with the cluster name, count failures, and only call
`with_error` if every cluster failed (or if a non-zero failure count should
mark the instance degraded, the maintainer's call). Keeps the visibility of
finding 1 without the blast radius.

### 5. No timeout on any request

The SDK passes kwargs straight to `requests.get/post` and sets no timeout
(`sdk-lib: suite_api_client.py:338-360`); the adapter never supplies one.
A hung Ops node holds the collect call until the platform kills the
container process, at which point `__exit__` never runs and the session
token is not released (`suite_api_client.py:82-95, 124-129`), so it lives
until server-side expiry. **PR (small):** pass `timeout=(connect, read)` on
every call through the four helpers in `suite_api.py` (one constant), and
let `requests.Timeout` hit the per-cluster handler from finding 4.

### 6. Request volume

Counting the code paths per cluster with N hosts and V VMs: about
`13 + 18N + 6V` HTTPS calls, each a fresh connection (module-level
`requests`, no `Session`). `fetch_child_hosts` alone runs seven times per
cluster (`cluster.py:192`, reached twice, plus `208, 229, 250, 278` and `traversal.py:92`), and
`get_property` pulls every host property to read one
(`suite_api.py:79-85`). A 50-host, 1000-VM estate is roughly 7,000 calls a
cycle against the Ops cluster.

**SDK/API mechanism.** `POST /api/resources/stats/latest/query`
(public spec, `reference/docs/operations-api.json`, schema
`latest-stat-query`: up to 1000 `resourceId`s and any number of `statKey`s
per call) replaces the per-VM and per-host loops with a handful of calls.
Caveat for the PR author: `latest_stat`'s docstring
(`suite_api.py:49-56`) explains that instanced metrics come back under an
aggregated key name, so the bulk response must be matched by requested key
with that rename in mind. **PR (medium)**: fetch the host list once per
cluster and pass it to the helpers (small, safe, do first), then batch the
stat reads (medium, needs regression comparison of old and new values on
one lab cycle).

### 7. Token and response bodies logged at DEBUG (SDK side)

The adapter itself never logs a secret: the password arrives over the
input pipe, is held in memory by `SuiteApiConnectionParameters`, is never
written to disk, and the request body that carries it is not logged.
`main()` logs `argv` (`adapter.py:261`), which is only the method name and
pipe paths. Token lifecycle is correct: acquired on `with client:`,
released in `__exit__` even on exception (finding 5 is the exception).

The SDK, however, logs the live token and every response body at DEBUG:

```python
logger.debug("Acquired token " + self.token)
...
logger.debug(result.text)
```
(`sdk-lib: suite_api_client.py:116, 351`)

The second line also re-logs the token-acquire JSON. Anyone who raises the
adapter log level to DEBUG for troubleshooting (the `loglevels.cfg`
mechanism in `sdk-lib: adapter_logging.py:50-98`) writes a usable bearer
token into `/var/log/adapter.log` and its five rotations, and the adapter's
own `logger.debug(f"Returning collection result {result.get_json()}")`
(`adapter.py:246`) adds the full payload on top, which is bulky but not
secret. **PR (small):** a `logging.Filter` on the `aria.ops.suite_api_client`
logger installed in `main()` after `setup_logging`, redacting
`vRealizeOpsToken`/`"token"` values. The proper fix is upstream in the SDK
(same venue as 2(c)).

### 8. Test Connection verifies nothing

`test()` returns an empty `TestResult()` (`adapter.py:97-103`). The comment
is accurate: the SDK supplies no Suite API client during `test`
(`sdk-lib: adapter_instance.py:71-80`), so the adapter cannot check its one
real dependency there. What it can still check cheaply:
`monster_vm_threshold_pct` parses as a number in a sane range (today a bad
value is only caught at collect time with a warning, `adapter.py:138-145`),
and the publish enum is one of its two values. **PR (small):** validate
parameters in `test()` and return `with_error` on bad input; say in the
README that a green Test Connection does not prove Suite API access, the
first collection does (and finding 1 makes that first collection honest).

### 9. Packaging hygiene

- `manifest.txt` still carries template placeholders:
  `"display_name": "DISPLAY_NAME"` (line 2), `"description": "DESCRIPTION"`
  (line 4), `"vendor": "VENDOR"` (line 14). These are what Ops shows on the
  Repository / Integrations tile. The SDK tool normally fills them from the
  `mp-init` answers; here they were never set. Trivial PR.
- `README.md` is one sentence; nothing on install, the publish-to-native
  flag and its side effects, required Ops privileges, or the TLS posture.
  Small doc PR, pairs naturally with findings 2, 3 and 8.
- `.gitignore` line 4 names a virtualenv directory that does not belong to
  this project. Harmless; the maintainer may prefer it out of a public
  repo. Trivial.

### 10. Versions and base image (no action)

- `requirements.txt`: `vmware-aria-operations-integration-sdk==1.3.1`,
  which is the latest on PyPI (uploaded 2026-03-05).
- `adapter_requirements.txt`: `vmware-aria-operations-integration-sdk-lib~=1.1.0`,
  latest is 1.1.0 (2025-02-03); `Dockerfile:5` installs with `--upgrade`,
  so it will float to any 1.1.x patch.
- `Dockerfile:2`: `FROM base-adapter:python-1.2.0`, exactly the base
  version the 1.3.1 tool bundles (`sdk-tool: container_versions.json`). In
  1.3.x that image is built locally from bundled source
  (`python:3.11.12-slim-bookworm` plus `apt-get upgrade` at build time), so
  its patch currency is the date the maintainer last built it, not a
  registry tag. Nothing for a PR; worth a README note that rebuilding picks
  up OS patches.

---

## Suggested PR sequence

1. Honest failures: findings 1, 4, 5 (one PR, small, behaviour-only, no new
   parameters). Highest value per line changed.
2. Unknown is not zero: finding 3 first bullet (tiny, separate so it can
   be reviewed on its own merits).
3. TLS: finding 2 option (a) plus README posture; option (b) after the live
   probe.
4. Hygiene and docs: findings 8, 9, and the finding 3 stale-value note.
5. Efficiency: finding 6, host list reuse first, bulk stats second.
6. Upstream SDK issue for 2(c) and 7 (not a PR to this repo).

## Follow-up

- **Which fork Scott meant.** The quoted complaint ("certificate validation
  options and credential storage") does not fit this adapter. It fits
  `content/sdk-adapters/vsanhostmetrics/` (upstream
  `nickfirefoot/vsanhostmetrics`): there the vCenter **username is a plain
  instance parameter** (`app/adapter.py:63-69`, `define_string_parameter`)
  while only the password is in the credential (`app/adapter.py:90-96`), and
  "Verify vCenter certificate" (`app/adapter.py:72-78`) uses
  `ssl.create_default_context()` (`app/perfsvc.py:155`), container system
  trust only, ignoring the certificate its own `get_endpoints`
  (`app/adapter.py:281-288`) hands to Ops for acceptance; the parameter text
  says "Disable only for initial bring-up". Not assessed further here;
  confirm with Scott before a separate assessment.
- Live probe for finding 2: the `host_name` value in
  `cluster_connection_info` and whether `certificate_config` is populated
  for this adapter.
- Live probe for finding 3 third bullet: what the collector does with an
  external `VMWARE` key whose resource no longer exists.

## Correction 2026-10-13 (finding 9, manifest)

`DISPLAY_NAME`, `DESCRIPTION` and `VENDOR` in manifest.txt are the SDK's
documented localization keys, resolved through `resources/resources.properties`
(which carries "Cluster Performance Risk", a description and "gillaspy").
They are not placeholders and the pak is installable as shipped. The README
and `.gitignore` parts of finding 9 stand.
