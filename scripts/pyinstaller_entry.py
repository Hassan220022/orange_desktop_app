"""PyInstaller entrypoint for building Alarm Viewer executables."""

import multiprocessing

try:
    from main import main
except ImportError:
    from alarm_app.main import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
