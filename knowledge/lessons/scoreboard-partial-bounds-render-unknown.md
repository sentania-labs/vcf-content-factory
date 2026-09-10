# Scoreboard tiles with a partial bound set render "?" with no error

**Date:** 2026-08-25. **Where:** VCF Operations 9.2 pre-release lab build; the same
widget code path exists on 9.1.

## What happened

A summary dashboard's Scoreboard tiles rendered a grey "?" (state
Unknown) on every adapter-specific metric, while PropertyList widgets on
the same object showed live values for the same keys. Data was two
minutes old, nothing was instanced, nothing was disabled in policy, the
materialized summary copy was identical to the source. Every diagnosis
that looked at the data was a dead end.

## Root cause

A Scoreboard metric entry with `colorMethod: 0` must carry all three
numeric bounds (`yellowBound`, `orangeBound`, `redBound`). With a partial
set (only `redBound`, or yellow and orange without red) the server's own
`getMetricValues` answers `value: "?"`, `state: Unknown`, even though the
same response carries the populated `doubleValue`. Proven by replaying
the widget's `.action` calls with single-field variants: the identical
entry with `(1, 1, 1)` returns the value and Normal.

Thresholds are ascending and inclusive: `>= yellow` Warning, `>= orange`
Immediate, `>= red` Critical. "Red at anything above zero" is `(1, 1, 1)`,
which is what the vendor's own dashboards use for flag metrics.
`colorMethod: 3` means percent-of-`maxValue` thresholds in vendor
exports; the factory does not emit bounds for it (only for 0), and the
loader rejects bounds supplied with 3.

## Rule

- Author bounds as a full triple or not at all. Uncolored is fine;
  partial is a silent failure.
- The dashboard loader rejects partial sets on `color_method: 0`
  (added the same day). If you see "?" on a tile whose value you can
  read elsewhere, check the bounds before checking the data.
- Do not put a unit on a metric whose statkey has none: a 0/1 flag
  labelled `%` renders "1 %".
