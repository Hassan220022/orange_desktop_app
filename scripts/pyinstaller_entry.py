"""PyInstaller entrypoint for building Alarm Viewer executables."""

try:
    from alarm_app.main import main
except ImportError:
    from main import main


if __name__ == "__main__":
    main()
