# Reference sources (allowlist)

External repositories and archives that ops-recon **must** grep
before concluding that a piece of content does not already exist.
These are ground-truth examples of working VCF Operations content
— dashboards, views, super metrics, policies — authored by people
other than us. Adapting an existing bundle is almost always cheaper
and more correct than authoring from scratch.

## Hard rules

1. **Allowlist only.** ops-recon may only consult sources listed
   in this file. New sources are added here by the orchestrator
   after the user approves them; agents do not add entries on
   their own.
2. **Local clones only.** Sources are cloned under `references/`
   (gitignored). Agents grep the local clone; no WebFetch round
   trips. If a listed source is missing locally, ops-recon reports
   that as a gap and continues with the remaining sources — it
   does not try to clone.
3. **Attribution preserved.** If content from a reference source
   is adapted into this repo, the resulting YAML must cite the
   source path + original filename in its description, and any
   license/attribution requirement in the source entry below
   must be honored.
4. **Never copy blindly.** Reference content is a starting point,
   not a drop-in. Super metric UUIDs, metric keys, and adapter
   kinds must still be validated against this instance's live
   vocabulary (`/statkeys`) before the adapted content is synced.

## Clone convention

```
references/
  <source-slug>/        # git clone or extracted archive
```

The directory is gitignored. Populate with:

```bash
mkdir -p references
git clone <url> references/<slug>
# or refresh:
cd references/<slug> && git pull
```

No automation yet — manual clone/pull is fine for now. If the
list grows past ~3 sources, add a `scripts/sync_references.sh`.

## Sources

### sentania/AriaOperationsContent

- **URL:** https://github.com/sentania/AriaOperationsContent
- **Local path:** `references/AriaOperationsContent/`
- **Owner:** user (sentania). Public repo.
- **Scope:** Working content bundles for VCF Operations —
  dashboards, views, super metrics, and policies packaged as
  content-import zips and/or raw JSON/XML. Organized by topical
  bundle (e.g., `VCF License Consumption Overview`).
- **What to grep for:**
  - **Super metric formulas:** `*.json` files named
    `supermetric.json` or similar — keyed by UUID, contain the
    raw formula DSL. Grep for metric keys (`cpu|readyPct`) or
    resource kinds (`ClusterComputeResource`) to find examples.
  - **Dashboards:** `dashboard.zip` bundles — extract and read
    the widget definitions for patterns (ResourceList pickers,
    View embeds, interaction wiring).
  - **Views:** `views.zip` bundles — list view subjects, columns,
    and filters.
  - **Policy XML:** look for `exportedPolicies.xml` inside policy
    export zips for examples of `<SuperMetrics>` blocks and
    per-resource-kind enablement patterns.
- **Wire format note:** supermetric.json is keyed by UUID, which
  is why this repo's UUID-stability contract exists. See
  `context/uuids_and_cross_references.md`.
- **Attribution:** public repo, no explicit license last checked
  — when adapting, cite `sentania/AriaOperationsContent/<bundle>/<file>`
  in the YAML description.

<!-- Add new sources below. Keep entries in the same shape. -->
