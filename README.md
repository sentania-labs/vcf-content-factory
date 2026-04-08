# VCF Operations SuperMetrics Framework

A small framework to author VCF Operations super metrics as version-controlled
YAML files and synchronize them into a VCF Operations instance via the
Suite API (`/suite-api/api/supermetrics`).

## What is a super metric?

A super metric is a custom mathematical formula built from one or more
metrics/properties of one or more objects. Formulas are written in the
VCF Operations super metric DSL, e.g.:

```
avg(${adaptertype=VMWARE, objecttype=VirtualMachine, attribute=cpu|usage_average, depth=1})
```

Key DSL elements (see VCF 9 docs, "Configuring Super Metrics", p. 4171+):

- **Resource entry** — `${ ... }` block describing the metric source. Either
  bound to the assigned object (`${this, metric=...}`) or to a related
  object set (`${adaptertype=..., objecttype=..., attribute=..., depth=N}`).
- **`depth`** — relationship distance from the assigned object. `depth=1`
  is one level below; `depth=-1` is one level above. Cannot be 0.
- **Looping functions** — `avg`, `sum`, `min`, `max`, `count`, `combine`.
- **Single functions** — `abs`, `sqrt`, `log`, `pow`, trig, etc.
- **`where` clause** — filter by another metric *on the same object*,
  e.g. `where=(${metric=summary|runtime|powerState}==1)`.
- **Aliasing** — `${...} as cpu` lets you reuse a resource entry.
- **Ternary** — `cond ? a : b`.

## Layout

```
supermetrics/           YAML definitions, one per file
vcfops_supermetrics/    Python package: client, loader, CLI
  client.py             Suite API client (token auth + supermetric CRUD)
  loader.py             Load + validate YAML definitions
  cli.py                `python -m vcfops_supermetrics ...`
```

## YAML schema

```yaml
name: Cluster - Avg Powered-On VM CPU Usage (%)
description: Average CPU usage across powered-on VMs in the cluster.
formula: |
  avg(${adaptertype=VMWARE, objecttype=VirtualMachine,
       attribute=cpu|usage_average, depth=2,
       where=(${metric=summary|runtime|powerState}==1)})
```

`name` and `formula` are required; `description` is optional. The `name`
field is the natural key used for upserts.

## Usage

```bash
export VCFOPS_HOST=vcfops.example.com
export VCFOPS_USER=admin
export VCFOPS_PASSWORD=...
# optional: VCFOPS_AUTH_SOURCE=Local, VCFOPS_VERIFY_SSL=false

# Validate every YAML file under supermetrics/
python -m vcfops_supermetrics validate

# List super metrics on the target instance
python -m vcfops_supermetrics list

# Push (create or update) every YAML file under supermetrics/
python -m vcfops_supermetrics sync

# Push a single file
python -m vcfops_supermetrics sync supermetrics/cluster_avg_vm_cpu.yaml

# Delete a super metric by name
python -m vcfops_supermetrics delete "Cluster - Avg Powered-On VM CPU Usage (%)"
```

`sync` is idempotent: if a super metric with the same `name` already
exists it is updated (PUT), otherwise it is created (POST). After sync
the super metric still needs to be enabled in the relevant policy and
assigned to an object type from the UI (the public API does not expose
object-type assignment).

## Requirements

```
pip install -r requirements.txt
```
