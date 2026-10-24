# Owner approval: merge the open PR round and close its issues, 2026-10-23

Scott's go for merging five pull requests under his GitHub identity and
closing the issues they fix. This file is committed on the first branch
merged (PR #247) so the words land on `main` with the first merge; the
later merges, version bumps and issue closures run after it.

## Verbatim

- **2026-10-23, the go:** "please merge them all and then ensure the
  associated issues are clsoed"
- **Context, same day:** "I've merged 243.  wha tnext?" and "merged 241",
  after the earlier standing directive "please begin working through
  closing all open issues. interrupt me when a change is ready to merge
  or if framework decisions need to be made."

## Scope executed under these words

1. Squash-merge PRs #247, #246, #248 and #251 into `main` in that order,
   deleting the branches.
2. Between merges, renumber the buildkit on the branches that still claim
   `1.0.13`: #248 to `1.0.14`, #251 to `1.0.15`, each by a merge of `main`
   plus a version commit, no force-push, with CI green before the merge.
3. Close every issue each PR body names, with a comment naming the merging
   PR, where GitHub's closing keyword did not already do it.

Not covered: tagging a buildkit release, pushing anything to the pak
repos, and every item still on the decision list.
