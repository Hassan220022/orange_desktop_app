"""Small wrapping layout for command/tool rows.

Qt's box layouts keep every widget on one line. This layout keeps the same
button sizing semantics but wraps widgets onto new rows when the available
width is too small or the app font is zoomed.
"""

from PyQt5.QtCore import QPoint, QRect, QSize, Qt
from PyQt5.QtWidgets import QLayout, QSizePolicy, QStyle


class FlowLayout(QLayout):
    def __init__(self, parent=None, *, margin: int = 0, hspacing: int = 8, vspacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._hspacing = hspacing
        self._vspacing = vspacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        while self.count():
            self.takeAt(0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _smart_spacing(self, orientation):
        parent = self.parent()
        if parent is None:
            return -1
        if parent.isWidgetType():
            return parent.style().pixelMetric(
                QStyle.PM_LayoutHorizontalSpacing if orientation == Qt.Horizontal else QStyle.PM_LayoutVerticalSpacing,
                None,
                parent,
            )
        return parent.spacing()

    def _do_layout(self, rect, *, test_only):
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            space_x = self._hspacing if self._hspacing >= 0 else self._smart_spacing(Qt.Horizontal)
            space_y = self._vspacing if self._vspacing >= 0 else self._smart_spacing(Qt.Vertical)
            hint = item.sizeHint()
            if widget is not None and widget.sizePolicy().horizontalPolicy() == QSizePolicy.Expanding:
                hint.setWidth(max(hint.width(), item.minimumSize().width()))
            next_x = x + hint.width() + space_x
            if x > effective.x() and next_x - space_x > effective.right() + 1:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + hint.width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + bottom
