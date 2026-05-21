# War Story: UniFi Metric Key Parity — MPB Ignores Your Keys

**Campaign:** UniFi MP .13 release  
**Date:** 2026-05-16  
**Core finding:** MPB derives metric keys from labels. The `key:` field in design.json is ignored.

## The discovery

Six of eight UniFi base metrics had different keys when installed via the factory
vs. installed via MPB UI. Symptoms built against `cpu_pct` would have silently
failed against an MPB-installed pak that emitted `cpu_`:

| Label | Factory key (pre-fix) | MPB-derived key |
|---|---|---|
| `CPU %` | `cpu_pct` | `cpu_` |
| `Memory %` | `mem_pct` | `memory_` |
| `Uptime (s)` | `uptime_seconds` | `uptime_s` |
| `Load Average (1m)` | `load_avg_1m` | `load_average_1m` |

We assumed we could fix parity by setting explicit `key:` values in design.json.
We were wrong. MPB's API import ignores the `metric.key` field entirely — the
runtime emits whatever the label-derivation algorithm produces regardless. The
only fix was making the factory match what MPB does (not the other way around).

The derivation algorithm is documented in
`context/mpb_explicit_key_investigation_2026_05_16.md`. Factory YAML `key:` is
now an authoring-side identifier only — never written on the wire.

## The filter projection dead-end

While investigating the radio metrics (TX retries per radio), we confirmed that
MPB's runtime doesn't support JMESPath filter projections. The expression grammar
is dot-path + single `data.*`, backed by Jackson `JsonNode` — zero predicates.
Cleanroom corpus analysis (54 paths, all dot-path) confirmed this. First-party
engineer confirmed JQ filter targets MPB 9.2, not present in current runtime.

The tempting workaround was `radio_table[0]` / `radio_table[1]` index access.
We chose to drop the radio metrics instead:

- **Cost of dropping:** a note in `known_limitations.md`, deferred capability
- **Cost of shipping:** silent wrong-band labels when firmware updates reorder
  the array, escaping into dashboards and alerts, no obvious failure signal for
  operators

The math is asymmetric. Drop wins. Refuse fragile early; re-add cleanly when
the capability lands (MPB 9.2 or Tier 2 promotion).

## Verification timing pitfall

The install agent reported several metrics as "absent" — claimed source-data gap.
The user looked at the UI and saw the values flowing. The agent had queried prod
before the second collection cycle landed.

Pattern: when an agent reports "metric X not flowing," treat it as "not flowing
*at the moment recon queried*," not as "will never flow." Confirm by waiting an
extra collection cycle or asking the user to eyeball the UI.

## Process pattern that worked

Parallel install paths (factory → prod, MPB → devel) within minutes of each
other gave us same-source, different-pipeline behavior to compare directly. That's
how we proved key parity worked — identical registered keys on both sides.

For capability questions, the three-question form proved reliable:
1. **What does the runtime parse?** (cleanroom corpus)
2. **Is there a reference pak doing X?** (grep references/)
3. **What's the idiomatic pattern?** (implies the answer to Q1+Q2)

All three agreed before making a decision.

## Reference files

- `context/mpb_explicit_key_investigation_2026_05_16.md` — derivation algorithm
- `context/mp_authoring_design_principles.md` — codified design rules
- `context/known_limitations.md` — "MPB <9.2 runtime: no JMESPath filter projections"
