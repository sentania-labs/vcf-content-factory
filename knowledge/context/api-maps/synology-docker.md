# Synology API Map: Docker (Docker Container Object)

## Endpoints

### SYNO.Docker.Container (list)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Docker.Container&version=1&method=list&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema

**CONFIRMED 2026-04-16 via live API call.** The `list` response returns detailed Docker inspect-level data per container but does NOT include CPU/memory resource metrics inline. Resource metrics come from a separate `SYNO.Docker.Container.Resource` API.

Sample container entry (abbreviated -- full response includes Labels, NetworkSettings, Mounts, HostConfig):
```json
{
  "Image": "ghcr.io/immich-app/immich-server:v2",
  "ImageID": "sha256:44da6b17...",
  "Labels": { "com.docker.compose.service": "immich-server", "..." : "..." },
  "NetworkSettings": { "Networks": { "immich-app_default": { "IPAddress": "172.17.0.3", "..." : "..." } } },
  "State": {
    "Dead": false,
    "Error": "",
    "ExitCode": 0,
    "FinishedAt": "2026-02-24T14:19:33.036106954Z",
    "Health": { "FailingStreak": 0, "Status": "healthy", "Log": [] },
    "OOMKilled": false,
    "Paused": false,
    "Pid": 21886,
    "Restarting": false,
    "Running": true,
    "StartedAt": "2026-02-24T14:23:14.459089407Z",
    "Status": "running"
  },
  "cmd": "tini -- /bin/bash -c start.sh",
  "created": 1769627261,
  "enable_service_portal": false,
  "exporting": false,
  "finish_time": null,
  "id": "5b09fd8f9659...",
  "image": "ghcr.io/immich-app/immich-server:v2",
  "is_ddsm": false,
  "is_package": false,
  "name": "immich_server",
  "services": null,
  "status": "running",
  "up_status": "Up 7 weeks (healthy)",
  "up_time": null
}
```

The `list` response also includes pagination fields at the top level:
```json
{
  "data": {
    "containers": [ ... ],
    "limit": 4,
    "offset": 0,
    "total": 4
  }
}
```

**Important finding**: `up_time` is always `null` in the `list` response. Uptime must be derived from `State.StartedAt` (ISO 8601 timestamp). The `up_status` field provides a human-readable string (e.g., "Up 7 weeks (healthy)") but is not machine-parseable.

#### Field -> Object Mapping (from `list` response)

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `name` | container_name | IDENTIFIER | STRING | | Primary key; unique within the NAS |
| `name` | name | PROPERTY | STRING | | Display name |
| `id` | container_id | PROPERTY | STRING | | Docker container ID (64-char hex) |
| `image` | image | PROPERTY | STRING | | Container image reference (includes registry) |
| `status` | status | PROPERTY | STRING | | "running", "stopped" (top-level shorthand) |
| `State.Status` | state | PROPERTY | STRING | | "running", "exited", "paused", "dead" (Docker native) |
| `State.Health.Status` | health | PROPERTY | STRING | | "healthy", "unhealthy", "" (no healthcheck defined) |
| `State.StartedAt` | started_at | PROPERTY | STRING | | ISO 8601 timestamp; use to derive uptime |
| `State.Running` | is_running | PROPERTY | BOOLEAN | | Direct boolean for running state |
| `State.OOMKilled` | oom_killed | PROPERTY | BOOLEAN | | OOM kill flag |
| `State.ExitCode` | exit_code | METRIC | NUMBER | | Last exit code (0 = clean) |
| `up_status` | up_status | PROPERTY | STRING | | Human-readable uptime string (e.g., "Up 7 weeks (healthy)") |
| `created` | created | PROPERTY | NUMBER | unix epoch | Container creation timestamp |
| `is_ddsm` | is_ddsm | PROPERTY | BOOLEAN | | Whether container is a Docker DSM instance |
| `is_package` | is_package | PROPERTY | BOOLEAN | | Whether container is a Synology package |
| `Labels["com.docker.compose.project"]` | compose_project | PROPERTY | STRING | | Compose project name (if applicable) |
| `Labels["com.docker.compose.service"]` | compose_service | PROPERTY | STRING | | Compose service name (if applicable) |

**Note on uptime**: `up_time` is always `null` in both `list` and `get` responses. Uptime must be calculated as `now - State.StartedAt`. The MPB should parse the ISO 8601 `StartedAt` timestamp and compute seconds since start.

---

### SYNO.Docker.Container.Resource (get)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Docker.Container.Resource&version=1&method=get&_sid=<session>`
- **Auth**: Session ID required (admin)

**CONFIRMED 2026-04-16 via live API call.** This is the endpoint for per-container CPU and memory metrics. Returns all running containers in a single call (no per-container requests needed).

#### Response Schema

```json
{
  "success": true,
  "data": {
    "resources": [
      {
        "cpu": 0.30000001192092896,
        "memory": 379998208,
        "memoryPercent": 1.825469732284546,
        "name": "immich_server"
      },
      {
        "cpu": 0,
        "memory": 270413824,
        "memoryPercent": 1.2990384101867676,
        "name": "immich_postgres"
      },
      {
        "cpu": 0.02500000037252903,
        "memory": 41988096,
        "memoryPercent": 0.20170621573925018,
        "name": "immich_machine_learning"
      },
      {
        "cpu": 0.10000000149011612,
        "memory": 28852224,
        "memoryPercent": 0.13860292732715607,
        "name": "immich_redis"
      }
    ]
  }
}
```

#### Field -> Object Mapping (Resource metrics)

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `name` | (join key) | | STRING | | Matches `containers[].name` from `list` response |
| `cpu` | cpu_usage | METRIC | NUMBER | % | CPU usage percentage (float, e.g., 0.3 = 0.3%) |
| `memory` | memory_usage | METRIC | NUMBER | bytes | Memory usage in bytes (e.g., 379998208 = ~362 MB) |
| `memoryPercent` | memory_usage_pct | METRIC | NUMBER | % | Memory usage as % of NAS total RAM (float, e.g., 1.83%) |

**Note**: The `get` method on `SYNO.Docker.Container` (per-container detail) also returns `memory` (bytes) and `memoryPercent` (%) at the top level of `data.details`, but NOT `cpu`. The `Container.Resource` API is the authoritative single-call source for both CPU and memory across all containers.

---

## Identifier Chains (Relationships)

### Diskstation -> Docker Container
- All containers are direct children of the Diskstation (world object)
- No explicit join field needed; all containers belong to the one NAS
- Container `name` is unique within the NAS

---

## Collection Strategy

- **Requests per cycle (5-min interval)**: 1
  - `SYNO.Docker.Container.Resource` `get` -- CPU and memory for all running containers in one call

- **Requests per cycle (30-min interval)**: 1
  - `SYNO.Docker.Container` `list` -- container inventory, state, health, image, compose metadata

- **Pagination**: The `list` response includes `limit`, `offset`, `total` fields. Pass `limit=0&offset=0&type=all` to get all containers in one call. Observed: 4 containers returned with `total: 4`.
- **Known quirks**:
  - Docker package must be installed on the NAS; API returns error 102 if not
  - Container names may include underscores (compose-style naming: `immich_server`)
  - Container health depends on whether the image defines a HEALTHCHECK -- containers without HEALTHCHECK have `State.Health.Status` as empty string
  - `up_time` field is always `null` in both `list` and `get` responses -- uptime must be derived from `State.StartedAt`
  - `Container.Resource` returns only running containers -- stopped containers will not appear in the `resources` array
  - CPU values from `Container.Resource` are float percentages (e.g., 0.3 means 0.3% of total NAS CPU)
  - Memory values are in bytes; `memoryPercent` is pre-calculated as % of total NAS RAM
  - The `list` response contains full Docker inspect-level data (Labels, NetworkSettings, Mounts, HostConfig) -- much richer than initially assumed
  - `get_status` method does not exist (returns error 103); `stats` method exists but returns raw Docker stats (cgroup-level counters, not pre-calculated) -- use `Container.Resource` instead

## Gaps (all closed 2026-04-16)

- **cpu_usage**: CONFIRMED. Field is `cpu` (float, %) from `SYNO.Docker.Container.Resource` `get`. Not available in `list` response.
- **memory_usage**: CONFIRMED. Field is `memory` (bytes) and `memoryPercent` (%) from `SYNO.Docker.Container.Resource` `get`. Also available in `Container` `get` per-container detail but not in `list`.
- **uptime**: CONFIRMED NOT AVAILABLE as a direct field. `up_time` is always `null`. Derive from `State.StartedAt` (ISO 8601 timestamp in `list` response). The `up_status` field (e.g., "Up 7 weeks (healthy)") is human-readable only.
