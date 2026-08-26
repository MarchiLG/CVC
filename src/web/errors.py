"""
errors.py

API errors that carry a translation code alongside the message.

A plain HTTPException only serializes `detail`, so the browser would
receive an English sentence it cannot translate. ApiError adds a stable
`code` (one of the "api.*"/"calibration.*" keys in src/i18n.py) and the
handler below puts it in the JSON body:

    {"detail": "Camera not found.", "code": "api.camera_not_found"}

The front-end translates `code` and falls back to `detail` when it does
not recognize it (see web/static/js/api.js), so a new error added on
the server is never invisible — at worst it shows in English.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from i18n import DEFAULT_LANGUAGE, t


class ApiError(HTTPException):
    """HTTP error whose message the interfaces can translate.

    `detail` is filled from the English catalog so that logs, `curl` and
    /api/docs stay readable without any client-side translation.
    """

    def __init__(self, status_code: int, code: str, **params):
        super().__init__(status_code=status_code, detail=t(code, DEFAULT_LANGUAGE, **params))
        self.code = code
        self.params = params


def register_error_handler(app: FastAPI) -> None:
    """Makes every HTTPException answer in the same shape.

    Errors raised by FastAPI itself (a 404 from an unknown route, for
    instance) go through here too — they simply have no `code`, and the
    front-end shows their `detail` as-is.
    """

    @app.exception_handler(HTTPException)
    async def _handle(_request: Request, exc: HTTPException) -> JSONResponse:
        body: dict = {"detail": exc.detail}
        code = getattr(exc, "code", None)
        if code:
            body["code"] = code
            body["params"] = getattr(exc, "params", {})

        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)
