"""
deps.py

Reference to the live AppRuntime, shared between server.py (which
creates/replaces the runtime) and api.py (which consumes it in the
routes). It exists only to break the import cycle between the two
modules: server.py imports api.py to register the routes, so api.py
cannot import server.py back.

`_runtime` is None from process start until the credential vault
(src/security/env_vault.py) is unlocked: the web app now starts LOCKED
and POST /api/unlock builds and assigns the real AppRuntime once the
browser's lock screen posts the right password (see web/api.py) — the
desktop GUI (src/main.py) still unlocks it before ever calling
create_web_app-equivalent code, so for it `_runtime` is only ever set
once, same as before.

get_runtime() used to treat "_runtime is not None" as the entire
authorization check — i.e. "has anyone, ever, unlocked this process",
not "did THIS request come from someone who knows the password". That
was fine for a single trusted machine but meant that port-forwarding
the web UI let anyone who reached it in, with zero credentials, the
moment the real owner unlocked it once. It now also requires the
request to carry a valid session cookie (sessions.py), issued only by
a successful POST /api/unlock.
"""

from fastapi import Request

_runtime = None


def set_runtime(runtime) -> None:
    """Called by server.py at startup (possibly with None, for a locked
    start) and again by the /api/unlock route once the vault opens."""
    global _runtime
    _runtime = runtime


def peek_runtime():
    """The current AppRuntime, or None while the vault is still locked.

    For lifecycle code that must tolerate "not created yet" instead of
    raising: server.py's lifespan shutdown (nothing to stop if the app
    was closed before ever unlocking) and routes that must work even
    when locked (GET /api/lock, GET /api/i18n — the lock screen itself
    needs translations)."""
    return _runtime


def get_runtime(request: Request):
    """Dependency of routes that need the live backend. Raises a
    translatable ApiError — 423 while the vault has not been unlocked
    yet (the browser shows this as a normal error instead of a crash,
    which matters now that reaching these routes before POST
    /api/unlock is a real, if unusual, case, not just a programming
    error), or 401 when the vault IS unlocked but this particular
    request carries no valid session cookie (see sessions.py) — i.e. it
    never itself went through POST /api/unlock with the right
    password."""
    from .errors import ApiError

    if _runtime is None:
        raise ApiError(423, "api.locked")

    from . import sessions

    if not sessions.touch(request.cookies.get(sessions.COOKIE_NAME)):
        raise ApiError(401, "api.unauthorized")

    return _runtime
