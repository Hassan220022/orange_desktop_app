---
title: Add computed report dispatcher for backup times and chart sections
label: ready-for-agent
type: AFK
blocked_by:
  - 001-mcp-pagination-redaction-network-summary.md
  - 003-mcp-all-stored-alarm-events.md
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add computed report dispatcher for backup times and chart sections

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Add the first slice of the read-only `get_computed_report` MCP dispatcher. This slice should route report requests for Backup Time calculations and chart/report section data to existing app logic, returning structured paginated content instead of duplicating formulas in MCP-specific code.

The goal is a working dispatcher path for computed outputs that do not require HT Export Week or external accepted PM source files.

## Acceptance criteria

- [ ] `get_computed_report` is available through MCP/OpenRouter tool definitions and marked read-only.
- [ ] `report_type=backup_times` reuses existing Backup Time calculation logic.
- [ ] Alarm chart report types reuse existing chart/report data logic where available.
- [ ] BDT chart report types reuse existing chart/report data logic where available.
- [ ] Responses follow the shared pagination/path-redaction contract when returning row sections.
- [ ] Unsupported report types return structured errors.
- [ ] Tests prove dispatcher routing for backup times, alarm chart data, BDT chart data, and unsupported report types.

## Blocked by

- `001-mcp-pagination-redaction-network-summary.md`
- `003-mcp-all-stored-alarm-events.md`
