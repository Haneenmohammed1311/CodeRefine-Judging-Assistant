"""
Real login-based authentication, replacing a static key that would sit
visibly in the website's own code forever.

How this is different and better: instead of one forever-valid secret
baked into the page (readable by anyone via "View Page Source"), a judge
types a PASSWORD once. The server checks it and hands back a randomly
generated SESSION TOKEN, valid for a few hours. That token not the
password is what the website then uses for further requests, and it's
never written into the page's source code; it only ever exists in the
browser's memory for that session, and expires on its own.

"""

import os
import secrets
import time
from fastapi import Header, HTTPException

# In-memory session store: {token: (role, expires_at_timestamp)}.
# Fine at this scale (one small competition, one running process) --
# would need a shared store (e.g. Redis) if this ever ran as multiple
# server instances behind a load balancer.
_sessions: dict[str, tuple[str, float]] = {}

SESSION_LIFETIME_SECONDS = 5 * 60 * 60  # 5 hours


def create_session(role: str) -> str:
    token = secrets.token_hex(32)
    _sessions[token] = (role, time.time() + SESSION_LIFETIME_SECONDS)
    return token


def _validate_session(token: str, required_role: str) -> None:
    entry = _sessions.get(token)
    if entry is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please log in again.")
    role, expires_at = entry
    if time.time() > expires_at:
        del _sessions[token]
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    if role != required_role:
        raise HTTPException(status_code=403, detail="This session does not have access to this action.")


def require_team_session(x_session_token: str = Header(...)) -> None:
    _validate_session(x_session_token, "team")


def require_judge_session(x_session_token: str = Header(...)) -> None:
    _validate_session(x_session_token, "judge")


def check_login_password(password: str, role: str) -> bool:
    expected = os.environ.get(f"{role.upper()}_PASSWORD")
    return bool(expected) and secrets.compare_digest(password, expected)
