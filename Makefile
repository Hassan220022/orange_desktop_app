.PHONY: run build-windows build-macos

run:
	cd .. && alarm_app/.venv/bin/python -m alarm_app.main

build-windows:
	cd scripts && build_windows.bat

build-macos:
	cd scripts && ./build_macos.sh
