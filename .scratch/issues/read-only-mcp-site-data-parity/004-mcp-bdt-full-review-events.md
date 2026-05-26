---
title: Add full BDT MCP query with review events
label: ready-for-agent
type: AFK
blocked_by:
  - 001-mcp-pagination-redaction-network-summary.md
parent: docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md
---

# Add full BDT MCP query with review events

## Parent

- `docs/superpowers/specs/2026-05-22-read-only-mcp-site-data-parity-design.md`
- `docs/superpowers/plans/2026-05-22-read-only-mcp-site-data-parity.md`

## What to build

Add a read-only `query_bdt_full` MCP tool that exposes BDT Summary Catalog rows, BDT validation runs, rule results, BDT photo metadata, and site-related review events. BDT Summary rows should include normalized query-friendly fields and original BDT Summary Workbook header fields.

The tool should return structured sections, not image bytes. Site-related engineer, reviewer, and comment fields are in scope. Raw local filesystem paths are not in scope and must be redacted or reduced to safe metadata.

## Acceptance criteria

- [ ] `query_bdt_full` is available through MCP/OpenRouter tool definitions and marked read-only.
- [ ] BDT Summary rows include normalized fields and original BDT Summary Workbook header fields.
- [ ] Validation runs, BDT test details, rule results, and photo metadata are reachable by Site ID/date filters.
- [ ] Site-related review events are included as operational review history.
- [ ] Reviewer/engineer/comment fields are returned when present in operational data.
- [ ] Photo metadata does not include image bytes.
- [ ] Raw local file paths are redacted from photo metadata, upload provenance, and review-event payloads.
- [ ] Raw JSON fields are parsed by default and included only when `include_raw_json=true`.
- [ ] Pagination follows the shared MCP contract from issue 001 for each returned section.
- [ ] Tests cover BDT Summary original fields, validation/rule/photo/review sections, path redaction, and raw JSON opt-in.

## Blocked by

- `001-mcp-pagination-redaction-network-summary.md`
