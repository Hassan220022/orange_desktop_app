"""Compatibility shim — real module lives at alarm_app.data.sync."""
import sys
import alarm_app.data.sync as _real  # noqa: F401

sys.modules[__name__] = _real
