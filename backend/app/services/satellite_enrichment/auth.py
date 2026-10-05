"""OAuth2 client-credentials token handling for the Copernicus Data Space
Ecosystem (CDSE). Confirmed live and unauthenticated-reachable (returns a
clear 401 without a token, rather than a generic error) on 2026-09-27:

    curl -X POST https://sh.dataspace.copernicus.eu/api/v1/statistics
    -> 401 {"error":{"code":"COMMON_UNAUTHORIZED", ...}}

Token endpoint and grant type per
https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html.
Not yet verified against a real client_id/secret (none was available while
building this) - the request/response shape below is the standard Keycloak
client_credentials flow that endpoint uses, but confirm with a real account
before bulk use.
"""

import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger("satellite_enrichment.auth")


class CdseConfigError(Exception):
    """Missing credentials, or the identity server rejected them."""


class CdseAuthError(Exception):
    """Token request failed for a reason other than bad/missing credentials."""


@dataclass
class _CachedToken:
    access_token: str
    expires_at: float  # epoch seconds


class CdseTokenProvider:
    """Fetches and caches an access token, reusing it until shortly before
    expiry. The identity server explicitly rate-limits token requests, so
    never fetch a fresh one per API call - see this module's docstring."""

    def __init__(self, client_id: str | None, client_secret: str | None, token_url: str, timeout_seconds: float = 15.0):
        self._client_id = client_id
        self._client_secret = client_secret
        self._token_url = token_url
        self._timeout = timeout_seconds
        self._cached: _CachedToken | None = None

    def get_token(self, client: httpx.Client) -> str:
        if not self._client_id or not self._client_secret:
            raise CdseConfigError(
                "CDSE_CLIENT_ID/CDSE_CLIENT_SECRET are not set - register a free "
                "OAuth client at https://dataspace.copernicus.eu/ (see backend/README.md)."
            )

        now = time.monotonic()
        if self._cached and self._cached.expires_at - 30 > now:
            return self._cached.access_token

        try:
            response = client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise CdseAuthError(f"Token request failed: {exc}") from exc

        if response.status_code in (400, 401):
            raise CdseConfigError(f"CDSE rejected the OAuth client credentials (HTTP {response.status_code})")
        if response.status_code != 200:
            raise CdseAuthError(f"Token endpoint returned HTTP {response.status_code}: {response.text[:200]}")

        body = response.json()
        access_token = body.get("access_token")
        expires_in = body.get("expires_in")
        if not access_token or not isinstance(expires_in, (int, float)):
            raise CdseAuthError("Token response missing access_token/expires_in")

        self._cached = _CachedToken(access_token=access_token, expires_at=time.monotonic() + expires_in)
        return access_token
