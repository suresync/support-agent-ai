import httpx

from app.richpanel_client import RichpanelClient


def test_list_conversations_sends_filters_and_returns_fixture():
    fixture = [{"id": "conv-1", "status": "OPEN"}]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/conversations"
        assert dict(request.url.params) == {
            "status": "OPEN",
            "start_date": "2026-08-01",
            "end_date": "2026-08-06",
            "page": "2",
            "per_page": "25",
        }
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json=fixture)

    client = RichpanelClient(
        token="test-token",
        base_url="https://api.example.test/",
        transport=httpx.MockTransport(handler),
    )

    result = client.list_conversations(
        status="OPEN",
        start_date="2026-08-01",
        end_date="2026-08-06",
        page=2,
        per_page=25,
    )

    assert result == fixture


def test_get_conversation_uses_conversation_path():
    fixture = {"id": "conv-1", "subject": "Order status"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/conversations/conv-1"
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json=fixture)

    client = RichpanelClient(
        token="test-token",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    assert client.get_conversation("conv-1") == fixture


def test_send_message_posts_body_to_messages_path():
    fixture = {"id": "message-1", "body": "Your order has shipped."}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/conversations/conv-1/messages"
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.read() == b'{"body":"Your order has shipped."}'
        return httpx.Response(201, json=fixture)

    client = RichpanelClient(
        token="test-token",
        base_url="https://api.example.test",
        transport=httpx.MockTransport(handler),
    )

    assert client.send_message("conv-1", "Your order has shipped.") == fixture
