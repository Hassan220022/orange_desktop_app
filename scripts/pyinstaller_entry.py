"""PyInstaller entrypoint for building Alarm Viewer executables."""

import multiprocessing

try:
    from alarm_app.main import main
except ImportError:
    from main import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
