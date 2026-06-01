# Uncovered Temp Alarms UI Design

## Goal

Fix the cramped top section of the `Uncovered Temp Alarms` dialog by replacing the current single-row strip with a card-dashboard header that keeps controls, metrics, and export action readable.

## Approved Direction

The approved direction is **Option C: Card dashboard** from the visual companion.

## Scope

- Update only the Temp alarm dialog header UI in `ui/dialogs.py`.
- Preserve existing behavior: changing Y margin recomputes results, summary values update, and XLSX export still works.
- Keep the existing dark theme and metric colors.
- Keep the explanatory note below the header.
- Do not change the Temp alarm matching algorithm or export algorithm in this UI pass.

## Layout

The header becomes a three-part dashboard:

1. **Left filter card**
   - Label: `FILTER`
   - Text: `Y margin after Power clearance`
   - Existing `QSpinBox`, styled and centered.

2. **Middle metric card grid**
   - Four equal metric cards:
     - Uncovered temp alarms
     - Unique sites
     - Y margin
     - Total clear duration
   - Each card has a colored primary value and a muted label.

3. **Right export button**
   - Existing export button, visually sized like a dashboard action card.
   - Button text remains `Export XLSX` normally and `Exporting...` during export.

## Responsiveness

The dialog width remains 1180px by default. The metric grid should consume available horizontal space while the filter card and export button keep predictable minimum widths. Labels must not overlap values or adjacent cards.

## Testing

Use the existing Temp alarm tests to ensure no behavior changed. Add no new test unless the implementation introduces a separately testable helper. Manual visual validation is required because this is a PyQt layout polish change.

## Self-Review

- No placeholders remain.
- Scope is limited to the dialog header UI.
- Behavior preservation is explicit.
- The export correctness issues found earlier are intentionally out of scope for this visual fix.
