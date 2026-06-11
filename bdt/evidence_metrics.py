"""
Pure BDT evidence metrics shared by the validator and human calibration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from alarm_app.bdt.parser import BDTData
except ImportError:
    from bdt.parser import BDTData


@dataclass(frozen=True)
class R3Evidence:
    max_pos_delta: float
    max_neg_delta: float
    worst_imbalance_ratio: float
    worst_imbalance_label: str
    checked_points: int


@dataclass(frozen=True)
class DischargeTrendMetrics:
    max_delta: float
    late_delta: float
    bus_amp_slope: float
    baseline_amp: float
    last_amp: float
    discharge_minutes_reached: float


def parse_discharge_minute_label(label) -> float | None:
    if label is None:
        return None
    text = str(label).strip()
    if not text:
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def has_discharge_evidence(bdt: BDTData) -> bool:
    """True when the discharge table has at least one voltage or ampere reading."""
    if not bdt.discharge_readings:
        return False
    return any(
        voltage is not None or ampere is not None
        for _, voltage, ampere in bdt.discharge_readings
    )


def max_reached_discharge_minutes(bdt: BDTData) -> float | None:
    max_mins = 0.0
    for label, voltage, ampere in bdt.discharge_readings:
        if voltage is None and ampere is None:
            continue
        mins = parse_discharge_minute_label(label)
        if mins is None:
            continue
        if mins > max_mins:
            max_mins = mins
    return max_mins if max_mins > 0 else None


def _string_imbalance_ratio(string_amps: list[float]) -> float | None:
    active = [abs(a) for a in string_amps if a is not None and abs(a) > 0.01]
    if len(active) < 2:
        return None
    total = sum(active)
    if total <= 0:
        return None
    return max(active) / total


def worst_r3_evidence(bdt: BDTData) -> R3Evidence | None:
    """Worst E−Σ deltas and string imbalance across paired discharge rows."""
    if not bdt.string_discharge_readings or not bdt.discharge_readings:
        return None

    string_readings = bdt.string_discharge_readings[1:]
    max_pos = 0.0
    max_neg = 0.0
    worst_imb = 0.0
    worst_label = ""
    checked = 0

    for dr, sr in zip(bdt.discharge_readings, string_readings):
        bus_a = dr[2]
        string_amps = [a for _, a in sr if a is not None]
        if bus_a is None or not string_amps:
            continue

        string_sum = sum(string_amps)
        diff = float(bus_a) - float(string_sum)
        checked += 1
        if diff > max_pos:
            max_pos = diff
        if diff < 0 and abs(diff) > max_neg:
            max_neg = abs(diff)

        imb = _string_imbalance_ratio(string_amps)
        if imb is not None and imb > worst_imb:
            worst_imb = imb
            worst_label = str(dr[0])

    if checked == 0:
        return None

    return R3Evidence(
        max_pos_delta=max_pos,
        max_neg_delta=max_neg,
        worst_imbalance_ratio=worst_imb,
        worst_imbalance_label=worst_label,
        checked_points=checked,
    )


def discharge_trend_metrics(bdt: BDTData) -> DischargeTrendMetrics | None:
    """Bus-ampere trend and max deviation from the first timed reading."""
    readings: list[tuple[str, float, float]] = []
    for label, _, ampere in bdt.discharge_readings:
        if ampere is None:
            continue
        minute = parse_discharge_minute_label(label)
        if minute is None:
            continue
        readings.append((label, minute, float(ampere)))

    if len(readings) < 2:
        return None

    baseline_label, baseline_min, baseline = readings[0]
    last_label, last_min, last_amp = readings[-1]
    span = max(1.0, last_min - baseline_min)
    slope = (last_amp - baseline) / span

    max_delta = 0.0
    late_delta = 0.0
    ten_min_amp: float | None = None
    for label, minute, ampere in readings:
        delta = abs(ampere - baseline)
        if delta > max_delta:
            max_delta = delta
        if minute >= 10.0:
            if ten_min_amp is None:
                ten_min_amp = ampere
            late_delta = max(late_delta, abs(ampere - ten_min_amp))

    reached = max_reached_discharge_minutes(bdt) or last_min
    return DischargeTrendMetrics(
        max_delta=max_delta,
        late_delta=late_delta,
        bus_amp_slope=slope,
        baseline_amp=baseline,
        last_amp=last_amp,
        discharge_minutes_reached=reached,
    )
