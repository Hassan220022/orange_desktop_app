.PHONY: run dev live server build-windows build-macos build-windows-installer build-macos-installer lint typecheck test

# Start the app (backend starts automatically as a child process).
run:
	cd .. && alarm_app/.venv/bin/python -m alarm_app.main

# Run the backend server standalone (for development/debugging).
server:
	cd .. && alarm_app/.venv/bin/python -m uvicorn alarm_app.web.app:app --host 127.0.0.1 --port 8787 --reload

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

lint:
	ruff check .

typecheck:
	mypy --ignore-missing-imports --no-strict-optional core/ data/ db/ web/ llm_tools/

test:
	pytest tests/ -x
