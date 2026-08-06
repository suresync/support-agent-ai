import json
from types import SimpleNamespace

from app.config import Settings
from app.memory import MemoryHit


def test_generate_draft_builds_grounded_prompt_and_parses_response(monkeypatch):
    from app import draft_agent

    captured = {}
    expected = {
        "text": "Ihre Bestellung wird derzeit bearbeitet.",
        "confidence": 0.72,
        "internal_note": "Lieferdatum ist nicht bestätigt.",
    }

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(text=json.dumps(expected))]
            )

    class FakeAnthropic:
        def __init__(self, *, api_key):
            captured["api_key"] = api_key
            self.messages = FakeMessages()

    monkeypatch.setattr(draft_agent.anthropic, "Anthropic", FakeAnthropic)

    result = draft_agent.generate_draft(
        transcript="Kundin: Wann wird meine Bestellung versendet?",
        language="de",
        faq_chunks=["Bearbeitung dauert normalerweise 2–3 Werktage."],
        memories=[
            MemoryHit(
                id="7",
                question_summary="Versandstatus",
                final_reply="Die Bestellung wird bearbeitet.",
                score=0.91,
            )
        ],
        instruction="Be concise.",
        settings=Settings(
            anthropic_api_key="test-key",
            anthropic_model="claude-test",
        ),
    )

    assert result == draft_agent.DraftResult(**expected)
    assert captured["api_key"] == "test-key"
    assert captured["model"] == "claude-test"
    assert captured["max_tokens"] > 0

    system = captured["system"]
    assert "Never invent tracking numbers, refund amounts, or stock promises" in system
    assert "Never claim customs included in shipping" in system
    assert "Cloth cut-to-order" in system
    assert "Match the customer language" in system
    assert "lower the confidence" in system
    assert "internal_note" in system

    payload = json.loads(captured["messages"][0]["content"])
    assert payload["transcript"] == "Kundin: Wann wird meine Bestellung versendet?"
    assert payload["language"] == "de"
    assert payload["faq_chunks"] == [
        "Bearbeitung dauert normalerweise 2–3 Werktage."
    ]
    assert payload["memories"] == [
        {
            "question_summary": "Versandstatus",
            "final_reply": "Die Bestellung wird bearbeitet.",
            "score": 0.91,
        }
    ]
    assert payload["instruction"] == "Be concise."


def test_generate_draft_accepts_null_internal_note(monkeypatch):
    from app import draft_agent

    class FakeAnthropic:
        def __init__(self, *, api_key):
            self.messages = SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    content=[
                        SimpleNamespace(
                            text='{"text":"Hello","confidence":0.98,"internal_note":null}'
                        )
                    ]
                )
            )

    monkeypatch.setattr(draft_agent.anthropic, "Anthropic", FakeAnthropic)

    result = draft_agent.generate_draft(
        transcript="Customer: Hello",
        language="en",
        faq_chunks=[],
        memories=[],
        instruction=None,
        settings=Settings(anthropic_api_key="test-key"),
    )

    assert result.internal_note is None
