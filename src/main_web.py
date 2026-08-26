"""
main_web.py

Entry point of the WEB interface (HTML/CSS/JS in the browser). Started
through ./run-html.sh — including by just double-clicking it, which is
exactly why this file does NOT ask for the credential-store password on
the terminal (there may not be one visible/attached): the server starts
LOCKED and the browser's lock screen unlocks it over the API (POST
/api/unlock in web/api.py) instead. See src/security/env_vault.py for
the encryption itself, and web/server.py's create_web_app() for how a
locked start works. The desktop GUI (src/main.py) is unaffected — it
still prompts on the terminal, since it always has one.

It starts the same backend as the desktop GUI (bootstrap.AppRuntime:
cameras, YOLO inference, notifications, LLM narrator) and exposes it
through a local HTTP server instead of Qt windows. Neither interface
replaces the other — for the desktop version, without a browser, use
src/main.py / ./run.sh.

Usage:
    python src/main_web.py [--host 0.0.0.0] [--port 8000] [--no-browser]

By default it listens on 127.0.0.1 only (this machine). Use
--host 0.0.0.0 to reach it from another device on the network — but note
there is no authentication once unlocked: anyone who can reach the port
while the application is running sees the cameras.
"""

import argparse
import logging
import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

import uvicorn

from web.server import create_web_app

logger = logging.getLogger("cv_central.main_web")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Computer Vision Central — web interface.")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"Listen address (default: {DEFAULT_HOST}; use 0.0.0.0 to expose on the network).")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"HTTP port (default: {DEFAULT_PORT}).")
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not open the browser automatically.")
    return parser.parse_args(argv)


def _open_browser_when_ready(url: str, delay: float = 1.5):
    """Opens the browser on a separate thread, with a small delay so
    the server is already accepting connections when the tab loads."""
    threading.Timer(delay, lambda: webbrowser.open(url)).start()


def main(argv=None):
    args = parse_args(argv)

    app = create_web_app()

    # On 0.0.0.0 the local browser still needs a reachable host name.
    display_host = "localhost" if args.host in ("0.0.0.0", "127.0.0.1") else args.host
    url = f"http://{display_host}:{args.port}"

    logger.info("Web interface at %s — enter the credential-store password there.", url)
    logger.info("Stop it from the browser's Exit button, or Ctrl+C here.")
    if not args.no_browser:
        _open_browser_when_ready(url)

    # uvicorn.Server (rather than the uvicorn.run() shortcut) so the
    # "Exit application" button can stop it from inside a request: POST
    # /api/shutdown sets server.should_exit = True, which uvicorn polls
    # in its own serve loop — the exact same mechanism Ctrl+C uses via
    # its signal handler, still installed below by server.run() too.
    config = uvicorn.Config(app, host=args.host, port=args.port, log_level="warning")
    server = uvicorn.Server(config)
    app.state.uvicorn_server = server
    server.run()


if __name__ == "__main__":
    main()
