"""Tests for SmartMeter Emulator coordinator."""
from unittest.mock import MagicMock, patch


def test_coordinator_creation():
    """Test coordinator can be created."""
    with patch("custom_components.growatt_smartmeter_emulator.coordinator._LOGGER"):
        from custom_components.growatt_smartmeter_emulator.coordinator import (
            SmartMeterEmulatorCoordinator,
        )
        from custom_components.growatt_smartmeter_emulator.modbus_server import ModbusServer

        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"
        entry.data = {
            "power_sensor": "sensor.power",
            "voltage_sensor": "sensor.voltage",
            "current_sensor": "sensor.current",
            "frequency_sensor": "sensor.frequency",
        }

        modbus_server = MagicMock(spec=ModbusServer)
        coordinator = SmartMeterEmulatorCoordinator(hass, entry, modbus_server)
        assert coordinator is not None
        assert coordinator.modbus_server == modbus_server
        assert len(coordinator.sensors_map) == 4
