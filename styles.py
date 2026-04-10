"""
Stylesheets — Catppuccin Mocha (dark) and Latte (light) themes.
Kept in a separate module so the main window code stays clean.
"""

STYLE_DARK = """
/* ── Base ──────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background: #13131f;
}
QWidget {
    background: #13131f;
    color: #cdd6f4;
    font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
    font-size: 13px;
}

/* ── Left sidebar background ───────────────────────────────── */
QWidget#sidebar {
    background: #0f0f1a;
    border-right: 1px solid #2a2a3e;
}

/* ── Top header ─────────────────────────────────────────────── */
QWidget#header {
    background: #0f0f1a;
    border-bottom: 1px solid #2a2a3e;
}

/* ── GroupBox ───────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    color: #6c7086;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    background: transparent;
}

/* ── Buttons ────────────────────────────────────────────────── */
QPushButton {
    background: #2a2a3e;
    color: #cdd6f4;
    border: 1px solid #3a3a52;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
    min-width: 0px;
}
QPushButton:hover {
    background: #313150;
    border-color: #89b4fa;
    color: #89b4fa;
}
QPushButton:pressed {
    background: #1e1e36;
    border-color: #7287fd;
    color: #7287fd;
}
QPushButton:disabled {
    background: #1e1e2e;
    border-color: #2a2a3e;
    color: #45475a;
}

/* Search — primary blue */
QPushButton#btn_search {
    background: #1a2744;
    color: #89b4fa;
    border: 1px solid #2a4070;
    min-width: 0px;
}
QPushButton#btn_search:hover {
    background: #1f3258;
    border-color: #89b4fa;
}

/* Clear — red */
QPushButton#btn_clear {
    background: #2e1a22;
    color: #f38ba8;
    border: 1px solid #5a2030;
}
QPushButton#btn_clear:hover {
    background: #3d1e2c;
    border-color: #f38ba8;
}

/* Export — green */
QPushButton#btn_export {
    background: #1a2e22;
    color: #a6e3a1;
    border: 1px solid #244030;
}
QPushButton#btn_export:hover {
    background: #1e3828;
    border-color: #a6e3a1;
}

/* Backup Time — purple */
QPushButton#btn_backup {
    background: #261a38;
    color: #cba6f7;
    border: 1px solid #402858;
}
QPushButton#btn_backup:hover {
    background: #2e1e44;
    border-color: #cba6f7;
}

/* Both P+D — orange */
QPushButton#btn_both {
    background: #2e2010;
    color: #fab387;
    border: 1px solid #4a3018;
}
QPushButton#btn_both:hover {
    background: #3a2814;
    border-color: #fab387;
}

/* Load — amber */
QPushButton#btn_load {
    background: #2e2010;
    color: #fab387;
    border: 1px solid #4a3018;
    font-size: 13px;
    padding: 8px 14px;
}
QPushButton#btn_load:hover {
    background: #3a2814;
    border-color: #fab387;
}
QPushButton#btn_load:disabled {
    background: #1e1e2e;
    border-color: #2a2a3e;
    color: #45475a;
}

/* Small selection buttons */
QPushButton#btn_small {
    background: #1e1e2e;
    color: #6c7086;
    border: 1px solid #2a2a3e;
    border-radius: 5px;
    padding: 4px 10px;
    min-width: 38px;
    font-size: 11px;
}
QPushButton#btn_small:hover {
    background: #2a2a3e;
    color: #cdd6f4;
    border-color: #45475a;
}

/* Sidebar Browse/Scan */
QPushButton#btn_dir {
    background: #1e1e2e;
    color: #89b4fa;
    border: 1px solid #2a3a5a;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    min-width: 60px;
}
QPushButton#btn_dir:hover {
    background: #1a2744;
    border-color: #89b4fa;
}

/* ── Inputs ─────────────────────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit {
    background: #1a1a2a;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
    font-size: 13px;
    selection-background-color: #313150;
    selection-color: #cdd6f4;
    min-height: 28px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
    border-color: #454560;
    background: #1e1e30;
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover {
    border-color: #3a3a52;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: #1a1a2a;
    border: 1px solid #3a3a52;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: #313150;
    selection-color: #89b4fa;
}

/* ── File list ──────────────────────────────────────────────── */
QListWidget {
    background: #0f0f1a;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
    outline: none;
    padding: 2px;
}
QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
    margin: 1px 2px;
    color: #6c7086;
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 11px;
}
QListWidget::item:selected {
    background: #1a1a2e;
    color: #89b4fa;
    border: 1px solid #2a2a52;
}
QListWidget::item:hover:!selected {
    background: #181828;
    color: #a6adc8;
}

/* ── Tables ─────────────────────────────────────────────────── */
QTableView, QTableWidget {
    background: #0f0f1a;
    alternate-background-color: #121220;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    gridline-color: #1e1e30;
    outline: none;
    selection-background-color: #1e1e40;
}
QTableView::item, QTableWidget::item {
    padding: 3px 8px;
    border: none;
}
QTableView::item:selected, QTableWidget::item:selected {
    background: #1e1e40;
    color: #cdd6f4;
}
QHeaderView {
    background: transparent;
}
QHeaderView::section {
    background: #13131f;
    color: #6c7086;
    border: none;
    border-right: 1px solid #2a2a3e;
    border-bottom: 2px solid #2a2a3e;
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
QHeaderView::section:first {
    border-top-left-radius: 6px;
}
QHeaderView::section:hover {
    background: #1a1a2e;
    color: #89b4fa;
}
QHeaderView::section:checked {
    color: #89b4fa;
}

/* ── Scrollbars ─────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #2a2a3e;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #3a3a52;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #2a2a3e;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #3a3a52;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: #0a0a14;
    color: #45475a;
    border-top: 1px solid #1e1e2e;
    font-size: 11px;
    padding: 2px 8px;
}
QStatusBar::item {
    border: none;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    color: #cdd6f4;
    background: transparent;
}
QLabel#lbl_app_name {
    color: #cdd6f4;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QLabel#lbl_app_ver {
    color: #313244;
    font-size: 11px;
}
QLabel#lbl_section {
    color: #45475a;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}
QLabel#lbl_green {
    color: #a6e3a1;
    font-weight: 600;
    font-size: 12px;
}
/* ── Progress bar ───────────────────────────────────────────── */
QProgressBar {
    border: none;
    border-radius: 3px;
    background: #1e1e2e;
    text-align: center;
    color: transparent;
    max-height: 4px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #89b4fa, stop:1 #cba6f7);
    border-radius: 3px;
}

/* ── Splitter ───────────────────────────────────────────────── */
QSplitter::handle {
    background: #1e1e2e;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ── Calendar ───────────────────────────────────────────────── */
QCalendarWidget {
    background: #13131f;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: #1a1a2a;
    border-bottom: 1px solid #2a2a3e;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 4px 8px;
    min-height: 36px;
}
QCalendarWidget QToolButton {
    background: transparent;
    color: #cdd6f4;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 13px;
    font-weight: 600;
}
QCalendarWidget QToolButton:hover {
    background: #2a2a3e;
    border-color: #3a3a52;
    color: #89b4fa;
}
QCalendarWidget QToolButton:pressed {
    background: #1e1e36;
}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {
    min-width: 28px;
    min-height: 28px;
    border-radius: 14px;
    qproperty-icon: none;
    font-size: 14px;
    color: #89b4fa;
}
QCalendarWidget QToolButton#qt_calendar_prevmonth { qproperty-text: "<"; }
QCalendarWidget QToolButton#qt_calendar_nextmonth { qproperty-text: ">"; }
QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {
    background: #1a2744;
    border-color: #89b4fa;
}
QCalendarWidget QSpinBox {
    background: #1a1a2a;
    color: #cdd6f4;
    border: 1px solid #2a2a3e;
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 13px;
    font-weight: 600;
    selection-background-color: #313150;
    selection-color: #89b4fa;
}
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {
    subcontrol-origin: border;
    width: 18px;
    background: #2a2a3e;
    border: none;
}
QCalendarWidget QSpinBox::up-button:hover,
QCalendarWidget QSpinBox::down-button:hover {
    background: #3a3a52;
}

/* Day grid */
QCalendarWidget QAbstractItemView {
    background: #13131f;
    color: #cdd6f4;
    font-size: 13px;
    outline: none;
    selection-background-color: #1a2744;
    selection-color: #89b4fa;
    border: none;
    padding: 2px;
}
QCalendarWidget QAbstractItemView:enabled {
    color: #cdd6f4;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #45475a;
}

/* Header row (day names) */
QCalendarWidget QWidget { alternate-background-color: #13131f; }
QCalendarWidget QHeaderView::section {
    background: #1a1a2a;
    color: #6c7086;
    border: none;
    border-bottom: 1px solid #2a2a3e;
    padding: 6px 4px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}

/* SpinBox in calendar (year) */
QCalendarWidget QMenu {
    background: #1a1a2a;
    border: 1px solid #3a3a52;
    border-radius: 6px;
    color: #cdd6f4;
    padding: 4px;
}
QCalendarWidget QMenu::item:selected {
    background: #313150;
    color: #89b4fa;
}

/* ── Tab widget ────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background: #13131f;
}
QTabBar::tab {
    background: #1a1a2a;
    color: #6c7086;
    border: 1px solid #2a2a3e;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #13131f;
    color: #89b4fa;
    border-color: #2a2a3e;
}
QTabBar::tab:hover:!selected {
    background: #1e1e30;
    color: #cdd6f4;
}

/* ── BDT Detail Panel — Command Console aesthetic ─────────── */
QWidget#bdt_detail_panel {
    background: #0d0d17;
}
QFrame#bdt_info_frame {
    background: #10101c;
    border: 1px solid #1c1c2c;
    border-radius: 8px;
    padding: 4px;
}
QLabel#bdt_info_key {
    color: #6c7086;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_info_val {
    color: #cdd6f4;
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_section_title {
    color: #6c7086;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    background: transparent;
    padding: 6px 0 4px 0;
}
QLabel#bdt_empty_hint {
    color: #45475a;
    font-size: 10px;
    font-style: italic;
    background: transparent;
    padding: 2px 2px 6px 2px;
}

/* "PREVIOUS TEST — yyyy-MM-dd" separator inside the photo scroll.
   Stronger weight and an accent-colored top border so the user
   instantly sees where a historical test starts. */
QLabel#bdt_history_separator {
    color: #fab387;
    background: #1a1528;
    border: 1px solid #2e2538;
    border-top: 2px solid #fab387;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 8px 12px;
    margin-top: 14px;
    margin-bottom: 4px;
}

/* ── BDT Photo Gallery ────────────────────────────────────── */
QScrollArea#bdt_photo_scroll {
    background: #0f0f1a;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
}
QScrollArea#bdt_info_scroll {
    background: transparent;
    border: none;
}
QScrollArea#bdt_info_scroll > QWidget > QWidget {
    background: transparent;
}
QWidget#bdt_photo_container {
    background: #0f0f1a;
}
QFrame#bdt_photo_card {
    background: #13131f;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
    padding: 4px;
}
QLabel#bdt_photo_label {
    color: #6c7086;
    font-size: 10px;
    font-weight: 600;
    background: transparent;
    padding: 2px 0 0 0;
}
QFrame#bdt_photo_missing {
    background: #1a1a2a;
    border: 2px dashed #f38ba8;
    border-radius: 6px;
    min-height: 120px;
}
QLabel#bdt_photo_missing_label {
    color: #f38ba8;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

/* ═══════════════════════════════════════════════════════════════ */
/*  FILTER PANEL — Command Console aesthetic                       */
/*  Info-dense NOC look: thin borders, accent rails, uppercase     */
/*  section caps, phosphor focus glow.                             */
/* ═══════════════════════════════════════════════════════════════ */

/* Outer panel — replaces the old GroupBox */
QFrame#filter_panel {
    background: #0d0d17;
    border: 1px solid #1e1e2e;
    border-top: 1px solid #232336;
    border-radius: 10px;
}

/* Tiny uppercase section cap label ("SITE", "CLASSIFICATION"…) */
QLabel#filter_section {
    color: #6c7086;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    background: transparent;
    padding: 0 0 2px 0;
}
QLabel#filter_section_active {
    color: #89b4fa;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    background: transparent;
    padding: 0 0 2px 0;
}

/* Subtle grouping container — no heavy box, just a darker tint */
QFrame#filter_group {
    background: #10101c;
    border: 1px solid #1c1c2c;
    border-radius: 8px;
}
QFrame#filter_group_date {
    background: #10101c;
    border: 1px solid #1c1c2c;
    border-left: 2px solid #45475a;
    border-radius: 8px;
}

/* Vertical accent rail — 2px stripe that marks a group as "active" */
QFrame#filter_rail {
    background: #2a2a3e;
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}
QFrame#filter_rail_active {
    background: #89b4fa;
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}

/* Inline label inside a group — muted, small, fixed weight */
QLabel#filter_inline {
    color: #7f849c;
    font-size: 11px;
    font-weight: 500;
    background: transparent;
    padding: 0 2px;
}

/* Refined inputs — darker surface, thin border, phosphor focus glow */
QLineEdit#filter_input {
    background: #0a0a14;
    border: 1px solid #20202e;
    border-radius: 6px;
    padding: 7px 11px;
    color: #cdd6f4;
    font-size: 13px;
    font-weight: 500;
    selection-background-color: #1e2a4a;
    selection-color: #cdd6f4;
    min-height: 26px;
}
QLineEdit#filter_input:hover {
    border-color: #2a2a3e;
    background: #0c0c18;
}
QLineEdit#filter_input:focus {
    border-color: #89b4fa;
    background: #0e0e1c;
}
QLineEdit#filter_input:disabled {
    background: #0a0a14;
    color: #45475a;
    border-color: #1a1a28;
}

/* Compact combo */
QComboBox#filter_combo {
    background: #0a0a14;
    border: 1px solid #20202e;
    border-radius: 6px;
    padding: 6px 10px;
    padding-right: 24px;
    color: #cdd6f4;
    font-size: 12px;
    font-weight: 600;
    min-height: 26px;
}
QComboBox#filter_combo:hover {
    border-color: #2a2a3e;
    background: #0c0c18;
}
QComboBox#filter_combo:focus, QComboBox#filter_combo:on {
    border-color: #89b4fa;
    background: #0e0e1c;
}
QComboBox#filter_combo::drop-down {
    border: none;
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}

/* Compact date picker inside filter panel */
QDateEdit#filter_date {
    background: #0a0a14;
    border: 1px solid #20202e;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QDateEdit#filter_date:hover {
    border-color: #2a2a3e;
    background: #0c0c18;
}
QDateEdit#filter_date:focus {
    border-color: #89b4fa;
    background: #0e0e1c;
}
QDateEdit#filter_date:disabled {
    background: #0a0a14;
    color: #45475a;
    border-color: #1a1a28;
}

/* Numeric spin inside filter panel */
QSpinBox#filter_spin {
    background: #0a0a14;
    border: 1px solid #20202e;
    border-radius: 6px;
    padding: 6px 8px;
    color: #cdd6f4;
    font-size: 12px;
    font-weight: 700;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QSpinBox#filter_spin:focus {
    border-color: #89b4fa;
    background: #0e0e1c;
}
QSpinBox#filter_spin:disabled {
    color: #45475a;
    border-color: #1a1a28;
}

/* Toggle-style checkbox — larger, accent fill when checked */
QCheckBox#filter_toggle {
    color: #a6adc8;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    background: transparent;
    spacing: 7px;
    padding: 2px 0;
}
QCheckBox#filter_toggle:disabled {
    color: #45475a;
}
QCheckBox#filter_toggle::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #2a2a3e;
    background: #0a0a14;
}
QCheckBox#filter_toggle::indicator:hover {
    border-color: #454560;
}
QCheckBox#filter_toggle::indicator:checked {
    background: #89b4fa;
    border: 1px solid #89b4fa;
    image: none;
}
QCheckBox#filter_toggle::indicator:disabled {
    background: #0a0a14;
    border-color: #1a1a28;
}

/* Pill-shaped quick-pick button */
QPushButton#btn_pill {
    background: #0a0a14;
    color: #7f849c;
    border: 1px solid #20202e;
    border-radius: 12px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-width: 0;
    min-height: 22px;
}
QPushButton#btn_pill:hover {
    background: #141424;
    color: #89b4fa;
    border-color: #3a4a7a;
}
QPushButton#btn_pill:pressed {
    background: #1a2744;
    color: #89b4fa;
    border-color: #89b4fa;
}
QPushButton#btn_pill:disabled {
    background: #0a0a14;
    color: #35354a;
    border-color: #1a1a28;
}

/* "Add" accent button for specific-days input */
QPushButton#btn_pill_accent {
    background: #1a2744;
    color: #89b4fa;
    border: 1px solid #2a4070;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-height: 22px;
}
QPushButton#btn_pill_accent:hover {
    background: #1f3258;
    color: #b4d0fa;
    border-color: #89b4fa;
}
QPushButton#btn_pill_accent:disabled {
    background: #0a0a14;
    color: #35354a;
    border-color: #1a1a28;
}

/* Ghost clear button */
QPushButton#btn_ghost {
    background: transparent;
    color: #6c7086;
    border: 1px solid #20202e;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    min-height: 22px;
}
QPushButton#btn_ghost:hover {
    color: #f38ba8;
    border-color: #5a2030;
    background: #1a0f14;
}
QPushButton#btn_ghost:disabled {
    color: #35354a;
    border-color: #1a1a28;
}
"""

STYLE_LIGHT = """
/* ── Base ──────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background: #eff1f5;
}
QWidget {
    background: #eff1f5;
    color: #4c4f69;
    font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
    font-size: 13px;
}

/* ── Left sidebar background ───────────────────────────────── */
QWidget#sidebar {
    background: #e6e9ef;
    border-right: 1px solid #bcc0cc;
}

/* ── Top header ─────────────────────────────────────────────── */
QWidget#header {
    background: #e6e9ef;
    border-bottom: 1px solid #bcc0cc;
}

/* ── GroupBox ───────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #bcc0cc;
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    color: #8c8fa1;
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    background: transparent;
}

/* ── Buttons ────────────────────────────────────────────────── */
QPushButton {
    background: #ccd0da;
    color: #4c4f69;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
    min-width: 0px;
}
QPushButton:hover {
    background: #bcc0cc;
    border-color: #1e66f5;
    color: #1e66f5;
}
QPushButton:pressed {
    background: #acb0be;
    border-color: #7287fd;
    color: #7287fd;
}
QPushButton:disabled {
    background: #dce0e8;
    border-color: #ccd0da;
    color: #9ca0b0;
}

/* Search — primary blue */
QPushButton#btn_search {
    background: #d5e0fc;
    color: #1e66f5;
    border: 1px solid #a8c2f8;
    min-width: 0px;
}
QPushButton#btn_search:hover {
    background: #c5d5fa;
    border-color: #1e66f5;
}

/* Clear — red */
QPushButton#btn_clear {
    background: #f5d0d8;
    color: #d20f39;
    border: 1px solid #e8a0b0;
}
QPushButton#btn_clear:hover {
    background: #f0c0cc;
    border-color: #d20f39;
}

/* Export — green */
QPushButton#btn_export {
    background: #d0eacc;
    color: #40a02b;
    border: 1px solid #a8d4a0;
}
QPushButton#btn_export:hover {
    background: #c0e0b8;
    border-color: #40a02b;
}

/* Backup Time — purple */
QPushButton#btn_backup {
    background: #e0d0f8;
    color: #8839ef;
    border: 1px solid #c8a8f0;
}
QPushButton#btn_backup:hover {
    background: #d4c0f4;
    border-color: #8839ef;
}

/* Both P+D — orange */
QPushButton#btn_both {
    background: #fce0c8;
    color: #fe640b;
    border: 1px solid #f0c8a0;
}
QPushButton#btn_both:hover {
    background: #f8d4b8;
    border-color: #fe640b;
}

/* Load — amber */
QPushButton#btn_load {
    background: #fce0c8;
    color: #fe640b;
    border: 1px solid #f0c8a0;
    font-size: 13px;
    padding: 8px 14px;
}
QPushButton#btn_load:hover {
    background: #f8d4b8;
    border-color: #fe640b;
}
QPushButton#btn_load:disabled {
    background: #dce0e8;
    border-color: #ccd0da;
    color: #9ca0b0;
}

/* Small selection buttons */
QPushButton#btn_small {
    background: #dce0e8;
    color: #8c8fa1;
    border: 1px solid #ccd0da;
    border-radius: 5px;
    padding: 4px 10px;
    min-width: 38px;
    font-size: 11px;
}
QPushButton#btn_small:hover {
    background: #ccd0da;
    color: #4c4f69;
    border-color: #acb0be;
}

/* Sidebar Browse/Scan */
QPushButton#btn_dir {
    background: #dce0e8;
    color: #1e66f5;
    border: 1px solid #a8c2f8;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    min-width: 60px;
}
QPushButton#btn_dir:hover {
    background: #d5e0fc;
    border-color: #1e66f5;
}

/* ── Inputs ─────────────────────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit {
    background: #dce0e8;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    padding: 6px 10px;
    color: #4c4f69;
    font-size: 13px;
    selection-background-color: #acb0be;
    selection-color: #4c4f69;
    min-height: 28px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
    border-color: #8c8fa1;
    background: #ccd0da;
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover {
    border-color: #acb0be;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: #dce0e8;
    border: 1px solid #acb0be;
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: #bcc0cc;
    selection-color: #1e66f5;
}

/* ── File list ──────────────────────────────────────────────── */
QListWidget {
    background: #e6e9ef;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    outline: none;
    padding: 2px;
}
QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
    margin: 1px 2px;
    color: #8c8fa1;
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 11px;
}
QListWidget::item:selected {
    background: #d5e0fc;
    color: #1e66f5;
    border: 1px solid #a8c2f8;
}
QListWidget::item:hover:!selected {
    background: #dce0e8;
    color: #6c6f85;
}

/* ── Tables ─────────────────────────────────────────────────── */
QTableView, QTableWidget {
    background: #e6e9ef;
    alternate-background-color: #eaecf3;
    border: 1px solid #bcc0cc;
    border-radius: 8px;
    gridline-color: #ccd0da;
    outline: none;
    selection-background-color: #d5e0fc;
}
QTableView::item, QTableWidget::item {
    padding: 3px 8px;
    border: none;
}
QTableView::item:selected, QTableWidget::item:selected {
    background: #d5e0fc;
    color: #4c4f69;
}
QHeaderView {
    background: transparent;
}
QHeaderView::section {
    background: #eff1f5;
    color: #8c8fa1;
    border: none;
    border-right: 1px solid #bcc0cc;
    border-bottom: 2px solid #bcc0cc;
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
QHeaderView::section:first {
    border-top-left-radius: 6px;
}
QHeaderView::section:hover {
    background: #e6e9ef;
    color: #1e66f5;
}
QHeaderView::section:checked {
    color: #1e66f5;
}

/* ── Scrollbars ─────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #bcc0cc;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #acb0be;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #bcc0cc;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #acb0be;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: #dce0e8;
    color: #9ca0b0;
    border-top: 1px solid #ccd0da;
    font-size: 11px;
    padding: 2px 8px;
}
QStatusBar::item {
    border: none;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    color: #4c4f69;
    background: transparent;
}
QLabel#lbl_app_name {
    color: #4c4f69;
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QLabel#lbl_app_ver {
    color: #acb0be;
    font-size: 11px;
}
QLabel#lbl_section {
    color: #9ca0b0;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}
QLabel#lbl_green {
    color: #40a02b;
    font-weight: 600;
    font-size: 12px;
}
/* ── Progress bar ───────────────────────────────────────────── */
QProgressBar {
    border: none;
    border-radius: 3px;
    background: #ccd0da;
    text-align: center;
    color: transparent;
    max-height: 4px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #1e66f5, stop:1 #8839ef);
    border-radius: 3px;
}

/* ── Splitter ───────────────────────────────────────────────── */
QSplitter::handle {
    background: #ccd0da;
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ── Calendar ───────────────────────────────────────────────── */
QCalendarWidget {
    background: #eff1f5;
    border: 1px solid #bcc0cc;
    border-radius: 8px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: #dce0e8;
    border-bottom: 1px solid #bcc0cc;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 4px 8px;
    min-height: 36px;
}
QCalendarWidget QToolButton {
    background: transparent;
    color: #4c4f69;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 13px;
    font-weight: 600;
}
QCalendarWidget QToolButton:hover {
    background: #ccd0da;
    border-color: #acb0be;
    color: #1e66f5;
}
QCalendarWidget QToolButton:pressed {
    background: #bcc0cc;
}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {
    min-width: 28px;
    min-height: 28px;
    border-radius: 14px;
    qproperty-icon: none;
    font-size: 14px;
    color: #1e66f5;
}
QCalendarWidget QToolButton#qt_calendar_prevmonth { qproperty-text: "<"; }
QCalendarWidget QToolButton#qt_calendar_nextmonth { qproperty-text: ">"; }
QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {
    background: #d5e0fc;
    border-color: #1e66f5;
}
QCalendarWidget QSpinBox {
    background: #dce0e8;
    color: #4c4f69;
    border: 1px solid #bcc0cc;
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 13px;
    font-weight: 600;
    selection-background-color: #acb0be;
    selection-color: #1e66f5;
}
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {
    subcontrol-origin: border;
    width: 18px;
    background: #ccd0da;
    border: none;
}
QCalendarWidget QSpinBox::up-button:hover,
QCalendarWidget QSpinBox::down-button:hover {
    background: #bcc0cc;
}

/* Day grid */
QCalendarWidget QAbstractItemView {
    background: #eff1f5;
    color: #4c4f69;
    font-size: 13px;
    outline: none;
    selection-background-color: #d5e0fc;
    selection-color: #1e66f5;
    border: none;
    padding: 2px;
}
QCalendarWidget QAbstractItemView:enabled {
    color: #4c4f69;
}
QCalendarWidget QAbstractItemView:disabled {
    color: #9ca0b0;
}

/* Header row (day names) */
QCalendarWidget QWidget { alternate-background-color: #eff1f5; }
QCalendarWidget QHeaderView::section {
    background: #dce0e8;
    color: #8c8fa1;
    border: none;
    border-bottom: 1px solid #bcc0cc;
    padding: 6px 4px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}

/* SpinBox in calendar (year) */
QCalendarWidget QMenu {
    background: #dce0e8;
    border: 1px solid #acb0be;
    border-radius: 6px;
    color: #4c4f69;
    padding: 4px;
}
QCalendarWidget QMenu::item:selected {
    background: #bcc0cc;
    color: #1e66f5;
}

/* ── Tab widget ────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background: #eff1f5;
}
QTabBar::tab {
    background: #dce0e8;
    color: #8c8fa1;
    border: 1px solid #bcc0cc;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: #eff1f5;
    color: #1e66f5;
    border-color: #bcc0cc;
}
QTabBar::tab:hover:!selected {
    background: #ccd0da;
    color: #4c4f69;
}

/* ── BDT Detail Panel — Command Console aesthetic ─────────── */
QWidget#bdt_detail_panel {
    background: #e6e9ef;
}
QFrame#bdt_info_frame {
    background: #dce0e8;
    border: 1px solid #ccd0da;
    border-radius: 8px;
    padding: 4px;
}
QLabel#bdt_info_key {
    color: #8c8fa1;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_info_val {
    color: #4c4f69;
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_section_title {
    color: #8c8fa1;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    background: transparent;
    padding: 6px 0 4px 0;
}
QLabel#bdt_empty_hint {
    color: #9ca0b0;
    font-size: 10px;
    font-style: italic;
    background: transparent;
    padding: 2px 2px 6px 2px;
}

/* "PREVIOUS TEST — yyyy-MM-dd" separator inside the photo scroll.
   Stronger weight and an accent-colored top border so the user
   instantly sees where a historical test starts. */
QLabel#bdt_history_separator {
    color: #fe640b;
    background: #fce0c8;
    border: 1px solid #f0c8a0;
    border-top: 2px solid #fe640b;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    padding: 8px 12px;
    margin-top: 14px;
    margin-bottom: 4px;
}

/* ── BDT Photo Gallery ────────────────────────────────────── */
QScrollArea#bdt_photo_scroll {
    background: #e6e9ef;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
}
QScrollArea#bdt_info_scroll {
    background: transparent;
    border: none;
}
QScrollArea#bdt_info_scroll > QWidget > QWidget {
    background: transparent;
}
QWidget#bdt_photo_container {
    background: #e6e9ef;
}
QFrame#bdt_photo_card {
    background: #eff1f5;
    border: 1px solid #bcc0cc;
    border-radius: 6px;
    padding: 4px;
}
QLabel#bdt_photo_label {
    color: #8c8fa1;
    font-size: 10px;
    font-weight: 600;
    background: transparent;
    padding: 2px 0 0 0;
}
QFrame#bdt_photo_missing {
    background: #dce0e8;
    border: 2px dashed #d20f39;
    border-radius: 6px;
    min-height: 120px;
}
QLabel#bdt_photo_missing_label {
    color: #d20f39;
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

/* ═══════════════════════════════════════════════════════════════ */
/*  FILTER PANEL — Command Console aesthetic                       */
/*  Info-dense NOC look: thin borders, accent rails, uppercase     */
/*  section caps, phosphor focus glow.                             */
/* ═══════════════════════════════════════════════════════════════ */

/* Outer panel — replaces the old GroupBox */
QFrame#filter_panel {
    background: #e6e9ef;
    border: 1px solid #ccd0da;
    border-top: 1px solid #bcc0cc;
    border-radius: 10px;
}

/* Tiny uppercase section cap label ("SITE", "CLASSIFICATION"…) */
QLabel#filter_section {
    color: #8c8fa1;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    background: transparent;
    padding: 0 0 2px 0;
}
QLabel#filter_section_active {
    color: #1e66f5;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.6px;
    text-transform: uppercase;
    background: transparent;
    padding: 0 0 2px 0;
}

/* Subtle grouping container — no heavy box, just a lighter tint */
QFrame#filter_group {
    background: #dce0e8;
    border: 1px solid #ccd0da;
    border-radius: 8px;
}
QFrame#filter_group_date {
    background: #dce0e8;
    border: 1px solid #ccd0da;
    border-left: 2px solid #9ca0b0;
    border-radius: 8px;
}

/* Vertical accent rail — 2px stripe that marks a group as "active" */
QFrame#filter_rail {
    background: #bcc0cc;
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}
QFrame#filter_rail_active {
    background: #1e66f5;
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}

/* Inline label inside a group — muted, small, fixed weight */
QLabel#filter_inline {
    color: #7c7f93;
    font-size: 11px;
    font-weight: 500;
    background: transparent;
    padding: 0 2px;
}

/* Refined inputs — lighter surface, thin border, blue focus glow */
QLineEdit#filter_input {
    background: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 7px 11px;
    color: #4c4f69;
    font-size: 13px;
    font-weight: 500;
    selection-background-color: #d5e0fc;
    selection-color: #4c4f69;
    min-height: 26px;
}
QLineEdit#filter_input:hover {
    border-color: #bcc0cc;
    background: #eaecf3;
}
QLineEdit#filter_input:focus {
    border-color: #1e66f5;
    background: #e6e9ef;
}
QLineEdit#filter_input:disabled {
    background: #eff1f5;
    color: #9ca0b0;
    border-color: #dce0e8;
}

/* Compact combo */
QComboBox#filter_combo {
    background: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 6px 10px;
    padding-right: 24px;
    color: #4c4f69;
    font-size: 12px;
    font-weight: 600;
    min-height: 26px;
}
QComboBox#filter_combo:hover {
    border-color: #bcc0cc;
    background: #eaecf3;
}
QComboBox#filter_combo:focus, QComboBox#filter_combo:on {
    border-color: #1e66f5;
    background: #e6e9ef;
}
QComboBox#filter_combo::drop-down {
    border: none;
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}

/* Compact date picker inside filter panel */
QDateEdit#filter_date {
    background: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 6px 10px;
    color: #4c4f69;
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QDateEdit#filter_date:hover {
    border-color: #bcc0cc;
    background: #eaecf3;
}
QDateEdit#filter_date:focus {
    border-color: #1e66f5;
    background: #e6e9ef;
}
QDateEdit#filter_date:disabled {
    background: #eff1f5;
    color: #9ca0b0;
    border-color: #dce0e8;
}

/* Numeric spin inside filter panel */
QSpinBox#filter_spin {
    background: #eff1f5;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 6px 8px;
    color: #4c4f69;
    font-size: 12px;
    font-weight: 700;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QSpinBox#filter_spin:focus {
    border-color: #1e66f5;
    background: #e6e9ef;
}
QSpinBox#filter_spin:disabled {
    color: #9ca0b0;
    border-color: #dce0e8;
}

/* Toggle-style checkbox — larger, accent fill when checked */
QCheckBox#filter_toggle {
    color: #6c6f85;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    background: transparent;
    spacing: 7px;
    padding: 2px 0;
}
QCheckBox#filter_toggle:disabled {
    color: #9ca0b0;
}
QCheckBox#filter_toggle::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #bcc0cc;
    background: #eff1f5;
}
QCheckBox#filter_toggle::indicator:hover {
    border-color: #8c8fa1;
}
QCheckBox#filter_toggle::indicator:checked {
    background: #1e66f5;
    border: 1px solid #1e66f5;
    image: none;
}
QCheckBox#filter_toggle::indicator:disabled {
    background: #eff1f5;
    border-color: #dce0e8;
}

/* Pill-shaped quick-pick button */
QPushButton#btn_pill {
    background: #eff1f5;
    color: #7c7f93;
    border: 1px solid #ccd0da;
    border-radius: 12px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-width: 0;
    min-height: 22px;
}
QPushButton#btn_pill:hover {
    background: #e6e9ef;
    color: #1e66f5;
    border-color: #8aaef0;
}
QPushButton#btn_pill:pressed {
    background: #d5e0fc;
    color: #1e66f5;
    border-color: #1e66f5;
}
QPushButton#btn_pill:disabled {
    background: #eff1f5;
    color: #bcc0cc;
    border-color: #dce0e8;
}

/* "Add" accent button for specific-days input */
QPushButton#btn_pill_accent {
    background: #d5e0fc;
    color: #1e66f5;
    border: 1px solid #a8c2f8;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-height: 22px;
}
QPushButton#btn_pill_accent:hover {
    background: #c5d5fa;
    color: #1450c8;
    border-color: #1e66f5;
}
QPushButton#btn_pill_accent:disabled {
    background: #eff1f5;
    color: #bcc0cc;
    border-color: #dce0e8;
}

/* Ghost clear button */
QPushButton#btn_ghost {
    background: transparent;
    color: #8c8fa1;
    border: 1px solid #ccd0da;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    min-height: 22px;
}
QPushButton#btn_ghost:hover {
    color: #d20f39;
    border-color: #e8a0b0;
    background: #fce8ec;
}
QPushButton#btn_ghost:disabled {
    color: #bcc0cc;
    border-color: #dce0e8;
}
"""

# Backwards compatibility
STYLE = STYLE_DARK
