"""PyInstaller entrypoint for building Alarm Viewer executables."""

import sys
from pathlib import Path

# Ensure the parent folder (which contains the alarm_app package dir)
# is importable regardless of the current working directory.
PROJECT_DIR = Path(__file__).resolve().parents[1]
PARENT_DIR = PROJECT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from alarm_app.main import main


if __name__ == "__main__":
    main()
