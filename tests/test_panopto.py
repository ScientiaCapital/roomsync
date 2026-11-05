import asyncio
from collections.abc import Callable
from urllib.parse import parse_qs

import httpx
import pytest
from conftest import FAKE_CLIENT_ID, FAKE_CLIENT_SECRET, FAKE_TOKEN

from roomsync.models import Recorder
from roomsync.platform.panopto import MAX_PAGES, PanoptoClient, PanoptoError
from roomsync.settings import Settings

TOKEN_PATH = "/Panopto/oauth2/connect/token"
SEARCH_PATH = "/Panopto/api/v1/remoteRecorders/search"

Handler = Callable[[httpx.Request], httpx.Response]


def settings() -> Settings:
    return Settings(
        panopto_base_url="https://panopto.example.edu",
        panopto_client_id=FAKE_CLIENT_ID,
        panopto_client_secret=FAKE_CLIENT_SECRET,
        _env_file=None,
    )  # type: ignore[call-arg]


def recorder_json(n: int, state: str | None = "Stopped") -> dict[str, object]:
    body: dict[str, object] = {
        "Id": f"00000000-0000-0000-0000-{n:012d}",
        "Name": f"Room {200 + n} recorder",
        "DefaultRecordingFolder": None,
    }
    if state is not None:
        body["State"] = state
    return body


class FakePanopto:
    """Answers the token call and serves recorder pages; records every request."""

    def __init__(self, pages: list[list[dict[str, object]]], search_status: int = 200, token_status: int = 200):
        self.pages = pages
        self.search_status = search_status
        self.token_status = token_status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == TOKEN_PATH:
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "invalid_client"})
            return httpx.Response(200, json={"access_token": FAKE_TOKEN, "token_type": "Bearer", "expires_in": 3600})
        if request.url.path == SEARCH_PATH:
            if self.search_status != 200:
                return httpx.Response(self.search_status, text=f"denied {FAKE_TOKEN}")
            page = int(request.url.params["pageNumber"])
            results = self.pages[page] if page < len(self.pages) else []
            return httpx.Response(200, json={"Results": results})
        return httpx.Response(404)

    @property
    def searches(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.url.path == SEARCH_PATH]


def run_search(fake: Handler, query: str = "Room") -> list[Recorder]:
    async def go() -> list[Recorder]:
        http = httpx.AsyncClient(transport=httpx.MockTransport(fake))
        async with PanoptoClient(settings(), http=http) as client:
            return await client.search_recorders(query)

    return asyncio.run(go())


def test_token_request_uses_client_credentials_post() -> None:
    fake = FakePanopto(pages=[])
    run_search(fake)
    token = fake.requests[0]
    assert token.method == "POST"
    assert str(token.url) == "https://panopto.example.edu/Panopto/oauth2/connect/token"
    assert token.headers["content-type"] == "application/x-www-form-urlencoded"
    form = {k: v[0] for k, v in parse_qs(token.content.decode()).items()}
    assert form == {
        "grant_type": "client_credentials",
        "scope": "api",
        "client_id": FAKE_CLIENT_ID,
        "client_secret": FAKE_CLIENT_SECRET,
    }
    assert "authorization" not in token.headers


def test_search_sends_bearer_and_query() -> None:
    fake = FakePanopto(pages=[[recorder_json(4)]])
    run_search(fake, query="Room 204")
    search = fake.searches[0]
    assert search.method == "GET"
    assert search.headers["authorization"] == f"Bearer {FAKE_TOKEN}"
    assert search.url.params["searchQuery"] == "Room 204"
    assert search.url.params["pageNumber"] == "0"


def test_pages_until_empty_and_maps_fields() -> None:
    fake = FakePanopto(pages=[[recorder_json(1), recorder_json(2, state=None)], [recorder_json(3, "Recording")]])
    recorders = run_search(fake)
    assert [r.url.params["pageNumber"] for r in fake.searches] == ["0", "1", "2"]
    assert recorders == [
        Recorder(id="00000000-0000-0000-0000-000000000001", name="Room 201 recorder", state="Stopped"),
        Recorder(id="00000000-0000-0000-0000-000000000002", name="Room 202 recorder", state=None),
        Recorder(id="00000000-0000-0000-0000-000000000003", name="Room 203 recorder", state="Recording"),
    ]


def test_token_is_fetched_once_per_client() -> None:
    fake = FakePanopto(pages=[[recorder_json(1)], [recorder_json(2)]])
    run_search(fake)
    assert sum(1 for r in fake.requests if r.url.path == TOKEN_PATH) == 1


def test_empty_first_page_returns_nothing() -> None:
    fake = FakePanopto(pages=[])
    assert run_search(fake) == []
    assert len(fake.searches) == 1


def test_null_results_count_as_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            return httpx.Response(200, json={"access_token": FAKE_TOKEN})
        return httpx.Response(200, json={"Results": None})

    assert run_search(handler) == []


def test_page_cap_raises_instead_of_looping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            return httpx.Response(200, json={"access_token": FAKE_TOKEN})
        return httpx.Response(200, json={"Results": [recorder_json(1)]})

    with pytest.raises(PanoptoError, match="page"):
        run_search(handler)


def test_page_cap_value() -> None:
    assert MAX_PAGES == 1000


@pytest.mark.parametrize("status", [401, 403])
def test_search_auth_errors_name_call_without_secrets(status: int) -> None:
    fake = FakePanopto(pages=[], search_status=status)
    with pytest.raises(PanoptoError) as info:
        run_search(fake)
    message = str(info.value)
    assert "remoteRecorders/search" in message
    assert str(status) in message
    assert FAKE_CLIENT_SECRET not in message
    assert FAKE_TOKEN not in message
    assert FAKE_CLIENT_SECRET not in repr(info.value)
    assert FAKE_TOKEN not in repr(info.value)


@pytest.mark.parametrize("status", [400, 401, 403, 500])
def test_token_errors_name_call_without_secrets(status: int) -> None:
    fake = FakePanopto(pages=[], token_status=status)
    with pytest.raises(PanoptoError) as info:
        run_search(fake)
    message = str(info.value)
    assert "token" in message
    assert str(status) in message
    assert FAKE_CLIENT_SECRET not in message
    assert info.value.__cause__ is None or FAKE_CLIENT_SECRET not in str(info.value.__cause__)


def test_other_search_errors_raise() -> None:
    fake = FakePanopto(pages=[], search_status=500)
    with pytest.raises(PanoptoError, match="500"):
        run_search(fake)


def test_token_response_without_access_token_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"token_type": "Bearer"})

    with pytest.raises(PanoptoError, match="access_token"):
        run_search(handler)


def test_malformed_search_body_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == TOKEN_PATH:
            return httpx.Response(200, json={"access_token": FAKE_TOKEN})
        return httpx.Response(200, text="<html>not json</html>")

    with pytest.raises(PanoptoError, match="remoteRecorders/search"):
        run_search(handler)


def test_transport_error_becomes_panopto_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(PanoptoError, match="token"):
        run_search(handler)


def test_client_repr_hides_secret_and_token() -> None:
    async def go() -> str:
        fake = FakePanopto(pages=[])
        http = httpx.AsyncClient(transport=httpx.MockTransport(fake))
        async with PanoptoClient(settings(), http=http) as client:
            await client.search_recorders("Room")
            return repr(client) + str(vars(client))

    text = asyncio.run(go())
    assert FAKE_CLIENT_SECRET not in text
    assert FAKE_TOKEN not in text


def test_injected_http_client_is_not_closed() -> None:
    async def go() -> bool:
        http = httpx.AsyncClient(transport=httpx.MockTransport(FakePanopto(pages=[])))
        async with PanoptoClient(settings(), http=http):
            pass
        closed = http.is_closed
        await http.aclose()
        return closed

    assert asyncio.run(go()) is False
