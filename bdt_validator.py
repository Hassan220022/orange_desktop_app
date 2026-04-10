"""Compatibility shim — real module lives at alarm_app.bdt.validator."""
import sys
import alarm_app.bdt.validator as _real  # noqa: F401

sys.modules[__name__] = _real
