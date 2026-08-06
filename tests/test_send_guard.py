from app import embeddings
from app.db import init_db
from app.sender import approve_and_send


class FakeClient:
    def __init__(self, conversation):
        self.conversation = conversation
        self.send_calls = []

    def get_conversation(self, conversation_id):
        assert conversation_id == "conv-1"
        return self.conversation

    def send_message(self, conversation_id, body):
        self.send_calls.append((conversation_id, body))
        return {"id": "message-1"}


def _setup_db(tmp_path, *, edited_text=None):
    conn = init_db(str(tmp_path / "test.db"))
    conn.execute(
        """
        INSERT INTO conversations (id, subject, language, raw_snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        ("conv-1", "Missing yarn", "en", "{}"),
    )
    conn.execute(
        """
        INSERT INTO drafts (
            id, conversation_id, status, draft_text, edited_text,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "draft-1",
            "conv-1",
            "needs_review",
            "We will resend the yarn.",
            edited_text,
            "2026-08-06T10:00:00+00:00",
            "2026-08-06T10:00:00+00:00",
        ),
    )
    conn.commit()
    return conn


def test_send_guard_blocks_when_newer_outbound(tmp_path):
    conn = _setup_db(tmp_path)
    client = FakeClient(
        {
            "id": "conv-1",
            "messages": [
                {
                    "direction": "outbound",
                    "sender_type": "agent",
                    "created_at": "2026-08-06T10:01:00+00:00",
                }
            ],
        }
    )

    result = approve_and_send(conn, client, "draft-1", dry_run=False)

    assert result.ok is False
    assert result.status == "needs_review"
    assert result.error
    assert client.send_calls == []


def test_dry_run_does_not_call_send(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts: [b"embedding"])
    conn = _setup_db(tmp_path)
    client = FakeClient({"id": "conv-1", "messages": []})

    result = approve_and_send(conn, client, "draft-1", dry_run=True)

    assert result.ok is True
    assert result.status == "sent_simulated"
    assert client.send_calls == []
    assert conn.execute(
        "SELECT status FROM drafts WHERE id = 'draft-1'"
    ).fetchone()[0] == "sent_simulated"


def test_approve_writes_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(embeddings, "embed_texts", lambda texts: [b"embedding"])
    conn = _setup_db(tmp_path, edited_text="We have resent your yarn.")
    client = FakeClient({"id": "conv-1", "messages": []})

    result = approve_and_send(conn, client, "draft-1", dry_run=False)

    memory = conn.execute(
        """
        SELECT final_reply, source, conversation_id
        FROM approved_memory
        """
    ).fetchone()
    audit = conn.execute(
        "SELECT action FROM audit_log WHERE draft_id = 'draft-1'"
    ).fetchone()
    assert result.ok is True
    assert client.send_calls == [("conv-1", "We have resent your yarn.")]
    assert memory == ("We have resent your yarn.", "approved_live", "conv-1")
    assert audit == ("approve_send",)
