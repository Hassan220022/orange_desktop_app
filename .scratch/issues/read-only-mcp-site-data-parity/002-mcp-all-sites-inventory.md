---
title: Add all-sites MCP inventory with source flags
label: ready-for-agent
type: AFK
blocked_by:
  - 001-mcp-pagination-redaction-network-summary.md
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add all-sites MCP inventory with source flags

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Add a read-only `list_sites` MCP tool that discovers every known Site ID across Site Metadata, alarm rows, BDT Summary Catalog rows, and BDT validation data. The tool should expose both `site_id` and `site_code` as aliases for the same normalized Site ID and include source flags so orphan operational data is visible.

The tool is an inventory/index, not a full row dump. It should help MCP clients decide which Site IDs have metadata, alarms, BDT Summary data, and BDT validation data before calling deeper tools.

## Acceptance criteria

- [ ] `list_sites` is available through MCP/OpenRouter tool definitions and marked read-only.
- [ ] `list_sites` returns the union of Site IDs from Site Metadata, alarms, BDT Summary Catalog, and BDT validation data.
- [ ] Each site row includes `site_id` and `site_code` aliases for the same normalized Site ID.
- [ ] Each site row includes source flags such as `has_metadata`, `has_alarms`, `has_bdt_summary`, and `has_bdt_validation`.
- [ ] The tool supports filters for site text, area, contractor/subcontractor, backup/battery status, and source flags.
- [ ] Pagination follows the shared MCP contract from issue 001.
- [ ] Raw file paths and desktop UI state are not exposed.
- [ ] Tests cover union behavior and source flags.

## Blocked by

- `001-mcp-pagination-redaction-network-summary.md`
