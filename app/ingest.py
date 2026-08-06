from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.draft_agent import generate_draft
from app.faq import load_faq_chunks
from app.language import detect_language
from app.memory import search_similar


@dataclass(frozen=True)
class SyncStats:
    conversations_seen: int = 0
    conversations_upserted: int = 0
    drafts_created: int = 0
    drafts_skipped: int = 0


def _payload(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("data"), (dict, list)):
        return value["data"]
    return value


def _conversation_list(response: Any) -> list[dict[str, Any]]:
    response = _payload(response)
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if not isinstance(response, dict):
        return []
    for key in ("conversations", "items", "results"):
        items = response.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _messages(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    conversation = _payload(conversation)
    if not isinstance(conversation, dict):
        return []
    messages: Any = conversation.get("messages", [])
    messages = _payload(messages)
    if isinstance(messages, dict):
        messages = messages.get("items", messages.get("results", []))
    if not isinstance(messages, list):
        return []
    return [message for message in messages if isinstance(message, dict)]


def _text(message: dict[str, Any]) -> str:
    for key in ("body", "text", "message", "content"):
        value = message.get(key)
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            nested = value.get("text") or value.get("body")
            if isinstance(nested, str):
                return nested.strip()
    return ""


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _message_timestamp(message: dict[str, Any]) -> str | None:
    value = (
        message.get("created_at")
        or message.get("sent_at")
        or message.get("timestamp")
        or message.get("updated_at")
    )
    return value if isinstance(value, str) else None


def _is_customer_message(message: dict[str, Any]) -> bool:
    direction = str(
        message.get("direction") or message.get("message_direction") or ""
    ).lower()
    role = str(
        message.get("sender_type")
        or message.get("actor_type")
        or message.get("user_type")
        or message.get("role")
        or ""
    ).lower()
    return direction in {"inbound", "incoming", "in"} or role in {
        "customer",
        "contact",
        "end_user",
        "user",
    }


def _customer(conversation: dict[str, Any]) -> tuple[str | None, str | None]:
    customer = conversation.get("customer") or conversation.get("contact") or {}
    if not isinstance(customer, dict):
        customer = {}
    email = (
        customer.get("email")
        or conversation.get("customer_email")
        or conversation.get("email")
    )
    name = (
        customer.get("name")
        or customer.get("full_name")
        or conversation.get("customer_name")
    )
    return (
        str(email) if email is not None else None,
        str(name) if name is not None else None,
    )


def _channel(conversation: dict[str, Any]) -> str | None:
    value: Any = (
        conversation.get("channel")
        or conversation.get("source")
        or conversation.get("via")
    )
    if isinstance(value, dict):
        value = value.get("type") or value.get("name")
    return str(value).lower() if value is not None else None


def _transcript(conversation: dict[str, Any]) -> tuple[str, str | None, str]:
    lines: list[str] = []
    customer_messages: list[tuple[datetime | None, str | None, str]] = []
    for message in _messages(conversation):
        body = _text(message)
        if not body:
            continue
        is_customer = _is_customer_message(message)
        lines.append(f"{'Customer' if is_customer else 'Agent'}: {body}")
        if is_customer:
            raw_ts = _message_timestamp(message)
            customer_messages.append((_timestamp(raw_ts), raw_ts, body))

    if customer_messages:
        customer_messages.sort(
            key=lambda item: item[0] or datetime.min.replace(tzinfo=UTC)
        )
        _, last_customer_at, latest_customer_text = customer_messages[-1]
    else:
        last_customer_at = conversation.get("last_customer_message_at")
        latest_customer_text = str(conversation.get("subject") or "")

    transcript = "\n".join(lines) or latest_customer_text
    return transcript, last_customer_at, latest_customer_text


def _is_newer(customer_at: str | None, draft_at: str) -> bool:
    customer_timestamp = _timestamp(customer_at)
    draft_timestamp = _timestamp(draft_at)
    return (
        customer_timestamp is not None
        and draft_timestamp is not None
        and customer_timestamp > draft_timestamp
    )


def sync_once(conn, client, settings) -> SyncStats:
    now = datetime.now(UTC)
    page = 1
    page_size = 50
    conversations: list[dict[str, Any]] = []
    while True:
        response = client.list_conversations(
            status="OPEN",
            start_date=(now - timedelta(days=7)).date().isoformat(),
            end_date=now.date().isoformat(),
            page=page,
            per_page=page_size,
        )
        page_conversations = _conversation_list(response)
        conversations.extend(page_conversations)
        if len(page_conversations) < page_size:
            break
        page += 1

    seen = len(conversations)
    upserted = 0
    created = 0
    skipped = 0
    faq_chunks: list[str] | None = None

    for listed in conversations:
        listed = _payload(listed)
        if not isinstance(listed, dict):
            continue
        channel = _channel(listed)
        if channel and channel not in {"email", "mail"}:
            continue

        conversation = listed
        if not _messages(listed):
            get_conversation = getattr(client, "get_conversation", None)
            if callable(get_conversation):
                detailed = _payload(get_conversation(str(listed.get("id"))))
                if isinstance(detailed, dict):
                    conversation = {**listed, **detailed}

        conversation_id = (
            conversation.get("id")
            or conversation.get("conversation_id")
            or conversation.get("_id")
        )
        if conversation_id is None:
            continue
        conversation_id = str(conversation_id)
        transcript, last_customer_at, latest_customer_text = _transcript(
            conversation
        )
        language = detect_language(latest_customer_text or transcript)
        customer_email, customer_name = _customer(conversation)
        updated_at = conversation.get("updated_at") or now.isoformat()
        channel = _channel(conversation)

        conn.execute(
            """
            INSERT INTO conversations (
                id, conversation_no, subject, status, channel,
                customer_email, customer_name, language,
                last_customer_message_at, updated_at, raw_snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                conversation_no = excluded.conversation_no,
                subject = excluded.subject,
                status = excluded.status,
                channel = excluded.channel,
                customer_email = excluded.customer_email,
                customer_name = excluded.customer_name,
                language = excluded.language,
                last_customer_message_at = excluded.last_customer_message_at,
                updated_at = excluded.updated_at,
                raw_snapshot_json = excluded.raw_snapshot_json
            """,
            (
                conversation_id,
                conversation.get("conversation_no")
                or conversation.get("number"),
                conversation.get("subject"),
                conversation.get("status") or "OPEN",
                channel,
                customer_email,
                customer_name,
                language,
                last_customer_at,
                str(updated_at),
                json.dumps(conversation, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        upserted += 1

        active = conn.execute(
            """
            SELECT id, created_at
            FROM drafts
            WHERE conversation_id = ? AND status = 'needs_review'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (conversation_id,),
        ).fetchone()
        if active is not None and not _is_newer(last_customer_at, active[1]):
            continue
        if active is not None:
            cursor = conn.execute(
                """
                UPDATE drafts
                SET status = 'skipped', updated_at = ?
                WHERE conversation_id = ? AND status = 'needs_review'
                """,
                (now.isoformat(), conversation_id),
            )
            skipped += cursor.rowcount

        if faq_chunks is None:
            faq_chunks = load_faq_chunks(Path(__file__).resolve().parent.parent)
        memories = search_similar(
            conn,
            latest_customer_text or transcript,
            language=language,
            limit=5,
        )
        result = generate_draft(
            transcript=transcript,
            language=language,
            faq_chunks=faq_chunks,
            memories=memories,
            instruction=None,
            settings=settings,
        )
        draft_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        conn.execute(
            """
            INSERT INTO drafts (
                id, conversation_id, status, draft_text, internal_note,
                confidence, model, prompt_version, created_at, updated_at
            )
            VALUES (?, ?, 'needs_review', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                conversation_id,
                result.text,
                result.internal_note,
                result.confidence,
                settings.anthropic_model,
                "v1",
                created_at,
                created_at,
            ),
        )
        created += 1

    conn.commit()
    return SyncStats(seen, upserted, created, skipped)
