from app.config import Settings
from app.db import init_db
from app.draft_agent import DraftResult


class FakeClient:
    def __init__(self, conversations):
        self.conversations = conversations
        self.list_calls = []

    def list_conversations(self, **kwargs):
        self.list_calls.append(kwargs)
        return self.conversations


def test_sync_open_email_ticket_enqueues_needs_review_draft(
    tmp_path, monkeypatch
):
    from app import ingest

    conversation = {
        "id": "conv-1",
        "conversation_no": "1001",
        "subject": "Where is my order?",
        "status": "OPEN",
        "channel": "email",
        "customer": {"email": "buyer@example.com", "name": "Buyer"},
        "updated_at": "2026-08-06T12:00:00+00:00",
        "messages": [
            {
                "direction": "inbound",
                "sender_type": "customer",
                "body": "Hi, where is my order please?",
                "created_at": "2026-08-06T11:59:00+00:00",
            }
        ],
    }
    client = FakeClient([conversation])
    conn = init_db(str(tmp_path / "test.db"))
    monkeypatch.setattr(ingest, "search_similar", lambda *args, **kwargs: [])
    monkeypatch.setattr(ingest, "load_faq_chunks", lambda *args: ["FAQ"])
    monkeypatch.setattr(
        ingest,
        "generate_draft",
        lambda **kwargs: DraftResult("Your order is being checked.", 0.8, None),
    )

    stats = ingest.sync_once(conn, client, Settings())

    draft = conn.execute(
        "SELECT status, draft_text FROM drafts WHERE conversation_id = ?",
        ("conv-1",),
    ).fetchone()
    stored = conn.execute(
        "SELECT status, channel, customer_email, language FROM conversations"
    ).fetchone()
    assert draft == ("needs_review", "Your order is being checked.")
    assert stored == ("OPEN", "email", "buyer@example.com", "en")
    assert stats.conversations_seen == 1
    assert stats.drafts_created == 1
    assert client.list_calls[0]["status"] == "OPEN"


def test_sync_skips_stale_draft_when_customer_wrote_again(
    tmp_path, monkeypatch
):
    from app import ingest

    conn = init_db(str(tmp_path / "test.db"))
    conn.execute(
        "INSERT INTO conversations (id) VALUES ('conv-1')"
    )
    conn.execute(
        """
        INSERT INTO drafts (
            id, conversation_id, status, draft_text, created_at, updated_at
        )
        VALUES (
            'old-draft', 'conv-1', 'needs_review', 'Old reply',
            '2026-08-06T10:00:00+00:00', '2026-08-06T10:00:00+00:00'
        )
        """
    )
    client = FakeClient(
        [
            {
                "id": "conv-1",
                "status": "OPEN",
                "channel": "email",
                "messages": [
                    {
                        "direction": "inbound",
                        "body": "I have another question about my order.",
                        "created_at": "2026-08-06T10:01:00+00:00",
                    }
                ],
            }
        ]
    )
    monkeypatch.setattr(ingest, "search_similar", lambda *args, **kwargs: [])
    monkeypatch.setattr(ingest, "load_faq_chunks", lambda *args: [])
    monkeypatch.setattr(
        ingest,
        "generate_draft",
        lambda **kwargs: DraftResult("New reply", 0.7, None),
    )

    stats = ingest.sync_once(conn, client, Settings())

    rows = conn.execute(
        "SELECT status, draft_text FROM drafts ORDER BY created_at"
    ).fetchall()
    assert rows == [("skipped", "Old reply"), ("needs_review", "New reply")]
    assert stats.drafts_skipped == 1
    assert stats.drafts_created == 1
