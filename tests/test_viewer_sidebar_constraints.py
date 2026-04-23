from types import SimpleNamespace

from alarm_app.ui.viewer import AlarmViewer


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
