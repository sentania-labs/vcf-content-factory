# Growth path — toward "Hi, I'm vcf-cf"

The factory's north-star, as articulated by Scott on 2026-04-29:

> "Hi, I'm vcf-cf. Give me API credentials, an API spec, or an API
> starting point, and I'll build you a management pack we can iterate on."

This document captures the gap between today and that vision, and a
prioritized work plan to close it. Sibling document
`context/mpb_synology_pickup_2026_04_29.md` is the operational log for
the active workstream that exposed most of the gaps below.

---

## Where we are (2026-04-29)

### What's mature

**Non-MP content authoring.** Dashboards, super metrics, views, custom
groups, symptoms, alerts, reports. Sharp authoring agents, well-mapped
wire formats, working install pipelines. Recurring authoring for
non-MP content rarely surprises anymore. Edge cases (PropertyList
widget, multi-policy enable, recommendations-via-REST) are documented
known limitations rather than mysteries.

**Content-zip install path.** Distribution packages that include
super metrics, views, dashboards, alerts, symptoms, reports are
reliable. UI-session uninstall has the admin-account constraint
(server-side issue, not ours) and is documented loudly.

**Reverse extraction.** Pulling a live dashboard out of an Ops
instance and turning it into factory YAML works (`/extract` skill).

### What's alpha

**Management pack authoring.** New capability — three new agents
(api-cartographer, mp-designer, mp-author) and `vcfops_managementpacks`
landed in the past two weeks. Wire format is large and partially
undocumented. Today's investigation (see
`mpb_synology_import_diff_2026_04_29.md`,
`mpb_object_binding_wire_format.md`,
`mpb_synology_pickup_2026_04_29.md`) closed three structural defects
and added two YAML grammars (`is_singleton`, explicit chain
declaration), but the substrate is still thin: only one design JSON
(Rubrik) had been mined for `objectBinding` patterns at the time the
renderer was authored. New references downloaded today (jcox-au's
Unifi + phpipam, vrealize.it's vSAN-policy) confirm two more wire
patterns we hadn't yet seen.

**Reference-pack catalog.** ~7 reference packs in `references/`
(Rubrik, Synology DSM, GitLab-Basic, Unifi, phpIPAM, vSAN-policy, plus
3 non-MPB VMware adapter packs). They're mined reactively, one shape
at a time, when bugs hit. No structured catalog, no normalized index,
no diffing infrastructure.

**Pre-flight and regression detection.** No automated path from
"YAML on disk" to "verified working on a live instance and rolled
back." Today's loop is: render → drag into UI → guess. Same on the
non-MP side: validate → sync → check the dashboard manually.

### What's missing entirely

**An mp-designer that actually does the heavy lifting.** Today
`mp-designer` is an aspirational agent definition. In practice, design
artifacts are hand-authored (`designs/synology-mp-v1.md` etc.). A real
mp-designer would consume structured api-cartographer output, ask user
the genuinely-ambiguous questions only (1–3 questions, not 30), and
produce a design YAML directly.

**Structured api-cartographer output.** Today api-cartographer
produces narrative API maps. To feed mp-designer, it needs to produce
structured data: endpoints with paging style + auth + response schema,
candidate object kinds with confidence scores, candidate relationships
with field-match heuristics.

**Pre-flight pipeline for any content.** End-to-end "render →
sandbox-deploy → verify → rollback" CLI command. Currently every
class of bug we discover lived in the gap between "validate passes" and
"actually works on live Ops."

**Fixture-snapshot regression coverage.** No renderer in the
`vcfops_*` packages has snapshot tests against captured working
examples. Renderer changes can silently drift from the wire format
(today's `objectBinding` bug is the cleanest example).

**Authoring-friction-surfacing protocol.** mp-author hit
`world_count == 1` today and worked around it by adding a phantom
World stub. The friction surfaced only when Scott noticed the
structurally-defective output. Authoring agents should report
"I worked around constraint X" as a hard signal, not paper over it.

---

## Path from here

### Phase 1 — Synology MP (TERMINATED as MPB target, 2026-04-29)

**Status: cannot ship as MPB** due to data-model mismatch between
Synology DSM API and MPB chained-collection wire format. See
`mpb_synology_pickup_2026_04_29.md` §"End-of-session verdict" for
the empirical evidence and three-phase failure mode analysis.

Synology MP **moved to Phase 2.5 (Operations SDK queue).** The SDK's
imperative model matches the API's URL-path-identity pattern; MPB's
declarative wire format does not.

**Substrate cost of this discovery:** ~4 hours of agent time across
api-explorer, tooling, mp-author. **Substrate gain:** seven durable
items captured in `mpb_synology_pickup_2026_04_29.md`
§"Substrate gains today" — including the three-phase MPB validation
model, the URL-path-identity pattern recognition rule, three new
reference packs ingested, and the `is_singleton`/chain grammars.

### Phase 1.5 — Unifi MP from scratch ("cheating with reference")

Author a Unifi management pack through the factory pipeline
(api-cartographer → mp-designer → mp-author → render → install) using
the **jcox-au design JSON as a comparison anchor, not as input**. The
factory does its own discovery against the live Unifi controller API;
the reference design is consulted only at the end to diff our shape
against a known-working one.

**Why this phase exists.** Scott has wanted a factory-built Unifi
pack since before jcox-au's work surfaced. Doing it now serves three
purposes:

1. **Calibration.** Test the tooling against a target where the
   correct answer is on disk. If the factory's output diverges
   meaningfully from jcox-au's, that's a substrate gap.
2. **Substrate stress-test.** Synology drove the recent tooling work;
   the renderer was effectively designed against it. Unifi exposes
   which gaps were Synology-specific and which are general.
3. **Practical value.** Scott gets a Unifi pack for personal use.

**Discipline:** the comparison-with-reference is post-render only.
api-cartographer should map the Unifi API from scratch; mp-designer
should propose object hierarchy without consulting jcox-au's design;
mp-author should write YAML based on the design, not the reference.
Only at the diff stage do we look at jcox-au's choices and decide
whether ours matches, diverges meaningfully, or is wrong.

If the factory's output is structurally similar to jcox-au's:
substrate is close to beta. If it diverges substantially: the
divergences are the substrate gaps Phase 3 should prioritize.

### Phase 2 — clean-slate MPB MP (no reference)

Author an MPB-format MP for a target where we have **no reference
design** — no diff-against-reference safety net. Same factory pipeline
as Phase 1.5 (api-cartographer → mp-designer → mp-author → render →
preflight → install), but the discovery and validation are real:
nothing to compare against, nothing to fall back on.

Candidate target TBD; Scott to specify. Likely candidates: a public
REST API with modest scope (5–8 object kinds), modern authentication,
accessible test environment. Should be different enough from Synology
and Unifi that overlapping patterns aren't doing the heavy lifting.

This phase is the real proof: framework produces a correct, working
MP for a target it's never seen, without a known-good comparison
anchor. Surfaces which substrate gaps still bite when there's no
escape hatch.

### Phase 2.5 — Operations SDK MP (different output target)

> "Then do a quick and easy operations SDK MP run."

Build an MP using the VMware Aria Operations Python Adapter SDK — a
**different code path** from MPB. The factory's current output target
is the MPB design JSON envelope; the Operations SDK's output is a
Python-based adapter package with a different runtime and packaging
shape.

**Scope question for Scott.** Two flavors of this phase, your call:

- **(a) Side experiment** — build an SDK-format MP outside the factory
  (manually or with one-off scripts) to learn the wire format, then
  decide whether to add SDK emission to the factory in Phase 3. Lower
  effort, no factory change, gets you the pack you want.
- **(b) Factory extension** — add SDK output emission as a renderer
  variant in `vcfops_managementpacks` (alongside the existing MPB
  exchange-format render). Larger scope, makes "SDK MP" a first-class
  factory capability for future targets. This becomes a Phase 3
  substrate item, not Phase 2.5.

If you mean (a), keeping it as Phase 2.5 makes sense — small target,
quick win, framework not affected. If you mean (b), it gets folded
into Phase 3 substrate work and Phase 2.5 collapses.

Defaulting to (a) until you confirm.

### Phase 3 — substrate work (closes the alpha→beta gap)

In rough priority order:

#### 3a. Pre-flight pipeline (highest leverage)

`vcfops <type> preflight foo.yaml --profile sandbox`

For dashboards / super metrics / views / symptoms / alerts / reports:
- render → sync to sandbox profile
- run validate-on-instance checks (does the SM compute? does the alert
  trigger? does the dashboard render?)
- automated rollback (delete just-synced content)
- exit 0 if green; actionable error if not

For management packs:
- render-export → POST `/designs/import` → poll `/status` for VALID →
  trigger source-test → POST `/install` → wait for "Applied" → verify
  resources discovered → uninstall + DELETE design

This single capability catches every bug class today's session
generated. Estimated 3–5 sessions of tooling work.

Probably the highest single return-on-investment item. Required for
the vcf-cf "I just verified this works" output line.

#### 3b. Fixture-snapshot regression tests

Every `render*.py` in `vcfops_*` gets a snapshot test against captured
working designs. Drift fails CI. Lock in:
- Each existing reference pack (Rubrik, Synology, Unifi, phpIPAM,
  vSAN-policy, GitLab) → render an equivalent factory YAML, snapshot
  the rendered exchange JSON
- Each chain pattern (no chain, single chain, multiple chains, chain
  with response echo, chain without response echo)
- Each objectBinding pattern (null, attribute-stitch, parameter-stitch
  with ARIA_OPS_METRIC)
- Each is_world/is_singleton/list combination
- Each non-MP renderer (dashboard widget types, view column transforms,
  symptom threshold types, etc.)

Cheap to add now while patterns are stable. Expensive after the next
renderer rewrite.

#### 3c. Reference-pack parsed catalog

Turn `references/` from "dead JSON files" into "queryable knowledge
base." Build a tool (`vcfops_managementpacks/catalog.py` maybe) that:
- Scans every MPB design JSON in `references/`
- Normalizes envelope shape (some have `type` at top-level, some don't)
- Indexes by axis: auth type, paging style, chain shape,
  objectBinding pattern, world/singleton/list ratio, identifier
  strategy, stitching presence
- Exposes a CLI: `vcfops_managementpacks reference-search
  --chain-with-no-echo` returns the references that match
- mp-designer and mp-author consult this rather than developer memory

Output: a catalog index file in `context/` plus a CLI for ad-hoc
queries.

#### 3d. Packaging-time dependency audit

Per memory `feedback_packaging_dependency_audit.md` — bundles refuse
to build if metric refs are unresolved or disabled, if symptom names
don't exist, if dashboard widgets reference missing views, etc.
Today this manifests as "ships broken, debug at install." Should be a
build-time error.

#### 3e. Multi-policy enable + recommendations-via-REST

Per CLAUDE.md known limitations #2 and #3. Real-world ops instances
run multiple policies; bundles need to enable on a configurable target
policy. And alerts-via-REST need to ship with their recommendations
intact.

#### 3f. mp-designer for real

Once the substrate (reference catalog, pre-flight, snapshot tests) is
denser, rebuild mp-designer to be a sharp instrument:
- Input: structured api-cartographer output + 1–3 user inputs
  (device-identity field, cardinality of root entity, relationship
  hierarchy preference)
- Output: design YAML, ready for mp-author
- Behavior: consults reference catalog for analogous patterns,
  surfaces ambiguity to user before guessing, never invents metrics
  that aren't in the API map

#### 3g. Authoring-friction-surfacing protocol

Tighten the prompts on every authoring agent so working around the
schema is a hard stop. The signal: "I needed to add a stub kind to
satisfy the loader's `world_count == 1` rule" should fire the gap
report, not a workaround.

#### 3h. Widget renderer expansion

PropertyList first (~47 uses on survey instance). Then the next 5–10
by frequency. Each is bounded work — wire format is exportable from
any existing dashboard with that widget.

#### 3i. UI-rendering verification

For dashboards, screenshot-comparison or DOM-snapshot tests against a
sandbox profile. Catches the "Super Metric|" prefix-class of bugs that
wire-format validation can't see. Expensive infrastructure but high
catch rate. Defer until Phase 3i; not worth building before #3a–c
are in.

### Phase 4 — vcf-cf shape

Once the substrate is dense enough, the user-facing shape is:

```
$ vcfops new-mp --api-creds creds.yaml --api-spec openapi.json
[1/6] api-cartographer: 47 endpoints mapped, 12 paged, auth=cookie_session
[2/6] mp-designer: proposing 8 object kinds, 6 relationships, 4 chains
                   3 ambiguous decisions need your input — y/n questions only
[3/6] mp-author: writing managementpacks/<name>.yaml ... done
[4/6] render: 8 objects, 47 requests, 6 relationships emitted
[5/6] preflight on devel: import OK, source-test OK, install OK,
                          first collection OK (62 objects discovered)
[6/6] cleanup: design+adapter removed from devel
SHIP: managementpacks/<name>.yaml + designs/<name>.md + tmp/<name>.json
```

The same pattern works for non-MP content:

```
$ vcfops new-dashboard --intent "VKS consumption rollup" --instance prod
... (interview, render, preflight, ship)
```

Both shapes require Phase 3a (preflight) and 3b (snapshot tests) at
minimum. The MP shape additionally needs 3c (catalog) and 3f (real
mp-designer).

---

## Acknowledged limitations of this plan

**Time horizon.** Phase 3 is multi-month work, not multi-session.
Each item is multi-session. Realistic pace is one Tier-1 item per
month at current cadence.

**Substrate-driven discovery.** Some gaps in this list will turn
out to be wrong-priority once we start filling them. Reference-pack
catalog (3c) might be more important than fixture tests (3b) if the
catalog reveals patterns the snapshot fixtures would miss. Adjust as
evidence comes in.

**No new agents in Phase 3.** Tempting to add a "code-skeptic for
designs" or "schema-truth agent" — defer until existing agents have
been sharpened against the new substrate. New agents on top of weak
substrate is how we got into this position.

**The vision skips infrastructure work that's real.** "Give me API
creds and an API spec" implies the framework can ingest OpenAPI specs
(api-cartographer can do this only partially today). Real-world APIs
without OpenAPI specs (Synology's case) need probing — also partially
supported. Phase 4 needs Phase 3 plus extension to api-cartographer,
not flagged above.

---

## References

- `context/mpb_synology_pickup_2026_04_29.md` — workstream that
  exposed these gaps
- `context/mpb_synology_import_diff_2026_04_29.md` — defect analysis
- `context/mpb_object_binding_wire_format.md` — empirical wire-format
  investigation
- `context/mp_chain_authoring.md` — chain grammar (one of two new
  YAML grammars added today)
- `references/jcox-au_vmware/` — Unifi + phpIPAM (downloaded today,
  not yet folded into wire-format docs)
- `references/vrealize_it_vsan_default_policy/` — vSAN policy stitching
  pattern (downloaded today, not yet folded)
