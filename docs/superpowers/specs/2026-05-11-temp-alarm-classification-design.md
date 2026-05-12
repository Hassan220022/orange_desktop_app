# Temp Alarm Classification Design

## Goal

Add `Temp` alarm classification to the existing alarm import flow so temperature alarms load from Excel and CSV exports with the same schema as other alarm types.

## Inputs

Temp alarm workbooks use the current alarm columns:

- `Alarm Source`
- `Site Name`
- `Last Occurred On`
- `Cleared On`
- `Duration(hh:mm:ss)`
- `Alarm ID`
- `Alarm Name`
- `Clearance Status`
- `Network Type`
- `Vendor`

## Classification Rules

Classify an imported row as `Temp` when either condition matches:

- The source filename contains `temp`, case-insensitive.
- The row `alarm_name` equals one of these values, case-insensitive after trimming whitespace:
  - `BASE STATION EXTERNAL ALARM NOTIFICATION`
  - `EXTERNAL AL 9`
  - `Shelter High Temperature`
  - `Switch Room 2 High Temperature`

Filename matching applies to every row in that file. Alarm-name matching applies row by row.

## Architecture

Keep the schema unchanged. `alarm_category` already stores free-text categories, and UI filters read distinct values from the stored data.

Update two places:

- `data.loaders.parse_alarm_file`: set the initial category to `Temp` when the filename contains `temp`.
- `core.classify.classify_by_alarm_id`: apply row-level `Temp` classification based on the approved alarm names.

`Temp` classification should not change `site_down_flag`; only `Down` and matched `Power` rows affect that flag.

## Tests

Add tests that prove:

- A filename containing `temp` marks imported rows as `Temp`.
- Each approved alarm name marks the row as `Temp`.
- Existing `Door` heuristic still works.
- Existing `Power` and `Down` ID classification still works.
