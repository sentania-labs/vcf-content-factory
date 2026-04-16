# Synology API Map: Docker (Docker Container Object)

## Endpoints

### SYNO.Docker.Container (list)

- **Path**: `/webapi/entry.cgi`
- **Method**: GET
- **Params**: `api=SYNO.Docker.Container&version=1&method=list&_sid=<session>`
- **Auth**: Session ID required (admin)

#### Response Schema

```json
{
  "success": true,
  "data": {
    "containers": [
      {
        "name": "immich_server",
        "image": "ghcr.io/immich-app/immich-server:v2",
        "state": "running",
        "health": "healthy",
        "up_time": 4320000,
        "cpu_usage": 2.5,
        "memory_usage": 524288000
      },
      {
        "name": "immich_postgres",
        "image": "postgres:14-vectorchord0.4.3",
        "state": "running",
        "health": "",
        "up_time": 4320000,
        "cpu_usage": 0.3,
        "memory_usage": 262144000
      },
      {
        "name": "immich_machine_learning",
        "image": "immich-machine-learning:v2",
        "state": "running",
        "health": "",
        "up_time": 4320000,
        "cpu_usage": 1.0,
        "memory_usage": 1073741824
      },
      {
        "name": "immich_redis",
        "image": "valkey:9",
        "state": "running",
        "health": "",
        "up_time": 4320000,
        "cpu_usage": 0.1,
        "memory_usage": 8388608
      }
    ]
  }
}
```

**Note**: The exact response field names for CPU/memory/uptime within the container list are not fully confirmed from the live brief. The brief confirms `SYNO.Docker.Container` `list` returns "All containers with image, state, health (Immich stack: 4 containers)" but does not capture the detailed per-field schema. The fields shown above are based on the design artifact's requirements and community documentation (N4S4/synology-api, Home Assistant integration). Field names need live API verification.

#### Field -> Object Mapping

| Response Field | MP Key | Usage | Type | Unit | Notes |
|---|---|---|---|---|---|
| `name` | container_name | IDENTIFIER | STRING | | Primary key |
| `name` | name | PROPERTY | STRING | | Display name |
| `image` | image | PROPERTY | STRING | | Container image reference |
| `state` | status | PROPERTY | STRING | | "running", "stopped", "exited" |
| `health` | health | PROPERTY | STRING | | "healthy", "unhealthy", "" (no healthcheck) |
| `cpu_usage` | cpu_usage | METRIC | NUMBER | % | SOURCE: NOT CONFIRMED -- field name and unit need live verification |
| `memory_usage` | memory_usage | METRIC | NUMBER | bytes | SOURCE: NOT CONFIRMED -- field name and unit need live verification |
| `up_time` | uptime | METRIC | NUMBER | seconds | SOURCE: NOT CONFIRMED -- field name needs live verification |

---

## Identifier Chains (Relationships)

### Diskstation -> Docker Container
- All containers are direct children of the Diskstation (world object)
- No explicit join field needed; all containers belong to the one NAS
- Container `name` is unique within the NAS

---

## Collection Strategy

- **Requests per cycle (30-min interval)**: 1
  - `SYNO.Docker.Container` `list` -- container inventory and status

- **Pagination**: Unknown -- likely none for typical container counts (< 50)
- **Known quirks**:
  - Docker package must be installed on the NAS; API returns error 102 if not
  - Container names may include underscores (compose-style naming: `immich_server`)
  - Container health depends on whether the image defines a HEALTHCHECK -- some containers will have empty health
  - CPU/memory usage may only be available when the container is running
  - The exact response structure for resource usage (cpu_usage, memory_usage) needs live verification -- the community wrappers document `get` method with container name for detailed stats, while `list` may return summary data only
  - If detailed per-container resource metrics are not in the `list` response, a separate `SYNO.Docker.Container` `get` call per container may be needed (increases request count)

## Gaps

- **cpu_usage field name and availability**: SOURCE: NOT CONFIRMED. The live brief confirms the API returns "state, health" but does not explicitly confirm CPU usage in the list response. May require `get` method per container.
- **memory_usage field name and availability**: SOURCE: NOT CONFIRMED. Same as above.
- **uptime field name**: SOURCE: NOT CONFIRMED. May be `up_time`, `uptime`, or calculated from container start time.
- **Detailed container stats**: If `list` only returns metadata (name, image, state, health), a separate `SYNO.Docker.Container` `get` with `method=get_status` or similar may be needed for CPU/memory. This would add N requests per cycle (one per container).
