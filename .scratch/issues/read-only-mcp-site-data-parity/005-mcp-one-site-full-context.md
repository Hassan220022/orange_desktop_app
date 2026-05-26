---
title: Add one-site full context MCP tool
label: ready-for-agent
type: AFK
blocked_by:
  - 001-mcp-pagination-redaction-network-summary.md
  - 002-mcp-all-sites-inventory.md
  - 003-mcp-all-stored-alarm-events.md
  - 004-mcp-bdt-full-review-events.md
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add one-site full context MCP tool

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Add a read-only `get_site_full_context` MCP tool that composes the core site-data parity tools into one per-site context. For a given Site ID, MCP clients should be able to retrieve Site Metadata, alarm stats, alarm rows, BDT Summary rows, BDT validation data, rule results, photo metadata, and review events through a single structured response.

The tool should use saved database/catalog state and explicit arguments only. It must not depend on current desktop UI filters, selected tabs, unsaved import previews, or app-interface state.

## Acceptance criteria

- [ ] `get_site_full_context` is available through MCP/OpenRouter tool definitions and marked read-only.
- [ ] The tool requires `site_id` or `site_code` and treats them as aliases for the same normalized Site ID.
- [ ] The response includes Site Metadata, alarm stats, alarm rows, BDT Summary, validation runs, rule results, photo metadata, and review events.
- [ ] Per-section data follows the shared pagination and path-redaction contracts.
- [ ] The tool uses saved database/catalog state plus explicit arguments only.
- [ ] Missing Site ID returns a structured user-actionable error.
- [ ] Tests cover successful composition and missing Site ID behavior.

## Blocked by

- `001-mcp-pagination-redaction-network-summary.md`
- `002-mcp-all-sites-inventory.md`
- `003-mcp-all-stored-alarm-events.md`
- `004-mcp-bdt-full-review-events.md`
