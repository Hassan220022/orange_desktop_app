---
title: Add Reference Workbook validation suite
label: ready-for-agent
type: AFK
blocked_by: 005-reference-workbook-writer.md, 006-weekly-summary-and-consolidated.md, 007-site-metadata-enrichment-and-warnings.md
parent: ../prds/ht-alarm-workbook-reference-export.md
---

# Add Reference Workbook validation suite

## What to build

Add a validation test suite that protects the reverse-engineered Reference Workbook behavior. The tests should use small fixtures and targeted assertions rather than depending on the large production workbook, while encoding the observed reference behavior for sheet structure, Meet derivation, summary derivation, and styling.

## Acceptance criteria

- [ ] Tests validate Reference Workbook sheet order and visible headers.
- [ ] Tests validate Meet rows are exactly HT Study rows with Meet decision.
- [ ] Tests validate fixed seven-hour threshold semantics.
- [ ] Tests validate Weekly Summary derives from Meet rows.
- [ ] Tests validate Consolidated is not a duplicate of Weekly Summary when history spans multiple weeks.
- [ ] Tests validate missing metadata sheet appears only when needed.
- [ ] Tests validate key style/layout expectations where stable and meaningful.

## Blocked by

- `005-reference-workbook-writer.md`
- `006-weekly-summary-and-consolidated.md`
- `007-site-metadata-enrichment-and-warnings.md`
