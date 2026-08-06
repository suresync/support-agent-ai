from fastapi.testclient import TestClient

from app import embeddings
from app.config import Settings
from app.db import init_db
from app.draft_agent import DraftResult


class FakeClient:
    def get_conversation(self, conversation_id):
        assert conversation_id == "conv-1"
        return {"id": conversation_id, "messages": []}

    def send_message(self, conversation_id, body):
        raise AssertionError("dry-run approval must not send a message")


def test_approve_uses_dry_run_setting(tmp_path, monkeypatch):
    from app.api import create_app

    database_path = str(tmp_path / "test.db")
    conn = init_db(database_path)
    conn.execute(
        """
        INSERT INTO conversations (id, subject, language, raw_snapshot_json)
        VALUES ('conv-1', 'Order status', 'en', '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO drafts (
            id, conversation_id, status, draft_text, created_at, updated_at
        )
        VALUES (
            'draft-1', 'conv-1', 'needs_review', 'I will check your order.',
            '2026-08-06T10:00:00+00:00', '2026-08-06T10:00:00+00:00'
        )
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts: [b"embedding"])
    settings = Settings(database_path=database_path, dry_run=True)

    with TestClient(create_app(settings=settings, client=FakeClient())) as api:
        response = api.post("/api/drafts/draft-1/approve", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "sent_simulated"


def test_reject_and_regenerate_write_audit_entries(tmp_path, monkeypatch):
    from app import api as api_module

    database_path = str(tmp_path / "test.db")
    conn = init_db(database_path)
    conn.execute(
        """
        INSERT INTO conversations (id, subject, language, raw_snapshot_json)
        VALUES ('conv-1', 'Order status', 'en', '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO drafts (
            id, conversation_id, status, draft_text, created_at, updated_at
        )
        VALUES (
            'draft-1', 'conv-1', 'needs_review', 'Original reply',
            '2026-08-06T10:00:00+00:00', '2026-08-06T10:00:00+00:00'
        )
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(api_module, "search_similar", lambda *args, **kwargs: [])
    monkeypatch.setattr(api_module, "load_faq_chunks", lambda *args: [])
    monkeypatch.setattr(
        api_module,
        "generate_draft",
        lambda **kwargs: DraftResult("Regenerated reply", 0.9, None),
    )
    settings = Settings(database_path=database_path, dry_run=True)

    with TestClient(api_module.create_app(settings=settings, client=FakeClient())) as api:
        reject_response = api.post(
            "/api/drafts/draft-1/reject", json={"reason": "Incorrect"}
        )
        regenerate_response = api.post(
            "/api/drafts/draft-1/regenerate",
            json={"instruction": "Be concise"},
        )

    conn = init_db(database_path)
    audits = conn.execute(
        """
        SELECT action, conversation_id, draft_id
        FROM audit_log
        ORDER BY id
        """
    ).fetchall()
    conn.close()
    assert reject_response.status_code == 200
    assert regenerate_response.status_code == 200
    assert audits == [
        ("reject", "conv-1", "draft-1"),
        ("regenerate", "conv-1", "draft-1"),
    ]
