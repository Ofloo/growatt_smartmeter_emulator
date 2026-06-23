"""Tests for SmartMeter Emulator coordinator."""
from unittest.mock import MagicMock, patch

from custom_components.growatt_meter_emulator.coordinator import SensorValue


def test_sensor_value_dataclass():
    """Test SensorValue dataclass."""
    value = SensorValue(
        value=100.0,
        entity_id="sensor.test",
        last_updated=1234567890,
    )

    assert value.value == 100.0
    assert value.entity_id == "sensor.test"
    assert value.last_updated == 1234567890


def test_coordinator_creation():
    """Test coordinator can be created."""
    with patch("custom_components.growatt_meter_emulator.coordinator.DataUpdateCoordinator"):
        with patch("custom_components.growatt_meter_emulator.coordinator._LOGGER"):
            from custom_components.growatt_meter_emulator.coordinator import (
                SmartMeterEmulatorCoordinator,
            )

            hass = MagicMock()
            entry = MagicMock()
            entry.entry_id = "test_entry"

            coordinator = SmartMeterEmulatorCoordinator(hass, entry)
            assert coordinator is not None
