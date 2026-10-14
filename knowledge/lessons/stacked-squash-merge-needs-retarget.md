# Squash-merging a PR stack without deleting base branches lands the upper PRs in the wrong place

Date: 2026-10-13. Compliance adapter PRs #44, #45, #46 (builds 88 to 93).

## What happened

Three stacked PRs: #44 to main, #45 based on #44's branch, #46 based on
#45's branch. The merge script squash-merged #44 into main with
`--delete-branch=false`, waited briefly for GitHub to retarget #45 to main,
then merged anyway when it did not. GitHub retargets a stacked PR only when
its base branch is deleted. So #45 squashed into the build-88 branch and
#46 into the build-90 branch; main ended with builds 88 and 89 only. The
script then tagged main `v1.0.0.93`. The release workflow's version check
refused the tag (adapter.yaml at that commit said build 89), which is the
only reason a wrong release did not ship. Recovery: delete the tag, open one
PR from the top branch to main (#47), re-tag after it merges.

## Lesson

- Merging a stack bottom-up with squash requires either deleting each base
  branch on merge (GitHub then retargets the next PR to main) or retargeting
  the next PR explicitly (`gh pr edit --base main`) and confirming
  `baseRefName == main` before merging. Never merge on a timeout.
- Alternatively collapse the stack: one PR from the top branch to main once
  the lower reviews are done.
- A release tag is cut only after reading `build_number` at the tagged
  commit and comparing it to the intended tag, locally, before pushing. The
  CI check is the backstop, not the first line.
