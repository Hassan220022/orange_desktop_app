# Alarm Viewer Requirements Specification

## 1. Purpose

This document defines functional and non-functional requirements for the Alarm Viewer desktop application, including alarm loading, filtering, export, and BDT (Battery Discharge Test) validation.

## 1.1 Chat-Derived Requirement Summary

These are the exact high-priority requirements requested during this chat:

- Load very large mixed directories quickly, but load only correct alarm data.
- Ignore incorrect/non-alarm files safely (no crash, no hang).
- Keep UI responsive during long operations with background processing and progress.
- Support multi-year BDT comparison for the same site.
- Compare latest vs previous test photos (especially load, modules, batteries).
- Rename validation item from `Ampere = 0` to `I Battery`.
- Update end-voltage validation: for tests `>= 180` minutes, accept by theoretical-duration logic; otherwise enforce `45-47 V` range.
- Skip BDT files without valid `BDT sheet` structure instead of failing the whole run.
å
## 2. Product Scope

Alarm Viewer is a PyQt5 desktop app used to:

- Load Huawei/Nokia alarm exports from CSV/XLSX files.
- Normalize alarm data into a common internal schema.
- Filter and analyze alarms by date/site/category/vendor/duration.
- Validate BDT files against alarm history using rule-based checks.
- Compare photos across multiple BDT test years for the same site.
- Export filtered/processed results to Excel.

## 3. Functional Requirements

### FR-1 Alarm File Discovery and Loading

- The system shall recursively scan a selected directory for alarm files (`.csv`, `.xlsx`, `.xls`).
- The system shall ignore temporary/system files (e.g. `~$`, `._` prefixes).
- The system shall exclude BDT files from alarm loading.
- The system shall validate headers and only include files that match supported alarm schemas.
- The system shall parse files in a background thread and show progress.
- The system shall merge valid alarm files into one DataFrame and preserve all required internal columns.

### FR-2 Alarm Data Normalization

- The system shall map Huawei/Nokia source columns to unified internal columns.
- The system shall classify alarm category as `Power` or `Down` (by filename and optional ID classification flow).
- The system shall compute `_duration_secs` from `duration` for fast filtering.
- The system shall parse `occurred_on` and `cleared_on` as datetimes where possible.

### FR-3 Alarm Search and Filtering

- The UI shall support filtering by site, date range, category, vendor, and duration thresholds.
- The filter operation shall always start from the master dataset (`self._full_df`).
- The visible row count shall update after each filter/clear action.

### FR-4 BDT File Parsing and Validation

- The system shall parse BDT files using fast cell-based extraction.
- The system shall skip embedded photo extraction during bulk validation.
- The system shall validate each BDT file using configured rules (R1-R8).
- Files without required BDT sheet structure shall be skipped safely without app crash.

### FR-5 BDT Rule Behavior (Updated)

- R5 rule label shall be `I Battery` (replacing `Ampere = 0` wording).
- R6 end-voltage rule shall accept values in `45-47 V` for normal checks.
- R6 shall auto-accept if discharge duration is `>= 180` minutes and theoretical backup time is greater than reported backup time.

### FR-6 Multi-Year BDT Comparison

- The system shall group BDT results by normalized site code.
- The system shall sort tests by date (latest first) per site.
- The UI shall allow selecting another year/test for comparison against the latest test.
- The UI shall support key-slot photo comparison and full-slot comparison.

### FR-7 Validation UI Features

- The validation tab shall include a smart search field.
- Search shall support live filtering by site code, year, and date-like text.
- Validation processing shall run in background with progress updates.

### FR-8 Export

- The system shall export the currently displayed dataset to Excel.
- Export shall run in a background thread and report progress/errors.

## 4. Non-Functional Requirements

### NFR-1 Performance

- Alarm discovery shall avoid non-alarm files and complete quickly on large directories.
- XLSX alarm parsing shall use a high-performance engine (calamine when available).
- BDT bulk validation shall complete without UI freeze even with thousands of files.

### NFR-2 Reliability

- Invalid/corrupt files shall be skipped safely.
- Per-file parse failures shall not crash the overall loading/validation run.
- Error messages shall be surfaced to the user in existing UI error flows.

### NFR-3 Usability

- Long operations (load/validate/export) shall show progress status.
- The interface shall remain responsive during background operations.

### NFR-4 Compatibility

- The application shall run on Python 3.14 with PyQt5 stack.
- Required dependencies shall include `python-calamine` for fast XLSX reads.

## 5. Acceptance Criteria

- Loading the provided large dataset includes only real alarm files in the alarm file list.
- Alarm load completes without crash and produces merged records from valid alarm files.
- Running BDT validation on the provided directory completes without crash.
- Files lacking `BDT sheet` are skipped, not fatal.
- R5 appears as `I Battery` in validation output.
- R6 behavior follows the updated duration/theoretical-time rule.
- Multi-year photo comparison UI is available for sites with multiple tests.

## 6. Out of Scope

- Automated image similarity scoring between BDT photos.
- Any redesign of finalized UI theme/layout outside requested feature updates.
