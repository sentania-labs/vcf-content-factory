# MP icon library

Per-resource-kind SVG icons that ship inside factory-built management
pack paks. Shared across all MPs — pick by hint, not by authoring new
files per MP.

## Where the icons live

`src/vcfops_managementpacks/templates/icons/<hint>.svg`

These are factory-authored, single-color flat vectors using
`viewBox="0 0 400 400"` and the VMware-blue palette
(`#0098c7` + optional `#005c8a` accents). They match the visual style
of MPB's stock SVGs without copying VMware's actual logo.

## How the builder picks an icon

For each `object_types[]` entry in the MP YAML, the builder looks at
the optional `icon:` field:

```yaml
object_types:
  - key: access_point
    label: Access Point
    icon: access_point        # → templates/icons/access_point.svg
    ...
```

Behavior:

- If `icon:` is set and matches a file in `templates/icons/`, use that SVG.
- If `icon:` is set but the file doesn't exist, fall back to
  `default.svg` (and the builder emits a WARN — see "Validation" below).
- If `icon:` is unset, fall back to `default.svg`.

Output paths inside the pak:

- `conf/images/ResourceKind/<adapter_kind>_<object_type.key>.svg` —
  one per declared object_type
- `conf/images/AdapterKind/<adapter_kind>.svg` — adapter-level
- `conf/images/TraversalSpec/default.svg` — traversal browser
- `default.svg` at pak root — manifest `pak_icon`

## Available hints (2026-05-16)

| Hint | Silhouette | Typical use |
|---|---|---|
| `default` | Hexagon outline + inner hex + center dot | Fallback. Don't reference explicitly — it's automatic. |
| `access_point` | Disc/dome with concentric wifi arc waves | Wireless APs |
| `switch` | 1U rack chassis with port row + status LEDs | Network switches |
| `gateway` | Shield outline with bidirectional traffic arrows | Routers, firewalls, gateways |
| `client` | Laptop silhouette (screen + keyboard + touchpad) | Endpoint devices, clients |
| `network` | Three connected nodes (hub + 2 leaves) | VLANs, subnets, networks |
| `world` | Globe with equator + meridians | Root container, "world" object |
| `adapter_instance` | Plug + socket with directional arrow | The synthetic adapter-instance object every MP has |
| `host_system` | Server rack unit with disk bays + LEDs | Physical/virtual host servers |
| `datastore` | Stacked disk platters + capacity bar | Storage volumes, datastores, file shares |
| `nas` | Front-facing desktop NAS enclosure with 4 drive bays, status LEDs, network port | NAS appliances (e.g. Synology DiskStation) |
| `storage_pool` | Stacked disk platters with RAID shield/check-mark badge overlay | RAID storage pools |
| `disk` | 3.5" hard drive with platter circle and connector pins | Individual physical disks |
| `iscsi_lun` | Cylinder (LUN shape) with target/crosshair overlay on top face | iSCSI LUNs |
| `nfs_export` | Folder shape with share arrow and dual destination nodes | NFS exports, shared folders |
| `ups` | Rectangular battery body with positive terminal nub and lightning bolt | UPS devices |

## When the library doesn't have a fit

The library is meant to grow. When designing an MP with a resource
kind that doesn't match any existing hint, **don't shoehorn it into
the closest fit and don't ship as default.** Instead:

1. **mp-designer** raises a **TOOLSET GAP** during the design
   interview: "Object type `<kind>` has no matching icon hint in the
   library. Closest existing options: `<list>`. Recommend adding
   `<new_hint>.svg` for: `<one-line description of the silhouette>`."
2. The orchestrator delegates to `tooling` to author the SVG in the
   same style (`viewBox="0 0 400 400"`, `#0098c7` palette, flat 2D,
   single accent color, 8-12% edge padding, recognizable at thumbnail
   size).
3. Once the SVG lands in `templates/icons/`, design and authoring
   continue with the new hint resolved.
4. The new icon is now available to every future MP — the library
   accumulates.

## When two object types could share a hint

Reuse is encouraged. If a new MP has a "WiFi Radio" kind that's
conceptually adjacent to `access_point`, reusing `access_point` is
fine — the hint is about visual category, not exact object type.
Authoring a new icon is only justified when no existing hint is
visually adequate.

## What's NOT here

- **Per-MP custom icons** — no `content/managementpacks/icons/<mp>/<rk>.svg`
  override path. The framework deliberately centralizes the library.
  If a future MP needs a unique icon, add it to `templates/icons/` and
  reference the hint; don't fork per MP.
- **Icons for ARIA_OPS-stitched object types** — those objects don't
  appear in the MP's describe.xml as ResourceKinds (they target
  foreign adapter kinds like `VMWARE:Datastore`), so the pak doesn't
  ship icons for them. The `icon:` field is accepted on ARIA_OPS
  types for documentation but the file is not written to the pak.
- **Multi-state / variant icons** — one icon per kind. UI variations
  (e.g. "healthy vs degraded") come from VCF Ops's own badge layer,
  not from the MP.

## Validation

The builder emits a WARN at build time when any object_type falls back
to `default.svg` — either because the YAML lacked an `icon:` hint or
because the hint didn't resolve to a file. WARN format:

```
[icon] object_type '<key>' has no resolved icon hint, using default.svg
```

This is an authoring smell, not a hard failure: the pak still ships,
the UI renders the default hexagon, but the framework's discipline is
"every kind should have a deliberate icon choice." If a fallback is
intentional (e.g. an internal synthetic kind that doesn't need its own
silhouette), the YAML should set `icon: default` explicitly to silence
the WARN.

## Related

- `src/vcfops_managementpacks/builder.py` — `_icon_bytes_for(hint)` helper
  and the `conf/images/` write loop
- `src/vcfops_managementpacks/loader.py` — `ObjectTypeDef.icon` field +
  `_parse_icon_hint()` extension normalization
- `src/vcfops_managementpacks/templates/icons/` — the SVG files themselves
- `.claude/agents/mp-designer.md` — icon-selection step in the design
  interview
- `.claude/agents/mp-author.md` — icon-resolution enforcement at YAML
  emission time
