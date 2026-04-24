"""Guarded local data access for MCP/OpenRouter agents."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
import base64
import json
from pathlib import Path
import re
from typing import Any

import pandas as pd
from sqlalchemy import inspect as sa_inspect

try:
    from ..data import alarm_store, state
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
except ImportError:
    from alarm_app.data import alarm_store, state
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


MAX_QUERY_LIMIT = 500
MAX_BLOB_BYTES = 5 * 1024 * 1024
EXPORT_DIR = Path.home() / ".alarm_viewer" / "exports"


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

    def export_report(self, **kwargs) -> dict[str, Any]:
        report_type = str(kwargs.get("report_type") or "bdt_results").strip()
        fmt = str(kwargs.get("format") or "xlsx").lower()
        name = str(kwargs.get("name") or report_type)
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
        else:
            return {"error": f"unsupported report_type: {report_type}"}

        path = _safe_export_path(self.export_dir, name, fmt)
        if fmt == "csv":
            df.to_csv(path, index=False)
        else:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name=report_type[:31] or "Report")
        return {"path": str(path), "rows": len(df), "format": fmt}

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
