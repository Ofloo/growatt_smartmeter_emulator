"""Tests for SmartMeter Emulator modbus server."""
import pytest
from unittest.mock import MagicMock, patch

from custom_components.growatt_smartmeter_emulator.modbus_server import (
    ModbusServer,
    RegisterMapping,
)


def test_register_mapping():
    """Test RegisterMapping dataclass."""
    mapping = RegisterMapping(
        address=40001,
        value=1500,
        sensor_entity_id="sensor.test_power",
        scale=1.0,
        signed=True,
        description="Test register",
    )

    assert mapping.address == 40001
    assert mapping.value == 1500
    assert mapping.sensor_entity_id == "sensor.test_power"
    assert mapping.scale == 1.0
    assert mapping.signed is True
    assert mapping.description == "Test register"


def test_modbus_server_init():
    """Test Modbus server initialization."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)

        assert server.host == "0.0.0.0"
        assert server.port == 502
        assert server.slave_id == 1
        assert server.register_map == {}
        assert server.server is None
        assert server.running is False


def test_modbus_server_setup_registers():
    """Test register setup."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
            "voltage_sensor": "sensor.test_voltage",
            "current_sensor": "sensor.test_current",
            "frequency_sensor": "sensor.test_frequency",
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        assert len(server.register_map) >= 4
        assert 40001 in server.register_map
        assert 40002 in server.register_map
        assert 40003 in server.register_map
        assert 40004 in server.register_map

        reg = server.register_map[40001]
        assert reg.address == 40001
        assert reg.signed is True


def test_modbus_server_get_register():
    """Test getting register value."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        value = server.get_register(40001)
        assert value is not None

        value = server.get_register(99999)
        assert value is None


def test_modbus_server_update_register_from_sensor():
    """Test updating register from sensor."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        state = MagicMock()
        state.state = "1500"
        hass.states.get.return_value = state

        result = server.update_register_from_sensor(40001)
        assert result is True
        assert server.register_map[40001].value == 1500


def test_modbus_server_update_register_from_sensor_unavailable():
    """Test updating register with unavailable sensor."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        state = MagicMock()
        state.state = "unavailable"
        hass.states.get.return_value = state

        result = server.update_register_from_sensor(40001)
        assert result is False
        assert server.register_map[40001].value == 0


def test_modbus_server_bounds_checking():
    """Test bounds checking."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        state = MagicMock()
        state.state = "100000"
        hass.states.get.return_value = state

        result = server.update_register_from_sensor(40001)
        assert result is True
        assert server.register_map[40001].value == 32767

        state.state = "-100000"
        result = server.update_register_from_sensor(40001)
        assert result is True
        assert server.register_map[40001].value == -32768


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
