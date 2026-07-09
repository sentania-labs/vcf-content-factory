# Getting Started

This is the doc that gets you talking to the framework in 10 minutes
and producing real content shortly after. If [README.md](README.md)
sold you on the "why," this is the "how it actually feels."

You will not be writing YAML. You will be having a conversation. The
framework writes the YAML for you.

---

## Setup (5 minutes)

### 1. Clone the repo and install Python deps

```bash
git clone https://github.com/sentania-labs/vcf-content-factory.git
cd vcf-content-factory
pip install -r requirements.txt
```

### 2. Put your VCF Operations credentials in `.env`

```bash
cp .env.example .env
chmod 600 .env
```

Edit `.env`. The minimum that needs to work is one profile (any of
`prod`, `qa`, or `devel`):

```bash
export VCFOPS_DEVEL_HOST=vcfops-devel.example.com
export VCFOPS_DEVEL_USER=admin
export VCFOPS_DEVEL_PASSWORD='your-password'
export VCFOPS_DEVEL_AUTH_SOURCE=Local
export VCFOPS_DEVEL_VERIFY_SSL=false

export VCFOPS_PROFILE=devel
```

Three profiles exist by convention — `prod` (read-only recon),
`qa` (admin for round-trips), `devel` (destructive playground).
Validate and list commands default to `prod`; sync, enable, and
delete default to `devel`. Override on any command with
`--profile <name>`.

Federated SSO sources (VIDB, VIDM) aren't supported on the install
path — create a Local service account if those are the only
options available.

### 3. Populate reference content (optional but recommended)

The framework grep-checks community content before authoring so it
doesn't reinvent patterns that exist. Skip this and the framework
just won't have those references to consult.

```bash
./scripts/bootstrap_references.sh
```

### 4. Open Claude Code in this directory

```bash
claude
```

You're ready.

---

## Your first conversation (5 minutes)

There's no special syntax. You just say what you want. The framework
clarifies what it needs to clarify and proposes content where it
already has enough to propose.

A simple opener — try this verbatim if you've got a VCF Ops instance
with some VMs on it:

> Show me a super metric for total provisioned vCPUs across all
> powered-on VMs in a cluster.

What you'll see:

1. The framework checks the live instance and the repo for existing
   super metrics that already cover this.
2. It looks up the metric keys it needs (`config|hardware|numCpu`,
   `summary|runtime|powerState`) and confirms they exist.
3. It proposes a YAML — including the formula, the resource kind
   assignment, and the rollup definition.
4. It shows you the YAML and asks: install on `devel`?
5. You say yes. It validates, syncs, enables the super metric on the
   Default Policy, and tells you where to find it in the Ops UI.

Whole thing is ~2 minutes if everything matches.

### How the framework asks for help

When the framework is missing information it can't infer, it asks
— but it does so with a proposal already on the table, not a blank
form:

> "I see you want firmware reporting for your servers. The Redfish
> `UpdateService/FirmwareInventory` endpoint exposes Version,
> SoftwareId, ReleaseDate, Health, and Updateable per component.
> Should I model each firmware component as its own resource (alertable
> per-component, more graph nodes), or as a property on the parent
> server (compact, harder to alert per-component)? Default for
> Dell-shape adapters: per-resource."

You answer with a sentence. The framework moves on.

---

## Example prompts by track

Use these verbatim to get a feel for each track, then bend them to
your own needs.

### Super metrics

> "Sum provisioned memory across all powered-on VMs per cluster."

> "Average CPU ready percent for production VMs (production = those
> in folders whose name contains 'PROD')."

> "Datastore free space as a percentage, with rollups at host and
> cluster level."

Expected behavior: framework probes existing super metrics, then
either adapts one or writes a new formula. The DSL is hidden from
you unless you want to see it (the YAML is there to read).

### Custom groups

> "Production VMs — those in folders whose name contains 'PROD' or
> are tagged `env=prod`."

> "Linux VMs with more than 8 GB of memory."

> "Datastores backed by NFS."

Expected behavior: framework infers a property-rule expression,
checks any tag/property name against the live instance, and writes
the rule. You don't need to know the rule grammar.

### List views

> "Top 50 VMs by CPU ready percent in the last 24 hours."

> "All hosts grouped by vendor, with model and serial number columns."

> "Datastores sorted by free-percent ascending — the smallest left."

Expected behavior: framework figures out the subject resource kind,
the columns (mixing built-ins and super metrics), the sort, and the
limit. You'll be asked which super metrics to wire in if there are
multiple candidates.

### Dashboards

> "VM right-sizing review — top oversized and undersized VMs side
> by side, with the cluster they live in."

> "Storage capacity for the CFO — datastore free, growth trend,
> projected exhaustion date."

> "K8s ops view — pods, nodes, recent restarts, namespace tags."

Expected behavior: framework asks what views/SMs exist that it can
embed, proposes a widget layout, and authors the dashboard. Lands
in the `VCF Content Factory` folder under Dashboards.

### Symptoms + alerts + recommendations

> "Alert me when any datastore is below 10% free and trending down
> over 6 hours."

> "Alert when an ESXi host has been in maintenance mode for more
> than 24 hours."

> "Alert on cluster overcommitment risk and link the recommendation
> to our 'rebalance vMotion' runbook."

Expected behavior: framework writes the symptom set, the alert
definition, and the (linked, reusable) recommendation in one pass.
Severity tiers default to sensible values; you can override.

### Reports

> "Monthly cluster capacity report — cover page, table of contents,
> per-cluster utilization chart, top capacity offenders."

> "Storage health quarterly — embed the storage dashboard plus a
> view of all datastores below 20% free."

Expected behavior: framework asks for the audience and the cadence,
then assembles sections from existing views and dashboards.

### Management packs

> "Build me a management pack for Dell PowerEdge servers via Redfish."

> "I have a REST API for [vendor product]. Here's the OpenAPI spec.
> Build a management pack."

> "Monitor my Synology NAS — here are the API docs."

Expected behavior: framework recognizes well-known API shapes
(Redfish, vSphere REST, K8s, Synology DSM, etc.), proposes an
object model, and asks the small set of clarifying questions
that actually matter ("Make this Dell-specific or generic Redfish?"
"Stitch to vSphere HostSystem via the BIOS UUID property?"). The
output is a `.pak` file plus the YAML it came from. Tier 1 (MPB)
for HTTP REST adapters; Tier 2 (native Java SDK) for cases MPB
can't express (complex auth, non-HTTP protocols, per-instance
attribute groups).

### Extracting + adapting community content

You don't have to start from scratch. The framework can extract
content from a dashboard, view, or super-metric export and reshape
it into the factory's YAML:

> "Pull the 'NUMA Optimization' super metric from
> johnddias/vrops-super-metric-numa-optimize and adapt it for my
> instance."

The framework walks the dependencies, asks for any deltas, and
produces a clean YAML you own.

---

## What happens when you say "yes, install it"

```
You: "install it on devel"

Framework: → validates the YAML
           → renders the wire format (super metric ID prefixing,
             content-zip packaging, etc.)
           → syncs to devel via the Suite API
           → enables on the Default Policy if appropriate
           → verifies the resource shows up
           → reports back with the UI link

You: <click link, see the content>
```

You can also build a **distribution zip** for any admin to install
on any instance without the framework:

```
You: "package the VKS Core Consumption bundle as a distribution zip"
Framework: → bundles every dependency (SMs + views + dashboard)
           → writes a self-contained installer (Python + PowerShell)
           → produces dist/[VCF Content Factory] VKS Core Consumption.zip
```

Hand that to a colleague. They run `python3 install.py`, answer the
prompts, done.

---

## When something goes wrong

The framework leaves a trail. If an install fails:

- Look at the error the framework printed. It'll usually point at the
  exact YAML field.
- The validation step runs before any wire-format work, so most
  errors come up early.
- For installer issues, see
  [knowledge/lessons/pak-install-reliability.md](knowledge/lessons/pak-install-reliability.md)
  and [knowledge/context/api-surface/install_and_enable.md](knowledge/context/api-surface/install_and_enable.md).
- If the framework hits something it doesn't understand, it will say
  so explicitly and emit a **TOOLSET GAP** report — never silently
  work around. You decide whether to defer, spawn an investigator
  agent, or shrink the request.

---

## A note on the conversation style

You'll notice the framework doesn't make you specify everything. It
infers what it can, asks about the rest, and only interviews on
ambiguities that actually matter. Two examples:

**It will not ask:** "Should this metric have a key derived from the
label?" (Answer is always yes; it's handled.)

**It will ask:** "I see two existing super metrics that compute 'VM
CPU ready' — one rolls up at the cluster level, one doesn't. Are you
asking for the cluster version, or do you want a new formula?"
(Genuine ambiguity that affects the output.)

This means the conversation feels like working with a colleague who
already knows the framework, not like filling out a form.

---

## Next steps

- Skim [vcf_ops_concepts.md](knowledge/vcf_ops_concepts.md) for a
  reference on what each VCF Ops content type actually is — useful
  if "what's a super metric vs a custom group?" is a real question
  for you.
- Read [HOW_IT_WORKS.md](knowledge/HOW_IT_WORKS.md) if you want to understand
  the orchestrator + agents architecture before extending it.
- Read [CLAUDE.md](CLAUDE.md) if you're forking or contributing — it's
  the rules the orchestrator follows.
- Look at the `bundles/` directory for examples of factory-built
  content you can install today.
