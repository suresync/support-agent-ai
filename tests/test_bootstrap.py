import numpy as np
import pytest

from app.config import Settings
from app.db import init_db


class FakeClient:
    def __init__(self, conversations):
        self.conversations = conversations
        self.list_calls = []

    def list_conversations(self, **kwargs):
        self.list_calls.append(kwargs)
        return self.conversations if kwargs["page"] == 1 else []


@pytest.fixture
def closed_conversations():
    return [
        {
            "id": "auto-only",
            "status": "CLOSED",
            "messages": [
                {
                    "direction": "inbound",
                    "sender_type": "customer",
                    "body": "Can you check my order status?",
                },
                {
                    "direction": "outbound",
                    "sender_type": "agent",
                    "body": 'Reply to this email with a "hi" to check your status.',
                },
            ],
        },
        {
            "id": "human-reply",
            "status": "CLOSED",
            "messages": [
                {
                    "direction": "inbound",
                    "sender_type": "customer",
                    "body": "My order arrived without the blue yarn cones.",
                },
                {
                    "direction": "outbound",
                    "sender_type": "agent",
                    "body": "Sorry about that. We will ship the missing cones today.",
                },
            ],
        },
    ]


def test_bootstrap_skips_auto_replies_and_stores_human_reply(
    tmp_path, monkeypatch, closed_conversations
):
    from app import bootstrap

    conn = init_db(str(tmp_path / "test.db"))
    client = FakeClient(closed_conversations)
    monkeypatch.setattr(
        "app.embeddings.embed_texts",
        lambda texts: [np.array([1.0], dtype=np.float32).tobytes() for _ in texts],
    )

    inserted = bootstrap.bootstrap_memory(
        conn,
        client,
        start_date="2025-08-06",
        end_date="2026-08-06",
        settings=Settings(),
    )

    rows = conn.execute(
        """
        SELECT conversation_id, customer_question_summary, final_reply, source
        FROM approved_memory
        """
    ).fetchall()
    assert inserted == 1
    assert rows == [
        (
            "human-reply",
            "My order arrived without the blue yarn cones.",
            "Sorry about that. We will ship the missing cones today.",
            "historic",
        )
    ]
    assert client.list_calls == [
        {
            "status": "CLOSED",
            "start_date": "2025-08-06",
            "end_date": "2026-08-06",
            "page": 1,
            "per_page": 50,
        },
        {
            "status": "CLOSED",
            "start_date": "2025-08-06",
            "end_date": "2026-08-06",
            "page": 2,
            "per_page": 50,
        },
    ]
