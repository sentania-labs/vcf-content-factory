# Design: VM Snapshot Inventory (dashboard)

**Status: APPROVED 2026-07-27 (plan-mode approval, RULE-011 satisfied).**

## Initial prompt

See knowledge/designs/views/vm-snapshot-inventory.md — same request; the
dashboard is deliverable 2's wrapper around the view.

## Vision

Thin wrapper: the view carries the content. One full-width View widget
showing the snapshot inventory, plus a small header row of summary stat
widgets so the dashboard answers "how bad is it?" at a glance before the
table answers "which snapshots?".

## Proposed wireframe (pending approval)

```
+----------------------------------------------------------------------+
| Row 1 (short)                                                        |
| +----------------------+  +----------------------+  +--------------+ |
| | Scoreboard:          |  | Scoreboard:          |  | TextDisplay: | |
| | VMs with snapshots   |  | Total snapshot       |  | 24h snapshot | |
| | (count)              |  | space (GB, fleet)    |  | visibility   | |
| |                      |  |                      |  | note         | |
| +----------------------+  +----------------------+  +--------------+ |
+----------------------------------------------------------------------+
| Row 2 (tall, full width)                                             |
| +------------------------------------------------------------------+ |
| | View widget: [VCF Content Factory] VM Snapshot Inventory         | |
| | (one row per snapshot instance; sorted by Age desc)              | |
| | VM | Snapshot Name | Age | Size GB | Creator | Descr | Cluster.. | |
| +------------------------------------------------------------------+ |
+----------------------------------------------------------------------+
```

Notes:
- Reconciled 2026-08-20 with the shipped layout (issue #79): the
  TextDisplay note tile (`snapshot_visibility_note`, x:9 y:1) was added
  during the 24h-materialization work after the original approval; this
  wireframe now shows every shipped widget per RULE-011.
- Coords are 1-indexed on the wire (DEF-013) — author accordingly.
- Scoreboards driven by flat metrics (`summary|snapshotSpace` /
  `diskspace|snapshot`) so they need no instanced plumbing.
- No interactions needed; the view is self-contained.
