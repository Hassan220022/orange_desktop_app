---
title: Import BDT Summary Workbook into BDT Summary Catalog
label: ready-for-agent
type: AFK
blocked_by: None
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Import BDT Summary Workbook into BDT Summary Catalog

## What to build

Add an end-to-end import path for BDT Summary Workbooks. Every sheet in the workbook is treated as a BDT summary sheet. All rows and columns are stored in both databases, keyed by Site ID plus reporting identity, with source sheet/reporting period, row-level week, test date, and test year preserved for querying.

## Acceptance criteria

- [ ] A BDT Summary Workbook with any number of sheets can be imported.
- [ ] Every sheet is treated as BDT summary data; sheet names are preserved as reporting-period keys.
- [ ] Rows store normalized Site ID plus row-level week, test date, and test year where available.
- [ ] Imports merge by reporting period: imported periods replace matching existing rows, and absent periods remain.
- [ ] All columns are stored with normalized names and original-header mapping.
- [ ] Both database copies are updated consistently.
- [ ] Tests cover one-sheet, multi-sheet, and merge-by-period imports.

## Blocked by

None - can start immediately.
