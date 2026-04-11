---
name: vcfops-supermetric-dsl
description: >
  The VCF Operations super metric formula DSL: looping functions,
  single functions, operators, resource entry forms, depth modifiers,
  where clauses, aliasing, cross-SM references, and critical pitfalls
  (silent failures with string && operators, instanced metrics,
  property vs metric addressing). Use this skill whenever writing,
  reviewing, debugging, or explaining a super metric formula. Also
  use when a formula produces no data, when choosing between where
  clauses and custom groups for filtering, or when planning a
  multi-SM subtraction pattern.
---

# Super metric formula DSL

## Functions

### Looping functions (aggregate over children)

`avg`, `sum`, `min`, `max`, `count`, `combine`

These take a single resource entry and aggregate across matching
resources.

### Single functions (scalar math)

`abs`, `acos`, `asin`, `atan`, `ceil`, `cos`, `cosh`, `exp`,
`floor`, `log`, `log10`, `pow`, `rand`, `sin`, `sinh`, `sqrt`,
`tan`, `tanh`

## Operators

Arithmetic: `+ - * / %`
Comparison: `== != < <= > >=`
Logical: `&& || !`
Ternary: `cond ? a : b`
Grouping: `( )`, arrays `[x, y, z]`

## Resource entry forms

```
${this, metric=group|name}
```
Bound to the assigned object.

```
${adaptertype=ADAPT, objecttype=KIND, attribute=group|name, depth=N}
```
Iterate over related objects N hops away.

```
${adaptertype=..., objecttype=..., resourcename=NAME,
  identifiers={k=v,...}, metric=...}
```
A specific named resource.

- `objecttype=*` is allowed only with explicit `adaptertype=`.
- `metric=` slot accepts both real metric keys AND property keys.

## Depth

Positive = children, negative = parents. **Never 0.**

Cannot cross sibling branches in one formula (e.g. VM → Datastore
Cluster requires two chained super metrics).

## Where clauses

A bare quoted string inside a resource entry:

```
where="property|key equals literal_value"
```

**No nested `${}` around the property key.** No single quotes
around the literal. No wrapping in parens.

### String operators (where clause only)

`equals`, `contains`, `startsWith`, `endsWith`, and their `!`
negations (`!equals`, `!contains`, etc.).

### Numeric operators (where clause)

`==`, `!=`, `<`, `>`, `<=`, `>=`

### Special references in where

- `$value` — the outer entry's own value
- `$value.isFresh()` — freshness check

### Comparing to empty string

`where="key !equals "` (empty literal after the operator).

## CRITICAL PITFALLS

### 1. String && silently fails

**Do NOT use `&&` with string operators.** Compound `&&` works
with numeric conditions:

```
where=($value == 7 && $value.isFresh())    ← OK
```

But **silently fails** with string operators:

```
where="prop1 equals X && prop2 contains Y"  ← BROKEN: imports,
                                               validates, produces
                                               ZERO DATA with no error
```

This is the most dangerous bug in the DSL. Discovered 2026-04-09.

**Subtraction pattern** — the correct way to filter on two string
properties simultaneously:

1. Create single-condition SMs for each dimension:
   - SM-A: `where="summary|config|type equals VMOperator"`
   - SM-B: `where="productName equals VKS Cluster Node Image"`
2. Compute the difference via cross-SM reference:
   ```
   ${this, metric=Super Metric|sm_<uuid_A>}
   -
   ${this, metric=Super Metric|sm_<uuid_B>}
   ```

All referenced SMs must share resource kind assignments and policy.

### 2. powerState is a string

`summary|runtime|powerState` is a string property (`"Powered On"`).
Do NOT use `where=(${metric=...}==1)`. Use `sys|poweredOn` (numeric,
1.0 = on) instead.

### 3. Instanced metrics need aggregate form

Instanced metric families (virtualDisk, net, datastore,
guestfilesystem) have no data under the bare key. Use the
`:Aggregate of all instances|` form unless you want a single
instance pin.

### 4. Misspelled keys import silently

A misspelled metric key is accepted at import time and produces no
data forever. Always ground keys against the live `/statkeys`
endpoint or `docs/vcf9/metrics-properties.md`.

### 5. metric= accepts both metrics and properties

The `metric=` slot in a resource entry addresses both real metric
keys (`cpu|usage_average`) and property keys
(`config|hardware|num_Cpu`). Watch exact spelling — `num_Cpu` has
an underscore and capital C.

## Aliasing

```
${...} as alias
```

Case-insensitive. Cannot start with a digit. Cannot contain
`()[]+-*/%|&!=<>,.?:$`. Each name used at most once.

## Cross-SM references in formulas

In YAML: `@supermetric:"<exact name>"` inside the formula string.
Loader rewrites to `sm_<uuid>` at validate time.

On the wire: `${this, metric=Super Metric|sm_<uuid>}`.

## Canonical example

Sum provisioned vCPUs of powered-on VMs in a cluster:

```
sum(${adaptertype=VMWARE, objecttype=VirtualMachine,
      metric=config|hardware|num_Cpu, depth=10,
      where=(${metric=sys|poweredOn}==1)})
```

## Formula validation

The loader (`vcfops_supermetrics/loader.py`) enforces a subset of
these rules. **The loader is not a full parser** — treat a
successful `validate` as necessary but not sufficient. Always
re-read the formula yourself.

## Style conventions

- Names: Title Case, include scope and unit:
  `Cluster - Avg Powered-On VM CPU Usage (%)`
- One super metric per file. Filename is short snake_case.
- `description` explains why the metric exists and any non-obvious
  depth/where choices.
