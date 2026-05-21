---
title: HT Alarm Workbook Reference Export
label: ready-for-agent
created: 2026-05-21
---

# HT Alarm Workbook Reference Export PRD

## Problem Statement

Users need the app to export HT Alarm Workbooks that match the existing Excel reference workbook exactly in behavior, content, layout, styling, and naming. The current export mixes the app's timestamp-based Power-Coverage Gap analysis with the Reference Workbook's daily HT-vs-Power Meet logic, duplicates the Weekly Summary into `Consolidated`, misses Site Metadata from Network Summary, and ignores most BDT Summary Workbook data that should be queryable by AI/MCP and available to BDT workflows.

## Solution

Build a Reference Workbook-compatible HT Alarm Workbook export path. The app will use the Reference Workbook as the source of truth for sheet structure and logic, use explicit Export Week selection, compute Meet Sheet rows using same-site same-day HT and Power duration totals with a fixed seven-hour threshold, summarize from Meet rows, recompute Consolidated History from raw alarm data over a configured historical period, and enrich workbook output with Site Metadata keyed by stable Site ID.

The app will also import and store two workbook-backed catalogs in both databases: the Network Summary Site Metadata Catalog and the BDT Summary Catalog. Both catalogs are keyed by Site ID and are available for exports, BDT workflows, AI, and MCP queries.

## User Stories

1. As an alarm reporting user, I want to export `2024-HT-Alarms-W27.xlsx`, so that the workbook filename follows the approved reporting convention.
2. As an alarm reporting user, I want to select the Export Week explicitly, so that the workbook does not silently choose the wrong week.
3. As an alarm reporting user, I want the Export Week date range shown, so that I can confirm the Sunday-start period before exporting.
4. As an alarm reporting user, I want `W27 AUTIN HT` to contain weekly raw HT alarms, so that the workbook matches the reference raw HT sheet.
5. As an alarm reporting user, I want `W27 AUTIN Power` to contain weekly raw Power alarms, so that the workbook matches the reference raw Power sheet.
6. As an alarm reporting user, I want `W27 AUTIN HT Study` to contain the same helper fields and Meet calculation as the Reference Workbook, so that downstream sheets are traceable.
7. As an alarm reporting user, I want `Meet` to contain only rows where same-site same-day HT duration exceeds Power duration by more than seven hours or Power duration is unavailable, so that the workbook matches the established report logic.
8. As an alarm reporting user, I want the Meet threshold fixed at seven hours, so that exported workbooks remain compatible with the reference report.
9. As an alarm reporting user, I want the UI preview to show Meet Sheet rows, so that what I see matches what I export.
10. As an alarm reporting user, I want the Weekly Summary to summarize Meet rows by site, so that `W27` matches the Reference Workbook summary behavior.
11. As an alarm reporting user, I want `Consolidated` to contain historical weekly summary rows, so that I can see long-term HT history in the same workbook.
12. As an alarm reporting user, I want Consolidated History recomputed from raw alarm data over a configured historical range, so that I do not need to upload old HT workbooks.
13. As an alarm reporting user, I want week labels like `W27-24` to use the Reference Workbook week rule, so that sheet names and summary rows match the existing reports.
14. As an alarm reporting user, I want rolling week marker columns to show whether a site appeared in recent weeks, so that recurring HT problem sites are visible.
15. As an alarm reporting user, I want Site Metadata joined by stable Site ID, so that area, subcontractor, battery type, and backup status are present in summaries.
16. As an alarm reporting user, I want missing Site Metadata to be non-blocking, so that exports can continue even when metadata is incomplete.
17. As an alarm reporting user, I want missing Site IDs reported in the workbook and warning UI, so that metadata gaps can be fixed later.
18. As an alarm reporting user, I want the workbook to keep the Reference Workbook's six visible sheets when no metadata is missing, so that standard output stays clean.
19. As an app operator, I want to import Network Summary `DB` sheet data, so that Site Metadata Catalog is available for exports and AI/MCP queries.
20. As an app operator, I want Network Summary imports to replace both database copies all-or-nothing, so that DuckDB and SQLite do not diverge.
21. As an app operator, I want Network Summary columns normalized but traceable to original headers, so that code can query clean names while preserving source context.
22. As an app operator, I want all Network Summary columns stored, so that AI/MCP can answer broad site questions.
23. As a BDT user, I want Huawei BDT Summary Workbook rows stored from all sheets, so that BDT history is available beyond one validation run.
24. As a BDT user, I want BDT Summary Catalog merged by reporting period, so that importing one workbook updates relevant periods without deleting absent periods.
25. As an AI/MCP user, I want Site Metadata Catalog and BDT Summary Catalog accessible through database tables and helper functions, so that I can ask questions using Site ID as the connection key.
26. As an AI/MCP user, I want ad-hoc historical HT queries to ask for from/to dates when needed, so that query scope is explicit.
27. As a developer, I want Power-Coverage Gap analysis kept separate from HT Alarm Workbook export logic, so that Y margin does not corrupt the Reference Workbook export.
28. As a developer, I want tests to validate behavior against Reference Workbook observations, so that refactors do not drift from the expected report.

## Implementation Decisions

- The Reference Workbook is the source of truth for HT Alarm Workbook behavior, not the current timestamp-overlap export implementation.
- HT Workbook Week Labels use the Sunday-based `%U + 1` rule, not ISO weeks.
- Export Week is explicit and maps to Sunday 00:00 inclusive through the next Sunday 00:00 exclusive.
- The exported filename format is `{year}-HT-Alarms-W{week_number}.xlsx`.
- The HT Alarm Workbook UI previews Meet Sheet rows and exports the full Reference Workbook-compatible workbook.
- The current Power-Coverage Gap analysis remains a separate concept. Y margin belongs there, not to HT Alarm Workbook Meet logic.
- Meet Sheet rows are derived from HT Study rows where same-site same-day HT duration minus same-site same-day Power duration is greater than seven hours, or same-site same-day Power duration is unavailable.
- The seven-hour Meet threshold is fixed.
- Weekly Summary rows are built from Meet Sheet rows for the selected Export Week.
- Consolidated History is recomputed from raw alarm data from a configurable historical start week/date, defaulting to `W40-22`.
- Rolling Week Marker columns are based on the current Export Week's eight-week window.
- Site ID is the canonical stable key connecting alarms, Network Summary metadata, BDT records, weekly summaries, and AI/MCP query context.
- Site Metadata Catalog stores all columns from the Network Summary `DB` sheet in both DuckDB and SQLite. Network Summary workbook imports replace both database copies all-or-nothing.
- Site Metadata Catalog uses normalized query-friendly field names and preserves original header mapping.
- Alarm enrichment matches exact normalized Site ID first, parses Site ID from alarm source only as fallback, and never fuzzy matches.
- Missing Site Metadata leaves enrichment-only fields blank and produces non-blocking warning output plus a `Missing Metadata` sheet only when needed.
- BDT Summary Catalog stores all rows and columns from every sheet in selected BDT Summary Workbooks in both DuckDB and SQLite.
- BDT Summary Catalog imports merge by reporting period: imported periods replace matching existing periods, while periods not present in the import remain.
- For yearly BDT summary sheets, source sheet name is the sheet/reporting-period key; row-level week, test date, and test year are stored for querying.
- AI/MCP access should support direct database queries and app-level helper functions such as site metadata lookup, site search, site alarm context, and BDT summary queries.

## Testing Decisions

- Tests should verify observable workbook behavior through public export/build interfaces, not private helper internals.
- Reference-workbook-derived expectations should be encoded as behavior tests: sheet names, visible columns, row derivation, week labels, summary source, and fixed Meet threshold.
- Site Metadata Catalog tests should import a small workbook fixture into both database backends and verify all-or-nothing replacement behavior plus normalized/original header preservation.
- BDT Summary Catalog tests should import a fixture with multiple variable sheet names and verify merge-by-reporting-period behavior.
- HT workbook export tests should use small DataFrame fixtures and workbook inspection via openpyxl to verify formulas/values, sheet order, and summary output.
- Existing `tests/test_temp_alarm.py` provides prior art for core HT alarm computations and workbook assertions.
- Existing BDT export/parser tests provide prior art for workbook-driven BDT summary behavior.

## Out of Scope

- Remote GitHub issue publishing for this planning pass.
- Full main Alarm page metadata filtering by area/subcontractor/backup status. The data model should allow it later, but first implementation focuses on HT export and AI/MCP query access.
- Changing the Reference Workbook's seven-hour Meet threshold.
- Replacing Power-Coverage Gap analysis entirely. It remains separate and may become its own UI/tool later.
- User upload/import of the HT Reference Workbook during normal app use.

## Further Notes

- Relevant ADRs: `0001-ht-workbook-week-labels-follow-reference-workbook` and `0002-reference-workbook-is-ht-export-source-of-truth`.
- The Obsidian note `HT Alarm Workbook Reverse Engineering` mirrors the current domain decisions.
- Current app export incorrectly duplicates Weekly Summary into `Consolidated`; this PRD replaces that behavior.
