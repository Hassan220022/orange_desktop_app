import sys as _sys
from alarm_app.ui import viewer as _real
_sys.modules[__name__] = _real
