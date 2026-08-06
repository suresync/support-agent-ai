import httpx


CONVERSATIONS_PATH = "/v1/conversations"
CONVERSATION_PATH = "/v1/conversations/{conversation_id}"
MESSAGES_PATH = "/v1/conversations/{conversation_id}/messages"


class RichpanelClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {token}"},
            transport=transport,
        )

    def list_conversations(
        self,
        *,
        status: str,
        start_date: str,
        end_date: str,
        page: int = 1,
        per_page: int = 50,
    ) -> list[dict]:
        response = self._client.get(
            CONVERSATIONS_PATH,
            params={
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
                "page": page,
                "per_page": per_page,
            },
        )
        response.raise_for_status()
        return response.json()

    def get_conversation(self, conversation_id: str) -> dict:
        response = self._client.get(
            CONVERSATION_PATH.format(conversation_id=conversation_id)
        )
        response.raise_for_status()
        return response.json()

    def send_message(self, conversation_id: str, body: str) -> dict:
        response = self._client.post(
            MESSAGES_PATH.format(conversation_id=conversation_id),
            json={"body": body},
        )
        response.raise_for_status()
        return response.json()
