# Content migrator v1: moved

This document now lives in the tool's own repo, where a change can be judged
against the reasons for it without leaving the repo:

**`sentania-labs/vcf-cf-migrator`, `docs/design/content-migrator-v1.md`**

Moved 2026-09-15, after v0.3.0, on Scott's word: "in terms of the design doc,
I think that should be pushed down into the project repo itself."

The six migrator review records that were under
`knowledge/context/reviews/framework/` went with it, to `docs/reviews/` in
that repo.

## What stayed here, and why

`vcf-cf-tooling-core` is maintained in this repo. Its carve-out design
(`tooling-core-carveout-v1.md`) and the `m2-row*` review records under
`knowledge/context/reviews/framework/` are this repo's record and stay.

The migrator consumes that library and does not own it. It pins a wheel from a
`core-v*` release of this repo by URL, deliberately rather than through a
package index: a build of the tool is then reproducible from two git tags and
nothing else. When it needs something from the library, the path is an issue
on this repo, a release, and a pin bump on its side. Scott, verbatim: "this
repo is basically the maintainer of those packages, and I can open up an issue
from the child project."

## One thing that did not move

The copies in that repo have corpus-derived identifiers redacted. The versions
in this repo's history do not, and neither do
`knowledge/context/exports/*.json`, which carry 272 distinct uuids from the
lab. Whether any of that should be scrubbed is an open decision, recorded in
the moved document under "Open items for Scott". It is object ids rather than
credentials, and no person names were found in them.

The tool that checks this now lives in the migrator repo as
`tools/corpus_leak_scan.py`. It harvests from the corpus rather than from a
remembered list, and `--history` reads every blob in every revision.
