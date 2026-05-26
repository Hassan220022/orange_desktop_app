"""Federated site query descriptors and helpers for MCP tools."""

from __future__ import annotations

import json
import re
from typing import Any

import pandas as pd

ROW_CAP = 500
FEDERATED_MAX_SOURCE_ROWS = 50000
ADMIN_SQL_MAX_OFFSET = FEDERATED_MAX_SOURCE_ROWS
ADMIN_SQL_MAX_COUNT_ROWS = FEDERATED_MAX_SOURCE_ROWS
ADMIN_SQL_MAX_COLUMNS = 100
ADMIN_SQL_MAX_CELL_STRING_LENGTH = 10_000
ADMIN_SQL_MAX_SERIALIZED_BYTES = 1_000_000

SITE_FIELDS = [
    "site_id", "site_code", "site_name", "area", "office", "vip", "contractor", "subcontractor",
    "backup_status", "battery_status", "has_metadata", "has_alarms", "alarm_count", "latest_alarm_at",
    "has_bdt_summary", "bdt_summary_count", "has_bdt_validation", "bdt_validation_count", "has_bdt",
    "latest_bdt_at",
]

SOURCES = {
    "site_metadata": "Network Summary / Site Metadata rows keyed by Site ID.",
    "alarms": "Stored alarm rows and alarm aggregates keyed by Site ID.",
    "bdt_summary": "BDT Summary Catalog rows keyed by Site ID.",
    "bdt_validation": "BDT validation runs, rule results, photo metadata, and review events keyed by Site ID.",
}

NESTED_SECTIONS = [
    "network_summary_rows", "alarm_rows", "bdt_summary_rows", "bdt_validation_runs",
    "bdt_rule_results", "photo_metadata", "review_events",
]

OPERATORS = ["eq", "neq", "contains", "not_contains", "in", "not_in", "is_blank", "is_not_blank", "gte", "lte"]
SOURCE_FIELDS = {
    "site_metadata": "has_metadata",
    "alarms": "has_alarms",
    "bdt_summary": "has_bdt_summary",
    "bdt_validation": "has_bdt_validation",
}
NUMERIC_SITE_FIELDS = {"alarm_count", "bdt_summary_count", "bdt_validation_count"}


ADMIN_SQL_VIEWS = {
    "site_metadata_view": [
        "site_id",
        "site_code",
        "site_name",
        "area",
        "office",
        "vip",
        "contractor",
        "subcontractor",
        "backup_status",
        "battery_status",
    ],
    "site_index_view": list(SITE_FIELDS),
    "alarm_events_view": [
        "site_id",
        "alarm_name",
        "alarm_id",
        "occurred_on",
        "cleared_on",
        "duration",
        "duration_secs",
        "category",
        "vendor",
        "network_type",
        "severity",
        "alarm_category",
        "clearance_status",
        "site_down",
    ],
    "alarm_summary_view": ["site_id", "alarm_count", "latest_alarm_at"],
    "bdt_summary_view": ["site_id", "reporting_period", "week", "test_date", "site_name"],
    "bdt_validation_runs_view": [
        "site_id",
        "validation_run_id",
        "bdt_test_id",
        "test_date",
        "overall_verdict",
        "run_at",
    ],
    "bdt_rule_results_view": [
        "site_id",
        "validation_run_id",
        "rule_id",
        "rule_name",
        "verdict",
        "test_date",
        "created_at",
    ],
    "photo_metadata_view": [
        "site_id",
        "bdt_test_id",
        "slot_index",
        "slot_category",
        "sha256",
        "mime_type",
        "file_size",
        "width",
        "height",
        "created_at",
    ],
    "review_events_view": [
        "site_id",
        "event_type",
        "test_date",
        "reviewer",
        "filename",
        "verdict",
        "reviewed_at",
        "created_at",
    ],
}


BLOCKED_SQL_PATTERN = re.compile(
    r"(?i)\b(?:"
    r"INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|ATTACH|DETACH|PRAGMA|COPY|INSTALL|LOAD|CALL|SET|"
    r"VACUUM|EXPORT|IMPORT|"
    r"read_csv|read_parquet|read_json|read_text|read_blob|"
    r"sqlite_master|sqlite_schema|sqlite_temp_schema|information_schema|duckdb_[A-Za-z0-9_]+|glob|sqlite_scan|pg_[A-Za-z0-9_]*|pg_catalog"
    r")\b"
)


_BLOCKED_RUNTIME_FUNCTIONS = {
    "version",
    "current_setting",
    "current_database",
    "current_schema",
    "range",
    "generate_series",
    "repeat",
    "list_value",
    "array_value",
    "map",
    "struct_pack",
    "rpad",
    "lpad",
    "current_user",
    "session_user",
    "txid_current",
    "printf",
    "format",
    "random",
    "uuid",
    "gen_random_uuid",
    "format_bytes",
}


def _apply_duckdb_resource_limits(conn: Any) -> str | None:
    """Configure DuckDB hardening options.

    DuckDB versions differ in available config keys. We treat unsupported values as
    hard failures only when no known resource-limiting knob can be enabled.
    """

    attempts: list[tuple[str, str]] = [
        ("memory_limit", "'128MB'"),
        ("threads", "1"),
    ]

    configured = 0
    failures: list[str] = []
    for name, value in attempts:
        try:
            conn.execute(f"SET {name}={value}")
            configured += 1
        except Exception as exc:
            failures.append(f"{name}: {exc}")

    if configured == 0:
        return "duckdb runtime hardening settings unavailable: " + "; ".join(failures)

    if failures:
        # Environment does not support one setting, but at least one hardening knob is active.
        return "duckdb resource settings partly unavailable: " + "; ".join(failures)

    return None


def describe_admin_sql_views() -> dict[str, Any]:
    return {
        "join_key": "site_id",
        "row_cap": ROW_CAP,
        "views": {name: list(fields) for name, fields in ADMIN_SQL_VIEWS.items()},
        "allowed_sql": [
            "SELECT",
            "WITH",
            "JOIN",
            "WHERE",
            "GROUP BY",
            "ORDER BY",
            "CASE",
            "subqueries",
            "COUNT",
            "SUM",
            "MIN",
            "MAX",
            "AVG",
        ],
        "blocked_sql": [
            "INSERT",
            "UPDATE",
            "DELETE",
            "CREATE",
            "DROP",
            "ALTER",
            "ATTACH",
            "DETACH",
            "PRAGMA",
            "COPY",
            "INSTALL",
            "LOAD",
            "read_csv",
            "read_parquet",
        ],
        "examples": [
            {
                "question": "List latest alarms by site for recent critical events.",
                "sql": "SELECT site_id, alarm_id, alarm_name, occurred_on FROM alarm_events_view WHERE severity = 'Critical' ORDER BY occurred_on DESC",
            },
            {
                "question": "Count accepted BDT rules per site.",
                "sql": "SELECT site_id, COUNT(*) AS accepted_rules FROM bdt_rule_results_view WHERE verdict = 'Accepted' GROUP BY site_id",
            },
        ],
    }


def validate_admin_sql(sql: str) -> str | None:
    if not isinstance(sql, str):
        return "sql must be a string"

    statement = sql.strip()
    if not statement:
        return "sql is required"

    normalized = statement.rstrip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].rstrip()

    def _redact_single_quoted_literals(sql_text: str) -> str:
        out: list[str] = []
        i = 0
        length = len(sql_text)
        while i < length:
            ch = sql_text[i]
            if ch == "'":
                out.append("''")
                i += 1
                while i < length:
                    if sql_text[i] == "'":
                        if i + 1 < length and sql_text[i + 1] == "'":
                            i += 2
                            continue
                        i += 1
                        break
                    i += 1
                continue

            out.append(ch)
            i += 1

        return "".join(out)

    redacted_for_multistmt = _redact_single_quoted_literals(normalized)

    if ";" in redacted_for_multistmt:
        return "sql must contain one statement only"

    if re.match(r"(?is)^with\s+recursive\b", redacted_for_multistmt.lstrip()):
        return "sql with RECURSIVE is not allowed"

    redacted_for_blocks = _redact_single_quoted_literals(normalized)

    def _contains_blocked_runtime_call(sql_text: str) -> bool:
        # Match explicit function calls and prevent runtime/system functions and
        # resource-heavy list constructors from entering query plans.
        # Includes quoted identifiers and optional schema-qualified references.
        for match in re.finditer(r'(?is)(?:(?:"[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\s*\.\s*)?("[^"]+"|[A-Za-z_][A-Za-z0-9_]*)\s*\(',
                               sql_text):
            candidate = match.group(1)
            if candidate is None:
                continue

            candidate_norm = candidate.strip().strip('"').lower()
            if candidate_norm in _BLOCKED_RUNTIME_FUNCTIONS:
                return True
        return False

    if BLOCKED_SQL_PATTERN.search(redacted_for_blocks):
        return "sql contains disallowed operations or functions"

    if _contains_blocked_runtime_call(redacted_for_blocks):
        return "sql contains disallowed operations or functions"

    lower = normalized.lower().lstrip()
    if not (lower.startswith("select") or lower.startswith("with")):
        return "sql must start with SELECT or WITH"

    def _extract_relation_identifier(text: str, start: int) -> tuple[str | None, bool, int]:
        n = len(text)
        i = start
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            return None, False, i

        if text[i] == "(":
            return None, False, i

        if text[i] == '"':
            i += 1
            begin = i
            while i < n:
                if text[i] == '"':
                    if i + 1 < n and text[i + 1] == '"':
                        i += 2
                        continue
                    token = text[begin:i].replace('""', '"')
                    i += 1
                    break
                i += 1
            else:
                return None, False, i
        else:
            begin = i
            if not re.match(r"[A-Za-z_]", text[i]):
                return None, False, i
            i += 1
            while i < n and re.match(r"[A-Za-z0-9_]", text[i]):
                i += 1
            token = text[begin:i]

        # Skip whitespace and optional schema qualification for relation-like token forms.
        while i < n and text[i].isspace():
            i += 1

        if i < n and text[i] == ".":
            # Handle optional schema/object qualification: schema.table
            j = i + 1
            if j < n and text[j] == '"':
                j += 1
                begin2 = j
                while j < n:
                    if text[j] == '"':
                        if j + 1 < n and text[j + 1] == '"':
                            j += 2
                            continue
                        j += 1
                        break
                    j += 1
                if j >= n:
                    return None, False, i
                qualified_name = text[begin2 : j - 1].replace('""', '"')
                token = f"{token}.{qualified_name}"
                i = j
                while i < n and text[i].isspace():
                    i += 1
            elif j < n and re.match(r"[A-Za-z_]", text[j]):
                begin2 = j
                while j < n and re.match(r"[A-Za-z0-9_]", text[j]):
                    j += 1
                token = f"{token}.{text[begin2:j]}"
                i = j
                while i < n and text[i].isspace():
                    i += 1

        is_function = i < n and text[i] == "("
        return token, is_function, i

    def _extract_cte_aliases(sql_text: str) -> set[str]:
        aliases: set[str] = set()

        with_tokens = list(re.finditer(r"(?is)\bwith\b", sql_text))
        if not with_tokens:
            return aliases

        for with_match in with_tokens:
            i = with_match.end()

            def _skip_ws(idx: int) -> int:
                while idx < len(sql_text) and sql_text[idx].isspace():
                    idx += 1
                return idx

            def _scan_identifier(idx: int) -> tuple[str | None, int]:
                idx = _skip_ws(idx)
                if idx >= len(sql_text):
                    return None, idx

                if sql_text[idx] == '"':
                    idx += 1
                    begin = idx
                    while idx < len(sql_text):
                        if sql_text[idx] == '"':
                            if idx + 1 < len(sql_text) and sql_text[idx + 1] == '"':
                                idx += 2
                                continue
                            return sql_text[begin:idx].replace('""', '"'), idx + 1
                        idx += 1
                    return None, idx

                if not re.match(r"[A-Za-z_]", sql_text[idx]):
                    return None, idx

                begin = idx
                idx += 1
                while idx < len(sql_text) and re.match(r"[A-Za-z0-9_]", sql_text[idx]):
                    idx += 1
                return sql_text[begin:idx], idx

            def _scan_parenthesized(idx: int) -> int:
                if idx >= len(sql_text) or sql_text[idx] != "(":
                    return idx

                idx += 1
                depth = 1
                in_single_quote = False
                in_double_quote = False
                while idx < len(sql_text) and depth > 0:
                    ch = sql_text[idx]
                    if in_single_quote:
                        if ch == "'":
                            if idx + 1 < len(sql_text) and sql_text[idx + 1] == "'":
                                idx += 2
                                continue
                            in_single_quote = False
                            idx += 1
                            continue
                        idx += 1
                        continue

                    if in_double_quote:
                        if ch == '"':
                            if idx + 1 < len(sql_text) and sql_text[idx + 1] == '"':
                                idx += 2
                                continue
                            in_double_quote = False
                            idx += 1
                            continue
                        idx += 1
                        continue

                    if ch == "'":
                        in_single_quote = True
                        idx += 1
                        continue
                    if ch == '"':
                        in_double_quote = True
                        idx += 1
                        continue

                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                    idx += 1

                return idx

            while i < len(sql_text):
                i = _skip_ws(i)
                if i >= len(sql_text):
                    break

                lower_tail = sql_text[i:].lower()
                if lower_tail.startswith("select") or lower_tail.startswith("(select"):
                    break

                alias, i = _scan_identifier(i)
                if not alias:
                    break

                aliases.add(alias.casefold())

                i = _skip_ws(i)
                if i < len(sql_text) and sql_text[i] == '(':
                    i = _scan_parenthesized(i)
                    i = _skip_ws(i)

                if i + 2 > len(sql_text):
                    break

                if not sql_text[i : i + 2].lower() == "as":
                    break
                i += 2

                i = _skip_ws(i)
                if i >= len(sql_text) or sql_text[i] != '(':
                    break

                i = _scan_parenthesized(i)
                i = _skip_ws(i)

                if i < len(sql_text) and sql_text[i] == ',':
                    i += 1
                    continue
                break

        return aliases

    def _has_approved_relation(sql_text: str) -> bool:
        approved = {name.lower() for name in ADMIN_SQL_VIEWS}
        for match in re.finditer(r"(?is)\b(?:from|join)\b", sql_text):
            token, is_function, _ = _extract_relation_identifier(sql_text, match.end())
            if token is None:
                continue
            if is_function:
                continue
            token_clean = token.strip()
            if "." in token_clean:
                part = token_clean.rsplit(".", 1)[-1].strip()
            else:
                part = token_clean
            part = part.strip('"').lower()
            if part in approved:
                return True

        return False

    if not _has_approved_relation(normalized):
        return "query references unsupported view(s) or invalid SQL"

    cte_aliases = _extract_cte_aliases(redacted_for_blocks)
    if any(alias in {name.casefold() for name in ADMIN_SQL_VIEWS} for alias in cte_aliases):
        return "query references disallowed CTE alias"

    def _contains_single_quoted_source_literals(sql_text: str) -> bool:
        pattern = re.compile(r"(?is)\b(?:from|join)\b\s+('[^']*(?:''[^']*)*')")
        for match in pattern.finditer(sql_text):
            token = match.group(1)
            if "." in token:
                return True
            return True

        return False

    def _contains_table_functions(sql_text: str) -> bool:
        from_iter = re.compile(r"(?is)\b(?:from|join)\s+(?:(?:[A-Za-z_][A-Za-z0-9_]*|\"[^\"]+\")\.)?(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*)\s*\(")
        for _ in from_iter.finditer(sql_text):
            return True

        return False

    if _contains_single_quoted_source_literals(normalized):
        return "sql references disallowed path or file-based table reference"

    if _contains_table_functions(normalized):
        return "query references unsupported view(s) or invalid SQL"

    import duckdb

    conn = duckdb.connect(database=":memory:")
    try:
        hardening_status = _apply_duckdb_resource_limits(conn)
        if hardening_status is not None and hardening_status.startswith("duckdb runtime hardening settings unavailable"):
            return hardening_status

        for view_name, columns in ADMIN_SQL_VIEWS.items():
            conn.register(view_name, pd.DataFrame(columns=list(columns)))

        conn.execute(f"EXPLAIN {normalized}")
    except Exception:
        return "query references unsupported view(s) or invalid SQL"
    finally:
        conn.close()

    return None


def run_admin_sql(
    sql: str,
    frames: dict[str, pd.DataFrame],
    *,
    offset: int = 0,
    limit: int = ROW_CAP,
) -> dict[str, Any]:
    normalized_sql = sql.strip()
    if normalized_sql.endswith(";"):
        normalized_sql = normalized_sql[:-1].rstrip()

    try:
        capped_limit = max(0, min(int(limit), ROW_CAP))
    except (TypeError, ValueError):
        return {
            "rows": [],
            "returned": 0,
            "limit": 0,
            "offset": 0,
            "has_more": False,
            "total": 0,
            "error": "invalid limit value; expected an integer",
        }

    try:
        capped_offset = max(0, int(offset))
    except (TypeError, ValueError):
        return {
            "rows": [],
            "returned": 0,
            "limit": capped_limit,
            "offset": 0,
            "has_more": False,
            "total": 0,
            "error": "invalid offset value; expected an integer",
        }

    if capped_offset > ADMIN_SQL_MAX_OFFSET:
        return {
            "rows": [],
            "returned": 0,
            "limit": capped_limit,
            "offset": capped_offset,
            "has_more": False,
            "total": 0,
            "error": f"offset exceeds max of {ADMIN_SQL_MAX_OFFSET}",
        }

    validation_error = validate_admin_sql(normalized_sql)
    if validation_error is not None:
        return {
            "rows": [],
            "returned": 0,
            "limit": capped_limit,
            "offset": capped_offset,
            "has_more": False,
            "total": 0,
            "error": validation_error,
        }

    import duckdb

    conn = duckdb.connect(database=":memory:")
    try:
        hardening_status = _apply_duckdb_resource_limits(conn)
        if hardening_status is not None and hardening_status.startswith("duckdb runtime hardening settings unavailable"):
            return {
                "rows": [],
                "returned": 0,
                "limit": capped_limit,
                "offset": capped_offset,
                "has_more": False,
                "total": 0,
                "error": hardening_status,
            }

        for view_name, columns in ADMIN_SQL_VIEWS.items():
            frame = frames.get(view_name)
            if not isinstance(frame, pd.DataFrame):
                frame = pd.DataFrame(columns=list(columns))
            else:
                frame = frame.copy()
            if frame.empty and not frame.columns.to_list():
                frame = pd.DataFrame(columns=list(columns))
            conn.register(view_name, frame)

        hardening_warning = hardening_status if (hardening_status and not hardening_status.startswith("duckdb runtime hardening settings unavailable")) else None
        warnings = []
        if hardening_warning is not None:
            warnings.append(hardening_warning)

        if capped_limit == 0:
            return {
                "rows": [],
                "returned": 0,
                "limit": capped_limit,
                "offset": capped_offset,
                "has_more": False,
                "total": 0,
                **({"warnings": warnings} if warnings else {}),
            }

        page_size = capped_limit + 1 if capped_limit > 0 else 0
        if page_size == 0:
            rows = []
        else:
            paged_query = (
                f"SELECT * FROM ({normalized_sql}) AS admin_query "
                f"LIMIT {int(page_size)} OFFSET {int(capped_offset)}"
            )
            rows_df = conn.execute(paged_query).fetch_df()
            rows = rows_df.to_dict(orient="records") if rows_df is not None else []

        page_rows = rows[:capped_limit] if capped_limit >= 0 else rows
        returned = len(page_rows)

        count_query = (
            "SELECT COUNT(*) FROM ("
            f"SELECT * FROM ({normalized_sql}) AS admin_count_query "
            f"LIMIT {int(ADMIN_SQL_MAX_COUNT_ROWS + 1)}"
            ") AS capped_count_query"
        )
        count_rows = conn.execute(count_query).fetchone()
        if count_rows and count_rows[0] is not None:
            count_total = int(count_rows[0])
        else:
            count_total = 0

        if count_total > ADMIN_SQL_MAX_COUNT_ROWS:
            total = ADMIN_SQL_MAX_COUNT_ROWS
            warnings = ["result count exceeded safety cap; total is capped"]
        else:
            total = count_total
            warnings = []

        if hardening_warning is not None:
            warnings.append(hardening_warning)

        has_more = capped_limit > 0 and capped_offset + returned < total

        def _row_column_count(row_value: Any) -> int:
            if isinstance(row_value, dict):
                return len(row_value)
            if isinstance(row_value, (list, tuple)):
                return len(row_value)
            return 0

        if any(_row_column_count(row) > ADMIN_SQL_MAX_COLUMNS for row in page_rows):
            return {
                "rows": [],
                "returned": 0,
                "limit": capped_limit,
                "offset": capped_offset,
                "has_more": False,
                "total": 0,
                "error": f"result row has too many columns (>{ADMIN_SQL_MAX_COLUMNS})",
            }

        for row in page_rows:
            if isinstance(row, dict):
                for value in row.values():
                    if isinstance(value, (list, tuple, dict, set)):
                        return {
                            "rows": [],
                            "returned": 0,
                            "limit": capped_limit,
                            "offset": capped_offset,
                            "has_more": False,
                            "total": 0,
                            "error": "result contains unsupported nested/list/map cell values",
                        }

                    if hasattr(value, "tolist") and callable(value.tolist):
                        try:
                            value_as_list = value.tolist()
                        except TypeError:
                            value_as_list = None
                        if isinstance(value_as_list, (list, tuple, dict, set)):
                            return {
                                "rows": [],
                                "returned": 0,
                                "limit": capped_limit,
                                "offset": capped_offset,
                                "has_more": False,
                                "total": 0,
                                "error": "result contains unsupported nested/list/map cell values",
                            }

                    if isinstance(value, str) and len(value) > ADMIN_SQL_MAX_CELL_STRING_LENGTH:
                        return {
                            "rows": [],
                            "returned": 0,
                            "limit": capped_limit,
                            "offset": capped_offset,
                            "has_more": False,
                            "total": 0,
                            "error": "result cell text exceeds allowed length",
                        }

        try:
            payload_bytes = len(json.dumps(page_rows, default=str).encode("utf-8"))
        except Exception:
            payload_bytes = 0

        if payload_bytes > ADMIN_SQL_MAX_SERIALIZED_BYTES:
            return {
                "rows": [],
                "returned": 0,
                "limit": capped_limit,
                "offset": capped_offset,
                "has_more": False,
                "total": 0,
                "error": "result payload exceeds serialized size limit",
            }

        return {
            "rows": page_rows,
            "returned": returned,
            "limit": capped_limit,
            "offset": capped_offset,
            "has_more": has_more,
            "total": total,
            **({"warnings": warnings} if warnings else {}),
        }
    except Exception as exc:
        return {
            "rows": [],
            "returned": 0,
            "limit": capped_limit,
            "offset": capped_offset,
            "has_more": False,
            "total": 0,
            "error": str(exc),
        }
    finally:
        conn.close()


def describe_federated_site_data() -> dict[str, Any]:
    return {
        "join_key": "site_id",
        "row_cap": ROW_CAP,
        "sources": dict(SOURCES),
        "fields": list(SITE_FIELDS),
        "nested_sections": list(NESTED_SECTIONS),
        "operators": list(OPERATORS),
        "section_match_modes": ["filter_nested_only", "require_matching_sites"],
        "examples": [
            {
                "question": "List VIP sites with backup status.",
                "select": ["site_id", "site_name", "vip", "office", "area", "subcontractor", "backup_status"],
                "site_filters": {"vip": {"not_in": ["_", "", None]}},
            },
            {
                "question": "Get per-site context for VIP sites with recent alarms.",
                "select": ["site_id", "site_name", "vip", "alarm_count", "latest_alarm_at"],
                "site_filters": {"vip": {"not_in": ["_", "", None]}},
                "section_match_mode": "require_matching_sites",
            },
        ],
    }


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def validate_site_filters(filters: dict[str, Any] | None) -> str | None:
    if not filters:
        return None
    if not isinstance(filters, dict):
        return "site_filters must be an object"

    for field, spec in filters.items():
        if field not in SITE_FIELDS:
            return f"unsupported site filter field: {field}"
        if isinstance(spec, dict):
            for operator_name in spec.keys():
                if operator_name not in OPERATORS:
                    return f"unsupported site filter operator: {operator_name}"
                if operator_name in {"gte", "lte"} and spec[operator_name] is None:
                    return f"{operator_name} filter for '{field}' requires a non-null expected value"
    return None


def _filter_text(value: Any) -> str:
    return "" if value is None else str(value)


def _matches_filter(value: Any, spec: Any, *, field: str | None = None) -> bool:
    if not isinstance(spec, dict):
        return _filter_text(value).casefold() == _filter_text(spec).casefold()

    def _to_float(candidate: Any) -> float | None:
        try:
            return float(candidate)
        except (TypeError, ValueError):
            return None

    for op, expected in spec.items():
        text = _filter_text(value)
        expected_values = expected if isinstance(expected, list) else [expected]
        expected_texts = [_filter_text(item) for item in expected_values]

        if op == "eq" and text.casefold() != _filter_text(expected).casefold():
            return False
        if op == "neq" and text.casefold() == _filter_text(expected).casefold():
            return False
        if op == "contains" and _filter_text(expected).casefold() not in text.casefold():
            return False
        if op == "not_contains" and _filter_text(expected).casefold() in text.casefold():
            return False
        if op == "in":
            text_folded = text.casefold()
            expected_texts_folded = {item.casefold() for item in expected_texts}
            if text_folded not in expected_texts_folded:
                return False
        if op == "not_in":
            text_folded = text.casefold()
            expected_texts_folded = {item.casefold() for item in expected_texts}
            if text_folded in expected_texts_folded:
                return False
        if op == "is_blank" and not _is_blank(value):
            return False
        if op == "is_not_blank" and _is_blank(value):
            return False
        if op == "gte":
            value_number = _to_float(value)
            expected_number = _to_float(expected)
            if field in NUMERIC_SITE_FIELDS and (value_number is None or expected_number is None):
                return False
            if value_number is not None and expected_number is not None:
                if value_number < expected_number:
                    return False
            elif field not in NUMERIC_SITE_FIELDS and text < _filter_text(expected):
                return False
            continue
        if op == "lte":
            value_number = _to_float(value)
            expected_number = _to_float(expected)
            if field in NUMERIC_SITE_FIELDS and (value_number is None or expected_number is None):
                return False
            if value_number is not None and expected_number is not None:
                if value_number > expected_number:
                    return False
            elif field not in NUMERIC_SITE_FIELDS and text > _filter_text(expected):
                return False
            continue
        if op not in OPERATORS:
            return False
    return True


def apply_site_filters(rows: list[dict[str, Any]], filters: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not filters:
        return rows
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if all(_matches_filter(row.get(field), spec, field=field) for field, spec in filters.items()):
            filtered.append(row)
    return filtered


def project_site_fields(row: dict[str, Any], select: list[str] | None) -> dict[str, Any]:
    fields = select or SITE_FIELDS
    return {field: row.get(field) for field in fields}
