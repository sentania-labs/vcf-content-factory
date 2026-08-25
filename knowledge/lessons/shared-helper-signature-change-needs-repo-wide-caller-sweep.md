# A shared helper's signature or behavior change obligates a repo-wide caller sweep

## The story

The `${this, metric=...}` audit fix (PR #137) changed
`_refs_from_formula()` in `src/vcfops_packaging/deps.py`: a new
`resource_kinds` parameter, and a this-bound ref with no usable kinds
became a hard `AuditError` instead of a silent skip.

Every caller inside `vcfops_packaging` was found and updated. The
framework review gate verified the change thoroughly, twice, and
approved it. Both the author and the reviewer scoped their caller
sweep to `src/vcfops_packaging/`.

`src/vcfops_extractor/extractor.py` called the same helper at two
sites, without the new argument. The change would have made `/extract`
abort the entire extraction workflow on any live-lab super metric
using `${this, metric=...}`. An external Codex review caught it after
the internal gate had cleared the branch.

## The lesson

When a function's signature, defaults, or failure behavior change,
the blast radius is defined by its callers, not by the package it
lives in. Python's cross-package imports make "this is a
vcfops_packaging change" an assumption, not a fact.

Before calling such a change reviewed:

1. `grep -rn "<helper_name>" src/ tests/` across the WHOLE repo, not
   the package being edited.
2. Every hit either passes the new contract, is updated, or is
   explicitly recorded as unaffected and why.
3. New hard-failure paths deserve special suspicion: a caller that
   predates the failure mode inherits it as a crash, in a workflow
   the author was not thinking about.

The validate chain and the per-package test files will not catch
this: they exercise packages in isolation, and the crashing path may
need live-shaped data (here: an extracted SM with assignment
metadata) that no packaging test constructs.

## Where this bit before

The review reports for #113 and #124 record adjacent shapes of the
same failure: coverage scoped to where the change was made, while the
consequence lived where the changed thing was consumed.
