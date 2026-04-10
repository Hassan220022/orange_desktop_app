.PHONY: run dev live build-windows build-macos build-windows-installer build-macos-installer

run:
	cd .. && alarm_app/.venv/bin/python -m alarm_app.main

# Live code patching — edits to functions/methods apply instantly without restart.
# Layout/widget changes still need a restart (use `make dev` for those).
live:
	cd .. && alarm_app/.venv/bin/python -m jurigged -m alarm_app.main

# Auto-restart on file change — full restart, loses window state, catches everything.
dev:
	cd .. && find alarm_app -name '*.py' -not -path '*__pycache__*' | entr -r alarm_app/.venv/bin/python -m alarm_app.main

build-windows:
	cd scripts && build_windows.bat

build-macos:
	cd scripts && ./build_macos.sh

build-windows-installer:
	cd scripts && build_windows_installer.bat

build-macos-installer:
	cd scripts && ./build_macos_installer.sh
