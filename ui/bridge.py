"""UIBridge — typed references to all UI widgets, grouped by source panel.

Eliminates 40+ manual bridge assignments in AlarmViewer._build_ui.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt5.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDateEdit,
        QLabel,
        QLineEdit,
        QListWidget,
        QPushButton,
        QSpinBox,
    )


@dataclass(slots=True)
class UIBridge:
    """Typed widget references extracted from UI panels."""

    # ── From LeftPanel ──
    edit_dir: QLineEdit
    lbl_file_count: QLabel
    file_list: QListWidget
    btn_load: QPushButton
    cmb_alarm_source: QComboBox
    lbl_loaded: QLabel
    stats: dict

    # ── From BdtWorkspacePanel ──
    edit_bdt_dir: QLineEdit
    lbl_bdt_file_count: QLabel
    bdt_file_list: QListWidget
    btn_bdt_summary: QPushButton

    # ── From SearchPanel ──
    edit_site: QLineEdit
    cb_cat: QComboBox
    cb_net: QComboBox
    cb_vnd: QComboBox
    chk_mindur: QCheckBox
    spn_mindur: QSpinBox
    chk_date: QCheckBox
    chk_date_range: QCheckBox
    d_from: QDateEdit
    d_to: QDateEdit
    lbl_from: QLabel
    lbl_to: QLabel
    date_quick_widgets: list
    chk_date_days: QCheckBox
    lbl_day: QLabel
    d_day: QDateEdit
    btn_add_day: QPushButton
    edit_days: QLineEdit
    btn_clear_days: QPushButton
    btn_export: QPushButton
    btn_backup: QPushButton
    btn_temp: QPushButton
    btn_site_sheet: QPushButton
    btn_network_summary: QPushButton
    btn_site_report: QPushButton
    btn_both: QPushButton

    @classmethod
    def from_panels(cls, left_panel, search_panel, bdt_sidebar):
        """Create a UIBridge from the three source panels."""
        return cls(
            # LeftPanel
            edit_dir=left_panel.edit_dir,
            lbl_file_count=left_panel.lbl_file_count,
            file_list=left_panel.file_list,
            btn_load=left_panel.btn_load,
            cmb_alarm_source=left_panel.cmb_alarm_source,
            lbl_loaded=left_panel.lbl_loaded,
            stats=left_panel.stats,
            # BdtWorkspacePanel
            edit_bdt_dir=bdt_sidebar.edit_dir,
            lbl_bdt_file_count=bdt_sidebar.lbl_file_count,
            bdt_file_list=bdt_sidebar.file_list,
            btn_bdt_summary=bdt_sidebar.btn_bdt_summary,
            # SearchPanel
            edit_site=search_panel.edit_site,
            cb_cat=search_panel.cb_cat,
            cb_net=search_panel.cb_net,
            cb_vnd=search_panel.cb_vnd,
            chk_mindur=search_panel.chk_mindur,
            spn_mindur=search_panel.spn_mindur,
            chk_date=search_panel.chk_date,
            chk_date_range=search_panel.chk_date_range,
            d_from=search_panel.d_from,
            d_to=search_panel.d_to,
            lbl_from=search_panel.lbl_from,
            lbl_to=search_panel.lbl_to,
            date_quick_widgets=search_panel.date_quick_widgets,
            chk_date_days=search_panel.chk_date_days,
            lbl_day=search_panel.lbl_day,
            d_day=search_panel.d_day,
            btn_add_day=search_panel.btn_add_day,
            edit_days=search_panel.edit_days,
            btn_clear_days=search_panel.btn_clear_days,
            btn_export=search_panel.btn_export,
            btn_backup=search_panel.btn_backup,
            btn_temp=search_panel.btn_temp,
            btn_site_sheet=search_panel.btn_site_sheet,
            btn_network_summary=search_panel.btn_network_summary,
            btn_site_report=search_panel.btn_site_report,
            btn_both=search_panel.btn_both,
        )
