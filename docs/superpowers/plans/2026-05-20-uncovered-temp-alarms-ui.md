# Uncovered Temp Alarms UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cramped `Uncovered Temp Alarms` dialog header with the approved card-dashboard layout.

**Architecture:** Keep all changes inside `TempAlarmDialog` in `ui/dialogs.py`. Reuse the existing `QSpinBox`, summary render lifecycle, and export button behavior while changing only widget composition and styling.

**Tech Stack:** Python, PyQt5, pandas, pytest.

---

## File Structure

- Modify: `ui/dialogs.py`
  - `TempAlarmDialog._build`: change the top header from one horizontal strip to a dashboard header with filter card, metric grid, and export action.
  - `TempAlarmDialog._render_summary`: render metric cards into the new metric grid with fixed styling and no overlap.
- Test: `tests/test_temp_alarm.py` existing behavior coverage.

## Task 1: Replace Header Layout

**Files:**
- Modify: `ui/dialogs.py:1755-1821`

- [ ] **Step 1: Run impact analysis before editing**

Run: `/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream TempAlarmDialog._build`

Expected: impact is limited to the Temp alarm dialog construction path.

- [ ] **Step 2: Update `_build` layout**

Replace the current `top`/`tl` one-row layout with:

```python
        top = QFrame()
        top.setObjectName("tempDashboardHeader")
        top.setStyleSheet("QFrame#tempDashboardHeader { background:#313244; border-radius:8px; }")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(12, 10, 12, 10)
        tl.setSpacing(12)

        filter_card = QFrame()
        filter_card.setObjectName("tempFilterCard")
        filter_card.setMinimumWidth(250)
        filter_card.setStyleSheet("QFrame#tempFilterCard { background:#1e1e2e; border-radius:8px; }")
        fl = QVBoxLayout(filter_card)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(6)

        filter_title = QLabel("FILTER")
        filter_title.setStyleSheet("color:#6c7086; font-size:10px; font-weight:700; letter-spacing:1px;")
        fl.addWidget(filter_title)

        margin_label = QLabel("Y margin after Power clearance")
        margin_label.setStyleSheet("color:#a6adc8; font-size:12px; font-weight:600;")
        margin_label.setWordWrap(True)
        fl.addWidget(margin_label)

        self._spn_margin = QSpinBox()
        self._spn_margin.setRange(0, 60)
        self._spn_margin.setSuffix(" min")
        self._spn_margin.setValue(self._margin_minutes)
        self._spn_margin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self._spn_margin.setAlignment(Qt.AlignCenter)
        self._spn_margin.setFixedSize(100, 34)
        self._spn_margin.setStyleSheet(
            """
            QSpinBox {
                background:#11111b;
                border:1px solid #89b4fa;
                border-radius:6px;
                color:#cdd6f4;
                font-size:13px;
                font-weight:700;
                padding:0 10px;
            }
            QSpinBox:focus { border-color:#b4befe; }
            QSpinBox:disabled {
                background:#313244;
                border-color:#45475a;
                color:#6c7086;
            }
            """
        )
        self._spn_margin.valueChanged.connect(self._recompute)
        fl.addWidget(self._spn_margin, 0, Qt.AlignLeft)
        tl.addWidget(filter_card)

        self._summary_strip = QHBoxLayout()
        self._summary_strip.setSpacing(10)
        tl.addLayout(self._summary_strip, 1)
```

- [ ] **Step 3: Keep export widgets on the right**

After the summary layout in `_build`, keep `self._export_status`, `self._export_progress`, and `self._btn_export`, but style the button as a taller action card:

```python
        self._btn_export = QPushButton("Export XLSX")
        self._btn_export.setObjectName("btn_export")
        self._btn_export.setMinimumSize(110, 64)
        self._btn_export.clicked.connect(self._export)
        tl.addWidget(self._btn_export)
```

## Task 2: Render Dashboard Metric Cards

**Files:**
- Modify: `ui/dialogs.py:1846-1874`

- [ ] **Step 1: Run impact analysis before editing**

Run: `/opt/homebrew/bin/gitnexus impact -r orange_desktop_app -d upstream TempAlarmDialog._render_summary`

Expected: impact is limited to summary widgets inside the Temp alarm dialog.

- [ ] **Step 2: Update metric card styling**

Inside `_render_summary`, replace each plain `QWidget` metric box with a `QFrame` card:

```python
            box = QFrame()
            box.setObjectName("tempMetricCard")
            box.setMinimumWidth(120)
            box.setStyleSheet(
                "QFrame#tempMetricCard { background:#181825; border-radius:8px; }"
            )
            vb = QVBoxLayout(box)
            vb.setContentsMargins(10, 8, 10, 8)
            vb.setSpacing(3)
            lv = QLabel(val)
            lv.setAlignment(Qt.AlignCenter)
            lv.setFont(QFont("Segoe UI", 12, QFont.Bold))
            lv.setStyleSheet(f"color:{color};")
            lt = QLabel(label)
            lt.setAlignment(Qt.AlignCenter)
            lt.setWordWrap(True)
            lt.setStyleSheet("color:#a6adc8; font-size:10px;")
            vb.addWidget(lv)
            vb.addWidget(lt)
            self._summary_strip.addWidget(box, 1)
```

- [ ] **Step 3: Shorten labels**

Use labels:

```python
[
    ("Uncovered", f"{n:,}", "#f38ba8"),
    ("Sites", f"{site_count:,}", "#a6e3a1"),
    ("Y margin", f"{self._margin_minutes} min", "#fab387"),
    ("Clear duration", _fmt_td(duration.sum()) if not duration.empty else "-", "#94e2d5"),
]
```

## Task 3: Verify Behavior and Visual Safety

**Files:**
- Test: `tests/test_temp_alarm.py`

- [ ] **Step 1: Run Temp alarm tests**

Run: `./.venv/bin/python -m pytest tests/test_temp_alarm.py -q`

Expected: all tests pass.

- [ ] **Step 2: Compile changed UI file**

Run: `./.venv/bin/python -m py_compile ui/dialogs.py`

Expected: command exits successfully with no output.

- [ ] **Step 3: Manual visual check**

Open the `Uncovered Temp Alarms` dialog in the app and verify:

- Y margin card appears on the left.
- Four metric cards do not overlap.
- Export button appears on the right and remains clickable.
- The explanatory note remains below the header.

## Self-Review

- Spec coverage: the plan implements the approved card-dashboard layout and preserves existing behavior.
- Placeholder scan: no placeholder steps remain.
- Type consistency: all referenced methods and widgets already exist on `TempAlarmDialog`.
