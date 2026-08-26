"""
web

The web interface (HTML/CSS/JS) of the application: a local FastAPI
server that serves the static UI in static/ and exposes the backend
(the same bootstrap.AppRuntime used by the Qt GUI) as a REST API +
MJPEG streaming.

    server.py     builds the FastAPI app, serves the static files and
                  drives the backend lifecycle
    api.py        REST routes: cameras, tasks, calibration, alerts,
                  employees
    streaming.py  live MJPEG video and JPEG snapshots
    errors.py     API errors carrying a translation code
"""
