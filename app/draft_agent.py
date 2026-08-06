from __future__ import annotations

import json
from dataclasses import dataclass

import anthropic

from app.config import Settings
from app.memory import MemoryHit


SYSTEM_PROMPT = """You draft customer-support replies using only the supplied context.

Hard constraints:
- Never invent tracking numbers, refund amounts, or stock promises not present in the context.
- Never claim customs included in shipping.
- Cloth cut-to-order is generally non-returnable.
- Match the customer language specified in the payload.
- If uncertain, lower the confidence and provide an internal_note for a human reviewer.

Return only valid JSON with exactly these fields:
{"text": "reply to customer", "confidence": 0.0, "internal_note": null}
confidence must be a number from 0 to 1. internal_note must be a string or null.
"""


@dataclass
class DraftResult:
    text: str
    confidence: float
    internal_note: str | None


def generate_draft(
    *,
    transcript: str,
    language: str,
    faq_chunks: list[str],
    memories: list[MemoryHit],
    instruction: str | None,
    settings: Settings,
) -> DraftResult:
    payload = {
        "transcript": transcript,
        "language": language,
        "faq_chunks": faq_chunks,
        "memories": [
            {
                "question_summary": memory.question_summary,
                "final_reply": memory.final_reply,
                "score": memory.score,
            }
            for memory in memories
        ],
        "instruction": instruction,
    }

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    parsed = json.loads(response.content[0].text)
    return DraftResult(
        text=parsed["text"],
        confidence=float(parsed["confidence"]),
        internal_note=parsed["internal_note"],
    )
