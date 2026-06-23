"""Tests for SmartMeter Emulator config flow."""
import pytest
from unittest.mock import MagicMock

from custom_components.growatt_smartmeter_emulator.config_flow import (
    STEP_DATA_SCHEMA,
    validate_input,
)


def test_config_flow_schema():
    """Test config flow schema."""
    assert STEP_DATA_SCHEMA is not None


def test_validate_input_valid():
    """Test validation with valid input."""
    data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 1,
        "power_sensor": "sensor.power",
        "voltage_sensor": "sensor.voltage",
    }

    import asyncio

    async def run_test():
        result = await validate_input(MagicMock(), data)
        assert result["title"] == "Growatt Meter Emulator"

    asyncio.run(run_test())


def test_validate_input_missing_power_sensor():
    """Test validation with missing power sensor."""
    data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 1,
    }

    import asyncio

    async def run_test():
        with pytest.raises(Exception):
            await validate_input(MagicMock(), data)

    asyncio.run(run_test())


def test_validate_input_invalid_port():
    """Test validation with invalid port."""
    data = {
        "host": "0.0.0.0",
        "port": 70000,
        "slave": 1,
        "power_sensor": "sensor.power",
    }

    import asyncio

    async def run_test():
        with pytest.raises(Exception):
            await validate_input(MagicMock(), data)

    asyncio.run(run_test())


def test_validate_input_invalid_slave():
    """Test validation with invalid slave."""
    data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 300,
        "power_sensor": "sensor.power",
    }

    import asyncio

    async def run_test():
        with pytest.raises(Exception):
            await validate_input(MagicMock(), data)

    asyncio.run(run_test())


def test_validate_input_frequency_default():
    """Test validation with default frequency (50 Hz)."""
    data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 1,
        "power_sensor": "sensor.test_power",
    }

    import asyncio

    async def run_test():
        result = await validate_input(MagicMock(), data)
        assert result["title"] == "Growatt Meter Emulator"
        # Default frequency should be 50
        assert data.get("frequency", 50) == 50

    asyncio.run(run_test())


def test_validate_input_frequency_custom():
    """Test validation with custom frequency (60 Hz)."""
    data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 1,
        "power_sensor": "sensor.test_power",
        "frequency": 60,
    }

    import asyncio

    async def run_test():
        result = await validate_input(MagicMock(), data)
        assert result["title"] == "Growatt Meter Emulator"
        # Custom frequency should be preserved
        assert data.get("frequency") == 60

    asyncio.run(run_test())


def test_validate_input_entity_selector():
    """Test validation with entity selectors for power, voltage, and current sensors."""
    data = {
        "host": "0.0.0.0",
        "port": 502,
        "slave": 1,
        "power_sensor": "sensor.test_power",
        "voltage_sensor": "sensor.test_voltage",
        "current_sensor": "sensor.test_current",
    }

    import asyncio

    async def run_test():
        result = await validate_input(MagicMock(), data)
        assert result["title"] == "Growatt Meter Emulator"
        # Check if entity IDs are preserved
        assert data["power_sensor"] == "sensor.test_power"
        assert data["voltage_sensor"] == "sensor.test_voltage"
        assert data["current_sensor"] == "sensor.test_current"

    asyncio.run(run_test())


def test_validate_input_invalid_host():
    """Test validation with empty host."""
    data = {
        "host": "",
        "port": 502,
        "slave": 1,
        "power_sensor": "sensor.power",
    }

    import asyncio

    async def run_test():
        with pytest.raises(Exception):
            await validate_input(MagicMock(), data)

    asyncio.run(run_test())
