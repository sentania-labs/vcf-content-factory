# vcommunity shape fixtures (issue #218)

Stand-ins for the retired vcommunity pak view corpora, so the real-corpus
tests that used to read `content/sdk-adapters/vcommunity*/views/` run in CI
and on a fresh clone instead of skipping.

## What these are

Factory-written views, not copies. Each file reproduces one **shape class**
that occurs in the source corpus, classified by exactly what the code under
test reads: data type and presentation, bucket mode, whether the attribute
is a super metric, a property-looking key (the DEF-012 hint list) or a
numeric key, `is_property`, `is_string_attribute`, and the column keys
present. Metric and property keys are real VCF Operations keys taken from
the source corpus (RULE-002); names, descriptions and ids are new.

| Directory | Shape source | Classes |
|---|---|---|
| `distribution_fixed/` | `sentania-labs/vcf-content-factory-sdk-vcommunity-vsphere` at `5981c3cd9d13dfdcb11ae58238cd7003dae3de79`, `views/` (51 distribution views) | 7, one file each |
| `distribution_unfixed/` | `sentania-labs/vcf-content-factory-sdk-vcommunity` at `4eb026634448f65dd47686fa3f0e6065287699e4`, `views/` (50 distribution views, pre-DEF-012 vendor originals) | 5, one file each |
| `render/` | same vcommunity commit, `views/` (96 views) | the render shapes that commit carried and the tracked factory corpus does not: pie-chart distribution, unit `day`, `7004`, `auto`, `week`, `msec`, `tb`, `mbps`, `MIN` and `TIMESTAMP` transformations, and the `APPLICATIONDISCOVERY` subject |

The sibling fixture `tests/fixtures/sdk_adapters/solutionconfig_six/` keeps
the six SolutionConfig file names and root elements from the same vcommunity
commit (`content/files/solutionconfig/`) with synthetic bodies.

## Why not copy the corpus

The vcommunity paks are a port of `vmbro/VCF-Operations-vCommunity`, which
is now published under the PolyForm Noncommercial License 1.0.0. Copying
that content into this repository is a licensing decision that has not been
made, so these fixtures carry shapes and vendor metric keys only.

## Keeping them honest

The super metric column names a real factory super metric
(`[VCF Content Factory] Cluster - Idle VM Count`), so the render test
resolves it against `content/supermetrics/` in scoped mode. Renaming that
super metric means updating the two files that reference it.
