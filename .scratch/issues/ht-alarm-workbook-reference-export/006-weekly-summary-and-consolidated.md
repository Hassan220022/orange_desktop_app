---
title: Build Weekly Summary and Consolidated from Meet rows
label: ready-for-agent
type: AFK
blocked_by: 004-meet-sheet-engine.md
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Build Weekly Summary and Consolidated from Meet rows

## What to build

Generate the Weekly Summary sheet and Consolidated History from Meet Sheet rows. Weekly Summary contains only the selected Export Week. Consolidated recomputes per-week summaries from raw alarm data across the configured historical start range, defaulting to the Reference Workbook's `W40-22` start, and uses rolling week marker columns based on the current Export Week.

## Acceptance criteria

- [ ] Weekly Summary contains one row per Site ID for the selected Export Week, summarized from Meet rows only.
- [ ] Weekly Summary columns match the Reference Workbook summary columns.
- [ ] Consolidated contains historical weekly summary rows, not a duplicate of the current weekly sheet.
- [ ] Consolidated uses the same Meet-derived summary rule for every included week.
- [ ] Historical recompute uses configurable start week/date with default `W40-22`.
- [ ] Rolling week marker columns reflect the current Export Week's eight-week window.
- [ ] Tests prove Weekly Summary and Consolidated differ when historical data has multiple weeks.

## Blocked by

- `004-meet-sheet-engine.md`
