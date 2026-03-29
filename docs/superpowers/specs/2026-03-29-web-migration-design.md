# Alarm Viewer Web Migration Design Spec

## 1. Overview

Migrate the Alarm Viewer PyQt5 desktop app to a web platform. The web version replicates all existing alarm analysis and BDT validation functionality, adds direct integration with Huawei OWS/UTN network management systems, and supports multi-team access with role-based permissions.

### Goals

- Replace the desktop app with a web app accessible from any browser
- Pull alarm data directly from Huawei NCE-T (REST API) and U2000 (file import)
- Support 10,500+ sites and 10-20 GB of alarm data with millions of records
- Multi-team access with admin-managed membership
- Strengthen BDT validation with alarm-BDT linkage and 4 new fraud detection rules
- Host on a standard VPS (no cloud-specific services required)

### Non-Goals

- Real-time alarm streaming (teams work with historical data)
- Cloud hosting (Vercel, AWS managed services)
- Mobile-native app
- Automated photo similarity scoring between BDT tests

## 2. System Architecture

```
+-----------------------------------------------------------+
|                          VPS                               |
|                                                            |
|  +----------+    +--------------+    +--------------+     |
|  |  Nginx   |--->|   FastAPI    |--->|  PostgreSQL  |     |
|  | (reverse |    |  (Uvicorn)   |    |              |     |
|  |  proxy)  |    +------+-------+    +--------------+     |
|  |          |           |                                  |
|  |  serves  |    +------v-------+    +--------------+     |
|  |  React   |    |   Celery     |--->|    Redis     |     |
|  |  static  |    |   Workers    |    |  (broker +   |     |
|  |  build   |    |   + Beat     |    |   cache)     |     |
|  +----------+    +--------------+    +--------------+     |
|                         |                                  |
|              +----------+----------+                       |
|              v          v          v                        |
|        Huawei NCE-T   FTP/SFTP   Shared                   |
|        REST API       pickup     path scan                 |
|                                                            |
|  +------------------------------------------------------+ |
|  |  /data/bdt_photos/{site}/{date}/originals/            | |
|  |  /data/bdt_photos/{site}/{date}/thumbnails/           | |
|  |  (Nginx serves directly as static files)              | |
|  +------------------------------------------------------+ |
+-----------------------------------------------------------+
```

### Components

| Component           | Role                                                                   |
| ------------------- | ---------------------------------------------------------------------- |
| Nginx               | Reverse proxy, serves React static build + BDT photos, SSL termination |
| FastAPI (Uvicorn)   | REST API for frontend, auth, alarm queries, BDT results                |
| Celery Workers      | Heavy processing: alarm sync, file parsing, BDT validation, exports    |
| Celery Beat         | Scheduler: triggers cron jobs on configured intervals                  |
| PostgreSQL 16       | All persistent data: users, teams, alarms, BDT results, config         |
| Redis               | Celery message broker + optional query result caching                  |
| Filesystem (/data/) | BDT photo storage: originals + pre-generated thumbnails                |

## 3. Tech Stack

| Layer        | Technology                                                                          |
| ------------ | ----------------------------------------------------------------------------------- |
| Frontend     | React 18, Vite, React Router, TanStack Table, TanStack Query, Tailwind CSS, Zustand |
| Backend      | FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2                               |
| Auth         | JWT (access + refresh tokens), passlib + bcrypt                                     |
| Task Queue   | Celery + Redis, Celery Beat                                                         |
| Database     | PostgreSQL 16 with table partitioning                                               |
| File Storage | Filesystem with Nginx direct serving                                                |
| Deployment   | Nginx, Uvicorn, systemd services, Docker optional                                   |
| Python libs  | pandas, openpyxl, python-calamine, numpy, Pillow, httpx                             |

## 4. Database Schema

### 4.1 Auth & Teams

```sql
CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    created_by  UUID,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(150) NOT NULL,
    role          VARCHAR(20) NOT NULL CHECK (role IN ('superadmin','admin','member','viewer')),
    team_id       UUID REFERENCES teams(id),
    is_active     BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now(),
    last_login    TIMESTAMPTZ
);
```

Role hierarchy:

- `superadmin`: manages all teams, users, system config
- `admin`: manages their own team members, data sources, alarm ID config
- `member`: loads, filters, validates, exports
- `viewer`: read-only access

### 4.2 Sites

```sql
CREATE TABLE sites (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id    VARCHAR(50) UNIQUE NOT NULL,
    site_name  VARCHAR(200),
    vendor     VARCHAR(20),
    region     VARCHAR(100),
    team_id    UUID REFERENCES teams(id),
    -- Known battery specs (for R11 cross-check)
    battery_brand   VARCHAR(100),
    battery_ah      FLOAT,
    battery_voltage FLOAT,
    num_strings     INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_sites_team ON sites(team_id);
CREATE INDEX idx_sites_site_id ON sites(site_id);
```

### 4.3 Alarms

```sql
CREATE TABLE alarms (
    id                BIGSERIAL PRIMARY KEY,
    site_id           UUID NOT NULL REFERENCES sites(id),
    alarm_id          VARCHAR(50),
    alarm_name        VARCHAR(300),
    alarm_source      VARCHAR(300),
    network_type      VARCHAR(10),
    vendor            VARCHAR(50),
    occurred_on       TIMESTAMPTZ NOT NULL,
    cleared_on        TIMESTAMPTZ,
    duration_secs     FLOAT,
    duration_display  VARCHAR(20),
    clearance_status  VARCHAR(50),
    alarm_category    VARCHAR(20) CHECK (alarm_category IN ('Power','Down','Unknown')),
    site_down_flag    BOOLEAN DEFAULT false,
    source_type       VARCHAR(20) CHECK (source_type IN ('nce_api','file_import')),
    source_ref        VARCHAR(300),
    ingested_at       TIMESTAMPTZ DEFAULT now()
) PARTITION BY RANGE (occurred_on);

-- Monthly partitions (create as needed)
-- CREATE TABLE alarms_2026_01 PARTITION OF alarms
--     FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE INDEX idx_alarms_site_date ON alarms(site_id, occurred_on);
CREATE INDEX idx_alarms_category ON alarms(alarm_category);
CREATE INDEX idx_alarms_occurred ON alarms(occurred_on);
CREATE INDEX idx_alarms_source ON alarms(source_type, source_ref);
```

Partitioned by month on `occurred_on`. At 10-20 GB this keeps individual partition scans fast. Old partitions can be detached for archival.

Deduplication: unique constraint on `(site_id, alarm_id, occurred_on)` prevents the same alarm from creating duplicate rows regardless of source. During ingestion, `ON CONFLICT DO NOTHING` skips already-seen alarms.

```sql
CREATE UNIQUE INDEX idx_alarms_dedup ON alarms(site_id, alarm_id, occurred_on);
```

Site auto-creation: when ingesting alarms for a `site_id` not yet in the `sites` table, the ingestion task creates a stub site record with vendor derived from the alarm source. Teams can enrich site records later.

### 4.4 BDT Files & Validation

```sql
CREATE TABLE bdt_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        VARCHAR(300) NOT NULL,
    file_path       VARCHAR(500),
    site_id         UUID REFERENCES sites(id),
    test_date       DATE,
    time_in         VARCHAR(20),
    time_out        VARCHAR(20),
    discharge_minutes FLOAT,
    start_voltage   FLOAT,
    start_ampere    FLOAT,
    end_voltage     FLOAT,
    end_ampere      FLOAT,
    after_reconnect_voltage FLOAT,
    after_reconnect_ampere  FLOAT,
    ibat_before_test FLOAT,
    battery_brand   VARCHAR(100),
    battery_ah      FLOAT,
    battery_voltage FLOAT,
    num_strings     INT,
    discharge_readings JSONB,
    photo_count     INT DEFAULT 0,
    parse_errors    JSONB,
    uploaded_by     UUID REFERENCES users(id),
    source_type     VARCHAR(20) CHECK (source_type IN ('upload','scan')),
    status          VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending','validated','error')),
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (filename, site_id, test_date)
);

CREATE INDEX idx_bdt_site ON bdt_files(site_id);
CREATE INDEX idx_bdt_date ON bdt_files(test_date);

CREATE TABLE bdt_validations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bdt_file_id     UUID NOT NULL REFERENCES bdt_files(id) ON DELETE CASCADE,
    overall_verdict VARCHAR(20) NOT NULL CHECK (overall_verdict IN ('Accepted','Rejected','Revise')),
    tolerance_used  FLOAT NOT NULL,
    health_pct_used FLOAT NOT NULL,
    validated_at    TIMESTAMPTZ DEFAULT now(),
    validated_by    UUID REFERENCES users(id)
);

CREATE TABLE bdt_rule_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    validation_id   UUID NOT NULL REFERENCES bdt_validations(id) ON DELETE CASCADE,
    rule_id         VARCHAR(10) NOT NULL,
    rule_name       VARCHAR(100) NOT NULL,
    verdict         VARCHAR(20) NOT NULL CHECK (verdict IN ('Accepted','Rejected','Revise','N/A')),
    detail          TEXT,
    passed          BOOLEAN
);

CREATE INDEX idx_bdt_rules_validation ON bdt_rule_results(validation_id);
```

### 4.5 BDT Photos

```sql
CREATE TABLE bdt_photos (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bdt_file_id   UUID NOT NULL REFERENCES bdt_files(id) ON DELETE CASCADE,
    slot_index    INT NOT NULL CHECK (slot_index BETWEEN 0 AND 14),
    label         VARCHAR(200),
    storage_path  VARCHAR(500),
    thumbnail_path VARCHAR(500),
    image_ext     VARCHAR(10),
    file_size_bytes BIGINT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (bdt_file_id, slot_index)
);
```

Photo storage layout on disk:

```
/data/bdt_photos/
  {site_id}/
    {test_date}/
      originals/
        slot_00_rectifier_front.jpg
        slot_01_rectifier_readings.jpg
        ...
      thumbnails/
        slot_00_rectifier_front_thumb.jpg
        ...
```

Nginx serves photos via X-Accel-Redirect: the FastAPI endpoint checks auth + team permissions, then returns an `X-Accel-Redirect` header so Nginx serves the file directly without exposing the filesystem path. This prevents unauthenticated access to photos.

Estimated storage: 300-500 GB for originals + thumbnails.

### 4.6 Alarm-BDT Linkage

```sql
CREATE TABLE bdt_alarm_links (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bdt_file_id       UUID NOT NULL REFERENCES bdt_files(id) ON DELETE CASCADE,
    alarm_id          BIGINT NOT NULL REFERENCES alarms(id),
    link_type         VARCHAR(20) CHECK (link_type IN ('power_match','down_match')),
    time_offset_secs  FLOAT,
    duration_diff_secs FLOAT,
    confidence        VARCHAR(20) CHECK (confidence IN ('exact','within_tolerance','mismatch','unlinked')),
    linked_at         TIMESTAMPTZ DEFAULT now(),
    linked_by         VARCHAR(20) CHECK (linked_by IN ('auto','manual'))
);

CREATE INDEX idx_bdt_links_bdt ON bdt_alarm_links(bdt_file_id);
CREATE INDEX idx_bdt_links_alarm ON bdt_alarm_links(alarm_id);
```

Auto-linking confidence levels:

- **exact**: timestamps within 60s, duration within 5%
- **within_tolerance**: timestamps within 5 min, duration within configured tolerance
- **mismatch**: same site + date but times/durations don't align
- **unlinked**: no matching alarm found (strongest fraud signal)

### 4.7 Data Source Config

```sql
CREATE TABLE data_sources (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                  VARCHAR(200) NOT NULL,
    source_type           VARCHAR(20) NOT NULL CHECK (source_type IN ('nce_rest','file_ftp','file_sftp','file_local')),
    connection_config     JSONB NOT NULL,  -- encrypted credentials
    sync_interval_minutes INT DEFAULT 15,
    is_active             BOOLEAN DEFAULT true,
    last_sync_at          TIMESTAMPTZ,
    last_sync_status      VARCHAR(50),
    last_sync_records     INT,
    team_id               UUID REFERENCES teams(id),
    created_at            TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE alarm_id_config (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id    UUID UNIQUE REFERENCES teams(id),
    power_ids  JSONB DEFAULT '[]',
    down_ids   JSONB DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

## 5. API Design

### 5.1 Auth

```
POST   /api/auth/login              email + password -> JWT access + refresh tokens
POST   /api/auth/refresh            refresh token -> new access token
POST   /api/auth/logout             invalidate token
GET    /api/auth/me                 current user profile
PUT    /api/auth/me/password        change own password
```

### 5.2 Team & User Management (admin+)

```
GET    /api/teams                   list teams
POST   /api/teams                   create team (superadmin)
GET    /api/teams/{id}/members      list members
POST   /api/teams/{id}/members      add member (admin+)
PUT    /api/teams/{id}/members/{uid} update role / deactivate
DELETE /api/teams/{id}/members/{uid} remove from team
```

### 5.3 Sites

```
GET    /api/sites                   paginated, filterable by team/vendor/region
GET    /api/sites/{id}              site detail with battery specs
POST   /api/sites/import            bulk import from CSV
PUT    /api/sites/{id}              update battery specs (for R11 cross-check)
```

### 5.4 Alarms

```
POST   /api/alarms/search           main search endpoint
```

Search request body:

```json
{
  "site_ids": ["3420", "KONA"],
  "date_from": "2025-12-01",
  "date_to": "2026-01-15",
  "category": "power",
  "network_type": "4G",
  "vendor": "huawei",
  "min_duration_minutes": 15,
  "both_pd_only": false,
  "column_filters": { "clearance_status": ["Cleared"] },
  "sort_by": "occurred_on",
  "sort_order": "desc",
  "page": 1,
  "page_size": 100
}
```

```
GET    /api/alarms/stats            total/power/down/sites/avg_duration for current filters
POST   /api/alarms/export           queue XLSX export -> returns task ID
GET    /api/alarms/export/{task_id} download when ready
POST   /api/alarms/backup-time      compute backup times for current filters
GET    /api/alarms/{id}/linked-bdt  BDT test linked to this alarm
```

### 5.5 Data Ingestion

```
GET    /api/sources                 list configured data sources
POST   /api/sources                 add NCE-T connection or file path
PUT    /api/sources/{id}            update connection config
POST   /api/sources/{id}/sync       trigger manual sync
GET    /api/sources/{id}/status     last sync status + stats

POST   /api/import/upload           upload CSV/XLSX alarm files manually
GET    /api/import/history          past imports with row counts + errors
```

### 5.6 BDT Validation

```
POST   /api/bdt/upload              upload BDT Excel file(s)
POST   /api/bdt/validate            run validation on uploaded or scanned files
GET    /api/bdt/results             list results (paginated, filterable)
GET    /api/bdt/results/{id}        single result with rules + detail
GET    /api/bdt/results/{id}/photos photo slot metadata + thumbnail URLs
GET    /api/bdt/results/{id}/linked-alarms  alarms matched to this BDT test
POST   /api/bdt/results/{id}/relink manually link/unlink alarms
GET    /api/bdt/compare/{site_id}   multi-year comparison data
GET    /api/bdt/integrity-report    linked vs unlinked vs mismatch overview
POST   /api/bdt/export              queue XLSX export -> task ID
GET    /api/bdt/export/{task_id}    download when ready

GET    /api/bdt/scan-config         current scan path + schedule
PUT    /api/bdt/scan-config         update scan path + schedule
POST   /api/bdt/scan-config/trigger manual scan
```

### 5.7 Config

```
GET    /api/config/alarm-ids        current power/down ID lists
PUT    /api/config/alarm-ids        update and trigger re-classification
```

### 5.8 Background Tasks

```
GET    /api/tasks/{id}              poll task status (export, validation, sync)
```

## 6. Celery Tasks & Cron Jobs

### Periodic (Celery Beat)

| Task                      | Default Interval | Description                                                                                                        |
| ------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------ |
| `sync_alarms_from_nce`    | 15 min           | Authenticate to NCE-T REST, pull new alarms, deduplicate, classify, compute site_down_flag                         |
| `sync_alarms_from_files`  | 30 min           | Scan FTP/SFTP/local paths for new CSV/XLSX, parse, deduplicate, ingest, archive processed files                    |
| `scan_bdt_files`          | 60 min           | Scan shared path for new BDT xlsx, parse, extract photos, generate thumbnails, auto-link to alarms, run validation |
| `create_alarm_partitions` | Daily            | Create next month's partition table if it doesn't exist                                                            |

### On-Demand (triggered by API)

| Task                      | Trigger                                              |
| ------------------------- | ---------------------------------------------------- |
| `validate_bdt_upload`     | User uploads BDT file(s)                             |
| `export_alarms_xlsx`      | User requests alarm export                           |
| `export_bdt_results_xlsx` | User requests BDT results export                     |
| `relink_bdt_alarms`       | Re-run alarm linkage after new alarm data            |
| `reclassify_alarms`       | Re-run power/down classification after config change |
| `compute_backup_times`    | User requests backup time analysis                   |

## 7. BDT Validation Rules

### Existing Rules (ported from desktop)

| Rule | Name              | Logic                                                                                                                                                                  |
| ---- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1   | Photos            | All 15 photo slots filled. Revise if partial, Reject if zero.                                                                                                          |
| R2   | Power Alarm Match | Power alarm exists within 30 min of BDT `time_in` for the same site. Upgraded from date-level to timestamp-level matching.                                             |
| R3   | Duration Match    | BDT discharge duration matches the time-closest Power alarm duration within configured tolerance (default 15%). Upgraded from longest-alarm to closest-alarm matching. |
| R4   | Discharge Table   | Last discharge reading timestamp matches reported duration within tolerance.                                                                                           |
| R5   | I Battery         | Battery current before test < 0.5A (rounds to zero).                                                                                                                   |
| R6   | End Voltage       | Final voltage 45-47V. Auto-accept if test ran 180+ min with remaining theoretical capacity.                                                                            |
| R7   | V/A Inverse       | Negative correlation between voltage and ampere across readings (3+ paired readings required).                                                                         |
| R8   | Theoretical BT    | Reported duration vs calculated theoretical from battery specs. 3-hour cutoff detection widened to 170-185 min band.                                                   |

### New Rules (web version)

| Rule | Name                      | Logic                                                                                                                                       |
| ---- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| R9   | After Reconnect           | After rectifier reconnection, voltage must rise from last discharge reading. If after_reconnect_voltage <= end_voltage, data is fabricated. |
| R10  | Duplicate Detection       | Flag BDT files for the same site with identical discharge readings (copy-paste detection). Compare voltage/ampere arrays with tolerance.    |
| R11  | Battery Specs Cross-Check | If site has known battery specs in the database, compare BDT-reported specs (AH, voltage, strings) against them. Flag mismatches.           |
| R12  | Alarm Timestamp Sync      | Exact time offset between alarm `occurred_on` and BDT `time_in`. Report offset in seconds. Flag if offset > 30 min.                         |

### Alarm-BDT Auto-Linking

Runs after every BDT validation and after every alarm ingestion batch:

1. Match BDT `site_code` to `sites.site_id`
2. Find Power alarm where `occurred_on` is within 30 min of BDT test start (`test_date + time_in`)
3. Compare durations
4. Assign confidence: exact / within_tolerance / mismatch / unlinked
5. Store in `bdt_alarm_links` table

### Overall Verdict Logic

- Any rule Rejected -> overall Rejected
- Any rule Revise (none Rejected) -> overall Revise
- All rules Accepted or N/A -> overall Accepted

## 8. Huawei Integration

### NCE-T REST API (newer systems)

```
Authentication:
  POST https://{host}:26335/controller/v2/tokens
  Body: {"userName": "nbi_user", "password": "..."}
  Returns: token_id (expires ~30 min)

Query alarms:
  POST https://{host}:26335/restconf/v1/alarm/alarms
  Header: X-Auth-Token: {token}
  Body: {"pageSize": 100, "pageIndex": 1}
  Returns: JSON alarm records

Query historical alarms:
  POST https://{host}:26335/restconf/v1/alarm/history-alarms
  Body: {"startTime": "...", "endTime": "...", "pageSize": 100}
```

Field mapping from NCE-T JSON to internal schema:

| NCE-T Field | Internal Column                          |
| ----------- | ---------------------------------------- |
| neName      | site_id (lookup via sites table)         |
| alarmName   | alarm_name                               |
| alarmId     | alarm_id                                 |
| severity    | (mapped to category via alarm_id_config) |
| occurTime   | occurred_on                              |
| clearTime   | cleared_on                               |
| alarmSource | alarm_source                             |
| category    | network_type (derived)                   |

### U2000 File Import (legacy systems)

Reuses existing parser logic from `parsers.py`:

- `discover_alarm_files()` scans configured directory
- `parse_alarm_file()` handles CSV/XLSX with Huawei/Nokia schema detection
- `classify_by_alarm_id()` applies team's alarm ID config
- `compute_site_down_flag()` marks power+down correlation

Supports both manual upload (via API) and automated pickup from FTP/SFTP/local paths.

## 9. Frontend Pages

```
/login                          email + password

/dashboard                      overview stats, recent syncs, BDT summary

/alarms                         main alarm table
  - sidebar: site filter, date range, category, network, vendor, duration
  - table: sortable columns, filter popups, server-side pagination
  - stats panel: total / power / down / sites / avg duration
  - actions: export, backup time, both P+D filter
  - row click: alarm detail with linked BDT test

/alarms/backup-time             backup time analysis results + export

/validation                     BDT validation
  - search: site ID, date, year
  - results table: file, site, date, verdict, R1-R12
  - detail panel: file info, discharge readings, rules, photos
  - photo comparison: side-by-side multi-year
  - integrity report: linked vs unlinked vs mismatch
  - upload BDT files

/sites                          site directory
  - list with search/filter
  - site detail: battery specs, alarm history, BDT history
  - bulk import

/settings
  /settings/team                manage members, roles
  /settings/alarm-ids           power/down alarm ID classification
  /settings/sources             data source connections
  /settings/bdt-scan            scan path + schedule
  /settings/profile             password, preferences

/admin                          superadmin only
  /admin/teams                  manage all teams
  /admin/users                  all users
  /admin/system                 sync status, task queue, storage usage
```

## 10. Desktop-to-Web Port Map

| Desktop Module                            | Web Equivalent              | Changes                                        |
| ----------------------------------------- | --------------------------- | ---------------------------------------------- |
| `parsers.py` file discovery + parsing     | Celery task + service layer | Same logic, runs server-side                   |
| `parsers.py` `classify_by_alarm_id()`     | Service function            | Uses DB config instead of JSON file            |
| `parsers.py` `compute_site_down_flag()`   | Service function            | Runs on ingestion, result stored in DB         |
| `bdt_parser.py` `parse_bdt_file()`        | Celery task                 | Same extraction, saves to DB + filesystem      |
| `bdt_validator.py` rules R1-R8            | Validation service          | Expanded to R1-R12, queries DB                 |
| `backup_time.py` `compute_backup_times()` | API endpoint + Celery task  | Same join logic against DB                     |
| `models.py` `AlarmTableModel`             | Not needed                  | Frontend table handles display                 |
| `state.py` session persistence            | Not needed                  | DB replaces Parquet, auth replaces local state |
| `styles.py` Catppuccin theme              | Tailwind config             | Port color palette to Tailwind custom theme    |
| `viewer.py` `_apply_filters()`            | SQL WHERE clauses           | Same filters, server-side                      |

## 11. Deployment

### VPS Requirements

| Resource    | Minimum   | Recommended         |
| ----------- | --------- | ------------------- |
| CPU         | 4 cores   | 8 cores             |
| RAM         | 8 GB      | 16 GB               |
| OS disk     | 50 GB SSD | 100 GB SSD          |
| Data volume | 300 GB    | 500 GB (BDT photos) |
| PostgreSQL  | 16+       | 16+                 |

### Services (systemd)

```
alarm-web-api.service       Uvicorn (FastAPI)
alarm-celery-worker.service Celery worker (concurrency=4)
alarm-celery-beat.service   Celery Beat scheduler
nginx.service               Reverse proxy + static files
postgresql.service          Database
redis.service               Message broker
```

### Nginx Config

- `/` serves React static build from `/var/www/alarm-web/dist/`
- `/api/` proxies to Uvicorn on `127.0.0.1:8000`
- `/photos/` serves `/data/bdt_photos/` as static files
- SSL via Let's Encrypt / certbot

## 12. Security

- Passwords hashed with bcrypt (passlib)
- JWT access tokens (15 min expiry) + refresh tokens (7 day expiry)
- Huawei connection credentials encrypted at rest in `data_sources.connection_config` (Fernet symmetric encryption, key from environment variable)
- All API endpoints require valid JWT except `/api/auth/login`
- Team data isolation: every DB query scoped by `team_id` from the authenticated user's token
- Rate limiting on auth endpoints (5 attempts per minute)
- CORS restricted to the frontend origin
- Photos served via Nginx X-Accel-Redirect (auth checked by FastAPI before Nginx serves file)
- Initial superadmin account created via CLI seed command (`python -m alarm_web seed-admin --email admin@example.com`)

## 13. Scope Decomposition

This is a large system. Recommended build order:

### Phase 1: Foundation

- Project scaffolding (FastAPI + React + Vite + PostgreSQL + Alembic)
- Auth system (users, teams, JWT, role-based access)
- Database schema + migrations
- Sites CRUD + bulk import

### Phase 2: Alarm Engine

- Alarm ingestion from file upload (port parsers.py)
- Alarm search API (port \_apply_filters to SQL)
- Frontend alarm table with filters, stats, pagination
- Alarm export
- Alarm ID config + reclassification

### Phase 3: Huawei Integration

- NCE-T REST API client
- File-based sync (FTP/SFTP/local path scanning)
- Celery Beat scheduled sync
- Data source management UI
- Deduplication logic

### Phase 4: BDT Validation

- BDT file upload + parsing (port bdt_parser.py)
- Photo extraction + thumbnail generation
- Validation rules R1-R12 (port + expand bdt_validator.py)
- Alarm-BDT auto-linkage engine
- Validation results UI with detail panel
- Multi-year photo comparison

### Phase 5: Backup Time & Reporting

- Backup time computation (port backup_time.py)
- Backup time UI
- BDT integrity report
- Dashboard with overview stats

### Phase 6: Polish & Deploy

- Catppuccin dark theme port to Tailwind
- Error handling + loading states
- Deployment setup (Nginx, systemd, SSL)
- Data migration from desktop (import existing Parquet cache if needed)
