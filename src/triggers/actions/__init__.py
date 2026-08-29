"""
triggers.actions

Package of trigger action backends. Importing this package registers
every built-in one (see registry.py). http_webhook needs no optional
dependency; mqtt/modbus_tcp do, so they are guarded — a machine missing
paho-mqtt/pymodbus simply doesn't offer that action type, the rest of
the application keeps working normally.
"""

from . import http_webhook  # noqa: F401

try:
    from . import mqtt  # noqa: F401
except ImportError:
    pass

try:
    from . import modbus_tcp  # noqa: F401
except ImportError:
    pass
