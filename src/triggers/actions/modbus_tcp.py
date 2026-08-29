"""
modbus_tcp.py

Writes a single holding register over Modbus TCP — a standard, widely
supported way to reach PLCs and microcontrollers (including an ESP32
running a Modbus TCP server). Optional dependency (pymodbus) — this
module fails to import without it, which is exactly what makes it
disappear from available_types() (see triggers/actions/__init__.py's
guard).

target expected in Triggers.yaml:
    host: str (required)
    port: int (defaults to 502)
    register: int (required) — holding register address
    value: int (required) — value to write
"""

from pymodbus.client import ModbusTcpClient

from notify.flag import Flag

from .registry import register


@register("modbus_tcp")
def execute(target: dict, flag: Flag) -> None:
    client = ModbusTcpClient(target["host"], port=target.get("port", 502))
    if not client.connect():
        raise ConnectionError(f"Could not connect to Modbus TCP device at {target['host']}:{target.get('port', 502)}")
    try:
        client.write_register(target["register"], target["value"])
    finally:
        client.close()
