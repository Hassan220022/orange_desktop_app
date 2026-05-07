"""Handles save/restore of UI state to/from persistent storage."""

from PyQt5.QtCore import QDate

from alarm_app.data import state


class StateManager:
    """Handles save/restore of UI state to/from persistent storage."""

    @staticmethod
    def collect(viewer) -> dict:
        """Collect ALL UI state from an AlarmViewer into a dict for persistence."""
        ui = viewer._ui
        hdr = viewer._table.horizontalHeader()
        sort_section = hdr.sortIndicatorSection()
        sort_order = int(hdr.sortIndicatorOrder())

        col_filters_json = {}
        for col, vals in viewer._col_filters.items():
            col_filters_json[col] = sorted(vals, key=str) if vals is not None else None

        geo = viewer.geometry()
        file_paths = [info["path"] for info in viewer._file_infos]
        return {
            "directory": ui.edit_dir.text(),
            "uploaded_folder_path": viewer._uploaded_folder_path or ui.edit_dir.text(),
            "bdt_directory": ui.edit_bdt_dir.text(),
            "alarm_load_source": viewer._get_alarm_load_mode(),
            "bdt_load_source": viewer._bdt_validation_panel.cmb_bdt_source.currentData(),
            "workspace_view": viewer._tabs.currentIndex(),
            "file_paths": file_paths,
            "file_hashes": state.compute_file_hashes(file_paths),
            "sync_on": viewer._sync_flags.get("sync_on", False),
            "cloud_read_on": viewer._sync_flags.get("cloud_read_on", False),
            "bootstrap_on": viewer._sync_flags.get("bootstrap_on", False),
            "site_filter": ui.edit_site.text(),
            "date_enabled": ui.chk_date.isChecked(),
            "date_use_range": ui.chk_date_range.isChecked(),
            "date_use_days": ui.chk_date_days.isChecked(),
            "date_from": ui.d_from.date().toString("yyyy-MM-dd"),
            "date_to": ui.d_to.date().toString("yyyy-MM-dd"),
            "date_day": ui.d_day.date().toString("yyyy-MM-dd"),
            "date_days": ui.edit_days.text().strip(),
            "category": ui.cb_cat.currentIndex(),
            "network": ui.cb_net.currentIndex(),
            "vendor": ui.cb_vnd.currentIndex(),
            "dur_enabled": ui.chk_mindur.isChecked(),
            "dur_minutes": ui.spn_mindur.value(),
            "both_pd": viewer._both_pd_active,
            "col_filters": col_filters_json,
            "sort_column": sort_section if sort_section >= 0 else None,
            "sort_order": sort_order,
            "alarm_page_offset": viewer._page_offset,
            "alarm_page_size": viewer._page_size,
            "window_geometry": [geo.x(), geo.y(), geo.width(), geo.height()],
            "ui_zoom_pct": viewer._app_zoom_pct,
            "theme_mode": viewer._theme_mode,
            "skip_photos": viewer._skip_photos,
            # API keys are never persisted in plaintext; caller handles _openrouter_api_key separately
            "chat_model": viewer._chat_panel.model() if hasattr(viewer, "_chat_panel") else "",
            "chat_state": viewer._chat_panel.chat_state() if hasattr(viewer, "_chat_panel") else {},
            "assistant_open": bool(getattr(viewer, "_assistant_open", True)),
            "assistant_width": int(getattr(viewer, "_assistant_width", 420) or 420),
        }

    @staticmethod
    def apply(viewer, saved_state: dict):
        """Restore UI state from a saved dict onto an AlarmViewer."""
        ui = viewer._ui
        s = saved_state

        # Window geometry
        geo = s.get("window_geometry")
        if geo and len(geo) == 4:
            viewer.setGeometry(*geo)
        if "ui_zoom_pct" in s:
            viewer._set_app_zoom(s["ui_zoom_pct"])

        if "theme_mode" in s:
            viewer._theme_mode = s["theme_mode"]
            viewer._update_theme_button_label()
        viewer._skip_photos = bool(s.get("skip_photos", viewer._skip_photos))
        if hasattr(viewer, "_chat_panel"):
            viewer._chat_panel.refresh_settings()
        if "chat_model" in s and hasattr(viewer, "_chat_panel"):
            viewer._chat_panel.set_model(str(s.get("chat_model") or ""))
        if "chat_state" in s and hasattr(viewer, "_chat_panel"):
            viewer._chat_panel.restore_chat_state(s.get("chat_state"))
        if "assistant_width" in s:
            viewer._assistant_width = max(120, min(340, int(s.get("assistant_width") or viewer._assistant_width)))
        if "assistant_open" in s:
            viewer._assistant_open = bool(s.get("assistant_open"))

        workspace_view = int(s.get("workspace_view", 0) or 0)
        viewer._set_workspace_view(workspace_view, persist=False)
        viewer._set_assistant_panel_open(viewer._assistant_open, persist=False)

        # Directory & site filter
        restored_directory = str(s.get("directory") or "")
        viewer._uploaded_folder_path = str(s.get("uploaded_folder_path") or restored_directory or "")
        viewer._bdt_uploaded_folder_path = str(
            s.get("bdt_directory") or viewer._uploaded_folder_path or restored_directory or ""
        )
        if restored_directory:
            ui.edit_dir.setText(restored_directory)
        elif viewer._uploaded_folder_path:
            ui.edit_dir.setText(viewer._uploaded_folder_path)
        if viewer._bdt_uploaded_folder_path:
            ui.edit_bdt_dir.setText(viewer._bdt_uploaded_folder_path)
        alarm_load_source = str(s.get("alarm_load_source") or "directory")
        idx = ui.cmb_alarm_source.findData(alarm_load_source)
        if idx >= 0:
            ui.cmb_alarm_source.setCurrentIndex(idx)
        bdt_load_source = str(s.get("bdt_load_source") or "directory")
        bdt_idx = viewer._bdt_validation_panel.cmb_bdt_source.findData(bdt_load_source)
        if bdt_idx >= 0:
            viewer._bdt_validation_panel.cmb_bdt_source.setCurrentIndex(bdt_idx)
        if s.get("site_filter"):
            ui.edit_site.setText(s["site_filter"])

        # Date filter
        if "date_enabled" in s:
            ui.chk_date.setChecked(s["date_enabled"])
        if s.get("date_from"):
            d = QDate.fromString(s["date_from"], "yyyy-MM-dd")
            if d.isValid():
                ui.d_from.setDate(d)
        if s.get("date_to"):
            d = QDate.fromString(s["date_to"], "yyyy-MM-dd")
            if d.isValid():
                ui.d_to.setDate(d)
        use_range = s.get("date_use_range")
        use_days = s.get("date_use_days")
        if use_range is not None:
            ui.chk_date_range.setChecked(use_range)
        if use_days is not None:
            ui.chk_date_days.setChecked(use_days)
        if use_range is None and use_days is None and "day_only" in s:
            ui.chk_date_range.setChecked(not s["day_only"])
            ui.chk_date_days.setChecked(s["day_only"])
        if s.get("date_day"):
            d = QDate.fromString(s["date_day"], "yyyy-MM-dd")
            if d.isValid():
                ui.d_day.setDate(d)
        if s.get("date_days"):
            ui.edit_days.setText(str(s["date_days"]))
        elif s.get("day_only") and s.get("date_day"):
            ui.edit_days.setText(str(s["date_day"]))
        viewer._toggle_date_mode_controls()

        # Combo filters
        if "category" in s:
            ui.cb_cat.setCurrentIndex(s["category"])
        if "network" in s:
            ui.cb_net.setCurrentIndex(s["network"])
        if "vendor" in s:
            ui.cb_vnd.setCurrentIndex(s["vendor"])

        # Duration filter
        if "dur_enabled" in s:
            ui.chk_mindur.setChecked(s["dur_enabled"])
        if "dur_minutes" in s:
            ui.spn_mindur.setValue(s["dur_minutes"])

        # Both P+D filter
        if s.get("both_pd"):
            viewer._both_pd_active = True
            ui.btn_both.setStyleSheet(
                "QPushButton { background:#4a3018; color:#fab387; "
                "border:2px solid #fab387; border-radius:6px; "
                "padding:7px 16px; font-weight:700; font-size:12px; "
                "min-width:72px; }")

        # Column filters — convert lists back to sets; JSON roundtrips int keys to str
        cf = s.get("col_filters", {})
        for col, vals in cf.items():
            try:
                resolved_col = int(col)
            except (ValueError, TypeError):
                resolved_col = col
            viewer._col_filters[resolved_col] = set(vals) if vals is not None else None

        # Stash sort info for after data loads
        viewer._pending_sort_col = s.get("sort_column")
        viewer._pending_sort_order = s.get("sort_order", 0)
        viewer._page_offset = max(int(s.get("alarm_page_offset", 0) or 0), 0)
        viewer._page_size = max(int(s.get("alarm_page_size", viewer._page_size) or viewer._page_size), 1)
