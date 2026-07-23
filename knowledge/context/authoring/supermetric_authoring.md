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

Place under `content/supermetrics/<short_snake_case>.yaml`:

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

## 3. DSL rules (from `reference/docs/vcf9/supermetrics.md`)

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
- **`where` clause — TWO DIALECTS.** (Empirically established
  2026-07-22 by a 6-probe suite on devel; see "Parenthesized
  `$value` dialect" below for the second one. The dialects have
  DIFFERENT rules — do not mix guidance between them.)

  **Dialect A — quoted-string**: a **bare quoted string** inside a
  resource entry. Property keys and literal values appear bare — no
  nested `${}` around the property key, no single quotes around the
  literal, no wrapping the whole thing in parens. String operators
  (`equals`, `contains`, `startsWith`, `endsWith`, and their `!`
  negations) and numeric operators (`==`, `!=`, `<`, `>`, `<=`,
  `>=`) are both valid. Canonical example — sum provisioned vCPUs
  of VM Service VMs:

  ```
  sum(${adaptertype=VMWARE, objecttype=VirtualMachine,
        metric=config|hardware|num_Cpu, depth=10,
        where="summary|config|type equals VMOperator"})
  ```

  **Do NOT write** `where=(${metric=key} equals 'literal')` —
  nested `${}` inside a where clause and quoted string literals are
  both wrong and get the whole super metric silently skipped at
  import time. Comparing to "not empty" is `where="key !equals "`
  (empty literal after the operator). Use `$value` to refer to the
  outer entry's own value (`where="$value == 1"`) and `isFresh()`
  for freshness (`where="$value.isFresh()"`).

  **CRITICAL (Dialect A only): Do NOT use `&&` with string
  operators.** Compound
  `&&` works with numeric conditions
  (`where=($value == 7 && $value.isFresh())`), but **silently
  fails** when combined with string operators (`equals`,
  `contains`, etc.). A formula like
  `where="prop1 equals X && prop2 contains Y"` imports
  successfully, validates, and produces **zero data** with no
  error — the most dangerous kind of bug. Discovered 2026-04-09
  when three VKS super metrics all returned 0 despite correct
  property values on the target VMs. **This restriction does NOT
  apply to Dialect B below** — the 2026-04-09 finding was
  overgeneralized until the 2026-07-22 probe suite separated the
  two grammars.

  **Dialect B — parenthesized `$value`**: `where=( … )` with
  `$value` referring to the entry's own metric/property value and
  **single-quoted** string literals:

  ```
  count(${this, metric=cpu|cpuModel,
    where=($value contains 'Gold 61' || $value contains 'EPYC 7551')}) ? 1 : 0
  ```

  Vendor-attested ("My Top 15 vRealize Operations Super Metrics"
  blog, #8/#9/#10) and verified end-to-end on devel 2026-07-22 by a
  6-probe suite (probe SMs installed, policy-enabled, per-host
  values checked against known cpuModel ground truth — 45/45 series
  correct, zero silent failures). Established behavior:

  | Construct | Verdict |
  |---|---|
  | `$value contains 'A' \|\| $value contains 'B'` | ✅ works (both arms evaluated) |
  | `$value contains 'A' && $value contains 'B'` | ✅ works (unlike Dialect A!) |
  | `!($value contains 'A')` | ✅ works (inverts correctly) |
  | Parens inside the quoted literal (`'Core(TM) i7'`) | ✅ works |
  | Chained ternary `c1 ? 2 : c2 ? 1 : 0` around counts | ✅ correct precedence |
  | Case-insensitive matching | ❌ NO — `contains 'I7'` does not match `i7`; literals must be byte-exact case |

  Use Dialect B whenever a formula must test one string
  property against multiple literals (classification, allowlists);
  use Dialect A for cross-property filtering on related resources.
  Testing DIFFERENT properties in one compound Dialect-B where is
  untested — probe first (the 2026-07-22 suite only exercised
  multiple conditions on the same `$value`).

  **Subtraction pattern** — the correct way to filter on two
  string properties simultaneously:

  1. Create single-condition SMs for each dimension:
     - SM-A: `where="summary|config|type equals VMOperator"` → all VMOperator vCPU
     - SM-B: `where="summary|config|productName equals vSphere Kubernetes Service Cluster Node Image"` → VKS node image vCPU
  2. Compute the difference via cross-SM reference:
     ```
     ${this, metric=Super Metric|sm_<uuid_A>}
     -
     ${this, metric=Super Metric|sm_<uuid_B>}
     ```
     Result = VM Service vCPU (VMOperator minus VKS).

  All referenced SMs must be assigned to the same resource kinds
  and enabled in the same policy. See `vks_vmservice_vcpu.yaml`,
  `vks_cp_vcpu.yaml` for working examples of this pattern.

  **Cross-SM time-misalignment (one-cycle lag).** A super metric that
  references another super metric (`${this, metric=Super Metric|sm_<uuid>}`)
  reads that upstream SM's value from the **previous collection cycle**, not
  the current one — the platform does not guarantee the upstream SM is
  recomputed before the dependent SM within the same cycle. A chain of
  dependent SMs is therefore **time-skewed by one collection per hop**, and the
  skew is invisible: it imports, validates, and produces plausible-but-lagged
  values. **Prefer a single self-contained formula** over splitting one logical
  metric into a chain of dependent SMs when the inputs must be time-aligned.
  Use the cross-SM subtraction pattern above only when one formula genuinely
  cannot express the result (e.g. two mutually-exclusive `where` filters), and
  treat the one-cycle lag as a known, accepted trade-off. (Source: ops-PM
  domain review, 2026-06-29.)

  **Also: `summary|runtime|powerState` is a string property**
  (`"Powered On"`), not a numeric metric. Do not use it in
  `where=(${metric=...}==1)`. Use `sys|poweredOn` (numeric,
  1.0 = on) instead. See `cluster_avg_vm_cpu.yaml` for the
  corrected pattern: `where=(${metric=sys|poweredOn}==1)`.

- **Metric vs property targets**: the `metric=` slot in a resource
  entry can be either a real metric key (`cpu|corecount_provisioned`)
  or a property key (`config|hardware|num_Cpu`,
  `summary|config|type`, `summary|parentGuestCluster`) — Ops
  addresses both through the same slot. For "sum provisioned vCPUs"
  both `cpu|corecount_provisioned` and `config|hardware|num_Cpu`
  work on VirtualMachine. Watch the **exact spelling**: `num_Cpu`
  has an underscore and a capital C, not `numCpu`. Misspelled keys
  are accepted at import time and silently produce no data.
- **Aliasing**: `${...} as alias` lets you reuse a resource entry.
  Alias is case-insensitive, cannot start with a digit, cannot use
  `()[]+-*/%|&!=<>,.?:$`, and each name can be used at most once.
  See `content/supermetrics/datastore_vm_iops_ratio.yaml`.
- **Ternary**: `cond ? a : b`, e.g.
  `${this, metric=cpu|demandmhz} as a != 0 ? 1/a : -1`.

The loader (`src/vcfops_supermetrics/loader.py`) enforces a subset of
these rules. **The loader is not a full parser** — it catches obvious
mistakes but cannot certify semantic correctness. Treat a successful
`validate` as necessary but not sufficient; reread the formula
yourself before proposing to install it.

## 4. Validate locally

```bash
python -m vcfops_supermetrics validate content/supermetrics/<file>.yaml
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
