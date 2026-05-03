"""Guarded local data access for MCP/OpenRouter agents."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
import base64
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import inspect as sa_inspect

try:
    from ..bdt.export import build_bdt_export_sheets
    from ..data import alarm_store, state
    from ..data.site_report import (
        build_pm_accept_report,
        build_site_alarm_report,
        collect_site_sheet_keys,
        infer_site_id_column,
        normalize_site_key,
        read_pm_accept_sheet,
    )
    from ..db import engine as db_engine
    from ..db.models import (
        BDTPhoto,
        BDTTest,
        BlobAsset,
        UploadedFile,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
    )
    from ..db.repos import blob_repo
    from ..db.repos.pm_repo import load_all_validation_results
except ImportError:
    from alarm_app.bdt.export import build_bdt_export_sheets
    from alarm_app.data import alarm_store, state
    from alarm_app.data.site_report import (
        build_pm_accept_report,
        build_site_alarm_report,
        collect_site_sheet_keys,
        infer_site_id_column,
        normalize_site_key,
        read_pm_accept_sheet,
    )
    from alarm_app.db import engine as db_engine
    from alarm_app.db.models import (
        BDTPhoto,
        BDTTest,
        BlobAsset,
        UploadedFile,
        PMRuleCatalog,
        PMRuleResult,
        PMValidationRun,
    )
    from alarm_app.db.repos import blob_repo
    from alarm_app.db.repos.pm_repo import load_all_validation_results


MAX_QUERY_LIMIT = 500
MAX_BLOB_BYTES = 5 * 1024 * 1024
EXPORT_DIR = Path.home() / ".alarm_viewer" / "exports"
ALLOWED_UPLOAD_SUFFIXES = {".csv", ".xls", ".xlsx"}


def _jsonable(value: Any) -> Any:
    if value is pd.NaT:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    if value is not None and not isinstance(value, (list, dict, tuple, set)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value


def _limit(value: Any, default: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(0, min(parsed, MAX_QUERY_LIMIT))


def _date_value(value: Any) -> date | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).date()


def _datetime_value(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).to_pydatetime()


def _safe_export_path(base_dir: Path, name: str, suffix: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name or "export")).strip("._")
    if not stem:
        stem = "export"
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    return base_dir / f"{stem[:80]}{suffix}"


def _safe_source_file_path(path: str | Path) -> Path:
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise ValueError(f"source file not found: {resolved}")
    if resolved.suffix.lower() not in ALLOWED_UPLOAD_SUFFIXES:
        raise ValueError("source_file_path must be a CSV or Excel file")
    return resolved


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].apply(lambda v: None if pd.isna(v) else pd.Timestamp(v).isoformat())
    return [_jsonable(row) for row in safe.to_dict(orient="records")]


class LocalDataService:
    """Read-only app-data facade with controlled export actions."""

    def __init__(self, *, export_dir: Path | None = None):
        self.export_dir = Path(export_dir) if export_dir else EXPORT_DIR

    def list_data_sources(self) -> dict[str, Any]:
        sqlite_tables: list[dict[str, Any]] = []
        sqlite_error = None
        try:
            engine = db_engine.create_engine()
            with engine.connect() as conn:
                inspector = sa_inspect(conn)
                for table in inspector.get_table_names():
                    try:
                        count = conn.exec_driver_sql(f'SELECT COUNT(*) FROM "{table}"').scalar()
                    except Exception:
                        count = None
                    sqlite_tables.append({"name": table, "rows": count})
        except Exception as exc:
            sqlite_error = str(exc)

        alarm_paths = [state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE]
        duckdb_sources = []
        for path in alarm_paths:
            exists = Path(path).exists()
            row_count = 0
            duckdb_error = None
            if exists:
                previous = alarm_store.ALARM_DB_FILE
                try:
                    alarm_store.set_alarm_db_file(path)
                    row_count = alarm_store.count_alarms(alarm_store.AlarmQuery())
                except Exception as exc:
                    row_count = None
                    duckdb_error = str(exc)
                finally:
                    alarm_store.set_alarm_db_file(previous)
            duckdb_sources.append({
                "path": str(path),
                "exists": exists,
                "rows": row_count,
                "error": duckdb_error,
                "modified": datetime.fromtimestamp(Path(path).stat().st_mtime).isoformat() if exists else None,
            })

        return {
            "sqlite": {
                "path": str(db_engine.DB_PATH),
                "exists": Path(db_engine.DB_PATH).exists(),
                "tables": sqlite_tables,
                "error": sqlite_error,
            },
            "duckdb": duckdb_sources,
            "blob_storage": {
                "path": str(blob_repo.BLOB_DIR),
                "exists": Path(blob_repo.BLOB_DIR).exists(),
            },
            "exports": str(self.export_dir),
        }

    def get_current_time(self) -> dict[str, Any]:
        local_now = datetime.now().astimezone()
        utc_now = datetime.now(timezone.utc)
        return {
            "local_time": local_now.isoformat(timespec="seconds"),
            "utc_time": utc_now.isoformat(timespec="seconds"),
            "timezone": local_now.tzname() or "local",
        }

    def _with_alarm_source(self, fn):
        previous = alarm_store.ALARM_DB_FILE
        last_result = None
        last_error: Exception | None = None
        for path in (state.ALARM_DB_FILE, state.ALARM_DB_FALLBACK_FILE):
            if not Path(path).exists():
                continue
            try:
                alarm_store.set_alarm_db_file(path)
                result = fn()
                last_result = result
                if isinstance(result, pd.DataFrame):
                    if not result.empty:
                        return result
                elif isinstance(result, dict):
                    if int(result.get("total") or result.get("row_count") or 0) > 0:
                        return result
                elif result:
                    return result
            except Exception as exc:
                last_error = exc
                continue
            finally:
                alarm_store.set_alarm_db_file(previous)
        if last_result is not None:
            return last_result
        try:
            return fn()
        except Exception:
            if last_error is not None:
                raise last_error
            raise

    def query_alarms(self, **kwargs) -> dict[str, Any]:
        q = alarm_store.AlarmQuery(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_id") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
            sort_by=str(kwargs.get("sort_by") or "occurred_on"),
            sort_desc=bool(kwargs.get("sort_desc", False)),
            limit=_limit(kwargs.get("limit"), default=100),
            offset=max(int(kwargs.get("offset") or 0), 0),
        )
        df = self._with_alarm_source(lambda: alarm_store.query_alarms(q))
        return {"rows": _df_records(df), "row_count": len(df)}

    def alarm_stats(self, **kwargs) -> dict[str, Any]:
        q = alarm_store.AlarmQuery(
            site_text=str(kwargs.get("site_text") or kwargs.get("site_id") or ""),
            category=str(kwargs.get("category") or "All"),
            vendor=str(kwargs.get("vendor") or "All"),
            network_type=str(kwargs.get("network_type") or "All"),
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        return self._with_alarm_source(lambda: alarm_store.stats(q)) or alarm_store.stats(q)

    def query_bdt_results(self, **kwargs) -> dict[str, Any]:
        limit = _limit(kwargs.get("limit"), default=100)
        offset = max(int(kwargs.get("offset") or 0), 0)
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        overall = str(kwargs.get("overall") or "").strip()
        rule_id = str(kwargs.get("rule_id") or "").strip().upper()
        rule_verdict = str(kwargs.get("rule_verdict") or "").strip()
        date_from = _date_value(kwargs.get("date_from"))
        date_to = _date_value(kwargs.get("date_to"))

        session = db_engine.get_session()
        try:
            query = (
                session.query(PMValidationRun, BDTTest)
                .join(BDTTest, PMValidationRun.bdt_test_id == BDTTest.id)
                .order_by(PMValidationRun.run_at.desc())
            )
            if site_code:
                query = query.filter(BDTTest.site_code == site_code)
            if overall:
                query = query.filter(PMValidationRun.overall_verdict == overall)
            if date_from:
                query = query.filter(BDTTest.test_date >= date_from)
            if date_to:
                query = query.filter(BDTTest.test_date <= date_to)
            if rule_id or rule_verdict:
                query = query.join(PMRuleResult, PMRuleResult.validation_run_id == PMValidationRun.id)
                if rule_id:
                    query = query.join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                    query = query.filter(PMRuleCatalog.rule_code == rule_id)
                if rule_verdict:
                    query = query.filter(PMRuleResult.verdict == rule_verdict)

            total = query.count()
            rows = []
            for run, bdt in query.offset(offset).limit(limit).all():
                rows.append({
                    "validation_run_id": run.id,
                    "bdt_test_id": bdt.id,
                    "site_code": bdt.site_code,
                    "test_date": bdt.test_date,
                    "filename": self._filename_for_bdt(session, bdt),
                    "overall_verdict": run.overall_verdict,
                    "run_at": run.run_at,
                    "discharge_minutes": bdt.discharge_minutes,
                    "battery_brand": bdt.battery_brand,
                    "num_strings": bdt.num_strings,
                    "end_voltage": bdt.end_voltage,
                })
            return {"total": total, "rows": _jsonable(rows)}
        finally:
            session.close()

    def get_bdt_detail(self, **kwargs) -> dict[str, Any]:
        run_id = kwargs.get("validation_run_id")
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        test_date = _date_value(kwargs.get("test_date"))
        session = db_engine.get_session()
        try:
            query = session.query(PMValidationRun, BDTTest).join(
                BDTTest,
                PMValidationRun.bdt_test_id == BDTTest.id,
            )
            if run_id:
                query = query.filter(PMValidationRun.id == int(run_id))
            elif site_code:
                query = query.filter(BDTTest.site_code == site_code)
                if test_date:
                    query = query.filter(BDTTest.test_date == test_date)
            else:
                return {"error": "validation_run_id or site_code is required"}
            run, bdt = query.order_by(PMValidationRun.run_at.desc()).first() or (None, None)
            if not run or not bdt:
                return {"error": "BDT validation result not found"}

            rules = []
            for rr, catalog in (
                session.query(PMRuleResult, PMRuleCatalog)
                .join(PMRuleCatalog, PMRuleResult.rule_id == PMRuleCatalog.id)
                .filter(PMRuleResult.validation_run_id == run.id)
                .order_by(PMRuleCatalog.rule_code.asc())
                .all()
            ):
                detail = rr.evidence_json
                try:
                    detail = json.loads(detail) if detail else ""
                except (TypeError, json.JSONDecodeError):
                    pass
                rules.append({
                    "rule_code": catalog.rule_code,
                    "rule_name": catalog.name,
                    "verdict": rr.verdict,
                    "detail": detail,
                })

            return _jsonable({
                "validation_run_id": run.id,
                "overall_verdict": run.overall_verdict,
                "run_at": run.run_at,
                "bdt": {
                    "id": bdt.id,
                    "filename": self._filename_for_bdt(session, bdt),
                    "site_code": bdt.site_code,
                    "site_name": bdt.site_name,
                    "test_date": bdt.test_date,
                    "time_in": bdt.time_in,
                    "time_out": bdt.time_out,
                    "battery_brand": bdt.battery_brand,
                    "battery_ah": bdt.battery_ah,
                    "battery_voltage": bdt.battery_voltage,
                    "num_strings": bdt.num_strings,
                    "num_batteries": bdt.num_batteries,
                    "num_modules": bdt.num_modules,
                    "start_voltage": bdt.start_voltage,
                    "end_voltage": bdt.end_voltage,
                    "discharge_minutes": bdt.discharge_minutes,
                    "discharge_readings": json.loads(bdt.discharge_readings_json or "[]"),
                    "string_discharge_readings": json.loads(bdt.string_discharge_readings_json or "[]"),
                },
                "rules": rules,
                "photos": self._photo_rows_for_bdt(session, bdt.id),
            })
        finally:
            session.close()

    def get_photo_metadata(self, **kwargs) -> dict[str, Any]:
        site_code = str(kwargs.get("site_code") or "").strip().upper()
        bdt_test_id = kwargs.get("bdt_test_id")
        limit = _limit(kwargs.get("limit"), default=100)
        session = db_engine.get_session()
        try:
            query = (
                session.query(BDTPhoto, BDTTest, BlobAsset)
                .join(BDTTest, BDTPhoto.bdt_test_id == BDTTest.id)
                .outerjoin(BlobAsset, BDTPhoto.blob_asset_id == BlobAsset.id)
            )
            if bdt_test_id:
                query = query.filter(BDTPhoto.bdt_test_id == int(bdt_test_id))
            if site_code:
                query = query.filter(BDTTest.site_code == site_code)
            rows = []
            for photo, bdt, blob in query.order_by(BDTTest.test_date.desc(), BDTPhoto.slot_index.asc()).limit(limit).all():
                rows.append(self._photo_row(photo, bdt, blob))
            return {"rows": _jsonable(rows), "row_count": len(rows)}
        finally:
            session.close()

    def read_photo_blob(self, **kwargs) -> dict[str, Any]:
        sha256 = str(kwargs.get("sha256") or "").strip()
        if not sha256:
            return {"error": "sha256 is required"}
        session = db_engine.get_session()
        try:
            blob = session.query(BlobAsset).filter(BlobAsset.sha256 == sha256).first()
            if not blob or not blob.local_path:
                return {"error": "blob not found"}
            path = Path(blob.local_path)
            if not path.exists():
                return {"error": "blob file missing"}
            if path.stat().st_size > MAX_BLOB_BYTES:
                return {"error": f"blob too large; max {MAX_BLOB_BYTES} bytes"}
            return {
                "sha256": blob.sha256,
                "mime_type": blob.mime_type or "application/octet-stream",
                "base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        finally:
            session.close()

    def get_site_dossier(self, **kwargs) -> dict[str, Any]:
        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        if not site_code:
            return {"error": "site_code is required"}
        alarm_df = self._alarm_rows_for_sites(
            {site_code},
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        bdt_payload = self.query_bdt_results(
            site_code=site_code,
            date_from=kwargs.get("date_from"),
            date_to=kwargs.get("date_to"),
            limit=MAX_QUERY_LIMIT,
        )
        bdt_rows = bdt_payload.get("rows", []) if isinstance(bdt_payload, dict) else []
        bdt_details = []
        for row in bdt_rows[:_limit(kwargs.get("bdt_detail_limit"), default=MAX_QUERY_LIMIT)]:
            if isinstance(row, dict) and row.get("validation_run_id"):
                bdt_details.append(self.get_bdt_detail(validation_run_id=row["validation_run_id"]))

        export_path = self._export_site_dossier_workbook(
            site_code=site_code,
            alarm_df=alarm_df,
            bdt_rows=[row for row in bdt_rows if isinstance(row, dict)],
            bdt_details=[detail for detail in bdt_details if isinstance(detail, dict) and "error" not in detail],
        )

        return {
            "site_code": site_code,
            "alarm_total": len(alarm_df),
            "alarm_stats": self._site_alarm_summary(alarm_df),
            "alarm_rows": _df_records(alarm_df.head(_limit(kwargs.get("alarm_preview_limit"), default=50))),
            "bdt_total": int(bdt_payload.get("total") or len(bdt_rows)) if isinstance(bdt_payload, dict) else len(bdt_rows),
            "bdt_rows": _jsonable(bdt_rows[:_limit(kwargs.get("bdt_preview_limit"), default=50)]),
            "bdt_details": _jsonable(bdt_details),
            "export_path": str(export_path),
        }

    def generate_graph(self, **kwargs) -> dict[str, Any]:
        graph_type = str(kwargs.get("graph_type") or "alarm_category_counts").strip()
        site_code = normalize_site_key(kwargs.get("site_code") or kwargs.get("site_text") or "")
        title = str(kwargs.get("title") or graph_type.replace("_", " ").title())
        if graph_type.startswith("alarm_"):
            alarm_df = self._alarm_rows_for_sites(
                {site_code} if site_code else set(self._alarm_reference_df()["site_id"].map(normalize_site_key).dropna()),
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
            ) if site_code else self._with_alarm_source(lambda: alarm_store.query_alarms(alarm_store.AlarmQuery(
                date_from=_date_value(kwargs.get("date_from")),
                date_to=_date_value(kwargs.get("date_to")),
                limit=None,
                offset=0,
            )))
            labels, values = self._alarm_graph_series(alarm_df, graph_type)
        elif graph_type == "bdt_verdict_counts":
            payload = self.query_bdt_results(site_code=site_code, limit=MAX_QUERY_LIMIT)
            rows = payload.get("rows", []) if isinstance(payload, dict) else []
            series = pd.Series([r.get("overall_verdict") for r in rows if isinstance(r, dict)]).fillna("Unknown")
            counts = series.value_counts()
            labels, values = counts.index.astype(str).tolist(), counts.astype(int).tolist()
        elif graph_type == "bdt_duration_trend":
            payload = self.query_bdt_results(site_code=site_code, limit=MAX_QUERY_LIMIT)
            rows = [r for r in payload.get("rows", []) if isinstance(r, dict)] if isinstance(payload, dict) else []
            rows = sorted(rows, key=lambda r: str(r.get("test_date") or ""))
            labels = [str(r.get("test_date") or "")[:10] for r in rows if r.get("discharge_minutes") is not None]
            values = [float(r.get("discharge_minutes") or 0) for r in rows if r.get("discharge_minutes") is not None]
        else:
            return {"error": f"unsupported graph_type: {graph_type}"}

        path = _safe_export_path(self.export_dir / "charts", f"{title}_{site_code or 'all'}", "png")
        self._draw_bar_chart(path, title, labels, values)
        return {
            "path": str(path),
            "graph_type": graph_type,
            "site_code": site_code,
            "points": len(values),
            "labels": labels,
            "values": values,
        }

    def export_report(self, **kwargs) -> dict[str, Any]:
        report_type = str(kwargs.get("report_type") or "bdt_results").strip()
        fmt = str(kwargs.get("format") or "xlsx").lower()
        name = str(kwargs.get("name") or report_type)
        passthrough = {
            key: value for key, value in kwargs.items()
            if key not in {"report_type", "format", "name"}
        }
        if fmt not in {"xlsx", "csv"}:
            return {"error": "format must be xlsx or csv"}

        if report_type == "alarms":
            payload = self.query_alarms(**kwargs)
            df = pd.DataFrame(payload["rows"])
        elif report_type == "bdt_results":
            payload = self.query_bdt_results(**kwargs)
            df = pd.DataFrame(payload["rows"])
        elif report_type == "photo_manifest":
            payload = self.get_photo_metadata(**kwargs)
            df = pd.DataFrame(payload["rows"])
        elif report_type == "site_alarm_report":
            return self._export_site_alarm_report(fmt=fmt, name=name, **passthrough)
        elif report_type == "accepted_pm_report":
            return self._export_accepted_pm_report(fmt=fmt, name=name, **passthrough)
        elif report_type == "bdt_export":
            return self._export_bdt_validation_report(fmt=fmt, name=name, **passthrough)
        else:
            return {"error": f"unsupported report_type: {report_type}"}

        path = _safe_export_path(self.export_dir, name, fmt)
        if fmt == "csv":
            df.to_csv(path, index=False)
        else:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name=report_type[:31] or "Report")
        return {"path": str(path), "rows": len(df), "format": fmt, "report_type": report_type}

    def _export_site_alarm_report(self, *, fmt: str, name: str, **kwargs) -> dict[str, Any]:
        source_file_path = str(kwargs.get("source_file_path") or "").strip()
        if not source_file_path:
            return {"error": "source_file_path is required for site_alarm_report"}
        source_path = _safe_source_file_path(source_file_path)
        site_df, sheet_name, site_col = self._read_site_list(source_path)
        site_keys = collect_site_sheet_keys(site_df, site_col)
        alarm_df = self._alarm_rows_for_sites(
            site_keys,
            date_from=_date_value(kwargs.get("date_from")),
            date_to=_date_value(kwargs.get("date_to")),
        )
        report_df = build_site_alarm_report(site_df, site_col, alarm_df)
        path = _safe_export_path(self.export_dir, name, fmt)
        self._write_dataframe(report_df, path, fmt, "Site Report")
        return {
            "path": str(path),
            "rows": len(report_df),
            "format": fmt,
            "report_type": "site_alarm_report",
            "source_file_path": str(source_path),
            "sheet_name": sheet_name,
            "site_column": site_col,
            "site_count": len(site_keys),
            "alarm_rows": len(alarm_df),
        }

    def _export_accepted_pm_report(self, *, fmt: str, name: str, **kwargs) -> dict[str, Any]:
        source_file_path = str(kwargs.get("source_file_path") or "").strip()
        if not source_file_path:
            return {"error": "source_file_path is required for accepted_pm_report"}
        source_path = _safe_source_file_path(source_file_path)
        reference_df = self._alarm_reference_df()
        pm_df, sheet_name, site_col, date_col, status_col = read_pm_accept_sheet(
            str(source_path),
            reference_df,
        )
        site_keys = collect_site_sheet_keys(pm_df, site_col)
        alarm_df = self._alarm_rows_for_pm_sheet(pm_df, site_col, date_col)
        bdt_results = self._load_validation_results(site_keys=site_keys)
        report_df = build_pm_accept_report(
            pm_df,
            site_col,
            date_col,
            bdt_results,
            alarm_df,
            health_pct=float(kwargs.get("health_pct") or 80.0),
            status_column=status_col,
        )
        path = _safe_export_path(self.export_dir, name, fmt)
        self._write_dataframe(report_df, path, fmt, "Accepted PM")
        return {
            "path": str(path),
            "rows": len(report_df),
            "format": fmt,
            "report_type": "accepted_pm_report",
            "source_file_path": str(source_path),
            "sheet_name": sheet_name,
            "site_column": site_col,
            "date_column": date_col,
            "status_column": status_col,
            "site_count": len(site_keys),
            "alarm_rows": len(alarm_df),
            "bdt_results": len(bdt_results),
        }

    def _export_bdt_validation_report(self, *, fmt: str, name: str, **kwargs) -> dict[str, Any]:
        if fmt != "xlsx":
            return {"error": "bdt_export supports xlsx only because it contains multiple sheets"}
        site_keys: set[str] | None = None
        source_file_path = str(kwargs.get("source_file_path") or "").strip()
        source_path = None
        if source_file_path:
            source_path = _safe_source_file_path(source_file_path)
            site_df, _sheet_name, site_col = self._read_site_list(source_path)
            site_keys = collect_site_sheet_keys(site_df, site_col)
        bdt_results = self._load_validation_results(site_keys=site_keys)
        sheets = build_bdt_export_sheets(
            bdt_results,
            health_pct=float(kwargs.get("health_pct") or 80.0),
        )
        path = _safe_export_path(self.export_dir, name, "xlsx")
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for sheet_name, df in sheets.items():
                df.to_excel(writer, index=False, sheet_name=str(sheet_name)[:31] or "Sheet")
        return {
            "path": str(path),
            "rows": sum(len(df) for df in sheets.values()),
            "format": "xlsx",
            "report_type": "bdt_export",
            "source_file_path": str(source_path) if source_path else "",
            "site_count": len(site_keys or set()),
            "bdt_results": len(bdt_results),
            "sheets": list(sheets.keys()),
        }

    def _read_site_list(self, source_path: Path) -> tuple[pd.DataFrame, str, str]:
        if source_path.suffix.lower() == ".csv":
            df = pd.read_csv(source_path, dtype=object)
            site_col = infer_site_id_column(df, self._alarm_reference_df())
            if not site_col:
                raise ValueError("Could not identify a site ID column in the uploaded file.")
            return df, "Sheet1", site_col

        book = pd.ExcelFile(source_path)
        reference_df = self._alarm_reference_df()
        best: tuple[pd.DataFrame, str, str, int] | None = None
        try:
            for sheet_name in book.sheet_names:
                df = pd.read_excel(book, sheet_name=sheet_name, dtype=object)
                site_col = infer_site_id_column(df, reference_df)
                if not site_col:
                    continue
                keys = {normalize_site_key(v) for v in df[site_col].dropna().tolist() if normalize_site_key(v)}
                score = len(keys)
                if best is None or score > best[3]:
                    best = (df, sheet_name, site_col, score)
        finally:
            try:
                book.close()
            except Exception:
                pass
        if best is None:
            raise ValueError("Could not identify a site ID column in the uploaded workbook.")
        return best[0], best[1], best[2]

    def _alarm_reference_df(self) -> pd.DataFrame:
        try:
            values = self._with_alarm_source(lambda: alarm_store.distinct_values("site_id")) or []
        except Exception:
            values = []
        return pd.DataFrame({"site_id": values})

    def _alarm_rows_for_sites(
        self,
        site_keys: set[str],
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> pd.DataFrame:
        if not site_keys:
            return pd.DataFrame()
        query = alarm_store.AlarmQuery(
            site_scope_keys=site_keys,
            date_from=date_from,
            date_to=date_to,
            sort_by="occurred_on",
            limit=None,
            offset=0,
        )
        return self._with_alarm_source(lambda: alarm_store.query_alarms(query))

    def _alarm_rows_for_pm_sheet(self, pm_df: pd.DataFrame, site_col: str, date_col: str) -> pd.DataFrame:
        site_keys = collect_site_sheet_keys(pm_df, site_col)
        dates = pd.to_datetime(pm_df[date_col], errors="coerce", format="mixed")
        valid_dates = [pd.Timestamp(v).date() for v in dates.dropna().tolist()]
        date_from = min(valid_dates) - timedelta(days=1) if valid_dates else None
        date_to = max(valid_dates) + timedelta(days=1) if valid_dates else None
        return self._alarm_rows_for_sites(site_keys, date_from=date_from, date_to=date_to)

    def _export_site_dossier_workbook(
        self,
        *,
        site_code: str,
        alarm_df: pd.DataFrame,
        bdt_rows: list[dict[str, Any]],
        bdt_details: list[dict[str, Any]],
    ) -> Path:
        path = _safe_export_path(self.export_dir, f"site_dossier_{site_code}", "xlsx")
        rules: list[dict[str, Any]] = []
        photos: list[dict[str, Any]] = []
        discharge_rows: list[dict[str, Any]] = []
        for detail in bdt_details:
            bdt = detail.get("bdt") if isinstance(detail.get("bdt"), dict) else {}
            run_id = detail.get("validation_run_id")
            for rule in detail.get("rules", []) if isinstance(detail.get("rules"), list) else []:
                if isinstance(rule, dict):
                    rules.append({"validation_run_id": run_id, **rule})
            for photo in detail.get("photos", []) if isinstance(detail.get("photos"), list) else []:
                if isinstance(photo, dict):
                    photos.append({"validation_run_id": run_id, **photo})
            for reading in bdt.get("discharge_readings", []) if isinstance(bdt, dict) else []:
                discharge_rows.append({
                    "validation_run_id": run_id,
                    "site_code": bdt.get("site_code"),
                    "test_date": bdt.get("test_date"),
                    "reading": reading,
                })

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            alarm_df.to_excel(writer, index=False, sheet_name="Alarms")
            pd.DataFrame(bdt_rows).to_excel(writer, index=False, sheet_name="BDT Results")
            pd.DataFrame(rules).to_excel(writer, index=False, sheet_name="BDT Rules")
            pd.DataFrame(photos).to_excel(writer, index=False, sheet_name="BDT Photos")
            pd.DataFrame(discharge_rows).to_excel(writer, index=False, sheet_name="Discharge")
        return path

    @staticmethod
    def _site_alarm_summary(alarm_df: pd.DataFrame) -> dict[str, Any]:
        if alarm_df is None or alarm_df.empty:
            return {"total": 0, "by_category": {}, "first_alarm": None, "last_alarm": None}
        work = alarm_df.copy()
        if "occurred_on" in work.columns:
            work["occurred_on"] = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed")
        category_col = "alarm_category" if "alarm_category" in work.columns else None
        counts = work[category_col].fillna("Unknown").value_counts().to_dict() if category_col else {}
        return {
            "total": len(work),
            "by_category": {str(k): int(v) for k, v in counts.items()},
            "first_alarm": _jsonable(work["occurred_on"].min()) if "occurred_on" in work.columns else None,
            "last_alarm": _jsonable(work["occurred_on"].max()) if "occurred_on" in work.columns else None,
        }

    @staticmethod
    def _alarm_graph_series(alarm_df: pd.DataFrame, graph_type: str) -> tuple[list[str], list[float]]:
        if alarm_df is None or alarm_df.empty:
            return [], []
        work = alarm_df.copy()
        if graph_type == "alarm_category_counts":
            col = "alarm_category" if "alarm_category" in work.columns else "alarm_name"
            counts = work[col].fillna("Unknown").value_counts()
            return counts.index.astype(str).tolist(), counts.astype(float).tolist()
        if graph_type == "alarm_daily_counts":
            if "occurred_on" not in work.columns:
                return [], []
            days = pd.to_datetime(work["occurred_on"], errors="coerce", format="mixed").dropna().dt.date
            counts = days.value_counts().sort_index()
            return [str(v) for v in counts.index.tolist()], counts.astype(float).tolist()
        if graph_type == "alarm_duration_by_category":
            if "_duration_secs" not in work.columns:
                return [], []
            col = "alarm_category" if "alarm_category" in work.columns else "alarm_name"
            grouped = work.groupby(col, dropna=False)["_duration_secs"].mean().sort_values(ascending=False)
            return grouped.index.astype(str).tolist(), (grouped / 60.0).astype(float).tolist()
        return [], []

    @staticmethod
    def _draw_bar_chart(path: Path, title: str, labels: list[str], values: list[float]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        width, height = 1100, 620
        margin_left, margin_right, margin_top, margin_bottom = 92, 42, 82, 122
        image = Image.new("RGB", (width, height), "#10111a")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()
        draw.text((margin_left, 28), title, fill="#d8def8", font=title_font)
        if not values:
            draw.text((margin_left, height // 2), "No matching data", fill="#8f96ad", font=font)
            image.save(path)
            return
        max_points = 24
        labels = labels[:max_points]
        values = values[:max_points]
        max_value = max(max(values), 1.0)
        chart_w = width - margin_left - margin_right
        chart_h = height - margin_top - margin_bottom
        axis_color = "#3a3d55"
        draw.line((margin_left, margin_top, margin_left, margin_top + chart_h), fill=axis_color, width=2)
        draw.line((margin_left, margin_top + chart_h, margin_left + chart_w, margin_top + chart_h), fill=axis_color, width=2)
        bar_gap = 8
        bar_w = max(14, int((chart_w - bar_gap * (len(values) - 1)) / max(len(values), 1)))
        for idx, (label, value) in enumerate(zip(labels, values, strict=False)):
            x0 = margin_left + idx * (bar_w + bar_gap)
            bar_h = int((float(value) / max_value) * (chart_h - 24))
            y0 = margin_top + chart_h - bar_h
            x1 = x0 + bar_w
            y1 = margin_top + chart_h
            draw.rectangle((x0, y0, x1, y1), fill="#7aa2ff")
            draw.text((x0, max(margin_top, y0 - 18)), f"{value:g}", fill="#d8def8", font=font)
            short = str(label)[:14]
            draw.text((x0, y1 + 10), short, fill="#b9c1dc", font=font)
        image.save(path)

    @staticmethod
    def _write_dataframe(df: pd.DataFrame, path: Path, fmt: str, sheet_name: str) -> None:
        if fmt == "csv":
            df.to_csv(path, index=False)
            return
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31] or "Report")

    @staticmethod
    def _load_validation_results(*, site_keys: set[str] | None = None) -> list:
        session = db_engine.get_session()
        try:
            results = load_all_validation_results(session)
        finally:
            session.close()
        if not site_keys:
            return results
        return [
            result for result in results
            if normalize_site_key(getattr(result, "site_code", "")) in site_keys
        ]

    @staticmethod
    def _filename_for_bdt(session, bdt: BDTTest) -> str:
        if not bdt.file_id:
            return ""
        try:
            uploaded = session.get(UploadedFile, bdt.file_id)
            return str(uploaded.original_name or "") if uploaded else ""
        except Exception:
            return ""

    def _photo_rows_for_bdt(self, session, bdt_test_id: int) -> list[dict[str, Any]]:
        rows = []
        query = (
            session.query(BDTPhoto, BDTTest, BlobAsset)
            .join(BDTTest, BDTPhoto.bdt_test_id == BDTTest.id)
            .outerjoin(BlobAsset, BDTPhoto.blob_asset_id == BlobAsset.id)
            .filter(BDTPhoto.bdt_test_id == bdt_test_id)
            .order_by(BDTPhoto.slot_index.asc())
        )
        for photo, bdt, blob in query.all():
            rows.append(self._photo_row(photo, bdt, blob))
        return rows

    @staticmethod
    def _photo_row(photo: BDTPhoto, bdt: BDTTest, blob: BlobAsset | None) -> dict[str, Any]:
        return {
            "bdt_test_id": bdt.id,
            "site_code": bdt.site_code,
            "test_date": bdt.test_date,
            "slot_index": photo.slot_index,
            "slot_category": photo.slot_category,
            "sha256": blob.sha256 if blob else None,
            "mime_type": blob.mime_type if blob else None,
            "file_size": blob.file_size if blob else None,
            "width": blob.width if blob else None,
            "height": blob.height if blob else None,
            "local_path": blob.local_path if blob else None,
        }
