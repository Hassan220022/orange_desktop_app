"""Background worker threads."""

import hashlib
import json
import logging
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
from uuid import uuid4

import pandas as pd

from PyQt5.QtCore import QThread, pyqtSignal

try:
    from ..constants import SCHEMA_1_MAP, SCHEMA_2_MAP, ALL_INTERNAL_COLS
    from ..core.backup_time import compute_backup_times
    from ..core.duration import duration_to_secs as _duration_to_secs
    from ..core.duration import secs_to_hhmmss as _secs_to_hhmmss
    from ..core.classify import classify_by_alarm_id, compute_site_down_flag
    from ..data import loaders as _loaders
    from ..data.loaders import (
        parse_alarm_file,
        deduplicate_alarm_rows,
    )
    from ..data import state
    from ..db.engine import create_engine as _db_create_engine, init_db as _db_init_db, get_session_factory as _db_get_session_factory
    from ..db.hashing import compute_file_sha256
    from ..db.repos.file_repo import file_exists as _file_exists, register_file as _register_file
    from ..db.repos.alarm_repo import bulk_upsert_alarms as _bulk_upsert_alarms
except ImportError:
    try:
        from alarm_app.constants import SCHEMA_1_MAP, SCHEMA_2_MAP, ALL_INTERNAL_COLS
        from alarm_app.core.backup_time import compute_backup_times
        from alarm_app.core.duration import duration_to_secs as _duration_to_secs
        from alarm_app.core.duration import secs_to_hhmmss as _secs_to_hhmmss
        from alarm_app.core.classify import classify_by_alarm_id, compute_site_down_flag
        from alarm_app.data import loaders as _loaders
        from alarm_app.data.loaders import (
            parse_alarm_file,
            deduplicate_alarm_rows,
        )
        from alarm_app.data import state
        from alarm_app.db.engine import create_engine as _db_create_engine, init_db as _db_init_db, get_session_factory as _db_get_session_factory
        from alarm_app.db.hashing import compute_file_sha256
        from alarm_app.db.repos.file_repo import file_exists as _file_exists, register_file as _register_file
        from alarm_app.db.repos.alarm_repo import bulk_upsert_alarms as _bulk_upsert_alarms
    except ImportError:
        from constants import SCHEMA_1_MAP, SCHEMA_2_MAP, ALL_INTERNAL_COLS
        from core.backup_time import compute_backup_times
        from core.duration import duration_to_secs as _duration_to_secs
        from core.duration import secs_to_hhmmss as _secs_to_hhmmss
        from core.classify import classify_by_alarm_id, compute_site_down_flag
        from data import loaders as _loaders
        from data.loaders import (
            parse_alarm_file,
            deduplicate_alarm_rows,
        )
        from data import state
        from db.engine import create_engine as _db_create_engine, init_db as _db_init_db, get_session_factory as _db_get_session_factory
        from db.hashing import compute_file_sha256
        from db.repos.file_repo import file_exists as _file_exists, register_file as _register_file
        from db.repos.alarm_repo import bulk_upsert_alarms as _bulk_upsert_alarms

_log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Background loader thread
# ─────────────────────────────────────────────────────────────────
class LoaderThread(QThread):
    """Load selected files in a background thread.

    Signals:
        progress(int, str)  — percentage + status message
        finished(DataFrame, str) — merged data + summary message
        error(str) — traceback on failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, str)
    error    = pyqtSignal(str)

    def __init__(self, file_infos: list[dict]):
        super().__init__()
        self.file_infos = file_infos

    def run(self):
        try:
            dfs: list[pd.DataFrame] = []
            total = len(self.file_infos)
            file_paths = [info.get("path", "") for info in self.file_infos if info.get("path")]

            # Open a thread-local DB session for dedup checks.
            # If DB init fails, proceed without dedup (best-effort).
            db_session = None
            try:
                _engine = _db_create_engine()
                _db_init_db(_engine)
                _factory = _db_get_session_factory(_engine)
                db_session = _factory()
            except Exception:
                _log.warning("DB session init failed; file-level dedup disabled", exc_info=True)

            # ── Build parse list (always parse all files for UI display) ──
            # File-level dedup only prevents duplicate DB writes, not parsing.
            # Users expect to see their data after loading regardless of prior imports.
            _already_imported: set[str] = set()
            infos_to_parse: list[tuple[int, dict]] = []
            ordered = sorted(
                enumerate(self.file_infos),
                key=lambda t: t[1].get("size_kb", 0),
                reverse=True,
            )
            for idx, info in ordered:
                fp = info.get("path", "")
                if db_session and fp and os.path.isfile(fp):
                    try:
                        file_sha = compute_file_sha256(fp)
                        if _file_exists(db_session, file_sha):
                            _already_imported.add(fp)
                    except Exception:
                        _log.warning("File-level dedup check failed for %s", fp, exc_info=True)
                infos_to_parse.append((idx, info))

            workers = min(max(len(infos_to_parse), 1), (os.cpu_count() or 1) * 2, 12)
            done_count = 0
            parse_total = len(infos_to_parse) or 1

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(parse_alarm_file, info): idx
                    for idx, info in infos_to_parse
                }
                for future in as_completed(futures):
                    done_count += 1
                    idx = futures[future]
                    info = self.file_infos[idx]
                    self.progress.emit(
                        10 + int(done_count / parse_total * 80),
                        f"[{done_count}/{parse_total}]  {info['filename']}",
                    )
                    try:
                        df = future.result()
                        if df is not None and not df.empty:
                            dfs.append(df)
                    except Exception:
                        _log.warning("File parse failed: %s", info.get("filename", "unknown"), exc_info=True)

            if not dfs:
                if db_session:
                    try:
                        db_session.close()
                    except Exception:
                        pass
                self.error.emit(
                    "No readable alarm records found in selected files.")
                return

            self.progress.emit(92, "Merging records …")
            combined = pd.concat(dfs, ignore_index=True)

            # Fast vectorised datetime conversion
            for col in ("occurred_on", "cleared_on"):
                if col in combined.columns:
                    combined[col] = pd.to_datetime(
                        combined[col], errors="coerce", format="mixed")

            if "site_id" in combined.columns:
                combined["site_id"] = (
                    combined["site_id"].astype(str).str.strip())

            # Compute duration for records that don't have it (Nokia)
            if "duration" in combined.columns:
                missing_dur = combined["duration"].fillna("").astype(str).str.strip().eq("")
                if missing_dur.any():
                    has_times = (missing_dur
                                 & combined["occurred_on"].notna()
                                 & combined["cleared_on"].notna())
                    if has_times.any():
                        td = combined.loc[has_times, "cleared_on"] - combined.loc[has_times, "occurred_on"]
                        total_secs = td.dt.total_seconds().fillna(0)
                        h = (total_secs // 3600).astype(int)
                        m = ((total_secs % 3600) // 60).astype(int)
                        s = (total_secs % 60).astype(int)
                        combined.loc[has_times, "duration"] = (
                            h.astype(str).str.zfill(2) + ":"
                            + m.astype(str).str.zfill(2) + ":"
                            + s.astype(str).str.zfill(2))

            # Pre-computed duration seconds for fast filtering
            # Handles str "HH:MM:SS", datetime.time, and Timestamp objects
            if "duration" in combined.columns:
                combined["_duration_secs"] = combined["duration"].apply(_duration_to_secs)
                # Normalize duration display to HH:MM:SS strings
                combined["duration"] = combined["_duration_secs"].apply(_secs_to_hhmmss)

            combined, dropped_duplicates = deduplicate_alarm_rows(combined)

            # ── Emit data to UI FIRST so the user sees results immediately ──
            self.progress.emit(95, "Rendering …")
            skip_msg = ""
            duplicate_msg = f"; dropped {dropped_duplicates:,} duplicate row(s)" if dropped_duplicates else ""

            # Close DB session before emitting — we'll open a fresh one
            # for the background persist below.
            if db_session:
                try:
                    db_session.close()
                except Exception:
                    pass
                db_session = None

            self.progress.emit(100, "Done!")
            self.finished.emit(
                combined,
                f"Loaded {len(combined):,} records from {len(dfs)} file(s){skip_msg}{duplicate_msg}",
            )

            # ── Background DB persist: file metadata only ──
            # Alarm rows stay in-memory (DataFrame) and persist via Parquet
            # in state.save_dataframe(). Writing 1.8M rows to SQLite is too
            # slow for the desktop use case. The DB stores file registrations,
            # BDT tests, PM runs, and sync events — not bulk alarm rows.
            try:
                bg_engine = _db_create_engine()
                _db_init_db(bg_engine)
                bg_factory = _db_get_session_factory(bg_engine)
                bg_session = bg_factory()

                for _idx, info in infos_to_parse:
                    fp = info.get("path", "")
                    if fp and fp not in _already_imported and os.path.isfile(fp):
                        try:
                            file_sha = compute_file_sha256(fp)
                            ext = os.path.splitext(fp)[1].lower()
                            source_kind = "alarm_xlsx" if ext in (".xlsx", ".xls") else "alarm_csv"
                            _register_file(
                                bg_session,
                                file_sha256=file_sha,
                                original_path=str(fp),
                                original_name=info.get("filename", os.path.basename(fp)),
                                file_size=os.path.getsize(fp),
                                source_kind=source_kind,
                            )
                        except Exception:
                            _log.warning("File registration failed for %s", fp, exc_info=True)
                            try:
                                bg_session.rollback()
                            except Exception:
                                pass
                try:
                    bg_session.commit()
                except Exception:
                    pass
                bg_session.close()
                _log.info("File registrations persisted to DB")
            except Exception:
                _log.warning("DB file registration failed", exc_info=True)

            # Durable sync journal entries (local outbox) for future cloud migration.
            try:
                file_hashes = state.compute_file_hashes(file_paths)
                for fp, file_sha in file_hashes.items():
                    state.append_outbox_event(
                        entity_type="uploaded_file",
                        entity_local_id=fp,
                        op="upsert",
                        entity_hash=file_sha,
                        payload={
                            "filename": os.path.basename(fp),
                            "file_sha256": file_sha,
                        },
                    )

                batch_payload = {
                    "rows": int(len(combined)),
                    "file_count": int(len(file_hashes)),
                    "dropped_duplicates": int(dropped_duplicates),
                }
                batch_hash = hashlib.sha256(
                    json.dumps(batch_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                state.append_outbox_event(
                    entity_type="alarm_record_batch",
                    entity_local_id=str(uuid4()),
                    op="upsert",
                    entity_hash=batch_hash,
                    payload=batch_payload,
                )
            except Exception:
                pass

        except Exception:
            self.error.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────
# Background export thread
# ─────────────────────────────────────────────────────────────────
class ExportThread(QThread):
    """Write one or more DataFrames to Excel in a background thread.

    Signals:
        progress(int, str)  — percentage + status message
        finished(str)       — file path on success
        error(str)          — error message on failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame | dict[str, pd.DataFrame], path: str):
        super().__init__()
        self._df = df
        self._path = path

    def run(self):
        try:
            self.progress.emit(30, "Writing Excel file …")
            if isinstance(self._df, dict):
                with pd.ExcelWriter(self._path, engine="openpyxl") as writer:
                    total = max(len(self._df), 1)
                    for idx, (sheet_name, df) in enumerate(self._df.items(), start=1):
                        frame = df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)
                        frame.to_excel(writer, sheet_name=sheet_name, index=False)
                        pct = 30 + int(60 * idx / total)
                        self.progress.emit(min(pct, 95), f"Writing sheet: {sheet_name}")
            else:
                self._df.to_excel(self._path, index=False, engine="openpyxl")
            self.progress.emit(100, "Export complete")
            self.finished.emit(self._path)
        except Exception:
            self.error.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────
# BDT validation thread
# ─────────────────────────────────────────────────────────────────
class BDTValidationThread(QThread):
    """Parse and validate BDT files in a background thread.

    Signals:
        progress(int, str) — percentage + status message
        finished(list, dict) — (ValidationResult list, site->BDTData dict)
        error(str)         — error message on failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, object)
    error    = pyqtSignal(str)

    def __init__(self, bdt_files: list[str], alarm_df,
                 tolerance: float, health_pct: float, skip_photos: bool = False):
        super().__init__()
        self._files = bdt_files
        self._alarm_df = alarm_df
        self._tolerance = tolerance
        self._health_pct = health_pct
        self._skip_photos = skip_photos

    @staticmethod
    def _is_invalid_bdt_payload(bdt_data) -> bool:
        parse_errors_lc = [str(e).lower() for e in getattr(bdt_data, "errors", [])]
        hard_file_error = any(
            ("cannot open file" in err) or ("failed to read bdt sheet" in err)
            for err in parse_errors_lc
        )
        no_extractable_data = (
            not getattr(bdt_data, "site_code", "")
            and not getattr(bdt_data, "test_date", None)
            and not getattr(bdt_data, "discharge_readings", [])
            and getattr(bdt_data, "start_voltage", None) is None
            and getattr(bdt_data, "start_ampere", None) is None
        )
        return bool(hard_file_error or no_extractable_data)

    @staticmethod
    def _persist_deferred_photos(photo_jobs: list[dict]) -> None:
        if not photo_jobs:
            return
        try:
            try:
                from alarm_app.bdt.history import persist_photo_jobs
            except ImportError:
                from bdt.history import persist_photo_jobs
            stored = persist_photo_jobs(photo_jobs)
            _log.info("Deferred BDT photo jobs completed: photos=%d", stored)
        except Exception:
            _log.warning("Deferred BDT photo jobs failed", exc_info=True)

    def run(self):
        try:
            from alarm_app.bdt.parser import parse_bdt_file
            from alarm_app.bdt.validator import validate_bdt
        except ImportError:
            from bdt.parser import parse_bdt_file
            from bdt.validator import validate_bdt
        from datetime import datetime

        try:
            total = len(self._files)
            results = []
            by_site: dict[str, list] = {}
            persist_items: list[dict] = []
            done = 0
            summary_lookup = _loaders._load_external_summary_lookup(self._files)

            # xlsx parsing is I/O-bound (zip extraction + XML parse); GIL releases on I/O so more threads help.
            workers = min(total, (os.cpu_count() or 1) * 4, 32)

            def _parse_and_validate(file_path: str):
                bdt_data = parse_bdt_file(file_path, skip_photos=self._skip_photos)
                if self._is_invalid_bdt_payload(bdt_data):
                    return None

                if summary_lookup:
                    matched_summary = _loaders._match_external_summary_row(
                        bdt_data, summary_lookup)
                    if matched_summary:
                        bdt_data.summary_data = matched_summary

                result = validate_bdt(
                    bdt_data, self._alarm_df,
                    self._tolerance, self._health_pct)
                return result, bdt_data

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(_parse_and_validate, fp): fp
                    for fp in self._files
                }
                for future in as_completed(futures):
                    done += 1
                    fp = futures[future]
                    fname = os.path.basename(fp)
                    pct = int(done / total * 90)
                    self.progress.emit(
                        pct, f"[{done}/{total}]  {fname}")

                    try:
                        payload = future.result()
                    except Exception:
                        continue
                    if not payload:
                        self.progress.emit(
                            pct, f"[{done}/{total}]  skipped invalid BDT: {fname}")
                        continue

                    result, bdt_data = payload
                    results.append(result)
                    persist_items.append({
                        "bdt_data": bdt_data,
                        "validation_result": result,
                    })

                    # FR-005 Section 9: structured per-result audit log
                    r1_rule = next(
                        (r for r in getattr(result, "rules", []) if getattr(r, "rule_id", "") == "R1"),
                        None,
                    )
                    overall = getattr(result, "overall", "") or ""
                    _log.info(
                        "BDT validation result: site=%s date=%s overall=%s "
                        "file_path=%s layout_family=%s photo_detection_mode=%s "
                        "photo_mapping_confidence=%s r1_verdict=%s failure_reason_code=%s",
                        getattr(bdt_data, "site_code", "") or "",
                        getattr(bdt_data, "test_date", "") or "",
                        overall,
                        getattr(bdt_data, "file_path", "") or fp,
                        getattr(bdt_data, "core_layout_family", "") or "",
                        getattr(bdt_data, "photo_detection_mode", "") or "",
                        getattr(bdt_data, "photo_mapping_confidence", "") or "",
                        getattr(r1_rule, "verdict", "") if r1_rule else "",
                        overall if overall not in ("Accepted", "") else "",
                    )

                    if bdt_data.site_code:
                        key = bdt_data.site_code.strip().upper()
                        by_site.setdefault(key, []).append(bdt_data)

            self.progress.emit(95, "Sorting results…")

            # Sort each site's tests by date (newest first)
            for key in by_site:
                by_site[key].sort(
                    key=lambda b: b.test_date or datetime.min,
                    reverse=True)

            self.progress.emit(100, "Done!")
            self.finished.emit(results, by_site)

            if persist_items:
                try:
                    try:
                        from alarm_app.bdt.history import save_validation_batch
                    except ImportError:
                        from bdt.history import save_validation_batch
                    run_payloads, photo_jobs, failed_items = save_validation_batch(
                        items=persist_items,
                        alarm_df=self._alarm_df,
                        params={
                            "tolerance": self._tolerance,
                            "health_pct": self._health_pct,
                        },
                    )

                    if run_payloads:
                        outbox_events = []
                        for run_data in run_payloads:
                            outbox_events.append({
                                "entity_type": "pm_run",
                                "entity_local_id": run_data["run_id"],
                                "op": "upsert",
                                "entity_hash": run_data["idempotency_key"],
                                "payload": {
                                    "site_code": run_data["site_code"],
                                    "test_date": run_data["test_date"],
                                    "overall_verdict": run_data["overall_verdict"],
                                    "rule_count": run_data["rule_count"],
                                },
                            })
                        state.append_outbox_events(outbox_events)

                    if failed_items:
                        # FR-005: log each failure with site/date identifiers
                        for fi in failed_items:
                            _log.error(
                                "BDT persistence failure: site=%s date=%s error_type=%s error=%s",
                                fi.get("site_code", ""),
                                fi.get("test_date", ""),
                                fi.get("error_type", ""),
                                fi.get("error_message", ""),
                            )

                    if photo_jobs:
                        Thread(
                            target=self._persist_deferred_photos,
                            args=(photo_jobs,),
                            daemon=True,
                        ).start()
                except Exception:
                    _log.warning("Deferred BDT persistence failed", exc_info=True)

        except Exception:
            self.error.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────
# Backup-time computation thread
# ─────────────────────────────────────────────────────────────────
class BackupTimeThread(QThread):
    """Compute backup times in a background thread.

    Signals:
        progress(int, str)            — percentage + status message
        finished(DataFrame, str)      — result df + error string ('' on success)
        error(str)                    — traceback on unexpected failure
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object, str)
    error    = pyqtSignal(str)

    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self._df = df

    def run(self):
        try:
            self.progress.emit(30, "Computing backup times …")
            result, err = compute_backup_times(self._df)
            self.progress.emit(100, "Done")
            self.finished.emit(result, err)
        except Exception:
            self.error.emit(traceback.format_exc())


# ─────────────────────────────────────────────────────────────────
# Restore-from-cache thread
# ─────────────────────────────────────────────────────────────────
class RestoreThread(QThread):
    """Load cached DataFrame from Parquet in a background thread."""
    finished = pyqtSignal(object)  # DataFrame or None
    error = pyqtSignal(str)

    def run(self):
        try:
            df = state.load_dataframe()
            self.finished.emit(df)
        except Exception as e:
            self.error.emit(str(e))
