# A failed git checkout inside a multi-line command lets the rest land on the wrong branch

Date: 2026-10-15. Factory branches chore/retire-vcommunity-paks and
docs/prod-incident-hotfix-94.

## What happened

The orchestrator ran one Bash call that did `git checkout -q <branch> &&
python3 - <<EOF ... EOF`, then on later lines `git rm`, `git add -A`,
`git commit`, `git push`. The checkout failed ("already used by worktree",
because a tooling agent had the branch checked out in its own worktree).
The `&&` protected only the heredoc. The later lines ran on the branch the
tree was already on, committed a file deletion there and pushed it. Recovery
was a plain revert commit on that branch; the real change had to wait for the
worktree to be released.

## The rule

- One Bash call, one branch. Never chain a checkout with edits and a commit.
  Check out, confirm with `git branch --show-current`, then edit and commit in
  a later call.
- Before `git commit`, the command that commits also prints the branch name,
  so the wrong branch shows up in the output before the push.
- When an agent is working on a branch in a worktree, the branch is theirs
  until they report. Edit the branch after the report, or do the work in the
  agent's brief.

## Why it matters

A pushed commit on the wrong branch cannot be removed without a force-push,
which needs Scott's verbatim go (RULE-008). A revert pair is the only
self-service recovery, and it leaves noise in a PR that was not involved.
