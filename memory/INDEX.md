# Memory Index

Per-user and per-session state. Advisory — read for context, never overrides rules or lessons.

## Structure

- **sessions/** — Session pickup notes (`.gitignore`d, per-user state)
- **environment/** — Lab names, instance URLs, user preferences

## What goes here

- Instance URLs and profile names
- Lab naming conventions
- Session-to-session continuity notes
- User-specific preferences

## What does NOT go here

- Binding constraints → `rules/`
- Lessons from failures → `lessons/`
- Domain knowledge → `context/`
- Authoring patterns → `context/authoring/` or agent prompts

## The soul lives in `Memory.md`

`Memory.md` (repo root) is the framework's baseline personality and defaults.
It ships with the repo. This `memory/` directory is per-user state that grows
through use and can be regenerated. Loss of `memory/` is inconvenient; loss of
`Memory.md` is not — a fresh clone has it.
