# Dashboard: Summary Widget Smoke (HostSystem)

## Initial prompt

Framework gate, not a user request: this branch
added Section, Alert Volume, gauge Scoreboard, `view_details`, and
`summary_for` with `bind-summary`. Each must round-trip through a live
import and the Summary-tab bind before the branch ships.

## Vision

A five-widget dashboard on `VMWARE:HostSystem` that uses every new
widget type once, declared as a summary dashboard, installed on a
disposable build, bound, verified with `getSummaryTabId`, then unbound
and deleted. Never released (`released: false`), never bundled.

Mock (RULE-011): `summary-widget-smoke.html` beside this file. Values
simulated; keys verified against
`knowledge/context/adapter_describe_cache/VMWARE/HostSystem.json`.

Name: `[VCF Content Factory] Summary Widget Smoke (HostSystem)`.
`summary_for: "VMWARE:HostSystem"`. Every widget `self_provider: false`.

## Layout (12-column grid)

| Row | Col span | Widget | Type | Subject / keys | Notes |
|---|---|---|---|---|---|
| 1 | 1-12 | Host Summary Smoke | Section (`collapsed: false`) | | Children: every widget below (rows 2 and 3). x must be 1. |
| 2 | 1-4 | Host Facts | PropertyList, compact | properties `summary\|version`, `sys\|build`, `hardware\|vendorModel`, `hardware\|cpuInfo\|numCpuCores` | |
| 2 | 5-9 | Alerts Summary | AlertVolume | (page object) | No options exist; fixed 7-day window. |
| 2 | 10-12 | More | TextDisplay | static text | `view_details: /ui/operate/dashboards/dashboards` (static route, no placeholders). |
| 3 | 1-7 | Utilization | Scoreboard, `visual_theme: 9`, `max_value: 100` | `cpu\|usage_average`, `mem\|usage_average` | bounds 70 / 85; `show_percent_text: true`. |
| 3 | 8-12 | Alerts | Scoreboard, `visual_theme: 8` | `System Attributes\|alert_count_critical`, `alert_count_warning` | |

## Interaction wiring

None. Everything inherits the page object.

## Constraints

- `summary_for` requires `self_provider: false` everywhere and no pinned
  resources (validated by the loader).
- Section row rule: no other widget on row 1.
- Test target: a disposable lab build (`qa` or `main` profiles), admin
  account. Bind replaces the native HostSystem summary page on that
  build only; `bind-summary --unbind` restores it, then the dashboard is
  deleted.

## Acceptance (content-installer, then qa-tester)

1. `sync` imports with `imported=1`; `isLoading: false` after materialization.
2. `getWidgetConfigs` shows: Section with the five child ids; `IntSummaryAlertVolume` with `selfProvider: false`; Scoreboard theme 9 with `maxValue: 100` and the gauge switches; TextDisplay `viewDetails` equal to the route.
3. `bind-summary --dry-run` prints `002006VMWAREHostSystem`; `bind-summary` prints `LIVE tabId` and the template UUID; `getSummaryTabId` for a HostSystem returns that tabId with `isDashboard: true`.
4. Browser pass (Playwright if available): the Summary tab of one host renders all five widgets; VIEW DETAILS navigates to the dashboards list.
5. `bind-summary --unbind` restores the default; template deleted; dashboard deleted; `getSummaryTabId` returns null.

## Approval

Approved by Scott, 2026-08-25 (mock and table), for install on the `qa` lab build.
