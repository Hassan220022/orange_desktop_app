from alarm_app.ui.panels.chat_panel import (
    ChatPanel,
    _alarm_row_columns,
    _json_output_text,
    _normalize_message_text,
    _output_paths,
    _photo_group_summary,
    _parse_markdown_blocks,
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


def test_build_prompt_includes_uploaded_files_for_tools():
    panel = ChatPanel.__new__(ChatPanel)
    panel._messages = [("User", "Generate a VIP report")]
    panel._uploaded_files = [{"name": "vip.csv", "path": "/tmp/vip.csv"}]

    prompt = ChatPanel._build_prompt(panel)

    assert "Uploaded local files available to tools:" in prompt
    assert "vip.csv -> /tmp/vip.csv" in prompt
    assert "source_file_path" in prompt
    assert "site_alarm_report" in prompt
    assert "Do not repeat full row tables" in prompt


def test_rows_preview_limit_caps_alarm_rows_to_one_hundred():
    assert _rows_preview_limit(250, 10) == 10
    assert _rows_preview_limit(250, 120) == 100
    assert _rows_preview_limit(7, 10) == 7


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
