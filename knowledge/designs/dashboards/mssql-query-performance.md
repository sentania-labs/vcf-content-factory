# MSSQL Query Performance & Blocking Dashboard

Slug: `mssql-query-performance`
Adapter: `SqlServerAdapter` (MSSQL adapter)
Primary object: `SqlServer`

## Initial prompt

> I am a SQL administrator monitoring oracle and MSSQL with VCF Operations.
> I would like a more robust dashboard to investigate query performance.
> I am interested in supplementing or replacing some of the monitoring
> performed by Solarwinds DPA. I have attached a screenshot of one of my
> most common views that I use from Solarwinds.
>
> Can you help me create a dashboard for MSSQL and a different for Oracle
> that presents a similar view and helps me dig into query performance and
> blocking?

(See `tmp/sql.png` for the Solarwinds DPA reference screenshot. Layout:
top stacked-bar chart of top wait-time queries, middle Active/Blocked
session count tiles, bottom row of four resource line charts —
OS CPU %, Page Life Expectancy, Disk Write Latency, Disk Read Latency.)

## Vision

A single-page MSSQL dashboard that lets a DBA pick one `SqlServer`
instance and triage query performance + blocking in three vertical
stripes: **what's slow** (top), **who's stuck** (middle), **what's the
box doing** (bottom). Closest possible behavioural match to DPA, adapted
to VCF Ops idioms where DPA's exact widget type doesn't translate.

### Confirmed user choices (don't relitigate)

- **Scope:** SqlServer instance picker at the top drives every other
  widget. No fleet section.
- **Queries panel:** heatmap + sortable list view of `SqlQuery`
  resources scoped to the picked server. They are all the same objects
  — DPA's "Highest Total / Long Running Avg / Most Executed" tabs
  collapse into one list with sortable columns.
- **Sessions panel:** two count tiles (active, blocked) + drill-down
  list below.
- **Bottom resources row:** CPU %, Page Life Expectancy, Disk Read
  Latency (multi-line per database), Disk Write Latency (multi-line per
  database).

### Constraints surfaced by ops-recon (binding)

1. **No per-session resource exists.** The adapter does not surface
   individual sessions as VCF Ops resources, so a per-session
   drill-down list is impossible. The drill-down behind the count tiles
   uses `microsoft_sql_server_wait_time` resources — a wait-type
   breakdown (what the sessions are waiting on) rather than a per-
   session table. The user explicitly accepted this substitution.

2. **Disk latency lives on `SqlDatabase`, not `SqlServer`.**
   `disk_access|read_delay` and `disk_access|write_delay` are
   per-database metrics. The latency charts must be multi-line trend
   charts, one line per `SqlDatabase` whose parent is the selected
   `SqlServer`. The user explicitly accepted this — "you see which DB
   is slow, not just that the instance is."

3. **Reference dashboards exist but are stale.**
   `reference/references/brockpeterson_operations_dashboards/Legacy MSSQL Dashboards.zip`
   (extracted to `/tmp/mssql_ref/mssql_extracted/`) has a useful
   layout/interaction pattern reference, especially
   `MS-SQL-DBA-Overview.json` and `MS-SQL-Query-Analysis.json`. Several
   metric keys in those JSONs are from an older adapter version; treat
   the file as a layout/interaction reference, NOT as a metric-key
   reference. Cite `brockpeterson/operations_dashboards/Legacy MSSQL Dashboards.zip`
   in the dashboard description if the layout is adapted.

## Panel-by-panel spec

All widgets except the picker have an Interaction set so that the
picker (and the queries list) drive them.

### 1. Instance picker (top)
- **Widget:** ResourceList (or equivalent picker widget)
- **Subject:** `SqlServer`
- **Behavior:** selection broadcasts to all downstream widgets.

### 2. Queries panel (large, just below picker)

#### 2a. Heatmap
- **Subject:** `SqlQuery` resources whose ancestor is the selected `SqlServer`.
- **Color metric:** `general|total_worker_time` (DPA's "total execution time" analogue).
- **Size metric:** `general|execution_count`.
- Optional: tooltip / label shows query name / hash.

#### 2b. Sortable list view
- **Subject:** `SqlQuery` (same scope as heatmap).
- **Columns (verified collected):**
  - Name (resource name — usually query hash or text fragment)
  - `general|total_worker_time` (Total Worker Time)
  - `general|avg_execution_time` (Average Execution Time)
  - `general|execution_count` (Execution Count)
  - `general|total_logical_reads` (Total Logical Reads)
  - `general|total_logical_writes` (Total Logical Writes)
  - `general|last_execution` (Last Execution)
- **Default sort:** Total Worker Time descending (matches DPA default).
- **Interaction:** selecting a row drives downstream widgets (if the
  author can wire query-level drill; if not, the picker is the only
  driver — acceptable fallback).

### 3. Sessions panel (middle)

#### 3a. Active sessions count tile
- **Widget:** Sparkline / scoreboard / metric tile (whichever the
  factory supports today — author picks).
- **Subject:** the selected `SqlServer`.
- **Metric:** `sysprocesses_states|running` (Process States — Running Processes).
- **Label:** "Currently Active Sessions"

#### 3b. Blocked sessions count tile
- Same widget type as 3a.
- **Metric:** `sysprocesses_states|blocked` (Process States — Blocked Processes).
- **Label:** "Currently Blocked Sessions"
- Optional: red-tint when > 0.

#### 3c. Wait-type drill-down list (below the tiles)
- **Subject:** `microsoft_sql_server_wait_time` resources whose ancestor
  is the selected `SqlServer`.
- **Columns (to verify against describe cache):**
  - Name (wait type — e.g. `PAGEIOLATCH_SH`, `LCK_M_X`)
  - Wait time metric (`general|wait_time` or whatever exists — author resolves)
  - `general|waiting_tasks_count` (Waiting Tasks Count)
- **Default sort:** wait time descending.

### 4. Resources row (bottom — four trend charts)

All trend charts scoped to the selected `SqlServer` unless noted.

#### 4a. CPU %
- **Metric:** `cpu|cpu_usage` on the selected `SqlServer` (process CPU %
  of the SQL Server engine — closest to DPA's "O/S CPU Utilization").
- **Y-axis:** 0–100, %.

#### 4b. Page Life Expectancy
- **Metric:** `buffer|buffer_ideal_page_life_expectancy` (or whichever
  PLE key is collected — author confirms against describe cache).
- **Y-axis:** seconds.

#### 4c. Disk Read Latency (multi-line, per database)
- **Subject:** all `SqlDatabase` resources whose parent is the selected
  `SqlServer`.
- **Metric:** `disk_access|read_delay`.
- **Series:** one line per `SqlDatabase`, labelled by database name.

#### 4d. Disk Write Latency (multi-line, per database)
- Same shape as 4c.
- **Metric:** `disk_access|write_delay`.

## Author notes / cross-references

- **Naming:** dashboard display name `[VCF Content Factory] MSSQL Query
  Performance & Blocking` (RULE-006).
- **Description:** include a one-line note that the disk latency rows
  are per-database and that the wait-type list is the closest available
  proxy for a per-session blocker view.
- **Views needed:** the heatmap widget can render directly off a
  resource-kind subject, but the sortable query list and the wait-type
  list should be authored as named list views under `views/` so they
  can be reused (alerts, reports). The author should decide which
  widgets need a dedicated view vs. inline.
- **Super metrics:** none planned. Every value above is either a
  collected base metric or a resource attribute. If the author finds a
  case that genuinely needs a super metric, return TOOLSET GAP — do not
  invent one silently.
- **Validation gate:** every metric key in the final YAML must exist in
  `knowledge/context/adapter_describe_cache/MSSQL/`. RULE-002 is non-negotiable.
