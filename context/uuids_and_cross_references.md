# UUIDs are part of the contract

The central design constraint of this repo. Read this before touching
anything that creates or references content objects.

## The problem

- View definitions reference super metrics as literal `sm_<uuid>`
  strings in `attributeKey`. **No name-based lookup exists.**
- Dashboard widgets reference views by UUID (and, indirectly, the
  super metrics those views use).
- Super metric formulas cross-reference other super metrics as
  `${this, metric=Super Metric|sm_<uuid>}`.
- Therefore a repo-authored bundle (super metrics + views +
  dashboards) survives cross-instance installation only if every
  object lands with the **same UUID on every instance**.

## Why `POST /api/supermetrics` is a dead end

The public create endpoint rejects caller-supplied `id`:

```
POST /api/supermetrics  →  400 "must be null"
```

Confirmed empirically against the lab. Server assigns a fresh random
UUID every time. That's incompatible with bundle portability.

## The scheme

**Store a random UUIDv4 in the YAML** at authoring time, reuse it
forever.

```yaml
id: 76801377-1807-4a46-93d4-9b9dc0f0c54b   # generated once, never touched
name: [VCF Content Factory] Cluster - Avg Powered-On VM CPU Usage (%)
```

- The loader generates a `uuid4()` and writes it back on first
  `validate` if the `id` field is missing. Subsequent runs reuse it.
- Rename-safe: changing `name` does not change `id`, so cross-refs
  survive authoring iteration.
- Matches the pattern the sentania/AriaOperationsContent bundles
  already use — the `supermetric.json` files there are keyed by
  hand-picked v4 UUIDs, for the same reason.
- No namespace bookkeeping, no "derive from name" magic, no collision
  surface between authors.

## The install path

Install flows through `POST /api/content/operations/import` with a
zip whose `supermetrics.json` is keyed by the YAML's `id`. Ops stores
the UUID verbatim — verified round-trip: derived a custom UUID, built
a content zip with it, imported, listed, UUID matched byte-for-byte.

See `context/wire_formats.md` for the exact zip layout and
`context/install_and_enable.md` for the CLI flow.

## Cross-references in authoring

Because UUIDs live in the YAML, the loader can resolve references by
name at load time without round-tripping to the server:

- **Views/dashboards referencing a super metric**: YAML uses
  `attribute: supermetric:"<name>"`; loader looks up the super metric
  YAML by name, reads its `id`, emits `sm_<id>`.
- **Super metric formulas referencing another super metric**: YAML
  uses `@supermetric:"<name>"` inside the formula string; loader
  rewrites to `sm_<id>` at validation time. Validation fails loudly
  if the referenced name doesn't resolve.

## Orphan and rename handling

Under the new scheme renaming a YAML keeps the same `id`, so the
orphan problem is much smaller than before. But deleting a YAML
leaves the corresponding super metric on the server until someone
cleans it up. Plan: an `orphans` CLI that lists server-side objects
whose UUID doesn't match any current YAML, so operators can prune.
