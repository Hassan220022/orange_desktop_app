import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import alarm_app.llm_tools.openrouter_agent as openrouter_agent_mod
from alarm_app.llm_tools.mcp_server import AlarmViewerMcpServer
from alarm_app.llm_tools.openrouter_agent import OpenRouterAgent
from alarm_app.llm_tools.openrouter_agent import OpenRouterToolSupportError
from alarm_app.llm_tools.openrouter_models import (
    FREE_MODELS_ROUTER,
    fetch_free_tool_models,
    is_free_model_id,
    normalize_free_model_id,
)
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


def test_openrouter_model_helpers_enforce_free_models():
    assert is_free_model_id(FREE_MODELS_ROUTER)
    assert is_free_model_id("provider/model:free")
    assert normalize_free_model_id("openai/gpt-4o-mini") == FREE_MODELS_ROUTER
    assert normalize_free_model_id("provider/model:free") == "provider/model:free"


def test_fetch_free_tool_models_filters_api_response(monkeypatch):
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({
                "data": [
                    {
                        "id": "free/tool:free",
                        "name": "Free Tool",
                        "pricing": {"prompt": "0", "completion": "0"},
                        "supported_parameters": ["tools"],
                    },
                    {
                        "id": "free/no-tools:free",
                        "name": "Free No Tools",
                        "pricing": {"prompt": "0", "completion": "0"},
                        "supported_parameters": [],
                    },
                    {
                        "id": "paid/tool",
                        "name": "Paid Tool",
                        "pricing": {"prompt": "0.1", "completion": "0"},
                        "supported_parameters": ["tools"],
                    },
                ]
            }).encode("utf-8")

    monkeypatch.setattr("alarm_app.llm_tools.openrouter_models.urllib.request.urlopen", lambda req, timeout: _Response())

    options = fetch_free_tool_models()
    ids = {option.id for option in options}

    assert FREE_MODELS_ROUTER in ids
    assert "free/tool:free" in ids
    assert "free/no-tools:free" not in ids
    assert "paid/tool" not in ids


def test_tool_definitions_are_available_for_mcp_and_openrouter():
    mcp_names = {tool["name"] for tool in tool_definitions_for_mcp()}
    openrouter_names = {tool["function"]["name"] for tool in tool_definitions_for_openrouter()}

    assert "query_alarms" in mcp_names
    assert "get_site_dossier" in mcp_names
    assert "generate_graph" in mcp_names
    assert "export_report" in openrouter_names
    assert mcp_names == openrouter_names


def test_export_report_schema_includes_chat_uploaded_report_types():
    tools = {tool["name"]: tool for tool in tool_definitions_for_mcp()}
    schema = tools["export_report"]["inputSchema"]

    assert "source_file_path" in schema["properties"]
    assert "site_alarm_report" in schema["properties"]["report_type"]["enum"]
    assert "accepted_pm_report" in schema["properties"]["report_type"]["enum"]
    assert "bdt_export" in schema["properties"]["report_type"]["enum"]


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


def test_export_site_alarm_report_uses_uploaded_site_list(tmp_path, monkeypatch):
    source = tmp_path / "vip.csv"
    source.write_text("Site Code\nAAA001\n", encoding="utf-8")
    service = LocalDataService(export_dir=tmp_path / "exports")

    monkeypatch.setattr(
        service,
        "_alarm_reference_df",
        lambda: pd.DataFrame({"site_id": ["AAA001"]}),
    )
    monkeypatch.setattr(
        service,
        "_alarm_rows_for_sites",
        lambda site_keys, date_from=None, date_to=None: pd.DataFrame([
            {
                "site_id": "AAA001",
                "alarm_category": "Power",
                "occurred_on": "2026-04-01 10:00:00",
                "cleared_on": "2026-04-01 11:00:00",
            },
            {
                "site_id": "AAA001",
                "alarm_category": "Down",
                "occurred_on": "2026-04-01 10:30:00",
                "cleared_on": "2026-04-01 10:45:00",
            },
        ]),
    )

    result = service.export_report(
        report_type="site_alarm_report",
        source_file_path=str(source),
        format="csv",
        name="vip_report",
    )

    assert result["rows"] == 1
    assert result["site_count"] == 1
    assert Path(result["path"]).exists()
    exported = pd.read_csv(result["path"])
    assert exported.loc[0, "Alarm Match Status"] == "Power and Down found"


def test_export_accepted_pm_report_uses_uploaded_pm_list(tmp_path, monkeypatch):
    source = tmp_path / "accepted_pm.csv"
    source.write_text("Site Code,Actual Done Date,Status\nAAA001,2026-04-01,Accepted\n", encoding="utf-8")
    service = LocalDataService(export_dir=tmp_path / "exports")

    bdt_data = SimpleNamespace(
        test_date="2026-04-01",
        time_in="10:00",
        time_out="11:00",
        battery_ah=100,
        battery_voltage=48,
        num_strings=1,
        start_voltage=48,
        start_ampere=10,
        battery_brand="Lithium",
        discharge_minutes=60,
    )
    result_obj = SimpleNamespace(
        filename="AAA001.xlsx",
        site_code="AAA001",
        test_date="2026-04-01",
        overall="Accepted",
        bdt_data=bdt_data,
        rules=[],
    )

    monkeypatch.setattr(
        service,
        "_alarm_reference_df",
        lambda: pd.DataFrame({"site_id": ["AAA001"]}),
    )
    monkeypatch.setattr(
        service,
        "_alarm_rows_for_pm_sheet",
        lambda pm_df, site_col, date_col: pd.DataFrame([
            {
                "site_id": "AAA001",
                "alarm_category": "Power",
                "occurred_on": "2026-04-01 09:55:00",
                "cleared_on": "2026-04-01 11:05:00",
            },
            {
                "site_id": "AAA001",
                "alarm_category": "Down",
                "occurred_on": "2026-04-01 10:30:00",
                "cleared_on": "2026-04-01 10:40:00",
            },
        ]),
    )
    monkeypatch.setattr(service, "_load_validation_results", lambda site_keys=None: [result_obj])

    result = service.export_report(
        report_type="accepted_pm_report",
        source_file_path=str(source),
        format="xlsx",
        name="accepted_pm",
    )

    assert result["rows"] == 1
    assert result["bdt_results"] == 1
    assert Path(result["path"]).exists()


def test_get_site_dossier_exports_full_site_workbook(tmp_path, monkeypatch):
    service = LocalDataService(export_dir=tmp_path / "exports")
    alarm_df = pd.DataFrame([
        {
            "site_id": "AAA001",
            "alarm_category": "Power",
            "occurred_on": "2026-04-01 10:00:00",
            "cleared_on": "2026-04-01 11:00:00",
        },
        {
            "site_id": "AAA001",
            "alarm_category": "Down",
            "occurred_on": "2026-04-01 10:30:00",
            "cleared_on": "2026-04-01 10:40:00",
        },
    ])
    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None: alarm_df)
    monkeypatch.setattr(
        service,
        "query_bdt_results",
        lambda **kwargs: {
            "total": 1,
            "rows": [{"validation_run_id": 7, "site_code": "AAA001", "overall_verdict": "Rejected"}],
        },
    )
    monkeypatch.setattr(
        service,
        "get_bdt_detail",
        lambda **kwargs: {
            "validation_run_id": 7,
            "bdt": {
                "site_code": "AAA001",
                "test_date": "2026-04-01",
                "discharge_readings": [["10 Mins", 48.0, 20.0]],
            },
            "rules": [{"rule_code": "R3", "verdict": "Rejected", "detail": "Mismatch"}],
            "photos": [{"slot_category": "rectifier", "sha256": "abc"}],
        },
    )

    result = service.get_site_dossier(site_code="AAA001")

    assert result["alarm_total"] == 2
    assert result["bdt_total"] == 1
    assert result["alarm_stats"]["by_category"] == {"Power": 1, "Down": 1}
    assert Path(result["export_path"]).exists()


def test_generate_graph_writes_png_from_alarm_data(tmp_path, monkeypatch):
    service = LocalDataService(export_dir=tmp_path / "exports")
    alarm_df = pd.DataFrame([
        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-01"},
        {"site_id": "AAA001", "alarm_category": "Down", "occurred_on": "2026-04-02"},
        {"site_id": "AAA001", "alarm_category": "Power", "occurred_on": "2026-04-03"},
    ])
    monkeypatch.setattr(service, "_alarm_rows_for_sites", lambda site_keys, date_from=None, date_to=None: alarm_df)

    result = service.generate_graph(graph_type="alarm_category_counts", site_code="AAA001")

    assert result["points"] == 2
    assert Path(result["path"]).exists()
    assert Path(result["path"]).suffix == ".png"


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
    agent._complete = lambda messages, tools, model=None: responses.pop(0)

    assert agent.ask("what data exists?") == "SQLite exists."


def test_openrouter_agent_emits_tool_events_for_ui_rendering():
    service = SimpleNamespace(alarm_stats=lambda: {"total": 5, "power": 2})
    agent = OpenRouterAgent(api_key="test", service=service)
    events = []
    responses = [
        {
            "tool_calls": [
                {
                    "id": "call_stats",
                    "function": {
                        "name": "alarm_stats",
                        "arguments": "{}",
                    },
                }
            ],
            "content": None,
        },
        {"content": "There are 5 alarms."},
    ]
    agent._complete = lambda messages, tools, model=None: responses.pop(0)

    answer = agent.ask("stats?", on_tool_event=events.append)

    assert answer == "There are 5 alarms."
    assert events == [
        {
            "status": "running",
            "tool_call_id": "call_stats",
            "name": "alarm_stats",
            "args": {},
        },
        {
            "status": "complete",
            "tool_call_id": "call_stats",
            "name": "alarm_stats",
            "args": {},
            "result": {"total": 5, "power": 2},
        },
    ]


def test_openrouter_agent_retries_tool_capable_fallback_model():
    service = SimpleNamespace(list_data_sources=lambda: {"ok": True})
    agent = OpenRouterAgent(api_key="test", model="provider/model:free", service=service)
    models: list[str] = []

    def _complete(messages, tools, model=None):
        models.append(model)
        if model == "provider/model:free":
            raise OpenRouterToolSupportError("No endpoints found that support tool use")
        return {"content": "fallback worked"}

    agent._complete = _complete

    assert agent.ask("sources?") == "fallback worked"
    assert models == ["provider/model:free", FREE_MODELS_ROUTER]


def test_openrouter_agent_main_loads_api_key_and_model_from_dotenv(tmp_path, monkeypatch, capsys):
    (tmp_path / ".env").write_text(
        "OPENROUTER_API_KEY=dotenv-key\nOPENROUTER_MODEL=dotenv-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    captured: dict[str, str] = {}

    class _Agent:
        def __init__(self, *, api_key: str, model: str):
            captured["api_key"] = api_key
            captured["model"] = model

        def ask(self, prompt: str) -> str:
            captured["prompt"] = prompt
            return "answer-from-dotenv"

    monkeypatch.setattr(openrouter_agent_mod, "OpenRouterAgent", _Agent)

    rc = openrouter_agent_mod.main(["How", "many", "alarms?"])
    output = capsys.readouterr().out.strip()

    assert rc == 0
    assert output == "answer-from-dotenv"
    assert captured == {
        "api_key": "dotenv-key",
        "model": "dotenv-model",
        "prompt": "How many alarms?",
    }
