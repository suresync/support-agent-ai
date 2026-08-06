from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.db import log_audit
from app.memory import add_memory


@dataclass(frozen=True)
class SendResult:
    ok: bool
    status: str
    error: str | None = None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _messages(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    payload: Any = conversation.get("data", conversation)
    if not isinstance(payload, dict):
        return []
    messages: Any = payload.get("messages", [])
    if isinstance(messages, dict):
        messages = messages.get("data", messages.get("items", []))
    return [message for message in messages if isinstance(message, dict)]


def _is_outbound_agent_message(message: dict[str, Any]) -> bool:
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
    is_outbound = direction in {"outbound", "outgoing", "out"}
    is_agent = role in {"agent", "operator", "admin", "staff"}
    return (is_outbound and (is_agent or not role)) or (is_agent and not direction)


def _has_newer_outbound(
    conversation: dict[str, Any], draft_created_at: datetime
) -> bool:
    for message in _messages(conversation):
        if not _is_outbound_agent_message(message):
            continue
        created_at = _parse_timestamp(
            message.get("created_at")
            or message.get("sent_at")
            or message.get("timestamp")
        )
        if created_at is not None and created_at > draft_created_at:
            return True
    return False


def approve_and_send(
    conn, client, draft_id: str, *, dry_run: bool
) -> SendResult:
    row = conn.execute(
        """
        SELECT
            d.conversation_id,
            d.status,
            d.draft_text,
            d.edited_text,
            d.created_at,
            c.subject,
            c.language
        FROM drafts AS d
        JOIN conversations AS c ON c.id = d.conversation_id
        WHERE d.id = ?
        """,
        (draft_id,),
    ).fetchone()
    if row is None:
        return SendResult(False, "not_found", f"Draft {draft_id!r} was not found")

    (
        conversation_id,
        current_status,
        draft_text,
        edited_text,
        created_at,
        subject,
        language,
    ) = row
    draft_created_at = _parse_timestamp(created_at)
    if draft_created_at is None:
        return SendResult(False, current_status, "Draft has an invalid created_at")

    conversation = client.get_conversation(conversation_id)
    if _has_newer_outbound(conversation, draft_created_at):
        return SendResult(
            False,
            current_status,
            "A newer outbound agent/operator message already exists",
        )

    final_text = edited_text if edited_text is not None else draft_text
    if final_text is None:
        return SendResult(False, current_status, "Draft has no text to send")

    status = "sent_simulated" if dry_run else "sent"
    if not dry_run:
        client.send_message(conversation_id, final_text)

    now = datetime.now(UTC).isoformat()
    conn.execute(
        """
        UPDATE drafts
        SET status = ?, updated_at = ?, reviewed_at = ?, sent_at = ?
        WHERE id = ?
        """,
        (status, now, now, now, draft_id),
    )
    add_memory(
        conn,
        question_summary=subject or f"Conversation {conversation_id}",
        final_reply=final_text,
        language=language or "unknown",
        theme_tags=[],
        source="approved_live",
        conversation_id=conversation_id,
    )
    log_audit(
        conn,
        "approve_send",
        conversation_id=conversation_id,
        draft_id=draft_id,
        detail={"status": status, "dry_run": dry_run},
    )
    conn.commit()
    return SendResult(True, status, None)
