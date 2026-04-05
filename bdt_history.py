"""
BDT History -- store and compare battery discharge test records across time.

Persists BDT validation results per site to detect equipment changes
between consecutive PM visits (battery type, count, rectifier, modules).
"""

import json
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path


HISTORY_DIR = Path.home() / ".alarm_viewer" / "bdt_history"


@dataclass
class BDTTestRecord:
    """Stored snapshot of a BDT test for future comparison."""
    site_code: str
    test_date: str            # ISO format YYYY-MM-DD
    file_path: str
    battery_brand: str
    battery_ah: float | None
    battery_voltage: float | None
    num_strings: int | None
    num_batteries: int | None
    num_modules: int | None
    rectifier_brand: str
    overall_verdict: str
    saved_at: str             # ISO datetime when saved


@dataclass
class BDTComparison:
    """Result of comparing current vs previous BDT test."""
    previous: BDTTestRecord
    current_date: str
    differences: list[str]      # Human-readable change descriptions
    has_critical_change: bool   # True if battery type/count/rectifier changed


def save_test_record(bdt, verdict: str) -> None:
    """Persist a BDT test result for future comparison.

    Args:
        bdt: BDTData instance (from bdt_parser)
        verdict: Overall validation verdict string
    """
    if not bdt.site_code or not bdt.test_date:
        return

    site_dir = HISTORY_DIR / bdt.site_code.strip().upper()
    site_dir.mkdir(parents=True, exist_ok=True)

    test_date_str = (bdt.test_date.strftime("%Y-%m-%d")
                     if isinstance(bdt.test_date, (date, datetime))
                     else str(bdt.test_date))

    record = BDTTestRecord(
        site_code=bdt.site_code,
        test_date=test_date_str,
        file_path=str(bdt.file_path or ""),
        battery_brand=str(bdt.battery_brand or ""),
        battery_ah=bdt.battery_ah,
        battery_voltage=bdt.battery_voltage,
        num_strings=bdt.num_strings,
        num_batteries=getattr(bdt, "num_batteries", None),
        num_modules=getattr(bdt, "num_modules", None),
        rectifier_brand=str(getattr(bdt, "rectifier_brand", "") or ""),
        overall_verdict=verdict,
        saved_at=datetime.now().isoformat(),
    )

    filename = f"{test_date_str}.json"
    path = site_dir / filename
    path.write_text(json.dumps(asdict(record), indent=2, default=str))


def load_previous_test(site_code: str, before_date: date) -> BDTTestRecord | None:
    """Find the most recent test record for a site before the given date.

    Args:
        site_code: Site identifier (e.g., "0167DE")
        before_date: Find tests BEFORE this date

    Returns:
        BDTTestRecord or None if no history found
    """
    site_dir = HISTORY_DIR / site_code.strip().upper()
    if not site_dir.exists():
        return None

    best_record = None
    best_date = None

    for json_file in site_dir.glob("*.json"):
        try:
            data = json.loads(json_file.read_text())
            record_date = date.fromisoformat(data["test_date"])
            if record_date < before_date:
                if best_date is None or record_date > best_date:
                    best_date = record_date
                    best_record = BDTTestRecord(**{
                        k: data.get(k) for k in BDTTestRecord.__dataclass_fields__
                    })
        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    return best_record


def compare_tests(current_bdt, previous: BDTTestRecord) -> BDTComparison:
    """Compare current BDT data against a previous test record.

    Args:
        current_bdt: BDTData instance (current test)
        previous: BDTTestRecord (historical test)

    Returns:
        BDTComparison with list of differences and critical change flag
    """
    differences = []
    critical = False

    current_date = (current_bdt.test_date.strftime("%Y-%m-%d")
                    if isinstance(current_bdt.test_date, (date, datetime))
                    else str(current_bdt.test_date or ""))

    # Critical fields: changes here indicate equipment swap
    _crit = [
        ("Battery Brand",
         str(current_bdt.battery_brand or "").strip().lower(),
         str(previous.battery_brand or "").strip().lower()),
        ("Number of Batteries",
         str(getattr(current_bdt, "num_batteries", None) or ""),
         str(previous.num_batteries or "")),
        ("Number of Modules",
         str(getattr(current_bdt, "num_modules", None) or ""),
         str(previous.num_modules or "")),
        ("Rectifier Brand",
         str(getattr(current_bdt, "rectifier_brand", "") or "").strip().lower(),
         str(previous.rectifier_brand or "").strip().lower()),
    ]

    for label, curr, prev in _crit:
        if curr and prev and curr != prev:
            differences.append(f"{label}: '{prev}' -> '{curr}'")
            critical = True

    # Non-critical fields: spec changes
    _spec = [
        ("Battery AH", current_bdt.battery_ah, previous.battery_ah),
        ("Battery Voltage", current_bdt.battery_voltage, previous.battery_voltage),
        ("Number of Strings", current_bdt.num_strings, previous.num_strings),
    ]

    for label, curr, prev in _spec:
        if curr is not None and prev is not None and curr != prev:
            differences.append(f"{label}: {prev} -> {curr}")

    return BDTComparison(
        previous=previous,
        current_date=current_date,
        differences=differences,
        has_critical_change=critical,
    )
