# Enumerate paks through the registry reader, never a grep

**Date:** 2026-10-26

## What happened

Asked for a cross-repo issue/PR summary, the orchestrator built the repo
list by grepping `knowledge/context/managed_paks.md` for
`sentania-labs/vcf-content-factory-sdk-*` remotes. That pulled the three
retired vcommunity repos back in as live work, eleven days after Scott had
retired them and the registry had recorded it under `## Retired paks`.
Scott: "the vcommunity packs are deprecated - what are we missing to make
it so you don't forget".

## The lesson

The registry has a retirement boundary and two readers that honour it:
`scripts/bootstrap_managed_paks.sh` and
`src/vcfcf_packaging/managed_paks.py` both stop at `## Retired paks`.
A grep does not. Any time you need "the list of paks" or "the list of
pak repos" for status, triage, CI, or publishing, go through the Python
reader:

```
python3 -c "import sys; sys.path.insert(0,'src'); from vcfcf_packaging import managed_paks as m; print(m.__doc__)"
```

and take the names it returns. If you find yourself grepping the
registry for URLs or `Target:` lines, stop; you are about to re-surface
something Scott already closed.

The only reader meant to see below the boundary is the defect gate's
name check (issue #219), so a defect naming a retired pak still
attributes correctly.

## Applies when

- Building any multi-repo listing (issues, PRs, CI runs, releases).
- Writing a hook or script that fans out over pak repos.
