#!/usr/bin/env python3
"""
Generate golden fixtures from a real BDT test folder.

Usage:
    python tests/generate_golden.py /path/to/alarm/folder

Outputs JSON fixtures to tests/fixtures/golden/.
Run this ONCE before any storage migration to lock current behavior.
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from alarm_app.bdt.parser import parse_bdt_file
from alarm_app.bdt.validator import RuleResult, ValidationResult, validate_bdt
from alarm_app.core.backup_time import compute_backup_times
from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
from alarm_app.data.loaders import deduplicate_alarm_rows, discover_alarm_files, parse_alarm_file

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"


def _json_safe(obj):
    """Convert non-serializable types for JSON output."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, float) and pd.isna(obj):
        return None
    if isinstance(obj, bytes):
        return f"<bytes:{len(obj)}>"
    if hasattr(obj, "__dict__"):
        return {k: _json_safe(v) for k, v in obj.__dict__.items()
                if not k.startswith("_")}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, tuple):
        return [_json_safe(v) for v in obj]
    return obj


def _df_summary(df: pd.DataFrame) -> dict:
    """Summarize a DataFrame for golden comparison."""
    return {
        "columns": list(df.columns),
        "row_count": len(df),
        "dtypes": {c: str(df[c].dtype) for c in df.columns},
        "category_counts": (
            df["_category"].value_counts().to_dict()
            if "_category" in df.columns else {}
        ),
        "vendor_counts": (
            df["vendor"].value_counts().to_dict()
            if "vendor" in df.columns else {}
        ),
    }


def _rule_result_to_dict(r: RuleResult) -> dict:
    return {
        "rule_id": r.rule_id,
        "rule_name": r.rule_name,
        "passed": r.passed,
        "verdict": r.verdict,
        "detail": r.detail,
    }


def _validation_result_to_dict(vr: ValidationResult) -> dict:
    return {
        "filename": vr.filename,
        "site_code": vr.site_code,
        "test_date": vr.test_date,
        "overall": vr.overall,
        "rules": [_rule_result_to_dict(r) for r in vr.rules],
        "parse_errors": vr.parse_errors,
    }


def generate(directory: str):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    directory = str(directory)

    # 1. Discover files
    print(f"Discovering alarm files in {directory}...")
    file_infos = discover_alarm_files(directory)
    with open(GOLDEN_DIR / "discover_files.json", "w") as f:
        json.dump(_json_safe(file_infos), f, indent=2)
    print(f"  Found {len(file_infos)} files")

    # 2. Parse alarm files
    print("Parsing alarm files...")
    frames = []
    for info in file_infos:
        df = parse_alarm_file(info)
        if df is not None and not df.empty:
            frames.append(df)
    if not frames:
        print("  No alarm data parsed. Exiting.")
        return

    full_df = pd.concat(frames, ignore_index=True)
    full_df, n_dupes = deduplicate_alarm_rows(full_df)
    print(f"  Parsed {len(full_df)} rows ({n_dupes} duplicates removed)")

    with open(GOLDEN_DIR / "parse_summary.json", "w") as f:
        json.dump(_df_summary(full_df), f, indent=2)

    # 3. Classify
    print("Classifying alarms...")
    from alarm_app.data.state import load_alarm_ids
    alarm_ids = load_alarm_ids()
    classified = classify_by_alarm_id(full_df.copy(), alarm_ids)
    with open(GOLDEN_DIR / "classify_summary.json", "w") as f:
        json.dump({
            "category_counts": classified["_category"].value_counts().to_dict(),
        }, f, indent=2)

    # 4. Site down flag
    print("Computing site down flags...")
    flagged = compute_site_down_flag(classified.copy())
    site_down_count = int(flagged["site_down"].sum()) if "site_down" in flagged.columns else 0
    with open(GOLDEN_DIR / "site_down_summary.json", "w") as f:
        json.dump({"site_down_count": site_down_count}, f, indent=2)

    # 5. Backup times
    print("Computing backup times...")
    bt_result = compute_backup_times(flagged)
    if isinstance(bt_result, tuple):
        bt_df, bt_err = bt_result
    else:
        bt_df, _bt_err = bt_result, None
    bt_summary = _df_summary(bt_df) if bt_df is not None and not bt_df.empty else {"row_count": 0}
    with open(GOLDEN_DIR / "backup_times_summary.json", "w") as f:
        json.dump(bt_summary, f, indent=2)

    # 6. BDT validation
    print("Finding and validating BDT files...")
    bdt_results = []
    import os
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            if fname.lower().endswith((".xlsx", ".xls")) and "bdt" in fname.lower():
                fpath = os.path.join(root, fname)
                try:
                    bdt = parse_bdt_file(fpath)
                    if bdt and bdt.site_code:
                        vr = validate_bdt(bdt, flagged)
                        bdt_results.append(_validation_result_to_dict(vr))
                except Exception as e:
                    print(f"  WARN: {fname}: {e}")

    with open(GOLDEN_DIR / "bdt_validation_results.json", "w") as f:
        json.dump(bdt_results, f, indent=2)
    print(f"  Validated {len(bdt_results)} BDT files")

    print(f"\nGolden fixtures saved to {GOLDEN_DIR}/")
    print("Files generated:")
    for p in sorted(GOLDEN_DIR.glob("*.json")):
        print(f"  {p.name}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/generate_golden.py /path/to/alarm/folder")
        sys.exit(1)
    generate(sys.argv[1])
