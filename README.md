# Alarm Viewer

A desktop application for exploring, filtering, and analyzing telecom alarm data from **Huawei** and **Nokia** network management systems. Built with Python, PyQt5, and pandas.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15+-41CD52?logo=qt&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-2.0+-150458?logo=pandas&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Overview

Alarm Viewer lets telecom engineers load CSV/XLSX alarm exports, filter them by site, date range, category, vendor, network type, and duration, compute **backup-time analytics** (how long battery held between Power and Down alarms), validate **Battery Discharge Test (BDT)** reports against real alarm data, and export results to Excel.

### Key Features

- **Multi-vendor support** -- auto-detects Huawei and Nokia schemas from column headers
- **Bulk file loading** -- recursive directory scan with parallel parsing via `ThreadPoolExecutor`
- **Advanced filtering** -- text search, date range, vendor/network/category dropdowns, duration range, and Google Sheets-style per-column filter popups
- **Backup-time analysis** -- matches Power and Down alarms per site to compute battery hold time, with summary statistics (avg, min, max) and CSV/Excel export
- **BDT validation** -- parses Battery Discharge Test Excel files and cross-references against alarm data using 11 automated rules across alarm, discharge, and summary validations
- **Daily review report** -- counts reviewed BDT files by day from the local review ledger
- **Session persistence** -- saves UI state (filters, window geometry) and DataFrame cache to `~/.alarm_viewer/` for instant restore on next launch
- **Site Down detection** -- flags Power alarms where a Down alarm occurred within the same outage window
- **Alarm ID configuration** -- custom alarm ID lists for Power/Down/Door classification beyond filename-based detection
- **Dark theme** -- Catppuccin Mocha-inspired professional dark UI
- **Windows standalone** -- builds to a single `.exe` via PyInstaller (no Python needed on target machine)

## Screenshots

_The application features a dark-themed interface with a left sidebar for file browsing and loading, and a main panel with filterable alarm table, statistics strip, and tabbed views for alarm data and BDT validation._

## Installation

### Prerequisites

- Python 3.9 or higher
- pip

### Setup

```bash
# Clone the repository
git clone git@github.com:Hassan220022/orange_desktop_app.git
cd orange_desktop_app

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate.bat     # Windows

# Install dependencies
pip install -r requirements.txt
```

### Dependencies

| Package     | Purpose                             |
| ----------- | ----------------------------------- |
| PyQt5       | GUI framework                       |
| pandas      | Data manipulation and filtering     |
| numpy       | Numerical operations                |
| openpyxl    | Read/write `.xlsx` files            |
| xlrd        | Read legacy `.xls` files            |
| pyarrow     | Parquet serialization (state cache) |
| pyinstaller | Build standalone Windows executable |

## Web Stack (Migration Target)

The desktop app remains fully supported. For the new web runtime/deployment artifacts, use:

- `web/docker-compose.yml`
- `web/deploy/env/backend.env.example`
- `web/deploy/env/frontend.env.example`
- `web/deploy/nginx/alarm-web.conf`
- `web/deploy/systemd/*.service`

### Quick Setup (Web)

```bash
# from alarm_app/
cp web/deploy/env/backend.env.example web/deploy/env/backend.env
# fill web/deploy/env/backend.env with real values (do not commit)
# required: ALARM_WEB_SECRET_KEY, ALARM_WEB_DATABASE_URL, ALARM_WEB_CORS_ALLOWED_ORIGINS
# strongly recommended: set ALARM_WEB_SEED_ADMIN_PASSWORD to a strong unique password
# optional hardening: configure ALARM_WEB_AUTH_RATE_LIMIT_MAX_ATTEMPTS /
# ALARM_WEB_AUTH_RATE_LIMIT_WINDOW_SECONDS and ALARM_WEB_SOURCE_CONFIG_ENCRYPTION_KEY

# frontend env template:
# copy web/deploy/env/frontend.env.example -> web/frontend/.env.production
```

### Run with Compose

```bash
# expects frontend static build at web/frontend/dist
docker compose -f web/docker-compose.yml up -d
```

For local frontend dev only:

```bash
cd web
cp .env.example .env
cd frontend && npm install && npm run dev
```

### One-command local test run

```bash
make web-up
```

This command builds the frontend, ensures `web/deploy/env/backend.env` exists (copied from example if missing), and then:

- uses Docker Compose when Docker is available
- automatically falls back to local mode when Docker daemon is unavailable

After startup it prints ready-to-test links:

- Frontend: `http://127.0.0.1:4173` (local fallback) or `http://127.0.0.1` (compose/nginx on 80)
- Backend health: `http://127.0.0.1:8000/health`

Services: `postgres`, `redis`, `api` (FastAPI/Uvicorn), `worker` (Celery), `beat` (Celery Beat), and `nginx`.

Compose command is executed from `web/`, so all paths resolve relative to that folder.

### Stop / Restart / Logs

```bash
make web-down
make web-up
```

- Local fallback logs: `/tmp/alarm_frontend.log`, `/tmp/alarm_backend.log`
- Compose logs: `cd web && docker compose -f docker-compose.yml logs -f api worker beat nginx`

### Health checks

```bash
curl -sS http://127.0.0.1:8000/health
curl -i http://127.0.0.1/api/auth/me
```

- `postgres` and `redis` include compose healthchecks.
- `api/worker/beat/nginx` should be verified via logs and endpoint checks above.

### Web Security + Integration Behavior

- Auth endpoints `/api/auth/login` and `/api/auth/refresh` are rate limited by
  `ALARM_WEB_AUTH_RATE_LIMIT_MAX_ATTEMPTS` in
  `ALARM_WEB_AUTH_RATE_LIMIT_WINDOW_SECONDS` per user/token + client IP.
- Source `connection_config` sensitive keys are encrypted at rest
  (`ALARM_WEB_SOURCE_CONFIG_SENSITIVE_KEYS`) using
  `ALARM_WEB_SOURCE_CONFIG_ENCRYPTION_KEY` (or fallback `ALARM_WEB_SECRET_KEY`).
- Source APIs mask sensitive values (`********`) in responses.
- Manual source sync queues `sync_alarms_from_nce` for `nce_rest` sources and
  `sync_alarms_from_files` for file-based sources.
- Worker sync behavior:
  - `nce_rest`: calls configured HTTP endpoint (`endpoint` + optional `path`) and persists returned alarm records. Missing endpoint fails the task explicitly.
  - `file_local`: scans configured local path for `csv/xlsx/xls`, parses alarms, persists to DB, and reclassifies team alarms.
  - `file_ftp`/`file_sftp`: currently fail explicitly as not yet implemented in worker.
  - `scan_bdt_files`: scans configured team paths, ingests new BDT files, then runs validation/relink pass.
  - `create_alarm_partitions`: creates next-month PostgreSQL partition when applicable; SQLite/dev returns a clear skip status.

### Alembic Migrations

From `alarm_app/web/backend`:

```bash
PYTHONPATH=. ../../.venv/bin/alembic -c alembic.ini upgrade head
PYTHONPATH=. ../../.venv/bin/alembic -c alembic.ini current
```

Migration files live under `web/backend/alembic/versions/`.

### Nginx Routing Assumptions

- `/` serves frontend static files from `/var/www/alarm-web/dist/`
- `/api/` proxies to FastAPI API routes (`/api/*`) on port `8000`
- `/photos/` follows an auth-checked flow (`X-Accel-Redirect`) and serves protected files from `/data/bdt_photos/` via `/_protected_photos/`
- Keep `/api/` and frontend `VITE_API_BASE_URL=/api` aligned.

### systemd Examples

Sample units are provided for VM/VPS deployments:

- `web/deploy/systemd/alarm-web-api.service`
- `web/deploy/systemd/alarm-celery-worker.service`
- `web/deploy/systemd/alarm-celery-beat.service`

When using systemd deployment mode, these units expect:

- project checkout at `/opt/alarm-web`
- backend import path at `/opt/alarm-web/web/backend`
- backend environment file at `/etc/alarm-web/backend.env`
- set `ALARM_WEB_ENVIRONMENT=production`
- use production DB/Redis URLs for host deployment (not compose hostnames)

### Web Stack Testing

From `alarm_app/`:

```bash
# backend + shared tests
./.venv/bin/pytest -q

# frontend checks
cd web/frontend
npm install
npm run lint
npm run build
```

Quick smoke after compose up:

```bash
curl -I http://localhost/
curl -i http://localhost/api/auth/me   # expected: HTTP 401 without token
```

## Usage

### Running the Application

```bash
# From the parent directory of alarm_app
python -m alarm_app.main
```

Or using the included Makefile:

```bash
cd alarm_app
make run
```

### Workflow

1. **Load alarm data** -- click "Browse" in the sidebar to select a directory containing alarm CSV/XLSX exports. The app recursively discovers all supported files.
2. **Select files** -- check the files you want to load from the file list, then click "Load Selected".
3. **Filter** -- use the search bar, date pickers, dropdown filters (vendor, network, category, status), and duration range to narrow results. Click column headers for per-column filter popups.
4. **Backup-time analysis** -- click the "Backup Time" button to compute battery hold times across all loaded Power and Down alarms. Results open in a dedicated dialog with summary statistics and export.
5. **BDT validation** -- switch to the BDT tab, load Battery Discharge Test `.xlsx` files, and validate them against the loaded alarm data. Each file is checked against 11 rules with per-rule verdicts. If a weekly summary workbook (for example, `Weekly Battery Update.xlsx`) is present beside the BDT files, R11 also cross-checks against that workbook by **Short Code + Test Date**.
6. **Export** -- export the current filtered view or backup-time results to Excel. BDT export writes one summary sheet (`BDT 2025-2026`) in the same 53-column layout used by the weekly summary file, with normalized week/date/unit formatting.
7. **Reporting** -- open the daily review report from the BDT tab or top bar.

### Alarm Classification

Alarms are classified by:

- **Filename keywords**: files containing `"power"`, `"down"`, or `"door"` in the name are classified accordingly
- **Alarm ID lists**: configurable via the UI; alarm IDs can be mapped to Power, Down, or Door categories (stored in `~/.alarm_viewer/alarm_ids.json`)
- **Door heuristics**: alarms with door signals in `alarm_name`/`file_source`/`alarm_source` are auto-classified as Door

### Schema Detection

The parser auto-detects the vendor schema by inspecting column headers:

| Header present                  | Schema |
| ------------------------------- | ------ |
| `Site ID` (without `Site Name`) | Nokia  |
| `Site Name`                     | Huawei |

Both schemas normalize to the same internal column set for unified filtering and analysis.

## Architecture

```
alarm_app/
├── main.py            Entry point -- QApplication setup, High-DPI, Fusion style
├── constants.py       Schema maps (Huawei/Nokia), display columns, widths, app metadata
├── styles.py          Catppuccin Mocha dark QSS theme
├── models.py          AlarmTableModel -- QAbstractTableModel with pre-stringified 2D cache
├── parsers.py         File discovery, CSV/XLSX parsing, LoaderThread, ExportThread
├── backup_time.py     compute_backup_times() + BackupTimeDialog + BackupTimeThread
├── bdt_parser.py      Battery Discharge Test Excel parser (openpyxl, non-tabular layout)
├── bdt_validator.py   11-rule BDT validation engine with cross-referencing against alarms
├── state.py           Session persistence -- JSON state + Parquet DataFrame cache
├── viewer.py          AlarmViewer (QMainWindow) -- all UI, filter logic, slots
├── requirements.txt   Python dependencies
├── Makefile           Convenience runner
└── scripts/
    └── build_windows.bat   PyInstaller build script for standalone .exe
```

### Data Flow

```
Directory scan (os.walk)
        |
        v
LoaderThread (parallel parsing via ThreadPoolExecutor)
        |
        v
Schema detection + column normalization
        |
        v
self._full_df (master unfiltered DataFrame)
        |
        v
Filter pipeline (_search) -- always starts from _full_df
        |
        v
AlarmTableModel (pre-stringified 2D cache for fast scrolling)
        |
        v
QTableView display
```

### BDT Validation Rules

| Rule | Name                  | Description                                                   |
| ---- | --------------------- | ------------------------------------------------------------- |
| R1   | Photos                | Required photo categories (rectifier and batteries) are present |
| R2   | Power Alarm + Duration | Rejects when summary duration exists without a Power alarm; otherwise aligns power-alarm duration with BDT duration using a default ±15 minute tolerance (configurable) |
| R3   | String vs Bus Bar Ampere | Uses `E = bus bar ampere - sum(string amperes)` and accepts only when `-3 <= E <= 0` |
<!-- | R4   | Discharge Table Match | Reported backup time matches discharge readings               | -->
| R5   | Starting I-Battery ampere | Starting battery current is approximately 0 A (`|I| < 0.5A`) |
| R6   | End Voltage / Completion | Accepted when discharge is `>= 180` min OR end voltage is `45.0--47.0 V` |
| R7   | V/A Inverse           | Voltage and ampere show inverse correlation during discharge  |
| R8   | Sizing vs Actual      | Validates expected backup duration from battery sizing against measured duration using the configured tolerance |
| R9   | Discharge Current Tolerance | Discharge current remains within ±1 A of baseline reading |
| R10  | Door Alarm Condition  | Door alarm detected for same site on test date               |
| R11  | Summary Checklist     | Cross-checks Short Code/PLD/rectifier-battery-discharge values against Summary sheet or external weekly summary workbook |

History comparison is shown in the **TEST HISTORY COMPARISON** panel in the details view and does not participate in rule scoring.

### Performance Optimizations

- **Parallel file parsing** -- `ThreadPoolExecutor` with up to 6 workers, largest files first
- **Pre-stringified table cache** -- `AlarmTableModel` converts all cells to strings once on load; `data()` never touches pandas per-cell
- **Parquet session cache** -- DataFrame saved as Parquet for sub-second restore vs. 10--30s re-parsing
- **Vectorized datetime conversion** -- `pd.to_datetime` with `format="mixed"` and `errors="coerce"`
- **Pre-computed duration seconds** -- `_duration_secs` float column for fast numeric filtering

## Building executable apps (GUI)

### Windows bundle (internal/dev)

Run the included build script from any directory:

```bash
cd alarm_app/scripts
build_windows.bat
```

This creates an installed-product style bundle at `alarm_app/dist/AlarmViewer/`. The script:

1. Creates a temporary virtual environment
2. Installs all dependencies
3. Builds the app bundle with `AlarmViewer.spec`
4. Cleans up build artifacts

### Windows installer (.exe setup)

To create a polished installer wizard for end users:

```bash
cd alarm_app/scripts
build_windows_installer.bat
```

This produces:

- `alarm_app/dist/AlarmViewer/` (installer staging bundle)
- `alarm_app/dist/AlarmViewer-Setup.exe` (installer wizard)

The installer is the intended end-user distribution. On first launch the app
bootstraps its local runtime under `~/.alarm_viewer/`, including:

- SQLite app database
- DuckDB alarm store
- blob/image storage
- rotating log files

Installer requirements:

- Inno Setup 6 (`iscc`) installed and available on PATH

### macOS

Run the included macOS build script:

```bash
cd alarm_app/scripts
./build_macos.sh
```

This creates the macOS app bundle at `dist/AlarmViewer.app`.

### macOS installer (.dmg)

To package a user-friendly macOS installer image:

```bash
cd alarm_app/scripts
./build_macos_installer.sh
```

This produces:

- `dist/AlarmViewer.app`
- `dist/AlarmViewer-macOS.dmg`

The script supports optional signing/notarization via environment variables:

- `APPLE_DEVELOPER_ID_APPLICATION`
- `APPLE_ID`
- `APPLE_TEAM_ID`
- `APPLE_APP_SPECIFIC_PASSWORD`

### Makefile shortcuts

From `alarm_app/` you can also run:

```bash
make build-windows
make build-macos
make build-windows-installer
make build-macos-installer
```

### Get ready-made installers from GitHub Actions

If you want installable artifacts without running local packaging commands:

1. Push your branch to GitHub.
2. Open **Actions** and run one of:
        - **Build Windows EXE**
        - **Build Windows Installer**
        - **Build macOS Installer**
3. Click **Run workflow**.
4. Download artifacts:
        - `AlarmViewer-windows-bundle-internal`
        - `AlarmViewer-windows-installer`
        - `AlarmViewer-macos-installer`

Windows users should install via `AlarmViewer-Setup.exe`. macOS users should install from `AlarmViewer-macOS.dmg`.

## Session Persistence

The installed app bootstraps and saves state under `~/.alarm_viewer/`:

| File                 | Contents                                        |
| -------------------- | ----------------------------------------------- |
| `state.json`         | UI settings, filter values, window geometry     |
| `alarm_viewer.db`    | SQLite app metadata/state DB                    |
| `alarms.duckdb`      | Local DuckDB alarm store                        |
| `blobs/`             | Blob-backed stored images                       |
| `logs/`              | Rotating app/backend/database logs              |
| `alarm_ids.json`     | Custom Power/Down alarm ID classification lists |

## Local LLM Data Agent

The app includes a local read-only data tool layer for LLM use. It can read:

- `~/.alarm_viewer/alarms.duckdb`
- `~/.alarm_viewer/alarms.local.duckdb`
- `~/.alarm_viewer/alarm_viewer.db`
- `~/.alarm_viewer/blobs/`

It can also create CSV/XLSX exports under `~/.alarm_viewer/exports/`. It does not update operational alarm, BDT, rule, or blob records.

Run the MCP server over stdio:

```bash
python -m alarm_app.llm_tools
```

The normal app entrypoint can also run it without launching the GUI:

```bash
python -m alarm_app.main --mcp-server
```

The installed/package executable uses the same mode:

```bash
AlarmViewer --mcp-server
```

For MCP clients, configure the command as:

```json
{
  "command": "python",
  "args": ["-m", "alarm_app.main", "--mcp-server"],
  "cwd": "/path/to/orange"
}
```

For the installed app, point the MCP client at the packaged `AlarmViewer` executable and use:

```json
{
  "command": "/path/to/AlarmViewer",
  "args": ["--mcp-server"]
}
```

Available tools include:

- `list_data_sources`
- `query_alarms`
- `alarm_stats`
- `query_bdt_results`
- `get_bdt_detail`
- `get_photo_metadata`
- `read_photo_blob`
- `export_report`

Use the OpenRouter-backed local agent:

```bash
export OPENROUTER_API_KEY="..."
python -m alarm_app.llm_tools.openrouter_agent "How many rejected BDT validations do we have?"
```

Or through the normal app entrypoint:

```bash
OPENROUTER_API_KEY="..." python -m alarm_app.main --ask "How many rejected BDT validations do we have?"
```

The installed/package executable supports the same agent mode:

```bash
OPENROUTER_API_KEY="..." AlarmViewer --ask "How many rejected BDT validations do we have?"
```

Optional model override:

```bash
OPENROUTER_MODEL="openai/gpt-4.1-mini" python -m alarm_app.llm_tools.openrouter_agent "Export rejected R3 BDT rows to CSV"
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m "Add my feature"`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License.

## Web Frontend Scaffold (Migration)

A React + Vite TypeScript scaffold now lives in `alarm_app/web/frontend`.

```bash
cd alarm_app/web
cp .env.example .env
# set VITE_API_BASE_URL/VITE_PHOTOS_BASE_URL if needed
cd frontend
npm install
npm run dev
```

Build check:

```bash
npm run build
```
