# Alarm Reporting

This context defines the language used for alarm analysis workbooks and weekly high-temperature alarm reporting.

## Language

**HT Alarm Workbook**:
An Excel workbook for a single export week that includes raw HT alarms, raw Power alarms, HT-vs-Power study rows, meeting rows, a weekly summary, and consolidated history.
_Avoid_: Temp export, uncovered export
The exported workbook filename follows the pattern `{year}-HT-Alarms-W{week_number}.xlsx`, for example `2024-HT-Alarms-W27.xlsx`.
Exporting this workbook follows the Reference Workbook's daily SUMIFS-style Meet logic, not the Power-Coverage Gap timestamp-overlap logic.
The HT/temp export UI previews Meet Sheet rows so the visible table and exported HT Alarm Workbook use the same logic.
The HT Alarm Workbook UI should include an Export Week selector, date range display, Site Metadata filters such as site/area/subcontractor, a Meet Sheet preview table, export controls, summary counts, and missing-metadata warnings. Preview and export should follow the Reference Workbook as source of truth; if the Reference Workbook's visible Meet Sheet has nine columns, the primary preview uses those nine columns.

**Power-Coverage Gap**:
A Temp alarm occurrence that is not covered by a same-site Power alarm timestamp window plus the configured Y margin. This is a timestamp-overlap analysis concept and is distinct from the HT Alarm Workbook's Meet Sheet logic.
_Avoid_: Meet row, HT workbook row
The user-facing name for this analysis is “Temp Alarms Outside Power Coverage.”
Y margin belongs to Power-Coverage Gap analysis, not HT Alarm Workbook Meet logic.

**Reference Workbook**:
An existing HT Alarm Workbook used as the authority for expected content, sheet layout, formulas, styling, and export behavior.
_Avoid_: Template, sample file
The user does not upload the Reference Workbook during normal app use; it is a developer validation and reverse-engineering artifact.
When workbook behavior is unclear, the Reference Workbook is the source of truth and implementation should match its observed behavior rather than inventing new rules.

**Network Summary DB Sheet**:
The `DB` sheet in the Network Summary workbook. It is the site metadata source for area, subcontractor, site name, battery type, and backup status used to enrich alarm reporting.
_Avoid_: BDT summary, alarm database

**BDT Summary Workbook**:
A Huawei BDT summary workbook with yearly summary sheets. It contains BDT report rows keyed by **Site ID** and test/week information, including site, network, battery, rectifier, discharge, severity, engineer, and comment fields.
_Avoid_: Network Summary DB Sheet, HT Alarm Workbook

**BDT Summary Catalog**:
The stored collection of all rows and columns from yearly BDT Summary Workbook sheets. It is keyed by **Site ID** plus BDT time/report identity such as test date and week, and is used for BDT workflows, exports, AI, and MCP queries.
_Avoid_: Site Metadata Catalog, Network Summary

The catalog is stored in both the alarm analytics database and the app database. Every sheet in a BDT Summary Workbook is considered a BDT summary sheet; sheets differ by export year or reporting period. Workbooks may contain one, two, three, or more sheets, and sheet count/year coverage are not fixed.
Importing a BDT Summary Workbook merges by reporting period: rows for periods present in the imported workbook replace existing rows for those periods, while existing periods not present in the workbook remain in the catalog. Reporting period identity depends on the summary/data type; for yearly BDT summary sheets, the source sheet name is preserved as the sheet/reporting-period key, while row-level week, test date, and test year are also stored for querying.

**Site ID**:
The canonical, stable site key used to connect alarms, Network Summary metadata, BDT records, weekly summaries, and consolidated history. It corresponds to the Network Summary `Code` value and the alarm data `site_id` value after normalization, and it does not change over time.
_Avoid_: Short Code, Site Code, Rectifier Code as separate identities

**Site Metadata**:
Descriptive site attributes keyed by **Site ID**, including site name, Orange area, subcontractor, battery type, backup status, office, site type, and power source. When the Network Summary has multiple rectifier rows for one **Site ID**, site-level attributes come from the primary rectifier row, while battery attributes may combine distinct values across rectifiers.
_Avoid_: Alarm fields, BDT-only fields

**Site Metadata Catalog**:
The searchable collection of all Network Summary `DB` sheet columns keyed by **Site ID**. It is used both for HT Alarm Workbook enrichment and for answering site questions through AI or MCP tooling, with exports and other services joining to it on demand.
_Avoid_: Export-only metadata, hidden lookup

The catalog is stored in both the alarm analytics database and the app database so alarm workflows, BDT workflows, AI, and MCP queries can all access it without treating it as export-only data. The Network Summary workbook is the source of truth; imports replace both database copies from the same workbook.
Imports are all-or-nothing across both database copies; partial Site Metadata Catalog updates are invalid.
The catalog uses normalized query-friendly field names while preserving a mapping back to the original Network Summary column headers.
Initial use is HT Alarm Workbook enrichment and AI/MCP querying. Main Alarm page metadata filters are a later enhancement.
The catalog should be accessible both as database tables for flexible queries and through app-level helper functions for common site lookups, site searches, and site alarm context.
Alarm enrichment uses exact normalized **Site ID** matches first. If an alarm row has missing or invalid **Site ID**, the app may parse a **Site ID** from the alarm source as a fallback. Fuzzy matching is not valid for enrichment.
When no **Site Metadata** match exists, alarm-derived identifiers remain in the workbook and enrichment-only fields stay blank.
Missing **Site Metadata** matches are non-blocking data-quality issues. The user should be warned and given the missing **Site ID** values, but exports may continue.
When missing metadata occurs during HT Alarm Workbook export, the user sees a non-blocking warning and the workbook includes a `Missing Metadata` sheet with the affected **Site ID** values. When no metadata is missing, the workbook keeps the Reference Workbook's six visible sheets.

**Rectifier Metadata**:
Additional Network Summary data for a rectifier at a **Site ID**, including rectifier number and rectifier code. It supports BDT work, AI/MCP questions, and detailed queries, but it does not replace **Site ID** as the canonical connection key.
_Avoid_: Site ID replacement, primary site key

**Rectifier Code**:
The Network Summary identifier for a specific rectifier row at a **Site ID**, such as `0001AL2`. It may also be called rectifier ID in discussion, but **Rectifier Code** is the canonical term.
_Avoid_: Treating it as the site key

**Weekly Summary**:
A report sheet for one export week only. Each row summarizes one site for that week.
_Avoid_: Consolidated, history
Weekly Summary rows are summarized from Meet Sheet rows, matching the Reference Workbook.

**Consolidated History**:
A long-term ledger of weekly HT summary rows across many weeks. It includes historical rows plus the current export week.
_Avoid_: Current week summary, duplicate weekly sheet

Consolidated History for HT Alarm Workbooks is recomputed from raw alarm data in the alarm database when exporting, instead of relying on user-uploaded HT workbooks. Recompute uses a configurable historical start week/date, defaulting to the Reference Workbook's `W40-22` history start. It is built from per-week Weekly Summary rows using the same Meet Sheet source rule as the export week. AI/MCP queries may ask users for an explicit from/to period by day/date when they need ad-hoc historical ranges.

**Rolling Week Marker**:
A recent-week column that marks whether the row's site also appears in that week. The marker columns are based on the export week's rolling window.
_Avoid_: Raw week data, formula column

**Meet Sheet**:
The HT Alarm Workbook sheet containing HT Study rows whose daily same-site HT duration exceeds same-site Power duration by more than seven hours, or whose same-site daily Power duration is unavailable. The seven-hour threshold is fixed to match the Reference Workbook. It is derived from the HT Study sheet, not from direct timestamp-overlap coverage alone.
_Avoid_: Covered temps, uncovered temps

**HT Workbook Week Label**:
The week label used by HT Alarm Workbooks, such as `W27-24`. It follows the Reference Workbook's Sunday-based week numbering rule, equivalent to `%U + 1`, not ISO week numbering.
_Avoid_: ISO week label, calendar week when that implies Monday-based ISO behavior

**Export Week**:
The explicit week/period selected for an HT Alarm Workbook export. It determines weekly sheet names, `Week No.` values, raw sheet scope, and the rolling week marker window.
_Avoid_: Implicit latest week, current calendar week
An Export Week uses a Sunday-start seven-day period: Sunday 00:00 inclusive through the next Sunday 00:00 exclusive.
HT coverage computation may use Power alarm context outside the Export Week when needed for correct boundary decisions, but raw HT/Power workbook sheets remain scoped to alarms whose occurrence timestamp falls inside the Export Week. Coverage context includes any same-site Power window whose occurrence/clearance-plus-margin interval overlaps the Export Week.
An active or uncleared same-site Power alarm covers Temp alarms indefinitely from its occurrence until a clearance is known.

## Example dialogue

Developer: “Should `W27` and `Consolidated` contain the same rows?”
Domain expert: “No. `W27` is the Weekly Summary for W27 only. `Consolidated` is the Consolidated History with many historical weeks, including W27 at the end.”

Developer: “What do the W27-24 through W20-24 columns mean?”
Domain expert: “They are Rolling Week Markers showing whether that site also appeared in those recent weeks.”

Developer: “Should we use ISO weeks for HT exports?”
Domain expert: “No. Use the Reference Workbook's HT Workbook Week Label rule so dates like 2024-06-30 are grouped as W27-24.”

Developer: “How do we know which week to export?”
Domain expert: “The user selects the Export Week or period explicitly. The app may default from current filters, but it should not silently infer the week.”

Developer: “What goes into the Meet sheet?”
Domain expert: “Rows from HT Study where HT daily duration minus Power daily duration is greater than seven hours, plus rows where no Power daily duration is available.”

Developer: “Is the Uncovered Temp dialog the same as the HT Alarm Workbook Meet sheet?”
Domain expert: “No. The dialog should use Power-Coverage Gap language, while HT Alarm Workbook export follows the Reference Workbook's daily SUMIFS-style Meet logic.”
