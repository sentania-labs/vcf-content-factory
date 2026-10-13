# vsanhostmetrics tune-up assessment (2026-10-13)

Investigator: `api-explorer`. Target: `content/sdk-adapters/vsanhostmetrics/`,
fork of `nickfirefoot/vsanhostmetrics` at upstream `main` `49ac57f`
(origin `sentania-labs/vsanhostmetrics`, `upstream` remote configured).
Method: static read only. The clone's code was never executed and nothing in
it was changed. No lab calls were made.

Purpose: shortlist of pull requests for the upstream author, per Scott:
"I'd like to give them a few PRs to tune them up - i.e. one I just tested
needs some help with the certificate validation options and credential
storage."

Sources checked against:

- SDK lib `vmware-aria-operations-integration-sdk-lib` 1.1.0 (sdist, the
  version the adapter pins `~=1.1.0`; 1.1.0 is also the newest on PyPI as of
  today): `aria/ops/adapter_instance.py`, `certificate_info.py`,
  `result.py`, `definition/credential_type.py`, `definition/parameter.py`,
  `adapter_logging.py`, `timer.py`.
- SDK CLI `vmware-aria-operations-integration-sdk` 1.3.1 wheel: the Python
  `new_adapter` template (`adapter.py.template`), `serialization.py`
  (how `mp-test` emulates the platform's certificate hand-off),
  `images/base-python-adapter/Dockerfile` (base image is
  `python:3.11.12-slim-bookworm`).
- `pyvmomi` 9.1.1.0 wheel (current): `pyVim/connect.py`,
  `pyVmomi/SoapAdapter.py`, bundled `vsanapiutils.py` / `vsanmgmtObjects.py`.
- `reference/docs` holds no Python SDK documentation (grep for
  `get_certificates`, `certificate_config`, `endpoint_urls`: no hits), so the
  lib source and the generator template are the documented mechanism.

## Summary

The adapter is well written and honest about its limits, and it already
does two of the things asked about: the password is in a credential type
(stored encrypted by Ops) and there is a verify toggle plus a
`get_endpoints()` that drives the Review and Accept Certificate dialog. The
gap is that the certificate the user accepts in that dialog is **never
used**. The platform hands it to the adapter in `AdapterInstance`, the
adapter ignores it and verifies against the container's stock CA bundle,
so the default (`verify=true`) fails on every VMCA-signed vCenter and the
docs tell users to turn verification off. Second most valuable: a
collection failure is **silently discarded**, so every error message the
author carefully wrote for collect never reaches the Ops UI or the log.

| Rank | Finding | PR size |
|---|---|---|
| 1 | Accepted certificate ignored; default verify fails out of the box; vendored helper turns off TLS verification process-wide | M |
| 2 | `collect()` exceptions vanish (no `except`, `sys.exit(0)` in `finally`) | XS |
| 3 | One non-vSAN (or perf-service-off) cluster aborts the whole collection; Test Connection probes only the first cluster | S |
| 4 | Credential storage: password correct, username is a plain identifier | S code, breaking for existing accounts |
| 5 | pyVmomi undeclared, `adapter_requirements.txt` not committed, README says "stdlib only"; vendored 2021 vSAN bindings now duplicate pyVmomi's | S (M if vendored copy is dropped) |
| 6 | Datacenters inside folders are skipped, their clusters silently uncollected | XS |
| 7 | Test Connection gaps (what it does and does not prove) | S, folds into 3 |
| 8 | Hostname field not normalized | XS, folds into 1 |
| 9 | Minor: "problems" warning fires every cycle; silent vmodl version fallback; verify toggle is part of account uniqueness | XS each |

Neither `BUGS-UPSTREAM.md` nor `BACKLOG.md` lists findings 1 to 8 as such.
`BUGS-UPSTREAM.md` is scoped to Broadcom's ESXi `/vsanmetrics` endpoint and
says so. `BACKLOG.md:267` comes closest: "`verify_certs: true` is untested,
and the reasoning behind it may be wrong", suspecting that accepted certs
land in the Ops trust store while the container uses its own CA bundle. That
suspicion is half right (see 1). `BACKLOG.md:250-253` asks for loud failure
instead of an empty successful collection; `PerfSvcError` was written for
that, but finding 2 defeats it.

---

## 1. Certificate validation (rank 1, PR size M)

### How it connects today

- `app/perfsvc.py:153-198` `connect()`: pyVmomi `SmartConnect` to vCenter
  SOAP (`/sdk`), then a second `SoapStubAdapter` to `/vsanHealth` built by
  the vendored `vsanapiutils.GetVsanVcMos` (`app/vendor/vsanapiutils.py:44-60,73`),
  reusing the session cookie and the same `sslContext`.
- `perfsvc.py:155`: `ssl.create_default_context() if verify else
  ssl._create_unverified_context()`. Verify on means "trust only the
  container's system CA bundle".
- Toggle: `adapter.py:72-78`, enum `verify_certs` `"true"/"false"`, default
  `"true"`, parsed at `adapter.py:228-230`.
- `adapter.py:281-288` `get_endpoints()` returns `https://{host}`, so Ops
  shows the Review and Accept Certificate dialog.

### What is wrong

1. **The accepted certificate is never read.** The SDK passes what the user
   accepted as `certificate_config.certificates` in the adapter instance
   (`adapter_instance.py:60-67`), exposed as
   `AdapterInstance.get_certificates()` returning `CertificateInfo` objects
   with `get_certificate_string()` (PEM), `is_expired_certificate_accepted()`
   and `is_invalid_hostname_accepted()`. The SDK's own template says what to
   do with them: "Any certificate that is encountered in those methods should
   then be validated against the certificate(s) in the AdapterInstance"
   (`adapter.py.template:124-125`). No file in `app/` calls
   `get_certificates`. Result: the dialog prompts, the user accepts, and the
   connection still fails with `CERTIFICATE_VERIFY_FAILED`.
2. **The shipped default therefore fails.** The docs say so plainly
   (`README.md:335`, `QUICKSTART.md:76-77`, `REQUIREMENTS.md:99`), and the
   two remedies offered are "set it false" or "import the VMCA root into the
   container trust store". The second is not practical for a pak user (the
   container is rebuilt from the image), so in practice everyone runs
   unverified, and the accept prompt is theatre.
3. **The vendored version probe disables TLS verification for the whole
   process.** `perfsvc.py:195-197` calls
   `vsanapiutils.GetLatestVmodlVersion(host)`, which does
   `ssl._create_default_https_context = ssl._create_unverified_context`
   (`app/vendor/vsanapiutils.py:232`) before fetching
   `https://<host>/sdk/vsanServiceVersions.xml` unverified, even with the
   toggle on. pyVmomi calls pass an explicit context so they are not
   affected today, but any later stdlib HTTPS call in the process is. Note
   Broadcom's current copy bundled in pyVmomi 9.1.1.0 has the same line
   (`vsanapiutils.py:256-258`), so swapping to the upstream helper does not
   fix it.
4. When verify is off, `get_endpoints()` still triggers the accept prompt,
   for a certificate that is then not checked at all.

### The right change

pyVmomi 9.1.1.0 already implements exactly the semantics Ops wants:
`SmartConnect(..., serverPemCert=<pem>)` and
`SoapStubAdapter(..., serverPemCert=<pem>)` first try normal verification
and, only on `SSLCertVerificationError`, reconnect and require the peer
certificate to **exactly match** the pinned PEM
(`SoapAdapter.py:1116-1142`, `_Connect` / `_VerifyPinnedIdentity`). An
exact pin makes hostname and expiry moot, which matches what accepting a
certificate in Ops means, and it makes an IP address in the vCenter field
work once accepted.

Sketch of the PR:

- `adapter.py`: read `adapter_instance.get_certificates()` and pass the PEM
  strings into `perfsvc.connect(..., accepted_pems=[...])`.
- `perfsvc.connect`: when verify is on, use `ssl.create_default_context()`
  and pass `serverPemCert=` to `SmartConnect` and to the vSAN stub. The
  vendored `_GetVsanStub` takes only `context`, so either build the
  `SoapStubAdapter` directly in `perfsvc.py` (about 10 lines) or add a
  parameter to the vendored helper. If several certificates are accepted,
  try each, or fall back to a context that trusts them all (below).
- Replace `GetLatestVmodlVersion(host)` with a fetch of
  `vsanServiceVersions.xml` that uses the same verified context (or skip the
  probe and use `VmomiSupport.newestVersions.Get('vsan')`, since the 6.6
  branch it guards is long out of support). Either way, no global SSL
  mutation.
- `get_endpoints()`: return the URL only when verify is on, so the prompt
  appears only when its answer matters.
- Docs: drop "set it false for bring-up" and the container-trust-store
  advice from `README.md`, `QUICKSTART.md`, `REQUIREMENTS.md`; the field
  description at `adapter.py:76` ("Disable only for initial bring-up")
  becomes "Accept the certificate when prompted".
- Test: `test_cert_failure_names_the_remedy` (`test_perfsvc.py:251`) asserts
  the old remedy text and needs updating.

Alternative if the pinning path is unwanted: build the context with
`ctx.load_verify_locations(cadata=pem)` for each accepted cert **and**
`ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN`. The flag matters
because what Ops passes is the presented (leaf) certificate, not the VMCA
root (that is what `mp-test` emulates: `ssl.get_server_certificate`, the leaf,
`serialization.py:283`), and OpenSSL rejects a leaf as a trust anchor
without it. The base image is Python 3.11, where the flag exists (3.10+)
but is not on by default (3.13+). Honour
`is_invalid_hostname_accepted()` by clearing `check_hostname`. This path
cannot honour `is_expired_certificate_accepted()` (stdlib has no
expiry-only skip), which `mp-test` sets to true by default, mirroring Ops
(`serialization.py:286-292`). That gap is the reason to prefer the pin.

Size: about 50 to 80 changed lines across `adapter.py` and `perfsvc.py`,
plus docs and one test. Needs one live check against a VMCA-signed vCenter
(accept in the dialog, verify on, Validate Connection green, collect
green). `mp-test` exercises the hand-off locally because it fetches and
injects the endpoint certificate the same way.

## 2. Collection failures are silently discarded (rank 2, PR size XS)

`adapter.py:294-372` `collect()` is `try: ... finally:
_safe_disconnect(si)` with **no `except`**. Every `PerfSvcError` (bad
password, cert failure, no clusters, perf service returning nothing)
propagates out to `main()`, whose `finally` ends in `sys.exit(0)`
(`adapter.py:419-421`). `sys.exit` in a `finally` replaces the in-flight
exception, so the process exits 0, no result is written, and the exception
is never logged (`Timer.__exit__` logs only elapsed time, `timer.py:30-40`).
The operator gets a generic collection failure in Ops with no message and an
`adapter.log` with no traceback.

The `main()` block is the SDK template's verbatim, and it is safe in the
template only because the template's `collect()` catches:
`logger.exception(e)` then `result.with_error(...)`
(`adapter.py.template:94-97`). The adapter dropped that `except`.

Fix: add `except Exception as exc: logger.exception(...);
result.with_error(str(exc))` (and return the result). `CollectResult.with_error`
puts the adapter instance in an error state with that message
(`result.py:304-314`). About 5 lines. Highest value per line in this list,
and it is what makes every other failure visible.

## 3. One bad cluster aborts everything (rank 3, PR size S)

- `perfsvc.py:184-193` collects **every** `ClusterComputeResource`, vSAN or
  not.
- `perfsvc.collect()` raises `PerfSvcError` when a cluster yields no data
  (`perfsvc.py:633-639`), whatever the per-entity error was.
- `adapter.py:319-320` loops clusters with no per-cluster handling, so the
  first non-vSAN cluster, or a vSAN cluster with the Performance Service
  off, raises out of the loop and loses the data for all clusters. Combined
  with finding 2, silently.
- `test()` probes only `clusters[0]` (`adapter.py:264-265`): if the first
  cluster in inventory order is compute-only, Validate Connection fails
  with "Performance Service returned no data" while collection of the vSAN
  clusters would have worked; the reverse case passes test and then fails
  collect.

Established from code; not reproduced live (no mixed vSAN / non-vSAN lab
was used).

Fix: filter to vSAN-enabled clusters
(`cluster.configurationEx.vsanConfigInfo.enabled`, the same object
`perfsvc.py:222-224` already reads), catch `PerfSvcError` per cluster into
`total_problems`, raise only when every cluster failed; in `test()`, report
per cluster and pass if at least one vSAN cluster returns data. About 15 to
25 lines.

## 4. Credential storage (rank 4, PR size S code, breaking)

What is right: the password is a `CredentialPasswordParameter` in a
credential type (`adapter.py:90-96`), so Ops stores it encrypted and passes
it only in the per-call input (`adapter_instance.py:37-46`); the adapter
reads it with `get_credential_value` (`adapter.py:233-234`).

What is not: the **username is a plain identifier**
(`adapter.py:63-69`, `vcenter_user`). Identifiers are stored and shown in
clear on the account, and because `define_string_parameter` defaults to
`advanced=False`, it is emitted as `ident_type` 1 (`parameter.py:50`), so
the username is part of the account's uniqueness tuple. Rotating the
service account therefore edits account identity, and the credential cannot
be reused as a complete login across accounts from the Credentials page.
The native vCenter adapter keeps user and password together in its
credential.

Secrets reaching logs or files: none found.

- Nothing logs the password or the credential map. `main()` logs `argv`
  (`adapter.py:392`), which is method plus input and output file paths, not
  contents.
- Login failure text is `vCenter login failed for {user}@{host}: {exc}`
  (`perfsvc.py:176`); pyVmomi's `InvalidLogin` message carries no password.
- pyVmomi 9.1.1.0 has no logging in `SoapAdapter` / `connect` (only
  `Differ.py` imports `logging`), so raising `loglevels.cfg` to DEBUG does
  not expose the SOAP login body. The DEBUG `collect` line dumps the whole
  result JSON (`adapter.py:371`): large, not secret.
- The dormant host-scrape bearer token (`app/vsanmetrics.py`) is used only
  in a request header and never logged; `docs/soap/01-login.xml` uses
  placeholders; no tokens or passwords committed (grep).

Fix: add `cred.define_string_parameter("vcenter_user", "vCenter username")`
to the credential type and read the user from the credential, falling back
to the old identifier when the credential field is absent so existing
accounts keep working; retire the identifier in a later major version.
Code is small; the compatibility call (existing accounts need the user
re-entered into the credential, and removing an identifying field from the
describe changes account identity) is the maintainer's, so offer it as its
own PR with that trade stated.

## 5. Dependencies and pins (rank 5, PR size S, M with vendor removal)

- SDK lib pin `~=1.1.0` (`REQUIREMENTS.md:25,245`) is current: 1.1.0 is the
  newest release. Base image `base-adapter:python-1.2.0`
  (`Dockerfile.reference:2`), Python 3.11.12.
- **pyVmomi is required and undeclared.** `perfsvc.py:31,47-48` import it;
  the repo has no `adapter_requirements.txt`, `commands.cfg` or
  `manifest.txt` (generated by the scaffold and not committed, though
  `Dockerfile.reference:12-13` copies the first two), and `README.md:112`
  still says "Nothing to add to `adapter_requirements.txt` -- stdlib only",
  which was true for the host-scrape design and not since the move to the
  Performance Service. A build from a clean clone either fails at import or
  floats to whatever pyVmomi PyPI serves that day. Whether the published
  paks were built from an untracked requirements file was not checked.
- The vendored 2021 vSAN bindings (`app/vendor/`) need a monkeypatch shim
  for pyVmomi's removed `stableVersions` / `publicVersions`
  (`perfsvc.py:34-43`) and are put first on `sys.path` (`perfsvc.py:29`).
  pyVmomi 9.1.1.0 ships its own `vsanapiutils.py`, `vsanmgmtObjects.py` and
  `pyVmomi/_typeinfo_vsanhealth.py` (verified by listing the wheel; the
  first pyVmomi release to bundle them was not checked). So the vendored
  copy shadows a maintained one of the same module names.

Fix: commit `adapter_requirements.txt` (SDK lib plus a pinned pyVmomi that
has `serverPemCert`, which 9.1.1.0 does) and correct `README.md:112`: S.
Dropping `app/vendor/` in favour of pyVmomi's bundled bindings is a
separate M PR that needs a live regression run.

## 6. Datacenters inside folders are skipped (rank 6, PR size XS)

`perfsvc.py:191-193` walks only `content.rootFolder.childEntity` entries
that are themselves `vim.Datacenter`. A datacenter placed in a folder under
the root is a `vim.Folder` at that level and is skipped, so its clusters
are never collected and nothing reports it. `build_name_map` already uses a
`ContainerView` for VMs for the same reason (`perfsvc.py:230-237`). Fix: a
recursive `ContainerView` of `vim.ClusterComputeResource` from the root,
about 6 lines.

## 7. What Test Connection actually verifies (rank 7, folds into 3)

`adapter.py:249-278`. It proves:

- a vCenter host is configured;
- login succeeds with the configured user and credential, over the
  network path, under whatever TLS mode the toggle selects;
- at least one cluster of any kind is visible;
- a full query of every modelled entity type against `clusters[0]` returns
  at least one data row.

It does not prove: the other clusters; that the account can read what the
name map and parent map need (VM inventory, `QueryVsanManagedDisks`, the
vCenter instance UUID); those paths swallow every error by design
(`perfsvc.py:219-303, 370-460`), so missing privileges show up only as
UUID object names and missing relationships, never as a test failure. It
passes with verify off and gives no hint that the connection is
unverified. Per-entity problems are logged as a warning, not surfaced.
Suggested: fold into PR 3 (per-cluster result, pass on at least one vSAN
cluster), and fail or warn when `content.about.instanceUuid` is
unreadable, since without it no object gets a vCenter parent
(`perfsvc.py:367-374`).

## 8. Hostname handling (rank 8, folds into 1)

`_cfg` (`adapter.py:224-225`) returns the identifier raw. A value with
whitespace, an `https://` prefix, a trailing path, or a `:port` produces
`https://https://...` in `get_endpoints()` and a failed `SmartConnect`
(which also takes no port from the field). The field description says
"FQDN or IP" (`adapter.py:60`) while the docs say an IP fails verification
(`README.md:345-347`); with the pin from finding 1 an accepted IP works, so
the description becomes true. Fix: one normaliser used by
`get_endpoints()`, `connect()` and the version probe, about 10 lines.

## 9. Minor (XS each)

- The "unsupported entity types" summary is appended to `problems`
  (`perfsvc.py:626-631`), and almost every cluster has some, so the
  "collection problem(s)" warning at `adapter.py:363-367`, meant to be
  loud, fires every cycle and trains readers to ignore it. Keep the summary
  on its own INFO line.
- `GetLatestVmodlVersion` returns the plain `vim` version on any error
  (`app/vendor/vsanapiutils.py:243-247`), after which vSAN calls can fail
  with an obscure version error rather than the real cause. Goes away with
  the probe change in finding 1.
- `verify_certs` is `ident_type` 1 (part of account uniqueness). Moving it
  under Advanced Settings with `advanced=True` would also take it out of
  uniqueness, which is an identity change on existing accounts (same
  mechanism as `knowledge/context/investigations/2026-10-13-account-dialog-advanced-settings-and-cert-accept.md`
  §1). Leave as is unless bundled with the finding 4 major-version change.

## Suggested PR order

1. Finding 2 (XS): visible errors first, so the other PRs are testable.
2. Finding 1 with 8 (M): certificate pin, no global SSL mutation, hostname
   normaliser, docs.
3. Finding 3 with 7 and 6 (S): per-cluster isolation, vSAN filter, folder
   walk, better Test Connection.
4. Finding 5 (S): requirements file and README correction.
5. Finding 4 (S, breaking): username into the credential, with fallback.
6. Optional: drop the vendored bindings (M), minor items.
