# Reference Workbook is the HT export source of truth

HT Alarm Workbook export behavior must match the observed `2024 - HT Alarms W27.xlsx` Reference Workbook for sheet names, visible columns, formulas, styles, layouts, summary logic, and Meet Sheet filtering. When a product or implementation question conflicts with inferred code behavior, the Reference Workbook wins because exact Excel compatibility is the goal.

## Considered Options

- Preserve current app “Uncovered Temp” timestamp-overlap logic for export: rejected because the Reference Workbook uses daily same-site HT-vs-Power totals and a fixed seven-hour Meet threshold.
- Reinterpret the Reference Workbook into a cleaner new model: rejected because users need output matching the existing report exactly.

## Consequences

- The HT export UI previews Meet Sheet rows, not Power-Coverage Gap rows.
- Weekly Summary and Consolidated History are derived from Meet Sheet rows.
- Y margin belongs only to the separate Power-Coverage Gap analysis, not HT Alarm Workbook export.
