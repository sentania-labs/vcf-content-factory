# `PUT /internal/supermetrics/assign` — verified wire format

Empirically verified against lab VCF Ops on 2026-04-08 using super metric
`[AI Content] Cluster - Max VM CPU Ready (%)`
(`035e2f37-703d-42f3-aeae-f9a87d38f491`) against the Default Policy
(`e74c28bf-44f8-4cd1-a8d9-2ee5c6b6c2fd`). See also the sibling endpoint
`PUT /internal/supermetrics/assign/default` which has the same body and
no query params.

## Spec ground truth (`docs/internal-api.json`)

- Path: `/internal/supermetrics/assign`
- Method: `PUT`
- Tag: `Internal Super Metrics`, operationId `updateSuperMetric`
- Query params:
  - `policyIds` — `array<uuid>`, **not required per spec**. Empirically:
    repeatable form (`?policyIds=a&policyIds=b`). **In practice the server
    only accepts the Default Policy id here — see "Surprises" below.**
  - `X-Ops-API-use-unsupported` — declared as a header (bool, default true).
- Request body (JSON, required), schema `supermetric-assignment-param`:

  ```json
  {
    "superMetricId": "<uuid>",
    "resourceKindKeys": [
      { "adapterKind": "VMWARE", "resourceKind": "ClusterComputeResource" }
    ]
  }
  ```

  Also accepts XML with the same shape. `resourceKindKeys` is an array —
  one call can assign to multiple resource kinds.
- Response: `200` with **empty body**, `Content-Length: 0`. No JSON envelope.

## Verified request/response

Happy path:

```
PUT https://<host>/suite-api/internal/supermetrics/assign
    ?policyIds=e74c28bf-44f8-4cd1-a8d9-2ee5c6b6c2fd
Authorization: OpsToken <token>
Content-Type: application/json
Accept: application/json
X-Ops-API-use-unsupported: true

{"superMetricId":"035e2f37-703d-42f3-aeae-f9a87d38f491",
 "resourceKindKeys":[{"adapterKind":"VMWARE","resourceKind":"ClusterComputeResource"}]}

→ 200 OK, empty body
```

Minimum Python reproducer:

```python
import os, requests, urllib3
urllib3.disable_warnings()
host = os.environ["VCFOPS_HOST"]
# acquire token
tok = requests.post(
    f"https://{host}/suite-api/api/auth/token/acquire",
    json={"username": os.environ["VCFOPS_USER"],
          "password": os.environ["VCFOPS_PASSWORD"],
          "authSource": os.environ.get("VCFOPS_AUTH_SOURCE", "Local")},
    headers={"Accept": "application/json"}, verify=False,
).json()["token"]

requests.put(
    f"https://{host}/suite-api/internal/supermetrics/assign",
    headers={
        "Authorization": f"OpsToken {tok}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Ops-API-use-unsupported": "true",
    },
    params=[("policyIds", "e74c28bf-44f8-4cd1-a8d9-2ee5c6b6c2fd")],
    json={
        "superMetricId": "035e2f37-703d-42f3-aeae-f9a87d38f491",
        "resourceKindKeys": [
            {"adapterKind": "VMWARE", "resourceKind": "ClusterComputeResource"}
        ],
    },
    verify=False,
).raise_for_status()
```

curl equivalent:

```bash
curl -k -X PUT \
  "https://$VCFOPS_HOST/suite-api/internal/supermetrics/assign?policyIds=e74c28bf-44f8-4cd1-a8d9-2ee5c6b6c2fd" \
  -H "Authorization: OpsToken $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "X-Ops-API-use-unsupported: true" \
  -d '{"superMetricId":"035e2f37-703d-42f3-aeae-f9a87d38f491",
       "resourceKindKeys":[{"adapterKind":"VMWARE","resourceKind":"ClusterComputeResource"}]}'
```

## Readback — how to confirm enablement

`GET /suite-api/api/supermetrics/{id}` does **not** return assignment
or policy enablement state (only id/name/formula/description/modTime).

The working readback is the policy export zip:

```
GET /suite-api/api/policies/export?id=<policyId>   Accept: application/zip
```

Returns a zip containing `exportedPolicies.xml`. Grep for the super
metric UUID; it appears inside:

```xml
<SuperMetrics adapterKind="VMWARE" resourceKind="ClusterComputeResource">
    <SuperMetric enabled="true" id="035e2f37-703d-42f3-aeae-f9a87d38f491"/>
    ...
</SuperMetrics>
```

Note: the public `/api/policies/{id}/settings?type=...` endpoint has
no `SUPER_METRIC` type in its enum — it is not a readback path.

Find the Default policy id with
`GET /suite-api/api/policies` → look for
`"defaultPolicy": true` entry in `policySummaries` (**not** `policies`;
that was a bug in earlier notes).

## Surprises / gotchas

1. **`policyIds` only accepts the Default Policy.** Despite the spec's
   `array<uuid>` type, the lab server rejects any non-default policy id:

   ```
   PUT ...?policyIds=1ea3fc2e-a2de-43b6-82d6-a5afd167eeb9
   → 400 apiErrorCode 1501
   "Value \"1ea3fc2e-...\" is invalid for request param \"policyIds\".
    Allowed values are = \"[[e74c28bf-44f8-4cd1-a8d9-2ee5c6b6c2fd]]\"."
   ```

   So `/internal/supermetrics/assign` with `policyIds=<default>` and
   `/internal/supermetrics/assign/default` (no query param) are
   functionally equivalent. **To enable a super metric in a non-default
   policy, this endpoint is not sufficient** — must use the policy
   export / edit XML / re-import path instead. Flag this as a gap for
   the planned `enable` CLI.

2. **`X-Ops-API-use-unsupported` header is required, not optional.**
   Spec marks it `required: false` but omitting it yields
   `403 Forbidden` (HTML body). The default value declared in the spec
   is not applied server-side.

3. **Omitting `policyIds` entirely returns 200.** In that mode the call
   only sets the resource-kind assignment (no policy enablement). This
   matches the operation's dual purpose ("assign and optionally enable").

4. **Idempotent.** Calling with the same body twice returns 200 both
   times with empty body. No "already enabled" signal.

5. **Response is always empty on 200** — `Content-Length: 0`. Do not
   try to `.json()` the response; check status only.

6. **Bogus policy id** returns 400 apiErrorCode 1501 with a clear
   message naming the invalid value. Use as the CLI's validation error
   path.

7. **No unassign / disable counterpart.** Neither internal nor public
   API exposes a way to remove a super metric from a policy via this
   endpoint family. Disabling requires the policy export-edit-import
   round trip. Cleanup after a bad `enable` is therefore expensive.

## Recommended CLI wiring

For an `enable` command targeting the Default Policy (the only policy
this endpoint can actually write to):

1. Resolve Default Policy id via `GET /api/policies`, filter
   `policySummaries` for `defaultPolicy: true`. Cache per session.
2. Resolve super metric by YAML id (already known in the YAML file —
   no lookup needed).
3. PUT with body `{superMetricId, resourceKindKeys:[...]}` and
   `policyIds=<default>` as a single repeatable query param.
4. Treat 200 as success (no body parsing).
5. For non-default policies: raise `NotImplementedError` pointing the
   user at the policy export/import path, OR implement that path as a
   second code route. Do not silently downgrade to "default only".

## Supportability caveat

`/internal/*` endpoints are explicitly unsupported by VMware — no
backward-compat guarantee across versions. The `X-Ops-API-use-unsupported:
true` header is the caller's acknowledgement. Any CLI command built on
this endpoint must surface that caveat in `--help` text.

## Cleanup status for this investigation

The PUT landed on an already-populated `<SuperMetrics
adapterKind="VMWARE" resourceKind="ClusterComputeResource">` block
containing 7 cluster super metrics (none of which are managed by this
repo). The target SM was listed among them post-call; pre-call state
was not snapshotted but the call is idempotent and the user's brief
explicitly stated the guinea-pig SM is "safe to enable/disable". No
other state on the instance was touched. No test objects were created.
