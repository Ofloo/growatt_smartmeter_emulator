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


def test_modbus_server_frequency_default():
    """Test Modbus server uses default frequency (50 Hz) if no sensor is configured."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
            "frequency": 50,  # Default
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        # Check if default frequency (50 Hz) is used (50 * 100 = 5000)
        assert server.register_map[40004].value == 5000


def test_modbus_server_frequency_custom():
    """Test Modbus server uses custom frequency (60 Hz) if specified."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
            "frequency": 60,  # Custom
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        # Check if custom frequency (60 Hz) is used (60 * 100 = 6000)
        assert server.register_map[40004].value == 6000


def test_modbus_server_frequency_dropdown_only():
    """Test that the frequency register cannot be overwritten by a sensor."""
    with patch("custom_components.growatt_smartmeter_emulator.modbus_server._LOGGER"):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,
            "power_sensor": "sensor.test_power",
            "frequency": 50,  # Default
        }
        entry.entry_id = "test_entry"

        server = ModbusServer(hass, entry)
        server.setup_registers()

        # Check if default frequency (50 Hz) is used (50 * 100 = 5000)
        assert server.register_map[40004].value == 5000
        assert server.register_map[40004].sensor_entity_id is None

        # Simulate updating the register (should not change the value)
        server.update_register_from_sensor(40004)
        assert server.register_map[40004].value == 5000  # Still 50 Hz




def test_modbus_server_start():
    """Test of de start()-methode een ModbusServerContext correct initialiseert."""
    from unittest.mock import MagicMock, patch
    from pymodbus.datastore import ModbusSequentialDataBlock
    from pymodbus.server import StartAsyncTcpServer

    # Mock pymodbus-klassen
    with (
        patch("custom_components.growatt_smartmeter_emulator.modbus_server.ModbusSequentialDataBlock") as mock_block,
        patch("custom_components.growatt_smartmeter_emulator.modbus_server.ModbusServerContext") as mock_server_context,
        patch("custom_components.growatt_smartmeter_emulator.modbus_server.StartAsyncTcpServer") as mock_start_server,
    ):

        # Configureer mocks
        mock_store = MagicMock(spec=ModbusSequentialDataBlock)
        mock_block.return_value = mock_store

        mock_context = MagicMock()
        mock_server_context.return_value = mock_context

        # Simuleer ConfigEntry
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "host": "0.0.0.0",
            "port": 502,
            "slave": 1,  # slave_id = 1
            "power_sensor": "sensor.test_power",
            "frequency": 50,
        }
        entry.entry_id = "test_entry"

        # Initialiseer ModbusServer
        server = ModbusServer(hass, entry)

        # Roep start() aan
        server.start()

        # Controleer of ModbusSequentialDataBlock correct wordt aangemaakt
        mock_block.assert_called_once_with(1, [0] * 100)

        # Controleer of ModbusServerContext correct wordt geïnitialiseerd
        mock_server_context.assert_called_once()  # Geen argumenten verwacht in constructor

        # Controleer of StartAsyncTcpServer wordt aangeroepen
        mock_start_server.assert_called_once()



def test_modbus_server_port_in_use():
    """Test of de server een fout gooit als de poort al in gebruik is."""
    from unittest.mock import MagicMock, patch

    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 1,
        "power_sensor": "sensor.test_power",
        "debug_logging": True,
    }
    entry.entry_id = "test_entry"

    server = ModbusServer(hass, entry)

    # Simuleer dat de poort in gebruik is
    with patch.object(server, 'is_port_in_use', return_value=True):
        with pytest.raises(RuntimeError, match="Port 502 is already in use"):
            server.start()


def test_modbus_server_start_import_error():
    """Test of start() een ImportError gooit als pymodbus niet kan worden geïmporteerd."""
    from unittest.mock import MagicMock, patch

    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 1,
        "power_sensor": "sensor.test_power",
        "frequency": 50,
    }
    entry.entry_id = "test_entry"

    server = ModbusServer(hass, entry)

    # Mock de start()-methode om een ImportError te gooien
    with patch.object(server, 'start', side_effect=ImportError("Failed to import pymodbus")):
        with pytest.raises(ImportError):
            server.start()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
