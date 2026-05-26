# Read-only MCP site data parity design

## Goal

Expand the Alarm Viewer MCP surface so ChatGPT or any MCP client can read the same operational structured site data that the desktop app can already inspect: Network Summary/Site Metadata, alarm events, BDT summary catalog data, BDT validation runs, rule results, photo metadata, and existing computed report outputs.

“Everything” means every structured row and field is reachable through MCP tools with pagination. It does not mean returning all rows in one response, returning raw BDT image bytes through broad context tools, or handing back an Excel file as the primary interface.

The MCP must remain read-only for application data. For export-style workflows, it should expose the report content that the app would generate, not hand back an Excel file path as the primary interface. It must not import files, mutate databases, delete data, update app state, or browse arbitrary local paths.

## Current state

The MCP server is `alarm-viewer-local-data` and is exposed by:

- stdio via `main.py --mcp-server`
- HTTP `/mcp` for ChatGPT/Cloudflare Quick Tunnel

Existing tools already cover basic alarm queries, BDT result queries, site metadata search, BDT summary queries, site dossiers, charts, photo blob reads, and exports. The gap is that clients do not have a complete, explicit read-only parity layer for all-sites discovery and full per-site context.

## Scope

Add read-only, paginated, MCP-safe tools for:

1. discovering all known sites across Network Summary, alarms, BDT summary catalog, and BDT validation DB;
2. reading complete Network Summary/Site Metadata rows with original workbook fields;
3. reading all alarm rows with app-supported filters and pagination;
4. reading combined BDT summary catalog rows and validation-run details;
5. building one-site full context payloads;
6. exposing filtered or all-site report content in workbook-like sections without requiring the MCP client to retrieve an Excel file;
7. invoking existing app computation/report functions for Backup Time calculations, HT Alarm Workbook Meet logic, Weekly Summary/Consolidated History, BDT verdict calculations, accepted PM report logic, charts, and report sections;
8. reading site-related review events as operational review history, with any file-path-like values redacted.

The interface should be hybrid: common core entities get direct tools, while computed outputs are accessed through one broad report dispatcher. Direct tools keep common site/alarm/catalog queries easy for MCP clients; a computed-report dispatcher avoids schema sprawl for every app-derived report.

Out of scope:

- importing Network Summary or BDT Summary files;
- creating, editing, or deleting alarms, BDT runs, metadata, photos, app settings, or UI state;
- exposing desktop UI settings/state or other app-interface configuration that is not site operational data;
- returning arbitrary local files;
- returning raw local filesystem paths in any MCP response;
- treating broad site context as image transport. MCP parity means structured records and generated reports, not inline bulk image bytes, because plugin-style clients such as ChatGPT and Claude are not a practical transport for many BDT photo blobs.

## Tool design

### `list_sites`

Returns a paginated inventory of known sites. Each row includes the normalized site code, available display/name fields from Network Summary, area/contractor/backup/battery fields when available, alarm counts, BDT summary counts, validation-run counts, and latest known alarm/BDT dates.

“All sites” is the union of site identities found in Site Metadata Catalog, alarm rows, BDT Summary Catalog, and BDT validation DB. The response must include source flags such as `has_metadata`, `has_alarms`, `has_bdt_summary`, and `has_bdt_validation` so orphan operational data is visible instead of hidden behind missing metadata.

Filters:

- `site_text`, `site_code`, `site_id`
- `area`
- `subcontractor`, `contractor`
- `backup_status`, `battery_status`
- `has_alarms`, `has_bdt`, `has_metadata`
- source-specific flags such as `has_bdt_summary` and `has_bdt_validation`
- `limit`, `offset`

The tool should not return every alarm or BDT row. It is an index for navigation.

MCP schemas should expose both `site_id` and `site_code` as equal aliases for the same normalized **Site ID** value. They are not separate identities.

### `query_network_summary`

Reads imported Network Summary/Site Metadata catalog rows. It returns normalized columns plus original workbook fields expanded from `raw_data_json`.

Rows include both normalized query-friendly fields and original Network Summary workbook-header fields so clients get stable filtering plus source-faithful detail.

Filters:

- `site_text`, `site_code`, `site_id`
- `area`
- `subcontractor`, `contractor`
- `backup_status`, `battery_status`
- `limit`, `offset`

This supersedes the narrower `search_site_metadata` and `query_site_metadata` for full metadata reads, while keeping those existing tools compatible.

### `query_alarm_events`

Reads alarm rows from DuckDB with explicit all-alarm semantics. It should expose the same safe filters used by the app and existing `query_alarms`:

“All alarm info” means every alarm field currently stored in DuckDB/app storage. MCP should not promise original uploaded alarm columns that the app did not preserve. If original alarm-source columns are preserved in a future storage format, MCP can expose them then.

- site text / site id
- category
- vendor
- network type
- date range
- sort field and direction
- limit and offset

It returns row count for the returned page and, where cheap, total matching count. It must cap page size to the existing MCP maximum unless an export tool is used.

### `query_bdt_full`

Reads BDT data from both sources:

- imported BDT Summary catalog in DuckDB;
- app validation DB runs, rule results, BDT test details, and photo metadata.

BDT Summary Catalog rows include both normalized query-friendly fields and original BDT Summary Workbook header fields so clients get stable filtering plus source-faithful detail.

Filters:

- site code / site id
- reporting period / period
- week
- BDT test date range
- overall verdict
- rule id
- rule verdict
- limit and offset

The response includes separate arrays/sections for summary catalog rows, validation runs, rule results, and photo metadata. It must not return image bytes.

### `get_site_full_context`

Builds a complete read-only JSON context for one site:

- normalized site code;
- Network Summary/Site Metadata rows;
- alarm statistics;
- paginated/recent alarm rows;
- BDT Summary catalog rows;
- BDT validation runs;
- BDT rule results;
- BDT photo metadata;
- review events for the site/test period, including reviewer/verdict/timestamps and path-redacted payload metadata.

Inputs include `site_code`/`site_id`, optional date filters, and per-section limits. Defaults should keep the response small enough for LLM consumption.

### `get_sites_context_report`

Returns workbook-like report content for one site, filtered sites, or all sites. This tool mirrors export features as structured sections that MCP clients can read directly. It does not return an Excel file itself.

Calling without a `sheet` returns a manifest with every available sheet name and total row count. Calling with a `sheet`, `offset`, and `limit` returns that sheet page. Clients can page through each sheet until they have all rows.

Sheets:

- `Sites`
- `Network Summary`
- `Alarm Stats`
- `Alarms`
- `BDT Summary`
- `BDT Runs`
- `BDT Rules`
- `Photo Metadata`
- `Review Events`

Inputs should support the same filters as `list_sites`, `query_alarm_events`, and `query_bdt_full`. The tool returns sheet names, row counts, and bounded page content. Large sheets must be paginated rather than returned in one response.

### Computed report tools

MCP parity includes existing computed outputs the app can already produce, but the MCP implementation must call shared app functions rather than duplicating report logic. A single dispatcher tool such as `get_computed_report(report_type, ...)` should route to these shared functions. This applies to:

- Backup Time calculations;
- HT Alarm Workbook Meet logic;
- Weekly Summary and Consolidated History rows;
- BDT verdict calculations;
- accepted PM report logic;
- chart/report section generation.

These tools return structured rows/sections and pagination metadata. They do not import source files or mutate stored app data.

Date/period-sensitive computed tools must require explicit scope. If an HT Alarm Workbook, Weekly Summary, Consolidated History, Backup Time, accepted PM, or similar report request is missing required week/date inputs, the MCP tool should return a structured error telling the client to ask the user for the missing period instead of silently inferring from latest data or UI state.

MCP tools read saved database/catalog state only. They must not depend on current GUI filters, unsaved import previews, selected tabs, or other transient desktop UI state. If a caller wants a filter, it must pass that filter explicitly as tool arguments.

Source-file-dependent computed reports, such as accepted PM report logic, may only use app-known source files internally. A tool may reference an existing `uploaded_files` record by ID when the recorded path, size, suffix, and hash still verify, or use an MCP upload allowlist if a connector provides one. It must never accept or read arbitrary raw local paths supplied by the model, and it must not expose stored local file paths in responses.

## Data flow

The MCP tool registry in `llm_tools/tools.py` declares tool schemas and annotations. Dispatch remains through `dispatch_tool()` into `LocalDataService` methods.

`LocalDataService` remains the guarded facade. It should compose existing helpers where possible:

- `alarm_store` for DuckDB alarm reads and stats;
- `catalog_store` for Network Summary/Site Metadata and BDT Summary catalog reads;
- SQLAlchemy repositories/models for validation runs, BDT tests, rule results, and photo metadata;
- existing report-building logic where it can produce structured rows without requiring a file handoff.
- existing computation/report functions for Backup Time, HT Alarm Workbook, BDT verdicts, accepted PM logic, and chart data.

No new tool should bypass `LocalDataService` for data access.

## Safety and limits

- All new tools are annotated `readOnlyHint: true`.
- No tool accepts arbitrary local paths.
- No MCP response returns raw local filesystem paths. Path-backed records should expose safe IDs, original names, hashes, sizes, MIME types, dimensions, source kind, and parsed timestamps instead.
- No tool imports files or changes DB contents.
- Large data access must use pagination or report sections.
- New broad tools must not impose “preview only” ceilings beyond page-size limits. The complete dataset must remain reachable by increasing `offset` across repeated calls.
- Page sizes default to 500 rows per call. Callers may request a different `limit`, with a hard cap of 1000 rows per call. If a caller asks for more than 1000 rows, the tool returns at most 1000 and includes pagination metadata so the client can continue with the next `offset`.
- Paginated tools always return `returned`, `limit`, `offset`, and `has_more`. They return `total` when it can be computed cheaply without forcing expensive full report recomputation.
- Photo metadata may include stored path/sha/mime/size dimensions. New broad context and export tools must not return image bytes.
- Broad/context/report tools must not expose raw local filesystem paths. They should return stable identifiers and useful metadata such as upload IDs, original filenames, SHA-256 hashes, sizes, MIME types, and image dimensions instead of paths like user home directories or blob storage paths.
- Site-related operational person/comment fields, such as engineer names, reviewer names, and BDT/Network Summary comments, remain in scope when they are part of site metadata, BDT rows, validation records, or report content.
- Site-related review events are in scope as operational review history. They may expose reviewer names, verdicts, reviewed timestamps, and non-path payload fields. File paths and path-like filename values must be redacted or reduced to safe original names.
- JSON payload columns such as `raw_data_json`, `original_headers_json`, `evidence_json`, and `payload_json` should be parsed and expanded into normal response fields by default. Raw JSON strings are returned only when the caller explicitly passes `include_raw_json=true`.
- Existing token protection for HTTP MCP remains unchanged.

## Compatibility

Existing MCP tools stay available. New tools are additive. Current ChatGPT connector behavior and `.mcp.json` stdio behavior should not change.

## Testing

Add tests for:

- tool definitions include new schemas and read-only/export annotations;
- `list_sites` merges site identities across metadata, alarms, BDT summary, and validation runs;
- `query_network_summary` expands original workbook fields;
- Network Summary/Site Metadata responses include both normalized fields and original workbook-header fields;
- Alarm responses include every stored alarm field, without inventing unavailable original upload columns;
- `query_alarm_events` respects filters, pagination, and limits;
- `query_bdt_full` returns summary catalog data plus validation-rule/photo metadata without blob bytes;
- BDT Summary responses include both normalized fields and original workbook-header fields;
- `get_site_full_context` composes all per-site sections with limits;
- `get_sites_context_report` returns workbook-like sections with row counts and bounded content pages;
- MCP `tools/list` exposes the new tools over stdio/HTTP without breaking existing tools.

## Acceptance criteria

- MCP clients can discover all known sites.
- MCP clients can query full Network Summary metadata for all sites or one site.
- MCP clients can query alarms and BDT data through paginated read-only tools.
- MCP clients can ask for a comprehensive one-site context without needing to know internal tables.
- MCP clients can read all-site or filtered-site report content through workbook-like sections and pagination.
- Every structured row/field in those report sections is reachable through repeated paginated MCP calls.
- MCP clients can request existing computed app outputs through tools that reuse shared app logic instead of reimplementing formulas in MCP-specific code.
- Core data uses direct tools; computed app outputs use a report dispatcher such as `get_computed_report(report_type, ...)`.
- Date/period-sensitive computed tools fail with a user-actionable missing-period error instead of silently inferring periods.
- MCP results come from saved database/catalog state and explicit tool arguments, not transient GUI state.
- Source-file-dependent reports use verified app-known uploads or MCP allowlisted uploads only; arbitrary local paths are rejected.
- Broad/context/report tools redact raw local filesystem paths while preserving stable identifiers and metadata needed for reasoning.
- Desktop UI state/settings are not part of MCP site-data parity.
- Site-related engineer/reviewer/comment fields are returned when present in operational data or report content.
- Site-related review events are returned as operational review history, with file paths redacted.
- Raw JSON payload strings are hidden by default, but available through `include_raw_json=true` for auditing/debugging.
- Broad MCP tools default to 500 rows per call, honor caller-requested page sizes up to 1000 rows per call, and keep complete datasets reachable through repeated paginated calls.
- Paginated MCP responses always include `returned`, `limit`, `offset`, and `has_more`; `total` is included when cheap.
- MCP schemas expose `site_id` and `site_code` as equal aliases for the same normalized **Site ID**.
- No new MCP tool mutates app data.
- Existing CI quality, tests, and bundle workflows pass.
