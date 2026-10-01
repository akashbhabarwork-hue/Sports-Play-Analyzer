"""Google OpenID Connect login via Authlib (Authorization Code + PKCE S256, state, nonce).

Endpoints are registered explicitly (no discovery fetch per login). Authlib validates the
ID token signature against Google's JWKS, plus aud, iss, nonce and expiry.
"""

import logging
from typing import Any

import httpx2
from authlib.integrations.starlette_client import OAuth, OAuthError
from joserfc.errors import JoseError

from ..core.models import OAuthProfile
from ..errors import OAuthLoginError

logger = logging.getLogger(__name__)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUER = "https://accounts.google.com"
# Google documents both issuer spellings for its ID tokens.
ID_TOKEN_CLAIMS = {"iss": {"values": [GOOGLE_ISSUER, "accounts.google.com"]}}


class GoogleOAuthClient:
    def __init__(self, client_id: str, client_secret: str):
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            authorize_url=GOOGLE_AUTHORIZE_URL,
            access_token_url=GOOGLE_TOKEN_URL,
            jwks_uri=GOOGLE_JWKS_URI,
            issuer=GOOGLE_ISSUER,
            client_kwargs={"scope": "openid email profile", "code_challenge_method": "S256"},
        )
        self.client = oauth.google

    async def authorize_redirect(self, request: Any, redirect_uri: str) -> Any:
        # Generates state, nonce and the PKCE verifier; keeps them in the transient
        # SessionMiddleware cookie and redirects to Google with the S256 challenge.
        return await self.client.authorize_redirect(request, redirect_uri)

    async def fetch_profile(self, request: Any) -> OAuthProfile:
        try:
            token = await self.client.authorize_access_token(
                request, claims_options=ID_TOKEN_CLAIMS
            )
        except (OAuthError, JoseError, httpx2.HTTPError) as e:
            # Log the type only: provider messages can echo codes or state values.
            logger.warning("google login failed", extra={"error_type": type(e).__name__})
            raise OAuthLoginError("Google login failed") from e

        info = token.get("userinfo") or {}
        if not info.get("sub"):
            raise OAuthLoginError("Google login returned no account id")
        return OAuthProfile(
            provider="google",
            sub=str(info["sub"]),
            # An unverified address is not trusted as an identity attribute.
            email=info.get("email") if info.get("email_verified") else None,
            name=info.get("name"),
            avatar_url=info.get("picture"),
        )
