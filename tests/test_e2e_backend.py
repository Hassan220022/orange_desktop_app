"""Comprehensive E2E tests for the FastAPI backend.

Covers health, alarm upsert/query, sync batches/status, PM runs,
and full workflow pipelines.
"""

import hashlib
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient wired to a fresh temporary SQLite database."""
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("alarm_app.web.config.DATABASE_URL", db_url)
    monkeypatch.setattr("alarm_app.web.deps._engine", None)
    monkeypatch.setattr("alarm_app.web.deps._SessionFactory", None)
    monkeypatch.setattr("alarm_app.db.engine._app_engine", None)
    monkeypatch.setattr("alarm_app.db.engine._app_session_factory", None)

    try:
        from alarm_app.web.app import create_app
    except ImportError:
        from web.app import create_app

    app = create_app()
    yield TestClient(app)


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    """Direct SQLAlchemy session for seeding / verifying against the same DB."""
    monkeypatch.setattr("alarm_app.db.engine.STATE_DIR", tmp_path)
    monkeypatch.setattr("alarm_app.db.engine.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(
        "alarm_app.web.config.DATABASE_URL",
        f"sqlite:///{tmp_path / 'test.db'}",
    )
    monkeypatch.setattr("alarm_app.web.deps._engine", None)
    monkeypatch.setattr("alarm_app.web.deps._SessionFactory", None)
    monkeypatch.setattr("alarm_app.db.engine._app_engine", None)
    monkeypatch.setattr("alarm_app.db.engine._app_session_factory", None)

    try:
        from alarm_app.db.engine import create_engine, init_db
    except ImportError:
        from db.engine import create_engine, init_db

    from sqlalchemy.orm import Session

    engine = create_engine()
    init_db(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_alarm_payload(site_id="SITE01", name="Power Failure", **overrides):
    """Build a single alarm item dict ready for the /v1/alarms/upsert body."""
    return {
        "site_id": site_id,
        "alarm_name": name,
        "occurred_on": "2026-01-15 10:30:00",
        "cleared_on": "2026-01-15 12:00:00",
        "duration": "01:30:00",
        "category": "Power",
        "vendor": "Huawei",
        **overrides,
    }


def _make_event(overrides=None):
    """Build a single sync event dict."""
    base = {
        "event_id": str(uuid4()),
        "origin_device_id": str(uuid4()),
        "entity_type": "uploaded_file",
        "entity_local_id": "/path/to/file.csv",
        "op": "upsert",
        "entity_hash": hashlib.sha256(b"test").hexdigest(),
        "payload": {"filename": "alarms.csv", "file_sha256": "abc123"},
    }
    if overrides:
        base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealthE2E:
    def test_health_returns_200_and_app_name(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data


# ---------------------------------------------------------------------------
# ChatGPT MCP connector
# ---------------------------------------------------------------------------


class TestMcpConnectorE2E:
    def test_tunnel_origin_header_blocks_non_mcp_routes(self, client):
        r = client.get(
            "/v1/alarms/query",
            headers={"Host": "alarm-viewer-mcp.local"},
        )

        assert r.status_code == 403
        assert r.json()["detail"] == "Tunnel access is limited to the MCP endpoint"

    def test_tunnel_origin_header_allows_mcp_route(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post(
            "/mcp?token=secret-token",
            headers={"Host": "alarm-viewer-mcp.local"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
        )

        assert r.status_code == 200

    def test_tunnel_origin_header_allows_mcp_trailing_slash_without_redirect(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post(
            "/mcp/?token=secret-token",
            headers={"Host": "alarm-viewer-mcp.local"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
            follow_redirects=False,
        )

        assert r.status_code == 200

    def test_mcp_get_probe_returns_json_status_instead_of_method_error(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.get("/mcp?token=secret-token", follow_redirects=False)

        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        assert r.json()["transport"] == "streamable-http"

    def test_mcp_head_probe_returns_success_without_redirect(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.head("/mcp?token=secret-token", follow_redirects=False)

        assert r.status_code == 200

    def test_mcp_requires_connector_token(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        assert r.status_code == 401
        assert r.json()["detail"] == "Unauthorized"

    def test_mcp_rejects_wrong_connector_token(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=wrong", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        assert r.status_code == 401
        assert r.json()["detail"] == "Unauthorized"

    def test_mcp_accepts_saved_connector_token(self, client, monkeypatch):
        monkeypatch.delenv("ALARM_MCP_TOKEN", raising=False)
        monkeypatch.setattr(
            "alarm_app.web.routers.mcp.state.load_state",
            lambda: {"chatgpt_mcp_token": "saved-token"},
        )

        r = client.post("/mcp?token=saved-token", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        assert r.status_code == 200

    def test_mcp_returns_503_when_connector_token_missing(self, client, monkeypatch):
        monkeypatch.delenv("ALARM_MCP_TOKEN", raising=False)
        monkeypatch.setattr("alarm_app.web.routers.mcp.state.load_state", lambda: {})

        r = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        assert r.status_code == 503
        assert r.json()["detail"] == "ChatGPT MCP connector token is not configured"

    def test_mcp_accepts_lowercase_bearer_token(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post(
            "/mcp",
            headers={"Authorization": "bearer secret-token"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
        )

        assert r.status_code == 200

    def test_mcp_initialize_over_http(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        })

        assert r.status_code == 200
        payload = r.json()
        assert payload["jsonrpc"] == "2.0"
        assert payload["id"] == 1
        assert payload["result"]["serverInfo"]["name"] == "alarm-viewer-local-data"
        assert payload["result"]["capabilities"] == {"tools": {}}

    def test_mcp_tools_list_includes_chatgpt_safety_annotations(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "id": "tools",
            "method": "tools/list",
            "params": {},
        })

        assert r.status_code == 200
        tools = {tool["name"]: tool for tool in r.json()["result"]["tools"]}
        assert tools["query_alarms"]["annotations"] == {"readOnlyHint": True}
        assert tools["export_report"]["annotations"] == {
            "readOnlyHint": False,
            "openWorldHint": False,
            "destructiveHint": False,
        }

    def test_mcp_notification_returns_empty_202(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

        assert r.status_code == 202
        assert r.content == b""

    def test_mcp_invalid_json_rpc_returns_400(self, client, monkeypatch):
        monkeypatch.setenv("ALARM_MCP_TOKEN", "secret-token")

        r = client.post("/mcp?token=secret-token", json={"method": "tools/list"})

        assert r.status_code == 400
        assert r.json()["detail"] == "MCP requests must use JSON-RPC 2.0"


# ---------------------------------------------------------------------------
# Alarm upsert + query
# ---------------------------------------------------------------------------


class TestAlarmUpsertAndQueryE2E:
    def test_upsert_single_alarm_and_query_it(self, client):
        # Act: upsert one alarm
        upsert_r = client.post("/v1/alarms/upsert", json={
            "alarms": [_make_alarm_payload(site_id="SITE01", name="Power Failure")],
        })
        assert upsert_r.status_code == 200
        assert upsert_r.json()["inserted"] == 1

        # Act: query all
        query_r = client.get("/v1/alarms/query")
        assert query_r.status_code == 200
        alarms = query_r.json()["alarms"]
        assert len(alarms) == 1
        assert alarms[0]["site_id"] == "SITE01"
        assert alarms[0]["alarm_name"] == "Power Failure"

    def test_upsert_multiple_alarms_and_verify_count(self, client):
        alarms = [
            _make_alarm_payload(site_id="SITE01", name=f"Alarm {i}")
            for i in range(3)
        ]
        r = client.post("/v1/alarms/upsert", json={"alarms": alarms})
        assert r.status_code == 200
        assert r.json()["inserted"] == 3

        query_r = client.get("/v1/alarms/query")
        assert len(query_r.json()["alarms"]) == 3

    def test_upsert_duplicate_is_idempotent(self, client):
        alarm = _make_alarm_payload(site_id="SITE01", name="Dup Alarm")

        r1 = client.post("/v1/alarms/upsert", json={"alarms": [alarm]})
        assert r1.status_code == 200
        assert r1.json()["inserted"] == 1
        assert r1.json()["skipped"] == 0

        r2 = client.post("/v1/alarms/upsert", json={"alarms": [alarm]})
        assert r2.status_code == 200
        assert r2.json()["inserted"] == 0
        assert r2.json()["skipped"] >= 1

        # Still only one row in the DB
        query_r = client.get("/v1/alarms/query")
        assert len(query_r.json()["alarms"]) == 1

    def test_query_with_site_id_filter(self, client):
        s1 = _make_alarm_payload(site_id="S1", name="S1 Alarm")
        s2 = _make_alarm_payload(site_id="S2", name="S2 Alarm")
        client.post("/v1/alarms/upsert", json={"alarms": [s1, s2]})

        r = client.get("/v1/alarms/query?site_id=S1")
        alarms = r.json()["alarms"]
        assert len(alarms) == 1
        assert alarms[0]["site_id"] == "S1"

    def test_query_with_limit(self, client):
        alarms = [
            _make_alarm_payload(site_id="SITE01", name=f"A-{i}")
            for i in range(10)
        ]
        client.post("/v1/alarms/upsert", json={"alarms": alarms})

        r = client.get("/v1/alarms/query?limit=5")
        assert len(r.json()["alarms"]) == 5

    def test_query_empty_alarms(self, client):
        r = client.get("/v1/alarms/query")
        assert r.status_code == 200
        assert r.json()["alarms"] == []


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


class TestSyncE2E:
    def test_post_batch_returns_applied(self, client):
        event = _make_event({"entity_hash": hashlib.sha256(b"batch-applied").hexdigest()})
        payload = {
            "idempotency_key": str(uuid4()),
            "events": [dict(event)],
        }
        r = client.post("/v1/sync/batches", json=payload)
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 1
        assert results[0]["status"] == "applied"

    def test_duplicate_event_returns_duplicate(self, client):
        event_id = str(uuid4())
        event = _make_event({"event_id": event_id,
                             "entity_hash": hashlib.sha256(b"dup-test").hexdigest()})
        payload = {
            "idempotency_key": str(uuid4()),
            "events": [dict(event)],
        }

        r1 = client.post("/v1/sync/batches", json=payload)
        assert r1.json()["results"][0]["status"] == "applied"

        r2 = client.post("/v1/sync/batches", json=payload)
        assert r2.json()["results"][0]["status"] == "duplicate"

    def test_mixed_batch_new_and_duplicate(self, client):
        evt_a = _make_event({"event_id": str(uuid4()),
                             "entity_hash": hashlib.sha256(b"mixed-A").hexdigest()})
        evt_b = _make_event({"event_id": str(uuid4()),
                             "entity_hash": hashlib.sha256(b"mixed-B").hexdigest()})
        evt_c = _make_event({"event_id": str(uuid4()),
                             "entity_hash": hashlib.sha256(b"mixed-C").hexdigest()})

        # First batch: A, B
        r1 = client.post("/v1/sync/batches", json={
            "idempotency_key": str(uuid4()),
            "events": [evt_a, evt_b],
        })
        statuses = [r["status"] for r in r1.json()["results"]]
        assert statuses == ["applied", "applied"]

        # Second batch: B, C
        r2 = client.post("/v1/sync/batches", json={
            "idempotency_key": str(uuid4()),
            "events": [evt_b, evt_c],
        })
        results = r2.json()["results"]
        status_by_event = {r["event_id"]: r["status"] for r in results}
        assert status_by_event[evt_b["event_id"]] == "duplicate"
        assert status_by_event[evt_c["event_id"]] == "applied"

    def test_sync_status_reports_counts(self, client, db_session):
        try:
            from alarm_app.db.models import SyncOutboxEvent
        except ImportError:
            from db.models import SyncOutboxEvent

        # Seed pending + synced outbox events via direct session
        db_session.add(SyncOutboxEvent(
            event_id=str(uuid4()),
            origin_device_id="dev-1",
            entity_type="alarm_record",
            entity_local_id="1",
            op="upsert",
            entity_hash="hash-pending",
            payload_json="{}",
            status="pending",
        ))
        db_session.add(SyncOutboxEvent(
            event_id=str(uuid4()),
            origin_device_id="dev-1",
            entity_type="alarm_record",
            entity_local_id="2",
            op="upsert",
            entity_hash="hash-synced",
            payload_json="{}",
            status="synced",
        ))
        db_session.commit()

        r = client.get("/v1/sync/status")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2
        assert data["pending"] >= 1
        assert data["synced"] >= 1


# ---------------------------------------------------------------------------
# PM
# ---------------------------------------------------------------------------


class TestPME2E:
    def test_get_nonexistent_run_returns_404(self, client):
        r = client.get("/v1/pm/runs/99999")
        assert r.status_code == 404

    def test_get_existing_run_with_rule_results(self, db_session, client):
        # -- Arrange: seed BDTTest + PMValidationRun + PMRuleResult via repos --

        try:
            from alarm_app.db.repos.bdt_repo import save_bdt_test
        except ImportError:
            from db.repos.bdt_repo import save_bdt_test

        try:
            from alarm_app.db.repos.pm_repo import (
                get_or_create_rule_catalog,
                save_validation_run,
            )
        except ImportError:
            from db.repos.pm_repo import (
                get_or_create_rule_catalog,
                save_validation_run,
            )

        bdt_dict = {
            "site_code": "TEST01",
            "test_date": date(2026, 3, 15),
            "battery_brand": "Sonnenschein",
            "battery_ah": 100.0,
            "battery_voltage": 12.0,
            "num_batteries": 24,
            "num_strings": 2,
            "start_voltage": 54.0,
            "end_voltage": 46.5,
            "site_name": "Test Site A",
        }
        bdt = save_bdt_test(db_session, bdt_dict)
        db_session.commit()

        catalog = get_or_create_rule_catalog(db_session)

        rules = [
            {"rule_code": "R1", "verdict": "Accepted", "detail": "Photo count OK"},
            {"rule_code": "R2", "verdict": "Rejected",
             "detail": "Power alarm duration mismatch"},
        ]
        run = save_validation_run(
            db_session,
            bdt_test_id=bdt.id,
            alarm_input_sha256=hashlib.sha256(b"test-alarms").hexdigest(),
            validator_code_ref="alarm_app.bdt.validator",
            overall_verdict="Rejected",
            rule_results=rules,
        )
        db_session.commit()
        run_id = run.id

        # -- Act: query the run via API --

        r = client.get(f"/v1/pm/runs/{run_id}")
        assert r.status_code == 200
        data = r.json()

        # -- Assert --

        assert data["run_id"] == run_id
        assert data["bdt_test_id"] == bdt.id
        assert data["overall_verdict"] == "Rejected"
        assert data["alarm_input_sha256"] == hashlib.sha256(b"test-alarms").hexdigest()
        assert data["run_at"] is not None

        assert len(data["rules"]) == 2
        rule_by_id = {rr["rule_id"]: rr for rr in data["rules"]}
        assert rule_by_id[catalog["R1"]]["verdict"] == "Accepted"
        assert rule_by_id[catalog["R2"]]["verdict"] == "Rejected"


# ---------------------------------------------------------------------------
# Full workflow
# ---------------------------------------------------------------------------


class TestFullWorkflowE2E:
    def test_upsert_alarms_through_sync_to_query(self, client, db_session):
        """Simulate full pipeline: upsert alarms via API, verify in DB, query back."""
        # -- Arrange: upsert alarms through the API --
        alarms = [
            _make_alarm_payload(site_id="WF01", name="Workflow Alarm A"),
            _make_alarm_payload(site_id="WF01", name="Workflow Alarm B"),
        ]
        r = client.post("/v1/alarms/upsert", json={"alarms": alarms})
        assert r.status_code == 200
        assert r.json()["inserted"] == 2

        # -- Verify in DB directly --
        try:
            from alarm_app.db.models import AlarmRecord
        except ImportError:
            from db.models import AlarmRecord

        rows = db_session.query(AlarmRecord).filter_by(site_id="WF01").all()
        assert len(rows) == 2

        # -- Query through API --
        qr = client.get("/v1/alarms/query?site_id=WF01")
        assert len(qr.json()["alarms"]) == 2

    def test_seed_bdt_and_query_pm_run(self, db_session, client):
        """Seed BDT data through repo functions, then verify API returns it."""
        try:
            from alarm_app.db.repos.bdt_repo import save_bdt_test
        except ImportError:
            from db.repos.bdt_repo import save_bdt_test

        try:
            from alarm_app.db.repos.pm_repo import (
                get_or_create_rule_catalog,
                save_validation_run,
            )
        except ImportError:
            from db.repos.pm_repo import (
                get_or_create_rule_catalog,
                save_validation_run,
            )

        # -- Seed --
        bdt_dict = {
            "site_code": "WFPM01",
            "test_date": date(2026, 4, 1),
            "battery_brand": "FIAMM",
            "battery_ah": 120.0,
            "battery_voltage": 12.0,
            "num_batteries": 24,
            "num_strings": 2,
            "start_voltage": 52.0,
            "end_voltage": 45.0,
            "site_name": "Workflow PM Site",
        }
        bdt = save_bdt_test(db_session, bdt_dict)
        db_session.commit()

        get_or_create_rule_catalog(db_session)
        rules = [
            {"rule_code": code, "verdict": "Accepted", "detail": f"{code} passed"}
            for code in ("R1", "R2", "R3")
        ]
        run = save_validation_run(
            db_session,
            bdt_test_id=bdt.id,
            alarm_input_sha256=hashlib.sha256(b"wf-pm").hexdigest(),
            validator_code_ref="alarm_app.bdt.validator",
            overall_verdict="Accepted",
            rule_results=rules,
        )
        db_session.commit()

        # -- Query through API --
        r = client.get(f"/v1/pm/runs/{run.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["overall_verdict"] == "Accepted"
        assert len(data["rules"]) == 3
