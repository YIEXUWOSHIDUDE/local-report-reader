import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict_factory(cursor: sqlite3.Cursor, row: tuple[Any, ...]) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = _dict_factory
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    settings = get_settings()
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime_type TEXT,
                file_size INTEGER NOT NULL,
                status TEXT NOT NULL,
                language TEXT NOT NULL,
                parser_notes TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                analysis_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_ids TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def insert_report(payload: dict[str, Any]) -> int:
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO reports (
                filename, stored_path, mime_type, file_size, status, language,
                parser_notes, extracted_text, analysis_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload["filename"],
                payload["stored_path"],
                payload.get("mime_type"),
                payload["file_size"],
                payload["status"],
                payload["language"],
                payload["parser_notes"],
                payload["extracted_text"],
                json.dumps(payload.get("analysis"), ensure_ascii=False)
                if payload.get("analysis") is not None
                else None,
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


def list_reports() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, mime_type, file_size, status, language,
                   parser_notes, analysis_json, created_at, updated_at
            FROM reports
            ORDER BY created_at DESC
            """
        ).fetchall()
    for row in rows:
        row["analysis"] = json.loads(row.pop("analysis_json")) if row.get("analysis_json") else None
    return rows


def get_report(report_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if row and row.get("analysis_json"):
        row["analysis"] = json.loads(row.pop("analysis_json"))
    elif row:
        row["analysis"] = None
        row.pop("analysis_json", None)
    return row


def update_report_analysis(report_id: int, analysis: dict[str, Any], status: str = "analyzed") -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE reports
            SET analysis_json = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(analysis, ensure_ascii=False), status, utc_now(), report_id),
        )


def insert_comparison(report_ids: list[int], result: dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO comparisons (report_ids, result_json, created_at)
            VALUES (?, ?, ?)
            """,
            (json.dumps(report_ids), json.dumps(result, ensure_ascii=False), utc_now()),
        )
        return int(cur.lastrowid)


def get_comparison(comparison_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM comparisons WHERE id = ?", (comparison_id,)).fetchone()
    if row:
        row["report_ids"] = json.loads(row["report_ids"])
        row["result"] = json.loads(row.pop("result_json"))
    return row
