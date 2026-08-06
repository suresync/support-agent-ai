import json
from app.db import get_connection, init_db, log_audit


def test_init_db_creates_tables(tmp_path):
    path = tmp_path / "t.db"
    init_db(str(path))
    conn = get_connection(str(path))
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert {"conversations", "drafts", "approved_memory", "audit_log"} <= tables


def test_log_audit_writes_row(tmp_path):
    path = tmp_path / "t.db"
    conn = init_db(str(path))
    log_audit(
        conn,
        "sync",
        conversation_id="conv-1",
        draft_id=None,
        detail={"count": 3},
    )
    conn.commit()
    row = conn.execute(
        "SELECT action, conversation_id, draft_id, detail_json FROM audit_log"
    ).fetchone()
    assert row[0] == "sync"
    assert row[1] == "conv-1"
    assert row[2] is None
    assert json.loads(row[3]) == {"count": 3}
