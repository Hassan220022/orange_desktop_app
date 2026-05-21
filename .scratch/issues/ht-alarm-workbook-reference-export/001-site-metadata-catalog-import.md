---
title: Import Network Summary into Site Metadata Catalog
label: ready-for-agent
type: AFK
blocked_by: None
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Import Network Summary into Site Metadata Catalog

## What to build

Add an end-to-end import path for the Network Summary DB Sheet that stores every column in both app databases as the Site Metadata Catalog. The import validates required Site ID fields, normalizes query-friendly field names while preserving original header mapping, and replaces both database copies all-or-nothing from the Network Summary workbook source of truth.

## Acceptance criteria

- [ ] A Network Summary workbook with a `DB` sheet can be imported into both databases.
- [ ] Every source column is stored and queryable by normalized field name.
- [ ] Original Excel header names are preserved for traceability.
- [ ] Site ID is normalized from the `Code` column and is the primary join key.
- [ ] Rectifier No. and Rectifier Code are preserved as additional metadata.
- [ ] Imports fail before replacing existing data if required key columns are missing or no valid rows exist.
- [ ] If either database write fails, neither database is left partially updated.
- [ ] Tests cover successful import, missing key validation, original-header mapping, and all-or-nothing behavior.

## Blocked by

None - can start immediately.
