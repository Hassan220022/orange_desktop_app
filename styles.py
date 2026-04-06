"""
Stylesheet — Catppuccin Mocha-inspired professional dark theme.
Kept in a separate module so the main window code stays clean.
"""

STYLE = """
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

/* ── BDT Detail Panel ──────────────────────────────────────── */
QWidget#bdt_detail_panel {
    background: #0f0f1a;
}
QFrame#bdt_info_frame {
    background: #0f0f1a;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
    padding: 8px;
}
QLabel#bdt_info_key {
    color: #6c7086;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: transparent;
}
QLabel#bdt_info_val {
    color: #cdd6f4;
    font-size: 12px;
    background: transparent;
}
QLabel#bdt_section_title {
    color: #89b4fa;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.8px;
    background: transparent;
    padding: 4px 0;
}

/* ── BDT Photo Gallery ────────────────────────────────────── */
QScrollArea#bdt_photo_scroll {
    background: #0f0f1a;
    border: 1px solid #2a2a3e;
    border-radius: 6px;
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
"""
