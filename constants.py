"""
Constants — schema maps, display columns, app metadata.
"""

try:
    from alarm_app.versioning import get_app_version
except ImportError:
    from versioning import get_app_version  # type: ignore[no-redef]  # PyInstaller flat bundle

APP_NAME    = "Alarm Viewer"
APP_VERSION = get_app_version()

# ── Huawei schema ────────────────────────────────────────────────
SCHEMA_1_MAP = {
    "Alarm Source":           "alarm_source",
    "Site Name":              "site_id",
    "Last Occurred On":       "occurred_on",
    "Cleared On":             "cleared_on",
    "Duration(hh:mm:ss)":     "duration",
    "Alarm ID":               "alarm_id",
    "Alarm Name":             "alarm_name",
    "Clearance Status":       "clearance_status",
    "Network Type":           "network_type",
    "Vendor":                 "vendor",
}

# ── Nokia schema ─────────────────────────────────────────────────
SCHEMA_2_MAP = {
    "Clearance Status": "clearance_status",
    "Site ID":          "site_id",
    "Alarm ID":         "alarm_id",
    "Vendor":           "vendor",
    "Alarm Source":     "alarm_source",
    "Alarm Name":       "alarm_name",
    "Network Type":     "network_type",
    "Last Occurred On": "occurred_on",
    "Cleared On":       "cleared_on",
}

# ── Ordered display columns ──────────────────────────────────────
DISPLAY_COLUMNS = [
    ("site_id",          "Site ID"),
    ("alarm_name",       "Alarm Name"),
    ("alarm_id",         "Alarm ID"),
    ("network_type",     "Network"),
    ("vendor",           "Vendor"),
    ("occurred_on",      "Occurred On"),
    ("cleared_on",       "Cleared On"),
    ("duration",         "Duration"),
    ("clearance_status", "Status"),
    ("alarm_source",     "Alarm Source"),
    ("site_down_flag",   "Site Down?"),
    ("alarm_category",   "Category"),
    ("file_source",      "Source File"),
]

ALL_INTERNAL_COLS = [k for k, _ in DISPLAY_COLUMNS]

# ── Column widths for table ──────────────────────────────────────
COL_WIDTHS = {
    "site_id":          90,
    "alarm_name":      300,
    "alarm_id":         75,
    "network_type":     75,
    "vendor":           80,
    "occurred_on":     165,
    "cleared_on":      165,
    "duration":        100,
    "clearance_status": 85,
    "alarm_source":    270,
    "site_down_flag":   80,
    "alarm_category":   80,
    "file_source":     210,
}

# ── Backup-time dialog constants ─────────────────────────────────
BT_HEADERS = {
    "site_id":        "Site ID",
    "network_type":   "Network",
    "vendor":         "Vendor",
    "power_time":     "Power Alarm (mains failed)",
    "power_cleared":  "Power Cleared (mains restored)",
    "down_time":      "Down Alarm (site down)",
    "end_event_type": "Matched End Path",
    "backup_time":    "Backup Duration  (HH:MM:SS)",
}

BT_WIDTHS = {
    "site_id": 90, "network_type": 70, "vendor": 80,
    "power_time": 185, "power_cleared": 185,
    "down_time": 185, "end_event_type": 130, "backup_time": 160,
}

TEMP_HEADERS = {
    "site_id": "Site ID",
    "network_type": "Network",
    "vendor": "Vendor",
    "power_time": "Power Alarm",
    "power_cleared": "Power Cleared",
    "x_duration": "X Duration",
    "y_margin": "Y Margin",
    "temp_time": "Temp Alarm",
    "temp_cleared": "Temp Cleared",
    "temp_delay_after_power": "Temp After Power",
    "temp_delay_after_power_clearance": "Temp After Clearance",
    "temp_clear_duration": "Temp Clear Duration",
    "temp_alarm_name": "Temp Alarm Name",
    "temp_alarm_source": "Temp Alarm Source",
    "temp_clearance_status": "Status",
    "match_window": "Coverage Status",
}

TEMP_WIDTHS = {
    "site_id": 90, "network_type": 70, "vendor": 80,
    "power_time": 175, "power_cleared": 175, "x_duration": 105,
    "y_margin": 90, "temp_time": 175, "temp_cleared": 175,
    "temp_delay_after_power": 140, "temp_delay_after_power_clearance": 165,
    "temp_clear_duration": 135, "temp_alarm_name": 220,
    "temp_alarm_source": 240, "temp_clearance_status": 90,
    "match_window": 120,
}

# ── HT Meet Workbook dialog constants ──────────────────────────
HT_MEET_HEADERS = {
    "Site Name": "Site Name",
    "Alarm Source": "Alarm Source",
    "Last Occurred On": "Last Occurred On",
    "Cleared On": "Cleared On",
    "Duration(hh:mm:ss)": "Duration",
    "Alarm Name": "Alarm Name",
    "Clearance Status": "Status",
    "Cleared By": "Cleared By",
    "Alarm Reporting Type": "Reporting Type",
}

HT_MEET_WIDTHS = {
    "Site Name": 200,
    "Alarm Source": 280,
    "Last Occurred On": 170,
    "Cleared On": 170,
    "Duration(hh:mm:ss)": 135,
    "Alarm Name": 220,
    "Clearance Status": 90,
    "Cleared By": 130,
    "Alarm Reporting Type": 130,
}

# ── BDT validation constants ──────────────────────────────
BDT_DEFAULT_TOLERANCE = 0.15   # 15% — fractional sizing tolerance for R8
BDT_DEFAULT_HEALTH_PCT = 0.80  # 80% default battery health (lead-acid)
BDT_DISCHARGE_CURRENT_TOLERANCE_A = 1.0   # R9 — discharge current absolute floor (A)
BDT_DISCHARGE_CURRENT_PCT = 0.03          # R9 — discharge current % tolerance of baseline (3%)
BDT_DISCHARGE_CURRENT_ACCEPT_A = 15.0     # R9 — accept band max |ΔI| when slope is calm
BDT_DISCHARGE_SLOPE_ACCEPT_A_PER_MIN = 0.12   # R9 — accept band bus-amp slope (A/min)
BDT_DISCHARGE_SLOPE_REJECT_A_PER_MIN = 0.20   # R9 — reject band bus-amp slope (A/min)
BDT_DISCHARGE_SPIKE_REJECT_A = 10.0       # R9 — late-interval spike reject threshold (A)
BDT_STRING_AMPERE_TOLERANCE_A = 3.0       # R3 — max strings-above-bus (negative diff reject)
BDT_STRING_AMPERE_POS_TOLERANCE_A = 0.5   # R3 — legacy positive diff (superseded by accept/revise)
BDT_STRING_AMPERE_POS_ACCEPT_A = 1.5      # R3 — accept band max bus-above-strings (A)
BDT_STRING_AMPERE_POS_REVISE_A = 5.0      # R3 — revise band max bus-above-strings (A)
BDT_STRING_IMBALANCE_REJECT_RATIO = 0.85  # R3 — one string share that triggers reject
BDT_STRING_IMBALANCE_REVISE_RATIO = 0.70  # R3 — milder imbalance revise band
BDT_INCOMPLETE_REJECT_MINUTES = 30        # R2/R6 — severe incomplete discharge threshold
BDT_INCOMPLETE_REVISE_MINUTES = 90        # R2/R6 — weak/short backup revise threshold
BDT_OVERALL_IGNORE_NA_RULES = ("R11", "R5", "R7")
BDT_POWER_TIMING_TOLERANCE_MIN = 15       # R2 — power-alarm timing window (minutes)
BDT_START_AMPERE_THRESHOLD_A = 1.0        # R5 — starting I-Battery |I| tolerance for human-reviewed idle current
BDT_COMPLETION_MINUTES = 180              # R6/R8 — discharge target ceiling (minutes)
BDT_END_VOLTAGE_MIN = 45.0                # R6 — acceptable end voltage min (V)
BDT_END_VOLTAGE_MAX = 47.0                # R6 — acceptable end voltage max (V)
BDT_SIZING_TOLERANCE_MINUTES = 15         # R8 — minutes floor for sizing window
BDT_LITHIUM_HEALTH_MIN = 0.95
BDT_LITHIUM_HEALTH_MAX = 1.00
BDT_SIZING_SKIP_MINUTES = 180
BDT_REQUIRED_PHOTO_CATEGORIES = ("rectifier", "batteries")
BDT_REQUIRED_PHOTO_COUNT = 16

BDT_RULES = [
    ("R1", "Photos"),
    ("R2", "Power Alarm + Duration"),
    ("R3", "String vs Bus Bar Ampere"),
    ("R5", "Starting I-Battery ampere"),
    ("R6", "End Voltage Range"),
    ("R7", "V/A Inverse"),
    ("R8", "Sizing vs Actual"),
    ("R9", "Discharge Current Tolerance"),
    ("R10", "Door Alarm Condition"),
    ("R11", "Summary Checklist"),
]
BDT_RULE_NAME_BY_CODE = dict(BDT_RULES)


def format_bdt_rule_label(rule_code: str, rule_name: str | None = None) -> str:
    code = str(rule_code or "").strip()
    if not code:
        return str(rule_name or "").strip()
    name = str(rule_name or BDT_RULE_NAME_BY_CODE.get(code, "")).strip()
    return f"{code} - {name}" if name else code

BDT_RESULT_HEADERS = [
    "File", "Site Code", "Test Date", "Verdict", "Insight Status", "Insight Severity", "Battery Status",
    "R1", "R2", "R3", "R5", "R6", "R7", "R8", "R9", "R10", "R11",
    "End Rectifier Voltage (V)", "Lead-acid SOH (%)",
]

BDT_RULE_DETAIL_HEADERS = [f"{rule_id} Detail" for rule_id, _ in BDT_RULES]
BDT_VALIDATION_EXPORT_HEADERS = BDT_RESULT_HEADERS + BDT_RULE_DETAIL_HEADERS

BDT_PM_SUMMARY_HEADERS = [
    "Week", "Ser", "Site Name", "Short Code", "On Air Date",
    "Nodal Degree", "PLD Value", "Linked sites name codes", "Type",
    "Site Category", "Power Source", "# of BSC", "BSC Type", "# of BTS",
    "BTS Type", "# of GSM/MRFU/RF", "# of DSC/MRFU/RF", "# of MW", "MW Type",
    "# of SDH", "# of ADM", "# of Routers", "AC1 Type", "AC1 HP", "AC2 Type",
    "AC2 HP", "3G Type", "No. Of 3G RF", "4G Type", "No. Of 4G RF",
    "Orange office", "Subcontractor", "Office", "Area", "Network",
    "Rectifier Brand", "# of Modules", "Battery Brand", "Battery Volt",
    "Battery Ampere Hour", "No of String", "No of Batteries", "Start Volt",
    "Start Amp", "Charging current", "End Volt", "End Amp",
    "Discharge time( Mins)", "Reason for Stop BDT", "Test Date",
    "Reason for Repeated BDT", "CAP request", "Comment",
]

BDT_SUMMARY_SHEET_NAME = "BDT 2025-2026"
BDT_SUMMARY_EXPORT_HEADERS = [
    "Week", "Ser", "Site Name", "Short Code", "On Air Date",
    "Nodal Degree", "PLD Value", "Linked sites name codes", "Type",
    "Site Category", "Power Source", "# of BSC", "BSC Type", "# of BTS",
    "BTS Type", "# of GSM/MRFU/RF", "# of DSC/MRFU/RF", "# of MW", "MW Type",
    "# of SDH", "# of ADM", "# of Routers", "AC1 Type", "AC1 HP", "AC2 Type",
    "AC2 HP", "3G Type", "No. Of 3G RF", "4G Type", "No. Of 4G RF",
    "Orange office", "Subcontractor", "Office", "Area", "Network",
    "Rectifier Brand", "# of Modules", "Battery Brand", "Battery Volt",
    "Battery Ampere Hour", "No of String", "No of Batteries ", "Start Volt",
    "Start Amp", "Charging current", "End Volt", "End Amp",
    "Discharge time( Mins)", "Reason for Stop BDT", "Test Date",
    "Reason for Repeated BDT", "CAP request ", "Comment",
]

BDT_RESULT_WIDTHS = {
    "File": 200, "Site Code": 90, "Test Date": 100, "Verdict": 90,
    "Insight Status": 220, "Insight Severity": 110,
    "Battery Status": 120,
    "R1": 65, "R2": 65, "R3": 65,
    "R5": 65, "R6": 65, "R7": 65, "R8": 65, "R9": 65, "R10": 65, "R11": 65,
    "End Rectifier Voltage (V)": 170,
    "Lead-acid SOH (%)": 150,
    "R1 Detail": 300, "R2 Detail": 300, "R3 Detail": 300,
    "R5 Detail": 300, "R6 Detail": 300, "R7 Detail": 300,
    "R8 Detail": 300, "R9 Detail": 300, "R10 Detail": 300, "R11 Detail": 300,
}
