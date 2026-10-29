# vsanhostmetrics tune-up review, 2026-10-28

- **Fork:** `content/sdk-adapters/vsanhostmetrics/` (sentania-labs/vsanhostmetrics)
- **Branch:** `tuneup/upstream-2026-10` at `dd533ca`, 10 commits on `origin/main` `c8dbdf5` (equal to `upstream/main`, nickfirefoot/vsanhostmetrics 1.4.7)
- **Scope reviewed:** fork issues #1, #2, #3, #4, #6, #7, #10, #11, planned as one upstream PR (version 1.5.0 set by the tag; `manifest.txt` unchanged per upstream RELEASING.md section 1)
- **Checklist:** `knowledge/context/python_integration_sdk.md` section 10
- **Verdict:** CHANGES REQUESTED (0 BLOCKING, 5 WARNING, 7 NIT)

There are no blocking defects. The certificate pin is correct for what `mp-test` hands the adapter. The process-wide SSL change is gone. Failures now reach Operations. The identity bits did not move. The five warnings are cheap to fix and should be fixed before the upstream PR opens.

## Claims check (what was rerun)

| Claim | Rerun | Result |
|---|---|---|
| Unit suites in the adapter image: 45/20/26 (1.4.7: 34/19/10) | Built `base-adapter:python-1.2.0` image from `git archive` of `dd533ca` and of `c8dbdf5`; ran each suite the way CI does (read-only mount, copied in, `--network none`) | Reproduced exactly: branch 45/45, 20/20, 26/26; base 34/34, 19/19, 10/10 |
| `mp-build` (SDK 1.3.1, headless) builds image and pak | `mp-build --no-ttl -r 127.0.0.1:5077/vsanhostmetrics` against a throwaway `registry:2` on 127.0.0.1, logged in beforehand with `--password-stdin` (no password on argv); registry, login and tags removed afterwards | rc 0, `VsanHostMetrics_1.4.7.pak`. The `.conf` `DIGEST` equals the registry's `Docker-Content-Digest` (`sha256:8c2ccf5c...7877`). describe: 70 ResourceKinds, 1701 attributes; credential `vcenter_username` (required=false, password=false) and `vcenter_password`; `vcenter_user` `required="false" identType="1"` |
| Identity unchanged (#4) | Dumped `get_adapter_definition().to_json()` inside both images and diffed | All identifier keys and every `ident_type` are unchanged. Only label, description and `required` changed on `vcenter_user`, and only descriptions on `vcenter_host` and `verify_certs`. The 69 object types are identical. The only addition is the credential field |
| Pin accepts the accepted cert, rejects others, login never on an unpinned connection (#1) | Own repro (`scratchpad/revtools/tlsrepro.py`): real pyVmomi 8.0.3.0.1 in the image against a local TLS server presenting a leaf signed by a private CA, recording every request body | Confirmed, see the table below. On every mismatch **zero POSTs** reach the server, so no SOAP body is sent on an unpinned connection |
| No global SSL state | Checked `ssl._create_default_https_context is ssl.create_default_context` before and after all connect paths; grepped app and image | Unchanged after every path. The only remaining unverified contexts are per-call: the verify-off path, the pinned path (the pin replaces verification), the vendored `GetLatestVmodlVersion` (no longer called by the adapter) and the dormant `vsanmetrics.py` |
| `HostConnectFault` handling | pyVim `connect.py:494-505` (8.0.3.0.1) re-raises inside `except`, so `__context__` holds the `ThumbprintMismatchException`; repro case 3 | `_pin_mismatch` walks the chain correctly. A mismatch reports "matches none", not "login failed" |
| Live `mp-test` against vcf-lab-vcenter-mgmt | Not rerun. I read the author's final run in `scratchpad/out/final/` (username masked) | Consistent with the PR body: fqdn, IP and URL pin and pass; noaccept and reject fail with the right text; verify off connects; nouser and legacyuser behave as stated; wld01 reports "none with vSAN enabled". The earlier `out/c1b/reject` run said "login failed"; it predates the `_pin_mismatch` fix |
| 183 "not defined in describe.xml" warnings are pre-existing on 1.4.7 | Looked for a 1.4.7 collect run in the author's outputs; read `perfsvc.collect` | **No 1.4.7 collect against a vSAN cluster exists in the author's outputs** (the base runs are wld01, which has no vSAN). The claim still holds by construction: describe is identical, and the emission loop (`perfsvc.py:983-997`) is untouched by the diff. That loop filters only `<name>Actual` whose base is in `keep`; it never filters labels by `keep` itself. See NIT 5 |
| Secret hygiene | Scanned 759 files (author `out/`, `PR_BODY.md`, my outputs, the fork tree) in-process against the six lab passwords from the factory `.env`; nothing printed | 0 password hits. The only hits were `VCENTER_CREDENTIAL`, which is a UPN username, in login-failure lines in `out/c1b`. `/dev/shm` is empty, so the author's `connections.json` was removed |
| Em-dashes | Grepped the added lines, the commit messages and the PR body for U+2014 | None |

Workflow: the diff does not touch `.github/workflows/`, so actionlint and the Trivy gate do not apply.

### Accept/reject repro (pyVmomi 8.0.3.0.1, self-signed chain)

| Case | POSTs | Outcome |
|---|---|---|
| verify on, nothing accepted | 0 | "not trusted ... no certificate has been accepted" |
| verify on, leaf accepted (FQDN, and IP) | 1 | pin passed, reached SOAP |
| verify on, a different cert accepted (reject, or a renewed vCenter cert) | 0 | "matches none of the 1 certificate(s)" |
| verify on, **issuing CA accepted instead of the leaf** | 0 | "matches none" (fails closed, see WARNING 2) |
| verify on, other then leaf | 1 | second PEM matched |
| verify on, PEM with a leading newline | 0 | **raw `ValueError: Invalid PEM encoding`**, loop aborted (WARNING 3) |
| verify on, a non-PEM entry before the leaf | 0 | **raw `ValueError`**, the valid leaf never tried (WARNING 3) |
| verify off | 1 | no pin, connects unverified (documented in the field help) |
| verify on, CA in the bundle, nothing accepted (FQDN and IP SAN) | 1 | CA path, no pin needed |
| vSAN stub, pin match / mismatch | n/a | connects / `ThumbprintMismatchException` |

Renewal behaviour is as documented: a renewed or replaced vCenter certificate fails closed with the re-accept instruction. Verify off skips the pin, which the field help, README and QUICKSTART all say ("False turns certificate checking off entirely"), and `get_endpoints` then returns nothing.

## BLOCKING

None.

## WARNING

1. **No timeout on any vCenter call, in lines this branch rewrote.** `app/perfsvc.py:286` (`SmartConnect` in `_login`) and `app/vendor/vsanapiutils.py:59` (`SoapStubAdapter` for `/vsanHealth`) pass no `httpConnectionTimeout`, so pyVmomi uses none. SmartConnect's version probe (`pyVim/connect.py` `__GetElementTree`) also has none. The Cloud Proxy has no collector timeout (SDK section 1.1), so a vCenter that accepts the TCP connection and then stalls hangs that collection indefinitely. The gap predates this branch, but `_login` and `_GetVsanStub` are new or edited here, and it is a checklist item. Fix: pass `httpConnectionTimeout` (for example 60 s) to `SmartConnect`, and add the same parameter to the vendored `_GetVsanStub`/`GetVsanVcStub`/`GetVsanVcMos` (mark it LOCAL CHANGE like the thumbprint). The version probe takes no timeout argument; since the adapter is a one-shot subprocess, `socket.setdefaulttimeout()` at the top of `connect()` covers it.

2. **The pin works only if Operations hands back the leaf, and that is unproven.** `perfsvc.py:247-262` compares SHA-256 of each accepted PEM's DER against the presented leaf. `mp-test` stores the leaf (`cli:serialization.py:274-295`), so the live proof is real. What the Operations dialog stores was not established (SDK reference "Not established from source"). Repro case 4 shows that an accepted issuing CA fails closed with "matches none". If any of 8.18, 9.0 or 9.1 stores a CA or a chain, verify-on cannot work there, and users go back to `false`. Fix before the upstream PR:
   - In the three-version proof, record subject, issuer and SHA-256 of every entry in `certificate_config` on each version. A mismatch log line that prints these would serve.
   - Put the presented SHA-256 (`ThumbprintMismatchException.actual`) and the accepted SHA-256s in the "matches none" error, so a field failure can be diagnosed from the UI.
   - If any version sends a CA, add the trust-anchor fallback from SDK section 3.3 pattern 2 (`load_verify_locations(cadata=...)` plus `VERIFY_X509_PARTIAL_CHAIN`).

3. **One malformed accepted-certificate entry aborts the whole pin loop with a raw `ValueError`.** `_thumbprint` (`perfsvc.py:193`) is called at `:248`, outside the per-PEM `try`, so a PEM with leading whitespace, or the string `"None"`, raises `ValueError: Invalid PEM encoding` (repro cases 6 and 7b). `CertificateInfo.get_certificate_string()` returns `str(None)` when the key is missing, and `adapter.py:545` passes it through. A valid accepted cert later in the list is never tried, and the user sees a meaningless error. Fix: parse each PEM inside the loop (`cert.get_certificate_object().public_bytes(Encoding.DER)` is the SDK's own parser, or `.strip()` before `PEM_cert_to_DER_cert`); log and skip an unparseable entry; if none parse, report "no usable accepted certificate".

4. **The README tells users to edit an identifying field and states an unproven outcome as fact.** `README.md:452-457` (and `BACKLOG.md:19`) say to "clear *vCenter username (deprecated)*" and that "The old field stays part of the account's identity, as it was, so no account is re-created". The reasoning is backwards: because `vcenter_user` keeps `identType="1"`, clearing it **is** a change to the account's identifying set. How Operations handles that edit on an existing adapter instance (in-place update, uniqueness collision with another account, re-created resources) is exactly what the PR body lists under "could not prove". The README sentence breaks upstream `CLAUDE.md` rules 2 and 4 (verify the outcome; do not claim what was not measured). Fix, either way:
   - Prove it on the three-version run: upgrade over 1.4.7, clear the field, and confirm the same adapter instance UUID, the same object IDs and continuous metric history.
   - Or change the advice to "enter the username in the credential; the old field is then ignored and can be left as is", and drop the "no account is re-created" claim.

5. **The non-vSAN pre-filter may silently drop clusters 1.4.7 collected.** `adapter.py:571` skips any cluster whose `configurationEx.vsanConfigInfo.enabled` is False, logged only at INFO. A vSAN compute cluster (HCI Mesh / vSAN Max client mounting a remote vSAN datastore) may report `enabled` False while the Performance Service still serves its client-side entities. 1.4.7 queried every cluster. This was not verified either way (the lab has no such cluster). Fix: either confirm on a compute cluster, or drop the pre-filter. Query every cluster, and when a cluster with `enabled is False` raises "returned no data", log it at INFO as not-vSAN rather than counting it as a failure. That keeps the wld01 behaviour and loses no coverage.

## NIT

1. **A deleted cluster can still sink the cycle.** `adapter.py:572` and `:729` read `cluster.name` with `getattr(..., "?")` outside any per-cluster `try`. `getattr` defaults only on `AttributeError`, and a cluster removed between the ContainerView read and these lines raises `vmodl.fault.ManagedObjectNotFound`, which fails the whole cycle (fix #3's failure mode, in a narrow race). Move the name read inside the per-cluster `try`, or fetch names with the view.
2. **`with_error` and test text carry the full pyVmomi fault repr.** `perfsvc.py:294` interpolates the fault into the message; the repro shows `(vim.fault.HostConnectFault) { dynamicType = <unset>, dynamicProperty = ...` in the user-facing error. Use `exc.msg` when the exception is a `vmodl.MethodFault`.
3. **The deprecated username can disagree with the credential, and nothing says so.** When both are set and differ, the credential wins and nothing is logged. One INFO line saying the deprecated field is ignored would help the migration.
4. **Fork-tracker references would land in upstream history.** Every commit ends `Refs: sentania-labs/vsanhostmetrics#N`, and upstream history uses no such trailer. Keep the fork references in the PR body and drop them from the commits.
5. **The PR body overstates the 183-warning proof.** "This is the same on 1.4.7" reads as measured, but no 1.4.7 collect against a vSAN cluster was run. Say "unchanged by construction: describe and the emission loop are identical", or run it. Upstream rule 4 again.
6. **Pre-existing gaps the branch does not touch (follow-up issues, not this PR):**
   - The Suite API attach path (`adapter.py:382-450`) has no timeouts; it is off by default.
   - `app/vendor/vsanapiutils.py` shadows the `vsanapiutils` module that pyVmomi 8.0.3.0.1 installs at site-packages top level (that copy still flips the global SSL default, and the vendored path wins only because of `sys.path.insert(0, ...)`). This is a checklist item, so name it in the vendor docstring.
   - The `tools/` scripts connect unverified; the PR body discloses this.
7. **Factory process, not the PR.** `out/mpbuild3.raw` shows `docker login --password` on argv: `--registry-password` was used, contrary to SDK section 4. The credentials were dummies for a throwaway registry, so nothing was exposed. Log in beforehand with `--password-stdin`, as this review did.

## Checklist (section 10) summary

- **Certificates:**
  - Endpoint from the normalised host, empty when verify is off: pass.
  - `get_certificates()` used with a pin on both stubs: pass.
  - No global SSL change: pass.
  - One context per pinned connection: pass (fresh unverified context per PEM attempt, no `serverPemCert` mutation in 8.0.3.0.1).
  - Robustness of the pin: W2, W3.
- **Credentials:**
  - Username moved into the credential: pass.
  - No secret in logs, identifiers or messages: pass.
  - `connections.json`, `logs/`, `build/` gitignored: pass.
- **Error reporting:**
  - `collect` and `test` catch, log and call `with_error`: pass.
  - `sys.exit(0)` removed from `finally`: pass.
  - Per-cluster isolation, `with_error` only when all clusters fail: pass (N1 race).
  - `test` probes every vSAN cluster: pass.
- **Timeouts:** fail (W1).
- **Tokens:** Suite API path unchanged; the token check is present; no DEBUG raise.
- **Definition and identity:**
  - Identity bits unchanged: pass.
  - The identity edit in the migration advice is unproven (W4).
- **Dependencies:**
  - No new third-party imports (`hashlib`, `urllib.parse`, `pyVmomi.Security` in the pinned 8.0.3.0.1): pass.
  - SDK pins as expected: pass.
  - Vendored shadowing: N6.
- **Packaging:** the pak builds and the digest is read back and matches; version comes from the tag per upstream discipline.

## If shipped as-is

- Users who follow the new README leave verification on and accept the certificate. That works as long as Operations hands back the leaf, as `mp-test` does.
- On any Operations version that stores the CA instead, every new account fails "matches none", and users turn verification off again.
- A vCenter that stalls mid-call hangs that collection with no timeout, as it does today.
- Users who follow the migration step clear an identifying field on a live account, and the outcome is unknown.
- Owners of vSAN compute or HCI Mesh client clusters may lose those clusters with only an INFO line to say so.
- Nothing is silently swallowed any more, and no credential reaches a log.
