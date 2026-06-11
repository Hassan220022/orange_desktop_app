#!/usr/bin/env python3
"""Calibrate BDT validation thresholds from human review data.

Run:
    python scripts/calibrate_bdt_human_criteria.py

Optional overrides:
    --book1 PATH
    --auto-export PATH
    --bdt-folder PATH
    --out-dir PATH   (default: .scratch)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bdt.human_calibration import (  # noqa: E402
    build_calibration_rows,
    build_human_aligned_profile,
    parse_book1,
    render_report_markdown,
    run_calibration,
    load_auto_export_index,
)


DEFAULT_BOOK1 = Path("/Users/mikawi/Desktop/Book1.xlsx")
DEFAULT_AUTO = Path(
    "/Users/mikawi/Desktop/bdt_validation_20260611_132237.xlsx"
)
DEFAULT_BDT = Path("/Volumes/nvme 500/Alarms/BDT_May2026")
DEFAULT_OUT = _ROOT / ".scratch"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book1", type=Path, default=DEFAULT_BOOK1)
    parser.add_argument("--auto-export", type=Path, default=DEFAULT_AUTO)
    parser.add_argument("--bdt-folder", type=Path, default=DEFAULT_BDT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.book1.exists():
        print(f"Book1 not found: {args.book1}", file=sys.stderr)
        return 1
    if not args.bdt_folder.exists():
        print(f"BDT folder not found: {args.bdt_folder}", file=sys.stderr)
        return 1

    auto_path = args.auto_export if args.auto_export.exists() else None
    rows, profile = run_calibration(args.book1, args.bdt_folder, auto_path)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.out_dir / "human_calibration_report.md"
    profile_path = args.out_dir / "human_aligned_profile.json"

    report_path.write_text(render_report_markdown(rows, profile), encoding="utf-8")
    profile_path.write_text(
        json.dumps(profile, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    missing = sum(1 for r in rows if not r.bdt_path)
    parsed = sum(1 for r in rows if r.bdt_path and not r.parse_error)
    print(f"Rows: {len(rows)} | parsed: {parsed} | missing BDT: {missing}")
    print(f"Report: {report_path}")
    print(f"Profile: {profile_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
