"""PyInstaller entrypoint for building Alarm Viewer executables."""

# Prefer flat-module imports so packaged builds do not depend on the checkout
# directory being named "alarm_app".
from main import main


if __name__ == "__main__":
    main()
