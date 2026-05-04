import alarm_app.ui.panels.chat_panel as chat_panel_mod
from alarm_app.ui.panels.chat_panel import (
    ChatPanel,
    _alarm_row_columns,
    _json_output_text,
    _normalize_message_text,
    _output_paths,
    _photo_group_summary,
    _parse_markdown_blocks,
    _set_combo_text,
    _rows_preview_limit,
)


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

    state = ChatPanel.chat_state(panel)

    restored = ChatPanel.__new__(ChatPanel)
    restored._messages = []
    restored._conversation_summary = ""
    restored._uploaded_files = []
    restored._saved_sessions = []
    ChatPanel.restore_chat_state(restored, state)

    assert restored._conversation_summary == "Summary text"
    assert restored._messages == [{"role": "user", "content": "hello", "timestamp": "t"}]
    assert restored._uploaded_files == [{"name": "vip.csv", "path": "/tmp/vip.csv", "kind": "uploaded_list"}]


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



def test_chat_state_round_trips_saved_sessions():
    panel = ChatPanel.__new__(ChatPanel)
    panel._conversation_summary = ""
    panel._messages = [{"role": "user", "content": "hi", "timestamp": ""}]
    panel._uploaded_files = []
    panel._saved_sessions = [
        {"id": "abc", "title": "old chat", "messages": [{"role": "user", "content": "bye", "timestamp": ""}], "summary": "old summary"},
    ]

    state = ChatPanel.chat_state(panel)
    assert len(state["saved_sessions"]) == 1

    restored = ChatPanel.__new__(ChatPanel)
    restored._messages = []
    restored._conversation_summary = ""
    restored._uploaded_files = []
    restored._saved_sessions = []
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
    viewer._edit_site = type("Edit", (), {"setText": lambda self, value: setattr(self, "text", value)})()
    viewer._cb_cat = _FakeCombo(["All", "Power", "Down"])
    viewer._cb_net = _FakeCombo(["All", "4G", "5G"])
    viewer._cb_vnd = _FakeCombo(["All", "HUAWEI", "Nokia"])
    viewer._chk_mindur = _FakeToggle()
    viewer._edit_days = type("Days", (), {"clear": lambda self: setattr(self, "cleared", True)})()
    viewer._chk_date = _FakeToggle()
    viewer._chk_date_range = _FakeToggle()
    viewer._chk_date_days = _FakeToggle()
    viewer._d_from = _FakeDateEdit()
    viewer._d_to = _FakeDateEdit()
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
    assert viewer._edit_site.text == "AAA001"
    assert viewer._cb_cat.current_index == 1
    assert viewer._cb_net.current_index == 1
    assert viewer._cb_vnd.current_index == 1
    assert viewer._chk_mindur.checked is False
    assert viewer._chk_date.checked is True
    assert viewer._chk_date_range.checked is True
    assert viewer._chk_date_days.checked is False
    assert viewer._d_from.value == "2026-04-01"
    assert viewer._d_to.value == "2026-04-30"
    assert viewer._both_pd_active is False
    assert viewer._col_filters == {}
    assert viewer._page_size == 10
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
    viewer._edit_site = type("Edit", (), {"setText": lambda self, value: setattr(self, "text", value)})()
    viewer._cb_cat = _FakeCombo(["All", "Power", "Down"])
    viewer._cb_net = _FakeCombo(["All", "4G", "5G"])
    viewer._cb_vnd = _FakeCombo(["All", "HUAWEI", "Nokia"])
    viewer._chk_mindur = _FakeToggle()
    viewer._edit_days = type("Days", (), {"clear": lambda self: setattr(self, "cleared", True)})()
    viewer._chk_date = _FakeToggle()
    viewer._chk_date_range = _FakeToggle()
    viewer._chk_date_days = _FakeToggle()
    viewer._d_from = _FakeDateEdit()
    viewer._d_to = _FakeDateEdit()
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
    assert viewer._edit_site.text == "AAA001, BBB002"
    assert viewer._cb_cat.current_index == 1
    assert viewer._cb_net.current_index == 1
    assert viewer._cb_vnd.current_index == 1
    assert viewer._chk_mindur.checked is False
    assert viewer._chk_date.checked is True
    assert viewer._chk_date_range.checked is True
    assert viewer._chk_date_days.checked is False
    assert viewer._d_from.value == "2026-04-01"
    assert viewer._d_to.value == "2026-04-30"
    assert viewer._both_pd_active is False
    assert viewer._col_filters == {}
    assert viewer._page_size == 2
    assert viewer._page_offset == 0
    assert calls == {
        "offset": 0,
        "status_message": "Assistant results shown in Alarms",
    }
