---
title: Add MCP pagination, redaction, raw-JSON contract, and Network Summary query
label: ready-for-agent
type: AFK
blocked_by: []
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add MCP pagination, redaction, raw-JSON contract, and Network Summary query

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Add the shared MCP read contract for broad site-data tools, then expose full Network Summary/Site Metadata rows through a read-only `query_network_summary` tool. The tool should return normalized query-friendly fields and original Network Summary workbook-header fields, while defaulting to safe pagination and redacting raw local filesystem paths.

This slice establishes the conventions every later MCP parity tool depends on: default page size 500, max page size 1000, `returned`/`limit`/`offset`/`has_more` metadata, raw JSON hidden by default, and `include_raw_json=true` for auditing/debugging.

## Acceptance criteria

- [ ] Broad MCP helpers default to 500 rows per call and cap requested limits at 1000.
- [ ] Paginated responses include `returned`, `limit`, `offset`, and `has_more`; `total` is included when cheap.
- [ ] Raw JSON payload fields are parsed into normal fields by default.
- [ ] Raw JSON strings are returned only when `include_raw_json=true`.
- [ ] Raw local filesystem paths are omitted from broad MCP responses.
- [ ] `query_network_summary` is available through MCP/OpenRouter tool definitions and marked read-only.
- [ ] `query_network_summary` returns Site Metadata rows with normalized fields and original Network Summary workbook-header fields.
- [ ] Existing MCP tools continue to list and dispatch successfully.
- [ ] Focused MCP unit tests pass.

## Blocked by

None - can start immediately
