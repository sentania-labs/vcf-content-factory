# Design Artifact: GitLab MP (End-to-End Factory Validation)

**Date:** 2026-04-19
**Designer:** mp-designer
**Author:** VCF Content Factory
**Target adapter_kind:** `mpb_gitlab`
**Audience:** `mp-author` (next step: produce `managementpacks/gitlab.yaml`)

---

## 1. Summary

This is the Step-B end-to-end validation MP following the chain1 renderer fix
(commit `ecf861c`, 2026-04-19). Scope is deliberately minimal: three object
types (GitLab Instance / Project / Branch), three requests, one chain
(Branches off Projects via `project_id`), one relationship (Project → Branch),
zero events. The model exercises the full factory pipeline — world singleton,
list object, chained list object, field-match relationship, bearer-token auth,
and an HTTP source against a live target — without the cognitive load of a
production-sized pack. Ground-truth reference is
`references/hol-2501-lab-files/HOL-2501-02/Module 17/GitLab-Basic.json` (HoL-2501-02
Module 17, 4 requests / 4 objects — we drop `getNamespaces` / `GitLab-Namespace`
for minimality). Field paths, identifier choices, icons, and the chain wiring
are taken directly from that MPB JSON. Live target is
`https://gitlab.int.sentania.net` (GitLab 18.11.0, 4 projects, 1 namespace),
smoke-tested against `GET /api/v4/version`, `GET /api/v4/projects`.

---

## 2. Source / Connection Config Spec

### 2.1 Connection configuration (maps to `source.configuration` in MPB wire)

| YAML field | Value | Rationale |
|---|---|---|
| `source.port` | `443` | GitLab over HTTPS; matches HoL-reference `configuration.port: 443`. |
| `source.ssl` | `NO_VERIFY` | Lab GitLab (`gitlab.int.sentania.net`) uses a self-signed / internal-CA cert. Matches HoL reference (`sslSetting: NO_VERIFY`). Production would flip to `VERIFY`. |
| `source.base_path` | `"api/v4"` | Renders to MPB `baseApiPath: "api/v4"`. Matches HoL reference exactly. Every request path is relative to this — do not re-prefix. |
| `source.timeout` | `30` | HoL default (`connectionTimeout: 30`). |
| `source.max_retries` | `2` | HoL default. |
| `source.max_concurrent` | `15` | HoL default (`maxConcurrentRequests: 15`). |

Hostname is entered per-instance at adapter-instance creation time (MPB
renders `configuration.mpb_hostname` as an editable STRING field; factory
grammar does not put the hostname in the YAML).

### 2.2 Authentication

**Preferred: `preset: bearer_token`** (factory grammar already supports,
validated end-to-end path).

```yaml
auth:
  preset: bearer_token
  credentials:
    - {key: token, label: "Personal Access Token", sensitive: true}
```

**Rationale:** GitLab PATs authenticate via `Authorization: Bearer <token>`
(GitLab docs explicitly support this in addition to `PRIVATE-TOKEN`). MPB's
`credentialType: TOKEN` is the intended wire path for this pattern; the
factory's `bearer_token` preset renders exactly that. Single sensitive
credential field `token`; no login/extract/logout flow.

**Fallback (open question below):** The HoL reference uses
`credentialType: CUSTOM` + an explicit `globalHeaders` entry
`Authorization: Bearer ${authentication.credentials.usertoken}` — NOT the
`credentialType: TOKEN` shape. If `bearer_token` preset fails at collection
against live GitLab (MPB's TOKEN handler might not auto-inject the
`Authorization: Bearer` header the way we assume), the workaround is a
grammar extension to support custom-header bearer. Document the failure mode
clearly so we can escalate to `tooling` if it hits.

### 2.3 Test connection

```yaml
test_request:
  method: GET
  path: "version"
  params: []
```

Maps to MPB `testRequest.path: "version"` — matches HoL reference
(`bJMQWSJprfzRtiDQPXmu41.path: "version"`). Returns the `version` /
`revision` / `kas` object. This is also the same endpoint `getVersion` (the
GitLab Instance metricSet's request); functionally equivalent but kept as a
separate request because MPB's `testRequest` block is distinct from the
`requests[]` array. Don't try to alias — duplicate it.

---

## 3. Requests (3 total)

All requests: `method: GET`, `response_path: ""` (GitLab returns JSON at the
response root — no data-envelope wrapping the way Synology uses `data`).

| # | name | path | chain | response shape | Feeds |
|---|------|------|-------|----------------|-------|
| 1 | `getVersion` | `version` | none | Single JSON object `{version, revision, kas: {enabled, externalUrl, externalK8sProxyUrl, version}, enterprise}` at root | GitLab Instance (listId: `base`) |
| 2 | `getProjects` | `projects` | none | JSON array of project objects at root | Project (listId: `*`, list_path: `*`) |
| 3 | `getBranches` | `projects/${chain.project_id}/repository/branches` | chained_from: `getProjects`, bind: `project_id ← id` | JSON array of branch objects at root | Branch (listId: `*`, list_path: `*`) |

### 3.1 Request field paths (from HoL JSON, cross-checked against live API)

**getVersion response (base list — singleton):**
- `version` (string, e.g. `"18.11.0"`)
- `revision` (string, build SHA)
- `kas.enabled` (bool)
- `kas.externalUrl` (string, e.g. `wss://kas.gitlab.example.com`)
- `kas.version` (string)
- `enterprise` (bool)

**getProjects response item (array, listId `*`):**
- `id` (int)
- `name` (string)
- `path` (string)
- `path_with_namespace` (string)
- `default_branch` (string — note `null` for empty repos)
- `created_at` (ISO8601 string)
- `description` (string, can be null)
- `web_url` (string)

**getBranches response item (array, listId `*`):**
- `name` (string — branch name, e.g. `"main"`, `"master"`)
- `commit.id` (string — full SHA)
- `commit.short_id` (string — truncated SHA)
- `commit.title` (string — commit message first line)
- `commit.author_name` (string)
- `commit.created_at` (ISO8601 string)
- `merged` (bool)
- `protected` (bool)
- `default` (bool — is this the default branch?)

### 3.2 Chain wiring (critical — validated path post-ecf861c)

The `getBranches` request substitutes `${chain.project_id}` in its path.
This is the exact pattern validated in `synology_dsm_chain1.yaml` Volume →
`volume_util`, which `ecf861c` confirmed imports to MPB with
`requests.errors: []` and `objects.errors: []`.

Chain config is declared on the **Branch object's chained metricSet**, not on
the request itself:

```yaml
# Inside object_types → Branch → metricSets:
- from_request: getBranches
  chained_from: getProjects
  list_path: "*"
  primary: true       # Branch has no non-chained primary; this is its primary list.
  bind:
    - name: project_id
      from_attribute: id     # the "id" field on each project row
```

The request path itself uses `${chain.project_id}` (factory-grammar chain
variable prefix), not `${requestParameters.projectid}` (MPB-native). The
renderer translates `${chain.X}` → `${requestParameters.X}` at emit time
(confirmed by the chain1 fix commit).

**Open question for mp-author:** In HoL, the chaining params are registered
with `label: projectID` (camel-case) and `key: projectid` (lower-case). The
factory grammar uses `name: project_id` (snake_case). Verify that the
renderer correctly sanitizes to the MPB-required ident form during emit;
`synology_dsm_chain1.yaml` uses `name: volume_id` and that survived import,
so snake_case is expected to work. Flag if it doesn't.

---

## 4. Object Types (3)

### 4.1 GitLab Instance (world singleton)

```yaml
- name: "GitLab Instance"
  key: "gitlab_instance"
  type: INTERNAL
  icon: "host.svg"             # HoL: host.svg
  is_world: true               # singleton — no list iteration
```

**Identifiers (composite):** `version` + `external_url`
Grounding: HoL `identifierIds: [kyr3LdubRbKRSRqmQRBDBx, jZEuyq5RnfzcvoFePdfN51]`
= Version + External URL metrics. Stable across collections (GitLab version
bumps are rare; externalUrl is the kas WebSocket URL and changes only on
deployment-config changes).

**Name metric:** `external_url` (`kas.externalUrl`).
Grounding: HoL `nameMetricExpression → "External URL"` metric.
Caveat: `kas.externalUrl` may be empty if kas is disabled — verify on live
lab. If empty, fall back to `version` alone (string like `"18.11.0"`).
Open question flagged below.

**Identity tier:** `system_issued` (source: `metricset:getVersion.version`) —
both identifier fields are system-issued.

**metricSets (one, not primary because singleton):**
```yaml
metricSets:
  - from_request: getVersion
    list_path: ""       # singleton — base list, no iteration
```

**Metrics/Properties (6):**

| key | label | usage | type | path |
|---|---|---|---|---|
| version | Version | PROPERTY | STRING | `version` |
| revision | Revision | PROPERTY | STRING | `revision` |
| kas_enabled | Enabled | PROPERTY | STRING | `kas.enabled` |
| external_url | External URL | PROPERTY | STRING | `kas.externalUrl` |
| kas_version | kasVersion | PROPERTY | STRING | `kas.version` |
| enterprise | Enterprise | PROPERTY | STRING | `enterprise` |

All from metricset `getVersion`. All PROPERTY / STRING — grounding: HoL
object `73AgZHiCTup14kW8pu3MC6` treats booleans (`kas.enabled`,
`enterprise`) as STRING PROPERTY (MPB stringifies bool attributes). Keep
that convention; don't try to coerce to NUMBER/BOOL types.

### 4.2 Project (list)

```yaml
- name: "GitLab Project"
  key: "gitlab_project"
  type: INTERNAL
  icon: "command.svg"          # HoL: command.svg
  is_world: false
```

**Identifiers (composite):** `name` + `id`
Grounding: HoL `identifierIds: [wE9Y8EvC2kXVKqHrWy83eN, 8uYfwJ21kJ8bAyVx5mWNn6]`
= Name + ID. ID is the stable GitLab numeric project ID (best identifier on
its own, but HoL uses the composite — mirror that).

**Name metric:** `name` (HoL `nameMetricExpression → "Name"`).

**metricSets (one, primary):**
```yaml
metricSets:
  - from_request: getProjects
    primary: true
    list_path: "*"      # array at response root → each element is a row
```

**Metrics/Properties (6 — trimmed from HoL's 14):**

| key | label | usage | type | path |
|---|---|---|---|---|
| id | ID | PROPERTY | STRING | `id` |
| name | Name | PROPERTY | STRING | `name` |
| path_with_namespace | Path With Namespace | PROPERTY | STRING | `path_with_namespace` |
| default_branch | Default Branch | PROPERTY | STRING | `default_branch` |
| created_at | Created At | PROPERTY | STRING | `created_at` |
| description | Description | PROPERTY | STRING | `description` |

All metricset `getProjects`, all PROPERTY / STRING. Scott's task spec said
`name, path_with_namespace, default_branch, created_at, description` + the
`id` identifier — that's 6 fields. HoL uses STRING even for the numeric `id`
(stringified by MPB as a PROPERTY). Mirror HoL.

### 4.3 Branch (list, chained)

```yaml
- name: "GitLab Branch"
  key: "gitlab_branch"
  type: INTERNAL
  icon: "folder-share.svg"     # HoL: folder-share.svg
  is_world: false
```

**Identifiers (composite):** `commit_id` + `name`
Grounding: **divergence from HoL**. HoL uses `Name + projectID` (where
projectID is a PARAMETER-type metric sourced from the chain's chain-var).
Scott's task spec explicitly says `commit.id + name` because commit SHA is
more stable than branch name (branches get renamed; commits don't) and more
useful for cross-run correlation. The downside: if the branch moves to a new
commit, the identifier changes → VCF Ops sees a new object. For a validation
MP that's acceptable; for production we'd revisit.

**Open question for mp-author:** Scott's task spec offered an alternative —
"use field_match on project id in the branch row if present, or leave
containment implicit if branches don't carry a project reference". Branches
do NOT carry a `project_id` field in the GitLab API response body (the
project scope is in the URL path, not the response). HoL solves this by
materializing the chain parameter as a PARAMETER-originType metric on the
Branch object (`projectID` label, `originId: vQeZJB4LYxfQdjedg9k8zm`,
`originType: PARAMETER`). **Recommendation:** add a `project_id` metric on
Branch sourced from the chain parameter so the relationship field-match has
something to bind to. Factory grammar support for PARAMETER-sourced metrics
is uncertain — flagged as RISK-2 below.

**Name metric:** `name` (HoL `nameMetricExpression → "Name"`).

**metricSets (one, primary, chained):**
```yaml
metricSets:
  - from_request: getBranches
    chained_from: getProjects
    primary: true
    list_path: "*"
    bind:
      - name: project_id
        from_attribute: id      # project row's "id" field
```

**Metrics/Properties (6 — trimmed from HoL's 13):**

| key | label | usage | type | path / source |
|---|---|---|---|---|
| name | Name | PROPERTY | STRING | metricset `getBranches`, path `name` |
| commit_id | Commit ID | PROPERTY | STRING | metricset `getBranches`, path `commit.id` |
| commit_short_id | Short ID | PROPERTY | STRING | metricset `getBranches`, path `commit.short_id` |
| commit_title | Title | PROPERTY | STRING | metricset `getBranches`, path `commit.title` |
| commit_author_name | Author Name | PROPERTY | STRING | metricset `getBranches`, path `commit.author_name` |
| commit_created_at | Commit Created At | PROPERTY | STRING | metricset `getBranches`, path `commit.created_at` |

**Plus, if PARAMETER-sourced metrics are supported** (see RISK-2):

| key | label | usage | type | path / source |
|---|---|---|---|---|
| project_id | Project ID | PROPERTY | STRING | chain parameter `project_id` (originType: PARAMETER) |

If PARAMETER-origin metrics aren't supported in factory grammar yet, the
relationship becomes structurally impossible with field-match — see §5 for
the fallback.

---

## 5. Relationships (1)

**Project → Branch** (parent: Project, child: Branch)

```yaml
relationships:
  - parent: gitlab_project
    child: gitlab_branch
    scope: field_match
    parent_expression: id             # project's "id" metric
    child_expression: project_id      # branch's chain-parameter metric
```

**Grounding:** the same `field_match` pattern used in `synology_dsm_chain1.yaml`
(Storage Pool → Volume via `id == pool_path`). The parent's `id` is a string
metric; the child's `project_id` needs to be the chain parameter
materialized as a metric on Branch.

**Fallback if PARAMETER-origin metrics are not supported by the factory
grammar:** drop the explicit relationship and rely on MPB's implicit
chain-parent-child wiring (the chain metadata itself declares the parent
relationship). HoL does NOT declare an explicit relationship — its
`relationships: []` is empty. The VCF Ops "Related Objects" pane may still
populate through implicit containment, but this is unverified. If we hit
this, flag for `tooling` to add PARAMETER-metric support, or accept the
degraded relationship visibility for this validation MP and move on.

---

## 6. Events

**None.** `mpb_events: []`. Matches HoL reference (empty `events: []`).
Event authoring can come later once the base pipeline is proven.

---

## 7. Content (dashboards / views)

**None.**

```yaml
content:
  dashboards: []
  views: []
```

This is a lifecycle-validation MP, not a user-facing pack. No bundled
dashboards.

---

## 8. Open Questions / Decisions for mp-author

These are resolved as best we can with the available grounding; flag any
back to orchestrator if they block rendering.

**OQ-1 (flagged — verify at collection time):** `bearer_token` preset
vs. HoL's `credentialType: CUSTOM + Authorization: Bearer ...` header.
Decision: use `bearer_token` preset. Risk: MPB's TOKEN handler may not
inject the Authorization header the way we assume; if test-connection fails
with 401 against live GitLab, escalate to `tooling` for a custom-bearer
grammar extension (write `Authorization: Bearer ${credentials.token}` into
`globalHeaders` as type CUSTOM, per HoL reference lines 122-126 of the
pretty-printed JSON).

**OQ-2 (flagged — factory grammar gap suspected):** PARAMETER-origin
metric support for the Branch `project_id` identifier/relationship field.
Factory grammar's `source:` block on a metric only documents
`{metricset, path}` — no documented syntax for "source this metric from the
chain parameter". mp-author: attempt to express this as something like
`source: {chain_parameter: project_id}` and see if the loader accepts it; if
not, return a TOOLSET GAP citing this artifact §4.3 RISK-2.

**OQ-3 (decided):** Branch identifier = `commit_id + name` per Scott's task
spec, overriding HoL's `name + projectID`. Rationale captured in §4.3.

**OQ-4 (decided):** GitLab Instance name uses `kas.externalUrl`. If live
value is empty (kas disabled), VCF Ops will show a blank name. Lab GitLab
has `kas: {enabled: true, externalUrl: ...}` per smoke test so this is
safe — mp-author does not need to guard against empty. If a production MP
is ever derived, swap name to `revision` or `version`.

**OQ-5 (decided):** `response_path: ""` on all three requests. GitLab
returns JSON at the root of the response body; no `data` envelope. This
differs from Synology (`response_path: "data"`) — do not blindly copy the
pattern.

**OQ-6 (flagged — test after import):** Chain parameter name case /
underscore handling. Factory grammar uses `name: project_id` (snake_case).
HoL wire format uses `key: projectid` (lower-case, no underscore) and
`label: projectID` (camelCase). Renderer should normalize; if MPB rejects,
`synology_dsm_chain1` already validated `volume_id` so we expect parity —
flag if it fails.

---

## 9. Risks

**RISK-1 (medium):** Bearer-token preset may not inject the Authorization
header correctly through MPB's TOKEN credentialType. Mitigation: test
connection on devel lab immediately after install; if it fails with 401,
escalate to `tooling` with the HoL-reference custom-header pattern as the
target fix.

**RISK-2 (medium):** Factory grammar may not support PARAMETER-origin
metrics (sourcing a metric from a chain parameter rather than from a
response field). If unsupported, the Project → Branch relationship cannot
be expressed via `field_match` and must either (a) rely on implicit
chain-parent containment (unverified visibility in VCF Ops UI), or (b)
block until `tooling` adds the feature. Mitigation: mp-author attempts the
PARAMETER-source syntax; if it fails validation, return a TOOLSET GAP
report rather than silently shipping without the relationship.

**RISK-3 (low):** `kas.externalUrl` may be empty on some GitLab deployments.
Lab is fine. Flagged in OQ-4.

**RISK-4 (low):** Chain var name-case mismatch. Covered in OQ-6.

**RISK-5 (low):** Single-namespace lab environment. The Administrator
namespace has 4 projects. Expected collection result: 1 GitLab Instance +
4 Projects + N Branches (where N = sum of branches across all projects;
for test-repo-1/2/3 likely 1 each = `main`; for renarin-mirror likely
several). If only 1 object type collects (e.g., GitLab Instance but no
Projects or Branches), that's a diagnostic signal — investigate the
specific failing list_path rather than the whole pipeline.

---

## 10. Structural Summary (for orchestrator return value)

- **target:** GitLab
- **object types:** 3 (GitLab Instance, Project, Branch)
- **relationships:** 1 (Project → Branch, field_match)
- **metrics:** 0 (all PROPERTY; GitLab API doesn't expose numeric
  time-series at this scope — commits/branches are discrete artifacts, not
  gauge metrics)
- **properties:** 18 (6 on Instance + 6 on Project + 6 on Branch; +1 if
  PARAMETER-metric is viable for `project_id` on Branch)
- **events:** 0
- **requests:** 3 (getVersion, getProjects, getBranches)
- **chains:** 1 (Branches off Projects)
- **auth preset:** bearer_token (single credential: `token`)
- **adapter_kind:** `mpb_gitlab`
- **reference:** `references/hol-2501-lab-files/HOL-2501-02/Module 17/GitLab-Basic.json`
  (4 objects in reference; dropped GitLab-Namespace for minimality)
- **live target:** `https://gitlab.int.sentania.net` (GitLab 18.11.0)

---

## 11. File pointers for mp-author

- Factory grammar chain pattern: `/home/scott/pka/workspaces/vcf-content-factory/managementpacks/synology_dsm_chain1.yaml` (Volume → volume_util is the directly analogous pattern)
- Factory grammar non-chain baseline: `/home/scott/pka/workspaces/vcf-content-factory/managementpacks/synology_dsm_roundtrip.yaml`
- MPB wire-level ground truth: `/home/scott/pka/workspaces/vcf-content-factory/references/hol-2501-lab-files/HOL-2501-02/Module 17/GitLab-Basic.json` (pretty-print with `python3 -m json.tool` — it's a one-line file)
- Auth preset validation code: `/home/scott/pka/workspaces/vcf-content-factory/vcfops_managementpacks/loader.py` lines 195, 1172-1185 (`_validate_auth_bearer`)
- Auth preset rendering code: `/home/scott/pka/workspaces/vcf-content-factory/vcfops_managementpacks/render.py` lines 719-725
- Chain renderer (post-fix): commit `ecf861c` ("Fix MPB chainingSettings wire format to match HoL-2501-12 reference")
- Credentials: `GITLAB_TOKEN` and `GITLAB_URL` env vars in `/home/scott/pka/workspaces/vcf-content-factory/.env`
