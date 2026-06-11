"""Battery chemistry/topology helpers shared by BDT validation and insights."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

LEAD_ACID_MARKERS = (
    "agm",
    "enersys",
    "gel",
    "lead",
    "power safe",
    "powersafe",
    "sbs",
    "vrla",
)


@dataclass(frozen=True)
class BatteryTopology:
    brand: str
    chemistry: str
    battery_ah: float | None = None
    battery_voltage: float | None = None
    num_strings: int | None = None
    num_batteries: int | None = None
    blocks_per_string: float | None = None
    string_voltage: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).replace("\xa0", " ").strip()


def _number(value: Any) -> float | None:
    raw = _text(value)
    if not raw:
        return None
    try:
        parsed = float(raw.replace(",", ""))
    except ValueError:
        return None
    if math.isnan(parsed):
        return None
    return parsed


def _integer(value: Any) -> int | None:
    parsed = _number(value)
    if parsed is None:
        return None
    return int(parsed)


def detect_battery_chemistry(brand: Any, *, battery_voltage: Any = None,
                             num_strings: Any = None,
                             num_batteries: Any = None) -> str:
    raw = _text(brand).lower()
    if "lith" in raw:
        return "lithium"
    if any(marker in raw for marker in LEAD_ACID_MARKERS):
        return "lead_acid"

    voltage = _number(battery_voltage)
    strings = _integer(num_strings)
    batteries = _integer(num_batteries)
    if (
        voltage is not None
        and voltage <= 24
        and strings is not None
        and strings > 0
        and batteries is not None
        and batteries > strings
    ):
        return "lead_acid"
    return "unknown"


def build_battery_topology(*, brand: Any = "", battery_ah: Any = None,
                           battery_voltage: Any = None, num_strings: Any = None,
                           num_batteries: Any = None) -> BatteryTopology:
    voltage = _number(battery_voltage)
    strings = _integer(num_strings)
    batteries = _integer(num_batteries)
    chemistry = detect_battery_chemistry(
        brand,
        battery_voltage=voltage,
        num_strings=strings,
        num_batteries=batteries,
    )

    blocks_per_string: float | None = None
    string_voltage = voltage
    if (
        chemistry == "lead_acid"
        and voltage is not None
        and strings is not None
        and strings > 0
        and batteries is not None
        and batteries > strings
    ):
        blocks_per_string = batteries / strings
        string_voltage = voltage * blocks_per_string

    return BatteryTopology(
        brand=_text(brand),
        chemistry=chemistry,
        battery_ah=_number(battery_ah),
        battery_voltage=voltage,
        num_strings=strings,
        num_batteries=batteries,
        blocks_per_string=blocks_per_string,
        string_voltage=string_voltage,
    )


def battery_topology_from_bdt(bdt: Any) -> BatteryTopology:
    return build_battery_topology(
        brand=getattr(bdt, "battery_brand", ""),
        battery_ah=getattr(bdt, "battery_ah", None),
        battery_voltage=getattr(bdt, "battery_voltage", None),
        num_strings=getattr(bdt, "num_strings", None),
        num_batteries=getattr(bdt, "num_batteries", None),
    )


def is_lead_acid_to_lithium_upgrade(previous: BatteryTopology,
                                    current: BatteryTopology) -> bool:
    return previous.chemistry == "lead_acid" and current.chemistry == "lithium"


def format_voltage(value: float | None) -> str:
    if value is None:
        return "unknown"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")
