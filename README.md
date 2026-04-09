# VCF Content Factory

**I'm here to take your plain-text descriptions, PowerCLI scripts, or
napkin sketches and turn them into real VCF Operations content.**

Super metrics, list views, dashboards, custom groups — you describe
what you want in English, I write the YAML, validate it, install it
on your VCF Operations instance, and enable it in policy. You stay
focused on the question you're trying to answer; I handle the DSL
quirks, the undocumented wire formats, and the "why does this render
as a blank column" landmines.

## What this is

A framework for authoring and installing VCF Operations content as
version-controlled YAML, driven by an agentic loop built around
Claude Code. You describe a need; a roster of specialized subagents
does the recon, authoring, and installation work, grounded in the
VCF Operations documentation and a library of reference content from
the community.

The value is not "one super metric." The value is:

- **You don't need to know the DSL.** Describe the filter, the
  aggregation, the rollup levels — I figure out the formula.
- **You don't need to hand-build dashboards.** Describe the report
  shape, I wire the view and dashboard together.
- **You don't need to hunt through undocumented wire formats.** The
  framework knows the quirks — correct `where` clause syntax,
  super-metric-column namespace prefixes, dashboard folder placement,
  `resourceKindId` stable prefixes — and applies them automatically.
- **Your content is version-controlled and portable.** Every super
  metric, view, and dashboard has a stable UUID stored in YAML, so
  the same bundle installs cleanly on dev, test, and prod instances
  with every cross-reference intact.
- **Nothing is hidden.** Every YAML is plain text. Every install is
  a visible CLI call. Every piece of recon leaves a trail. If you
  want to take over from the framework and hand-edit the output, it's
  all there.

## What this is not

- A UI. This is a CLI and an authoring loop.
- A replacement for understanding VCF Operations. You still need to
  know what you want to measure and roughly where it lives.
- A generic "ask the AI" wrapper. The framework refuses to fabricate
  metric keys, API endpoints, or DSL functions. When it doesn't know
  something, it runs reconnaissance against the live instance or
  asks you.

## What I can produce today

| Content type | Status |
|---|---|
| Super metrics (with per-level rollups, `where` clauses, cross-metric references) | Yes |
| Dynamic custom groups (with property + relationship rules) | Yes |
| List views (with built-in metrics and super metric columns) | Yes |
| Dashboards (with `View` and `ResourceList` widgets, in a named folder, shared by default) | Yes |
| Alert definitions | Not yet |
| Report definitions | Not yet |

All content is installed via the Ops content-import path, so UUIDs
are preserved — cross-references between super metrics, views, and
dashboards survive cross-instance installs without any manual
re-stitching.

## Getting started

1. Put your VCF Operations credentials in a `.env` file at the repo
   root:

   ```bash
   VCFOPS_HOST=vcfops.example.com
   VCFOPS_USER=admin
   VCFOPS_PASSWORD=...
   VCFOPS_AUTH_SOURCE=Local        # optional
   VCFOPS_VERIFY_SSL=false         # optional, for self-signed
   ```

2. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Tell the framework what you want. Open Claude Code in this
   directory and describe the content you need. Examples:

   > "I want a super metric that sums provisioned vCPUs for all
   > powered-on VMs in each cluster, excluding vCLS VMs."

   > "Give me a dashboard that shows VKS core consumption per
   > vCenter, mirroring this PowerCLI script: [paste]"

   > "Create a custom group for VMs on NFS datastores so I can
   > scope alerts to them."

4. Approve the YAML the framework shows you, and it installs +
   enables the content. Everything authored lands in the
   `VCF Content Factory` folder in the Ops dashboards sidebar,
   prefixed `[VCF Content Factory]` for easy identification.

## Where to go next

- **[ADMIN.md](ADMIN.md)** — detailed administrator guide. Read this
  before clicking around the GUI. It walks through every CLI
  command, the authoring workflow, how the subagents cooperate, and
  how to recover when something goes sideways.
- **[CLAUDE.md](CLAUDE.md)** — the framework's internal rules that
  the agents follow. Useful if you want to understand the guardrails
  or extend the framework yourself.
- **[context/](context/)** — topical background files the agents
  read on demand: the DSL reference, wire format notes, UUID
  contract, API surface map, reference-source allowlist. These are
  the authoritative answers the framework leans on when deciding
  what's possible.

## Where this came from

Built on top of Anthropic's [Claude Code](https://claude.com/claude-code)
with a roster of specialized subagents, each with a narrow
responsibility (reconnaissance, super metric authoring, dashboard
authoring, etc.). The agents cite VCF Operations' own documentation,
the OpenAPI specs, and an allowlisted library of reference content
from the community — nothing is invented from thin air.

The framework's author maintains
[sentania/AriaOperationsContent](https://github.com/sentania/AriaOperationsContent)
and uses it as the proving ground for new VCF Operations content
patterns; several of the design decisions in this framework (UUID
stability, content-zip install, `[VCF Content Factory]` naming
convention) come straight from real-world pain fixing broken bundles
in that repo.

## License

MIT. See [LICENSE](LICENSE).
