"""Compatibility shim — real module lives at alarm_app.ui.model."""
import sys
import alarm_app.ui.model as _real  # noqa: F401

sys.modules[__name__] = _real
