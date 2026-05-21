---
title: HT Alarm Workbook Reference Export TDD Plan
label: ready-for-agent
created: 2026-05-21
prd: ../prds/ht-alarm-workbook-reference-export.md
---

# HT Alarm Workbook Reference Export TDD Plan

## TDD Rules For This Work

- One behavior test at a time.
- Red → green per vertical slice; do not write all tests upfront.
- Tests verify public behavior through import/export/query functions and generated workbooks.
- Avoid private-helper coupling unless the helper is deliberately introduced as a public deep module interface.
- Keep workbook fixtures small but representative.

## Proposed Deep Module Interfaces

These names are descriptive, not mandatory. Keep interfaces small and behavior-rich.

1. **Site Metadata Catalog importer**
   - Input: Network Summary workbook path.
   - Output: import result with row count, source columns, missing/invalid keys.
   - Side effect: replaces Site Metadata Catalog in both databases all-or-nothing.

2. **BDT Summary Catalog importer**
   - Input: BDT Summary Workbook path.
   - Output: import result with sheets/periods imported and rows replaced.
   - Side effect: merges catalog periods in both databases.

3. **HT Export Week value object/service**
   - Input: date or selected week.
   - Output: full week label, short week label, Sunday-start range, filename.

4. **HT Meet engine**
   - Input: weekly HT rows and weekly/same-period Power rows.
   - Output: HT Study rows and Meet rows using Reference Workbook logic.

5. **HT workbook export service**
   - Input: Export Week, alarm source/query, Site Metadata Catalog, historical start.
   - Output: workbook file plus warning/report metadata.

6. **Catalog query helpers**
   - Input: Site ID/search filters/date period.
   - Output: site metadata, BDT summary rows, site alarm context.

## Slice 001 — Site Metadata Catalog Import

### Cycle 1

RED: Import a tiny Network Summary workbook with `DB` sheet and two rows; assert both databases expose rows by normalized Site ID.

GREEN: Add minimal importer and storage table(s) to pass.

### Cycle 2

RED: Import workbook with weird headers/spaces and assert normalized field names plus original header mapping are preserved.

GREEN: Add header normalization and mapping storage.

### Cycle 3

RED: Import workbook missing `Code`; assert import fails and existing catalog remains unchanged.

GREEN: Add validation before replacement.

### Cycle 4

RED: Simulate second database write failure; assert neither database is partially updated.

GREEN: Add temp-table/swap or rollback strategy.

### Refactor

- Extract shared workbook-to-normalized-frame logic if BDT Summary importer needs same behavior.
- Keep DB-specific write code behind small repository interfaces.

## Slice 002 — BDT Summary Catalog Import

### Cycle 1

RED: Import a BDT Summary workbook with one sheet; assert rows are queryable by Site ID and source sheet/reporting period.

GREEN: Add minimal BDT Summary Catalog importer.

### Cycle 2

RED: Import workbook with three sheets; assert every sheet is imported, regardless of name pattern.

GREEN: Iterate all sheets and store source sheet name.

### Cycle 3

RED: Import a later workbook containing one existing period and one new period; assert the existing period is replaced and absent periods remain.

GREEN: Add merge-by-reporting-period replacement.

### Cycle 4

RED: Assert row-level week, test date, and test year are extracted where available across variant headers.

GREEN: Add tolerant field extraction.

### Refactor

- Share normalized header handling with Site Metadata Catalog importer.

## Slice 003 — Export Week and Filename

### Cycle 1

RED: Given date `2024-06-30`, assert full label `W27-24`, short label `W27`, and Sunday-start range.

GREEN: Add Reference Workbook week label calculation.

### Cycle 2

RED: Given Export Week `W27-24`, assert filename `2024-HT-Alarms-W27.xlsx`.

GREEN: Add filename generation.

### Cycle 3

RED: Add boundary date tests around Saturday/Sunday transitions.

GREEN: Tighten range calculation.

### Refactor

- Centralize HT week math so summary, consolidated, and workbook writer cannot drift.

## Slice 004 — Meet Sheet Engine

### Cycle 1

RED: HT daily total 8h and Power daily total unavailable produces Meet row.

GREEN: Add minimal daily grouping and unavailable-Power Meet rule.

### Cycle 2

RED: HT 8h, Power 0h 59m produces Meet row because Diff > 7h.

GREEN: Add Diff threshold rule.

### Cycle 3

RED: HT 8h, Power 1h produces no Meet row because Diff == 7h.

GREEN: Make threshold strict greater-than.

### Cycle 4

RED: Multiple HT rows same Site ID/day share same HT daily total, matching Reference Workbook Support/Day behavior.

GREEN: Add same-site same-day totals.

### Cycle 5

RED: Meet row output exposes exactly the nine Reference Workbook visible columns.

GREEN: Add row projection.

### Refactor

- Keep HT Study row production separate from Meet projection.
- Use duration conversions already established in core code.

## Slice 005 — Reference Workbook Writer

### Cycle 1

RED: Generate tiny workbook and assert sheet order/names for Export Week.

GREEN: Wire workbook writer to Export Week and Meet engine.

### Cycle 2

RED: Assert raw HT/Power sheets include only occurrence timestamps inside Export Week.

GREEN: Add weekly raw scoping.

### Cycle 3

RED: Assert HT Study headers and selected helper columns match Reference Workbook.

GREEN: Add HT Study worksheet output.

### Cycle 4

RED: Assert Meet sheet headers and rows match Meet engine projection.

GREEN: Add Meet sheet output.

### Cycle 5

RED: Assert key styles/widths/autofilters match stable Reference Workbook expectations.

GREEN: Add or adjust formatting.

### Refactor

- Remove old write-only shortcuts only if they block exact layout/styling.

## Slice 006 — Weekly Summary and Consolidated

### Cycle 1

RED: Given Meet rows for one week and two sites, assert Weekly Summary counts/durations per Site ID.

GREEN: Add Meet-derived Weekly Summary builder.

### Cycle 2

RED: Given multiple historical weeks, assert Consolidated contains rows for each week and Weekly Summary only selected week.

GREEN: Add historical recompute path.

### Cycle 3

RED: Assert rolling marker columns use current Export Week eight-week window.

GREEN: Add rolling marker calculation.

### Cycle 4

RED: Assert historical start defaults to W40-22 and can be configured.

GREEN: Add setting/config read path.

### Refactor

- Keep summary logic independent from workbook writing.

## Slice 007 — Site Metadata Enrichment and Warnings

### Cycle 1

RED: Generated Weekly Summary row includes metadata from Site Metadata Catalog by exact normalized Site ID.

GREEN: Add metadata lookup into export flow.

### Cycle 2

RED: Alarm row with missing Site ID but parseable alarm source enriches from parsed Site ID.

GREEN: Add alarm-source fallback parser.

### Cycle 3

RED: Unmatched Site ID leaves enrichment blank but export succeeds and reports missing Site ID.

GREEN: Add warning result.

### Cycle 4

RED: Missing metadata creates `Missing Metadata` sheet; no missing metadata keeps six visible sheets.

GREEN: Add conditional sheet.

### Refactor

- Keep missing-metadata collection reusable by UI and workbook writer.

## Slice 008 — HT Workbook UI Preview and Export

### Cycle 1

RED: Dialog/thread preview result contains Meet rows, not Power-Coverage Gap rows.

GREEN: Route preview to Meet engine.

### Cycle 2

RED: Export Week control updates displayed Sunday-start date range.

GREEN: Add Export Week UI state.

### Cycle 3

RED: Export action writes workbook whose Meet rows equal preview rows.

GREEN: Wire export service to UI.

### Cycle 4

RED: Missing metadata warning appears non-blocking.

GREEN: Surface warning result.

### Cycle 5

RED: Y margin does not affect HT Alarm Workbook preview/export.

GREEN: Remove Y margin from this UI path.

### Refactor

- Preserve separate Power-Coverage Gap logic for future tool extraction.

## Slice 009 — AI/MCP Query Helpers

### Cycle 1

RED: Fetch Site Metadata by Site ID from imported catalog.

GREEN: Add helper.

### Cycle 2

RED: Search sites by area/subcontractor/backup status.

GREEN: Add search helper.

### Cycle 3

RED: Query BDT Summary rows by Site ID and period.

GREEN: Add BDT query helper.

### Cycle 4

RED: Query site alarm context for Site ID and date period.

GREEN: Add alarm context helper using existing alarm DB.

### Refactor

- Keep helper outputs stable and serializable for MCP/AI tools.

## Slice 010 — Reference Validation Suite

### Cycle 1

RED: Fixture-based test encodes Reference Workbook sheet order/headers.

GREEN: Add validation assertions.

### Cycle 2

RED: Test asserts Meet rows are HT Study rows with Meet decision.

GREEN: Reuse Meet engine expectations.

### Cycle 3

RED: Test asserts Weekly Summary and Consolidated are not duplicates when history spans weeks.

GREEN: Add consolidated fixture.

### Cycle 4

RED: Test asserts missing metadata sheet conditional behavior.

GREEN: Add workbook inspection helper.

### Refactor

- Keep validation fixtures small and documented.

## First Implementation Order

1. `003-export-week-and-filename`
2. `004-meet-sheet-engine`
3. `005-reference-workbook-writer`
4. `006-weekly-summary-and-consolidated`
5. `001-site-metadata-catalog-import`
6. `007-site-metadata-enrichment-and-warnings`
7. `008-ht-workbook-ui-preview-and-export`
8. `002-bdt-summary-catalog-import`
9. `009-ai-mcp-query-helpers`
10. `010-reference-validation-suite`

The order starts with the smallest Reference Workbook-compatible HT export path, then metadata enrichment, then UI and broader catalogs.
