---
title: Add explicit HT Export Week and filename behavior
label: ready-for-agent
type: AFK
blocked_by: None
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Add explicit HT Export Week and filename behavior

## What to build

Introduce the HT Workbook Week Label and Export Week behavior used by HT Alarm Workbook exports. Users select an explicit Export Week or period; the app derives the Sunday-start date range, short sheet label, full week label, and default filename using the Reference Workbook week rule.

## Acceptance criteria

- [ ] `2024-06-30` resolves to `W27-24` using the Reference Workbook week rule.
- [ ] Export Week ranges are Sunday 00:00 inclusive through next Sunday 00:00 exclusive.
- [ ] A selected export week produces short sheet label `W27` and full label `W27-24`.
- [ ] Default filename follows `2024-HT-Alarms-W27.xlsx`.
- [ ] No ISO-week behavior is used for HT Alarm Workbook week labels.
- [ ] Tests cover boundary dates and filename generation.

## Blocked by

None - can start immediately.
