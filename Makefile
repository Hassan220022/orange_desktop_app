.PHONY: run build-windows build-macos build-windows-installer build-macos-installer

run:
	cd .. && alarm_app/.venv/bin/python -m alarm_app.main

build-windows:
	cd scripts && build_windows.bat

build-macos:
	cd scripts && ./build_macos.sh

build-windows-installer:
	cd scripts && build_windows_installer.bat

build-macos-installer:
	cd scripts && ./build_macos_installer.sh
