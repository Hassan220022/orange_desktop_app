# HT workbook week labels follow the Reference Workbook

HT Alarm Workbook exports use the Reference Workbook's Sunday-based week label rule, equivalent to `%U + 1`, rather than ISO week numbering. This keeps sheet names, `Week No.` values, and rolling week marker columns aligned with the existing Excel reports such as `2024 - HT Alarms W27.xlsx`, where 2024-06-30 belongs to `W27-24`.

## Considered Options

- ISO week numbering: rejected because it can shift dates into different week labels and break exact workbook validation.
- Configurable week numbering: rejected for now because HT Alarm Workbook exports must match the Reference Workbook exactly.

## Consequences

- HT workbook week labels are intentionally report-compatible, not ISO-standard.
- Any future implementation that groups HT alarm data by week must reuse this rule for weekly sheets, Consolidated History, and Rolling Week Markers.
