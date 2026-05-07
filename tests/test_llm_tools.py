import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

import alarm_app.llm_tools.openrouter_agent as openrouter_agent_mod
from alarm_app.llm_tools.mcp_server import AlarmViewerMcpServer
from alarm_app.llm_tools.openrouter_agent import OpenRouterAgent, OpenRouterToolSupportError, _chat_message
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

    assert "get_current_time" in mcp_names
    assert "get_current_time" in openrouter_names
    assert "query_alarms" in mcp_names
    assert "query_backup_times" in mcp_names
    assert "get_site_dossier" in mcp_names
    assert "generate_graph" in mcp_names
    assert "export_report" in openrouter_names
    assert mcp_names == openrouter_names


def test_get_current_time_tool_returns_host_clock_context():
    service = LocalDataService()

    result = service.get_current_time()

    assert result["local_time"]
    assert result["utc_time"]
    assert result["timezone"]


def test_export_report_schema_includes_chat_uploaded_report_types():
    tools = {tool["name"]: tool for tool in tool_definitions_for_mcp()}
    schema = tools["export_report"]["inputSchema"]

    assert "source_file_path" in schema["properties"]
    assert "site_alarm_report" in schema["properties"]["report_type"]["enum"]
    assert "accepted_pm_report" in schema["properties"]["report_type"]["enum"]
    assert "bdt_export" in schema["properties"]["report_type"]["enum"]


def test_query_alarms_schema_caps_rows_at_one_hundred():
    tools = {tool["name"]: tool for tool in tool_definitions_for_mcp()}

    assert tools["query_alarms"]["inputSchema"]["properties"]["limit"]["maximum"] == 100


def test_query_backup_times_schema_exposes_threshold_and_row_limit():
    tools = {tool["name"]: tool for tool in tool_definitions_for_mcp()}

    assert tools["query_backup_times"]["inputSchema"]["properties"]["min_minutes"]["minimum"] == 0
    assert tools["query_backup_times"]["inputSchema"]["properties"]["limit"]["maximum"] == 500


def test_query_backup_times_filters_and_groups_sites(monkeypatch):
    service = LocalDataService()

    monkeypatch.setattr(
        "alarm_app.llm_tools.service.alarm_store.query_alarms",
        lambda q: pd.DataFrame([
            {
                "site_id": "AAA001",
                "alarm_category": "Power",
                "occurred_on": "2026-04-01 10:00:00",
                "cleared_on": "2026-04-01 11:20:00",
                "network_type": "4G",
                "vendor": "HUAWEI",
            }
        ]),
    )
    monkeypatch.setattr(
        "alarm_app.llm_tools.service.compute_backup_times",
        lambda df: (
            pd.DataFrame([
                {
                    "site_id": "AAA001",
                    "network_type": "4G",
                    "vendor": "HUAWEI",
                    "power_time": "2026-04-01 10:00:00",
                    "power_cleared": "2026-04-01 11:20:00",
                    "down_time": "2026-04-01 11:05:00",
                    "backup_time": "01:05:00",
                },
                {
                    "site_id": "AAA001",
                    "network_type": "4G",
                    "vendor": "HUAWEI",
                    "power_time": "2026-04-01 12:00:00",
                    "power_cleared": "2026-04-01 13:00:00",
                    "down_time": "2026-04-01 12:30:00",
                    "backup_time": "00:30:00",
                },
                {
                    "site_id": "BBB002",
                    "network_type": "5G",
                    "vendor": "Nokia",
                    "power_time": "2026-04-01 10:00:00",
                    "power_cleared": "2026-04-01 11:40:00",
                    "down_time": "2026-04-01 11:10:00",
                    "backup_time": "01:10:00",
                },
            ]),
            "",
        ),
    )

    result = service.query_backup_times(min_minutes=50, limit=100)

    assert result["site_count"] == 2
    assert result["site_ids"] == ["BBB002", "AAA001"]
    assert result["rows"][0]["site_id"] == "BBB002"
    assert result["rows"][1]["site_id"] == "AAA001"
    assert result["rows"][1]["incident_count"] == 1


def test_alarm_duration_chart_uses_total_duration_by_category():
    service = LocalDataService()
    df = pd.DataFrame([
        {"alarm_category": "Power", "_duration_secs": 120},
        {"alarm_category": "Power", "_duration_secs": 180},
        {"alarm_category": "Down", "_duration_secs": 60},
    ])

    labels, values = service._alarm_graph_series(df, "alarm_duration_by_category")

    assert labels == ["Power", "Down"]
    assert values == [5.0, 1.0]


def test_format_chart_label_shortens_full_dates():
    assert LocalDataService._format_chart_label("2026-05-04") == "05-04"
    assert LocalDataService._format_chart_label("2026-05-04 12:30:00") == "05-04"


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


def test_openrouter_agent_injects_runtime_context_message(monkeypatch):
    service = SimpleNamespace(list_data_sources=lambda: {"ok": True})
    agent = OpenRouterAgent(api_key="test", service=service)
    captured = {}
    monkeypatch.setattr(
        openrouter_agent_mod,
        "_runtime_context_message",
        lambda: "Current local machine time: 2026-05-03T12:34:56+03:00",
    )

    def _complete(messages, tools, model=None):
        captured["messages"] = messages
        return {"content": "done"}

    agent._complete = _complete

    assert agent.ask("hello") == "done"
    assert captured["messages"][1] == {
        "role": "system",
        "content": "Current local machine time: 2026-05-03T12:34:56+03:00",
    }


def test_openrouter_agent_assembles_summary_history_and_current_message():
    service = SimpleNamespace(list_data_sources=lambda: {"ok": True})
    agent = OpenRouterAgent(api_key="test", service=service)
    captured = {}

    def _complete(messages, tools, model=None):
        captured["messages"] = messages
        return {"content": "done"}

    agent._complete = _complete

    assert agent.ask(
        "current",
        summary="Earlier summary",
        history=[
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"},
        ],
    ) == "done"
    assert captured["messages"][2] == {
        "role": "system",
        "content": "Conversation summary:\nEarlier summary",
    }
    assert captured["messages"][3:6] == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "current"},
    ]


def test_openrouter_agent_normalizes_history_to_alternating_turns():
    history = OpenRouterAgent._normalized_history([
        {"role": "user", "content": "first"},
        {"role": "user", "content": "duplicate user"},
        {"role": "assistant", "content": "reply"},
        {"role": "assistant", "content": "duplicate assistant"},
        {"role": "user", "content": "next"},
    ])

    assert history == [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": "next"},
    ]


def test_openrouter_agent_summarizes_history_with_existing_summary():
    agent = OpenRouterAgent(api_key="test", service=SimpleNamespace())
    captured = {}

    def _complete(messages, tools, model=None):
        captured["messages"] = messages
        captured["tools"] = tools
        return {"content": "updated summary"}

    agent._complete = _complete

    assert agent.summarize_history(
        [
            {"role": "user", "content": "hello", "timestamp": "2026-05-04T00:00:00Z"},
            {"role": "assistant", "content": "hi", "timestamp": ""},
        ],
        existing_summary="old summary",
    ) == "updated summary"
    assert captured["tools"] == []
    prompt = captured["messages"][1]["content"]
    assert "old summary" in prompt
    assert "User [2026-05-04T00:00:00Z]: hello" in prompt
    assert "Assistant: hi" in prompt


def test_openrouter_complete_omits_tool_choice_when_no_tools(monkeypatch):
    agent = OpenRouterAgent(api_key="test", service=SimpleNamespace())
    captured = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")

    def _urlopen(req, timeout):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr(openrouter_agent_mod.urllib.request, "urlopen", _urlopen)

    assert agent._complete([{"role": "user", "content": "summarize"}], tools=[]) == {"content": "ok"}
    assert "tools" not in captured["payload"]
    assert "tool_choice" not in captured["payload"]


def test_chat_message_includes_role_content_and_timestamp(monkeypatch):
    class _Now:
        @classmethod
        def now(cls, tz=None):
            return cls()

        def isoformat(self, timespec=None):
            return "2026-05-04T00:00:00+00:00"

    monkeypatch.setattr(openrouter_agent_mod, "datetime", _Now)

    assert _chat_message("user", "hello") == {
        "role": "user",
        "content": "hello",
        "timestamp": "2026-05-04T00:00:00+00:00",
    }


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
