# Visual verification (Playwright pass)

Shared procedure for `qa-tester` and `content-installer` whenever a
verification brief covers UI-rendered content (dashboards, views,
reports). API checks prove content exists and returns data; only a
browser proves it renders. The defect classes only a visual pass
catches: leaked localization keys in the UI (`view.<uuid>.title`
strings), blank or broken widgets on dashboards that "exist" by UUID,
mangled column layouts, error banners.

## Procedure

1. **Probe for the Playwright MCP tools** via ToolSearch
   (`select:mcp__playwright__browser_navigate`; if the schema loads,
   the server is available).
2. **If available**: log into the instance UI (flow:
   `knowledge/context/api-surface/dashboard_delete_api.md`,
   self-signed cert expected), open each installed dashboard, one
   representative view per resource kind, and each report definition.
   Screenshot each to files and list the paths in the report. Verdict
   per surface: LOOKS RIGHT or VISUAL DEFECT (described). Never edit
   or save anything in the UI; navigate and look only.
3. **If unavailable**: do NOT silently skip. The report MUST carry a
   verbatim block:

   ```
   VISUAL VERIFICATION: SKIPPED
   Playwright MCP is not configured. Rendering defects are invisible
   to API-level checks. Enable via:
     claude mcp add playwright -- npx @playwright/mcp@latest
   ```

   This notice repeats on EVERY skipped run by design; the user asked
   to be reminded periodically, and the recurring block is the
   reminder.

## Judge layout quality, not just presence

A widget that renders data can still be a VISUAL DEFECT. For each
screenshot, check:

- **Widget sizing**: is content clipped, truncated, or scrollbarred
  inside the widget? Scoreboard/stat tiles must show the value, unit,
  and title comfortably; a cramped tile is a defect (lesson learned
  2026-07-27: h:2 scoreboards shipped and the user had to catch it).
- **Proportion**: no large dead space inside widgets; row heights fit
  their content.
- **Tables/views**: column headers readable, no mangled columns.

Report sizing verdicts explicitly: "renders" without a layout
judgment is an incomplete visual pass.
