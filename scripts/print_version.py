#!/usr/bin/env python3
"""Print the resolved Alarm Viewer version."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from alarm_app.versioning import get_app_version
except ImportError:
    from versioning import get_app_version  # type: ignore[no-redef]


if __name__ == "__main__":
    print(get_app_version())
