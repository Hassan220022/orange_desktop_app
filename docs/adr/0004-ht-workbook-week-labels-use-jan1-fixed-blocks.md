# HT workbook week labels use Jan-1 fixed 7-day blocks

HT Alarm Workbook exports use fixed 7-day blocks anchored on 1 January each year. `W1` covers 01/01–07/01, `W2` covers 08/01–14/01, and so on. Week number is `(dayofyear - 1) // 7 + 1`; labels are `W{week:02d}-{year%100:02d}`.

This supersedes [ADR 0001](0001-ht-workbook-week-labels-follow-reference-workbook.md), which used Sunday-based `%U + 1` numbering.

## Considered Options

- Keep Reference Workbook `%U + 1` rule: rejected because temp/HT export week selection now follows explicit Jan-1 blocks aligned with search date ranges.
- ISO week numbering: rejected because it does not match the required fixed Jan-1 blocks.

## Consequences

- Export week ranges are `Jan 1 + (week-1)*7` through `+7 days` (end exclusive).
- Maximum week per year is `ceil(days_in_year / 7)` (52 or 53).
- Existing exports validated against old Reference Workbook week labels may no longer match.
