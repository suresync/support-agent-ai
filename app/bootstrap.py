from __future__ import annotations

from typing import Any

from app.auto_reply import is_generic_auto_reply
from app.language import detect_language
from app.memory import add_memory

_PAGE_SIZE = 50
_SUMMARY_LIMIT = 500


def _payload(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("data"), (dict, list)):
        return value["data"]
    return value


def _conversations(response: Any) -> list[dict[str, Any]]:
    response = _payload(response)
    if isinstance(response, list):
        return [item for item in response if isinstance(item, dict)]
    if isinstance(response, dict):
        for key in ("conversations", "items", "results"):
            items = response.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
    return []


def _messages(conversation: dict[str, Any]) -> list[dict[str, Any]]:
    messages = _payload(conversation.get("messages", []))
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


def _role(message: dict[str, Any]) -> str:
    return str(
        message.get("sender_type")
        or message.get("actor_type")
        or message.get("user_type")
        or message.get("role")
        or ""
    ).lower()


def _is_customer(message: dict[str, Any]) -> bool:
    direction = str(
        message.get("direction") or message.get("message_direction") or ""
    ).lower()
    return direction in {"inbound", "incoming", "in"} or _role(message) in {
        "customer",
        "contact",
        "end_user",
        "user",
    }


def _is_agent(message: dict[str, Any]) -> bool:
    direction = str(
        message.get("direction") or message.get("message_direction") or ""
    ).lower()
    return direction in {"outbound", "outgoing", "out"} or _role(message) in {
        "agent",
        "admin",
        "operator",
        "teammate",
    }


def _truncate(text: str) -> str:
    if len(text) <= _SUMMARY_LIMIT:
        return text
    return text[: _SUMMARY_LIMIT - 1].rstrip() + "…"


def bootstrap_memory(
    conn,
    client,
    *,
    start_date: str,
    end_date: str,
    settings,
) -> int:
    """Seed approved memory from human replies in closed conversations."""
    del settings  # Reserved for a future model-based question summarizer.
    inserted = 0
    page = 1

    while True:
        listed_conversations = _conversations(
            client.list_conversations(
                status="CLOSED",
                start_date=start_date,
                end_date=end_date,
                page=page,
                per_page=_PAGE_SIZE,
            )
        )
        if not listed_conversations:
            break

        for listed in listed_conversations:
            conversation = listed
            messages = _messages(conversation)
            if not messages:
                conversation_id = (
                    listed.get("id")
                    or listed.get("conversation_id")
                    or listed.get("_id")
                )
                get_conversation = getattr(client, "get_conversation", None)
                if conversation_id is not None and callable(get_conversation):
                    detailed = _payload(get_conversation(str(conversation_id)))
                    if isinstance(detailed, dict):
                        conversation = {**listed, **detailed}
                        messages = _messages(conversation)

            conversation_id = (
                conversation.get("id")
                or conversation.get("conversation_id")
                or conversation.get("_id")
            )
            last_customer_message = ""
            for message in messages:
                body = _text(message)
                if not body:
                    continue
                if _is_customer(message):
                    last_customer_message = body
                    continue
                if (
                    not _is_agent(message)
                    or not last_customer_message
                    or is_generic_auto_reply(body)
                ):
                    continue

                question_summary = _truncate(last_customer_message)
                add_memory(
                    conn,
                    question_summary=question_summary,
                    final_reply=body,
                    language=detect_language(question_summary),
                    theme_tags=[],
                    source="historic",
                    conversation_id=(
                        str(conversation_id)
                        if conversation_id is not None
                        else None
                    ),
                )
                inserted += 1

        page += 1

    return inserted
