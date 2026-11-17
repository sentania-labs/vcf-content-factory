# vROps Content Management and the Suite-API (summary)

- **Title:** vROps Content Management and the Suite-API
- **Author:** Brock Peterson
- **URL:** https://www.brockpeterson.com/post/vrops-content-management-and-the-suite-api
- **Published:** 2021-12-28 (updated 2025-09-06)
- **Retrieved:** 2026-04-07

This is the factory's summary of a community blog post, not a copy of it.
Read the original at the URL above.

## Summary

Brock Peterson walks through exporting and importing vROps content two
ways: the Content Management page in the UI (added in vROps 8.2 as
all-or-nothing, made selective in 8.6), and the Suite API content
endpoints. He authenticates with a token, posts an export request with a
custom scope (dashboards only in his example), then downloads the
resulting zip, and notes that the same scope mechanism covers views,
reports, outbound settings, integrations and other content types.

## Facts the factory relies on (credit: Brock Peterson)

- The Suite API exposes five content-management endpoints:
  `GET /api/content/operations/export` (last export details),
  `POST /api/content/operations/export` (start an export),
  `GET /api/content/operations/export/zip` (download the latest export),
  `GET /api/content/operations/import` (last import details) and
  `POST /api/content/operations/import` (start an import).
- An export runs asynchronously: post the export, wait for it to finish,
  then fetch the zip.
- The export body takes a scope that selects content types, so a single
  type (for example dashboards) can be exported on its own.
- Export time scales with scope; in his lab a full export took about ten
  minutes and a dashboards-only export about three.

The factory's own, verified description of this surface is in the
`vcfops-api` skill and `knowledge/context/api-surface/`.
