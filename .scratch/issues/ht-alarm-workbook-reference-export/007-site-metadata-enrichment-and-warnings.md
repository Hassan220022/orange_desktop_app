---
title: Enrich HT Alarm Workbook with Site Metadata and warnings
label: ready-for-agent
type: AFK
blocked_by: 001-site-metadata-catalog-import.md, 005-reference-workbook-writer.md, 006-weekly-summary-and-consolidated.md
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Enrich HT Alarm Workbook with Site Metadata and warnings

## What to build

Join Site Metadata Catalog data into HT Alarm Workbook export using canonical Site ID. Use exact normalized Site ID first, parse from alarm source only as fallback, and never fuzzy match. Missing metadata remains non-blocking: workbook identifiers stay alarm-derived, enrichment fields remain blank, the user is warned, and the workbook includes a `Missing Metadata` sheet only when gaps exist.

## Acceptance criteria

- [ ] HT workbook output uses Site Metadata for site name, area, subcontractor, battery type, and backup status where available.
- [ ] Matching uses normalized Site ID and optional alarm-source parse fallback only.
- [ ] Fuzzy or contains matching is not used.
- [ ] Missing metadata does not fail export.
- [ ] Missing metadata emits a non-blocking warning with affected Site IDs.
- [ ] Missing metadata adds a `Missing Metadata` workbook sheet only when needed.
- [ ] When no metadata is missing, workbook keeps the Reference Workbook's six visible sheets.
- [ ] Tests cover matched metadata, fallback parsing, missing metadata warning, and conditional sheet creation.

## Blocked by

- `001-site-metadata-catalog-import.md`
- `005-reference-workbook-writer.md`
- `006-weekly-summary-and-consolidated.md`
