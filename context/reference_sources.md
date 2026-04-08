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

### brockpeterson/operations_supermetrics

- **URL:** https://github.com/brockpeterson/operations_supermetrics
- **Local path:** `references/brockpeterson_operations_supermetrics/`
- **Owner:** Brock Peterson (Broadcom/VCF field). Public repo.
- **Scope:** Curated VCF Operations super metrics.
- **What to grep for:** formula DSL examples, metric keys, resource
  kinds. Cross-check against `docs/vcf9/` before adapting.
- **Attribution:** cite `brockpeterson/operations_supermetrics/<file>`
  in adapted YAML descriptions.

### brockpeterson/operations_dashboards

- **URL:** https://github.com/brockpeterson/operations_dashboards
- **Local path:** `references/brockpeterson_operations_dashboards/`
- **Owner:** Brock Peterson. Public repo.
- **Scope:** VCF Operations dashboards (most-starred repo in the set
  — 31★). Likely includes widget layouts, ResourceList pickers, view
  embeds, and interaction wiring.
- **What to grep for:** dashboard JSON/zip bundles, widget kinds,
  referenced view/super-metric UUIDs or names.
- **Attribution:** cite `brockpeterson/operations_dashboards/<file>`.

### brockpeterson/operations_reports

- **URL:** https://github.com/brockpeterson/operations_reports
- **Local path:** `references/brockpeterson_operations_reports/`
- **Owner:** Brock Peterson. Public repo.
- **Scope:** VCF Operations report definitions. Reports are not yet
  a first-class authoring target in this repo, but the bundles may
  reference views/dashboards worth adapting.
- **Attribution:** cite `brockpeterson/operations_reports/<file>`.

### brockpeterson/operations_alerts

- **URL:** https://github.com/brockpeterson/operations_alerts
- **Local path:** `references/brockpeterson_operations_alerts/`
- **Owner:** Brock Peterson. Public repo.
- **Scope:** VCF Operations alert definitions / symptom + alert
  templates. Alerts are not yet a first-class authoring target here,
  but the symptom definitions often reference super metrics worth
  mining.
- **Attribution:** cite `brockpeterson/operations_alerts/<file>`.

### tkopton/aria-operations-content

- **URL:** https://github.com/tkopton/aria-operations-content
- **Local path:** `references/tkopton_aria_operations_content/`
- **Owner:** Thomas Kopton. Public repo, no explicit license.
- **Scope:** Aria/VCF Operations content — dashboards, views, super
  metrics, and related bundles.
- **What to grep for:** super metric formulas, dashboard widget
  layouts, view definitions. Cross-check metric keys against
  `docs/vcf9/` before adapting.
- **Attribution:** cite `tkopton/aria-operations-content/<file>` in
  adapted YAML descriptions.

### dalehassinger/unlocking-the-potential

- **URL:** https://github.com/dalehassinger/unlocking-the-potential
- **Local path:** `references/dalehassinger_unlocking_the_potential/`
- **Owner:** Dale Hassinger. Public repo, companion code to his blog.
- **Scope:** Multi-product; the relevant subtree is
  `VMware-Aria-Operations/` which contains `Dashboards/`, `Views/`,
  `SuperMetrics/`, `Metric-Searches/`, `Management-Packs/`, and
  `API-Examples/`. Ignore sibling directories (Ansible, Photon,
  PowerShell-PowerCLI, Aria Automation, Aria Ops Logs, Tiered-Memory,
  VMware Explore session material) — out of scope.
- **What to grep for:** super metric JSON exports, dashboard/view
  bundles. Restrict greps to
  `references/dalehassinger_unlocking_the_potential/VMware-Aria-Operations/`.
- **Attribution:** cite
  `dalehassinger/unlocking-the-potential/VMware-Aria-Operations/<path>`.

### johnddias/vrops-super-metric-numa-optimize

- **URL:** https://github.com/johnddias/vrops-super-metric-numa-optimize
- **Local path:** `references/johnddias_vrops_super_metric_numa_optimize/`
- **Owner:** John Dias. Public repo.
- **Scope:** Focused bundle — `NUMA Optimization.json` super metric
  export implementing VM NUMA/CPU sizing logic based on the VMware
  "Virtual Machine Computer Optimizer" fling.
- **What to grep for:** NUMA/CPU sizing super metric formulas,
  host-relationship traversal patterns.
- **Attribution:** cite
  `johnddias/vrops-super-metric-numa-optimize/NUMA Optimization.json`.

<!-- Add new sources below. Keep entries in the same shape. -->
