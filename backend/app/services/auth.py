"""Login / logout use cases. Sync; the async /auth routes call these via run_in_threadpool."""

import logging
import secrets
from datetime import datetime

from ..core.models import OAuthProfile, User
from ..core.ports import SessionRepo, UserRepo
from ..core.sessions import hash_token, session_expiry

logger = logging.getLogger(__name__)


def login_user(
    users: UserRepo,
    sessions: SessionRepo,
    profile: OAuthProfile,
    now: datetime,
    ttl_days: int,
    previous_token: str | None = None,
) -> tuple[User, str]:
    """Upsert the user and start a fresh session. Returns the raw token for the cookie.

    A session the browser already had is deleted first (rotation: no session fixation).
    """
    user = users.upsert_from_oauth(
        profile.provider, profile.sub, profile.email, profile.name, profile.avatar_url
    )
    if previous_token:
        sessions.delete(hash_token(previous_token))
    token = secrets.token_urlsafe(32)
    sessions.create(hash_token(token), user.id, session_expiry(now, ttl_days))
    logger.info("user logged in", extra={"user_id": str(user.id)})
    return user, token


def logout(sessions: SessionRepo, token: str | None) -> None:
    if token:
        sessions.delete(hash_token(token))


def user_for_token(sessions: SessionRepo, token: str | None) -> User | None:
    if not token:
        return None
    return sessions.get_user_by_token(hash_token(token))
