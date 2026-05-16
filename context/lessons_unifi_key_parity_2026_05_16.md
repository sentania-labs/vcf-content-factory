# Lessons learned: UniFi .13 metric-key parity sprint (2026-05-16)

Session-specific learnings from getting the factory-built UniFi pak
and the MPB-pipeline UniFi design to emit byte-identical metric
keys, and from deciding *not* to ship the radio metrics. Forward-
looking guidance is in `context/mp_authoring_design_principles.md`;
this file captures what we did, what surprised us, and what we'd
do the same way next time.

## What we set out to do

1. Make factory-built `.pak` output and MPB-pipeline `.pak` output
   produce identical metric keys for the same source YAML.
2. Investigate why the UniFi per-radio TX-retries metrics weren't
   flowing on prod (filter-projection expressions).
3. Ship a `.13` build of the UniFi MP that resolves both.

## What actually drove the design

### Cross-pipeline key parity is a hard requirement, not nice-to-have

The framework's promise is "author content (symptoms, alerts,
dashboards, SMs) against a metric key, sync it to any VCF Ops
instance." That breaks the moment two ways of building the same
MP emit different keys on the wire. We saw this concretely:

| Label | YAML key (factory wire pre-fix) | MPB-derived wire |
|---|---|---|
| `CPU %` | `cpu_pct` | `cpu_` |
| `Memory %` | `mem_pct` | `memory_` |
| `Uptime (s)` | `uptime_seconds` | `uptime_s` |
| `Load Average (1m)` | `load_avg_1m` | `load_average_1m` |

Six of eight UniFi base metrics drifted. A symptom referencing
`cpu_pct` would have failed against an MPB-installed pak. This
isn't a corner case — it's structural drift between the two
official paths to install an MP.

**Fix:** factory derives keys from labels using the same algorithm
MPB uses (`mpb_explicit_key_investigation_2026_05_16.md` documents
the algorithm). YAML `key:` becomes an authoring-side identifier
only — never written on the wire.

### Cleanroom triangulation is the right tool for capability questions

We hit "does MPB runtime support JMESPath filter projections?"
three times in the same session. Each time we layered:

1. **Empirical:** install a probe build, watch what flows. Devel
   MPB pipeline + prod factory pak both showed the same 4/8 — that
   *itself* was diagnostic, ruling out factory-specific bugs.
2. **Cleanroom corpus analysis:** "across all the reference paks
   we have, find every compiled expression and tell us the
   grammar bound." Came back: 54 paths, all dot-path + `data.*`,
   zero predicates, Jackson `JsonNode` backed.
3. **First-party engineer:** confirmed jq filter is targeted for
   MPB 9.2, not present in current runtime.

All three agreed before we made a decision. Any single source on
its own would have been weaker — empirical doesn't bound the
grammar, cleanroom doesn't tell you the roadmap, first-party
doesn't tell you the exact mechanics. Together they're definitive.

**Pattern to keep:** when you have a capability question that's
costing iteration cycles, structure it as three concrete questions
(Q1: what does the runtime parse? Q2: is there a reference pak
doing X? Q3: what's the idiomatic pattern?) and hand all three to
the cleanroom team. They can answer Q1/Q2 surgically; Q3 forces
them to crystallize the *implication* of Q1/Q2.

### Refusing fragile is cheaper than supporting fragile

Once we knew filter projections weren't supported, the tempting
quick-win was `radio_table[0]` / `radio_table[1]` index access.
Would have shipped. Would have produced "Radio 2.4 GHz TX Retries"
that lied on any device where the array was reordered (firmware
update, Wi-Fi 6E tri-band APs at customer sites we don't control).

Cost of dropping: a short note in `known_limitations.md` and a
deferred capability that re-adds cleanly when MPB 9.2 lands or via
Tier 2 promotion.

Cost of shipping fragile: silent wrong-band labels in customer
deployments, escaping into dashboards and alerts, no obvious
trigger for the customer to suspect the data is wrong, support
burden permanently elevated.

The math is asymmetric and "drop" wins. Codified as Principle 1
in `mp_authoring_design_principles.md`.

## Surprises

### MPB derives keys from labels period — `key:` in design.json is ignored

We thought the MPB API import would respect an explicit `metric.key`
in the design.json. It doesn't. The runtime emits whatever the
label-derivation algorithm produces, regardless of what's in the
design body. This is why .12 design.json imports on devel produced
`cpu_`, `memory_`, `uptime_s` while the factory pak from the same
YAML produced `cpu_pct`, `mem_pct`, `uptime_seconds`.

That meant we couldn't fix parity by "making MPB respect our
keys" — only by making the factory respect what MPB does. Which
also turned out to be the simpler change.

### Installer-agent verification is timing-sensitive

The prod install agent reported `memory_pct` and `load_average_*`
as "absent" — claimed source-data gap. User looked at the UI and
saw the values flowing. Recon agent ran later and also showed
them flowing on devel but absent on prod, where the user saw them
in the UI.

Root cause: agent verification queried prod before the second
collection cycle had landed the values, then concluded "no data
points." This kind of false-negative is hard to detect in an
automated report.

**Pattern to keep:** when an agent reports "metric X not flowing,"
treat it as "not flowing *at the moment recon queried*," not as
"will never flow." Confirm by waiting an extra collection cycle
or asking the user to eyeball the UI. The user's "visually
they're there" caught what the agent's API query missed.

### Parallel install paths (factory→prod, MPB→devel) is a useful diagnostic

Yesterday we agreed devel stays on the MPB pipeline as the
canonical first-party install path; today the user manually
imported `.13` design.json there while the factory `.pak` installed
on prod. The two paths landing within minutes of each other gave
us same-source, different-pipeline behavior to compare directly.
That's how we proved key parity worked — by seeing identical
registered keys on both sides.

## What we'd change next time

1. **Sequence the renderer change before any compound-MP rewrite.**
   We discovered the key-drift problem only after building
   `.12`, which meant we shipped a pak that had to be re-shipped.
   If the orchestrator runs a "key parity audit" as a first-class
   gate on every MP build, this surfaces before authoring time
   instead of post-install.

2. **Lint the YAML at validation time for label quality.** The
   `[label-lint]` warning we added now catches `%`, `.`, parens in
   labels — but only when authors run validate. A pre-author hook
   in `mp-author` that surfaces label quality before emitting would
   prevent the original drift entirely.

3. **Cleanroom-question template.** The three-questions form we
   used (parser grammar / reference pak example / idiomatic
   pattern) worked well. Codify it as a template in
   `context/cleanroom_handoff_template.md` so future MP work hits
   the same productive shape from turn one.

## References

- `context/mp_authoring_design_principles.md` — codified design rules
- `context/mpb_explicit_key_investigation_2026_05_16.md` — derivation algorithm
- `context/mpb_designer_wire_format.md` — runtime expression grammar
- `context/known_limitations.md` §"MPB <9.2 runtime: no JMESPath filter projections"
