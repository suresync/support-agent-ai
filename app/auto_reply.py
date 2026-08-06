"""Detect generic auto-reply messages that should be filtered out."""

_AUTO_REPLY_PHRASES = (
    'reply to this email with a "hi"',
    "did you mean to check the status",
    "auto-response",
)


def is_generic_auto_reply(text: str) -> bool:
    """Return True if text matches known generic auto-responder patterns."""
    lowered = text.lower()
    return any(phrase in lowered for phrase in _AUTO_REPLY_PHRASES)
