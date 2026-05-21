# Reports API Surface & Wire Format

## API Endpoints

### Public REST (`operations-api.json`)

| Verb | Path | Purpose |
|---|---|---|
| GET | `/api/reportdefinitions` | List (paged, filterable by name/subject/owner) |
| GET | `/api/reportdefinitions/{id}` | Get one |
| GET/POST/PUT | `/api/reportdefinitions/{id}/schedules` | List/create/update schedules |
| GET/DELETE | `/api/reportdefinitions/{id}/schedules/{scheduleId}` | Get/delete one schedule |
| GET/POST | `/api/reports` | List / generate a report |
| GET/DELETE | `/api/reports/{id}` | Get/delete generated report |
| GET | `/api/reports/{id}/download` | Download rendered PDF or CSV |

**No POST/PUT on `/api/reportdefinitions`.** Report definitions cannot be
created or updated via REST. The only create/update path is content-zip import.

**Internal API:** No relevant report-definition endpoints.

## Wire Format

Report definitions live in `reports.zip` inside the content-zip, containing
a `content.xml`:

```xml
<Content>
  <Reports>
    <ReportDef id="<UUID>">
      <isTenant>false</isTenant>
      <Title>Report Name</Title>
      <Description>Description</Description>
      <SubjectType adapterKind="VMWARE" resourceKind="VirtualMachine"
                   type="self" filter="<html-entity-encoded-JSON>"/>
      <SubjectType adapterKind="VMWARE" resourceKind="VirtualMachine"
                   type="descendant"/>
      <Sections>
        <Section>
          <ContentType>CoverPage</ContentType>
          <ContentKey>COVER_PAGE</ContentKey>
        </Section>
        <Section>
          <ContentType>TableOfContents</ContentType>
          <ContentKey>TABLE_OF_CONTENTS</ContentKey>
        </Section>
        <Section>
          <ContentType>View</ContentType>
          <ContentKey><view-UUID></ContentKey>
          <ContentOrientation>Landscape|Portrait</ContentOrientation>
          <ContentFormatting>
            <ColorizeListView>true|false</ColorizeListView>
          </ContentFormatting>
        </Section>
        <Section>
          <ContentType>Dashboard</ContentType>
          <ContentKey><dashboard-UUID></ContentKey>
          <ContentOrientation>Landscape</ContentOrientation>
        </Section>
      </Sections>
      <Settings>
        <ShowPageFooter>true|false</ShowPageFooter>
        <OutputFormat>pdf</OutputFormat>
        <OutputFormat>csv</OutputFormat>
      </Settings>
    </ReportDef>
  </Reports>
</Content>
```

## Section ContentType Values

| ContentType | ContentKey | Notes |
|---|---|---|
| `CoverPage` | `COVER_PAGE` | Static, no references |
| `TableOfContents` | `TABLE_OF_CONTENTS` | Static, no references |
| `View` | View UUID | References a ViewDef by UUID |
| `Dashboard` | Dashboard UUID | References a dashboard by UUID (stretch goal) |

## Content-Zip Structure

```
outer.zip
+-- <19-digit>L.v1           # marker file
+-- configuration.json       # {"reports": N, "type": "ALL|CUSTOM"}
+-- reports.zip              # nested: content.xml + optional i18n resources/
+-- views.zip                # (if VIEW_DEFINITIONS co-exported)
```

`REPORT_DEFINITIONS` and `REPORT_SCHEDULES` are both valid `contentTypes`
in the export/import enum.

**Alternative format:** Third-party packs ship as a flat `content.xml` zip
containing both `<Views>` and `<Reports>` in one `<Content>` root. The
importer accepts this format too — no marker file or configuration.json needed.

## SubjectType Filter

The `filter` attribute is HTML-entity-encoded JSON, same syntax as view
SubjectType filters:

```json
[[{"filterType":"metrics","metricKey":"reclaimable|cost",
   "condition":"GREATER_THAN","metricValue":{"value":0,"isStringMetric":false}}]]
```

## Report vs Dashboard

| Aspect | Report | Dashboard |
|---|---|---|
| Container | XML `<ReportDef>` in `reports.zip/content.xml` | JSON in `dashboards/<owner>/dashboard/dashboard.json` |
| View reference | `Section/ContentKey` = view UUID | Widget `config.viewDefinitionId` = view UUID |
| Can embed dashboards | Yes (`ContentType=Dashboard`) | No |
| Layout model | Ordered pages (sections) | Spatial grid (widgets) |
| Output | Static PDF/CSV (server-rendered) | Interactive web UI |
| REST CRUD | GET only | None |
| Import path | Content-zip `REPORT_DEFINITIONS` | Content-zip `DASHBOARDS` |

## View Compatibility

All view types (list, distribution, trend) work in reports. Our renderer
already emits `<Usage>report</Usage>` so existing views are report-compatible
without modification. The same view UUID can appear in both a dashboard
widget and a report section.

## Schedules

Schedules are a separate REST resource (not in the report definition XML).
Required fields: `reportDefinitionId`, `resourceId[]`, `recurrence`,
`dayOfTheMonth`, `relativePath[]`, `startDate`. Schedules are exported/imported
as content type `REPORT_SCHEDULES` (separate from `REPORT_DEFINITIONS`).

## Reference Examples

- `references/brockpeterson_operations_reports/` — 5 report+view bundles
- `references/AriaOperationsContent/Cost Reporting/` — dashboard + report + views bundle

## Dependency Chain

```
super metric → view → report
                    → dashboard
```

Same bottom-up authoring pattern as dashboards. Reports and dashboards
are peer consumers of views.
