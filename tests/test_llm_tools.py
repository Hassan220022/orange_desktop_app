import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from alarm_app.llm_tools.mcp_server import AlarmViewerMcpServer
from alarm_app.llm_tools.openrouter_agent import OpenRouterAgent
from alarm_app.llm_tools.service import LocalDataService, _jsonable, _limit, _safe_export_path
from alarm_app.llm_tools.tools import (
    dispatch_tool,
    tool_definitions_for_mcp,
    tool_definitions_for_openrouter,
)


def test_limit_clamps_to_safe_maximum():
    assert _limit(999_999) == 500
    assert _limit("bad", default=17) == 17


def test_jsonable_converts_pandas_missing_values():
    assert _jsonable(pd.NaT) is None
    assert _jsonable({"when": pd.Timestamp("2026-04-24")}) == {
        "when": "2026-04-24T00:00:00"
    }


def test_safe_export_path_stays_under_export_dir(tmp_path):
    path = _safe_export_path(tmp_path, "../../bad/name", "csv")

    assert path.parent == tmp_path
    assert path.name == "bad_name.csv"


def test_tool_definitions_are_available_for_mcp_and_openrouter():
    mcp_names = {tool["name"] for tool in tool_definitions_for_mcp()}
    openrouter_names = {tool["function"]["name"] for tool in tool_definitions_for_openrouter()}

    assert "query_alarms" in mcp_names
    assert "export_report" in openrouter_names
    assert mcp_names == openrouter_names


def test_mcp_server_lists_and_calls_tools():
    class _Service:
        def list_data_sources(self):
            return {"ok": True}

    server = AlarmViewerMcpServer(service=_Service())

    listed = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert listed["result"]["tools"]

    called = server.handle({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "list_data_sources", "arguments": {}},
    })
    text = called["result"]["content"][0]["text"]
    assert json.loads(text) == {"ok": True}


def test_dispatch_unknown_tool_returns_error():
    assert dispatch_tool(LocalDataService(), "missing_tool") == {
        "error": "unknown tool: missing_tool"
    }


def test_dispatch_tool_returns_structured_tool_errors():
    class _Service:
        def list_data_sources(self):
            raise RuntimeError("duckdb locked")

    assert dispatch_tool(_Service(), "list_data_sources") == {
        "error": "list_data_sources failed: duckdb locked"
    }


def test_export_report_writes_to_configured_directory(tmp_path, monkeypatch):
    service = LocalDataService(export_dir=tmp_path)
    monkeypatch.setattr(
        service,
        "query_bdt_results",
        lambda **kwargs: {"rows": [{"site_code": "AAA001", "overall_verdict": "Accepted"}]},
    )

    result = service.export_report(report_type="bdt_results", format="csv", name="../../report")

    assert result["rows"] == 1
    assert Path(result["path"]).parent == tmp_path
    assert Path(result["path"]).exists()


def test_alarm_source_selection_skips_empty_primary_dict_results(tmp_path, monkeypatch):
    primary = tmp_path / "alarms.duckdb"
    fallback = tmp_path / "alarms.local.duckdb"
    primary.touch()
    fallback.touch()
    service = LocalDataService()
    calls = []

    monkeypatch.setattr("alarm_app.llm_tools.service.state.ALARM_DB_FILE", primary)
    monkeypatch.setattr("alarm_app.llm_tools.service.state.ALARM_DB_FALLBACK_FILE", fallback)

    def _set_alarm_db_file(path):
        calls.append(str(path))

    monkeypatch.setattr("alarm_app.llm_tools.service.alarm_store.set_alarm_db_file", _set_alarm_db_file)
    monkeypatch.setattr("alarm_app.llm_tools.service.alarm_store.ALARM_DB_FILE", primary)

    results = iter([
        {"total": 0},
        {"total": 12},
    ])

    assert service._with_alarm_source(lambda: next(results)) == {"total": 12}
    assert str(primary) in calls
    assert str(fallback) in calls


def test_alarm_source_selection_skips_locked_primary(tmp_path, monkeypatch):
    primary = tmp_path / "alarms.duckdb"
    fallback = tmp_path / "alarms.local.duckdb"
    primary.touch()
    fallback.touch()
    service = LocalDataService()
    current = {"path": primary}
    calls = []

    monkeypatch.setattr("alarm_app.llm_tools.service.state.ALARM_DB_FILE", primary)
    monkeypatch.setattr("alarm_app.llm_tools.service.state.ALARM_DB_FALLBACK_FILE", fallback)
    monkeypatch.setattr("alarm_app.llm_tools.service.alarm_store.ALARM_DB_FILE", primary)

    def _set_alarm_db_file(path):
        current["path"] = path
        calls.append(str(path))

    monkeypatch.setattr("alarm_app.llm_tools.service.alarm_store.set_alarm_db_file", _set_alarm_db_file)

    def _read_current_source():
        if current["path"] == primary:
            raise RuntimeError("primary locked")
        return {"total": 9}

    assert service._with_alarm_source(_read_current_source) == {"total": 9}
    assert str(primary) in calls
    assert str(fallback) in calls


def test_list_data_sources_reports_duckdb_count_errors(tmp_path, monkeypatch):
    primary = tmp_path / "alarms.duckdb"
    primary.touch()
    service = LocalDataService(export_dir=tmp_path / "exports")

    monkeypatch.setattr("alarm_app.llm_tools.service.state.ALARM_DB_FILE", primary)
    monkeypatch.setattr("alarm_app.llm_tools.service.state.ALARM_DB_FALLBACK_FILE", tmp_path / "missing.duckdb")
    monkeypatch.setattr("alarm_app.llm_tools.service.alarm_store.set_alarm_db_file", lambda path: None)
    monkeypatch.setattr(
        "alarm_app.llm_tools.service.alarm_store.count_alarms",
        lambda query: (_ for _ in ()).throw(RuntimeError("locked")),
    )

    sources = service.list_data_sources()

    assert sources["duckdb"][0]["rows"] is None
    assert "locked" in sources["duckdb"][0]["error"]


def test_openrouter_agent_executes_tool_call_then_returns_final_answer():
    service = SimpleNamespace(list_data_sources=lambda: {"sqlite": {"exists": True}})
    agent = OpenRouterAgent(api_key="test", service=service)
    responses = [
        {
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "list_data_sources",
                        "arguments": "{}",
                    },
                }
            ],
            "content": None,
        },
        {"content": "SQLite exists."},
    ]
    agent._complete = lambda messages, tools: responses.pop(0)

    assert agent.ask("what data exists?") == "SQLite exists."
