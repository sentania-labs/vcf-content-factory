# Memory Index

Advisory knowledge — observations, quirks, and session notes. Read for texture, never overrides rules or decisions.

## Structure

- **quirks/** — API weirdness, tool gotchas, one-off oddities
- **observations/** — "We noticed that..." — patterns that don't rise to rule/decision level yet
- **sessions/** — Session pickup notes (`.gitignore`d, per-user state)

## What goes here

Memory is for knowledge that doesn't fit elsewhere:

- API rate limits discovered empirically
- Tool timeout behaviors
- Vendor-specific quirks that don't affect design decisions
- Session-to-session continuity notes

## What does NOT go here

- Binding constraints → `rules/`
- Architectural choices → `decisions/`
- Domain knowledge → `context/`
- Authoring patterns → `context/rules_*.md` or agent prompts

## Promotion path

If a memory entry keeps being relevant, promote it:
- Observation → rule (if it's a constraint)
- Observation → context (if it's domain knowledge)
- Observation → decision (if it's an architectural choice)

Document the promotion when it happens.
