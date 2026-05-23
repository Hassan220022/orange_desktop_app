---
title: Add computed report dispatcher for HT and BDT report sections
label: ready-for-agent
type: AFK
blocked_by:
  - 001-mcp-pagination-redaction-network-summary.md
  - 003-mcp-all-stored-alarm-events.md
  - 004-mcp-bdt-full-review-events.md
  - 007-mcp-computed-report-backup-and-charts.md
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add computed report dispatcher for HT and BDT report sections

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Extend the read-only `get_computed_report` MCP dispatcher to cover computed report sections that require existing app report functions: HT Alarm Workbook Meet logic, Weekly Summary, Consolidated History, BDT export sections, and accepted PM report logic.

Date/period-sensitive reports must not guess scope. If required week/date inputs are missing, the tool should return a structured error telling the MCP client to ask the user. Source-file-dependent reports must use verified app-known uploads or MCP allowlisted uploads only and must not expose raw local paths.

## Acceptance criteria

- [ ] HT Meet rows are reachable through `get_computed_report` by reusing existing HT Alarm Workbook Meet logic.
- [ ] Weekly Summary rows are reachable through `get_computed_report` by reusing existing app logic.
- [ ] Consolidated History rows are reachable through `get_computed_report` by reusing existing app logic.
- [ ] BDT export sections are reachable through `get_computed_report` by reusing existing BDT export section logic.
- [ ] Accepted PM report content is reachable only from verified app-known uploads or MCP allowlisted uploads.
- [ ] Missing Export Week/date/source-file inputs return user-actionable structured errors instead of silently inferring.
- [ ] Responses return structured sections/rows, not Excel file paths as the primary interface.
- [ ] Raw local filesystem paths are redacted from all responses.
- [ ] Tests cover HT missing-period errors, successful HT section output, BDT section output, accepted PM source-file validation, and path redaction.

## Blocked by

- `001-mcp-pagination-redaction-network-summary.md`
- `003-mcp-all-stored-alarm-events.md`
- `004-mcp-bdt-full-review-events.md`
- `007-mcp-computed-report-backup-and-charts.md`
