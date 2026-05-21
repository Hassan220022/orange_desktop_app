---
title: Write Reference-compatible HT Alarm Workbook sheets
label: ready-for-agent
type: AFK
blocked_by: 003-export-week-and-filename.md, 004-meet-sheet-engine.md
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Write Reference-compatible HT Alarm Workbook sheets

## What to build

Update HT Alarm Workbook export so it writes the Reference Workbook's sheet order, names, visible columns, formulas/values, styles, widths, filters, and layouts for raw HT, raw Power, HT Study, and Meet sheets. The export path uses the Meet Sheet engine and explicit Export Week scope.

## Acceptance criteria

- [ ] Workbook sheet order starts with weekly raw HT, weekly raw Power, weekly HT Study, and Meet.
- [ ] Sheet names use the short Export Week label, e.g. `W27 AUTIN HT`.
- [ ] Raw HT and raw Power sheets are scoped to occurrence timestamps inside the Export Week.
- [ ] HT Study helper columns and formulas/values match Reference Workbook behavior.
- [ ] Meet sheet columns match the Reference Workbook's nine visible columns.
- [ ] Standard export without missing metadata contains the Reference Workbook's six visible sheets once summary sheets are added by later slices.
- [ ] Tests inspect generated workbooks for sheet names, headers, styles, and selected formulas/values.

## Blocked by

- `003-export-week-and-filename.md`
- `004-meet-sheet-engine.md`
