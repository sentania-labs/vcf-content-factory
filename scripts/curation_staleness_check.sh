#!/usr/bin/env bash
# curation_staleness_check.sh — SessionStart staleness nudge for the curator (P6).
#
# Informs the orchestrator when the governance corpus is due for a curation
# pass. It NEVER launches anything — orchestrators spawn agents, hooks inform.
# FAIL-OPEN: any internal error exits 0 silently and never blocks a session.
#
# Trigger: last_run > 7 days  OR  sessions-since-last-curation > 10.
#   - context/curation/.last-run   (COMMITTED)  holds `last_run=<ISO8601>` — the
#     durable "when did we last curate", reset by the orchestrator when the
#     curator completes.
#   - context/curation/.sessions-since (GITIGNORED) is a per-checkout velocity
#     counter the hook increments each session; zeroed on curation. It is not
#     committed because "sessions since" has no meaning shared across clones.
#
# When due, emits a SessionStart additionalContext block instructing the
# orchestrator to spawn `curator` in the background and tell the user.
# Design of record: designs/curator-v1.md.

# No `set -e` — fail-open is the priority. Wrap everything; any failure → exit 0.
{
  REPO_ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)" || exit 0
  CUR_DIR="${REPO_ROOT}/context/curation"
  MARKER="${CUR_DIR}/.last-run"
  COUNTER="${CUR_DIR}/.sessions-since"
  THRESHOLD_DAYS=7
  THRESHOLD_SESSIONS=10

  # Not installed (fresh tree without the dir) → silent, no-op.
  [ -d "$CUR_DIR" ] || exit 0

  # --- increment the gitignored per-checkout velocity counter ---
  sessions=0
  if [ -f "$COUNTER" ]; then
    sessions="$(tr -dc '0-9' < "$COUNTER" 2>/dev/null)"
    [ -n "$sessions" ] || sessions=0
  fi
  sessions=$((sessions + 1))
  echo "$sessions" > "$COUNTER" 2>/dev/null || true

  # --- read the durable last_run timestamp ---
  last_run=""
  if [ -f "$MARKER" ]; then
    last_run="$(grep -E '^last_run=' "$MARKER" 2>/dev/null | head -1 | cut -d= -f2-)"
  fi

  days=0
  if [ -n "$last_run" ]; then
    last_epoch="$(date -d "$last_run" +%s 2>/dev/null || echo "")"
    now_epoch="$(date +%s 2>/dev/null || echo "")"
    if [ -n "$last_epoch" ] && [ -n "$now_epoch" ]; then
      days=$(( (now_epoch - last_epoch) / 86400 ))
    fi
  fi

  # --- decide whether curation is due ---
  due_reason=""
  if [ -z "$last_run" ]; then
    due_reason="no prior curation recorded"
  elif [ "$days" -gt "$THRESHOLD_DAYS" ]; then
    due_reason="${days}d since last curation (>${THRESHOLD_DAYS}d)"
  elif [ "$sessions" -gt "$THRESHOLD_SESSIONS" ]; then
    due_reason="${sessions} sessions since last curation (>${THRESHOLD_SESSIONS})"
  fi

  # Not due → silent.
  [ -n "$due_reason" ] || exit 0

  # --- emit the nudge as SessionStart additionalContext ---
  # Single-quoted message: no backticks / double-quotes / backslashes / newlines,
  # so it is safe both for bash and as a raw JSON string value.
  msg='CURATION DUE ('"$due_reason"'). The governance corpus (rules/, lessons/, context/, .claude/agents/, CLAUDE.md) is overdue for a staleness audit. Per the curator contract in CLAUDE.md: spawn the curator agent in the BACKGROUND (read-only; it writes context/curation/<date>-report.md) and tell the user it is running. Do not block the current task. On completion, reset context/curation/.last-run last_run to today and zero context/curation/.sessions-since.'
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"%s"}}\n' "$msg"
} 2>/dev/null || true

exit 0
