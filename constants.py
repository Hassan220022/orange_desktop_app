"""
Constants — schema maps, display columns, app metadata.
"""

APP_NAME    = "Alarm Viewer"
APP_VERSION = "0.1.7"

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
    "backup_time":    "Backup Duration  (HH:MM:SS)",
}

BT_WIDTHS = {
    "site_id": 90, "network_type": 70, "vendor": 80,
    "power_time": 185, "power_cleared": 185,
    "down_time": 185, "backup_time": 160,
}

# ── BDT validation constants ──────────────────────────────
BDT_DEFAULT_TOLERANCE = 0.15   # 15%
BDT_DEFAULT_HEALTH_PCT = 0.80  # 80% default battery health
BDT_DISCHARGE_CURRENT_TOLERANCE_A = 1.0
BDT_STRING_AMPERE_TOLERANCE_A = 3.0
BDT_POWER_TIMING_TOLERANCE_MIN = 15
BDT_COMPLETION_MINUTES = 180
BDT_END_VOLTAGE_MIN = 45.0
BDT_END_VOLTAGE_MAX = 47.0
BDT_SIZING_TOLERANCE_MINUTES = 15
BDT_LITHIUM_HEALTH_MIN = 0.95
BDT_LITHIUM_HEALTH_MAX = 1.00
BDT_SIZING_SKIP_MINUTES = 180
BDT_REQUIRED_PHOTO_CATEGORIES = ("rectifier", "batteries")
BDT_REQUIRED_PHOTO_COUNT = 16

BDT_RULES = [
    ("R1", "Photos"),
    ("R2", "Power Alarm + Duration"),
    ("R3", "String vs Bus Bar Ampere"),
    ("R4", "Discharge Table Match"),
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
    "File", "Site Code", "Test Date", "Verdict",
    "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11",
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
    "R1": 65, "R2": 65, "R3": 65, "R4": 65,
    "R5": 65, "R6": 65, "R7": 65, "R8": 65, "R9": 65, "R10": 65, "R11": 65,
    "End Rectifier Voltage (V)": 170,
    "Lead-acid SOH (%)": 150,
    "R1 Detail": 300, "R2 Detail": 300, "R3 Detail": 300, "R4 Detail": 300,
    "R5 Detail": 300, "R6 Detail": 300, "R7 Detail": 300,
    "R8 Detail": 300, "R9 Detail": 300, "R10 Detail": 300, "R11 Detail": 300,
}
