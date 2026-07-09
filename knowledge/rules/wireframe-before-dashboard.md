---
id: RULE-011
---

# RULE-011: Wireframe + plan-mode approval before dashboard authoring

Before delegating to `dashboard-author`, the orchestrator MUST enter plan
mode and present an ASCII (or markdown table) wireframe of the proposed
dashboard layout for explicit user approval. No dashboard YAML gets
written until the user signs off on the wireframe.

The wireframe must show:

1. **Grid placement** of every widget (12-column grid; widget block
   coordinates / spans).
2. **Widget type** per cell (ResourceList picker, View embed, Heatmap,
   Scoreboard, MetricChart, etc.).
3. **Subject / metric** per non-View widget so the user can see which
   resource kind and metric each cell will pull from.
4. **Interaction wiring** — which widget drives which (picker → all,
   list selection → drill-down, etc.).
5. **Known constraints** that shaped the layout (e.g., "Disk latency is
   per-database because the metric doesn't exist on the parent
   `SqlServer`").

The wireframe lives in the design note (`knowledge/designs/dashboards/<slug>.md`),
**not** in chat alone — so a future reader can diff it against the
shipped YAML. The orchestrator commits the wireframe to the design note
BEFORE spawning `dashboard-author`.

This rule does NOT apply to:

- View authoring (`view-author`) — column choices are easier to read
  from a brief than a wireframe.
- Super metric authoring (`supermetric-author`) — formulas don't have a
  spatial layout.
- Other content types where there is no spatial layout to approve.
- **Bug fixes / property tweaks on an already-approved dashboard** that
  do NOT change widget grid placement, widget type, interaction wiring,
  or the resource-kind subject of any widget. Changing a `size_by`
  metric, swapping a metric key, tightening a threshold, fixing a typo
  — these don't need a re-wireframe. Anything that adds, removes,
  moves, resizes, or changes the *purpose* of a widget does need one.

It DOES apply to dashboards specifically because a wireframe is the
cheapest correction loop — re-arranging a wireframe takes seconds; a
re-authored, re-validated, re-installed dashboard takes minutes and
burns user trust.

**Plan mode is the enforcement mechanism.** Use the harness's plan mode
to surface the wireframe + intent to the user, then wait for explicit
approval before exiting plan mode and delegating to the author.

**If violated:** The user discovers layout problems only after install
— widgets misplaced, the wrong metrics chosen, panel collapses that
could have been caught in a 30-second wireframe review. This was the
specific feedback that motivated the rule.
