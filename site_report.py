"""Compatibility shim — real module lives at alarm_app.data.site_report."""
import sys
import alarm_app.data.site_report as _real  # noqa: F401

sys.modules[__name__] = _real
