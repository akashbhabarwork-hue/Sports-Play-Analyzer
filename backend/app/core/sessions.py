"""Pure session helpers. Token generation (randomness) lives in services/auth.py."""

import hashlib
from datetime import datetime, timedelta


def hash_token(token: str) -> bytes:
    """sha256 of the cookie token; only this is stored, so a DB leak exposes no sessions."""
    return hashlib.sha256(token.encode()).digest()


def session_expiry(now: datetime, ttl_days: int) -> datetime:
    return now + timedelta(days=ttl_days)
