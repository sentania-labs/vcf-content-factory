# Oracle Query Performance & Blocking Dashboard

Slug: `oracle-query-performance`
Adapter: `OracleDBAdapter` (Oracle Database adapter)
Primary object: `oracle_database_oracle_database_instance`

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

(See `tmp/sql.png` for the Solarwinds DPA reference screenshot. Layout
described in `mssql-query-performance.md`. This Oracle dashboard is the
direct counterpart of the MSSQL one with Oracle-specific objects and
metrics substituted.)

## Vision

Same three-stripe layout as the MSSQL dashboard — pick one Oracle
database instance, triage query performance and blocking on it. The
Oracle adapter has a much richer wait-event taxonomy than MSSQL, so the
"Sessions" drill-down is more useful here (Oracle DBAs typically think
in wait-event groups).

### Confirmed user choices (don't relitigate)

- **Scope:** Oracle database-instance picker at the top drives every
  other widget. No fleet section.
- **Queries panel:** heatmap + sortable list view of
  `oracle_database_oracle_database_query` resources scoped to the
  picked instance.
- **Sessions panel:** active + blocked count tiles, drill-down by wait
  event group.
- **Bottom resources row:** Host CPU %, Buffer Cache Hit Ratio,
  Disk Read Latency, Disk Write Latency.

### Constraints surfaced by ops-recon (binding)

1. **`Performance|` metric group is currently NOT collected on the live
   instance.** User has agreed to enable it in the Oracle collection
   policy: *Policies → Oracle DB policy → Object Types → Oracle
   Database Instance → enable `Performance` group metrics.* Until that
   is done, the Host CPU and Buffer Cache widgets will be empty. The
   dashboard is authored assuming the policy is enabled — the metric
   keys ARE declared in the adapter describe, so validation will pass
   and widgets will populate as soon as collection starts.

2. **No per-session resource exists.** Same constraint as the MSSQL
   side. The drill-down behind the count tiles uses
   `oracle_database_oracle_database_event_wait_group` resources — a
   wait-event-category breakdown. The user explicitly accepted this.

3. **No Oracle reference dashboard exists** in any allowlisted
   reference repo. Layout pattern can borrow from the MSSQL
   brockpeterson reference; metric keys must come exclusively from
   `knowledge/context/adapter_describe_cache/ORACLE/`.

## Panel-by-panel spec

All widgets except the picker have an Interaction set so that the
picker (and the queries list) drive them.

### 1. Instance picker (top)
- **Widget:** ResourceList / equivalent.
- **Subject:** `oracle_database_oracle_database_instance`.
- **Behavior:** selection broadcasts to all downstream widgets.

### 2. Queries panel

#### 2a. Heatmap
- **Subject:** `oracle_database_oracle_database_query` whose ancestor
  is the selected instance.
- **Color metric:** `Activity|elapsed_time` (Oracle's "wall clock" cost
  metric — equivalent to DPA's "total execution time" axis).
- **Size metric:** `Activity|executions`.

#### 2b. Sortable list view
- **Subject:** `oracle_database_oracle_database_query` (same scope).
- **Columns (all verified in describe cache):**
  - Name (query name — usually SQL_ID or text fragment)
  - `Activity|elapsed_time` (Elapsed Time)
  - `Activity|cpu_time` (CPU Time)
  - `Activity|executions` (Executions)
  - `Activity|user_io_wait_time` (User I/O Wait Time)
  - `Activity|application_wait_time` (Application Wait Time)
  - `Activity|concurrency_wait_time` (Concurrency Wait Time — this is
    the column that lights up for blocking)
  - `Activity|disk_reads` (Disk Reads)
- **Default sort:** Elapsed Time descending.

### 3. Sessions panel

#### 3a. Active sessions count tile
- **Subject:** selected Oracle instance.
- **Metric (author to confirm exact key against describe):** an active-
  session count from the `Session|` group. Candidates the author should
  pick from in priority order (use the first that exists in the
  describe cache):
  1. `Session|active_user_sessions`
  2. `Session|unblocked_user_sessions` (collected, recon confirmed)
  3. `Session|user_sessions` minus `Session|inactive_user_sessions`
     (super metric — only if neither of the above is available; if it
     comes to this, return TOOLSET GAP / propose a super metric).
- **Label:** "Currently Active Sessions"

#### 3b. Blocked sessions count tile
- **Subject:** selected Oracle instance.
- **Metric:** `Session|blocked_user_sessions` (recon confirmed collected).
- **Label:** "Currently Blocked Sessions"
- Optional: red-tint when > 0.

#### 3c. Wait-event-group drill-down list (below tiles)
- **Subject:** `oracle_database_oracle_database_event_wait_group`
  resources whose ancestor is the selected instance.
- **Columns:**
  - Name (wait group — e.g. `User I/O`, `Concurrency`, `Cluster`,
    `Application`)
  - `Activity|time_waited` (Time Waited)
  - `Activity|total_waits` (Total Waits)
- **Default sort:** Time Waited descending.

### 4. Resources row (bottom — four trend charts)

All scoped to the selected Oracle instance.

#### 4a. Host CPU %
- **Metric:** `Performance|host_cpu_utilization`.
- **Y-axis:** 0–100, %.
- **Note:** depends on `Performance|` group being enabled in policy
  (see Constraint 1).

#### 4b. Buffer Cache Hit Ratio
- **Metric:** `Performance|buffer_cache_hit_ratio` (verify exact key
  against describe — may be `Performance|buffer_cache_hit_pct` etc.).
- **Y-axis:** 0–100, %.
- **Note:** same `Performance|` group dependency.

#### 4c. Disk Read Latency
- **Metric:** `Disk IO|average_read_time` on the selected instance
  (verified in describe).
- **Y-axis:** time units as declared.

#### 4d. Disk Write Latency
- **Metric:** `Disk IO|average_write_time` (verified in describe).

## Author notes / cross-references

- **Naming:** dashboard display name `[VCF Content Factory] Oracle Query
  Performance & Blocking` (RULE-006).
- **Description:** mention the `Performance|` policy dependency
  explicitly in the dashboard description so a future user who sees
  empty Host CPU / Buffer Cache widgets knows where to look.
- **Views needed:** sortable query list and wait-group list as named
  views under `views/` (reusable). Author decides whether the heatmap
  needs its own view.
- **Super metrics:** none planned. If the active-session count requires
  a derived value (option 3 under panel 3a), return TOOLSET GAP — do
  not invent silently.
- **Validation gate:** every metric key in the final YAML must exist in
  `knowledge/context/adapter_describe_cache/ORACLE/`. RULE-002 is non-negotiable.
