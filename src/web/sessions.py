"""
sessions.py

Per-browser session tokens, sitting between the encrypted vault
(security/env_vault.py) and the routes in api.py.

Unlocking the vault used to be a single process-wide fact: once ANY
client posted the right password to POST /api/unlock, every other
client reaching the port afterward was treated as authorized too,
forever (or until the process restarted) — fine on a laptop nobody
else can reach, a real hole the moment the port is forwarded to the
internet. This module makes "unlocked" a property of one browser's
cookie instead: POST /api/unlock (web/api.py) now calls create() and
sets that token as a cookie on the response, and deps.get_runtime()
requires a request to present a still-valid one before it hands back
the live AppRuntime.

Deliberately process-lifetime only, same as env_vault's cached key: no
persistence to disk, so every session is gone on restart along with the
decrypted vault itself. An opaque, server-side-checked random token
(rather than a signed cookie via itsdangerous/starlette's
SessionMiddleware) keeps this dependency-free and is exactly as secure
here, since validity is always re-checked against this dict, never
inferred from the token's own contents.
"""

import secrets
import time

COOKIE_NAME = "cvc_session"

# Sliding idle timeout: a session stays valid as long as it is used at
# least once every this many seconds. Chosen to match a full workday
# without forcing a re-login mid-use, while still expiring a forgotten
# open tab well before "indefinitely".
IDLE_TIMEOUT_SECONDS = 12 * 60 * 60

_sessions: dict[str, float] = {}  # token -> last_seen epoch seconds


def create() -> str:
    """Issues a new session token for a request that just proved it
    knows the vault password (see web/api.py's POST /api/unlock)."""
    token = secrets.token_urlsafe(32)
    _sessions[token] = time.time()
    return token


def touch(token: str | None) -> bool:
    """True (and refreshes the idle timer) if `token` is a live
    session; False for a missing/unknown/expired one. Every protected
    route calls this through deps.get_runtime() on every request, so
    an active browser's session never goes idle while it is actually
    being used."""
    if token is None:
        return False
    last_seen = _sessions.get(token)
    if last_seen is None:
        return False
    if time.time() - last_seen > IDLE_TIMEOUT_SECONDS:
        _sessions.pop(token, None)
        return False
    _sessions[token] = time.time()
    return True


def invalidate(token: str | None) -> None:
    if token is not None:
        _sessions.pop(token, None)


def invalidate_all() -> None:
    """Called when the app shuts down / the vault is conceptually
    re-locked, so no stale cookie is honored if the process were ever
    reused without restarting."""
    _sessions.clear()
