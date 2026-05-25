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
MCP BDT Summary responses should include both normalized query-friendly fields and original BDT Summary Workbook header fields.

**Site ID**:
The canonical, stable site key used to connect alarms, Network Summary metadata, BDT records, weekly summaries, and consolidated history. It corresponds to the Network Summary `Code` value and the alarm data `site_id` value after normalization, and it does not change over time.
MCP schemas may expose `site_id` and `site_code` as equal aliases for this same normalized value.
_Avoid_: Short Code, Site Code, Rectifier Code as separate identities

**Site Metadata**:
Descriptive site attributes keyed by **Site ID**, including site name, Orange area, subcontractor, battery type, backup status, office, site type, and power source. When the Network Summary has multiple rectifier rows for one **Site ID**, site-level attributes come from the primary rectifier row, while battery attributes may combine distinct values across rectifiers.
_Avoid_: Alarm fields, BDT-only fields

**Site Metadata Catalog**:
The searchable collection of all Network Summary `DB` sheet columns keyed by **Site ID**. It is used both for HT Alarm Workbook enrichment and for answering site questions through AI or MCP tooling, with exports and other services joining to it on demand.
_Avoid_: Export-only metadata, hidden lookup

The catalog is stored in both the alarm analytics database and the app database so alarm workflows, BDT workflows, AI, and MCP queries can all access it without treating it as export-only data. The Network Summary workbook is the source of truth for imported rows. Imports merge by normalized **Site ID**: imported rows replace matching **Site ID** values and preserve sites not present in the imported Network Summary.
A single Network Summary import should not leave only one database copy updated. In a multi-file import batch, successful files may remain imported if a later file fails and the user is told which files failed.
The catalog uses normalized query-friendly field names while preserving a mapping back to the original Network Summary column headers.
MCP Site Metadata responses should include both normalized query-friendly fields and original Network Summary workbook-header fields.
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

**MCP Site Data Parity**:
AI/MCP access to the same structured operational site records and computed report outputs the app can inspect, including **Site Metadata**, alarm rows, **BDT Summary Catalog** rows, BDT validation data, rule results, photo metadata, Backup Time calculations, HT Alarm Workbook Meet logic, Weekly Summary and Consolidated History rows, BDT verdict calculations, accepted PM report logic, charts, and report sections. “Everything” means every structured row and field related to all sites is reachable through paginated queries or workbook-like report sections; it does not mean returning all rows in one response, transporting raw BDT image bytes through broad context queries, importing files, mutating app data, exposing desktop UI state/settings, or exposing raw local file paths. For MCP site discovery, “all sites” is the union of site identities found in Site Metadata, alarm rows, BDT Summary Catalog rows, and BDT validation data, with source flags showing which data exists for each **Site ID**. Computed MCP outputs must reuse shared app logic rather than reimplementing formulas in MCP-only code.
For alarms, MCP Site Data Parity means every alarm field currently stored in app/DuckDB storage. It does not imply original uploaded alarm columns that were never preserved.
Date/period-sensitive MCP computations should ask the user for missing required week/date scope instead of silently inferring a period from latest data or UI state.
MCP tools use saved database/catalog state and explicit tool arguments only; they do not read transient GUI filters, unsaved import previews, selected tabs, desktop UI settings, or other app-interface state.
Source-file-dependent MCP reports, such as accepted PM report logic, may use verified app-known uploads or MCP allowlisted uploads internally, but they must not read arbitrary raw local paths supplied by the model.
MCP responses should ignore/redact raw local filesystem paths and expose stable IDs, original names, hashes, sizes, MIME types, dimensions, source kind, and parsed timestamps instead.
Site-related operational person/comment fields, such as engineer names, reviewer names, and BDT/Network Summary comments, remain part of MCP Site Data Parity when they are present in site metadata, BDT rows, validation records, review events, or report content. Site-related review events are operational review history and may be exposed through MCP with file paths redacted.
Raw JSON payload columns should be parsed into normal MCP fields by default. Raw JSON strings may be exposed only when explicitly requested for auditing/debugging.
Broad MCP tools default to 500 rows per call and enforce a hard cap of 500 rows per request. Larger datasets remain reachable through repeated paginated calls.
Paginated MCP responses always include returned row count, limit, offset, and whether more rows are available; total row count is included when cheap to compute.
_Avoid_: One giant MCP response, bulk image transport, write-capable plugin access

**All-Sites Full Context Report**:
A paginated AI/MCP report keyed by **Site ID** that can return a page of sites with nested per-site context, such as **Site Metadata**, alarm summary, recent alarm rows, **BDT Summary Catalog** rows, BDT validation runs, rule results, photo metadata, and review events. Each nested context section has its own page-size limit so the report remains reachable in repeated calls instead of becoming one giant response.
The report's default site universe is all known sites: the union of Site Metadata, alarm rows, BDT Summary Catalog rows, and BDT validation data. Callers may narrow that universe with source-presence filters such as metadata-only, alarm-only, BDT-only, or specific source flags.
Each site row should expose an operational base row with common fields such as site name, Orange area, office, VIP marker, contractor, subcontractor, backup status, battery status, source flags, counts, and latest known dates, while full source-faithful metadata remains available in nested Network Summary rows.
By default, each site row should include a small recent nested context: a few Network Summary rows, the latest alarm rows, latest BDT Summary rows, latest BDT validation runs, latest rule results, photo metadata only, and latest review events. Callers may override nested section limits, but site-page and nested-section limits must follow the global 500-row MCP request cap so the response stays safe for MCP clients.
_Avoid_: Arbitrary SQL joins, one-call full database dump, replacing **Site ID** with rectifier-level identity

**Federated Site Query**:
A safe AI/MCP query over multiple app data sources, joined by canonical **Site ID** in application logic rather than by arbitrary model-written SQL. It lets callers choose from whitelisted fields, whitelisted source groups, and whitelisted filter operators across Site Metadata, alarms, BDT Summary Catalog, and BDT validation data. It may read from both the app database and DuckDB-backed stores, but it should not expose raw SQL execution, raw database schema, arbitrary table joins, or unrestricted database internals to the model.
The All-Sites Full Context Report should be a preset use case over the same federated query foundation, so common full-context requests and custom field/filter requests share the same source reads, Site ID stitching, pagination, sanitization, and source-error handling.
Its curated field catalog includes common site-level metadata and source flags/counts, plus selectable nested operational sections such as Network Summary rows, alarm rows, BDT Summary rows, BDT validation runs, rule results, photo metadata, and review events.
Federated Site Query filters are two-level: site filters decide which **Site ID** rows appear, while section filters decide which nested operational rows appear inside each site. A caller may also require that specific nested sections have matches before a site is included.
When nested section filters are present, the default behavior is to filter nested rows only; callers must explicitly choose a matching-sites mode when they want sites without matching nested rows excluded.
AI/MCP clients should learn the Federated Site Query's available fields, source groups, filters, operators, nested sections, and examples from a curated data-model description, not from raw database schema or table names.
Federated Site Query results must be capped at 500 rows per request, including site rows and any nested section rows.
_Avoid_: Raw SELECT/JOIN text from the model, schema-dump tool, cross-database free-form SQL

**Admin Read-Only SQL Query**:
An expert AI/MCP capability for trusted users to run read-only SQL-style queries against approved application data sources when the curated Federated Site Query is not expressive enough. It is distinct from the normal Federated Site Query path and must preserve MCP safety expectations: no app-data mutation, no arbitrary local file access, no raw local filesystem path exposure, and no response larger than the global MCP row cap.
Admin Read-Only SQL Query should expose approved, stable, read-only views rather than raw physical tables. Those views may represent data from both the app database and DuckDB-backed stores, but the query surface should remain source-faithful and bounded.
Admin Read-Only SQL Query may join approved read-only views together in one query, including views backed by different app data stores, as long as the query remains read-only, bounded, and sanitized.
_Avoid_: Write-capable SQL, file-system access through SQL, uncapped result sets, replacing normal site questions with SQL-first behavior

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
