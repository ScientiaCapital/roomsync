"""Read-only Panopto client. Every call here is in Panopto's published API description; nothing in RemoteRecorderAPI
is used.

Spec: Panopto Public API v1, `/Panopto/api/v1/panoptoApi.json` on any Panopto site (Swagger 2.0, base path
`/Panopto`). Auth: the OpenID discovery document `/Panopto/oauth2/.well-known/openid-configuration`, which the spec's
`info.description` names.
"""

from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from roomsync.models import Recorder
from roomsync.settings import Settings

MAX_PAGES = 1000
"""Stop paging here and raise. The spec gives no page limit, so this only guards against a server that never ends."""

TOKEN_CALL = "POST /Panopto/oauth2/connect/token"
SEARCH_CALL = "GET /Panopto/api/v1/remoteRecorders/search"


class PanoptoError(Exception):
    """A Panopto call failed. The message names the call and the HTTP status, never a secret, token or body."""


class _RemoteRecorder(BaseModel):
    """Spec definition `RemoteRecorder`: `Id` (guid), `Name`, `State` (`RemoteRecorderState`), `DefaultRecordingFolder`.

    The spec marks `State` required; it is optional here so one odd row doesn't hide the rest.
    """

    model_config = ConfigDict(extra="ignore")

    Id: str
    Name: str
    State: str | None = None


class _ListResponseOfRemoteRecorder(BaseModel):
    """Spec definition `ListResponseOfRemoteRecorder`: one property, `Results`, an array of `RemoteRecorder`."""

    model_config = ConfigDict(extra="ignore")

    Results: list[_RemoteRecorder] | None = None


class PanoptoClient:
    """Reads a Panopto site. Use as an async context manager.

    `panopto_base_url` is the site root (https://panopto.example.edu); the client adds the spec's `/Panopto` base.
    Pass `http` to supply the httpx client (tests pass one with a MockTransport). An injected client is not closed.
    """

    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None) -> None:
        self._base = str(settings.panopto_base_url).rstrip("/") + "/Panopto"
        self._client_id = settings.panopto_client_id
        self._client_secret = settings.panopto_client_secret
        # Never follow a redirect, so every request goes only to the configured site. SECURITY.md relies on it.
        self._http = http if http is not None else httpx.AsyncClient(timeout=30.0, follow_redirects=False)
        self._owns_http = http is None
        self._token: SecretStr | None = None

    def __repr__(self) -> str:
        return f"PanoptoClient(base={self._base!r})"

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _access_token(self) -> str:
        """Get an OAuth2 token with the client-credentials grant, cached for the life of this client.

        Endpoint, grant and scope come from the OpenID discovery document named in the spec's `info.description`:
        token endpoint `/Panopto/oauth2/connect/token`, grant `client_credentials`, scope `api`, client auth
        `client_secret_post` (discovery also lists `client_secret_basic`). UNVERIFIED: nobody has confirmed this grant
        and scope are right for a roomsync client on a given site. The spec has no token response schema;
        `access_token` is the standard OAuth2 field name.
        """
        if self._token is not None:
            return self._token.get_secret_value()
        form = {
            "grant_type": "client_credentials",
            "scope": "api",
            "client_id": self._client_id,
            "client_secret": self._client_secret.get_secret_value(),
        }
        # Discovery doc /Panopto/oauth2/.well-known/openid-configuration, token_endpoint
        response = await self._send(TOKEN_CALL, "POST", "/oauth2/connect/token", data=form)
        try:
            token = response.json()["access_token"]
        except (ValueError, KeyError, TypeError):
            raise PanoptoError(f"{TOKEN_CALL} returned no access_token") from None
        if not isinstance(token, str) or not token:
            raise PanoptoError(f"{TOKEN_CALL} returned no access_token")
        self._token = SecretStr(token)
        return token

    async def search_recorders(self, query: str) -> list[Recorder]:
        """List the remote recorders that match `query`, reading every page.

        The spec: "To fetch all elements, this endpoint can be called multiple times, starting at pageNumber = 0 and
        incrementing the page number until no results are returned." Raises PanoptoError after MAX_PAGES pages.
        """
        token = await self._access_token()
        recorders: list[Recorder] = []
        for page in range(MAX_PAGES):
            # Spec path /api/v1/remoteRecorders/search (RemoteRecorders tag),
            # 200 schema ListResponseOfRemoteRecorder.
            response = await self._send(
                SEARCH_CALL,
                "GET",
                "/api/v1/remoteRecorders/search",
                params={"searchQuery": query, "pageNumber": page},
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                body = _ListResponseOfRemoteRecorder.model_validate_json(response.content)
            except ValidationError:
                raise PanoptoError(f"{SEARCH_CALL} page {page} returned a body that is not a recorder list") from None
            if not body.Results:
                return recorders
            recorders.extend(Recorder(id=r.Id, name=r.Name, state=r.State) for r in body.Results)
        raise PanoptoError(f"{SEARCH_CALL} still returned results after {MAX_PAGES} pages; stopped")

    async def _send(self, call: str, method: str, path: str, **kwargs: object) -> httpx.Response:
        """Send one request. Any failure becomes a PanoptoError naming `call`, with no request detail attached."""
        try:
            response = await self._http.request(method, self._base + path, **kwargs)  # type: ignore[arg-type]
        except httpx.HTTPError as exc:
            raise PanoptoError(f"{call} failed: {type(exc).__name__}") from None
        if response.status_code in (401, 403):
            raise PanoptoError(
                f"{call} returned HTTP {response.status_code}: the client credentials were refused or lack access"
            )
        if not response.is_success:
            raise PanoptoError(f"{call} returned HTTP {response.status_code}")
        return response
