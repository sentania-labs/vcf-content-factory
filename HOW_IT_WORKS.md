# How It Works

This is the deeper architectural dive — for anyone considering
forking, extending, or just curious how the agent loop is set up.

If you're trying to use the framework, you don't need this.
[Getting_Started.md](Getting_Started.md) is what you want.

If you're trying to *understand* the framework — or build something
similar for a different platform — read on.

---

## The shape of the problem

VCF Operations content (super metrics, dashboards, views, etc.) lives
in a half-dozen overlapping wire formats with cross-references via
both names and UUIDs. Authoring it correctly requires knowing:

- The DSL syntax for each content type (super metric formula DSL,
  custom group rule grammar, symptom condition grammar).
- The wire format for each content type (XML, JSON, content-zip
  envelope) — including the parts that aren't documented.
- The cross-reference contract (super metrics in views resolve to
  `sm_<uuid>` strings; views in dashboards resolve to view UUIDs;
  symptoms in alerts resolve to names then to server-assigned IDs).
- The validation rules (factory-emits-derived-key trap;
  `[VCF Content Factory]` prefix; `instanced="true"` is Tier 2 only;
  ARIA_OPS stitching gotchas).
- The live instance's state (existing content, enabled super
  metrics, available adapter kinds).

A naive LLM with no scaffolding gets the first two roughly right
and the rest wrong. The result is plausible-looking content that
doesn't validate, doesn't install, or installs but doesn't render.

The framework is the scaffolding that turns "ask the LLM" into "drive
a disciplined authoring loop."

---

## The shape of the solution

```
                ┌──────────────────────────────┐
                │     User (in conversation)   │
                └──────────────┬───────────────┘
                               │
                ┌──────────────▼───────────────┐
                │       Orchestrator (you)     │
                │  clarify · delegate · broker │
                │   validate · install · report│
                └─┬────────┬────────┬────────┬─┘
                  │        │        │        │
        ┌─────────▼─┐ ┌────▼────┐ ┌─▼──────┐ ┌▼────────┐
        │ ops-recon │ │authors  │ │tooling │ │installer│
        │           │ │(narrow) │ │vcfops_*│ │packager │
        │read-only  │ │one each │ │python  │ │qa-tester│
        │live Ops   │ │content  │ │renderer│ │ship+test│
        └───────────┘ │type     │ └────────┘ └─────────┘
                      └─────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  context/  files│
                   │  shared knowledge
                   │  rules · format │
                   │  · api maps · etc
                   └─────────────────┘
```

**One orchestrator, many specialized agents.** The orchestrator is
Claude Code in its default mode, holding the conversation with the
user and the bird's-eye view of the work. Agents are subprocesses
under `.claude/agents/` with narrow responsibilities and hard rules
about what they will and won't do.

Each agent has:

- A specific lane (one content type, or recon, or research, or build)
- An authoritative prompt file under `.claude/agents/`
- A "writes to" boundary (the orchestrator does not author YAML; it
  delegates to the agent whose lane that file is in)
- A TOOLSET GAP escape hatch — if the agent hits something it can't
  do, it reports the gap and stops rather than working around

The full roster and lane discipline is in [CLAUDE.md](CLAUDE.md).

---

## Why this shape and not just "smart agent"

Four design pressures push toward narrow agents instead of one big
generalist:

1. **Context window economics.** A single agent that authors super
   metrics and dashboards and management packs and runs installs and
   talks to the user accumulates everything it sees. Narrow agents
   read only the files they need, return only their result, and let
   the orchestrator keep the big picture without holding the details.

2. **Lane discipline.** "Author the super metric" and "validate the
   describe.xml" are different jobs with different failure modes.
   Mixing them in one prompt produces an agent that's mediocre at
   both. Splitting them produces agents that are deeply correct in
   their lanes.

3. **TOOLSET GAP as first-class outcome.** When the renderer doesn't
   support a feature the user needs, the right answer is "stop and
   report the gap so we can fix the framework" — not "improvise and
   ship something that almost works." Narrow agents make the gap
   visible. A generalist agent has too much room to silently route
   around the problem.

4. **Reviewability.** Each agent's behavior is in one file. When
   something goes wrong, you can read the prompt that produced the
   wrong behavior and fix it. The fix becomes part of the framework.

---

## The recon-before-author discipline

Every authoring task starts with `ops-recon`. The brief is the user's
plain-language goal plus the specific questions you want answered.

Recon checks, in order:

1. **Built-in metrics.** Does VCF Ops already collect this? No author
   needed.
2. **Existing instance content.** Does a super metric / view /
   dashboard already exist that satisfies the goal? Adapt it,
   don't author from scratch.
3. **Existing repo YAML.** Does the factory already author something
   close? Same.
4. **Reference repos.** Has someone in the community already solved
   this? `references/` carries an allowlist of grepped-but-not-trusted
   source material (see `context/reference_sources.md`).

This step is the framework's first line of defense against
reinventing things, **and** the framework's mechanism for grounding
its output in real instance state. The "infer don't ask" UX commitment
in [Getting_Started.md](Getting_Started.md) is mostly recon plus a
willingness to propose.

---

## The codification loop

Auto-memory is disabled by design (CLAUDE.md Hard Rule 8). The
framework does not silently remember corrections across sessions.
Instead, every hard-won lesson goes somewhere reviewable:

- `context/` — topical knowledge files (wire formats, API surfaces,
  patterns, anti-patterns, known limitations)
- `.claude/agents/<agent>.md` — behavior changes for a specific
  agent's lane
- `CLAUDE.md` — orchestrator-level rules
- New skills / new agents — when the lesson is structurally a new
  capability

The process is documented in
[context/rules_codification.md](context/rules_codification.md). The
practical rule of thumb: when the user says "no, do it this way
instead," ask yourself which of the above files should remember
that.

This is also what makes the framework portable. Knowledge that lives
in a Claude session is gone tomorrow. Knowledge that lives in a YAML
or a context file is committable, reviewable, and survives forks.

---

## The "infer don't ask" UX commitment

Codified across all author agents (with per-agent details in their
prompts and shared discipline in
`context/rules_content_authoring.md`):

1. **Probe the existing state before asking the user.** Live
   instance + repo + references. If the answer is already there,
   use it; don't make the user repeat themselves.
2. **Look at the API / schema / data to propose a structure.**
   When the source is a REST API, look at its OpenAPI. When the
   source is an existing super metric, look at its formula.
   Propose with a default; ask for confirmation.
3. **Interview only on ambiguities that actually matter.**
   "Should this super metric use SUM or AVG aggregation?" matters
   to the user. "Should the on-wire metric key be derived from the
   label?" doesn't.
4. **Default-propose stitching to existing kinds.** Hardware-inventory
   MPs almost always want to stitch to vSphere HostSystem via a
   serial/UUID property; the framework proposes that rather than
   asking the user to remember it.

The failure mode this fights against is "framework asks user 47
questions before producing anything." A user who has to specify
every detail is not getting value from automation. A framework
that infers, proposes, and asks for confirmation on the few real
ambiguities is.

---

## Cross-reference contracts

Content references content. Each content type uses a specific
identification scheme that the framework holds invariant:

| From → To | YAML carries | Resolves to (on the wire) |
|---|---|---|
| Super metric formula → another SM | `@supermetric:"<name>"` | `sm_<uuid>` |
| View column → super metric | `supermetric:"<name>"` in attribute block | `sm_<uuid>` |
| Dashboard widget → view | `view: "<name>"` | view UUID |
| Report section → view / dashboard | `view:` / `dashboard:` | UUID |
| Alert → symptom | `name: "<name>"` in symptom set | symptom ID (server-assigned at sync) |
| Alert → recommendation | `name: "<name>"` + `priority` | recommendation ID |
| Custom group rule → property/metric | property/metric key | literal key on wire |

UUID-identified types (super metrics, views, dashboards, reports)
have stable UUIDs in the YAML `id` field, generated on first
validate and never touched after. That's the trick that makes the
content portable across instances — the UUID travels with the YAML.

Name-identified types (custom groups, symptoms, alerts,
recommendations) get server-assigned IDs at install time; cross
references resolve by name lookup. Renaming any of those breaks
references; the framework warns on rename intent.

Full grammar in
[context/uuids_and_cross_references.md](context/uuids_and_cross_references.md).

---

## Tier 1 vs Tier 2 (management packs)

Two paths for management pack authoring:

**Tier 1 — Management Pack Builder (MPB):** REST-API-sourced adapters
expressed in YAML, rendered to MPB's design JSON, compiled by the
server-side MPB compiler into a `.pak`. Fast to author, runs in MPB's
shared classloader, no Java required from the user. Limitations:
single host per adapter instance, no per-instance attribute groups,
HTTP only.

**Tier 2 — Native Java SDK adapter:** Custom Java code extending
`UnlicensedAdapter`, packaged as a `.pak` with the
`vcfcf-adapter-base.jar` framework runtime. The framework adapter
provides typed auth strategies, retry policies, HTTP client, metric
push helpers, describe.xml builder. Per-adapter code is small
(~50–150 lines for simple cases). Handles cases MPB can't: complex
data-model stitching, advanced auth (OAuth2 refresh, Kerberos),
non-HTTP protocols, per-instance attribute groups, dynamic time
parameters.

The decision framework is in
[context/tier_decision_framework.md](context/tier_decision_framework.md).
The default is Tier 1 unless a specific trigger forces Tier 2.

Tier 2 Phase 1 is complete (framework JAR + builder + hello-world
adapter); Synology and Dell PowerEdge are queued as the first real
Tier 2 adapters.

---

## What lives where in the repo

```
.claude/agents/                  agent prompts — authoritative behavior per agent
.claude/skills/                  named skill prompts (e.g. /publish, /extract)
.claude/settings.json            harness config (autoMemoryEnabled: false)

content/managementpacks/         MP YAML — Tier 1 authoring source
content/sdk-adapters/            Tier 2 Java adapter projects
supermetrics/  views/  dashboards/  customgroups/  symptoms/  alerts/
recommendations/  reports/       per-content-type YAML

vcfops_*/                        Python packages — renderer, loader, builder,
                                 installer. Only the `tooling` agent edits.

context/                         shared knowledge files (wire formats, rules,
                                 API maps, codified lessons). Agents read on
                                 demand.

designs/                         design artifacts from `mp-designer` and other
                                 ad-hoc planning docs.

references/                      cloned community repos (allowlisted in
                                 context/reference_sources.md). Gitignored —
                                 each user clones their own.

bundles/                         release-grade bundle manifests + dist outputs.
dist/                            built `.pak` files (ephemeral, gitignored).
tmp/                             session scratch space (gitignored).

CLAUDE.md                        orchestrator rules — hard rules + delegation
                                 protocol + workflow patterns.

README.md  Getting_Started.md    user-facing docs.
HOW_IT_WORKS.md                  this doc.
docs/vcf_ops_concepts.md         VCF Ops content-type reference.
```

Three things are deliberately small:

- **The orchestrator's lane.** It clarifies, delegates, validates,
  installs, and reports. It does not author YAML, edit Python, run
  recon, or post-process wire formats. When you catch yourself doing
  one of those inline, the rule is: stop and delegate.
- **Cross-agent communication.** Agents pass filenames, not file
  contents. Each agent reads what it needs from disk. This is how
  the architecture stays affordable.
- **Auto-memory.** Off. Knowledge lives in the repo.

---

## Forking guidance

If you're considering building something similar for a different
platform (Splunk, Datadog, ServiceNow, etc.), the elements that
transfer:

1. **The orchestrator + narrow agents pattern.** Lane discipline,
   filenames-not-contents, TOOLSET GAP as first-class outcome.
2. **Recon-before-author.** Every platform has live state worth
   probing before authoring.
3. **Codification loop.** Auto-memory off, knowledge in the repo,
   "where does this lesson belong" as a habit.
4. **Hard rules as guardrails.** Don't fabricate keys/endpoints/
   functions. Validate before install. Use names + UUIDs that
   survive cross-instance migration.
5. **The "infer don't ask" UX commitment.** Almost all the framework's
   value compresses into "the framework knows what it needs to know
   so the user doesn't have to."

Elements that are specific to this codebase (and would be different
in your fork):

- The content type list and their cross-reference grammar — your
  platform will have different ones.
- The Tier 1 / Tier 2 decision — only relevant if your platform also
  has a "fast declarative path" vs "full code path" split. Most
  don't.
- The specific wire formats and DSL quirks. Your platform has its
  own.

The CLAUDE.md hard rules in this repo are a reasonable starting
template for your own. The recon-before-author discipline is the
single most valuable transferable piece.

---

## Where the framework is going

- **Tier 2 Phase 2: Synology + Dell PowerEdge** as the first real
  native-SDK adapters. Forces the framework JAR to grow capabilities
  (instanced groups, multi-host iteration) under real use.
- **mp-designer interview improvements** — codified API-pattern
  recognition (Redfish, vSphere REST, K8s, etc.) so the framework
  proposes a model immediately for any well-known shape.
- **Cross-content codification** — apply the infer-don't-ask
  discipline uniformly across every author agent, not just
  mp-designer.
- **Extension surface** — currently the way to teach the framework
  about a new platform is to clone the repo and add agents. Long
  term, a clearer extension model.

See [ROADMAP.md](ROADMAP.md) for the current priorities.
