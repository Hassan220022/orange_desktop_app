---
title: Add all stored alarm event MCP query
label: ready-for-agent
type: AFK
blocked_by:
  - 001-mcp-pagination-redaction-network-summary.md
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add all stored alarm event MCP query

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Add a read-only `query_alarm_events` MCP tool that exposes every alarm field currently stored in the app's alarm storage. It should support the same safe filtering and sorting concepts used by the app while making all stored alarm rows reachable through pagination.

This tool should not promise original uploaded alarm columns that were never preserved. It should return stored alarm fields only, without raw local paths or UI state.

## Acceptance criteria

- [ ] `query_alarm_events` is available through MCP/OpenRouter tool definitions and marked read-only.
- [ ] The tool accepts `site_id` and `site_code` aliases for the same normalized Site ID.
- [ ] The tool supports category, vendor, network type, date range, sort field, sort direction, limit, and offset filters.
- [ ] Returned rows include all stored alarm fields from app/DuckDB storage.
- [ ] The tool does not invent unavailable original upload columns.
- [ ] Pagination follows the shared MCP contract from issue 001.
- [ ] Raw local filesystem paths and desktop UI state are not exposed.
- [ ] Tests cover stored-field preservation, filters, and pagination metadata.

## Blocked by

- `001-mcp-pagination-redaction-network-summary.md`
