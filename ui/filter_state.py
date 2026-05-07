"""Shared filter state extracted from AlarmViewer UI widgets.

This module eliminates the ~80% duplicated filter-reading code between
``_apply_filters`` (in-memory DataFrame path) and ``_build_alarm_query``
(DuckDB query path).  Both now consume a single ``FilterState`` dataclass
produced by ``FilterState.from_viewer(viewer)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt

try:
    from alarm_app.core.filters import parse_manual_days
except ImportError:
    from core.filters import parse_manual_days

if TYPE_CHECKING:
    pass


@dataclass(slots=True)
class FilterState:
    """All alarm filter settings read from UI widgets.

    This is the single source of truth for filter criteria,
    shared by the in-memory DataFrame path and the DuckDB query path.
    """

    site_text: str = ""
    category: str = "All"
    vendor: str = "All"
    network_type: str = "All"
    min_duration_secs: float | None = None
    date_from: date | None = None
    date_to: date | None = None
    manual_days: set | None = None
    invalid_manual_days: list[str] = field(default_factory=list)
    both_pd: bool = False
    col_filters: dict[str, set] = field(default_factory=dict)
    sort_by: str | None = None
    sort_desc: bool = False
    limit: int | None = None
    offset: int = 0
    site_scope_keys: set[str] | None = None

    @classmethod
    def from_viewer(cls, viewer) -> FilterState:
        """Read all filter state from an AlarmViewer instance."""
        ui = viewer._ui
        manual_days = None
        invalid_days: list[str] = []
        if ui.chk_date.isChecked() and ui.chk_date_days.isChecked():
            manual_days, invalid_days = parse_manual_days(ui.edit_days.text())

        sort_by = None
        sort_desc = False
        sort_section = viewer._table.horizontalHeader().sortIndicatorSection()
        cols = viewer._current_alarm_columns()
        if 0 <= sort_section < len(cols):
            sort_by = cols[sort_section]
            sort_desc = (
                viewer._table.horizontalHeader().sortIndicatorOrder()
                == Qt.DescendingOrder
            )

        return cls(
            site_text=ui.edit_site.text().strip(),
            category=ui.cb_cat.currentText(),
            vendor=ui.cb_vnd.currentText(),
            network_type=ui.cb_net.currentText(),
            min_duration_secs=(
                ui.spn_mindur.value() * 60
                if ui.chk_mindur.isChecked()
                else None
            ),
            date_from=(
                ui.d_from.date().toPyDate()
                if ui.chk_date.isChecked()
                and ui.chk_date_range.isChecked()
                else None
            ),
            date_to=(
                ui.d_to.date().toPyDate()
                if ui.chk_date.isChecked()
                and ui.chk_date_range.isChecked()
                else None
            ),
            manual_days=manual_days,
            invalid_manual_days=invalid_days,
            both_pd=viewer._both_pd_active,
            col_filters={k: set(v) if v is not None else v for k, v in viewer._col_filters.items()},
            sort_by=sort_by,
            sort_desc=sort_desc,
            site_scope_keys=viewer._uploaded_site_keys if viewer._uploaded_site_keys is not None else None,
        )

    def to_alarm_query(self):
        """Build an ``alarm_store.AlarmQuery`` from this filter state."""
        try:
            from alarm_app.data import alarm_store
        except ImportError:
            from data import alarm_store

        return alarm_store.AlarmQuery(
            site_text=self.site_text,
            category=self.category,
            vendor=self.vendor,
            network_type=self.network_type,
            min_duration_secs=self.min_duration_secs,
            date_from=self.date_from,
            date_to=self.date_to,
            manual_days=list(self.manual_days) if self.manual_days is not None else None,
            both_pd=self.both_pd,
            col_filters=dict(self.col_filters.items()),
            sort_by=self.sort_by,
            sort_desc=self.sort_desc,
            limit=self.limit,
            offset=self.offset,
            site_scope_keys=self.site_scope_keys,
        )
