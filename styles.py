"""
Stylesheets — Catppuccin Mocha (dark) and Latte (light) themes.

Colour palettes are defined once. The QSS is generated from
position-parameterised templates to keep hex values DRY.

Exports: STYLE, STYLE_DARK, STYLE_LIGHT, MOCHA, LATTE
"""


# ── Catppuccin Mocha palette ────────────────────────────────────────
MOCHA = {
    "rosewater": "#f5e0dc",
    "flamingo": "#f2cdcd",
    "pink": "#f5c2e7",
    "mauve": "#cba6f7",
    "red": "#f38ba8",
    "maroon": "#eba0ac",
    "peach": "#fab387",
    "yellow": "#f9e2af",
    "green": "#a6e3a1",
    "teal": "#94e2d5",
    "sky": "#89dceb",
    "sapphire": "#74c7ec",
    "blue": "#89b4fa",
    "lavender": "#b4befe",
    "text": "#cdd6f4",
    "subtext1": "#bac2de",
    "subtext0": "#a6adc8",
    "overlay2": "#9399b2",
    "overlay1": "#7f849c",
    "overlay0": "#6c7086",
    "surface2": "#585b70",
    "surface1": "#45475a",
    "surface0": "#313244",
    "base": "#1e1e2e",
    "mantle": "#181825",
    "crust": "#11111b",
}


# ── Catppuccin Latte palette ─────────────────────────────────────────
LATTE = {
    "rosewater": "#dc8a78",
    "flamingo": "#dd7878",
    "pink": "#ea76cb",
    "mauve": "#8839ef",
    "red": "#d20f39",
    "maroon": "#e64553",
    "peach": "#fe640b",
    "yellow": "#df8e1d",
    "green": "#40a02b",
    "teal": "#179299",
    "sky": "#04a5e5",
    "sapphire": "#209fb5",
    "blue": "#1e66f5",
    "lavender": "#7287fd",
    "text": "#4c4f69",
    "subtext1": "#5c5f77",
    "subtext0": "#6c6f85",
    "overlay2": "#7c7f93",
    "overlay1": "#8c8fa1",
    "overlay0": "#9ca0b0",
    "surface2": "#acb0be",
    "surface1": "#bcc0cc",
    "surface0": "#ccd0da",
    "base": "#eff1f5",
    "mantle": "#e6e9ef",
    "crust": "#dce0e8",
}


# ── Key name per placeholder position ────────────────────────────────
_KEYS = [
    "bg_QMainWindow__QDialog", "bg_QWidget", "text", "bg_QWidgetactivity_bar", "bd_QWidgetactivity_bar", "bg_QWidgetsidebar",
    "bd_QWidgetsidebar", "bg_QWidgetassistant_panel", "bd_QWidgetassistant_panel", "bg_QWidgetheader", "bd_QWidgetheader", "bd_QGroupBox",
    "overlay0", "bg_QPushButton", "text", "bd_QPushButton", "bg_QPushButtonhover", "blue",
    "blue_1", "bg_QPushButtonpressed", "bd_QPushButtonpressed", "fg_QPushButtonpressed", "base", "bd_QPushButtondisabled",
    "surface1", "bg_QPushButtonbtn_search", "blue_2", "bd_QPushButtonbtn_search", "bg_QPushButtonbtn_searchhover", "blue_3",
    "bg_QPushButtonbtn_clear", "red", "bd_QPushButtonbtn_clear", "bg_QPushButtonbtn_clearhover", "red", "bg_QPushButtonbtn_export",
    "green", "bd_QPushButtonbtn_export", "bg_QPushButtonbtn_exporthover", "green_1", "bg_QPushButtonbtn_backup", "mauve",
    "bd_QPushButtonbtn_backup", "bg_QPushButtonbtn_backuphover", "mauve", "bg_QPushButtonbtn_both", "peach", "bd_QPushButtonbtn_both",
    "bg_QPushButtonbtn_bothhover", "peach", "bg_QPushButtonbtn_load", "peach", "bd_QPushButtonbtn_load", "bg_QPushButtonbtn_loadhover",
    "peach", "base_1", "bd_QPushButtonbtn_loaddisabled", "surface1_1", "base_2", "overlay0",
    "bd_QPushButtonbtn_small", "bg_QPushButtonbtn_smallhover", "text", "surface1_2", "base_3", "blue_4",
    "bd_QPushButtonbtn_dir", "bg_QPushButtonbtn_dirhover", "blue_5", "bg_QPushButtonbtn_assistant", "blue_6", "bd_QPushButtonbtn_assistant",
    "bg_QPushButtonbtn_assistanthove", "blue_7", "bg_QPushButtonbtn_assistantchec", "blue_8", "bd_QPushButtonbtn_assistantchec", "overlay0",
    "bg_QPushButtonactivity_btnhover", "text", "bd_QPushButtonactivity_btnhover", "bg_QPushButtonactivity_btncheck", "blue_9", "blue_10",
    "bg_QLineEdit__QComboBox__QDateE_0", "bd_QLineEdit__QComboBox__QDateE", "text", "bg_QLineEdit__QComboBox__QDateE_1", "text", "bd_QLineEditfocus__QComboBoxfoc",
    "bg_QLineEditfocus__QComboBoxfoc", "bd_QLineEdithover__QComboBoxhov", "bg_QTextEdit__QTextBrowser_0", "text", "bd_QTextEdit__QTextBrowser", "bg_QTextEdit__QTextBrowser_1",
    "text", "bd_QTextEditfocus__QTextBrowser", "bg_QTextEditfocus__QTextBrowser", "bg_QTextEditchat_input", "bd_QTextEditchat_input", "bg_QFrameassistant_toolbar__QFr",
    "bd_QFrameassistant_toolbar__QFr", "fg_QLabelassistant_title", "fg_QLabelassistant_status", "bg_QComboBoxchat_model", "bd_QComboBoxchat_model", "fg_QComboBoxchat_model",
    "bg_QPushButtonassistant_chip", "blue_11", "bd_QPushButtonassistant_chip", "bg_QPushButtonassistant_chiphov", "blue_12", "fg_QPushButtonassistant_chiphov",
    "bg_QPushButtonassistant_chippre", "bg_QPushButtonassistant_send", "fg_QPushButtonassistant_send", "bd_QPushButtonassistant_send", "bg_QPushButtonassistant_sendhov", "bd_QPushButtonassistant_sendhov",
    "bg_QScrollAreaassistant_history", "bd_QScrollAreaassistant_history", "bg_QWidgetassistant_history_hos", "bg_QFramechat_bubble_user", "bd_QFramechat_bubble_user", "bg_QFramechat_bubble_assistant",
    "bd_QFramechat_bubble_assistant", "bg_QFramechat_bubble_system", "bd_QFramechat_bubble_system", "bg_QFramechat_bubble_error", "bd_QFramechat_bubble_error", "fg_QLabelchat_meta_user",
    "fg_QLabelchat_meta_assistant", "fg_QLabelchat_meta_system", "fg_QLabelchat_meta_error", "fg_QLabelchat_text", "fg_QLabelchat_code", "bg_QLabelchat_code",
    "bd_QLabelchat_code", "fg_QLabelchat_table", "bg_QLabelchat_table", "bd_QLabelchat_table", "bg_QFrametool_card", "bd_QFrametool_card",
    "bg_QFrametool_card_error", "bd_QFrametool_card_error", "bg_QFrametool_kv", "bd_QFrametool_kv", "fg_QLabeltool_title", "green_2",
    "fg_QLabeltool_status_error__QLa", "fg_QLabeltool_section", "fg_QLabeltool_body__QLabeltool_", "fg_QLabeltool_kv_key__QLabeltoo", "fg_QLabeltool_metric_value", "bg_QFrametool_metric",
    "bd_QFrametool_metric", "bg_QTableWidgettool_table_0", "bg_QTableWidgettool_table_1", "bd_QTableWidgettool_table", "gl_QTableWidgettool_table", "fg_QTableWidgettool_table",
    "bg_QTableWidgettool_table_QHead", "fg_QTableWidgettool_table_QHead", "bd_QTableWidgettool_table_QHead", "bd_QTableWidgettool_table_QHead", "bg_QComboBox_QAbstractItemView_0", "bd_QComboBox_QAbstractItemView",
    "bg_QComboBox_QAbstractItemView_1", "blue_13", "bg_QListWidget", "bd_QListWidget", "overlay0", "bg_QListWidgetitemselected",
    "blue_14", "bd_QListWidgetitemselected", "bg_QListWidgetitemhoverselected", "subtext0", "bg_QTableView__QTableWidget_0", "bg_QTableView__QTableWidget_1",
    "bd_QTableView__QTableWidget", "gl_QTableView__QTableWidget", "bg_QTableView__QTableWidget_2", "bg_QTableViewitemselected__QTab", "text", "bg_QHeaderViewsection",
    "overlay0", "bd_QHeaderViewsection", "bd_QHeaderViewsection", "bg_QHeaderViewsectionhover", "blue_15", "blue_16",
    "bg_QScrollBarhandlevertical", "bg_QScrollBarhandleverticalhove", "bg_QScrollBarhandlehorizontal", "bg_QScrollBarhandlehorizontalho", "bg_QStatusBar", "surface1_3",
    "base_4", "text", "text", "surface0", "blue_17", "bg_QLabellbl_workspace_tag",
    "bd_QLabellbl_workspace_tag", "surface1_4", "blue_18", "bg_QLabelactivity_brand", "bd_QLabelactivity_brand", "overlay0",
    "text", "overlay1", "text", "green_3", "bg_QFrameworkspace_card", "bd_QFrameworkspace_card",
    "bd_QProgressBar", "crust", "blue_19", "mauve", "base_5", "bg_QCalendarWidget",
    "bd_QCalendarWidget", "bg_QCalendarWidget_QWidgetqt_ca", "bd_QCalendarWidget_QWidgetqt_ca", "text", "bg_QCalendarWidget_QToolButtonh", "bd_QCalendarWidget_QToolButtonh",
    "blue_20", "bg_QCalendarWidget_QToolButtonp", "blue_21", "bg_QCalendarWidget_QToolButtonq", "blue_22", "bg_QCalendarWidget_QSpinBox_0",
    "text", "bd_QCalendarWidget_QSpinBox", "bg_QCalendarWidget_QSpinBox_1", "blue_23", "bg_QCalendarWidget_QSpinBoxupbu_0", "bg_QCalendarWidget_QSpinBoxupbu_1",
    "bg_QCalendarWidget_QAbstractIte_0", "text", "bg_QCalendarWidget_QAbstractIte_1", "blue_24", "text", "surface1_5",
    "bg_QCalendarWidget_QWidget", "bg_QCalendarWidget_QHeaderViews", "overlay0", "bd_QCalendarWidget_QHeaderViews", "bg_QCalendarWidget_QMenu", "bd_QCalendarWidget_QMenu",
    "text", "bg_QCalendarWidget_QMenuitemsel", "blue_25", "bg_QTabWidgetpane", "bg_QTabBartab", "overlay0",
    "bd_QTabBartab", "bg_QTabBartabselected", "blue_26", "bd_QTabBartabselected", "bg_QTabBartabhoverselected", "text",
    "bg_QWidgetbdt_detail_panel", "bg_QFramebdt_info_frame", "bd_QFramebdt_info_frame", "overlay0", "text", "overlay0",
    "surface1_6", "peach", "bg_QLabelbdt_history_separator", "bd_QLabelbdt_history_separator", "peach", "bg_QScrollAreabdt_photo_scroll",
    "bd_QScrollAreabdt_photo_scroll", "bg_QWidgetbdt_photo_container", "bg_QFramebdt_photo_card", "bd_QFramebdt_photo_card", "overlay0", "overlay1_1",
    "bg_QFramebdt_photo_missing", "red", "red", "bg_QFramefilter_panel", "base_6", "bd_QFramefilter_panel",
    "overlay0", "blue_27", "bg_QFramefilter_group", "bd_QFramefilter_group", "bg_QFramefilter_group_date", "bd_QFramefilter_group_date",
    "surface1_7", "bg_QFramefilter_rail", "blue_28", "overlay1_2", "bg_QLineEditfilter_input_0", "bd_QLineEditfilter_input",
    "text", "bg_QLineEditfilter_input_1", "text", "bd_QLineEditfilter_inputhover", "bg_QLineEditfilter_inputhover", "blue_29",
    "bg_QLineEditfilter_inputfocus", "bg_QLineEditfilter_inputdisable", "surface1_8", "bd_QLineEditfilter_inputdisable", "bg_QComboBoxfilter_combo", "bd_QComboBoxfilter_combo",
    "text", "bd_QComboBoxfilter_combohover", "bg_QComboBoxfilter_combohover", "blue_30", "bg_QComboBoxfilter_combofocus__", "bg_QDateEditfilter_date",
    "bd_QDateEditfilter_date", "text", "bd_QDateEditfilter_datehover", "bg_QDateEditfilter_datehover", "blue_31", "bg_QDateEditfilter_datefocus",
    "bg_QDateEditfilter_datedisabled", "surface1_9", "bd_QDateEditfilter_datedisabled", "bg_QSpinBoxfilter_spin", "bd_QSpinBoxfilter_spin", "text",
    "blue_32", "bg_QSpinBoxfilter_spinfocus", "surface1_10", "bd_QSpinBoxfilter_spindisabled", "subtext0", "surface1_11",
    "bd_QCheckBoxfilter_toggleindica_0", "bg_QCheckBoxfilter_toggleindica", "bd_QCheckBoxfilter_toggleindica_1", "blue_33", "blue_34", "bg_QCheckBoxfilter_toggleindica",
    "bd_QCheckBoxfilter_toggleindica_2", "bg_QPushButtonbtn_pill", "overlay1_3", "bd_QPushButtonbtn_pill", "bg_QPushButtonbtn_pillhover", "blue_35",
    "bd_QPushButtonbtn_pillhover", "bg_QPushButtonbtn_pillpressed", "blue_36", "blue_37", "bg_QPushButtonbtn_pilldisabled", "fg_QPushButtonbtn_pilldisabled",
    "bd_QPushButtonbtn_pilldisabled", "bg_QPushButtonbtn_pill_accent", "blue_38", "bd_QPushButtonbtn_pill_accent", "bg_QPushButtonbtn_pill_accentho", "fg_QPushButtonbtn_pill_accentho",
    "blue_39", "bg_QPushButtonbtn_pill_accentdi", "fg_QPushButtonbtn_pill_accentdi", "bd_QPushButtonbtn_pill_accentdi", "overlay0", "bd_QPushButtonbtn_ghost",
    "red", "bd_QPushButtonbtn_ghosthover", "bg_QPushButtonbtn_ghosthover", "fg_QPushButtonbtn_ghostdisabled", "bd_QPushButtonbtn_ghostdisabled", "bg_QFramestats_frame",
    "base_7", "surface1_12", "surface1_13", "blue_40", "red", "peach",
    "sky", "green_4", "mauve", "base_8", "base_9"
]


# ── Dark-theme colour per position ───────────────────────────────────
_DARK = [
    "#13131f", "#13131f", "#cdd6f4", "#0a0a14", "#202032", "#0f0f1a", "#2a2a3e", "#0f0f1a", "#2a2a3e", "#0f0f1a", "#2a2a3e", "#2a2a3e",
    "#6c7086", "#2a2a3e", "#cdd6f4", "#3a3a52", "#313150", "#89b4fa", "#89b4fa", "#1e1e36", "#7287fd", "#7287fd", "#1e1e2e", "#2a2a3e",
    "#45475a", "#1a2744", "#89b4fa", "#2a4070", "#1f3258", "#89b4fa", "#2e1a22", "#f38ba8", "#5a2030", "#3d1e2c", "#f38ba8", "#1a2e22",
    "#a6e3a1", "#244030", "#1e3828", "#a6e3a1", "#261a38", "#cba6f7", "#402858", "#2e1e44", "#cba6f7", "#3e2c12", "#fab387", "#604020",
    "#4a3818", "#fab387", "#3e2c12", "#fab387", "#604020", "#4a3818", "#fab387", "#1e1e2e", "#2a2a3e", "#45475a", "#1e1e2e", "#6c7086",
    "#2a2a3e", "#2a2a3e", "#cdd6f4", "#45475a", "#1e1e2e", "#89b4fa", "#2a3a5a", "#1a2744", "#89b4fa", "#1f2438", "#89b4fa", "#31415d",
    "#26314a", "#89b4fa", "#1a2744", "#89b4fa", "#3a5c96", "#6c7086", "#171726", "#cdd6f4", "#454560", "#171726", "#89b4fa", "#89b4fa",
    "#1a1a2a", "#2a2a3e", "#cdd6f4", "#313150", "#cdd6f4", "#454560", "#1e1e30", "#3a3a52", "#0f0f1a", "#cdd6f4", "#2a2a3e", "#313150",
    "#cdd6f4", "#454560", "#11111f", "#0d1020", "#27314c", "#0f1426", "#232d45", "#e4e9ff", "#8f9dc4", "#0c1122", "#2a3754", "#d7def8",
    "#1a2744", "#89b4fa", "#2a4070", "#1f3258", "#89b4fa", "#b4d4ff", "#162240", "#224177", "#cfe1ff", "#355996", "#2a4f8f", "#6f9de6",
    "#090d1c", "#222e48", "#090d1c", "#173666", "#315b99", "#111a30", "#293657", "#31230f", "#5a3f1c", "#3a1f2a", "#6f2f44", "#bdd8ff",
    "#9cb0d8", "#f3c488", "#f0a8bc", "#d8e1ff", "#c6d6ff", "#0a1228", "#2a406f", "#d8e1ff", "#0a1228", "#2a4060", "#0d1424", "#1e3050",
    "#2a1520", "#5a2535", "#0a101c", "#1a2840", "#dbe7ff", "#a6e3a1", "#f0a8bc", "#8f9dc4", "#cbd8f7", "#8f9dc4", "#e5edff", "#121f38",
    "#2b4067", "#0b1224", "#101a30", "#273958", "#1d2a42", "#d7e2ff", "#101a30", "#9fb4e0", "#273958", "#273958", "#1a1a2a", "#3a3a52",
    "#313150", "#89b4fa", "#0f0f1a", "#2a2a3e", "#6c7086", "#1a1a2e", "#89b4fa", "#2a2a52", "#181828", "#a6adc8", "#0f0f1a", "#121220",
    "#2a2a3e", "#1e1e30", "#1e1e40", "#1e1e40", "#cdd6f4", "#13131f", "#6c7086", "#2a2a3e", "#2a2a3e", "#1a1a2e", "#89b4fa", "#89b4fa",
    "#2a2a3e", "#3a3a52", "#2a2a3e", "#3a3a52", "#0a0a14", "#45475a", "#1e1e2e", "#cdd6f4", "#cdd6f4", "#313244", "#89b4fa", "#171726",
    "#2a4070", "#45475a", "#89b4fa", "#13131f", "#2a2a3e", "#6c7086", "#cdd6f4", "#7f849c", "#cdd6f4", "#a6e3a1", "#10101c", "#222236",
    "#2a2a3e", "#11111b", "#89b4fa", "#cba6f7", "#1e1e2e", "#13131f", "#2a2a3e", "#1a1a2a", "#2a2a3e", "#cdd6f4", "#2a2a3e", "#3a3a52",
    "#89b4fa", "#1e1e36", "#89b4fa", "#1a2744", "#89b4fa", "#1a1a2a", "#cdd6f4", "#2a2a3e", "#313150", "#89b4fa", "#2a2a3e", "#3a3a52",
    "#13131f", "#cdd6f4", "#1a2744", "#89b4fa", "#cdd6f4", "#45475a", "#13131f", "#1a1a2a", "#6c7086", "#2a2a3e", "#1a1a2a", "#3a3a52",
    "#cdd6f4", "#313150", "#89b4fa", "#13131f", "#1a1a2a", "#6c7086", "#2a2a3e", "#13131f", "#89b4fa", "#2a2a3e", "#1e1e30", "#cdd6f4",
    "#0d0d17", "#10101c", "#1c1c2c", "#6c7086", "#cdd6f4", "#6c7086", "#45475a", "#fab387", "#1a1528", "#2e2538", "#fab387", "#0f0f1a",
    "#2a2a3e", "#0f0f1a", "#13131f", "#2a2a3e", "#6c7086", "#7f849c", "#1a1a2a", "#f38ba8", "#f38ba8", "#0d0d17", "#1e1e2e", "#232336",
    "#6c7086", "#89b4fa", "#10101c", "#1c1c2c", "#10101c", "#1c1c2c", "#45475a", "#2a2a3e", "#89b4fa", "#7f849c", "#0a0a14", "#20202e",
    "#cdd6f4", "#1e2a4a", "#cdd6f4", "#2a2a3e", "#0c0c18", "#89b4fa", "#0e0e1c", "#0a0a14", "#45475a", "#1a1a28", "#0a0a14", "#20202e",
    "#cdd6f4", "#2a2a3e", "#0c0c18", "#89b4fa", "#0e0e1c", "#0a0a14", "#20202e", "#cdd6f4", "#2a2a3e", "#0c0c18", "#89b4fa", "#0e0e1c",
    "#0a0a14", "#45475a", "#1a1a28", "#0a0a14", "#20202e", "#cdd6f4", "#89b4fa", "#0e0e1c", "#45475a", "#1a1a28", "#a6adc8", "#45475a",
    "#2a2a3e", "#0a0a14", "#454560", "#89b4fa", "#89b4fa", "#0a0a14", "#1a1a28", "#0a0a14", "#7f849c", "#20202e", "#141424", "#89b4fa",
    "#3a4a7a", "#1a2744", "#89b4fa", "#89b4fa", "#0a0a14", "#35354a", "#1a1a28", "#1a2744", "#89b4fa", "#2a4070", "#1f3258", "#b4d0fa",
    "#89b4fa", "#0a0a14", "#35354a", "#1a1a28", "#6c7086", "#20202e", "#f38ba8", "#5a2030", "#1a0f14", "#35354a", "#1a1a28", "#0a0a14",
    "#1e1e2e", "#45475a", "#45475a", "#89b4fa", "#f38ba8", "#fab387", "#89dceb", "#a6e3a1", "#cba6f7", "#1e1e2e", "#1e1e2e"
]


# ── Light-theme colour per position ──────────────────────────────────
_LIGHT = [
    "#eff1f5", "#eff1f5", "#4c4f69", "#ccd0da", "#bcc0cc", "#e6e9ef", "#bcc0cc", "#eff1f5", "#bcc0cc", "#e6e9ef", "#bcc0cc", "#bcc0cc",
    "#8c8fa1", "#ccd0da", "#4c4f69", "#bcc0cc", "#bcc0cc", "#1e66f5", "#1e66f5", "#acb0be", "#7287fd", "#7287fd", "#dce0e8", "#ccd0da",
    "#9ca0b0", "#d5e0fc", "#1e66f5", "#a8c2f8", "#c5d5fa", "#1e66f5", "#f5d0d8", "#d20f39", "#e8a0b0", "#f0c0cc", "#d20f39", "#d0eacc",
    "#40a02b", "#a8d4a0", "#c0e0b8", "#40a02b", "#e0d0f8", "#8839ef", "#c8a8f0", "#d4c0f4", "#8839ef", "#fce0c8", "#fe640b", "#f0c8a0",
    "#f8d4b8", "#fe640b", "#fce0c8", "#fe640b", "#f0c8a0", "#f8d4b8", "#fe640b", "#dce0e8", "#ccd0da", "#9ca0b0", "#dce0e8", "#8c8fa1",
    "#ccd0da", "#ccd0da", "#4c4f69", "#acb0be", "#dce0e8", "#1e66f5", "#a8c2f8", "#d5e0fc", "#1e66f5", "#dce0e8", "#1e66f5", "#a8c2f8",
    "#d5e0fc", "#1e66f5", "#ccd9f8", "#1e66f5", "#86a7ef", "#8c8fa1", "#e6e9ef", "#4c4f69", "#8c8fa1", "#eff1f5", "#1e66f5", "#1e66f5",
    "#dce0e8", "#bcc0cc", "#4c4f69", "#acb0be", "#4c4f69", "#8c8fa1", "#ccd0da", "#acb0be", "#eff1f5", "#4c4f69", "#bcc0cc", "#acb0be",
    "#4c4f69", "#8c8fa1", "#e6e9ef", "#f5f7ff", "#b7c8e9", "#f4f7ff", "#c3d0e8", "#1d2f57", "#61739a", "#edf2fb", "#b7c8e9", "#223662",
    "#e0e8f8", "#2a5090", "#a8b8d8", "#d0dcf0", "#6080b0", "#1a4080", "#c8d4e8", "#2f5fad", "#edf3ff", "#4b76c0", "#386cbe", "#6f96d2",
    "#f8faff", "#c3d0e8", "#f8faff", "#dbe8ff", "#9cb8ea", "#eef3ff", "#c6d3eb", "#fbeed8", "#e2be82", "#ffe8ec", "#e6a6b3", "#2e4f8f",
    "#4a5f8d", "#aa6206", "#b44258", "#243a67", "#26457e", "#edf2ff", "#b9caeb", "#243a67", "#f0f4fa", "#c0d0e8", "#e8effa", "#b0c4e0",
    "#fae8ec", "#d0a0b0", "#f0f4fa", "#c0cce0", "#263f73", "#2f8a3a", "#b44258", "#64759e", "#243a67", "#64759e", "#233c72", "#f8faff",
    "#c8d6ef", "#f8faff", "#eef3ff", "#c8d6ef", "#d7e2f4", "#243a67", "#e4ecfb", "#3f5683", "#c8d6ef", "#c8d6ef", "#dce0e8", "#acb0be",
    "#bcc0cc", "#1e66f5", "#e6e9ef", "#bcc0cc", "#8c8fa1", "#d5e0fc", "#1e66f5", "#a8c2f8", "#dce0e8", "#6c6f85", "#e6e9ef", "#eaecf3",
    "#bcc0cc", "#ccd0da", "#d5e0fc", "#d5e0fc", "#4c4f69", "#eff1f5", "#8c8fa1", "#bcc0cc", "#bcc0cc", "#e6e9ef", "#1e66f5", "#1e66f5",
    "#bcc0cc", "#acb0be", "#bcc0cc", "#acb0be", "#dce0e8", "#9ca0b0", "#ccd0da", "#4c4f69", "#4c4f69", "#acb0be", "#1e66f5", "#e6e9ef",
    "#b7c9f7", "#9ca0b0", "#1e66f5", "#eff1f5", "#bcc0cc", "#8c8fa1", "#4c4f69", "#6c6f85", "#4c4f69", "#40a02b", "#eff1f5", "#ccd0da",
    "#bcc0cc", "#e6e9ef", "#1e66f5", "#8839ef", "#ccd0da", "#eff1f5", "#bcc0cc", "#dce0e8", "#bcc0cc", "#4c4f69", "#ccd0da", "#acb0be",
    "#1e66f5", "#bcc0cc", "#1e66f5", "#d5e0fc", "#1e66f5", "#dce0e8", "#4c4f69", "#bcc0cc", "#acb0be", "#1e66f5", "#ccd0da", "#bcc0cc",
    "#eff1f5", "#4c4f69", "#d5e0fc", "#1e66f5", "#4c4f69", "#9ca0b0", "#eff1f5", "#dce0e8", "#8c8fa1", "#bcc0cc", "#dce0e8", "#acb0be",
    "#4c4f69", "#bcc0cc", "#1e66f5", "#eff1f5", "#dce0e8", "#8c8fa1", "#bcc0cc", "#eff1f5", "#1e66f5", "#bcc0cc", "#ccd0da", "#4c4f69",
    "#e6e9ef", "#dce0e8", "#ccd0da", "#8c8fa1", "#4c4f69", "#8c8fa1", "#9ca0b0", "#fe640b", "#fce0c8", "#f0c8a0", "#fe640b", "#e6e9ef",
    "#bcc0cc", "#e6e9ef", "#eff1f5", "#bcc0cc", "#8c8fa1", "#7c7f93", "#dce0e8", "#d20f39", "#d20f39", "#e6e9ef", "#ccd0da", "#bcc0cc",
    "#8c8fa1", "#1e66f5", "#dce0e8", "#ccd0da", "#dce0e8", "#ccd0da", "#9ca0b0", "#bcc0cc", "#1e66f5", "#7c7f93", "#eff1f5", "#ccd0da",
    "#4c4f69", "#d5e0fc", "#4c4f69", "#bcc0cc", "#eaecf3", "#1e66f5", "#e6e9ef", "#eff1f5", "#9ca0b0", "#dce0e8", "#eff1f5", "#ccd0da",
    "#4c4f69", "#bcc0cc", "#eaecf3", "#1e66f5", "#e6e9ef", "#eff1f5", "#ccd0da", "#4c4f69", "#bcc0cc", "#eaecf3", "#1e66f5", "#e6e9ef",
    "#eff1f5", "#9ca0b0", "#dce0e8", "#eff1f5", "#ccd0da", "#4c4f69", "#1e66f5", "#e6e9ef", "#9ca0b0", "#dce0e8", "#6c6f85", "#9ca0b0",
    "#bcc0cc", "#eff1f5", "#8c8fa1", "#1e66f5", "#1e66f5", "#eff1f5", "#dce0e8", "#eff1f5", "#7c7f93", "#ccd0da", "#e6e9ef", "#1e66f5",
    "#8aaef0", "#d5e0fc", "#1e66f5", "#1e66f5", "#eff1f5", "#bcc0cc", "#dce0e8", "#d5e0fc", "#1e66f5", "#a8c2f8", "#c5d5fa", "#1450c8",
    "#1e66f5", "#eff1f5", "#bcc0cc", "#dce0e8", "#8c8fa1", "#ccd0da", "#d20f39", "#e8a0b0", "#fce8ec", "#bcc0cc", "#dce0e8", "#dce0e8",
    "#ccd0da", "#6c6f85", "#6c6f85", "#1e66f5", "#d20f39", "#fe640b", "#209fb5", "#40a02b", "#8839ef", "#ccd0da", "#ccd0da"
]


def _render(template, colors):
    """Substitute {0} … {N} placeholders with palette values."""
    result = template
    for i in range(len(colors) - 1, -1, -1):
        result = result.replace("{" + str(i) + "}", colors[i])
    return result


# ── TMPL_DARK QSS template ──
_TMPL_DARK = """\

/* ── Base ──────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background: {0};
}
QWidget {
    background: {1};
    color: {2};
    font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
    font-size: 13px;
}

/* ── Left sidebar background ───────────────────────────────── */
QWidget#activity_bar {
    background: {3};
    border-right: 1px solid {4};
}
QWidget#sidebar {
    background: {5};
    border-right: 1px solid {6};
}
QWidget#assistant_panel {
    background: {7};
    border-left: 1px solid {8};
}

/* ── Top header ─────────────────────────────────────────────── */
QWidget#header {
    background: {9};
    border-bottom: 1px solid {10};
}

/* ── GroupBox ───────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid {11};
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    color: {12};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    background: transparent;
}

/* ── Buttons ────────────────────────────────────────────────── */
QPushButton {
    background: {13};
    color: {14};
    border: 1px solid {15};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
    min-width: 0px;
    min-height: 34px;
}
QPushButton:hover {
    background: {16};
    border-color: {17};
    color: {18};
}
QPushButton:pressed {
    background: {19};
    border-color: {20};
    color: {21};
}
QPushButton:disabled {
    background: {22};
    border-color: {23};
    color: {24};
}

/* Search — primary blue */
QPushButton#btn_search {
    background: {25};
    color: {26};
    border: 1px solid {27};
    min-width: 0px;
}
QPushButton#btn_search:hover {
    background: {28};
    border-color: {29};
}
QPushButton#btn_search[compact="true"] {
    min-width: 0px;
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}

/* Clear — red */
QPushButton#btn_clear {
    background: {30};
    color: {31};
    border: 1px solid {32};
}
QPushButton#btn_clear:hover {
    background: {33};
    border-color: {34};
}

/* Export — green */
QPushButton#btn_export {
    background: {35};
    color: {36};
    border: 1px solid {37};
}
QPushButton#btn_export:hover {
    background: {38};
    border-color: {39};
}
QPushButton#btn_export[compact="true"] {
    min-width: 0px;
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}

/* Backup Time — purple */
QPushButton#btn_backup {
    background: {40};
    color: {41};
    border: 1px solid {42};
}
QPushButton#btn_backup:hover {
    background: {43};
    border-color: {44};
}

/* Both P+D — orange */
QPushButton#btn_both {
    background: {45};
    color: {46};
    border: 1px solid {47};
}
QPushButton#btn_both:hover {
    background: {48};
    border-color: {49};
}

/* Load — amber */
QPushButton#btn_load {
    background: {50};
    color: {51};
    border: 1px solid {52};
    font-size: 13px;
    padding: 8px 14px;
    min-height: 38px;
}
QPushButton#btn_load:hover {
    background: {53};
    border-color: {54};
}
QPushButton#btn_load:disabled {
    background: {55};
    border-color: {56};
    color: {57};
}
QPushButton#btn_load[compact="true"] {
    min-width: 0px;
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}

/* Small selection buttons */
QPushButton#btn_small {
    background: {58};
    color: {59};
    border: 1px solid {60};
    border-radius: 5px;
    padding: 4px 10px;
    min-width: 38px;
    font-size: 11px;
    min-height: 28px;
}
QPushButton#btn_small:hover {
    background: {61};
    color: {62};
    border-color: {63};
}

/* Sidebar Browse/Scan */
QPushButton#btn_dir {
    background: {64};
    color: {65};
    border: 1px solid {66};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    min-width: 60px;
    min-height: 34px;
}
QPushButton#btn_dir:hover {
    background: {67};
    border-color: {68};
}
QPushButton#btn_dir[compact="true"] {
    min-width: 0px;
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}
QPushButton[compact="true"] {
    padding: 3px 8px;
    font-size: 11px;
    min-height: 26px;
    border-radius: 5px;
}
QPushButton#btn_assistant {
    background: {69};
    color: {70};
    border: 1px solid {71};
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}
QPushButton#btn_assistant:hover {
    background: {72};
    border-color: {73};
}
QPushButton#btn_assistant:checked {
    background: {74};
    color: {75};
    border: 1px solid {76};
}
QPushButton#activity_btn {
    background: transparent;
    color: {77};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 10px;
    padding: 10px 6px;
    font-size: 11px;
    font-weight: 700;
    text-align: center;
    min-width: 0px;
}
QPushButton#activity_btn:hover {
    background: {78};
    color: {79};
    border-left-color: {80};
}
QPushButton#activity_btn:checked {
    background: {81};
    color: {82};
    border-left-color: {83};
}

/* ── Inputs ─────────────────────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit {
    background: {84};
    border: 1px solid {85};
    border-radius: 6px;
    padding: 6px 10px;
    color: {86};
    font-size: 13px;
    selection-background-color: {87};
    selection-color: {88};
    min-height: 28px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
    border-color: {89};
    background: {90};
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover {
    border-color: {91};
}
QTextEdit, QTextBrowser {
    background: {92};
    color: {93};
    border: 1px solid {94};
    border-radius: 8px;
    padding: 8px;
    selection-background-color: {95};
    selection-color: {96};
}
QTextEdit:focus, QTextBrowser:focus {
    border-color: {97};
    background: {98};
}
QTextBrowser#chat_transcript {
    font-size: 13px;
    line-height: 1.35;
}
QTextEdit#chat_input {
    font-size: 13px;
    min-height: 58px;
    background: {99};
    border: 1px solid {100};
    border-radius: 8px;
}
QFrame#assistant_toolbar, QFrame#assistant_composer {
    background: {101};
    border: 1px solid {102};
    border-radius: 8px;
}
QFrame#assistant_composer {
    margin-top: 4px;
}
QFrame#assistant_quick_actions {
    background: transparent;
    border: none;
}
QLabel#assistant_title {
    color: {103};
    font-size: 17px;
    font-weight: 700;
}
QLabel#assistant_status {
    color: {104};
    font-size: 11px;
    font-weight: 600;
}
QComboBox#chat_model {
    min-height: 30px;
    background: {105};
    border: 1px solid {106};
    border-radius: 8px;
    color: {107};
    padding: 4px 8px;
}
QPushButton#assistant_chip {
    background: {108};
    color: {109};
    border: 1px solid {110};
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 28px;
    min-width: 0px;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#assistant_chip:hover {
    background: {111};
    border-color: {112};
    color: {113};
}
QPushButton#assistant_chip:pressed {
    background: {114};
}
QPushButton#assistant_send {
    background: {115};
    color: {116};
    border: 1px solid {117};
    border-radius: 8px;
    min-height: 32px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#assistant_send:hover {
    background: {118};
    border-color: {119};
}
QPushButton#assistant_stop {
    background: {30};
    color: {31};
    border: 1px solid {32};
    border-radius: 8px;
    min-height: 32px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#assistant_stop:hover {
    background: {33};
    border-color: {34};
}
QScrollArea#assistant_history_scroll {
    background: {120};
    border: none;
    border-radius: 0px;
}
QWidget#assistant_history_host {
    background: {122};
}
QWidget#chat_row {
    background: transparent;
    border: none;
}
QFrame#chat_bubble_user {
    background: {123};
    border: 1px solid {124};
    border-radius: 8px;
}
QFrame#chat_bubble_assistant {
    background: {125};
    border: 1px solid {126};
    border-radius: 8px;
}
QFrame#chat_bubble_system {
    background: {127};
    border: 1px solid {128};
    border-radius: 8px;
}
QFrame#chat_bubble_thinking {
    background: {127};
    border: 1px dashed {128};
    border-radius: 8px;
}
QFrame#chat_bubble_error {
    background: {129};
    border: 1px solid {130};
    border-radius: 8px;
}
QFrame#chat_empty_state {
    background: transparent;
    border: none;
}
QFrame#chat_api_banner {
    background: {129};
    border: 1px solid {130};
    border-radius: 6px;
    margin: 4px 0;
}
QLabel#chat_meta_user {
    color: {131};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_meta_assistant {
    color: {132};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_meta_system {
    color: {133};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_meta_error {
    color: {134};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_text {
    color: {135};
    font-size: 13px;
    line-height: 1.4;
}
QLabel#chat_code {
    color: {136};
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 12px;
    background: {137};
    border: 1px solid {138};
    border-radius: 8px;
    padding: 6px;
}
QLabel#chat_table {
    color: {139};
    font-size: 12px;
    background: {140};
    border: 1px solid {141};
    border-radius: 6px;
}
QFrame#tool_card {
    background: {142};
    border: 1px solid {143};
    border-radius: 8px;
    margin: 6px 0px;
}
QFrame#tool_card_error {
    background: {144};
    border: 1px solid {145};
    border-radius: 8px;
    margin: 2px 0px;
}
QFrame#tool_detail {
    background: transparent;
    border: none;
    margin-top: 4px;
}
QFrame#tool_kv {
    background: {146};
    border: 1px solid {147};
    border-radius: 6px;
    padding: 4px;
}
QFrame#tool_metrics {
    background: transparent;
    border: none;
}
QLabel#tool_title {
    color: {148};
    font-size: 13px;
    font-weight: 800;
}
QLabel#tool_status {
    color: {149};
    font-size: 11px;
    font-weight: 700;
}
QLabel#tool_status_error, QLabel#tool_error {
    color: {150};
    font-size: 12px;
    font-weight: 700;
}
QLabel#tool_section {
    color: {151};
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#tool_body, QLabel#tool_kv_value {
    color: {152};
    font-size: 12px;
}
QLabel#tool_kv_key, QLabel#tool_metric_label {
    color: {153};
    font-size: 11px;
    font-weight: 700;
}
QLabel#tool_metric_value {
    color: {154};
    font-size: 14px;
    font-weight: 800;
}
QFrame#tool_metric {
    background: {155};
    border: 1px solid {156};
    border-radius: 8px;
}
QTableWidget#tool_table {
    background: {157};
    alternate-background-color: {158};
    border: 1px solid {159};
    border-radius: 8px;
    gridline-color: {160};
    color: {161};
}
QTableWidget#tool_table QHeaderView::section {
    background: {162};
    color: {163};
    border-right: 1px solid {164};
    border-bottom: 1px solid {165};
    font-size: 10px;
    font-weight: 800;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: {166};
    border: 1px solid {167};
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: {168};
    selection-color: {169};
}

/* ── File list ──────────────────────────────────────────────── */
QListWidget {
    background: {170};
    border: 1px solid {171};
    border-radius: 6px;
    outline: none;
    padding: 2px;
}
QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
    margin: 1px 2px;
    color: {172};
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 11px;
}
QListWidget::item:selected {
    background: {173};
    color: {174};
    border: 1px solid {175};
}
QListWidget::item:hover:!selected {
    background: {176};
    color: {177};
}

/* ── Tables ─────────────────────────────────────────────────── */
QTableView, QTableWidget {
    background: {178};
    alternate-background-color: {179};
    border: 1px solid {180};
    border-radius: 8px;
    gridline-color: {181};
    outline: none;
    selection-background-color: {182};
}
QTableView::item, QTableWidget::item {
    padding: 3px 8px;
    border: none;
}
QTableView::item:selected, QTableWidget::item:selected {
    background: {183};
    color: {184};
}
QHeaderView {
    background: transparent;
}
QHeaderView::section {
    background: {185};
    color: {186};
    border: none;
    border-right: 1px solid {187};
    border-bottom: 2px solid {188};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
}
QHeaderView::section:first {
    border-top-left-radius: 6px;
}
QHeaderView::section:hover {
    background: {189};
    color: {190};
}
QHeaderView::section:checked {
    color: {191};
}

/* ── Scrollbars ─────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: {192};
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: {193};
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: {194};
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: {195};
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: {196};
    color: {197};
    border-top: 1px solid {198};
    font-size: 11px;
    padding: 2px 8px;
}
QStatusBar::item {
    border: none;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    color: {199};
    background: transparent;
}
QLabel#lbl_app_name {
    color: {200};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QLabel#lbl_app_ver {
    color: {201};
    font-size: 11px;
}
QLabel#lbl_workspace_tag {
    color: {202};
    background: {203};
    border: 1px solid {204};
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#lbl_section {
    color: {205};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
}
QLabel#activity_brand {
    color: {206};
    background: {207};
    border: 1px solid {208};
    border-radius: 12px;
    font-size: 12px;
    font-weight: 800;
    padding: 10px 0;
}
QLabel#sidebar_brand {
    color: {209};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.9px;
}
QLabel#sidebar_title {
    color: {210};
    font-size: 18px;
    font-weight: 700;
}
QLabel#sidebar_body {
    color: {211};
    font-size: 12px;
}
QLabel#workspace_card_title {
    color: {212};
    font-size: 12px;
    font-weight: 700;
}
QLabel#lbl_green {
    color: {213};
    font-weight: 600;
    font-size: 12px;
}
QFrame#workspace_card {
    background: {214};
    border: 1px solid {215};
    border-radius: 10px;
}
/* ── Progress bar ───────────────────────────────────────────── */
QProgressBar {
    border: 1px solid {216};
    border-radius: 6px;
    background: {217};
    text-align: center;
    color: transparent;
    min-height: 12px;
    max-height: 12px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {218}, stop:1 {219});
    border-radius: 5px;
}

/* ── Splitter ───────────────────────────────────────────────── */
QSplitter::handle {
    background: {220};
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ── Calendar ───────────────────────────────────────────────── */
QCalendarWidget {
    background: {221};
    border: 1px solid {222};
    border-radius: 8px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: {223};
    border-bottom: 1px solid {224};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 4px 8px;
    min-height: 36px;
}
QCalendarWidget QToolButton {
    background: transparent;
    color: {225};
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 13px;
    font-weight: 600;
}
QCalendarWidget QToolButton:hover {
    background: {226};
    border-color: {227};
    color: {228};
}
QCalendarWidget QToolButton:pressed {
    background: {229};
}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {
    min-width: 28px;
    min-height: 28px;
    border-radius: 14px;
    qproperty-icon: none;
    font-size: 14px;
    color: {230};
}
QCalendarWidget QToolButton#qt_calendar_prevmonth { qproperty-text: "<"; }
QCalendarWidget QToolButton#qt_calendar_nextmonth { qproperty-text: ">"; }
QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {
    background: {231};
    border-color: {232};
}
QCalendarWidget QSpinBox {
    background: {233};
    color: {234};
    border: 1px solid {235};
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 13px;
    font-weight: 600;
    selection-background-color: {236};
    selection-color: {237};
}
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {
    subcontrol-origin: border;
    width: 18px;
    background: {238};
    border: none;
}
QCalendarWidget QSpinBox::up-button:hover,
QCalendarWidget QSpinBox::down-button:hover {
    background: {239};
}

/* Day grid */
QCalendarWidget QAbstractItemView {
    background: {240};
    color: {241};
    font-size: 13px;
    outline: none;
    selection-background-color: {242};
    selection-color: {243};
    border: none;
    padding: 2px;
}
QCalendarWidget QAbstractItemView:enabled {
    color: {244};
}
QCalendarWidget QAbstractItemView:disabled {
    color: {245};
}

/* Header row (day names) */
QCalendarWidget QWidget { alternate-background-color: {246}; }
QCalendarWidget QHeaderView::section {
    background: {247};
    color: {248};
    border: none;
    border-bottom: 1px solid {249};
    padding: 6px 4px;
    font-size: 11px;
    font-weight: 700;
}

/* SpinBox in calendar (year) */
QCalendarWidget QMenu {
    background: {250};
    border: 1px solid {251};
    border-radius: 6px;
    color: {252};
    padding: 4px;
}
QCalendarWidget QMenu::item:selected {
    background: {253};
    color: {254};
}

/* ── Tab widget ────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background: {255};
}
QTabBar::tab {
    background: {256};
    color: {257};
    border: 1px solid {258};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: {259};
    color: {260};
    border-color: {261};
}
QTabBar::tab:hover:!selected {
    background: {262};
    color: {263};
}

/* ── BDT Detail Panel — Command Console aesthetic ─────────── */
QWidget#bdt_detail_panel {
    background: {264};
}
QFrame#bdt_info_frame {
    background: {265};
    border: 1px solid {266};
    border-radius: 8px;
    padding: 4px;
}
QLabel#bdt_info_key {
    color: {267};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_info_val {
    color: {268};
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_section_title {
    color: {269};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    background: transparent;
    padding: 2px 0 2px 0;
}
QLabel#bdt_empty_hint {
    color: {270};
    font-size: 10px;
    font-style: italic;
    background: transparent;
    padding: 2px 2px 6px 2px;
}

/* "PREVIOUS TEST — yyyy-MM-dd" separator inside the photo scroll.
   Stronger weight and an accent-colored top border so the user
   instantly sees where a historical test starts. */
QLabel#bdt_history_separator {
    color: {271};
    background: {272};
    border: 1px solid {273};
    border-top: 2px solid {274};
    border-radius: 6px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
    padding: 8px 12px;
    margin-top: 14px;
    margin-bottom: 4px;
}

/* ── BDT Photo Gallery ────────────────────────────────────── */
QScrollArea#bdt_photo_scroll {
    background: {275};
    border: 1px solid {276};
    border-radius: 6px;
}
QScrollArea#bdt_info_scroll {
    background: transparent;
    border: none;
}
QScrollArea#bdt_info_scroll > QWidget > QWidget {
    background: transparent;
}
QWidget#bdt_photo_container {
    background: {277};
}
QFrame#bdt_photo_card {
    background: {278};
    border: 1px solid {279};
    border-radius: 6px;
    padding: 4px;
}
QLabel#bdt_photo_label {
    color: {280};
    font-size: 10px;
    font-weight: 600;
    background: transparent;
    padding: 2px 0 0 0;
}
QLabel#bdt_photo_meta {
    color: {281};
    font-size: 9px;
    font-weight: 500;
    background: transparent;
    padding: 1px 4px 2px 4px;
}
QFrame#bdt_photo_missing {
    background: {282};
    border: 2px dashed {283};
    border-radius: 6px;
    min-height: 120px;
}
QLabel#bdt_photo_missing_label {
    color: {284};
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

/* ═══════════════════════════════════════════════════════════════ */
/*  FILTER PANEL — Command Console aesthetic                       */
/*  Info-dense NOC look: thin borders, accent rails, uppercase     */
/*  section caps, phosphor focus glow.                             */
/* ═══════════════════════════════════════════════════════════════ */

/* Outer panel — replaces the old GroupBox */
QFrame#filter_panel {
    background: {285};
    border: 1px solid {286};
    border-top: 1px solid {287};
    border-radius: 10px;
}

/* Tiny uppercase section cap label ("SITE", "CLASSIFICATION"…) */
QLabel#filter_section {
    color: {288};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    background: transparent;
    padding: 0 0 2px 0;
}
QLabel#filter_section_active {
    color: {289};
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.6px;
    background: transparent;
    padding: 0 0 2px 0;
}

/* Subtle grouping container — no heavy box, just a darker tint */
QFrame#filter_group {
    background: {290};
    border: 1px solid {291};
    border-radius: 8px;
}
QFrame#filter_group_date {
    background: {292};
    border: 1px solid {293};
    border-left: 2px solid {294};
    border-radius: 8px;
}

/* Vertical accent rail — 2px stripe that marks a group as "active" */
QFrame#filter_rail {
    background: {295};
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}
QFrame#filter_rail_active {
    background: {296};
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}

/* Inline label inside a group — muted, small, fixed weight */
QLabel#filter_inline {
    color: {297};
    font-size: 11px;
    font-weight: 500;
    background: transparent;
    padding: 0 2px;
}

/* Refined inputs — darker surface, thin border, phosphor focus glow */
QLineEdit#filter_input {
    background: {298};
    border: 1px solid {299};
    border-radius: 6px;
    padding: 7px 11px;
    color: {300};
    font-size: 13px;
    font-weight: 500;
    selection-background-color: {301};
    selection-color: {302};
    min-height: 26px;
}
QLineEdit#filter_input:hover {
    border-color: {303};
    background: {304};
}
QLineEdit#filter_input:focus {
    border-color: {305};
    background: {306};
}
QLineEdit#filter_input:disabled {
    background: {307};
    color: {308};
    border-color: {309};
}

/* Compact combo */
QComboBox#filter_combo {
    background: {310};
    border: 1px solid {311};
    border-radius: 6px;
    padding: 6px 10px;
    padding-right: 24px;
    color: {312};
    font-size: 12px;
    font-weight: 600;
    min-height: 26px;
}
QComboBox#filter_combo:hover {
    border-color: {313};
    background: {314};
}
QComboBox#filter_combo:focus, QComboBox#filter_combo:on {
    border-color: {315};
    background: {316};
}
QComboBox#filter_combo::drop-down {
    border: none;
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}

/* Compact date picker inside filter panel */
QDateEdit#filter_date {
    background: {317};
    border: 1px solid {318};
    border-radius: 6px;
    padding: 6px 10px;
    color: {319};
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QDateEdit#filter_date:hover {
    border-color: {320};
    background: {321};
}
QDateEdit#filter_date:focus {
    border-color: {322};
    background: {323};
}
QDateEdit#filter_date:disabled {
    background: {324};
    color: {325};
    border-color: {326};
}

/* Numeric spin inside filter panel */
QSpinBox#filter_spin {
    background: {327};
    border: 1px solid {328};
    border-radius: 6px;
    padding: 6px 8px;
    color: {329};
    font-size: 12px;
    font-weight: 700;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QSpinBox#filter_spin:focus {
    border-color: {330};
    background: {331};
}
QSpinBox#filter_spin:disabled {
    color: {332};
    border-color: {333};
}

/* Toggle-style checkbox — larger, accent fill when checked */
QCheckBox#filter_toggle {
    color: {334};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    background: transparent;
    spacing: 7px;
    padding: 2px 0;
}
QCheckBox#filter_toggle:disabled {
    color: {335};
}
QCheckBox#filter_toggle::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {336};
    background: {337};
}
QCheckBox#filter_toggle::indicator:hover {
    border-color: {338};
}
QCheckBox#filter_toggle::indicator:checked {
    background: {339};
    border: 1px solid {340};
    image: none;
}
QCheckBox#filter_toggle::indicator:disabled {
    background: {341};
    border-color: {342};
}

/* Pill-shaped quick-pick button */
QPushButton#btn_pill {
    background: {343};
    color: {344};
    border: 1px solid {345};
    border-radius: 12px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-width: 0;
    min-height: 22px;
}
QPushButton#btn_pill:hover {
    background: {346};
    color: {347};
    border-color: {348};
}
QPushButton#btn_pill:pressed {
    background: {349};
    color: {350};
    border-color: {351};
}
QPushButton#btn_pill:disabled {
    background: {352};
    color: {353};
    border-color: {354};
}

/* "Add" accent button for specific-days input */
QPushButton#btn_pill_accent {
    background: {355};
    color: {356};
    border: 1px solid {357};
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-height: 22px;
}
QPushButton#btn_pill_accent:hover {
    background: {358};
    color: {359};
    border-color: {360};
}
QPushButton#btn_pill_accent:disabled {
    background: {361};
    color: {362};
    border-color: {363};
}

/* Ghost clear button */
QPushButton#btn_ghost {
    background: transparent;
    color: {364};
    border: 1px solid {365};
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    min-height: 22px;
}
QPushButton#btn_ghost:hover {
    color: {366};
    border-color: {367};
    background: {368};
}
QPushButton#btn_ghost:disabled {
    color: {369};
    border-color: {370};
}
/* ── Statistics panel ────────────────────────────────────────── */
QFrame#stats_frame {
    background: {371};
    border: 1px solid {372};
    border-radius: 8px;
}
QLabel#stats_section_label {
    color: {373};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    background: transparent;
}
QLabel#stats_label {
    color: {374};
    font-size: 11px;
    background: transparent;
}
QLabel#stat_total  { color: {375}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_power  { color: {376}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_down   { color: {377}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_door   { color: {378}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_sites  { color: {379}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_avg_dur { color: {380}; font-size: 12px; font-weight: bold; background: transparent; }
QFrame#stats_sep {
    color: {381};
    background: {382};
    max-height: 1px;
}
"""

# ── TMPL_LIGHT QSS template ──
_TMPL_LIGHT = """\

/* ── Base ──────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background: {0};
}
QWidget {
    background: {1};
    color: {2};
    font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
    font-size: 13px;
}

/* ── Left sidebar background ───────────────────────────────── */
QWidget#activity_bar {
    background: {3};
    border-right: 1px solid {4};
}
QWidget#sidebar {
    background: {5};
    border-right: 1px solid {6};
}
QWidget#assistant_panel {
    background: {7};
    border-left: 1px solid {8};
}

/* ── Top header ─────────────────────────────────────────────── */
QWidget#header {
    background: {9};
    border-bottom: 1px solid {10};
}

/* ── GroupBox ───────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid {11};
    border-radius: 8px;
    margin-top: 10px;
    padding: 10px 8px 8px 8px;
    color: {12};
    font-size: 11px;
    font-weight: bold;
    letter-spacing: 0.8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    background: transparent;
}

/* ── Buttons ────────────────────────────────────────────────── */
QPushButton {
    background: {13};
    color: {14};
    border: 1px solid {15};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
    font-size: 12px;
    min-width: 0px;
    min-height: 34px;
}
QPushButton:hover {
    background: {16};
    border-color: {17};
    color: {18};
}
QPushButton:pressed {
    background: {19};
    border-color: {20};
    color: {21};
}
QPushButton:disabled {
    background: {22};
    border-color: {23};
    color: {24};
}

/* Search — primary blue */
QPushButton#btn_search {
    background: {25};
    color: {26};
    border: 1px solid {27};
    min-width: 0px;
}
QPushButton#btn_search:hover {
    background: {28};
    border-color: {29};
}

/* Clear — red */
QPushButton#btn_clear {
    background: {30};
    color: {31};
    border: 1px solid {32};
}
QPushButton#btn_clear:hover {
    background: {33};
    border-color: {34};
}

/* Export — green */
QPushButton#btn_export {
    background: {35};
    color: {36};
    border: 1px solid {37};
}
QPushButton#btn_export:hover {
    background: {38};
    border-color: {39};
}

/* Backup Time — purple */
QPushButton#btn_backup {
    background: {40};
    color: {41};
    border: 1px solid {42};
}
QPushButton#btn_backup:hover {
    background: {43};
    border-color: {44};
}

/* Both P+D — orange */
QPushButton#btn_both {
    background: {45};
    color: {46};
    border: 1px solid {47};
}
QPushButton#btn_both:hover {
    background: {48};
    border-color: {49};
}

/* Load — amber */
QPushButton#btn_load {
    background: {50};
    color: {51};
    border: 1px solid {52};
    font-size: 13px;
    padding: 8px 14px;
    min-height: 38px;
}
QPushButton#btn_load:hover {
    background: {53};
    border-color: {54};
}
QPushButton#btn_load:disabled {
    background: {55};
    border-color: {56};
    color: {57};
}
QPushButton#btn_load[compact="true"] {
    min-width: 0px;
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}

/* Small selection buttons */
QPushButton#btn_small {
    background: {58};
    color: {59};
    border: 1px solid {60};
    border-radius: 5px;
    padding: 4px 10px;
    min-width: 38px;
    font-size: 11px;
    min-height: 28px;
}
QPushButton#btn_small:hover {
    background: {61};
    color: {62};
    border-color: {63};
}

/* Sidebar Browse/Scan */
QPushButton#btn_dir {
    background: {64};
    color: {65};
    border: 1px solid {66};
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    min-width: 60px;
    min-height: 34px;
}
QPushButton#btn_dir:hover {
    background: {67};
    border-color: {68};
}
QPushButton#btn_dir[compact="true"] {
    min-width: 0px;
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}
QPushButton[compact="true"] {
    padding: 3px 8px;
    font-size: 11px;
    min-height: 26px;
    border-radius: 5px;
}
QPushButton#btn_assistant {
    background: {69};
    color: {70};
    border: 1px solid {71};
    min-height: 26px;
    padding: 3px 8px;
    font-size: 11px;
    border-radius: 5px;
}
QPushButton#btn_assistant:hover {
    background: {72};
    border-color: {73};
}
QPushButton#btn_assistant:checked {
    background: {74};
    color: {75};
    border: 1px solid {76};
}
QPushButton#activity_btn {
    background: transparent;
    color: {77};
    border: none;
    border-left: 3px solid transparent;
    border-radius: 10px;
    padding: 10px 6px;
    font-size: 11px;
    font-weight: 700;
    text-align: center;
    min-width: 0px;
}
QPushButton#activity_btn:hover {
    background: {78};
    color: {79};
    border-left-color: {80};
}
QPushButton#activity_btn:checked {
    background: {81};
    color: {82};
    border-left-color: {83};
}

/* ── Inputs ─────────────────────────────────────────────────── */
QLineEdit, QComboBox, QDateEdit {
    background: {84};
    border: 1px solid {85};
    border-radius: 6px;
    padding: 6px 10px;
    color: {86};
    font-size: 13px;
    selection-background-color: {87};
    selection-color: {88};
    min-height: 28px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {
    border-color: {89};
    background: {90};
}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover {
    border-color: {91};
}
QTextEdit, QTextBrowser {
    background: {92};
    color: {93};
    border: 1px solid {94};
    border-radius: 8px;
    padding: 8px;
    selection-background-color: {95};
    selection-color: {96};
}
QTextEdit:focus, QTextBrowser:focus {
    border-color: {97};
    background: {98};
}
QTextBrowser#chat_transcript {
    font-size: 13px;
    line-height: 1.35;
}
QTextEdit#chat_input {
    font-size: 13px;
    min-height: 58px;
    background: {99};
    border: 1px solid {100};
    border-radius: 8px;
}
QFrame#assistant_toolbar, QFrame#assistant_composer {
    background: {101};
    border: 1px solid {102};
    border-radius: 8px;
}
QFrame#assistant_composer {
    margin-top: 4px;
}
QFrame#assistant_quick_actions {
    background: transparent;
    border: none;
}
QLabel#assistant_title {
    color: {103};
    font-size: 17px;
    font-weight: 700;
}
QLabel#assistant_status {
    color: {104};
    font-size: 11px;
    font-weight: 600;
}
QComboBox#chat_model {
    min-height: 30px;
    background: {105};
    border: 1px solid {106};
    border-radius: 8px;
    color: {107};
    padding: 4px 8px;
}
QPushButton#assistant_chip {
    background: {108};
    color: {109};
    border: 1px solid {110};
    border-radius: 6px;
    padding: 5px 10px;
    min-height: 28px;
    min-width: 0px;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#assistant_chip:hover {
    background: {111};
    border-color: {112};
    color: {113};
}
QPushButton#assistant_chip:pressed {
    background: {114};
}
QPushButton#assistant_send {
    background: {115};
    color: {116};
    border: 1px solid {117};
    border-radius: 8px;
    min-height: 32px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#assistant_send:hover {
    background: {118};
    border-color: {119};
}
QPushButton#assistant_stop {
    background: {30};
    color: {31};
    border: 1px solid {32};
    border-radius: 8px;
    min-height: 32px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#assistant_stop:hover {
    background: {33};
    border-color: {34};
}
QScrollArea#assistant_history_scroll {
    background: {120};
    border: none;
    border-radius: 0px;
}
QWidget#assistant_history_host {
    background: {122};
}
QWidget#chat_row {
    background: transparent;
    border: none;
}
QFrame#chat_bubble_user {
    background: {123};
    border: 1px solid {124};
    border-radius: 8px;
}
QFrame#chat_bubble_assistant {
    background: {125};
    border: 1px solid {126};
    border-radius: 8px;
}
QFrame#chat_bubble_system {
    background: {127};
    border: 1px solid {128};
    border-radius: 8px;
}
QFrame#chat_bubble_thinking {
    background: {127};
    border: 1px dashed {128};
    border-radius: 8px;
}
QFrame#chat_bubble_error {
    background: {129};
    border: 1px solid {130};
    border-radius: 8px;
}
QFrame#chat_empty_state {
    background: transparent;
    border: none;
}
QFrame#chat_api_banner {
    background: {129};
    border: 1px solid {130};
    border-radius: 6px;
    margin: 4px 0;
}
QLabel#chat_meta_user {
    color: {131};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_meta_assistant {
    color: {132};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_meta_system {
    color: {133};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_meta_error {
    color: {134};
    font-size: 11px;
    font-weight: 700;
}
QLabel#chat_text {
    color: {135};
    font-size: 13px;
    line-height: 1.4;
}
QLabel#chat_code {
    color: {136};
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 12px;
    background: {137};
    border: 1px solid {138};
    border-radius: 8px;
    padding: 6px;
}
QLabel#chat_table {
    color: {139};
    font-size: 12px;
    background: {140};
    border: 1px solid {141};
    border-radius: 6px;
}
QFrame#tool_card {
    background: {142};
    border: 1px solid {143};
    border-radius: 8px;
    margin: 6px 0px;
}
QFrame#tool_card_error {
    background: {144};
    border: 1px solid {145};
    border-radius: 8px;
    margin: 2px 0px;
}
QFrame#tool_detail {
    background: transparent;
    border: none;
    margin-top: 4px;
}
QFrame#tool_kv {
    background: {146};
    border: 1px solid {147};
    border-radius: 6px;
    padding: 4px;
}
QFrame#tool_metrics {
    background: transparent;
    border: none;
}
QLabel#tool_title {
    color: {148};
    font-size: 13px;
    font-weight: 800;
}
QLabel#tool_status {
    color: {149};
    font-size: 11px;
    font-weight: 700;
}
QLabel#tool_status_error, QLabel#tool_error {
    color: {150};
    font-size: 12px;
    font-weight: 700;
}
QLabel#tool_section {
    color: {151};
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#tool_body, QLabel#tool_kv_value {
    color: {152};
    font-size: 12px;
}
QLabel#tool_kv_key, QLabel#tool_metric_label {
    color: {153};
    font-size: 11px;
    font-weight: 700;
}
QLabel#tool_metric_value {
    color: {154};
    font-size: 14px;
    font-weight: 800;
}
QFrame#tool_metric {
    background: {155};
    border: 1px solid {156};
    border-radius: 8px;
}
QTableWidget#tool_table {
    background: {157};
    alternate-background-color: {158};
    border: 1px solid {159};
    border-radius: 8px;
    gridline-color: {160};
    color: {161};
}
QTableWidget#tool_table QHeaderView::section {
    background: {162};
    color: {163};
    border-right: 1px solid {164};
    border-bottom: 1px solid {165};
    font-size: 10px;
    font-weight: 800;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}
QComboBox::down-arrow {
    width: 10px;
    height: 10px;
}
QComboBox QAbstractItemView {
    background: {166};
    border: 1px solid {167};
    border-radius: 6px;
    padding: 4px;
    outline: none;
    selection-background-color: {168};
    selection-color: {169};
}

/* ── File list ──────────────────────────────────────────────── */
QListWidget {
    background: {170};
    border: 1px solid {171};
    border-radius: 6px;
    outline: none;
    padding: 2px;
}
QListWidget::item {
    padding: 5px 8px;
    border-radius: 4px;
    margin: 1px 2px;
    color: {172};
    font-family: 'Consolas', 'Cascadia Code', monospace;
    font-size: 11px;
}
QListWidget::item:selected {
    background: {173};
    color: {174};
    border: 1px solid {175};
}
QListWidget::item:hover:!selected {
    background: {176};
    color: {177};
}

/* ── Tables ─────────────────────────────────────────────────── */
QTableView, QTableWidget {
    background: {178};
    alternate-background-color: {179};
    border: 1px solid {180};
    border-radius: 8px;
    gridline-color: {181};
    outline: none;
    selection-background-color: {182};
}
QTableView::item, QTableWidget::item {
    padding: 3px 8px;
    border: none;
}
QTableView::item:selected, QTableWidget::item:selected {
    background: {183};
    color: {184};
}
QHeaderView {
    background: transparent;
}
QHeaderView::section {
    background: {185};
    color: {186};
    border: none;
    border-right: 1px solid {187};
    border-bottom: 2px solid {188};
    padding: 8px 10px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.6px;
}
QHeaderView::section:first {
    border-top-left-radius: 6px;
}
QHeaderView::section:hover {
    background: {189};
    color: {190};
}
QHeaderView::section:checked {
    color: {191};
}

/* ── Scrollbars ─────────────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: {192};
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: {193};
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: {194};
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: {195};
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}

/* ── Status bar ─────────────────────────────────────────────── */
QStatusBar {
    background: {196};
    color: {197};
    border-top: 1px solid {198};
    font-size: 11px;
    padding: 2px 8px;
}
QStatusBar::item {
    border: none;
}

/* ── Labels ─────────────────────────────────────────────────── */
QLabel {
    color: {199};
    background: transparent;
}
QLabel#lbl_app_name {
    color: {200};
    font-size: 15px;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QLabel#lbl_app_ver {
    color: {201};
    font-size: 11px;
}
QLabel#lbl_workspace_tag {
    color: {202};
    background: {203};
    border: 1px solid {204};
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
}
QLabel#lbl_section {
    color: {205};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
}
QLabel#activity_brand {
    color: {206};
    background: {207};
    border: 1px solid {208};
    border-radius: 12px;
    font-size: 12px;
    font-weight: 800;
    padding: 10px 0;
}
QLabel#sidebar_brand {
    color: {209};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.9px;
}
QLabel#sidebar_title {
    color: {210};
    font-size: 18px;
    font-weight: 700;
}
QLabel#sidebar_body {
    color: {211};
    font-size: 12px;
}
QLabel#workspace_card_title {
    color: {212};
    font-size: 12px;
    font-weight: 700;
}
QLabel#lbl_green {
    color: {213};
    font-weight: 600;
    font-size: 12px;
}
QFrame#workspace_card {
    background: {214};
    border: 1px solid {215};
    border-radius: 10px;
}
/* ── Progress bar ───────────────────────────────────────────── */
QProgressBar {
    border: 1px solid {216};
    border-radius: 6px;
    background: {217};
    text-align: center;
    color: transparent;
    min-height: 12px;
    max-height: 12px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 {218}, stop:1 {219});
    border-radius: 5px;
}

/* ── Splitter ───────────────────────────────────────────────── */
QSplitter::handle {
    background: {220};
}
QSplitter::handle:horizontal {
    width: 1px;
}
QSplitter::handle:vertical {
    height: 1px;
}

/* ── Calendar ───────────────────────────────────────────────── */
QCalendarWidget {
    background: {221};
    border: 1px solid {222};
    border-radius: 8px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background: {223};
    border-bottom: 1px solid {224};
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 4px 8px;
    min-height: 36px;
}
QCalendarWidget QToolButton {
    background: transparent;
    color: {225};
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 13px;
    font-weight: 600;
}
QCalendarWidget QToolButton:hover {
    background: {226};
    border-color: {227};
    color: {228};
}
QCalendarWidget QToolButton:pressed {
    background: {229};
}
QCalendarWidget QToolButton#qt_calendar_prevmonth,
QCalendarWidget QToolButton#qt_calendar_nextmonth {
    min-width: 28px;
    min-height: 28px;
    border-radius: 14px;
    qproperty-icon: none;
    font-size: 14px;
    color: {230};
}
QCalendarWidget QToolButton#qt_calendar_prevmonth { qproperty-text: "<"; }
QCalendarWidget QToolButton#qt_calendar_nextmonth { qproperty-text: ">"; }
QCalendarWidget QToolButton#qt_calendar_prevmonth:hover,
QCalendarWidget QToolButton#qt_calendar_nextmonth:hover {
    background: {231};
    border-color: {232};
}
QCalendarWidget QSpinBox {
    background: {233};
    color: {234};
    border: 1px solid {235};
    border-radius: 5px;
    padding: 2px 6px;
    font-size: 13px;
    font-weight: 600;
    selection-background-color: {236};
    selection-color: {237};
}
QCalendarWidget QSpinBox::up-button,
QCalendarWidget QSpinBox::down-button {
    subcontrol-origin: border;
    width: 18px;
    background: {238};
    border: none;
}
QCalendarWidget QSpinBox::up-button:hover,
QCalendarWidget QSpinBox::down-button:hover {
    background: {239};
}

/* Day grid */
QCalendarWidget QAbstractItemView {
    background: {240};
    color: {241};
    font-size: 13px;
    outline: none;
    selection-background-color: {242};
    selection-color: {243};
    border: none;
    padding: 2px;
}
QCalendarWidget QAbstractItemView:enabled {
    color: {244};
}
QCalendarWidget QAbstractItemView:disabled {
    color: {245};
}

/* Header row (day names) */
QCalendarWidget QWidget { alternate-background-color: {246}; }
QCalendarWidget QHeaderView::section {
    background: {247};
    color: {248};
    border: none;
    border-bottom: 1px solid {249};
    padding: 6px 4px;
    font-size: 11px;
    font-weight: 700;
}

/* SpinBox in calendar (year) */
QCalendarWidget QMenu {
    background: {250};
    border: 1px solid {251};
    border-radius: 6px;
    color: {252};
    padding: 4px;
}
QCalendarWidget QMenu::item:selected {
    background: {253};
    color: {254};
}

/* ── Tab widget ────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background: {255};
}
QTabBar::tab {
    background: {256};
    color: {257};
    border: 1px solid {258};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 20px;
    margin-right: 2px;
    font-size: 12px;
    font-weight: 600;
}
QTabBar::tab:selected {
    background: {259};
    color: {260};
    border-color: {261};
}
QTabBar::tab:hover:!selected {
    background: {262};
    color: {263};
}

/* ── BDT Detail Panel — Command Console aesthetic ─────────── */
QWidget#bdt_detail_panel {
    background: {264};
}
QFrame#bdt_info_frame {
    background: {265};
    border: 1px solid {266};
    border-radius: 8px;
    padding: 4px;
}
QLabel#bdt_info_key {
    color: {267};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_info_val {
    color: {268};
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    background: transparent;
    padding: 2px 0;
}
QLabel#bdt_section_title {
    color: {269};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    background: transparent;
    padding: 2px 0 2px 0;
}
QLabel#bdt_empty_hint {
    color: {270};
    font-size: 10px;
    font-style: italic;
    background: transparent;
    padding: 2px 2px 6px 2px;
}

/* "PREVIOUS TEST — yyyy-MM-dd" separator inside the photo scroll.
   Stronger weight and an accent-colored top border so the user
   instantly sees where a historical test starts. */
QLabel#bdt_history_separator {
    color: {271};
    background: {272};
    border: 1px solid {273};
    border-top: 2px solid {274};
    border-radius: 6px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
    padding: 8px 12px;
    margin-top: 14px;
    margin-bottom: 4px;
}

/* ── BDT Photo Gallery ────────────────────────────────────── */
QScrollArea#bdt_photo_scroll {
    background: {275};
    border: 1px solid {276};
    border-radius: 6px;
}
QScrollArea#bdt_info_scroll {
    background: transparent;
    border: none;
}
QScrollArea#bdt_info_scroll > QWidget > QWidget {
    background: transparent;
}
QWidget#bdt_photo_container {
    background: {277};
}
QFrame#bdt_photo_card {
    background: {278};
    border: 1px solid {279};
    border-radius: 6px;
    padding: 4px;
}
QLabel#bdt_photo_label {
    color: {280};
    font-size: 10px;
    font-weight: 600;
    background: transparent;
    padding: 2px 0 0 0;
}
QLabel#bdt_photo_meta {
    color: {281};
    font-size: 9px;
    font-weight: 500;
    background: transparent;
    padding: 1px 4px 2px 4px;
}
QFrame#bdt_photo_missing {
    background: {282};
    border: 2px dashed {283};
    border-radius: 6px;
    min-height: 120px;
}
QLabel#bdt_photo_missing_label {
    color: {284};
    font-size: 11px;
    font-weight: 600;
    background: transparent;
}

/* ═══════════════════════════════════════════════════════════════ */
/*  FILTER PANEL — Command Console aesthetic                       */
/*  Info-dense NOC look: thin borders, accent rails, uppercase     */
/*  section caps, phosphor focus glow.                             */
/* ═══════════════════════════════════════════════════════════════ */

/* Outer panel — replaces the old GroupBox */
QFrame#filter_panel {
    background: {285};
    border: 1px solid {286};
    border-top: 1px solid {287};
    border-radius: 10px;
}

/* Tiny uppercase section cap label ("SITE", "CLASSIFICATION"…) */
QLabel#filter_section {
    color: {288};
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.6px;
    background: transparent;
    padding: 0 0 2px 0;
}
QLabel#filter_section_active {
    color: {289};
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.6px;
    background: transparent;
    padding: 0 0 2px 0;
}

/* Subtle grouping container — no heavy box, just a lighter tint */
QFrame#filter_group {
    background: {290};
    border: 1px solid {291};
    border-radius: 8px;
}
QFrame#filter_group_date {
    background: {292};
    border: 1px solid {293};
    border-left: 2px solid {294};
    border-radius: 8px;
}

/* Vertical accent rail — 2px stripe that marks a group as "active" */
QFrame#filter_rail {
    background: {295};
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}
QFrame#filter_rail_active {
    background: {296};
    border: none;
    max-width: 2px;
    min-width: 2px;
    border-radius: 1px;
}

/* Inline label inside a group — muted, small, fixed weight */
QLabel#filter_inline {
    color: {297};
    font-size: 11px;
    font-weight: 500;
    background: transparent;
    padding: 0 2px;
}

/* Refined inputs — lighter surface, thin border, blue focus glow */
QLineEdit#filter_input {
    background: {298};
    border: 1px solid {299};
    border-radius: 6px;
    padding: 7px 11px;
    color: {300};
    font-size: 13px;
    font-weight: 500;
    selection-background-color: {301};
    selection-color: {302};
    min-height: 26px;
}
QLineEdit#filter_input:hover {
    border-color: {303};
    background: {304};
}
QLineEdit#filter_input:focus {
    border-color: {305};
    background: {306};
}
QLineEdit#filter_input:disabled {
    background: {307};
    color: {308};
    border-color: {309};
}

/* Compact combo */
QComboBox#filter_combo {
    background: {310};
    border: 1px solid {311};
    border-radius: 6px;
    padding: 6px 10px;
    padding-right: 24px;
    color: {312};
    font-size: 12px;
    font-weight: 600;
    min-height: 26px;
}
QComboBox#filter_combo:hover {
    border-color: {313};
    background: {314};
}
QComboBox#filter_combo:focus, QComboBox#filter_combo:on {
    border-color: {315};
    background: {316};
}
QComboBox#filter_combo::drop-down {
    border: none;
    width: 20px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}

/* Compact date picker inside filter panel */
QDateEdit#filter_date {
    background: {317};
    border: 1px solid {318};
    border-radius: 6px;
    padding: 6px 10px;
    color: {319};
    font-size: 12px;
    font-weight: 600;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QDateEdit#filter_date:hover {
    border-color: {320};
    background: {321};
}
QDateEdit#filter_date:focus {
    border-color: {322};
    background: {323};
}
QDateEdit#filter_date:disabled {
    background: {324};
    color: {325};
    border-color: {326};
}

/* Numeric spin inside filter panel */
QSpinBox#filter_spin {
    background: {327};
    border: 1px solid {328};
    border-radius: 6px;
    padding: 6px 8px;
    color: {329};
    font-size: 12px;
    font-weight: 700;
    font-family: 'SF Mono', 'Consolas', 'Cascadia Code', monospace;
    min-height: 26px;
}
QSpinBox#filter_spin:focus {
    border-color: {330};
    background: {331};
}
QSpinBox#filter_spin:disabled {
    color: {332};
    border-color: {333};
}

/* Toggle-style checkbox — larger, accent fill when checked */
QCheckBox#filter_toggle {
    color: {334};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    background: transparent;
    spacing: 7px;
    padding: 2px 0;
}
QCheckBox#filter_toggle:disabled {
    color: {335};
}
QCheckBox#filter_toggle::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {336};
    background: {337};
}
QCheckBox#filter_toggle::indicator:hover {
    border-color: {338};
}
QCheckBox#filter_toggle::indicator:checked {
    background: {339};
    border: 1px solid {340};
    image: none;
}
QCheckBox#filter_toggle::indicator:disabled {
    background: {341};
    border-color: {342};
}

/* Pill-shaped quick-pick button */
QPushButton#btn_pill {
    background: {343};
    color: {344};
    border: 1px solid {345};
    border-radius: 12px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-width: 0;
    min-height: 22px;
}
QPushButton#btn_pill:hover {
    background: {346};
    color: {347};
    border-color: {348};
}
QPushButton#btn_pill:pressed {
    background: {349};
    color: {350};
    border-color: {351};
}
QPushButton#btn_pill:disabled {
    background: {352};
    color: {353};
    border-color: {354};
}

/* "Add" accent button for specific-days input */
QPushButton#btn_pill_accent {
    background: {355};
    color: {356};
    border: 1px solid {357};
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    min-height: 22px;
}
QPushButton#btn_pill_accent:hover {
    background: {358};
    color: {359};
    border-color: {360};
}
QPushButton#btn_pill_accent:disabled {
    background: {361};
    color: {362};
    border-color: {363};
}

/* Ghost clear button */
QPushButton#btn_ghost {
    background: transparent;
    color: {364};
    border: 1px solid {365};
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
    min-height: 22px;
}
QPushButton#btn_ghost:hover {
    color: {366};
    border-color: {367};
    background: {368};
}
QPushButton#btn_ghost:disabled {
    color: {369};
    border-color: {370};
}
/* ── Statistics panel ────────────────────────────────────────── */
QFrame#stats_frame {
    background: {371};
    border: 1px solid {372};
    border-radius: 8px;
}
QLabel#stats_section_label {
    color: {373};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    background: transparent;
}
QLabel#stats_label {
    color: {374};
    font-size: 11px;
    background: transparent;
}
QLabel#stat_total  { color: {375}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_power  { color: {376}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_down   { color: {377}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_door   { color: {378}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_sites  { color: {379}; font-size: 12px; font-weight: bold; background: transparent; }
QLabel#stat_avg_dur { color: {380}; font-size: 12px; font-weight: bold; background: transparent; }
QFrame#stats_sep {
    color: {381};
    background: {382};
    max-height: 1px;
}
"""

STYLE_DARK = _render(_TMPL_DARK, _DARK)
STYLE_LIGHT = _render(_TMPL_LIGHT, _LIGHT)

# Backwards compatibility
STYLE = STYLE_DARK
