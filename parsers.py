"""Compatibility shim -- real code lives in data.loaders and ui.threads."""
import sys as _sys

import alarm_app.data.loaders as _loaders  # noqa: F401

# Make alarm_app.parsers and alarm_app.data.loaders the same module object
# so that unittest.mock.patch("alarm_app.parsers.X") affects code that
# accesses the attribute through alarm_app.data.loaders.
_sys.modules[__name__] = _loaders

# Inject thread classes into the module so existing imports like
# ``from alarm_app.parsers import LoaderThread`` keep working.
from alarm_app.ui.threads import (  # noqa: E402,F401
    LoaderThread as LoaderThread,
    ExportThread as ExportThread,
    BDTValidationThread as BDTValidationThread,
)
_loaders.LoaderThread = LoaderThread
_loaders.ExportThread = ExportThread
_loaders.BDTValidationThread = BDTValidationThread
