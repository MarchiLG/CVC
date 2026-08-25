"""
server.py

Builds the FastAPI app that serves the web interface:

    /            -> static/index.html (the whole UI)
    /static/*    -> CSS and JS (edit these files to change the looks)
    /api/*       -> routes in api.py

Lifecycle: the backend (bootstrap.AppRuntime — cameras, inference,
notifications, narrator) starts together with the server on the startup
event and is shut down on shutdown. It is the same backend as the Qt
GUI; only the presentation layer differs.

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
from .deps import set_runtime
from .errors import register_error_handler

logger = logging.getLogger("cv_central.web.server")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
INDEX_PATH = os.path.join(STATIC_DIR, "index.html")


def create_web_app(runtime: AppRuntime | None = None, start_backend: bool = True) -> FastAPI:
    """Creates the FastAPI app.

    `runtime` may be injected (tests pass a fake runtime); when None,
    one is assembled from the default YAML files. `start_backend=False`
    builds the app without starting any thread — useful for testing the
    routes without opening real cameras.
    """
    runtime = runtime or AppRuntime.create()
    set_runtime(runtime)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Everything before the `yield` runs when the server starts;
        # everything after it, when the server goes down (Ctrl+C). This
        # is where the capture/inference threads begin and end.
        if start_backend:
            runtime.start()
        yield
        if start_backend:
            runtime.stop()

    app = FastAPI(
        lifespan=lifespan,
        title="Computer Vision Central",
        description="Web interface of Computer Vision Central.",
        version="1.0.0",
        docs_url="/api/docs",       # interactive route documentation
        redoc_url=None,
    )
    app.state.runtime = runtime

    register_error_handler(app)
    app.include_router(api_router)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        """Single-page app: all routing between tabs happens in the
        browser (static/js/app.js), without reloading the page."""
        return FileResponse(INDEX_PATH, headers={"Cache-Control": "no-store"})

    return app
