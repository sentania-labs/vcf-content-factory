# Upstream issue drafts for vmware/vmware-vcf-operations-integration-sdk (2026-10-13)

**Status: drafts for Scott's review. Nothing has been filed.** Filing goes out
under Scott's GitHub identity, so each issue needs his explicit go
(CLAUDE.md rule 8).

Investigator: `api-explorer`. Target repo:
https://github.com/vmware/vmware-vcf-operations-integration-sdk, clone at
`reference/references/vmware-vcf-operations-integration-sdk/`, commit `9619df8`
(main, 2026-09-28). That commit is CLI 1.3.1, lib 1.1.0 and base image
`python-1.2.0`. All three are the newest published versions on PyPI as of
today. Every line number below is from that clone.

## How each claim was checked

- Every candidate was read in source at the cited line.
- Every repro that appears in a draft was run today against the **published**
  packages, in scratch venvs: `vmware-aria-operations-integration-sdk-lib==1.1.0`
  and `vmware-aria-operations-integration-sdk==1.3.1` from PyPI. Outputs
  quoted in the drafts are copied from those runs. No live Ops was involved.
  The Suite API client repros patch `requests.post`, and an earlier pass used
  a local stub HTTP server, with the same results.
- The Trivy findings come from the fork CI run
  `gh run view 38471417171 -R sentania-labs/cluster-perf-risk --log` (scan at
  4:33 PM today). The scan passed only because the fork's `.trivyignore.yaml`
  lists eight known findings. The log echoes that file, and its entries are the
  source for the advisory IDs. Fixed versions come from the OSV / GitHub
  advisory database (api.osv.dev), queried today.
- The vendored pip copies (candidate 2) were located in the locally built
  `base-adapter:python-1.2.0` image (built from the SDK Dockerfile today, with
  pip 26.2.1) by a read-only `docker run --rm`.
- Duplicate check: all 158 issues (open and closed) and 300 PRs were pulled
  with `gh issue list` / `gh pr list`, and body searches were run with
  `gh search issues --include-prs`. Related items: #161 (open, certificate
  helpers), #270 (closed, same registry parser, different input), #83 (open,
  enum ordering, platform side, not this bug), #443 (merged, CVE fixes in the
  base image only, lib pin untouched), #403 (merged, introduced the
  `cryptography == 44.0.0` pin with `CertificateInfo`). Nothing else covers any
  candidate.

## Grouping decisions

- **3, 4 and 5 become three issues.** They have different fixes with different
  risk. Item 4 (token logged) is a near one-line fix a maintainer can merge
  quickly. Item 3 (verify default) has a compatibility trade-off and needs
  discussion. Item 5 changes behavior callers may depend on. Bundling them
  would park the easy fix behind the hard one.
- **10 folds into 5.** Same function (`_paged_request`), same root
  (failures are not surfaced), and one fix covers both.
- **11 folds into 1.** Same three lines of `lib/python/setup.cfg`, one PR.
- **6 and 7 are one issue.** Both are serializer bugs in the CLI's
  `describe.py`, both are one-line fixes, and both show up in the same
  generated `describe.xml`. Note that they are **CLI** bugs, not lib bugs as
  the candidate list said: the lib emits `is_kpi` and the enum default
  correctly in its JSON, and the CLI drops or miscompares them.
- **13 is one issue**, about the registry password on argv. The
  `connections.json` half shrank to a one-paragraph side ask (see Dropped).
- **14 is a comment on the existing open #161**, not a new issue.

## Recommended filing order

1. Issue 1: cryptography pin and undeclared requests (every pack built from
   the current `mp-init` template inherits it, and packs cannot override it).
2. Issue 2: Suite API client reports failures as empty results.
3. Issue 3: token and response bodies at DEBUG (small, quick to merge).
4. Issue 4: verify off by default, warning silenced process-wide.
5. Issue 5: `describe.xml` drops `isKpi`, enum per-value default always false.
6. Issue 6: `get_objects_by_type` compares the wrong field.
7. Issue 7: `suite-api/` prefix sent as a relative URL.
8. Issue 8: registry host without a dot parsed as Docker Hub (cross-ref #270).
9. Issue 9: registry password on the `docker login` command line.
10. Comment on #161: certificate example.

## Dropped, and why

- **Candidate 2 (pip's vendored msgpack, urllib3, setuptools in the base
  image) is dropped as an SDK issue.** The premise was that rebuilding the base
  image with current pip clears the findings. It does not. The fork CI rebuilt
  the base image from the SDK Dockerfile today, and that Dockerfile already
  runs `pip3 install --no-cache-dir --upgrade pip setuptools wheel`
  (`images/base-python-adapter/Dockerfile`). It installed pip 26.2.1, which is
  the current release on PyPI. Inside that image,
  `pip/_vendor/vendor.txt` lists `msgpack==1.1.2`, `urllib3==2.7.0` and
  `setuptools==70.3.0`, the exact versions Trivy flagged
  (GHSA-6v7p-g79w-8964, CVE-2026-97687, CVE-2026-97689, CVE-2025-47273). They
  ship inside pip itself, so nothing in this repo can clear them short of
  removing pip from the final image (a multi-stage redesign, since the pack
  Dockerfile runs `pip3 install` on top of the base image). If anything is
  filed, it belongs with pypa/pip, and that is out of scope here.
- **The `connections.json` plaintext half of candidate 13 is dropped as a
  defect.** Plaintext storage is documented with a warning
  (`docs/references/project_connections_config.md:4-9`), and the file is
  added to `.gitignore`. That is a design choice, not a bug. What survives is
  a small ask inside issue 9: create the file `0600`. Today it is created with
  plain `open(..., "w")` (`config.py:74, 82`; `project.py:241`), so it gets
  the process umask, which is usually 0644.
- **Nothing else was dropped.** Candidates 1 and 3 to 14 all reproduced.

## Things Scott should know before filing

- **First person is limited to what actually happened.** "I" in pass two
  covers building and reviewing the two fork packs on SDK 1.3.1 / lib 1.1.0,
  the fork CI Trivy scan, and the scripted repros run today. No draft claims a
  failure seen in production or on a live Ops, because none was. Issue 2
  says the cluster-perf-risk empty-collection defect was **found in review**,
  because the assessment found it in source, not live.
- **Issue 8 was reproduced at the parser, not by a full `mp-build` run.** The
  conf values in that draft (`REGISTRY=registry.hub.docker.com`,
  `REPOSITORY=/localhost`) are derived from the parser output plus
  `mp_build.py:415-420, 502-503`, and the draft says so. If Scott has the
  actual `mp-build` output from today's session, paste it in; it is
  stronger.
- **Issue 5's enum half has an unverified effect.** The `ResourceIdentifier`
  `default` attribute is right, and I did not check what the account dialog
  preselects. The draft says that plainly rather than claiming a visible UI
  bug.
- **Issue 4 deliberately does not ask to flip the default.** Defaulting to
  `verify=True` would break packs whose Ops certificate is not in the
  container trust store (self-signed or VMCA, the common case).
- **Advisory IDs in issue 1 are 2026 IDs from today's Trivy DB.** Re-run the
  OSV lookup on filing day if more than a few weeks pass.

---

## Issue 1: cryptography exact pin, undeclared requests and urllib3 (candidates 1 and 11)

### Pass one

````markdown
Title: lib: exact pin cryptography == 44.0.0 carries fixable HIGH CVEs; requests/urllib3 not declared

**What happens**
vmware-aria-operations-integration-sdk-lib 1.1.0 pins cryptography exactly to
44.0.0. Four HIGH advisories against 44.0.0 have fixed releases. Every pack
built on the lib inherits them, and container scans flag them.
The lib also imports requests and urllib3 without declaring them.

**Where**
lib/python/setup.cfg:25-27
    install_requires =
        aenum == 3.1.11
        cryptography == 44.0.0
lib/python/src/aria/ops/suite_api_client.py:15-16 (import requests, import urllib3)

**Advisories (Trivy, 2026-10-13)**
- CVE-2026-26007 (GHSA-r6ph-v2qm-q3c2), fixed in 46.0.5
- GHSA-537c-gmf6-5ccf (bundled OpenSSL), fixed in 48.0.1
- CVE-2026-69249 (GHSA-jwv3-5hgf-82ww), fixed in 49.0.0
- CVE-2026-69247 (GHSA-g6cj-pr64-35w5), fixed in 50.0.0

**Reproduce**
1. Scan any adapter image built from the mp-init template with Trivy.
2. pip install lib 1.1.0 into a clean venv; import aria.ops.suite_api_client
   -> ModuleNotFoundError: requests.

**Effect on pack authors**
Packs cannot raise the version: pip reports ResolutionImpossible.
Unit tests outside the base image fail on import.

**Proposed fix**
cryptography >= 44.0.0 (floor, not pin); add requests to install_requires.
Lib tests pass with cryptography 50.0.2.
````

### Skeptical reread, what changed

- "Every pack built on the lib" was too broad. The samples pin lib `0.7.*` /
  `0.8.*`, and the pin arrived in 1.1.0 (#403). Narrowed to packs on lib
  1.1.0, which is what the current `mp-init` template requests (`~=1.1.0`).
- The ResolutionImpossible claim needed the exact command and output, which
  were added.
- Added the python_requires trade-off: cryptography 50 requires Python 3.9 or
  later, and setup.cfg says `>=3.6`. That is why the fix is a floor, not
  `>= 50`.
- "Unit tests outside the base image fail" was checked against our own CI
  notes: tests were moved into the adapter image for exactly this reason. That
  is now stated as what we did, not as a general claim.

### Pass two (file this)

````markdown
Title: lib 1.1.0 pins cryptography==44.0.0, which has four fixed HIGH advisories, and packs can't override it

Our pack CI runs Trivy against the adapter image. The only fixable HIGH findings we can't clear ourselves come from cryptography 44.0.0, which is there because `lib/python/setup.cfg:27` pins it exactly:

```
    cryptography == 44.0.0
```

These are the advisories Trivy reported on 2026-10-13, with the first fixed release according to the GitHub advisory database:

| Advisory | Fixed in |
|---|---|
| CVE-2026-26007 (GHSA-r6ph-v2qm-q3c2) | 46.0.5 |
| GHSA-537c-gmf6-5ccf (OpenSSL bundled in the wheel) | 48.0.1 |
| CVE-2026-69249 (GHSA-jwv3-5hgf-82ww) | 49.0.0 |
| CVE-2026-69247 (GHSA-g6cj-pr64-35w5) | 50.0.0 |

A pack can't raise the version on its own. I tried adding a newer cryptography next to the template's lib line:

```
$ cat adapter_requirements.txt
vmware-aria-operations-integration-sdk-lib~=1.1.0
cryptography>=46.0.5
$ pip install -r adapter_requirements.txt
ERROR: Cannot install -r adapter_requirements.txt (line 1) and cryptography>=46.0.5 because these package versions have conflicting dependencies.
ERROR: ResolutionImpossible: for help visit https://pip.pypa.io/en/latest/topics/dependency-resolution/#dealing-with-dependency-conflicts
```

The lib only calls `x509.load_pem_x509_certificate` (`certificate_info.py:27`). I ran the lib's own tests (116) against cryptography 50.0.2 and they pass, and `CertificateInfo.get_certificate_object()` parses a PEM fine on it.

My suggestion is a floor instead of a pin, `cryptography >= 44.0.0`, in a 1.1.1 release. I wouldn't pin `>= 50`: cryptography 50 needs Python 3.9 or later, and setup.cfg still says `python_requires = >=3.6`. With a floor, pip picks the newest wheel the interpreter supports, which is 50.x on the 3.11 base image.

One more thing in the same file. The lib imports `requests` and `urllib3` (`suite_api_client.py:15-16`) but doesn't declare either. Inside the base image you don't notice, because connexion pulls in requests. In a plain venv you do:

```
$ python3 -m venv v
$ v/bin/pip install vmware-aria-operations-integration-sdk-lib==1.1.0
$ v/bin/python -c "import aria.ops.suite_api_client"
ModuleNotFoundError: No module named 'requests'
```

We ended up running our pack unit tests inside the adapter image because of this. Adding `requests` to `install_requires` (it brings urllib3 with it) would fix it.
````

---

## Issue 2: Suite API client reports failures as empty results (candidates 5 and 10)

### Pass one

````markdown
Title: lib: SuiteApiClient failures look like successful empty results (token acquire, paging)

**What happens**
1. get_token() logs a WARNING on a failed /api/auth/token/acquire and leaves
   the token empty. Later calls go out without Authorization and get 401.
2. _paged_request returns {key: []} when the first page is non-2xx.
3. A failed later page reuses the previous page body, or raises
   UnboundLocalError if no later page succeeded yet.
4. query_for_resources catches every exception and returns [].

**Where**
suite_api_client.py:114-120, 314-322, 329-335, 291-294

**Reproduce**
Script patching requests.post (below). Output:
    token: ''
    paged_post: {'resourceList': []}
    page 2 fails: UnboundLocalError
    page 1 fails: {'resourceList': [{'id': 'r0'}, {'id': 'r2'}, {'id': 'r2'}]}

**Effect on pack authors**
Bad credentials, 403s and 5xx are indistinguishable from "no objects".
Collections report success with no data, or duplicate objects.

**Proposed fix**
Raise a SuiteApiError on token failure and on any non-2xx page;
let query_for_resources propagate it.
````

### Skeptical reread, what changed

- Checked the claim "a 401 looks like zero results" against the stub run, not
  only the source. Confirmed.
- The first page goes through the same `_paged_request`, so the claim that
  "the first-page failure is the same function as the later-page bug" holds.
  One issue is justified.
- Pass one implied an observed production failure. The cluster-perf-risk
  defect was found in review, so the draft now says that.
- Added the trade-off (behavior change for callers relying on `[]`) and an
  opt-in alternative, so the ask is not all-or-nothing.
- Added the page-order oddity (0, then N-1 down to 1) as a side note only. It
  is in the same function and was observed in the stub run.

### Pass two (file this)

````markdown
Title: SuiteApiClient reports failures as empty results (failed token acquire, failed pages)

While reviewing a pack that reads from the Suite API, I found that a failed Suite API login would show up as a successful collection with no data. Tracing it led to a few spots in `suite_api_client.py` where a failure quietly turns into "nothing found".

`get_token()` only warns when `/api/auth/token/acquire` fails (lines 118-120, `logger.warning(f"Could not acquire SuiteAPI token: {token_response}")`). The `with` block carries on, and every later request goes out without an Authorization header and gets a 401. `_paged_request` then turns a non-2xx first page into an empty list (line 322, `return {key: []}`, right under the existing TODO asking how to tell the caller).

Later pages have a separate problem. `page_n_body` is only assigned on success (lines 331-334), so a failed later page either raises `UnboundLocalError` (when it's the first later page requested) or re-adds the previous page's objects. `query_for_resources` catches every exception and returns `[]` (lines 291-294), so through that method all of these end up as an empty list.

This runs without an Ops instance:

```python
import json
from unittest import mock
import requests
from aria.ops.suite_api_client import SuiteApiClient, SuiteApiConnectionParameters

def resp(status, body):
    r = requests.models.Response()
    r.status_code = status
    r._content = json.dumps(body).encode()
    return r

def fake_post(url, fail_page=None, token_ok=True, **kwargs):
    if url.endswith("auth/token/acquire"):
        return resp(200, {"token": "t"}) if token_ok else resp(401, {})
    if url.endswith("auth/token/release"):
        return resp(200, {})
    if "Authorization" not in kwargs["headers"]:
        return resp(401, {})
    page = kwargs["params"]["page"]
    if page == fail_page:
        return resp(500, {})
    return resp(200, {"pageInfo": {"totalCount": 3},
                      "resourceList": [{"id": f"r{page}"}]})

params = SuiteApiConnectionParameters("ops.example.com", "user", "pw")

with mock.patch("requests.post", lambda url, **kw: fake_post(url, token_ok=False, **kw)):
    with SuiteApiClient(params) as c:
        print("token:", repr(c.token))
        print("paged_post:", c.paged_post("/api/resources/query", "resourceList", json={}))

with mock.patch("requests.post", lambda url, **kw: fake_post(url, fail_page=2, **kw)):
    with SuiteApiClient(params) as c:
        try:
            c.paged_post("/api/resources/query", "resourceList", json={}, pageSize=1)
        except Exception as e:
            print("page 2 fails:", type(e).__name__)

with mock.patch("requests.post", lambda url, **kw: fake_post(url, fail_page=1, **kw)):
    with SuiteApiClient(params) as c:
        print("page 1 fails:", c.paged_post("/api/resources/query", "resourceList",
                                             json={}, pageSize=1))
```

On lib 1.1.0 that prints:

```
token: ''
paged_post: {'resourceList': []}
page 2 fails: UnboundLocalError
page 1 fails: {'resourceList': [{'id': 'r0'}, {'id': 'r2'}, {'id': 'r2'}]}
```

For a pack, bad credentials, a 403 and a 500 all look the same as an environment with zero matching objects, so the collection goes green and the dashboards go empty.

What I'd suggest is a `SuiteApiError` raised from `__enter__` when no token comes back, and from `_paged_request` on any non-2xx page, with `query_for_resources` letting it through. That changes behavior for packs that currently get `[]`, so it probably wants a minor version and a CHANGELOG line. If you'd rather keep the default, an opt-in `raise_on_error=True` on the client would work for us too.

Side note from the same function: pages come back in the order 0, N-1, ..., 1 because `remaining_pages` counts down. Probably harmless, but it surprised me.
````

---

## Issue 3: token and response bodies logged at DEBUG (candidate 4)

### Pass one

````markdown
Title: lib: SuiteApiClient logs the session token and response bodies at DEBUG

**What happens**
With DEBUG enabled for aria.ops.suite_api_client, adapter.log receives the
live token and every response body.

**Where**
suite_api_client.py:116   logger.debug("Acquired token " + self.token)
suite_api_client.py:351   logger.debug(result.text)

**Reproduce**
Script below; output shows the token twice.

**Effect on pack authors**
Anyone turning on DEBUG to troubleshoot writes a usable bearer token to disk.

**Proposed fix**
Don't log the token; skip or truncate bodies.
````

### Skeptical reread, what changed

- Checked whether DEBUG is on by default. It is not: `adapter_logging.py`
  defaults to INFO, and DEBUG comes from `/var/log/loglevels.cfg`. The draft
  now says it is opt-in, so it does not overstate exposure.
- Confirmed the token appears **twice** (line 116, plus line 351 logging the
  acquire response body). That is the most concrete detail, so it leads.
- Dropped a pass-one thought that adapter logs end up in support bundles. That
  was not verified.

### Pass two (file this)

````markdown
Title: SuiteApiClient writes the Suite API token and every response body to the log at DEBUG

When DEBUG is on for `aria.ops.suite_api_client` (through `loglevels.cfg`, which is what you'd do while troubleshooting a pack), the live token gets logged twice. Line 116 logs it directly:

```python
                    logger.debug("Acquired token " + self.token)
```

Line 351 then logs every response body, and that includes the `/auth/token/acquire` response. Repro without an Ops instance:

```python
import json, logging
from unittest import mock
import requests
from aria.ops.suite_api_client import SuiteApiClient, SuiteApiConnectionParameters

logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")
for name in ("urllib3", "charset_normalizer"):
    logging.getLogger(name).setLevel(logging.WARNING)

def fake_post(url, **kwargs):
    r = requests.models.Response()
    r.status_code = 200
    body = {"token": "abc123-live-token"} if url.endswith("acquire") else {}
    r._content = json.dumps(body).encode()
    return r

with mock.patch("requests.post", fake_post):
    with SuiteApiClient(SuiteApiConnectionParameters("ops.example.com", "u", "p")):
        pass
```

```
aria.ops.suite_api_client INFO fake_post https://ops.example.com/suite-api/api/auth/token/acquire: OK(200)
aria.ops.suite_api_client DEBUG {"token": "abc123-live-token"}
aria.ops.suite_api_client DEBUG Acquired token abc123-live-token
aria.ops.suite_api_client INFO fake_post https://ops.example.com/suite-api/api/auth/token/release: OK(200)
aria.ops.suite_api_client DEBUG {}
```

The token stays valid until it's released or expires, and the rotated log files stay on disk afterwards. INFO is the default, so this only bites once someone turns DEBUG on, but that's also when people tend to pass logs around.

Could line 116 just say "Acquired token" without the value, and line 351 skip the body for the `auth/token/*` endpoints? Truncating other bodies to a few hundred characters would keep most of the debugging value and keep the log size sane.
````

---

## Issue 4: verify off by default, warning silenced process-wide (candidate 3)

### Pass one

````markdown
Title: lib: SuiteApiClient defaults verify=False and disables InsecureRequestWarning process-wide

**What happens**
_to_vrops_request sets verify=False unless the caller passes verify=.
Importing the module calls urllib3.disable_warnings for InsecureRequestWarning.

**Where**
suite_api_client.py:22    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
suite_api_client.py:360   kwargs.setdefault("verify", False)

**Reproduce**
Print warnings.filters before and after import; print the verify kwarg.

**Effect on pack authors**
The platform-supplied Ops password goes to auth/token/acquire over unverified
TLS. Any unverified request the pack makes to its own target is also
silenced.

**Proposed fix**
Default verify=True.
````

### Skeptical reread, what changed

- **Changed the ask.** Defaulting to `verify=True` would break every pack
  whose Ops certificate is not in the container trust store, which is the
  common self-signed or VMCA case. A maintainer would reject it. The fix is
  now two compatible changes: scope the warning suppression to the client,
  and add a `verify` setting on the connection parameters.
- Added the platform constraint a maintainer would raise next: `get_endpoints`
  gets no Suite API client (`adapter_instance.py:71-80` docstring: "Returns
  'None' when called from 'test' and 'get_endpoints'"), so a pack cannot offer
  the Ops certificate for acceptance today.
- Led with the process-wide warning, which is the least debatable part.

### Pass two (file this)

````markdown
Title: Importing suite_api_client silences InsecureRequestWarning for the whole process, and the client defaults to verify=False

Line 22 of `suite_api_client.py` runs at import time:

```python
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

That covers the entire adapter process, not just the client. Once a pack imports `aria.ops.suite_api_client`, its own `requests` calls to its target with `verify=False` stop warning too, and that warning is one of the few signs a pack author gets that verification is off. A quick check:

```python
import warnings, urllib3
before = [f for f in warnings.filters if f[2] is urllib3.exceptions.InsecureRequestWarning]
from aria.ops.suite_api_client import SuiteApiClient, SuiteApiConnectionParameters
after = [f for f in warnings.filters if f[2] is urllib3.exceptions.InsecureRequestWarning]
print("filters before import:", before)
print("filters after import: ", after)
c = SuiteApiClient(SuiteApiConnectionParameters("ops.example.com", "u", "p"))
print("verify:", c._to_vrops_request("/api/resources")["verify"])
```

```
filters before import: []
filters after import:  [('ignore', None, <class 'urllib3.exceptions.InsecureRequestWarning'>, None, 0)]
verify: False
```

The second part is `kwargs.setdefault("verify", False)` at line 360. Because it's `setdefault`, a pack can pass `verify=` on every call, but nothing lets it set this once. The POST to `/api/auth/token/acquire` carries the platform-supplied Ops username and password over that connection.

I'm not asking to flip the default. The Ops certificate is often self-signed or VMCA-signed and not in the container's trust store, so `verify=True` by default would break working packs. What would help:

1. Move the warning suppression inside the client, wrapped around the client's own requests (`warnings.catch_warnings()` when verify is off), so it stops leaking into pack code.
2. Accept a `verify` value (bool or CA bundle path) on `SuiteApiConnectionParameters` that the client uses as its default, so a pack can turn verification on in one place.

Longer term, a pack can't offer the Ops certificate for acceptance the way it does for its target: `get_suite_api_client()` returns None in `get_endpoints` (`adapter_instance.py:71-80`), so the pack doesn't know the Ops host at that point. That probably needs input from the platform side, and I'm only mentioning it for context.
````

---

## Issue 5: `describe.xml` drops `isKpi` and miscompares the enum default (candidates 6 and 7)

### Pass one

````markdown
Title: lib: KPI flags dropped from describe.xml; enum per-value default always false

**What happens**
1. define_metric(is_kpi=True) never yields isKpi="true" in describe.xml.
2. Every <enum> value gets default="false", even the declared default.

**Where**
describe.py:430-449 (add_attribute has no isKpi)
describe.py:424 "default": str(value == identifier_json.get("default", False)).lower()

**Reproduce**
Define an enum parameter with default and a KPI metric; generate describe.xml.

**Effect on pack authors**
KPI metrics don't feed Self - Health Score. Enum defaults not preselected.

**Proposed fix**
Emit isKpi; compare value["key"] to the default.
````

### Skeptical reread, what changed

- **Wrong component in pass one.** The title said "lib". The lib serializes
  both correctly into its JSON (`attribute.py:60` has `"is_kpi": self.is_kpi`,
  `parameter.py:168-181` has the enum default). The loss happens in the
  CLI's `vmware_aria_operations_integration_sdk/describe.py`. The title was
  fixed.
- Pass one said "Enum defaults not preselected". That is not verified: the
  `ResourceIdentifier default` attribute is correct, and I did not check
  which one the dialog reads. The draft now says so.
- Narrowed the enum bug to the schema_version 1 path. `_add_enum_values_v0`
  (line 407) compares strings and is fine. The lib emits `schema_version: 1`
  (`adapter_definition.py:80`), so v1 is what current packs hit.
- The KPI effect is quoted from the schema documentation (xsd:694-698), not
  asserted from memory.
- Noted that credential enum fields go through the same function
  (`describe.py:328`).

### Pass two (file this)

````markdown
Title: describe.xml: isKpi is never written, and enum values always get default="false"

Two small bugs in the CLI's `describe.py`. I found both reading the serializer while reviewing packs built with 1.3.1, then confirmed them with the snippet below.

`define_metric(..., is_kpi=True)` makes it into the definition JSON (`"is_kpi": True`), but `add_attribute` (describe.py:430-449) never writes an `isKpi` attribute, so the flag disappears. The schema has it at `describeSchema.xsd:694`, documented as feeding the Self - Health Score.

For enums, `_add_enum_values_v1` compares the whole enum value dict to the default string, so the result is always false (line 424):

```python
                "default": str(value == identifier_json.get("default", False)).lower(),
```

The lib emits `schema_version: 1`, so this is the path current packs take. The v0 function compares plain strings and is fine. The schema describes the per-value `default` as "If true the enumeration entry is selected by default" (xsd:612). Credential enum fields go through the same code (line 328).

Repro:

```python
from lxml import etree
from aria.ops.definition.adapter_definition import AdapterDefinition
from vmware_aria_operations_integration_sdk.describe import json_to_xml

d = AdapterDefinition("ReproAdapter", "Repro Adapter", "repro_instance", "Repro Instance")
d.define_enum_parameter("mode", ["fast", "slow"], label="Mode", default="slow")
d.define_object_type("host", "Host").define_metric("cpu", "CPU", is_kpi=True)

describe, _ = json_to_xml(d.to_json())
for el in describe.iter():
    if etree.QName(el).localname in ("ResourceIdentifier", "enum", "ResourceAttribute"):
        keep = ("key", "value", "default", "isKpi", "isImpact")
        print(etree.QName(el).localname, {k: v for k, v in el.attrib.items() if k in keep})
```

With CLI 1.3.1 and lib 1.1.0:

```
ResourceIdentifier {'default': 'slow', 'key': 'mode'}
enum {'value': 'fast', 'default': 'false'}
enum {'value': 'slow', 'default': 'false'}
ResourceAttribute {'key': 'cpu', 'isImpact': 'false'}
```

To be fair about the enum half: the `ResourceIdentifier` itself carries `default="slow"`, and I haven't checked which of the two the account dialog uses, so you may see no difference in the UI. The file still contradicts the definition.

Both fixes look like one line each: add `"isKpi": str(attribute_json.get("is_kpi", False)).lower()` to `add_attribute`, and compare `value["key"] == identifier_json.get("default")` in the v1 function.
````

---

## Issue 6: `get_objects_by_type` compares the wrong field (candidate 8)

### Pass one

````markdown
Title: lib: CollectResult.get_objects_by_type filters on adapter kind instead of object kind

**Where**
result.py:256   if obj.adapter_type() == object_type

**Reproduce**
Add a Host and a Datastore; get_objects_by_type("Host") returns [];
get_objects_by_type("MyAdapter") returns both.

**Proposed fix**
obj.object_type() == object_type
````

### Skeptical reread, what changed

- Confirmed the method is on `CollectResult` (class at `result.py:163`), so
  the title names the right class.
- Checked for callers: none in samples or tests, which explains why it went
  unnoticed. Added that, plus a pointer to the existing test file, so the ask
  includes a test.
- Pass one was already right; it only gained context.

### Pass two (file this)

````markdown
Title: CollectResult.get_objects_by_type compares object_type against the adapter kind

`get_objects_by_type` checks the adapter type where it should check the object type (`result.py:256`):

```python
            if obj.adapter_type() == object_type
```

So asking for an object type returns nothing, and asking for your adapter kind returns everything:

```python
from aria.ops.result import CollectResult

result = CollectResult()
result.object("MyAdapter", "Host", "esx01")
result.object("MyAdapter", "Datastore", "ds01")

print(result.get_objects_by_type("Host"))
print([o.object_type() for o in result.get_objects_by_type("MyAdapter")])
```

```
[]
['Host', 'Datastore']
```

The fix is `obj.object_type() == object_type`. Nothing in the samples or tests calls this method, which is probably why it hasn't come up. A case in `lib/python/tests/test_collect_result.py` would keep it fixed.
````

---

## Issue 7: `suite-api/` prefix sent as a relative URL (candidate 9)

### Pass one

````markdown
Title: lib: SuiteApiClient strips a suite-api/ prefix but never re-applies the host

**Where**
suite_api_client.py:371-372
        if url.startswith("suite-api/"):
            url = url[10:]
(kwargs["url"] is never updated in this branch)

**Reproduce**
client.get("/suite-api/api/versions/current") -> requests MissingSchema

**Proposed fix**
Change the following elif to if, so the stripped path falls through.
````

### Skeptical reread, what changed

- Checked that the proposed `elif` to `if` change is correct for every case:
  `suite-api/api/x` becomes `api/x` and takes the api branch, and
  `suite-api/foo` becomes `foo` and takes the else branch, which adds `api/`.
  Both are right.
- Added the workaround (`/api/...`) so a reader knows the severity is low.

### Pass two (file this)

````markdown
Title: SuiteApiClient sends paths that start with suite-api/ as relative URLs

`_to_vrops_request` strips a leading `suite-api/` into the local `url` but never writes the result back to `kwargs["url"]` (lines 371-372), so the request goes out with the original relative path:

```python
from aria.ops.suite_api_client import SuiteApiClient, SuiteApiConnectionParameters
c = SuiteApiClient(SuiteApiConnectionParameters("ops.example.com", "u", "p"))
for path in ["/api/versions/current", "suite-api/api/versions/current", "/suite-api/api/versions/current"]:
    print(f"{path:35} -> {c._to_vrops_request(path)['url']}")
c.get("/suite-api/api/versions/current")
```

```
/api/versions/current               -> https://ops.example.com/suite-api/api/versions/current
suite-api/api/versions/current      -> suite-api/api/versions/current
/suite-api/api/versions/current     -> /suite-api/api/versions/current
requests.exceptions.MissingSchema: Invalid URL '/suite-api/api/versions/current': No scheme supplied. ...
```

Easy to avoid once you know (use `/api/...`), but people copy full paths from the Suite API docs. Turning the `elif url.startswith("api") ...` on line 373 into a plain `if` lets the stripped path fall through to the normal handling.
````

---

## Issue 8: registry host without a dot parsed as Docker Hub (candidate 12)

### Pass one

````markdown
Title: CLI: mp-build mis-parses a registry host without a dot (localhost:5055 -> registry.hub.docker.com, repository /localhost)

**Where**
validation/input_validators.py:282-286
            domain, path = container_registry.split("/", 1)
            if "." not in domain:
                path = f"{domain}/{path}"
                domain = cls.default_domain
mp_build.py:502-503 writes REGISTRY= / REPOSITORY=/

**Reproduce**
mp-build -r localhost:5055/myadapter; inspect adapter.zip conf.

**Proposed fix**
Treat the first component as a host if it contains "." or ":" or is "localhost".
````

### Skeptical reread, what changed

- **The repro was not one I ran.** I did not run a full `mp-build` against a
  local registry. The repro is now the parser call I did run, plus the
  conf-writing lines, and the draft says the conf values are derived.
- Ran the parser: the path comes out as `localhost` and the "tag" as
  `5055/myadapter`. The leading slash in `REPOSITORY=/localhost` comes from
  `mp_build.py:503` (`REPOSITORY=/{conf_repo_field}`). The candidate's
  "/localhost" is right for the conf.
- Added the interactive symptom, which I ran: the prompt validator rejects
  the same string with a misleading "should not include a tag" message.
- Added the cross-reference to #270 (same function, earlier fix for a
  different input), which a maintainer would want.

### Pass two (file this)

````markdown
Title: mp-build treats a registry host without a dot (localhost:5055, registry:5000) as a Docker Hub path

This came up while I was planning a CI build against a throwaway registry on localhost. `ContainerRegistryValidator.get_container_registry_components` only treats the first path component as a registry host when it contains a dot (`validation/input_validators.py:284`):

```python
            if "." not in domain:
```

Docker's own reference rules also accept a component with a port, or the literal `localhost`. Calling the parser directly:

```python
from vmware_aria_operations_integration_sdk.validation.input_validators import (
    ContainerRegistryValidator,
)
for r in ["localhost:5055/myadapter", "registry:5000/myadapter",
          "harbor.lab.local:5000/proj/myadapter"]:
    print(f"{r:38} {ContainerRegistryValidator.get_container_registry_components(r)}")
```

```
localhost:5055/myadapter               {'domain': 'registry.hub.docker.com', 'port': '', 'path': 'localhost', 'tag': '5055/myadapter'}
registry:5000/myadapter                {'domain': 'registry.hub.docker.com', 'port': '', 'path': 'registry', 'tag': '5000/myadapter'}
harbor.lab.local:5000/proj/myadapter   {'domain': 'harbor.lab.local', 'port': '5000', 'path': 'proj/myadapter', 'tag': ''}
```

`mp-build` builds the pak conf from these components (`mp_build.py:236-241, 415-420, 502-503`), so by that code a pak for `localhost:5055/myadapter` would say `REGISTRY=registry.hub.docker.com` and `REPOSITORY=/localhost`. I got there from the parser and the conf-writing code rather than from inspecting a built pak. At the interactive prompt, the same string gets a misleading rejection:

```
Path should not include a tag, but ':5055/myadapter' was provided. If ':5055/myadapter' is not a tag, check that the domain is valid.
```

#270 fixed a different input in this same function. Matching Docker's rule would cover both: treat the first component as the registry host when it contains `.` or `:`, or equals `localhost`.
````

---

## Issue 9: registry password on the `docker login` command line (candidate 13)

### Pass one

````markdown
Title: CLI: mp-build --registry-password puts the password on the command line; mp-test stores passwords in plaintext

**What happens**
docker_wrapper.login appends --password <value> to the docker login argv.
connections.json holds suite_api_password and credential passwords in plaintext.

**Where**
docker_wrapper.py:64-66
project.py:118-127 (Connection.json includes suite_api_password)

**Proposed fix**
--password-stdin; encrypt or keyring connections.json.
````

### Skeptical reread, what changed

- **Dropped the plaintext complaint.** It is documented with a warning
  (`docs/references/project_connections_config.md:4-9`), and the file is
  gitignored automatically. A maintainer would close that as working as
  designed. Kept only the cheap `0600` ask, as a side paragraph.
- Found a stronger point. The interactive Docker Hub prompt
  (`mp_build.py:143-144`) collects the password with `is_password=True`
  and then puts it on argv anyway, so the exposure is not limited to people
  who use the flag.
- `--registry-password` also sits in `mp-build`'s own argv for the whole
  build, which is longer than the `docker login` call. Added that, with the
  env var suggestion as a second, optional ask.
- Verified docker's own warning text by running `docker login --password`
  against a closed local port. Nothing was stored.

### Pass two (file this)

````markdown
Title: mp-build passes the registry password to docker login on the command line

`docker_wrapper.login` builds the `docker login` argv with the password in it (`docker_wrapper.py:64-66`):

```python
        command.append("--password")
        command.append(kwargs["registry_password"])
```

That path is used for `--registry-password`, and also for the interactive Docker Hub prompt in `mp_build.py:143-144`, which reads the password with `is_password=True` and then puts it on argv anyway. While `docker login` runs, any local user can see the password with `ps` or `/proc/<pid>/cmdline`. Docker itself complains:

```
WARNING! Using --password via the CLI is insecure. Use --password-stdin.
```

Switching to `--password-stdin` and passing the password with `subprocess.run(command, input=password, text=True)` fixes it, and I can't think of a downside.

A related, smaller point: `mp-build --registry-password X` keeps the password in `mp-build`'s own argv for the whole build, and in shell history. An environment variable alternative would help CI users. Separately, `connections.json` is created with plain `open(..., "w")` (`config.py:74, 82`), so it gets the umask (usually 0644). The plaintext storage is documented, but creating the file as 0600 would be a cheap improvement.
````

---

## Item 10: comment on open issue #161 (candidate 14)

#161 "Add HTTPS certificate helper functions in Python library" (open since
2023-04-28, no comments) asks for exactly this. A comment adds evidence
without opening a duplicate.

### Pass one

````markdown
No sample applies the accepted certificate from AdapterInstance.get_certificates().
- samples/vcenter-extension-mp/app/adapter.py:116 uses disableSslCertValidation=True
- samples/rest-template-mp/app/adapter.py:210-216 links an external blog and suggests verify=False
- docs/references/python_project/index.md:115-122 says certificates "should then be validated" but shows no code
Proposed: a documented example for pyVmomi (serverPemCert) and requests (fingerprint match).
````

### Skeptical reread, what changed

- Checked the external link: it covers client-certificate authentication and
  `verify=<truststore file>`, not pinning one accepted server certificate.
  The comment says so plainly, without dismissing the page.
- The pyVmomi `serverPemCert` behavior is confirmed from pyVmomi source
  (`SoapAdapter.py:1092-1142`, pyVmomi 9.1.1.0), not from a live run. The
  requests fingerprint pattern was derived from urllib3 source and has not
  been run live. The comment offers them as approaches, not proven recipes.
- Grepped samples, templates and docs for `get_certificates`: zero hits.

### Pass two (post as a comment on #161)

````markdown
Adding a data point, since this is still open. None of the samples or docs read `AdapterInstance.get_certificates()`; grepping the repo for it outside the lib finds nothing. The vCenter sample connects with `disableSslCertValidation=True` (`samples/vcenter-extension-mp/app/adapter.py:116`). The REST template's comment (`samples/rest-template-mp/app/adapter.py:210-216`) points to an external page about client-certificate auth and `verify=<truststore>`, and offers `verify=False` as the alternative. The Python project docs say certificates "should then be validated against the certificate(s) in the AdapterInstance" but stop there.

In a third-party pack I reviewed recently, the certificate the user accepts in the dialog is never read, which is what you'd expect when there's nothing to copy from.

Two approaches I'd expect an example to show. For pyVmomi, passing the accepted PEM as `serverPemCert` to `SmartConnect` does what the platform intends: from pyVmomi's `SoapAdapter.py`, it tries normal verification first and, only if that fails, requires the peer certificate to match the pinned PEM exactly. For `requests`, there's no "trust this leaf" switch; a mounted `HTTPAdapter` that sets urllib3's `assert_fingerprint` to the accepted certificate's SHA-256 is the closest match. I've worked both out from source, not against a live platform, so treat them as starting points. I'm happy to turn either into a sample PR if that's useful.
````
