# An exit status you did not enumerate is not a verdict

**Written 2026-08-24, after a review gate cleared the exact defect an
external reviewer then caught.**

## The shape

Code shells out to a tool, branches on the exit status, and collapses
"everything else" into whichever branch reads best:

```python
if rc == 0:
    return "a git repo there DOES ignore it"
if rc == 1:
    return "it is NOT git-ignored ..."
# 128 == not a git repository, plus anything unexpected.
return "its directory is not a git repo, so nothing there could commit it"
```

That comment is the whole bug. `git check-ignore` documents **128 as a
fatal error**, not as "no repository here". Verified against git 2.43.0,
three genuinely different situations all return 128:

- a plain directory that is not a repository
- a real repository with a **malformed** `.git/config`
- a real repository with an **unreadable** `.git/config`

So a broken repository was reported to the operator as *"its directory
is not a git repo, so nothing there could commit it"* — on the credential
wizard's prompt, the one place where someone decides whether to write a
plaintext password outside the repo. The tool said **safe** when it meant
**unknown**.

## The rule

**Map every status you have enumerated. Everything else is unknown, and
unknown is never the reassuring branch.**

`0 = yes`, `1 = no`, `else = could not determine`. If the residual bucket
carries a confident sentence, the code is asserting something it did not
establish.

This generalizes past exit codes: any residual `else` that emits a
positive claim is the same defect. Sibling instances found in this repo
within the same week:

- a lookup returning `@()` on an HTTP error, indistinguishable from a
  genuine empty result, feeding a create decision → duplicate objects
  created under existing names, reported as `OK Created`
- a poll reading an absent `state` member as `""`, indistinguishable
  from idle → a probe overlapping a live export
- an uninstall reporting `not found (already removed?)` from a lookup
  that had failed

Same shape every time: **a safe default for reading became an unsafe
default for deciding.**

## Why the review gate missed it

The gate did check the branch. It built a scenario table, ran the real
`git`, and marked the 128 row *"correct: yes"* — because it tested `.env`
in a plain directory, where the reassuring sentence happens to be true.
It never asked what **else** produces 128.

That is the durable lesson for reviewers, and it is the second time this
pattern has appeared here: **verifying the artifact is not the same as
verifying the signal about the artifact.** A scenario table proves the
cases you thought of. The defect lives in the case you did not, which is
exactly the one the residual branch swallows.

When reviewing a status/return-code mapping, ask directly: *what is the
complete set of values this can return, per its documentation, and which
of them land in the branch that sounds safe?*

## Recovering the benign case

Collapsing to "unknown" is correct but costs precision on the common,
harmless case. Where a second signal exists, use it rather than accepting
permanent vagueness: for this instance, walking up from the path looking
for a `.git` entry distinguishes "no repository" from "broken
repository" with no extra subprocess and no parsing of translatable
stderr. Tracked as #122.

## Provenance

Codex P2 on PR #117; fixed in `de1cfe3`. The review artifact that cleared
it (`knowledge/context/reviews/framework/common-doctor-setup-2026-08-23.md`)
carries a dated annotation rather than a corrected row, deliberately —
editing it would delete the only evidence the gate had a blind spot.
