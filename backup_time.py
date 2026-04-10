"""
Backup-time computation and dialog.

Dialog and thread classes moved to ui/dialogs.py and ui/threads.py;
re-exported here for backward compatibility.
"""

from alarm_app.ui.dialogs import BackupTimeDialog  # noqa: F401
from alarm_app.ui.threads import BackupTimeThread  # noqa: F401
