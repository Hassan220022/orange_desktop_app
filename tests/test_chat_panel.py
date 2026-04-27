from alarm_app.ui.panels.chat_panel import (
    ChatPanel,
    _normalize_message_text,
    _parse_markdown_blocks,
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
