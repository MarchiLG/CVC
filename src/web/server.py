"""
server.py

Builds the FastAPI app that serves the web interface:

    /            -> static/index.html (the whole UI)
    /static/*    -> CSS and JS (edit these files to change the looks)
    /api/*       -> routes in api.py

Lifecycle: unlike the desktop GUI (src/main.py), which unlocks the
credential vault on the terminal BEFORE anything else, the web app
starts LOCKED — no AppRuntime, no camera threads — so it can be opened
by double-clicking run-html.sh with no terminal to type a password
into. The browser's lock screen posts the password to POST
/api/unlock (src/web/api.py), which builds bootstrap.AppRuntime and
starts it from there; see src/security/env_vault.py for the encryption
itself. `runtime=` below skips all of that (used by tests, which pass
an already-"unlocked" fake).

This module is not meant to be run directly — use src/main_web.py (or
./run-html.sh), which resolves sys.path and starts uvicorn.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bootstrap import AppRuntime

from .api import router as api_router
from .deps import peek_runtime, set_runtime
from .errors import register_error_handler

logger = logging.getLogger("cv_central.web.server")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
INDEX_PATH = os.path.join(STATIC_DIR, "index.html")


class _NoCacheStaticFiles(StaticFiles):
    """Same as StaticFiles, but never lets the browser cache a response
    without asking again.

    Starlette's StaticFiles sets ETag/Last-Modified but no Cache-Control,
    which lets a browser silently keep serving an old app.js/CSS file —
    via its own heuristic freshness, with no revalidation request at all
    — after these files change on disk. That is exactly what made a
    freshly-added feature's JS never load once: the browser kept an old
    cached app.js while `/` (below) always served the new index.html,
    and the mismatch between the two showed up as a stray error instead
    of the new behavior. `/` already forces no-store for the same
    reason; this extends that to everything under /static.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store"
        return response


def create_web_app(runtime: AppRuntime | None = None, start_backend: bool = True) -> FastAPI:
    """Creates the FastAPI app.

    `runtime` may be injected (tests pass a fake runtime, already
    "unlocked"); when None, the app starts LOCKED and AppRuntime is
    only created once POST /api/unlock succeeds. `start_backend=False`
    never starts any thread, even for a provided `runtime` — useful for
    testing the routes without opening real cameras.
    """
    set_runtime(runtime)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Everything before the `yield` runs when the server starts;
        # everything after it, when the server goes down (Ctrl+C, or
        # the UI's Exit button setting uvicorn_server.should_exit — see
        # POST /api/shutdown in api.py). `runtime` here is the value
        # captured at create_web_app() call time (possibly None, for a
        # locked start) — peek_runtime() re-reads it below because
        # /api/unlock may have replaced it since.
        if start_backend and runtime is not None:
            runtime.start()
        yield
        if start_backend:
            current = peek_runtime()
            if current is not None:
                current.stop()

    app = FastAPI(
        lifespan=lifespan,
        title="Computer Vision Central",
        description="Web interface of Computer Vision Central.",
        version="1.0.0",
        docs_url="/api/docs",       # interactive route documentation
        redoc_url=None,
    )
    app.state.start_backend = start_backend
    # Set by main_web.py right after this returns, so POST /api/shutdown
    # can ask uvicorn to stop serving (see api.py's _trigger_shutdown).
    app.state.uvicorn_server = None

    register_error_handler(app)
    app.include_router(api_router)
    app.mount("/static", _NoCacheStaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        """Single-page app: all routing between tabs happens in the
        browser (static/js/app.js), without reloading the page. This
        includes the lock screen — it is part of the same HTML/JS, not
        a separate page."""
        return FileResponse(INDEX_PATH, headers={"Cache-Control": "no-store"})

    return app
