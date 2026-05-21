---
title: Replace HT export UI with Meet preview and Export Week controls
label: ready-for-agent
type: AFK
blocked_by: 003-export-week-and-filename.md, 004-meet-sheet-engine.md, 007-site-metadata-enrichment-and-warnings.md
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Replace HT export UI with Meet preview and Export Week controls

## What to build

Update the HT/temp export UI so the visible table previews Meet Sheet rows, not Power-Coverage Gap rows. The UI exposes an Export Week selector, date range display, Site Metadata filters, summary counts, export controls, and missing-metadata warnings. Y margin is removed from this UI because it belongs only to Power-Coverage Gap analysis.

## Acceptance criteria

- [ ] UI title and behavior reflect HT Alarm Workbook Meet preview/export.
- [ ] User selects Export Week explicitly and sees the corresponding Sunday-start date range.
- [ ] Preview table uses the Reference Workbook Meet Sheet's visible columns.
- [ ] Preview rows match the rows exported to the Meet sheet.
- [ ] Site Metadata filters can filter preview rows by supported metadata fields.
- [ ] Missing metadata warnings are visible and non-blocking.
- [ ] Y margin is not shown or used in HT Alarm Workbook export UI.
- [ ] Tests cover preview/export consistency at the dialog/thread boundary where practical.

## Blocked by

- `003-export-week-and-filename.md`
- `004-meet-sheet-engine.md`
- `007-site-metadata-enrichment-and-warnings.md`
