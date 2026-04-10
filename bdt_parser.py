"""Compatibility shim — real module lives at alarm_app.bdt.parser."""
import sys
import alarm_app.bdt.parser as _real  # noqa: F401

# Replace this shim in sys.modules so that monkeypatch / mock.patch
# targeting 'alarm_app.bdt_parser.<attr>' hits the real module.
sys.modules[__name__] = _real
