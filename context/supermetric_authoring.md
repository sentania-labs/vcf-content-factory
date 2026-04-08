# Super metric authoring

Step-by-step workflow for translating a user request into a valid
super metric YAML, plus the DSL rules the loader enforces.

## 1. Clarify the request

Confirm enough to write a correct formula:

- **What object type** the metric is assigned to (Cluster, Host, VM,
  Datastore, etc.). This determines `depth`.
- **Which underlying metric(s)** to read, and on which object type.
- **Aggregation**: average, max, min, sum, count, combine.
- **Filters** (e.g. powered-on VMs only) → become a `where` clause.
- **Units / display name**.

If the user gave a clear description ("average CPU of powered-on VMs
in a cluster"), do not over-clarify — proceed and show the result.

## 2. Author the YAML

Place under `supermetrics/<short_snake_case>.yaml`:

```yaml
id: <uuid4>                          # set on first validate, never touched again
name: <Scope> - <Human Name> (<unit>)
resource_kinds:
  - resource_kind_key: <ResourceKind>   # VirtualMachine, ClusterComputeResource, HostSystem, Datastore…
    adapter_kind_key: VMWARE            # almost always VMWARE for vSphere objects
description: >
  One or two sentences: what it measures, which resource kind it is
  assigned to, and any non-obvious depth or filtering choice.
formula: |
  <DSL expression>
```

`resource_kinds` is mandatory and wired straight through to the Suite
API's undocumented `resourceKinds` array. Field names
(`resource_kind_key`, `adapter_kind_key`) match the wire names
(`resourceKindKey`, `adapterKindKey`) exactly.

The list form is intentional: one super metric may be assigned to
multiple resource kinds. Most use a single entry; only use multiple
when the same formula genuinely applies to more than one kind.

If the user does not specify a resource kind, default to the resource
kind of interest — the object whose behavior the metric describes
(a "VM snapshot" metric defaults to `VirtualMachine`, a "cluster CPU"
metric to `ClusterComputeResource`). When in doubt, ask.

## 3. DSL rules (from `docs/vcf9/supermetrics.md`)

- **Looping functions**: `avg`, `sum`, `min`, `max`, `count`,
  `combine`. They take a single resource entry.
- **Single functions**: `abs`, `acos`, `asin`, `atan`, `ceil`, `cos`,
  `cosh`, `exp`, `floor`, `log`, `log10`, `pow`, `rand`, `sin`,
  `sinh`, `sqrt`, `tan`, `tanh`.
- **Operators**: `+ - * / %`, `== != < <= > >=`, `&& || !`, ternary
  `cond ? a : b`, parentheses, `[x, y, z]` arrays.
- **String operators** (only in a `where` clause): `equals`,
  `contains`, `startsWith`, `endsWith`, and their `!` negations.
- **Resource entry forms**:
  - `${this, metric=group|name}` — bound to the assigned object.
  - `${adaptertype=ADAPT, objecttype=KIND, attribute=group|name, depth=N}`
    — iterate over related objects N hops away.
  - `${..., resourcename=NAME, identifiers={k=v,...}, metric=...}` —
    a specific named resource.
  - `objecttype=*` is allowed only with an explicit `adaptertype=` and
    means "all resource kinds for that adapter".
- **`depth`**: positive = children, negative = parents, **never 0**.
  Cannot cross sibling branches in one super metric (e.g. VM →
  Datastore Cluster requires two chained super metrics; see p.4173).
- **`where` clause**: filters by another metric **on the same object**;
  the right operand must be a literal number, not another super
  metric or variable. Use `$value` to refer to the entry's own value
  (`where=($value==1)`). Use `isFresh()` for freshness:
  `where=($value.isFresh())`.
- **Aliasing**: `${...} as alias` lets you reuse a resource entry.
  Alias is case-insensitive, cannot start with a digit, cannot use
  `()[]+-*/%|&!=<>,.?:$`, and each name can be used at most once.
  See `supermetrics/datastore_vm_iops_ratio.yaml`.
- **Ternary**: `cond ? a : b`, e.g.
  `${this, metric=cpu|demandmhz} as a != 0 ? 1/a : -1`.

The loader (`vcfops_supermetrics/loader.py`) enforces a subset of
these rules. **The loader is not a full parser** — it catches obvious
mistakes but cannot certify semantic correctness. Treat a successful
`validate` as necessary but not sufficient; reread the formula
yourself before proposing to install it.

## 4. Validate locally

```bash
python -m vcfops_supermetrics validate supermetrics/<file>.yaml
```

Fix any error and re-run until clean. Do not edit the loader to make
a bad formula pass.

## 5. Show the user the result

Show them the YAML and formula. Briefly explain the depth choice, any
`where` clause, and which object type the metric applies to. Ask for
confirmation before touching their VCF Ops instance.

## 6. Install

See `context/install_and_enable.md` for the install path (content-zip
import via `vcfops_supermetrics sync`) and how to enable a super
metric in a policy after install.

## Style

- Names use Title Case, include object scope and unit:
  `Cluster - Avg Powered-On VM CPU Usage (%)`. **Never rename** a
  super metric post-install — the name is used at bundle authoring
  time for cross-references; the `id` in the YAML is what keeps the
  identity stable across renames.
- One super metric per file. File name is short snake_case.
- `description` explains *why* the metric exists and any non-obvious
  depth/where choice.
