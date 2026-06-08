"""Shared Network Summary/BDT battery backup insight rules."""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from alarm_app.core.battery_topology import (
        build_battery_topology,
        is_lead_acid_to_lithium_upgrade,
    )
except ImportError:
    from core.battery_topology import (
        build_battery_topology,
        is_lead_acid_to_lithium_upgrade,
    )


FAILED_RULE_VERDICTS = {"REJECTED", "REVISE", "NO DATA", "FAILED"}


def jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def coerce_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = text(value)
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def build_snapshot_freshness(
    *,
    has_network_rows: bool,
    network_summary_date: Any,
    bdt_test_date: Any,
) -> dict[str, Any]:
    warnings: list[str] = []
    network_date = coerce_date(network_summary_date)
    bdt_date = coerce_date(bdt_test_date)

    if not has_network_rows:
        warnings.append("No Network Summary row was available for this BDT comparison.")
        status = "network_summary_missing"
    elif network_date is None:
        warnings.append("Network Summary row has no usable recent test/reporting date, so freshness cannot be verified.")
        status = "network_summary_date_missing"
    elif bdt_date is None:
        warnings.append("BDT test date is missing, so Network Summary freshness cannot be compared to the BDT.")
        status = "bdt_date_missing"
    elif network_date < bdt_date:
        warnings.append("Network Summary snapshot is older than the BDT test date; matching values may still be stale.")
        status = "network_summary_older_than_bdt"
    elif network_date > bdt_date:
        status = "network_summary_newer_than_bdt"
    else:
        status = "same_date"

    return {
        "status": status,
        "network_summary_date": network_date.isoformat() if network_date else text(network_summary_date),
        "bdt_test_date": bdt_date.isoformat() if bdt_date else text(bdt_test_date),
        "warnings": warnings,
    }


def snapshot_status_is_stale(
    network_rows: list[dict[str, Any]],
    network_summary_date: Any,
    bdt_test_date: Any,
) -> bool:
    freshness = build_snapshot_freshness(
        has_network_rows=bool(network_rows),
        network_summary_date=network_summary_date,
        bdt_test_date=bdt_test_date,
    )
    return freshness.get("status") == "network_summary_older_than_bdt"


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).replace("\xa0", " ").strip()


def upper(value: Any) -> str:
    return text(value).upper()


def first_non_empty(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    return value


def first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            value = first_non_empty(row.get(key))
            if value is not None:
                return value
    return None


def coerce_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def coerce_int(value: Any) -> int | None:
    parsed = coerce_number(value)
    if parsed is None:
        return None
    try:
        return int(parsed)
    except (TypeError, ValueError):
        return None


def is_placeholder(value: Any) -> bool:
    return upper(value) in {"", "_", "NON", "NONE", "NO", "N/A", "NA", "0", "NOT AVAILABLE", "NOTAVAILABLE"}


def tokens(value: Any) -> set[str]:
    return {token for token in re.split(r"[^A-Z0-9]+", upper(value)) if len(token) >= 3}


def strings_match(left: Any, right: Any) -> bool:
    left_tokens = tokens(left)
    right_tokens = tokens(right)
    if not left_tokens or not right_tokens:
        return True
    return bool(left_tokens & right_tokens)


def max_severity(current: str, candidate: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


def section_rows(payload: dict[str, Any], name: str) -> list[dict[str, Any]]:
    section = payload.get(name) if isinstance(payload, dict) else None
    rows = section.get("rows", []) if isinstance(section, dict) else []
    return rows if isinstance(rows, list) else []


def section_total(payload: dict[str, Any], name: str) -> int:
    section = payload.get(name) if isinstance(payload, dict) else None
    if not isinstance(section, dict):
        return 0
    try:
        return int(section.get("total") if section.get("total") is not None else section.get("returned") or 0)
    except (TypeError, ValueError):
        return 0


def expand_network_summary_row(row: dict[str, Any]) -> dict[str, Any]:
    expanded = dict(row)
    raw_rows: dict[str, Any] | None = None
    raw_value = expanded.get("raw_data_json")
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            parsed = None
        if isinstance(parsed, dict):
            raw_rows = parsed
            for key, value in parsed.items():
                expanded.setdefault(str(key), value)

    headers_json = expanded.get("original_headers_json")
    if isinstance(headers_json, str) and headers_json.strip() and raw_rows:
        try:
            headers = json.loads(headers_json)
        except (TypeError, json.JSONDecodeError):
            headers = None
        if isinstance(headers, dict):
            for original_field, normalized_key in headers.items():
                source_key = str(normalized_key)
                if source_key in raw_rows:
                    expanded[str(original_field)] = raw_rows[source_key]

    expanded.pop("raw_data_json", None)
    expanded.pop("original_headers_json", None)
    return jsonable(expanded)


@dataclass
class NetworkBatteryContext:
    has_network_summary: bool
    no_usable_backup: bool
    backup_minutes: float | None = None
    reasons: list[str] = field(default_factory=list)
    battery_type_missing: bool = False
    raw_fields: dict[str, Any] = field(default_factory=dict)


def resolve_network_battery_context(
    network_rows: list[dict[str, Any]] | None,
    min_backup_minutes: float,
) -> NetworkBatteryContext:
    rows = list(network_rows or [])
    if not rows:
        return NetworkBatteryContext(has_network_summary=False, no_usable_backup=False)

    row = expand_network_summary_row(rows[0])
    battery_type = first(
        row,
        "battery_type",
        "Battery Type",
        "installed_battery_type",
        "Installed Battery Type",
        "battery_status",
    )
    installed_battery_type = first(row, "installed_battery_type", "Installed Battery Type")
    backup_status = first(row, "backup_status", "Backup Status")
    batt_reason = first(row, "batt_reason", "Batt Reason")
    backup_minutes = coerce_number(first(row, "backup_minutes", "Backup Minutes"))
    no_of_strings = coerce_int(first(
        row,
        "no_of_strings",
        "No of String",
        "No of Strings",
        "No. of Strings",
        "# of Strings",
        "num_strings",
    ))

    reasons: list[str] = []
    backup_status_text = upper(backup_status)
    batt_reason_text = upper(batt_reason)
    if "ZERO BACKUP" in backup_status_text or "ZERO BACKUP" in batt_reason_text:
        reasons.append("Network Summary backup status is ZERO BACKUP")
    if "STOLEN" in backup_status_text or "STOLEN" in batt_reason_text:
        reasons.append("Network Summary battery is marked STOLEN")
    if "REMOVED" in backup_status_text or "REMOVED" in batt_reason_text:
        reasons.append("Network Summary battery is marked REMOVED")
    if no_of_strings is not None and no_of_strings <= 0:
        reasons.append(f"Network Summary No of Strings is {no_of_strings}")
    if backup_minutes is not None and backup_minutes < float(min_backup_minutes):
        reasons.append(
            f"Network Summary backup minutes {backup_minutes:g} is below "
            f"{float(min_backup_minutes):g} minutes"
        )

    return NetworkBatteryContext(
        has_network_summary=True,
        no_usable_backup=bool(reasons),
        backup_minutes=backup_minutes,
        reasons=reasons,
        battery_type_missing=is_placeholder(battery_type) and is_placeholder(installed_battery_type),
        raw_fields={
            "battery_type": text(battery_type),
            "installed_battery_type": text(installed_battery_type),
            "backup_status": text(backup_status),
            "batt_reason": text(batt_reason),
            "backup_minutes": backup_minutes,
            "no_of_strings": no_of_strings,
        },
    )


def load_network_summary_rows_for_site(site_code: str, *, limit: int = 10) -> list[dict[str, Any]]:
    try:
        from alarm_app.data import catalog_store
    except ImportError:
        from data import catalog_store

    df = catalog_store.query_site_metadata(site_code)
    if df is None or df.empty:
        return []
    rows = df.head(max(int(limit), 0)).to_dict(orient="records")
    return [expand_network_summary_row(row) for row in rows if isinstance(row, dict)]


def build_battery_backup_insight(
    *,
    site_row: dict[str, Any],
    network_rows: list[dict[str, Any]],
    bdt_payload: dict[str, Any],
    min_backup_minutes: float = 90.0,
    backup_minutes_tolerance: float = 30.0,
) -> dict[str, Any]:
    site_id = str(site_row.get("site_id") or site_row.get("site_code") or "").strip()
    network_row = expand_network_summary_row(network_rows[0]) if network_rows else dict(site_row)

    bdt_tests = section_rows(bdt_payload, "bdt_tests")
    validation_runs = section_rows(bdt_payload, "validation_runs")
    rule_results = section_rows(bdt_payload, "rule_results")
    bdt_summary = section_rows(bdt_payload, "bdt_summary")

    latest_test = bdt_tests[0] if bdt_tests else {}
    latest_run = validation_runs[0] if validation_runs else {}

    battery_type = first(
        network_row,
        "battery_type",
        "Battery Type",
        "installed_battery_type",
        "Installed Battery Type",
        "battery_status",
    )
    installed_battery_type = first(network_row, "installed_battery_type", "Installed Battery Type")
    backup_status = first(network_row, "backup_status", "Backup Status")
    backup_minutes = coerce_number(first(network_row, "backup_minutes", "Backup Minutes"))
    no_of_strings = coerce_int(first(network_row, "no_of_strings", "No of Strings", "num_strings"))
    network_battery_voltage = coerce_number(first(network_row, "battery_voltage", "Battery Voltage", "Battery Volt"))
    network_battery_ah = coerce_number(first(network_row, "battery_ah", "Battery AH", "Battery Capacity"))
    network_num_batteries = coerce_int(first(network_row, "num_batteries", "No of Batteries", "Number of Batteries"))
    batt_reason = first(network_row, "batt_reason", "Batt Reason")
    power_source = first(network_row, "power_source", "Power Source")
    nodal = first(network_row, "nodal", "Nodal")
    vip = first(network_row, "vip", "VIP")
    five_g = first(network_row, "5g", "5G")
    site_type = first(network_row, "site_type", "Site Type")
    load_ampere = coerce_number(first(
        network_row,
        "load_ampere_from_power_sheet_or_pms",
        "Load Ampere  (From Power Sheet Or PMs)",
        "load_ampere",
    ))
    recent_network_date = first(
        network_row,
        "recent_test_date_or_reporting_date",
        "Recent Test Date Or Reporting Date",
    )

    bdt_battery_brand = first(latest_test, "battery_brand")
    bdt_discharge_minutes = coerce_number(first(latest_test, "discharge_minutes"))
    bdt_battery_ah = coerce_number(first(latest_test, "battery_ah"))
    bdt_battery_voltage = coerce_number(first(latest_test, "battery_voltage"))
    bdt_num_strings = coerce_int(first(latest_test, "num_strings"))
    bdt_num_batteries = coerce_int(first(latest_test, "num_batteries"))
    bdt_end_voltage = coerce_number(first(latest_test, "end_voltage"))
    latest_bdt_test_date = first(latest_test, "test_date") or first(latest_run, "test_date")
    overall_verdict = first(latest_run, "overall_verdict")

    critical_markers: list[str] = []
    if upper(vip) and upper(vip) != "_":
        critical_markers.append("vip")
    if upper(five_g) and upper(five_g) != "_":
        critical_markers.append("5g")
    if upper(nodal) and upper(nodal) not in {"", "_", "END POINT", "VIP (END POINT )"}:
        critical_markers.append("nodal_or_tx")

    battery_context = resolve_network_battery_context(network_rows, min_backup_minutes=0.0)
    battery_type_missing = battery_context.battery_type_missing
    declared_no_battery = (
        battery_type_missing
        or battery_context.no_usable_backup
        or (backup_minutes is not None and backup_minutes <= 0)
    )
    battery_declared = bool(network_rows) and not declared_no_battery
    has_bdt = bool(bdt_summary or bdt_tests or validation_runs)
    has_validation = bool(validation_runs)
    has_photos = section_total(bdt_payload, "photos") > 0 or bool(section_rows(bdt_payload, "photos"))

    failed_rules = [rule for rule in rule_results if upper(rule.get("verdict")) in FAILED_RULE_VERDICTS]
    network_topology = build_battery_topology(
        brand=battery_type,
        battery_ah=network_battery_ah,
        battery_voltage=network_battery_voltage,
        num_strings=no_of_strings,
        num_batteries=network_num_batteries,
    )
    bdt_topology = build_battery_topology(
        brand=bdt_battery_brand,
        battery_ah=bdt_battery_ah,
        battery_voltage=bdt_battery_voltage,
        num_strings=bdt_num_strings,
        num_batteries=bdt_num_batteries,
    )
    upgrade_detected = is_lead_acid_to_lithium_upgrade(network_topology, bdt_topology)

    differences: list[dict[str, Any]] = []
    reasons: list[str] = []
    flags: list[str] = []
    severity = "low"

    def add_flag(flag: str, reason: str, candidate_severity: str = "medium") -> None:
        nonlocal severity
        if flag not in flags:
            flags.append(flag)
        if reason not in reasons:
            reasons.append(reason)
        severity = max_severity(severity, candidate_severity)

    if not network_rows:
        add_flag("missing_network_summary", "No Network Summary metadata row was found for this site.", "high")

    if not battery_declared:
        add_flag("no_usable_battery_declared", "Network Summary does not declare a usable battery setup.", "high" if critical_markers else "medium")

    if battery_declared and not has_bdt:
        add_flag("missing_bdt", "Network Summary declares battery backup, but no BDT summary/test/validation was found.", "high" if critical_markers else "medium")

    if battery_declared and (
        "NEED PM" in upper(backup_status)
        or "NEED PM" in upper(batt_reason)
        or "UPGRADE NEEDED" in upper(backup_status)
    ):
        add_flag("network_summary_action_needed", "Network Summary marks the battery/backup state as needing PM or upgrade.", "medium")

    if has_bdt and not has_validation:
        add_flag("bdt_not_validated", "BDT data exists, but no validation run was found.", "medium")

    if has_bdt and not has_photos:
        add_flag("missing_photo_evidence", "BDT data exists, but no photo metadata was found.", "medium")

    overall_text = upper(overall_verdict)
    if overall_text in FAILED_RULE_VERDICTS:
        add_flag("bdt_failed", f"Latest BDT validation verdict is {overall_verdict}.", "high")

    if failed_rules:
        add_flag("failed_bdt_rules", f"{len(failed_rules)} BDT validation rule(s) are rejected/revise/no-data.", "high")

    if bdt_discharge_minutes is not None and bdt_discharge_minutes < min_backup_minutes:
        add_flag(
            "weak_measured_backup",
            f"Measured BDT discharge is {bdt_discharge_minutes:g} minutes, below the {min_backup_minutes:g} minute threshold.",
            "high" if critical_markers else "medium",
        )

    if battery_declared and upgrade_detected:
        differences.append({
            "field": "battery_technology_upgrade",
            "network_summary": text(battery_type),
            "bdt": text(bdt_battery_brand),
            "difference_type": "lead_acid_to_lithium_upgrade",
        })
        add_flag(
            "battery_technology_upgrade",
            "Network Summary appears to describe an older lead-acid setup while BDT shows a lithium upgrade.",
            "high" if snapshot_status_is_stale(network_rows, recent_network_date, latest_bdt_test_date) else "medium",
        )

    if (
        battery_declared
        and not upgrade_detected
        and bdt_battery_brand
        and battery_type
        and not strings_match(battery_type, bdt_battery_brand)
    ):
        differences.append({
            "field": "battery_type",
            "network_summary": text(battery_type),
            "bdt": text(bdt_battery_brand),
            "difference_type": "mismatch",
        })
        add_flag("network_bdt_mismatch", "Network Summary battery type does not match the latest BDT battery brand.", "high")

    if (
        not upgrade_detected
        and no_of_strings is not None
        and bdt_num_strings is not None
        and no_of_strings != bdt_num_strings
    ):
        differences.append({
            "field": "no_of_strings",
            "network_summary": no_of_strings,
            "bdt": bdt_num_strings,
            "difference_type": "mismatch",
        })
        add_flag("network_bdt_mismatch", "Network Summary string count does not match the latest BDT test.", "medium")

    if backup_minutes is not None and bdt_discharge_minutes is not None:
        minutes_delta = abs(float(backup_minutes) - float(bdt_discharge_minutes))
        if minutes_delta > backup_minutes_tolerance:
            differences.append({
                "field": "backup_minutes",
                "network_summary": backup_minutes,
                "bdt": bdt_discharge_minutes,
                "difference_type": "mismatch",
                "delta_minutes": round(minutes_delta, 2),
            })
            add_flag(
                "network_bdt_mismatch" if not upgrade_detected else "battery_technology_upgrade",
                "Network Summary backup minutes differ materially from measured BDT discharge.",
                "medium",
            )

    if "GOOD" in upper(backup_status) and bdt_discharge_minutes is not None and bdt_discharge_minutes < min_backup_minutes:
        differences.append({
            "field": "backup_status",
            "network_summary": text(backup_status),
            "bdt": f"{bdt_discharge_minutes:g} measured minutes",
            "difference_type": "contradiction",
        })
        add_flag("network_bdt_mismatch", "Network Summary says backup is good, but measured BDT backup is weak.", "high")

    if not flags and battery_declared and overall_text == "ACCEPTED":
        flags.append("bdt_passed")
        reasons.append("Battery exists, BDT validation is accepted, and no configured mismatch was detected.")
    elif not flags and battery_declared and has_bdt:
        flags.append("bdt_present")
        reasons.append("Battery exists and BDT data is present, but there is not enough validation evidence for a stronger verdict.")

    if "weak_measured_backup" in flags and critical_markers:
        insight_status = "Critical Site With Weak Backup"
        severity = "high"
    elif "battery_technology_upgrade" in flags:
        insight_status = "Battery Technology Upgrade Detected"
    elif "network_bdt_mismatch" in flags:
        insight_status = "Network Summary / BDT Mismatch"
    elif "bdt_failed" in flags or "failed_bdt_rules" in flags:
        insight_status = "Battery Exists - BDT Failed"
    elif "missing_bdt" in flags:
        insight_status = "Battery Exists - No BDT"
    elif "bdt_not_validated" in flags:
        insight_status = "Battery Exists - BDT Not Validated"
    elif "no_usable_battery_declared" in flags:
        insight_status = "No Battery Declared"
    elif "bdt_passed" in flags:
        insight_status = "Battery Exists - BDT Passed"
    elif "bdt_present" in flags:
        insight_status = "Battery Exists - BDT Present"
    else:
        insight_status = "Insufficient Data"

    snapshot_freshness = build_snapshot_freshness(
        has_network_rows=bool(network_rows),
        network_summary_date=recent_network_date,
        bdt_test_date=latest_bdt_test_date,
    )

    return jsonable({
        "site_id": site_id,
        "site_code": site_id,
        "site_name": first(network_row, "site_name", "Site Name") or site_row.get("site_name"),
        "area": first(network_row, "area", "area_code", "Area Code", "orange_area", "Orange Area") or site_row.get("area"),
        "subcontractor": first(network_row, "subcontractor", "Subcontractor") or site_row.get("subcontractor"),
        "office": first(network_row, "office", "Office") or site_row.get("office"),
        "insight_status": insight_status,
        "severity": severity,
        "insight_flags": flags,
        "reasons": reasons,
        "differences": differences,
        "critical_markers": critical_markers,
        "snapshot_freshness": snapshot_freshness,
        "network_summary": {
            "battery_declared": battery_declared,
            "battery_type": text(battery_type),
            "installed_battery_type": text(installed_battery_type),
            "backup_status": text(backup_status),
            "backup_minutes": backup_minutes,
            "no_of_strings": no_of_strings,
            "battery_ah": network_battery_ah,
            "battery_voltage": network_battery_voltage,
            "num_batteries": network_num_batteries,
            "batt_reason": text(batt_reason),
            "power_source": text(power_source),
            "site_type": text(site_type),
            "vip": text(vip),
            "5g": text(five_g),
            "nodal": text(nodal),
            "load_ampere": load_ampere,
            "recent_test_date_or_reporting_date": recent_network_date,
            "row_count": len(network_rows),
        },
        "bdt": {
            "has_bdt": has_bdt,
            "has_validation": has_validation,
            "has_photo_evidence": has_photos,
            "bdt_summary_count": section_total(bdt_payload, "bdt_summary"),
            "bdt_test_count": section_total(bdt_payload, "bdt_tests"),
            "validation_run_count": section_total(bdt_payload, "validation_runs"),
            "rule_result_count": section_total(bdt_payload, "rule_results"),
            "failed_rule_count": len(failed_rules),
            "photo_count": section_total(bdt_payload, "photos"),
            "latest_test_date": latest_bdt_test_date,
            "latest_validation_verdict": text(overall_verdict),
            "battery_brand": text(bdt_battery_brand),
            "battery_ah": bdt_battery_ah,
            "battery_voltage": bdt_battery_voltage,
            "num_strings": bdt_num_strings,
            "num_batteries": bdt_num_batteries,
            "measured_discharge_minutes": bdt_discharge_minutes,
            "end_voltage": bdt_end_voltage,
        },
        "battery_topology": {
            "upgrade_detected": upgrade_detected,
            "network_summary": network_topology.to_dict(),
            "bdt": bdt_topology.to_dict(),
        },
    })


def build_bdt_payload_from_validation(bdt_data: Any, validation_result: Any) -> dict[str, Any]:
    bdt_row = {
        "site_code": getattr(bdt_data, "site_code", "") or getattr(validation_result, "site_code", ""),
        "test_date": getattr(validation_result, "test_date", "") or getattr(bdt_data, "test_date", ""),
        "battery_brand": getattr(bdt_data, "battery_brand", ""),
        "battery_model": getattr(bdt_data, "battery_model", ""),
        "battery_ah": getattr(bdt_data, "battery_ah", None),
        "battery_voltage": getattr(bdt_data, "battery_voltage", None),
        "discharge_minutes": getattr(bdt_data, "discharge_minutes", None),
        "num_strings": getattr(bdt_data, "num_strings", None),
        "num_batteries": getattr(bdt_data, "num_batteries", None),
        "end_voltage": getattr(bdt_data, "end_voltage", None),
    }
    rule_rows = [
        {
            "rule_id": getattr(rule, "rule_id", ""),
            "rule_name": getattr(rule, "rule_name", ""),
            "verdict": getattr(rule, "verdict", ""),
            "detail": getattr(rule, "detail", ""),
        }
        for rule in getattr(validation_result, "rules", []) or []
    ]
    photo_count = int(getattr(bdt_data, "photo_count", 0) or 0)
    return {
        "bdt_summary": {"rows": [bdt_row], "returned": 1, "total": 1},
        "bdt_tests": {"rows": [bdt_row], "returned": 1, "total": 1},
        "validation_runs": {
            "rows": [{
                "site_code": bdt_row["site_code"],
                "test_date": bdt_row["test_date"],
                "overall_verdict": getattr(validation_result, "overall", ""),
            }],
            "returned": 1,
            "total": 1,
        },
        "rule_results": {"rows": rule_rows, "returned": len(rule_rows), "total": len(rule_rows)},
        "photos": {"rows": [], "returned": min(photo_count, 1), "total": photo_count},
    }


def build_bdt_validation_insight(
    validation_result: Any,
    bdt_data: Any | None = None,
    *,
    network_rows: list[dict[str, Any]] | None = None,
    min_backup_minutes: float = 90.0,
    backup_minutes_tolerance: float = 30.0,
) -> dict[str, Any]:
    bdt = bdt_data if bdt_data is not None else getattr(validation_result, "bdt_data", None)
    site_code = str(getattr(validation_result, "site_code", "") or getattr(bdt, "site_code", "") or "").strip()
    if network_rows is None:
        network_rows = load_network_summary_rows_for_site(site_code) if site_code else []
    site_row = dict(network_rows[0]) if network_rows else {
        "site_id": site_code,
        "site_code": site_code,
        "site_name": getattr(bdt, "site_name", ""),
    }
    return build_battery_backup_insight(
        site_row=site_row,
        network_rows=network_rows,
        bdt_payload=build_bdt_payload_from_validation(bdt, validation_result),
        min_backup_minutes=float(min_backup_minutes),
        backup_minutes_tolerance=float(backup_minutes_tolerance),
    )


def attach_battery_backup_insight(
    validation_result: Any,
    bdt_data: Any | None = None,
    *,
    network_rows: list[dict[str, Any]] | None = None,
    min_backup_minutes: float = 90.0,
    backup_minutes_tolerance: float = 30.0,
) -> dict[str, Any]:
    insight = build_bdt_validation_insight(
        validation_result,
        bdt_data,
        network_rows=network_rows,
        min_backup_minutes=min_backup_minutes,
        backup_minutes_tolerance=backup_minutes_tolerance,
    )
    validation_result.battery_backup_insight = insight
    return insight
