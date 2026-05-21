---
title: Build Reference Workbook Meet Sheet engine
label: ready-for-agent
type: AFK
blocked_by: 003-export-week-and-filename.md
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Build Reference Workbook Meet Sheet engine

## What to build

Build the core HT Study and Meet computation that follows the Reference Workbook. For each Export Week, raw HT and Power rows are grouped by same Site ID and day to compute daily HT totals, daily Power totals, difference, and Meet inclusion. Meet rows are those with unavailable same-site same-day Power total or HT-minus-Power duration greater than the fixed seven-hour threshold.

## Acceptance criteria

- [ ] HT Study rows contain Support, Day, HT daily total, Power daily total, Diff, and Meet decision.
- [ ] Meet rows are exactly the subset where Power daily total is unavailable or Diff is greater than seven hours.
- [ ] Diff equal to exactly seven hours is not Meet.
- [ ] The seven-hour threshold is fixed, not configurable.
- [ ] Meet rows expose the Reference Workbook's nine visible columns.
- [ ] Tests cover no Power total, greater-than-seven, exactly-seven, and less-than-seven cases.

## Blocked by

- `003-export-week-and-filename.md`
