---
title: Add workbook-like all-sites context report reader
label: ready-for-agent
type: AFK
blocked_by:
  - 002-mcp-all-sites-inventory.md
  - 003-mcp-all-stored-alarm-events.md
  - 004-mcp-bdt-full-review-events.md
  - 005-mcp-one-site-full-context.md
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add workbook-like all-sites context report reader

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Add a read-only `get_sites_context_report` MCP tool that exposes workbook-like report content without returning an Excel file. The tool should return a manifest when no sheet is requested, and paginated rows when a sheet is requested.

This is how MCP clients can reach all-site report content without one giant response and without local file handoff. Clients should be able to page through `Sites`, `Network Summary`, `Alarm Stats`, `Alarms`, `BDT Summary`, `BDT Runs`, `BDT Rules`, `Photo Metadata`, and `Review Events`.

## Acceptance criteria

- [ ] `get_sites_context_report` is available through MCP/OpenRouter tool definitions and marked read-only.
- [ ] Calling without `sheet` returns a manifest of sheet names and row counts/availability metadata.
- [ ] Calling with `sheet`, `offset`, and `limit` returns one paginated sheet page.
- [ ] Supported sheets include `Sites`, `Network Summary`, `Alarm Stats`, `Alarms`, `BDT Summary`, `BDT Runs`, `BDT Rules`, `Photo Metadata`, and `Review Events`.
- [ ] The tool does not return an Excel file path as its primary interface.
- [ ] The complete dataset remains reachable through repeated paginated calls.
- [ ] Raw local paths and desktop UI state are not exposed.
- [ ] Tests cover manifest mode, sheet page mode, unknown sheet behavior, and pagination metadata.

## Blocked by

- `002-mcp-all-sites-inventory.md`
- `003-mcp-all-stored-alarm-events.md`
- `004-mcp-bdt-full-review-events.md`
- `005-mcp-one-site-full-context.md`
