import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import alarm_app.ui.panels.chat_panel as chat_panel_mod
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QLabel, QTableWidget
from alarm_app.styles import STYLE_DARK, STYLE_LIGHT
from alarm_app.ui.panels.chat_panel import (
    ChatPanel,
    _alarm_row_columns,
    _json_output_text,
    _normalize_message_text,
    _output_paths,
    _parse_markdown_blocks,
    _photo_group_summary,
    _rows_preview_limit,
    _set_combo_text,
)

_qt_app = None


def _ensure_qapp():
    global _qt_app
    _qt_app = QApplication.instance() or QApplication([])
    return _qt_app


def _qss_block(style: str, selector: str) -> str:
    start = style.index(selector)
    open_brace = style.index("{", start)
    close_brace = style.index("}", open_brace)
    return style[open_brace + 1:close_brace]


def test_assistant_chip_button_metrics_match_themes():
    dark_block = _qss_block(STYLE_DARK, "QPushButton#assistant_chip")
    light_block = _qss_block(STYLE_LIGHT, "QPushButton#assistant_chip")

    for prop in ("padding: 5px 10px", "min-height: 28px", "font-size: 11px", "border-radius: 6px"):
        assert prop in dark_block
        assert prop in light_block


def test_assistant_quick_actions_are_transparent_in_both_themes():
    dark_block = _qss_block(STYLE_DARK, "QFrame#assistant_quick_actions")
    light_block = _qss_block(STYLE_LIGHT, "QFrame#assistant_quick_actions")

    for prop in ("background: transparent", "border: none"):
        assert prop in dark_block
        assert prop in light_block


def test_header_assistant_button_metrics_match_themes():
    dark_block = _qss_block(STYLE_DARK, "QPushButton#btn_assistant")
    light_block = _qss_block(STYLE_LIGHT, "QPushButton#btn_assistant")

    for prop in ("padding: 3px 8px", "min-height: 26px", "font-size: 11px", "border-radius: 5px"):
        assert prop in dark_block
        assert prop in light_block


def test_parse_markdown_blocks_recognizes_lists_and_paragraphs():
    text = (
        "Summary for site 3022CA\n"
        "- 55 alarms\n"
        "- 2 BDT validations\n"
        "\n"
        "1. Power alarms\n"
        "2. Down alarms\n"
    )

    blocks = _parse_markdown_blocks(text)

    assert blocks[0] == ("p", "Summary for site 3022CA")
    assert blocks[1] == ("ul", ["55 alarms", "2 BDT validations"])
    assert blocks[2] == ("ol", ["Power alarms", "Down alarms"])


def test_parse_markdown_blocks_recognizes_unicode_bullets():
    text = "• first\n• second"
    blocks = _parse_markdown_blocks(text)
    assert blocks == [("ul", ["first", "second"])]


def test_parse_markdown_blocks_recognizes_code_fences():
    text = "```json\n{\"total\": 10}\n```"
    blocks = _parse_markdown_blocks(text)
    assert blocks == [("code", "{\"total\": 10}")]


def test_chat_request_thread_passes_default_llm_response_log_path(monkeypatch, tmp_path):
    log_path = tmp_path / "llm_responses.jsonl"
    captured = {}

    class _Agent:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def ask(self, *args, **kwargs):
            return "answer"

    monkeypatch.setattr(chat_panel_mod, "OpenRouterAgent", _Agent)
    monkeypatch.setattr(chat_panel_mod, "default_llm_response_log_path", lambda: log_path)

    thread = chat_panel_mod.ChatRequestThread(
        prompt="hello",
        model="model-id",
        api_key="key",
    )
    thread.run()

    assert captured["response_log_path"] == log_path


def test_normalize_message_text_pretty_prints_json():
    raw = '{"total":10,"power":3}'
    normalized = _normalize_message_text(raw)
    assert normalized == '{\n  "total": 10,\n  "power": 3\n}'


def test_parse_markdown_blocks_recognizes_key_value_sequences():
    text = "Start voltage: 54.6 V\nEnd voltage: 45.1 V"
    blocks = _parse_markdown_blocks(text)
    assert blocks == [("kv", [("Start voltage", "54.6 V"), ("End voltage", "45.1 V")])]


def test_parse_markdown_blocks_keeps_single_colon_sentence_as_paragraph():
    text = "This is normal text: not metadata"
    blocks = _parse_markdown_blocks(text)
    assert blocks == [("p", "This is normal text: not metadata")]


def test_parse_markdown_blocks_splits_heading_from_key_value_group():
    text = "Summary:\nTotal alarms: 10\nPower alarms: 3"
    blocks = _parse_markdown_blocks(text)
    assert blocks == [
        ("p", "Summary:"),
        ("kv", [("Total alarms", "10"), ("Power alarms", "3")]),
    ]


def test_tool_title_maps_known_tools():
    assert ChatPanel._tool_title("alarm_stats") == "Alarm Statistics"
    assert ChatPanel._tool_title("query_backup_times") == "Backup Time Sites"
    assert ChatPanel._tool_title("query_bdt_results") == "BDT Results"


def test_format_tool_value_is_human_readable():
    assert ChatPanel._format_tool_value(2324839) == "2,324,839"
    assert ChatPanel._format_tool_value(12.345) == "12.35"
    assert ChatPanel._format_tool_value(None) == "--"
    assert ChatPanel._format_tool_value({"rows": [{"site": "4468CA"}], "total": 1}) == "1 row"
    assert ChatPanel._format_tool_value([{"site": "4468CA"}]) == "1 item"


def test_full_context_tool_result_uses_structured_sections_not_raw_json():
    _ensure_qapp()
    panel = ChatPanel.__new__(ChatPanel)
    result = {
        "site_id": "4468CA",
        "site_code": "4468CA",
        "network_summary": {
            "rows": [{"site_id": "4468CA", "site_name": "DERABOSEFEEN", "backup_status": "Bad"}],
            "returned": 1,
            "total": 1,
        },
        "alarm_stats": {"total": 15, "power": 11, "down": 1, "door": 3},
        "alarm_rows": {
            "rows": [{"site_id": "4468CA", "alarm_name": "Main Power Cut off", "occurred_on": "2026-03-31"}],
            "returned": 1,
            "total": 1,
        },
        "bdt_summary": {
            "rows": [{"site_code": "4468CA", "backup_status": "Bad"}],
            "returned": 1,
            "total": 1,
        },
        "validation_runs": {
            "rows": [{"validation_run_id": 13061, "bdt_test_id": 3552, "site_code": "4468CA"}],
            "returned": 1,
            "total": 1,
        },
        "photos": {"rows": [], "returned": 0, "total": 0},
        "review_events": {"rows": [], "returned": 0, "total": 0},
    }

    widget = ChatPanel._tool_result_widget(panel, "get_site_full_context", result)

    labels = [label.text() for label in widget.findChildren(QLabel)]
    assert "NETWORK SUMMARY" in labels
    assert "ALARM PREVIEW" in labels
    assert "BDT SUMMARY" in labels
    assert "VALIDATION RUNS" in labels
    assert not any('"rows"' in text for text in labels)
    assert len(widget.findChildren(QTableWidget)) >= 3


def test_photo_group_summary_counts_categories():
    summary = _photo_group_summary([
        {"slot_category": "rectifier"},
        {"slot_category": "batteries"},
        {"slot_category": "batteries"},
        {"slot_category": ""},
    ])

    assert summary == "batteries: 2, other: 1, rectifier: 1"


def test_output_paths_extracts_shareable_files_without_duplicates():
    paths = _output_paths({
        "path": "/tmp/chart.png",
        "export_path": "/tmp/report.xlsx",
        "rows": [{"local_path": "/tmp/photo.jpg"}, {"local_path": "/tmp/photo.jpg"}],
    })

    assert paths == ["/tmp/chart.png", "/tmp/report.xlsx", "/tmp/photo.jpg"]


def test_json_output_text_is_copyable_pretty_json():
    text = _json_output_text({"path": "/tmp/report.xlsx", "rows": [{"site": "0600UP"}]})

    assert '"path": "/tmp/report.xlsx"' in text
    assert '"site": "0600UP"' in text


def test_build_system_context_includes_uploaded_files_for_tools():
    panel = ChatPanel.__new__(ChatPanel)
    panel._uploaded_files = [{"name": "vip.csv", "path": "/tmp/vip.csv"}]

    ctx = ChatPanel._build_system_context(panel)

    assert "Uploaded local files available to tools:" in ctx
    assert "vip.csv -> /tmp/vip.csv" in ctx
    assert "source_file_path" in ctx
    assert "site_alarm_report" in ctx
    assert "Do not repeat full row tables" in ctx
    assert "Use query_backup_times" in ctx


def test_build_system_context_excludes_upload_section_when_no_files():
    panel = ChatPanel.__new__(ChatPanel)
    panel._uploaded_files = []

    ctx = ChatPanel._build_system_context(panel)

    assert "Uploaded local files" not in ctx
    assert "Do not repeat full row tables" in ctx
    assert "Use query_backup_times" in ctx


def test_chat_state_round_trips_summary_messages_and_uploads():
    panel = ChatPanel.__new__(ChatPanel)
    panel._conversation_summary = "Summary text"
    panel._messages = [{"role": "user", "content": "hello", "timestamp": "t"}]
    panel._uploaded_files = [{"name": "vip.csv", "path": "/tmp/vip.csv", "kind": "uploaded_list"}]
    panel._saved_sessions = []
    panel._model = "openrouter/model-a"

    state = ChatPanel.chat_state(panel)

    restored = ChatPanel.__new__(ChatPanel)
    restored._messages = []
    restored._conversation_summary = ""
    restored._uploaded_files = []
    restored._saved_sessions = []
    restored._model = "openrouter/model-b"
    restored.set_model = lambda model: setattr(restored, "_model", model)
    ChatPanel.restore_chat_state(restored, state)

    assert restored._conversation_summary == "Summary text"
    assert restored._messages == [{"role": "user", "content": "hello", "timestamp": "t"}]
    assert restored._uploaded_files == [{"name": "vip.csv", "path": "/tmp/vip.csv", "kind": "uploaded_list"}]
    assert restored._model == "openrouter/model-a"


def test_restore_chat_state_preserves_all_message_turns():
    restored = ChatPanel.__new__(ChatPanel)
    restored._messages = []
    restored._conversation_summary = ""
    restored._uploaded_files = []
    restored._saved_sessions = []

    ChatPanel.restore_chat_state(restored, {
        "messages": [
            {"role": "user" if idx % 2 == 0 else "assistant", "content": f"turn {idx}", "timestamp": ""}
            for idx in range(12)
        ],
    })

    assert len(restored._messages) == 12
    assert restored._messages[0]["content"] == "turn 0"


def test_restore_session_applies_saved_model():
    class _Status:
        def __init__(self):
            self.messages = []

        def showMessage(self, message, timeout=0):
            self.messages.append((message, timeout))

    class _Layout:
        def count(self):
            return 1

    panel = ChatPanel.__new__(ChatPanel)
    panel._thread = None
    panel._summary_thread = None
    panel._saved_sessions = []
    panel._messages = []
    panel._conversation_summary = ""
    panel._uploaded_files = []
    panel._tool_cards = {}
    panel._pending_tool_events = {}
    panel._pending_tool_order = []
    panel._pending_tool_seq = 0
    panel._history_layout = _Layout()
    panel._viewer = type("Viewer", (), {"_sbar": _Status()})()
    panel._model = "openrouter/current-model"
    panel._rehydrate_history = lambda: None
    panel.set_model = lambda model: setattr(panel, "_model", model)

    ChatPanel._restore_session(panel, {
        "model": "openrouter/restored-model",
        "messages": [{"role": "user", "content": "old question", "timestamp": ""}],
    })

    assert panel._model == "openrouter/restored-model"
    assert panel._messages == [{"role": "user", "content": "old question", "timestamp": ""}]



def test_chat_state_round_trips_saved_sessions():
    panel = ChatPanel.__new__(ChatPanel)
    panel._conversation_summary = ""
    panel._messages = [{"role": "user", "content": "hi", "timestamp": ""}]
    panel._uploaded_files = []
    panel._saved_sessions = [
        {"id": "abc", "title": "old chat", "messages": [{"role": "user", "content": "bye", "timestamp": ""}], "summary": "old summary"},
    ]
    panel._model = "model"

    state = ChatPanel.chat_state(panel)
    assert len(state["saved_sessions"]) == 1

    restored = ChatPanel.__new__(ChatPanel)
    restored._messages = []
    restored._conversation_summary = ""
    restored._uploaded_files = []
    restored._saved_sessions = []
    restored.set_model = lambda model: setattr(restored, "_model", model)
    ChatPanel.restore_chat_state(restored, state)
    assert len(restored._saved_sessions) == 1
    assert restored._saved_sessions[0]["title"] == "old chat"




def test_chat_error_preserves_failed_user_turn_with_assistant_error_turn():
    panel = ChatPanel.__new__(ChatPanel)
    panel._messages = [{"role": "user", "content": "original question", "timestamp": ""}]
    panel._pending_tool_events = {"call": {}}
    panel._pending_tool_order = ["call"]
    panel._append_message = lambda *args, **kwargs: None
    panel._schedule_scroll_to_bottom = lambda: None
    panel._viewer = type("Viewer", (), {"_sbar": type("Sbar", (), {"showMessage": lambda *args, **kwargs: None})()})()

    ChatPanel._on_error(panel, "timeout")

    assert panel._messages[0]["content"] == "original question"
    assert panel._messages[1]["role"] == "assistant"
    assert panel._pending_tool_events == {}
    assert panel._pending_tool_order == []


def test_restore_chat_state_rehydrates_after_uploads_are_loaded():
    panel = ChatPanel.__new__(ChatPanel)
    panel._messages = []
    panel._conversation_summary = ""
    panel._uploaded_files = []
    panel._saved_sessions = []
    calls = []
    panel._rehydrate_history = lambda: calls.append(list(panel._uploaded_files))

    ChatPanel.restore_chat_state(panel, {
        "uploaded_files": [{"name": "vip.csv", "path": "/tmp/vip.csv", "kind": "uploaded_list"}],
    })

    assert calls == [[{"name": "vip.csv", "path": "/tmp/vip.csv", "kind": "uploaded_list"}]]




def test_refresh_settings_ignores_api_banner_deleted_during_history_rehydrate(monkeypatch):
    app = _ensure_qapp()
    monkeypatch.setattr(ChatPanel, "refresh_free_models", lambda self: None)

    class _Viewer:
        def __init__(self):
            self.api_key = ""

        def openrouter_api_key(self):
            return self.api_key

    viewer = _Viewer()
    panel = ChatPanel(viewer)
    panel.refresh_settings()
    assert panel._api_banner_widget is not None

    panel._conversation_summary = ""
    panel._uploaded_files = []
    panel._upload_allowlist = {}
    panel._messages = []
    panel._rehydrate_history()
    app.sendPostedEvents(None, QEvent.DeferredDelete)

    viewer.api_key = "openrouter-key"
    panel.refresh_settings()

    assert panel._api_banner_widget is None
    panel.deleteLater()
    app.sendPostedEvents(None, QEvent.DeferredDelete)



def test_show_chat_history_preserves_current_chat_archived_during_restore(monkeypatch):
    class _Signal:
        def __init__(self):
            self.callback = None

        def connect(self, callback):
            self.callback = callback

    class _Dialog:
        def __init__(self, sessions, parent=None):
            self.sessions = list(sessions)
            self.session_selected = _Signal()

        def exec_(self):
            self.session_selected.callback(self.sessions[0])

        def remaining_sessions(self):
            return list(self.sessions)

    monkeypatch.setattr(chat_panel_mod, "ChatHistoryDialog", _Dialog)

    panel = ChatPanel.__new__(ChatPanel)
    panel._saved_sessions = [{"id": "old", "title": "old chat", "messages": []}]
    panel._messages = [{"role": "user", "content": "current question", "timestamp": ""}]
    panel._conversation_summary = ""
    panel._uploaded_files = []
    panel._model = "model"
    panel._restore_session = lambda session: ChatPanel._archive_current_session(panel)

    ChatPanel.show_chat_history(panel)

    titles = [session.get("title") for session in panel._saved_sessions]
    assert "current question" in titles
    assert "old chat" in titles


def test_restore_session_is_blocked_while_summary_thread_runs():
    class _Thread:
        def isRunning(self):
            return True

    class _Status:
        def __init__(self):
            self.messages = []

        def showMessage(self, message, timeout=0):
            self.messages.append((message, timeout))

    panel = ChatPanel.__new__(ChatPanel)
    panel._thread = None
    panel._summary_thread = _Thread()
    panel._viewer = type("Viewer", (), {"_sbar": _Status()})()
    panel._saved_sessions = []
    panel._messages = [{"role": "user", "content": "active question", "timestamp": ""}]
    panel._conversation_summary = "active summary"
    panel._uploaded_files = []

    ChatPanel._restore_session(panel, {"messages": [{"role": "user", "content": "old question"}]})

    assert panel._messages == [{"role": "user", "content": "active question", "timestamp": ""}]
    assert panel._conversation_summary == "active summary"
    assert panel._saved_sessions == []
    assert panel._viewer._sbar.messages == [
        ("Wait for the current chat task to finish before restoring history.", 3500)
    ]



def test_rows_preview_limit_caps_alarm_rows_to_one_hundred():
    assert _rows_preview_limit(250, 10) == 10
    assert _rows_preview_limit(250, 120) == 100
    assert _rows_preview_limit(7, 10) == 7


def test_message_bubble_width_caps_on_small_and_large_panels():
    assert ChatPanel._message_bubble_width(300, "assistant") == 280
    assert ChatPanel._message_bubble_width(2000, "assistant") == 760
    assert ChatPanel._message_bubble_width(1000, "system") == 760


def test_display_graph_type_removes_underscores():
    assert ChatPanel._display_graph_type("alarm_daily_counts") == "Alarm Daily Counts"
    assert ChatPanel._display_graph_type(None) == "--"


def test_graph_preview_width_clamps_to_chat_area():
    panel = ChatPanel.__new__(ChatPanel)
    panel._history_scroll = type("Scroll", (), {"viewport": lambda self: type("Vp", (), {"width": lambda self: 260})()})()

    assert panel._graph_preview_width() == 320


def test_schedule_scroll_to_bottom_triggers_immediate_and_delayed_scroll(monkeypatch):
    panel = ChatPanel.__new__(ChatPanel)
    calls = []

    monkeypatch.setattr("alarm_app.ui.panels.chat_panel.QTimer.singleShot", lambda delay, fn: calls.append(delay))
    panel._scroll_to_bottom = lambda: None

    ChatPanel._schedule_scroll_to_bottom(panel)

    assert calls == [0, 50]


def test_alarm_row_columns_match_alarm_tab_order():
    rows = [{
        "site_id": "AAA001",
        "alarm_name": "Power Loss",
        "alarm_id": "28003",
        "network_type": "4G",
        "vendor": "HUAWEI",
        "occurred_on": "2026-05-03",
        "cleared_on": "2026-05-03",
        "duration": "00:10:00",
        "clearance_status": "Cleared",
        "alarm_source": "NMS",
        "site_down_flag": "No",
        "alarm_category": "Power",
        "file_source": "alarms.csv",
    }]

    assert _alarm_row_columns(rows, "query_alarms") == [
        "site_id",
        "alarm_name",
        "alarm_id",
        "network_type",
        "vendor",
        "occurred_on",
        "cleared_on",
        "duration",
        "clearance_status",
        "alarm_source",
        "site_down_flag",
        "alarm_category",
        "file_source",
    ]


class _FakeCombo:
    def __init__(self, values):
        self.values = list(values)
        self.current_index = 0
        self.blocked = False

    def findText(self, text):
        try:
            return self.values.index(text)
        except ValueError:
            return -1

    def setCurrentIndex(self, index):
        self.current_index = index

    def blockSignals(self, value):
        self.blocked = bool(value)


class _FakeToggle:
    def __init__(self):
        self.checked = None

    def setChecked(self, value):
        self.checked = bool(value)


class _FakeDateEdit:
    def __init__(self):
        self.value = None

    def setDate(self, value):
        self.value = value.toString("yyyy-MM-dd")


class _FakeHeader:
    def __init__(self):
        self.sort = None

    def setSortIndicator(self, section, order):
        self.sort = (section, order)


class _FakeTable:
    def __init__(self, columns):
        self._header = _FakeHeader()
        self.columns = list(columns)

    def horizontalHeader(self):
        return self._header


def test_set_combo_text_selects_matching_value():
    combo = _FakeCombo(["All", "Power", "Down"])

    _set_combo_text(combo, "Down")

    assert combo.current_index == 2
    assert combo.blocked is False


def test_show_alarm_results_in_viewer_applies_exact_alarm_filters():
    panel = ChatPanel.__new__(ChatPanel)
    viewer = type("Viewer", (), {})()
    viewer._workspace = None
    viewer._set_workspace_view = lambda index: setattr(viewer, "_workspace", index)
    viewer._ui = SimpleNamespace(
        edit_site=type("Edit", (), {"setText": lambda self, value: setattr(self, "text", value)})(),
        cb_cat=_FakeCombo(["All", "Power", "Down"]),
        cb_net=_FakeCombo(["All", "4G", "5G"]),
        cb_vnd=_FakeCombo(["All", "HUAWEI", "Nokia"]),
        chk_mindur=_FakeToggle(),
        edit_days=type("Days", (), {"clear": lambda self: setattr(self, "cleared", True)})(),
        chk_date=_FakeToggle(),
        chk_date_range=_FakeToggle(),
        chk_date_days=_FakeToggle(),
        d_from=_FakeDateEdit(),
        d_to=_FakeDateEdit(),
    )
    viewer._both_pd_active = True
    viewer._col_filters = {"alarm_name": {"Power Loss"}}
    viewer._btn_both = type("Btn", (), {"setStyleSheet": lambda self, value: setattr(self, "style", value)})()
    viewer._page_size = 500
    viewer._page_offset = 99
    viewer._table = _FakeTable(["site_id", "alarm_name", "occurred_on"])
    viewer._current_alarm_columns = lambda: ["site_id", "alarm_name", "occurred_on"]
    calls = {}
    viewer._load_alarm_page = lambda *, offset, status_message=None: calls.update({"offset": offset, "status_message": status_message}) or True
    panel._viewer = viewer

    event = {
        "name": "query_alarms",
        "args": {
            "site_text": "AAA001",
            "category": "Power",
            "network_type": "4G",
            "vendor": "HUAWEI",
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "sort_by": "occurred_on",
            "sort_desc": True,
            "limit": 10,
            "offset": 3,
        },
        "result": {"rows": [{"site_id": "AAA001"}]},
    }

    panel._show_alarm_results_in_viewer(event)

    assert viewer._workspace == 0
    assert viewer._ui.edit_site.text == "AAA001"
    assert viewer._ui.cb_cat.current_index == 1
    assert viewer._ui.cb_net.current_index == 1
    assert viewer._ui.cb_vnd.current_index == 1
    assert viewer._ui.chk_mindur.checked is False
    assert viewer._ui.chk_date.checked is True
    assert viewer._ui.chk_date_range.checked is True
    assert viewer._ui.chk_date_days.checked is False
    assert viewer._ui.d_from.value == "2026-04-01"
    assert viewer._ui.d_to.value == "2026-04-30"
    assert viewer._both_pd_active is False
    assert viewer._col_filters == {}
    # Pagination size is user-controlled; the chat panel must NOT mutate it
    # (it persists to state and the next launch would otherwise show only N rows).
    assert viewer._page_size == 500
    assert viewer._page_offset == 3
    assert viewer._table.horizontalHeader().sort == (2, 1)
    assert calls == {
        "offset": 3,
        "status_message": "Assistant results shown in Alarms",
    }


def test_show_alarm_results_in_viewer_uses_backup_time_site_ids():
    panel = ChatPanel.__new__(ChatPanel)
    viewer = type("Viewer", (), {})()
    viewer._workspace = None
    viewer._set_workspace_view = lambda index: setattr(viewer, "_workspace", index)
    viewer._ui = SimpleNamespace(
        edit_site=type("Edit", (), {"setText": lambda self, value: setattr(self, "text", value)})(),
        cb_cat=_FakeCombo(["All", "Power", "Down"]),
        cb_net=_FakeCombo(["All", "4G", "5G"]),
        cb_vnd=_FakeCombo(["All", "HUAWEI", "Nokia"]),
        chk_mindur=_FakeToggle(),
        edit_days=type("Days", (), {"clear": lambda self: setattr(self, "cleared", True)})(),
        chk_date=_FakeToggle(),
        chk_date_range=_FakeToggle(),
        chk_date_days=_FakeToggle(),
        d_from=_FakeDateEdit(),
        d_to=_FakeDateEdit(),
    )
    viewer._both_pd_active = True
    viewer._col_filters = {"alarm_name": {"Power Loss"}}
    viewer._btn_both = type("Btn", (), {"setStyleSheet": lambda self, value: setattr(self, "style", value)})()
    viewer._page_size = 500
    viewer._page_offset = 99
    viewer._table = _FakeTable(["site_id", "alarm_name", "occurred_on"])
    viewer._current_alarm_columns = lambda: ["site_id", "alarm_name", "occurred_on"]
    calls = {}
    viewer._load_alarm_page = lambda *, offset, status_message=None: calls.update({"offset": offset, "status_message": status_message}) or True
    panel._viewer = viewer

    event = {
        "name": "query_backup_times",
        "args": {
            "site_text": "ignored",
            "category": "Power",
            "network_type": "4G",
            "vendor": "HUAWEI",
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "limit": 2,
        },
        "result": {
            "site_ids": ["AAA001", "BBB002"],
            "row_count": 2,
            "rows": [
                {"site_id": "AAA001", "max_backup_time": "01:05:00"},
                {"site_id": "BBB002", "max_backup_time": "00:55:00"},
            ],
        },
    }

    panel._show_alarm_results_in_viewer(event)

    assert viewer._workspace == 0
    assert viewer._ui.edit_site.text == "AAA001, BBB002"
    assert viewer._ui.cb_cat.current_index == 1
    assert viewer._ui.cb_net.current_index == 1
    assert viewer._ui.cb_vnd.current_index == 1
    assert viewer._ui.chk_mindur.checked is False
    assert viewer._ui.chk_date.checked is True
    assert viewer._ui.chk_date_range.checked is True
    assert viewer._ui.chk_date_days.checked is False
    assert viewer._ui.d_from.value == "2026-04-01"
    assert viewer._ui.d_to.value == "2026-04-30"
    assert viewer._both_pd_active is False
    assert viewer._col_filters == {}
    # Pagination size is user-controlled; chat panel must not mutate it.
    assert viewer._page_size == 500
    assert viewer._page_offset == 0
    assert calls == {
        "offset": 0,
        "status_message": "Assistant results shown in Alarms",
    }


def test_show_alarm_results_in_viewer_does_not_mutate_page_size():
    """Regression: chat panel must NOT overwrite viewer._page_size.

    A query result of (e.g.) 1 row would set _page_size=1, which then
    persisted to ui_state and was restored on every subsequent launch,
    leaving the alarms table showing exactly one row per page even though
    the DuckDB cache had 3M+ rows.
    """
    panel = ChatPanel.__new__(ChatPanel)
    viewer = type("Viewer", (), {})()
    viewer._workspace = None
    viewer._set_workspace_view = lambda index: None
    viewer._ui = SimpleNamespace(
        edit_site=type("Edit", (), {"setText": lambda self, value: None})(),
        cb_cat=_FakeCombo(["All", "Power", "Down"]),
        cb_net=_FakeCombo(["All", "4G", "5G"]),
        cb_vnd=_FakeCombo(["All", "HUAWEI", "Nokia"]),
        chk_mindur=_FakeToggle(),
        edit_days=type("Days", (), {"clear": lambda self: None})(),
        chk_date=_FakeToggle(),
        chk_date_range=_FakeToggle(),
        chk_date_days=_FakeToggle(),
        d_from=_FakeDateEdit(),
        d_to=_FakeDateEdit(),
    )
    viewer._both_pd_active = False
    viewer._col_filters = {}
    viewer._btn_both = type("Btn", (), {"setStyleSheet": lambda self, value: None})()
    viewer._page_size = 500
    viewer._page_offset = 0
    viewer._table = _FakeTable(["site_id", "alarm_name", "occurred_on"])
    viewer._current_alarm_columns = lambda: ["site_id", "alarm_name", "occurred_on"]
    viewer._load_alarm_page = lambda *, offset, status_message=None: True
    panel._viewer = viewer

    # A query that returns only ONE row must not shrink the user's page size.
    event = {
        "name": "query_alarms",
        "args": {"site_text": "AAA001", "limit": 1, "offset": 0},
        "result": {"rows": [{"site_id": "AAA001"}], "row_count": 1},
    }

    panel._show_alarm_results_in_viewer(event)

    assert viewer._page_size == 500, (
        f"chat panel must not overwrite _page_size (got {viewer._page_size!r})"
    )
