# Temp Alarm Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `Temp` classification for imported alarm rows based on filename and approved alarm names.

**Architecture:** Keep the alarm schema unchanged and store `Temp` in the existing `alarm_category` column. Add filename-based classification in `data.loaders.parse_alarm_file` and row-level name classification in `core.classify.classify_by_alarm_id`.

**Tech Stack:** Python, pandas, pytest, Excel/CSV alarm imports.

---

## File Structure

- Modify `data/loaders.py`: classify whole files as `Temp` when the filename contains `temp`.
- Modify `core/classify.py`: classify rows as `Temp` when `alarm_name` matches one of the approved names.
- Modify `tests/test_parsers.py`: add focused tests for filename and alarm-name classification.

## Task 1: Filename-Based Temp Category

**Files:**
- Modify: `tests/test_parsers.py`
- Modify: `data/loaders.py`

- [ ] **Step 1: Write the failing test**

Add this method to `TestParseAlarmFile` in `tests/test_parsers.py` after `test_category_door_from_filename`:

```python
    def test_category_temp_from_filename(self, tmp_path):
        cols = list(SCHEMA_1_MAP.keys())
        rows = [["src1", "SiteA", "2024-01-01 10:00", "2024-01-01 11:00",
                 "01:00:00", "65036", "Shelter High Temperature", "Cleared", "LTE", "Huawei"]]
        info = self._write_csv(tmp_path, "temp_alarms_2024.csv", cols, rows)
        result = parse_alarm_file(info)
        assert result is not None
        assert (result["alarm_category"] == "Temp").all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_parsers.py::TestParseAlarmFile::test_category_temp_from_filename -q`

Expected: FAIL because `alarm_category` is currently empty for temp filenames.

- [ ] **Step 3: Write minimal implementation**

In `data/loaders.py`, update the category block in `parse_alarm_file`:

```python
    fname_lower = fname.lower()
    if "temp" in fname_lower:
        df["alarm_category"] = "Temp"
    elif "power" in fname_lower:
        df["alarm_category"] = "Power"
    elif "down" in fname_lower:
        df["alarm_category"] = "Down"
    elif "door" in fname_lower:
        df["alarm_category"] = "Door"
    else:
        df["alarm_category"] = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_parsers.py::TestParseAlarmFile::test_category_temp_from_filename -q`

Expected: PASS.

## Task 2: Alarm-Name Temp Category

**Files:**
- Modify: `tests/test_parsers.py`
- Modify: `core/classify.py`

- [ ] **Step 1: Write the failing test**

Add this method to `TestClassifyByAlarmId` in `tests/test_parsers.py` after `test_door_heuristic_from_name_or_source`:

```python
    def test_temp_alarm_names_classified(self):
        names = [
            "BASE STATION EXTERNAL ALARM NOTIFICATION",
            "EXTERNAL AL 9",
            "Shelter High Temperature",
            "Switch Room 2 High Temperature",
        ]
        df = pd.DataFrame({
            "alarm_id": ["1", "2", "3", "4"],
            "alarm_category": ["", "", "", ""],
            "alarm_name": names,
        })
        result = classify_by_alarm_id(df, {"power": [], "down": [], "door": []})
        assert (result["alarm_category"] == "Temp").all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/bin/python -m pytest tests/test_parsers.py::TestClassifyByAlarmId::test_temp_alarm_names_classified -q`

Expected: FAIL because those names are not classified as `Temp` yet.

- [ ] **Step 3: Write minimal implementation**

In `core/classify.py`, add this constant after the import:

```python
TEMP_ALARM_NAMES = {
    "base station external alarm notification",
    "external al 9",
    "shelter high temperature",
    "switch room 2 high temperature",
}
```

Then add this block in `classify_by_alarm_id` after the door heuristic block:

```python
    if "alarm_name" in df.columns:
        temp_mask = (
            df["alarm_name"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(TEMP_ALARM_NAMES)
        )
        df.loc[temp_mask, "alarm_category"] = "Temp"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/bin/python -m pytest tests/test_parsers.py::TestClassifyByAlarmId::test_temp_alarm_names_classified -q`

Expected: PASS.

## Task 3: Regression Check

**Files:**
- Test: `tests/test_parsers.py`

- [ ] **Step 1: Run parser and classifier tests**

Run: `./.venv/bin/python -m pytest tests/test_parsers.py::TestParseAlarmFile tests/test_parsers.py::TestClassifyByAlarmId -q`

Expected: PASS with no failures.

- [ ] **Step 2: Verify temp workbook sample through the existing parser**

Run this command:

```bash
./.venv/bin/python - <<'PY'
from data.loaders import parse_alarm_file
from core.classify import classify_by_alarm_id

info = {
    "path": "/Users/mikawi/Developer/orange/data/mail_alarms/temp_alarms/HT-FEB-2026.xlsx",
    "ext": ".xlsx",
    "filename": "HT-FEB-2026.xlsx",
    "size_kb": 0,
}
df = parse_alarm_file(info)
print(None if df is None else df["alarm_category"].value_counts(dropna=False).head().to_dict())
df = classify_by_alarm_id(df, {"power": [], "down": [], "door": []})
print(df["alarm_category"].value_counts(dropna=False).head().to_dict())
PY
```

Expected: the second printed dict includes `Temp`.

## Self-Review

- Spec coverage: filename matching, alarm-name matching, schema preservation, and tests are covered.
- Placeholder scan: no placeholders remain.
- Type consistency: the plan uses existing `alarm_category`, `alarm_name`, and `parse_alarm_file` names.
