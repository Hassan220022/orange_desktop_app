# HT workbook week labels follow the Reference Workbook

> **Superseded by [ADR 0004](0004-ht-workbook-week-labels-use-jan1-fixed-blocks.md).** Temp/HT export week labels now use Jan-1 fixed 7-day blocks instead of Sunday-based `%U + 1`.

HT Alarm Workbook exports previously used the Reference Workbook's Sunday-based week label rule, equivalent to `%U + 1`, rather than ISO week numbering. This kept sheet names, `Week No.` values, and rolling week marker columns aligned with the existing Excel reports such as `2024 - HT Alarms W27.xlsx`, where 2024-06-30 belonged to `W27-24`.

## Considered Options

- ISO week numbering: rejected because it can shift dates into different week labels and break exact workbook validation.
- Configurable week numbering: rejected for now because HT Alarm Workbook exports must match the Reference Workbook exactly.

## Consequences

- HT workbook week labels were intentionally report-compatible, not ISO-standard.
- Any future implementation that groups HT alarm data by week must reuse the superseding Jan-1 block rule for weekly sheets, Consolidated History, and Rolling Week Markers.
