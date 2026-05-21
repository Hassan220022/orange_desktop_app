---
title: Add AI and MCP query helpers for site and BDT catalogs
label: ready-for-agent
type: AFK
blocked_by: 001-site-metadata-catalog-import.md, 002-bdt-summary-catalog-import.md
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Add AI and MCP query helpers for site and BDT catalogs

## What to build

Add app-level helper functions over the Site Metadata Catalog and BDT Summary Catalog so AI/MCP tools can answer common site, alarm, and BDT questions without relying only on raw SQL. Direct database tables remain available for flexible queries.

## Acceptance criteria

- [ ] Helper can fetch Site Metadata by Site ID.
- [ ] Helper can search sites by common metadata fields.
- [ ] Helper can return site alarm context by Site ID and optional date period.
- [ ] Helper can query BDT Summary rows by Site ID, reporting period, week, or test date.
- [ ] Helpers use normalized Site ID consistently.
- [ ] Tests cover helper behavior against small catalog fixtures.

## Blocked by

- `001-site-metadata-catalog-import.md`
- `002-bdt-summary-catalog-import.md`
