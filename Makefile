# Alarm Viewer — run from repo root (directory containing this Makefile).
# Desktop entry uses parent-dir layout: `cd $(PARENT) && python -m alarm_app.main`

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PARENT := $(abspath $(ROOT)/..)

ifeq ($(OS),Windows_NT)
	VENV_PY := $(ROOT)/.venv/Scripts/python.exe
	PIP := $(ROOT)/.venv/Scripts/pip.exe
else
	VENV_PY := $(ROOT)/.venv/bin/python
	PIP := $(ROOT)/.venv/bin/pip
endif

PY := $(if $(wildcard $(VENV_PY)),$(VENV_PY),python3)
ifeq ($(OS),Windows_NT)
	PY := $(if $(wildcard $(VENV_PY)),$(VENV_PY),python)
endif

# CI skips slow GUI e2e suites (same as .github/workflows).
PYTEST_CI_IGNORE := --ignore=tests/test_e2e_gui_viewer.py --ignore=tests/test_e2e_gui_bdt.py
MYPY_ARGS := --ignore-missing-imports --explicit-package-bases --follow-imports=silent
# Match .github/workflows/quality.yml (llm_tools checked separately via `make typecheck`).
MYPY_CI_PATHS := $(ROOT)/core/ $(ROOT)/data/ $(ROOT)/db/ $(ROOT)/web/ $(ROOT)/bdt/

.PHONY: help venv install ci-install run dev live server \
	build-windows build-macos build-windows-installer build-macos-installer \
	lint typecheck ci-lint ci-typecheck test ci-test test-ui test-workspace ci-quality

help:
	@echo "Alarm Viewer Makefile (run from $(ROOT))"
	@echo ""
	@echo "  make install          Local venv + requirements + pytest/ruff/mypy"
	@echo "  make ci-install       CI venv (uv when available, else pip)"
	@echo "  make run              Start desktop app"
	@echo "  make dev / live       Dev reload helpers"
	@echo "  make server           FastAPI backend only"
	@echo "  make test             Full pytest (local)"
	@echo "  make ci-test          Pytest for GitHub Actions (skips GUI e2e)"
	@echo "  make test-ui          Workspace switch regression tests"
	@echo "  make lint / ci-lint   ruff check"
	@echo "  make typecheck        mypy (local paths)"
	@echo "  make ci-typecheck     mypy (CI flags + paths)"
	@echo "  make ci-quality       lint + typecheck + ci-test (full quality gate)"
	@echo "  make build-macos / build-windows  Packaging"

venv:
	python3 -m venv $(ROOT)/.venv
	$(PIP) install -r $(ROOT)/requirements.txt
	$(PIP) install pytest ruff mypy

install: venv

# GitHub Actions + local parity: uv on CI runners, pip fallback elsewhere.
ci-install:
ifeq ($(OS),Windows_NT)
	uv venv $(ROOT)/.venv --python python
	uv pip install --python $(VENV_PY) -r $(ROOT)/requirements.txt pytest ruff mypy
else
	if command -v uv >/dev/null 2>&1; then \
		uv venv $(ROOT)/.venv --python python3; \
		uv pip install --python $(VENV_PY) -r $(ROOT)/requirements.txt pytest ruff mypy; \
	else \
		$(MAKE) install; \
	fi
endif

run:
	cd $(PARENT) && $(PY) -m alarm_app.main

server:
	cd $(PARENT) && $(PY) -m uvicorn alarm_app.web.app:app --host 127.0.0.1 --port 8787 --reload

live:
	cd $(PARENT) && $(PY) -m jurigged -m alarm_app.main

dev:
	cd $(PARENT) && find $(ROOT) -name '*.py' -not -path '*__pycache__*' | entr -r $(PY) -m alarm_app.main

build-windows:
	cd $(ROOT)/scripts && build_windows.bat

build-macos:
	cd $(ROOT)/scripts && ./build_macos.sh

build-windows-installer:
	cd $(ROOT)/scripts && build_windows_installer.bat

build-macos-installer:
	cd $(ROOT)/scripts && ./build_macos_installer.sh

lint ci-lint:
	$(PY) -m ruff check $(ROOT)

typecheck:
	$(PY) -m mypy --ignore-missing-imports \
		$(ROOT)/core/ $(ROOT)/data/ $(ROOT)/db/ $(ROOT)/web/ $(ROOT)/llm_tools/

ci-typecheck:
	$(PY) -m mypy $(MYPY_ARGS) $(MYPY_CI_PATHS)

test:
	$(PY) -m pytest $(ROOT)/tests/ -x

ci-test:
	$(PY) -m pytest $(ROOT)/tests/ -q $(PYTEST_CI_IGNORE) -x

test-ui test-workspace:
	$(PY) -m pytest $(ROOT)/tests/test_state_manager.py $(ROOT)/tests/test_workspace_switch.py -q

ci-quality: ci-lint ci-typecheck ci-test
