# Approval: compliance build 90, central overrides file (design compliance-overrides-file)

- **Date:** 2026-10-13
- **From:** Scott, in session
- **Verbatim:** "let's move forward on that, then I have a brainstorming question"
  (in reply to the design note `knowledge/designs/sdk-adapters/compliance-overrides-file.md`
  at commit c36b064, after "i feel like we ship a template and the user copies it and
  then names the copy per adapter instnace")

## Scope this covers

- Author build 90 of the compliance adapter from the design: shipped template under
  content/files/solutionconfig, new `overrides_file` instance setting, Skip / Override /
  Profile entries, status properties and alert, docs/overrides.md, README link rename.
- The two open questions proceed on the design's stated assumptions: Override is
  per-instance scope in this cut; the Custom CSV choice stays one release behind a WARN.
- Review, pak-compare, local build. Devel install is a separate go.

## Not covered

- Devel install of build 90, the Summary rebind on devel, pushes, PRs, tags.
