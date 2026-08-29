from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("pymodbus")

from notify.flag import Flag
from triggers.actions import modbus_tcp


def test_writes_register_and_closes_connection(monkeypatch):
    client = MagicMock()
    client.connect.return_value = True

    monkeypatch.setattr(modbus_tcp, "ModbusTcpClient", lambda host, port: client)

    modbus_tcp.execute({"host": "192.168.1.60", "register": 100, "value": 1}, Flag(camera_id="c", task_type="t", flag_id="f"))

    client.connect.assert_called_once()
    client.write_register.assert_called_once_with(100, 1)
    client.close.assert_called_once()


def test_uses_default_port_when_not_given(monkeypatch):
    seen = {}

    def _fake_client(host, port):
        seen["host"], seen["port"] = host, port
        return SimpleNamespace(connect=lambda: True, write_register=lambda *a: None, close=lambda: None)

    monkeypatch.setattr(modbus_tcp, "ModbusTcpClient", _fake_client)

    modbus_tcp.execute({"host": "h", "register": 1, "value": 0}, Flag(camera_id="c", task_type="t", flag_id="f"))

    assert seen == {"host": "h", "port": 502}


def test_raises_when_connection_fails(monkeypatch):
    client = MagicMock()
    client.connect.return_value = False
    monkeypatch.setattr(modbus_tcp, "ModbusTcpClient", lambda host, port: client)

    with pytest.raises(ConnectionError):
        modbus_tcp.execute({"host": "h", "register": 1, "value": 0}, Flag(camera_id="c", task_type="t", flag_id="f"))
