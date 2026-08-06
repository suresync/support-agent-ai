import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.models import SCHEMA


def get_connection(path: str) -> sqlite3.Connection:
    return sqlite3.connect(path)


def init_db(path: str) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(str(db_path))
    conn.executescript(SCHEMA)
    return conn


def log_audit(
    conn: sqlite3.Connection,
    action: str,
    conversation_id: str | None = None,
    draft_id: str | None = None,
    detail: dict | None = None,
) -> None:
    ts = datetime.now(UTC).isoformat()
    detail_json = json.dumps(detail) if detail is not None else None
    conn.execute(
        """
        INSERT INTO audit_log (ts, action, conversation_id, draft_id, detail_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ts, action, conversation_id, draft_id, detail_json),
    )
