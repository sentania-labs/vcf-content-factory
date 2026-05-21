# guide_codification.md

How to turn one-off corrections into permanent framework knowledge.

## Why this file exists

The framework is the product. That guarantee only holds if the
hard-won lessons accumulated in conversation get written down where
the next session — or the next admin who clones the repo — can find
them. This file is the playbook for that.

Auto-memory is disabled by design (`CLAUDE.md` Hard Rule 8). Without
this discipline, knowledge lives only in transcripts and
disappears.

## When to codify

Codify whenever any of the following happen:

1. The user corrects the orchestrator or an agent on a substantive
   point — a DSL quirk, a wire format detail, a metric-key
   spelling, a mistaken delegation.
2. An `api-explorer` or `tooling` agent discovers something that
   isn't yet documented.
3. A "this works, that doesn't" pattern emerges across more than
   one session.
4. An install fails in a non-obvious way and the failure mode is
   reproducible.
5. The user says something like "remember that…" or "from now on…"
   — that's a literal cue, not a suggestion.

If the orchestrator finds itself wanting to add a note to memory,
that's the cue: it goes in the repo instead.

## Where it goes

Pick the destination by scope, not by convenience:

| Kind of knowledge | Destination |
|---|---|
| DSL pattern, formula idiom, anti-pattern | `context/supermetric_authoring.md` AND `.claude/agents/supermetric-author.md` (the agent prompt is what gets loaded at delegation time) |
| Wire format detail (zip layout, JSON shape, header) | `context/wire_formats.md` (or the topical wire format file) AND the relevant `vcfops_*/render.py` or `loader.py` if the renderer needs to emit it |
| API surface (endpoint, behavior, auth quirk) | `context/content_api_surface.md` or the topical API file |
| "Do this not that" correction for an agent | The agent's prompt under `.claude/agents/<agent>.md`. Hard rules go in the **Hard rules** section; idioms go in the workflow section |
| Orchestrator-level rule (delegation, install gating) | `CLAUDE.md` itself, in the relevant section |
| Cross-cutting operational rule (credentials, labs) | The matching `context/rules_*.md` |
| New capability boundary discovered | `context/known_limitations.md` (so future sessions surface it early instead of discovering it mid-workflow) |

When in doubt, write to two places: the topical context file (for
depth) and the agent prompt (for the always-loaded, agent-scoped
version).

## What "codified" looks like

A good codification entry has all of:

1. **The rule, stated affirmatively.** Not "don't use single quotes
   around the where literal" — say what TO do: "where clause
   literals are bare, with no surrounding quotes."
2. **The minimum reproducer that exposes the failure mode.** If
   the agent can pattern-match on a small example, it will catch
   the issue without re-deriving the rule.
3. **The failure mode if violated.** "Installs cleanly, produces
   zero data" is information; "doesn't work" is not.
4. **A pointer back to the source of truth** if there is one
   (DSL doc section, OpenAPI path, an export specimen under
   `references/`).

Bad codification is just a war story. Good codification is a rule
the next session can apply without re-reading the war story.

## Things that should never be codified

- One-shot fixes that only made sense in the context of one
  conversation. If the underlying issue isn't reproducible, the
  rule won't be either, and you'll mislead future sessions.
- User-specific preferences about formatting, brevity, or tone.
  Those go in `userPreferences`, not in the framework.
- Information about which lab to use, which credentials to use, or
  which machine the user is on. That belongs in `.env` and
  `guide_operational.md`, not scattered across context files.
- Anything about the user personally — their name, their employer,
  their schedule, their other projects. The framework is the
  product, and the framework should work the same for any admin
  who clones it.

## How to know it worked

A codification worked if:

- A future session, given a similar trigger, applies the rule
  without being told — the agent prompt or context file was loaded
  at the right moment and the rule was specific enough to fire.
- The user doesn't have to make the same correction twice across
  sessions.
- Someone else who clones the repo can read the rule and
  understand why it exists, not just what it says.

If a rule keeps needing to be re-explained, it's in the wrong
place or stated badly. Move it or rewrite it.

## The compounding effect

Every time the framework gets corrected and the correction lands
in the right place, the next session starts smarter. That's the
whole bet. The orchestrator's job is not just to do the current
task — it's to make sure the framework comes out of the session
slightly more capable than it went in.

A session that completed the user's task but didn't codify the
lessons it learned is a session that left value on the table.