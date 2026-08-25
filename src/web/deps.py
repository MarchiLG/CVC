"""
deps.py

Reference to the live AppRuntime, shared between server.py (which
creates the runtime) and api.py (which consumes it in the routes).

It exists only to break the import cycle between the two modules:
server.py imports api.py to register the routes, so api.py cannot
import server.py back.
"""

_runtime = None


def set_runtime(runtime) -> None:
    """Called once by server.py at startup."""
    global _runtime
    _runtime = runtime


def get_runtime():
    """Dependency of the routes in api.py. Raises RuntimeError if the
    routes are called before startup — which would only happen through a
    programming error, never in normal use."""
    if _runtime is None:
        raise RuntimeError("AppRuntime has not been initialized yet (see web/server.py).")
    return _runtime
