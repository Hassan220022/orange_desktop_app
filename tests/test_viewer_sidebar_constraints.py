from types import SimpleNamespace
from datetime import date

from alarm_app.ui.viewer import AlarmViewer
from alarm_app.data.alarm_store import AlarmQuery


class _Stack:
    def __init__(self, current_widget):
        self._current_widget = current_widget

    def currentWidget(self):
        return self._current_widget


class _Splitter:
    def __init__(self, sizes):
        self._sizes = list(sizes)

    def sizes(self):
        return list(self._sizes)

    def setSizes(self, sizes):
        self._sizes = list(sizes)


class _WidthOnly:
    def __init__(self, width):
        self._width = width

    def width(self):
        return self._width


class _Button:
    def __init__(self):
        self.checked = None
        self.text = None

    def setChecked(self, value):
        self.checked = bool(value)

    def setText(self, value):
        self.text = value


def test_min_sidebar_width_uses_current_sidebar_recommendation():
    viewer = SimpleNamespace(
        _sidebar_stack=_Stack(SimpleNamespace(_recommended_min_width=320))
    )

    assert AlarmViewer._min_sidebar_width(viewer) == 320


def test_apply_sidebar_constraints_enforces_open_minimum_width():
    splitter = _Splitter([180, 820])
    viewer = SimpleNamespace(
        _main_splitter=splitter,
        _sidebar=SimpleNamespace(setMinimumWidth=lambda value: None, setMaximumWidth=lambda value: None),
        _sidebar_width=180,
        _min_sidebar_width=lambda: 320,
        _max_sidebar_width=lambda: 400,
    )

    AlarmViewer._apply_sidebar_constraints(viewer)

    assert splitter.sizes() == [320, 680]
    assert viewer._sidebar_width == 320


def test_apply_assistant_constraints_enforces_open_minimum_width():
    splitter = _Splitter([900, 120])
    btn = _Button()
    viewer = SimpleNamespace(
        _content_splitter=splitter,
        _assistant_width=120,
        _assistant_open=True,
        _btn_assistant=btn,
        _assistant_min_width=lambda: 320,
        _assistant_max_width=lambda: 540,
    )

    AlarmViewer._apply_assistant_constraints(viewer)

    assert splitter.sizes() == [700, 320]
    assert viewer._assistant_width == 320
    assert viewer._assistant_open is True
    assert btn.checked is True
    assert btn.text == "Assistant On"


def test_assistant_max_width_caps_to_sixty_percent_of_available_space():
    viewer = SimpleNamespace(
        _content_splitter=_WidthOnly(1000),
    )

    assert AlarmViewer._assistant_max_width(viewer) == 600


def test_set_assistant_panel_open_closes_drawer_and_remembers_width():
    splitter = _Splitter([860, 340])
    btn = _Button()
    viewer = SimpleNamespace(
        _content_splitter=splitter,
        _assistant_width=340,
        _assistant_open=True,
        _btn_assistant=btn,
        _assistant_min_width=lambda: 320,
        _assistant_max_width=lambda: 540,
        _apply_assistant_constraints=lambda: None,
    )

    AlarmViewer._set_assistant_panel_open(viewer, False, persist=False)

    assert splitter.sizes() == [1200, 0]
    assert viewer._assistant_width == 340
    assert viewer._assistant_open is False


def test_expand_backup_time_query_extends_date_window():
    query = AlarmQuery(
        site_text="AAA001",
        date_from=date(2026, 5, 3),
        date_to=date(2026, 5, 3),
        manual_days=[date(2026, 5, 3)],
        limit=10,
        offset=5,
        sort_by="occurred_on",
        sort_desc=True,
    )

    expanded = AlarmViewer._expand_backup_time_query(query)

    assert expanded.limit is None
    assert expanded.offset == 0
    assert expanded.sort_by is None
    assert expanded.sort_desc is False
    assert expanded.date_from == date(2026, 5, 2)
    assert expanded.date_to == date(2026, 5, 4)
    assert expanded.manual_days == [date(2026, 5, 2), date(2026, 5, 3), date(2026, 5, 4)]
