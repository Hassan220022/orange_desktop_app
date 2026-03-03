# Alarm ID Classification & BDT Validation Design

**Date:** 2026-03-02
**Status:** Approved

## 1. Alarm ID Classification

### Problem

Category detection (Power/Down) currently relies on filename keywords. This is unreliable — the actual alarm ID should determine the category.

### Solution

A configurable alarm ID list replaces filename-based detection entirely.

**Config file:** `~/.alarm_viewer/alarm_ids.json`

```json
{
  "power": ["22001", "22002", "22003"],
  "down": ["35001", "35002", "35003"]
}
```

- Loaded at app start. Created with empty lists if missing.
- IDs stored as strings (alarm IDs may have leading zeros or non-numeric formats).
- Universal — same lists for all vendors.
- No match = "Unknown" category. No fallback to filename logic.

### UI

A gear/settings button in the sidebar opens a "Configure Alarm IDs" dialog:

- Two text areas: Power IDs, Down IDs (comma-separated)
- Save writes to the JSON file
- After saving, loaded data is re-classified immediately without re-parsing files

### Impact

- `parsers.py` — Remove filename-based `cat = ("Power" if "power" in fl ...)` logic. Use alarm ID config instead.
- `constants.py` — No change to schema maps.

---

## 2. BDT (Battery Discharge Test) Validation

### Problem

Subcontractors submit BDT Excel reports that may be fraudulent. The app needs to cross-reference BDT data against actual alarm data (ground truth from NMS) to catch fake tests.

### BDT File Structure

Each `.xlsx` file contains 4 sheets:

| Sheet       | Contents                                                                                                                                               |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| BDT sheet   | Site info, power cabinet, battery info, discharge test table (time vs V/A per string), temperature, equipment, per-battery voltage, photo placeholders |
| Power Alarm | Engineer info, rectifier status, BTS/mail capture screenshots                                                                                          |
| Config      | NSN vs Huawei site config — rectifier load, modules, strings, A/C, RF counts                                                                           |
| Summary     | Single flat row (~53 columns) — site metadata, battery specs, start/end V/A, discharge time, test date                                                 |

**Key data extraction points (BDT sheet):**

- Site code: row 4, col 8 (e.g. "0483DE")
- Test date: row 3, col 14
- Start/End time: rows 4-5, col 14
- Start V/A: row 75 ("Before disconnecting Rectifier")
- End V/A: row 87 ("After Connecting Rectifier")
- Discharge time-series: rows 76-86 (10min to 300min intervals)
- Photo presence: openpyxl `_images` count per sheet
- Ibat before test: row 46 area

### Validation Rules

| #   | Rule                                             | Source                                                                   | Pass     | Fail     |
| --- | ------------------------------------------------ | ------------------------------------------------------------------------ | -------- | -------- |
| 1   | Photos exist in placeholders                     | BDT embedded images > 0                                                  | Accepted | Rejected |
| 2   | Power alarm exists on test date for same site    | BDT site+date vs loaded alarm data                                       | Accepted | Rejected |
| 3   | Test duration matches Power alarm duration       | BDT discharge time vs alarm duration (+-tolerance)                       | Accepted | Rejected |
| 4   | Backup time matches discharge table calculation  | Last non-empty row in discharge table vs reported duration (+-tolerance) | Accepted | Revise   |
| 5   | Ampere before test = 0                           | BDT Ibat before start                                                    | Accepted | Rejected |
| 6   | End voltage in 40.5-45V range                    | BDT end voltage                                                          | Accepted | Rejected |
| 7   | Volt/Ampere inverse relationship throughout test | Discharge time-series correlation                                        | Accepted | Rejected |

**Tolerance:** Rules 2, 3, 4 use configurable tolerance (default 15%, range 10-20%).

**Overall verdict:**

- **Accepted** — all rules pass
- **Rejected** — any rule (except rule 4 alone) fails
- **Revise** — only rule 4 fails, all others pass

### Cross-Reference Logic

The alarm app's loaded data is the **source of truth**. The Power alarm from the NMS cannot be faked.

- If BDT says test was on date X but no Power alarm exists for that site on date X → test is fake, power was never cut.
- If BDT says duration was 2 hours but Power alarm lasted 1 hour → subcontractor is lying about discharge time.

---

## 3. UI — New "Test Validation" Tab

The main window adds a **tab bar** at the top of the right content area:

- **Alarms** tab — the entire existing alarm viewer (unchanged)
- **Test Validation** tab — the new BDT validator

### Test Validation Tab Layout

```
┌─────────────────────────────────────────────────────────┐
│  [Browse BDT Folder]  [Validate]     Tolerance: [15% v] │
├─────┬──────────┬────────┬────┬────┬────┬────┬────┬──────┤
│ File│ Site Code│  Date  │ R1 │ R2 │ R3 │ R4 │ R5 │ R6 ..│
├─────┼──────────┼────────┼────┼────┼────┼────┼────┼──────┤
│ BDT…│  0483DE  │Jan 12  │ x  │ x  │ x  │ x  │ ok │ x   │
│ BDT…│  4415DE  │Jan 14  │ ok │ ok │ ok │ ok │ ok │ ok   │
└─────┴──────────┴────────┴────┴────┴────┴────┴────┴──────┘
│                                                         │
│  Overall: 1 Accepted  |  1 Rejected  |  0 Revise        │
│                                                         │
│  [Export Results XLSX]                                   │
└─────────────────────────────────────────────────────────┘
```

- Each row = one BDT file
- R1-R7 columns: green (Accepted), red (Rejected), orange (Revise)
- Click row to expand detail — extracted values vs expected values per rule
- Requires alarm data loaded in Alarms tab for rules 2 & 3. If none, those rules show "No alarm data" in grey.
- Export button produces summary XLSX

---

## 4. Architecture

### New Files

- `alarm_app/bdt_parser.py` — Extract structured data from BDT Excel files
- `alarm_app/bdt_validator.py` — Run 7 validation rules, produce per-file results
- `~/.alarm_viewer/alarm_ids.json` — Configurable Power/Down alarm ID lists

### Modified Files

- `constants.py` — BDT constants (rule names, column widths, default tolerance)
- `viewer.py` — Tab bar wrapping existing content + Test Validation tab + gear button for Alarm ID config dialog
- `parsers.py` — Replace filename-based category detection with alarm ID config lookup
- `styles.py` — QSS for tab bar, validation colors, config dialog

### Unchanged Files

- `models.py`, `backup_time.py`, `state.py`, `main.py`

### Data Flow

```
BDT files (.xlsx) --> bdt_parser.py extracts structured data
                           |
alarm_ids.json --> parsers.py classifies alarms by ID
                           |
Alarm data (Alarms tab) + Parsed BDT data
                           |
                  bdt_validator.py runs 7 rules
                           |
                  Results table in Test Validation tab
```
